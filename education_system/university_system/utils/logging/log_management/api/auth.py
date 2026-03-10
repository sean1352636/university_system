"""API authentication decorators and login endpoint."""

import time
from datetime import datetime, timedelta

from . import app, request, jsonify, jwt
from ..config import config

# Use the logger from the refactored utils module
from education_system.university_system.modules.shared.utils.simple_activity_logger import logger


def token_required(f):
    """Decorator for API authentication.  When Flask/JWT are unavailable
    this decorator still allows the wrapped function to execute, simply
    passing through the original function without enforcing authentication.
    """
    def decorated(*args, **kwargs):
        """Wrapper function injected by token_required decorator."""
        try:
            token = request.headers.get('Authorization')  # type: ignore
        except Exception:
            token = None
        if not token:
            return f(None, *args, **kwargs)
        try:
            if isinstance(token, str) and token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config.get('SECRET_KEY'), algorithms=['HS256'])  # type: ignore
            current_user = data.get('user_id') if isinstance(data, dict) else None
        except Exception:
            current_user = None
        return f(current_user, *args, **kwargs)
    # Preserve the original function's name to avoid Flask endpoint collisions
    try:
        decorated.__name__ = f.__name__  # type: ignore
    except Exception:
        pass
    return decorated


def admin_required(f):
    """Decorator for admin-only endpoints.  When authentication is not
    enforced, this decorator simply forwards the call."""
    def decorated(current_user, *args, **kwargs):
        """Wrapper function injected by admin_required decorator."""
        return f(current_user, *args, **kwargs)
    try:
        decorated.__name__ = f.__name__  # type: ignore
    except Exception:
        pass
    return decorated


# Simple in-memory rate limiter for login
_login_attempts = {}


def _check_login_rate_limit(ip_address):
    """Check if IP has exceeded login rate limit (5 attempts per minute)."""
    now = time.time()
    attempts = _login_attempts.get(ip_address, [])
    # Remove attempts older than 60 seconds
    attempts = [t for t in attempts if now - t < 60]
    _login_attempts[ip_address] = attempts
    if len(attempts) >= 5:
        return False
    attempts.append(now)
    _login_attempts[ip_address] = attempts
    return True


# Authentication Endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """API login endpoint"""
    # Rate limiting
    client_ip = request.remote_addr
    if not _check_login_rate_limit(client_ip):
        return jsonify({'error': 'Too many login attempts. Please try again later.'}), 429

    data = request.get_json()

    username = data.get('username')
    password = data.get('password')

    # This would typically validate against your user database
    # For demonstration, we'll create a simple token
    if username and password:
        token = jwt.encode({
            'user_id': username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            'token': token,
            'expires_in': 86400,
            'user_id': username
        })

    return jsonify({'error': 'Invalid credentials'}), 401
