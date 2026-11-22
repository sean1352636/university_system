"""Exit interviews for learners who withdraw early (retention).

One table, ``exit_interviews``: why the learner left (a primary reason
category plus any others), where they are going, what could have helped
them stay, whether staff think they could have been retained, who
interviewed them, when and how.

Started from a withdrawal: :func:`start_from_withdrawal` opens a
*Pending* interview (one per withdrawal — calling it again for the same
leaving date returns the existing one), with the year group and tutor
group snapshotted from the learner's enrolment and the free-text reason
given at withdrawal. ``students.withdraw_student`` calls it best-effort,
so every withdrawal lands on the pending list. An interview can also be
created by hand (e.g. for a withdrawal recorded before this existed).

Reports: the pending list, and :func:`reasons_summary` — counts by
primary reason, all reasons, destination, what would have helped, year
group, month, and the share judged retainable — the retention evidence
for the self-assessment report.

Access: PASTORAL or STUDENTS_MANAGE, and the object-level
``can_see_student``; reads and writes go to the sensitive-access log.
The automatic start from a withdrawal is a system action (it holds no
interview content yet) and needs no capability.
Interviews reference the student with ``ON DELETE RESTRICT``.
"""

from __future__ import annotations

import datetime as _dt
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.pastoral import _people, _records
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB
AREA = "exit_interviews"

PENDING = "Pending"
COMPLETED = "Completed"
STATUSES: tuple[str, ...] = (PENDING, COMPLETED, "Declined",
                             "Unable to contact")
