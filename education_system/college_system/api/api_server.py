"""Flask API server with app factory pattern."""

from flask import Flask
from flask_cors import CORS
import logging

from education_system.college_system.api.config import Config
from education_system.college_system.api.errors import register_error_handlers
from education_system.college_system.api.routes import ALL_BLUEPRINTS, ALL_INIT_FUNCS
from education_system.college_system.infrastructure.database.schema import init_db, seed_default_data
from education_system.college_system.core.paths import ensure_directories

logger = logging.getLogger(__name__)


def create_app(db_path: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    ensure_directories()

    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)

    # Initialize database
    init_db(db_path)
    seed_default_data(db_path)

    # Initialize route modules with db_path
    for init_func in ALL_INIT_FUNCS:
        init_func(db_path)

    # Register blueprints
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Register error handlers
    register_error_handlers(app)

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
