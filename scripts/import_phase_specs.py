#!/usr/bin/env python3
"""
Import Phase Spec PDFs from JobTread into the database.
Downloads PDFs, extracts text, parses into sections/items, and stores in DB.
"""

import os
import sys
import re
import logging
import requests
import tempfile
from typing import List, Dict, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pdfplumber
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '31.97.137.221'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'dbname': os.getenv('DB_NAME', 'takeoff_pricing_db'),
    'user': os.getenv('DB_USER', 'Jon'),
    'password': os.getenv('DB_PASSWORD', 'Transplant4real')
}

JOBTREAD_CONFIG = {
    'api_key': os.getenv('JOBTREAD_API_KEY', '22T9iRwLuuk7r7Q8Q4bkvrcW86EVnMUwN5'),
    'base_url': os.getenv('JOBTREAD_API_BASE_URL', 'https://api.jobtread.com/pave'),
    'organization_id': os.getenv('JOBTREAD_ORGANIZATION_ID', '22NQrV725Q3z')
}

PHASE_SPECS_JOB_ID = os.getenv('PHASE_SPECS_JOB_ID', '22PAFPENQXz5')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def jobtread_query(query: dict) -> dict:
    """Execute a Pave query against JobTread API"""
    if '$' not in query:
        query['$'] = {}
    query['$']['grantKey'] = JOBTREAD_CONFIG['api_key']

    response = requests.post(
        JOBTREAD_CONFIG['base_url'],
        json={'query': query},
        headers={'Content-Type': 'application/json'}
    )
    response.raise_for_status()
    return response.json()


def get_phase_spec_files() -> List[Dict]:
    """Get all PDF files from the Phase Specs job in JobTread"""
    query = {
        'job': {
            '$': {'id': PHASE_SPECS_JOB_ID},
            'files': {
                '$': {'size': 100},
                'nodes': {
                    'id': {},
                    'name': {},
                    'url': {},
                    'size': {},
                    'type': {}
                }
            }
        }
    }

    result = jobtread_query(query)
    files = result.get('job', {}).get('files', {}).get('nodes', [])

    # Filter to PDFs only
    pdf_files = [f for f in files if f.get('type') == 'application/pdf']

    # Sort by phase code
    def get_sort_key(f):
        match = re.search(r'Phase\s+(\d+)-(\d+)', f.get('name', ''))
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (999, 999)

    pdf_files.sort(key=get_sort_key)
    return pdf_files


def download_pdf(url: str) -> str:
    """Download PDF to temp file and return path"""
    response = requests.get(url)
    response.raise_for_status()

    fd, path = tempfile.mkstemp(suffix='.pdf')
    with os.fdopen(fd, 'wb') as f:
        f.write(response.content)

    return path


def extract_pdf_text(pdf_path: str) -> Tuple[str, int]:
    """Extract all text from PDF, return (text, page_count)"""
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text, len(pdf.pages)


def parse_phase_info(filename: str) -> Tuple[str, str]:
    """Extract phase code and name from filename"""
    # Pattern: "Phase 30-500 ALARM SYSTEM.pdf"
    match = re.search(r'Phase\s+(\d+-\d+)\s+(.+?)\.pdf', filename, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2).strip()
    return None, filename.replace('.pdf', '')


def parse_sections_and_items(text: str) -> List[Dict]:
    """Parse PDF text into sections and items"""
    sections = []
    current_section = None
    current_items = []

    # Known section headers
    section_patterns = [
        r'^(Bids for Work)',
        r'^(Work Requirements)',
        r'^(Administrative and Contractual Requirements)',
        r'^(Administrative Requirements)',
        r'^(Contractual Requirements)',
        r'^(Safety Requirements)',
        r'^(Quality Requirements)',
        r'^(Material Requirements)',
        r'^(Installation Requirements)',
        r'^(Cleanup Requirements)'
    ]
    section_regex = '|'.join(section_patterns)

    lines = text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Check for section header
        section_match = re.match(section_regex, line, re.IGNORECASE)
        if section_match:
            # Save previous section
            if current_section and current_items:
                sections.append({
                    'name': current_section,
                    'items': current_items
                })

            current_section = section_match.group(0)
            current_items = []
            i += 1
            continue

        # Check for numbered item (e.g., "1.", "2.", "12.")
        item_match = re.match(r'^(\d+)\.\s+(.+)', line)
        if item_match and current_section:
            item_num = item_match.group(1)
            item_text = item_match.group(2)

            # Collect continuation lines (don't start with number and not a section)
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()

                # Stop if new numbered item
                if re.match(r'^\d+\.\s+', next_line):
                    break
                # Stop if section header
                if re.match(section_regex, next_line, re.IGNORECASE):
                    break
                # Stop if page footer (date pattern)
                if re.match(r'^\d+-\d+\s+\w+\s+\d{4}', next_line):
                    i += 1
                    continue
                # Skip empty lines at boundaries
                if not next_line:
                    i += 1
                    continue

                item_text += " " + next_line
                i += 1

            # Clean up the text
            item_text = re.sub(r'\s+', ' ', item_text).strip()

            current_items.append({
                'number': item_num,
                'text': item_text
            })
            continue

        # Check for bullet point items (• or -)
        bullet_match = re.match(r'^[•\-]\s+(.+)', line)
        if bullet_match and current_section and current_items:
            # Add as sub-item to last numbered item
            bullet_text = bullet_match.group(1)
            if current_items:
                current_items[-1]['text'] += f"\n• {bullet_text}"
            i += 1
            continue

        i += 1

    # Save last section
    if current_section and current_items:
        sections.append({
            'name': current_section,
            'items': current_items
        })

    return sections


