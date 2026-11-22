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

**One absence store.** ``attendance_leave_requests`` is the single
table behind every kind of absence somebody tells the college about:

* planned leave asked for here (``origin = 'leave'``),
* requests logged by the pastoral team through
  :mod:`pastoral.absence_requests` (``origin = 'pastoral'``), and
* inbound reports and self-certifications taken by
  :mod:`attendance_absence_reports` (``origin = 'report'``).

It was chosen because its lifecycle is the superset of the other two —
requested, decided, marks written, and on cancellation the marks voided —
and because it sits next to the register it writes. The two older
modules keep their public functions and their vocabularies, and read and
write through the ``store_*`` helpers below. Their original tables
(``absence_requests`` and ``attendance_absence_reports``) are left in
place; :func:`migrate_legacy_stores` copies their rows across once, keyed
on ``legacy_ref`` so that running it again copies nothing twice.
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
    ("Illness", "I", False,
     "Unwell — usually reported on the day, or self-certified."),
    ("Study leave", "S", False,
     "Exam-season study leave the college grants, usually to a cohort."),
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
# A report replaced by a later one covering the same absence.
SUPERSEDED: str = "Superseded"
STATES: tuple[str, ...] = (REQUESTED, APPROVED, DECLINED, WITHDRAWN,
                           CANCELLED, SUPERSEDED)

# Where a row in the one absence store came from.
ORIGIN_LEAVE: str = "leave"          # planned leave asked for here
ORIGIN_PASTORAL: str = "pastoral"    # logged via pastoral absence requests
ORIGIN_REPORT: str = "report"        # an inbound report / self-cert
ORIGINS: tuple[str, ...] = (ORIGIN_LEAVE, ORIGIN_PASTORAL, ORIGIN_REPORT)
# Planned absence — what the leave workflow (notice, allowance, overlap
# checks, the pastoral request log) is about. Reports are claims about
# absence already happening and have their own queue.
PLANNED_ORIGINS: tuple[str, ...] = (ORIGIN_LEAVE, ORIGIN_PASTORAL)

# legacy_ref prefixes for rows copied from the older stores.
LEGACY_PASTORAL: str = "absence_requests"
LEGACY_REPORTS: str = "attendance_absence_reports"

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

# Columns added when the three absence stores were unified. Added with
# ALTER TABLE so an existing database keeps every row it has.
_EXTRA_COLUMNS: tuple[tuple[str, str], ...] = (
    ("origin",         "TEXT NOT NULL DEFAULT 'leave'"),
    ("channel",        "TEXT"),
    ("reporter_type",  "TEXT"),
    ("reporter_name",  "TEXT"),
    ("reason_id",      "INTEGER"),
    ("reason_text",    "TEXT"),
    ("message",        "TEXT"),
    ("self_certified", "INTEGER NOT NULL DEFAULT 0"),
    ("contact_phone",  "TEXT"),
    ("supporting_doc", "TEXT"),
    ("notes",          "TEXT"),
    ("request_date",   "TEXT"),
    ("updated_at",     "TEXT"),
    ("legacy_ref",     "TEXT"),
)
_EXTRA_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_att_leave_origin
    ON attendance_leave_requests(origin, state);
CREATE UNIQUE INDEX IF NOT EXISTS idx_att_leave_legacy
    ON attendance_leave_requests(legacy_ref) WHERE legacy_ref IS NOT NULL;
