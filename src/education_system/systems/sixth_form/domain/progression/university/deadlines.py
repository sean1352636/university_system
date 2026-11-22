"""UCAS deadlines per cycle, applied to each application automatically.

Until this module the workflow's due dates were optional and typed in by
hand, one stage at a time, so "who is going to miss the deadline" had no
answer unless somebody had remembered to type one. UCAS deadlines are
not a matter of opinion — they follow from the cycle and from what the
learner has applied for — so they are computed here:

``OCT_EQUAL``   15 October (the year before entry). The equal-consideration
                deadline for **Oxford, Cambridge** and most **medicine,
                dentistry and veterinary** courses. An application with any
                such choice must be in by this date.
``JAN_EQUAL``   the January equal-consideration deadline for everything else.
``JUNE_FINAL``  30 June — the last date to apply to choices directly; after
                it an applicant goes into Clearing.
``RESULTS_DAY`` A-level results day, used by Extra/Clearing (see
                :mod:`.post_offer`).

Each external deadline also has an **internal college deadline**, earlier,
so references and checks happen before UCAS's date rather than on it.

Every computed date can be overridden for a cycle (``ucas_cycle_deadlines``)
because UCAS does move them — that table, not this file, is the place to
correct a date. Every choice's October-deadline flag is detected from the
university and course, and can be overridden per choice
(``ucas_choice_deadline_flags``) for the course the keywords get wrong.

The application's deadline then sets the due dates on its workflow stages
(:func:`stage_due_dates`, read by :func:`.workflow.get_pipeline`), unless
somebody has set a stage's date by hand.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass
from typing import Any

from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_UCAS_DB

OCT_EQUAL = "OCT_EQUAL"
JAN_EQUAL = "JAN_EQUAL"
JUNE_FINAL = "JUNE_FINAL"
RESULTS_DAY = "RESULTS_DAY"

DEADLINE_KEYS: tuple[str, ...] = (OCT_EQUAL, JAN_EQUAL, JUNE_FINAL, RESULTS_DAY)
DEADLINE_LABELS: dict[str, str] = {
    OCT_EQUAL: "15 October — Oxford, Cambridge, medicine/dentistry/veterinary",
    JAN_EQUAL: "January equal-consideration deadline",
    JUNE_FINAL: "30 June — final date for direct applications",
    RESULTS_DAY: "A-level results day",
}

#: Days before each external deadline that the college's own deadline
#: falls. Defaults only — set the internal date per cycle to override.
#: January's lead is long because the college closes for Christmas and
#: references need writing in term time.
DEFAULT_INTERNAL_LEAD_DAYS: dict[str, int] = {
    OCT_EQUAL: 21,
    JAN_EQUAL: 42,
    JUNE_FINAL: 21,
}

#: How close to the internal deadline an unfinished application turns
#: "At risk".
AT_RISK_DAYS: int = 21

#: Workflow stage due dates, as days *before* the internal deadline.
#: Ordered like the pipeline so each stage is due before the next.
STAGE_OFFSETS_DAYS: dict[str, int] = {
    "ucas_registered": 42,
    "statement_drafted": 28,
    "reference_requested": 35,
    "predicted_grades": 21,
    "statement_approved": 14,
    "reference_submitted": 7,
    "tutor_check": 3,
    "application_submitted": 0,
}

EARLY_ROUTES: tuple[str, ...] = (
    "Oxford", "Cambridge", "Medicine", "Dentistry", "Veterinary",
    "Other October-deadline course",
)
#: A manual override meaning "the keywords flagged this, but it is not an
#: October-deadline course" (e.g. a medical-sciences degree).
NOT_EARLY = "Not early"
FLAG_VALUES: tuple[str, ...] = EARLY_ROUTES + (NOT_EARLY,)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ucas_cycle_deadlines (
    cycle_year     INTEGER NOT NULL,
    deadline_key   TEXT NOT NULL,
    deadline_date  TEXT,
    internal_date  TEXT,
    notes          TEXT,
    updated_by     TEXT,
    updated_at     TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (cycle_year, deadline_key)
);

CREATE TABLE IF NOT EXISTS ucas_choice_deadline_flags (
    choice_id    INTEGER PRIMARY KEY,
    early_route  TEXT NOT NULL,
    notes        TEXT,
    set_by       TEXT,
    set_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (choice_id) REFERENCES ucas_choices(choice_id) ON DELETE CASCADE
);
"""


