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

from flask import Flask, g, jsonify, redirect
from flask_cors import CORS

from education_system.platform.delivery.api.security_headers import (
    is_development,
    register_security_headers,
)
from education_system.platform.kernel.core.structured_logging import setup_structured_logging

# Initialise logging early. Interactive launchers set compact text/warnings;
# deployments can opt into JSON/INFO through environment variables.
setup_structured_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_format=os.getenv("LOG_FORMAT", "text"),
    system="unified",
)

logger = logging.getLogger(__name__)

API_VERSION = "v1"


def _init_security(app: Flask) -> None:
    """Apply the shared header policy, cookie flags and production debug guard.

    The header set lives in delivery/api/security_headers.py so every app in
    the platform gets the same floor; this app used to carry its own copy,
    which had drifted (no Permissions-Policy, no cross-origin isolation, and a
    CSP that allowed Google Fonts on JSON responses).
    """
    register_security_headers(app)


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
    _dev_defaults: list[str] = []
    if not _api_secret:
        if not _is_dev:
            raise RuntimeError(
                "API_SECRET_KEY environment variable is required in production. "
                "A random per-process key invalidates sessions on every restart. "
                "Set a persistent API_SECRET_KEY via env/secret manager."
            )
        _api_secret = os.urandom(32).hex()
        _dev_defaults.append("ephemeral session key")
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
        _dev_defaults.append("localhost-only CORS")
        CORS(app, origins=dev_origins)
    else:
        raise RuntimeError(
            "API_CORS_ORIGINS must be set in production. Refuse to start with "
            "a wildcard CORS policy. Set API_CORS_ORIGINS to a comma-separated "
            "list of trusted origins (e.g. 'https://app.example.com')."
        )

    if _dev_defaults:
        logger.warning(
            "Development defaults active: %s. Configure API_SECRET_KEY and "
            "API_CORS_ORIGINS before deployment.",
            ", ".join(_dev_defaults),
        )

    # Relax the CSP for WebSocket connections when Socket.IO is attached.
    # Flask runs after_request hooks in reverse registration order, so this
    # must be registered *before* _init_security's header hook to see the
    # default policy that hook applies.
    @app.after_request
    def _allow_ws_csp(response):
        if "socketio" not in app.extensions:
            return response
        csp = response.headers.get("Content-Security-Policy", "")
        if "connect-src" in csp and "ws:" not in csp:
            response.headers["Content-Security-Policy"] = csp.replace(
                "connect-src 'self'",
                "connect-src 'self' ws: wss:",
            )
        return response

    _init_security(app)

    # CSRF via the kernel wrapper rather than the governance module directly:
    # it delegates to the same shared validator but scopes the check to
    # cookie-authenticated, unsafe-method requests. A call carrying
    # `Authorization: Bearer` is exempt — a browser will not attach that
    # header cross-origin, so demanding a CSRF token would break every API
    # client for no gain. The portal's write endpoints are covered either way.
    from education_system.platform.delivery.api.middleware.csrf import register_csrf
    register_csrf(app)

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

    # Local administrative control (orderly shutdown from the portal).
    from education_system.platform.delivery.api.admin_control import admin_control_bp
    app.register_blueprint(admin_control_bp, url_prefix=f"/api/{API_VERSION}")

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

    # ── Linked platform: learners, transfers, systems, events ────────────
    try:
        from education_system.platform.delivery.api.routes.learners_routes import (
            learners_bp, init_learner_routes,
        )
        init_learner_routes()
        app.register_blueprint(learners_bp, url_prefix=f"/api/{API_VERSION}")
        logger.info("Registered linked-platform routes under /api/%s/"
                    "{learners,transfers,progression,systems,events,tasks}",
                    API_VERSION)
    except Exception as e:
        logger.warning("Failed to load linked-platform routes (non-fatal): %s", e)

    # ── Notification preferences ─────────────────────────────────────────
    try:
        from education_system.platform.delivery.api.routes.notification_routes import (
            notification_prefs_bp, init_notification_routes,
        )
        init_notification_routes()
        app.register_blueprint(
            notification_prefs_bp, url_prefix=f"/api/{API_VERSION}/notifications")
        logger.info("Registered notification preference routes under "
                    "/api/%s/notifications/", API_VERSION)
    except Exception as e:
        logger.warning("Failed to load notification routes (non-fatal): %s", e)

    # ── Shared bus consumers (notifications, webhooks, calendar) ─────────
    # Each system drains its own inbound events, but only while it runs. The
    # API server drains the shared consumers for every system so a transfer
    # into a system nobody has open still notifies its staff. The thread is
    # named CrossSystemBusDrainer, so the test suite never starts it.
    try:
        from education_system.platform.integrations.external.bus_drainer import (
            start_platform_drainer,
        )
        start_platform_drainer()
    except Exception as e:
        logger.warning("Platform bus drainer not started (non-fatal): %s", e)

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
    # OpenAPI: the spec is generated from registry.iter_routes over this
    # app, so it cannot describe a route that is not mounted or omit one
    # that is. /api/v1/docs (Swagger UI) and /api/v1/openapi.json.
    try:
        from education_system.platform.delivery.api.openapi.ui import docs_bp
        app.register_blueprint(docs_bp)
        logger.info("Registered OpenAPI docs at /api/%s/docs", API_VERSION)
    except Exception:
        logger.warning("OpenAPI docs not registered", exc_info=True)

    from education_system.platform.delivery.api.web.routes import web_bp
    app.register_blueprint(web_bp)

    # The university HTML routes lived in university/shell/api, which was
    # removed. The portal frontend is preserved at platform/webui/ and will
    # be re-served as the university API is rebuilt module by module.

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
        from education_system.platform.delivery.api.auth import token_required as graphql_token_required
        graphql_view = graphql_token_required(make_graphql_view())
        app.add_url_rule(
            f"/api/{API_VERSION}/graphql",
            view_func=graphql_view,
            methods=["POST"],
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
        if os.getenv("APP_ENV", "production").lower() == "production":
            raise RuntimeError("GraphQL API failed to initialize") from e
        logger.warning("Failed to load GraphQL API in development mode: %s", e)

    # ── University system ───────────────────────────────────────────────
    # REMOVED. The university API (systems/university/shell/api) was deleted
    # deliberately so it can be rebuilt module by module. Re-register each
    # blueprint here as it is rewritten; keep the /api/v1/university/ prefix
    # so the existing frontend keeps working per module.
    #
    # The shared helpers those routes used — platform/delivery/api/university/
    # {auth,pagination,validators} — are intentionally still present: 128
    # domain modules import them, and they are a library, not an API surface.
    #
    # Backup of the removed tree:
    #   var/backups/maintenance/api-removal-20260908_204628/api-trees.tar.gz

    # ── Sixth-form (college) routes under /api/v1/sixthform/ ─────────
    try:
        from education_system.api.sixth_form.routes import (
            academic_year_bp, students_bp, academics_bp, assessment_bp,
            finance_bp, governance_bp, pastoral_bp, progression_bp,
            reports_bp, staff_comms_bp, student_services_bp,
            advanced_search_bp, calendar_bp,
        )
        for bp in (
            academic_year_bp, students_bp, academics_bp, assessment_bp,
            finance_bp, governance_bp, pastoral_bp, progression_bp,
            reports_bp, staff_comms_bp, student_services_bp,
            advanced_search_bp, calendar_bp,
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
        from education_system.api.nursery.routes import ALL_BLUEPRINTS as _nursery_bps
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
        from education_system.api.primary.routes import ALL_BLUEPRINTS as _primary_bps
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
        from education_system.api.secondary.routes import ALL_BLUEPRINTS as _school_bps
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
        # All seven systems, from the mount table rather than a literal: the
        # literal listed five, so FE college and apprenticeships were
        # invisible here while being real systems with routes of their own.
        from education_system.platform.delivery.api import registry as _api_registry
        return jsonify({
            "service": "Education System API",
            "version": API_VERSION,
            "auth": f"/api/{API_VERSION}/auth/login",
            "health": f"/api/{API_VERSION}/health",
            "docs": f"/api/{API_VERSION}/docs",
            "graphql": f"/api/{API_VERSION}/graphql",
            "systems": {
                key: f"{mount.prefix}/"
                for key, mount in _api_registry.mounts_by_system().items()
            },
            "registry": f"/api/{API_VERSION}/systems",
            "learners": f"/api/{API_VERSION}/learners/<journey_id>",
            "transfers": f"/api/{API_VERSION}/transfers",
            "events": f"/api/{API_VERSION}/events",
        })

    # ── Error handlers ──────────────────────────────────────────────────
    # One envelope for every failure: RFC 7807 problem+json, built by
    # kernel/problems.py. Bodies carry type/title/status/detail plus a
    # trace_id matching the request id, and a legacy "error" key while
    # clients still read one.
    from education_system.platform.delivery.api.kernel.problems import (
        problem,
        validation_problem,
    )

    @app.errorhandler(400)
    def bad_request(e):
        return problem(400, getattr(e, "description", None))

    @app.errorhandler(401)
    def unauthorized(e):
        return problem(401, "Authentication is required.")

    @app.errorhandler(403)
    def forbidden(e):
        return problem(403, "You may not access this resource.")

    @app.errorhandler(404)
    def not_found(e):
        return problem(404, "Not found")

    @app.errorhandler(409)
    def conflict(e):
        return problem(409, getattr(e, "description", None))

    @app.errorhandler(413)
    def request_too_large(e):
        max_mb = app.config.get("MAX_CONTENT_LENGTH", 0) / (1024 * 1024)
        return problem(413, f"Maximum request size is {max_mb:.0f} MB")

    @app.errorhandler(429)
    def rate_limited(e):
        return problem(429, "Rate limit exceeded")

    @app.errorhandler(500)
    def server_error(e):
        # Return only a generic message plus a correlation id; the full
        # exception (with traceback) goes to the protected server log keyed by
        # the same id, so support can join the two without the client ever
        # seeing a stack trace, SQL, path or token.
        cid = getattr(g, "request_id", None)
        logger.error("Unhandled 500 (request_id=%s): %s", cid, e, exc_info=True)
        # Detail stays generic: the traceback goes to the protected log under
        # the same id, so support can join the two without the client seeing it.
        return problem(500, "Internal server error", correlation_id=cid)

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        # HTTP exceptions (404/413/429/…) keep their own status and handlers.
        from werkzeug.exceptions import HTTPException

        if isinstance(e, HTTPException):
            return e
        cid = getattr(g, "request_id", None)
        logger.error("Uncaught exception (request_id=%s): %s", cid, e, exc_info=True)
        return problem(500, "Internal server error", correlation_id=cid)

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

    logger.info("Unified API server created (version=%s)", API_VERSION)
    return app


def run_unified_api(host: str | None = None, port: int | None = None):
    """Run the unified API server."""
    host = host or os.getenv("API_HOST", "0.0.0.0")
    port = port or int(os.getenv("API_PORT", "5000"))
    app = create_unified_app()
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    if debug and not is_development():
        # The Werkzeug debugger renders tracebacks and offers an interactive
        # console to anyone who can reach the port. It is never a production
        # option, so an API_DEBUG=true there is a startup failure, not a
        # warning that a hurried operator would scroll past.
        raise RuntimeError(
            "API_DEBUG=true is refused because APP_ENV is production. The "
            "debugger exposes stack traces and a remote console."
        )
    # 0.0.0.0 means "bind every interface"; it is not an address a browser
    # can usefully open, so the printed links use localhost instead.
    shown = "localhost" if host in ("0.0.0.0", "::") else host
    print(f"\n  Education System API · {API_VERSION}")
    print(f"  Server   http://{shown}:{port}   (bound to {host})")
    print(f"  Login    http://{shown}:{port}/")
    print(f"  Home     http://{shown}:{port}/portal/   (after sign-in)")
    print(f"  Docs     http://{shown}:{port}/api/{API_VERSION}/docs")
    print(f"  Health   http://{shown}:{port}/api/{API_VERSION}/health")
    # Use socketio.run() when Socket.IO is available for proper async transport
    _socketio = app.extensions.get("socketio") if hasattr(app, "extensions") else None
    if _socketio is not None:
        print("  Socket.IO enabled · Press Ctrl+C to stop.\n")
        _socketio.run(app, host=host, port=port, debug=debug, use_reloader=debug)
    else:
        print("  Press Ctrl+C to stop.\n")
        app.run(host=host, port=port, debug=debug)