"""

# Columns the store helpers may write. Anything else is refused, so a
# caller's payload can never name a column into the SQL.
_WRITABLE: frozenset[str] = frozenset({
    "student_id", "date_from", "date_to", "kind", "detail", "destination",
    "requested_by", "requested_at", "notice_days", "state", "code",
    "decided_by", "decided_at", "decision_note", "marks_written",
} | {name for name, _decl in _EXTRA_COLUMNS})


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
    # Unified-store columns (see the module docstring).
    origin: str = ORIGIN_LEAVE
    channel: str | None = None
    reporter_type: str | None = None
    reporter_name: str | None = None
    reason_id: int | None = None
    reason_text: str | None = None
    message: str | None = None
    self_certified: bool = False
    contact_phone: str | None = None
    supporting_doc: str | None = None
    notes: str | None = None
    request_date: str | None = None
    updated_at: str | None = None
    legacy_ref: str | None = None

    @property
    def days(self) -> int:
        return (_dt.date.fromisoformat(self.date_to)
                - _dt.date.fromisoformat(self.date_from)).days + 1

    @property
    def is_planned(self) -> bool:
        return self.origin in PLANNED_ORIGINS

    @property
    def needs_marks(self) -> bool:
        """Approved, but nothing has been written to the register.

        A pastoral approval records the decision only; this is the list
        of those still waiting for somebody to code the register.
        """
        return self.state == APPROVED and not self.marks_written

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
        _ensure_columns(conn)
        conn.executescript(_EXTRA_INDEXES)
        conn.commit()
        _DB_READY = True
        try:
            migrate_legacy_stores(conn=conn)
        except sqlite3.Error:
            # A copy that fails leaves the old rows where they were and
            # is tried again on the next start; it must not stop the
            # register from opening.
            logger.exception("Absence-store migration failed; will retry")
    logger.debug("Leave-request schema ready at %s", DB_PATH)


def _ensure_columns(conn: sqlite3.Connection) -> None:
    have = {r["name"] for r in conn.execute(
        "PRAGMA table_info(attendance_leave_requests)").fetchall()}
    for name, decl in _EXTRA_COLUMNS:
        if name not in have:
            conn.execute(
                f"ALTER TABLE attendance_leave_requests ADD COLUMN {name} {decl}")


def _row(r: sqlite3.Row) -> LeaveRequest:
    keys = set(r.keys())

    def opt(name: str, default: Any = None) -> Any:
        return r[name] if name in keys else default

    return LeaveRequest(
        request_id=r["request_id"], student_id=r["student_id"],
        date_from=r["date_from"], date_to=r["date_to"], kind=r["kind"],
        detail=r["detail"], destination=r["destination"],
        requested_by=r["requested_by"], requested_at=r["requested_at"],
        notice_days=r["notice_days"], state=r["state"], code=r["code"],
        decided_by=r["decided_by"], decided_at=r["decided_at"],
        decision_note=r["decision_note"], marks_written=r["marks_written"],
        origin=opt("origin") or ORIGIN_LEAVE,
        channel=opt("channel"), reporter_type=opt("reporter_type"),
        reporter_name=opt("reporter_name"), reason_id=opt("reason_id"),
        reason_text=opt("reason_text"), message=opt("message"),
        self_certified=bool(opt("self_certified", 0)),
        contact_phone=opt("contact_phone"),
        supporting_doc=opt("supporting_doc"), notes=opt("notes"),
        request_date=opt("request_date"), updated_at=opt("updated_at"),
        legacy_ref=opt("legacy_ref"))


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
    if request.state in (WITHDRAWN, CANCELLED, SUPERSEDED):
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
    written, used, skipped = _write_marks(request, code, actor=decided_by)

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_leave_requests
                  SET state = ?, code = ?, decided_by = ?,
                      decided_at = datetime('now'), decision_note = ?,
                      marks_written = ?, updated_at = datetime('now')
                WHERE request_id = ?""",
            (APPROVED, code, decided_by.strip(),
             (note or "").strip() or None, written, request_id))
        conn.commit()
    logger.info("Leave #%d approved as %s: %d mark(s)", request_id, code,
                written)
    return ApplyResult(request_id=request_id, marks_written=written,
                       dates=used, skipped=skipped)


def _write_marks(request: LeaveRequest, code: str, *,
                 actor: str | None) -> tuple[int, list[str], list[str]]:
    """Code every timetabled lesson in the span; skip closed days and
    submitted registers. Returns (marks written, dates used, skipped)."""
    written = 0
    used: list[str] = []
    skipped: list[str] = []
    decided_by = actor
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
    return written, used, skipped


