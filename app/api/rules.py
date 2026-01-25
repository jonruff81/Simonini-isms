"""
Rules API endpoints for Simonini-isms
Includes version history support
"""
from flask import Blueprint, jsonify, request, g
from app.models.base import get_db
from app.utils.auth import require_auth, require_admin, get_user_id

rules_bp = Blueprint('rules', __name__)


@rules_bp.route('', methods=['GET'])
@require_auth
def get_rules():
    """Get all rules, optionally filtered by search query"""
    search = request.args.get('q', '').strip()
    phase_id = request.args.get('phase_id')

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        if search:
            # Full text search
            db.cursor.execute("""
                SELECT
                    r.rule_id, r.phase_id, r.rule_number, r.rule_text, r.rule_html,
                    p.phase_code, p.phase_name,
                    ts_rank(to_tsvector('english', r.rule_text), plainto_tsquery('english', %s)) as rank
                FROM takeoff.isms_rules r
                JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
                WHERE r.is_active = TRUE AND p.is_active = TRUE
                AND (
                    to_tsvector('english', r.rule_text) @@ plainto_tsquery('english', %s)
                    OR r.rule_text ILIKE %s
                )
                ORDER BY rank DESC, p.sort_order, r.rule_number
                LIMIT 100
            """, (search, search, f'%{search}%'))
        elif phase_id:
            db.cursor.execute("""
                SELECT
                    r.rule_id, r.phase_id, r.rule_number, r.rule_text, r.rule_html,
                    p.phase_code, p.phase_name
                FROM takeoff.isms_rules r
                JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
                WHERE r.phase_id = %s AND r.is_active = TRUE AND p.is_active = TRUE
                ORDER BY r.rule_number
            """, (phase_id,))
        else:
            db.cursor.execute("""
                SELECT
                    r.rule_id, r.phase_id, r.rule_number, r.rule_text, r.rule_html,
                    p.phase_code, p.phase_name
                FROM takeoff.isms_rules r
                JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
                WHERE r.is_active = TRUE AND p.is_active = TRUE
                ORDER BY p.sort_order, p.phase_code, r.rule_number
            """)

        rules = [dict(row) for row in db.cursor.fetchall()]
        return jsonify(rules)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@rules_bp.route('/<int:rule_id>', methods=['GET'])
