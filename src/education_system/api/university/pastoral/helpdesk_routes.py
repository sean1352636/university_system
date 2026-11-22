"""Helpdesk routes: support tickets, replies, KB articles, FAQs, SLA policies."""

from __future__ import annotations

import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from education_system.platform.delivery.api.university.auth import admin_required, token_required
from education_system.platform.delivery.api.university.pagination import get_pagination_params, paginated_response
from education_system.platform.delivery.api.university.validators import (
    validate_faq_create,
    validate_kb_article_create,
    validate_support_ticket_create,
    validate_ticket_reply_create,
)
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)

helpdesk_bp = Blueprint("helpdesk", __name__, url_prefix="/api/helpdesk")


def _row_to_dict(row) -> dict:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}


# ---- Support Tickets ----
#
# Tickets are the one ticket model shared with Student Support: every read
# and write goes through the ticket service (``student_support.service`` /
# ``helpdesk.tickets.service``), which decides who may see or act on a
# ticket (team and confidentiality tier), reveals sealed text only after the
# gate, keeps internal notes from students, and applies routing, crisis
# detection, SLA and e-mail. The caller is the token's username (``sub``),
# never an id from the request.


def _ticket_service():
    from education_system.systems.university.domains.student_support.domain.student_support import (
        service,
    )
    return service


def _helpdesk_service():
    from education_system.systems.university.domains.student_support.domain.helpdesk.tickets import (
        service,
    )
    return service


def _caller() -> dict:
    """The signed-in caller as the ticket service takes them."""
    user = g.get("current_user") or {}
    return {"username": str(user.get("sub") or user.get("username") or "").strip(),
            "role": str(user.get("role") or "").lower(), "id": user.get("user_id")}


def _refused(exc: Exception):
    """A service refusal as a response: PermissionError 403, a missing
    ticket 404, any other ValueError 400 (the message is fit to show)."""
    if isinstance(exc, PermissionError):
        status, error = 403, "Forbidden"
    elif "not found" in str(exc).lower():
        status, error = 404, "Not Found"
    else:
        status, error = 400, "Bad Request"
    return jsonify({"error": error, "message": str(exc), "status": status}), status


def _is_case_worker(actor) -> bool:
    from education_system.systems.university.domains.student_support.domain.student_support import (
        auth as support_auth,
    )
    return support_auth.is_case_worker(actor)


@helpdesk_bp.route("/tickets", methods=["GET"])
@token_required
def list_tickets():
    actor = _caller()
    filters = {k: request.args.get(k) for k in ("status", "priority", "category", "search")
               if request.args.get(k)}
    svc = _ticket_service()
    lister = svc.list_tickets if _is_case_worker(actor) else svc.list_my_tickets
    page, per_page, _offset = get_pagination_params()
    try:
        result = lister(actor, filters, page, per_page)
    except (PermissionError, ValueError) as exc:
        return _refused(exc)
    log_activity("view", "support_tickets", user=actor["username"])
    if "search" in filters:
        return jsonify({"items": result["tickets"], "total": result["total_count"]})
    return jsonify(paginated_response(result["tickets"], result["total_count"], page, per_page))


@helpdesk_bp.route("/tickets/<int:ticket_id>", methods=["GET"])
@token_required
def get_ticket(ticket_id: int):
    actor = _caller()
    try:
        ticket = _ticket_service().get_ticket(actor, ticket_id)
    except (PermissionError, ValueError) as exc:
        return _refused(exc)
    log_activity("view", "support_ticket", user=actor["username"])
    return jsonify(ticket)


