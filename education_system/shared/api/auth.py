"""Unified JWT authentication for all education system APIs.

Single login endpoint that authenticates against the shared auth database.
The JWT includes the user's accessible systems and roles, so any system
API can validate access without a separate login flow.

Endpoints:
    POST /api/auth/login       — authenticate, get JWT with system access
    POST /api/auth/register    — create account (admin only)
    GET  /api/auth/me          — current user info from token
    POST /api/auth/change-password
    POST /api/auth/mfa/verify  — complete MFA challenge
    POST /api/auth/refresh     — refresh an expiring token
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

    from education_system.shared.auth.core import UserAuth
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
    from education_system.shared.auth.rate_limit_store import PersistentRateLimiter
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
    from education_system.shared.auth.db import connect
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
                   token_type: str = "access") -> str:
    """Generate a JWT containing the user's ID, username, and system access.

    The ``systems`` list comes straight from ``UserAuth.login()`` and looks
    like ``[{"system_key": "college", "role": "admin"}, ...]``.
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
    if token_type == "refresh":
        jti = secrets.token_urlsafe(24)
        payload["jti"] = jti
        _record_refresh_jti(jti, user_id, exp)
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])


def _create_mfa_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "purpose": "mfa_verify",
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm="HS256")


# ── Decorators ──────────────────────────────────────────────────────────

_KNOWN_SYSTEMS = ("university", "college", "school", "primary", "nursery")


def _system_key_from_path(path: str) -> str | None:
    """If *path* sits under ``/api/<v>/<system>/``, return ``<system>``."""
    if not path or not path.startswith("/api/"):
        return None
    parts = path.split("/")
    # ['', 'api', 'v1', 'university', ...]
    if len(parts) >= 4 and parts[3] in _KNOWN_SYSTEMS:
        return parts[3]
    return None


def _role_for_system(systems: list[dict], system_key: str | None) -> str | None:
    if not system_key:
        return None
    for s in systems or []:
        if s.get("system_key") == system_key:
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
            has_access = any(
                s["system_key"] == system_key
                for s in g.current_user.get("systems", [])
            )
            if not has_access:
                return jsonify({"error": "Access denied",
                                "message": f"No access to {system_key} system"}), 403
            # Set role for this specific system
            for s in g.current_user.get("systems", []):
                if s["system_key"] == system_key:
                    g.current_user["role"] = s["role"]
                    break
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

@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate and receive access + refresh tokens.

    Request body:
        {"username": "...", "password": "..."}

    Response:
        {"token": "...", "refresh_token": "...", "user": {...}}
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"login:{ip}", _LOGIN_LIMIT, _LOGIN_WINDOW):
        return jsonify({"error": "Too many login attempts. Try again later."}), 429

    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password required"}), 400

    if _username_rate_limited(data["username"]):
        return jsonify({"error": "Too many login attempts for this account. Try again later."}), 429

    try:
        from education_system.shared.auth.core import UserAuth
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        result = auth.login(data["username"], data["password"])
    except Exception:
        logger.warning("Login failed for '%s'", data.get("username"))
        _record_username_login_failure(data["username"])
        return jsonify({"error": "Invalid credentials"}), 401

    if not result:
        _record_username_login_failure(data["username"])
        return jsonify({"error": "Invalid credentials"}), 401

    # Password matched — clear the per-username failure counter so a
    # successful login (or successful MFA primary step) doesn't leave the
    # account hovering near a lockout from earlier failed attempts.
    _clear_username_login_failures(data["username"])

    # MFA challenge
    if result.get("mfa_required"):
        mfa_token = _create_mfa_token(result["user_id"])
        return jsonify({
            "mfa_required": True,
            "mfa_token": mfa_token,
            "user_id": result["user_id"],
            "username": result["username"],
        })

    systems = result.get("systems", [])
    access_token = generate_token(result["user_id"], result["username"], systems, "access")
    refresh_token = generate_token(result["user_id"], result["username"], systems, "refresh")

    return jsonify({
        "message": "Login successful.",
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": result["user_id"],
            "username": result["username"],
            "display_name": result.get("display_name", result["username"]),
            "systems": systems,
            "password_expired": bool(result.get("password_expired")),
            "must_change_password": bool(result.get("must_change_password")),
        },
    })


