"""JWT authentication for the Flask API.

Provides token creation, validation, and the ``@token_required``
decorator that populates ``flask.g.current_user``.
"""

from __future__ import annotations

import functools
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from flask import current_app, g, jsonify, request

logger = logging.getLogger(__name__)

# In-memory set of invalidated JTIs (cleared on restart – acceptable for
# single-process deployments).
_blacklisted_tokens: set[str] = set()
_STAFF_ROLES = {"admin", "staff", "superadmin", "instructor", "teacher", "faculty"}
_KNOWN_ROLES = _STAFF_ROLES | {"student", "parent", "alumni"}

# Roles absent from the canonical PERMISSIONS map are resolved through an
# alias so a valid staff role never silently collapses to zero permissions.
_ROLE_PERMISSION_ALIAS = {
    "superadmin": "admin",
    "teacher": "instructor",
    "faculty": "instructor",
}


def _effective_permissions(user: dict) -> set:
    """Resolve the caller's permission set.

    Prefers an explicit ``permissions`` claim on the token; otherwise derives
    it from the role via the canonical role→permission map (with alias
    mapping). Resolving here rather than embedding the full set in every JWT
    keeps tokens small and avoids a stale claim surviving a permission change.
    """
    claim = user.get("permissions")
    if isinstance(claim, (list, tuple, set)):
        return set(claim)
    role = str(user.get("role") or "").lower()
    role = _ROLE_PERMISSION_ALIAS.get(role, role)
    try:
        from education_system.systems.university.infrastructure.auth.core_utils.constants import (
            PERMISSIONS,
        )
    except Exception:
        return set()
    return set(PERMISSIONS.get(role, []))


def authorize_object(owner_id=None, *, permission=None, staff_roles=None):
    """Authorize an object at the route/service boundary.

    Staff roles may access objects only when their role grants the requested
    capability; non-staff users may access only records owned by their own
    authenticated subject. Missing/unknown identity always denies.
    """
    user = g.get("current_user") or {}
    role = str(user.get("role") or "").lower()
    if role not in _KNOWN_ROLES:
        return jsonify({"error": "Forbidden", "status": 403}), 403
    if role in (staff_roles or _STAFF_ROLES):
        # A required capability is now enforced (previously inert because the
        # JWT carried no permissions claim): resolve the caller's permissions
        # from their role and deny if the capability is absent.
        if permission and permission not in _effective_permissions(user):
            return jsonify({"error": "Forbidden", "status": 403}), 403
        return None
    if owner_id is None:
        return jsonify({"error": "Forbidden", "status": 403}), 403
    principals = {str(user.get("sub") or ""), str(user.get("user_id") or ""),
                  str(user.get("student_id") or "")}
    if str(owner_id) not in principals:
        return jsonify({"error": "Forbidden", "status": 403}), 403
    return None


def require_staff(*, permission=None):
    """Require a recognised staff role and optional permission claim."""
    return authorize_object("staff-boundary", permission=permission)


def is_staff() -> bool:
    """True if the current user holds a recognised staff role."""
    role = str((g.get("current_user") or {}).get("role") or "").lower()
    return role in _STAFF_ROLES


def current_subject_id() -> str | None:
    """The authenticated caller's own subject identifier.

    For students the username IS the student id (e.g. ``S12345``), so ``sub``
    is the owning subject; ``user_id`` is included as a fallback.
    """
    user = g.get("current_user") or {}
    return str(user.get("sub") or user.get("user_id") or "") or None


