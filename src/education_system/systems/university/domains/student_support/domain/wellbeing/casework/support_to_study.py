"""Support to Study: the staged process for a student whose health or
wellbeing is affecting their studies (or the people around them).

* **Stage 1 — informal**: a conversation with the student, usually with
  their personal tutor or a wellbeing adviser, and an agreed action plan.
* **Stage 2 — formal**: a case meeting chaired by student support, a
  formal action plan with dates; the student may bring a supporter.
* **Stage 3 — Fitness to Study panel**: a panel decides whether the student
  can continue, with conditions, or should interrupt their studies.

A case moves one stage at a time (:func:`escalate`); it may be opened at
stage 2 or 3 only with a reason (a serious or urgent concern). Each stage
has meetings, actions and an outcome. An outcome that interrupts studies
goes through the student lifecycle (``wellbeing_bus.interrupt_studies`` →
``student_lifecycle.change_status``), never by writing the status. Letters
(meeting invitation, action plan, outcome) are PDF files
(:mod:`.letters`). A case links to the other records about the same
student: support tickets, Early Warning interventions, engagement cases,
counselling referrals, Fitness to Practise and DSA cases.

Every function takes the signed-in ``actor`` first and raises
``PermissionError`` / ``ValueError`` with a message a screen can show.
Support staff see every case; a student sees their own (with the meeting
summaries, actions, outcomes and letters — nothing is hidden from them).
"""

from __future__ import annotations

from datetime import date, datetime

from education_system.systems.university.domains.student_support.domain.wellbeing.casework import (
    access,
    letters,
    schema,
)
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.services.bus import wellbeing_bus

STAGES = {1: "Stage 1 — informal", 2: "Stage 2 — formal case meeting",
          3: "Stage 3 — Fitness to Study panel"}
OUTCOMES = {
    1: ("action_plan_agreed", "no_further_action", "escalate"),
    2: ("action_plan_agreed", "no_further_action", "escalate", "agreed_interruption"),
    3: ("continue_with_conditions", "no_further_action", "interruption_of_studies",
        "agreed_interruption"),
}
OUTCOME_LABELS = {
    "action_plan_agreed": "Action plan agreed",
    "no_further_action": "No further action — case closed",
    "escalate": "Move to the next stage",
    "agreed_interruption": "Interruption of studies agreed with the student",
    "continue_with_conditions": "Continue studying with conditions",
    "interruption_of_studies": "Interruption of studies (panel decision)",
}
INTERRUPTING = ("agreed_interruption", "interruption_of_studies")
CLOSING = ("no_further_action",) + INTERRUPTING
ACTION_STATUSES = ("open", "done", "missed", "cancelled")
MEETING_STATUSES = ("scheduled", "held", "cancelled", "postponed")
LINK_KINDS = {
    "support_ticket": ("support_tickets", "ticket_id", "Support ticket"),
    "early_warning": ("early_warning_interventions", "intervention_id",
                      "Early Warning intervention"),
    "engagement_case": ("engagement_cases", "id", "Engagement case"),
    "counselling_referral": ("counselling_referrals", "referral_id", "Counselling referral"),
    "fitness_to_practise": ("ftp_cases", "case_id", "Fitness to Practise case"),
    "dsa_case": ("dsa_cases", "case_id", "DSA case"),
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _date(value, what) -> str | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10]).isoformat()
    except ValueError:
        raise ValueError(f"{what} must be a date (YYYY-MM-DD).") from None


def _log(action, case_id, actor, **details) -> None:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    try:
        log_activity(action, "support_to_study", user=access.username(actor),
                     details={"case_id": case_id, **details})
    except Exception:
        pass


def _reading():
    conn = get_connection()
    schema.ensure_support_to_study(conn)
    return conn


def _case(conn, case_id) -> dict:
    row = conn.execute("SELECT * FROM sts_cases WHERE case_id = ?", (int(case_id),)).fetchone()
    if not row:
        raise ValueError(f"Support to Study case #{case_id} was not found.")
    return dict(row)


def _open_case(conn, case_id) -> dict:
    case = _case(conn, case_id)
    if case["status"] != "open":
        raise ValueError("That case is closed.")
    return case