@auth_bp.route("/mfa/verify", methods=["POST"])
def mfa_verify():
    """Complete MFA challenge.

    Request body:
        {"code": "123456"}
    Headers:
        Authorization: Bearer <mfa_token>
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"mfa:{ip}", _MFA_IP_LIMIT, _MFA_IP_WINDOW):
        return jsonify({"error": "Too many MFA attempts. Try again later."}), 429

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "MFA token required"}), 401

    token = auth_header.split(" ", 1)[1]
    try:
        data = jwt.decode(token, _get_jwt_secret(), algorithms=["HS256"])
        if data.get("purpose") != "mfa_verify":
            return jsonify({"error": "Invalid token type"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid or expired MFA token"}), 401

    # Per-user cap: block brute-forcing one account's code even from many IPs.
    if _rate_limited(f"mfa_user:{data.get('user_id')}", _MFA_USER_LIMIT, _MFA_USER_WINDOW):
        return jsonify({"error": "Too many MFA attempts. Try again later."}), 429

    body = request.get_json(silent=True)
    if not body or not body.get("code"):
        return jsonify({"error": "MFA code required"}), 400

    try:
        from education_system.shared.auth.core import UserAuth
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        result = auth.verify_mfa(data["user_id"], body["code"])
    except Exception as e:
        logger.error("MFA verification failed: %s", e)
        return jsonify({"error": "MFA verification failed"}), 401

    systems = result.get("systems", [])
    access_token = generate_token(result["user_id"], result["username"], systems, "access")
    refresh_token = generate_token(result["user_id"], result["username"], systems, "refresh")

    return jsonify({
        "message": "MFA verified.",
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": result["user_id"],
            "username": result["username"],
            "systems": systems,
        },
    })


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    """Exchange a refresh token for a new access token.

    Request body:
        {"refresh_token": "..."}
    """
    body = request.get_json(silent=True)
    if not body or not body.get("refresh_token"):
        return jsonify({"error": "refresh_token required"}), 400

    try:
        data = decode_token(body["refresh_token"])
        if data.get("type") != "refresh":
            return jsonify({"error": "Not a refresh token"}), 401
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Refresh token expired, please login again"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid refresh token"}), 401

    # Enforce rotation: the refresh-token's JTI must exist in our store and
    # not yet be revoked. A revoked JTI being presented means either the
    # token was already rotated (replay) or was explicitly logged out — in
    # either case we revoke the entire chain for that user as a defensive
    # measure (refresh-token reuse detection).
    jti = data.get("jti")
    user_id = data.get("user_id")
    if not jti:
        # Legacy refresh tokens (issued before rotation was wired in) have
        # no JTI. Reject them so callers are forced to log in once; the new
        # tokens will then be rotation-tracked.
        return jsonify({"error": "Refresh token must be re-issued, please login again"}), 401

    state = _refresh_jti_state(jti)
    if state is None:
        # Unknown JTI — either DB was reset or token was forged for a user
        # that no longer exists. Reject.
        return jsonify({"error": "Refresh token not recognised"}), 401
    if state.get("revoked"):
        logger.warning(
            "Refresh-token reuse detected for user_id=%s jti=%s — revoking all sessions",
            user_id, jti,
        )
        if user_id is not None:
            _revoke_all_refresh_jtis_for_user(int(user_id))
        return jsonify({"error": "Refresh token has been revoked"}), 401

    systems = data.get("systems", [])
    new_access = generate_token(data["user_id"], data["username"], systems, "access")
    new_refresh = generate_token(data["user_id"], data["username"], systems, "refresh")
    # Mark the old JTI as revoked and link it to the new one (decoded lazily
    # — we need the new JTI from the freshly-issued token).
    try:
        new_payload = jwt.decode(new_refresh, _get_jwt_secret(), algorithms=["HS256"])
        _revoke_refresh_jti(jti, replaced_by=new_payload.get("jti"))
    except Exception:
        _revoke_refresh_jti(jti)

    return jsonify({
        "token": new_access,
        "refresh_token": new_refresh,
    })


@auth_bp.route("/register", methods=["POST"])
@role_required("admin")
def register():
    """Create a new user account (admin only).

    Request body:
        {"username": "...", "password": "...", "email": "...",
         "systems": [{"system_key": "college", "role": "student"}, ...]}
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"register:{ip}", _REGISTER_LIMIT, _REGISTER_WINDOW):
        return jsonify({"error": "Too many registration attempts."}), 429

    data = request.get_json(silent=True)
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password required"}), 400

    systems_list = data.get("systems", [{"system_key": "college", "role": "student"}])
    system_tuples = [(s["system_key"], s.get("role", "student")) for s in systems_list]

    try:
        from education_system.shared.auth.core import UserAuth
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        user_id = auth.create_user(
            username=data["username"],
            password=data["password"],
            email=data.get("email"),
            systems=system_tuples,
        )
    except Exception as e:
        logger.error("User registration failed: %s", e)
        return jsonify({"error": "Registration failed"}), 400

    return jsonify({"message": "User created.", "user_id": user_id}), 201


