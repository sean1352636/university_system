"""
Flask Security Headers Utility.

Provides security headers for Flask applications via the @app.after_request decorator.
This module mirrors the functionality of the FastAPI SecurityHeadersMiddleware.

Usage:
    from flask import Flask
    from university_system.infrastructure.security.flask_security_headers import (
        add_security_headers,
        init_security_headers
    )

    app = Flask(__name__)

    # Option 1: Use decorator on individual responses
    @app.after_request
    def apply_security_headers(response):
        return add_security_headers(response)

    # Option 2: Initialize once for the entire app
    init_security_headers(app)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_default_csp() -> str:
    """
    Return the default Content Security Policy.

    Returns:
        CSP header value string
    """
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )


def get_hsts_value(
    max_age: int = 31536000,
    include_subdomains: bool = True,
    preload: bool = False
) -> str:
    """
    Build the HSTS header value.

    Args:
        max_age: Max age in seconds (default: 1 year)
        include_subdomains: Include subdomains directive
        preload: Include preload directive

    Returns:
        HSTS header value string
    """
    parts = [f"max-age={max_age}"]
    if include_subdomains:
        parts.append("includeSubDomains")
    if preload:
        parts.append("preload")
    return "; ".join(parts)


def add_security_headers(
    response,
    enable_hsts: bool = None,
    hsts_max_age: int = 31536000,
    content_security_policy: str = None,
    frame_options: str = "DENY",
    referrer_policy: str = "strict-origin-when-cross-origin",
    is_authenticated: bool = False,
):
    """
    Add security headers to a Flask response object.

    Args:
        response: Flask response object
        enable_hsts: Enable HSTS (default: auto based on APP_ENV)
        hsts_max_age: HSTS max-age in seconds
        content_security_policy: Custom CSP (default: restrictive policy)
        frame_options: X-Frame-Options value (default: DENY)
        referrer_policy: Referrer-Policy value
        is_authenticated: Whether request is authenticated (for cache control)

    Returns:
        Modified response with security headers
    """
    # Auto-detect HSTS based on environment if not specified
    if enable_hsts is None:
        app_env = os.getenv("APP_ENV", "production").lower()
        enable_hsts = app_env not in ("development", "dev", "local", "test")

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = frame_options

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Enable XSS protection in older browsers
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # HTTP Strict Transport Security
    if enable_hsts:
        response.headers["Strict-Transport-Security"] = get_hsts_value(hsts_max_age)

    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        content_security_policy or get_default_csp()
    )

    # Referrer Policy
    response.headers["Referrer-Policy"] = referrer_policy

    # Permissions Policy
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    # Cache control for authenticated responses
    if is_authenticated:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"

    return response


def init_cookie_security(app):
    """Configure secure cookie settings for a Flask application."""
    app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
    app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    if os.getenv('APP_ENV', 'production').lower() not in ('development', 'dev', 'local', 'test'):
        app.config.setdefault('SESSION_COOKIE_SECURE', True)


def init_security_headers(
    app,
    enable_hsts: bool = None,
    content_security_policy: str = None,
    frame_options: str = "DENY",
    referrer_policy: str = "strict-origin-when-cross-origin",
):
    """
    Initialize security headers for a Flask application.

    This registers an after_request handler that adds security headers
    to all responses.

    Args:
        app: Flask application instance
        enable_hsts: Enable HSTS (default: auto based on APP_ENV)
        content_security_policy: Custom CSP
        frame_options: X-Frame-Options value
        referrer_policy: Referrer-Policy value

    Example:
        from flask import Flask
        from university_system.infrastructure.security.flask_security_headers import (
            init_security_headers
        )

        app = Flask(__name__)
        init_security_headers(app)
    """
    @app.after_request
    def apply_security_headers(response):
        # Check if request has Authorization header for cache control
        from flask import request
        is_authenticated = bool(request.headers.get("Authorization"))

        return add_security_headers(
            response,
            enable_hsts=enable_hsts,
            content_security_policy=content_security_policy,
            frame_options=frame_options,
            referrer_policy=referrer_policy,
            is_authenticated=is_authenticated,
        )

    # Also configure secure cookie settings
    init_cookie_security(app)

    app_env = os.getenv("APP_ENV", "production").lower()
    is_dev = app_env in ("development", "dev", "local", "test")
    mode = "development" if is_dev else "production"
    logger.info(f"Flask security headers initialized ({mode} mode)")

    return app


def create_security_headers_blueprint():
    """
    Create a Flask Blueprint that applies security headers.

    This is useful for modular Flask applications using blueprints.

    Returns:
        Flask Blueprint with security headers after_request handler

    Example:
        from flask import Flask
        from university_system.infrastructure.security.flask_security_headers import (
            create_security_headers_blueprint
        )

        app = Flask(__name__)
        security_bp = create_security_headers_blueprint()
        app.register_blueprint(security_bp)
    """
    try:
        from flask import Blueprint, request
    except ImportError:
        logger.warning("Flask not installed, cannot create security headers blueprint")
        return None

    security_bp = Blueprint('security_headers', __name__)

    @security_bp.after_app_request
    def apply_security_headers(response):
        is_authenticated = bool(request.headers.get("Authorization"))
        return add_security_headers(response, is_authenticated=is_authenticated)

    return security_bp
