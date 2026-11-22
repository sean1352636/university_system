"""Who a Student Union row belongs to.

Union rows (`club_members`, `equipment_checkouts`, public events,
`community_feedback`, `social_impact_projects`, …) are keyed by the
*student* id, read out of ``users.student_id``. Staff and admin accounts
have no student record, so that column is NULL for them — and every
screen took the NULL at face value: it wrote rows owned by NULL, then
looked them back up with ``WHERE owner = NULL``, which matches nothing in
SQL. The account could create a project, a booking or a checkout and be
told seconds later that it had none.

``current_student_id`` gives those accounts a stable id of their own —
``user:<username>`` — so writes and reads agree. Screens that join the
``students`` table still show nothing for such an account, because there
genuinely is no student record behind it; that is a display gap, not
data loss.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

FALLBACK_PREFIX = "user:"


def fallback_id(username: str | None) -> str | None:
    """The owner id used for an account with no student record."""
    username = (username or "").strip()
    return f"{FALLBACK_PREFIX}{username}" if username else None


def is_fallback(student_id: str | None) -> bool:
    """True if ``student_id`` is a stand-in rather than a real student id."""
    return bool(student_id) and str(student_id).startswith(FALLBACK_PREFIX)


def current_student_id(cursor, auth=None) -> str | None:
    """Return the id Student Union rows should be owned by for this user.

    Prefers the real ``users.student_id``; falls back to
    ``user:<username>`` when the account has no student record. Returns
    ``None`` only when nobody is signed in.
    """
    user = getattr(auth, "current_user", None) if auth is not None else None
    if not user:
        return None

    username = user.get("username")
    try:
        cursor.execute(
            "SELECT student_id, username FROM users WHERE id = ?",
            (user.get("id"),),
        )
        row = cursor.fetchone()
        if row:
            if row[0]:
                return str(row[0])
            if len(row) > 1 and row[1]:
                username = row[1]
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("current_student_id lookup failed: %s", exc)

    return fallback_id(username)


def contact_email(cursor, student_id: str | None) -> str | None:
    """Return the address to write to for an owner id.

    Handles both real student ids and the ``user:<username>`` stand-in,
    checking ``users`` first (every account has one) and falling back to
    the student record's own address.
    """
    if not student_id:
        return None

    queries = []
    if is_fallback(student_id):
        queries.append(("SELECT email FROM users WHERE username = ?",
                        student_id[len(FALLBACK_PREFIX):]))
    else:
        queries.append(("SELECT email FROM users WHERE student_id = ?", student_id))
        queries.append(("SELECT email_address FROM students WHERE student_id = ?",
                        student_id))

    for sql, param in queries:
        try:
            cursor.execute(sql, (param,))
            row = cursor.fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("contact_email lookup failed: %s", exc)
    return None


def admin_recipients(cursor, roles=("admin", "superadmin")) -> list[tuple[str, str]]:
    """Return ``(username, email)`` for the accounts reports should go to.

    Used by the Student Union report screens so a report reaches the
    actual administrators rather than a hardcoded address.
    """
    out: list[tuple[str, str]] = []
    try:
        placeholders = ", ".join("?" for _ in roles)
        # db-audit: ignore[DBW001] - string literal
        cursor.execute(
            f"SELECT username, email FROM users "
            f"WHERE LOWER(role) IN ({placeholders}) AND email IS NOT NULL "
            f"ORDER BY username",
            tuple(r.lower() for r in roles),
        )
        out = [(str(r[0]), str(r[1])) for r in cursor.fetchall() if r[1]]
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("admin_recipients lookup failed: %s", exc)
    return out


__all__ = [
    "current_student_id", "fallback_id", "is_fallback", "FALLBACK_PREFIX",
    "contact_email", "admin_recipients",
]
