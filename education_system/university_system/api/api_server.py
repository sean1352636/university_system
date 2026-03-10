"""Flask application factory and server runner for the University Management System API.

Usage:
    from education_system.university_system.api.api_server import create_app, run_api_server

    # Create the app (useful for testing / WSGI)
    app = create_app()

    # Or start the dev server directly
    run_api_server()
"""

from __future__ import annotations

import logging
import os
import re
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS

from education_system.university_system.api.auth import check_rate_limit
from education_system.university_system.api.config import load_config
from education_system.university_system.api.errors import register_error_handlers
from education_system.university_system.api.routes import register_routes
from education_system.university_system.infrastructure.security.flask_security_headers import (
    init_security_headers,
)

logger = logging.getLogger(__name__)

# Matches scheme://host[:port] with no trailing path
_ORIGIN_RE = re.compile(r"^https?://[a-zA-Z0-9._-]+(:\d{1,5})?$")

_DEV_ENVS = {"development", "dev", "local"}


def _validate_cors_origin(origin: str) -> bool:
    """Return True if *origin* looks like a valid scheme://host[:port] string."""
    return bool(_ORIGIN_RE.match(origin))


def _get_cors_origins(api_config: dict) -> list[str]:
    """Build a validated list of allowed CORS origins.

    * ``CORS_ALLOWED_ORIGINS`` env var takes precedence (comma-separated).
    * In development (``APP_ENV`` in {development, dev, local}): defaults to
      ``["http://localhost:3000"]`` when no env var is set.
    * In production: defaults to an **empty** list (no cross-origin requests)
      when no env var is set.

    Invalid origins are silently dropped with a warning.
    """
    app_env = os.environ.get("APP_ENV", "production").lower()
    is_dev = app_env in _DEV_ENVS

    env_origins = os.environ.get("CORS_ALLOWED_ORIGINS")
    if env_origins is not None:
        raw = [o.strip() for o in env_origins.split(",") if o.strip()]
    elif is_dev:
        raw = ["http://localhost:3000"]
    else:
        logger.warning(
            "CORS_ALLOWED_ORIGINS is not set and APP_ENV=%s; "
            "no cross-origin requests will be allowed",
            app_env,
        )
        return []

    valid: list[str] = []
    for origin in raw:
        if _validate_cors_origin(origin):
            valid.append(origin)
        else:
            logger.warning("Ignoring invalid CORS origin: %r", origin)

    return valid


def _resolve_debug(api_config: dict) -> bool:
    """Determine whether debug mode should be enabled.

    Debug mode is only permitted when ``APP_ENV`` is a development value
    **and** the config file sets ``debug: true``.  In production, debug
    is always forced to ``False`` regardless of the config file.
    """
    app_env = os.environ.get("APP_ENV", "production").lower()
    is_dev = app_env in _DEV_ENVS
    config_debug = api_config.get("debug", False)

    if config_debug and not is_dev:
        logger.warning(
            "Config has debug=true but APP_ENV=%s; forcing debug=False",
            app_env,
        )
        return False

    return bool(config_debug and is_dev)


def create_app(config_path: str | None = None) -> Flask:
    """Application factory – returns a fully configured Flask instance."""
    app = Flask(__name__)

    # Load configuration
    api_config = load_config(config_path)
    app.config["API_CONFIG"] = api_config

    # Debug mode — only allowed in development environments
    app.config["DEBUG"] = _resolve_debug(api_config)

    # Request body size limit (default 16 MB)
    app.config["MAX_CONTENT_LENGTH"] = api_config.get(
        "max_content_length", 16 * 1024 * 1024
    )

    # CORS — validate origins, safe default per environment
    CORS(app, origins=_get_cors_origins(api_config), supports_credentials=True)

    # Security headers & cookie hardening
    init_security_headers(app)

    # Error handlers
    register_error_handlers(app)

    # Rate limiting (before every request)
    @app.before_request
    def _rate_limit():
        result = check_rate_limit(api_config)
        if result is not None:
            return result

    # Register blueprints
    register_routes(app)

    logger.info("Flask API application created")
    return app


def run_api_server(config_path: str | None = None) -> None:
    """Initialise the system and start the Flask development server."""
    # Ensure project root is on the path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Initialise database
    from education_system.university_system.infrastructure.database.database_utils import init_db

    init_db()

    # Initialise auth system
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import set_auth, is_auth_initialized

    if not is_auth_initialized():
        auth_instance = UserAuth()
        set_auth(auth_instance)

    # Build and run the app
    app = create_app(config_path)
    api_config = app.config["API_CONFIG"]

    host = api_config.get("host", "localhost")
    port = api_config.get("port", 5000)
    debug = _resolve_debug(api_config)

    logger.info("Starting University Management System API on http://%s:%s", host, port)
    logger.info("Press Ctrl+C to stop the server")
    app.run(host=host, port=port, debug=debug)
