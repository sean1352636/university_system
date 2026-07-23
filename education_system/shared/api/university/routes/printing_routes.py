"""Printing routes: quotas, print jobs, and credit transactions."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.post_18.university_system.core.exceptions import ValidationError
from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

printing_bp = Blueprint("printing", __name__, url_prefix="/api/printing")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- quotas ----

@printing_bp.route("/quotas", methods=["GET"])
@token_required
def list_quotas():
    student_id = request.args.get("student_id")
    semester = request.args.get("semester")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if semester:
            conditions.append("semester = ?")
            params.append(semester)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM print_quotas" + where + " ORDER BY quota_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM print_quotas" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "print_quotas", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@printing_bp.route("/quotas/<int:quota_id>", methods=["GET"])
@token_required
def get_quota(quota_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM print_quotas WHERE quota_id = ?", (quota_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"quotas {quota_id} not found")
    log_activity("view", "print_quotas", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@printing_bp.route("/quotas", methods=["POST"])
@token_required
def create_quota():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "total_pages", "semester"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO print_quotas
               (student_id, total_pages, semester, used_pages, color_pages_used, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["total_pages"], data["semester"], data.get("used_pages", 0), data.get("color_pages_used", 0), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM print_quotas WHERE quota_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "print_quotas", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201

# ---- jobs ----

@printing_bp.route("/jobs", methods=["GET"])
@token_required
def list_jobs():
    search = request.args.get("search")
    student_id = request.args.get("student_id")
    status = request.args.get("status")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM print_jobs WHERE file_name LIKE ?",
                (pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
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
            "SELECT * FROM print_jobs" + where + " ORDER BY job_id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM print_jobs" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "print_jobs", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@printing_bp.route("/jobs/<int:job_id>", methods=["GET"])
@token_required
def get_job(job_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM print_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"jobs {job_id} not found")
    log_activity("view", "print_jobs", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))

@printing_bp.route("/jobs", methods=["POST"])
@token_required
def create_job():
    data = request.get_json(silent=True) or {}
    for field in ["student_id", "file_name", "pages"]:
        if field not in data:
            raise ValidationError(f"Missing required field: {field}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO print_jobs
               (student_id, file_name, pages, copies, color, double_sided, paper_size, printer_location, cost_credits, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["student_id"], data["file_name"], data["pages"], data.get("copies", 1), data.get("color", 0), data.get("double_sided", 0), data.get("paper_size", ""), data.get("printer_location", ""), data.get("cost_credits", ""), now,),
        )
        new_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM print_jobs WHERE job_id = ?", (new_id,)
        ).fetchone()

    log_activity("create", "print_jobs", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
