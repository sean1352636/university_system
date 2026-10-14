"""Attendance routes: sessions, records, and analytics."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import (
    current_subject_id,
    require_staff,
    scoped_to,
    token_required,
)
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import (
    validate_attendance_record_create,
    validate_attendance_session_create,
)
from education_system.systems.university.infrastructure.exceptions import StudentNotFoundError, ValidationError
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

attendance_bp = Blueprint("attendance", __name__, url_prefix="/api/attendance")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


#: Creating teaching sessions and recording who attended them. An instructor
#: holds ``manage_module_attendance`` for their own modules while central
#: staff hold ``manage_attendance``; either is enough to take a register, and
#: requiring only one of them would lock out half the people who do the job.
ATTENDANCE_MANAGE = ("manage_attendance", "manage_module_attendance")

#: Reading attendance that is not your own.
ATTENDANCE_READ_ANY = ("view_module_students",) + ATTENDANCE_MANAGE


def _forbidden():
    return jsonify({"error": "Forbidden", "status": 403}), 403


def _staff_with_any(permissions) -> bool:
    """True for a staff role holding at least one of *permissions*."""
    return any(require_staff(permission=p) is None for p in permissions)


def _may_read_any_attendance() -> bool:
    return _staff_with_any(ATTENDANCE_READ_ANY)


def _require_attendance_manager():
    """Gate register-writing endpoints. Returns a response, or None to allow.

    Creating sessions and records carried only ``@token_required``, so a
    student could invent a teaching session and mark themselves present at
    it — or mark a classmate absent. An attendance record is an academic
    record; writing one is a staff act.
    """
    if _staff_with_any(ATTENDANCE_MANAGE):
        return None
    logger.warning(
        "Refused attendance write by %r (role %r)",
        (g.current_user or {}).get("sub"), (g.current_user or {}).get("role"),
    )
    return _forbidden()


@attendance_bp.route("/sessions", methods=["GET"])
@token_required
def list_sessions():
    module_code = request.args.get("module_code")

    with get_connection() as conn:
        if module_code:
            rows = conn.execute(
                "SELECT * FROM attendance_sessions WHERE module_code = ? ORDER BY session_date DESC",
                (module_code,),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM attendance_sessions ORDER BY session_date DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM attendance_sessions").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "attendance_sessions", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@attendance_bp.route("/sessions", methods=["POST"])
@token_required
def create_session():
    denial = _require_attendance_manager()
    if denial is not None:
        return denial

    data = request.get_json(silent=True) or {}
    validate_attendance_session_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO attendance_sessions
               (module_code, session_date, session_type, location, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data["module_code"],
                data["session_date"],
                data["session_type"],
                data.get("location", ""),
                data.get("notes", ""),
                now,
            ),
        )
        session_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM attendance_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

    log_activity("create", "attendance_session", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@attendance_bp.route("/records", methods=["GET"])
@token_required
def list_records():
    student_id = request.args.get("student_id")
    session_id = request.args.get("session_id")

    # A student sees their own register entries and nobody else's; a
    # ``session_id`` filter must not widen that back out to the whole class.
    if not _may_read_any_attendance():
        student_id = current_subject_id()
        if not student_id:
            return _forbidden()
        session_id = None

    with get_connection() as conn:
        conditions = []
        params = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM attendance_records" + where + " ORDER BY recorded_at DESC",
            params,
        ).fetchall()

    log_activity("view", "attendance_records", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@attendance_bp.route("/records", methods=["POST"])
@token_required
def create_record():
    denial = _require_attendance_manager()
    if denial is not None:
        return denial

    data = request.get_json(silent=True) or {}
    validate_attendance_record_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO attendance_records
               (student_id, session_id, status, notes, recorded_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["student_id"],
                data["session_id"],
                data["status"],
                data.get("notes", ""),
                now,
            ),
        )
        record_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM attendance_records WHERE record_id = ?", (record_id,)
        ).fetchone()

    log_activity("create", "attendance_record", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@attendance_bp.route("/analytics/<student_id>", methods=["GET"])
@token_required
@scoped_to("student_id", permission="view_module_students")
def student_analytics(student_id: str):
    with get_connection() as conn:
        student = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not student:
            raise StudentNotFoundError(student_id)

        rows = conn.execute(
            """SELECT
                 asess.module_code,
                 COUNT(ar.record_id) AS total_sessions,
                 SUM(CASE WHEN ar.status = 'present' THEN 1 ELSE 0 END) AS present,
                 SUM(CASE WHEN ar.status = 'absent' THEN 1 ELSE 0 END) AS absent,
                 SUM(CASE WHEN ar.status = 'late' THEN 1 ELSE 0 END) AS late,
                 SUM(CASE WHEN ar.status = 'excused' THEN 1 ELSE 0 END) AS excused
               FROM attendance_records ar
               JOIN attendance_sessions asess ON ar.session_id = asess.session_id
               WHERE ar.student_id = ?
               GROUP BY asess.module_code""",
            (student_id,),
        ).fetchall()

    modules = []
    for r in rows:
        d = _row_to_dict(r)
        total = d.get("total_sessions", 0)
        present = d.get("present", 0)
        d["attendance_rate"] = round((present / total) * 100, 1) if total > 0 else 0.0
        modules.append(d)

    log_activity("view", "attendance_analytics", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "modules": modules})
