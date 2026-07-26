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

from education_system.platform.kernel.core.structured_logging import setup_structured_logging

# Initialise structured logging as early as possible so every record
# (including blueprint registration warnings) uses the JSON formatter.
setup_structured_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_format=os.getenv("LOG_FORMAT", "json"),
    system="unified",
)

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

    # Disable werkzeug's default request logger — the custom middleware
    # already logs every request with timing and request_id.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # Flask SECRET_KEY. A random per-process key silently invalidates every
    # signed cookie/session on each restart and worker, so production must
    # supply a persistent API_SECRET_KEY. Dev/test may fall back to a random
    # ephemeral key. Fail closed otherwise — matches JWT_SECRET_KEY handling.
    _app_env = os.getenv("APP_ENV", "production").lower()
    _is_dev = _app_env in ("development", "dev", "local", "test")
    _api_secret = os.getenv("API_SECRET_KEY")
    if not _api_secret:
        if not _is_dev:
            raise RuntimeError(
                "API_SECRET_KEY environment variable is required in production. "
                "A random per-process key invalidates sessions on every restart. "
                "Set a persistent API_SECRET_KEY via env/secret manager."
            )
        _api_secret = os.urandom(32).hex()
        logger.warning(
            "API_SECRET_KEY not set — using an ephemeral random key (dev only). "
            "Sessions will not survive a restart. Set API_SECRET_KEY before deploying."
        )
    app.config["SECRET_KEY"] = _api_secret
    app.config["JSON_SORT_KEYS"] = False
    # Request size limit (default 16 MB)
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("API_MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # CORS — fail closed. Production requires an explicit allow-list;
    # development falls back to localhost only, never "*".
    allowed_origins = os.getenv("API_CORS_ORIGINS", "").split(",")
    allowed_origins = [o.strip() for o in allowed_origins if o.strip()]
    app_env = os.getenv("APP_ENV", "production").lower()
    is_dev = app_env in ("development", "dev", "local", "test")
    if allowed_origins:
        CORS(app, origins=allowed_origins)
    elif is_dev:
        dev_origins = [
            "http://localhost:5000", "http://127.0.0.1:5000",
            "http://localhost:3000", "http://127.0.0.1:3000",
        ]
        logger.warning(
            "API_CORS_ORIGINS not set — defaulting to localhost origins in dev mode. "
            "Set API_CORS_ORIGINS for any non-dev deployment."
        )
        CORS(app, origins=dev_origins)
    else:
        raise RuntimeError(
            "API_CORS_ORIGINS must be set in production. Refuse to start with "
            "a wildcard CORS policy. Set API_CORS_ORIGINS to a comma-separated "
            "list of trusted origins (e.g. 'https://app.example.com')."
        )

    _init_security(app)

    # CSRF protection for all mutating requests.
    #
    # Mutating JSON requests must present either a same-origin Origin or
    # Referer header. Non-browser API clients (curl, SDKs) can either send
    # an explicit Origin matching the server host, or authenticate with a
    # Bearer token — bearer-token requests are exempt because the token
    # itself is not an ambient credential (no CSRF surface).
    @app.before_request
    def csrf_check():
        from flask import request
        from urllib.parse import urlparse
        if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
            return

        # Bearer-token auth carries no ambient credential — CSRF doesn't apply.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return

        content_type = request.content_type or ""
        is_json = "application/json" in content_type

        if is_json:
            origin = request.headers.get("Origin")
            referer = request.headers.get("Referer")
            if not origin and not referer:
                return jsonify({
                    "error": "Missing Origin/Referer — request blocked",
                }), 403
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
    from education_system.platform.delivery.api.auth import auth_bp, init_auth
    from education_system.platform.identity.auth.db import AUTH_DB_FILE
    # Let init_auth use its own securely generated default if env var is unset
    jwt_secret = os.getenv("JWT_SECRET_KEY") or None
    init_auth(auth_db_path=str(AUTH_DB_FILE), jwt_secret=jwt_secret)
    app.register_blueprint(auth_bp, url_prefix=f"/api/{API_VERSION}/auth")

    # ── Scheduled audit / rate-limit cleanup ─────────────────────────
    try:
        from education_system.platform.identity.auth.audit_scheduler import start_cleanup_scheduler
        start_cleanup_scheduler(str(AUTH_DB_FILE))
    except Exception as e:
        logger.warning("Audit cleanup scheduler failed to start (non-fatal): %s", e)

    # ── Health check ────────────────────────────────────────────────────
    from education_system.platform.delivery.api.health import health_bp, init_health
    init_health(system_name="Education System (Unified)")
    app.register_blueprint(health_bp, url_prefix=f"/api/{API_VERSION}")

    # ── Metrics (Prometheus + enriched health) ───────────────────────
    from education_system.platform.delivery.api.metrics_routes import metrics_bp, init_metrics
    init_metrics(
        db_paths={"auth": str(AUTH_DB_FILE)},
        system_name="Education System (Unified)",
    )
    app.register_blueprint(metrics_bp)

    # ── GDPR data retention ──────────────────────────────────────────────
    try:
        from education_system.platform.delivery.api.retention_routes import retention_bp, init_retention
        init_retention()
        app.register_blueprint(retention_bp, url_prefix=f"/api/{API_VERSION}/retention")
        logger.info("Registered retention routes under /api/%s/retention/", API_VERSION)
    except Exception as e:
        logger.warning("Failed to load retention routes (non-fatal): %s", e)

    # ── Cross-system single student view ─────────────────────────────────
    try:
        from education_system.platform.delivery.api.journey_routes import (
            journey_bp, init_journey_routes,
        )
        init_journey_routes()
        app.register_blueprint(
            journey_bp, url_prefix=f"/api/{API_VERSION}/journey")
        logger.info("Registered journey routes under /api/%s/journey/", API_VERSION)
    except Exception as e:
        logger.warning("Failed to load journey routes (non-fatal): %s", e)

    # ── Cross-system reporting warehouse ─────────────────────────────────
    try:
        from education_system.platform.delivery.api.warehouse_routes import (
            warehouse_bp, init_warehouse_routes,
        )
        init_warehouse_routes()
        app.register_blueprint(
            warehouse_bp, url_prefix=f"/api/{API_VERSION}/warehouse")
        logger.info("Registered warehouse routes under /api/%s/warehouse/", API_VERSION)
    except Exception as e:
        logger.warning("Failed to load warehouse routes (non-fatal): %s", e)

    # ── LMS integration (Canvas, Moodle, Google Classroom) ───────────────
    try:
        from education_system.platform.delivery.api.lms_routes import lms_bp, init_lms_routes
        import os as _os
        _lms_db = _os.getenv(
            "LMS_DB_PATH",
            str(AUTH_DB_FILE).replace("auth.db", "lms_integrations.db"),
        )
        init_lms_routes(_lms_db)
        app.register_blueprint(lms_bp, url_prefix=f"/api/{API_VERSION}/lms")
        logger.info("Registered LMS integration routes under /api/%s/lms/", API_VERSION)
    except Exception as e:
        logger.warning("Failed to load LMS integration routes (non-fatal): %s", e)

    # ── Webhook management ───────────────────────────────────────────────
    try:
        from education_system.platform.delivery.api.webhook_routes import webhook_bp, init_webhook_routes
        init_webhook_routes()
        app.register_blueprint(webhook_bp, url_prefix=f"/api/{API_VERSION}/webhooks")
        logger.info("Registered webhook routes under /api/%s/webhooks/", API_VERSION)
    except Exception as e:
        logger.warning("Failed to load webhook routes (non-fatal): %s", e)

    # ── API documentation (Swagger UI + OpenAPI spec) ───────────────────
    from education_system.platform.delivery.api.docs import docs_bp as api_docs_bp
    app.register_blueprint(api_docs_bp)

    # ── API key authentication ────────────────────────────────────────
    from education_system.platform.delivery.api.api_keys import init_api_keys
    try:
        init_api_keys(str(AUTH_DB_FILE))
    except Exception:
        logger.warning("API key init failed (non-fatal)")

    # ── Rate limiting ───────────────────────────────────────────────────
    from education_system.platform.delivery.api.rate_limiter import rate_limiter
    rate_limiter.init_app(app)

    # ── Caching middleware ────────────────────────────────────────────
    from education_system.platform.delivery.api.caching import register_caching_middleware
    register_caching_middleware(app)

    # ── Middleware ──────────────────────────────────────────────────────
    from education_system.platform.delivery.api.middleware import register_middleware
    register_middleware(app)

    # ── Multi-tenancy middleware + routes ─────────────────────────────
    try:
        from education_system.platform.delivery.api.tenant_middleware import register_tenant_middleware
        from education_system.platform.delivery.api.tenant_routes import tenant_bp, init_tenant_routes
        from education_system.platform.kernel.core.tenant_models import init_tenant_db
        from education_system.platform.identity.auth.db import AUTH_DB_FILE as _AUTH_DB_FILE_INNER

        # Central tenants DB lives alongside the auth DB
        import os as _os
        _tenants_db = _os.path.join(
            _os.path.dirname(str(_AUTH_DB_FILE_INNER)), "tenants.db"
        )
        init_tenant_db(_tenants_db)
        register_tenant_middleware(app, tenants_db_path=_tenants_db)
        init_tenant_routes(tenants_db_path=_tenants_db)
        app.register_blueprint(tenant_bp, url_prefix=f"/api/{API_VERSION}/tenants")
        logger.info("Registered tenant middleware and routes under /api/%s/tenants/", API_VERSION)
    except Exception as e:
        logger.warning("Failed to load tenant middleware/routes (non-fatal): %s", e)

    # Add tenant context to request logging
    @app.before_request
    def _log_tenant_context():
        from flask import g as _g
        tenant = getattr(_g, "tenant", None)
        if tenant:
            logger.debug(
                "Request tenant: slug=%r id=%d",
                tenant.slug, tenant.id,
            )

    # ── Web frontend (login + dashboard) ─────────────────────────────
    from education_system.platform.delivery.api.web.routes import web_bp
    app.register_blueprint(web_bp)

    # ── PWA support ──────────────────────────────────────────────────────
    from education_system.platform.delivery.api.web.pwa import pwa_bp
    app.register_blueprint(pwa_bp)

    # ── Parent portal ─────────────────────────────────────────────────
    try:
        from education_system.platform.delivery.api.parent_portal.routes import parent_portal_bp
        app.register_blueprint(parent_portal_bp)
        logger.info("Registered parent portal at /parent/")
    except Exception as e:
        logger.error("Failed to load parent portal: %s", e)

    # ── GraphQL API (Strawberry) ──────────────────────────────────────
    try:
        from education_system.platform.delivery.api.graphql.schema import (
            make_graphql_view,
            make_graphiql_view,
        )
        app.add_url_rule(
            f"/api/{API_VERSION}/graphql",
            view_func=make_graphql_view(),
        )
        app_env = os.getenv("APP_ENV", "production").lower()
        if app_env in ("development", "dev", "local", "test"):
            app.add_url_rule(
                f"/api/{API_VERSION}/graphiql",
                view_func=make_graphiql_view(),
            )
            logger.info(
                "GraphiQL IDE available at /api/%s/graphiql (development mode)",
                API_VERSION,
            )
        logger.info(
            "GraphQL endpoint mounted at /api/%s/graphql", API_VERSION
        )
    except Exception as e:
        logger.warning("Failed to load GraphQL API (non-fatal): %s", e)

    # ── University system ───────────────────────────────────────────────
    try:
        from education_system.systems.university.infrastructure.paths import ensure_directories as uni_ensure
        from education_system.systems.university.infrastructure.database.database_utils import (
            init_db as uni_init_db,
        )

        uni_ensure()
        uni_init_db()

        # Import all university blueprints and register them under /api/v1/university/
        from education_system.platform.delivery.api.university.routes import (
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

    # ── Sixth-form (college) routes under /api/v1/sixthform/ ─────────
    try:
        from education_system.platform.delivery.api.sixthform.routes import (
            academic_year_bp, students_bp, academics_bp, assessment_bp,
            finance_bp, governance_bp, pastoral_bp, progression_bp,
            reports_bp, staff_comms_bp, student_services_bp,
            advanced_search_bp,
        )
        for bp in (
            academic_year_bp, students_bp, academics_bp, assessment_bp,
            finance_bp, governance_bp, pastoral_bp, progression_bp,
            reports_bp, staff_comms_bp, student_services_bp,
            advanced_search_bp,
        ):
            new_prefix = _reprefix(bp.url_prefix, "sixthform")
            new_name = f"sixthform_{bp.name}"
            app.register_blueprint(bp, url_prefix=new_prefix, name=new_name)
        logger.info("Registered sixth-form routes under /api/%s/sixthform/",
                    API_VERSION)
    except Exception as e:
        logger.error("Failed to load sixth-form system: %s", e)

    # ── Nursery (early years) routes under /api/v1/nursery/ ──────────
    try:
        from education_system.platform.delivery.api.nursery.routes import ALL_BLUEPRINTS as _nursery_bps
        for bp in _nursery_bps:
            new_prefix = _reprefix(bp.url_prefix, "nursery")
            new_name = f"nursery_{bp.name}"
            app.register_blueprint(bp, url_prefix=new_prefix, name=new_name)
        logger.info("Registered %d nursery routes under /api/%s/nursery/",
                    len(_nursery_bps), API_VERSION)
    except Exception as e:
        logger.error("Failed to load nursery system: %s", e)

    # ── Primary-school routes under /api/v1/primary/ ─────────────────
    try:
        from education_system.platform.delivery.api.primary.routes import ALL_BLUEPRINTS as _primary_bps
        for bp in _primary_bps:
            new_prefix = _reprefix(bp.url_prefix, "primary")
            new_name = f"primary_{bp.name}"
            app.register_blueprint(bp, url_prefix=new_prefix, name=new_name)
        logger.info("Registered %d primary routes under /api/%s/primary/",
                    len(_primary_bps), API_VERSION)
    except Exception as e:
        logger.error("Failed to load primary system: %s", e)

    # ── Secondary-school routes under /api/v1/school/ ────────────────
    try:
        from education_system.platform.delivery.api.school.routes import ALL_BLUEPRINTS as _school_bps
        for bp in _school_bps:
            new_prefix = _reprefix(bp.url_prefix, "school")
            new_name = f"school_{bp.name}"
            app.register_blueprint(bp, url_prefix=new_prefix, name=new_name)
        logger.info("Registered %d secondary routes under /api/%s/school/",
                    len(_school_bps), API_VERSION)
    except Exception as e:
        logger.error("Failed to load secondary system: %s", e)

    # ── Backward-compatibility redirects ─────────────────────────────
    @app.before_request
    def redirect_unversioned():
        """Redirect old /api/<system>/... to /api/v1/<system>/..."""
        from flask import request
        path = request.path
        # Only redirect /api/<known-prefix> that is NOT already versioned
        if path.startswith("/api/") and not path.startswith(f"/api/{API_VERSION}/"):
            for prefix in ("sixthform", "school", "primary", "nursery", "university", "auth", "health"):
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
            "graphql": f"/api/{API_VERSION}/graphql",
            "systems": {
                "university": f"/api/{API_VERSION}/university/",
                "sixth_form": f"/api/{API_VERSION}/sixthform/",
                "secondary": f"/api/{API_VERSION}/school/",
                "primary": f"/api/{API_VERSION}/primary/",
                "nursery": f"/api/{API_VERSION}/nursery/",
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
    from education_system.platform.delivery.api.request_validator import PayloadValidationError

    @app.errorhandler(PayloadValidationError)
    def handle_payload_validation(e):
        logger.warning("Payload validation error: %s", e)
        return jsonify({
            "error": "Validation Error",
            "message": "The request payload failed validation.",
            "details": e.errors,
        }), 422

    # ── WebSocket / Socket.IO ────────────────────────────────────────────
    try:
        from education_system.platform.delivery.api.websocket_server import init_socketio
        _socketio = init_socketio(app)
        if _socketio is not None:
            # Expose socketio on the app so run_unified_api can use it
            app.extensions["socketio"] = _socketio
            logger.info("Socket.IO attached to unified app")
    except Exception as _ws_exc:
        logger.warning("WebSocket init failed (non-fatal): %s", _ws_exc)

    # Update CSP to allow WebSocket connections
    @app.after_request
    def _allow_ws_csp(response):
        csp = response.headers.get("Content-Security-Policy", "")
        if "connect-src" in csp and "ws:" not in csp:
            response.headers["Content-Security-Policy"] = csp.replace(
                "connect-src 'self'",
                "connect-src 'self' ws: wss:",
            )
        return response

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
    print(f"  GraphQL:    http://{host}:{port}/api/{API_VERSION}/graphql")
    print("  Press Ctrl+C to stop.\n")
    # Use socketio.run() when Socket.IO is available for proper async transport
    _socketio = app.extensions.get("socketio") if hasattr(app, "extensions") else None
    if _socketio is not None:
        print("  WebSockets: enabled (Socket.IO)")
        _socketio.run(app, host=host, port=port, debug=debug, use_reloader=debug)
    else:
        app.run(host=host, port=port, debug=debug)