def apply_marks(request_id: int, *, actor: str,
                code: str | None = None,
                ignore_clashes: bool = False) -> ApplyResult:
    """Code the register for leave that was approved without marks.

    Pastoral approvals (and rows copied from the old request log) record
    the decision but write nothing; this finishes the job, with the same
    exam-clash guard :func:`approve` applies.
    """
    init_db()
    request = get_request(request_id)
    if request is None:
        raise ValidationError(f"No leave request with id {request_id}")
    if request.state != APPROVED:
        raise ValidationError(
            f"Request #{request_id} is {request.state.lower()}, not approved")
    if not (actor or "").strip():
        raise ValidationError("Marks have to be written by somebody named")
    exam_clashes = [c for c in clashes(request_id)
                    if c.what == "Exam sitting"]
    if exam_clashes and not ignore_clashes:
        raise ValidationError(
            f"{request.student_id} is sitting {exam_clashes[0].detail} on "
            f"{exam_clashes[0].date} — confirm before writing leave over it")
    code = (codes.validate_code(code) if code
            else request.code or code_for_kind(request.kind))
    written, used, skipped = _write_marks(request, code, actor=actor)
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_leave_requests SET code = ?, "
            "marks_written = marks_written + ?, updated_at = datetime('now') "
            "WHERE request_id = ?", (code, written, request_id))
        conn.commit()
    logger.info("Leave #%d marks applied as %s: %d mark(s)", request_id,
                code, written)
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
                      decision_note = ?, updated_at = datetime('now')
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
            "decision_note = COALESCE(?, decision_note), "
            "updated_at = datetime('now') WHERE request_id = ?",
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
                      decided_at = datetime('now'), updated_at = datetime('now')
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
                  limit: int = 200,
                  origins: tuple[str, ...] | None = PLANNED_ORIGINS,
                  channel: str | None = None,
                  self_certified: bool | None = None,
                  newest_first: bool = False) -> list[LeaveRequest]:
    """Rows from the absence store.

    ``origins`` defaults to planned absence (leave and pastoral
    requests), which is what every leave screen has always shown; pass
    ``(ORIGIN_REPORT,)`` for reports or ``None`` for everything.
    """
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if origins:
        clauses.append(f"origin IN ({','.join('?' * len(origins))})")
        args.extend(origins)
    if channel:
        clauses.append("channel = ?")
        args.append(channel)
    if self_certified is not None:
        clauses.append("self_certified = ?")
        args.append(1 if self_certified else 0)
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
            + ("ORDER BY date_from DESC, request_id DESC LIMIT ?"
               if newest_first else "ORDER BY date_from, request_id LIMIT ?"),
            args).fetchall()
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


# ── Study leave for a cohort ────────────────────────────────────────

@dataclass
class StudyLeaveResult:
    granted: list[ApplyResult] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        marks = sum(r.marks_written for r in self.granted)
        return (f"Study leave granted to {len(self.granted)} learner(s) "
                f"({marks} mark(s)); {len(self.skipped)} skipped")


def grant_study_leave(
    date_from: str,
    date_to: str,
    *,
    decided_by: str,
    student_ids: list[str] | None = None,
    group_id: int | None = None,
    detail: str | None = None,
    ignore_clashes: bool = True,
) -> StudyLeaveResult:
    """Grant study leave to a group of learners in one go.

    Study leave is decided by the college for a cohort (a year group's
    exam season), not asked for one learner at a time, so each learner
    gets a request that is approved at once and coded ``S``. Exam
    sittings inside the span are expected — the learner comes in for
    them — so clashes are ignored by default. Learners with leave
    already covering the dates are skipped and listed, not overwritten.
    """
    init_db()
    ids = [str(s).strip() for s in (student_ids or []) if str(s).strip()]
    if group_id is not None:
        from education_system.systems.sixth_form.domain.academics.class_groups import (  # noqa: E501
            class_groups as _cg,
        )
        ids.extend(m for m in _cg.list_members(group_id) if m not in ids)
    if not ids:
        raise ValidationError("Choose the learners (or a group) to grant "
                              "study leave to")
    if not (decided_by or "").strip():
        raise ValidationError("Study leave has to be granted by somebody named")
    result = StudyLeaveResult()
    for sid in ids:
        try:
            request = request_leave(
                sid, date_from, date_to=date_to, kind="Study leave",
                detail=detail or "Study leave", requested_by=decided_by)
            result.granted.append(approve(
                request.request_id, decided_by=decided_by,
                note="Cohort study leave", ignore_clashes=ignore_clashes))
        except ValidationError as e:
            result.skipped[sid] = str(e)
    logger.info("Study leave %s → %s: %s", date_from, date_to,
                result.summary)
    return result


# ── Bridge to the pastoral request log ──────────────────────────────

