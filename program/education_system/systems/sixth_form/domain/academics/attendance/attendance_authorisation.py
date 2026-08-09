"""Absence authorisation and off-site placement for Sixth Form Attendance.

Sibling to :mod:`attendance`. Two related questions the plain row could
not answer:

**Who authorised this?** "Authorised" was a status, which meant it was a
claim with nobody's name against it. Any member of staff could turn an
unauthorised absence into an authorised one and leave no trace of having
done so. Here, authorising is an *act*: it stamps who did it, when, on
what grounds, and against which absence reason, and it writes to the
amendment trail. :func:`pending` is the other half — the queue of
absences nobody has yet made a decision about, which is the work list a
college attendance officer actually has.

**Where was the learner?** Sixth form runs on placements: work
experience, partner-college lessons, university days, fieldwork. Those
learners are neither present in the room nor absent from education, and
recording them as either is wrong. :func:`set_offsite` records the
placement location against an approved-activity code, so the register
says what actually happened and the funding return can prove it.

Both operations route through :func:`attendance.update_record`, so the
submitted-register lock applies here exactly as it does everywhere else.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_audit as audit,
    attendance_codes as codes,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# Suggested off-site locations. Not a closed list — `offsite_location`
# is free text, because no fixed vocabulary survives contact with a real
# placement register — but these cover the common cases and keep the
# picker from being an empty box.
OFFSITE_KINDS: tuple[str, ...] = (
    "Work placement",
    "Partner college",
    "University session",
    "Educational visit",
    "Fieldwork",
    "Sports fixture",
    "Alternative provision",
)

# The code an off-site placement is normally recorded under, by kind.
OFFSITE_DEFAULT_CODES: dict[str, str] = {
    "Work placement":        "W",
    "Partner college":       "D",
    "University session":    "B",
    "Educational visit":     "V",
    "Fieldwork":             "V",
    "Sports fixture":        "V",
    "Alternative provision": "B",
}

# Codes an authorisation may land on. Authorising means deciding the
# absence was acceptable, so the result has to be an authorised-absence
# code — you cannot "authorise" someone into `O`.
AUTHORISABLE_CODES: tuple[str, ...] = tuple(
    m.code for m in codes.codes_for_meaning(codes.AUTHORISED))
DEFAULT_AUTHORISED_CODE: str = "C"

# How long an unexplained absence may sit in the queue before it is
# worth chasing rather than waiting for. Used by :func:`pending` to
# flag rows, not to change them.
STALE_AFTER_DAYS: int = 5


@dataclass
class PendingAbsence:
    """An absence waiting for somebody to make a decision about it."""

    record: core.AttendanceRecord
    student_name: str
    days_waiting: int
    reason_name: str | None

    @property
    def record_id(self) -> int:
        return self.record.record_id

    @property
    def stale(self) -> bool:
        return self.days_waiting >= STALE_AFTER_DAYS

    @property
    def label(self) -> str:
        code = self.record.code or "?"
        return (f"{self.record.date} {self.student_name} "
                f"[{code}] {self.reason_name or 'no reason given'}")


@dataclass
class AuthorisationResult:
    """What a bulk authorisation did."""

    authorised: int = 0
    skipped: int = 0
    failures: list[str] | None = None

    @property
    def message(self) -> str:
        bits = [f"{self.authorised} authorised"]
        if self.skipped:
            bits.append(f"{self.skipped} skipped")
        if self.failures:
            bits.append(f"{len(self.failures)} failed")
        return ", ".join(bits)


@dataclass
class OffsiteRow:
    """One off-site placement mark, ready to display."""

    record: core.AttendanceRecord
    student_name: str
    location: str
    code: str


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """No tables of its own — the columns live on ``attendance_records``
    and the trail lives in :mod:`attendance_audit`."""
    codes.init_db()
    audit.init_db()


def _student_names(student_ids: set[str]) -> dict[str, str]:
    if not student_ids:
        return {}
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return {s.student_id: s.full_name for s in _students.list_students()
            if s.student_id in student_ids}


def _days_between(earlier: str, later: str) -> int:
    import datetime as _dt
    return (_dt.date.fromisoformat(later)
            - _dt.date.fromisoformat(earlier)).days


def _today() -> str:
    import datetime as _dt
    return _dt.date.today().isoformat()


# ── Authorising ─────────────────────────────────────────────────────

def _validate_authorised_code(value: Any) -> str:
    code = codes.validate_code(value)
    if code not in AUTHORISABLE_CODES:
        raise ValidationError(
            f"{code} is not an authorised-absence code. Use one of: "
            + " ".join(AUTHORISABLE_CODES))
    return code


def authorise(
    record_id: int,
    *,
    authorised_by: str,
    code: str | None = None,
    reason_id: int | None = None,
    note: str | None = None,
) -> core.AttendanceRecord:
    """Sign an absence off as authorised.

    Sets the mark code (defaulting to `C`, "other authorised
    circumstances"), stamps the authoriser and the time, and records the
    grounds. ``reason_id`` names *what happened*; if the reason carries a
    default code and the caller did not name one, that code is used —
    so authorising an absence against "Medical appointment" lands on `M`
    without anybody having to remember the letter.

    Authorising an already-authorised row re-stamps it, which is the
    right behaviour when a decision is revisited: the amendment trail
    keeps the previous authoriser.
    """
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No record with id {record_id}")
    if record.voided:
        raise ValidationError(
            f"Record #{record_id} is voided — restore it before authorising")
    if not (authorised_by or "").strip():
        raise ValidationError("An authorisation needs an authoriser")
    core._lifecycle().assert_unlocked(record.slot_id, record.date)

    if reason_id is not None:
        reason_id = codes.validate_reason_id(reason_id)
    if code:
        code = _validate_authorised_code(code)
    elif reason_id is not None and codes.suggest_code(reason_id):
        suggested = codes.suggest_code(reason_id)
        # A reason may suggest an approved-activity code (work
        # experience is `W`, not an absence at all) — respect it rather
        # than forcing it into the authorised bucket.
        code = suggested or DEFAULT_AUTHORISED_CODE
    else:
        code = DEFAULT_AUTHORISED_CODE

    updated = core.update_record(
        record_id,
        {"code": code,
         "status": codes.status_for_code(code),
         **({"reason_id": reason_id} if reason_id is not None else {})},
        actor=authorised_by, reason=note or "Absence authorised",
        allow_retro=True)

    stamp = (authorised_by or "").strip()
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_records
                  SET authorised_by = ?, authorised_at = datetime('now'),
                      authorisation_note = ?
                WHERE record_id = ?""",
            (stamp, (note or "").strip() or None, record_id))
        conn.commit()

    out = core.get_record(record_id)
    assert out is not None
    audit.record_amendment(
        record=out, action="authorise", field="authorised_by",
        old_value=record.authorised_by, new_value=stamp,
        reason=note or "Absence authorised", actor=authorised_by)
    logger.info("Authorised record #%d (%s on %s) as %s by %s",
                record_id, record.student_id, record.date, code, stamp)
    return out