@auth_bp.route("/me", methods=["GET"])
@token_required
def get_me():
    """Return current user info from token."""
    return jsonify({"user": g.current_user})


@auth_bp.route("/change-password", methods=["POST"])
@token_required
def change_password():
    """Change the current user's password.

    Request body:
        {"old_password": "...", "new_password": "..."}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("old_password") or not data.get("new_password"):
        return jsonify({"error": "old_password and new_password required"}), 400

    try:
        from education_system.shared.auth.core import UserAuth
        from education_system.shared.auth.db import AUTH_DB_FILE
        auth = UserAuth(_auth_db_path or str(AUTH_DB_FILE))
        auth.change_password(g.current_user["user_id"],
                             data["old_password"], data["new_password"])
    except Exception as e:
        logger.error("Auth update failed: %s", e)
        return jsonify({"error": "Password change failed"}), 400

    return jsonify({"message": "Password changed successfully."})


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Request a password reset token.

    Request body:
        {"email": "user@example.com"}
    """
    ip = request.remote_addr or "unknown"
    if _rate_limited(f"forgot:{ip}", 3, 3600):
        return jsonify({"error": "Too many reset requests. Try again later."}), 429

    data = request.get_json(silent=True)
    if not data or not data.get("email"):
        return jsonify({"error": "email required"}), 400

    try:
        from education_system.shared.auth.password_reset import PasswordResetService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = PasswordResetService(_auth_db_path or str(AUTH_DB_FILE))
        result = svc.request_reset(data["email"])

        # Send the reset email if a token was generated
        if result.get("token"):
            _send_password_reset_email(
                email=result["email"],
                username=result["username"],
                token=result["token"],
                expires_at=result["expires_at"],
            )
    except Exception as e:
        logger.error("Account reset request failed: %s", e)
        # Don't reveal errors to prevent email enumeration

    return jsonify({"message": "If that email exists, a reset link has been sent."})


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Reset password using a token.

    Request body:
        {"token": "...", "new_password": "..."}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("token") or not data.get("new_password"):
        return jsonify({"error": "token and new_password required"}), 400

    try:
        from education_system.shared.auth.password_reset import PasswordResetService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = PasswordResetService(_auth_db_path or str(AUTH_DB_FILE))
        svc.reset_password(data["token"], data["new_password"])
    except Exception as e:
        logger.error("Account reset failed: %s", e)
        return jsonify({"error": "Password reset failed"}), 400

    return jsonify({"message": "Password reset successful. Please login with your new password."})


