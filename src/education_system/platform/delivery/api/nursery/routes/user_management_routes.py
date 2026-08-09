"""REST API for Nursery User Management.

Exposes the roles-and-access overview (access matrix, role distribution,
pre-filtered user listings, aggregate snapshot) plus bulk grant / revoke /
set-active operations layered over the shared auth database.
"""

from __future__ import annotations

import dataclasses
import functools
import logging
import os

from flask import Blueprint, g, jsonify, request

logger = logging.getLogger(__name__)

user_management_bp = Blueprint(
    "nsy_user_management", __name__, url_prefix="/api/user-management"
)


def _token_required(view):
    try:
        from education_system.platform.delivery.api.auth import token_required
        return token_required(view)
    except Exception:
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            expected = os.environ.get("NURSERY_API_TOKEN")
            got = request.headers.get("X-Nursery-Token")
            if expected and got and got == expected:
                g.current_user = {"sub": "service", "role": "service"}
                return view(*args, **kwargs)
            return jsonify({"error": "Unauthorized"}), 401
        return wrapper


def _dump(obj):
    """Serialize a domain dataclass (or list of them) to JSON-safe data."""
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    return obj


def _auth():
    """Build a shared-auth facade bound to the default auth DB.

    Every user_management function takes this object as its first argument.
    """
    from education_system.platform.identity.auth.core import UserAuth
    return UserAuth()


def _int_list(raw):
    """Coerce a JSON value into a list[int]; raise ValueError on bad input."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("user_ids must be a list of integers")
    return [int(x) for x in raw]


# ── Overview (GET) ──────────────────────────────────────────────────

@user_management_bp.route("", methods=["GET"])
@user_management_bp.route("/", methods=["GET"])
@_token_required
def access_matrix():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    matrix = data.access_matrix(_auth())
    return jsonify(_dump(matrix))


@user_management_bp.route("/summary", methods=["GET"])
@_token_required
def summary():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    return jsonify(_dump(data.snapshot(_auth())))


@user_management_bp.route("/role-distribution", methods=["GET"])
@_token_required
def role_distribution():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    from education_system.systems.nursery.interfaces.user_accounts import (
        SYSTEM_KEY,
    )
    system_key = request.args.get("system_key") or SYSTEM_KEY
    return jsonify(data.role_distribution(_auth(), system_key))


@user_management_bp.route("/admins", methods=["GET"])
@_token_required
def list_admins():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    rows = data.list_admins(_auth())
    return jsonify({"items": _dump(rows), "count": len(rows)})


@user_management_bp.route("/locked", methods=["GET"])
@_token_required
def list_locked():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    rows = data.list_locked(_auth())
    return jsonify({"items": _dump(rows), "count": len(rows)})


@user_management_bp.route("/inactive", methods=["GET"])
@_token_required
def list_inactive():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    rows = data.list_inactive(_auth())
    return jsonify({"items": _dump(rows), "count": len(rows)})


@user_management_bp.route("/without-access", methods=["GET"])
@_token_required
def list_without_access():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    rows = data.list_without_access(_auth())
    return jsonify({"items": _dump(rows), "count": len(rows)})


# ── Bulk operations (POST) ──────────────────────────────────────────

@user_management_bp.route("/bulk-grant", methods=["POST"])
@_token_required
def bulk_grant():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    from education_system.systems.nursery.interfaces.user_accounts import (
        SYSTEM_KEY,
        UserAccountError,
    )
    payload = request.get_json(silent=True) or {}
    try:
        user_ids = _int_list(payload.get("user_ids"))
        system_key = payload.get("system_key") or SYSTEM_KEY
        role = payload.get("role")
        if not role:
            raise UserAccountError("role is required")
        result = data.bulk_grant(_auth(), user_ids, system_key, role)
    except (UserAccountError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))


@user_management_bp.route("/bulk-revoke", methods=["POST"])
@_token_required
def bulk_revoke():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    from education_system.systems.nursery.interfaces.user_accounts import (
        SYSTEM_KEY,
        UserAccountError,
    )
    payload = request.get_json(silent=True) or {}
    try:
        user_ids = _int_list(payload.get("user_ids"))
        system_key = payload.get("system_key") or SYSTEM_KEY
        result = data.bulk_revoke(_auth(), user_ids, system_key)
    except (UserAccountError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))


@user_management_bp.route("/bulk-set-active", methods=["POST"])
@_token_required
def bulk_set_active():
    from education_system.systems.nursery.domain.governance.user_management import (
        user_management as data,
    )
    from education_system.systems.nursery.interfaces.user_accounts import (
        UserAccountError,
    )
    payload = request.get_json(silent=True) or {}
    try:
        user_ids = _int_list(payload.get("user_ids"))
        active = bool(payload.get("active", True))
        result = data.bulk_set_active(_auth(), user_ids, active)
    except (UserAccountError, ValueError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_dump(result))
