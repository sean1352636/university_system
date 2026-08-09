"""Feedback workflow for coursework: release, receipt, appeal, SLA.

Sibling to :mod:`assignments` (assignments, submissions, files) and
:mod:`assignments_marking` (how a mark is arrived at). This module owns
what happens to a mark *after* it is decided and *before* the student
acts on it:

* **Marking turnaround SLA** — days from hand-in to marked, against a
  departmental target, plus the overdue-marking report a head of
  department actually chases people with.
* **Anonymous marking** — names hidden while marking is in progress,
  revealed when feedback is released.
* **Release control** — a mark can exist without the student seeing it,
  so a class gets its results together rather than in dribs.
* **Acknowledgement** — a read receipt and an optional student
  response, which is the evidence that feedback was acted on.
* **Appeals** — a student-initiated remark request with an outcome
  trail, so a disputed mark has a record rather than a corridor
  conversation.

Release is the hinge. :func:`is_visible_to_student` is the single
question everything else asks, and anonymity, acknowledgement and the
appeal window all key off the release date rather than the mark date.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.assignments import (
    assignments as core,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ASSIGNMENTS_DB

ValidationError = core.ValidationError


# ── Vocabularies ──────────────────────────────────────────────────

APPEAL_TYPES: tuple[str, ...] = (
    "Remark request",
    "Administrative error",
    "Procedural concern",
    "Late penalty",
    "Other",
)
DEFAULT_APPEAL_TYPE: str = "Remark request"

APPEAL_STATUSES: tuple[str, ...] = (
    "Submitted", "Under review", "Upheld", "Partly upheld",
    "Rejected", "Withdrawn",
)
DEFAULT_APPEAL_STATUS: str = "Submitted"

# Statuses that mean the appeal is finished with.
CLOSED_APPEAL_STATUSES: tuple[str, ...] = (
    "Upheld", "Partly upheld", "Rejected", "Withdrawn",
)

# What a student sees instead of a classmate's name while marking is
# anonymous. Stable per submission so a marker can refer to "candidate
# 0042" across a marking session.
ANONYMOUS_PREFIX: str = "Candidate"

# The college default when an assignment doesn't set its own.
DEFAULT_MARKING_SLA_DAYS: int = 15

# How long a student has to appeal after release, when the assignment
# doesn't set its own window.
DEFAULT_APPEAL_WINDOW_DAYS: int = 10


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_appeals (
    appeal_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    appeal_type       TEXT NOT NULL DEFAULT 'Remark request',
    status            TEXT NOT NULL DEFAULT 'Submitted',
    grounds           TEXT NOT NULL,
    raised_on         TEXT NOT NULL,
    raised_by         TEXT,
    marks_at_appeal   REAL,
    grade_at_appeal   TEXT,
    reviewer          TEXT,
    review_started_on TEXT,
    outcome           TEXT,
    outcome_on        TEXT,
    marks_after       REAL,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cwappeal_sub
    ON coursework_appeals(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwappeal_status
    ON coursework_appeals(status);
"""


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class Appeal:
    appeal_id: int
    submission_id: int
    appeal_type: str
    status: str
    grounds: str
    raised_on: str
    raised_by: str | None
    marks_at_appeal: float | None
    grade_at_appeal: str | None
    reviewer: str | None
    review_started_on: str | None
    outcome: str | None
    outcome_on: str | None
    marks_after: float | None
    notes: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status not in CLOSED_APPEAL_STATUSES

    @property
    def mark_changed(self) -> float | None:
        if self.marks_after is None or self.marks_at_appeal is None:
            return None
        return round(self.marks_after - self.marks_at_appeal, 2)


