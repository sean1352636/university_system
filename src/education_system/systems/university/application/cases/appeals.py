"""Academic appeals, following the OIA Good Practice Framework.

An academic appeal is a case in the shared register
(``application.case_management``, case type ``appeal``) with an
``academic_appeals`` record that carries what the register cannot: the
grounds, what is being appealed, the stage and its deadline, the outcome and
the Completion of Procedures letter.

Stages, each with a deadline in working days, and the register status each
maps to::

    submitted -> eligibility -> investigation -> outcome -> review -> closed
    (open)       (triage)       (investigation)  (decision) (review)  (closed)

* **Submitted**: by the student (their own appeal only) or by staff for them,
  within :data:`SUBMISSION_WINDOW_DAYS` working days of the results being
  released; a later appeal needs a reason and is marked late.
* **Eligibility**: is it on admissible grounds (UK sector grounds — procedural
  irregularity, material circumstances not previously known, bias, admin
  error)? Academic judgement alone is not a ground. Ineligible appeals go
  straight to *outcome* as ``ineligible``.
* **Investigation** -> **outcome**: upheld, partly upheld or not upheld, with
  the issues considered. An upheld appeal sets *actions* in motion:
  ``remark`` (the module result is re-opened for marking), ``uncapped_resit``
  (resit sittings offer an uncapped deferral — see
  ``assessment.outcomes.appeal_uncapped_resit``) and ``board_reconvene`` (the
  assessment board is reopened with independent approval; it regenerates its
  agenda and decides again, so any re-classification is the board's).
* **Review**: the student may ask for a review within
  :data:`REVIEW_REQUEST_DAYS` working days of the outcome.
* **Closed**: a Completion of Procedures letter is generated (OIA template
  fields; 12 months to go to the OIA) unless the appeal was withdrawn.

Students are told of each step by inbox message and by e-mail through the
university outbox (sent after the commit).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from education_system.systems.university.application import case_management
from education_system.systems.university.application.cases import completion_letter
from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    transaction,
)
from education_system.systems.university.infrastructure.database.schemas import (
    academic_appeals_schema as schema,
)

logger = logging.getLogger(__name__)

STAGES = ("submitted", "eligibility", "investigation", "outcome", "review", "closed")
CASE_STATUS = {"submitted": "open", "eligibility": "triage", "investigation": "investigation",
               "outcome": "decision", "review": "review", "closed": "closed"}
GROUNDS = {
    "procedural_irregularity": "Procedural irregularity in the assessment or its conduct",
    "material_circumstances": "Material circumstances not previously known (with good reason)",
    "bias": "Bias, prejudice or perception of bias",
    "administrative_error": "Administrative error (e.g. a mark recorded wrongly)",
}
OUTCOMES = ("upheld", "partly_upheld", "not_upheld", "ineligible", "withdrawn")
UPHELD = ("upheld", "partly_upheld")
ACTIONS = ("remark", "uncapped_resit", "board_reconvene")
REVIEW_OUTCOMES = ("original_decision_stands", "outcome_changed", "referred_back")
#: Working-day deadlines.
SUBMISSION_WINDOW_DAYS = 10
STAGE_DAYS = {"submitted": 5, "eligibility": 5, "investigation": 20, "outcome": 10,
              "review": 20}
REVIEW_REQUEST_DAYS = 10
#: The OIA expects internal procedures to finish within 90 calendar days.
TARGET_CLOSE_DAYS = 90
STAFF_ROLES = ("admin", "administrator", "superadmin", "staff", "registrar")


@dataclass(frozen=True)
class Who:
    username: str
    role: str = ""
    student_id: str | None = None

    @property
    def is_staff(self) -> bool:
        return self.role.lower() in STAFF_ROLES

    @property
    def is_student(self) -> bool:
        return self.role.lower() == "student"


def who_from_user(user: dict | None) -> Who:
    """The acting person from a session user dict (student id resolved by username)."""
    user = user or {}
    username = str(user.get("username") or user.get("id") or "").strip()
    role = str(user.get("role") or "").lower()
    student_id = user.get("student_id")
    if role == "student" and not student_id and username:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT student_id FROM users WHERE username = ?",
                                   (username,)).fetchone()
            student_id = row[0] if row and row[0] else username
        except Exception:
            student_id = username
    return Who(username=username or "unknown", role=role,
               student_id=str(student_id) if student_id else None)


# ── helpers ─────────────────────────────────────────────────────────────


def _today() -> date:
    return date.today()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def add_working_days(start: date, days: int) -> date:
    """``start`` plus ``days`` working days (Monday to Friday)."""
    current, left = start, days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def _date(value, label) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ValueError(f"{label} must be a date (YYYY-MM-DD)") from None


def ensure() -> None:
    with get_connection() as conn:
        schema.apply_to_connection(conn)


def _require_staff(who: Who) -> None:
    if not who.is_staff:
        raise PermissionError("Only appeals staff can do this")


def _appeal(conn, appeal_id) -> dict:
    row = conn.execute("SELECT * FROM academic_appeals WHERE appeal_id = ?",
                       (int(appeal_id),)).fetchone()
    if row is None:
        raise ValueError(f"Appeal {appeal_id} does not exist")
    return dict(row)


def _visible(conn, who: Who, appeal_id) -> dict:
    appeal = _appeal(conn, appeal_id)
    if not who.is_staff and appeal["student_id"] != who.student_id:
        raise PermissionError("You can only see your own appeals")
    return appeal


def _set_stage(conn, appeal, stage, who, reason, **fields) -> None:
    today = _today()
    due = add_working_days(today, STAGE_DAYS[stage]) if stage in STAGE_DAYS else None
    sets = {"stage": stage, "stage_entered_at": _now(),
            "stage_due": due.isoformat() if due else None, **fields}
    # db-audit: ignore[DBW001] - keys are code literals
    conn.execute(f"UPDATE academic_appeals SET {', '.join(f'{k} = ?' for k in sets)} "
                 "WHERE appeal_id = ?", (*sets.values(), appeal["appeal_id"]))
    case_management.transition_case_on(conn, appeal["case_id"], CASE_STATUS[stage],
                                       actor_id=who.username, reason=reason,
                                       details={"appeal_id": appeal["appeal_id"], "stage": stage})


def _notify(conn, appeal, subject, body) -> list[tuple[str, str, str]]:
    """Inbox message to the student; the e-mails to send after the commit."""
    student_id = appeal["student_id"]
    try:
        from education_system.systems.university.infrastructure.email.messages_inbox import (
            deliver_inbox_message_on,
        )
        deliver_inbox_message_on(conn, student_id, subject, body)
    except Exception:
        logger.debug("Appeal inbox message not delivered", exc_info=True)
    try:
        row = conn.execute("SELECT COALESCE(u.email, s.email_address) FROM students s LEFT JOIN "
                           "users u ON u.student_id = s.student_id WHERE s.student_id = ?",
                           (student_id,)).fetchone()
    except Exception:  # no users table (fresh database): inbox only
        row = None
    return [(row[0], subject, body)] if row and row[0] and "@" in str(row[0]) else []


def _send_emails(emails) -> int:
    """Through the university outbox; best-effort, after the commit."""
    sent = 0
    for address, subject, body in emails or []:
        try:
            from education_system.systems.university.infrastructure.email import outbox_delivery
            outbox_delivery.enqueue(address, subject, body, category="appeals")
            sent += 1
        except Exception:
            logger.warning("Appeal e-mail to %s not queued", address, exc_info=True)
    return sent


def _ref(appeal) -> str:
    return f"APL-{int(appeal['appeal_id']):05d}"


# ── submission ──────────────────────────────────────────────────────────


def _module_grade_id(conn, student_id, module_code):
    if not module_code:
        return None
    try:
        row = conn.execute("SELECT id FROM module_grades WHERE student_id = ? AND module_code = ? "
                           "ORDER BY id LIMIT 1", (student_id, module_code)).fetchone()
    except Exception:
        return None
    return int(row[0]) if row else None


def check_submission(who: Who, student_id, grounds, statement) -> None:
    if not student_id:
        raise ValueError("Say which student is appealing")
    if who.is_student and student_id != who.student_id:
        raise PermissionError("You can only appeal your own results")
    if not (who.is_student or who.is_staff):
        raise PermissionError("Only the student or appeals staff can submit an appeal")
    if grounds not in GROUNDS:
        raise ValueError("Grounds must be one of: " + ", ".join(GROUNDS))
    if len((statement or "").strip()) < 20:
        raise ValueError("Explain the appeal in at least a sentence or two")


def submit(who: Who, student_id: str, grounds: str, statement: str, *,
           module_code: str | None = None, assessment_name: str | None = None,
           current_result: str | None = None, board_id: int | None = None,
           board_decision_id: int | None = None, progression_outcome_id: int | None = None,
           results_released_on=None, late_reason: str | None = None,
           ticket_id: int | None = None) -> int:
    """Open an appeal case and its record. Returns the appeal id."""
    student_id = str(student_id or "").strip()
    check_submission(who, student_id, grounds, statement)
    if not (module_code or board_id or progression_outcome_id):
        raise ValueError("Say what is appealed: a module result, a board decision or a "
                         "progression outcome")
    ensure()
    released = _date(results_released_on, "Results release date")
    deadline = add_working_days(released, SUBMISSION_WINDOW_DAYS) if released else None
    late = bool(deadline and _today() > deadline)
    if late and not (late_reason or "").strip():
        raise ValueError(f"The appeal window closed on {deadline}; give the reason it is late")
    what = module_code or (f"board {board_id}" if board_id else
                           f"progression outcome {progression_outcome_id}")
    today = _today()
    with transaction() as conn:
        schema.apply_to_connection(conn)
        summary = (f"Academic appeal: {what} ({GROUNDS[grounds].split(' (')[0].lower()}) "
                   f"submitted {_now()}")
        case_id = case_management.open_case_on(conn, "appeal", student_id, summary,
                                               opened_by=who.username)
        cur = conn.execute(
            "INSERT INTO academic_appeals (case_id, student_id, stage, grounds, statement, "
            "module_code, assessment_name, current_result, module_grade_id, board_id, "
            "board_decision_id, progression_outcome_id, results_released_on, "
            "submission_deadline, late, late_reason, submitted_at, submitted_by, "
            "stage_entered_at, stage_due, target_close_date, ticket_id) "
            "VALUES (?, ?, 'submitted', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, student_id, grounds, statement.strip(), module_code or None,
             assessment_name or None, current_result or None,
             _module_grade_id(conn, student_id, module_code), board_id, board_decision_id,
             progression_outcome_id, released.isoformat() if released else None,
             deadline.isoformat() if deadline else None, int(late),
             (late_reason or "").strip() or None, _now(), who.username, _now(),
             add_working_days(today, STAGE_DAYS["submitted"]).isoformat(),
             (today + timedelta(days=TARGET_CLOSE_DAYS)).isoformat(), ticket_id))
        appeal = _appeal(conn, cur.lastrowid)
        emails = _notify(conn, appeal, f"Appeal received ({_ref(appeal)})",
                         f"We have received your academic appeal about {what}. Reference "
                         f"{_ref(appeal)}. We will tell you whether it is eligible by "
                         f"{appeal['stage_due']}.")
    _send_emails(emails)
    return int(appeal["appeal_id"])


# ── handling ────────────────────────────────────────────────────────────


def assign(who: Who, appeal_id, handler: str) -> None:
    _require_staff(who)
    if not (handler or "").strip():
        raise ValueError("Name the appeal handler")
    with transaction() as conn:
        appeal = _appeal(conn, appeal_id)
        if appeal["stage"] == "closed":
            raise ValueError("The appeal is closed")
        conn.execute("UPDATE academic_appeals SET handler = ? WHERE appeal_id = ?",
                     (handler.strip(), appeal["appeal_id"]))
        conn.execute("UPDATE institutional_cases SET owner_id = ? WHERE case_id = ?",
                     (handler.strip(), appeal["case_id"]))
        case_management.record_event_on(conn, appeal["case_id"], "assigned",
                                         actor_id=who.username,
                                         details={"handler": handler.strip()})


def start_eligibility(who: Who, appeal_id) -> None:
    _require_staff(who)
    with transaction() as conn:
        appeal = _appeal(conn, appeal_id)
        if appeal["stage"] != "submitted":
            raise ValueError("Only a newly submitted appeal moves to the eligibility check")
        _set_stage(conn, appeal, "eligibility", who, "Eligibility check started")


def decide_eligibility(who: Who, appeal_id, eligible: bool, reason: str) -> None:
    """Eligible appeals go to investigation; ineligible ones to outcome."""
    _require_staff(who)
    if not (reason or "").strip():
        raise ValueError("Give the reason for the eligibility decision")
    with transaction() as conn:
        appeal = _appeal(conn, appeal_id)
        if appeal["stage"] not in ("submitted", "eligibility"):
            raise ValueError("Eligibility has already been decided")
        fields = {"eligibility_decision": "eligible" if eligible else "ineligible",
                  "eligibility_reason": reason.strip()}
        if eligible:
            _set_stage(conn, appeal, "investigation", who, reason.strip(), **fields)
            subject, body = "Your appeal will be investigated", \
                f"Your appeal {_ref(appeal)} is eligible and will now be investigated."
        else:
            today = _today().isoformat()
            _set_stage(conn, appeal, "outcome", who, reason.strip(), outcome="ineligible",
                       outcome_rationale=reason.strip(), outcome_at=_now(),
                       final_decision_date=today,
                       issues_considered=json.dumps(["Eligibility of the appeal"]), **fields)
            subject, body = "Your appeal is not eligible", \
                (f"Your appeal {_ref(appeal)} is not eligible: {reason.strip()}\nYou may ask "
                 f"for a review within {REVIEW_REQUEST_DAYS} working days.")
        emails = _notify(conn, appeal, subject, body)
    _send_emails(emails)


def _clean_actions(appeal, outcome, actions) -> list[dict]:
    actions = [dict(a) for a in actions or []]
    if actions and outcome not in UPHELD:
        raise ValueError("Only an upheld or partly upheld appeal can set actions in motion")
    for action in actions:
        if action.get("type") not in ACTIONS:
            raise ValueError("Actions are: " + ", ".join(ACTIONS))
        if action["type"] in ("remark", "uncapped_resit") and not appeal["module_code"]:
            raise ValueError(f"A {action['type'].replace('_', ' ')} needs the appealed module")
        if action["type"] == "board_reconvene":
            if not appeal["board_id"]:
                raise ValueError("A board reconvene needs the appealed board")
            if not (action.get("approved_by") or "").strip():
                raise ValueError("Reconvening a board needs an independent approver")
    return actions


def _issues(issues) -> list[str]:
    if isinstance(issues, str):
        issues = issues.splitlines()
    return [str(i).strip(" -•\t") for i in issues or [] if str(i).strip(" -•\t")]


def record_outcome(who: Who, appeal_id, outcome: str, rationale: str, issues,
                   actions=None) -> dict:
    """The investigation's outcome, the issues considered and any actions.

    ``actions`` is a list of ``{"type": remark|uncapped_resit|board_reconvene,
    "assigned_to"?, "details"?, "approved_by"? (board_reconvene)}``. The board
    is reopened after the outcome is committed (the boards service owns its
    own transaction); a refusal there leaves the action ``failed`` with the
    reason, to retry with :func:`retry_action`.
    """
    _require_staff(who)
    if outcome not in ("upheld", "partly_upheld", "not_upheld"):
        raise ValueError("Outcome is upheld, partly_upheld or not_upheld")
    issue_list = _issues(issues)
    if not issue_list or not (rationale or "").strip():
        raise ValueError("Record the issues considered and the reasons for the outcome")
    with transaction() as conn:
        appeal = _appeal(conn, appeal_id)
        if appeal["stage"] != "investigation":
            raise ValueError("An outcome is recorded at the end of the investigation")
        clean = _clean_actions(appeal, outcome, actions)
        _set_stage(conn, appeal, "outcome", who, f"Outcome: {outcome}", outcome=outcome,
                   outcome_rationale=rationale.strip(), outcome_at=_now(),
                   final_decision_date=_today().isoformat(),
                   issues_considered=json.dumps(issue_list))
        created = [_create_action(conn, appeal, a, who) for a in clean]
        emails = _notify(conn, appeal, f"Outcome of your appeal ({_ref(appeal)})",
                         f"Outcome: {outcome.replace('_', ' ')}.\n{rationale.strip()}\nYou may "
                         f"ask for a review within {REVIEW_REQUEST_DAYS} working days.")
    _send_emails(emails)
    reconvene = [a for a in created if a["action_type"] == "board_reconvene"]
    for action in reconvene:
        _reopen_board(action["action_id"], who)
    return {"actions": [a["action_id"] for a in created]}


def _create_action(conn, appeal, action, who) -> dict:
    details = {k: v for k, v in action.items() if k not in ("type", "assigned_to")}
    cur = conn.execute(
        "INSERT INTO academic_appeal_actions (appeal_id, action_type, student_id, module_code, "
        "board_id, assigned_to, details, status, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (appeal["appeal_id"], action["type"], appeal["student_id"], appeal["module_code"],
         appeal["board_id"], (action.get("assigned_to") or "").strip() or None,
         json.dumps(details, default=str),
         "in_progress" if action["type"] == "remark" else "open", who.username, _now()))
    if action["type"] == "remark":
        _reopen_result(conn, appeal)
    case_management.record_event_on(conn, appeal["case_id"], f"action:{action['type']}",
                                     actor_id=who.username,
                                     details={"action_id": cur.lastrowid, **details})
    return {"action_id": int(cur.lastrowid), "action_type": action["type"]}


def _reopen_result(conn, appeal) -> None:
    """Re-open the appealed module result for re-marking.

    A board-confirmed result is unlocked and made provisional again, so marks
    can be re-entered and the result recalculated; the board then confirms it
    afresh.
    """
    conn.execute("UPDATE module_grades SET locked = 0, status = 'provisional' "
                 "WHERE student_id = ? AND module_code = ?",
                 (appeal["student_id"], appeal["module_code"]))


def _reopen_board(action_id, who: Who) -> dict:
    with get_connection() as conn:
        action = dict(conn.execute("SELECT * FROM academic_appeal_actions WHERE action_id = ?",
                                   (int(action_id),)).fetchone())
        appeal = _appeal(conn, action["appeal_id"])
    details = json.loads(action["details"] or "{}")
    from education_system.systems.university.domains.assessment.domain.boards import service
    try:
        correction = service.reopen(
            int(action["board_id"]), requested_by=who.username,
            approved_by=str(details.get("approved_by") or ""),
            reason=f"Academic appeal {_ref(appeal)} upheld: board reconvened",
            decision_id=appeal["board_decision_id"])
    except ValueError as exc:
        _finish_action(action_id, "failed", str(exc), who)
        return {"status": "failed", "error": str(exc)}
    with transaction() as conn:
        conn.execute("UPDATE academic_appeal_actions SET status = 'in_progress', "
                     "correction_id = ?, result = ? WHERE action_id = ?",
                     (correction, f"Board {action['board_id']} reopened (correction "
                                  f"{correction}); awaiting re-ratification", int(action_id)))
        case_management.record_event_on(conn, appeal["case_id"], "board_reopened",
                                         actor_id=who.username,
                                         details={"board_id": action["board_id"],
                                                  "correction_id": correction})
    return {"status": "in_progress", "correction_id": correction}


def retry_action(who: Who, action_id) -> dict:
    """Retry a failed board reconvene (e.g. once the board has been ratified)."""
    _require_staff(who)
    with get_connection() as conn:
        row = conn.execute("SELECT action_type, status FROM academic_appeal_actions "
                           "WHERE action_id = ?", (int(action_id),)).fetchone()
    if row is None or row[0] != "board_reconvene" or row[1] not in ("failed", "open"):
        raise ValueError("Only a board reconvene that has not started can be retried")
    return _reopen_board(action_id, who)


def _finish_action(action_id, status, result, who: Who) -> None:
    with transaction() as conn:
        conn.execute("UPDATE academic_appeal_actions SET status = ?, result = ?, "
                     "completed_by = ?, completed_at = ? WHERE action_id = ?",
                     (status, result, who.username, _now(), int(action_id)))


def complete_action(who: Who, action_id, result: str) -> None:
    """Record that a re-mark or resit arrangement is done, with what came of it."""
    _require_staff(who)
    if not (result or "").strip():
        raise ValueError("Say what the action produced")
    with transaction() as conn:
        row = conn.execute("SELECT a.status, p.case_id FROM academic_appeal_actions a JOIN "
                           "academic_appeals p ON p.appeal_id = a.appeal_id "
                           "WHERE a.action_id = ?", (int(action_id),)).fetchone()
        if row is None:
            raise ValueError(f"Action {action_id} does not exist")
        if row[0] in ("completed", "cancelled"):
            raise ValueError("That action is already finished")
        conn.execute("UPDATE academic_appeal_actions SET status = 'completed', result = ?, "
                     "completed_by = ?, completed_at = ? WHERE action_id = ?",
                     (result.strip(), who.username, _now(), int(action_id)))
        case_management.record_event_on(conn, row[1], "action_completed", actor_id=who.username,
                                         details={"action_id": int(action_id),
                                                  "result": result.strip()})


def uncapped_resit_appeal(student_id: str, module_code: str) -> int | None:
    """The appeal granting an uncapped resit on this module, if any (not cancelled)."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT appeal_id FROM academic_appeal_actions WHERE student_id = ? AND "
                "module_code = ? AND action_type = 'uncapped_resit' AND status IN "
                "('open', 'in_progress', 'completed') ORDER BY action_id DESC LIMIT 1",
                (str(student_id), module_code)).fetchone()
    except Exception:  # table not created yet: no appeals
        return None
    return int(row[0]) if row else None