@helpdesk_bp.route("/tickets", methods=["POST"])
@token_required
def create_ticket():
    actor = _caller()
    data = request.get_json(silent=True) or {}
    validate_support_ticket_create(data)
    try:
        created = _helpdesk_service().submit_helpdesk_ticket(
            actor, subject=data["title"], description=data["description"],
            category=data["category"], priority=data["priority"],
            subcategory=data.get("subcategory"), channel="api",
            requester=data.get("student_id") or None)
        ticket = _ticket_service().get_ticket(actor, created["ticket_id"])
    except (PermissionError, ValueError) as exc:
        return _refused(exc)
    # Crisis language: the contacts to show the person at once.
    ticket["crisis"] = created.get("crisis")
    log_activity("create", "support_ticket", user=actor["username"])
    return jsonify(ticket), 201


@helpdesk_bp.route("/tickets/<int:ticket_id>", methods=["PUT"])
@token_required
def update_ticket(ticket_id: int):
    actor = _caller()
    data = request.get_json(silent=True) or {}
    if not data:
        raise ValidationError("No fields provided for update")
    allowed = ("status", "priority", "category", "assigned_to", "resolution",
               "satisfaction_rating", "satisfaction_feedback")
    if not any(f in data for f in allowed):
        raise ValidationError("No valid fields to update")
    svc = _ticket_service()
    try:
        # Raises when the caller may not see the ticket at all.
        svc.get_ticket(actor, ticket_id)
        if "satisfaction_rating" in data:
            svc.rate_ticket(actor, ticket_id, data["satisfaction_rating"],
                            data.get("satisfaction_feedback"))
        simple = {k: data[k] for k in ("priority", "category") if k in data}
        if simple:
            if not svc.bulk_update(actor, [ticket_id], simple):
                raise PermissionError(f"Only support staff working ticket #{ticket_id} "
                                      "can change it")
        if "assigned_to" in data:
            svc.assign(actor, ticket_id, data["assigned_to"])
        if "status" in data:
            svc.set_status(actor, ticket_id, data["status"], note=data.get("resolution"))
        elif data.get("resolution"):
            raise ValueError("A resolution is recorded with a status of resolved or closed")
        ticket = svc.get_ticket(actor, ticket_id)
    except (PermissionError, ValueError) as exc:
        return _refused(exc)
    log_activity("update", "support_ticket", user=actor["username"])
    return jsonify(ticket)


# ---- Ticket Replies ----

@helpdesk_bp.route("/tickets/<int:ticket_id>/replies", methods=["GET"])
@token_required
def list_replies(ticket_id: int):
    actor = _caller()
    try:
        # Internal notes reach only the staff working the ticket.
        replies = _ticket_service().get_ticket(actor, ticket_id)["responses"]
    except (PermissionError, ValueError) as exc:
        return _refused(exc)
    page, per_page, offset = get_pagination_params()
    log_activity("view", "ticket_replies", user=actor["username"])
    return jsonify(paginated_response(replies[offset:offset + per_page], len(replies),
                                      page, per_page))


@helpdesk_bp.route("/tickets/<int:ticket_id>/replies", methods=["POST"])
@token_required
def create_reply(ticket_id: int):
    actor = _caller()
    data = request.get_json(silent=True) or {}
    validate_ticket_reply_create(data)
    svc = _ticket_service()
    try:
        posted = svc.post_response(actor, ticket_id, data["message"],
                                   internal=bool(data.get("is_internal")))
        reply = next((r for r in svc.get_ticket(actor, ticket_id)["responses"]
                      if r.get("response_id") == posted["response_id"]),
                     {"response_id": posted["response_id"], "ticket_id": ticket_id})
    except (PermissionError, ValueError) as exc:
        return _refused(exc)
    reply["crisis"] = posted.get("crisis")
    log_activity("create", "ticket_reply", user=actor["username"])
    return jsonify(reply), 201


# ---- KB Articles ----

@helpdesk_bp.route("/kb", methods=["GET"])
@token_required
def list_kb_articles():
    category = request.args.get("category")
    search = request.args.get("search")

    with get_connection() as conn:
        if search:
            pattern = f"%{escape_like(search)}%"
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


# ---- Links, time, followers, incidents, known issues, support e-mail ----
#
# The same support services the GUI and CLI use; each checks the caller
# (working the ticket for links / time / followers, support staff for
# incidents and e-mail review, an administrator for the settings).


