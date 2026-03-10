"""Helpdesk routes: support tickets, replies, KB articles, FAQs, SLA policies."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.university_system.api.auth import admin_required, token_required
from education_system.university_system.api.pagination import get_pagination_params, paginated_response
from education_system.university_system.api.validators import (
    validate_faq_create,
    validate_kb_article_create,
    validate_support_ticket_create,
    validate_ticket_reply_create,
)
from education_system.university_system.core.exceptions import ValidationError
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

helpdesk_bp = Blueprint("helpdesk", __name__, url_prefix="/api/helpdesk")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Support Tickets ----

@helpdesk_bp.route("/tickets", methods=["GET"])
@token_required
def list_tickets():
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM support_tickets WHERE title LIKE ? OR description LIKE ?",
                (pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = []
        params: list = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM support_tickets" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM support_tickets" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "support_tickets", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@helpdesk_bp.route("/tickets/<int:ticket_id>", methods=["GET"])
@token_required
def get_ticket(ticket_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
    if not row:
        raise ValidationError(f"Ticket {ticket_id} not found")
    log_activity("view", "support_ticket", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


@helpdesk_bp.route("/tickets", methods=["POST"])
@token_required
def create_ticket():
    data = request.get_json(silent=True) or {}
    validate_support_ticket_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO support_tickets
               (title, description, category, priority, status,
                student_id, created_datetime, created_at)
               VALUES (?, ?, ?, ?, 'open', ?, ?, ?)""",
            (
                data["title"],
                data["description"],
                data["category"],
                data["priority"],
                data.get("student_id"),
                now,
                now,
            ),
        )
        ticket_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()

    log_activity("create", "support_ticket", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


@helpdesk_bp.route("/tickets/<int:ticket_id>", methods=["PUT"])
@token_required
def update_ticket(ticket_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Ticket {ticket_id} not found")

    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")

    set_clauses = []
    values = []
    allowed = [
        "status", "priority", "category", "assigned_to", "resolution",
        "satisfaction_rating", "satisfaction_feedback",
    ]
    for field in allowed:
        if field in data:
            set_clauses.append(field + " = ?")
            values.append(data[field])

    if not set_clauses:
        raise ValidationError("No valid fields to update")

    set_clauses.append("updated_at = datetime('now')")
    values.append(ticket_id)

    with transaction() as conn:
        conn.execute(
            "UPDATE support_tickets SET " + ", ".join(set_clauses) + " WHERE ticket_id = ?",
            values,
        )

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()

    log_activity("update", "support_ticket", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row))


# ---- Ticket Replies ----

@helpdesk_bp.route("/tickets/<int:ticket_id>/replies", methods=["GET"])
@token_required
def list_replies(ticket_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if not existing:
            raise ValidationError(f"Ticket {ticket_id} not found")

        page, per_page, offset = get_pagination_params()
        rows = conn.execute(
            "SELECT * FROM ticket_replies WHERE ticket_id = ? ORDER BY created_at LIMIT ? OFFSET ?",
            (ticket_id, per_page, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM ticket_replies WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "ticket_replies", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@helpdesk_bp.route("/tickets/<int:ticket_id>/replies", methods=["POST"])
@token_required
def create_reply(ticket_id: int):
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM support_tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
    if not existing:
        raise ValidationError(f"Ticket {ticket_id} not found")

    data = request.get_json(silent=True) or {}
    validate_ticket_reply_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO ticket_replies
               (ticket_id, user_id, message, is_internal, reply_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ticket_id,
                g.current_user.get("user_id"),
                data["message"],
                data.get("is_internal", 0),
                data.get("reply_type", "comment"),
                now,
            ),
        )
        reply_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM ticket_replies WHERE reply_id = ?", (reply_id,)
        ).fetchone()

    log_activity("create", "ticket_reply", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- KB Articles ----

@helpdesk_bp.route("/kb", methods=["GET"])
@token_required
def list_kb_articles():
    category = request.args.get("category")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{search}%"
            rows = conn.execute(
                "SELECT * FROM kb_articles WHERE is_published = 1 AND (title LIKE ? OR content LIKE ? OR search_keywords LIKE ?)",
                (pattern, pattern, pattern),
            ).fetchall()
            items = [_row_to_dict(r) for r in rows]
            return jsonify({"items": items, "total": len(items)})

        conditions = ["is_published = 1"]
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = " WHERE " + " AND ".join(conditions)
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM kb_articles" + where + " ORDER BY view_count DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM kb_articles" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "kb_articles", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@helpdesk_bp.route("/kb", methods=["POST"])
@token_required
@admin_required
def create_kb_article():
    data = request.get_json(silent=True) or {}
    validate_kb_article_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO kb_articles
               (title, content, summary, category, author_id, created_datetime, is_published)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data["title"],
                data["content"],
                data.get("summary", ""),
                data["category"],
                g.current_user.get("sub"),
                now,
                data.get("is_published", 0),
            ),
        )
        article_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM kb_articles WHERE article_id = ?", (article_id,)
        ).fetchone()

    log_activity("create", "kb_article", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- FAQs ----

@helpdesk_bp.route("/faqs", methods=["GET"])
@token_required
def list_faqs():
    category = request.args.get("category")

    with get_connection() as conn:
        conditions = []
        params: list = []
        if category:
            conditions.append("category = ?")
            params.append(category)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        page, per_page, offset = get_pagination_params()
        params_count = list(params)
        params.extend([per_page, offset])

        rows = conn.execute(
            "SELECT * FROM faqs" + where + " ORDER BY view_count DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) FROM faqs" + where, params_count
        ).fetchone()
        total = total_row[0] if total_row else 0

    log_activity("view", "faqs", user=g.current_user.get("sub"))
    return jsonify(paginated_response(
        [_row_to_dict(r) for r in rows], total, page, per_page
    ))


@helpdesk_bp.route("/faqs", methods=["POST"])
@token_required
@admin_required
def create_faq():
    data = request.get_json(silent=True) or {}
    validate_faq_create(data)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with transaction() as conn:
        conn.execute(
            """INSERT INTO faqs
               (question, answer, category, created_by, created_datetime)
               VALUES (?, ?, ?, ?, ?)""",
            (
                data["question"],
                data["answer"],
                data["category"],
                g.current_user.get("sub"),
                now,
            ),
        )
        faq_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM faqs WHERE faq_id = ?", (faq_id,)
        ).fetchone()

    log_activity("create", "faq", user=g.current_user.get("sub"))
    return jsonify(_row_to_dict(row)), 201


# ---- SLA Policies ----

@helpdesk_bp.route("/sla-policies", methods=["GET"])
@token_required
def list_sla_policies():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sla_policies WHERE is_active = 1 ORDER BY name"
        ).fetchall()

    log_activity("view", "sla_policies", user=g.current_user.get("sub"))
    return jsonify({"items": [_row_to_dict(r) for r in rows], "total": len(rows)})