# ── Password reset email helper ────────────────────────────────────────

def _send_password_reset_email(email: str, username: str, token: str, expires_at: str):
    """Send a password reset email containing the reset token.

    Uses the shared email config. Falls back silently if email is not
    configured (the token is still returned in the API response for
    development/testing).
    """
    try:
        from education_system.shared.email.config import load_email_config
        from email.mime.text import MIMEText
        import smtplib

        cfg = load_email_config()
        smtp_server = cfg.get("smtp_server", "")
        smtp_port = cfg.get("smtp_port", 587)
        smtp_user = cfg.get("smtp_username", "")
        smtp_pass = cfg.get("smtp_password", "")
        use_tls = cfg.get("use_tls", True)
        sender = cfg.get("sender_email", smtp_user)

        if not all([smtp_server, smtp_user, smtp_pass]):
            logger.debug("Email not configured — skipping password reset email")
            return

        base_url = os.getenv("APP_BASE_URL", "http://localhost:5000")
        reset_link = f"{base_url}/web/reset-password?token={token}"

        body = (
            f"Hello {username},\n\n"
            f"A password reset was requested for your Education System account.\n\n"
            f"Click the link below to reset your password:\n"
            f"  {reset_link}\n\n"
            f"This link expires at {expires_at}.\n\n"
            f"If you did not request this, you can safely ignore this email.\n"
        )

        msg = MIMEText(body)
        msg["Subject"] = "Education System — Password Reset"
        msg["From"] = sender
        msg["To"] = email

        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        if use_tls:
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(sender, [email], msg.as_string())
        server.quit()
        logger.info("Password reset email sent to %s", email)
    except Exception as exc:
        logger.debug("Could not send password reset email: %s", exc)


# ── Email verification endpoints ───────────────────────────────────────

@auth_bp.route("/send-verification", methods=["POST"])
@token_required
def send_verification_email():
    """Send an email verification link to the current user's email.

    Response:
        {"message": "Verification email sent."}
    """
    try:
        from education_system.shared.auth.email_verification import EmailVerificationService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = EmailVerificationService(_auth_db_path or str(AUTH_DB_FILE))
        svc.send_verification(g.current_user["user_id"])
    except Exception as e:
        logger.error("Email verification send failed: %s", e)
        return jsonify({"error": "Failed to send verification email"}), 500

    return jsonify({"message": "Verification email sent."})


@auth_bp.route("/verify-email", methods=["POST"])
def verify_email():
    """Verify an email address using a token.

    Request body:
        {"token": "..."}
    """
    data = request.get_json(silent=True)
    if not data or not data.get("token"):
        return jsonify({"error": "token required"}), 400

    try:
        from education_system.shared.auth.email_verification import EmailVerificationService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = EmailVerificationService(_auth_db_path or str(AUTH_DB_FILE))
        svc.verify(data["token"])
    except Exception as e:
        logger.error("Email verification failed: %s", e)
        return jsonify({"error": "Email verification failed"}), 400

    return jsonify({"message": "Email verified successfully."})


# ── OAuth2 / social login endpoints ───────────────────────────────────

@auth_bp.route("/oauth/providers", methods=["GET"])
def oauth_providers():
    """List available OAuth providers and their configuration status."""
    try:
        from education_system.shared.auth.oauth_service import OAuthService
        return jsonify({"providers": OAuthService.list_providers()})
    except Exception as e:
        logger.error("OAuth providers list failed: %s", e)
        return jsonify({"providers": []}), 500


