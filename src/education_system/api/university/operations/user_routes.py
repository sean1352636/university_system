"""University user profiles: the ``users`` table in ``student_records.db``.

Columns are selected by name, so a password hash, salt or MFA secret cannot come
back from here. ``user_accounts`` and the central ``auth.db`` hold those, and only
the sign-in status and last sign-in are read from ``auth.db``.

The ``<id>`` in these URLs is the local ``users.id``. It is not the ``user_id`` in
a token, which is the central id: ``admin`` is 19 centrally and 1 locally. So
"is this me" compares against the id resolved from the username.

Only name and e-mail can be changed, and only by a holder of ``manage_users``.
Role and active status are refused because they are not decided here: sign-in and
tokens read ``auth.db``, across every system, so changing the local copies would
report a change that does nothing. Creating accounts belongs to student
provisioning and staff HR. There is no password reset route.

Routes (under ``/api/v1/university/users``):

* ``GET   /``       administrators and staff; ``role``, ``search``, paging
* ``GET   /me``     any university user
* ``GET   /<id>``   that user, administrators and staff
* ``PATCH /<id>``   administrators (``manage_users``)
"""

from __future__ import annotations

from datetime import datetime

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
    validate_email,
    validate_enum,
    validate_string_length,
    validate_user_update,
)
from education_system.platform.identity.auth.db import connect as auth_connect
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.exceptions import ValidationError
from education_system.systems.university.infrastructure.security.audit_helpers import (
    safe_log_security_event,
)
from education_system.systems.university.infrastructure.sql_safety import escape_like

user_bp = Blueprint("users", __name__, url_prefix="/api/users")

_READER_ROLES = {"admin", "superadmin", "staff"}
#: Only administrators hold it.
_CHANGE_CAPABILITY = "manage_users"
_ROLES = {"admin", "instructor", "staff", "student"}
_EDITABLE = {"first_name", "last_name", "email"}
_SELECT = ("SELECT id, username, first_name, last_name, email, role, student_id, "
           "created_at, updated_at, COALESCE(service_account, 0) AS service_account "
           "FROM users")


def _with_login_state(rows) -> list[dict]:
    """Rows as dicts, with sign-in status and last sign-in from ``auth.db``."""
    users = [dict(row) for row in rows]
    names = [user["username"] for user in users]
    state = {}
    if names:
        placeholders = ",".join("?" for _ in names)
        with auth_connect(current_app.config.get("AUTH_DB_PATH")) as conn:
            state = {row[0]: (row[1], row[2]) for row in conn.execute(
                f"SELECT username, is_active, last_login FROM users "  # nosec B608
                f"WHERE username IN ({placeholders})", names)}
    for user in users:
        active, last_login = state.get(user["username"], (None, None))
        user["login_active"] = bool(active) if active is not None else None
        user["last_login"] = last_login
        user["service_account"] = bool(user["service_account"])
    return users


def _fetch(user_id: int):
    with get_connection() as conn:
        return conn.execute(_SELECT + " WHERE id = ?", (user_id,)).fetchone()


def _deny_unless_self_or_reader(user_id: int):
    """403 unless it is the caller's own local profile or they hold a reader role."""
    if user_id == _identity.local_user_id():
        return authorize_object(current_subject_id())
    return authorize_object(None, staff_roles=_READER_ROLES)


@user_bp.route("", methods=["GET"])
@token_required
def list_users():
    denied = authorize_object(None, staff_roles=_READER_ROLES)
    if denied is not None:
        return denied
    conditions, params = [], []
    role = request.args.get("role")
    if role:
        try:
            validate_enum(role, "role", _ROLES)
        except ValueError as exc:
            return problem(400, str(exc))
        conditions.append("role = ?")
        params.append(role)
    search = (request.args.get("search") or "").strip()
    if search:
        pattern = f"%{escape_like(search)}%"
        conditions.append("(username LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\' OR "
                          "first_name LIKE ? ESCAPE '\\' OR last_name LIKE ? ESCAPE '\\')")
        params += [pattern] * 4
    where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    page, per_page, offset = get_pagination_params()
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users" + where, params).fetchone()[0]
        rows = conn.execute(_SELECT + where + " ORDER BY username LIMIT ? OFFSET ?",
                            [*params, per_page, offset]).fetchall()
    log_activity("view", "users", user=_identity.username())
    return jsonify(paginated_response(_with_login_state(rows), total, page, per_page))


@user_bp.route("/me", methods=["GET"])
@token_required
def my_profile():
    denied = authorize_object(current_subject_id())
    if denied is not None:
        return denied
    local_id = _identity.local_user_id()
    row = _fetch(local_id) if local_id is not None else None
    if row is None:
        return problem(404, "You have no university profile.")
    return jsonify(_with_login_state([row])[0])


@user_bp.route("/<int:user_id>", methods=["GET"])
@token_required
def get_user(user_id: int):
    denied = _deny_unless_self_or_reader(user_id)
    if denied is not None:
        return denied
    row = _fetch(user_id)
    if row is None:
        return problem(404, "User not found.")
    return jsonify(_with_login_state([row])[0])


@user_bp.route("/<int:user_id>", methods=["PATCH"])
@token_required
def update_user(user_id: int):
    denied = require_staff(permission=_CHANGE_CAPABILITY)
    if denied is not None:
        return denied
    data = request.get_json(silent=True) or {}
    unknown = sorted(set(data) - _EDITABLE)
    if unknown:
        return problem(400, f"These fields cannot be changed here: {', '.join(unknown)}.")
    fields = {}
    try:
        validate_user_update(data)
        for name in ("first_name", "last_name"):
            if name in data:
                value = str(data[name] or "").strip()
                validate_string_length(value, name, 1, 100)
                fields[name] = value
        if "email" in data:
            email = str(data["email"] or "").strip()
            validate_email(email)
            fields["email"] = email
    except (ValidationError, ValueError) as exc:
        return problem(400, str(exc))
    if _fetch(user_id) is None:
        return problem(404, "User not found.")
    # Column names come from _EDITABLE, never from the request.
    assignments = ", ".join(f"{name} = ?" for name in fields)  # nosec B608
    with get_connection() as conn:
        if "email" in fields and conn.execute(
                "SELECT 1 FROM users WHERE email = ? AND id != ?",
                (fields["email"], user_id)).fetchone():
            return problem(409, "That e-mail address is already in use.")
        conn.execute(
            f"UPDATE users SET {assignments}, updated_at = ? WHERE id = ?",  # nosec B608
            [*fields.values(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_id])
        conn.commit()
    log_activity("update", "users", user=_identity.username())
    safe_log_security_event(
        action="USER_UPDATE", user_id=_identity.username(), resource_type="user",
        resource_id=str(user_id), details={"fields": sorted(fields)})
    return jsonify(_with_login_state([_fetch(user_id)])[0])
