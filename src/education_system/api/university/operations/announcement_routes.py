"""Announcements: the ``announcements`` table the GUI's Announcements tab uses.

Reading and creating go through the same communication service as the GUI, so
the audience rule and the e-mail to the audience are the same. A reader sees
what is active, in its date window and aimed at their role. The ids in that
table are ``student_records.db`` ids, so the caller's is resolved by username.

Routes (under ``/api/v1/university/announcements``):

* ``GET    /``              what the caller may read; ``scope=managed`` lists
                            what they may edit, including hidden ones
* ``POST   /``              create (staff)
* ``GET    /<id>``          one announcement, under the reader rule
* ``PATCH  /<id>``          edit (its creator or an administrator)
* ``DELETE /<id>``          hide (its creator or an administrator)
* ``POST   /<id>/viewed``   record that the caller has read it
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

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
    validate_announcement_create,
    validate_announcement_update,
    validate_date,
    validate_enum,
    validate_string_length,
)
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.exceptions import ValidationError

announcement_bp = Blueprint("announcements", __name__, url_prefix="/api/announcements")

_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
#: The audiences the service can actually reach; anything else would be saved
#: and then shown to nobody.
_AUDIENCES = {"all", "students", "staff", "instructors"}
#: Who reads which audience. The same map as ``get_announcements``.
_READS = {"student": {"all", "students"}, "instructor": {"all", "instructors"},
          "staff": {"all", "staff"}, "admin": {"all", "staff"}}
_ADMIN_ROLES = {"admin", "superadmin"}
_EDITABLE = {"title", "content", "target_audience", "is_urgent", "start_date", "end_date"}
_COLUMNS = ("SELECT a.id, a.creator_id, u.username AS creator, a.title, a.content, "
            "a.target_audience, a.is_urgent, a.is_active, a.start_date, a.end_date, "
            "a.created_at, a.updated_at FROM announcements a "
            "LEFT JOIN users u ON u.id = a.creator_id")


def _to_dict(row) -> dict:
    item = {key: row[key] for key in row.keys()}
    item["is_urgent"] = bool(item["is_urgent"])
    item["is_active"] = bool(item["is_active"])
    return item


def _fetch(announcement_id: int):
    with get_connection() as conn:
        return conn.execute(_COLUMNS + " WHERE a.id = ?", (announcement_id,)).fetchone()


def _may_read(row) -> bool:
    role = _identity.service_role()
    if role == "admin" or row["creator_id"] == _identity.local_user_id():
        return True
    now = datetime.now().strftime(_DATE_FORMAT)
    return (bool(row["is_active"]) and row["start_date"] <= now
            and (row["end_date"] is None or row["end_date"] >= now)
            and row["target_audience"] in _READS.get(role, {"all"}))


def _deny_unless_editor(row):
    """403 unless the caller is staff and created it, or is an administrator."""
    denied = require_staff()
    if denied is not None:
        return denied
    if row["creator_id"] == _identity.local_user_id():
        return None
    return authorize_object(None, staff_roles=_ADMIN_ROLES)


def _validated_fields(data: dict) -> dict:
    """The body's fields, checked; raises ``ValueError`` on the first bad one."""
    fields = {}
    for name in ("title", "content"):
        if name in data:
            value = str(data[name] or "").strip()
            validate_string_length(value, name, 1, 200 if name == "title" else 10000)
            fields[name] = value
    if "target_audience" in data:
        validate_enum(data["target_audience"], "target_audience", _AUDIENCES)
        fields["target_audience"] = data["target_audience"]
    if "is_urgent" in data:
        fields["is_urgent"] = 1 if data["is_urgent"] else 0
    for name in ("start_date", "end_date"):
        if data.get(name):
            validate_date(data[name], _DATE_FORMAT)
            fields[name] = data[name]
        elif name == "end_date" and name in data:
            fields[name] = None
    start, end = fields.get("start_date"), fields.get("end_date")
    if start and end and end < start:
        raise ValueError("'end_date' must not be before 'start_date'.")
    return fields


