"""
Phases API endpoints for Simonini-isms
"""
from flask import Blueprint, jsonify, request, g
from app.models.base import get_db
from app.utils.auth import require_auth, require_admin, get_user_id

phases_bp = Blueprint('phases', __name__)


@phases_bp.route('', methods=['GET'])
@require_auth
def get_phases():
    """Get all active phases"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT
                p.phase_id, p.phase_code, p.phase_name, p.description,
                p.sort_order, p.created_at, p.updated_at,
                COUNT(r.rule_id) as rule_count
            FROM takeoff.isms_phases p
            LEFT JOIN takeoff.isms_rules r ON r.phase_id = p.phase_id AND r.is_active = TRUE
            WHERE p.is_active = TRUE
            GROUP BY p.phase_id
            ORDER BY p.sort_order, p.phase_code
        """)
        phases = [dict(row) for row in db.cursor.fetchall()]
        return jsonify(phases)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@phases_bp.route('/<int:phase_id>', methods=['GET'])
@require_auth
def get_phase(phase_id):
    """Get a single phase with its rules"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Get phase
        db.cursor.execute("""
            SELECT phase_id, phase_code, phase_name, description, sort_order
            FROM takeoff.isms_phases
            WHERE phase_id = %s AND is_active = TRUE
        """, (phase_id,))
        phase = db.cursor.fetchone()

        if not phase:
            return jsonify({'error': 'Phase not found'}), 404

        phase = dict(phase)

        # Get rules for this phase
        db.cursor.execute("""
            SELECT rule_id, rule_number, rule_text, rule_html
            FROM takeoff.isms_rules
            WHERE phase_id = %s AND is_active = TRUE
            ORDER BY rule_number
        """, (phase_id,))
        phase['rules'] = [dict(row) for row in db.cursor.fetchall()]

        return jsonify(phase)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@phases_bp.route('/code/<phase_code>', methods=['GET'])
@require_auth
def get_phase_by_code(phase_code):
    """Get a phase by its code (e.g., '30-100')"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT phase_id, phase_code, phase_name, description, sort_order
            FROM takeoff.isms_phases
            WHERE phase_code = %s AND is_active = TRUE
        """, (phase_code,))
        phase = db.cursor.fetchone()

        if not phase:
            return jsonify({'error': 'Phase not found'}), 404

        phase = dict(phase)

        # Get rules
        db.cursor.execute("""
            SELECT rule_id, rule_number, rule_text, rule_html
            FROM takeoff.isms_rules
            WHERE phase_id = %s AND is_active = TRUE
            ORDER BY rule_number
        """, (phase['phase_id'],))
        phase['rules'] = [dict(row) for row in db.cursor.fetchall()]

        return jsonify(phase)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@phases_bp.route('', methods=['POST'])
@require_admin
def create_phase():
    """Create a new phase (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    phase_code = data.get('phase_code')
    phase_name = data.get('phase_name')

    if not phase_code or not phase_name:
        return jsonify({'error': 'phase_code and phase_name are required'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Get next sort order
        db.cursor.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM takeoff.isms_phases")
        next_sort = db.cursor.fetchone()[0]

        db.cursor.execute("""
            INSERT INTO takeoff.isms_phases (phase_code, phase_name, description, sort_order, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING phase_id, phase_code, phase_name, description, sort_order
        """, (phase_code, phase_name, data.get('description'), data.get('sort_order', next_sort), get_user_id()))

        phase = dict(db.cursor.fetchone())
        db.commit()
        return jsonify(phase), 201
    except Exception as e:
        db.rollback()
        if 'unique' in str(e).lower():
            return jsonify({'error': 'Phase code already exists'}), 409
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@phases_bp.route('/<int:phase_id>', methods=['PUT'])
@require_admin
def update_phase(phase_id):
    """Update a phase (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Build update query dynamically
        updates = []
        values = []

        if 'phase_code' in data:
            updates.append('phase_code = %s')
            values.append(data['phase_code'])
        if 'phase_name' in data:
            updates.append('phase_name = %s')
            values.append(data['phase_name'])
        if 'description' in data:
            updates.append('description = %s')
            values.append(data['description'])
        if 'sort_order' in data:
            updates.append('sort_order = %s')
            values.append(data['sort_order'])

        updates.append('updated_by = %s')
        values.append(get_user_id())
        values.append(phase_id)

        db.cursor.execute(f"""
            UPDATE takeoff.isms_phases
            SET {', '.join(updates)}
            WHERE phase_id = %s AND is_active = TRUE
            RETURNING phase_id, phase_code, phase_name, description, sort_order
        """, values)

        phase = db.cursor.fetchone()
        if not phase:
            return jsonify({'error': 'Phase not found'}), 404

        db.commit()
        return jsonify(dict(phase))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@phases_bp.route('/<int:phase_id>', methods=['DELETE'])
@require_admin
def delete_phase(phase_id):
    """Soft delete a phase (admin only)"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            UPDATE takeoff.isms_phases
            SET is_active = FALSE, updated_by = %s
            WHERE phase_id = %s
            RETURNING phase_id
        """, (get_user_id(), phase_id))

        result = db.cursor.fetchone()
        if not result:
            return jsonify({'error': 'Phase not found'}), 404

        db.commit()
        return jsonify({'message': 'Phase deleted successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@phases_bp.route('/reorder', methods=['POST'])
@require_admin
def reorder_phases():
    """Reorder phases (admin only)"""
    data = request.get_json()
    if not data or 'order' not in data:
        return jsonify({'error': 'order array required'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        for idx, phase_id in enumerate(data['order']):
            db.cursor.execute("""
                UPDATE takeoff.isms_phases
                SET sort_order = %s, updated_by = %s
                WHERE phase_id = %s
            """, (idx, get_user_id(), phase_id))

        db.commit()
        return jsonify({'message': 'Phases reordered successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()
