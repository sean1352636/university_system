"""Extracted function implementation."""

from .. import election_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def _send_candidate_email(db, template_name, template_vars, student_id):
    """Render a student_union/* template and queue it for one student.

    Looks up the student's email_address from the central ``students``
    table, renders the template via shared template_utils, queues via
    shared.utils.email_service.queue_email. Silently no-ops on missing
    email/template/infra so the caller's primary action is never
    blocked. Returns True on a successful queue.
    """
    email, name = _student_contact(db, student_id)
    if not email:
        return False
    full_vars = {
        'student_name': name,
        'student_id': str(student_id),
        **(template_vars or {}),
    }
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (  # noqa: E501
            render_template,
        )
        subject, body = render_template(
            f'student_union/{template_name}', full_vars)
        if not (subject and body):
            return False
    except Exception:
        return False
    try:
        from education_system.systems.university.infrastructure.utils.email_service import (  # noqa: E501
            queue_email,
        )
        return bool(queue_email(email, subject, body))
    except Exception:
        return False
