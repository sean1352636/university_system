"""Planned-absence requests for the Sixth Form System.

Sibling to :mod:`attendance`. Some absence is known about weeks in
advance: a university open day, an apprenticeship interview, a driving
test, a family wedding. Handled as ordinary absence it arrives as an
unexplained mark that somebody recodes afterwards, which is backwards —
the college agreed to it beforehand.

So leave is *requested*, *decided*, and only then *marked*. Three
consequences worth having:

* **Notice.** A request carries how much warning it gave, and
  :data:`NOTICE_DAYS` sets what the college expects. Late requests are
  not refused — a driving test cancellation does not respect policy —
  but they are visibly late.
* **A budget.** Leave of the discretionary kinds counts against a
  yearly allowance (:func:`leave_used`), so "I only asked twice" can be
  checked rather than argued about.
* **Clash detection.** :func:`clashes` looks for exam sittings and
  assessment deadlines inside the requested span, because the one
  question worth asking before approving a holiday in May is whether
  the learner is sitting a paper that week.

Approving writes the marks across every timetabled lesson in the span,
with the code the leave kind implies — `C` for an open day, `H` for an
agreed holiday, `B` for anything the college itself arranged.

**Relationship to :mod:`pastoral.absence_requests`.** That module is the
pastoral team's record that a request was made and answered; it does not
touch the register. This one is the attendance engine — notice, clashes,
allowance, and the marks themselves. :func:`adopt_pastoral_request`
pulls one across so nobody types the same holiday twice.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_codes as codes,
    attendance_register as reg,
    attendance_weeks as weeks,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# (kind, code, counts_against_allowance, description)
LEAVE_KINDS: tuple[tuple[str, str, bool, str], ...] = (
    ("University open day", "C", False,
     "Visiting a university. Educational, and the college encourages it."),
    ("Interview", "C", False,
     "University, apprenticeship or employment interview."),
    ("Audition or trial", "C", False,
     "Conservatoire audition, sports trial or similar."),
    ("Driving test", "C", True,
     "A driving test, which cannot be booked outside college hours."),
    ("Medical appointment", "M", False,
     "An appointment that could not be made outside college hours."),
    ("Religious observance", "R", False,
     "A day set apart for religious observance."),
    ("Family holiday", "H", True,
     "Leave of absence agreed in advance. Discretionary."),
    ("Family event", "C", True,
     "A wedding, a significant family occasion."),
    ("Bereavement", "C", False,
     "Compassionate leave."),
    ("College activity", "B", False,
     "Something the college itself arranged — a trip, a competition."),
    ("Other", "C", True, "Anything else, decided case by case."),
)
KIND_INDEX: dict[str, tuple[str, str, bool, str]] = {
    kind: row for row in LEAVE_KINDS for kind in (row[0],)
}
KINDS: tuple[str, ...] = tuple(row[0] for row in LEAVE_KINDS)
DEFAULT_KIND: str = "Other"

REQUESTED: str = "Requested"
APPROVED: str = "Approved"
DECLINED: str = "Declined"
WITHDRAWN: str = "Withdrawn"
CANCELLED: str = "Cancelled"
STATES: tuple[str, ...] = (REQUESTED, APPROVED, DECLINED, WITHDRAWN,
                           CANCELLED)

# Working days of notice the college asks for.
NOTICE_DAYS: int = 10

# Discretionary leave days a learner may be granted in an academic year
# before it needs a conversation above tutor level.
ANNUAL_ALLOWANCE_DAYS: int = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_leave_requests (
    request_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    date_from     TEXT NOT NULL,
    date_to       TEXT NOT NULL,
    kind          TEXT NOT NULL DEFAULT 'Other',
    detail        TEXT,
    destination   TEXT,
    requested_by  TEXT,
    requested_at  TEXT DEFAULT (datetime('now')),
    notice_days   INTEGER,
    state         TEXT NOT NULL DEFAULT 'Requested',
    code          TEXT,
    decided_by    TEXT,
    decided_at    TEXT,
    decision_note TEXT,
    marks_written INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_leave_state
    ON attendance_leave_requests(state);
CREATE INDEX IF NOT EXISTS idx_att_leave_student
    ON attendance_leave_requests(student_id, date_from);
CREATE INDEX IF NOT EXISTS idx_att_leave_dates
    ON attendance_leave_requests(date_from, date_to);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class LeaveRequest:
    """One request for planned absence."""

    request_id: int
    student_id: str
    date_from: str
    date_to: str
    kind: str
    detail: str | None
    destination: str | None
    requested_by: str | None
    requested_at: str | None
    notice_days: int | None
    state: str
    code: str | None
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    marks_written: int
    student_name: str | None = None

    @property
    def days(self) -> int:
        return (_dt.date.fromisoformat(self.date_to)
                - _dt.date.fromisoformat(self.date_from)).days + 1

    @property
    def is_pending(self) -> bool:
        return self.state == REQUESTED

    @property
    def is_live(self) -> bool:
        return self.state in (REQUESTED, APPROVED)

    @property
    def short_notice(self) -> bool:
        return self.notice_days is not None and self.notice_days < NOTICE_DAYS

    @property
    def counts_against_allowance(self) -> bool:
        row = KIND_INDEX.get(self.kind)
        return bool(row and row[2])

    @property
    def span(self) -> str:
        return (self.date_from if self.date_from == self.date_to
                else f"{self.date_from} → {self.date_to}")

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        notice = " ⚠ short notice" if self.short_notice else ""
        return f"{who} · {self.span} · {self.kind}{notice}"


@dataclass
class Clash:
    """Something already in the diary during the requested span."""

    date: str
    what: str
    detail: str | None = None

    @property
    def label(self) -> str:
        return f"{self.date}: {self.what}" + (f" ({self.detail})"
                                              if self.detail else "")


@dataclass
class LeaveAllowance:
    """How much discretionary leave a learner has had this year."""

    student_id: str
    used_days: int
    allowance: int
    year_from: str
    year_to: str

    @property
    def remaining(self) -> int:
        return max(0, self.allowance - self.used_days)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0


@dataclass
class ApplyResult:
    request_id: int
    marks_written: int
    dates: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


# ── DB plumbing ─────────────────────────────────────────────────────

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
    reg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Leave-request schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> LeaveRequest:
    return LeaveRequest(
        request_id=r["request_id"], student_id=r["student_id"],
        date_from=r["date_from"], date_to=r["date_to"], kind=r["kind"],
        detail=r["detail"], destination=r["destination"],
        requested_by=r["requested_by"], requested_at=r["requested_at"],
        notice_days=r["notice_days"], state=r["state"], code=r["code"],
        decided_by=r["decided_by"], decided_at=r["decided_at"],
        decision_note=r["decision_note"], marks_written=r["marks_written"])


# ── Validation ──────────────────────────────────────────────────────

def validate_kind(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return DEFAULT_KIND
    for kind in KINDS:
        if s.lower() == kind.lower():
            return kind
    raise ValidationError(f"Kind must be one of: {', '.join(KINDS)}")


def code_for_kind(kind: str) -> str:
    """The mark an approved leave of this kind earns."""
    row = KIND_INDEX.get(validate_kind(kind))
    return row[1] if row else "C"


def describe_kind(kind: str) -> str:
    row = KIND_INDEX.get(validate_kind(kind))
    return row[3] if row else ""


# ── Requesting ──────────────────────────────────────────────────────

def request_leave(
    student_id: str,
    date_from: str,
    *,
    date_to: str | None = None,
    kind: str = DEFAULT_KIND,
    detail: str | None = None,
    destination: str | None = None,
    requested_by: str | None = None,
    on: str | None = None,
) -> LeaveRequest:
    """Ask for planned absence. Writes no mark until it is approved."""
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    date_from = core._validate_date(date_from)
    date_to = core._validate_date(date_to or date_from)
    if date_to < date_from:
        raise ValidationError("Leave cannot end before it starts")
    if (_dt.date.fromisoformat(date_to)
            - _dt.date.fromisoformat(date_from)).days > 60:
        raise ValidationError(
            "Request at most two months at a time — a longer absence is a "
            "change of circumstances, not leave")
    kind = validate_kind(kind)
    today = core._validate_date(on or _dt.date.today().isoformat())
    notice = (_dt.date.fromisoformat(date_from)
              - _dt.date.fromisoformat(today)).days

    overlapping = [r for r in list_requests(student_id=student.student_id)
                   if r.is_live and not (r.date_to < date_from
                                         or r.date_from > date_to)]
    if overlapping:
        raise ValidationError(
            f"{student.student_id} already has leave "
            f"{overlapping[0].span} covering those dates")

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_leave_requests
                   (student_id, date_from, date_to, kind, detail,
                    destination, requested_by, notice_days, state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student.student_id, date_from, date_to, kind,
             (detail or "").strip() or None,
             (destination or "").strip() or None,
             (requested_by or "").strip() or None, notice, REQUESTED))
        conn.commit()
        request_id = int(cur.lastrowid or 0)
    logger.info("Leave requested: %s %s → %s (%s)", student.student_id,
                date_from, date_to, kind)
    out = get_request(request_id)
    assert out is not None
    return out


# ── Deciding ────────────────────────────────────────────────────────

def clashes(request_id: int) -> list[Clash]:
    """What is already booked during the requested span.

    Exam sittings first, because approving a holiday over a paper is the
    mistake this whole workflow exists to prevent.
    """
    init_db()
    request = get_request(request_id)
    if request is None:
        raise ValidationError(f"No leave request with id {request_id}")
    out: list[Clash] = []

    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_exams as _exams,
        )
        for sitting, candidate in _exams.student_record(request.student_id):
            if request.date_from <= sitting.date <= request.date_to:
                out.append(Clash(date=sitting.date, what="Exam sitting",
                                 detail=f"{sitting.paper_code} at "
                                        f"{sitting.start_time}"))
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Exam clash lookup unavailable", exc_info=True)

    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (  # noqa: E501
            attendance_placements as _placements,
        )
        for day in _placements.list_days(student_id=request.student_id,
                                         date_from=request.date_from,
                                         date_to=request.date_to):
            out.append(Clash(date=day.date, what="Work placement day",
                             detail=day.state))
    except Exception:                       # pragma: no cover - optional dep
        logger.debug("Placement clash lookup unavailable", exc_info=True)

    out.sort(key=lambda c: c.date)
    return out


def _academic_year_window(date: str) -> tuple[str, str]:
    """The September-to-August year a date sits in."""
    target = _dt.date.fromisoformat(date)
    start_year = target.year if target.month >= 9 else target.year - 1
    return (f"{start_year}-09-01", f"{start_year + 1}-08-31")


def leave_used(student_id: str, *, on: str | None = None) -> LeaveAllowance:
    """Discretionary leave days already granted this academic year."""
    init_db()
    on = core._validate_date(on or _dt.date.today().isoformat())
    year_from, year_to = _academic_year_window(on)
    used = 0
    for request in list_requests(student_id=student_id, state=APPROVED,
                                 date_from=year_from, date_to=year_to):
        if request.counts_against_allowance:
            used += request.days
    return LeaveAllowance(student_id=student_id.strip(), used_days=used,
                          allowance=ANNUAL_ALLOWANCE_DAYS,
                          year_from=year_from, year_to=year_to)


def approve(
    request_id: int,
    *,
    decided_by: str,
    code: str | None = None,
    note: str | None = None,
    ignore_clashes: bool = False,
) -> ApplyResult:
    """Grant leave and code the register across the span.

    Refuses over an exam sitting unless somebody deliberately overrides,
    because that decision should be made by a person who has been told.
    """
    init_db()
    request = get_request(request_id)
    if request is None:
        raise ValidationError(f"No leave request with id {request_id}")
    if request.state == APPROVED:
        raise ValidationError(f"Request #{request_id} is already approved")
    if request.state in (WITHDRAWN, CANCELLED):
        raise ValidationError(
            f"Request #{request_id} was {request.state.lower()}")
    if not (decided_by or "").strip():
        raise ValidationError("Leave has to be approved by somebody named")

    found = clashes(request_id)
    exam_clashes = [c for c in found if c.what == "Exam sitting"]
    if exam_clashes and not ignore_clashes:
        raise ValidationError(
            f"{request.student_id} is sitting "
            f"{exam_clashes[0].detail} on {exam_clashes[0].date} — approve "
            "again with ignore_clashes if that is genuinely intended")

    code = codes.validate_code(code) if code else code_for_kind(request.kind)
    written = 0
    used: list[str] = []
    skipped: list[str] = []
    cursor = _dt.date.fromisoformat(request.date_from)
    end = _dt.date.fromisoformat(request.date_to)
    while cursor <= end:
        date = cursor.isoformat()
        cursor += _dt.timedelta(days=1)
        if not calendar.is_open(date):
            skipped.append(date)
            continue
        weekday = _dt.date.fromisoformat(date).weekday() + 1
        slots = weeks.filter_slots(
            [s for s in tt.list_slots(student_id=request.student_id)
             if s.day == weekday], date)
        marked = 0
        for slot in slots:
            if reg.is_locked(slot.slot_id, date):
                continue
            try:
                marked += core.save_register(
                    slot.slot_id, date,
                    {request.student_id: {
                        "code": code,
                        "notes": f"{request.kind}"
                                 + (f": {request.destination}"
                                    if request.destination else ""),
                        "is_offsite": codes.implies_offsite(code),
                        "offsite_location": request.destination,
                        "data_source": "derived"}},
                    actor=decided_by,
                    reason=f"Approved leave: {request.kind}",
                    allow_retro=True)
            except ValidationError as e:
                logger.debug("Leave skipped slot #%d on %s: %s",
                             slot.slot_id, date, e)
        written += marked
        (used if marked else skipped).append(date)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_leave_requests
                  SET state = ?, code = ?, decided_by = ?,
                      decided_at = datetime('now'), decision_note = ?,
                      marks_written = ?
                WHERE request_id = ?""",
            (APPROVED, code, decided_by.strip(),
             (note or "").strip() or None, written, request_id))
        conn.commit()
    logger.info("Leave #%d approved as %s: %d mark(s)", request_id, code,
                written)
    return ApplyResult(request_id=request_id, marks_written=written,
                       dates=used, skipped=skipped)