@dataclass
class TurnaroundRow:
    """One submission's marking turnaround against the target."""

    submission: core.Submission
    student_name: str
    target_days: int
    days_taken: int | None = None
    days_waiting: int | None = None

    @property
    def is_marked(self) -> bool:
        return self.days_taken is not None

    @property
    def within_target(self) -> bool | None:
        if self.days_taken is None:
            return None
        return self.days_taken <= self.target_days

    @property
    def is_overdue(self) -> bool:
        """Still unmarked and already past the target."""
        return (self.days_taken is None
                and self.days_waiting is not None
                and self.days_waiting > self.target_days)

    @property
    def message(self) -> str:
        if self.days_taken is not None:
            verdict = ("within" if self.within_target else "over")
            return (f"Marked in {self.days_taken} day(s) — "
                    f"{verdict} the {self.target_days}-day target")
        if self.days_waiting is None:
            return "Not submitted"
        if self.is_overdue:
            return (f"Unmarked after {self.days_waiting} day(s) — "
                    f"{self.days_waiting - self.target_days} over target")
        return (f"Unmarked, {self.days_waiting} day(s) in "
                f"(target {self.target_days})")


@dataclass
class TurnaroundReport:
    assignment_id: int | None
    target_days: int
    rows: list[TurnaroundRow] = field(default_factory=list)

    @property
    def marked(self) -> list[TurnaroundRow]:
        return [r for r in self.rows if r.is_marked]

    @property
    def overdue(self) -> list[TurnaroundRow]:
        return [r for r in self.rows if r.is_overdue]

    @property
    def average_days(self) -> float | None:
        taken = [r.days_taken for r in self.marked
                 if r.days_taken is not None]
        if not taken:
            return None
        return round(sum(taken) / len(taken), 1)

    @property
    def within_target_percent(self) -> float | None:
        marked = self.marked
        if not marked:
            return None
        hit = sum(1 for r in marked if r.within_target)
        return round(100.0 * hit / len(marked), 1)

    @property
    def message(self) -> str:
        if not self.rows:
            return "Nothing submitted"
        parts = [f"{len(self.marked)}/{len(self.rows)} marked"]
        if self.average_days is not None:
            parts.append(f"average {self.average_days:g} day(s)")
        if self.within_target_percent is not None:
            parts.append(f"{self.within_target_percent:g}% within the "
                         f"{self.target_days}-day target")
        if self.overdue:
            parts.append(f"{len(self.overdue)} overdue")
        return "; ".join(parts)


@dataclass
class ReleaseResult:
    released: int
    already_released: int
    skipped_unmarked: int

    @property
    def message(self) -> str:
        parts = [f"{self.released} released"]
        if self.already_released:
            parts.append(f"{self.already_released} already visible")
        if self.skipped_unmarked:
            parts.append(f"{self.skipped_unmarked} not marked yet")
        return ", ".join(parts)


# ── DB plumbing ───────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Feedback schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_appeal(r: sqlite3.Row) -> Appeal:
    return Appeal(
        appeal_id=r["appeal_id"], submission_id=r["submission_id"],
        appeal_type=r["appeal_type"], status=r["status"],
        grounds=r["grounds"], raised_on=r["raised_on"],
        raised_by=r["raised_by"],
        marks_at_appeal=r["marks_at_appeal"],
        grade_at_appeal=r["grade_at_appeal"],
        reviewer=r["reviewer"],
        review_started_on=r["review_started_on"],
        outcome=r["outcome"], outcome_on=r["outcome_on"],
        marks_after=r["marks_after"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _today() -> str:
    return _dt.date.today().isoformat()


def _days_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        return (_dt.date.fromisoformat(end)
                - _dt.date.fromisoformat(start)).days
    except ValueError:
        return None


def _require_submission(submission_id: int) -> core.Submission:
    sub = core.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    return sub


def _student_names() -> dict[str, str]:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        return {s.student_id: s.full_name
                for s in _students.list_students()}
    except Exception:
        logger.debug("Student names unavailable", exc_info=True)
        return {}


# ── Feedback release (item 22) ────────────────────────────────────

def is_visible_to_student(submission: core.Submission,
                          assignment: core.Assignment | None = None,
                          *, today: str | None = None) -> bool:
    """Can this student see their mark and feedback yet?

    The one question the rest of the module asks. An unmarked piece is
    never visible; beyond that the assignment's release policy decides.
    """
    if submission.marks is None and not submission.feedback:
        return False
    if submission.feedback_released:
        return True
    if assignment is None:
        assignment = core.get_assignment(submission.assignment_id)
    if assignment is None:
        return False
    policy = assignment.release_policy or core.DEFAULT_RELEASE_POLICY
    if policy == "Immediate":
        return True
    if policy == "On date":
        day = today or _today()
        return bool(assignment.release_on and assignment.release_on <= day)
    return False        # Manual — someone has to press the button


def release_submission(submission_id: int, *,
                        released_by: str | None = None,
                        notify: bool = True) -> core.Submission:
    """Publish one student's mark and feedback to them."""
    init_db()
    sub = _require_submission(submission_id)
    if sub.marks is None and not sub.feedback:
        raise ValidationError(
            "There is nothing to release — this submission has neither "
            "a mark nor feedback")
    if sub.feedback_released:
        return sub
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET feedback_released = 1, "
            "feedback_released_on = ?, feedback_released_by = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (_today(), (released_by or "").strip() or None,
             submission_id))
        conn.commit()
    out = _require_submission(submission_id)
    logger.info("Released feedback on submission #%d (student %s)",
                submission_id, out.student_id)
    if notify:
        _notify_release(out)
    return out


