"""Chat rooms: the rooms, members and messages the GUI's chat tab shows.

These live in ``student_records.db`` (``chat_rooms``, ``chat_room_members``,
``chat_messages``) and go through the same service as the GUI, so bans, mutes,
slow mode, announcement-only rooms, encrypted rooms and the safeguarding filter
all apply. ``platform/services/chat_service.py`` is a separate, empty store used
only by the Socket.IO namespace; pointing this at it would have shown none of
the university's rooms. Membership is keyed on ``student_records.db`` user ids,
so the caller's is resolved by username.

Being a member is the only way to read a room. Staff get no bypass here, since
the conversations are between other people. Attachment paths on the server are
never returned, and uploading attachments is not offered.

Routes (under ``/api/v1/university/chat``):

* ``GET  /rooms``                     ``filter=joined`` (default) or ``public``
* ``POST /rooms``                     create; course and department rooms need staff
* ``GET  /rooms/<id>``                a member's view, or a public room's summary
* ``POST /rooms/<id>/join``           public rooms, or private with an invitation
* ``POST /rooms/<id>/leave``
* ``GET  /rooms/<id>/members``        members only
* ``GET  /rooms/<id>/messages``       members only
* ``POST /rooms/<id>/messages``       members only
* ``POST /rooms/<id>/read``           mark read up to the latest message
* ``DELETE /messages/<id>``           the sender's own, or a room admin's
* ``GET  /unread``                    unread count per joined room
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from education_system.api.university import _identity
from education_system.platform.delivery.api.kernel.problems import problem
from education_system.platform.delivery.api.university.auth import (
    authorize_object,
    current_subject_id,
    is_staff,
    token_required,
)
from education_system.platform.delivery.api.university.pagination import (
    get_pagination_params,
    paginated_response,
)
from education_system.platform.delivery.api.university.validators import (
    validate_chat_room_create,
    validate_enum,
    validate_string_length,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.exceptions import ValidationError

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")

_MAX_MESSAGE = 4000
_ROOM_TYPES = {"public", "private", "course", "department"}
_STAFF_ROOM_TYPES = {"course", "department"}
#: Course and department rooms are filled by enrolment sync. The service would
#: let anyone join by id, which would open another cohort's history.
_SELF_JOIN_TYPES = {"public", "private"}
_ROOM_COLUMNS = ("id, name, description, room_type, created_at, category, "
                 "linked_course_code, announcement_mode, is_active")


def _room(room_id: int):
    with get_connection() as conn:
        return conn.execute(
            f"SELECT {_ROOM_COLUMNS} FROM chat_rooms WHERE id = ?",  # nosec B608
            (room_id,)).fetchone()


def _membership(room_id: int):
    local_id = _identity.local_user_id()
    if local_id is None:
        return None
    with get_connection() as conn:
        return conn.execute(
            "SELECT is_admin, COALESCE(is_banned, 0) AS is_banned, muted_until "
            "FROM chat_room_members WHERE room_id = ? AND user_id = ?",
            (room_id, local_id)).fetchone()


def _deny_unless_room_member(room_id: int):
    """403 unless the caller is a member of the room and not banned from it."""
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    member = _membership(room_id)
    if member is None or member["is_banned"]:
        return problem(403, "You are not a member of this room.")
    return None


def _service_or_problem():
    service = _identity.communications()
    if service is None:
        return None, problem(403, "You have no university profile to use chat with.")
    return service, None


def _public_message(message: dict) -> dict:
    return {key: value for key, value in message.items() if key != "attachment_path"}


@chat_bp.route("/rooms", methods=["GET"])
@token_required
def list_rooms():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    room_filter = request.args.get("filter", "joined")
    if room_filter not in {"joined", "public"}:
        return problem(400, "'filter' must be 'joined' or 'public'.")
    page, per_page, _offset = get_pagination_params()
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    result = service.get_chat_rooms(user_filter=room_filter, page=page, limit=per_page) or {}
    return jsonify(paginated_response(result.get("rooms", []),
                                      result.get("total_count", 0), page, per_page))


@chat_bp.route("/rooms", methods=["POST"])
@token_required
def create_room():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    try:
        validate_chat_room_create(data)
        name = str(data["name"]).strip()
        validate_string_length(name, "name", 1, 100)
        validate_enum(data["room_type"], "room_type", _ROOM_TYPES)
    except (ValidationError, ValueError) as exc:
        return problem(400, str(exc))
    if data["room_type"] in _STAFF_ROOM_TYPES and not is_staff():
        return problem(403, "Only staff can create course and department rooms.")
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    room_id = service.create_chat_room(
        name, description=data.get("description"), room_type=data["room_type"],
        max_members=data.get("max_members"))
    if not room_id:
        return problem(409, "The room could not be created. The name may already be in "
                            "use, or 'max_members' may be below 2.")
    log_activity("create", "chat_rooms", user=_identity.username())
    return jsonify(dict(_room(room_id))), 201


@chat_bp.route("/rooms/<int:room_id>", methods=["GET"])
@token_required
def get_room(room_id: int):
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    room = _room(room_id)
    member = _membership(room_id) if room else None
    visible = room and room["is_active"] and (
        (member is not None and not member["is_banned"]) or room["room_type"] == "public")
    if not visible:
        return problem(404, "Room not found.")
    payload = dict(room)
    payload["is_member"] = member is not None
    payload["is_admin"] = bool(member and member["is_admin"])
    return jsonify(payload)


@chat_bp.route("/rooms/<int:room_id>/join", methods=["POST"])
@token_required
def join_room(room_id: int):
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    room = _room(room_id)
    if not room or not room["is_active"]:
        return problem(404, "Room not found.")
    if room["room_type"] not in _SELF_JOIN_TYPES:
        return problem(403, "Membership of this room comes from enrolment.")
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    result = service.join_chat_room(room_id)
    if result == "already_member":
        return jsonify({"room_id": room_id, "joined": False, "already_member": True})
    if result == "banned" or not result:
        # A private room with no invitation lands here too.
        return problem(403, "You cannot join this room.")
    return jsonify({"room_id": room_id, "joined": True})


@chat_bp.route("/rooms/<int:room_id>/leave", methods=["POST"])
@token_required
def leave_room(room_id: int):
    denied = _deny_unless_room_member(room_id)
    if denied is not None:
        return denied
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    if not service.leave_chat_room(room_id):
        return problem(409, "You could not leave this room. A room's only "
                            "administrator has to hand over first.")
    return jsonify({"room_id": room_id, "left": True})


@chat_bp.route("/rooms/<int:room_id>/members", methods=["GET"])
@token_required
def list_members(room_id: int):
    denied = _deny_unless_room_member(room_id)
    if denied is not None:
        return denied
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    # A fellow member's e-mail address and moderation state are not for everyone.
    public = ("user_id", "username", "full_name", "joined_at", "is_admin", "is_creator")
    members = [{key: m.get(key) for key in public}
               for m in service.get_room_members(room_id) or []]
    return jsonify({"items": members, "total": len(members)})


@chat_bp.route("/rooms/<int:room_id>/messages", methods=["GET"])
@token_required
def list_messages(room_id: int):
    denied = _deny_unless_room_member(room_id)
    if denied is not None:
        return denied
    page, per_page, _offset = get_pagination_params()
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    result = service.get_chat_messages(room_id, page=page, limit=per_page) or {}
    return jsonify(paginated_response(
        [_public_message(m) for m in result.get("messages", [])],
        result.get("total_count", 0), page, per_page))


@chat_bp.route("/rooms/<int:room_id>/messages", methods=["POST"])
@token_required
def send_message(room_id: int):
    denied = _deny_unless_room_member(room_id)
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    content = str(data.get("content") or "").strip()
    try:
        validate_string_length(content, "content", 1, _MAX_MESSAGE)
    except ValueError as exc:
        return problem(400, str(exc))
    reply_to = data.get("reply_to_id")
    if reply_to is not None and (isinstance(reply_to, bool) or not isinstance(reply_to, int)):
        return problem(400, "'reply_to_id' must be a message id.")
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    message_id = service.send_chat_message(room_id, content, reply_to_id=reply_to)
    if not message_id:
        # The service gives one answer for all of these.
        return problem(409, "The message was not sent. You may be muted, the room may "
                            "be closed, announcement-only or in slow mode, or the "
                            "safeguarding filter may have blocked it.")
    return jsonify({"id": message_id, "room_id": room_id}), 201


@chat_bp.route("/rooms/<int:room_id>/read", methods=["POST"])
@token_required
def mark_read(room_id: int):
    denied = _deny_unless_room_member(room_id)
    if denied is not None:
        return denied
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    if not service.mark_chat_messages_read(room_id):
        return problem(500, "The room could not be marked as read.")
    return jsonify({"room_id": room_id, "read": True})


@chat_bp.route("/messages/<int:message_id>", methods=["DELETE"])
@token_required
def delete_message(message_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT room_id FROM chat_messages WHERE id = ?",
                           (message_id,)).fetchone()
    # An unknown id and someone else's room look the same from outside.
    denied = (authorize_object(current_subject_id()) if row is None
              else _deny_unless_room_member(row["room_id"]))
    if denied is not None:
        return denied
    if row is None:
        return problem(403, "You are not a member of this room.")
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    if not service.delete_chat_message(message_id):
        return problem(403, "Only the sender or a room administrator can delete this.")
    log_activity("delete", "chat_messages", user=_identity.username())
    return jsonify({"id": message_id, "deleted": True})


@chat_bp.route("/unread", methods=["GET"])
@token_required
def unread_counts():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    service, refused = _service_or_problem()
    if refused is not None:
        return refused
    counts = service.get_unread_chat_counts() or {}
    return jsonify({"rooms": {str(room): count for room, count in counts.items()},
                    "total": sum(counts.values())})