# ── review, withdrawal, closure ─────────────────────────────────────────


def request_review(who: Who, appeal_id, reason: str) -> None:
    if not (reason or "").strip():
        raise ValueError("Say why the outcome should be reviewed")
    with transaction() as conn:
        appeal = _visible(conn, who, appeal_id)
        if appeal["stage"] != "outcome":
            raise ValueError("A review can be requested once the outcome is known")
        decided = _date(appeal["final_decision_date"], "Decision date") or _today()
        window = add_working_days(decided, REVIEW_REQUEST_DAYS)
        if _today() > window and not who.is_staff:
            raise ValueError(f"The review window closed on {window}")
        _set_stage(conn, appeal, "review", who, reason.strip(),
                   review_requested_at=_now(), review_reason=reason.strip())


def decide_review(who: Who, appeal_id, review_outcome: str, rationale: str) -> None:
    _require_staff(who)
    if review_outcome not in REVIEW_OUTCOMES:
        raise ValueError("Review outcome is one of: " + ", ".join(REVIEW_OUTCOMES))
    if not (rationale or "").strip():
        raise ValueError("Give the reasons for the review decision")
    with transaction() as conn:
        appeal = _appeal(conn, appeal_id)
        if appeal["stage"] != "review" or appeal["review_decided_at"]:
            raise ValueError("There is no review waiting for a decision")
        if review_outcome == "referred_back":
            # Back to investigation for a fresh outcome.
            _set_stage(conn, appeal, "investigation", who, rationale.strip(),
                       review_outcome=review_outcome, review_rationale=rationale.strip(),
                       review_decided_at=_now())
            return
        conn.execute("UPDATE academic_appeals SET review_outcome = ?, review_rationale = ?, "
                     "review_decided_at = ?, final_decision_date = ? WHERE appeal_id = ?",
                     (review_outcome, rationale.strip(), _now(), _today().isoformat(),
                      appeal["appeal_id"]))
        case_management.record_event_on(conn, appeal["case_id"], "review_decided",
                                         actor_id=who.username,
                                         details={"outcome": review_outcome})