def decline(request_id: int, *, reason: str,
            decided_by: str | None = None) -> LeaveRequest:
    """Refuse leave. The reason is mandatory — it will be asked about."""
    init_db()
    request = get_request(request_id)
    if request is None:
        raise ValidationError(f"No leave request with id {request_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to decline leave")
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_leave_requests
                  SET state = ?, decided_by = ?, decided_at = datetime('now'),
                      decision_note = ?
                WHERE request_id = ?""",
            (DECLINED, (decided_by or "").strip() or None, note, request_id))
        conn.commit()
    out = get_request(request_id)
    assert out is not None
    return out


def withdraw(request_id: int, *, reason: str | None = None) -> LeaveRequest:
    """The learner no longer needs it — before a decision."""
    init_db()
    request = get_request(request_id)
    if request is None:
        raise ValidationError(f"No leave request with id {request_id}")
    if request.state == APPROVED:
        raise ValidationError(
            f"Request #{request_id} is approved — cancel it instead so the "
            "marks are put back")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_leave_requests SET state = ?, "
            "decision_note = COALESCE(?, decision_note) WHERE request_id = ?",
            (WITHDRAWN, (reason or "").strip() or None, request_id))
        conn.commit()
    out = get_request(request_id)
    assert out is not None
    return out


def cancel(request_id: int, *, reason: str,
           actor: str | None = None) -> LeaveRequest:
    """Cancel approved leave, and put the marks back to unmarked.

    The interview was cancelled; the learner is in college after all.
    Leaving the `C` marks in place would credit an absence that never
    happened, so the rows are voided rather than merely forgotten.
    """
    init_db()
    request = get_request(request_id)
    if request is None:
        raise ValidationError(f"No leave request with id {request_id}")
    if request.state != APPROVED:
        raise ValidationError(
            f"Request #{request_id} is {request.state.lower()}, not approved")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to cancel approved leave")

    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_audit as audit,
    )
    voided = 0
    for record in core.list_records(student_id=request.student_id,
                                    date_from=request.date_from,
                                    date_to=request.date_to):
        if record.code != request.code:
            continue
        try:
            audit.void_record(record.record_id,
                              reason=f"Leave cancelled: {note}", actor=actor)
            voided += 1
        except ValidationError as e:
            logger.debug("Could not void record #%d: %s", record.record_id, e)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_leave_requests
                  SET state = ?, decision_note = ?, decided_by = ?,
                      decided_at = datetime('now')
                WHERE request_id = ?""",
            (CANCELLED, note, (actor or "").strip() or None, request_id))
        conn.commit()
    logger.info("Leave #%d cancelled: %d mark(s) voided", request_id, voided)
    out = get_request(request_id)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_request(request_id: int) -> LeaveRequest | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_leave_requests WHERE request_id = ?",
            (request_id,)).fetchone()
    return _row(r) if r else None


