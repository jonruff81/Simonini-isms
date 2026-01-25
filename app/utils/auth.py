"""
Authentication utilities for Simonini-isms
Validates against shared takeoff.users and takeoff.user_sessions tables
"""
import logging
from functools import wraps
from flask import request, jsonify, redirect, url_for, g
from urllib.parse import urlencode
from app.models.base import get_db
from app.config import get_config

logger = logging.getLogger(__name__)
config = get_config()


def _validate_demo_session(demo_token):
    """
    Validate demo session token against demo database.
    Returns a demo user dict if valid, None otherwise.
    """
    import os
    import psycopg2
    from psycopg2.extras import RealDictCursor

    try:
        # Connect to demo database (use Docker internal hostname)
        conn = psycopg2.connect(
            host=os.getenv('DEMO_DB_HOST', 'takeoff_postgres'),
            port=int(os.getenv('DEMO_DB_PORT', '5432')),
            dbname=os.getenv('DEMO_DB_NAME', 'takeoff_demo_db'),
            user=os.getenv('DEMO_DB_USER', 'demo_user'),
            password=os.getenv('DEMO_DB_PASSWORD', 'demo123'),
            connect_timeout=5
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute("""
            SELECT ds.id, ds.expires_at, dac.code
            FROM takeoff.demo_sessions ds
            JOIN takeoff.demo_access_codes dac ON ds.access_code_id = dac.id
            WHERE ds.session_token = %s
              AND ds.expires_at > CURRENT_TIMESTAMP
              AND dac.is_active = TRUE
        """, (demo_token,))

        session = cursor.fetchone()
        cursor.close()
        conn.close()

        if session:
            return {
                'user_id': -1,  # Demo user ID
                'username': 'demo_user',
                'email': 'demo@ruff.uno',
                'first_name': 'Demo',
                'last_name': 'User',
                'is_demo': True,
                'is_verified': True,
                'demo_session_id': session['id'],
                'demo_code': session['code'],
                'demo_expires': session['expires_at'],
                'can_read': True,
                'can_write': True,
                'can_delete': False,
                'can_admin': False,
                'user_role': 'demo'
            }
        return None

    except Exception as e:
        logger.error(f"Error validating demo session: {e}")
        return None

def get_current_user():
    """
    Get current user from session token.
    Checks Authorization header first, then session_token cookie.
    Also checks demo_session cookie for demo access.
    Validates against shared takeoff.user_sessions table.
    """
    token = None

    # Check Authorization header first
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ', 1)[1]

    # Fall back to cookie
    if not token:
        token = request.cookies.get('session_token')

    # Check for demo session if no regular session
    if not token:
        demo_token = request.cookies.get('demo_session')
        if demo_token:
            return _validate_demo_session(demo_token)
        return None

    # Validate session against shared tables
    db = get_db()
    if not db.connect():
        logger.error("Failed to connect to database for auth validation")
        return None

    try:
        db.cursor.execute("""
            SELECT
                s.session_id, s.user_id, s.expires_at, s.is_active as session_active,
                u.username, u.email, u.first_name, u.last_name, u.user_role,
                u.can_read, u.can_write, u.can_delete, u.can_admin,
                u.is_verified, u.is_active as user_active
            FROM takeoff.user_sessions s
            JOIN takeoff.users u ON s.user_id = u.user_id
            WHERE s.session_token = %s
            AND s.expires_at > CURRENT_TIMESTAMP
            AND s.is_active = TRUE
            AND u.is_active = TRUE
        """, (token,))

        result = db.cursor.fetchone()
        return dict(result) if result else None

    except Exception as e:
        logger.error(f"Error validating session: {e}")
        return None
    finally:
        db.disconnect()


def require_auth(f):
    """
    Decorator for API routes that require authentication.
    Returns 401 if not authenticated, 403 if not verified.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        if not user.get('is_verified') and not user.get('can_admin'):
            return jsonify({'error': 'Account pending approval'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """
    Decorator for API routes that require admin privileges.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required'}), 401
        if not user.get('can_admin'):
            return jsonify({'error': 'Admin privileges required'}), 403
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def get_external_url():
    """
    Get the external URL accounting for reverse proxy.
    Uses X-Forwarded-Proto header to determine the correct scheme.
    """
    # Check if behind reverse proxy
    proto = request.headers.get('X-Forwarded-Proto', 'http')
    host = request.headers.get('X-Forwarded-Host', request.host)

    # Build URL with correct scheme
    url = f"{proto}://{host}{request.path}"
    if request.query_string:
        url += f"?{request.query_string.decode('utf-8')}"
    return url


def html_require_auth(f):
    """
    Decorator for HTML routes that require authentication.
    Redirects to Ruff Estimates login if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            # Build redirect URL to Ruff Estimates login
            current_url = get_external_url()
            login_url = f"{config.RUFF_LOGIN_URL}?{urlencode({'redirect': current_url})}"
            return redirect(login_url)
        if not user.get('is_verified') and not user.get('can_admin'):
            return redirect(url_for('main.pending_approval'))
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def html_require_admin(f):
    """
    Decorator for HTML routes that require admin privileges.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            current_url = get_external_url()
            login_url = f"{config.RUFF_LOGIN_URL}?{urlencode({'redirect': current_url})}"
            return redirect(login_url)
        if not user.get('can_admin'):
            return redirect(url_for('main.unauthorized'))
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def get_user_id():
    """Get current user's ID from g object"""
    user = getattr(g, 'current_user', None)
    return user.get('user_id') if user else None


def is_admin():
    """Check if current user is admin"""
    user = getattr(g, 'current_user', None)
    return user.get('can_admin', False) if user else False
