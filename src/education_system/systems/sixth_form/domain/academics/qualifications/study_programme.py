"""Study programme planned hours and the 16-19 funding band.

A learner's planned hours for a funding year are

* **qualification hours** — one figure per learning aim live in that
  year. The aim's own ``planned_hours`` wins (it is what goes on the
  ILR); without it the hours are worked out from the timetable — the
  weekly lessons of the learner's class groups on a course teaching that
  aim, times :data:`TEACHING_WEEKS` — then the course's planned hours,
  then the subject's guided learning hours;
* plus **non-qualification hours** — tutorial, work experience,
  enrichment, employability — recorded per year in
  ``programme_hours``.

Aims withdrawn before their funding qualifying period are left out:
they do not count towards the learner's funded hours.

The total places the learner in a funding band, see
:data:`FUNDING_BANDS`.
"""

from __future__ import annotations

import datetime as _dt
import logging
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims,
)

logger = logging.getLogger(__name__)


#: Who may change study programme hours; reading it is open.
WRITE_CAPABILITIES = ('students.manage', 'admissions')


def _require_writer(action: str) -> None:
    """Refuse a write unless the signed-in principal (or a
    ``_guard.system_actor`` block) holds one of :data:`WRITE_CAPABILITIES`.
    Nobody signed in is refused, never trusted."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    _guard.require_any(WRITE_CAPABILITIES, action)


def can_write() -> bool:
    """Whether the signed-in user may change study programme hours (for screens)."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    return any(_guard.can(c) for c in WRITE_CAPABILITIES)

DB_PATH: Path | None = None

#: Teaching weeks used to turn a weekly timetable into annual hours.
#: Override per call with ``teaching_weeks=``.
TEACHING_WEEKS: int = 36
#: Lesson length assumed when a timetable slot has no start/end time.
DEFAULT_PERIOD_MINUTES: int = 60

NON_QUAL_CATEGORIES: tuple[str, ...] = (
    "Tutorial", "Work experience", "Enrichment", "Employability",
    "Industry placement", "Other",
)

