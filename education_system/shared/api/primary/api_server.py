"""Flask API server with app factory pattern for the Primary School system."""

import os

from flask import Flask
from flask_cors import CORS
import logging

from education_system.shared.api.primary.config import Config
from education_system.shared.api.primary.errors import register_error_handlers
from education_system.shared.api.primary.routes import ALL_BLUEPRINTS, ALL_INIT_FUNCS
from education_system.primary_school.infrastructure.database.schema import initialise_database, seed_default_users
from education_system.primary_school.core.paths import ensure_directories

logger = logging.getLogger(__name__)


def _init_security(app: Flask) -> None:
    """Apply security headers and cookie flags."""
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

    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    if os.getenv("APP_ENV", "production").lower() not in ("development", "dev", "local", "test"):
        app.config.setdefault("SESSION_COOKIE_SECURE", True)


def create_app(db_path: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    ensure_directories()

    app = Flask(__name__)
    app.config.from_object(Config)

    allowed_origins = os.getenv("PRIMARY_CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    if allowed_origins:
        CORS(app, origins=allowed_origins)
    else:
        CORS(app, origins=["http://127.0.0.1:5002", "http://localhost:5002"])

    _init_security(app)

    # Initialize database
    from education_system.primary_school.infrastructure.database.db import get_db_path
    path = db_path or get_db_path()
    initialise_database(path)
    seed_default_users(path)

    # Initialize route modules with db_path
    for init_func in ALL_INIT_FUNCS:
        init_func(path)

    # Register blueprints
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Register error handlers
    register_error_handlers(app)

    # Shared unified auth
    from education_system.shared.api.auth import auth_bp as shared_auth_bp, init_auth
    from education_system.shared.auth.db import AUTH_DB_FILE
    init_auth(auth_db_path=str(AUTH_DB_FILE), jwt_secret=Config.JWT_SECRET_KEY)
    app.register_blueprint(shared_auth_bp)

    # Health check endpoint (Improvement #20)
    from education_system.shared.api.health import health_bp, init_health
    init_health(path, system_name="Primary School")
    app.register_blueprint(health_bp)

    # Rate limiting (Improvement #5)
    from education_system.shared.api.rate_limiter import rate_limiter
    rate_limiter.init_app(app)

    # Request middleware (Improvement #12)
    from education_system.shared.api.middleware import register_middleware
    register_middleware(app)

    logger.info("Primary School Flask app created successfully")

    return app


def run_server(db_path: str | None = None, host: str = None, port: int = None):
    """Run the Flask development server."""
    from education_system.primary_school.core.defaults import API_HOST, API_PORT, API_DEBUG
    from education_system.primary_school.core.logs import setup_logging

    setup_logging()
    app = create_app(db_path)
    h = host or API_HOST
    p = port or API_PORT
    logger.info("Primary School API server starting on %s:%d", h, p)
    print(f"\n  Primary School Management System API")
    print(f"  Running on http://{h}:{p}")
    print(f"  Press Ctrl+C to stop.\n")
    app.run(host=h, port=p, debug=API_DEBUG)
