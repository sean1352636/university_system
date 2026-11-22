"""Notifications: the caller's inbox, as the GUI's Notifications Hub shows it.

There is no notifications table. It was removed on purpose, and the Hub reads
two message stores instead. Each keys on a different id, which is the trap here:

* University ``messages`` (``student_records.db``): ``recipient_id`` is the
  local ``users.id``, resolved from the username.
* ``cross_system_messages`` (``auth.db``): ``recipient_id`` is the central id,
  which is the token's ``user_id``.

Every query pins the recipient to the caller, so another person's message is a
404, the same as one that does not exist. Delivery preferences are the platform's
``/api/v1/notifications/preferences``.

Routes (under ``/api/v1/university/notifications``):

* ``GET  /``                         ``source=all|university|cross-system``,
                                     ``unread_only=true`` by default, as in the Hub
* ``GET  /unread-count``
* ``GET  /<source>/<id>``
* ``POST /<source>/<id>/read``
* ``POST /read-all``
* ``POST /``                         staff: put a message in someone's inbox
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from education_system.api.university import _identity
from education_system.platform.delivery.api.kernel.problems import problem
from education_system.platform.delivery.api.university.auth import (
    authorize_object,
    current_subject_id,
    require_staff,
    token_required,
)
from education_system.platform.delivery.api.university.pagination import (
    get_pagination_params,
    paginated_response,
)
from education_system.platform.delivery.api.university.validators import (
    validate_string_length,
)
from education_system.platform.features.messaging.messaging_service import (
    InterSystemMessagingService,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.email.messages_inbox import (
    deliver_inbox_message,
)

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

UNIVERSITY, CROSS_SYSTEM = "university", "cross-system"
_SOURCES = {UNIVERSITY, CROSS_SYSTEM}
_SYSTEM_KEY = "university"
_VISIBLE = ("m.recipient_id = ? AND COALESCE(m.is_archived, 0) = 0 "
            "AND COALESCE(m.is_deleted_by_recipient, 0) = 0")


def _cross_system() -> InterSystemMessagingService:
    return InterSystemMessagingService(db_path=current_app.config.get("AUTH_DB_PATH"))


def _university_item(row) -> dict:
    return {"source": UNIVERSITY, "id": row["id"], "subject": row["subject"],
            "body": row["content"] or row["message"], "sender": row["sender"],
            "sent_at": row["sent_at"], "is_read": bool(row["is_read"])}


def _cross_system_item(row: dict) -> dict:
    return {"source": CROSS_SYSTEM, "id": row["id"], "subject": row.get("subject"),
            "body": row.get("body"), "sender": row.get("sender_name"),
            "sender_system": row.get("sender_system"), "student_id": row.get("student_id"),
            "student_name": row.get("student_name"), "sent_at": row.get("created_at"),
            "is_read": bool(row.get("is_read"))}


_UNIVERSITY_SELECT = ("SELECT m.id, m.subject, m.content, m.message, m.sent_at, "
                      "COALESCE(m.is_read, 0) AS is_read, u.username AS sender "
                      "FROM messages m LEFT JOIN users u ON u.id = m.sender_id ")


def _university_page(unread_only: bool, limit: int) -> tuple[list[dict], int]:
    local_id = _identity.local_user_id()
    if local_id is None:
        return [], 0
    where = _VISIBLE + (" AND COALESCE(m.is_read, 0) = 0" if unread_only else "")
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM messages m WHERE " + where,
                             (local_id,)).fetchone()[0]
        rows = conn.execute(
            _UNIVERSITY_SELECT + "WHERE " + where + " ORDER BY m.sent_at DESC, m.id DESC LIMIT ?",
            (local_id, limit)).fetchall()
    return [_university_item(r) for r in rows], total


def _cross_system_inbox(unread_only: bool) -> list[dict]:
    rows = _cross_system().get_inbox(_identity.shared_auth_id(), system=_SYSTEM_KEY)
    return [_cross_system_item(r) for r in rows if not unread_only or not r.get("is_read")]


def _flag(name: str, default: bool) -> bool:
    value = request.args.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes"}


def _sort_key(item: dict) -> str:
    # University rows have a space where cross-system ones have a 'T'.
    return str(item.get("sent_at") or "").replace("T", " ")


@notification_bp.route("", methods=["GET"])
@token_required
def list_notifications():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    source = request.args.get("source", "all")
    if source != "all" and source not in _SOURCES:
        return problem(400, "'source' must be all, university or cross-system.")
    unread_only = _flag("unread_only", True)
    page, per_page, offset = get_pagination_params()
    items, total = [], 0
    if source in ("all", UNIVERSITY):
        local_items, local_total = _university_page(unread_only, offset + per_page)
        items += local_items
        total += local_total
    if source in ("all", CROSS_SYSTEM):
        cross_items = _cross_system_inbox(unread_only)
        items += cross_items
        total += len(cross_items)
    items.sort(key=_sort_key, reverse=True)
    return jsonify(paginated_response(items[offset:offset + per_page], total, page, per_page))


@notification_bp.route("/unread-count", methods=["GET"])
@token_required
def unread_count():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    local = _university_page(True, 0)[1]
    cross = _cross_system().get_unread_count(_identity.shared_auth_id(), _SYSTEM_KEY)
    return jsonify({"university": local, "cross_system": cross, "total": local + cross})


def _own_university(message_id: int):
    local_id = _identity.local_user_id()
    if local_id is None:
        return None
    with get_connection() as conn:
        return conn.execute(
            _UNIVERSITY_SELECT + "WHERE m.id = ? AND m.recipient_id = ? "
            "AND COALESCE(m.is_deleted_by_recipient, 0) = 0",
            (message_id, local_id)).fetchone()


def _own_cross_system(message_id: int):
    row = _cross_system().get_message(message_id)
    if (row and row.get("recipient_id") == _identity.shared_auth_id()
            and row.get("recipient_system") == _SYSTEM_KEY):
        return row
    return None


def _own_item(source: str, message_id: int):
    """The caller's own message as an API item, or ``None``."""
    if source == UNIVERSITY:
        row = _own_university(message_id)
        return _university_item(row) if row else None
    if source == CROSS_SYSTEM:
        row = _own_cross_system(message_id)
        return _cross_system_item(row) if row else None
    return None


