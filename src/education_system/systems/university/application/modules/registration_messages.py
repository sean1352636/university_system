"""Messages to a student when their module enrolment changes, sent after
the change is committed: the enrolment confirmation
(``student_life/student_lifecycle/enrolment_confirmation``) from
``module_registration.side_effects``, and the drop / withdrawal
acknowledgement (``withdrawal_acknowledgement``) from :func:`after_drop`.
Each goes to the student's inbox and, when they have an address, by e-mail.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.modules.registration import (
    _dicts, _has, _module_rows, academic_year,
)


TEMPLATES = {"enrolled": "student_life/student_lifecycle/enrolment_confirmation",
             "left": "student_life/student_lifecycle/withdrawal_acknowledgement"}


def _contact(conn, student_id) -> dict:
    rows = _dicts(conn.execute(
        "SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name, "
        "email_address FROM students WHERE student_id = ?", (str(student_id),)))
    row = rows[0] if rows else {"name": str(student_id), "email_address": None}
    row["mode"] = None
    if _has(conn, "student_registrations"):
        found = conn.execute("SELECT mode_of_study FROM student_registrations WHERE student_id = ? "
                             "ORDER BY rowid DESC LIMIT 1", (str(student_id),)).fetchone() \
            if "mode_of_study" in {c[1] for c in conn.execute(
                "PRAGMA table_info(student_registrations)")} else None
        row["mode"] = found[0] if found else None
    return row


def _first_session(conn, code) -> str:
    try:
        from education_system.systems.university.application.teaching import (
            occurrences as timetable_occurrences,
        )
        today = date.today()
        dates = sorted(str(o.get("date") or o.get("session_date") or "")[:10]
                       for o in timetable_occurrences.for_module(
                           conn, code, today, today.replace(year=today.year + 1)))
        dates = [d for d in dates if d]
        if dates:
            return dates[0]
    except Exception:
        pass
    return "shown on your timetable"


def _drop_deadline(conn) -> str:
    try:
        from education_system.systems.university.services.bus import registration_calendar as cal
        verdict = cal.classify_drop(conn=conn)
        period = verdict.get("period") or {}
        return period.get("drop_deadline") or "set by the Registry"
    except Exception:
        return "set by the Registry"


def _render(name, values):
    from education_system.systems.university.infrastructure.email.template_utils import (
        render_template,
    )
    subject, body = render_template(TEMPLATES[name], values)
    if not subject or not body:
        raise ValueError(f"E-mail template {TEMPLATES[name]} is missing")
    return subject, body


def enrolment_message(conn, student_id, code) -> tuple[str, str, str | None]:
    """``(subject, body, e-mail address)`` confirming an enrolment."""
    who = _contact(conn, student_id)
    module = _module_rows(conn, [code]).get(code) or {"module_name": code, "credits": None}
    semester = conn.execute("SELECT semester FROM modules WHERE module_code = ?",
                            (code,)).fetchone()
    subject, body = _render("enrolled", {
        "student_name": who["name"] or student_id, "student_id": student_id,
        "module_code": code, "module_name": module["module_name"] or code,
        "credits": module["credits"] or "not recorded", "academic_year": academic_year(),
        "semester": (semester[0] if semester and semester[0] else "see your timetable"),
        "enrolment_date": date.today().isoformat(),
        "mode_of_study": who["mode"] or "as registered",
        "first_session_date": _first_session(conn, code),
        "drop_deadline": _drop_deadline(conn)})
    return subject, body, who["email_address"]


def leaving_message(conn, student_id, code, status, reason=None,
                    actor=None) -> tuple[str, str, str | None]:
    """``(subject, body, e-mail address)`` acknowledging a drop or withdrawal."""
    who = _contact(conn, student_id)
    module = _module_rows(conn, [code]).get(code) or {"module_name": code}
    on_transcript = str(status).lower() == "withdrawn"
    subject, body = _render("left", {
        "student_name": who["name"] or student_id, "student_id": student_id,
        "module_code": code, "module_name": module["module_name"] or code,
        "withdrawal_date": date.today().isoformat(),
        "withdrawal_reason": (reason or "").strip() or "not given",
        "recorded_by": "you" if not actor or actor == student_id else actor,
        "transcript_status": ("Withdrawn (shown on your transcript)" if on_transcript else
                              "Dropped before the deadline (not shown on your transcript)")})
    return subject, body, who["email_address"]


def _deliver(student_id, build, db_path=None) -> bool:
    """Build the message on a fresh connection, put it in the student's
    inbox, commit, then e-mail it. ``False`` when it could not be sent."""
    from contextlib import closing

    from education_system.systems.university.infrastructure.database.db import get_connection
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    try:
        with closing(get_connection(db_path, row_factory=False)) as conn:
            subject, body, address = build(conn)
            deliver_inbox_message_on(conn, str(student_id), subject, body)
            conn.commit()
    except Exception:
        return False
    if not address:
        return True
    try:
        from education_system.systems.university.infrastructure.email import send_email
        send_email(recipient_email=address, subject=subject, body=body)
        return True
    except Exception:
        return False


def notify_enrolled(student_id, module_code, db_path=None) -> bool:
    """After an enrolment is committed: the enrolment confirmation."""
    return _deliver(student_id, lambda conn: enrolment_message(conn, student_id, module_code),
                    db_path)


def after_drop(student_id, module_code, status, reason=None, actor=None,
               db_path=None) -> bool:
    """After a drop / withdrawal is committed: the acknowledgement."""
    return _deliver(student_id, lambda conn: leaving_message(conn, student_id, module_code,
                                                             status, reason, actor), db_path)