def generate_summary(phase_name: str, sections: List[Dict]) -> str:
    """Generate a brief summary of the document"""
    total_items = sum(len(s['items']) for s in sections)
    section_names = [s['name'] for s in sections]

    summary = f"{phase_name} specifications covering {total_items} requirements"
    if section_names:
        summary += f" across sections: {', '.join(section_names[:3])}"
        if len(section_names) > 3:
            summary += f", and {len(section_names) - 3} more"

    return summary


def import_to_database(conn, file_info: Dict, page_count: int, sections: List[Dict]):
    """Import parsed content into database"""
    cursor = conn.cursor()

    phase_code, phase_name = parse_phase_info(file_info['name'])
    if not phase_code:
        logger.warning(f"Could not parse phase code from: {file_info['name']}")
        return False

    full_title = f"Phase {phase_code} {phase_name}"
    summary = generate_summary(phase_name, sections)

    try:
        # Check if already exists
        cursor.execute("""
            SELECT document_id FROM takeoff.isms_spec_documents WHERE phase_code = %s
        """, (phase_code,))
        existing = cursor.fetchone()

        if existing:
            # Update existing
            cursor.execute("""
                UPDATE takeoff.isms_spec_documents
                SET phase_name = %s, full_title = %s, jobtread_file_id = %s,
                    jobtread_url = %s, file_size = %s, page_count = %s,
                    summary = %s, updated_at = CURRENT_TIMESTAMP
                WHERE phase_code = %s
                RETURNING document_id
            """, (phase_name, full_title, file_info['id'], file_info['url'],
                  file_info.get('size'), page_count, summary, phase_code))
            document_id = cursor.fetchone()[0]

            # Delete old sections/items
            cursor.execute("""
                DELETE FROM takeoff.isms_spec_sections WHERE document_id = %s
            """, (document_id,))
        else:
            # Insert new document
            cursor.execute("""
                INSERT INTO takeoff.isms_spec_documents
                (phase_code, phase_name, full_title, jobtread_file_id, jobtread_url,
                 file_size, page_count, summary, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING document_id
            """, (phase_code, phase_name, full_title, file_info['id'], file_info['url'],
                  file_info.get('size'), page_count, summary,
                  int(phase_code.replace('-', ''))))
            document_id = cursor.fetchone()[0]

        # Insert sections and items
        for section_order, section in enumerate(sections, 1):
            cursor.execute("""
                INSERT INTO takeoff.isms_spec_sections
                (document_id, section_name, section_order)
                VALUES (%s, %s, %s)
                RETURNING section_id
            """, (document_id, section['name'], section_order))
            section_id = cursor.fetchone()[0]

            # Insert items
            for item in section['items']:
                # Convert text to simple HTML
                item_html = item['text'].replace('\n', '<br>')
                item_html = f"<p>{item_html}</p>"

                cursor.execute("""
                    INSERT INTO takeoff.isms_spec_items
                    (section_id, item_number, item_text, item_html)
                    VALUES (%s, %s, %s, %s)
                """, (section_id, item['number'], item['text'], item_html))

        conn.commit()
        logger.info(f"Imported: {full_title} ({len(sections)} sections)")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Error importing {file_info['name']}: {e}")
        return False


def main():
    """Main import process"""
    logger.info("Starting Phase Specs import...")

    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        # Get files from JobTread
        logger.info("Fetching files from JobTread...")
        files = get_phase_spec_files()
        logger.info(f"Found {len(files)} PDF files")

        success_count = 0
        error_count = 0

        for file_info in files:
            try:
                logger.info(f"Processing: {file_info['name']}")

                # Download PDF
                pdf_path = download_pdf(file_info['url'])

                try:
                    # Extract text
                    text, page_count = extract_pdf_text(pdf_path)

                    # Parse sections and items
                    sections = parse_sections_and_items(text)

                    if not sections:
                        logger.warning(f"No sections found in: {file_info['name']}")
                        error_count += 1
                        continue

                    # Import to database
                    if import_to_database(conn, file_info, page_count, sections):
                        success_count += 1
                    else:
                        error_count += 1

                finally:
                    # Clean up temp file
                    os.unlink(pdf_path)

            except Exception as e:
                logger.error(f"Error processing {file_info['name']}: {e}")
                error_count += 1

        logger.info(f"\nImport complete!")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Errors: {error_count}")

        # Show summary
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT COUNT(*) as doc_count FROM takeoff.isms_spec_documents
        """)
        doc_count = cursor.fetchone()['doc_count']

        cursor.execute("""
            SELECT COUNT(*) as item_count FROM takeoff.isms_spec_items
        """)
        item_count = cursor.fetchone()['item_count']

        logger.info(f"\nDatabase now contains:")
        logger.info(f"  Documents: {doc_count}")
        logger.info(f"  Items: {item_count}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