def _student_label(conn, student_id) -> str:
    row = conn.execute("SELECT first_name, last_name FROM students WHERE student_id = ?",
                       (str(student_id),)).fetchone()
    if not row:
        return str(student_id)
    return f"{row[0] or ''} {row[1] or ''}".strip() or str(student_id)


def _tell(student_id, subject, body) -> None:
    wellbeing_bus.notify_inbox(student_id, subject, body)


# ------------------------------------------------------------------ cases

def open_case(actor, student_id, reason, *, stage=1, case_manager=None) -> int:
    """Open a case (one open case per student). Stage 2 or 3 needs a reason
    of at least a few sentences: entering above stage 1 is for serious or
    urgent concerns."""
    access.require_support_staff(actor)
    reason = str(reason or "").strip()
    stage = int(stage)
    if stage not in STAGES:
        raise ValueError("Choose stage 1, 2 or 3.")
    if len(reason) < 10:
        raise ValueError("Describe the concern (at least a sentence).")
    if stage > 1 and len(reason) < 60:
        raise ValueError("Opening at stage 2 or 3 needs a fuller account of why the "
                         "informal stage is being skipped.")
    me = access.username(actor)
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                            (str(student_id),)).fetchone():
            raise ValueError(f"No student {student_id}.")
        if conn.execute("SELECT 1 FROM sts_cases WHERE student_id = ? AND status = 'open'",
                        (str(student_id),)).fetchone():
            raise ValueError("This student already has an open Support to Study case.")
        case_id = conn.execute(
            "INSERT INTO sts_cases (student_id, stage, reason, case_manager, opened_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (str(student_id), stage, wellbeing_bus.seal_text(reason),
             (case_manager or me).strip(), me)).lastrowid
        conn.execute("INSERT INTO sts_stage_history (case_id, from_stage, to_stage, reason, "
                     "changed_by) VALUES (?, NULL, ?, 'Case opened', ?)", (case_id, stage, me))
    _log("create", case_id, actor, stage=stage)
    _tell(student_id, "Support to Study",
          f"Student support has opened a Support to Study case with you "
          f"({STAGES[stage]}). Its purpose is to agree the support you need to keep "
          "studying. You will be invited to a meeting, and you can see the case under "
          "Wellbeing Casework → Support to Study.")
    return int(case_id)


