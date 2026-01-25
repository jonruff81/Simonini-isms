"""
Main HTML routes for Simonini-isms
"""
from flask import Blueprint, render_template, redirect, url_for, g
from app.models.base import get_db
from app.utils.auth import html_require_auth, html_require_admin, get_current_user

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@html_require_auth
def index():
    """Main page - list all phases with rules"""
    db = get_db()
    if not db.connect():
        return render_template('error.html', message='Database connection failed'), 500

    try:
        # Get all phases with rule counts
        db.cursor.execute("""
            SELECT
                p.phase_id, p.phase_code, p.phase_name, p.description,
                COUNT(r.rule_id) as rule_count
            FROM takeoff.isms_phases p
            LEFT JOIN takeoff.isms_rules r ON r.phase_id = p.phase_id AND r.is_active = TRUE
            WHERE p.is_active = TRUE
            GROUP BY p.phase_id
            ORDER BY p.sort_order, p.phase_code
        """)
        phases = [dict(row) for row in db.cursor.fetchall()]

        # Get rules for each phase
        for phase in phases:
            db.cursor.execute("""
                SELECT rule_id, rule_number, rule_text, rule_html
                FROM takeoff.isms_rules
                WHERE phase_id = %s AND is_active = TRUE
                ORDER BY rule_number
            """, (phase['phase_id'],))
            phase['rules'] = [dict(row) for row in db.cursor.fetchall()]

        # Get user's bookmarks for highlighting
        db.cursor.execute("""
            SELECT rule_id FROM takeoff.isms_bookmarks WHERE user_id = %s
        """, (g.current_user['user_id'],))
        bookmarked_ids = {row['rule_id'] for row in db.cursor.fetchall()}

        return render_template('index.html',
                             phases=phases,
                             bookmarked_ids=bookmarked_ids,
                             user=g.current_user)
    except Exception as e:
        return render_template('error.html', message=str(e)), 500
    finally:
        db.disconnect()


@main_bp.route('/phase/<phase_code>')
@html_require_auth
def view_phase(phase_code):
    """View a single phase (deep link)"""
    db = get_db()
    if not db.connect():
        return render_template('error.html', message='Database connection failed'), 500

    try:
        db.cursor.execute("""
            SELECT phase_id, phase_code, phase_name, description
            FROM takeoff.isms_phases
            WHERE phase_code = %s AND is_active = TRUE
        """, (phase_code,))
        phase = db.cursor.fetchone()

        if not phase:
            return render_template('404.html'), 404

        phase = dict(phase)

        # Get rules
        db.cursor.execute("""
            SELECT rule_id, rule_number, rule_text, rule_html
            FROM takeoff.isms_rules
            WHERE phase_id = %s AND is_active = TRUE
            ORDER BY rule_number
        """, (phase['phase_id'],))
        phase['rules'] = [dict(row) for row in db.cursor.fetchall()]

        # Get user's bookmarks
        db.cursor.execute("""
            SELECT rule_id FROM takeoff.isms_bookmarks WHERE user_id = %s
        """, (g.current_user['user_id'],))
        bookmarked_ids = {row['rule_id'] for row in db.cursor.fetchall()}

        return render_template('phase.html',
                             phase=phase,
                             bookmarked_ids=bookmarked_ids,
                             user=g.current_user)
    except Exception as e:
        return render_template('error.html', message=str(e)), 500
    finally:
        db.disconnect()