def _support(name):
    import importlib
    return importlib.import_module(
        f"education_system.systems.university.domains.student_support.domain.student_support.{name}")


def _support_gated(what, fn, *args, status=200, **kwargs):
    """``fn(caller, *args, **kwargs)`` as JSON; refusals as :func:`_refused`."""
    actor = _caller()
    try:
        result = fn(actor, *args, **kwargs)
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        return _refused(exc)
    log_activity("view" if request.method == "GET" else "update", what, user=actor["username"])
    if isinstance(result, list):
        result = {"items": result, "total": len(result)}
    elif isinstance(result, bool):
        result = {"changed": result}
    elif isinstance(result, int):
        result = {"count": result}
    return jsonify(result), status


def _body() -> dict:
    return request.get_json(silent=True) or {}


@helpdesk_bp.route("/tickets/<int:ticket_id>/links", methods=["GET"])
@token_required
def list_ticket_links(ticket_id: int):
    return _support_gated("ticket_links", _support("collaboration").list_links, ticket_id)


@helpdesk_bp.route("/tickets/<int:ticket_id>/links", methods=["POST"])
@token_required
def link_ticket(ticket_id: int):
    data = _body()
    return _support_gated("ticket_links", _support("collaboration").link_tickets, ticket_id,
                  data.get("ticket_id"), data.get("link_type") or "related_to", status=201)


@helpdesk_bp.route("/tickets/<int:ticket_id>/links/<int:other_id>", methods=["DELETE"])
@token_required
def unlink_ticket(ticket_id: int, other_id: int):
    return _support_gated("ticket_links", _support("collaboration").unlink_tickets, ticket_id, other_id)


@helpdesk_bp.route("/tickets/<int:ticket_id>/time", methods=["GET"])
@token_required
def list_ticket_time(ticket_id: int):
    return _support_gated("ticket_time", _support("collaboration").time_entries, ticket_id)


@helpdesk_bp.route("/tickets/<int:ticket_id>/time", methods=["POST"])
@token_required
def log_ticket_time(ticket_id: int):
    data = _body()
    try:
        minutes = int(data.get("minutes"))
    except (TypeError, ValueError):
        return _refused(ValueError("Give the time spent as a whole number of minutes"))
    return _support_gated("ticket_time", _support("collaboration").log_time, ticket_id, minutes,
                  data.get("description") or "", billable=bool(data.get("billable")), status=201)


@helpdesk_bp.route("/time/<int:time_id>", methods=["DELETE"])
@token_required
def delete_ticket_time(time_id: int):
    return _support_gated("ticket_time", _support("collaboration").delete_time_entry, time_id)


@helpdesk_bp.route("/tickets/<int:ticket_id>/followers", methods=["GET"])
@token_required
def list_ticket_followers(ticket_id: int):
    return _support_gated("ticket_followers", _support("collaboration").list_followers, ticket_id)


@helpdesk_bp.route("/tickets/<int:ticket_id>/followers", methods=["POST"])
@token_required
def add_ticket_follower(ticket_id: int):
    username = _body().get("username") or _caller()["username"]
    return _support_gated("ticket_followers", _support("collaboration").add_follower, ticket_id,
                  username, status=201)


@helpdesk_bp.route("/tickets/<int:ticket_id>/followers/<username>", methods=["DELETE"])
@token_required
def remove_ticket_follower(ticket_id: int, username: str):
    return _support_gated("ticket_followers", _support("collaboration").remove_follower, ticket_id,
                  username)


@helpdesk_bp.route("/followed", methods=["GET"])
@token_required
def list_followed_tickets():
    return _support_gated("ticket_followers", _support("collaboration").followed_tickets)


@helpdesk_bp.route("/incidents", methods=["GET"])
@token_required
def list_incidents():
    status = [s for s in (request.args.get("status") or "open,monitoring").split(",") if s]
    return _support_gated("support_incidents", _support("incidents").list_incidents, status)