def unauthorise(
    record_id: int,
    *,
    actor: str | None = None,
    reason: str | None = None,
    code: str = "O",
) -> core.AttendanceRecord:
    """Withdraw an authorisation.

    Clears the stamp and recodes the absence — by default to `O`
    (unauthorised), which is the decision being made. Pass ``code="N"``
    instead to put it back in the queue as undecided.
    """
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No record with id {record_id}")
    if not record.is_authorised:
        raise ValidationError(f"Record #{record_id} is not authorised")
    core._lifecycle().assert_unlocked(record.slot_id, record.date)
    code = codes.validate_code(code)

    core.update_record(
        record_id, {"code": code, "status": codes.status_for_code(code)},
        actor=actor, reason=reason or "Authorisation withdrawn",
        allow_retro=True)
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_records
                  SET authorised_by = NULL, authorised_at = NULL,
                      authorisation_note = NULL
                WHERE record_id = ?""",
            (record_id,))
        conn.commit()

    out = core.get_record(record_id)
    assert out is not None
    audit.record_amendment(
        record=out, action="unauthorise", field="authorised_by",
        old_value=record.authorised_by, new_value=None,
        reason=reason or "Authorisation withdrawn", actor=actor)
    logger.info("Withdrew authorisation on record #%d", record_id)
    return out


def bulk_authorise(
    record_ids: list[int],
    *,
    authorised_by: str,
    code: str | None = None,
    reason_id: int | None = None,
    note: str | None = None,
) -> AuthorisationResult:
    """Authorise many rows at once — a week of illness in one action.

    Rows that cannot be authorised (voided, locked, already gone) are
    counted and reported rather than aborting the batch: the point of a
    bulk action is that it gets through the list.
    """
    result = AuthorisationResult(failures=[])
    for record_id in record_ids:
        try:
            authorise(record_id, authorised_by=authorised_by, code=code,
                      reason_id=reason_id, note=note)
            result.authorised += 1
        except ValidationError as e:
            result.skipped += 1
            assert result.failures is not None
            result.failures.append(f"#{record_id}: {e}")
    logger.info("Bulk authorise: %s", result.message)
    return result


def authorise_range(
    student_id: str,
    *,
    date_from: str,
    date_to: str,
    authorised_by: str,
    code: str | None = None,
    reason_id: int | None = None,
    note: str | None = None,
) -> AuthorisationResult:
    """Authorise every absence a learner has in a date window.

    The hospital-admission case: one decision covering every lesson the
    learner missed, without hunting each row down.
    """
    init_db()
    absences = [r for r in core.list_records(
        student_id=student_id, date_from=date_from, date_to=date_to)
        if codes.is_absence(r.code) or r.status == "Absent"]
    return bulk_authorise([r.record_id for r in absences],
                          authorised_by=authorised_by, code=code,
                          reason_id=reason_id, note=note)


# ── The decision queue ──────────────────────────────────────────────

def pending(
    *,
    group_id: int | None = None,
    student_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    stale_only: bool = False,
) -> list[PendingAbsence]:
    """Absences nobody has decided about yet, oldest first.

    "Undecided" means an absence with no authoriser stamp and no
    unauthorised-absence code — i.e. sitting on `N`, or on a bare
    ``Absent`` status from before codes existed. An absence already
    coded `O` has been decided (the decision was "no"), so it is not in
    the queue.
    """
    init_db()
    rows = core.list_records(group_id=group_id, student_id=student_id,
                             date_from=date_from, date_to=date_to)
    today = _today()
    reasons = {r.reason_id: r.name for r in
               codes.list_reasons(active_only=False)}
    names = _student_names({r.student_id for r in rows})

    out: list[PendingAbsence] = []
    for record in rows:
        if record.is_authorised:
            continue
        undecided = (record.code in (None, "", "N")
                     and record.status in ("Absent", "Authorised"))
        if not undecided:
            continue
        out.append(PendingAbsence(
            record=record,
            student_name=names.get(record.student_id, record.student_id),
            days_waiting=max(0, _days_between(record.date, today)),
            reason_name=(reasons.get(record.reason_id)
                         if record.reason_id is not None else None),
        ))
    out.sort(key=lambda p: (p.record.date, p.student_name))
    if stale_only:
        out = [p for p in out if p.stale]
    return out


def pending_count(**kwargs: Any) -> int:
    return len(pending(**kwargs))


def authorised_by_staff(*, date_from: str | None = None,
                        date_to: str | None = None) -> dict[str, int]:
    """Who has been signing absences off, and how many.

    A single name against most of the college's authorisations is worth
    a conversation — either they are carrying the whole job or the
    account is being shared.
    """
    init_db()
    clauses = ["voided = 0", "authorised_by IS NOT NULL"]
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT authorised_by AS who, COUNT(*) AS n "
            f"FROM attendance_records WHERE {' AND '.join(clauses)} "
            "GROUP BY authorised_by ORDER BY n DESC", args).fetchall()
    return {r["who"]: int(r["n"]) for r in rows}


# ── Off-site placement ──────────────────────────────────────────────

def suggest_offsite_code(kind: str) -> str:
    """The mark code an off-site kind is normally recorded under."""
    return OFFSITE_DEFAULT_CODES.get((kind or "").strip(), "B")


def set_offsite(
    record_id: int,
    *,
    location: str,
    code: str | None = None,
    actor: str | None = None,
    note: str | None = None,
) -> core.AttendanceRecord:
    """Record that the learner was off site but still in education.

    The code defaults to the one that matches the location when it is
    one of :data:`OFFSITE_KINDS`, and to `B` (off-site educational
    activity) otherwise. Approved-activity codes count as attending, so
    this does not dent the learner's percentage — which is the whole
    point of having them.
    """
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No record with id {record_id}")
    if record.voided:
        raise ValidationError(f"Record #{record_id} is voided")
    location = (location or "").strip()
    if not location:
        raise ValidationError("An off-site mark needs a location")
    if len(location) > 120:
        raise ValidationError("Location must be 120 characters or fewer")
    core._lifecycle().assert_unlocked(record.slot_id, record.date)

    code = codes.validate_code(code) if code else suggest_offsite_code(location)
    out = core.update_record(
        record_id,
        {"code": code, "status": codes.status_for_code(code),
         "is_offsite": True, "offsite_location": location},
        actor=actor, reason=note or f"Off site: {location}",
        allow_retro=True)
    audit.record_amendment(
        record=out, action="offsite", field="offsite_location",
        old_value=record.offsite_location, new_value=location,
        reason=note, actor=actor)
    logger.info("Record #%d marked off site at %s (%s)",
                record_id, location, code)
    return out


def clear_offsite(record_id: int, *, actor: str | None = None,
                  code: str = "/") -> core.AttendanceRecord:
    """Undo an off-site mark, putting the learner back in the room."""
    init_db()
    record = core.get_record(record_id)
    if record is None:
        raise ValidationError(f"No record with id {record_id}")
    if not record.is_offsite:
        raise ValidationError(f"Record #{record_id} is not marked off site")
    core._lifecycle().assert_unlocked(record.slot_id, record.date)
    code = codes.validate_code(code)

    out = core.update_record(
        record_id,
        {"code": code, "status": codes.status_for_code(code),
         "is_offsite": False, "offsite_location": None},
        actor=actor, reason="Off-site placement cleared",
        allow_retro=True)
    audit.record_amendment(
        record=out, action="offsite", field="offsite_location",
        old_value=record.offsite_location, new_value=None,
        reason="Off-site placement cleared", actor=actor)
    return out


def list_offsite(*, group_id: int | None = None,
                 student_id: str | None = None,
                 date_from: str | None = None,
                 date_to: str | None = None) -> list[OffsiteRow]:
    """Every off-site mark in a window — the placement register."""
    init_db()
    rows = core.list_records(group_id=group_id, student_id=student_id,
                             date_from=date_from, date_to=date_to,
                             offsite_only=True)
    names = _student_names({r.student_id for r in rows})
    return [OffsiteRow(record=r,
                       student_name=names.get(r.student_id, r.student_id),
                       location=r.offsite_location or "(unspecified)",
                       code=r.code or "?")
            for r in rows]


def offsite_breakdown(*, date_from: str | None = None,
                      date_to: str | None = None) -> dict[str, int]:
    """Off-site marks grouped by location, busiest first."""
    init_db()
    clauses = ["voided = 0", "is_offsite = 1"]
    args: list[Any] = []
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    with _connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(NULLIF(TRIM(offsite_location), ''), "
            "'(unspecified)') AS place, COUNT(*) AS n "
            f"FROM attendance_records WHERE {' AND '.join(clauses)} "
            "GROUP BY place ORDER BY n DESC", args).fetchall()
    return {r["place"]: int(r["n"]) for r in rows}