def adopt_pastoral_request(pastoral_request_id: int, *,
                           kind: str | None = None) -> LeaveRequest:
    """Bring a pastoral request into the leave workflow.

    Since the stores were unified a pastoral request *is* a row here
    (``origin = 'pastoral'``), so there is nothing to copy: adopting it
    settles its leave kind — guessed from the pastoral reason unless one
    is given — so the right code is written when it is approved. The id
    is the one the pastoral window shows. A pre-unification id is
    followed through ``legacy_ref``.
    """
    init_db()
    request = get_request(pastoral_request_id)
    if request is None or request.origin == ORIGIN_REPORT:
        request = by_legacy_ref(LEGACY_PASTORAL, pastoral_request_id)
    if request is None:
        raise ValidationError(
            f"No pastoral absence request with id {pastoral_request_id}")
    guessed = kind
    if guessed is None:
        reason = (request.reason_text or request.detail or "").lower()
        guessed = (kind_for_pastoral_reason(request.reason_text)
                   if request.reason_text else
                   next((k for k in KINDS if k.lower() in reason),
                        DEFAULT_KIND))
    store_update(request.request_id, kind=validate_kind(guessed))
    out = get_request(request.request_id)
    assert out is not None
    return out


def adopt_pending_pastoral(*, limit: int = 50) -> list[LeaveRequest]:
    """Settle the leave kind on every pastoral request still at the default."""
    out: list[LeaveRequest] = []
    for request in list_requests(origins=(ORIGIN_PASTORAL,),
                                 limit=max(1, limit) * 4):
        if len(out) >= max(1, limit):
            break
        if request.kind != DEFAULT_KIND or not request.is_live:
            continue
        try:
            out.append(adopt_pastoral_request(request.request_id))
        except ValidationError as e:
            logger.debug("Could not adopt pastoral request #%d: %s",
                         request.request_id, e)
    return out


# ── The one absence store ───────────────────────────────────────────

# Pastoral reasons → leave kinds, so a request logged by the pastoral
# team earns the right code when it is approved.
_PASTORAL_REASON_KIND: dict[str, str] = {
    "Medical Appointment": "Medical appointment",
    "Illness": "Illness",
    "University Open Day": "University open day",
    "University Interview": "Interview",
    "Apprenticeship Interview": "Interview",
    "Work Experience": "College activity",
    "Family Bereavement": "Bereavement",
    "Family Emergency": "Family event",
    "Religious Observance": "Religious observance",
    "Sports / Competition": "Audition or trial",
    "Driving Test": "Driving test",
    "DBS / Passport Appointment": "Other",
    "Other": "Other",
}


def kind_for_pastoral_reason(reason: str | None) -> str:
    return _PASTORAL_REASON_KIND.get((reason or "").strip(), DEFAULT_KIND)


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def store_insert(student_id: str, date_from: str, date_to: str, *,
                 origin: str, **fields: Any) -> int:
    """Insert one row into the absence store. Returns its id.

    The low-level write the pastoral and report modules use; each keeps
    its own validation and calls this once it is satisfied. Only known
    columns are accepted.
    """
    init_db()
    if origin not in ORIGINS:
        raise ValidationError(f"Origin must be one of: {', '.join(ORIGINS)}")
    unknown = set(fields) - _WRITABLE
    if unknown:
        raise ValidationError(f"Unknown absence-store field(s): {sorted(unknown)}")
    row = {"student_id": student_id, "date_from": date_from,
           "date_to": date_to, "origin": origin,
           "kind": fields.pop("kind", None) or DEFAULT_KIND,
           "state": fields.pop("state", None) or REQUESTED}
    row.update({k: _clean(v) for k, v in fields.items()})
    cols = list(row)
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO attendance_leave_requests ({', '.join(cols)}, "
            "updated_at) VALUES ("
            + ", ".join("?" * len(cols)) + ", datetime('now'))",
            [row[c] for c in cols])
        conn.commit()
        return int(cur.lastrowid or 0)


def store_update(request_id: int, **fields: Any) -> None:
    """Change named columns on one row of the absence store."""
    init_db()
    if not fields:
        return
    unknown = set(fields) - _WRITABLE
    if unknown:
        raise ValidationError(f"Unknown absence-store field(s): {sorted(unknown)}")
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE attendance_leave_requests SET {sets}, "
            "updated_at = datetime('now') WHERE request_id = ?",
            [_clean(v) for v in fields.values()] + [request_id])
        conn.commit()
    if not cur.rowcount:
        raise ValidationError(f"No absence record with id {request_id}")


