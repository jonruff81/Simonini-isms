"""
Bookmarks API endpoints for Simonini-isms
User-specific bookmarked rules
"""
from flask import Blueprint, jsonify, request, g
from app.models.base import get_db
from app.utils.auth import require_auth, get_user_id

bookmarks_bp = Blueprint('bookmarks', __name__)


@bookmarks_bp.route('', methods=['GET'])
@require_auth
def get_bookmarks():
    """Get all bookmarks for current user"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

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
        """, (get_user_id(),))

        bookmarks = [dict(row) for row in db.cursor.fetchall()]
        return jsonify(bookmarks)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@bookmarks_bp.route('', methods=['POST'])
@require_auth
def add_bookmark():
    """Add a bookmark"""
    data = request.get_json()
    if not data or 'rule_id' not in data:
        return jsonify({'error': 'rule_id is required'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            INSERT INTO takeoff.isms_bookmarks (user_id, rule_id, notes)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, rule_id) DO UPDATE SET notes = EXCLUDED.notes
            RETURNING bookmark_id, rule_id, notes, created_at
        """, (get_user_id(), data['rule_id'], data.get('notes')))

        bookmark = dict(db.cursor.fetchone())
        db.commit()
        return jsonify(bookmark), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@bookmarks_bp.route('/<int:rule_id>', methods=['DELETE'])
@require_auth
def remove_bookmark(rule_id):
    """Remove a bookmark"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            DELETE FROM takeoff.isms_bookmarks
            WHERE user_id = %s AND rule_id = %s
            RETURNING bookmark_id
        """, (get_user_id(), rule_id))

        result = db.cursor.fetchone()
        if not result:
            return jsonify({'error': 'Bookmark not found'}), 404

        db.commit()
        return jsonify({'message': 'Bookmark removed'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@bookmarks_bp.route('/check/<int:rule_id>', methods=['GET'])
@require_auth
def check_bookmark(rule_id):
    """Check if a rule is bookmarked by current user"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT bookmark_id, notes FROM takeoff.isms_bookmarks
            WHERE user_id = %s AND rule_id = %s
        """, (get_user_id(), rule_id))

        bookmark = db.cursor.fetchone()
        return jsonify({
            'bookmarked': bookmark is not None,
            'bookmark': dict(bookmark) if bookmark else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()
