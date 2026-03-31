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
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import jwt
from flask import Blueprint, request, jsonify, g

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────

_JWT_SECRET = os.getenv("JWT_SECRET_KEY") or secrets.token_urlsafe(64)
_JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
_JWT_REFRESH_DAYS = int(os.getenv("JWT_REFRESH_DAYS", "7"))
_auth_db_path: str | None = None

# ── Rate limiting (per IP and per username) ────────────────────────────

_rate_store: dict[str, list[float]] = defaultdict(list)
_username_rate_store: dict[str, list[float]] = defaultdict(list)
_LOGIN_LIMIT, _LOGIN_WINDOW = 10, 60
_USERNAME_LOGIN_LIMIT, _USERNAME_LOGIN_WINDOW = 5, 60
_REGISTER_LIMIT, _REGISTER_WINDOW = 5, 3600


def _rate_limited(key: str, limit: int, window: int) -> bool:
    now = time.time()
    _rate_store[key] = [t for t in _rate_store[key] if now - t < window]
    if len(_rate_store[key]) >= limit:
        return True
    _rate_store[key].append(now)
    return False


def _username_rate_limited(username: str) -> bool:
    """Check per-username rate limit for login attempts."""
    now = time.time()
    key = username.lower()
    _username_rate_store[key] = [
        t for t in _username_rate_store[key] if now - t < _USERNAME_LOGIN_WINDOW
    ]
    if len(_username_rate_store[key]) >= _USERNAME_LOGIN_LIMIT:
        return True
    _username_rate_store[key].append(now)
    return False


# ── Blueprint ───────────────────────────────────────────────────────────

auth_bp = Blueprint("shared_auth", __name__, url_prefix="/api/auth")


def init_auth(auth_db_path: str | None = None, jwt_secret: str | None = None):
    """Initialise the shared auth blueprint.

    Call this once when creating the Flask app:
        init_auth(auth_db_path="/path/to/auth.db")
        app.register_blueprint(auth_bp)
    """
    global _auth_db_path, _JWT_SECRET
    if auth_db_path:
        _auth_db_path = auth_db_path
    if jwt_secret:
        _JWT_SECRET = jwt_secret


# ── Token helpers ───────────────────────────────────────────────────────

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
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])


def _create_mfa_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "purpose": "mfa_verify",
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


# ── Decorators ──────────────────────────────────────────────────────────

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
            g.current_user = {
                "user_id": data["user_id"],
                "username": data["username"],
                "systems": data.get("systems", []),
            }
            # Convenience: set role for the current system context
            g.current_user["role"] = _best_role(data.get("systems", []))
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Require one of the given roles (checked across all systems)."""
    def decorator(f):
        @functools.wraps(f)
        @token_required
        def decorated(*args, **kwargs):
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
    except Exception as e:
        logger.warning("Login failed for '%s'", data.get("username"))
        return jsonify({"error": "Invalid credentials"}), 401

    if not result:
        return jsonify({"error": "Invalid credentials"}), 401

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
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "MFA token required"}), 401

    token = auth_header.split(" ", 1)[1]
    try:
        data = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
        if data.get("purpose") != "mfa_verify":
            return jsonify({"error": "Invalid token type"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid or expired MFA token"}), 401

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

    systems = data.get("systems", [])
    new_access = generate_token(data["user_id"], data["username"], systems, "access")
    new_refresh = generate_token(data["user_id"], data["username"], systems, "refresh")

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
    except Exception as e:
        logger.error("Account reset request failed: %s", e)
        # Don't reveal errors to prevent email enumeration
        pass

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