def list_requests(*, student_id: str | None = None, state: str | None = None,
                  kind: str | None = None, date_from: str | None = None,
                  date_to: str | None = None,
                  limit: int = 200) -> list[LeaveRequest]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        if state not in STATES:
            raise ValidationError(f"State must be one of: {', '.join(STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if kind:
        clauses.append("kind = ?")
        args.append(validate_kind(kind))
    if date_from:
        clauses.append("date_to >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date_from <= ?")
        args.append(core._validate_date(date_to))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_leave_requests {where} "
            "ORDER BY date_from, request_id LIMIT ?", args).fetchall()
    return [_row(r) for r in rows]


def pending(*, with_names: bool = True) -> list[LeaveRequest]:
    """Requests waiting on a decision, soonest first.

    Ordered by when the leave starts rather than when it was asked for:
    a request for Thursday matters more than one for June.
    """
    out = list_requests(state=REQUESTED)
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for request in out:
            request.student_name = index.get(request.student_id)
    return out


def upcoming(*, days: int = 14) -> list[LeaveRequest]:
    """Approved leave about to happen — the week's known absences."""
    today = _dt.date.today()
    return list_requests(
        state=APPROVED, date_from=today.isoformat(),
        date_to=(today + _dt.timedelta(days=max(0, days))).isoformat())