def withdraw(who: Who, appeal_id, reason: str) -> None:
    with transaction() as conn:
        appeal = _visible(conn, who, appeal_id)
        if appeal["stage"] == "closed":
            raise ValueError("The appeal is already closed")
        _set_stage(conn, appeal, "closed", who, f"Withdrawn: {reason or 'no reason given'}",
                   outcome=appeal["outcome"] or "withdrawn", closed_at=_now())


def _letter(conn, appeal, issued_by) -> dict:
    name = conn.execute("SELECT TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, "
                        "'')) FROM students WHERE student_id = ?",
                        (appeal["student_id"],)).fetchone()
    outcome = (appeal["outcome"] or "").replace("_", " ")
    text = f"Appeal {outcome}. {appeal['outcome_rationale'] or ''}".strip()
    if appeal["review_outcome"]:
        text += (f" Review: {appeal['review_outcome'].replace('_', ' ')}. "
                 f"{appeal['review_rationale'] or ''}").rstrip()
    return completion_letter.build(
        student_name=(name[0] if name and name[0] else appeal["student_id"]),
        student_id=appeal["student_id"], case_ref=f"{_ref(appeal)} / {appeal['case_id']}",
        case_kind="appeal",
        summary=f"{GROUNDS[appeal['grounds']]}. {appeal['statement']}",
        issues=json.loads(appeal["issues_considered"] or "[]"), outcome=text,
        final_decision_date=appeal["final_decision_date"], issued_by=issued_by)


