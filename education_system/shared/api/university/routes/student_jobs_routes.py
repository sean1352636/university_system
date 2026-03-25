"""Student jobs routes: campus jobs, applications, employment, and work hours."""

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

student_jobs_bp = Blueprint("student_jobs", __name__, url_prefix="/api/student-jobs")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- postings ----

@student_jobs_bp.route("/postings", methods=["GET"])
@token_required
def list_postings():
    search = request.args.get("search")
    job_category = request.args.get("job_category")
    employment_type = request.args.get("employment_type")
    is_active = request.args.get("is_active")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM campus_job_postings WHERE job_title LIKE ? OR employer_name LIKE ? OR job_description LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if job_category:
            conditions.append("job_category = ?")
            params.append(job_category)
        if employment_type:
            conditions.append("employment_type = ?")
            params.append(employment_type)
        if is_active:
            conditions.append("is_active = ?")
            params.append(is_active)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM campus_job_postings" + where + " ORDER BY job_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_job_postings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_job_postings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_jobs_bp.route("/postings/<int:job_id>", methods=["GET"])
@token_required
def get_posting(job_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_job_postings WHERE job_id = ?", (job_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"postings {job_id} not found")
    log_activity("view", "campus_job_postings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@student_jobs_bp.route("/postings", methods=["POST"])
@token_required
def create_posting():
    data = request.get_json(silent=True) or {}
    for field in ["employer_name", "job_title", "job_description"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_job_postings
               (employer_name, job_title, job_description, department_id, job_category, employment_type, hourly_rate, hours_per_week, total_positions, required_skills, location, application_deadline, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["employer_name"], data["job_title"], data["job_description"], data.get("department_id", ""), data.get("job_category", ""), data.get("employment_type", ""), data.get("hourly_rate", ""), data.get("hours_per_week", ""), data.get("total_positions", ""), data.get("required_skills", ""), data.get("location", ""), data.get("application_deadline", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_job_postings WHERE job_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "campus_job_postings", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- applications ----

@student_jobs_bp.route("/applications", methods=["GET"])
@token_required
def list_applications():
    job_id = request.args.get("job_id")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if job_id:
            conditions.append("job_id = ?")
            params.append(job_id)
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM campus_job_applications" + where + " ORDER BY application_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM campus_job_applications" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "campus_job_applications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_jobs_bp.route("/applications/<int:application_id>", methods=["GET"])
@token_required
def get_application(application_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_job_applications WHERE application_id = ?", (application_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"applications {application_id} not found")
    log_activity("view", "campus_job_applications", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@student_jobs_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    for field in ["job_id", "student_id"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO campus_job_applications
               (job_id, student_id, cover_letter, resume_url, availability, expected_hours_per_week, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["job_id"], data["student_id"], data.get("cover_letter", ""), data.get("resume_url", ""), data.get("availability", ""), data.get("expected_hours_per_week", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM campus_job_applications WHERE application_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "campus_job_applications", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- employment ----

@student_jobs_bp.route("/employment", methods=["GET"])
@token_required
def list_employment():
    student_id = request.args.get("student_id")
    employment_status = request.args.get("employment_status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if employment_status:
            conditions.append("employment_status = ?")
            params.append(employment_status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_employment" + where + " ORDER BY employment_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_employment" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_employment", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@student_jobs_bp.route("/employment/<int:employment_id>", methods=["GET"])
@token_required
def get_employment(employment_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_employment WHERE employment_id = ?", (employment_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"employment {employment_id} not found")
    log_activity("view", "student_employment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@student_jobs_bp.route("/employment", methods=["POST"])
@token_required
def create_employment():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "job_id", "start_date"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_employment
               (student_id, job_id, start_date, application_id, hourly_rate, max_hours_per_week, supervisor_id, department, position_title, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["job_id"], data["start_date"], data.get("application_id", ""), data.get("hourly_rate", ""), data.get("max_hours_per_week", ""), data.get("supervisor_id", ""), data.get("department", ""), data.get("position_title", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_employment WHERE employment_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_employment", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