def list_cases(actor, *, include_closed=False, stage=None) -> list[dict]:
    """Staff: every case (open first); a student: their own."""
    scoped = access.support_scope(actor)
    clauses, params = [], []
    if scoped is not None:
        clauses.append("c.student_id = ?")
        params.append(scoped)
    if not include_closed:
        clauses.append("c.status = 'open'")
    if stage:
        clauses.append("c.stage = ?")
        params.append(int(stage))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    conn = _reading()
    try:
        rows = conn.execute(
            "SELECT c.case_id, c.student_id, c.stage, c.status, c.case_manager, c.opened_at, "
            "c.closed_at, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) "
            "AS student_name, (SELECT MIN(m.meeting_date) FROM sts_meetings m WHERE "
            "m.case_id = c.case_id AND m.status = 'scheduled' AND m.meeting_date >= date('now')) "
            "AS next_meeting, (SELECT COUNT(*) FROM sts_actions a WHERE a.case_id = c.case_id "
            "AND a.status = 'open') AS open_actions FROM sts_cases c LEFT JOIN students s "
            f"ON s.student_id = c.student_id {where} "  # nosec B608 - fixed clauses
            "ORDER BY c.status = 'open' DESC, c.stage DESC, c.opened_at", params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def case_detail(actor, case_id) -> dict:
    """The whole case: stage history, meetings, actions, outcomes, letters and
    links. Staff looks are audited (and refused if the audit fails)."""
    conn = _reading()
    try:
        case = _case(conn, case_id)
        access.require_student_access(actor, case["student_id"])
        if access.support_scope(actor) is None:
            access.record_view(actor, "support_to_study", student_id=case["student_id"],
                               record_id=case["case_id"])
        case["reason"] = wellbeing_bus.reveal(case.get("reason"))
        case["student_name"] = _student_label(conn, case["student_id"])
        case["stage_label"] = STAGES.get(case["stage"], "")

        def rows(sql):
            return [dict(r) for r in conn.execute(sql, (case["case_id"],)).fetchall()]

        case["history"] = rows("SELECT * FROM sts_stage_history WHERE case_id = ? ORDER BY id")
        case["meetings"] = rows("SELECT * FROM sts_meetings WHERE case_id = ? "
                                "ORDER BY meeting_date, meeting_time")
        for meeting in case["meetings"]:
            meeting["summary"] = wellbeing_bus.reveal(meeting.get("summary"))
        case["actions"] = rows("SELECT * FROM sts_actions WHERE case_id = ? "
                               "ORDER BY status = 'open' DESC, due_date")
        case["outcomes"] = rows("SELECT * FROM sts_outcomes WHERE case_id = ? "
                                "ORDER BY outcome_id")
        case["letters"] = rows("SELECT * FROM sts_letters WHERE case_id = ? "
                               "ORDER BY letter_id DESC")
        case["links"] = rows("SELECT * FROM sts_links WHERE case_id = ? ORDER BY link_id")
        return case
    finally:
        conn.close()


def set_case_manager(actor, case_id, username) -> None:
    access.require_support_staff(actor)
    username = str(username or "").strip()
    if not username:
        raise ValueError("Name the case manager (a username).")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        _open_case(conn, case_id)
        conn.execute("UPDATE sts_cases SET case_manager = ?, updated_at = ? WHERE case_id = ?",
                     (username, _now(), int(case_id)))
    _log("update", case_id, actor, case_manager=username)


def escalate(actor, case_id, reason) -> int:
    """Move the case to the next stage; returns the new stage."""
    access.require_support_staff(actor)
    reason = str(reason or "").strip()
    if len(reason) < 10:
        raise ValueError("Say why the case is moving to the next stage.")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        case = _open_case(conn, case_id)
        new = _escalate_on(conn, case, reason, access.username(actor))
    _log("escalate", case_id, actor, stage=new)
    _tell(case["student_id"], "Support to Study — next stage",
          f"Your Support to Study case has moved to {STAGES[new]}. You will be invited to a "
          "meeting and may bring a supporter with you.")
    return new


def _escalate_on(conn, case, reason, me) -> int:
    if case["stage"] >= 3:
        raise ValueError("The case is already at the Fitness to Study panel stage.")
    new = case["stage"] + 1
    conn.execute("UPDATE sts_cases SET stage = ?, updated_at = ? WHERE case_id = ?",
                 (new, _now(), case["case_id"]))
    conn.execute("INSERT INTO sts_stage_history (case_id, from_stage, to_stage, reason, "
                 "changed_by) VALUES (?, ?, ?, ?, ?)",
                 (case["case_id"], case["stage"], new, reason, me))
    return new


def close_case(actor, case_id, reason) -> None:
    access.require_support_staff(actor)
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Give a reason for closing the case.")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        case = _open_case(conn, case_id)
        _close_on(conn, case["case_id"], reason, access.username(actor))
    _log("close", case_id, actor)
    _tell(case["student_id"], "Support to Study case closed",
          f"Your Support to Study case has been closed: {reason}")


def _close_on(conn, case_id, reason, me) -> None:
    now = _now()
    conn.execute("UPDATE sts_cases SET status = 'closed', closed_by = ?, closed_at = ?, "
                 "closed_reason = ?, updated_at = ? WHERE case_id = ?",
                 (me, now, reason, now, case_id))
    conn.execute("UPDATE sts_actions SET status = 'cancelled' WHERE case_id = ? "
                 "AND status = 'open'", (case_id,))


# ------------------------------------------------------------------ meetings

def schedule_meeting(actor, case_id, meeting_date, *, meeting_time=None, location=None,
                     attendees=None, panel_members=None) -> int:
    """A meeting at the case's current stage. A stage 3 panel needs at least
    two panel members (comma-separated)."""
    access.require_support_staff(actor)
    when = _date(meeting_date, "The meeting date")
    if not when:
        raise ValueError("Give the meeting date.")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        case = _open_case(conn, case_id)
        panel = [p.strip() for p in str(panel_members or "").split(",") if p.strip()]
        if case["stage"] == 3 and len(panel) < 2:
            raise ValueError("A Fitness to Study panel needs at least two panel members.")
        meeting_id = conn.execute(
            "INSERT INTO sts_meetings (case_id, stage, meeting_date, meeting_time, location, "
            "attendees, panel_members, scheduled_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case["case_id"], case["stage"], when, (meeting_time or "").strip() or None,
             (location or "").strip() or None, (attendees or "").strip() or None,
             ", ".join(panel) or None, access.username(actor))).lastrowid
    _log("schedule_meeting", case_id, actor, meeting_id=meeting_id)
    _tell(case["student_id"], "Support to Study meeting",
          f"You are invited to a {STAGES[case['stage']]} meeting on {when}"
          f"{' at ' + meeting_time if meeting_time else ''}"
          f"{' (' + location + ')' if location else ''}. You may bring a supporter, such as "
          "a friend or a Students' Union adviser. Contact student support if the date does "
          "not suit you.")
    return int(meeting_id)


