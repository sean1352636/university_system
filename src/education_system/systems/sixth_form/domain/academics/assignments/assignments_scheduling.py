"""Getting coursework out of the system and in front of people.

Sibling to :mod:`assignments`. Everything here is a scheduled or
outward-facing action:

* **Set-date publishing** — write an assignment now, let it appear on
  its set date rather than the moment you save it.
* **Due-date reminders** — nudges at the offsets the assignment names
  (7/3/1 days by default), each sent once.
* **Missing-work chasers** — escalation after the deadline: the student
  first, then their tutor, then home.
* **Parent portal visibility** — a guardian-safe view of what is set,
  what is in, and what has been released.
* **Calendar integration** — deadlines pushed into the academic-year
  calendar so they sit alongside exams and trips.

Every sweep here is **idempotent and dated**: running the daily job
twice sends nothing twice, because what was sent is recorded on the
row rather than inferred from the clock.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.assignments import (
    integrity as assignments_integrity,
    models as assignments_models,
    store as assignments_store,
    submissions as assignments_submissions,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ASSIGNMENTS_DB

ValidationError = assignments_models.ValidationError


# ── Vocabularies ──────────────────────────────────────────────────

# How far ahead of the deadline a nudge goes out, when the assignment
# does not name its own offsets.
DEFAULT_REMINDER_DAYS: tuple[int, ...] = (7, 3, 1)

# Escalation ladder for work that never arrived. Level is stored on the
# submission so a re-run picks up where the last one stopped.
CHASE_LEVELS: tuple[tuple[int, str, str], ...] = (
    (1, "Student", "A direct nudge to the student"),
    (2, "Tutor", "The student's tutor is copied in"),
    (3, "Parent", "Home is contacted"),
)
MAX_CHASE_LEVEL: int = 3

# Days between escalations, so a student is not chased three times in
# one afternoon.
CHASE_INTERVAL_DAYS: int = 3

# Calendar event kind used for a coursework deadline.
CALENDAR_EVENT_KIND: str = "Deadline"

NOTICE_KINDS: tuple[str, ...] = ("reminder", "chase")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS coursework_notices (
    notice_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id     INTEGER NOT NULL,
    kind              TEXT NOT NULL,
    offset_days       INTEGER,
    level             INTEGER,
    recipient         TEXT,
    channel           TEXT NOT NULL DEFAULT 'Email',
    sent_on           TEXT NOT NULL,
    detail            TEXT,
    delivered         INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (submission_id) REFERENCES coursework_submissions(submission_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cwnotice_sub
    ON coursework_notices(submission_id);
CREATE INDEX IF NOT EXISTS idx_cwnotice_kind
    ON coursework_notices(kind);
"""


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class Notice:
    """One nudge that went out (or was attempted)."""

    notice_id: int
    submission_id: int
    kind: str
    offset_days: int | None
    level: int | None
    recipient: str | None
    channel: str
    sent_on: str
    detail: str | None
    delivered: bool
    created_at: str

    @property
    def label(self) -> str:
        if self.kind == "reminder":
            return f"Reminder, {self.offset_days} day(s) before"
        name = next((n for lvl, n, _ in CHASE_LEVELS
                      if lvl == self.level), "Chase")
        return f"Chase level {self.level} ({name})"


@dataclass
class SweepResult:
    """What a scheduled sweep did."""

    scanned: int = 0
    actioned: int = 0
    skipped: int = 0
    failures: int = 0
    detail: list[str] = field(default_factory=list)

    @property
    def message(self) -> str:
        bits = [f"{self.scanned} scanned", f"{self.actioned} actioned"]
        if self.skipped:
            bits.append(f"{self.skipped} already done")
        if self.failures:
            bits.append(f"{self.failures} failed")
        return ", ".join(bits)


@dataclass
class ParentAssignmentView:
    """One assignment as a guardian should see it."""

    assignment_id: int
    title: str
    subject_name: str
    assignment_type: str
    teacher: str | None
    set_date: str | None
    due_date: str | None
    status: str
    submitted: bool
    submitted_on: str | None
    is_late: bool
    is_missing: bool
    marks: float | None = None
    max_marks: float | None = None
    grade: str | None = None
    feedback_available: bool = False

    @property
    def state(self) -> str:
        if self.is_missing:
            return "Not handed in"
        if self.marks is not None:
            return "Marked"
        if self.submitted:
            return "Late" if self.is_late else "Handed in"
        return "Set"


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
    assignments_store.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Scheduling schema ready at %s", DB_PATH)
    _DB_READY = True


