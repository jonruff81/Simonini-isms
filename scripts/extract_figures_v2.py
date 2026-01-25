#!/usr/bin/env python3
"""
Extract actual figure images from Phase Spec PDFs.
Version 2: Extracts embedded images, not page renders.
"""

import os
import sys
import re
import requests
import fitz  # PyMuPDF
import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path

# Database connection
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'takeoff_pricing_db'),
    'user': os.getenv('DB_USER', 'Jon'),
    'password': os.getenv('DB_PASSWORD', 'Transplant4real')
}

FIGURES_DIR = Path('/app/app/static/figures')
MIN_IMAGE_SIZE = 10000  # Minimum bytes to be considered a figure (skip icons)
MIN_DIMENSION = 200     # Minimum width or height


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)


def download_pdf(url: str) -> bytes:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.content


def extract_large_images(pdf_bytes: bytes, phase_code: str) -> list:
    """
    Extract large embedded images from PDF (actual figures, not icons).
    """
    figures = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Find all figure references in the document
    fig_pattern = re.compile(r'Fig\.?\s*(\d{2}-\d{3}-\d{2}-\d{3})', re.IGNORECASE)
    all_fig_refs = set()

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        matches = fig_pattern.findall(text)
        all_fig_refs.update(matches)

    print(f"  Found figure references: {sorted(all_fig_refs)}")

    # Now extract large images from each page
    image_count = 0
    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images(full=True)

        for img_index, img in enumerate(images):
            xref = img[0]
            try:
                base_img = doc.extract_image(xref)
                if not base_img:
                    continue

                img_bytes = base_img["image"]
                width = base_img.get("width", 0)
                height = base_img.get("height", 0)
                ext = base_img.get("ext", "png")

                # Skip small images (icons, logos)
                if len(img_bytes) < MIN_IMAGE_SIZE:
                    continue
                if width < MIN_DIMENSION and height < MIN_DIMENSION:
                    continue

                image_count += 1

                # Check if this page has figure references
                page_text = page.get_text()
                page_figs = fig_pattern.findall(page_text)

                # Generate a figure code for this image
                if page_figs:
                    fig_code = page_figs[0]  # Use first figure ref on this page
                else:
                    # No figure ref on this page, check if it's a figure page (later pages)
                    # Use phase code + page number as identifier
                    fig_code = f"{phase_code}-P{page_num + 1:02d}-{img_index + 1:02d}"

                figures.append({
                    'figure_code': fig_code,
                    'page_number': page_num + 1,
                    'image_data': img_bytes,
                    'width': width,
                    'height': height,
                    'ext': ext if ext != 'jpeg' else 'jpg'
                })

                print(f"  Extracted image: {width}x{height} from page {page_num + 1} -> {fig_code}")

            except Exception as e:
                print(f"  Error extracting image: {e}")

    # If no large embedded images found, try to find figure pages and render them
    if not figures and all_fig_refs:
        print("  No large embedded images, looking for figure pages...")
        figures = extract_figure_pages(doc, phase_code, all_fig_refs)

    doc.close()
    return figures


def extract_figure_pages(doc, phase_code: str, fig_refs: set) -> list:
    """
    For PDFs where figures are drawn (not embedded images),
    find pages that contain figure labels and render those pages.
    """
    figures = []
    fig_pattern = re.compile(r'Fig\.?\s*(\d{2}-\d{3}-\d{2}-\d{3})', re.IGNORECASE)

    # Look for pages that seem to be figure pages
    # (pages with figure references AND minimal other text)
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()

        # Find figure refs on this page
        page_figs = fig_pattern.findall(text)
        if not page_figs:
            continue

        # Check if this is primarily a figure page (less text content)
        text_lines = [l.strip() for l in text.split('\n') if l.strip()]

        # Render this page as it contains figure references
        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
        pix = page.get_pixmap(matrix=mat)
        png_data = pix.tobytes("png")

        for fig_code in page_figs:
            if fig_code not in [f['figure_code'] for f in figures]:
                figures.append({
                    'figure_code': fig_code,
                    'page_number': page_num + 1,
                    'image_data': png_data,
                    'width': pix.width,
                    'height': pix.height,
                    'ext': 'png'
                })
                print(f"  Rendered page {page_num + 1} for {fig_code}")

    return figures


def save_figure(figure: dict) -> str:
    """Save figure image to static directory"""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{figure['figure_code']}.{figure['ext']}"
    filepath = FIGURES_DIR / filename

    with open(filepath, 'wb') as f:
        f.write(figure['image_data'])

    return f"figures/{filename}"


def main():
    print("=" * 60)
    print("Phase Spec Figure Extraction v2")
    print("=" * 60)

    # Clear existing figures
    if FIGURES_DIR.exists():
        for f in FIGURES_DIR.glob('*'):
            f.unlink()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_db_connection()
    cur = conn.cursor()

    # Clear existing figure records
    cur.execute("DELETE FROM takeoff.isms_spec_figures")
    conn.commit()

    try:
        cur.execute("""
            SELECT document_id, phase_code, phase_name, jobtread_url
            FROM takeoff.isms_spec_documents
            WHERE jobtread_url IS NOT NULL AND is_active = TRUE
            ORDER BY phase_code
        """)
        documents = cur.fetchall()

        print(f"\nProcessing {len(documents)} documents")

        total_figures = 0

        for doc in documents:
            print(f"\n--- {doc['phase_code']}: {doc['phase_name']} ---")

            try:
                pdf_bytes = download_pdf(doc['jobtread_url'])
                figures = extract_large_images(pdf_bytes, doc['phase_code'])

                if not figures:
                    print("  No figures extracted")
                    continue

                for fig in figures:
                    try:
                        image_path = save_figure(fig)

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
                        print(f"  Error saving {fig['figure_code']}: {e}")

                conn.commit()

            except Exception as e:
                print(f"  Error processing: {e}")

        print(f"\n{'=' * 60}")
        print(f"Extracted {total_figures} figures total")

    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
