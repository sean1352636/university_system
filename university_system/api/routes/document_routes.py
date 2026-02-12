"""Document management routes: repository, student documents, workflows."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from university_system.api.auth import token_required
from university_system.api.pagination import get_pagination_params, paginated_response
from university_system.api.validators import validate_document_create
from university_system.core.exceptions import ValidationError
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

document_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Document Repository ----

@document_bp.route("/repository", methods=["GET"])
@token_required
def list_repository():
    module_code = request.args.get("module_code")
    author_id = request.args.get("author_id")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM document_repository WHERE title LIKE ?",
                (pattern,),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if module_code:
            conditions.append("module_code = ?")
            params.append(module_code)
        if author_id:
            conditions.append("author_id = ?")
            params.append(author_id)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM document_repository" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM document_repository" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "document_repository", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@document_bp.route("/repository/<int:doc_id>", methods=["GET"])
@token_required
def get_repository_document(doc_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_repository WHERE id = ?", (doc_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Document {doc_id} not found")
    log_activity("view", "repository_document", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@document_bp.route("/repository", methods=["POST"])
@token_required
def create_repository_document():
    data = request.get_json(silent=True) or {}
    validate_document_create(data)

    import hashlib
    content_hash = hashlib.sha256(data["content"].encode()).hexdigest()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with transaction() as conn:
        conn.execute(
            """INSERT INTO document_repository
               (title, content, content_hash, author_id, module_code,
                submission_date, file_type, word_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["title"],
                data["content"],
                content_hash,
                g.current_user.get("user_id"),
                data.get("module_code"),
                now,
                data.get("file_type"),
                len(data["content"].split()),
            ),
        )
        did = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM document_repository WHERE id = ?", (did,)
        ).fetchone()

    log_activity("create", "repository_document", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- Student Documents ----

@document_bp.route("/student-documents", methods=["GET"])
@token_required
def list_student_documents():
    student_id = request.args.get("student_id")
    verification_status = request.args.get("verification_status")
    workflow_status = request.args.get("workflow_status")

    with get_connection() as conn:
        conditions = ["is_current_version = 1"]
        params: list = []
        if student_id:
            conditions.append("student_id = ?")
            params.append(student_id)
        if verification_status:
            conditions.append("verification_status = ?")
            params.append(verification_status)
        if workflow_status:
            conditions.append("workflow_status = ?")
            params.append(workflow_status)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM student_documents" + where + " ORDER BY upload_date DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM student_documents" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "student_documents", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@document_bp.route("/student-documents/<int:doc_id>", methods=["GET"])
@token_required
def get_student_document(doc_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM student_documents WHERE document_id = ?", (doc_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Student document {doc_id} not found")
    log_activity("view", "student_document", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Workflows ----

@document_bp.route("/workflows", methods=["GET"])
@token_required
def list_workflows():
    document_id = request.args.get("document_id")
    status = request.args.get("status")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if document_id:
            conditions.append("document_id = ?")
            params.append(document_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        rows = conn.execute(
            "SELECT * FROM document_workflow" + where + " ORDER BY step_order",
            params,
        ).fetchall()

    log_activity("view", "document_workflows", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