def staff_required(fn=None, *, permission=None):
    """Decorator requiring a recognised staff role (use after @token_required).

    For records that are staff-internal (e.g. safeguarding / early-warning
    data) rather than owner-accessible. Unlike ``admin_required`` this admits
    instructors and pastoral staff, not only ``admin``.
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            denial = require_staff(permission=permission)
            if denial is not None:
                return denial
            return f(*args, **kwargs)

        return wrapper

    return decorator(fn) if fn is not None else decorator


def deny_unless_owner_or_staff(owner_subject_id):
    """Row-level scope check for handlers keyed on a resource id, not the owner.

    Use when the path param is a resource id (e.g. appointment_id) and the
    owning subject must be read from the fetched row. Staff pass; everyone else
    must match ``owner_subject_id`` to their own subject. Returns a
    ``(jsonify, 403)`` tuple to short-circuit, or ``None`` to proceed — the
    same contract as :func:`authorize_object`.
    """
    if is_staff():
        return None
    me = current_subject_id()
    if me is None or str(owner_subject_id or "") != me:
        return jsonify({"error": "Forbidden", "status": 403}), 403
    return None


def scoped_to(owner_param: str, *, permission=None, staff_roles=None):
    """Route decorator enforcing object-level ownership at the boundary.

    Must sit *below* ``@token_required`` so ``g.current_user`` is populated.
    Staff roles pass (subject to ``permission`` once a permission claim
    exists); every other authenticated user may act only on the record whose
    id in the route kwargs (``owner_param``) matches their own subject id.

    This is the fix for the class of routes that carried only
    ``@token_required`` and let any authenticated student read or write any
    other subject's record by changing the id in the URL.

    Usage::

        @bp.route("/account/<student_id>")
        @token_required
        @scoped_to("student_id")
        def account(student_id): ...
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            owner_id = kwargs.get(owner_param)
            denial = authorize_object(owner_id, permission=permission, staff_roles=staff_roles)
            if denial is not None:
                return denial
            return f(*args, **kwargs)

        return wrapper

    return decorator


def create_access_token(user: dict[str, Any], config: dict) -> str:
    """Create a signed JWT access token for *user*."""
    jwt_cfg = config["jwt"]
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=jwt_cfg.get("access_token_expires_minutes", 30)
    )
    payload = {
        "sub": user["username"],
        "user_id": user["id"],
        "role": user["role"],
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": expires,
    }
    return jwt.encode(payload, jwt_cfg["secret_key"], algorithm=jwt_cfg.get("algorithm", "HS256"))


def create_refresh_token(user: dict[str, Any], config: dict) -> str:
    """Create a signed JWT refresh token for *user*."""
    jwt_cfg = config["jwt"]
    expires = datetime.now(timezone.utc) + timedelta(
        days=jwt_cfg.get("refresh_token_expires_days", 7)
    )
    payload = {
        "sub": user["username"],
        "user_id": user["id"],
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": expires,
    }
    return jwt.encode(payload, jwt_cfg["secret_key"], algorithm=jwt_cfg.get("algorithm", "HS256"))


def create_mfa_token(user: dict[str, Any], config: dict) -> str:
    """Create a short-lived JWT for the MFA verification window (5 min)."""
    jwt_cfg = config["jwt"]
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    payload = {
        "sub": user["username"],
        "user_id": user["id"],
        "role": user["role"],
        "type": "mfa_pending",
        "iat": datetime.now(timezone.utc),
        "exp": expires,
    }
    return jwt.encode(payload, jwt_cfg["secret_key"], algorithm=jwt_cfg.get("algorithm", "HS256"))


def decode_token(token: str, config: dict) -> dict[str, Any]:
    """Decode and validate a JWT token.  Raises on invalid/expired tokens."""
    jwt_cfg = config["jwt"]
    return jwt.decode(token, jwt_cfg["secret_key"], algorithms=[jwt_cfg.get("algorithm", "HS256")])


def blacklist_token(token: str) -> None:
    """Mark a token as revoked."""
    _blacklisted_tokens.add(token)


def is_token_blacklisted(token: str) -> bool:
    return token in _blacklisted_tokens


