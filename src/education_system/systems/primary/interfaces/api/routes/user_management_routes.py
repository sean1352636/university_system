"""REST API for Primary User Management (roles & access overview).

This module is a read-and-grant layer over the shared auth DB. It exposes
access matrices, role distribution, pre-filtered user listings, a snapshot
summary, and bulk grant/revoke/set-active operations. There is no per-id
CRUD here (that lives in ``user_accounts``), so the endpoints below are
listings/summaries (GET) plus bulk mutations (POST).
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

user_management_bp = Blueprint("pri_user_management", __name__, url_prefix="/api/user-management")


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("PRIMARY_API_TOKEN")
            got = request.headers.get("X-Primary-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if isinstance(obj, tuple):
        return [_dump(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dump(v) for k, v in dataclasses.asdict(obj).items()}
    return obj


def _auth():
    """Build a shared-auth facade bound to the default auth DB."""
    from education_system.platform.identity.auth.core import UserAuth
    return UserAuth()


def _items(rows):
    dumped = _dump(rows)
    return jsonify({"items": dumped, "count": len(dumped)})


# ── Access matrix / role distribution ──────────────────────────────

@user_management_bp.route("/matrix", methods=["GET"])
@_token_required
def get_matrix():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    return jsonify(_dump(data.access_matrix(_auth())))


@user_management_bp.route("/role-distribution", methods=["GET"])
@_token_required
def get_role_distribution():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    system_key = request.args.get("system_key")
    if system_key:
        dist = data.role_distribution(_auth(), system_key)
    else:
        dist = data.role_distribution(_auth())
    return jsonify(_dump(dist))


# ── Snapshot / summary ─────────────────────────────────────────────

@user_management_bp.route("/summary", methods=["GET"])
@user_management_bp.route("/snapshot", methods=["GET"])
@_token_required
def get_snapshot():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    return jsonify(_dump(data.snapshot(_auth())))


# ── Pre-filtered listings ──────────────────────────────────────────

@user_management_bp.route("/admins", methods=["GET"])
@_token_required
def list_admins():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    system_key = request.args.get("system_key")
    if system_key:
        rows = data.list_admins(_auth(), system_key=system_key)
    else:
        rows = data.list_admins(_auth())
    return _items(rows)


@user_management_bp.route("/without-access", methods=["GET"])
@_token_required
def list_without_access():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    system_key = request.args.get("system_key")
    if system_key:
        rows = data.list_without_access(_auth(), system_key=system_key)
    else:
        rows = data.list_without_access(_auth())
    return _items(rows)


@user_management_bp.route("/locked", methods=["GET"])
@_token_required
def list_locked():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    return _items(data.list_locked(_auth()))


@user_management_bp.route("/inactive", methods=["GET"])
@_token_required
def list_inactive():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    return _items(data.list_inactive(_auth()))


# ── Bulk grant / revoke / set-active ───────────────────────────────

@user_management_bp.route("/bulk/grant", methods=["POST"])
@_token_required
def bulk_grant():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    from education_system.systems.primary.interfaces.user_accounts import (
        UserAccountError,
    )
    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("user_ids") or []
    system_key = payload.get("system_key")
    role = payload.get("role")
    if not system_key or not role:
        return jsonify({"error": "system_key and role are required"}), 400
    try:
        result = data.bulk_grant(_auth(), user_ids, system_key, role)
    except UserAccountError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))


@user_management_bp.route("/bulk/revoke", methods=["POST"])
@_token_required
def bulk_revoke():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    from education_system.systems.primary.interfaces.user_accounts import (
        UserAccountError,
    )
    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("user_ids") or []
    system_key = payload.get("system_key")
    if not system_key:
        return jsonify({"error": "system_key is required"}), 400
    try:
        result = data.bulk_revoke(_auth(), user_ids, system_key)
    except UserAccountError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))


@user_management_bp.route("/bulk/set-active", methods=["POST"])
@_token_required
def bulk_set_active():
    from education_system.systems.primary.domain.governance.user_management import (
        user_management as data,
    )
    from education_system.systems.primary.interfaces.user_accounts import (
        UserAccountError,
    )
    payload = request.get_json(silent=True) or {}
    user_ids = payload.get("user_ids") or []
    active = bool(payload.get("active", True))
    try:
        result = data.bulk_set_active(_auth(), user_ids, active)
    except UserAccountError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))
