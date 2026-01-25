#!/usr/bin/env python3
"""
Import existing rules from HTML to database.
Parses the existing Simonini-isms index.html and imports phases/rules.
"""
import re
import sys
import os
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '31.97.137.221'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'dbname': os.getenv('DB_NAME', 'takeoff_pricing_db'),
    'user': os.getenv('DB_USER', 'Jon'),
    'password': os.getenv('DB_PASSWORD', 'Transplant4real')
}


def parse_html(html_path):
    """Parse the existing HTML and extract phases/rules"""
    with open(html_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    phases = []
    sections = soup.find_all('section', class_='section')

    for idx, section in enumerate(sections):
        section_id = section.get('id', '')
        title_el = section.find(class_='section-title')
        title = title_el.get_text(strip=True) if title_el else ''

        # Parse phase code from title (e.g., "Phase 30-100: Framing")
        phase_match = re.match(r'Phase\s+(\d+-\d+):\s*(.+)', title)
        if phase_match:
            phase_code = phase_match.group(1)
            phase_name = phase_match.group(2)
        else:
            # Non-phase sections like "Simonini-isms", "10 Rules of Business", etc.
            phase_code = section_id.replace('-', '_')[:20] if section_id else f'section_{idx}'
            phase_name = title if title else f'Section {idx + 1}'

        # Get description from detail-card paragraph if exists
        description = None
        detail_card = section.find(class_='detail-card')
        if detail_card:
            first_p = detail_card.find('p')
            if first_p and not detail_card.find('ol'):
                description = first_p.get_text(strip=True)

        # Extract rules (numbered list items)
        rules = []
        ol = section.find('ol')
        if ol:
            for li_idx, li in enumerate(ol.find_all('li', recursive=False)):
                rule_text = li.get_text(strip=True)
                rule_html = str(li)
                if rule_text:
                    rules.append({
                        'rule_number': li_idx + 1,
                        'rule_text': rule_text,
                        'rule_html': rule_html
                    })

        # Also get unordered list items as rules for some sections
        if not rules:
            uls = section.find_all('ul')
            rule_number = 1
            for ul in uls:
                for li in ul.find_all('li', recursive=False):
                    rule_text = li.get_text(strip=True)
                    if rule_text:
                        rules.append({
                            'rule_number': rule_number,
                            'rule_text': rule_text,
                            'rule_html': str(li)
                        })
                        rule_number += 1

        phases.append({
            'phase_code': phase_code,
            'phase_name': phase_name,
            'description': description,
            'sort_order': idx,
            'rules': rules
        })

    return phases


def import_to_database(phases, admin_user_id=1):
    """Import parsed phases and rules into the database"""
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    total_phases = 0
    total_rules = 0

    try:
        for phase in phases:
            # Skip empty phases
            if not phase['rules']:
                print(f"  Skipping empty phase: {phase['phase_code']}")
                continue

            # Insert or update phase
            cursor.execute("""
                INSERT INTO takeoff.isms_phases
                    (phase_code, phase_name, description, sort_order, created_by)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (phase_code) DO UPDATE SET
                    phase_name = EXCLUDED.phase_name,
                    description = EXCLUDED.description,
                    sort_order = EXCLUDED.sort_order
                RETURNING phase_id
            """, (
                phase['phase_code'],
                phase['phase_name'],
                phase['description'],
                phase['sort_order'],
                admin_user_id
            ))

            phase_id = cursor.fetchone()['phase_id']
            total_phases += 1
            print(f"  Phase: {phase['phase_code']} - {phase['phase_name']} ({len(phase['rules'])} rules)")

            # Insert rules
            for rule in phase['rules']:
                cursor.execute("""
                    INSERT INTO takeoff.isms_rules
                        (phase_id, rule_number, rule_text, rule_html, created_by)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (phase_id, rule_number) DO UPDATE SET
                        rule_text = EXCLUDED.rule_text,
                        rule_html = EXCLUDED.rule_html
                """, (
                    phase_id,
                    rule['rule_number'],
                    rule['rule_text'],
                    rule['rule_html'],
                    admin_user_id
                ))
                total_rules += 1

        conn.commit()
        print(f"\nImported {total_phases} phases with {total_rules} rules")

    except Exception as e:
        conn.rollback()
        print(f"Error importing data: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


def main():
    html_path = '/root/Simonini-isms/templates/index.html'

    if not os.path.exists(html_path):
        print(f"Error: HTML file not found at {html_path}")
        sys.exit(1)

    print(f"Parsing HTML from: {html_path}")
    phases = parse_html(html_path)

    print(f"\nFound {len(phases)} sections")
    print("\nImporting to database...")
    import_to_database(phases)

    print("\nImport complete!")


if __name__ == '__main__':
    main()
