"""Enrollment routes: enroll, drop, list.

The actual table is ``student_modules`` with columns:
  id, student_id, module_code, enrollment_date, status,
  module_type, module_name, grade, completion_date
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.validators import validate_enrollment_create
from education_system.systems.university.infrastructure.exceptions import (
    AlreadyEnrolledError,
    CourseFullError,
    CourseNotFoundError,
    EnrollmentClosedError,
    PrerequisiteError,
    StudentNotFoundError,
    ValidationError,
)
from education_system.systems.university.services.bus.enrolment_bus import (
    check_enrolment_eligibility,
)
from education_system.systems.university.services.bus.registration_calendar import (
    classify_drop,
    record_status_change,
)
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

enrollment_bp = Blueprint("enrollments", __name__, url_prefix="/api/enrollments")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


@enrollment_bp.route("", methods=["GET"])
@token_required
def list_enrollments():
    student_id = request.args.get("student_id")
    module_code = request.args.get("module_code")

    clauses = []
    params = []
    if student_id:
        clauses.append("student_id = ?")
        params.append(student_id)
    if module_code:
        clauses.append("module_code = ?")
        params.append(module_code)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_modules" + where, params
        ).fetchall()

    log_activity("view", "enrollments", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@enrollment_bp.route("", methods=["POST"])
@token_required
def enroll():
    data = request.get_json(silent=True) or {}
    validate_enrollment_create(data)

    student_id = data["student_id"]
    module_code = data["module_code"]

    with get_connection() as conn:
        # Verify student exists
        if not conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (student_id,)
        ).fetchone():
            raise StudentNotFoundError(student_id)

        # Verify module exists
        if not conn.execute(
            "SELECT 1 FROM modules WHERE module_code = ?", (module_code,)
        ).fetchone():
            raise CourseNotFoundError(f"Module {module_code} not found")

        # Check duplicate
        if conn.execute(
            "SELECT 1 FROM student_modules WHERE student_id = ? AND module_code = ?",
            (student_id, module_code),
        ).fetchone():
            raise AlreadyEnrolledError(student_id, module_code)

        # Enrolment rules: prerequisites, co-requisites, capacity. Shared
        # with both registration GUIs so the API cannot be used to sidestep
        # a rule the desktop client enforces. Staff clients may pass
        # ``override_eligibility`` to record a deliberate exception.
        eligibility = check_enrolment_eligibility(
            student_id, module_code, section_id=data.get("section_id"), conn=conn)
        if not eligibility.ok:
            if data.get("override_eligibility"):
                logger.warning(
                    "Enrolment rules overridden via API for %s in %s by %s: %s",
                    student_id, module_code, g.current_user.get("sub"),
                    eligibility.reason().replace("\n", "; "),
                )
            elif eligibility.only_capacity:
                raise CourseFullError(
                    module_code, details=eligibility.to_dict(),
                )
            elif eligibility.window and not eligibility.window["open"]:
                # Outside the registration window: a client retrying later is
                # the right response, so this is not a prerequisite failure.
                raise EnrollmentClosedError(
                    module_code, details=eligibility.to_dict(),
                )
            elif eligibility.needs_section:
                raise ValidationError(
                    f"{module_code} runs in sections — supply section_id. "
                    f"Open sections: "
                    + ", ".join(
                        f"{s['section_number']} (id {s['id']})"
                        for s in eligibility.sections
                    )
                )
            else:
                missing = [
                    m["code"]
                    for b in eligibility.blocks
                    for m in b.details.get("missing", [])
                ]
                raise PrerequisiteError(
                    module_code, missing_prereqs=missing,
                    details=eligibility.to_dict(),
                )

    now = datetime.now().strftime("%Y-%m-%d")
    section_id = data.get("section_id")
    with transaction() as conn:
        if section_id is None:
            conn.execute(
                """INSERT INTO student_modules
                   (student_id, module_code, enrollment_date, status, module_type)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, module_code, now, "Enrolled",
                 data.get("module_type", "Standard")),
            )
        else:
            conn.execute(
                """INSERT INTO student_modules
                   (student_id, module_code, enrollment_date, status, module_type,
                    section_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (student_id, module_code, now, "Enrolled",
                 data.get("module_type", "Standard"), section_id),
            )
        record_status_change(
            student_id, module_code, "Enrolled",
            changed_by=g.current_user.get("sub"), source="api",
            verdict=eligibility.window, conn=conn,
        )

    # Fetch the newly created enrollment
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_modules WHERE student_id = ? AND module_code = ? ORDER BY id DESC LIMIT 1",
            (student_id, module_code),
        ).fetchone()

    log_activity("create", "enrollment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@enrollment_bp.route("/<int:enrollment_id>", methods=["DELETE"])
@token_required
def drop_enrollment(enrollment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_modules WHERE id = ?", (enrollment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Enrollment {enrollment_id} not found")

    # Leaving a module is a status change, not an erasure: after the drop
    # deadline it becomes a transcript-visible withdrawal, and after the
    # withdrawal deadline it needs the formal process. Deleting the row would
    # destroy both the record and the evidence of when it happened.
    verdict = classify_drop()
    if not verdict["allowed"]:
        raise EnrollmentClosedError(
            row["module_code"], details={"reason": verdict["reason"],
                                         "deadline": verdict["deadline"]},
        )

    new_status = verdict["status"]
    with transaction() as conn:
        conn.execute(
            "UPDATE student_modules SET status = ? WHERE id = ?",
            (new_status, enrollment_id),
        )
        record_status_change(
            row["student_id"], row["module_code"], new_status,
            from_status=row["status"], changed_by=g.current_user.get("sub"),
            source="api", verdict=verdict, conn=conn,
        )

    log_activity("update", "enrollment", user=g.current_user.get("sub"))
    return jsonify({
        "message": f"Enrollment {enrollment_id} {new_status.lower()}",
        "status": new_status,
        "on_transcript": verdict["on_transcript"],
        "reason": verdict["reason"],
    })
