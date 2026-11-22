"""Inbound absence reporting for the Sixth Form System.

Sibling to :mod:`attendance`. Every mark in this package so far is
written by a member of staff. But the first person who knows a learner
is absent is almost never a member of staff — it is the learner, or
whoever rang at half past eight to say so.

Two routes in, and the difference between them matters:

* **A report** (:func:`report_absence`) — somebody tells the college.
  A parent rings, a learner emails, the portal takes a message. It is a
  *claim*, not a mark: it lands in a queue, somebody reads it, and it
  becomes a coded absence when a human decides what code it deserves.
* **A self-certification** (:func:`self_certify`) — the learner declares
  their own absence, which is appropriate at sixteen-plus and is how
  most colleges handle a day of illness. It codes the mark immediately,
  because making an adult wait for permission to have had a cold is
  theatre. What stops it being a blank cheque is a **cap**: past a few
  days a term, further self-certification is refused and a conversation
  is required instead.

The queue is the point of the first route. An absence somebody phoned in
and nobody actioned looks identical, in the register, to one nobody
explained — and the whole reason for taking the call was to tell those
two apart.

**Storage.** Reports live in the one absence store,
``attendance_leave_requests`` (see :mod:`attendance_leave`), as rows with
``origin = 'report'``; this module keeps its own vocabulary (Pending /
Accepted / Rejected / Superseded) and maps it onto the store's states.
``report_id`` is the store's ``request_id``. The original
``attendance_absence_reports`` table is still created and left in place;
its rows were copied across once and are not written to any more.

**Portals.** :func:`report_absence_for` and :func:`self_certify_for` are
the entry points for the parent and student portals: they take the
signed-in identity, check it may speak for the learner, and only then
call :func:`report_absence` / :func:`self_certify`.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_calendar as calendar,
    attendance_codes as codes,
    attendance_leave as store,
    attendance_register as reg,
    attendance_thresholds as thresholds,
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

# How the report reached us. Worth keeping: a college whose reports all
# arrive by phone at 08:25 has a different problem from one whose portal
# nobody uses.
PHONE: str = "Phone"
PORTAL: str = "Portal"
EMAIL: str = "Email"
SMS: str = "SMS"
IN_PERSON: str = "In person"
CHANNELS: tuple[str, ...] = (PHONE, PORTAL, EMAIL, SMS, IN_PERSON)

# Who made the claim.
PARENT: str = "Parent"
STUDENT: str = "Student"
STAFF: str = "Staff"
OTHER: str = "Other"
REPORTERS: tuple[str, ...] = (PARENT, STUDENT, STAFF, OTHER)

# Where a report has got to.
PENDING: str = "Pending"
ACCEPTED: str = "Accepted"
REJECTED: str = "Rejected"
SUPERSEDED: str = "Superseded"
STATES: tuple[str, ...] = (PENDING, ACCEPTED, REJECTED, SUPERSEDED)

# This module's states ↔ the absence store's.
_TO_STORE: dict[str, str] = {
    PENDING: store.REQUESTED, ACCEPTED: store.APPROVED,
    REJECTED: store.DECLINED, SUPERSEDED: store.SUPERSEDED,
}
_FROM_STORE: dict[str, str] = {
    store.REQUESTED: PENDING, store.APPROVED: ACCEPTED,
    store.DECLINED: REJECTED, store.SUPERSEDED: SUPERSEDED,
    # Withdrawn / cancelled from the leave screens: no longer live.
    store.WITHDRAWN: SUPERSEDED, store.CANCELLED: SUPERSEDED,
}

# The code a self-certified illness earns. `I` — authorised, and the
# learner said so themselves.
SELF_CERT_CODE: str = "I"
# What a report becomes if staff accept it without choosing a code.
DEFAULT_ACCEPT_CODE: str = "C"

SELF_CERT_SOURCE: str = "self-service"

# How far ahead somebody may report an absence. A parent ringing on
# Friday about next Wednesday's hospital appointment is normal.
MAX_FUTURE_DAYS: int = 60

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_absence_reports (
    report_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    date_from    TEXT NOT NULL,
    date_to      TEXT NOT NULL,
    channel      TEXT NOT NULL DEFAULT 'Phone',
    reported_by  TEXT NOT NULL DEFAULT 'Parent',
    reporter_name TEXT,
    reason_id    INTEGER,
    reason_text  TEXT,
    message      TEXT,
    state        TEXT NOT NULL DEFAULT 'Pending',
    self_certified INTEGER NOT NULL DEFAULT 0,
    code         TEXT,
    decided_by   TEXT,
    decided_at   TEXT,
    decision_note TEXT,
    marks_written INTEGER NOT NULL DEFAULT 0,
    received_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_absrep_state
    ON attendance_absence_reports(state);
CREATE INDEX IF NOT EXISTS idx_att_absrep_student
    ON attendance_absence_reports(student_id, date_from);
CREATE INDEX IF NOT EXISTS idx_att_absrep_dates
    ON attendance_absence_reports(date_from, date_to);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class AbsenceReport:
    """One claim that a learner is or will be absent."""

    report_id: int
    student_id: str
    date_from: str
    date_to: str
    channel: str
    reported_by: str
    reporter_name: str | None
    reason_id: int | None
    reason_text: str | None
    message: str | None
    state: str
    self_certified: bool
    code: str | None
    decided_by: str | None
    decided_at: str | None
    decision_note: str | None
    marks_written: int
    received_at: str | None
    student_name: str | None = None

    @property
    def is_pending(self) -> bool:
        return self.state == PENDING

    @property
    def days(self) -> int:
        return (_dt.date.fromisoformat(self.date_to)
                - _dt.date.fromisoformat(self.date_from)).days + 1

    @property
    def span(self) -> str:
        return (self.date_from if self.date_from == self.date_to
                else f"{self.date_from} → {self.date_to}")

    @property
    def label(self) -> str:
        who = self.student_name or self.student_id
        return (f"{who} · {self.span} · {self.reason_text or 'no reason given'}"
                f" ({self.reported_by} by {self.channel.lower()})")


@dataclass
class SelfCertStatus:
    """How much self-certification a learner has left."""

    student_id: str
    used_days: int
    cap: int
    window_from: str
    window_to: str

    @property
    def remaining(self) -> int:
        return max(0, self.cap - self.used_days)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    @property
    def label(self) -> str:
        return (f"{self.used_days}/{self.cap} self-certified day(s) used "
                f"since {self.window_from}")


@dataclass
class ApplyResult:
    """What accepting a report did to the register."""

    report_id: int
    marks_written: int
    dates: list[str]
    skipped: list[str]


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
    thresholds.init_db()
    with _connect() as conn:
        # The pre-unification table is kept so its rows stay readable;
        # creating it first lets the store's migration find them.
        conn.executescript(_SCHEMA)
        conn.commit()
    store.init_db()
    logger.debug("Absence-report schema ready at %s", DB_PATH)
    _DB_READY = True


def _row(r: sqlite3.Row) -> AbsenceReport:
    """A row of the *old* table — kept for anything reading it directly."""
    return AbsenceReport(
        report_id=r["report_id"], student_id=r["student_id"],
        date_from=r["date_from"], date_to=r["date_to"],
        channel=r["channel"], reported_by=r["reported_by"],
        reporter_name=r["reporter_name"], reason_id=r["reason_id"],
        reason_text=r["reason_text"], message=r["message"], state=r["state"],
        self_certified=bool(r["self_certified"]), code=r["code"],
        decided_by=r["decided_by"], decided_at=r["decided_at"],
        decision_note=r["decision_note"], marks_written=r["marks_written"],
        received_at=r["received_at"])


def _from_store(r: store.LeaveRequest) -> AbsenceReport:
    return AbsenceReport(
        report_id=r.request_id, student_id=r.student_id,
        date_from=r.date_from, date_to=r.date_to,
        channel=r.channel or PHONE, reported_by=r.reporter_type or PARENT,
        reporter_name=r.reporter_name, reason_id=r.reason_id,
        reason_text=r.reason_text, message=r.message,
        state=_FROM_STORE.get(r.state, PENDING),
        self_certified=r.self_certified, code=r.code,
        decided_by=r.decided_by, decided_at=r.decided_at,
        decision_note=r.decision_note, marks_written=r.marks_written,
        received_at=r.requested_at, student_name=r.student_name)


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Validation ──────────────────────────────────────────────────────

def validate_channel(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return PHONE
    for channel in CHANNELS:
        if s.lower() == channel.lower():
            return channel
    raise ValidationError(f"Channel must be one of: {', '.join(CHANNELS)}")


def validate_reporter(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    if not s:
        return PARENT
    for reporter in REPORTERS:
        if s.lower() == reporter.lower():
            return reporter
    raise ValidationError(f"Reporter must be one of: {', '.join(REPORTERS)}")


def _require_student(student_id: str) -> Any:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    return student


def _validate_span(date_from: str, date_to: str | None) -> tuple[str, str]:
    date_from = core._validate_date(date_from)
    date_to = core._validate_date(date_to or date_from)
    if date_to < date_from:
        raise ValidationError("An absence cannot end before it starts")
    span = (_dt.date.fromisoformat(date_to)
            - _dt.date.fromisoformat(date_from)).days
    if span > 90:
        raise ValidationError(
            "Report at most a term at a time — a longer absence needs a "
            "plan, not a phone call")
    ahead = (_dt.date.fromisoformat(date_from) - _dt.date.today()).days
    if ahead > MAX_FUTURE_DAYS:
        raise ValidationError(
            f"That is {ahead} days ahead; absences can be reported up to "
            f"{MAX_FUTURE_DAYS} days in advance")
    return date_from, date_to


# ── Reporting an absence ────────────────────────────────────────────

def report_absence(
    student_id: str,
    date_from: str,
    *,
    date_to: str | None = None,
    channel: str = PHONE,
    reported_by: str = PARENT,
    reporter_name: str | None = None,
    reason_id: int | None = None,
    reason_text: str | None = None,
    message: str | None = None,
) -> AbsenceReport:
    """Take a report. Writes no mark — that is a decision, made later.

    Deliberately permissive about what it accepts: the person on the
    phone is not filling in a form, and refusing a call because the
    reason does not match a dropdown is how a college ends up with a
    register full of unexplained absence and a message pad full of
    explanations.
    """
    init_db()
    student = _require_student(student_id)
    date_from, date_to = _validate_span(date_from, date_to)
    channel = validate_channel(channel)
    reported_by = validate_reporter(reported_by)
    if reason_id is not None:
        reason_id = codes.validate_reason_id(reason_id)
        if not reason_text:
            reason = codes.get_reason(reason_id)
            reason_text = reason.name if reason else None

    reason_text = (reason_text or "").strip() or None
    report_id = store.store_insert(
        student.student_id, date_from, date_to, origin=store.ORIGIN_REPORT,
        state=store.REQUESTED,
        kind=("Illness" if reason_text and "ill" in reason_text.lower()
              else store.DEFAULT_KIND),
        detail=reason_text, requested_by=reporter_name,
        requested_at=_now(), request_date=_dt.date.today().isoformat(),
        notice_days=(_dt.date.fromisoformat(date_from)
                     - _dt.date.today()).days,
        channel=channel, reporter_type=reported_by,
        reporter_name=reporter_name, reason_id=reason_id,
        reason_text=reason_text, message=message)
    logger.info("Absence reported: %s %s → %s via %s", student.student_id,
                date_from, date_to, channel)
    out = get_report(report_id)
    assert out is not None
    return out


# ── Self-certification ──────────────────────────────────────────────

def _term_window(date: str) -> tuple[str, str]:
    """The term a date falls in, or a rolling quarter if none is set up."""
    term = calendar.term_for(date)
    if term is not None:
        return term.start_date, term.end_date
    anchor = _dt.date.fromisoformat(date)
    return ((anchor - _dt.timedelta(days=90)).isoformat(),
            (anchor + _dt.timedelta(days=90)).isoformat())


def self_cert_status(student_id: str, *,
                     on: str | None = None) -> SelfCertStatus:
    """How many self-certified days a learner has used this term."""
    init_db()
    student = _require_student(student_id)
    on = core._validate_date(on or _dt.date.today().isoformat())
    window_from, window_to = _term_window(on)
    cap = int(thresholds.value_of(thresholds.SELF_CERT_CAP, default=3.0) or 3)

    used = 0
    for report in list_reports(student_id=student.student_id,
                               date_from=window_from, date_to=window_to,
                               state=ACCEPTED):
        if report.self_certified:
            used += report.days
    return SelfCertStatus(student_id=student.student_id, used_days=used,
                          cap=cap, window_from=window_from,
                          window_to=window_to)


def self_certify(
    student_id: str,
    date_from: str,
    *,
    date_to: str | None = None,
    reason_text: str | None = None,
    reason_id: int | None = None,
    message: str | None = None,
    channel: str = PORTAL,
) -> AbsenceReport:
    """A learner declares their own absence, and it is coded at once.

    Refused once the term's cap is used up — not as a punishment, but
    because a learner who has been ill four times this term needs a
    conversation rather than a fifth form.
    """
    init_db()
    student = _require_student(student_id)
    date_from, date_to = _validate_span(date_from, date_to)
    status = self_cert_status(student.student_id, on=date_from)
    days = (_dt.date.fromisoformat(date_to)
            - _dt.date.fromisoformat(date_from)).days + 1
    if status.remaining < days:
        raise ValidationError(
            f"{student.student_id} has {status.remaining} self-certified "
            f"day(s) left this term ({status.label}) — this needs "
            "authorising by staff instead")

    report = report_absence(
        student.student_id, date_from, date_to=date_to, channel=channel,
        reported_by=STUDENT, reporter_name=student.full_name,
        reason_id=reason_id, reason_text=reason_text or "Self-certified",
        message=message)
    store.store_update(report.report_id, self_certified=1, kind="Illness")
    accept(report.report_id, code=SELF_CERT_CODE,
           decided_by=student.student_id,
           note="Self-certified by the learner",
           data_source=SELF_CERT_SOURCE)
    out = get_report(report.report_id)
    assert out is not None
    return out


# ── Deciding a report ───────────────────────────────────────────────

def accept(
    report_id: int,
    *,
    code: str = DEFAULT_ACCEPT_CODE,
    decided_by: str | None = None,
    note: str | None = None,
    reason_id: int | None = None,
    data_source: str = "manual",
) -> ApplyResult:
    """Turn a report into marks.

    Codes every timetabled lesson across the reported span. Lessons on
    closed days are skipped, submitted registers are skipped, and the
    count of what actually landed comes back — a report that wrote
    nothing because the whole week was half term should say so rather
    than reading as actioned.
    """
    init_db()
    report = get_report(report_id)
    if report is None:
        raise ValidationError(f"No absence report with id {report_id}")
    if report.state == ACCEPTED:
        raise ValidationError(f"Report #{report_id} has already been accepted")
    code = codes.validate_code(code)
    if reason_id is None:
        reason_id = report.reason_id

    written = 0
    used: list[str] = []
    skipped: list[str] = []
    cursor = _dt.date.fromisoformat(report.date_from)
    end = _dt.date.fromisoformat(report.date_to)
    while cursor <= end:
        date = cursor.isoformat()
        cursor += _dt.timedelta(days=1)
        if not calendar.is_open(date):
            skipped.append(date)
            continue
        weekday = _dt.date.fromisoformat(date).weekday() + 1
        slots = [s for s in tt.list_slots(student_id=report.student_id)
                 if s.day == weekday]
        slots = weeks.filter_slots(slots, date)
        if not slots:
            skipped.append(date)
            continue
        marked_here = 0
        for slot in slots:
            if reg.is_locked(slot.slot_id, date):
                continue
            try:
                marked_here += core.save_register(
                    slot.slot_id, date,
                    {report.student_id: {
                        "code": code, "reason_id": reason_id,
                        "notes": report.reason_text,
                        "data_source": data_source}},
                    actor=decided_by,
                    reason=f"Absence reported by {report.reported_by.lower()}"
                           f" on {report.received_at or 'an earlier date'}",
                    allow_retro=True)
            except ValidationError as e:
                logger.debug("Absence report skipped slot #%d on %s: %s",
                             slot.slot_id, date, e)
        written += marked_here
        (used if marked_here else skipped).append(date)

    store.store_update(report_id, state=store.APPROVED, code=code,
                       reason_id=reason_id, decided_by=decided_by,
                       decided_at=_now(), decision_note=note,
                       marks_written=written)
    logger.info("Absence report #%d accepted as %s: %d mark(s)", report_id,
                code, written)
    return ApplyResult(report_id=report_id, marks_written=written,
                       dates=used, skipped=skipped)


def reject(report_id: int, *, reason: str,
           decided_by: str | None = None) -> AbsenceReport:
    """Decline a report — the explanation was not accepted.

    The report stays. "We were told and did not accept it" is a
    materially different record from "nobody told us", and only one of
    them is defensible at a panel.
    """
    init_db()
    report = get_report(report_id)
    if report is None:
        raise ValidationError(f"No absence report with id {report_id}")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to reject a report")
    store.store_update(report_id, state=store.DECLINED,
                       decided_by=decided_by, decided_at=_now(),
                       decision_note=note)
    out = get_report(report_id)
    assert out is not None
    return out


# ── Reads ───────────────────────────────────────────────────────────

def get_report(report_id: int) -> AbsenceReport | None:
    init_db()
    r = store.get_request(report_id)
    return _from_store(r) if r is not None and r.origin == store.ORIGIN_REPORT \
        else None


def get_legacy_report(old_report_id: int) -> AbsenceReport | None:
    """A report by its id in the pre-unification table."""
    init_db()
    r = store.by_legacy_ref(store.LEGACY_REPORTS, old_report_id)
    return _from_store(r) if r is not None else None


def list_reports(
    *,
    student_id: str | None = None,
    state: str | None = None,
    channel: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    self_certified: bool | None = None,
    limit: int = 200,
) -> list[AbsenceReport]:
    init_db()
    if state and state not in STATES:
        raise ValidationError(f"State must be one of: {', '.join(STATES)}")
    rows = store.list_requests(
        student_id=student_id,
        state=_TO_STORE[state] if state else None,
        date_from=date_from, date_to=date_to, limit=limit,
        origins=(store.ORIGIN_REPORT,),
        channel=validate_channel(channel) if channel else None,
        self_certified=self_certified, newest_first=True)
    return [_from_store(r) for r in rows]


def queue(*, with_names: bool = True) -> list[AbsenceReport]:
    """Reports waiting on a decision, oldest absence first.

    The list somebody works through after the phones quieten down. Its
    length is the honest measure of how far behind the office is.
    """
    out = list_reports(state=PENDING)
    out.sort(key=lambda r: (r.date_from, r.report_id))
    if with_names and out:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        index = {s.student_id: s.full_name for s in _students.list_students()}
        for report in out:
            report.student_name = index.get(report.student_id)
    return out


def queue_count() -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_leave_requests "
            "WHERE origin = ? AND state = ?",
            (store.ORIGIN_REPORT, store.REQUESTED)).fetchone()
    return int(r["n"])


def reports_for(student_id: str, *, date: str) -> list[AbsenceReport]:
    """Any report covering one learner on one date.

    Called when somebody is looking at an unexplained absence and
    wondering whether anyone rang about it.
    """
    date = core._validate_date(date)
    return [r for r in list_reports(student_id=student_id)
            if r.date_from <= date <= r.date_to]


def explained(student_id: str, date: str) -> bool:
    """Whether anybody has offered an explanation for this absence."""
    return any(r.state in (PENDING, ACCEPTED)
               for r in reports_for(student_id, date=date))


def channel_breakdown(*, date_from: str | None = None,
                      date_to: str | None = None) -> dict[str, int]:
    """How reports are arriving — the case for or against the portal."""
    out: dict[str, int] = {}
    for report in list_reports(date_from=date_from, date_to=date_to,
                               limit=5000):
        out[report.channel] = out.get(report.channel, 0) + 1
    return out


def self_certification_report(*, date_from: str | None = None,
                              date_to: str | None = None
                              ) -> list[SelfCertStatus]:
    """Who is at or near their self-certification cap."""
    init_db()
    seen: dict[str, SelfCertStatus] = {}
    for report in list_reports(state=ACCEPTED, self_certified=True,
                               date_from=date_from, date_to=date_to,
                               limit=5000):
        if report.student_id not in seen:
            seen[report.student_id] = self_cert_status(report.student_id)
    return sorted(seen.values(), key=lambda s: -s.used_days)


# ── Portal entry points ─────────────────────────────────────────────
#
# The parent and student portals call these, never report_absence /
# self_certify directly: the identity comes from the signed-in session
# and is checked against the learner before anything is written.

def _access_denied(message: str) -> Exception:
    try:
        from education_system.systems.sixth_form.domain.governance.user_management import (  # noqa: E501
            access as _access,
        )
        return _access.AccessDenied(message)
    except (ImportError, AttributeError):   # pragma: no cover - optional dep
        return PermissionError(message)


def _parent_account(parent_username: str) -> Any:
    from education_system.systems.sixth_form.domain.operations.communications.parent_portal import (  # noqa: E501
        parent_portal as _portal,
    )
    account = _portal.account_for_username(parent_username)
    if account is None:
        raise _access_denied(
            f"{parent_username or 'This account'} has no active parent "
            "portal account")
    return account, _portal


def report_absence_as_parent(
    parent_username: str,
    student_id: str,
    date_from: str,
    *,
    date_to: str | None = None,
    reason_text: str | None = None,
    reason_id: int | None = None,
    message: str | None = None,
    channel: str = PORTAL,
) -> AbsenceReport:
    """A parent reports their child's absence from the parent portal.

    The parent is identified by their signed-in username; the report is
    refused (``AccessDenied``) unless the portal account is linked to
    the learner. Lands in the queue as Pending, like a phone call.
    """
    account, portal = _parent_account(parent_username)
    sid = (student_id or "").strip()
    if not portal.is_linked(account.account_id, sid):
        raise _access_denied(
            f"{account.username} is not linked to student {sid}")
    return report_absence(
        sid, date_from, date_to=date_to, channel=channel,
        reported_by=PARENT, reporter_name=account.full_name,
        reason_id=reason_id, reason_text=reason_text,
        message=message)


def _require_active_student(student_id: str) -> Any:
    student = _require_student(student_id)
    if getattr(student, "status", "Active") not in ("Active", None):
        raise _access_denied(
            f"{student.student_id} is not an active student")
    return student


def report_absence_as_student(
    student_id: str,
    date_from: str,
    *,
    date_to: str | None = None,
    reason_text: str | None = None,
    reason_id: int | None = None,
    message: str | None = None,
    channel: str = PORTAL,
) -> AbsenceReport:
    """A learner tells the college about an absence for staff to decide.

    For anything that is not a self-certifiable illness — a learner who
    has used their self-certification, or a reason staff should code.
    """
    student = _require_active_student(student_id)
    return report_absence(
        student.student_id, date_from, date_to=date_to, channel=channel,
        reported_by=STUDENT, reporter_name=student.full_name,
        reason_id=reason_id, reason_text=reason_text, message=message)


def self_certify_as_student(
    student_id: str,
    date_from: str,
    *,
    date_to: str | None = None,
    reason_text: str | None = None,
    reason_id: int | None = None,
    message: str | None = None,
    channel: str = PORTAL,
) -> AbsenceReport:
    """A learner self-certifies from the student portal (coded at once).

    Same cap as :func:`self_certify`; raises ``ValidationError`` with the
    remaining allowance when it is used up.
    """
    student = _require_active_student(student_id)
    return self_certify(
        student.student_id, date_from, date_to=date_to,
        reason_text=reason_text, reason_id=reason_id, message=message,
        channel=channel)


def report_absence_for(principal: Any, student_id: str | None,
                       date_from: str, **kwargs: Any) -> AbsenceReport:
    """Report an absence as whoever ``principal`` is.

    ``principal`` is an ``access.Principal`` (``.is_parent``,
    ``.is_student``, ``.username``, ``.student_id``). A parent must name
    a linked learner; a student always reports for themselves (a
    ``student_id`` naming anybody else is refused).
    """
    if getattr(principal, "is_parent", False):
        if not student_id:
            raise ValidationError("Say which learner the report is for")
        return report_absence_as_parent(principal.username, student_id,
                                        date_from, **kwargs)
    if getattr(principal, "is_student", False):
        own = principal.student_id
        if not own:
            raise _access_denied("This login is not linked to a student")
        if student_id and student_id.strip() != own:
            raise _access_denied("Learners can only report their own absence")
        return report_absence_as_student(own, date_from, **kwargs)
    raise _access_denied("Only parents and students report absence here")


def self_certify_for(principal: Any, date_from: str,
                     **kwargs: Any) -> AbsenceReport:
    """Self-certify as the signed-in learner. Parents cannot self-certify."""
    if not getattr(principal, "is_student", False) or not principal.student_id:
        raise _access_denied("Only a learner can self-certify an absence")
    return self_certify_as_student(principal.student_id, date_from, **kwargs)


def portal_history(principal: Any, student_id: str | None = None, *,
                   limit: int = 50) -> list[AbsenceReport]:
    """Reports a parent or learner may see — their own, or a linked child's."""
    if getattr(principal, "is_student", False) and principal.student_id:
        sid = principal.student_id
    elif getattr(principal, "is_parent", False) and student_id:
        account, portal = _parent_account(principal.username)
        if not portal.is_linked(account.account_id, student_id.strip()):
            raise _access_denied(
                f"{account.username} is not linked to student {student_id}")
        sid = student_id.strip()
    else:
        raise _access_denied("No learner to show absence reports for")
    return list_reports(student_id=sid, limit=limit)