class ValidationError(ValueError):
    """Raised for invalid deadline input."""


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    _ucas.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True
    logger.debug("UCAS deadlines schema ready at %s", DB_PATH)


def _today() -> _dt.date:
    return _dt.date.today()


def _iso(d: _dt.date | None) -> str | None:
    return d.isoformat() if d else None


def _parse(value: Any, label: str) -> _dt.date | None:
    if value in (None, ""):
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None


# ── Computed defaults ───────────────────────────────────────────────

def last_wednesday_of_january(year: int) -> _dt.date:
    """The last Wednesday in January of *year*."""
    d = _dt.date(year, 1, 31)
    # Monday=0 … Wednesday=2.
    return d - _dt.timedelta(days=(d.weekday() - 2) % 7)


def results_thursday(year: int) -> _dt.date:
    """The Thursday falling 13–19 August — where results day has landed
    in recent years (2023: 17th, 2024: 15th, 2025: 14th, 2026: 13th).
    JCQ publishes the real date; set it per cycle if it differs."""
    d = _dt.date(year, 8, 13)
    return d + _dt.timedelta(days=(3 - d.weekday()) % 7)


def computed_deadline(cycle_year: int, key: str) -> _dt.date:
    """The default date for *key* in the cycle for entry in *cycle_year*.

    ``cycle_year`` is the entry year, as everywhere else in the UCAS
    package (:func:`.workflow.default_cycle_year`): the October deadline
    therefore falls in ``cycle_year - 1``.
    """
    if key == OCT_EQUAL:
        return _dt.date(cycle_year - 1, 10, 15)
    if key == JAN_EQUAL:
        # VERIFY AGAINST UCAS EACH CYCLE. The January deadline was
        # historically the last Wednesday in January, which is what this
        # computes; UCAS has moved it before (for 2026 entry it published
        # 14 January). Record the published date in ucas_cycle_deadlines
        # whenever it differs — the override wins over this computation.
        return last_wednesday_of_january(cycle_year)
    if key == JUNE_FINAL:
        return _dt.date(cycle_year, 6, 30)
    if key == RESULTS_DAY:
        return results_thursday(cycle_year)
    raise ValidationError(f"Unknown deadline: {key}")


@dataclass
class Deadline:
    cycle_year: int
    key: str
    label: str
    date: _dt.date
    internal_date: _dt.date | None
    source: str            # "computed" or "configured"
    notes: str | None


def get_deadlines(cycle_year: int) -> list[Deadline]:
    """Every deadline for the cycle, overrides applied."""
    init_db()
    with _connect() as conn:
        overrides = {r["deadline_key"]: r for r in conn.execute(
            "SELECT * FROM ucas_cycle_deadlines WHERE cycle_year = ?",
            (cycle_year,))}
    out: list[Deadline] = []
    for key in DEADLINE_KEYS:
        computed = computed_deadline(cycle_year, key)
        row = overrides.get(key)
        date = (_parse(row["deadline_date"], key) if row and row["deadline_date"]
                else computed)
        lead = DEFAULT_INTERNAL_LEAD_DAYS.get(key)
        internal = (_parse(row["internal_date"], key) if row and row["internal_date"]
                    else (date - _dt.timedelta(days=lead) if lead is not None else None))
        out.append(Deadline(
            cycle_year=cycle_year, key=key, label=DEADLINE_LABELS[key],
            date=date, internal_date=internal,
            source="configured" if row else "computed",
            notes=row["notes"] if row else None))
    return out


def get_deadline(cycle_year: int, key: str) -> Deadline:
    for d in get_deadlines(cycle_year):
        if d.key == key:
            return d
    raise ValidationError(f"Unknown deadline: {key}")