def _row_notice(r: sqlite3.Row) -> Notice:
    return Notice(
        notice_id=r["notice_id"], submission_id=r["submission_id"],
        kind=r["kind"], offset_days=r["offset_days"],
        level=r["level"], recipient=r["recipient"],
        channel=r["channel"], sent_on=r["sent_on"],
        detail=r["detail"], delivered=bool(r["delivered"]),
        created_at=r["created_at"],
    )


def _today() -> str:
    return _dt.date.today().isoformat()


def _days_until(target: str | None, today: str) -> int | None:
    if not target:
        return None
    try:
        return (_dt.date.fromisoformat(target)
                - _dt.date.fromisoformat(today)).days
    except ValueError:
        return None


def _student(student_id: str) -> Any:
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        return _students.get_student(student_id)
    except Exception:
        logger.debug("Student lookup failed for %s", student_id,
                      exc_info=True)
        return None


# ── Notice log ────────────────────────────────────────────────────

def record_notice(submission_id: int, *, kind: str,
                   offset_days: int | None = None,
                   level: int | None = None,
                   recipient: str | None = None,
                   channel: str = "Email",
                   detail: str | None = None,
                   delivered: bool = True,
                   sent_on: str | None = None) -> Notice:
    """Log one nudge. The log is what makes the sweeps idempotent."""
    init_db()
    if kind not in NOTICE_KINDS:
        raise ValidationError(
            f"Notice kind must be one of: {', '.join(NOTICE_KINDS)}")
    when = assignments_store._validate_date(sent_on, "Sent on") or _today()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO coursework_notices
                   (submission_id, kind, offset_days, level, recipient,
                    channel, sent_on, detail, delivered, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (submission_id, kind, offset_days, level,
             (recipient or "").strip() or None, channel, when,
             (detail or "").strip() or None, 1 if delivered else 0))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM coursework_notices WHERE notice_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_notice(r)


def list_notices(*, submission_id: int | None = None,
                  assignment_id: int | None = None,
                  kind: str | None = None) -> list[Notice]:
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
    if kind:
        clauses.append("kind = ?")
        args.append(kind)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_notice(r) for r in conn.execute(
            f"SELECT * FROM coursework_notices {where} "
            "ORDER BY notice_id DESC", args).fetchall()]


# ── Set-date publishing (item 35) ─────────────────────────────────

def publish_assignment(assignment_id: int, *,
                        notify: bool = True,
                        published_on: str | None = None
                        ) -> assignments_models.Assignment:
    """Move a Draft assignment to Set and tell the students.

    Publishing is what makes an assignment real to a student, so it is
    a distinct action from saving one.
    """
    init_db()
    a = assignments_store.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    if a.published_on:
        return a
    when = assignments_store._validate_date(published_on, "Published on") or _today()
    out = assignments_store.update_assignment(assignment_id, {
        "status": "Set" if a.status == "Draft" else a.status,
        "published_on": when,
    })
    if notify:
        try:
            assignments_store._notify_students_assignment_created(out)
        except Exception:
            logger.exception(
                "Could not notify students on publishing #%d",
                assignment_id)
    logger.info("Published assignment #%d on %s", assignment_id, when)
    return out


def publish_due(*, today: str | None = None,
                 notify: bool = True) -> SweepResult:
    """Publish every auto-publish assignment whose set date has come.

    Idempotent: ``published_on`` records the fact, so a second run the
    same day publishes nothing again.
    """
    init_db()
    day = assignments_store._validate_date(today, "today") or _today()
    result = SweepResult()
    for a in assignments_store.list_assignments(status="Draft"):
        if not a.auto_publish:
            continue
        result.scanned += 1
        if a.published_on:
            result.skipped += 1
            continue
        if not a.set_date or a.set_date > day:
            continue
        try:
            publish_assignment(a.assignment_id, notify=notify,
                                published_on=day)
            result.actioned += 1
            result.detail.append(f"#{a.assignment_id} {a.title}")
        except Exception as e:                      # pragma: no cover
            logger.exception("Could not publish #%d", a.assignment_id)
            result.failures += 1
            result.detail.append(f"#{a.assignment_id} failed: {e}")
    logger.info("Publish sweep on %s: %s", day, result.message)
    return result


