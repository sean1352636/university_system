"""Mobile app/PWA routes: devices, sessions, and sync queue."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

mobility_bp = Blueprint("mobility", __name__, url_prefix="/api/mobility")


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
    log_activity("view", "mobile_devices", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@mobility_bp.route("/devices", methods=["POST"])
@token_required
def create_device():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "device_name", "platform"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

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
    user_id = request.args.get("user_id")
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
    log_activity("view", "mobile_sessions", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@mobility_bp.route("/sessions", methods=["POST"])
@token_required
def create_session():
    data = request.get_json(silent=True) or {}
    for field in ["user_id", "device_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

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
