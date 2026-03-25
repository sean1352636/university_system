"""Unified API server for all education systems.

Single Flask app serving all four systems under versioned, prefixed routes:
    /api/v1/auth/*         — shared authentication (login, refresh, etc.)
    /api/v1/health/*       — health checks
    /api/v1/college/*      — Sixth Form College routes
    /api/v1/school/*       — Secondary School routes
    /api/v1/primary/*      — Primary School routes
    /api/v1/university/*   — University routes
    /api/v1/docs           — Swagger UI / OpenAPI spec

All systems share one login endpoint. The JWT contains the user's
system access list, and the system_required() decorator gates routes.
"""

import os
import logging
from copy import deepcopy

from flask import Flask, jsonify, redirect
from flask_cors import CORS

logger = logging.getLogger(__name__)

API_VERSION = "v1"


def _init_security(app: Flask) -> None:
    """Apply security headers and cookie flags."""
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if not getattr(response, "_custom_csp", False):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: https:; "
                "font-src 'self' data: https://fonts.gstatic.com; "
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


def _reprefix(url_prefix: str, system: str) -> str:
    """Convert '/api/students' → '/api/v1/college/students'."""
    if url_prefix and url_prefix.startswith("/api"):
        return f"/api/{API_VERSION}/{system}" + url_prefix[4:]
    return f"/api/{API_VERSION}/{system}{url_prefix or ''}"


def _register_system_blueprints(app: Flask, blueprints, init_funcs, db_path,
                                system_prefix: str, system_label: str,
                                auth_db_path=None):
    """Register a system's blueprints with prefixed names and URLs."""
    # Init route modules
    for init_func in init_funcs:
        try:
            # Some init funcs accept auth_db_path
            import inspect
            sig = inspect.signature(init_func)
            if 'auth_db_path' in sig.parameters:
                init_func(db_path, auth_db_path=auth_db_path)
            else:
                init_func(db_path)
        except Exception as e:
            logger.warning("Init %s failed: %s", init_func.__name__, e)

    # Register blueprints with unique names and system-prefixed URLs
    for bp in blueprints:
        new_prefix = _reprefix(bp.url_prefix, system_prefix)
        new_name = f"{system_prefix}_{bp.name}"
        app.register_blueprint(bp, url_prefix=new_prefix, name=new_name)

    logger.info("Registered %d %s routes under /api/%s/%s/",
                len(blueprints), system_label, API_VERSION, system_prefix)


