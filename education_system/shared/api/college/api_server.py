"""Flask API server with app factory pattern."""

import os

from flask import Flask
from flask_cors import CORS
import logging

from education_system.shared.api.college.config import Config
from education_system.shared.api.college.errors import register_error_handlers
from education_system.shared.api.college.routes import ALL_BLUEPRINTS, ALL_INIT_FUNCS
from education_system.college_system.infrastructure.database.schema import init_db, seed_default_data
from education_system.college_system.core.paths import ensure_directories

logger = logging.getLogger(__name__)


def _init_security(app: Flask) -> None:
    """Apply security headers, cookie flags, and CSRF protection."""
    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data: https:; font-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';"
        )
        app_env = os.getenv("APP_ENV", "production").lower()
        if app_env not in ("development", "dev", "local", "test"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Cookie security flags
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    if os.getenv("APP_ENV", "production").lower() not in ("development", "dev", "local", "test"):
        app.config.setdefault("SESSION_COOKIE_SECURE", True)


def create_app(db_path: str | None = None, auth_db_path: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    ensure_directories()

    app = Flask(__name__)
    app.config.from_object(Config)

    # CORS with explicit origins (defaults to same-origin in production)
    allowed_origins = os.getenv("COLLEGE_CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    if allowed_origins:
        CORS(app, origins=allowed_origins)
    else:
        CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"])

    _init_security(app)

    # CSRF protection for state-changing requests (require custom header)
    @app.before_request
    def csrf_check():
        from flask import request
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            # JSON APIs: require X-Requested-With header to prevent CSRF
            # Browsers won't send this header in cross-origin form submissions
            content_type = request.content_type or ""
            if "application/json" in content_type:
                return  # JSON content type is not sent by HTML forms
            if not request.headers.get("X-Requested-With"):
                from flask import jsonify as _jsonify
                return _jsonify({"error": "Missing CSRF header"}), 403

    # Initialize database
    init_db(db_path)
    seed_default_data(db_path)

    # Initialize route modules with db_path
    from education_system.shared.api.college.routes.auth_routes import init_auth_routes
    for init_func in ALL_INIT_FUNCS:
        if init_func is init_auth_routes:
            init_func(db_path, auth_db_path=auth_db_path)
        else:
            init_func(db_path)

    # Register blueprints
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Register error handlers
    register_error_handlers(app)

    # Shared unified auth
    from education_system.shared.api.auth import auth_bp as shared_auth_bp, init_auth
    from education_system.shared.auth.db import AUTH_DB_FILE
    init_auth(auth_db_path=auth_db_path or str(AUTH_DB_FILE), jwt_secret=Config.JWT_SECRET_KEY)
    app.register_blueprint(shared_auth_bp)

    # Health check endpoint (Improvement #20)
    from education_system.shared.api.health import health_bp, init_health
    init_health(db_path, system_name="Sixth Form College")
    app.register_blueprint(health_bp)

    # Rate limiting (Improvement #5)
    from education_system.shared.api.rate_limiter import rate_limiter
    rate_limiter.init_app(app)

    # Request middleware (Improvement #12)
    from education_system.shared.api.middleware import register_middleware
    register_middleware(app)

    logger.info("Flask app created successfully")

    return app


def run_server(db_path: str | None = None, host: str = "127.0.0.1", port: int = 5000):
    """Run the Flask development server."""
    from education_system.college_system.core.defaults import API_HOST, API_PORT, API_DEBUG

    app = create_app(db_path)
    from education_system.college_system.core.logs import configure_logging
    configure_logging()
    logger.info("API server starting on %s:%d", host or API_HOST, port or API_PORT)
    print(f"\n  Sixth Form College Management System API")
    print(f"  Running on http://{host or API_HOST}:{port or API_PORT}")
    print(f"  Press Ctrl+C to stop.\n")
    app.run(host=host or API_HOST, port=port or API_PORT, debug=API_DEBUG)
