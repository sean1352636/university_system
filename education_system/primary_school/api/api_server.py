"""Flask API server with app factory pattern for the Primary School system."""

from flask import Flask
from flask_cors import CORS
import logging

from education_system.primary_school.api.config import Config
from education_system.primary_school.api.errors import register_error_handlers
from education_system.primary_school.api.routes import ALL_BLUEPRINTS, ALL_INIT_FUNCS
from education_system.primary_school.infrastructure.database.schema import initialise_database, seed_default_users
from education_system.primary_school.core.paths import ensure_directories

logger = logging.getLogger(__name__)


def create_app(db_path: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    ensure_directories()

    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)

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