def create_unified_app() -> Flask:
    """Create the unified Flask application serving all systems."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("API_SECRET_KEY", os.urandom(32).hex())
    app.config["JSON_SORT_KEYS"] = False
    # Request size limit (default 16 MB)
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("API_MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # CORS
    allowed_origins = os.getenv("API_CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    if allowed_origins:
        CORS(app, origins=allowed_origins)
    else:
        # Allow any origin so other devices on the network can access the API.
        # The CSRF check (Origin/Referer matching request.host) still prevents
        # cross-site attacks from unrelated origins.
        CORS(app, origins="*")

    _init_security(app)

    # CSRF protection for all mutating requests
    @app.before_request
    def csrf_check():
        from flask import request
        from urllib.parse import urlparse
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            content_type = request.content_type or ""
            if "application/json" in content_type:
                # For JSON requests, validate Origin/Referer to prevent
                # cross-origin attacks (browsers always send these headers)
                origin = request.headers.get("Origin")
                referer = request.headers.get("Referer")
                if not origin and not referer:
                    # Non-browser client (e.g. curl, API SDK) — allow
                    return
                server_host = request.host  # includes port
                if origin:
                    parsed = urlparse(origin)
                    origin_host = parsed.netloc or parsed.path
                    if origin_host != server_host:
                        return jsonify({"error": "Origin mismatch — request blocked"}), 403
                elif referer:
                    parsed = urlparse(referer)
                    if parsed.netloc != server_host:
                        return jsonify({"error": "Referer mismatch — request blocked"}), 403
                return
            if not request.headers.get("X-Requested-With"):
                return jsonify({"error": "Missing CSRF header"}), 403

    # ── Shared auth ─────────────────────────────────────────────────────
    from education_system.shared.api.auth import auth_bp, init_auth
    from education_system.shared.auth.db import AUTH_DB_FILE
    # Let init_auth use its own securely generated default if env var is unset
    jwt_secret = os.getenv("JWT_SECRET_KEY") or None
    init_auth(auth_db_path=str(AUTH_DB_FILE), jwt_secret=jwt_secret)
    app.register_blueprint(auth_bp, url_prefix=f"/api/{API_VERSION}/auth")

    # ── Health check ────────────────────────────────────────────────────
    from education_system.shared.api.health import health_bp, init_health
    init_health(system_name="Education System (Unified)")
    app.register_blueprint(health_bp, url_prefix=f"/api/{API_VERSION}")

    # ── API documentation (Swagger UI + OpenAPI spec) ───────────────────
    from education_system.shared.api.docs import docs_bp as api_docs_bp
    app.register_blueprint(api_docs_bp)

    # ── API key authentication ────────────────────────────────────────
    from education_system.shared.api.api_keys import init_api_keys
    try:
        init_api_keys(str(AUTH_DB_FILE))
    except Exception as e:
        logger.warning("API key init failed (non-fatal): %s", e)

    # ── Rate limiting ───────────────────────────────────────────────────
    from education_system.shared.api.rate_limiter import rate_limiter
    rate_limiter.init_app(app)

    # ── Caching middleware ────────────────────────────────────────────
    from education_system.shared.api.caching import register_caching_middleware
    register_caching_middleware(app)

    # ── Middleware ──────────────────────────────────────────────────────
    from education_system.shared.api.middleware import register_middleware
    register_middleware(app)

    # ── Web frontend (login + dashboard) ─────────────────────────────
    from education_system.shared.api.web.routes import web_bp
    app.register_blueprint(web_bp)


    # ── College system ──────────────────────────────────────────────────
    try:
        from education_system.college_system.core.paths import ensure_directories as college_ensure
        from education_system.college_system.infrastructure.database.schema import (
            init_db as college_init_db, seed_default_data as college_seed,
        )
        from education_system.shared.api.college.routes import ALL_BLUEPRINTS as college_bps, ALL_INIT_FUNCS as college_inits

        college_ensure()
        college_init_db()
        college_seed()
        _register_system_blueprints(app, college_bps, college_inits, None,
                                    "college", "Sixth Form College",
                                    auth_db_path=str(AUTH_DB_FILE))
    except Exception as e:
        logger.error("Failed to load college system: %s", e)

    # ── Secondary school ────────────────────────────────────────────────
    try:
        from education_system.secondary_school.core.paths import ensure_directories as school_ensure
        from education_system.secondary_school.infrastructure.database.schema import (
            initialise_database as school_init_db, seed_default_users as school_seed,
            seed_default_staff as school_seed_staff,
        )
        from education_system.shared.api.secondary.routes import ALL_BLUEPRINTS as school_bps, ALL_INIT_FUNCS as school_inits

        school_ensure()
        school_init_db()
        school_seed()
        school_seed_staff()
        _register_system_blueprints(app, school_bps, school_inits, None,
                                    "school", "Secondary School",
                                    auth_db_path=str(AUTH_DB_FILE))
    except Exception as e:
        logger.error("Failed to load secondary school system: %s", e)

    # ── Primary school ──────────────────────────────────────────────────
    try:
        from education_system.primary_school.core.paths import ensure_directories as primary_ensure
        from education_system.primary_school.infrastructure.database.db import get_db_path as primary_db_path
        from education_system.primary_school.infrastructure.database.schema import (
            initialise_database as primary_init_db, seed_default_users as primary_seed,
            seed_default_staff as primary_seed_staff,
        )
        from education_system.shared.api.primary.routes import ALL_BLUEPRINTS as primary_bps, ALL_INIT_FUNCS as primary_inits

        primary_ensure()
        p_db = primary_db_path()
        primary_init_db(p_db)
        primary_seed(p_db)
        primary_seed_staff(p_db)
        _register_system_blueprints(app, primary_bps, primary_inits, p_db,
                                    "primary", "Primary School",
                                    auth_db_path=str(AUTH_DB_FILE))
    except Exception as e:
        logger.error("Failed to load primary school system: %s", e)

    # ── University system ───────────────────────────────────────────────
    try:
        from education_system.university_system.core.paths import ensure_directories as uni_ensure
        from education_system.university_system.infrastructure.database.database_utils import (
            init_db as uni_init_db,
        )

        uni_ensure()
        uni_init_db()

        # Import all university blueprints and register them under /api/v1/university/
        from education_system.shared.api.university.routes import (
            system_bp, auth_bp as uni_auth_bp, student_bp, module_bp,
            enrollment_bp, grade_bp, finance_bp, attendance_bp, assignment_bp,
            timetable_bp, course_bp, user_bp, dashboard_bp, housing_bp,
            library_bp, health_bp, facility_bp, career_bp, research_bp,
            admission_bp, alumni_bp, event_bp, dining_bp, notification_bp,
            mentorship_bp, parking_bp, club_bp, security_bp, lost_found_bp,
            scholarship_bp, study_group_bp, exam_bp, calendar_bp,
            assessment_bp, financial_aid_bp, degree_bp, announcement_bp,
            advising_bp, accommodation_bp, tutoring_bp, early_warning_bp,
            chat_bp, hr_bp, helpdesk_bp, parent_bp, lms_bp, integrity_bp,
            campus_bp, evaluation_bp, communication_bp, counseling_bp,
            emergency_bp, virtual_classroom_bp, equipment_bp, election_bp,
            document_bp, credential_bp, office_hours_bp, ta_bp, mfa_bp,
            account_bp, docs_bp, web_bp as uni_web_bp,
        )

        _uni_bps = [
            system_bp, student_bp, module_bp, enrollment_bp, grade_bp,
            finance_bp, attendance_bp, assignment_bp, timetable_bp,
            course_bp, user_bp, dashboard_bp, housing_bp, library_bp,
            health_bp, facility_bp, career_bp, research_bp, admission_bp,
            alumni_bp, event_bp, dining_bp, notification_bp, mentorship_bp,
            parking_bp, club_bp, security_bp, lost_found_bp, scholarship_bp,
            study_group_bp, exam_bp, calendar_bp, assessment_bp,
            financial_aid_bp, degree_bp, announcement_bp, advising_bp,
            accommodation_bp, tutoring_bp, early_warning_bp, chat_bp,
            hr_bp, helpdesk_bp, parent_bp, lms_bp, integrity_bp, campus_bp,
            evaluation_bp, communication_bp, counseling_bp, emergency_bp,
            virtual_classroom_bp, equipment_bp, election_bp, document_bp,
            credential_bp, office_hours_bp, ta_bp, mfa_bp, account_bp,
        ]

        for bp in _uni_bps:
            new_prefix = _reprefix(bp.url_prefix, "university")
            new_name = f"university_{bp.name}"
            app.register_blueprint(bp, url_prefix=new_prefix, name=new_name)

        logger.info("Registered university routes under /api/%s/university/", API_VERSION)
    except Exception as e:
        logger.error("Failed to load university system: %s", e)

    # ── Backward-compatibility redirects ─────────────────────────────
    @app.before_request
    def redirect_unversioned():
        """Redirect old /api/<system>/... to /api/v1/<system>/..."""
        from flask import request
        path = request.path
        # Only redirect /api/<known-prefix> that is NOT already versioned
        if path.startswith("/api/") and not path.startswith(f"/api/{API_VERSION}/"):
            for prefix in ("college", "school", "primary", "university", "auth", "health"):
                if path.startswith(f"/api/{prefix}"):
                    new_path = f"/api/{API_VERSION}" + path[4:]
                    return redirect(new_path, code=307)

    # ── Index route ─────────────────────────────────────────────────────
    @app.route("/")
    @app.route("/api")
    @app.route(f"/api/{API_VERSION}")
    def index():
        return jsonify({
            "service": "Education System API",
            "version": API_VERSION,
            "auth": f"/api/{API_VERSION}/auth/login",
            "health": f"/api/{API_VERSION}/health",
            "docs": f"/api/{API_VERSION}/docs",
            "systems": {
                "university": f"/api/{API_VERSION}/university/",
                "college": f"/api/{API_VERSION}/college/",
                "school": f"/api/{API_VERSION}/school/",
                "primary": f"/api/{API_VERSION}/primary/",
            },
        })

    # ── Error handlers ──────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(413)
    def request_too_large(e):
        max_mb = app.config.get("MAX_CONTENT_LENGTH", 0) / (1024 * 1024)
        return jsonify({
            "error": "Request entity too large",
            "message": f"Maximum request size is {max_mb:.0f} MB",
        }), 413

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Rate limit exceeded"}), 429

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    # Payload validation errors
    from education_system.shared.api.request_validator import PayloadValidationError

    @app.errorhandler(PayloadValidationError)
    def handle_payload_validation(e):
        return jsonify({
            "error": "Validation Error",
            "message": str(e),
            "details": e.errors,
        }), 422

    logger.info("Unified API server created (version=%s)", API_VERSION)
    return app


def run_unified_api(host: str | None = None, port: int | None = None):
    """Run the unified API server."""
    host = host or os.getenv("API_HOST", "0.0.0.0")
    port = port or int(os.getenv("API_PORT", "5000"))
    app = create_unified_app()
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    print(f"\n  Education System — Unified API ({API_VERSION})")
    print(f"  Running on http://{host}:{port}")
    print(f"  Web UI:     http://{host}:{port}/web/login")
    print(f"  Auth:       POST http://{host}:{port}/api/{API_VERSION}/auth/login")
    print(f"  Docs:       http://{host}:{port}/api/{API_VERSION}/docs")
    print(f"  College:    http://{host}:{port}/api/{API_VERSION}/college/...")
    print(f"  School:     http://{host}:{port}/api/{API_VERSION}/school/...")
    print(f"  Primary:    http://{host}:{port}/api/{API_VERSION}/primary/...")
    print(f"  University: http://{host}:{port}/api/{API_VERSION}/university/...")
    print(f"  Health:     http://{host}:{port}/api/{API_VERSION}/health")
    print(f"  Press Ctrl+C to stop.\n")
    app.run(host=host, port=port, debug=debug)