@notification_bp.route("/<source>/<int:message_id>", methods=["GET"])
@token_required
def get_notification(source: str, message_id: int):
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    item = _own_item(source, message_id)
    if item is None:
        return problem(404, "Notification not found.")
    return jsonify(item)


@notification_bp.route("/<source>/<int:message_id>/read", methods=["POST"])
@token_required
def mark_read(source: str, message_id: int):
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    if _own_item(source, message_id) is None:
        return problem(404, "Notification not found.")
    if source == UNIVERSITY:
        with get_connection() as conn:
            conn.execute(
                "UPDATE messages SET is_read = 1, read_at = COALESCE(read_at, datetime('now')) "
                "WHERE id = ? AND recipient_id = ?",
                (message_id, _identity.local_user_id()))
            conn.commit()
    else:
        _cross_system().mark_read(message_id)
    return jsonify({"source": source, "id": message_id, "is_read": True})


@notification_bp.route("/read-all", methods=["POST"])
@token_required
def mark_all_read():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    local_changed = 0
    local_id = _identity.local_user_id()
    if local_id is not None:
        with get_connection() as conn:
            local_changed = conn.execute(
                "UPDATE messages SET is_read = 1, read_at = COALESCE(read_at, datetime('now')) "
                "WHERE recipient_id = ? AND COALESCE(is_read, 0) = 0 "
                "AND COALESCE(is_archived, 0) = 0 AND COALESCE(is_deleted_by_recipient, 0) = 0",
                (local_id,)).rowcount
            conn.commit()
    service = _cross_system()
    unread = [row for row in service.get_inbox(_identity.shared_auth_id(), system=_SYSTEM_KEY)
              if not row.get("is_read")]
    for row in unread:
        service.mark_read(row["id"])
    return jsonify({"university": local_changed, "cross_system": len(unread)})


@notification_bp.route("", methods=["POST"])
@token_required
def send_notification():
    denied = require_staff()
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    recipient = str(data.get("recipient") or "").strip()
    subject = str(data.get("subject") or "").strip()
    body = str(data.get("body") or "").strip()
    try:
        validate_string_length(recipient, "recipient", 1, 100)
        validate_string_length(subject, "subject", 1, 200)
        validate_string_length(body, "body", 1, 10000)
    except ValueError as exc:
        return problem(400, str(exc))
    # A missing profile falls to the system sender rather than an id from the
    # other id space.
    message_id = deliver_inbox_message(recipient, subject, body,
                                       sender_id=_identity.local_user_id())
    if message_id is None:
        return problem(404, "No university user matches that recipient.")
    log_activity("create", "notifications", user=_identity.username())
    return jsonify({"source": UNIVERSITY, "id": message_id}), 201
