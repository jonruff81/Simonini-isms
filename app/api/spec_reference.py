"""
Phase Spec Reference API endpoints
Provides access to extracted Phase Spec content from database
"""
import logging
from flask import Blueprint, jsonify, request, g
from app.models.base import get_db
from app.utils.auth import require_auth

logger = logging.getLogger(__name__)

spec_reference_bp = Blueprint('spec_reference', __name__, url_prefix='/api/spec-reference')


@spec_reference_bp.route('/documents', methods=['GET'])
@require_auth
def get_documents():
    """
    Get all Phase Spec documents with section/item counts
    Optionally filter by category (phase prefix)
    """
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        category = request.args.get('category')

        query = """
            SELECT
                d.document_id, d.phase_code, d.phase_name, d.full_title,
                d.jobtread_url, d.file_size, d.page_count, d.summary,
                COUNT(DISTINCT s.section_id) as section_count,
                COUNT(i.item_id) as item_count
            FROM takeoff.isms_spec_documents d
            LEFT JOIN takeoff.isms_spec_sections s ON s.document_id = d.document_id
            LEFT JOIN takeoff.isms_spec_items i ON i.section_id = s.section_id
            WHERE d.is_active = TRUE
        """
        params = []

        if category:
            query += " AND d.phase_code LIKE %s"
            params.append(f"{category}%")

        query += """
            GROUP BY d.document_id
            ORDER BY d.sort_order, d.phase_code
        """

        db.cursor.execute(query, params)
        documents = [dict(row) for row in db.cursor.fetchall()]

        # Group by category
        categories = {}
        for doc in documents:
            cat = doc['phase_code'].split('-')[0]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(doc)

        return jsonify({
            'success': True,
            'count': len(documents),
            'documents': documents,
            'categories': categories
        })

    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/documents/<int:document_id>', methods=['GET'])
