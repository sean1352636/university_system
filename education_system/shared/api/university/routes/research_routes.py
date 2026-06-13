"""Research routes: projects and publications."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.shared.api.university.auth import token_required
from education_system.shared.api.university.pagination import get_pagination_params, paginated_response
from education_system.shared.api.university.validators import (
    validate_research_project_create,
    validate_research_publication_create,
)
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

research_bp = Blueprint("research", __name__, url_prefix="/api/research")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Projects ----

@research_bp.route("/projects", methods=["GET"])
@token_required
def list_projects():
    department = request.args.get("department")
    status = request.args.get("status")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM research_projects WHERE project_title LIKE ? OR project_description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if department:
            conditions.append("department = ?")
            params.append(department)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM research_projects" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM research_projects" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "research_projects", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@research_bp.route("/projects/<int:project_id>", methods=["GET"])
@token_required
def get_project(project_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM research_projects WHERE project_id = ?", (project_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Research project {project_id} not found")
    log_activity("view", "research_project", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@research_bp.route("/projects", methods=["POST"])
@token_required
def create_project():
    data = request.get_json(silent=True) or {}
    validate_research_project_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO research_projects
               (project_title, project_description, principal_investigator_id,
                department, project_type, start_date, end_date, status,
                total_budget, funding_source, ethics_approval_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, 'pending')""",
            (
                data["project_title"],
                data.get("project_description", ""),
                data["principal_investigator_id"],
                data["department"],
                data["project_type"],
                data["start_date"],
                data.get("end_date"),
                data.get("total_budget", 0),
                data.get("funding_source", ""),
            ),
        )
        project_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM research_projects WHERE project_id = ?", (project_id,)
        ).fetchone()

    log_activity("create", "research_project", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@research_bp.route("/projects/<int:project_id>", methods=["PUT"])
@token_required
def update_project(project_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM research_projects WHERE project_id = ?", (project_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Research project {project_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "project_title", "project_description", "department", "project_type",
        "start_date", "end_date", "status", "total_budget", "funding_source",
        "ethics_approval_status", "ethics_approval_date",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    values.append(project_id)
    with transaction() as conn:
        conn.execute(
            "UPDATE research_projects SET " + ", ".join(set_clauses) + " WHERE project_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM research_projects WHERE project_id = ?", (project_id,)
        ).fetchone()

    log_activity("update", "research_project", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Publications ----

@research_bp.route("/publications", methods=["GET"])
@token_required
def list_publications():
    project_id = request.args.get("project_id")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
            rows = conn.execute(
                "SELECT * FROM research_publications WHERE title LIKE ? OR authors LIKE ? OR keywords LIKE ?",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        if project_id:
            rows = conn.execute(
                "SELECT * FROM research_publications WHERE project_id = ? ORDER BY publication_date DESC",
                (project_id,),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM research_publications ORDER BY publication_date DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) FROM research_publications").fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "research_publications", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@research_bp.route("/publications", methods=["POST"])
@token_required
def create_publication():
    data = request.get_json(silent=True) or {}
    validate_research_publication_create(data)

    with transaction() as conn:
        conn.execute(
            """INSERT INTO research_publications
               (project_id, title, authors, publication_type, journal_name,
                conference_name, publication_date, doi, url, abstract, keywords, is_peer_reviewed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("project_id"),
                data["title"],
                data["authors"],
                data["publication_type"],
                data.get("journal_name", ""),
                data.get("conference_name", ""),
                data.get("publication_date", ""),
                data.get("doi", ""),
                data.get("url", ""),
                data.get("abstract", ""),
                data.get("keywords", ""),
                data.get("is_peer_reviewed", 0),
            ),
        )
        pub_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM research_publications WHERE publication_id = ?", (pub_id,)
        ).fetchone()

    log_activity("create", "research_publication", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201