def record_meeting(actor, meeting_id, *, status="held", student_attended=None, summary="",
                   supporter=None) -> None:
    access.require_support_staff(actor)
    if status not in MEETING_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(MEETING_STATUSES)}.")
    if status == "held" and len(str(summary or "").strip()) < 10:
        raise ValueError("Summarise what was discussed and agreed.")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        row = conn.execute("SELECT case_id FROM sts_meetings WHERE meeting_id = ?",
                           (int(meeting_id),)).fetchone()
        if not row:
            raise ValueError(f"Meeting #{meeting_id} was not found.")
        _open_case(conn, row[0])
        conn.execute(
            "UPDATE sts_meetings SET status = ?, student_attended = ?, summary = ?, "
            "supporter = ?, recorded_by = ? WHERE meeting_id = ?",
            (status, None if student_attended is None else int(bool(student_attended)),
             wellbeing_bus.seal_text(str(summary or "").strip()) if summary else None,
             (supporter or "").strip() or None, access.username(actor), int(meeting_id)))
    _log("record_meeting", row[0], actor, meeting_id=meeting_id, status=status)


# ------------------------------------------------------------------ action plans

def add_action(actor, case_id, action_text, *, owner="student", due_date=None) -> int:
    access.require_support_staff(actor)
    text = str(action_text or "").strip()
    if len(text) < 5:
        raise ValueError("Describe the action.")
    due = _date(due_date, "The due date")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        case = _open_case(conn, case_id)
        action_id = conn.execute(
            "INSERT INTO sts_actions (case_id, stage, action_text, owner, due_date, "
            "created_by) VALUES (?, ?, ?, ?, ?, ?)",
            (case["case_id"], case["stage"], text, (owner or "student").strip(), due,
             access.username(actor))).lastrowid
    _log("add_action", case_id, actor, action_id=action_id)
    return int(action_id)


def update_action(actor, action_id, status, notes=None) -> None:
    access.require_support_staff(actor)
    if status not in ACTION_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(ACTION_STATUSES)}.")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        row = conn.execute("SELECT case_id FROM sts_actions WHERE action_id = ?",
                           (int(action_id),)).fetchone()
        if not row:
            raise ValueError(f"Action #{action_id} was not found.")
        _open_case(conn, row[0])
        conn.execute(
            "UPDATE sts_actions SET status = ?, notes = COALESCE(?, notes), completed_at = "
            "CASE WHEN ? = 'done' THEN ? ELSE completed_at END WHERE action_id = ?",
            (status, (notes or "").strip() or None, status, _now(), int(action_id)))
    _log("update_action", row[0], actor, action_id=action_id, status=status)


def overdue_actions(actor) -> list[dict]:
    """Open actions past their due date, across open cases (staff)."""
    access.require_support_staff(actor)
    conn = _reading()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT a.*, c.student_id FROM sts_actions a JOIN sts_cases c ON "
            "c.case_id = a.case_id WHERE c.status = 'open' AND a.status = 'open' AND "
            "a.due_date IS NOT NULL AND a.due_date < date('now') ORDER BY a.due_date")]
    finally:
        conn.close()


# ------------------------------------------------------------------ outcomes