@auth_bp.route("/oauth/<provider>/authorize", methods=["GET"])
def oauth_authorize(provider: str):
    """Redirect to OAuth provider's authorization page."""
    try:
        from education_system.shared.auth.oauth_service import OAuthService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        url = svc.get_authorization_url(provider)
        return jsonify({"authorize_url": url})
    except Exception as e:
        logger.error("OAuth authorize failed: %s", e)
        return jsonify({"error": "OAuth authorization failed. Please try again."}), 400


@auth_bp.route("/oauth/<provider>/callback", methods=["GET", "POST"])
def oauth_callback(provider: str):
    """Handle OAuth provider callback after user authorization."""
    code = request.args.get("code") or (request.get_json(silent=True) or {}).get("code")
    state = request.args.get("state") or (request.get_json(silent=True) or {}).get("state")

    if not code or not state:
        return jsonify({"error": "code and state required"}), 400

    try:
        from education_system.shared.auth.oauth_service import OAuthService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        result = svc.handle_callback(provider, code, state)
    except Exception as e:
        logger.error("OAuth callback failed: %s", e)
        return jsonify({"error": "OAuth authentication failed. Please try again."}), 400

    systems = result.get("systems", [])
    access_token = generate_token(result["user_id"], result["username"], systems, "access")
    refresh_token = generate_token(result["user_id"], result["username"], systems, "refresh")

    return jsonify({
        "message": "OAuth login successful.",
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "user_id": result["user_id"],
            "username": result["username"],
            "display_name": result.get("display_name", result["username"]),
            "systems": systems,
            "oauth_provider": result.get("oauth_provider"),
        },
    })


@auth_bp.route("/oauth/linked", methods=["GET"])
@token_required
def oauth_linked_providers():
    """List OAuth providers linked to the current user's account."""
    try:
        from education_system.shared.auth.oauth_service import OAuthService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        providers = svc.get_linked_providers(g.current_user["user_id"])
        return jsonify({"linked_providers": providers})
    except Exception as e:
        logger.error("OAuth linked providers list failed: %s", e)
        return jsonify({"linked_providers": []}), 500


@auth_bp.route("/oauth/<provider>/unlink", methods=["POST"])
@token_required
def oauth_unlink(provider: str):
    """Unlink an OAuth provider from the current user's account."""
    try:
        from education_system.shared.auth.oauth_service import OAuthService
        from education_system.shared.auth.db import AUTH_DB_FILE
        svc = OAuthService(_auth_db_path or str(AUTH_DB_FILE))
        if svc.unlink_account(g.current_user["user_id"], provider):
            return jsonify({"message": f"{provider} account unlinked."})
        return jsonify({"error": f"No {provider} account linked."}), 404
    except Exception as e:
        logger.error("OAuth unlink failed: %s", e)
        return jsonify({"error": "Failed to unlink account"}), 500


# ── Device management endpoints ───────────────────────────────────────

@auth_bp.route("/devices", methods=["GET"])
@token_required
def list_devices():
    """List trusted devices for the current user."""
    try:
        from education_system.shared.auth.device_manager import DeviceManager
        from education_system.shared.auth.db import AUTH_DB_FILE
        mgr = DeviceManager(_auth_db_path or str(AUTH_DB_FILE))
        devices = mgr.list_devices(g.current_user["user_id"])
        return jsonify({"devices": devices})
    except Exception as e:
        logger.error("Device list failed: %s", e)
        return jsonify({"devices": []}), 500


@auth_bp.route("/devices/revoke-all", methods=["POST"])
@token_required
def revoke_all_devices():
    """Revoke all trusted devices for the current user."""
    try:
        from education_system.shared.auth.device_manager import DeviceManager
        from education_system.shared.auth.db import AUTH_DB_FILE
        mgr = DeviceManager(_auth_db_path or str(AUTH_DB_FILE))
        count = mgr.revoke_all_devices(g.current_user["user_id"])
        return jsonify({"message": f"Revoked {count} trusted device(s)."})
    except Exception as e:
        logger.error("Device revoke failed: %s", e)
        return jsonify({"error": "Failed to revoke devices"}), 500