def close(who: Who, appeal_id, *, directory=None) -> dict:
    """Close the appeal and generate its Completion of Procedures letter."""
    _require_staff(who)
    with transaction() as conn:
        appeal = _appeal(conn, appeal_id)
        if appeal["stage"] == "review" and not appeal["review_decided_at"]:
            raise ValueError("Decide the review before closing")
        if appeal["stage"] not in ("outcome", "review"):
            raise ValueError("An appeal is closed after its outcome (and any review)")
        letter = _letter(conn, appeal, who.username)
        path = completion_letter.save_pdf(letter, directory)
        _set_stage(conn, appeal, "closed", who, "Internal procedures completed",
                   closed_at=_now(), cop_issued_at=_now(), cop_path=str(path))
        case_management.record_event_on(conn, appeal["case_id"], "cop_letter_issued",
                                         actor_id=who.username,
                                         details={"path": str(path),
                                                  "oia_deadline": letter["oia_deadline"]})
        emails = _notify(conn, appeal, f"Completion of Procedures ({_ref(appeal)})",
                         completion_letter.render_text(letter))
    _send_emails(emails)
    return {"path": str(path), "oia_deadline": letter["oia_deadline"].isoformat()}


def cop_letter_pdf(who: Who, appeal_id) -> bytes:
    """The issued letter, re-rendered from the record (student: own appeal only)."""
    with get_connection() as conn:
        appeal = _visible(conn, who, appeal_id)
        if not appeal["cop_issued_at"]:
            raise ValueError("No Completion of Procedures letter has been issued yet")
        letter = _letter(conn, appeal, "")
    letter["issued_on"] = _date(appeal["cop_issued_at"], "Issue date")
    letter["oia_deadline"] = completion_letter.oia_deadline(letter["issued_on"])
    return completion_letter.render_pdf(letter)