def release_assignment(assignment_id: int, *,
                        released_by: str | None = None,
                        notify: bool = True,
                        only_marked: bool = True) -> ReleaseResult:
    """Publish a whole class's results at once.

    This is the point of holding results back: everybody finds out
    together rather than by looking over a shoulder.
    """
    init_db()
    a = core.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    released = already = skipped = 0
    for sub in core.list_submissions(assignment_id=assignment_id):
        if sub.feedback_released:
            already += 1
            continue
        if only_marked and sub.marks is None and not sub.feedback:
            skipped += 1
            continue
        release_submission(sub.submission_id, released_by=released_by,
                            notify=notify)
        released += 1
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_assignments SET released_at = ?, "
            "updated_at = datetime('now') WHERE assignment_id = ?",
            (_today(), assignment_id))
        conn.commit()
    logger.info("Released assignment #%d: %d released, %d already out, "
                "%d unmarked", assignment_id, released, already, skipped)
    return ReleaseResult(released=released, already_released=already,
                          skipped_unmarked=skipped)


def unrelease_submission(submission_id: int) -> core.Submission:
    """Pull a result back. Use when something was published in error."""
    init_db()
    _require_submission(submission_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET feedback_released = 0, "
            "feedback_released_on = NULL, feedback_released_by = NULL, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (submission_id,))
        conn.commit()
    logger.info("Withdrew released feedback on submission #%d",
                submission_id)
    return _require_submission(submission_id)


def release_due(*, today: str | None = None) -> ReleaseResult:
    """Publish everything whose 'On date' release date has arrived.

    Idempotent, so it is safe to run from a scheduler every morning.
    """
    init_db()
    day = core._validate_date(today, "today") or _today()
    released = already = skipped = 0
    for a in core.list_assignments():
        if a.release_policy != "On date":
            continue
        if not a.release_on or a.release_on > day:
            continue
        result = release_assignment(a.assignment_id,
                                     released_by="Scheduled release")
        released += result.released
        already += result.already_released
        skipped += result.skipped_unmarked
    return ReleaseResult(released=released, already_released=already,
                          skipped_unmarked=skipped)


def list_pending_release(*, assignment_id: int | None = None
                          ) -> list[core.Submission]:
    """Marked work the student cannot see yet."""
    init_db()
    out: list[core.Submission] = []
    assignments = ([core.get_assignment(assignment_id)]
                   if assignment_id is not None
                   else core.list_assignments())
    for a in assignments:
        if a is None:
            continue
        for sub in core.list_submissions(assignment_id=a.assignment_id):
            if sub.marks is None and not sub.feedback:
                continue
            if not is_visible_to_student(sub, a):
                out.append(sub)
    return out


def _notify_release(submission: core.Submission) -> None:
    """Tell the student their result is available. Best-effort."""
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domain.operations.communications.messages import (
            email_templates,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        a = core.get_assignment(submission.assignment_id)
        student = _students.get_student(submission.student_id)
        if a is None or student is None:
            return
        email_templates.send_from_template(
            "assignment_feedback_released",
            {
                "system_name":  SYSTEM_NAME,
                "first_name":   student.first_name,
                "full_name":    student.full_name,
                "student_id":   student.student_id,
                "title":        a.title,
                "subject_name": a.subject_name,
                "teacher":      a.teacher or "your teacher",
                "marks":        ("—" if submission.marks is None
                                  else f"{submission.marks:g}"),
                "max_marks":    ("—" if a.max_marks is None
                                  else f"{a.max_marks:g}"),
                "grade":        submission.grade or "—",
                "feedback":     (submission.feedback
                                  or "(See the portal for your feedback.)"),
                "appeal_days":  str(appeal_window_days(a)),
            },
            to_name=student.full_name,
            to_address=student.email,
            student_id=student.student_id,
        )
    except Exception:
        logger.exception(
            "Could not email the release notice for submission #%d",
            submission.submission_id)


# ── Anonymous marking (item 21) ───────────────────────────────────

def anonymous_label(submission: core.Submission) -> str:
    """A stable pseudonym for one submission."""
    return f"{ANONYMOUS_PREFIX} {submission.submission_id:04d}"


def display_name(submission: core.Submission,
                  assignment: core.Assignment | None = None,
                  *, names: dict[str, str] | None = None,
                  reveal: bool = False) -> str:
    """What to show a marker for this student.

    Anonymity lifts on release rather than on marking: a marker who has
    submitted their marks and had them published has nothing left to be
    swayed about, and staff need real names to talk to students.
    """
    if assignment is None:
        assignment = core.get_assignment(submission.assignment_id)
    if (not reveal and assignment is not None
            and assignment.anonymous_marking
            and not submission.feedback_released):
        return anonymous_label(submission)
    if names is None:
        names = _student_names()
    return names.get(submission.student_id, submission.student_id)


def display_student_id(submission: core.Submission,
                        assignment: core.Assignment | None = None,
                        *, reveal: bool = False) -> str:
    """The student id, or the pseudonym while marking is anonymous."""
    if assignment is None:
        assignment = core.get_assignment(submission.assignment_id)
    if (not reveal and assignment is not None
            and assignment.anonymous_marking
            and not submission.feedback_released):
        return anonymous_label(submission)
    return submission.student_id


def is_anonymous(submission: core.Submission,
                  assignment: core.Assignment | None = None) -> bool:
    if assignment is None:
        assignment = core.get_assignment(submission.assignment_id)
    return bool(assignment and assignment.anonymous_marking
                 and not submission.feedback_released)


# ── Acknowledgement (item 23) ─────────────────────────────────────

def acknowledge(submission_id: int, *,
                 response: str | None = None,
                 acknowledged_on: str | None = None
                 ) -> core.Submission:
    """Record that the student has read their feedback.

    Refuses when the feedback isn't visible yet — an acknowledgement of
    something the student cannot see would be worthless as evidence.
    """
    init_db()
    sub = _require_submission(submission_id)
    a = core.get_assignment(sub.assignment_id)
    if not is_visible_to_student(sub, a):
        raise ValidationError(
            "This feedback has not been released to the student yet")
    when = core._validate_date(acknowledged_on, "Acknowledged on") \
        or _today()
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET acknowledged_on = ?, "
            "student_response = COALESCE(?, student_response), "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (when, (response or "").strip() or None, submission_id))
        conn.commit()
    logger.info("Student %s acknowledged feedback on submission #%d",
                sub.student_id, submission_id)
    return _require_submission(submission_id)


def clear_acknowledgement(submission_id: int) -> core.Submission:
    init_db()
    _require_submission(submission_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET acknowledged_on = NULL, "
            "student_response = NULL, updated_at = datetime('now') "
            "WHERE submission_id = ?", (submission_id,))
        conn.commit()
    return _require_submission(submission_id)


def list_unacknowledged(*, assignment_id: int | None = None
                         ) -> list[core.Submission]:
    """Released feedback the student has not confirmed reading."""
    init_db()
    out: list[core.Submission] = []
    assignments = ([core.get_assignment(assignment_id)]
                   if assignment_id is not None
                   else core.list_assignments())
    for a in assignments:
        if a is None:
            continue
        for sub in core.list_submissions(assignment_id=a.assignment_id):
            if sub.acknowledged_on:
                continue
            if is_visible_to_student(sub, a):
                out.append(sub)
    return out


def acknowledgement_rate(*, assignment_id: int | None = None
                          ) -> tuple[int, int]:
    """(acknowledged, visible) — the inspection-friendly ratio."""
    init_db()
    acknowledged = visible = 0
    assignments = ([core.get_assignment(assignment_id)]
                   if assignment_id is not None
                   else core.list_assignments())
    for a in assignments:
        if a is None:
            continue
        for sub in core.list_submissions(assignment_id=a.assignment_id):
            if not is_visible_to_student(sub, a):
                continue
            visible += 1
            if sub.acknowledged_on:
                acknowledged += 1
    return acknowledged, visible


# ── Marking turnaround SLA (item 20) ──────────────────────────────

def sla_target(assignment: core.Assignment) -> int:
    return (assignment.marking_sla_days
            if assignment.marking_sla_days is not None
            else DEFAULT_MARKING_SLA_DAYS)


def turnaround_report(*, assignment_id: int | None = None,
                       teacher: str | None = None,
                       subject_name: str | None = None,
                       today: str | None = None) -> TurnaroundReport:
    """Days from hand-in to marked, against the departmental target.

    Only submitted work counts: an assignment nobody handed in cannot
    be late to mark.
    """
    init_db()
    day = core._validate_date(today, "today") or _today()
    if assignment_id is not None:
        a = core.get_assignment(assignment_id)
        assignments = [a] if a is not None else []
    else:
        assignments = core.list_assignments(teacher_like=teacher,
                                             subject_name=subject_name)
    names = _student_names()
    target = (sla_target(assignments[0]) if len(assignments) == 1
              else DEFAULT_MARKING_SLA_DAYS)
    report = TurnaroundReport(assignment_id=assignment_id,
                               target_days=target)
    for a in assignments:
        a_target = sla_target(a)
        for sub in core.list_submissions(assignment_id=a.assignment_id):
            if not sub.submitted_on:
                continue
            row = TurnaroundRow(
                submission=sub,
                student_name=names.get(sub.student_id, sub.student_id),
                target_days=a_target)
            if sub.marked_on:
                row.days_taken = _days_between(sub.submitted_on,
                                                sub.marked_on)
            else:
                row.days_waiting = _days_between(sub.submitted_on, day)
            report.rows.append(row)
    return report


def overdue_marking(*, teacher: str | None = None,
                     today: str | None = None) -> list[TurnaroundRow]:
    """The chase list: submitted work past the marking target."""
    report = turnaround_report(teacher=teacher, today=today)
    return sorted(report.overdue,
                   key=lambda r: -(r.days_waiting or 0))


def teacher_sla_summary(*, today: str | None = None
                         ) -> dict[str, TurnaroundReport]:
    """Turnaround broken down by teacher, for a head of department."""
    init_db()
    out: dict[str, TurnaroundReport] = {}
    for a in core.list_assignments():
        who = a.teacher or "(unassigned)"
        report = turnaround_report(assignment_id=a.assignment_id,
                                    today=today)
        if who not in out:
            out[who] = TurnaroundReport(assignment_id=None,
                                         target_days=sla_target(a))
        out[who].rows.extend(report.rows)
    return dict(sorted(out.items(),
                        key=lambda kv: -len(kv[1].overdue)))


# ── Appeals and remark requests (item 24) ─────────────────────────

def appeal_window_days(assignment: core.Assignment) -> int:
    return (assignment.appeal_window_days
            if assignment.appeal_window_days is not None
            else DEFAULT_APPEAL_WINDOW_DAYS)


def appeal_deadline(submission: core.Submission,
                     assignment: core.Assignment | None = None
                     ) -> str | None:
    """Last day this student can appeal, measured from release.

    The clock starts when the student can actually see the mark, not
    when it was entered — otherwise a mark held back for a fortnight
    would eat the whole appeal window.
    """
    if assignment is None:
        assignment = core.get_assignment(submission.assignment_id)
    if assignment is None:
        return None
    start = submission.feedback_released_on or submission.marked_on
    if not start:
        return None
    try:
        return (_dt.date.fromisoformat(start)
                + _dt.timedelta(
                    days=appeal_window_days(assignment))).isoformat()
    except ValueError:
        return None


def raise_appeal(submission_id: int, *,
                  grounds: str,
                  appeal_type: str = DEFAULT_APPEAL_TYPE,
                  raised_by: str | None = None,
                  raised_on: str | None = None,
                  allow_out_of_window: bool = False) -> Appeal:
    """Open a remark request against a released mark.

    Snapshots the mark and grade as they stood, so an upheld appeal can
    show what actually changed.
    """
    init_db()
    sub = _require_submission(submission_id)
    a = core.get_assignment(sub.assignment_id)
    grounds_text = core._require(grounds, "Grounds for appeal").strip()
    kind = (appeal_type or DEFAULT_APPEAL_TYPE).strip()
    if kind not in APPEAL_TYPES:
        raise ValidationError(
            f"Appeal type must be one of: {', '.join(APPEAL_TYPES)}")
    when = core._validate_date(raised_on, "Raised on") or _today()

    if not is_visible_to_student(sub, a):
        raise ValidationError(
            "A mark can only be appealed once it has been released to "
            "the student")
    if any(x.is_open for x in list_appeals(submission_id=submission_id)):
        raise ValidationError(
            "There is already an open appeal on this submission")
    deadline = appeal_deadline(sub, a)
    if deadline and when > deadline and not allow_out_of_window:
        raise ValidationError(
            f"The appeal window closed on {deadline}. Pass "
            f"allow_out_of_window=True to accept a late appeal.")

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_appeals
                   (submission_id, appeal_type, status, grounds,
                    raised_on, raised_by, marks_at_appeal,
                    grade_at_appeal, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                       datetime('now'), datetime('now'))""",
            (submission_id, kind, DEFAULT_APPEAL_STATUS, grounds_text,
             when, (raised_by or sub.student_id).strip() or None,
             sub.marks, sub.grade))
        conn.commit()
        new_id = int(cur.lastrowid or 0)
    out = get_appeal(new_id)
    assert out is not None
    logger.info("Appeal #%d raised on submission #%d (%s) by %s",
                new_id, submission_id, kind, out.raised_by or "—")
    return out


def get_appeal(appeal_id: int) -> Appeal | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM coursework_appeals WHERE appeal_id = ?",
            (appeal_id,)).fetchone()
        return _row_appeal(r) if r else None


def list_appeals(*, submission_id: int | None = None,
                  assignment_id: int | None = None,
                  status: str | None = None,
                  open_only: bool = False) -> list[Appeal]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if submission_id is not None:
        clauses.append("submission_id = ?")
        args.append(int(submission_id))
    if assignment_id is not None:
        clauses.append(
            "submission_id IN (SELECT submission_id "
            "FROM coursework_submissions WHERE assignment_id = ?)")
        args.append(int(assignment_id))
    if status:
        if status not in APPEAL_STATUSES:
            raise ValidationError(
                f"Appeal status must be one of: "
                f"{', '.join(APPEAL_STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    if open_only:
        ph = ",".join("?" * len(CLOSED_APPEAL_STATUSES))
        clauses.append(f"status NOT IN ({ph})")
        args.extend(CLOSED_APPEAL_STATUSES)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_appeal(r) for r in conn.execute(
            f"SELECT * FROM coursework_appeals {where} "
            "ORDER BY raised_on ASC, appeal_id ASC", args).fetchall()]


def start_review(appeal_id: int, *, reviewer: str,
                  notes: str | None = None) -> Appeal:
    """Assign an appeal to a reviewer."""
    init_db()
    appeal = get_appeal(appeal_id)
    if appeal is None:
        raise ValidationError(f"No appeal #{appeal_id}")
    if not appeal.is_open:
        raise ValidationError(
            f"Appeal #{appeal_id} is already {appeal.status}")
    who = core._require(reviewer, "Reviewer").strip()
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_appeals SET status = 'Under review', "
            "reviewer = ?, review_started_on = ?, "
            "notes = COALESCE(?, notes), updated_at = datetime('now') "
            "WHERE appeal_id = ?",
            (who, _today(), (notes or "").strip() or None, appeal_id))
        conn.commit()
    out = get_appeal(appeal_id)
    assert out is not None
    return out


def resolve_appeal(appeal_id: int, *,
                    status: str,
                    outcome: str,
                    new_marks: float | None = None,
                    resolved_by: str | None = None) -> Appeal:
    """Close an appeal, optionally changing the mark.

    A mark change goes through the marking pipeline, so the late
    penalty and grade boundaries reapply and the audit trail records
    that an appeal caused it.
    """
    init_db()
    appeal = get_appeal(appeal_id)
    if appeal is None:
        raise ValidationError(f"No appeal #{appeal_id}")
    if status not in CLOSED_APPEAL_STATUSES:
        raise ValidationError(
            f"Resolving status must be one of: "
            f"{', '.join(CLOSED_APPEAL_STATUSES)}")
    outcome_text = core._require(outcome, "Outcome").strip()

    marks_after: float | None = None
    if new_marks is not None:
        if status == "Rejected":
            raise ValidationError(
                "A rejected appeal cannot also change the mark")
        from education_system.systems.sixth_form.domain.academics.assignments import (
            assignments_marking as _marking,
        )
        updated = _marking.apply_marks(
            appeal.submission_id, raw_marks=new_marks,
            marked_by=resolved_by, source="moderation",
            reason=f"Appeal #{appeal_id} {status.lower()}: "
                   f"{outcome_text}",
            changed_by=resolved_by)
        marks_after = updated.marks

    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_appeals SET
                   status = ?, outcome = ?, outcome_on = ?,
                   marks_after = ?,
                   reviewer = COALESCE(?, reviewer),
                   updated_at = datetime('now')
               WHERE appeal_id = ?""",
            (status, outcome_text, _today(), marks_after,
             (resolved_by or "").strip() or None, appeal_id))
        conn.commit()
    out = get_appeal(appeal_id)
    assert out is not None
    logger.info("Appeal #%d resolved %s (mark %s → %s)",
                appeal_id, status, appeal.marks_at_appeal, marks_after)
    return out


def withdraw_appeal(appeal_id: int, *,
                     reason: str | None = None) -> Appeal:
    """The student changed their mind."""
    return resolve_appeal(appeal_id, status="Withdrawn",
                           outcome=reason or "Withdrawn by the student")


def appeal_summary(*, assignment_id: int | None = None
                    ) -> dict[str, int]:
    """Counts by status, for a governance report."""
    rows = list_appeals(assignment_id=assignment_id)
    out = {s: 0 for s in APPEAL_STATUSES}
    for appeal in rows:
        out[appeal.status] = out.get(appeal.status, 0) + 1
    out["_total"] = len(rows)
    out["_open"] = sum(1 for a in rows if a.is_open)
    out["_upheld"] = sum(1 for a in rows
                          if a.status in ("Upheld", "Partly upheld"))
    return out