# 16-19 funding bands by planned hours in the funding year.
# MUST be checked against the current ESFA "Funding guidance for young
# people" each year — the thresholds (Band 5 moved from 540 to 580 hours)
# and the age rules change. Each row: (band, minimum hours, maximum hours
# or None, who it applies to).
FUNDING_BANDS: tuple[tuple[str, int, int | None, str], ...] = (
    ("Band 5",  580, None, "16-17 (and 18+ high needs)"),
    ("Band 4a", 450, 579,  "16-17 (and 18+ high needs)"),
    ("Band 4b", 450, None, "18+ (not high needs)"),
    ("Band 3",  360, 449,  "all ages"),
    ("Band 2",  280, 359,  "all ages"),
    ("Band 1",    0, 279,  "all ages (funded per hour)"),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS programme_hours (
    entry_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    academic_year  TEXT NOT NULL,
    category       TEXT NOT NULL,
    hours          REAL NOT NULL,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, academic_year, category),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
"""


class ValidationError(ValueError):
    """Raised for invalid study-programme input."""


@dataclass
class AimHours:
    aim: learning_aims.LearningAim
    timetabled_weekly_hours: float
    timetabled_annual_hours: float
    planned_hours: float
    source: str           # "aim", "timetable", "course", "subject", "none"
    counted: bool         # False if withdrawn before qualifying period


@dataclass
class NonQualHours:
    entry_id: int
    student_id: str
    academic_year: str
    category: str
    hours: float
    notes: str | None


@dataclass
class ProgrammeHours:
    student_id: str
    academic_year: str
    age_on_31_august: int | None
    aims: list[AimHours] = field(default_factory=list)
    non_qualification: list[NonQualHours] = field(default_factory=list)
    high_needs: bool = False

    @property
    def qualification_hours(self) -> float:
        return round(sum(a.planned_hours for a in self.aims if a.counted), 1)

    @property
    def non_qualification_hours(self) -> float:
        return round(sum(n.hours for n in self.non_qualification), 1)

    @property
    def total_hours(self) -> float:
        return round(self.qualification_hours + self.non_qualification_hours, 1)

    @property
    def band(self) -> str:
        return funding_band(self.total_hours, self.age_on_31_august,
                            high_needs=self.high_needs)


# ── DB plumbing ────────────────────────────────────────────────────

def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _s,
    )
    return _s


def _db_path() -> Path:
    return Path(DB_PATH) if DB_PATH is not None else Path(_students().DB_PATH)


_READY_PATHS: set[str] = set()


def _connect() -> _sql.Connection:
    from education_system import paths
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(_db_path()))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    key = str(_db_path())
    if key in _READY_PATHS:
        return
    _students().init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY_PATHS.add(key)


# ── Band ───────────────────────────────────────────────────────────

def funding_band(hours: float, age: int | None = None, *,
                 high_needs: bool = False) -> str:
    """Funding band for planned hours (see FUNDING_BANDS).

    450+ hours is Band 5 / 4a for 16-17 year olds (and 18+ with high
    needs) and Band 4b for other 18+ learners. Unknown age is treated as
    16-17.
    """
    adult = age is not None and age >= 18 and not high_needs
    if hours >= 450:
        if adult:
            return "Band 4b"
        return "Band 5" if hours >= 580 else "Band 4a"
    if hours >= 360:
        return "Band 3"
    if hours >= 280:
        return "Band 2"
    return "Band 1"


def age_on_31_august(date_of_birth: str | None, academic_year: str) -> int | None:
    """Age on 31 August before the academic year starts (funding age)."""
    if not date_of_birth:
        return None
    try:
        dob = _dt.date.fromisoformat(date_of_birth)
    except ValueError:
        return None
    ref = _dt.date(int(academic_year[:4]), 8, 31)
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))


# ── Non-qualification hours ────────────────────────────────────────

def set_non_qual_hours(student_id: str, academic_year: str, category: str,
                       hours: Any, notes: str | None = None) -> NonQualHours:
    _require_writer("recording study programme hours")
    init_db()
    year = _year(academic_year)
    if category not in NON_QUAL_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(NON_QUAL_CATEGORIES)}")
    try:
        h = round(float(hours), 1)
    except (TypeError, ValueError):
        raise ValidationError("Hours must be a number") from None
    if h < 0 or h > 1500:
        raise ValidationError("Hours must be between 0 and 1500")
    if _students().get_student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO programme_hours (student_id, academic_year,
                   category, hours, notes) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(student_id, academic_year, category) DO UPDATE SET
                   hours = excluded.hours, notes = excluded.notes""",
            (student_id, year, category, h, (notes or "").strip() or None))
        conn.commit()
    return next(n for n in list_non_qual_hours(student_id, year)
                if n.category == category)


def delete_non_qual_hours(entry_id: int) -> bool:
    _require_writer("deleting study programme hours")
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM programme_hours WHERE entry_id = ?",
                           (int(entry_id),))
        conn.commit()
    return cur.rowcount > 0


def list_non_qual_hours(student_id: str, academic_year: str) -> list[NonQualHours]:
    init_db()
    with _connect() as conn:
        return [NonQualHours(entry_id=r["entry_id"], student_id=r["student_id"],
                             academic_year=r["academic_year"],
                             category=r["category"], hours=r["hours"],
                             notes=r["notes"])
                for r in conn.execute(
                    "SELECT * FROM programme_hours WHERE student_id = ? AND "
                    "academic_year = ? ORDER BY category",
                    (student_id, _year(academic_year)))]


def _year(value: Any) -> str:
    y = (str(value).strip() if value else "")
    learning_aims.academic_year_start(y)    # raises on a bad year
    return y


# ── Timetable (read-only) ──────────────────────────────────────────

def _slot_minutes(slot: Any) -> int:
    try:
        if slot.start_time and slot.end_time:
            sh, sm = (int(x) for x in slot.start_time.split(":")[:2])
            eh, em = (int(x) for x in slot.end_time.split(":")[:2])
            mins = (eh * 60 + em) - (sh * 60 + sm)
            if mins > 0:
                return mins
    except (ValueError, AttributeError):
        pass
    return DEFAULT_PERIOD_MINUTES