@require_auth
def get_document(document_id: int):
    """
    Get a single document with all sections and items
    """
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Get document
        db.cursor.execute("""
            SELECT
                document_id, phase_code, phase_name, full_title,
                jobtread_url, file_size, page_count, summary
            FROM takeoff.isms_spec_documents
            WHERE document_id = %s AND is_active = TRUE
        """, (document_id,))

        doc = db.cursor.fetchone()
        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        document = dict(doc)

        # Get sections with items
        db.cursor.execute("""
            SELECT section_id, section_name, section_order
            FROM takeoff.isms_spec_sections
            WHERE document_id = %s AND is_active = TRUE
            ORDER BY section_order
        """, (document_id,))

        sections = []
        for section in db.cursor.fetchall():
            section_dict = dict(section)

            # Get items for this section
            db.cursor.execute("""
                SELECT item_id, item_number, item_text, item_html
                FROM takeoff.isms_spec_items
                WHERE section_id = %s AND is_active = TRUE
                ORDER BY CAST(item_number AS INTEGER)
            """, (section_dict['section_id'],))

            section_dict['items'] = [dict(item) for item in db.cursor.fetchall()]
            sections.append(section_dict)

        document['sections'] = sections

        # Get user's bookmarks for this document
        db.cursor.execute("""
            SELECT item_id FROM takeoff.isms_spec_bookmarks
            WHERE user_id = %s AND item_id IN (
                SELECT item_id FROM takeoff.isms_spec_items i
                JOIN takeoff.isms_spec_sections s ON i.section_id = s.section_id
                WHERE s.document_id = %s
            )
        """, (g.current_user['user_id'], document_id))

        document['bookmarked_items'] = [row['item_id'] for row in db.cursor.fetchall()]

        return jsonify({
            'success': True,
            'document': document
        })

    except Exception as e:
        logger.error(f"Error fetching document: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/search', methods=['GET'])
@require_auth
def search_specs():
    """
    Search across all Phase Spec items
    """
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        query_text = request.args.get('q', '').strip()
        if not query_text:
            return jsonify({'error': 'Search query required'}), 400

        # Full-text search
        db.cursor.execute("""
            SELECT
                i.item_id, i.item_number, i.item_text,
                s.section_name,
                d.document_id, d.phase_code, d.phase_name, d.full_title,
                ts_rank(to_tsvector('english', i.item_text), plainto_tsquery('english', %s)) as rank
            FROM takeoff.isms_spec_items i
            JOIN takeoff.isms_spec_sections s ON i.section_id = s.section_id
            JOIN takeoff.isms_spec_documents d ON s.document_id = d.document_id
            WHERE i.is_active = TRUE
            AND d.is_active = TRUE
            AND to_tsvector('english', i.item_text) @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC, d.sort_order, s.section_order, CAST(i.item_number AS INTEGER)
            LIMIT 100
        """, (query_text, query_text))

        results = [dict(row) for row in db.cursor.fetchall()]

        return jsonify({
            'success': True,
            'query': query_text,
            'count': len(results),
            'results': results
        })

    except Exception as e:
        logger.error(f"Error searching specs: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/bookmarks', methods=['GET'])
@require_auth
def get_bookmarks():
    """Get user's spec bookmarks"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT
                b.bookmark_id, b.item_id, b.notes, b.created_at,
                i.item_number, i.item_text,
                s.section_name,
                d.document_id, d.phase_code, d.phase_name, d.full_title
            FROM takeoff.isms_spec_bookmarks b
            JOIN takeoff.isms_spec_items i ON i.item_id = b.item_id
            JOIN takeoff.isms_spec_sections s ON i.section_id = s.section_id
            JOIN takeoff.isms_spec_documents d ON s.document_id = d.document_id
            WHERE b.user_id = %s AND i.is_active = TRUE
            ORDER BY b.created_at DESC
        """, (g.current_user['user_id'],))

        bookmarks = [dict(row) for row in db.cursor.fetchall()]

        return jsonify({
            'success': True,
            'count': len(bookmarks),
            'bookmarks': bookmarks
        })

    except Exception as e:
        logger.error(f"Error fetching bookmarks: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/bookmarks', methods=['POST'])
@require_auth
def add_bookmark():
    """Add a bookmark to a spec item"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        data = request.get_json()
        item_id = data.get('item_id')
        notes = data.get('notes', '')

        if not item_id:
            return jsonify({'error': 'item_id required'}), 400

        db.cursor.execute("""
            INSERT INTO takeoff.isms_spec_bookmarks (user_id, item_id, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, item_id) DO UPDATE SET notes = EXCLUDED.notes
            RETURNING bookmark_id
        """, (g.current_user['user_id'], item_id, notes))

        bookmark_id = db.cursor.fetchone()['bookmark_id']
        db.conn.commit()

        return jsonify({
            'success': True,
            'bookmark_id': bookmark_id
        })

    except Exception as e:
        logger.error(f"Error adding bookmark: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/bookmarks/<int:item_id>', methods=['DELETE'])
@require_auth
def remove_bookmark(item_id: int):
    """Remove a bookmark"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            DELETE FROM takeoff.isms_spec_bookmarks
            WHERE user_id = %s AND item_id = %s
        """, (g.current_user['user_id'], item_id))

        db.conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error removing bookmark: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


# =====================================================================
# NOTES ENDPOINTS
# =====================================================================

@spec_reference_bp.route('/notes', methods=['GET'])
@require_auth
def get_notes():
    """Get all user's notes for spec items"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT
                n.note_id, n.item_id, n.note_text, n.created_at, n.updated_at,
                i.item_number, i.item_text,
                s.section_name,
                d.document_id, d.phase_code, d.phase_name
            FROM takeoff.isms_spec_notes n
            JOIN takeoff.isms_spec_items i ON i.item_id = n.item_id
            JOIN takeoff.isms_spec_sections s ON i.section_id = s.section_id
            JOIN takeoff.isms_spec_documents d ON s.document_id = d.document_id
            WHERE n.user_id = %s AND i.is_active = TRUE
            ORDER BY n.updated_at DESC
        """, (g.current_user['user_id'],))

        notes = [dict(row) for row in db.cursor.fetchall()]

        return jsonify({
            'success': True,
            'count': len(notes),
            'notes': notes
        })

    except Exception as e:
        logger.error(f"Error fetching notes: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/notes/<int:item_id>', methods=['GET'])
@require_auth
def get_note(item_id: int):
    """Get user's note for a specific item"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT note_id, item_id, note_text, created_at, updated_at
            FROM takeoff.isms_spec_notes
            WHERE user_id = %s AND item_id = %s
        """, (g.current_user['user_id'], item_id))

        note = db.cursor.fetchone()

        if note:
            return jsonify({
                'success': True,
                'note': dict(note)
            })
        else:
            return jsonify({
                'success': True,
                'note': None
            })

    except Exception as e:
        logger.error(f"Error fetching note: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/notes', methods=['POST'])
@require_auth
def save_note():
    """Create or update a note for a spec item"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        data = request.get_json()
        item_id = data.get('item_id')
        note_text = data.get('note_text', '').strip()

        if not item_id:
            return jsonify({'error': 'item_id required'}), 400

        if not note_text:
            # If empty note, delete it
            db.cursor.execute("""
                DELETE FROM takeoff.isms_spec_notes
                WHERE user_id = %s AND item_id = %s
            """, (g.current_user['user_id'], item_id))
            db.conn.commit()
            return jsonify({'success': True, 'deleted': True})

        db.cursor.execute("""
            INSERT INTO takeoff.isms_spec_notes (user_id, item_id, note_text)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, item_id) DO UPDATE SET
                note_text = EXCLUDED.note_text,
                updated_at = CURRENT_TIMESTAMP
            RETURNING note_id, created_at, updated_at
        """, (g.current_user['user_id'], item_id, note_text))

        result = db.cursor.fetchone()
        db.conn.commit()

        return jsonify({
            'success': True,
            'note_id': result['note_id'],
            'created_at': result['created_at'].isoformat() if result['created_at'] else None,
            'updated_at': result['updated_at'].isoformat() if result['updated_at'] else None
        })

    except Exception as e:
        logger.error(f"Error saving note: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@spec_reference_bp.route('/notes/<int:item_id>', methods=['DELETE'])
@require_auth
def delete_note(item_id: int):
    """Delete a note"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            DELETE FROM takeoff.isms_spec_notes
            WHERE user_id = %s AND item_id = %s
        """, (g.current_user['user_id'], item_id))

        db.conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error deleting note: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()