@announcement_bp.route("", methods=["GET"])
@token_required
def list_announcements():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    page, per_page, offset = get_pagination_params()
    if request.args.get("scope") == "managed":
        denied = require_staff()
        if denied is not None:
            return denied
        where, params = "", []
        if _identity.service_role() != "admin":
            where, params = " WHERE a.creator_id = ?", [_identity.local_user_id()]
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM announcements a" + where, params).fetchone()[0]
            rows = conn.execute(
                _COLUMNS + where + " ORDER BY a.created_at DESC LIMIT ? OFFSET ?",
                [*params, per_page, offset]).fetchall()
        return jsonify(paginated_response([_to_dict(r) for r in rows], total, page, per_page))

    service = _identity.communications()
    if service is None:
        return jsonify(paginated_response([], 0, page, per_page))
    result = service.get_announcements(page=page, limit=per_page) or {}
    return jsonify(paginated_response(result.get("announcements", []),
                                      result.get("total_count", 0), page, per_page))


@announcement_bp.route("", methods=["POST"])
@token_required
def create_announcement():
    denied = require_staff()
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    data.setdefault("start_date", datetime.now().strftime(_DATE_FORMAT))
    try:
        validate_announcement_create(data)
        fields = _validated_fields(data)
    except (ValidationError, ValueError) as exc:
        return problem(400, str(exc))
    service = _identity.communications()
    if service is None:
        return problem(409, "You have no university profile to post announcements from.")
    announcement_id = service.create_announcement(
        fields["title"], fields["content"], fields["target_audience"],
        is_urgent=fields.get("is_urgent", 0), start_date=fields.get("start_date"),
        end_date=fields.get("end_date"))
    if not announcement_id:
        return problem(500, "The announcement could not be saved.")
    log_activity("create", "announcements", user=_identity.username())
    return jsonify(_to_dict(_fetch(announcement_id))), 201


@announcement_bp.route("/<int:announcement_id>", methods=["GET"])
@token_required
def get_announcement(announcement_id: int):
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    row = _fetch(announcement_id)
    if row is None or not _may_read(row):
        return problem(404, "Announcement not found.")
    return jsonify(_to_dict(row))


@announcement_bp.route("/<int:announcement_id>", methods=["PATCH"])
@token_required
def update_announcement(announcement_id: int):
    row = _fetch(announcement_id)
    denied = require_staff() if row is None else _deny_unless_editor(row)
    if denied is not None:
        return denied
    if row is None:
        return problem(404, "Announcement not found.")
    data = request.get_json(silent=True) or {}
    unknown = sorted(set(data) - _EDITABLE)
    if unknown:
        return problem(400, f"These fields cannot be changed: {', '.join(unknown)}.")
    try:
        validate_announcement_update(data)
        fields = _validated_fields(data)
    except (ValidationError, ValueError) as exc:
        return problem(400, str(exc))
    if not fields:
        return problem(400, "No fields provided for update.")
    # Column names come from _EDITABLE, never from the request.
    assignments = ", ".join(f"{name} = ?" for name in fields)  # nosec B608
    with get_connection() as conn:
        conn.execute(
            f"UPDATE announcements SET {assignments}, updated_at = ? WHERE id = ?",  # nosec B608
            [*fields.values(), datetime.now().strftime(_DATE_FORMAT), announcement_id])
        conn.commit()
    log_activity("update", "announcements", user=_identity.username())
    return jsonify(_to_dict(_fetch(announcement_id)))


@announcement_bp.route("/<int:announcement_id>", methods=["DELETE"])
@token_required
def hide_announcement(announcement_id: int):
    """Hides it, as the GUI does; the row and its read history stay."""
    row = _fetch(announcement_id)
    denied = require_staff() if row is None else _deny_unless_editor(row)
    if denied is not None:
        return denied
    if row is None:
        return problem(404, "Announcement not found.")
    with get_connection() as conn:
        conn.execute("UPDATE announcements SET is_active = 0, updated_at = ? WHERE id = ?",
                     (datetime.now().strftime(_DATE_FORMAT), announcement_id))
        conn.commit()
    log_activity("delete", "announcements", user=_identity.username())
    return jsonify({"id": announcement_id, "is_active": False})


@announcement_bp.route("/<int:announcement_id>/viewed", methods=["POST"])
@token_required
def mark_viewed(announcement_id: int):
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    row = _fetch(announcement_id)
    if row is None or not _may_read(row):
        return problem(404, "Announcement not found.")
    service = _identity.communications()
    if service is None:
        return problem(409, "You have no university profile to record this against.")
    from education_system.systems.university.infrastructure.email.announcements import (
        mark_announcement_viewed,
    )
    if not mark_announcement_viewed(service, announcement_id):
        return problem(500, "The announcement could not be marked as viewed.")
    return jsonify({"id": announcement_id, "viewed": True})
