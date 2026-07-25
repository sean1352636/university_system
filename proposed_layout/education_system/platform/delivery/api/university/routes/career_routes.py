"""Career services routes: job postings, applications, and internships."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import validate_job_application_create, validate_job_posting_create
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

career_bp = Blueprint("career", __name__, url_prefix="/api/career")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Job Postings ----

@career_bp.route("/jobs", methods=["GET"])
@token_required
def list_jobs():
    search = request.args.get("search")
    category = request.args.get("category")
    job_type = request.args.get("job_type")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM job_postings WHERE is_active = 1 AND (job_title LIKE ? OR company_name LIKE ? OR job_description LIKE ?)",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = ["is_active = 1"]
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)
        if job_type:
            conditions.append("job_type = ?")
            params.append(job_type)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM job_postings" + where + " ORDER BY post_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM job_postings" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "job_postings", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@career_bp.route("/jobs/<int:job_id>", methods=["GET"])
@token_required
def get_job(job_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM job_postings WHERE job_id = ?", (job_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Job posting {job_id} not found")
    log_activity("view", "job_posting", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@career_bp.route("/jobs", methods=["POST"])
@token_required
def create_job():
    data = request.get_json(silent=True) or {}
    validate_job_posting_create(data)

    now = datetime.now().strftime("%Y-%m-%d")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO job_postings
               (posted_by, company_name, job_title, job_description, location,
                job_type, salary_range, requirements, application_method,
                contact_email, post_date, expiry_date, category, experience_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("posted_by"),
                data["company_name"],
                data["job_title"],
                data["job_description"],
                data.get("location", ""),
                data.get("job_type", "full-time"),
                data.get("salary_range", ""),
                data.get("requirements", ""),
                data.get("application_method", ""),
                data.get("contact_email", ""),
                now,
                data.get("expiry_date", ""),
                data.get("category", ""),
                data.get("experience_level", ""),
            ),
        )
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM job_postings WHERE job_id = ?", (job_id,)
        ).fetchone()

    log_activity("create", "job_posting", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Applications ----

@career_bp.route("/applications", methods=["GET"])
@token_required
def list_applications():
    applicant_id = request.args.get("applicant_id")
    job_id = request.args.get("job_id")

    with get_connection() as conn:
        conditions = []
        params = []
        if applicant_id:
            conditions.append("ja.applicant_id = ?")
            params.append(applicant_id)
        if job_id:
            conditions.append("ja.job_id = ?")
            params.append(job_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT ja.*, jp.job_title, jp.company_name"
            " FROM job_applications ja"
            " LEFT JOIN job_postings jp ON ja.job_id = jp.job_id"
            + where + " ORDER BY ja.application_date DESC",
            params,
        ).fetchall()

    log_activity("view", "job_applications", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


@career_bp.route("/applications", methods=["POST"])
@token_required
def create_application():
    data = request.get_json(silent=True) or {}
    validate_job_application_create(data)

    now = datetime.now().strftime("%Y-%m-%d")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO job_applications
               (job_id, applicant_id, application_date, status, cover_letter, resume_path)
               VALUES (?, ?, ?, 'submitted', ?, ?)""",
            (
                data["job_id"],
                data["applicant_id"],
                now,
                data.get("cover_letter", ""),
                data.get("resume_path", ""),
            ),
        )
        app_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM job_applications WHERE application_id = ?", (app_id,)
        ).fetchone()

    log_activity("create", "job_application", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Internships ----

@career_bp.route("/internships", methods=["GET"])
@token_required
def list_internships():
    page, per_page, offset = get_pagination_params()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM internships WHERE status = 'active' ORDER BY posted_date DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM internships WHERE status = 'active'"
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "internships", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@career_bp.route("/internships/<int:internship_id>/placements", methods=["GET"])
@token_required
def list_placements(internship_id: int):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM internship_placements WHERE internship_id = ? ORDER BY start_date DESC",
            (internship_id,),
        ).fetchall()

    log_activity("view", "internship_placements", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Resumes ----

@career_bp.route("/resumes", methods=["POST"])
@token_required
def upload_resume():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "resume_name", "file_url"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    is_primary = data.get("is_primary", False)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        if is_primary:
            conn.execute(
                "UPDATE student_resumes SET is_primary = 0 WHERE student_id = ?",
                (data["student_id"],),
            )
        conn.execute(
            """INSERT INTO student_resumes
               (student_id, resume_name, file_url, template_used, is_primary, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["resume_name"], data["file_url"],
             data.get("template_used", ""), 1 if is_primary else 0, now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_resumes WHERE resume_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_resume", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@career_bp.route("/resumes", methods=["GET"])
@token_required
def get_student_resumes():
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("student_id query parameter is required")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_resumes WHERE student_id = ? ORDER BY is_primary DESC, created_at DESC",
            (student_id,),
        ).fetchall()

    log_activity("view", "student_resumes", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Interviews ----

@career_bp.route("/interviews", methods=["POST"])
@token_required
def schedule_interview():
    data = request.get_json(silent=True) or {}
    for field in ["application_id", "interview_type", "interview_date", "interview_time"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO interview_schedules
               (application_id, interview_type, interview_date, interview_time,
                duration_minutes, location, meeting_link, interviewer_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["application_id"], data["interview_type"], data["interview_date"],
             data["interview_time"], data.get("duration_minutes", 60),
             data.get("location", ""), data.get("meeting_link", ""),
             data.get("interviewer_name", "")),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Update application status
        conn.execute(
            "UPDATE job_applications SET status = 'interview_scheduled' WHERE application_id = ?",
            (data["application_id"],),
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM interview_schedules WHERE interview_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "interview_schedule", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@career_bp.route("/interviews", methods=["GET"])
@token_required
def list_interviews():
    application_id = request.args.get("application_id")
    conditions = []
    params: list = []
    if application_id:
        conditions.append("application_id = ?")
        params.append(application_id)

    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM interview_schedules" + where + " ORDER BY interview_date DESC, interview_time DESC",
            params,
        ).fetchall()

    log_activity("view", "interview_schedules", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})


# ---- Career Events ----

@career_bp.route("/events", methods=["POST"])
@token_required
def create_career_event():
    data = request.get_json(silent=True) or {}
    for field in ["event_name", "event_type", "event_date", "location"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    start_datetime = f"{data['event_date']} {data.get('event_time', '')}".strip()
    with transaction() as conn:
        conn.execute(
            """INSERT INTO unified_events
               (title, event_type, start_datetime, location, description, max_capacity, is_public, source_type)
               VALUES (?, ?, ?, ?, ?, ?, 1, 'career')""",
            (data["event_name"], data["event_type"], start_datetime,
             data["location"], data.get("description", ""),
             data.get("max_attendees", 100)),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM unified_events WHERE event_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "career_event", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@career_bp.route("/events", methods=["GET"])
@token_required
def list_career_events():
    with get_connection() as conn:
        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM unified_events WHERE source_type = 'career' ORDER BY start_datetime DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM unified_events WHERE source_type = 'career'"
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "career_events", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@career_bp.route("/events/<int:event_id>/register", methods=["POST"])
@token_required
def register_for_career_event(event_id: int):
    data = request.get_json(silent=True) or {}
    student_id = data.get("student_id")
    if not student_id:
        raise ValidationError("Missing required field: student_id")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO unified_event_registrations
               (event_id, student_id, registered_at)
               VALUES (?, ?, ?)""",
            (event_id, student_id, now),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM unified_event_registrations WHERE registration_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "career_event_registration", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Skills ----

@career_bp.route("/skills", methods=["POST"])
@token_required
def add_skill():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "skill_name", "skill_category", "proficiency_level"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO student_skills
               (student_id, skill_name, skill_category, proficiency_level, verified)
               VALUES (?, ?, ?, ?, ?)""",
            (data["student_id"], data["skill_name"], data["skill_category"],
             data["proficiency_level"], data.get("verified", 0)),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_skills WHERE skill_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "student_skill", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@career_bp.route("/skills", methods=["GET"])
@token_required
def get_student_skills():
    student_id = request.args.get("student_id")
    if not student_id:
        raise ValidationError("student_id query parameter is required")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM student_skills WHERE student_id = ? ORDER BY skill_category, skill_name",
            (student_id,),
        ).fetchall()

    log_activity("view", "student_skills", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