@main_bp.route('/rule/<int:rule_id>')
@html_require_auth
def view_rule(rule_id):
    """View a single rule (deep link)"""
    db = get_db()
    if not db.connect():
        return render_template('error.html', message='Database connection failed'), 500

    try:
        db.cursor.execute("""
            SELECT
                r.rule_id, r.rule_number, r.rule_text, r.rule_html,
                r.created_at, r.updated_at,
                p.phase_id, p.phase_code, p.phase_name
            FROM takeoff.isms_rules r
            JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
            WHERE r.rule_id = %s AND r.is_active = TRUE
        """, (rule_id,))
        rule = db.cursor.fetchone()

        if not rule:
            return render_template('404.html'), 404

        rule = dict(rule)

        # Check if bookmarked
        db.cursor.execute("""
            SELECT bookmark_id FROM takeoff.isms_bookmarks
            WHERE user_id = %s AND rule_id = %s
        """, (g.current_user['user_id'], rule_id))
        rule['is_bookmarked'] = db.cursor.fetchone() is not None

        # Get user's note for this rule
        db.cursor.execute("""
            SELECT note_id, note_text FROM takeoff.isms_notes
            WHERE user_id = %s AND rule_id = %s
        """, (g.current_user['user_id'], rule_id))
        note = db.cursor.fetchone()
        rule['user_note'] = dict(note) if note else None

        # Get user's highlights for this rule
        db.cursor.execute("""
            SELECT highlight_id, start_offset, end_offset, highlighted_text, highlight_color
            FROM takeoff.isms_highlights
            WHERE user_id = %s AND rule_id = %s
            ORDER BY start_offset
        """, (g.current_user['user_id'], rule_id))
        rule['highlights'] = [dict(row) for row in db.cursor.fetchall()]

        return render_template('rule.html', rule=rule, user=g.current_user)
    except Exception as e:
        return render_template('error.html', message=str(e)), 500
    finally:
        db.disconnect()


@main_bp.route('/bookmarks')
@html_require_auth
def view_bookmarks():
    """View user's bookmarks"""
    db = get_db()
    if not db.connect():
        return render_template('error.html', message='Database connection failed'), 500

    try:
        db.cursor.execute("""
            SELECT
                b.bookmark_id, b.rule_id, b.notes, b.created_at,
                r.rule_number, r.rule_text,
                p.phase_id, p.phase_code, p.phase_name
            FROM takeoff.isms_bookmarks b
            JOIN takeoff.isms_rules r ON r.rule_id = b.rule_id
            JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
            WHERE b.user_id = %s AND r.is_active = TRUE
            ORDER BY b.created_at DESC
        """, (g.current_user['user_id'],))
        bookmarks = [dict(row) for row in db.cursor.fetchall()]

        return render_template('bookmarks.html', bookmarks=bookmarks, user=g.current_user)
    except Exception as e:
        return render_template('error.html', message=str(e)), 500
    finally:
        db.disconnect()


@main_bp.route('/search')
@html_require_auth
def search():
    """Search results page"""
    return render_template('search.html', user=g.current_user)


@main_bp.route('/admin')
@html_require_admin
def admin_dashboard():
    """Admin dashboard"""
    return render_template('admin/dashboard.html', user=g.current_user)


@main_bp.route('/phase-specs')
@html_require_auth
def phase_specs():
    """Phase Specs PDF library page"""
    return render_template('phase_specs.html', user=g.current_user)