def store_delete(request_id: int) -> bool:
    """Delete one row, and the old-store row it was copied from.

    The original is deleted too because :func:`migrate_legacy_stores`
    would otherwise copy it straight back on the next start.
    """
    init_db()
    request = get_request(request_id)
    if request is None:
        return False
    with _connect() as conn:
        conn.execute("DELETE FROM attendance_leave_requests "
                     "WHERE request_id = ?", (request_id,))
        _delete_legacy_source(conn, request.legacy_ref)
        conn.commit()
    logger.info("Deleted absence record #%d (%s)", request_id, request.origin)
    return True


def _delete_legacy_source(conn: sqlite3.Connection,
                          legacy_ref: str | None) -> None:
    if not legacy_ref or ":" not in legacy_ref:
        return
    table, _sep, raw_id = legacy_ref.partition(":")
    key = {LEGACY_PASTORAL: "request_id",
           LEGACY_REPORTS: "report_id"}.get(table)
    if key is None or not raw_id.isdigit() or not _table_exists(conn, table):
        return
    conn.execute(f"DELETE FROM {table} WHERE {key} = ?", (int(raw_id),))


def by_legacy_ref(table: str, legacy_id: int) -> LeaveRequest | None:
    """The store row copied from one row of an old table, if any."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_leave_requests WHERE legacy_ref = ?",
            (f"{table}:{int(legacy_id)}",)).fetchone()
    return _row(r) if r else None


def all_absence(*, student_id: str | None = None, state: str | None = None,
                date_from: str | None = None, date_to: str | None = None,
                origin: str | None = None,
                limit: int = 500) -> list[LeaveRequest]:
    """Every absence anybody has told the college about, newest first.

    Leave, pastoral requests and reports together — the one list the
    stores were unified to make possible.
    """
    rows = list_requests(student_id=student_id, state=state,
                         date_from=date_from, date_to=date_to, limit=limit,
                         origins=(origin,) if origin else None,
                         newest_first=True)
    if rows:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for request in rows:
            request.student_name = index.get(request.student_id)
    return rows


def awaiting_marks(*, limit: int = 200) -> list[LeaveRequest]:
    """Approved planned absence that has not reached the register."""
    return [r for r in list_requests(state=APPROVED, limit=5000)
            if r.needs_marks][:max(1, limit)]


def origin_counts() -> dict[str, int]:
    """How many rows the store holds from each source."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT origin, COUNT(*) AS n FROM attendance_leave_requests "
            "GROUP BY origin").fetchall()
    return {r["origin"]: r["n"] for r in rows}


# ── Copying the old stores in ───────────────────────────────────────

_PASTORAL_STATE: dict[str, str] = {
    "Pending": REQUESTED, "Approved": APPROVED, "Denied": DECLINED,
    "Cancelled": CANCELLED, "Withdrawn": WITHDRAWN,
}
_REPORT_STATE: dict[str, str] = {
    "Pending": REQUESTED, "Accepted": APPROVED, "Rejected": DECLINED,
    "Superseded": SUPERSEDED,
}


@dataclass
class MigrationResult:
    pastoral_copied: int = 0
    pastoral_linked: int = 0
    reports_copied: int = 0
    skipped: int = 0

    @property
    def summary(self) -> str:
        return (f"{self.pastoral_copied} pastoral request(s) copied, "
                f"{self.pastoral_linked} linked to existing leave, "
                f"{self.reports_copied} report(s) copied, "
                f"{self.skipped} skipped")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,)).fetchone() is not None


def _notice(request_date: str | None, date_from: str) -> int | None:
    try:
        return (_dt.date.fromisoformat(date_from)
                - _dt.date.fromisoformat((request_date or "")[:10])).days
    except ValueError:
        return None


