"""Flask application factory and server runner for the University Management System API.

Usage:
    from university_system.api.api_server import create_app, run_api_server

    # Create the app (useful for testing / WSGI)
    app = create_app()

    # Or start the dev server directly
    run_api_server()
"""

from __future__ import annotations

import logging
import os
import sys

from flask import Flask, jsonify, request
from flask_cors import CORS

from university_system.api.auth import check_rate_limit
from university_system.api.config import load_config
from university_system.api.errors import register_error_handlers
from university_system.api.routes import register_routes

logger = logging.getLogger(__name__)


def create_app(config_path: str | None = None) -> Flask:
    """Application factory – returns a fully configured Flask instance."""
    app = Flask(__name__)

    # Load configuration
    api_config = load_config(config_path)
    app.config["API_CONFIG"] = api_config
    app.config["DEBUG"] = api_config.get("debug", False)

    # CORS - restrict to configured origins
    allowed_origins = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')
    CORS(app, origins=allowed_origins, supports_credentials=True)

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
    from university_system.infrastructure.database.database_utils import init_db

    init_db()

    # Initialise auth system
    from university_system.infrastructure.auth import UserAuth
    from university_system.infrastructure.shared_context import set_auth, is_auth_initialized

    if not is_auth_initialized():
        auth_instance = UserAuth()
        set_auth(auth_instance)

    # Build and run the app
    app = create_app(config_path)
    api_config = app.config["API_CONFIG"]

    host = api_config.get("host", "localhost")
    port = api_config.get("port", 5000)
    debug = api_config.get("debug", False)

    print(f"Starting University Management System API on http://{host}:{port}")
    print("Press Ctrl+C to stop the server")
    app.run(host=host, port=port, debug=debug)