def set_deadline(cycle_year: int, key: str, *, deadline_date: str | None,
                 internal_date: str | None = None, notes: str | None = None,
                 updated_by: str | None = None) -> Deadline:
    """Record the published (or college-chosen) dates for one deadline."""
    init_db()
    if key not in DEADLINE_KEYS:
        raise ValidationError(f"Unknown deadline: {key}")
    try:
        cycle_year = int(cycle_year)
    except (TypeError, ValueError):
        raise ValidationError("Cycle year must be a year") from None
    ext = _parse(deadline_date, "Deadline date")
    internal = _parse(internal_date, "Internal deadline")
    effective = ext or computed_deadline(cycle_year, key)
    if internal and internal > effective:
        raise ValidationError(
            "The internal deadline must fall on or before the UCAS deadline.")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO ucas_cycle_deadlines
                   (cycle_year, deadline_key, deadline_date, internal_date,
                    notes, updated_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(cycle_year, deadline_key) DO UPDATE SET
                   deadline_date = excluded.deadline_date,
                   internal_date = excluded.internal_date,
                   notes = excluded.notes,
                   updated_by = excluded.updated_by,
                   updated_at = datetime('now')""",
            (cycle_year, key, _iso(ext), _iso(internal),
             (notes or "").strip() or None, updated_by))
        conn.commit()
    logger.info("UCAS deadline %s for cycle %d set (%s / internal %s)",
                key, cycle_year, _iso(ext), _iso(internal))
    return get_deadline(cycle_year, key)


def reset_deadline(cycle_year: int, key: str) -> bool:
    """Drop the override; the computed date applies again."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM ucas_cycle_deadlines WHERE cycle_year=? AND deadline_key=?",
            (cycle_year, key))
        conn.commit()
    return bool(cur.rowcount)


# ── October-deadline detection per choice ──────────────────────────

_OXFORD = re.compile(r"\boxford\b", re.I)
_CAMBRIDGE = re.compile(r"\bcambridge\b", re.I)
# Not October-deadline institutions despite the name.
_NOT_OXBRIDGE = re.compile(r"brookes|anglia|ruskin", re.I)
_MEDICINE = re.compile(r"\bmedicine\b|\bmbbs\b|\bmbchb\b|\bbm\s?bs\b", re.I)
_DENTISTRY = re.compile(r"\bdentistry\b|\bdental surgery\b|\bbds\b", re.I)
_VET = re.compile(r"veterinary (medicine|science|surgery)|\bbvsc\b|\bbvetmed\b|\bbvm", re.I)
# Courses that contain the words but sit on the January deadline.
_NOT_EARLY_COURSE = re.compile(
    r"biomedic|medical science|medicinal|pharmac|dental (hygiene|therapy|technology|nursing)"
    r"|veterinary (nursing|physiotherapy|bioscience)", re.I)
# UCAS course-code families: A1xx medicine, A2xx dentistry, D1xx veterinary.
_CODE_ROUTES = (("A1", "Medicine"), ("A2", "Dentistry"), ("D1", "Veterinary"))


def detect_early_route(university: str | None, course_name: str | None,
                       course_code: str | None = None) -> str | None:
    """Why this choice is on the 15 October deadline, or None."""
    uni = university or ""
    course = course_name or ""
    if not _NOT_OXBRIDGE.search(uni):
        if _OXFORD.search(uni):
            return "Oxford"
        if _CAMBRIDGE.search(uni):
            return "Cambridge"
    if _NOT_EARLY_COURSE.search(course):
        return None
    if _MEDICINE.search(course):
        return "Medicine"
    if _DENTISTRY.search(course):
        return "Dentistry"
    if _VET.search(course):
        return "Veterinary"
    code = (course_code or "").strip().upper()
    for prefix, route in _CODE_ROUTES:
        if len(code) == 4 and code.startswith(prefix) and code[2:].isdigit():
            return route
    return None


@dataclass
class ChoiceFlag:
    choice_id: int
    choice_order: int
    university: str
    course_name: str
    detected: str | None
    override: str | None
    notes: str | None

    @property
    def effective(self) -> str | None:
        if self.override == NOT_EARLY:
            return None
        return self.override or self.detected


def choice_flags(application_id: int) -> list[ChoiceFlag]:
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    choices = _ucas.list_choices(application_id)
    with _connect() as conn:
        overrides = {r["choice_id"]: r for r in conn.execute(
            "SELECT f.* FROM ucas_choice_deadline_flags f "
            "JOIN ucas_choices c ON c.choice_id = f.choice_id "
            "WHERE c.application_id = ?", (application_id,))}
    out = []
    for c in choices:
        o = overrides.get(c.choice_id)
        out.append(ChoiceFlag(
            choice_id=c.choice_id, choice_order=c.choice_order,
            university=c.university, course_name=c.course_name,
            detected=detect_early_route(c.university, c.course_name, c.course_code),
            override=o["early_route"] if o else None,
            notes=o["notes"] if o else None))
    return out


