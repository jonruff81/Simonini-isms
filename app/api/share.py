"""
Share API endpoints for Simonini-isms
Generate shareable links for phases and rules
"""
from flask import Blueprint, jsonify, request
from urllib.parse import quote
from app.models.base import get_db
from app.utils.auth import require_auth
from app.config import get_config

share_bp = Blueprint('share', __name__)
config = get_config()


@share_bp.route('/generate', methods=['POST'])
@require_auth
def generate_share():
    """Generate share URLs for a phase or rule"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    share_type = data.get('type')  # 'phase' or 'rule'
    item_id = data.get('id')

    if not share_type or not item_id:
        return jsonify({'error': 'type and id are required'}), 400

    base_url = config.APP_URL

    db = get_db()
    if not db.connect():
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        if share_type == 'phase':
            db.cursor.execute("""
                SELECT phase_code, phase_name
                FROM takeoff.isms_phases
                WHERE phase_id = %s AND is_active = TRUE
            """, (item_id,))
            phase = db.cursor.fetchone()

            if not phase:
                return jsonify({'error': 'Phase not found'}), 404

            url = f"{base_url}/phase/{phase['phase_code']}"
            title = f"Phase {phase['phase_code']}: {phase['phase_name']}"
            description = f"Simonini-ism - {phase['phase_name']}"

        elif share_type == 'rule':
            db.cursor.execute("""
                SELECT r.rule_id, r.rule_number, r.rule_text, p.phase_code, p.phase_name
                FROM takeoff.isms_rules r
                JOIN takeoff.isms_phases p ON p.phase_id = r.phase_id
                WHERE r.rule_id = %s AND r.is_active = TRUE
            """, (item_id,))
            rule = db.cursor.fetchone()

            if not rule:
                return jsonify({'error': 'Rule not found'}), 404

            url = f"{base_url}/rule/{rule['rule_id']}"
            title = f"Rule {rule['rule_number']} - Phase {rule['phase_code']}"
            # Truncate rule text for description
            rule_preview = rule['rule_text'][:100] + '...' if len(rule['rule_text']) > 100 else rule['rule_text']
            description = f"Simonini-ism: {rule_preview}"

        else:
            return jsonify({'error': 'Invalid share type. Use "phase" or "rule"'}), 400

        # Generate share links
        encoded_title = quote(title)
        encoded_desc = quote(description)
        encoded_url = quote(url)

        return jsonify({
            'url': url,
            'title': title,
            'description': description,
            'links': {
                'copy': url,
                'email': f"mailto:?subject={encoded_title}&body={encoded_desc}%0A%0A{encoded_url}",
                'sms': f"sms:?body={encoded_desc} {encoded_url}",
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.disconnect()