REASONS: tuple[str, ...] = (
    "Wrong course / subjects", "Academic difficulty", "Employment",
    "Apprenticeship", "Transferred to another provider", "Financial",
    "Physical health", "Mental health", "Family / caring responsibilities",
    "Moved away", "Travel / transport", "Attendance",
    "Behaviour / exclusion", "Pregnancy / parenthood",
    "Bullying / peer issues", "Teaching or support quality",
    "Personal reasons", "Other",
)
DESTINATIONS: tuple[str, ...] = (
    "Employment", "Apprenticeship", "Another sixth form / school",
    "FE college", "Traineeship / training", "Higher education",
    "Volunteering", "Gap year", "NEET", "Moved away", "Unknown", "Other",
)
HELP_OPTIONS: tuple[str, ...] = (
    "Better advice before enrolment", "Different subject combination",
    "Earlier academic support", "Financial support / bursary",
    "Wellbeing / counselling", "Mentoring", "Flexible timetable",
    "Transport help", "Careers guidance", "Earlier contact with home",
    "Nothing - leaving was right", "Other",
)
RETAINABLE: tuple[str, ...] = ("Yes", "Possibly", "No")
METHODS: tuple[str, ...] = ("In person", "Phone", "Video call",
                            "Questionnaire", "Other")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exit_interviews (
    interview_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            TEXT NOT NULL,
    withdrawal_date       TEXT NOT NULL,
    withdrawal_reason     TEXT,
    year_group            INTEGER,
    tutor_group           TEXT,
    status                TEXT NOT NULL DEFAULT 'Pending',
    primary_reason        TEXT,
    other_reasons         TEXT,
    reason_detail         TEXT,
    destination           TEXT,
    destination_detail    TEXT,
    what_could_have_helped TEXT,
    help_categories       TEXT,
    retainable            TEXT,
    interviewer_staff_id  TEXT,
    interviewer_name      TEXT,
    interview_date        TEXT,
    method                TEXT,
    notes                 TEXT,
    created_by            TEXT,
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, withdrawal_date),
    FOREIGN KEY (student_id) REFERENCES students(student_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (interviewer_staff_id) REFERENCES staff(staff_id)
        ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_exit_status ON exit_interviews(status);
CREATE INDEX IF NOT EXISTS idx_exit_date   ON exit_interviews(withdrawal_date);
"""


class ValidationError(ValueError):
    pass


@dataclass
class ExitInterview:
    interview_id: int
    student_id: str
    withdrawal_date: str
    withdrawal_reason: str | None
    year_group: int | None
    tutor_group: str | None
    status: str
    primary_reason: str | None
    other_reasons: str | None
    reason_detail: str | None
    destination: str | None
    destination_detail: str | None
    what_could_have_helped: str | None
    help_categories: str | None
    retainable: str | None
    interviewer_staff_id: str | None
    interviewer_name: str | None
    interview_date: str | None
    method: str | None
    notes: str | None
    created_by: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def reasons(self) -> list[str]:
        out = [self.primary_reason] if self.primary_reason else []
        out += [r for r in split_list(self.other_reasons) if r not in out]
        return out

    @property
    def helps(self) -> list[str]:
        return split_list(self.help_categories)


_C = _records.Col

SPEC = _records.TableSpec(
    table="exit_interviews", id_col="interview_id", row_type=ExitInterview,
    label="Exit interview",
    order_by="status <> 'Pending', withdrawal_date DESC, interview_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("withdrawal_date", "Withdrew on", "date", required=True,
           default=_records.today),
        _C("withdrawal_reason", "Reason given at withdrawal", listed=False),
        _C("year_group", "Year group", "int", min_value=12, max_value=14),
        _C("tutor_group", "Tutor group", listed=False),
        _C("status", "Status", "choice", choices=STATUSES, default=PENDING),
        _C("primary_reason", "Main reason", "choice", choices=REASONS),
        _C("other_reasons", "Other reasons (comma-separated)", listed=False),
        _C("reason_detail", "In their words", "multiline", listed=False),
        _C("destination", "Destination", "choice", choices=DESTINATIONS),
        _C("destination_detail", "Provider / employer", listed=False),
        _C("what_could_have_helped", "What could have helped", "multiline",
           listed=False),
        _C("help_categories", "Would have helped (comma-separated)",
           listed=False),
        _C("retainable", "Could we have kept them?", "choice",
           choices=RETAINABLE),
        _C("interviewer_staff_id", "Interviewer (staff)", listed=False),
        _C("interviewer_name", "Interviewer"),
        _C("interview_date", "Interview date", "date"),
        _C("method", "Method", "choice", choices=METHODS, listed=False),
        _C("notes", "Notes", "multiline", listed=False),
        _C("created_by", "Created by", hidden=True),
    ))


def split_list(v: str | None) -> list[str]:
    return [s.strip() for s in (v or "").split(",") if s.strip()]


def _check_list(v: Any, options: tuple[str, ...], label: str) -> str | None:
    items = v if isinstance(v, (list, tuple)) else split_list(v)
    out = []
    for item in items:
        match = next((o for o in options if o.lower() == str(item).lower()),
                     None)
        if match is None:
            raise ValidationError(f"{label}: '{item}' is not one of: "
                                  f"{', '.join(options)}")
        if match not in out:
            out.append(match)
    return ", ".join(out) or None


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    from education_system.systems.sixth_form.domain.staff import staff as _staff
    _students.init_db()
    _staff.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _access():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access


def _guard(action: str, student_id: str | None = None,
           ref: str | None = None) -> Any:
    """PASTORAL or STUDENTS_MANAGE, then the object check; logged."""
    a = _access()
    p = a.current()
    cap = a.PASTORAL if p.can(a.PASTORAL) else a.STUDENTS_MANAGE
    if not p.can(cap):
        a.log_sensitive_access(p, AREA, action, student_id=student_id,
                               record_ref=ref, allowed=False)
        p.require(a.PASTORAL, "exit interviews")
    if student_id and not a.can_see_student(p, student_id, capability=cap):
        a.log_sensitive_access(p, AREA, action, student_id=student_id,
                               record_ref=ref, allowed=False)
        raise a.AccessDenied(f"{p.username or 'This account'} may not see "
                             f"exit interviews for student {student_id}.")
    a.log_sensitive_access(p, AREA, action, student_id=student_id,
                           record_ref=ref)
    return p


def _visible(rows: list[Any]) -> list[Any]:
    a = _access()
    p = a.current()
    cap = a.PASTORAL if p.can(a.PASTORAL) else a.STUDENTS_MANAGE
    cache: dict[str, bool] = {}
    out = []
    for r in rows:
        if r.student_id not in cache:
            cache[r.student_id] = a.can_see_student(p, r.student_id,
                                                    capability=cap)
        if cache[r.student_id]:
            out.append(r)
    return out


def _rules(p: dict[str, Any]) -> None:
    today = _records.today()
    if p["withdrawal_date"] > today:
        raise ValidationError("Withdrew on cannot be in the future")
    p["other_reasons"] = _check_list(p["other_reasons"], REASONS,
                                     "Other reasons")
    p["help_categories"] = _check_list(p["help_categories"], HELP_OPTIONS,
                                       "Would have helped")
    p["interviewer_staff_id"] = _people.check_staff(
        p["interviewer_staff_id"], "Interviewer", ValidationError)
    if p["interviewer_staff_id"] and not p["interviewer_name"]:
        p["interviewer_name"] = _people.staff_name(p["interviewer_staff_id"])
    if p["interview_date"]:
        if p["interview_date"] > today:
            raise ValidationError("Interview date cannot be in the future")
    if p["status"] == COMPLETED:
        missing = [lbl for k, lbl in (("primary_reason", "main reason"),
                                      ("destination", "destination"),
                                      ("interview_date", "interview date"))
                   if not p[k]]
        if missing:
            raise ValidationError("A completed interview needs: "
                                  + ", ".join(missing))


def _snapshot(student_id: str) -> tuple[int | None, str | None]:
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolments as _enr,
        )
        e = _enr.current_enrolment(student_id)
        if e is not None:
            return e.year_group, e.tutor_group
    except Exception:
        logger.exception("Could not read the enrolment of %s", student_id)
    return None, None


def _fetch(interview_id: int) -> ExitInterview | None:
    with _connect() as conn:
        return _records.fetch(conn, SPEC, int(interview_id))


# ── Start / CRUD ────────────────────────────────────────────────────

def start_from_withdrawal(student_id: str, *,
                          withdrawal_date: str | None = None,
                          reason: str | None = None) -> ExitInterview:
    """Open a pending exit interview for a withdrawal (idempotent per
    student + leaving date). Called by ``students.withdraw_student``."""
    init_db()
    if not _people.student_exists(student_id):
        raise ValidationError(f"No student with id {student_id}")
    day = _records.check_date(withdrawal_date, "Withdrew on",
                              ValidationError) or _records.today()
    with _connect() as conn:
        r = conn.execute("SELECT interview_id FROM exit_interviews WHERE "
                         "student_id = ? AND withdrawal_date = ?",
                         (student_id, day)).fetchone()
        if r is not None:
            return _records.fetch(conn, SPEC, r[0])
        yg, tg = _snapshot(student_id)
        new_id = _records.insert(conn, SPEC, {
            "student_id": student_id, "withdrawal_date": day,
            "withdrawal_reason": (reason or "").strip() or None,
            "year_group": yg, "tutor_group": tg, "status": PENDING,
            "created_by": _records.current_username() or "withdrawal"})
        out = _records.fetch(conn, SPEC, new_id)
    p = _access().current()
    _access().log_sensitive_access(p, AREA, "start exit interview",
                                   student_id=student_id,
                                   record_ref=f"exit:{new_id}")
    logger.info("Exit interview #%d opened for %s (withdrew %s)", new_id,
                student_id, day)
    return out


def on_withdrawal(student_id: str, withdrawal_date: str | None,
                  reason: str | None) -> ExitInterview | None:
    """Hook for ``students.withdraw_student``: open the pending interview,
    best-effort — a failure is logged and never blocks the withdrawal."""
    try:
        return start_from_withdrawal(student_id,
                                     withdrawal_date=withdrawal_date,
                                     reason=reason)
    except Exception:
        logger.exception("Could not open an exit interview for %s",
                         student_id)
        return None


def create_interview(data: dict[str, Any]) -> ExitInterview:
    init_db()
    v = _records.validate(SPEC, data, error=ValidationError,
                          student_exists=_people.student_exists)
    _rules(v)
    actor = _guard("create exit interview", v["student_id"])
    if v["year_group"] is None and v["tutor_group"] is None:
        v["year_group"], v["tutor_group"] = _snapshot(v["student_id"])
    v["created_by"] = actor.staff_name or actor.username
    with _connect() as conn:
        try:
            new_id = _records.insert(conn, SPEC, v)
        except _sql.IntegrityError:
            raise ValidationError(
                "There is already an exit interview for this student and "
                "leaving date") from None
    return _fetch(new_id)


def get_interview(interview_id: int) -> ExitInterview | None:
    init_db()
    r = _fetch(interview_id)
    if r is not None:
        _guard("view exit interview", r.student_id, f"exit:{interview_id}")
    return r


def update_interview(interview_id: int, data: dict[str, Any]
                     ) -> ExitInterview:
    init_db()
    existing = _fetch(interview_id)
    if existing is None:
        raise ValidationError(f"No exit interview #{interview_id}")
    v = _records.validate(SPEC, data, error=ValidationError,
                          existing=existing)
    _rules(v)
    _guard("update exit interview", existing.student_id,
           f"exit:{interview_id}")
    with _connect() as conn:
        try:
            _records.update(conn, SPEC, interview_id, v)
        except _sql.IntegrityError:
            raise ValidationError(
                "There is already an exit interview for this student and "
                "leaving date") from None
    return _fetch(interview_id)


def delete_interview(interview_id: int) -> bool:
    init_db()
    existing = _fetch(interview_id)
    if existing is None:
        return False
    _guard("delete exit interview", existing.student_id,
           f"exit:{interview_id}")
    if existing.status == COMPLETED:
        raise ValidationError("A completed exit interview is retention "
                              "evidence and cannot be deleted")
    with _connect() as conn:
        return _records.delete(conn, SPEC, interview_id)


def list_interviews(*, student_id: str | None = None,
                    status: str | None = None,
                    date_from: str | None = None,
                    date_to: str | None = None,
                    primary_reason: str | None = None) -> list[ExitInterview]:
    init_db()
    _guard("list exit interviews", student_id)
    where, args = [], []
    if date_from:
        where.append("withdrawal_date >= ?")
        args.append(_records.check_date(date_from, "From", ValidationError))
    if date_to:
        where.append("withdrawal_date <= ?")
        args.append(_records.check_date(date_to, "To", ValidationError))
    with _connect() as conn:
        rows = _records.select(conn, SPEC, equals={
            "student_id": student_id, "status": status,
            "primary_reason": primary_reason}, where=where, args=args)
    return _visible(rows)


def pending_interviews() -> list[ExitInterview]:
    return list_interviews(status=PENDING)


# ── Summary report ──────────────────────────────────────────────────

def current_academic_year(today: _dt.date | None = None) -> str:
    d = today or _dt.date.today()
    start = d.year if d.month >= 9 else d.year - 1
    return f"{start}/{(start + 1) % 100:02d}"


def academic_year_bounds(year: str) -> tuple[str, str]:
    """``2025/26`` → ("2025-09-01", "2026-08-31")."""
    try:
        start = int(year.split("/")[0])
    except (ValueError, AttributeError):
        raise ValidationError("Academic year must look like 2025/26") from None
    return f"{start}-09-01", f"{start + 1}-08-31"


@dataclass
class ReasonsSummary:
    date_from: str | None
    date_to: str | None
    withdrawals: int = 0
    by_status: dict[str, int] = field(default_factory=dict)
    by_primary_reason: dict[str, int] = field(default_factory=dict)
    by_any_reason: dict[str, int] = field(default_factory=dict)
    by_destination: dict[str, int] = field(default_factory=dict)
    by_help: dict[str, int] = field(default_factory=dict)
    by_year_group: dict[str, int] = field(default_factory=dict)
    by_month: dict[str, int] = field(default_factory=dict)
    by_retainable: dict[str, int] = field(default_factory=dict)
    neet: int = 0

    @property
    def completed(self) -> int:
        return self.by_status.get(COMPLETED, 0)

    @property
    def completion_rate(self) -> float:
        return (100.0 * self.completed / self.withdrawals
                if self.withdrawals else 0.0)

    def lines(self) -> list[str]:
        span = (f"{self.date_from or 'start'} to {self.date_to or 'today'}")
        out = [f"Withdrawal reasons — {span}", "",
               f"  Withdrawals with an exit record: {self.withdrawals}",
               f"  Interviews completed:            {self.completed} "
               f"({self.completion_rate:.0f}%)",
               f"  Leaving to NEET:                 {self.neet}", ""]

        def block(title: str, d: dict[str, int], base: int) -> None:
            out.append(f"  {title}:")
            if not d:
                out.append("    (none)")
            for k, n in sorted(d.items(), key=lambda kv: (-kv[1], kv[0])):
                pct = f"{100.0 * n / base:4.0f}%" if base else ""
                out.append(f"    {k:<40} {n:>4}  {pct}")
            out.append("")

        done = self.completed
        block("Status", self.by_status, self.withdrawals)
        block("Main reason (completed interviews)", self.by_primary_reason,
              done)
        block("Any reason given", self.by_any_reason, done)
        block("Destination", self.by_destination, done)
        block("What would have helped", self.by_help, done)
        block("Could we have kept them?", self.by_retainable, done)
        block("Year group", self.by_year_group, self.withdrawals)
        block("Month of withdrawal", dict(sorted(self.by_month.items())),
              self.withdrawals)
        return out


def reasons_summary(*, date_from: str | None = None,
                    date_to: str | None = None,
                    academic_year: str | None = None) -> ReasonsSummary:
    """Retention summary over withdrawals in the window."""
    if academic_year:
        date_from, date_to = academic_year_bounds(academic_year)
    rows = list_interviews(date_from=date_from, date_to=date_to)
    s = ReasonsSummary(date_from, date_to, withdrawals=len(rows))

    def bump(d: dict[str, int], k: str | None) -> None:
        if k:
            d[k] = d.get(k, 0) + 1

    for r in rows:
        bump(s.by_status, r.status)
        bump(s.by_year_group, f"Year {r.year_group}" if r.year_group
             else "Unknown")
        bump(s.by_month, r.withdrawal_date[:7])
        if r.status != COMPLETED:
            continue
        bump(s.by_primary_reason, r.primary_reason)
        for reason in r.reasons:
            bump(s.by_any_reason, reason)
        bump(s.by_destination, r.destination)
        for h in r.helps:
            bump(s.by_help, h)
        bump(s.by_retainable, r.retainable)
        s.neet += r.destination == "NEET"
    return s


def days_since_withdrawal(r: ExitInterview) -> int:
    return (_dt.date.today() - _dt.date.fromisoformat(r.withdrawal_date)).days