def on_leave(date: str) -> list[LeaveRequest]:
    """Who is legitimately out on a given date."""
    date = core._validate_date(date)
    return [r for r in list_requests(state=APPROVED, date_from=date,
                                     date_to=date)]


def kind_breakdown(*, date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, int]:
    """Approved leave days by kind — what the college is agreeing to."""
    out: dict[str, int] = {}
    for request in list_requests(state=APPROVED, date_from=date_from,
                                 date_to=date_to, limit=5000):
        out[request.kind] = out.get(request.kind, 0) + request.days
    return out


def short_notice_report(*, date_from: str | None = None,
                        date_to: str | None = None) -> list[LeaveRequest]:
    """Requests that gave less warning than the college asks for."""
    return [r for r in list_requests(date_from=date_from, date_to=date_to,
                                     limit=5000) if r.short_notice]


# ── Bridge to the pastoral request log ──────────────────────────────

def adopt_pastoral_request(pastoral_request_id: int, *,
                           kind: str | None = None) -> LeaveRequest:
    """Pull a request from :mod:`pastoral.absence_requests` into here.

    The pastoral team takes the request; this module does the attendance
    work. Adopting rather than re-keying means the dates and the reason
    cannot drift apart between the two records.
    """
    init_db()
    from education_system.systems.sixth_form.domain.pastoral.absence_requests import (  # noqa: E501
        absence_requests as _pastoral,
    )
    source = _pastoral.get_request(pastoral_request_id)
    if source is None:
        raise ValidationError(
            f"No pastoral absence request with id {pastoral_request_id}")
    guessed = kind
    if guessed is None:
        reason = (source.reason or "").lower()
        guessed = next((k for k in KINDS if k.lower() in reason), DEFAULT_KIND)
    return request_leave(
        source.student_id, source.start_date, date_to=source.end_date,
        kind=guessed, detail=source.description or source.reason,
        requested_by=source.submitted_by,
        on=source.request_date)


def adopt_pending_pastoral(*, limit: int = 50) -> list[LeaveRequest]:
    """Adopt every pastoral request that has no leave record yet."""
    from education_system.systems.sixth_form.domain.pastoral.absence_requests import (  # noqa: E501
        absence_requests as _pastoral,
    )
    out: list[LeaveRequest] = []
    for source in _pastoral.list_requests()[:max(1, limit)]:
        overlapping = [r for r in list_requests(student_id=source.student_id)
                       if r.is_live and not (r.date_to < source.start_date
                                             or r.date_from > source.end_date)]
        if overlapping:
            continue
        try:
            out.append(adopt_pastoral_request(source.request_id))
        except ValidationError as e:
            logger.debug("Could not adopt pastoral request #%d: %s",
                         source.request_id, e)
    return out