def record_outcome(actor, case_id, outcome_type, decision, *, review_date=None,
                   effective_date=None, expected_return_date=None) -> int:
    """The outcome of the current stage.

    ``escalate`` moves the case on; ``no_further_action`` closes it; an
    interruption is applied through the student lifecycle first (if the
    student cannot be interrupted from their current status, nothing is
    recorded and the lifecycle's reason is raised), then the case closes."""
    access.require_support_staff(actor)
    decision = str(decision or "").strip()
    if len(decision) < 10:
        raise ValueError("Record the decision and the reasons for it.")
    review = _date(review_date, "The review date")
    returning = _date(expected_return_date, "The expected return date")
    conn = _reading()
    try:
        case = _open_case(conn, case_id)
    finally:
        conn.close()
    if outcome_type not in OUTCOMES[case["stage"]]:
        raise ValueError(f"At {STAGES[case['stage']]} the outcome must be one of: "
                         + ", ".join(OUTCOME_LABELS[o] for o in OUTCOMES[case["stage"]]) + ".")
    me = access.username(actor)
    history_id = None
    if outcome_type in INTERRUPTING:
        history_id = _interrupt(case, decision, me, effective_date, returning)
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        case = _open_case(conn, case_id)
        outcome_id = conn.execute(
            "INSERT INTO sts_outcomes (case_id, stage, outcome_type, decision, review_date, "
            "lifecycle_history_id, expected_return_date, decided_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case["case_id"], case["stage"], outcome_type, decision, review, history_id,
             returning, me)).lastrowid
        if outcome_type == "escalate":
            _escalate_on(conn, case, decision, me)
        elif outcome_type in CLOSING:
            _close_on(conn, case["case_id"], OUTCOME_LABELS[outcome_type], me)
    _log("outcome", case_id, actor, outcome=outcome_type, lifecycle_history_id=history_id)
    _tell(case["student_id"], "Support to Study outcome",
          f"The outcome of your {STAGES[case['stage']]} is: {OUTCOME_LABELS[outcome_type]}."
          "\n\n" + decision + "\n\nA letter confirming this will follow. If you disagree "
          "with a stage 3 decision you may ask for a review under the university's "
          "procedure, and then complain to the OIA.")
    return int(outcome_id)


def _interrupt(case, decision, me, effective_date, returning) -> int:
    status = wellbeing_bus.student_status(case["student_id"])
    if status != "Active":
        raise ValueError(f"Studies can only be interrupted for an Active student "
                         f"(this student is {status or 'not found'}).")
    try:
        return wellbeing_bus.interrupt_studies(
            case["student_id"], actor_id=me,
            reason=f"Support to Study case #{case['case_id']}: {decision}"[:500],
            effective_date=_date(effective_date, "The effective date"),
            expected_return_date=returning)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"The interruption could not be applied: {exc}") from None


# ------------------------------------------------------------------ links

def link(actor, case_id, kind, ref_id, note=None) -> int:
    """Link another record about the same student to the case."""
    access.require_support_staff(actor)
    if kind not in LINK_KINDS:
        raise ValueError("Choose what kind of record to link.")
    table, key, label = LINK_KINDS[kind]
    ref = str(ref_id or "").strip()
    if not ref:
        raise ValueError("Give the record's number.")
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        case = _open_case(conn, case_id)
        _check_link_target(conn, table, key, label, ref, case["student_id"])
        try:
            link_id = conn.execute(
                "INSERT INTO sts_links (case_id, kind, ref_id, note, linked_by) "
                "VALUES (?, ?, ?, ?, ?)",
                (case["case_id"], kind, ref, (note or "").strip() or None,
                 access.username(actor))).lastrowid
        except Exception:
            raise ValueError("That record is already linked to this case.") from None
    _log("link", case_id, actor, kind=kind, ref_id=ref)
    return int(link_id)


def _check_link_target(conn, table, key, label, ref, student_id) -> None:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,)).fetchone():
        raise ValueError(f"There are no {label.lower()}s to link yet.")
    cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
    # db-audit: ignore[DBW001] - table/key come from the LINK_KINDS literal map
    row = conn.execute(f'SELECT * FROM "{table}" WHERE "{key}" = ?',  # nosec B608
                       (ref,)).fetchone()
    if not row:
        raise ValueError(f"{label} #{ref} was not found.")
    if "student_id" in cols and str(dict(row).get("student_id") or "") not in ("",
                                                                               str(student_id)):
        raise ValueError(f"{label} #{ref} is about a different student.")