def list_scheduled(*, today: str | None = None
                    ) -> list[assignments_models.Assignment]:
    """Drafts waiting for their set date to arrive."""
    init_db()
    day = assignments_store._validate_date(today, "today") or _today()
    return [a for a in assignments_store.list_assignments(status="Draft")
            if a.auto_publish and not a.published_on
            and a.set_date and a.set_date > day]


# ── Due-date reminders (item 36) ──────────────────────────────────

def reminder_offsets(assignment: assignments_models.Assignment) -> list[int]:
    """The offsets this assignment nudges at, largest first."""
    if assignment.reminder_days:
        return [int(d) for d in assignment.reminder_days.split(",")
                if d.strip().lstrip("-").isdigit()]
    return list(DEFAULT_REMINDER_DAYS)


def _mark_reminder_sent(submission_id: int, offset: int) -> None:
    sub = assignments_store.get_submission(submission_id)
    if sub is None:
        return
    sent = set(sub.reminders_sent_list)
    sent.add(offset)
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET reminders_sent = ?, "
            "updated_at = datetime('now') WHERE submission_id = ?",
            (",".join(str(d) for d in sorted(sent, reverse=True)),
             submission_id))
        conn.commit()


def send_reminder(submission_id: int, *, offset_days: int,
                   notify: bool = True) -> Notice:
    """Nudge one student that a deadline is coming."""
    init_db()
    sub = assignments_store.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    a = assignments_store.get_assignment(sub.assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{sub.assignment_id}")
    due = assignments_submissions.effective_due_date(sub, a)
    delivered = True
    if notify:
        delivered = _email_reminder(sub, a, offset_days=offset_days,
                                     due=due)
    _mark_reminder_sent(submission_id, offset_days)
    return record_notice(
        submission_id, kind="reminder", offset_days=offset_days,
        recipient=sub.student_id, delivered=delivered,
        detail=f"{a.title} due {due or '—'}")


def sweep_reminders(*, today: str | None = None,
                     assignment_id: int | None = None,
                     notify: bool = True,
                     dry_run: bool = False) -> SweepResult:
    """Send every reminder due today, once each.

    A reminder fires when the days remaining is *at or below* the
    offset and that offset has not been sent — so a job that did not
    run for two days still catches up rather than silently skipping.
    """
    init_db()
    day = assignments_store._validate_date(today, "today") or _today()
    result = SweepResult()
    assignments = ([assignments_store.get_assignment(assignment_id)]
                   if assignment_id is not None
                   else assignments_store.list_assignments(open_only=True))
    for a in assignments:
        if a is None or not a.due_date:
            continue
        offsets = reminder_offsets(a)
        if not offsets:
            continue
        for sub in assignments_store.list_submissions(assignment_id=a.assignment_id):
            if sub.is_done or sub.status == "Excused":
                continue
            due = assignments_submissions.effective_due_date(sub, a)
            remaining = _days_until(due, day)
            if remaining is None or remaining < 0:
                continue
            already = set(sub.reminders_sent_list)
            pending = [o for o in offsets
                       if remaining <= o and o not in already]
            if not pending:
                continue
            result.scanned += 1
            # Send only the closest applicable offset, so a catch-up
            # run does not fire three emails at one student.
            offset = min(pending)
            if dry_run:
                result.detail.append(
                    f"{sub.student_id}: T-{offset} on "
                    f"#{a.assignment_id}")
                continue
            try:
                send_reminder(sub.submission_id, offset_days=offset,
                               notify=notify)
                # Any wider offsets that have gone by are marked as
                # spent so they don't fire late.
                for missed in (o for o in pending if o > offset):
                    _mark_reminder_sent(sub.submission_id, missed)
                result.actioned += 1
            except Exception as e:                  # pragma: no cover
                logger.exception("Reminder failed for #%d",
                                  sub.submission_id)
                result.failures += 1
                result.detail.append(str(e))
    logger.info("Reminder sweep on %s: %s", day, result.message)
    return result


def _email_reminder(submission: assignments_models.Submission,
                     assignment: assignments_models.Assignment, *,
                     offset_days: int, due: str | None) -> bool:
    """Best-effort reminder email. Never blocks the sweep."""
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates,
        )
        student = _student(submission.student_id)
        if student is None:
            return False
        email_templates.send_from_template(
            "assignment_reminder",
            {
                "system_name":  SYSTEM_NAME,
                "first_name":   student.first_name,
                "full_name":    student.full_name,
                "student_id":   student.student_id,
                "title":        assignment.title,
                "subject_name": assignment.subject_name,
                "teacher":      assignment.teacher or "your teacher",
                "due_date":     due or "—",
                "days_left":    str(offset_days),
                "status":       submission.status,
                "submission_method": (assignment.submission_method
                                       or "see the portal"),
            },
            to_name=student.full_name,
            to_address=student.email,
            student_id=student.student_id,
        )
        return True
    except Exception:
        logger.exception("Reminder email failed for submission #%d",
                          submission.submission_id)
        return False