@helpdesk_bp.route("/incidents", methods=["POST"])
@token_required
def declare_incident():
    data = _body()
    return _support_gated("support_incidents", _support("incidents").declare, data.get("title") or "",
                  data.get("description") or "", public_message=data.get("public_message") or "",
                  team=data.get("team"), severity=data.get("severity") or "major",
                  ticket_ids=data.get("ticket_ids") or (), status=201)


@helpdesk_bp.route("/incidents/<int:incident_id>", methods=["GET"])
@token_required
def get_incident(incident_id: int):
    return _support_gated("support_incidents", _support("incidents").get_incident, incident_id)


@helpdesk_bp.route("/incidents/<int:incident_id>/tickets", methods=["POST"])
@token_required
def attach_incident_tickets(incident_id: int):
    return _support_gated("support_incidents", _support("incidents").attach, incident_id,
                  _body().get("ticket_ids") or [])


@helpdesk_bp.route("/incidents/<int:incident_id>/tickets/<int:ticket_id>", methods=["DELETE"])
@token_required
def detach_incident_ticket(incident_id: int, ticket_id: int):
    return _support_gated("support_incidents", _support("incidents").detach, incident_id, ticket_id)


@helpdesk_bp.route("/incidents/<int:incident_id>/updates", methods=["POST"])
@token_required
def post_incident_update(incident_id: int):
    return _support_gated("support_incidents", _support("incidents").post_update, incident_id,
                  _body().get("message") or "")


@helpdesk_bp.route("/incidents/<int:incident_id>/status", methods=["POST"])
@token_required
def set_incident_status(incident_id: int):
    return _support_gated("support_incidents", _support("incidents").set_status, incident_id,
                  _body().get("status") or "")


@helpdesk_bp.route("/incidents/<int:incident_id>/resolve", methods=["POST"])
@token_required
def resolve_incident(incident_id: int):
    return _support_gated("support_incidents", _support("incidents").resolve, incident_id,
                  _body().get("resolution") or "")


@helpdesk_bp.route("/known-issues", methods=["GET"])
@token_required
def list_known_issues():
    return _support_gated("known_issues", _support("incidents").known_issues)


@helpdesk_bp.route("/known-issues/<int:incident_id>/affected", methods=["POST"])
@token_required
def report_affected(incident_id: int):
    return _support_gated("known_issues", _support("incidents").report_affected, incident_id,
                  _body().get("details") or "", status=201)


@helpdesk_bp.route("/inbound-mail", methods=["GET"])
@token_required
def list_inbound_mail():
    return _support_gated("support_inbound_mail", _support("email_in").list_mail,
                  request.args.get("status", "quarantined") or None)


@helpdesk_bp.route("/inbound-mail/<int:mail_id>", methods=["GET"])
@token_required
def read_inbound_mail(mail_id: int):
    return _support_gated("support_inbound_mail", _support("email_in").read_quarantined, mail_id)


@helpdesk_bp.route("/inbound-mail/<int:mail_id>/accept", methods=["POST"])
@token_required
def accept_inbound_mail(mail_id: int):
    return _support_gated("support_inbound_mail", _support("email_in").accept_quarantined, mail_id,
                  _body().get("requester") or "", status=201)


@helpdesk_bp.route("/inbound-mail/<int:mail_id>/discard", methods=["POST"])
@token_required
def discard_inbound_mail(mail_id: int):
    return _support_gated("support_inbound_mail", _support("email_in").discard_quarantined, mail_id,
                  _body().get("reason") or "")


@helpdesk_bp.route("/settings/automation", methods=["GET"])
@token_required
def get_automation_settings():
    return _support_gated("helpdesk_settings", _support("settings").read)


@helpdesk_bp.route("/settings/automation", methods=["PUT"])
@token_required
def update_automation_settings():
    return _support_gated("helpdesk_settings", _support("settings").update, _body())
