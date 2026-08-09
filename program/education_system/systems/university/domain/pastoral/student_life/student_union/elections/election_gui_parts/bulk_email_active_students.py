"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _bulk_email_active_students(db, template_name, template_vars):
    """Render ``student_union/<template_name>`` once per active student
    and queue it. Used for whole-cohort notifications such as the
    voting-closed broadcast.

    Returns the count of successfully queued emails.
    """
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (  # noqa: E501
            render_template,
        )
        from education_system.systems.university.infrastructure.utils.email_service import (  # noqa: E501
            queue_email,
        )
    except Exception:
        return 0

    try:
        conn = db.connect()
        # Prefer users.email over students.email_address so each row
        # routes through the inbox lookup successfully (see comment
        # on _student_contact for why).
        rows = conn.execute(
            "SELECT s.student_id, "
            "       COALESCE(u.email, s.email_address, ''), "
            "       COALESCE(NULLIF(TRIM(s.first_name||' '||s.last_name),''), "
            "                s.student_id) "
            "FROM students s "
            "LEFT JOIN users u ON u.student_id = s.student_id "
            "WHERE LOWER(COALESCE(s.status,'active')) = 'active' "
            "  AND COALESCE(u.email, s.email_address, '') <> ''").fetchall()
        conn.close()
    except sqlite3.Error:
        return 0

    sent = 0
    for sid, email, name in rows:
        full_vars = {
            'student_name': name,
            'student_id': str(sid),
            **(template_vars or {}),
        }
        try:
            subject, body = render_template(
                f'student_union/{template_name}', full_vars)
            if not (subject and body):
                continue
            if queue_email(email, subject, body):
                sent += 1
        except Exception:
            continue
    return sent
