"""
Highlights API endpoints for Simonini-isms
User-specific text highlights within rules
"""
from flask import Blueprint, jsonify, request, g
from app.models.base import get_db
from app.utils.auth import require_auth, get_user_id

highlights_bp = Blueprint('highlights', __name__)


@highlights_bp.route('', methods=['GET'])
@require_auth
def get_highlights():
    """Get all highlights for current user, optionally filtered by rule_id"""
    rule_id = request.args.get('rule_id')

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        if rule_id:
            db.cursor.execute("""
                SELECT
                    h.highlight_id, h.rule_id, h.start_offset, h.end_offset,
                    h.highlighted_text, h.highlight_color, h.created_at
                FROM takeoff.isms_highlights h
                WHERE h.user_id = %s AND h.rule_id = %s
                ORDER BY h.start_offset
            """, (get_user_id(), rule_id))
        else:
            db.cursor.execute("""
                SELECT
                    h.highlight_id, h.rule_id, h.start_offset, h.end_offset,
                    h.highlighted_text, h.highlight_color, h.created_at,
                    r.rule_number, p.phase_code, p.phase_name
                FROM takeoff.isms_highlights h
                JOIN takeoff.isms_rules r ON r.rule_id = h.rule_id
                JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
                WHERE h.user_id = %s AND r.is_active = TRUE
                ORDER BY h.created_at DESC
            """, (get_user_id(),))

        highlights = [dict(row) for row in db.cursor.fetchall()]
        return jsonify(highlights)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@highlights_bp.route('', methods=['POST'])
@require_auth
def add_highlight():
    """Add a highlight"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required = ['rule_id', 'start_offset', 'end_offset', 'highlighted_text']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            INSERT INTO takeoff.isms_highlights
            (user_id, rule_id, start_offset, end_offset, highlighted_text, highlight_color)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING highlight_id, rule_id, start_offset, end_offset, highlighted_text, highlight_color, created_at
        """, (
            get_user_id(),
            data['rule_id'],
            data['start_offset'],
            data['end_offset'],
            data['highlighted_text'],
            data.get('highlight_color', 'yellow')
        ))

        highlight = dict(db.cursor.fetchone())
        db.commit()
        return jsonify(highlight), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@highlights_bp.route('/<int:highlight_id>', methods=['DELETE'])
@require_auth
def remove_highlight(highlight_id):
    """Remove a highlight"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            DELETE FROM takeoff.isms_highlights
            WHERE highlight_id = %s AND user_id = %s
            RETURNING highlight_id
        """, (highlight_id, get_user_id()))

        result = db.cursor.fetchone()
        if not result:
            return jsonify({'error': 'Highlight not found'}), 404

        db.commit()
        return jsonify({'message': 'Highlight removed'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@highlights_bp.route('/rule/<int:rule_id>', methods=['DELETE'])
@require_auth
def remove_rule_highlights(rule_id):
    """Remove all highlights for a rule"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            DELETE FROM takeoff.isms_highlights
            WHERE rule_id = %s AND user_id = %s
        """, (rule_id, get_user_id()))

        db.commit()
        return jsonify({'message': 'Highlights removed'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()