def _weekly_hours_by_aim_key(student_id: str) -> tuple[dict[tuple[str, str], float],
                                                       dict[tuple[str, str], float]]:
    """({(type, subject): weekly hours}, {(type, subject): course planned hours})
    from the learner's class groups and their timetable slots."""
    weekly: dict[tuple[str, str], float] = {}
    course_hours: dict[tuple[str, str], float] = {}
    try:
        from education_system.systems.sixth_form.domain.academics.class_groups import (
            class_groups as _cg,
        )
        from education_system.systems.sixth_form.domain.academics.courses import (
            courses as _courses,
        )
        from education_system.systems.sixth_form.domain.academics.timetable import (
            timetable as _tt,
        )
        for g in _cg.groups_for_student(student_id):
            c = _courses.get_course(g.course_id)
            if c is None:
                continue
            key = (_courses.effective_qualification_type(c), c.subject)
            mins = sum(_slot_minutes(s) for s in _tt.list_slots(group_id=g.group_id))
            weekly[key] = weekly.get(key, 0.0) + mins / 60.0
            if c.planned_hours:
                course_hours[key] = max(course_hours.get(key, 0.0), c.planned_hours)
    except Exception:
        logger.debug("Timetable hours unavailable for %s", student_id, exc_info=True)
    return weekly, course_hours


def _subject_glh(subject: str) -> float | None:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        s = _subjects.get_subject_by_name(subject)
        return s.guided_learning_hours if s else None
    except Exception:
        return None


def _aim_in_year(aim: learning_aims.LearningAim, academic_year: str) -> bool:
    start = learning_aims.academic_year_start(academic_year)
    year_start = _dt.date(start.year, 8, 1).isoformat()
    year_end = _dt.date(start.year + 1, 7, 31).isoformat()
    end = aim.withdrawal_date or aim.actual_end_date or aim.planned_end_date
    return aim.start_date <= year_end and (end is None or end >= year_start)


# ── Planned hours ──────────────────────────────────────────────────

def planned_hours(student_id: str, academic_year: str | None = None, *,
                  teaching_weeks: int | None = None,
                  high_needs: bool = False) -> ProgrammeHours:
    """A learner's planned hours and funding band for a funding year."""
    year = academic_year or learning_aims.academic_year_for(
        _dt.date.today().isoformat())
    year = _year(year)
    weeks = teaching_weeks or TEACHING_WEEKS
    student = _students().get_student(student_id)
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    weekly, course_hours = _weekly_hours_by_aim_key(student_id)
    out = ProgrammeHours(
        student_id=student_id, academic_year=year,
        age_on_31_august=age_on_31_august(student.date_of_birth, year),
        high_needs=high_needs)
    for aim in learning_aims.list_aims(student_id):
        if not _aim_in_year(aim, year):
            continue
        key = (aim.qualification_type, aim.subject)
        wk = round(weekly.get(key, 0.0), 2)
        annual = round(wk * weeks, 1)
        if aim.planned_hours is not None:
            hours, source = aim.planned_hours, "aim"
        elif annual:
            hours, source = annual, "timetable"
        elif key in course_hours:
            hours, source = course_hours[key], "course"
        elif (glh := _subject_glh(aim.subject)) is not None:
            hours, source = glh, "subject"
        else:
            hours, source = 0.0, "none"
        counted = not learning_aims.qualifying_check_for(aim).withdrawn_before_qualifying
        out.aims.append(AimHours(aim=aim, timetabled_weekly_hours=wk,
                                 timetabled_annual_hours=annual,
                                 planned_hours=round(float(hours), 1),
                                 source=source, counted=counted))
    out.non_qualification = list_non_qual_hours(student_id, year)
    return out


@dataclass
class BandRow:
    student_id: str
    student_name: str
    hours: ProgrammeHours


def band_report(academic_year: str | None = None, *,
                teaching_weeks: int | None = None) -> list[BandRow]:
    """Planned hours and band for every active learner."""
    rows: list[BandRow] = []
    for s in _students().list_students():
        if s.status != "Active":
            continue
        rows.append(BandRow(student_id=s.student_id, student_name=s.full_name,
                            hours=planned_hours(s.student_id, academic_year,
                                                teaching_weeks=teaching_weeks)))
    return rows


def band_counts(rows: list[BandRow]) -> dict[str, int]:
    counts = {b[0]: 0 for b in FUNDING_BANDS}
    for r in rows:
        counts[r.hours.band] = counts.get(r.hours.band, 0) + 1
    return counts
