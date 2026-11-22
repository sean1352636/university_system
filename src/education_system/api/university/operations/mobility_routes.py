"""Mobile app/PWA routes: devices, sessions, and sync queue."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import require_staff, token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

mobility_bp = Blueprint("mobility", __name__, url_prefix="/api/mobility")

#: Devices (with their push tokens) and app sessions are one user's.
#: ``user_id`` is INTEGER, so it keys on the JWT ``user_id`` claim, not
#: ``sub``. Anyone else's needs ``system_admin`` (admin).
DEVICE_ADMIN = "system_admin"


def _my_user_id() -> str:
    return str((g.get("current_user") or {}).get("user_id") or "")


def _is_device_admin() -> bool:
    return require_staff(permission=DEVICE_ADMIN) is None


def _deny_unless_own_device(owner_user_id):
    """403 unless the row is the caller's (by JWT ``user_id``) or they are admin."""
    me = _my_user_id()
    if me and owner_user_id is not None and str(owner_user_id) == me:
        return None
    return require_staff(permission=DEVICE_ADMIN)


def _pinned_user_id(requested):
    """The user id a list may show: the caller's own unless they are admin."""
    return requested if _is_device_admin() else (_my_user_id() or None)


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- devices ----

@mobility_bp.route("/devices", methods=["GET"])
@token_required
def list_devices():
    search = request.args.get("search")
    user_id = request.args.get("user_id")
    platform = request.args.get("platform")
    if not _is_device_admin():
        # Pin to the caller first; the name search spans every user.
        user_id, search = _my_user_id(), None
        if not user_id:
            return jsonify({"error": "Forbidden", "status": 403}), 403

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM mobile_devices WHERE device_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if platform:
            conditions.append("platform = ?")
            params.append(platform)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM mobile_devices" + where + " ORDER BY device_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mobile_devices" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "mobile_devices", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@mobility_bp.route("/devices/<int:device_id>", methods=["GET"])
@token_required
def get_device(device_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mobile_devices WHERE device_id = ?", (device_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"devices {device_id} not found")
    denial = _deny_unless_own_device(row["user_id"])
    if denial is not None:
        return denial
    log_activity("view", "mobile_devices", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@mobility_bp.route("/devices", methods=["POST"])
@token_required
def create_device():
    data = request.get_json(silent=True) or {}
    # A device is registered to the caller, never to an id from the body.
    data["user_id"] = _pinned_user_id(data.get("user_id"))
    for field in ["user_id", "device_name", "platform"]:
        if not data.get(field):
            raise ValidationError(f"Missing required field: {field}")
    denial = _deny_unless_own_device(data["user_id"])
    if denial is not None:
        return denial

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO mobile_devices
               (user_id, device_name, platform, device_token, app_version, os_version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["user_id"], data["device_name"], data["platform"], data.get("device_token", ""), data.get("app_version", ""), data.get("os_version", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mobile_devices WHERE device_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "mobile_devices", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- sessions ----

@mobility_bp.route("/sessions", methods=["GET"])
@token_required
def list_sessions():
    user_id = _pinned_user_id(request.args.get("user_id"))
    if not user_id and not _is_device_admin():
        return jsonify({"error": "Forbidden", "status": 403}), 403
    device_id = request.args.get("device_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if device_id:
            conditions.append("device_id = ?")
            params.append(device_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM mobile_sessions" + where + " ORDER BY session_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM mobile_sessions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "mobile_sessions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@mobility_bp.route("/sessions/<int:session_id>", methods=["GET"])
@token_required
def get_session(session_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mobile_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"sessions {session_id} not found")
    denial = _deny_unless_own_device(row["user_id"])
    if denial is not None:
        return denial
    log_activity("view", "mobile_sessions", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@mobility_bp.route("/sessions", methods=["POST"])
@token_required
def create_session():
    data = request.get_json(silent=True) or {}
    data["user_id"] = _pinned_user_id(data.get("user_id"))
    for field in ["user_id", "device_id"]:
        if not data.get(field):
            raise ValidationError(f"Missing required field: {field}")
    with get_connection() as conn:
        device = conn.execute(
            "SELECT user_id FROM mobile_devices WHERE device_id = ?", (data["device_id"],)
        ).fetchone()
    # The session's device must be the same user's device.
    denial = _deny_unless_own_device(device["user_id"] if device else None)
    if denial is None and device is not None and str(device["user_id"]) != str(data["user_id"]):
        denial = jsonify({"error": "Forbidden", "status": 403}), 403
    if denial is not None:
        return denial

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO mobile_sessions
               (user_id, device_id, ip_address, user_agent, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (data["user_id"], data["device_id"], data.get("ip_address", ""), data.get("user_agent", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM mobile_sessions WHERE session_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "mobile_sessions", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
