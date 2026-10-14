"""Shared authentication: state, helpers and decorators.

Split out of the former ``delivery/api/auth.py``. The route handlers now
live in :mod:`..routes.auth_routes`; everything they stand on is here.

The split had to fall on this side of the module state. ``_JWT_SECRET``,
``_auth_db_path`` and ``_rate_limiter`` are module-level and are written
by :func:`init_auth` at startup, then read on every request. Duplicating
them across two modules would give the routes a second set that
``init_auth`` never touches — tokens would be signed with one secret and
verified against another. So this module owns them, and the routes
import from here rather than re-declaring anything.

``auth_bp`` is defined here too, so the decorators and the routes attach
to the same blueprint object.
"""

import functools
import os
import secrets
import logging
from datetime import datetime, timedelta

import jwt
from flask import Blueprint, request, jsonify, g

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────

_JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
_JWT_REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))
_auth_db_path: str | None = None
_JWT_SECRET: str | None = None

# ── Rate limiting (persistent, SQLite-backed) ─────────────────────────

_rate_limiter = None  # Initialised in init_auth()
_LOGIN_LIMIT, _LOGIN_WINDOW = 10, 60
_USERNAME_LOGIN_LIMIT, _USERNAME_LOGIN_WINDOW = 5, 60
_REGISTER_LIMIT, _REGISTER_WINDOW = 5, 3600
# MFA verification: cap attempts so a captured mfa_token can't be used to
# brute-force the 6-digit TOTP / recovery code. Limit both by client IP and
# by the target user id carried in the mfa_token.
_MFA_IP_LIMIT, _MFA_IP_WINDOW = 20, 300
_MFA_USER_LIMIT, _MFA_USER_WINDOW = 5, 300


def _rate_limited(key: str, limit: int, window: int) -> bool:
    if _rate_limiter is None:
        return False
    return _rate_limiter.is_limited(key, limit, window)


def _username_login_key(username: str) -> str:
    return f"user_login_fail:{username.lower()}"


def _username_rate_limited(username: str) -> bool:
    """Return True if *username* has too many recent **failed** logins.

    Only failures are counted (recorded by ``_record_username_login_failure``),
    so a legitimate user is not locked out merely by an attacker spamming
    requests against their username.
    """
    if _rate_limiter is None:
        return False
    key = _username_login_key(username)
    return _rate_limiter.count(key, _USERNAME_LOGIN_WINDOW) >= _USERNAME_LOGIN_LIMIT


def _record_username_login_failure(username: str) -> None:
    if _rate_limiter is None:
        return
    _rate_limiter.record(_username_login_key(username))


def _clear_username_login_failures(username: str) -> None:
    if _rate_limiter is None:
        return
    _rate_limiter.clear(_username_login_key(username))


# ── Blueprint ───────────────────────────────────────────────────────────

auth_bp = Blueprint("shared_auth", __name__, url_prefix="/api/auth")


def _load_or_create_jwt_secret(db_path: str | None) -> str:
    """Load the JWT secret.

    Production deployments **must** set ``JWT_SECRET_KEY`` via the
    environment (or a secret manager). Falling back to a plaintext value
    in the auth DB means read access to ``auth.db`` is enough to forge
    any token, so we refuse that path outside development/test.
    """
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret:
        return env_secret

    app_env = os.getenv("APP_ENV", "production").lower()
    is_dev = app_env in ("development", "dev", "local", "test")
    if not is_dev:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is required in production. "
            "Storing the JWT secret in auth.db lets anyone with file read "
            "access forge tokens. Set JWT_SECRET_KEY via env/secret manager."
        )

    from education_system.platform.identity.auth.core import UserAuth
    auth = UserAuth(db_path)
    stored = auth.get_setting("jwt_secret")
    if stored:
        return stored

    new_secret = secrets.token_urlsafe(64)
    auth.set_setting("jwt_secret", new_secret)
    logger.warning(
        "Generated dev JWT secret and persisted to auth.db. "
        "Set JWT_SECRET_KEY before deploying outside dev/test."
    )
    return new_secret


def init_auth(auth_db_path: str | None = None, jwt_secret: str | None = None):
    """Initialise the shared auth blueprint.

    Call this once when creating the Flask app:
        init_auth(auth_db_path="/path/to/auth.db")
        app.register_blueprint(auth_bp)
    """
    global _auth_db_path, _JWT_SECRET, _rate_limiter
    if auth_db_path:
        _auth_db_path = auth_db_path
    if jwt_secret:
        _JWT_SECRET = jwt_secret
    else:
        _JWT_SECRET = _load_or_create_jwt_secret(_auth_db_path)

    # Initialise persistent rate limiter
    from education_system.platform.identity.auth.rate_limit_store import PersistentRateLimiter
    _rate_limiter = PersistentRateLimiter(_auth_db_path)

    # Refresh-token rotation table (tracks JTIs so refresh tokens can be
    # revoked and reuse can be detected).
    _init_refresh_jti_table()


