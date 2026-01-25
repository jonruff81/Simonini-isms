#!/usr/bin/env python3
"""
Extract figure images from Phase Spec PDFs and store them for quick reference.

This script:
1. Downloads PDFs from JobTread
2. Extracts images from each page
3. Associates images with figure numbers found in the text
4. Saves images to static/figures/ and records in database
"""

import os
import sys
import re
import io
import hashlib
import requests
import fitz  # PyMuPDF
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'takeoff_pricing_db'),
    'user': os.getenv('DB_USER', 'Jon'),
    'password': os.getenv('DB_PASSWORD', 'Transplant4real')
}

# Output directory for figures
FIGURES_DIR = Path(__file__).parent.parent / 'app' / 'static' / 'figures'


def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def download_pdf(url: str) -> bytes:
    """Download PDF from URL"""
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def extract_figures_from_pdf(pdf_bytes: bytes, phase_code: str) -> list:
    """
    Extract figures from a PDF.

    Returns list of dicts with:
    - figure_code: The figure reference (e.g., "30-100-35-001")
    - page_number: PDF page number
    - image_data: PNG image bytes
    - width, height: Image dimensions
    """
    figures = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Pattern to match figure references
    fig_pattern = re.compile(r'Fig\.?\s*(\d{2}-\d{3}-\d{2}-\d{3})', re.IGNORECASE)

    for page_num in range(len(doc)):
        page = doc[page_num]

        # Get text from page to find figure references
        text = page.get_text()
        fig_matches = fig_pattern.findall(text)

        if not fig_matches:
            continue

        # Get images from page
        images = page.get_images(full=True)

        if not images:
            continue

        # For each figure reference found on this page
        for fig_code in fig_matches:
            # Get the largest image on the page (likely the figure)
            largest_img = None
            largest_size = 0

            for img_index, img in enumerate(images):
                xref = img[0]
                try:
                    base_img = doc.extract_image(xref)
                    if base_img:
                        img_bytes = base_img["image"]
                        img_size = len(img_bytes)

                        # Skip very small images (likely icons/logos)
                        if img_size < 5000:
                            continue

                        if img_size > largest_size:
                            largest_size = img_size
                            largest_img = {
                                'data': img_bytes,
                                'ext': base_img["ext"],
                                'width': base_img.get("width", 0),
                                'height': base_img.get("height", 0)
                            }
                except Exception as e:
                    print(f"  Error extracting image: {e}")
                    continue

            if largest_img:
                # Convert to PNG if not already
                if largest_img['ext'] != 'png':
                    try:
                        # Use fitz to convert
                        pix = fitz.Pixmap(largest_img['data'])
                        png_data = pix.tobytes("png")
                        largest_img['data'] = png_data
                        largest_img['ext'] = 'png'
                    except:
                        pass  # Keep original format

                figures.append({
                    'figure_code': fig_code,
                    'page_number': page_num + 1,
                    'image_data': largest_img['data'],
                    'width': largest_img['width'],
                    'height': largest_img['height'],
                    'ext': largest_img['ext']
                })
                print(f"  Found Fig. {fig_code} on page {page_num + 1}")

    doc.close()
    return figures


def render_page_as_image(pdf_bytes: bytes, page_num: int, dpi: int = 150) -> bytes:
    """Render a PDF page as a PNG image"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_num]

    # Render at specified DPI
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)

    png_data = pix.tobytes("png")
    doc.close()

    return png_data, pix.width, pix.height


def extract_figures_by_page(pdf_bytes: bytes, phase_code: str) -> list:
    """
    Alternative approach: render entire pages containing figure references as images.
    This ensures we capture the figure even if image extraction fails.
    """
    figures = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Pattern to match figure references
    fig_pattern = re.compile(r'Fig\.?\s*(\d{2}-\d{3}-\d{2}-\d{3})', re.IGNORECASE)

    # Track which figures we've already captured
    captured_figs = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        fig_matches = fig_pattern.findall(text)

        for fig_code in fig_matches:
            if fig_code in captured_figs:
                continue

            # Render the page as an image
            mat = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
            pix = page.get_pixmap(matrix=mat)
            png_data = pix.tobytes("png")

            figures.append({
                'figure_code': fig_code,
                'page_number': page_num + 1,
                'image_data': png_data,
                'width': pix.width,
                'height': pix.height,
                'ext': 'png'
            })

            captured_figs.add(fig_code)
            print(f"  Captured page {page_num + 1} for Fig. {fig_code}")

    doc.close()
    return figures


def save_figure(figure: dict, phase_code: str) -> str:
    """Save figure image to static directory"""
    # Create figures directory if needed
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # Create filename from figure code
    filename = f"{figure['figure_code']}.{figure['ext']}"
    filepath = FIGURES_DIR / filename

    with open(filepath, 'wb') as f:
        f.write(figure['image_data'])

    # Return relative path for web access
    return f"figures/{filename}"


def main():
    """Main extraction process"""
    print("=" * 60)
    print("Phase Spec Figure Extraction")
    print("=" * 60)

    # Ensure output directory exists
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get all documents with URLs
        cur.execute("""
            SELECT document_id, phase_code, phase_name, jobtread_url
            FROM takeoff.isms_spec_documents
            WHERE jobtread_url IS NOT NULL AND is_active = TRUE
            ORDER BY phase_code
        """)
        documents = cur.fetchall()

        print(f"\nFound {len(documents)} documents with PDF URLs")

        total_figures = 0

        for doc in documents:
            print(f"\n--- {doc['phase_code']}: {doc['phase_name']} ---")

            try:
                # Download PDF
                print(f"  Downloading PDF...")
                pdf_bytes = download_pdf(doc['jobtread_url'])
                print(f"  Downloaded {len(pdf_bytes)} bytes")

                # Try embedded image extraction first
                figures = extract_figures_from_pdf(pdf_bytes, doc['phase_code'])

                # If no figures found via image extraction, try page rendering
                if not figures:
                    print("  No embedded figures found, trying page rendering...")
                    figures = extract_figures_by_page(pdf_bytes, doc['phase_code'])

                if not figures:
                    print("  No figures found in this document")
                    continue

                # Save figures
                for fig in figures:
                    try:
                        # Save image file
                        image_path = save_figure(fig, doc['phase_code'])

                        # Insert or update database record
                        cur.execute("""
                            INSERT INTO takeoff.isms_spec_figures
                            (figure_code, phase_code, document_id, page_number, image_path, width, height)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (figure_code) DO UPDATE SET
                                image_path = EXCLUDED.image_path,
                                page_number = EXCLUDED.page_number,
                                width = EXCLUDED.width,
                                height = EXCLUDED.height
                        """, (
                            fig['figure_code'],
                            doc['phase_code'],
                            doc['document_id'],
                            fig['page_number'],
                            image_path,
                            fig['width'],
                            fig['height']
                        ))

                        total_figures += 1

                    except Exception as e:
                        print(f"  Error saving Fig. {fig['figure_code']}: {e}")

                conn.commit()

            except Exception as e:
                print(f"  Error processing document: {e}")
                continue

        print(f"\n{'=' * 60}")
        print(f"Extraction complete! Extracted {total_figures} figures")
        print(f"Figures saved to: {FIGURES_DIR}")

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
