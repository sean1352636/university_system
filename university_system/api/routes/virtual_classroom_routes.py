"""Virtual classroom routes: classrooms, sessions, recordings, study rooms."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import (
    validate_virtual_classroom_create,
    validate_virtual_session_create,
)
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

virtual_classroom_bp = Blueprint("virtual_classrooms", __name__, url_prefix="/api/virtual-classrooms")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Virtual Classrooms ----

@virtual_classroom_bp.route("", methods=["GET"])
@token_required
def list_classrooms():
    course_id = request.args.get("course_id")
    platform = request.args.get("platform")

    with get_connection() as conn:
        conditions = ["is_active = 1"]
        params: list = []
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)
        if platform:
            conditions.append("platform = ?")
            params.append(platform)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM virtual_classrooms" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM virtual_classrooms" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "virtual_classrooms", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@virtual_classroom_bp.route("/<int:classroom_id>", methods=["GET"])
@token_required
def get_classroom(classroom_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM virtual_classrooms WHERE classroom_id = ?", (classroom_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Virtual classroom {classroom_id} not found")
    log_activity("view", "virtual_classroom", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@virtual_classroom_bp.route("", methods=["POST"])
@token_required
def create_classroom():
    data = request.get_json(silent=True) or {}
    validate_virtual_classroom_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO virtual_classrooms
               (session_name, course_id, instructor_id, platform,
                meeting_link, meeting_id, passcode, max_participants, features)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["session_name"],
                data.get("course_id"),
                data["instructor_id"],
                data["platform"],
                data.get("meeting_link"),
                data.get("meeting_id"),
                data.get("passcode"),
                data.get("max_participants", 100),
                data.get("features"),
            ),
        )
        cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM virtual_classrooms WHERE classroom_id = ?", (cid,)
        ).fetchone()

    log_activity("create", "virtual_classroom", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Sessions ----

@virtual_classroom_bp.route("/<int:classroom_id>/sessions", methods=["GET"])
@token_required
def list_sessions(classroom_id: int):
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = ["classroom_id = ?"]
        params: list = [classroom_id]
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM virtual_sessions" + where + " ORDER BY start_time DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM virtual_sessions" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "virtual_sessions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@virtual_classroom_bp.route("/sessions", methods=["POST"])
@token_required
def create_session():
    data = request.get_json(silent=True) or {}
    validate_virtual_session_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO virtual_sessions
               (classroom_id, session_type, start_time, end_time, notes, status)
               VALUES (?, ?, ?, ?, ?, 'scheduled')""",
            (
                data["classroom_id"],
                data.get("session_type", "lecture"),
                data["start_time"],
                data.get("end_time"),
                data.get("notes", ""),
            ),
        )
        sid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM virtual_sessions WHERE session_id = ?", (sid,)
        ).fetchone()

    log_activity("create", "virtual_session", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Recordings ----

@virtual_classroom_bp.route("/sessions/<int:session_id>/recordings", methods=["GET"])
@token_required
def list_recordings(session_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM virtual_recordings WHERE session_id = ? ORDER BY created_at DESC",
            (session_id,),
        ).fetchall()

    log_activity("view", "virtual_recordings", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Virtual Study Rooms ----

@virtual_classroom_bp.route("/study-rooms", methods=["GET"])
@token_required
def list_study_rooms():
    course_id = request.args.get("course_id")
    active_only = request.args.get("active_only", "true").lower() == "true"

    with get_connection() as conn:
        conditions = []
        params: list = []
        if active_only:
            conditions.append("is_active = 1")
        if course_id:
            conditions.append("course_id = ?")
            params.append(course_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM virtual_study_rooms" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM virtual_study_rooms" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "virtual_study_rooms", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))