@require_auth
def get_rule(rule_id):
    """Get a single rule with phase info"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT
                r.rule_id, r.phase_id, r.rule_number, r.rule_text, r.rule_html,
                r.created_at, r.updated_at,
                p.phase_code, p.phase_name
            FROM takeoff.isms_rules r
            JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
            WHERE r.rule_id = %s AND r.is_active = TRUE
        """, (rule_id,))

        rule = db.cursor.fetchone()
        if not rule:
            return jsonify({'error': 'Rule not found'}), 404

        return jsonify(dict(rule))
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@rules_bp.route('', methods=['POST'])
@require_admin
def create_rule():
    """Create a new rule (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    phase_id = data.get('phase_id')
    rule_text = data.get('rule_text')

    if not phase_id or not rule_text:
        return jsonify({'error': 'phase_id and rule_text are required'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Get next rule number for this phase
        db.cursor.execute("""
            SELECT COALESCE(MAX(rule_number), 0) + 1
            FROM takeoff.isms_rules
            WHERE phase_id = %s
        """, (phase_id,))
        next_number = db.cursor.fetchone()[0]

        rule_number = data.get('rule_number', next_number)

        db.cursor.execute("""
            INSERT INTO takeoff.isms_rules (phase_id, rule_number, rule_text, rule_html, created_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING rule_id, phase_id, rule_number, rule_text, rule_html
        """, (phase_id, rule_number, rule_text, data.get('rule_html'), get_user_id()))

        rule = dict(db.cursor.fetchone())
        db.commit()
        return jsonify(rule), 201
    except Exception as e:
        db.rollback()
        if 'unique' in str(e).lower():
            return jsonify({'error': 'Rule number already exists in this phase'}), 409
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@rules_bp.route('/<int:rule_id>', methods=['PUT'])
@require_admin
def update_rule(rule_id):
    """Update a rule with version history (admin only)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Get current rule for version history
        db.cursor.execute("""
            SELECT rule_text, rule_html FROM takeoff.isms_rules
            WHERE rule_id = %s AND is_active = TRUE
        """, (rule_id,))
        current = db.cursor.fetchone()

        if not current:
            return jsonify({'error': 'Rule not found'}), 404

        # Save to version history if rule_text changed
        if 'rule_text' in data and data['rule_text'] != current['rule_text']:
            # Get next version number
            db.cursor.execute("""
                SELECT COALESCE(MAX(version_number), 0) + 1
                FROM takeoff.isms_rule_versions
                WHERE rule_id = %s
            """, (rule_id,))
            next_version = db.cursor.fetchone()[0]

            # Save current state to history
            db.cursor.execute("""
                INSERT INTO takeoff.isms_rule_versions
                (rule_id, version_number, rule_text, rule_html, change_summary, changed_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                rule_id, next_version,
                current['rule_text'], current['rule_html'],
                data.get('change_summary', 'Rule updated'),
                get_user_id()
            ))

        # Build update query
        updates = []
        values = []

        if 'rule_text' in data:
            updates.append('rule_text = %s')
            values.append(data['rule_text'])
        if 'rule_html' in data:
            updates.append('rule_html = %s')
            values.append(data['rule_html'])
        if 'rule_number' in data:
            updates.append('rule_number = %s')
            values.append(data['rule_number'])

        updates.append('updated_by = %s')
        values.append(get_user_id())
        values.append(rule_id)

        db.cursor.execute(f"""
            UPDATE takeoff.isms_rules
            SET {', '.join(updates)}
            WHERE rule_id = %s AND is_active = TRUE
            RETURNING rule_id, phase_id, rule_number, rule_text, rule_html
        """, values)

        rule = db.cursor.fetchone()
        db.commit()
        return jsonify(dict(rule))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@rules_bp.route('/<int:rule_id>', methods=['DELETE'])
@require_admin
def delete_rule(rule_id):
    """Soft delete a rule (admin only)"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            UPDATE takeoff.isms_rules
            SET is_active = FALSE, updated_by = %s
            WHERE rule_id = %s
            RETURNING rule_id
        """, (get_user_id(), rule_id))

        result = db.cursor.fetchone()
        if not result:
            return jsonify({'error': 'Rule not found'}), 404

        db.commit()
        return jsonify({'message': 'Rule deleted successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@rules_bp.route('/<int:rule_id>/versions', methods=['GET'])
@require_auth
def get_rule_versions(rule_id):
    """Get version history for a rule"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        db.cursor.execute("""
            SELECT
                v.version_id, v.version_number, v.rule_text, v.rule_html,
                v.change_summary, v.changed_at,
                u.username as changed_by_username
            FROM takeoff.isms_rule_versions v
            LEFT JOIN takeoff.users u ON u.user_id = v.changed_by
            WHERE v.rule_id = %s
            ORDER BY v.version_number DESC
        """, (rule_id,))

        versions = [dict(row) for row in db.cursor.fetchall()]
        return jsonify(versions)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()


@rules_bp.route('/<int:rule_id>/restore/<int:version_number>', methods=['POST'])
@require_admin
def restore_rule_version(rule_id, version_number):
    """Restore a rule to a previous version (admin only)"""
    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        # Get the version to restore
        db.cursor.execute("""
            SELECT rule_text, rule_html
            FROM takeoff.isms_rule_versions
            WHERE rule_id = %s AND version_number = %s
        """, (rule_id, version_number))

        version = db.cursor.fetchone()
        if not version:
            return jsonify({'error': 'Version not found'}), 404

        # Get current rule for version history
        db.cursor.execute("""
            SELECT rule_text, rule_html FROM takeoff.isms_rules
            WHERE rule_id = %s
        """, (rule_id,))
        current = db.cursor.fetchone()

        # Save current to history
        db.cursor.execute("""
            SELECT COALESCE(MAX(version_number), 0) + 1
            FROM takeoff.isms_rule_versions WHERE rule_id = %s
        """, (rule_id,))
        next_version = db.cursor.fetchone()[0]

        db.cursor.execute("""
            INSERT INTO takeoff.isms_rule_versions
            (rule_id, version_number, rule_text, rule_html, change_summary, changed_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            rule_id, next_version,
            current['rule_text'], current['rule_html'],
            f'Restored from version {version_number}',
            get_user_id()
        ))

        # Update rule to restored version
        db.cursor.execute("""
            UPDATE takeoff.isms_rules
            SET rule_text = %s, rule_html = %s, updated_by = %s
            WHERE rule_id = %s
            RETURNING rule_id, phase_id, rule_number, rule_text, rule_html
        """, (version['rule_text'], version['rule_html'], get_user_id(), rule_id))

        rule = dict(db.cursor.fetchone())
        db.commit()
        return jsonify(rule)
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()