def migrate_legacy_stores(*, conn: sqlite3.Connection | None = None
                          ) -> MigrationResult:
    """Copy rows from the two older absence tables into this one.

    Idempotent: each copied row carries ``legacy_ref`` ("<table>:<id>"),
    which has a unique index, so a second run copies nothing. A pastoral
    request that was already adopted under the old manual bridge (same
    learner, same dates, no legacy link yet) is *linked* to that leave
    row rather than copied, so it does not appear twice. The old tables
    are left exactly as they were.
    """
    if conn is None:
        init_db()       # init_db runs this itself on first use
        with _connect() as own:
            return migrate_legacy_stores(conn=own)

    result = MigrationResult()
    if not _table_exists(conn, "students"):
        return result
    students = {r[0] for r in conn.execute(
        "SELECT student_id FROM students").fetchall()}
    done = {r[0] for r in conn.execute(
        "SELECT legacy_ref FROM attendance_leave_requests "
        "WHERE legacy_ref IS NOT NULL").fetchall()}
    cols = ("student_id, date_from, date_to, kind, detail, requested_by, "
            "requested_at, notice_days, state, code, decided_by, decided_at, "
            "decision_note, marks_written, origin, channel, reporter_type, "
            "reporter_name, reason_id, reason_text, message, self_certified, "
            "contact_phone, supporting_doc, notes, request_date, updated_at, "
            "legacy_ref")
    insert = (f"INSERT INTO attendance_leave_requests ({cols}) VALUES ("
              + ", ".join("?" * len(cols.split(", "))) + ")")

    if _table_exists(conn, LEGACY_PASTORAL):
        for r in conn.execute(
                f"SELECT * FROM {LEGACY_PASTORAL} ORDER BY request_id"):
            ref = f"{LEGACY_PASTORAL}:{r['request_id']}"
            if ref in done:
                continue
            if r["student_id"] not in students:
                result.skipped += 1
                continue
            adopted = conn.execute(
                "SELECT request_id FROM attendance_leave_requests "
                "WHERE origin = ? AND legacy_ref IS NULL AND student_id = ? "
                "AND date_from = ? AND date_to = ? LIMIT 1",
                (ORIGIN_LEAVE, r["student_id"], r["start_date"],
                 r["end_date"])).fetchone()
            if adopted is not None:
                conn.execute(
                    """UPDATE attendance_leave_requests
                          SET legacy_ref = ?, reason_text = COALESCE(reason_text, ?),
                              reporter_type = COALESCE(reporter_type, ?),
                              contact_phone = COALESCE(contact_phone, ?),
                              supporting_doc = COALESCE(supporting_doc, ?),
                              notes = COALESCE(notes, ?),
                              request_date = COALESCE(request_date, ?)
                        WHERE request_id = ?""",
                    (ref, r["reason"], r["submitter_type"], r["contact_phone"],
                     r["supporting_doc"], r["notes"], r["request_date"],
                     adopted["request_id"]))
                result.pastoral_linked += 1
                continue
            conn.execute(insert, (
                r["student_id"], r["start_date"], r["end_date"],
                kind_for_pastoral_reason(r["reason"]), r["description"],
                r["submitted_by"], r["created_at"],
                _notice(r["request_date"], r["start_date"]),
                _PASTORAL_STATE.get(r["status"], REQUESTED), None,
                r["decided_by"], r["decision_date"], r["decision_notes"], 0,
                ORIGIN_PASTORAL, None, r["submitter_type"], None, None,
                r["reason"], None, 0, r["contact_phone"], r["supporting_doc"],
                r["notes"], r["request_date"], r["updated_at"], ref))
            result.pastoral_copied += 1

    if _table_exists(conn, LEGACY_REPORTS):
        for r in conn.execute(
                f"SELECT * FROM {LEGACY_REPORTS} ORDER BY report_id"):
            ref = f"{LEGACY_REPORTS}:{r['report_id']}"
            if ref in done:
                continue
            if r["student_id"] not in students:
                result.skipped += 1
                continue
            conn.execute(insert, (
                r["student_id"], r["date_from"], r["date_to"],
                "Illness" if r["self_certified"] else DEFAULT_KIND,
                r["reason_text"], r["reporter_name"], r["received_at"], None,
                _REPORT_STATE.get(r["state"], REQUESTED), r["code"],
                r["decided_by"], r["decided_at"], r["decision_note"],
                r["marks_written"] or 0, ORIGIN_REPORT, r["channel"],
                r["reported_by"], r["reporter_name"], r["reason_id"],
                r["reason_text"], r["message"], r["self_certified"] or 0,
                None, None, None, (r["received_at"] or "")[:10] or None,
                r["decided_at"] or r["received_at"], ref))
            result.reports_copied += 1

    conn.commit()
    if result.pastoral_copied or result.pastoral_linked \
            or result.reports_copied:
        logger.info("Absence stores unified: %s", result.summary)
    return result
