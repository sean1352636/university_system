"""The complaints procedure behind the Complaints Portal, in the OIA's stages.

The OIA's Good Practice Framework for handling complaints sets out three
stages, and every complaint in the portal's ``complaints`` table now moves
through them:

1. **Early resolution** (``early_resolution``) — handled close to where the
   problem arose, within :data:`WORKING_DAYS` (10 working days).
2. **Formal investigation** (``formal``) — 30 working days, and never later
   than 90 calendar days after the complaint was received.
3. **Review** (``review``) — of how the formal stage was handled, 20 working
   days. Its decision is final.

At stages 1 and 2 a handler records an **outcome** (upheld, partly upheld,
not upheld, resolved early, or withdrawn) with a summary and the issues
considered. The student then has :data:`ESCALATION_WORKING_DAYS` to ask for
the next stage; once that window has passed, or the student accepts the
outcome, the complaint is **finalised** (closed). A review decision closes
the complaint at once. Closing after the formal or review stage produces the
**Completion of Procedures letter** (``application.cases.completion_letter``)
— the OIA's 12-month window runs from its date; one can also be issued on
request for any other closed complaint.

The portal's old statuses stay meaningful: *Pending* (stage 1, nobody
assigned), *In Progress* (being handled), *Resolved* / *Rejected* (an outcome
has been given: not upheld is Rejected, everything else Resolved).

Deadline reminders (:func:`run_reminders`) go to the handler — or, while
nobody is assigned, the complaints administrators — once a day for each
complaint due within :data:`REMINDER_LEAD_DAYS` or overdue; it runs with the
university's daily jobs and from the portal / CLI.

Every action is written to ``complaint_events``. Working days are Monday to
Friday (bank holidays are not excluded). Functions take an open connection
and do not commit, except :func:`run_reminders`, which owns its transaction;
e-mails are returned for the caller to send after commit (:func:`send_emails`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

from education_system.systems.university.infrastructure.database.schemas import (
    complaints_procedure_schema as schema,
)

STAGES = ("early_resolution", "formal", "review", "closed")
STAGE_LABELS = {"early_resolution": "Stage 1: Early resolution",
                "formal": "Stage 2: Formal investigation",
                "review": "Stage 3: Review", "closed": "Closed"}
NEXT_STAGE = {"early_resolution": "formal", "formal": "review"}
#: Working days each stage has for a decision (OIA Good Practice Framework norms).
WORKING_DAYS = {"early_resolution": schema.EARLY_RESOLUTION_WORKING_DAYS, "formal": 30,
                "review": 20}
#: The formal stage must finish within this many calendar days of receipt.
FORMAL_CALENDAR_LIMIT = 90
#: Working days the student has to ask for the next stage after a decision.
ESCALATION_WORKING_DAYS = 10
#: Remind the handler this many days before a stage deadline.
REMINDER_LEAD_DAYS = 2
OUTCOMES = ("upheld", "partly_upheld", "not_upheld", "resolved_early", "withdrawn")
OUTCOME_LABELS = {"upheld": "Upheld", "partly_upheld": "Partly upheld",
                  "not_upheld": "Not upheld", "resolved_early": "Resolved at early resolution",
                  "withdrawn": "Withdrawn"}
_NOT_STAFF = frozenset({"", "student", "alumni", "alumnus", "parent", "guardian", "applicant"})
_ADMIN = frozenset({"admin", "administrator", "superadmin"})
#: Old portal statuses accepted by the legacy "Save Changes" path.
LEGACY_STATUSES = ("Pending", "In Progress", "Resolved", "Rejected")


@dataclass(frozen=True)
class Actor:
    """Who is acting: their username, role and every id their records may carry."""
    username: str
    role: str = ""
    ids: frozenset = field(default_factory=frozenset)

    @property
    def is_staff(self) -> bool:
        return self.role not in _NOT_STAFF

    @property
    def is_admin(self) -> bool:
        return self.role in _ADMIN


def actor_from_user(user: dict | None) -> Actor:
    user = user or {}
    ids = {str(user.get(k)) for k in ("username", "id", "user_id", "student_id") if user.get(k)}
    return Actor(str(user.get("username") or user.get("id") or "unknown"),
                 str(user.get("role") or "").lower(), frozenset(ids))


def ensure(conn) -> None:
    schema.apply_to_connection(conn)


# ── dates ───────────────────────────────────────────────────────────────


def add_working_days(start: date, days: int) -> date:
    """``start`` plus ``days`` working days (Monday to Friday)."""
    current, left = start, int(days)
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def stage_due(stage: str, started: date, received: date | None = None) -> date | None:
    if stage not in WORKING_DAYS:
        return None
    due = add_working_days(started, WORKING_DAYS[stage])
    if stage == "formal":
        due = min(due, (received or started) + timedelta(days=FORMAL_CALENDAR_LIMIT))
    return due


# ── rows ────────────────────────────────────────────────────────────────


def _dicts(cur) -> list[dict]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _has_table(conn, name) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (name,)).fetchone() is not None


def _raw(conn, cid) -> dict:
    ensure(conn)
    rows = _dicts(conn.execute("SELECT * FROM complaints WHERE id = ?", (str(cid).upper(),)))
    if not rows:
        raise ValueError(f"No complaint {cid}")
    return rows[0]


def describe(row: dict, today: date | None = None) -> dict:
    """The row plus labels, days left, whether it is overdue and can be escalated."""
    today = today or date.today()
    out = dict(row)
    due, esc = _day(row.get("stage_due")), _day(row.get("escalation_due"))
    open_stage = row.get("stage") in WORKING_DAYS and not row.get("outcome")
    out["stage_label"] = STAGE_LABELS.get(row.get("stage") or "", row.get("stage") or "—")
    out["outcome_label"] = OUTCOME_LABELS.get(row.get("outcome") or "", "")
    out["days_left"] = (due - today).days if due and open_stage else None
    out["overdue"] = bool(open_stage and due and due < today)
    out["can_escalate"] = bool(row.get("outcome") and row.get("stage") in NEXT_STAGE
                               and row.get("outcome") != "withdrawn" and esc and esc >= today)
    out["next_stage"] = NEXT_STAGE.get(row.get("stage") or "")
    return out


def get(conn, cid, today=None) -> dict:
    return describe(_raw(conn, cid), today)


def listing(conn, *, stage=None, handler=None, overdue_only=False, today=None) -> list[dict]:
    ensure(conn)
    sql, params = "SELECT * FROM complaints WHERE 1 = 1", []
    if stage:
        sql += " AND stage = ?"
        params.append(stage)
    if handler:
        sql += " AND assigned_to = ?"
        params.append(handler)
    rows = [describe(r, today) for r in _dicts(conn.execute(sql + " ORDER BY submitted DESC",
                                                            params))]
    return [r for r in rows if r["overdue"]] if overdue_only else rows


def is_owner(row: dict, actor: Actor) -> bool:
    return bool({str(row.get("user_id") or ""), str(row.get("submitted_by") or "")}
                & set(actor.ids))


def own(conn, actor: Actor, today=None) -> list[dict]:
    """The complaints this person submitted (by student/staff id or account)."""
    ensure(conn)
    ids = sorted(actor.ids) or ["\x00"]
    marks = ", ".join("?" for _ in ids)
    # db-audit: ignore[DBW001] - only placeholders are interpolated
    rows = _dicts(conn.execute(
        f"SELECT * FROM complaints WHERE user_id IN ({marks}) OR submitted_by IN ({marks}) "
        "ORDER BY submitted DESC", (*ids, *ids)))
    return [describe(r, today) for r in rows]


def history(conn, cid) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT created_at, event_type, stage, actor, detail FROM "
                               "complaint_events WHERE complaint_id = ? ORDER BY event_id",
                               (str(cid).upper(),)))


def _event(conn, cid, event_type, stage, actor, **detail) -> None:
    conn.execute("INSERT INTO complaint_events (complaint_id, event_type, stage, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (cid, event_type, stage, json.dumps(detail, default=str) if detail else None,
                  getattr(actor, "username", actor)))


def _status_for(stage, outcome, assigned) -> str:
    if outcome == "not_upheld":
        return "Rejected"
    if outcome or stage == "closed":
        return "Resolved"
    return "In Progress" if assigned or stage != "early_resolution" else "Pending"


def _update(conn, cid, **values) -> None:
    values["updated"] = date.today().isoformat() + " " + _clock()
    sets = ", ".join(f"{k} = ?" for k in values)
    # db-audit: ignore[DBW001] - keys are this module's literal column names
    conn.execute(f"UPDATE complaints SET {sets} WHERE id = ?", (*values.values(), cid))


def _clock() -> str:
    from datetime import datetime
    return datetime.now().strftime("%H:%M")


def _require_staff(actor: Actor) -> None:
    if not actor.is_staff:
        raise PermissionError("Only staff can handle complaints")


def _require_open(row) -> None:
    if row.get("stage") == "closed":
        raise ValueError(f"Complaint {row['id']} is closed")


# ── notices ─────────────────────────────────────────────────────────────


def _inbox(conn, ref, subject, body) -> None:
    if ref and _has_table(conn, "messages") and _has_table(conn, "users"):
        from education_system.systems.university.infrastructure.email.messages_inbox import (
            deliver_inbox_message_on,
        )
        deliver_inbox_message_on(conn, ref, subject, body)


def _notify_student(conn, row, subject, body, attachments=None) -> list[tuple]:
    _inbox(conn, row.get("user_id"), subject, body)
    email = row.get("email") or ""
    return [(email, subject, body, attachments)] if "@" in email else []


def _staff_email(conn, username) -> str | None:
    for table, column in (("staff", "email"), ("users", "email")):
        if _has_table(conn, table):
            # db-audit: ignore[DBW001] - table/column are literals from this function
            row = conn.execute(f"SELECT {column} FROM {table} WHERE username = ?",
                               (username,)).fetchone()
            if row and row[0] and "@" in row[0]:
                return row[0]
    return None


def _admins(conn) -> list[str]:
    if not _has_table(conn, "users"):
        return []
    return [r[0] for r in conn.execute(
        "SELECT username FROM users WHERE LOWER(COALESCE(role, '')) IN "
        "('admin', 'administrator') AND username IS NOT NULL ORDER BY username")]


def _notify_staff(conn, usernames, subject, body) -> list[tuple]:
    emails = []
    for name in dict.fromkeys(u for u in usernames if u):
        _inbox(conn, name, subject, body)
        address = _staff_email(conn, name)
        if address:
            emails.append((address, subject, body, None))
    return emails


def send_emails(emails, created_by="complaints") -> int:
    """Queue each ``(address, subject, body, attachments)`` in the university outbox."""
    from education_system.systems.university.infrastructure.email import outbox_delivery
    sent = 0
    for address, subject, body, attachments in emails:
        try:
            outbox_delivery.enqueue(address, subject, body, category="complaints",
                                    attachments=attachments, created_by=created_by)
            sent += 1
        except Exception:  # one bad address must not stop the rest
            continue
    return sent


def run(action, created_by="complaints"):
    """``action(conn)`` in one transaction on the university database, then the
    e-mails it returned are queued in the outbox. Errors propagate."""
    from education_system.systems.university.infrastructure.database.db import transaction
    with transaction() as conn:
        ensure(conn)
        result = action(conn)
    emails = result.get("emails") if isinstance(result, dict) else result
    if emails and isinstance(emails, list):
        send_emails(emails, created_by=created_by)
    return result


def read(action):
    """Read-only ``action(conn)`` (listings, history, statistics)."""
    from education_system.systems.university.infrastructure.database.db import get_connection
    conn = get_connection()
    try:
        ensure(conn)
        return action(conn)
    finally:
        conn.close()


def procedure_text(complaint: dict) -> str:
    """The stage, deadline, handler and outcome lines shown to the complainant."""
    lines = ["", "─────────────────── Complaints Procedure ───────────────────",
             f"Stage          : {complaint.get('stage_label') or '—'}"]
    if complaint.get("stage_due") and complaint.get("days_left") is not None:
        late = " (OVERDUE)" if complaint.get("overdue") else ""
        lines.append(f"Decision due   : {complaint['stage_due']}{late}")
    lines.append(f"Handled by     : {complaint.get('assigned_to') or 'not yet assigned'}")
    if complaint.get("outcome"):
        lines.append(f"Outcome        : {complaint.get('outcome_label')} "
                     f"(decided {complaint.get('decision_at') or '—'})")
    if complaint.get("can_escalate"):
        lines.append(f"You can ask for the next stage until {complaint['escalation_due']} "
                     "(Request Next Stage).")
    if complaint.get("cop_issued_at"):
        lines.append(f"Completion of Procedures letter issued {complaint['cop_issued_at']} — "
                     "you may complain to the OIA within 12 months of that date.")
    return "\n".join(lines) + "\n"


# ── the procedure ───────────────────────────────────────────────────────


def submit(conn, complaint: dict, submitted_by=None, today=None) -> dict:
    """Store a new complaint (the portal's columns) and start stage 1."""
    ensure(conn)
    cols = ("id", "name", "user_id", "email", "category", "priority", "subject",
            "description", "status", "response", "submitted", "updated")
    conn.execute("INSERT INTO complaints (" + ", ".join(cols) + ", submitted_by) VALUES ("
                 + ", ".join("?" for _ in cols) + ", ?)",
                 (*[complaint[c] for c in cols], submitted_by))
    return start(conn, complaint["id"], actor=submitted_by or "portal", today=today)


def start(conn, cid, actor="portal", today=None) -> dict:
    """Put a newly submitted complaint into stage 1 with its deadline."""
    row = _raw(conn, cid)
    today = today or date.today()
    received = _day(row.get("submitted")) or today
    due = stage_due("early_resolution", received)
    _update(conn, row["id"], stage="early_resolution", received_on=received.isoformat(),
            stage_started=received.isoformat(), stage_due=due.isoformat())
    _event(conn, row["id"], "submitted", "early_resolution", actor, due=due.isoformat(),
           category=row.get("category"))
    return get(conn, row["id"], today)


def _is_staff_username(conn, username) -> bool:
    if _has_table(conn, "staff") and conn.execute(
            "SELECT 1 FROM staff WHERE username = ?", (username,)).fetchone():
        return True
    if not _has_table(conn, "users"):
        return False
    row = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    return bool(row) and str(row[0] or "").lower() not in _NOT_STAFF


def assign(conn, cid, handler, actor: Actor) -> list[tuple]:
    """Make ``handler`` (a staff username) responsible for the complaint."""
    _require_staff(actor)
    row = _raw(conn, cid)
    _require_open(row)
    handler = (handler or "").strip()
    if not handler or not _is_staff_username(conn, handler):
        raise ValueError(f"{handler or 'Handler'} is not a member of staff")
    _update(conn, row["id"], assigned_to=handler,
            status=_status_for(row["stage"], row.get("outcome"), handler))
    _event(conn, row["id"], "assigned", row["stage"], actor, handler=handler,
           previous=row.get("assigned_to"))
    return _notify_staff(conn, [handler], f"Complaint {row['id']} assigned to you",
                         f"You are handling complaint {row['id']} ({row['subject']}), now at "
                         f"{STAGE_LABELS[row['stage']]}. Decision due {row.get('stage_due')}.")


def _move(conn, row, stage, actor, reason, today, event_type) -> list[tuple]:
    due = stage_due(stage, today, _day(row.get("received_on")))
    _update(conn, row["id"], stage=stage, stage_started=today.isoformat(),
            stage_due=due.isoformat(), outcome=None, decision_at=None, escalation_due=None,
            status=_status_for(stage, None, row.get("assigned_to")))
    _event(conn, row["id"], event_type, stage, actor, reason=reason, due=due.isoformat(),
           previous=row["stage"], previous_outcome=row.get("outcome"),
           previous_summary=row.get("outcome_summary"))
    return _notify_student(
        conn, row, f"Your complaint {row['id']} is now at {STAGE_LABELS[stage]}",
        f"Your complaint '{row['subject']}' has moved to {STAGE_LABELS[stage]}. "
        f"We aim to give you a decision by {due.isoformat()}.")


def advance(conn, cid, actor: Actor, reason, today=None) -> list[tuple]:
    """Staff move a complaint on to the next stage (e.g. too complex for stage 1)."""
    _require_staff(actor)
    row = _raw(conn, cid)
    _require_open(row)
    if row["stage"] not in NEXT_STAGE:
        raise ValueError("A review is the last stage; record its outcome instead")
    if not (reason or "").strip():
        raise ValueError("Give a reason for moving the complaint on")
    return _move(conn, row, NEXT_STAGE[row["stage"]], actor, reason.strip(),
                 today or date.today(), "advanced")


def escalate(conn, cid, actor: Actor, reason, today=None) -> list[tuple]:
    """The student asks for the next stage after a decision, within the time limit."""
    row = _raw(conn, cid)
    today = today or date.today()
    if not (is_owner(row, actor) or actor.is_staff):
        raise PermissionError("Only the complainant can escalate their complaint")
    _require_open(row)
    info = describe(row, today)
    if not row.get("outcome"):
        raise ValueError("You can ask for the next stage once this stage has a decision")
    if not info["can_escalate"]:
        raise ValueError("This complaint can no longer be escalated "
                         f"(the deadline was {row.get('escalation_due') or 'not set'})")
    if not (reason or "").strip():
        raise ValueError("Say why you are not satisfied with the outcome")
    emails = _move(conn, row, NEXT_STAGE[row["stage"]], actor, reason.strip(), today,
                   "escalated")
    if row.get("assigned_to"):
        emails += _notify_staff(conn, [row["assigned_to"]],
                                f"Complaint {row['id']} escalated",
                                f"The complainant asked for {STAGE_LABELS[NEXT_STAGE[row['stage']]]}"
                                f": {reason.strip()}")
    return emails


def _issues_text(issues) -> str:
    if isinstance(issues, str):
        items = [i.strip(" -•\t") for i in issues.splitlines()]
    else:
        items = [str(i).strip() for i in issues or []]
    return "\n".join(i for i in items if i)


def _check_outcome(row, outcome, summary) -> None:
    _require_open(row)
    if outcome not in OUTCOMES:
        raise ValueError(f"Outcome must be one of {', '.join(OUTCOMES)}")
    if outcome == "resolved_early" and row["stage"] != "early_resolution":
        raise ValueError("'Resolved early' only applies at the early resolution stage")
    if row.get("outcome") and outcome != "withdrawn":
        raise ValueError("This stage already has an outcome; escalate or finalise it")
    if not (summary or "").strip():
        raise ValueError("Write a summary of the outcome")


def record_outcome(conn, cid, actor: Actor, outcome, summary, issues="", today=None,
                   letter_dir=None) -> dict:
    """The decision at the current stage.

    Returns ``{'closed', 'letter', 'emails'}``. A review decision or a
    withdrawal closes the complaint; otherwise the student may escalate until
    ``escalation_due``.
    """
    row = _raw(conn, cid)
    today = today or date.today()
    if not (outcome == "withdrawn" and is_owner(row, actor)):
        _require_staff(actor)  # the complainant may only withdraw their own complaint
    _check_outcome(row, outcome, summary)
    due = _day(row.get("stage_due"))
    _update(conn, row["id"], outcome=outcome, outcome_summary=summary.strip(),
            issues_considered=_issues_text(issues) or row.get("issues_considered"),
            decision_at=today.isoformat(), response=summary.strip(),
            status=_status_for(row["stage"], outcome, row.get("assigned_to")))
    _event(conn, row["id"], "outcome", row["stage"], actor, outcome=outcome,
           due=row.get("stage_due"), on_time=bool(due is None or today <= due))
    if outcome == "withdrawn" or row["stage"] == "review":
        return finalise(conn, row["id"], actor, student_accepted=True, today=today,
                        letter_dir=letter_dir, _skip_checks=True)
    escalation = add_working_days(today, ESCALATION_WORKING_DAYS)
    _update(conn, row["id"], escalation_due=escalation.isoformat())
    nxt = STAGE_LABELS[NEXT_STAGE[row["stage"]]]
    emails = _notify_student(
        conn, row, f"Outcome of your complaint {row['id']}",
        f"Outcome: {OUTCOME_LABELS[outcome]}.\n\n{summary.strip()}\n\nIf you are not "
        f"satisfied you can ask for {nxt} until {escalation.isoformat()} (in the Complaints "
        "Portal, Track Complaint). After that the complaint will be closed.")
    return {"closed": False, "letter": None, "emails": emails}


def finalise(conn, cid, actor: Actor, *, student_accepted=False, today=None, letter_dir=None,
             _skip_checks=False) -> dict:
    """Close a decided complaint. After the formal or review stage the
    Completion of Procedures letter is produced."""
    row = _raw(conn, cid)
    today = today or date.today()
    if not _skip_checks:
        _check_finalise(row, actor, student_accepted, today)
    stage = row["stage"]
    _update(conn, row["id"], stage="closed", closed_stage=stage, closed_at=today.isoformat(),
            final_decision_at=row.get("decision_at") or today.isoformat(), stage_due=None,
            escalation_due=None)
    _event(conn, row["id"], "closed", stage, actor, student_accepted=bool(student_accepted))
    result = {"closed": True, "letter": None, "emails": []}
    current = _raw(conn, row["id"])
    if stage in ("formal", "review") and current.get("outcome") != "withdrawn":
        issued = issue_cop(conn, row["id"], actor, today=today, directory=letter_dir,
                           _system=True)
        result.update(letter=issued["path"], emails=issued["emails"])
    else:
        result["emails"] = _notify_student(
            conn, current, f"Your complaint {row['id']} is closed",
            f"Your complaint '{row['subject']}' is now closed "
            f"({OUTCOME_LABELS.get(current.get('outcome') or '', 'closed')}). You can ask for a "
            "Completion of Procedures letter from the complaints office.")
    return result


def _check_finalise(row, actor, student_accepted, today) -> None:
    _require_open(row)
    if not row.get("outcome"):
        raise ValueError("Record an outcome before closing the complaint")
    owner = is_owner(row, actor)
    if not (owner or actor.is_staff):
        raise PermissionError("Only staff or the complainant can close a complaint")
    window = _day(row.get("escalation_due"))
    if window and window >= today and not (student_accepted or owner):
        raise ValueError(f"The student may escalate until {window.isoformat()}; close it after "
                         "that, or once the student accepts the outcome")


def legacy_status(conn, cid, actor: Actor, status, response, today=None) -> dict | None:
    """The portal's old "Save Changes" status: Resolved / Rejected on an
    undecided stage records that stage's outcome; other statuses only change
    the label. Returns :func:`record_outcome`'s result when one was recorded."""
    row = _raw(conn, cid)
    if status not in LEGACY_STATUSES:
        raise ValueError(f"Status must be one of {', '.join(LEGACY_STATUSES)}")
    if status in ("Resolved", "Rejected") and row.get("stage") in WORKING_DAYS \
            and not row.get("outcome"):
        outcome = "not_upheld" if status == "Rejected" else (
            "resolved_early" if row["stage"] == "early_resolution" else "upheld")
        return record_outcome(conn, cid, actor, outcome, response or OUTCOME_LABELS[outcome],
                              today=today)
    _event(conn, row["id"], "status", row.get("stage"), actor, status=status)
    return None


# ── Completion of Procedures letter ─────────────────────────────────────


def issue_cop(conn, cid, actor: Actor, today=None, directory=None, _system=False) -> dict:
    """Produce the closed complaint's Completion of Procedures letter (PDF)."""
    from education_system.systems.university.application.cases import completion_letter
    if not _system:
        _require_staff(actor)
    row = _raw(conn, cid)
    today = today or date.today()
    if row.get("stage") != "closed":
        raise ValueError("A Completion of Procedures letter is issued once the complaint is closed")
    outcome = OUTCOME_LABELS.get(row.get("outcome") or "", "Closed")
    letter = completion_letter.build(
        student_name=row["name"], student_id=row.get("user_id") or "",
        case_ref=f"COMPLAINT-{row['id']}", case_kind="complaint",
        summary=f"{row['subject']} ({row['category']}): {row['description']}"[:1500],
        issues=row.get("issues_considered") or row["subject"],
        outcome=f"{outcome}. {row.get('outcome_summary') or row.get('response') or ''}".strip(),
        final_decision_date=row.get("final_decision_at") or row.get("closed_at") or today,
        issued_on=today, issued_by=getattr(actor, "username", str(actor)))
    path = completion_letter.save_pdf(letter, directory)
    _update(conn, row["id"], cop_issued_at=today.isoformat(), cop_path=str(path))
    _event(conn, row["id"], "cop_issued", "closed", actor, path=str(path),
           oia_deadline=letter["oia_deadline"].isoformat())
    emails = _notify_student(
        conn, row, f"Completion of Procedures letter — complaint {row['id']}",
        completion_letter.render_text(letter), attachments=[str(path)])
    return {"path": str(path), "oia_deadline": letter["oia_deadline"].isoformat(),
            "emails": emails}


# ── reminders ───────────────────────────────────────────────────────────


def due_reminders(conn, today=None, lead_days=REMINDER_LEAD_DAYS) -> list[dict]:
    """Open stages due within ``lead_days`` or overdue, not yet reminded today."""
    today = today or date.today()
    out = []
    for row in listing(conn, today=today):
        if row["days_left"] is None or row["days_left"] > lead_days:
            continue
        if row.get("last_reminder_on") == today.isoformat():
            continue
        out.append(row)
    return out


def remind(conn, today=None) -> list[tuple]:
    """Send today's reminders (inbox now, e-mails returned); marks each complaint."""
    today = today or date.today()
    emails: list[tuple] = []
    for row in due_reminders(conn, today):
        late = row["overdue"]
        subject = (f"Complaint {row['id']} is overdue" if late
                   else f"Complaint {row['id']} is due {row['stage_due']}")
        body = (f"{row['stage_label']} for complaint {row['id']} ({row['subject']}) "
                f"{'was' if late else 'is'} due {row['stage_due']}. "
                + ("" if row.get("assigned_to") else "Nobody is assigned to it yet."))
        recipients = [row["assigned_to"]] if row.get("assigned_to") else _admins(conn)
        emails += _notify_staff(conn, recipients, subject, body)
        _update(conn, row["id"], last_reminder_on=today.isoformat())
        _event(conn, row["id"], "reminder", row["stage"], "system",
               to=recipients, overdue=late)
    return emails


def run_reminders(today=None) -> int:
    """Daily job: send every due reminder once. Returns how many complaints."""
    from education_system.systems.university.infrastructure.database.db import transaction
    with transaction() as conn:
        ensure(conn)
        count = len(due_reminders(conn, today))
        emails = remind(conn, today)
    send_emails(emails, created_by="complaint-reminders")
    return count


# ── statistics ──────────────────────────────────────────────────────────


def _period(date_from, date_to) -> tuple[str, str]:
    return (str(date_from or "0000-01-01")[:10], str(date_to or "9999-12-31")[:10])


def _count_by(rows, key) -> dict:
    out: dict = {}
    for row in rows:
        name = row.get(key) or "not recorded"
        out[name] = out.get(name, 0) + 1
    return dict(sorted(out.items()))


def _escalations(conn, ids) -> dict:
    out = {"formal": 0, "review": 0}
    for cid, stage in conn.execute("SELECT complaint_id, stage FROM complaint_events WHERE "
                                   "event_type IN ('escalated', 'advanced')"):
        if cid in ids and stage in out:
            out[stage] += 1
    return out


def statistics(conn, date_from=None, date_to=None, today=None) -> dict:
    """OIA annual-statement style figures for complaints received in the period."""
    ensure(conn)
    start_day, end_day = _period(date_from, date_to)
    rows = [describe(r, today) for r in _dicts(conn.execute(
        "SELECT * FROM complaints WHERE COALESCE(received_on, substr(submitted, 1, 10)) "
        "BETWEEN ? AND ?", (start_day, end_day)))]
    ids = {r["id"] for r in rows}
    closed = [r for r in rows if r.get("stage") == "closed"]
    spans = [(_day(r["closed_at"]) - _day(r["received_on"])).days for r in closed
             if _day(r.get("closed_at")) and _day(r.get("received_on"))]
    on_time, decided = _timeliness_for(conn, ids)
    return {
        "period": (start_day, end_day), "received": len(rows), "open": len(rows) - len(closed),
        "closed": len(closed), "overdue_now": sum(1 for r in rows if r["overdue"]),
        "by_stage": _count_by(rows, "stage"), "by_category": _count_by(rows, "category"),
        "outcomes": _count_by(closed, "outcome"), "closed_at_stage": _count_by(closed,
                                                                             "closed_stage"),
        "escalations": _escalations(conn, ids),
        "decisions": decided, "decisions_on_time": on_time,
        "percent_on_time": round(100.0 * on_time / decided, 1) if decided else None,
        "average_days_to_close": round(sum(spans) / len(spans), 1) if spans else None,
        "cop_letters": sum(1 for r in rows if r.get("cop_issued_at")),
    }


def _timeliness_for(conn, ids) -> tuple[int, int]:
    on_time = total = 0
    for cid, detail in conn.execute("SELECT complaint_id, detail FROM complaint_events "
                                    "WHERE event_type = 'outcome'"):
        if cid not in ids:
            continue
        total += 1
        on_time += 1 if json.loads(detail or "{}").get("on_time") else 0
    return on_time, total


def statistics_lines(stats: dict) -> list[str]:
    """The figures as readable lines (GUI and CLI share them)."""
    def block(title, mapping, labels=None):
        lines = [title]
        lines += [f"  {(labels or {}).get(k, k)}: {v}" for k, v in mapping.items()] or ["  none"]
        return lines

    pct = stats["percent_on_time"]
    avg = stats["average_days_to_close"]
    lines = [f"Complaints received {stats['period'][0]} to {stats['period'][1]}: "
             f"{stats['received']}",
             f"Open: {stats['open']}   Closed: {stats['closed']}   "
             f"Overdue now: {stats['overdue_now']}",
             f"Decisions within the stage deadline: {stats['decisions_on_time']} of "
             f"{stats['decisions']}" + (f" ({pct}%)" if pct is not None else ""),
             f"Average days from receipt to closure: {avg if avg is not None else '—'}",
             f"Escalated to formal: {stats['escalations']['formal']}   "
             f"to review: {stats['escalations']['review']}",
             f"Completion of Procedures letters issued: {stats['cop_letters']}", ""]
    lines += block("Current stage:", stats["by_stage"], STAGE_LABELS) + [""]
    lines += block("Closed at stage:", stats["closed_at_stage"], STAGE_LABELS) + [""]
    lines += block("Outcomes (closed):", stats["outcomes"], OUTCOME_LABELS) + [""]
    lines += block("By category:", stats["by_category"])
    return lines


__all__ = [
    "Actor", "ESCALATION_WORKING_DAYS", "FORMAL_CALENDAR_LIMIT", "OUTCOMES", "OUTCOME_LABELS",
    "STAGES", "STAGE_LABELS", "WORKING_DAYS", "actor_from_user", "add_working_days", "advance",
    "assign", "describe", "due_reminders", "ensure", "escalate", "finalise", "get", "history",
    "issue_cop", "legacy_status", "listing", "own", "procedure_text", "read", "record_outcome",
    "remind", "run", "run_reminders", "send_emails", "start", "statistics", "statistics_lines",
    "submit",
]
