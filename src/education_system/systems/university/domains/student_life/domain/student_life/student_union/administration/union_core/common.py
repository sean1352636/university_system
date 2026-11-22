"""Shared helpers for the Student Union CLI parts: the signed-in student lookup, club e-mail, auth fallbacks.

Split out of ``student_union_core.py``, which re-exports every name here;
callers keep importing from ``student_union_core``.
"""

import logging

from education_system.systems.university.infrastructure.database.db import get_connection

# Same logger name as before the split, so log routing is unchanged.
logger = logging.getLogger("education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core")

# Auth helpers, with the same fallback as student_union_core.
try:
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None



def _club_current_student(conn=None):
    """(student_id, name, email) for the signed-in user, or (None, None, None).

    Resolved from the authenticated session rather than typed in.
    """
    user = None
    try:
        user = get_current_user()
    except Exception:
        user = None
    if not user:
        return None, None, None

    owns_conn = conn is None
    try:
        if owns_conn:
            conn = get_connection()
        row = conn.execute(
            "SELECT student_id FROM users WHERE id = ? OR username = ? LIMIT 1",
            (user.get('id'), user.get('username'))).fetchone()
        student_id = row[0] if row and row[0] else None
        if not student_id:
            return None, None, None

        detail = conn.execute(
            "SELECT first_name, last_name, email_address FROM students"
            " WHERE student_id = ? LIMIT 1", (student_id,)).fetchone()
        if detail:
            name = f"{detail[0] or ''} {detail[1] or ''}".strip() or student_id
            return student_id, name, detail[2]
        return student_id, user.get('username', student_id), user.get('email')
    except Exception as exc:
        print(f"Could not resolve your student record: {exc}")
        return None, None, None
    finally:
        if owns_conn and conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)


def _send_club_email(template_name, recipient_email, template_vars):
    """Render a club template and hand it to the university email system."""
    address = (recipient_email or '').strip()
    if not address:
        return False
    try:
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email as _send,
        )
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
    except ImportError:
        return False
    try:
        subject, body = render_template(template_name, template_vars)
        if subject is None or body is None:
            return False
        _send(recipient_email=address, subject=subject, body=body)
        return True
    except Exception:
        return False