# ── reading ─────────────────────────────────────────────────────────────


def list_appeals(who: Who, *, stage: str | None = None, student_id: str | None = None,
                 limit: int = 500) -> list[dict]:
    ensure()
    clauses, params = [], []
    if not who.is_staff:
        clauses.append("student_id = ?")
        params.append(who.student_id or "")
    elif student_id:
        clauses.append("student_id = ?")
        params.append(student_id)
    if stage:
        clauses.append("stage = ?")
        params.append(stage)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT appeal_id, case_id, student_id, stage, grounds, module_code, board_id, "
            "handler, stage_due, outcome, submitted_at, closed_at, late FROM academic_appeals "
            f"{where} ORDER BY appeal_id DESC LIMIT ?", (*params, int(limit))).fetchall()  # nosec B608
    today = _today().isoformat()
    return [dict(r, overdue=bool(r["stage"] != "closed" and r["stage_due"]
                                 and r["stage_due"] < today)) for r in rows]


def _board_state(conn, appeal) -> dict | None:
    if not appeal["board_id"]:
        return None
    try:
        board = conn.execute("SELECT status, version, ratified_at FROM assessment_boards "
                             "WHERE board_id = ?", (appeal["board_id"],)).fetchone()
        award = conn.execute("SELECT award_name, classification, status, ratified_at FROM "
                             "ratified_student_awards WHERE student_id = ? AND board_id = ? "
                             "ORDER BY award_id DESC LIMIT 1",
                             (appeal["student_id"], appeal["board_id"])).fetchone()
    except Exception:
        return None
    return {"board": dict(board) if board else None, "award": dict(award) if award else None}