# ── Missing-work chasers (item 37) ────────────────────────────────

def chase_level_name(level: int) -> str:
    return next((name for lvl, name, _ in CHASE_LEVELS
                  if lvl == level), "Unknown")


def chase_submission(submission_id: int, *,
                      notify: bool = True,
                      today: str | None = None) -> Notice | None:
    """Escalate one piece of missing work by one step.

    Returns ``None`` once the ladder is exhausted — the system stops
    escalating rather than nagging home indefinitely, at which point a
    human decides what happens next.
    """
    init_db()
    sub = assignments_store.get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    a = assignments_store.get_assignment(sub.assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{sub.assignment_id}")
    day = assignments_store._validate_date(today, "today") or _today()

    next_level = (sub.chase_level or 0) + 1
    if next_level > MAX_CHASE_LEVEL:
        return None

    recipient = chase_level_name(next_level)
    delivered = True
    if notify:
        delivered = _email_chase(sub, a, level=next_level)
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET chase_level = ?, "
            "last_chased_on = ?, updated_at = datetime('now') "
            "WHERE submission_id = ?",
            (next_level, day, submission_id))
        conn.commit()
    logger.info("Chased submission #%d to level %d (%s)",
                submission_id, next_level, recipient)
    return record_notice(
        submission_id, kind="chase", level=next_level,
        recipient=recipient, delivered=delivered, sent_on=day,
        detail=f"{a.title}: {chase_level_name(next_level)} contacted")


def sweep_chasers(*, today: str | None = None,
                   assignment_id: int | None = None,
                   notify: bool = True,
                   dry_run: bool = False) -> SweepResult:
    """Escalate work that is past its deadline and still not in.

    Waits :data:`CHASE_INTERVAL_DAYS` between steps, so a student gets
    a chance to respond to one nudge before the next one goes further
    up the chain.
    """
    init_db()
    day = assignments_store._validate_date(today, "today") or _today()
    result = SweepResult()
    overdue = assignments_integrity.list_overdue_submissions(
        today=day, assignment_id=assignment_id)
    # The sweep also picks up work already written off as Missing —
    # that is precisely the work that needs chasing.
    missing = [s for s in assignments_store.list_submissions(
        assignment_id=assignment_id, status="Missing")]
    seen: set[int] = set()
    for sub in [*overdue, *missing]:
        if sub.submission_id in seen:
            continue
        seen.add(sub.submission_id)
        a = assignments_store.get_assignment(sub.assignment_id)
        if a is None or not a.chase_enabled:
            continue
        result.scanned += 1
        if (sub.chase_level or 0) >= MAX_CHASE_LEVEL:
            result.skipped += 1
            continue
        if sub.last_chased_on:
            # Days elapsed since the last escalation: the sweep date
            # measured from that date, so a positive number means time
            # has passed.
            elapsed = _days_until(day, sub.last_chased_on)
            if elapsed is not None and elapsed < CHASE_INTERVAL_DAYS:
                result.skipped += 1
                continue
        if dry_run:
            result.detail.append(
                f"{sub.student_id}: level "
                f"{(sub.chase_level or 0) + 1} on #{a.assignment_id}")
            continue
        try:
            notice = chase_submission(sub.submission_id, notify=notify,
                                       today=day)
            if notice is None:
                result.skipped += 1
            else:
                result.actioned += 1
                result.detail.append(
                    f"{sub.student_id}: {notice.label}")
        except Exception as e:                      # pragma: no cover
            logger.exception("Chase failed for #%d", sub.submission_id)
            result.failures += 1
            result.detail.append(str(e))
    logger.info("Chase sweep on %s: %s", day, result.message)
    return result


