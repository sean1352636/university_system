"""Timetable routes: module schedules and student timetables."""

from __future__ import annotations

import logging

from flask import Blueprint, g, jsonify

from education_system.university_system.api.auth import token_required
from education_system.university_system.core.exceptions import CourseNotFoundError, StudentNotFoundError
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

timetable_bp = Blueprint("timetable", __name__, url_prefix="/api/timetable")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@timetable_bp.route("/modules/<module_code>", methods=["GET"])
@token_required
def module_schedule(module_code: str):
    with get_connection() as conn:
        mod = conn.execute(
            "SELECT 1 FROM modules WHERE module_code = ?", (module_code,)
        ).fetchone()
        if not mod:
            raise CourseNotFoundError(f"Module {module_code} not found")

        rows = conn.execute(
            "SELECT * FROM module_schedule WHERE module_code = ? ORDER BY day_of_week, start_time",
            (module_code,),
        ).fetchall()

    log_activity("view", "module_schedule", user=g.current_user.get("sub"))
    return jsonify({"module_code": module_code, "schedule": [_row_to_dict(r) for r in rows]})


@timetable_bp.route("/students/<student_id>", methods=["GET"])
@token_required
def student_timetable(student_id: str):
    with get_connection() as conn:
        student = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
        if not student:
            raise StudentNotFoundError(student_id)

        rows = conn.execute(
            """SELECT ms.* FROM module_schedule ms
               JOIN student_modules sm ON sm.module_code = ms.module_code
               WHERE sm.student_id = ?
               ORDER BY ms.day_of_week, ms.start_time""",
            (student_id,),
        ).fetchall()

    log_activity("view", "student_timetable", user=g.current_user.get("sub"))
    return jsonify({"student_id": student_id, "timetable": [_row_to_dict(r) for r in rows]})