def set_choice_flag(choice_id: int, early_route: str | None, *,
                    notes: str | None = None, set_by: str | None = None) -> None:
    """Override detection for one choice; ``None``/"" clears the override."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    if _ucas.get_choice(choice_id) is None:
        raise ValidationError(f"No choice with id {choice_id}")
    route = (early_route or "").strip()
    with _connect() as conn:
        if not route:
            conn.execute("DELETE FROM ucas_choice_deadline_flags WHERE choice_id=?",
                         (choice_id,))
        else:
            if route not in FLAG_VALUES:
                raise ValidationError(
                    f"Flag must be one of: {', '.join(FLAG_VALUES)}")
            conn.execute(
                """INSERT INTO ucas_choice_deadline_flags
                       (choice_id, early_route, notes, set_by, set_at)
                   VALUES (?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(choice_id) DO UPDATE SET
                       early_route = excluded.early_route,
                       notes = excluded.notes, set_by = excluded.set_by,
                       set_at = datetime('now')""",
                (choice_id, route, (notes or "").strip() or None, set_by))
        conn.commit()
    logger.info("Deadline flag for choice #%d → %s", choice_id, route or "(auto)")


# ── Per-application deadline ────────────────────────────────────────

STATE_SUBMITTED = "Submitted"
STATE_SUBMITTED_LATE = "Submitted after equal consideration"
STATE_MISSED = "Missed equal consideration"
STATE_CLOSED = "Past 30 June — Clearing only"
STATE_OVERDUE = "Overdue (internal deadline passed)"
STATE_AT_RISK = "At risk"
STATE_ON_TRACK = "On track"


@dataclass
class ApplicationDeadline:
    application_id: int
    student_id: str
    student_name: str
    cycle_year: int
    key: str                    # OCT_EQUAL or JAN_EQUAL
    reason: str
    deadline: _dt.date
    internal_date: _dt.date
    next_key: str               # the deadline still in play
    next_deadline: _dt.date
    submitted_at: str | None
    state: str
    days_to_internal: int
    outstanding: tuple[str, ...]

    def as_row(self) -> dict[str, Any]:
        return {
            "application_id": self.application_id,
            "student_id": self.student_id, "student_name": self.student_name,
            "cycle_year": self.cycle_year, "key": self.key,
            "reason": self.reason, "deadline": _iso(self.deadline),
            "internal_date": _iso(self.internal_date),
            "next_deadline": f"{self.next_key} {_iso(self.next_deadline)}",
            "submitted_at": self.submitted_at or "", "state": self.state,
            "days_to_internal": self.days_to_internal,
            "outstanding": ", ".join(self.outstanding),
        }


def _outstanding_stages(student_id: str, cycle_year: int) -> tuple[str, ...]:
    """Pipeline stages not yet done, read straight from the stage table so
    a deadline report does not re-run the whole pipeline sync."""
    from education_system.systems.sixth_form.domain.progression.university import (
        workflow as _wf,
    )
    try:
        pipeline = _wf.get_pipeline(student_id, cycle_year)
    except Exception:
        logger.debug("pipeline unavailable for %s", student_id, exc_info=True)
        return ()
    return tuple(s["label"] for s in pipeline["stages"]
                 if s["status"] not in ("Complete", "N/A")
                 and s["key"] != "application_submitted")


def application_deadline(application_id: int, *, today: _dt.date | None = None,
                         with_outstanding: bool = True,
                         _deadlines: dict[str, Deadline] | None = None,
                         _names: dict[str, str] | None = None) -> ApplicationDeadline:
    """The deadline that applies to one application and where it stands."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    app = _ucas.get_application(application_id)
    if app is None:
        raise ValidationError(f"No application with id {application_id}")
    today = today or _today()
    dl = _deadlines or {d.key: d for d in get_deadlines(app.cycle_year)}
    flags = [f for f in choice_flags(application_id) if f.effective]
    if flags:
        key = OCT_EQUAL
        reason = "; ".join(f"choice {f.choice_order}: {f.effective}" for f in flags)
    else:
        key = JAN_EQUAL
        reason = "No October-deadline choices"
    primary = dl[key]
    internal = primary.internal_date or primary.date

    # The deadline still in play once the primary one has gone.
    next_key = key
    for candidate in ((key, JAN_EQUAL, JUNE_FINAL) if key == OCT_EQUAL
                      else (key, JUNE_FINAL)):
        next_key = candidate
        if today <= dl[candidate].date:
            break
    next_date = dl[next_key].date

    submitted = (app.submitted_at or "").strip() or None
    outstanding: tuple[str, ...] = ()
    if submitted:
        try:
            sub_date = _dt.date.fromisoformat(submitted[:10])
        except ValueError:
            sub_date = None
        state = (STATE_SUBMITTED_LATE if sub_date and sub_date > primary.date
                 else STATE_SUBMITTED)
    elif today > dl[JUNE_FINAL].date:
        state = STATE_CLOSED
    elif today > primary.date:
        state = STATE_MISSED
    elif today > internal:
        state = STATE_OVERDUE
    else:
        if with_outstanding:
            outstanding = _outstanding_stages(app.student_id, app.cycle_year)
        state = (STATE_AT_RISK
                 if (internal - today).days <= AT_RISK_DAYS and outstanding
                 else STATE_ON_TRACK)
    if not submitted and state != STATE_ON_TRACK and not outstanding and with_outstanding:
        outstanding = _outstanding_stages(app.student_id, app.cycle_year)

    if _names is not None:
        name = _names.get(app.student_id, "(unknown)")
    else:
        from education_system.systems.sixth_form.domain.learners.students import (
            students as _students,
        )
        s = _students.get_student(app.student_id)
        name = s.full_name if s else "(unknown)"
    return ApplicationDeadline(
        application_id=app.application_id, student_id=app.student_id,
        student_name=name, cycle_year=app.cycle_year, key=key, reason=reason,
        deadline=primary.date, internal_date=internal, next_key=next_key,
        next_deadline=next_date, submitted_at=submitted, state=state,
        days_to_internal=(internal - today).days, outstanding=outstanding)


def cohort_deadlines(cycle_year: int, *, today: _dt.date | None = None,
                     state: str | None = None) -> list[ApplicationDeadline]:
    """Every application in the cycle with its deadline, soonest first."""
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    dl = {d.key: d for d in get_deadlines(cycle_year)}
    out = []
    for app in _ucas.list_applications(cycle_year=cycle_year):
        row = application_deadline(app.application_id, today=today,
                                   _deadlines=dl, _names=names)
        if state and row.state != state:
            continue
        out.append(row)
    out.sort(key=lambda r: (r.state in (STATE_SUBMITTED, STATE_SUBMITTED_LATE),
                            r.internal_date, r.student_name))
    return out


def overdue(cycle_year: int, *, today: _dt.date | None = None) -> list[ApplicationDeadline]:
    """Applications past an internal or UCAS deadline and not submitted."""
    return [r for r in cohort_deadlines(cycle_year, today=today)
            if r.state in (STATE_OVERDUE, STATE_MISSED, STATE_CLOSED)]


def at_risk(cycle_year: int, *, today: _dt.date | None = None) -> list[ApplicationDeadline]:
    return [r for r in cohort_deadlines(cycle_year, today=today)
            if r.state == STATE_AT_RISK]


# ── Workflow due dates ──────────────────────────────────────────────

def stage_due_dates(student_id: str, cycle_year: int) -> dict[str, str]:
    """``stage_key -> YYYY-MM-DD`` for the student's application, or {}.

    Read by :func:`.workflow.get_pipeline`, which writes them onto stages
    whose date was not set by hand. Empty when the student has no
    application in the cycle — there are no choices to decide which
    deadline applies.
    """
    init_db()
    from education_system.systems.sixth_form.domain.progression.university import ucas as _ucas
    app = _ucas.get_application_for_student(student_id, cycle_year=cycle_year)
    if app is None:
        return {}
    info = application_deadline(app.application_id, with_outstanding=False)
    return {key: _iso(info.internal_date - _dt.timedelta(days=offset))
            for key, offset in STAGE_OFFSETS_DAYS.items()}


__all__ = [
    "OCT_EQUAL", "JAN_EQUAL", "JUNE_FINAL", "RESULTS_DAY", "DEADLINE_KEYS",
    "DEADLINE_LABELS", "DEFAULT_INTERNAL_LEAD_DAYS", "AT_RISK_DAYS",
    "STAGE_OFFSETS_DAYS", "EARLY_ROUTES", "NOT_EARLY", "FLAG_VALUES",
    "ValidationError", "Deadline", "ChoiceFlag", "ApplicationDeadline",
    "last_wednesday_of_january", "results_thursday", "computed_deadline",
    "get_deadlines", "get_deadline", "set_deadline", "reset_deadline",
    "detect_early_route", "choice_flags", "set_choice_flag",
    "application_deadline", "cohort_deadlines", "overdue", "at_risk",
    "stage_due_dates",
]