def reset_chase(submission_id: int) -> assignments_models.Submission:
    """Clear the escalation state, e.g. after the work comes in."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE coursework_submissions SET chase_level = 0, "
            "last_chased_on = NULL, updated_at = datetime('now') "
            "WHERE submission_id = ?", (submission_id,))
        conn.commit()
    out = assignments_store.get_submission(submission_id)
    if out is None:
        raise ValidationError(f"No submission #{submission_id}")
    return out


def escalation_report(*, assignment_id: int | None = None
                       ) -> list[tuple[assignments_models.Submission, str]]:
    """Everyone currently somewhere up the chasing ladder."""
    init_db()
    out = []
    for sub in assignments_store.list_submissions(assignment_id=assignment_id):
        if not sub.chase_level:
            continue
        out.append((sub, chase_level_name(sub.chase_level)))
    return sorted(out, key=lambda pair: -pair[0].chase_level)


def _email_chase(submission: assignments_models.Submission,
                  assignment: assignments_models.Assignment, *, level: int) -> bool:
    """Best-effort chaser email to whoever this level targets."""
    try:
        from education_system.systems.sixth_form import SYSTEM_NAME
        from education_system.systems.sixth_form.domains.communications.domain.messages import (
            email_templates,
        )
        student = _student(submission.student_id)
        if student is None:
            return False
        to_address = student.email
        to_name = student.full_name
        if level >= 3:
            contact = _guardian_contact(submission.student_id)
            if contact:
                to_name, to_address = contact
        email_templates.send_from_template(
            "assignment_missing_work",
            {
                "system_name":  SYSTEM_NAME,
                "first_name":   student.first_name,
                "full_name":    student.full_name,
                "student_id":   student.student_id,
                "title":        assignment.title,
                "subject_name": assignment.subject_name,
                "teacher":      assignment.teacher or "the teacher",
                "due_date":     (assignments_submissions.effective_due_date(
                    submission, assignment) or "—"),
                "level":        str(level),
                "level_name":   chase_level_name(level),
            },
            to_name=to_name,
            to_address=to_address,
            student_id=student.student_id,
        )
        return True
    except Exception:
        logger.exception("Chase email failed for submission #%d",
                          submission.submission_id)
        return False


def _guardian_contact(student_id: str) -> tuple[str, str] | None:
    """Best guardian to write to, if one is recorded.

    Prefers a contact flagged to receive communications, then the
    primary contact, so a chaser goes to whoever the college has
    already agreed to contact rather than the first row in the table.
    """
    try:
        from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
            parent_contacts as _contacts,
        )
        candidates = _contacts.list_contacts(student_id=student_id)
        ranked = sorted(
            (c for c in candidates if c.email),
            key=lambda c: (not getattr(c, "receives_communications",
                                        True),
                            not c.is_primary))
        for contact in ranked:
            if not contact.email:
                continue
            name = " ".join(filter(None, [contact.first_name,
                                           contact.last_name])).strip()
            return (name or "Parent/Guardian", contact.email)
    except Exception:
        logger.debug("No guardian contact available for %s",
                      student_id, exc_info=True)
    return None


# ── Parent portal visibility (item 38) ────────────────────────────

def parent_view(student_id: str, *,
                 include_marks: bool = True,
                 limit: int | None = None,
                 today: str | None = None
                 ) -> list[ParentAssignmentView]:
    """A guardian-safe list of one student's coursework.

    Shows what was set and whether it went in. Marks and feedback only
    appear once released — a parent must not see a result before the
    student does, and an assignment flagged not parent-visible never
    appears at all.
    """
    init_db()
    day = assignments_store._validate_date(today, "today") or _today()
    out: list[ParentAssignmentView] = []
    for sub in assignments_store.list_submissions(student_id=str(student_id).strip()):
        a = assignments_store.get_assignment(sub.assignment_id)
        if a is None or not a.parent_visible:
            continue
        if a.status == "Draft" and not a.published_on:
            continue        # not yet issued to anyone
        due = assignments_submissions.effective_due_date(sub, a)
        overdue = bool(due and due < day)
        view = ParentAssignmentView(
            assignment_id=a.assignment_id, title=a.title,
            subject_name=a.subject_name,
            assignment_type=a.assignment_type, teacher=a.teacher,
            set_date=a.set_date, due_date=due, status=sub.status,
            submitted=sub.is_done, submitted_on=sub.submitted_on,
            is_late=sub.status == "Late",
            is_missing=(sub.status == "Missing"
                         or (overdue and not sub.is_done)),
            max_marks=a.max_marks)
        if include_marks:
            try:
                from education_system.systems.sixth_form.domain.academics.assignments import (
                    assignments_feedback as _feedback,
                )
                if _feedback.is_visible_to_student(sub, a, today=day):
                    view.marks = sub.marks
                    view.grade = sub.grade
                    view.feedback_available = bool(sub.feedback)
            except Exception:
                logger.debug("Release state unavailable for #%d",
                              sub.submission_id, exc_info=True)
        out.append(view)
    out.sort(key=lambda v: (v.due_date or "9999-12-31"), reverse=True)
    return out[:limit] if limit else out


def parent_summary(student_id: str, *,
                    today: str | None = None) -> dict[str, Any]:
    """Counts a guardian dashboard can show at a glance."""
    rows = parent_view(student_id, today=today)
    return {
        "total": len(rows),
        "handed_in": sum(1 for r in rows if r.submitted),
        "missing": sum(1 for r in rows if r.is_missing),
        "late": sum(1 for r in rows if r.is_late),
        "marked": sum(1 for r in rows if r.marks is not None),
        "awaiting": sum(1 for r in rows
                         if not r.submitted and not r.is_missing),
    }


def set_parent_visibility(assignment_id: int, *,
                           visible: bool) -> assignments_models.Assignment:
    """Hide or show one assignment from guardians."""
    init_db()
    if assignments_store.get_assignment(assignment_id) is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    return assignments_store.update_assignment(assignment_id,
                                   {"parent_visible": visible})


# ── Calendar integration (item 39) ────────────────────────────────

def push_to_calendar(assignment_id: int, *,
                     year_id: int | None = None) -> int | None:
    """Put an assignment's deadline in the academic-year calendar.

    Returns the calendar event id, or ``None`` when there is nothing to
    place — no due date, or no academic year covering it. Idempotent:
    an assignment already on the calendar is left alone.
    """
    init_db()
    a = assignments_store.get_assignment(assignment_id)
    if a is None:
        raise ValidationError(f"No assignment #{assignment_id}")
    if not a.due_date:
        return None
    if a.calendar_event_id:
        return a.calendar_event_id
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (
            academic_year as _ay,
        )
        target_year = year_id
        if target_year is None:
            for year in _ay.list_years():
                if year.start_date <= a.due_date <= year.end_date:
                    target_year = year.year_id
                    break
        if target_year is None:
            logger.info(
                "No academic year covers %s — assignment #%d not "
                "added to the calendar", a.due_date, assignment_id)
            return None
        event = _ay.create_event({
            "year_id": target_year,
            "name": f"{a.subject_name}: {a.title} due",
            "kind": (CALENDAR_EVENT_KIND
                      if CALENDAR_EVENT_KIND in _ay.EVENT_KINDS
                      else _ay.DEFAULT_EVENT_KIND),
            "date": a.due_date,
            "notes": (f"Coursework deadline for assignment "
                      f"#{assignment_id}"
                      + (f" ({a.teacher})" if a.teacher else "")),
        })
        assignments_store.update_assignment(assignment_id,
                                {"calendar_event_id": event.event_id})
        logger.info("Assignment #%d added to the calendar as event #%d",
                    assignment_id, event.event_id)
        return event.event_id
    except Exception:
        logger.exception(
            "Could not add assignment #%d to the calendar",
            assignment_id)
        return None


def remove_from_calendar(assignment_id: int) -> bool:
    """Take an assignment's deadline back off the calendar."""
    init_db()
    a = assignments_store.get_assignment(assignment_id)
    if a is None or not a.calendar_event_id:
        return False
    try:
        from education_system.systems.sixth_form.domain.academics.academic_year import (
            academic_year as _ay,
        )
        _ay.delete_event(a.calendar_event_id)
    except Exception:
        logger.exception("Could not delete calendar event #%s",
                          a.calendar_event_id)
    assignments_store.update_assignment(assignment_id, {"calendar_event_id": None})
    return True


