"""Who may use the e-mail administration screens, for the CLI and GUI menus.

The rules are ``application/mail/outbox.holds`` (bulk_sender /
email_admin roles; administrators hold both) and
``application/mail/admin.can_send_bulk``. These helpers read the logged-in
user from an ``auth`` object and open a short connection.
"""

from __future__ import annotations


def current(auth) -> tuple[str | None, str]:
    user = getattr(auth, "current_user", None) or {}
    return user.get("username"), str(user.get("role") or "")


def _with_conn(fn):
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection(None, row_factory=False)
    try:
        result = fn(conn)
        conn.commit()
        return result
    finally:
        conn.close()


def is_email_admin(auth) -> bool:
    """E-mail settings, templates, scheduling, the outbox and suppressions."""
    from education_system.systems.university.application.mail import outbox as email_outbox
    username, role = current(auth)
    if not username:
        return False
    return _with_conn(lambda conn: email_outbox.holds(conn, username, "email_admin", role))


def can_send_bulk(auth, audience="addresses") -> bool:
    from education_system.systems.university.application.mail import admin as email_admin
    username, role = current(auth)
    if not username:
        return False
    return _with_conn(lambda conn: email_admin.can_send_bulk(conn, username, role, audience))


DENIED = "You need the e-mail administrator role for this (ask an administrator)."
DENIED_BULK = "You need the bulk sender role to send bulk e-mail (ask an administrator)."