# ── Refresh-token rotation (JTI tracking) ─────────────────────────────

_REFRESH_JTI_SCHEMA = """
CREATE TABLE IF NOT EXISTS refresh_jtis (
    jti TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0,
    replaced_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_refresh_jtis_user ON refresh_jtis(user_id);
"""


def _refresh_jti_conn():
    from education_system.platform.identity.auth.db import connect
    return connect(_auth_db_path)


def _init_refresh_jti_table() -> None:
    if not _auth_db_path:
        return
    try:
        conn = _refresh_jti_conn()
        try:
            conn.executescript(_REFRESH_JTI_SCHEMA)
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - table init is best-effort
        logger.warning("Failed to init refresh_jtis table: %s", exc)


def _record_refresh_jti(jti: str, user_id: int, expires_at: datetime) -> None:
    if not _auth_db_path:
        return
    try:
        conn = _refresh_jti_conn()
        try:
            conn.execute(
                "INSERT INTO refresh_jtis (jti, user_id, issued_at, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (jti, user_id, datetime.utcnow().isoformat(), expires_at.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Failed to record refresh JTI: %s", exc)


def _refresh_jti_state(jti: str) -> dict | None:
    """Return the DB row for *jti* as a dict, or None if not found."""
    if not _auth_db_path:
        return None
    try:
        conn = _refresh_jti_conn()
        try:
            row = conn.execute(
                "SELECT jti, user_id, revoked, replaced_by, expires_at "
                "FROM refresh_jtis WHERE jti = ?",
                (jti,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Failed to read refresh JTI: %s", exc)
        return None


def _revoke_refresh_jti(jti: str, replaced_by: str | None = None) -> None:
    if not _auth_db_path:
        return
    try:
        conn = _refresh_jti_conn()
        try:
            conn.execute(
                "UPDATE refresh_jtis SET revoked = 1, replaced_by = ? WHERE jti = ?",
                (replaced_by, jti),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Failed to revoke refresh JTI: %s", exc)


def _revoke_all_refresh_jtis_for_user(user_id: int) -> None:
    """Revoke every outstanding refresh JTI for *user_id* (used on reuse-detection)."""
    if not _auth_db_path:
        return
    try:
        conn = _refresh_jti_conn()
        try:
            conn.execute(
                "UPDATE refresh_jtis SET revoked = 1 WHERE user_id = ? AND revoked = 0",
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Failed to revoke user refresh JTIs: %s", exc)


# ── Token helpers ───────────────────────────────────────────────────────

def _get_jwt_secret() -> str:
    """Return the JWT secret.

    Resolution order: in-process secret (set by ``init_auth``) → env var.
    Refuses to fall back to a constant placeholder — signing or verifying
    tokens with a known value would let any caller forge access tokens.
    """
    if _JWT_SECRET:
        return _JWT_SECRET
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret:
        return env_secret
    raise RuntimeError(
        "JWT secret is not configured. Call init_auth() during app startup "
        "or set the JWT_SECRET_KEY environment variable."
    )


def generate_token(user_id: int, username: str, systems: list[dict],
                   token_type: str = "access",
                   tenant_id: str | None = None) -> str:
    """Generate a JWT containing the user's ID, username, and system access.

    The ``systems`` list comes straight from ``UserAuth.login()`` and looks
    like ``[{"system_key": "college", "role": "admin"}, ...]``.

    *tenant_id* is the tenant slug this session is scoped to, and is the only
    thing the tenant middleware will accept as proof of tenancy — a
    client-supplied header is checked against it, never trusted instead of it.
    Omitted entirely for a single-tenant install, which keeps those tokens
    byte-identical to before.
    """
    if token_type == "refresh":
        exp = datetime.utcnow() + timedelta(days=_JWT_REFRESH_DAYS)
    else:
        exp = datetime.utcnow() + timedelta(hours=_JWT_EXPIRY_HOURS)

    payload = {
        "user_id": user_id,
        "username": username,
        "systems": systems,
        "type": token_type,
        "exp": exp,
        "iat": datetime.utcnow(),
    }
    if tenant_id:
        payload["tenant_id"] = tenant_id
    if token_type == "refresh":
        jti = secrets.token_urlsafe(24)
        payload["jti"] = jti
        _record_refresh_jti(jti, user_id, exp)
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])


def _create_mfa_token(user_id: int, tenant_id: str | None = None) -> str:
    payload = {
        "user_id": user_id,
        "purpose": "mfa_verify",
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow(),
    }
    # Carry the tenant chosen at the password step through the MFA round trip,
    # so a multi-tenant user is not asked to choose twice.
    if tenant_id:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def _login_tenant_slug(user_id: int, requested: str | None):
    """Resolve the tenant claim for a login, or a ``(response, status)`` denial.

    Returns ``(slug_or_None, None)`` on success. Tenancy problems are the
    user's to resolve, so they get a specific message rather than a generic
    401 — but never the list of tenants they are *not* in.
    """
    from education_system.platform.kernel.core.tenant_models import (
        AmbiguousTenantError,
        TenantMembershipError,
        resolve_login_tenant,
    )
    try:
        tenant = resolve_login_tenant(user_id, requested)
    except AmbiguousTenantError as exc:
        return None, (jsonify({
            "error": "Select a tenant to sign in to.",
            "tenant_required": True,
            "detail": str(exc),
        }), 409)
    except TenantMembershipError:
        return None, (jsonify({"error": "Not a member of that tenant."}), 403)
    except Exception:
        # Tenancy is optional infrastructure; a lookup failure must not take
        # authentication down with it.
        logger.warning("Tenant resolution failed for user_id=%s", user_id,
                       exc_info=True)
        return None, None
    return (tenant.slug if tenant else None), None


# ── Decorators ──────────────────────────────────────────────────────────

from education_system.platform.kernel.core.system_keys import (
    CANONICAL_SYSTEMS,
    canonical_system_key,
)

# Canonical system keys (nursery/primary/secondary/sixth_form/university).
_KNOWN_SYSTEMS = CANONICAL_SYSTEMS

#: First path segments under ``/api/<v>/`` that are platform surfaces, never
#: a system. They span systems by design, so authorisation there is done by
#: the cross-system permission decorators below, not by a path-derived role.
#: Listed explicitly so a future system key (or alias) that happened to
#: collide with one could not silently turn these into system-scoped routes.
_PLATFORM_SEGMENTS = frozenset({
    "auth", "health", "learners", "systems", "events", "transfers",
    "progression", "journey", "warehouse", "webhooks", "notifications",
    "tasks",
})


def _system_key_from_path(path: str) -> str | None:
    """If *path* sits under ``/api/<v>/<system>/``, return the canonical
    system_key. URL prefixes are normalised (e.g. ``sixthform`` / ``college`` /
    ``school`` → their canonical key) so path-scoped role enforcement always
    resolves — otherwise the route reads as unscoped and role checks fall back to
    the user's best cross-system role (a privilege-escalation gap)."""
    if not path or not path.startswith("/api/"):
        return None
    parts = path.split("/")
    # ['', 'api', 'v1', 'university', ...]
    if len(parts) >= 4:
        if parts[3] in _PLATFORM_SEGMENTS:
            return None
        seg = canonical_system_key(parts[3])
        if seg in _KNOWN_SYSTEMS:
            return seg
    return None


def _role_for_system(systems: list[dict], system_key: str | None) -> str | None:
    if not system_key:
        return None
    # Normalise both sides so a token still carrying a legacy key (e.g.
    # "college") matches a canonical target ("sixth_form"), and vice-versa.
    target = canonical_system_key(system_key)
    for s in systems or []:
        if canonical_system_key(s.get("system_key")) == target:
            return s.get("role")
    return None


def token_required(f):
    """Require a valid access JWT.  Sets ``g.current_user``."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Authentication required"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            data = decode_token(token)
            if data.get("type") == "refresh":
                return jsonify({"error": "Cannot use refresh token for API access"}), 401
            systems = data.get("systems", [])
            # JWT validity alone is insufficient: a user may have been
            # disabled or had their access revoked after token issuance.
            # Re-read the authoritative auth record on every request and fail
            # closed if the auth database is unavailable.
            from education_system.platform.identity.auth.db import connect
            with connect(_auth_db_path) as auth_conn:
                active = auth_conn.execute(
                    "SELECT is_active FROM users WHERE id = ? AND username = ?",
                    (data.get("user_id"), data.get("username")),
                ).fetchone()
            if not active or not active[0]:
                return jsonify({"error": "Authentication required"}), 401
            g.current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "systems": systems,
            }
            # Set role from the *current* system context if the request is
            # under a known system prefix — that way a `primary:admin /
            # university:student` user is treated as a student on
            # university routes. Fall back to the best cross-system role
            # for unscoped (e.g. /api/v1/auth/*) endpoints.
            scoped_system = _system_key_from_path(request.path)
            scoped_role = _role_for_system(systems, scoped_system)
            if scoped_system is not None:
                if scoped_role is None:
                    return jsonify({"error": "Access denied",
                                    "message": f"No access to {scoped_system} system"}), 403
                g.current_user["role"] = scoped_role
                g.current_user["system_key"] = scoped_system
            else:
                g.current_user["role"] = _best_role(systems)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def role_required(*roles, system_key: str | None = None):
    """Require one of the given roles.

    By default the check is **scoped to the current system** (the system
    prefix in the request URL). For unscoped routes (e.g. /api/v1/auth/*)
    the user's role is taken across all systems — pass an explicit
    ``system_key`` to constrain that.
    """
    def decorator(f):
        @functools.wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            target_system = system_key or _system_key_from_path(request.path)
            if target_system:
                role = _role_for_system(g.current_user.get("systems", []), target_system)
                if role not in roles:
                    return jsonify({"error": "Access denied",
                                    "message": f"Requires role: {', '.join(roles)}"}), 403
            else:
                user_roles = {s["role"] for s in g.current_user.get("systems", [])}
                if not user_roles & set(roles):
                    return jsonify({"error": "Access denied",
                                    "message": f"Requires role: {', '.join(roles)}"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def system_required(system_key: str):
    """Require the user to have access to a specific system."""
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "current_user"):
                return jsonify({"error": "Authentication required"}), 401
            target = canonical_system_key(system_key)
            has_access = any(
                canonical_system_key(s["system_key"]) == target
                for s in g.current_user.get("systems", [])
            )
            if not has_access:
                return jsonify({"error": "Access denied",
                                "message": f"No access to {system_key} system"}), 403
            # Set role for this specific system
            for s in g.current_user.get("systems", []):
                if canonical_system_key(s["system_key"]) == target:
                    g.current_user["role"] = s["role"]
                    break
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Cross-system authorisation ──────────────────────────────────────────
# The platform routes (learners, transfers, events) span systems, so a
# path-derived role means nothing there. They are gated on the capability
# classes and permissions in ``role_manager`` instead. The superadmin rule
# mirrors ``launcher.roles.is_superadmin``, which the platform may not import.

def is_superadmin_user(user: dict | None = None) -> bool:
    """Whether the request's user (or *user*) is a platform superadmin."""
    from education_system.platform.identity.auth.role_manager import is_superadmin_systems
    if user is None:
        user = getattr(g, "current_user", None) or {}
    return is_superadmin_systems(user.get("systems", []))


def superadmin_required(f):
    """Require a valid token belonging to a platform superadmin."""
    @functools.wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if not is_superadmin_user():
            return jsonify({"error": "Access denied",
                            "message": "Requires platform superadmin"}), 403
        g.current_user["superadmin"] = True
        return f(*args, **kwargs)
    return decorated


def permitted_systems_for(permission: str) -> set[str] | None:
    """Systems where the current user holds *permission*; ``None`` = all.

    ``None`` (rather than every known key) for a superadmin, so a caller
    filtering a query by system knows to apply no filter at all — including
    to destinations outside the platform, which no key list would contain.
    """
    from education_system.platform.identity.auth.role_manager import permitted_systems
    user = getattr(g, "current_user", None) or {}
    if is_superadmin_user(user):
        return None
    return permitted_systems(user.get("systems", []), permission)


def cross_system_permission_required(permission: str):
    """Require *permission* in at least one system (a superadmin has all).

    Whether the user may act on a *particular* learner or transfer depends
    on which systems that object touches, so the handler still checks the
    object with :func:`permitted_systems_for`; this gate only turns away
    users who hold the permission nowhere.
    """
    def decorator(f):
        @functools.wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            from education_system.platform.identity.auth.role_manager import (
                has_cross_system_permission,
            )
            systems = g.current_user.get("systems", [])
            if not has_cross_system_permission(systems, permission):
                return jsonify({"error": "Access denied",
                                "message": f"Requires permission: {permission}"}), 403
            g.current_user["superadmin"] = is_superadmin_user()
            return f(*args, **kwargs)
        return decorated
    return decorator


def _best_role(systems: list[dict]) -> str:
    """Pick the highest-privilege role from the user's systems."""
    priority = {"admin": 0, "staff": 1, "teacher": 2, "parent": 3, "student": 4}
    best = "student"
    for s in systems:
        r = s.get("role", "student")
        if priority.get(r, 99) < priority.get(best, 99):
            best = r
    return best


# ── Routes ──────────────────────────────────────────────────────────────
