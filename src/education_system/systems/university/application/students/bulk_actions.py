"""Bulk actions on the students a search found. Every write goes through the
same rules as a single change - ``student_lifecycle_service`` (details with
a reason and history, course transfer, withdraw, reinstate) or
``module_enrolment`` (enrol / withdraw from a module) - one student at a
time, so one refusal never undoes the others. Each run is audited.
"""

from __future__ import annotations

import secrets
from contextlib import closing

from education_system.systems.university.application.students import search
from education_system.systems.university.application.students.search import Viewer

MAX_STUDENTS = 500
#: Fields a bulk "set field" may change (personal details stay one-by-one).
SETTABLE = ("mode_of_study", "fee_status")
ACTIONS = {
    "set_field": "Set a field",
    "transfer": "Transfer to another course",
    "enrol_module": "Enrol on a module",
    "unenrol_module": "Withdraw from a module",
    "withdraw": "Withdraw from the university",
    "reinstate": "Reinstate (undo withdrawal)",
    "email": "Email their university address",
}


def _connect(db_path):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def _service(db_path, auth_db_path):
    from education_system.systems.university.application.students.lifecycle import (
        StudentLifecycleService,
    )
    return StudentLifecycleService(db_path, auth_db_path=auth_db_path)


def _check(action, viewer: Viewer, value, reason, ids):
    if action not in ACTIONS:
        raise ValueError(f"Unknown action {action!r}")
    needs = viewer.can_withdraw if action in ("withdraw", "reinstate") else viewer.can_update
    if not needs:
        raise ValueError(f"You do not have permission to {ACTIONS[action].lower()} in bulk")
    if not ids:
        raise ValueError("No students selected")
    if len(ids) > MAX_STUDENTS:
        raise ValueError(f"At most {MAX_STUDENTS} students per bulk action")
    if action != "email" and not (reason or "").strip():
        raise ValueError("Give a reason; it is recorded on each student")
    if action != "withdraw" and action != "reinstate" and not value:
        raise ValueError("Choose the value to apply")
    if action == "set_field" and value[0] not in SETTABLE:
        raise ValueError(f"Only {', '.join(SETTABLE)} can be set in bulk")


def _one(action, sid, value, reason, viewer, service, db_path):
    key = f"bulk:{action}:{sid}:{secrets.token_urlsafe(8)}"
    actor = viewer.username
    if action == "set_field":
        service.update(sid, {value[0]: value[1]}, actor_id=actor, reason=reason,
                       idempotency_key=key)
    elif action == "transfer":
        service.transfer_course(sid, value, actor_id=actor, reason=reason, idempotency_key=key)
    elif action == "withdraw":
        service.deactivate(sid, actor_id=actor, reason=reason, idempotency_key=key)
    elif action == "reinstate":
        service.restore(sid, actor_id=actor, reason=reason, idempotency_key=key)
    else:
        from education_system.systems.university.application.modules import (
            enrolment as module_enrolment,
        )
        with closing(_connect(db_path)) as conn:
            if action == "enrol_module":
                module_enrolment.enrol(conn, value, sid)
            elif not module_enrolment.withdraw(conn, value, sid):
                raise ValueError(f"not enrolled on {value}")
            conn.commit()


def _message(exc):
    errors = getattr(exc, "errors", None)
    return "; ".join(f"{k}: {v}" for k, v in errors.items()) if errors else str(exc)


def run(action, student_ids, viewer: Viewer, *, value=None, reason="", subject="",
        db_path=None, auth_db_path=None) -> dict:
    """Apply ``action`` to each student. ``value``: ``(field, new value)``
    for set_field, a course code for transfer, a module code for enrol /
    unenrol, the message body for email. Returns ``{"done", "failed":
    [(student_id, why)]}``."""
    ids = list(dict.fromkeys(str(s) for s in student_ids))
    _check(action, viewer, value, reason, ids)
    if action == "email":
        return _email(ids, subject, value, viewer, db_path)
    service = _service(db_path, auth_db_path)
    done, failed = 0, []
    for sid in ids:
        try:
            _one(action, sid, value, reason.strip(), viewer, service, db_path)
            done += 1
        except Exception as exc:
            failed.append((sid, _message(exc)))
    _audit(viewer, action, value, reason, done, failed, db_path)
    return {"done": done, "failed": failed}


def _audit(viewer, action, value, reason, done, failed, db_path):
    detail = (f"{ACTIONS[action]}: {value if action != 'email' else '(message)'}; reason: "
              f"{reason}; {done} done, {len(failed)} failed")
    with closing(_connect(db_path)) as conn:
        search.record(conn, viewer.username, "bulk", None, done, detail)
        conn.commit()


def _email(ids, subject, body, viewer, db_path):
    if not (subject or "").strip():
        raise ValueError("Give the email a subject")
    with closing(_connect(db_path)) as conn:
        marks = ", ".join("?" for _ in ids)
        rows = conn.execute(f"SELECT student_id, email_address FROM students WHERE student_id "
                            f"IN ({marks})", ids).fetchall()
    addresses = {sid: email for sid, email in rows if email and "@" in email}
    result = send_bulk_email(list(addresses.values()), subject, body)
    failed = [(sid, "no email address") for sid in ids if sid not in addresses]
    failed += [(sid, "not sent") for sid, email in addresses.items() if email in result["failed"]]
    _audit(viewer, "email", subject, "", result["sent"], failed, db_path)
    return {"done": result["sent"], "failed": failed}


def send_bulk_email(recipients, subject, message, batch_size=50):
    """Deliver one message to each address through the central email
    service; returns ``{"sent": n, "failed": [addresses]}``."""
    from education_system.systems.university.infrastructure.email.email_service import send_email
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    sent, failed = 0, []
    unique = list(dict.fromkeys(recipients))
    for start in range(0, len(unique), batch_size):
        for recipient in unique[start:start + batch_size]:
            try:
                success = send_email(recipient_email=recipient, subject=subject, body=message)
            except Exception:
                success = False
            if success:
                sent += 1
            else:
                failed.append(recipient)
    return {"sent": sent, "failed": failed}
