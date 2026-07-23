"""Flask API server for University Management System (standalone mode).

Replaces the legacy BaseHTTPRequestHandler with a Flask app factory
that reuses the same blueprints registered in the unified server.
"""

import datetime
import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

logger = logging.getLogger(__name__)


def create_app(config_path: str | None = None) -> Flask:
    """Create and configure the standalone University Flask application."""
    from education_system.shared.api.university.config import load_config

    config = load_config(config_path)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = config["jwt"]["secret_key"]
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = config.get("max_content_length", 16 * 1024 * 1024)

    # CORS
    allowed_origins = os.getenv("UNI_CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    if allowed_origins:
        CORS(app, origins=allowed_origins)
    else:
        CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"])

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not getattr(response, "_custom_csp", False):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; font-src 'self' data:; "
                "connect-src 'self'; frame-ancestors 'none'; "
                "base-uri 'self'; form-action 'self';"
            )
        app_env = os.getenv("APP_ENV", "production").lower()
        if app_env not in ("development", "dev", "local", "test"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Initialise database
    from education_system.post_18.university_system.core.paths import ensure_directories
    from education_system.post_18.university_system.infrastructure.database.database_utils import init_db

    ensure_directories()
    init_db()

    # Register all university route blueprints
    from education_system.shared.api.university.routes import (
        system_bp, student_bp, module_bp, enrollment_bp, grade_bp,
        finance_bp, attendance_bp, assignment_bp, timetable_bp, course_bp,
        user_bp, dashboard_bp, housing_bp, library_bp, health_bp,
        facility_bp, career_bp, research_bp, admission_bp, alumni_bp,
        event_bp, dining_bp, notification_bp, mentorship_bp, parking_bp,
        club_bp, security_bp, lost_found_bp, scholarship_bp, study_group_bp,
        exam_bp, calendar_bp, assessment_bp, financial_aid_bp, degree_bp,
        announcement_bp, advising_bp, accommodation_bp, tutoring_bp,
        early_warning_bp, chat_bp, hr_bp, helpdesk_bp, parent_bp, lms_bp,
        integrity_bp, campus_bp, evaluation_bp, communication_bp,
        counseling_bp, emergency_bp, virtual_classroom_bp, equipment_bp,
        election_bp, document_bp, credential_bp, office_hours_bp, ta_bp,
        mfa_bp, account_bp, docs_bp, absence_bp,
    )

    for bp in [
        system_bp, student_bp, module_bp, enrollment_bp, grade_bp,
        finance_bp, attendance_bp, assignment_bp, timetable_bp, course_bp,
        user_bp, dashboard_bp, housing_bp, library_bp, health_bp,
        facility_bp, career_bp, research_bp, admission_bp, alumni_bp,
        event_bp, dining_bp, notification_bp, mentorship_bp, parking_bp,
        club_bp, security_bp, lost_found_bp, scholarship_bp, study_group_bp,
        exam_bp, calendar_bp, assessment_bp, financial_aid_bp, degree_bp,
        announcement_bp, advising_bp, accommodation_bp, tutoring_bp,
        early_warning_bp, chat_bp, hr_bp, helpdesk_bp, parent_bp, lms_bp,
        integrity_bp, campus_bp, evaluation_bp, communication_bp,
        counseling_bp, emergency_bp, virtual_classroom_bp, equipment_bp,
        election_bp, document_bp, credential_bp, office_hours_bp, ta_bp,
        mfa_bp, account_bp, docs_bp, absence_bp,
    ]:
        app.register_blueprint(bp)

    # Shared authentication
    from education_system.shared.api.auth import auth_bp, init_auth
    from education_system.shared.auth.db import AUTH_DB_FILE
    init_auth(auth_db_path=str(AUTH_DB_FILE), jwt_secret=config["jwt"]["secret_key"])
    app.register_blueprint(auth_bp)

    # Health check
    from education_system.shared.api.health import health_bp as shared_health_bp, init_health
    init_health(system_name="University Management System")
    app.register_blueprint(shared_health_bp)

    # Rate limiting
    from education_system.shared.api.rate_limiter import rate_limiter
    rate_limiter.init_app(app)

    # Middleware
    from education_system.shared.api.middleware import register_middleware
    register_middleware(app)

    # Legacy compatibility endpoints
    _start_time = datetime.datetime.now(datetime.timezone.utc)

    @app.route("/api/status")
    def api_status():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "version": "1.0.0",
        })

    @app.route("/api/metrics")
    def api_metrics():
        uptime = (datetime.datetime.now(datetime.timezone.utc) - _start_time).total_seconds()
        return jsonify({
            "uptime_seconds": int(uptime),
            "status": "healthy",
        })

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    logger.info("University standalone Flask app created")
    return app


def run_api_server(host: str = "localhost", port: int = 5000):
    """Run the University API server."""
    app = create_app()
    debug = os.getenv("UNI_API_DEBUG", "false").lower() == "true"
    print("\n  University Management System API")
    print(f"  Running on http://{host}:{port}")
    print(f"  Docs:    http://{host}:{port}/api/docs")
    print(f"  Health:  http://{host}:{port}/api/health")
    print("  Press Ctrl+C to stop.\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_api_server()
