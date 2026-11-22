"""Console menu for the Complaints Portal and its OIA procedure.

The same ``complaints`` table and procedure (``application.complaints
.procedure``) as the Complaints Portal window. Everyone can submit a complaint
and see / escalate / accept / withdraw their own; staff see the register and
run the stages (assign, advance, outcome, close, Completion of Procedures
letter, history, statistics, deadline reminders).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from education_system.systems.university.application.complaints import procedure
from education_system.systems.university.infrastructure.i18n import get_text

auth: Any = None
_PREFIX = "cli.operations.complaints"
CATEGORIES = ("Academic", "Facilities", "Hostel/Accommodation", "Library", "IT Services",
              "Food Services", "Transportation", "Harassment/Discrimination", "Financial/Fees",
              "Other")
PRIORITIES = ("Low", "Medium", "High", "Urgent")


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _t(key: str, default: str) -> str:
    return get_text(f"{_PREFIX}.{key}", default=default)


def _user() -> dict:
    return dict(getattr(auth, "current_user", None) or {})


def _actor() -> procedure.Actor:
    return procedure.actor_from_user(_user())


def _ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _run(action, done: str) -> Any:
    try:
        result = procedure.run(action)
    except (ValueError, PermissionError) as exc:
        print(f"Error: {exc}")
        return None
    print(done)
    if isinstance(result, dict) and result.get("letter"):
        print(f"Completion of Procedures letter: {result['letter']}")
    return result


def _print_rows(rows: list[dict]) -> None:
    if not rows:
        print(_t("none", "No complaints."))
        return
    print(f"\n{'ID':<10} {'Status':<12} {'Stage':<31} {'Due':<11} {'Handler':<12} Subject")
    print("-" * 110)
    for c in rows:
        due = c.get("escalation_due") if c.get("can_escalate") else c.get("stage_due")
        flag = "!" if c.get("overdue") else " "
        print(f"{c['id']:<10} {c['status']:<12} {c['stage_label'][:30]:<31} "
              f"{(due or '-')[:10]:<10}{flag} {(c.get('assigned_to') or '-')[:12]:<12} "
              f"{c['subject'][:40]}")
    print(f"\n{_t('total', 'Total')}: {len(rows)}")


def _show(cid: str) -> None:
    rows = procedure.read(lambda conn: [procedure.get(conn, cid)])
    if not rows:
        print("The complaints database is not available.")
        return
    c = rows[0]
    print(f"\n{c['id']}  {c['subject']}  ({c['category']}, {c['priority']})")
    print(f"From {c['name']} ({c['user_id']}) {c['email']}  submitted {c['submitted']}")
    print(f"Status: {c['status']}\n\n{c['description']}")
    print(procedure.procedure_text(c))
    if c.get("outcome_summary"):
        print(f"Outcome summary: {c['outcome_summary']}")


# --- everyone -------------------------------------------------------------

def _identity(user: dict) -> tuple[str, str, str]:
    """Name, student/staff id and e-mail of the signed-in account, by username."""
    username = user.get("username") or ""

    def lookup(conn):
        row = conn.execute(
            "SELECT s.student_id, TRIM(COALESCE(s.first_name, '') || ' ' || "
            "COALESCE(s.last_name, '')), COALESCE(u.email, s.email_address, '') FROM users u "
            "LEFT JOIN students s ON s.student_id = u.student_id WHERE u.username = ?",
            (username,)).fetchone()
        return tuple(row) if row else None

    try:
        row = procedure.read(lookup) if username else None
    except Exception:  # an older database without these tables
        row = None
    sid, name, email = row or ("", "", "")
    return name or username, sid or username, email or user.get("email") or ""


def _confirm(email: str, values: dict) -> None:
    """The same receipt the portal sends (``communications/complaint_received``)."""
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
        subject, body = render_template("communications/complaint_received", values)
    except Exception:
        return
    if subject and body:
        procedure.send_emails([(email, subject, body, None)], created_by="complaints")


def _submit() -> None:
    user = _user()
    name, sid, email = _identity(user)
    name = _ask("Full name", name)
    sid = _ask("Student/staff ID", sid)
    email = _ask("E-mail", email)
    print("Categories: " + ", ".join(f"{i}. {c}" for i, c in enumerate(CATEGORIES, 1)))
    category = CATEGORIES[int(_ask("Category number", "1")) - 1]
    priority = _ask("Priority (" + "/".join(PRIORITIES) + ")", "Medium").title()
    subject, description = _ask("Subject"), _ask("Description")
    if not all((name, sid, email, subject, description)) or "@" not in email:
        print("Every field is required, with a valid e-mail address.")
        return
    if priority not in PRIORITIES:
        priority = "Medium"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    complaint = {"id": str(uuid.uuid4())[:8].upper(), "name": name, "user_id": sid,
                 "email": email, "category": category, "priority": priority,
                 "subject": subject, "description": description, "status": "Pending",
                 "response": "", "submitted": now, "updated": now}
    by = str(user.get("id") or user.get("username") or "") or None
    if _run(lambda conn: procedure.submit(conn, complaint, submitted_by=by),
            f"Complaint submitted. Your tracking ID is {complaint['id']}.") is None:
        return
    try:
        from education_system.systems.university.services.bus.integration_bus import (
            publish_complaint_filed,
        )
        publish_complaint_filed(complaint_id=complaint["id"], user_id=sid, email=email,
                                category=category, priority=priority, subject=subject)
    except Exception:
        pass  # best effort, as in the portal
    _confirm(email, {"student_name": name, "student_id": sid, "tracking_id": complaint["id"],
                     "subject": subject, "category": category, "priority": priority,
                     "submitted_at": now})


def _mine() -> None:
    actor = _actor()
    _print_rows(procedure.read(lambda conn: procedure.own(conn, actor)) or [])


def _track() -> None:
    try:
        _show(_ask("Tracking ID").upper())
    except ValueError as exc:
        print(f"Error: {exc}")


def _escalate() -> None:
    cid, reason = _ask("Tracking ID").upper(), _ask("Why are you not satisfied with the outcome?")
    _run(lambda conn: procedure.escalate(conn, cid, _actor(), reason),
         "Your complaint has moved to the next stage.")


def _accept() -> None:
    cid = _ask("Tracking ID").upper()
    if _ask("Accept the outcome and close? You cannot escalate afterwards (y/n)", "n") == "y":
        _run(lambda conn: procedure.finalise(conn, cid, _actor(), student_accepted=True),
             "Your complaint is closed.")


def _withdraw() -> None:
    cid, reason = _ask("Tracking ID").upper(), _ask("Reason for withdrawing")
    _run(lambda conn: procedure.record_outcome(conn, cid, _actor(), "withdrawn", reason),
         "Complaint withdrawn.")


# --- staff ----------------------------------------------------------------

def _register() -> None:
    stage = _ask("Stage (" + "/".join(procedure.STAGES) + ", blank for all)") or None
    overdue = _ask("Overdue only? (y/n)", "n") == "y"
    _print_rows(procedure.read(
        lambda conn: procedure.listing(conn, stage=stage, overdue_only=overdue)) or [])


def _assign() -> None:
    cid, handler = _ask("Complaint ID").upper(), _ask("Handler (staff username)")
    _run(lambda conn: procedure.assign(conn, cid, handler, _actor()), "Assigned.")


def _advance() -> None:
    cid, reason = _ask("Complaint ID").upper(), _ask("Reason for the next stage")
    _run(lambda conn: procedure.advance(conn, cid, _actor(), reason), "Moved to the next stage.")


def _outcome() -> None:
    cid = _ask("Complaint ID").upper()
    print("Outcomes: " + ", ".join(procedure.OUTCOMES))
    outcome = _ask("Outcome")
    summary = _ask("Summary of the outcome")
    print("Issues considered, one per line; blank line to finish:")
    issues = []
    while line := input("  - ").strip():
        issues.append(line)
    _run(lambda conn: procedure.record_outcome(conn, cid, _actor(), outcome, summary, issues),
         "Outcome recorded.")


def _close() -> None:
    cid = _ask("Complaint ID").upper()
    accepted = _ask("Has the student accepted the outcome? (y/n)", "n") == "y"
    _run(lambda conn: procedure.finalise(conn, cid, _actor(), student_accepted=accepted),
         "Complaint closed.")


def _cop() -> None:
    cid = _ask("Complaint ID").upper()
    result = _run(lambda conn: procedure.issue_cop(conn, cid, _actor()), "Letter issued.")
    if result:
        print(f"Saved to {result['path']} (OIA deadline {result['oia_deadline']}).")


def _history() -> None:
    cid = _ask("Complaint ID").upper()
    events = procedure.read(lambda conn: procedure.history(conn, cid)) or []
    for e in events:
        print(f"{str(e['created_at'])[:16]}  {e['event_type']:<11} {e['stage'] or '':<17} "
              f"{e['actor'] or '-':<12} {e['detail'] or ''}")
    if not events:
        print("No events.")


def _statistics() -> None:
    frm, to = _ask("From (YYYY-MM-DD, blank for all)"), _ask("To (YYYY-MM-DD, blank for all)")
    stats = procedure.read(lambda conn: procedure.statistics(conn, frm or None,
                                                                     to or None))
    print("\n".join(procedure.statistics_lines(stats)) if stats else "Database not available.")


def _reminders() -> None:
    print(f"{procedure.run_reminders()} deadline reminder(s) sent.")


_STUDENT_ACTIONS = {
    "1": ("Submit a complaint", _submit),
    "2": ("My complaints", _mine),
    "3": ("Track a complaint", _track),
    "4": ("Request the next stage", _escalate),
    "5": ("Accept the outcome and close", _accept),
    "6": ("Withdraw a complaint", _withdraw),
}
_STAFF_ACTIONS = {
    "7": ("Complaints register", _register),
    "8": ("Assign a handler", _assign),
    "9": ("Advance to the next stage", _advance),
    "10": ("Record an outcome", _outcome),
    "11": ("Close a complaint", _close),
    "12": ("Issue Completion of Procedures letter", _cop),
    "13": ("Complaint history", _history),
    "14": ("Statistics (OIA)", _statistics),
    "15": ("Send due reminders", _reminders),
}


def display_complaints_menu() -> None:
    """Top-level complaints menu."""
    if not _user():
        print(_t("login_required", "You must be logged in to use the complaints portal."))
        return
    actions = dict(_STUDENT_ACTIONS)
    if _actor().is_staff:
        actions.update(_STAFF_ACTIONS)
    while True:
        print(f"\n{_t('title', 'Complaints Portal')}")
        print("=" * 30)
        for key, (label, _) in actions.items():
            print(f"{key}. {label}")
        print(f"0. {_t('back', 'Return to Previous Menu')}")
        choice = input(f"\n{_t('choice', 'Enter your choice')}: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print(_t("invalid", "Invalid choice."))
            continue
        try:
            action[1]()
        except KeyboardInterrupt:
            print("\nCancelled.")
        except (ValueError, IndexError) as exc:
            print(f"Error: {exc}")
