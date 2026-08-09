"""Flask API server for University Management System (standalone mode).

Replaces the legacy BaseHTTPRequestHandler with a Flask app factory
that reuses the same blueprints registered in the unified server.
"""

import datetime
import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS

from education_system.platform.delivery.api.security_headers import (
    is_development,
    register_security_headers,
)

logger = logging.getLogger(__name__)


def create_app(config_path: str | None = None) -> Flask:
    """Create and configure the standalone University Flask application."""
    from education_system.platform.delivery.api.university.config import load_config

    config = load_config(config_path)

    app = Flask(__name__)
    app.config["SECRET_KEY"] = config["jwt"]["secret_key"]
    app.config["JSON_SORT_KEYS"] = False
    app.config["MAX_CONTENT_LENGTH"] = config.get("max_content_length", 16 * 1024 * 1024)

    # CORS — fail closed, matching the unified server. The previous fallback
    # applied a localhost allow-list in *every* environment, so a production
    # deployment that forgot UNI_CORS_ORIGINS silently ran a development CORS
    # policy instead of refusing to start.
    allowed_origins = os.getenv("UNI_CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    if allowed_origins:
        CORS(app, origins=allowed_origins)
    elif is_development():
        CORS(app, origins=["http://127.0.0.1:5000", "http://localhost:5000"])
    else:
        raise RuntimeError(
            "UNI_CORS_ORIGINS must be set in production. Refusing to start "
            "with a development CORS allow-list. Set it to a comma-separated "
            "list of trusted origins."
        )

    # Security headers, cookie flags and the production debug guard — shared
    # policy, so this app cannot drift from the unified server's floor.
    register_security_headers(app)

    # Initialise database
    from education_system.paths import ensure_university_directories
    from education_system.systems.university.infrastructure.database.schema_version import (
        require_supported_schema,
    )

    ensure_university_directories()
    require_supported_schema()

    # Register all university route blueprints
    from education_system.systems.university.interfaces.api.routes import (
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
        mfa_bp, account_bp, docs_bp, absence_bp, operations_bp,
        student_lifecycle_bp,
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
        mfa_bp, account_bp, docs_bp, absence_bp, operations_bp,
        student_lifecycle_bp,
    ]:
        app.register_blueprint(bp)

    # Shared authentication
    from education_system.platform.delivery.api.auth import auth_bp, init_auth
    from education_system.platform.identity.auth.db import AUTH_DB_FILE
    app.config["AUTH_DB_PATH"] = str(AUTH_DB_FILE)
    init_auth(auth_db_path=str(AUTH_DB_FILE), jwt_secret=config["jwt"]["secret_key"])
    app.register_blueprint(auth_bp)

    from education_system.platform.governance.security.csrf import register_csrf_middleware
    register_csrf_middleware(app)

    # Standalone mode must enforce the same authenticated tenant boundary as
    # the unified server; client-supplied tenant selectors are assertions only.
    from education_system.platform.delivery.api.tenant_middleware import register_tenant_middleware
    from education_system.platform.kernel.core.tenant_models import init_tenant_db
    tenant_db = os.path.join(os.path.dirname(str(AUTH_DB_FILE)), "tenants.db")
    init_tenant_db(tenant_db)
    register_tenant_middleware(app, tenants_db_path=tenant_db)

    # Health check
    from education_system.platform.delivery.api.health import health_bp as shared_health_bp, init_health
    init_health(system_name="University Management System")
    app.register_blueprint(shared_health_bp)

    # Rate limiting
    from education_system.platform.delivery.api.rate_limiter import rate_limiter
    rate_limiter.init_app(app)

    # Middleware
    from education_system.platform.delivery.api.middleware import register_middleware
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
    if debug and not is_development():
        # register_security_headers checked app.debug at creation time, but
        # app.run(debug=True) flips it afterwards — so the guard must also
        # sit here, exactly as run_unified_api does for API_DEBUG.
        raise RuntimeError(
            "UNI_API_DEBUG=true is refused because APP_ENV is production. "
            "The debugger exposes stack traces and a remote console."
        )
    print("\n  University Management System API")
    print(f"  Running on http://{host}:{port}")
    print(f"  Docs:    http://{host}:{port}/api/docs")
    print(f"  Health:  http://{host}:{port}/api/health")
    print("  Press Ctrl+C to stop.\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_api_server()
