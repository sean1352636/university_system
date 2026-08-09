"""Per-module chat rooms for newly registered students.

When a student is registered they are enrolled on an 18-module curriculum
(see :mod:`curriculum`). This module ensures a chat room exists for each of
those modules and adds the student as a member, so they are auto-joined to one
chat room per module they study upon account creation.

Rooms live in ``student_records.db`` (tables ``chat_rooms`` /
``chat_room_members``) and follow the same convention seeded by Alembic
migration ``a4c91b7d2e10`` (room ``name`` == module code, ``description`` ==
module name, ``room_type`` == 'course'). Shared by both the GUI and CLI
student-registration flows. Best-effort: never raises to the caller.
"""

from __future__ import annotations

import logging
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)

logger = logging.getLogger(__name__)

ROOM_TYPE = "course"
ROOM_MAX_MEMBERS = 500


def _admin_user_id(cursor) -> int | None:
    """Return the id of an admin user to own auto-created rooms, or None."""
    cursor.execute(
        "SELECT id FROM users "
        "WHERE LOWER(role) = 'admin' OR LOWER(username) = 'admin' "
        "ORDER BY id LIMIT 1"
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _module_info(cursor, code: str) -> tuple[str, str | None]:
    """Return (module_name, course_code) for a module code, with fallbacks."""
    cursor.execute(
        "SELECT module_name, course FROM modules WHERE module_code = ?", (code,)
    )
    row = cursor.fetchone()
    if not row:
        return code, None
    return (row[0] or code), row[1]


def _ensure_room(cursor, code: str, created_by: int, now: str) -> tuple[int, str]:
    """Return ``(room_id, module_name)``, creating the room if it's missing.

    A freshly created room gets its creator (an admin where available) added as
    an admin member, mirroring migration ``a4c91b7d2e10``.
    """
    cursor.execute(
        "SELECT id, description FROM chat_rooms WHERE name = ? AND is_active = 1",
        (code,),
    )
    row = cursor.fetchone()
    if row:
        name, _ = _module_info(cursor, code)
        return row[0], (row[1] or name)

    name, course_code = _module_info(cursor, code)
    cursor.execute(
        "INSERT INTO chat_rooms "
        "(name, description, room_type, created_by, created_at, is_active, "
        " max_members, linked_course_code) "
        "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
        (code, name, ROOM_TYPE, created_by, now, ROOM_MAX_MEMBERS, course_code),
    )
    room_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin) "
        "VALUES (?, ?, ?, 1)",
        (room_id, created_by, now),
    )
    logger.info("module-chat: created room for module %s (id=%s)", code, room_id)
    return room_id, name


def _join(cursor, room_id: int, user_id: int, now: str) -> None:
    """Add ``user_id`` to ``room_id`` as a member, if not already one."""
    cursor.execute(
        "SELECT 1 FROM chat_room_members WHERE room_id = ? AND user_id = ?",
        (room_id, user_id),
    )
    if cursor.fetchone():
        return
    cursor.execute(
        "INSERT INTO chat_room_members (room_id, user_id, joined_at, is_admin) "
        "VALUES (?, ?, ?, 0)",
        (room_id, user_id, now),
    )


def ensure_module_chat_rooms_and_join(
    student_id: str, module_codes
) -> list[tuple[str, str]]:
    """Ensure a chat room exists for each module and join the student to it.

    ``student_id`` is resolved to a user via ``users.username``. Any module
    without a room gets one created (name=module code, description=module
    name); the student is then added to every room. Idempotent on membership
    and safe to re-run.

    Returns the list of ``(module_code, module_name)`` the student is now a
    member of. Best-effort: logs problems and returns what it can, never
    raises.
    """
    if not module_codes:
        return []

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (student_id,))
        row = cursor.fetchone()
        if not row:
            logger.warning("module-chat: no user row for student %s", student_id)
            return []
        user_id = row[0]
        created_by = _admin_user_id(cursor) or user_id

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        joined: list[tuple[str, str]] = []
        for code in module_codes:
            try:
                room_id, name = _ensure_room(cursor, code, created_by, now)
                _join(cursor, room_id, user_id, now)
                joined.append((code, name))
            except sqlite3.Error as exc:  # isolate a single bad module
                logger.warning("module-chat: failed for module %s: %s", code, exc)
        conn.commit()
        return joined
    except sqlite3.Error as exc:
        logger.warning("module-chat: auto-join failed for %s: %s", student_id, exc)
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return []
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass


def sync_student_module_chat_rooms(student_id, removed_codes, added_codes):
    """Drop the student from chat rooms for ``removed_codes`` and ensure+join
    rooms for ``added_codes`` (creating any room that doesn't exist yet).

    Used when a student's enrolment changes (e.g. a course change). Returns
    ``(removed_pairs, added_pairs)`` — each a list of ``(module_code,
    module_name)`` — so the caller can report/email the change. Best-effort:
    logs problems and returns what it can, never raises.
    """
    removed_codes = list(removed_codes or [])
    added_codes = list(added_codes or [])
    if not removed_codes and not added_codes:
        return [], []

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (student_id,))
        row = cursor.fetchone()
        if not row:
            logger.warning("module-chat: no user row for student %s", student_id)
            return [], []
        user_id = row[0]
        created_by = _admin_user_id(cursor) or user_id
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        removed_pairs: list[tuple[str, str]] = []
        for code in removed_codes:
            cursor.execute(
                "SELECT id, description FROM chat_rooms "
                "WHERE name = ? AND is_active = 1",
                (code,),
            )
            r = cursor.fetchone()
            if not r:
                continue
            cursor.execute(
                "DELETE FROM chat_room_members WHERE room_id = ? AND user_id = ?",
                (r[0], user_id),
            )
            if cursor.rowcount > 0:
                removed_pairs.append((code, r[1] or _module_info(cursor, code)[0]))

        added_pairs: list[tuple[str, str]] = []
        for code in added_codes:
            try:
                room_id, name = _ensure_room(cursor, code, created_by, now)
                _join(cursor, room_id, user_id, now)
                added_pairs.append((code, name))
            except sqlite3.Error as exc:
                logger.warning("module-chat: sync failed for module %s: %s", code, exc)
        conn.commit()
        return removed_pairs, added_pairs
    except sqlite3.Error as exc:
        logger.warning("module-chat: sync failed for %s: %s", student_id, exc)
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return [], []
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass


def purge_user_chat_on_cursor(cursor, user_id, *, delete_messages=True):
    """Remove ``user_id`` from every chat room using the given cursor.

    Always deletes the user's ``chat_room_members`` rows. When
    ``delete_messages`` is true (a hard delete) it also deletes the messages
    they sent and any invitations to/from them. The caller owns the
    transaction and must commit. Returns ``(memberships, messages)`` counts.
    """
    if not user_id:
        return 0, 0
    cursor.execute("DELETE FROM chat_room_members WHERE user_id = ?", (user_id,))
    members = cursor.rowcount
    messages = 0
    if delete_messages:
        cursor.execute("DELETE FROM chat_messages WHERE sender_id = ?", (user_id,))
        messages = cursor.rowcount
        try:
            cursor.execute(
                "DELETE FROM chat_room_invitations "
                "WHERE user_id = ? OR invited_by = ?",
                (user_id, user_id),
            )
        except sqlite3.OperationalError:
            pass  # invitations table may not exist on minimal installs
    return members, messages


def purge_student_from_chat(student_id, *, delete_messages=True):
    """Resolve a student's user id (via ``users.username``) and purge their
    chat membership on a fresh connection. Best-effort; never raises. Returns
    ``(memberships, messages)`` counts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (student_id,))
        row = cursor.fetchone()
        if not row:
            return 0, 0
        result = purge_user_chat_on_cursor(
            cursor, row[0], delete_messages=delete_messages)
        conn.commit()
        return result
    except sqlite3.Error as exc:
        logger.warning("module-chat: purge failed for %s: %s", student_id, exc)
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        return 0, 0
    finally:
        try:
            conn.close()
        except sqlite3.Error:
            pass