def sync_calendar(*, assignment_id: int | None = None,
                   open_only: bool = True) -> SweepResult:
    """Put every dated assignment on the calendar."""
    init_db()
    result = SweepResult()
    assignments = ([assignments_store.get_assignment(assignment_id)]
                   if assignment_id is not None
                   else assignments_store.list_assignments(open_only=open_only))
    for a in assignments:
        if a is None or not a.due_date:
            continue
        result.scanned += 1
        if a.calendar_event_id:
            result.skipped += 1
            continue
        event_id = push_to_calendar(a.assignment_id)
        if event_id:
            result.actioned += 1
            result.detail.append(f"#{a.assignment_id} → event {event_id}")
        else:
            # No academic year covers the due date. That is a gap in
            # the calendar's setup, not a failure of this sweep, so it
            # is reported rather than counted as an error.
            result.skipped += 1
            result.detail.append(
                f"#{a.assignment_id} ({a.due_date}) is outside every "
                f"academic year — no calendar entry made")
    logger.info("Calendar sync: %s", result.message)
    return result


def deadline_clashes(*, year_group: str | None = None,
                      window_days: int = 7) -> list[dict[str, Any]]:
    """Weeks where a year group faces several deadlines at once.

    Not a rule — sometimes a busy week is unavoidable — but a head of
    year should be able to see it before the students do.
    """
    init_db()
    buckets: dict[str, list[assignments_models.Assignment]] = {}
    for a in assignments_store.list_assignments(year_group=year_group,
                                    open_only=True):
        if not a.due_date:
            continue
        try:
            due = _dt.date.fromisoformat(a.due_date)
        except ValueError:
            continue
        key = (due - _dt.timedelta(days=due.weekday())).isoformat()
        buckets.setdefault(key, []).append(a)
    out = []
    for week, rows in sorted(buckets.items()):
        if len(rows) < 2:
            continue
        out.append({
            "week_start": week,
            "count": len(rows),
            "subjects": sorted({a.subject_name for a in rows}),
            "assignments": [(a.assignment_id, a.title, a.due_date)
                             for a in rows],
        })
    return out


# ── The daily job ─────────────────────────────────────────────────

def run_daily(*, today: str | None = None,
               notify: bool = True) -> dict[str, SweepResult]:
    """Everything a scheduler should call once a morning.

    Ordered deliberately: publish first (so a newly-live assignment can
    be reminded about), then the late sweep, then reminders, then
    chasers — a student is never chased for work they were never told
    about.
    """
    init_db()
    day = assignments_store._validate_date(today, "today") or _today()
    results: dict[str, SweepResult] = {}
    results["published"] = publish_due(today=day, notify=notify)

    late = assignments_integrity.sweep_late_submissions(today=day)
    results["marked_missing"] = SweepResult(
        scanned=late["overdue"], actioned=late["marked_missing"])

    results["reminders"] = sweep_reminders(today=day, notify=notify)
    results["chasers"] = sweep_chasers(today=day, notify=notify)
    results["calendar"] = sync_calendar()

    logger.info("Daily coursework job for %s: %s", day,
                "; ".join(f"{k}: {v.message}"
                          for k, v in results.items()))
    return results
