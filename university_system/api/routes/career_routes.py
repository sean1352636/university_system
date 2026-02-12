"""Career services routes: job postings, applications, and internships."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import validate_job_application_create, validate_job_posting_create
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

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
            pattern = f"%{search}%"
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