def detail(who: Who, appeal_id) -> dict:
    """The appeal, its actions, the board's current state and award, and the case history."""
    ensure()
    with get_connection() as conn:
        appeal = _visible(conn, who, appeal_id)
        appeal["reference"] = _ref(appeal)
        appeal["issues_considered"] = json.loads(appeal["issues_considered"] or "[]")
        appeal["actions"] = [dict(r) for r in conn.execute(
            "SELECT * FROM academic_appeal_actions WHERE appeal_id = ? ORDER BY action_id",
            (appeal["appeal_id"],))]
        appeal["board_state"] = _board_state(conn, appeal)
    if who.is_staff:
        appeal["events"] = case_management.case_record(appeal["case_id"])["events"]
    return appeal


def overdue(who: Who) -> list[dict]:
    """Open appeals past their stage deadline (the reminder list for staff)."""
    _require_staff(who)
    return [a for a in list_appeals(who) if a["overdue"]]


def send_reminders(who: Who) -> int:
    """Remind each overdue appeal's handler (inbox + outbox), at most once a day."""
    _require_staff(who)
    today = _today().isoformat()
    emails, count = [], 0
    with transaction() as conn:
        schema.apply_to_connection(conn)
        rows = conn.execute(
            "SELECT * FROM academic_appeals WHERE stage <> 'closed' AND stage_due < ? AND "
            "handler IS NOT NULL AND COALESCE(substr(last_reminder_at, 1, 10), '') < ?",
            (today, today)).fetchall()
        from education_system.systems.university.infrastructure.email.messages_inbox import (
            deliver_inbox_message_on,
        )
        for row in rows:
            subject = f"Overdue appeal {_ref(row)} ({row['stage']})"
            body = (f"Appeal {_ref(row)} for {row['student_id']} was due to leave the "
                    f"{row['stage']} stage by {row['stage_due']}.")
            deliver_inbox_message_on(conn, row["handler"], subject, body)
            mail = conn.execute("SELECT email FROM users WHERE username = ?",
                                (row["handler"],)).fetchone()
            if mail and mail[0]:
                emails.append((mail[0], subject, body))
            conn.execute("UPDATE academic_appeals SET last_reminder_at = ? WHERE appeal_id = ?",
                         (_now(), row["appeal_id"]))
            count += 1
    _send_emails(emails)
    return count


# ── OIA statistics (in appeals_statistics; re-exported for callers) ──────


def statistics(who: Who, date_from=None, date_to=None) -> dict:
    """OIA-style case statistics for appeals submitted in the period."""
    _require_staff(who)
    ensure()
    from education_system.systems.university.application.cases import appeals_statistics
    return appeals_statistics.statistics(date_from, date_to)


def statistics_csv(stats: dict) -> str:
    from education_system.systems.university.application.cases import appeals_statistics
    return appeals_statistics.statistics_csv(stats)


def statistics_text(stats: dict) -> str:
    from education_system.systems.university.application.cases import appeals_statistics
    return appeals_statistics.statistics_text(stats)


__all__ = [
    "ACTIONS", "GROUNDS", "OUTCOMES", "REVIEW_OUTCOMES", "STAGES", "Who", "add_working_days",
    "assign", "close", "complete_action", "cop_letter_pdf", "decide_eligibility",
    "decide_review", "detail", "list_appeals", "overdue", "record_outcome", "request_review",
    "retry_action", "send_reminders", "start_eligibility", "statistics", "statistics_csv",
    "statistics_text", "submit", "uncapped_resit_appeal", "who_from_user", "withdraw",
]