def unlink(actor, link_id) -> None:
    access.require_support_staff(actor)
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        conn.execute("DELETE FROM sts_links WHERE link_id = ?", (int(link_id),))


# ------------------------------------------------------------------ letters

def generate_letter(actor, case_id, kind, ref_id=None, *, out_dir=None) -> str:
    """Write a letter as PDF and record it; returns its path. ``kind`` is
    ``invitation`` (``ref_id`` = meeting), ``action_plan`` or ``outcome``
    (``ref_id`` = outcome; default the latest)."""
    access.require_support_staff(actor)
    detail = case_detail(actor, case_id)
    subject, paragraphs, ref = _letter_body(detail, kind, ref_id)
    path = letters.write_letter(
        reference=f"STS-{detail['case_id']}-{kind}", recipient=detail["student_name"],
        address_lines=[f"Student number {detail['student_id']}"], subject=subject,
        paragraphs=paragraphs, signatory=f"{access.username(actor)}\nStudent Support",
        out_dir=out_dir)
    with transaction() as conn:
        schema.ensure_support_to_study(conn)
        conn.execute("INSERT INTO sts_letters (case_id, kind, ref_id, path, created_by) "
                     "VALUES (?, ?, ?, ?, ?)",
                     (detail["case_id"], kind, ref, path, access.username(actor)))
    _log("letter", case_id, actor, kind=kind)
    _tell(detail["student_id"], f"Support to Study — {subject}",
          "A letter about your Support to Study case has been prepared. Student support "
          "will give or e-mail it to you; you can also ask them for a copy.")
    return path


def _letter_body(detail, kind, ref_id):
    stage = STAGES[detail["stage"]]
    if kind == "invitation":
        meetings = [m for m in detail["meetings"]
                    if ref_id is None or m["meeting_id"] == int(ref_id)]
        if not meetings:
            raise ValueError("Schedule the meeting first.")
        m = meetings[-1]
        return ("Invitation to a Support to Study meeting", [
            f"You are invited to a {stage} meeting on {m['meeting_date']}"
            f"{' at ' + m['meeting_time'] if m.get('meeting_time') else ''}"
            f"{', ' + m['location'] if m.get('location') else ''}.",
            "The purpose of the meeting is to talk about how you are, how your studies are "
            "going and what support would help. It is not a disciplinary process.",
            ("Panel: " + m["panel_members"]) if m.get("panel_members") else "",
            "You may bring a supporter, such as a friend, family member or a Students' Union "
            "adviser. If you need adjustments to take part, or the date does not suit you, "
            "please let us know."], m["meeting_id"])
    if kind == "action_plan":
        actions = [a for a in detail["actions"] if a["status"] == "open"]
        if not actions:
            raise ValueError("There are no open actions to put in a plan.")
        lines = [f"• {a['action_text']} — {a['owner']}"
                 f"{', by ' + a['due_date'] if a.get('due_date') else ''}" for a in actions]
        return ("Your Support to Study action plan", [
            f"This confirms the action plan agreed at {stage}.", "\n".join(lines),
            "We will review progress with you. Please contact student support if anything "
            "in the plan becomes difficult."], None)
    if kind == "outcome":
        outcomes = [o for o in detail["outcomes"]
                    if ref_id is None or o["outcome_id"] == int(ref_id)]
        if not outcomes:
            raise ValueError("Record the outcome first.")
        o = outcomes[-1]
        extra = []
        if o["outcome_type"] in INTERRUPTING:
            extra.append("Your studies are interrupted from the date of this decision"
                         + (f"; we expect you to return on {o['expected_return_date']}"
                            if o.get("expected_return_date") else "")
                         + ". Before you return we will meet you to agree any support "
                         "you need.")
        if o.get("review_date"):
            extra.append(f"This will be reviewed on {o['review_date']}.")
        return (f"Outcome of your {stage}", [
            f"Outcome: {OUTCOME_LABELS.get(o['outcome_type'], o['outcome_type'])}.",
            o.get("decision") or "", *extra,
            "If you are unhappy with this decision you may ask for a review under the "
            "university's procedure. If you remain dissatisfied once that is complete, you "
            "may complain to the Office of the Independent Adjudicator (OIA)."],
            o["outcome_id"])
    raise ValueError("Choose invitation, action plan or outcome.")
