"""
Notes API endpoints for Simonini-isms
User-specific notes attached to rules
"""
from flask import Blueprint, jsonify, request, g
from app.models.base import get_db
from app.utils.auth import require_auth, get_user_id

notes_bp = Blueprint('notes', __name__)


@notes_bp.route('', methods=['GET'])
@require_auth
def get_notes():
    """Get all notes for current user"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT
                n.note_id, n.rule_id, n.note_text, n.created_at, n.updated_at,
                r.rule_number, r.rule_text,
                p.phase_id, p.phase_code, p.phase_name
            FROM takeoff.isms_notes n
            JOIN takeoff.isms_rules r ON r.rule_id = n.rule_id
            JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
            WHERE n.user_id = %s AND r.is_active = TRUE
            ORDER BY n.updated_at DESC
        """, (get_user_id(),))

        notes = [dict(row) for row in db.cursor.fetchall()]
        return jsonify(notes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@notes_bp.route('/rule/<int:rule_id>', methods=['GET'])
@require_auth
def get_note_for_rule(rule_id):
    """Get note for a specific rule"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT note_id, rule_id, note_text, created_at, updated_at
            FROM takeoff.isms_notes
            WHERE user_id = %s AND rule_id = %s
        """, (get_user_id(), rule_id))

        note = db.cursor.fetchone()
        if note:
            return jsonify(dict(note))
        return jsonify(None)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@notes_bp.route('', methods=['POST'])
@require_auth
def add_or_update_note():
    """Add or update a note for a rule"""
    data = request.get_json()
    if not data or 'rule_id' not in data or 'note_text' not in data:
        return jsonify({'error': 'rule_id and note_text are required'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Check if note already exists
        db.cursor.execute("""
            SELECT note_id FROM takeoff.isms_notes
            WHERE user_id = %s AND rule_id = %s
        """, (get_user_id(), data['rule_id']))

        existing = db.cursor.fetchone()

        if existing:
            # Update existing note
            db.cursor.execute("""
                UPDATE takeoff.isms_notes
                SET note_text = %s
                WHERE note_id = %s
                RETURNING note_id, rule_id, note_text, created_at, updated_at
            """, (data['note_text'], existing['note_id']))
        else:
            # Create new note
            db.cursor.execute("""
                INSERT INTO takeoff.isms_notes (user_id, rule_id, note_text)
                VALUES (%s, %s, %s)
                RETURNING note_id, rule_id, note_text, created_at, updated_at
            """, (get_user_id(), data['rule_id'], data['note_text']))

        note = dict(db.cursor.fetchone())
        db.commit()
        return jsonify(note), 201 if not existing else 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@notes_bp.route('/<int:note_id>', methods=['DELETE'])
@require_auth
def delete_note(note_id):
    """Delete a note"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            DELETE FROM takeoff.isms_notes
            WHERE note_id = %s AND user_id = %s
            RETURNING note_id
        """, (note_id, get_user_id()))

        result = db.cursor.fetchone()
        if not result:
            return jsonify({'error': 'Note not found'}), 404

        db.commit()
        return jsonify({'message': 'Note deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@notes_bp.route('/rule/<int:rule_id>', methods=['DELETE'])
@require_auth
def delete_note_for_rule(rule_id):
    """Delete note for a specific rule"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            DELETE FROM takeoff.isms_notes
            WHERE rule_id = %s AND user_id = %s
            RETURNING note_id
        """, (rule_id, get_user_id()))

        db.commit()
        return jsonify({'message': 'Note deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()