def _extract_bearer_token() -> Optional[str]:
    """Extract the Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def token_required(fn):
    """Decorator that enforces a valid access token.

    On success, ``flask.g.current_user`` is set to the decoded payload.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing authorization token", "status": 401}), 401

        if is_token_blacklisted(token):
            return jsonify({"error": "Token has been revoked", "status": 401}), 401

        try:
            config = current_app.config["API_CONFIG"]
            payload = decode_token(token, config)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired", "status": 401}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token", "status": 401}), 401

        if payload.get("type") != "access":
            return jsonify({"error": "Invalid token type", "status": 401}), 401

        # Re-check the authoritative user record so disabling an account or
        # removing its system access takes effect before the JWT expires.
        try:
            from education_system.platform.identity.auth.db import connect
            with connect(current_app.config.get("AUTH_DB_PATH")) as conn:
                active = conn.execute(
                    "SELECT is_active FROM users WHERE id = ? AND username = ?",
                    (payload.get("user_id"), payload.get("sub")),
                ).fetchone()
            if not active or not active[0]:
                return jsonify({"error": "Authentication required", "status": 401}), 401
        except Exception:
            logger.exception("University auth state could not be verified")
            return jsonify({"error": "Authentication unavailable", "status": 503}), 503

        g.current_user = payload
        g.raw_token = token
        return fn(*args, **kwargs)

    return wrapper


def mfa_token_required(fn):
    """Decorator that enforces a valid MFA-pending token.

    On success, ``flask.g.mfa_user`` is set to the decoded payload.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing authorization token", "status": 401}), 401

        if is_token_blacklisted(token):
            return jsonify({"error": "Token has been revoked", "status": 401}), 401

        try:
            config = current_app.config["API_CONFIG"]
            payload = decode_token(token, config)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "MFA token has expired", "status": 401}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token", "status": 401}), 401

        if payload.get("type") != "mfa_pending":
            return jsonify({"error": "Invalid token type — MFA token required", "status": 401}), 401

        g.mfa_user = payload
        g.raw_token = token
        return fn(*args, **kwargs)

    return wrapper


def token_or_mfa_token_required(fn):
    """Decorator that accepts either an access token or an MFA-pending token.

    Used for MFA setup endpoints that must be accessible during both:
    - Normal authenticated sessions (access token)
    - Login-time MFA setup when MFA is enforced but not yet configured (mfa_pending token)

    On success, ``flask.g.current_user`` is set to the decoded payload
    (normalised so ``user_id`` and ``sub`` are always present).
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"error": "Missing authorization token", "status": 401}), 401

        if is_token_blacklisted(token):
            return jsonify({"error": "Token has been revoked", "status": 401}), 401

        try:
            config = current_app.config["API_CONFIG"]
            payload = decode_token(token, config)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired", "status": 401}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token", "status": 401}), 401

        token_type = payload.get("type")
        if token_type not in ("access", "mfa_pending"):
            return jsonify({"error": "Invalid token type", "status": 401}), 401

        g.current_user = payload
        g.raw_token = token
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """Decorator that requires an admin role (must be used after @token_required)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if g.get("current_user", {}).get("role") != "admin":
            return jsonify({"error": "Admin access required", "status": 403}), 403
        return fn(*args, **kwargs)

    return wrapper


# ---- Simple in-memory rate limiter ------------------------------------------

_rate_limit_store: dict[str, list[float]] = {}


def check_rate_limit(config: dict) -> Optional[tuple]:
    """Return an error tuple if the caller has exceeded the rate limit, else None."""
    rl_cfg = config.get("rate_limiting", {})
    if not rl_cfg.get("enabled", False):
        return None

    rpm = rl_cfg.get("requests_per_minute", 100)
    ip = request.remote_addr or "unknown"
    now = time.time()
    window_start = now - 60

    timestamps = _rate_limit_store.get(ip, [])
    timestamps = [t for t in timestamps if t > window_start]
    timestamps.append(now)
    _rate_limit_store[ip] = timestamps

    if len(timestamps) > rpm:
        return jsonify({"error": "Rate limit exceeded", "status": 429}), 429

    return None