@main_bp.route('/spec-reference')
@html_require_auth
def spec_reference():
    """Phase Spec Reference - browsable content from PDFs (all on one page)"""
    db = get_db()
    if not db.connect():
        return render_template('error.html', message='Database connection failed'), 500

    try:
        # Get all documents
        db.cursor.execute("""
            SELECT document_id, phase_code, phase_name, full_title, jobtread_url, summary
            FROM takeoff.isms_spec_documents
            WHERE is_active = TRUE
            ORDER BY sort_order, phase_code
        """)
        documents = [dict(row) for row in db.cursor.fetchall()]

        # Get all sections and items for each document
        for doc in documents:
            db.cursor.execute("""
                SELECT section_id, section_name, section_order
                FROM takeoff.isms_spec_sections
                WHERE document_id = %s AND is_active = TRUE
                ORDER BY section_order
            """, (doc['document_id'],))
            doc['sections'] = []

            for section in db.cursor.fetchall():
                section_dict = dict(section)
                db.cursor.execute("""
                    SELECT item_id, item_number, item_text
                    FROM takeoff.isms_spec_items
                    WHERE section_id = %s AND is_active = TRUE
                    ORDER BY CAST(item_number AS INTEGER)
                """, (section_dict['section_id'],))
                section_dict['items'] = [dict(item) for item in db.cursor.fetchall()]
                doc['sections'].append(section_dict)

            # Count total items
            doc['item_count'] = sum(len(s['items']) for s in doc['sections'])

        # Get user's bookmarked item IDs
        db.cursor.execute("""
            SELECT item_id FROM takeoff.isms_spec_bookmarks WHERE user_id = %s
        """, (g.current_user['user_id'],))
        bookmarked_ids = {row['item_id'] for row in db.cursor.fetchall()}

        # Get user's notes
        db.cursor.execute("""
            SELECT item_id, note_text FROM takeoff.isms_spec_notes WHERE user_id = %s
        """, (g.current_user['user_id'],))
        user_notes = {row['item_id']: row['note_text'] for row in db.cursor.fetchall()}

        return render_template('spec_reference.html',
                             documents=documents,
                             bookmarked_ids=bookmarked_ids,
                             user_notes=user_notes,
                             user=g.current_user)
    except Exception as e:
        return render_template('error.html', message=str(e)), 500
    finally:
        db.disconnect()


@main_bp.route('/spec-reference/<phase_code>')
@html_require_auth
def spec_reference_detail(phase_code):
    """View a single Phase Spec document"""
    db = get_db()
    if not db.connect():
        return render_template('error.html', message='Database connection failed'), 500

    try:
        # Get document
        db.cursor.execute("""
            SELECT
                document_id, phase_code, phase_name, full_title,
                jobtread_url, file_size, page_count, summary
            FROM takeoff.isms_spec_documents
            WHERE phase_code = %s AND is_active = TRUE
        """, (phase_code,))

        doc = db.cursor.fetchone()
        if not doc:
            return render_template('404.html'), 404

        document = dict(doc)

        # Get sections with items
        db.cursor.execute("""
            SELECT section_id, section_name, section_order
            FROM takeoff.isms_spec_sections
            WHERE document_id = %s AND is_active = TRUE
            ORDER BY section_order
        """, (document['document_id'],))

        sections = []
        for section in db.cursor.fetchall():
            section_dict = dict(section)

            db.cursor.execute("""
                SELECT item_id, item_number, item_text, item_html
                FROM takeoff.isms_spec_items
                WHERE section_id = %s AND is_active = TRUE
                ORDER BY CAST(item_number AS INTEGER)
            """, (section_dict['section_id'],))

            section_dict['items'] = [dict(item) for item in db.cursor.fetchall()]
            sections.append(section_dict)

        document['sections'] = sections

        # Get user's bookmarked items
        db.cursor.execute("""
            SELECT item_id FROM takeoff.isms_spec_bookmarks
            WHERE user_id = %s AND item_id IN (
                SELECT item_id FROM takeoff.isms_spec_items i
                JOIN takeoff.isms_spec_sections s ON i.section_id = s.section_id
                WHERE s.document_id = %s
            )
        """, (g.current_user['user_id'], document['document_id']))

        bookmarked_ids = {row['item_id'] for row in db.cursor.fetchall()}

        return render_template('spec_reference_detail.html',
                             document=document,
                             bookmarked_ids=bookmarked_ids,
                             user=g.current_user)
    except Exception as e:
        return render_template('error.html', message=str(e)), 500
    finally:
        db.disconnect()


@main_bp.route('/pending-approval')
def pending_approval():
    """Page shown when user account is pending approval"""
    return render_template('pending_approval.html')


@main_bp.route('/unauthorized')
def unauthorized():
    """Page shown when user doesn't have permission"""
    return render_template('unauthorized.html')
