"""Who is the signed-in student, in the student-records id space.

The session user carries an auth.db id, which is not the ``students`` key
(admin is 19 there and 1 here). Resolve by username through the university
``users`` table instead, and only ever for a student: a staff account has no
"own" attendance, claims or permits, so self-service screens get ``None`` and
show an honest "this is for students" message.

Functions take an open connection and only read.
"""

from __future__ import annotations

from dataclasses import dataclass


class SelfServiceError(ValueError):
    """A self-service rule refused the action; the message is safe to show."""


@dataclass(frozen=True)
class Student:
    """The signed-in student: their student number and university user row."""

    student_id: str
    username: str
    user_pk: int | None = None


def _user_dict(user) -> dict:
    if not user:
        return {}
    if isinstance(user, dict):
        return user
    return dict(getattr(user, "__dict__", {}) or {})


def session_user(auth) -> dict:
    """The current user dict from an auth object (or ``{}``)."""
    return _user_dict(getattr(auth, "current_user", None))


def _student_exists(conn, student_id) -> bool:
    if not student_id:
        return False
    row = conn.execute("SELECT 1 FROM students WHERE student_id = ? LIMIT 1",
                       (str(student_id),)).fetchone()
    return row is not None


def _users_row(conn, username):
    try:
        return conn.execute(
            "SELECT id, student_id FROM users WHERE username = ? LIMIT 1",
            (username,)).fetchone()
    except Exception:  # no users table in this database
        return None


def resolve_student(conn, user) -> Student | None:
    """The :class:`Student` behind *user*, or ``None`` when the account is not
    a student or names no ``students`` row.

    Preference: the ``users`` row matched by username, then the session's own
    ``student_id``, then the username itself (seeded student logins use their
    student number). Each candidate must name a real ``students`` row.
    """
    user = _user_dict(user)
    if str(user.get("role") or "").lower() != "student":
        return None
    username = str(user.get("username") or "").strip()
    row = _users_row(conn, username) if username else None
    user_pk = int(row[0]) if row and row[0] is not None else None
    candidates = [row[1] if row else None, user.get("student_id"), username]
    for candidate in candidates:
        if candidate and _student_exists(conn, candidate):
            return Student(student_id=str(candidate), username=username, user_pk=user_pk)
    return None


def require_student(conn, user) -> Student:
    """:func:`resolve_student`, raising :class:`SelfServiceError` when absent."""
    student = resolve_student(conn, user)
    if student is None:
        raise SelfServiceError(
            "This page shows a student's own records. Your account is not linked "
            "to a student record.")
    return student


#: Tables the self-service pages may probe for; anything else is refused so
#: the name spliced into the PRAGMA below is always one of these literals.
_PROBED_TABLES = frozenset({
    "parking_permits", "vehicles", "parking_violations",
    "placement_profiles", "placement_hours_log", "visa_records",
})


def table_columns(conn, table: str) -> set[str]:
    """Column names of *table*, empty when it does not exist."""
    if table not in _PROBED_TABLES:
        raise ValueError(f"unexpected table {table!r}")
    # db-audit: ignore[DBW001] - table is one of the _PROBED_TABLES literals
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}  # nosec B608
