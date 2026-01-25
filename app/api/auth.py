"""
Authentication API endpoints for Simonini-isms
Validates against shared Ruff Estimates user/session tables
"""
from flask import Blueprint, jsonify, request, g
from app.utils.auth import get_current_user, require_auth

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/validate', methods=['GET'])
def validate_session():
    """Validate current session and return user info"""
    user = get_current_user()
    if not user:
        return jsonify({'authenticated': False}), 401

    if not user.get('is_verified') and not user.get('can_admin'):
        return jsonify({
            'authenticated': True,
            'verified': False,
            'message': 'Account pending approval'
        }), 403

    return jsonify({
        'authenticated': True,
        'verified': True,
        'user': {
            'user_id': user['user_id'],
            'username': user['username'],
            'email': user['email'],
            'first_name': user['first_name'],
            'last_name': user['last_name'],
            'is_admin': user.get('can_admin', False)
        }
    })


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user_info():
    """Get current user information"""
    user = g.current_user
    return jsonify({
        'user_id': user['user_id'],
        'username': user['username'],
        'email': user['email'],
        'first_name': user['first_name'],
        'last_name': user['last_name'],
        'is_admin': user.get('can_admin', False),
        'user_role': user.get('user_role', 'user')
    })
