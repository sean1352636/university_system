"""Clearing and adjustment routes: vacancies, applications, and adjustment requests."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

clearing_adjustment_bp = Blueprint("clearing_adjustment", __name__, url_prefix="/api/clearing-adjustment")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- vacancies ----

@clearing_adjustment_bp.route("/vacancies", methods=["GET"])
@token_required
def list_vacancies():
    active_only = request.args.get("active_only", "true").lower() == "true"
    department = request.args.get("department")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM clearing_vacancies WHERE course_name LIKE ? OR course_code LIKE ? OR department LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if active_only:
            conditions.append("is_active = 1")
        if department:
            conditions.append("department = ?")
            params.append(department)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM clearing_vacancies" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM clearing_vacancies" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "clearing_vacancies", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@clearing_adjustment_bp.route("/vacancies/<int:vacancy_id>", methods=["GET"])
@token_required
def get_vacancy(vacancy_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clearing_vacancies WHERE id = ?", (vacancy_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Vacancy {vacancy_id} not found")
    log_activity("view", "clearing_vacancy", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@clearing_adjustment_bp.route("/vacancies", methods=["POST"])
@token_required
def create_vacancy():
    data = request.get_json(silent=True) or {}
    for field in ["course_code", "course_name"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO clearing_vacancies
               (course_code, course_name, department, available_places,
                minimum_tariff, requirements, academic_year)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["course_code"], data["course_name"], data.get("department", ""),
             data.get("available_places", 0), data.get("minimum_tariff", 0),
             data.get("requirements", ""), data.get("academic_year", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clearing_vacancies WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "clearing_vacancy", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@clearing_adjustment_bp.route("/vacancies/<int:vacancy_id>", methods=["PUT"])
@token_required
def update_vacancy(vacancy_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM clearing_vacancies WHERE id = ?", (vacancy_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Vacancy {vacancy_id} not found")

    data = request.get_json(silent=True) or {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    allowed = ["course_name", "department", "available_places", "minimum_tariff",
               "requirements", "is_active", "academic_year"]
    sets = ["updated_at = ?"]
    params: list = [now]
    for key in allowed:
        if key in data:
            sets.append(f"{key} = ?")
            params.append(data[key])
    params.append(vacancy_id)

    with transaction() as conn:
        conn.execute(
            f"UPDATE clearing_vacancies SET {', '.join(sets)} WHERE id = ?", params
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clearing_vacancies WHERE id = ?", (vacancy_id,)
        ).fetchone()

    log_activity("update", "clearing_vacancy", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- applications ----

@clearing_adjustment_bp.route("/applications", methods=["GET"])
@token_required
def list_applications():
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM clearing_applications" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM clearing_applications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "clearing_applications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@clearing_adjustment_bp.route("/applications/<int:app_id>", methods=["GET"])
@token_required
def get_application(app_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clearing_applications WHERE id = ?", (app_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Clearing application {app_id} not found")
    log_activity("view", "clearing_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@clearing_adjustment_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    if "applicant_name" not in data:
        raise ValidationError("Missing required field: applicant_name")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO clearing_applications
               (applicant_name, email, phone, ucas_id, tariff_points,
                qualifications, preferred_course, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["applicant_name"], data.get("email", ""), data.get("phone", ""),
             data.get("ucas_id", ""), data.get("tariff_points", 0),
             data.get("qualifications", ""), data.get("preferred_course", ""),
             data.get("notes", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clearing_applications WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "clearing_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@clearing_adjustment_bp.route("/applications/<int:app_id>/status", methods=["PUT"])
@token_required
def update_application_status(app_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM clearing_applications WHERE id = ?", (app_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Clearing application {app_id} not found")

    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE clearing_applications SET status = ?, processed_by = ?, processed_at = ? WHERE id = ?",
            (data["status"], data.get("processed_by", ""), now, app_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM clearing_applications WHERE id = ?", (app_id,)
        ).fetchone()

    log_activity("update", "clearing_application_status", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- adjustment requests ----

@clearing_adjustment_bp.route("/adjustments", methods=["GET"])
@token_required
def list_adjustments():
    status = request.args.get("status")
    student_id = request.args.get("student_id")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM adjustment_requests" + where + " ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM adjustment_requests" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "adjustment_requests", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@clearing_adjustment_bp.route("/adjustments/<int:request_id>", methods=["GET"])
@token_required
def get_adjustment(request_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM adjustment_requests WHERE id = ?", (request_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Adjustment request {request_id} not found")
    log_activity("view", "adjustment_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@clearing_adjustment_bp.route("/adjustments", methods=["POST"])
@token_required
def create_adjustment():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "original_course", "requested_course"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO adjustment_requests
               (student_id, original_course, requested_course, reason, current_grades)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data["original_course"], data["requested_course"],
             data.get("reason", ""), data.get("current_grades", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM adjustment_requests WHERE id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "adjustment_request", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@clearing_adjustment_bp.route("/adjustments/<int:request_id>/status", methods=["PUT"])
@token_required
def process_adjustment(request_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM adjustment_requests WHERE id = ?", (request_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Adjustment request {request_id} not found")

    data = request.get_json(silent=True) or {}
    if "status" not in data:
        raise ValidationError("Missing required field: status")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            "UPDATE adjustment_requests SET status = ?, decided_by = ?, decided_at = ? WHERE id = ?",
            (data["status"], data.get("decided_by", ""), now, request_id),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM adjustment_requests WHERE id = ?", (request_id,)
        ).fetchone()

    log_activity("update", "adjustment_request_status", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- statistics ----

@clearing_adjustment_bp.route("/statistics", methods=["GET"])
@token_required
def get_statistics():
    with get_connection() as conn:
        total_vacancies = conn.execute("SELECT COUNT(*) FROM clearing_vacancies").fetchone()[0]
        active_vacancies = conn.execute("SELECT COUNT(*) FROM clearing_vacancies WHERE is_active = 1").fetchone()[0]
        total_applications = conn.execute("SELECT COUNT(*) FROM clearing_applications").fetchone()[0]
        pending_applications = conn.execute("SELECT COUNT(*) FROM clearing_applications WHERE status = 'pending'").fetchone()[0]
        total_adjustments = conn.execute("SELECT COUNT(*) FROM adjustment_requests").fetchone()[0]
        pending_adjustments = conn.execute("SELECT COUNT(*) FROM adjustment_requests WHERE status = 'pending'").fetchone()[0]

    log_activity("view", "clearing_statistics", user=g.current_user.get("sub"))
    return jsonify({
        "total_vacancies": total_vacancies,
        "active_vacancies": active_vacancies,
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "total_adjustments": total_adjustments,
        "pending_adjustments": pending_adjustments,
    })


@clearing_adjustment_bp.route("/available-courses", methods=["GET"])
@token_required
def get_available_courses():
    min_tariff = request.args.get("min_tariff", 0, type=int)

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM clearing_vacancies WHERE is_active = 1 AND available_places > 0 "
            "AND minimum_tariff <= ? ORDER BY course_name",
            (min_tariff,),
        ).fetchall()

    log_activity("view", "clearing_available_courses", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@clearing_adjustment_bp.route("/auto-shortlist", methods=["POST"])
@token_required
def auto_shortlist():
    shortlisted = []
    with transaction() as conn:
        apps = conn.execute(
            "SELECT * FROM clearing_applications WHERE status = 'pending'"
        ).fetchall()
        for app in apps:
            app_dict = _row_to_dict(app)
            vacancies = conn.execute(
                "SELECT * FROM clearing_vacancies WHERE is_active = 1 AND available_places > 0 "
                "AND minimum_tariff <= ? AND (course_name = ? OR course_code = ?)",
                (app_dict.get("tariff_points", 0),
                 app_dict.get("preferred_course", ""),
                 app_dict.get("preferred_course", "")),
            ).fetchall()
            if vacancies:
                conn.execute(
                    "UPDATE clearing_applications SET status = 'shortlisted' WHERE id = ?",
                    (app_dict["id"],),
                )
                shortlisted.append(app_dict)

    log_activity("action", "clearing_auto_shortlist", user=g.current_user.get("sub"))
    return jsonify({"shortlisted": shortlisted, "count": len(shortlisted)})
