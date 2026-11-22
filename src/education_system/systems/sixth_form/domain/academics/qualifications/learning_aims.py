"""Learning aims: every qualification a learner is studying.

The student record only ever had ``subject_1..subject_3`` — three
A-level slots — which left no room for a fourth A level, the EPQ, Core
Maths, a BTEC, a T Level or the GCSE English / maths resits a 16-19
study programme has to carry. A *learning aim* is one of those
qualifications for one learner, with the dates, awarding body, aim
(QAN / LARS) code, planned hours and status the funding returns need.

Two tables, both in the students database:

* ``learning_aims`` — one row per learner per qualification.
* ``learning_aim_changes`` — the history: every creation, withdrawal,
  course change and completion, with effective date, reason, approver
  and whether the aim had reached its funding qualifying period.

**The legacy slots are kept, as mirrors.** ``subject_1..3`` are written
from the first three *active A-level-type* aims (A Level / AS Level, in
``display_order``) after every change, so the dozens of screens and
reports that read ``Student.subjects`` keep working. Saving the student
form still works the other way too: a subject added to a slot becomes
an aim, a subject removed from a slot is withdrawn through the normal
workflow (so it lands in the history).

Existing learners are **backfilled lazily** from their slots the first
time their aims are read (:func:`ensure_backfilled`). It is idempotent:
a slot subject only gets an aim if the learner has never had an A-level
aim in that subject, so a withdrawn subject is never resurrected.

Funding qualifying period (ESFA 16-19 funding guidance): a learner only
counts for funding on an aim once they have been in learning for

* 42 days, for an aim planned to last 24 weeks or more;
* 14 days, for an aim planned to last 2 to 24 weeks;
* 1 day, for anything shorter;

counted from the start date. :func:`qualifying_check` answers that for
an aim and flags "withdrawn before qualifying period".
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.qualifications import (
    grade_scales,
)

logger = logging.getLogger(__name__)

#: None follows ``students.DB_PATH`` (the owner of sixthform.db), so a test
#: that rebinds the students module is isolated here too. Rebind to a
#: path to point this module somewhere else explicitly.
DB_PATH: Path | None = None

STATUSES: tuple[str, ...] = ("Active", "Withdrawn", "Completed", "Transferred")
DEFAULT_STATUS = "Active"

#: Who/what created an aim. Informational only.
SOURCES: tuple[str, ...] = (
    "manual", "backfill", "form", "option_blocks", "change",
)

AWARDING_BODIES: tuple[str, ...] = (
    "AQA", "OCR", "Pearson", "WJEC/Eduqas", "CIE", "NCFE", "City & Guilds",
    "Other",
)

#: Qualifying-period rule, longest first: (minimum planned length in
#: days, days the learner must be in learning). Check against the
#: current ESFA 16-19 funding regulations each year.
QUALIFYING_PERIOD_RULES: tuple[tuple[int, int], ...] = (
    (24 * 7, 42),   # 24 weeks or more  -> 42 days
    (14, 14),       # 2 to 24 weeks     -> 14 days
    (0, 1),         # under 2 weeks     -> 1 day
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AIM_CODE_RE = re.compile(r"^[A-Z0-9/]{4,12}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS learning_aims (
    aim_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    qualification_type TEXT NOT NULL,
    subject            TEXT NOT NULL,
    awarding_body      TEXT,
    aim_code           TEXT,
    academic_year      TEXT,
    start_date         TEXT NOT NULL,
    planned_end_date   TEXT,
    actual_end_date    TEXT,
    status             TEXT NOT NULL DEFAULT 'Active',
    withdrawal_date    TEXT,
    withdrawal_reason  TEXT,
    planned_hours      REAL,
    is_core_aim        INTEGER NOT NULL DEFAULT 0,
    display_order      INTEGER NOT NULL DEFAULT 0,
    source             TEXT NOT NULL DEFAULT 'manual',
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aims_student ON learning_aims(student_id);
CREATE INDEX IF NOT EXISTS idx_aims_subject ON learning_aims(subject);
CREATE INDEX IF NOT EXISTS idx_aims_status  ON learning_aims(status);
CREATE INDEX IF NOT EXISTS idx_aims_type    ON learning_aims(qualification_type);

CREATE TABLE IF NOT EXISTS learning_aim_changes (
    change_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    aim_id               INTEGER NOT NULL,
    student_id           TEXT NOT NULL,
    action               TEXT NOT NULL,
    effective_date       TEXT,
    reason               TEXT,
    approved_by          TEXT,
    recorded_by          TEXT,
    from_detail          TEXT,
    to_detail            TEXT,
    new_aim_id           INTEGER,
    days_in_learning     INTEGER,
    qualifying_days      INTEGER,
    qualifying_met       INTEGER,
    recorded_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (aim_id) REFERENCES learning_aims(aim_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_aim_changes_aim     ON learning_aim_changes(aim_id);
CREATE INDEX IF NOT EXISTS idx_aim_changes_student ON learning_aim_changes(student_id);
"""


class ValidationError(ValueError):
    """Raised for invalid learning-aim input."""


@dataclass
class LearningAim:
    aim_id: int
    student_id: str
    qualification_type: str
    subject: str
    awarding_body: str | None
    aim_code: str | None
    academic_year: str | None
    start_date: str
    planned_end_date: str | None
    actual_end_date: str | None
    status: str
    withdrawal_date: str | None
    withdrawal_reason: str | None
    planned_hours: float | None
    is_core_aim: bool
    display_order: int
    source: str
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def is_a_level_type(self) -> bool:
        return self.qualification_type in grade_scales.A_LEVEL_TYPES

    @property
    def label(self) -> str:
        return f"{self.qualification_type} {self.subject}"


@dataclass
class AimChange:
    change_id: int
    aim_id: int
    student_id: str
    action: str
    effective_date: str | None
    reason: str | None
    approved_by: str | None
    recorded_by: str | None
    from_detail: str | None
    to_detail: str | None
    new_aim_id: int | None
    days_in_learning: int | None
    qualifying_days: int | None
    qualifying_met: bool | None
    recorded_at: str | None


@dataclass
class QualifyingCheck:
    """Whether an aim reached its funding qualifying period."""
    aim_id: int
    start_date: str
    planned_end_date: str | None
    planned_length_days: int | None
    qualifying_days: int
    qualifying_date: str          # first date on which the aim counts
    end_date_used: str            # withdrawal / end date, or "as of" date
    days_in_learning: int
    met: bool
    withdrawn_before_qualifying: bool
    status: str


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
    """Create the aims tables (once per database file per process)."""
    key = str(_db_path())
    if key in _READY_PATHS:
        return
    _students().init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY_PATHS.add(key)
    logger.debug("Learning-aims schema ready at %s", key)


def _row(r: _sql.Row) -> LearningAim:
    return LearningAim(
        aim_id=r["aim_id"], student_id=r["student_id"],
        qualification_type=r["qualification_type"], subject=r["subject"],
        awarding_body=r["awarding_body"], aim_code=r["aim_code"],
        academic_year=r["academic_year"], start_date=r["start_date"],
        planned_end_date=r["planned_end_date"],
        actual_end_date=r["actual_end_date"], status=r["status"],
        withdrawal_date=r["withdrawal_date"],
        withdrawal_reason=r["withdrawal_reason"],
        planned_hours=r["planned_hours"],
        is_core_aim=bool(r["is_core_aim"]),
        display_order=int(r["display_order"] or 0),
        source=r["source"], notes=r["notes"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_change(r: _sql.Row) -> AimChange:
    met = r["qualifying_met"]
    return AimChange(
        change_id=r["change_id"], aim_id=r["aim_id"],
        student_id=r["student_id"], action=r["action"],
        effective_date=r["effective_date"], reason=r["reason"],
        approved_by=r["approved_by"], recorded_by=r["recorded_by"],
        from_detail=r["from_detail"], to_detail=r["to_detail"],
        new_aim_id=r["new_aim_id"],
        days_in_learning=r["days_in_learning"],
        qualifying_days=r["qualifying_days"],
        qualifying_met=(None if met is None else bool(met)),
        recorded_at=r["recorded_at"],
    )


# ── Date helpers ───────────────────────────────────────────────────

def _parse_date(value: Any, label: str, *, required: bool = False) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        if required:
            raise ValidationError(f"{label} is required")
        return None
    if isinstance(value, _dt.date):
        return value.isoformat()
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real calendar date") from None
    return s


def academic_year_for(date_iso: str | None) -> str | None:
    """'2025/26' for any date from 1 Aug 2025 to 31 Jul 2026."""
    if not date_iso:
        return None
    d = _dt.date.fromisoformat(date_iso)
    start = d.year if d.month >= 8 else d.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


def academic_year_start(academic_year: str) -> _dt.date:
    """1 September of the first year of '2025/26'."""
    m = re.match(r"^(\d{4})/\d{2}$", (academic_year or "").strip())
    if not m:
        raise ValidationError("Academic year must look like '2025/26'")
    return _dt.date(int(m.group(1)), 9, 1)


def _today() -> str:
    return _dt.date.today().isoformat()


# ── Qualifying period ──────────────────────────────────────────────

def qualifying_days_for(start_date: str, planned_end_date: str | None) -> int:
    """Days in learning an aim needs before it counts for funding.

    An aim with no planned end date is treated as a long (24 week+) aim,
    which is what every two-year A level and one-year resit is.
    """
    if not planned_end_date:
        return QUALIFYING_PERIOD_RULES[0][1]
    length = (_dt.date.fromisoformat(planned_end_date)
              - _dt.date.fromisoformat(start_date)).days + 1
    for min_len, days in QUALIFYING_PERIOD_RULES:
        if length >= min_len:
            return days
    return QUALIFYING_PERIOD_RULES[-1][1]


def _qualifying(start_date: str, planned_end_date: str | None,
                end_date: str, status: str, aim_id: int = 0) -> QualifyingCheck:
    start = _dt.date.fromisoformat(start_date)
    end = _dt.date.fromisoformat(end_date)
    q_days = qualifying_days_for(start_date, planned_end_date)
    in_learning = max(0, (end - start).days + 1)
    planned_len = None
    if planned_end_date:
        planned_len = (_dt.date.fromisoformat(planned_end_date) - start).days + 1
    met = in_learning >= q_days
    return QualifyingCheck(
        aim_id=aim_id, start_date=start_date,
        planned_end_date=planned_end_date,
        planned_length_days=planned_len, qualifying_days=q_days,
        qualifying_date=(start + _dt.timedelta(days=q_days - 1)).isoformat(),
        end_date_used=end_date, days_in_learning=in_learning, met=met,
        withdrawn_before_qualifying=(
            status in ("Withdrawn", "Transferred") and not met),
        status=status,
    )


def qualifying_check(aim_id: int, *, as_of: str | None = None) -> QualifyingCheck:
    """Funding qualifying-period check for one aim.

    The end of learning is the withdrawal date for a withdrawn or
    transferred aim, the actual end date for a completed one, and
    ``as_of`` (default today) for an active one.
    """
    aim = get_aim(aim_id)
    if aim is None:
        raise ValidationError(f"No learning aim #{aim_id}")
    return qualifying_check_for(aim, as_of=as_of)


def qualifying_check_for(aim: LearningAim, *, as_of: str | None = None
                         ) -> QualifyingCheck:
    if aim.status in ("Withdrawn", "Transferred"):
        end = aim.withdrawal_date or aim.actual_end_date or _today()
    elif aim.status == "Completed":
        end = aim.actual_end_date or aim.planned_end_date or _today()
    else:
        end = _parse_date(as_of, "As-of date") or _today()
    if end < aim.start_date:
        end = aim.start_date if aim.status != "Active" else end
    if end < aim.start_date:
        # Active aim that has not started yet: nothing in learning.
        q = qualifying_days_for(aim.start_date, aim.planned_end_date)
        return QualifyingCheck(
            aim_id=aim.aim_id, start_date=aim.start_date,
            planned_end_date=aim.planned_end_date, planned_length_days=None,
            qualifying_days=q,
            qualifying_date=(_dt.date.fromisoformat(aim.start_date)
                             + _dt.timedelta(days=q - 1)).isoformat(),
            end_date_used=end, days_in_learning=0, met=False,
            withdrawn_before_qualifying=False, status=aim.status)
    return _qualifying(aim.start_date, aim.planned_end_date, end,
                       aim.status, aim.aim_id)


def qualifying_if_withdrawn(aim: LearningAim, effective_date: str
                            ) -> QualifyingCheck:
    """Preview: the qualifying check if ``aim`` were withdrawn on that date."""
    eff = _parse_date(effective_date, "Effective date", required=True)
    return _qualifying(aim.start_date, aim.planned_end_date,
                       max(eff, aim.start_date), "Withdrawn", aim.aim_id)


# ── Validation ─────────────────────────────────────────────────────

def _validate_type(value: Any) -> str:
    raw = (str(value).strip() if value else "") or grade_scales.DEFAULT_QUALIFICATION_TYPE
    canon = grade_scales.canonical_type(raw)
    if canon is None:
        raise ValidationError(
            "Qualification type must be one of: "
            + ", ".join(grade_scales.QUALIFICATION_TYPES))
    return canon


def _validate_subject(subject: Any, qualification_type: str) -> str:
    name = (str(subject).strip() if subject else "")
    if not name:
        raise ValidationError("Subject is required")
    # A levels have always been checked against the subject catalogue;
    # vocational and resit aims often are not in it (a BTEC "Applied
    # Science" or GCSE "English Language" resit), so only A-level-type
    # aims are held to it.
    if qualification_type in grade_scales.A_LEVEL_TYPES:
        try:
            from education_system.systems.sixth_form.domain.academics.subjects import (
                subjects as _subjects,
            )
            if not _subjects.is_valid_subject(name):
                raise ValidationError(f"Unknown subject: {name}")
        except ImportError:
            pass
    return name


def _validate_payload(data: dict[str, Any], *, partial: bool = False,
                      existing: LearningAim | None = None) -> dict[str, Any]:
    def pick(key: str, default: Any = None) -> Any:
        if key in data:
            return data[key]
        if existing is not None:
            return getattr(existing, key)
        return default

    out: dict[str, Any] = {}
    qtype = _validate_type(pick("qualification_type"))
    out["qualification_type"] = qtype
    out["subject"] = _validate_subject(pick("subject"), qtype)

    body = (pick("awarding_body") or "").strip() or None
    out["awarding_body"] = body

    code = (pick("aim_code") or "").strip().upper().replace(" ", "") or None
    if code is not None and not _AIM_CODE_RE.match(code):
        raise ValidationError(
            "Aim / QAN code must be 4-12 letters, digits or '/' "
            "(e.g. 601/4635/X or 6014635X)")
    out["aim_code"] = code

    start = _parse_date(pick("start_date"), "Start date", required=True)
    out["start_date"] = start
    planned_end = _parse_date(pick("planned_end_date"), "Planned end date")
    if planned_end is not None and planned_end < start:
        raise ValidationError("Planned end date is before the start date")
    out["planned_end_date"] = planned_end

    year = (pick("academic_year") or "").strip() or academic_year_for(start)
    if year and not re.match(r"^\d{4}/\d{2}$", year):
        raise ValidationError("Academic year must look like '2025/26'")
    out["academic_year"] = year

    hours = pick("planned_hours")
    if hours in (None, ""):
        out["planned_hours"] = None
    else:
        try:
            h = float(hours)
        except (TypeError, ValueError):
            raise ValidationError("Planned hours must be a number") from None
        if h < 0 or h > 2000:
            raise ValidationError("Planned hours must be between 0 and 2000")
        out["planned_hours"] = round(h, 1)

    out["is_core_aim"] = 1 if bool(pick("is_core_aim", False)) else 0
    try:
        out["display_order"] = int(pick("display_order", 0) or 0)
    except (TypeError, ValueError):
        raise ValidationError("Display order must be a whole number") from None
    source = (pick("source") or "manual").strip()
    out["source"] = source if source in SOURCES else "manual"
    out["notes"] = (pick("notes") or "").strip() or None
    return out


# ── Reads ──────────────────────────────────────────────────────────

def get_aim(aim_id: int) -> LearningAim | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM learning_aims WHERE aim_id = ?",
                         (int(aim_id),)).fetchone()
    return _row(r) if r else None


def list_aims(student_id: str, *, status: str | None = None,
              include_inactive: bool = True,
              backfill: bool = True) -> list[LearningAim]:
    """Every learning aim for a learner, active first then by order.

    Backfills from the legacy subject slots on first read.
    """
    init_db()
    if backfill:
        ensure_backfilled(student_id)
    clauses = ["student_id = ?"]
    args: list[Any] = [student_id]
    if status:
        if status not in STATUSES:
            raise ValidationError(f"Status must be one of: {', '.join(STATUSES)}")
        clauses.append("status = ?")
        args.append(status)
    elif not include_inactive:
        clauses.append("status = 'Active'")
    sql = ("SELECT * FROM learning_aims WHERE " + " AND ".join(clauses)
           + " ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END, "
             "display_order, start_date, aim_id")
    with _connect() as conn:
        return [_row(r) for r in conn.execute(sql, args).fetchall()]


def active_aims(student_id: str) -> list[LearningAim]:
    return list_aims(student_id, status="Active")


def list_all_aims(*, status: str | None = "Active",
                  qualification_type: str | None = None,
                  subject: str | None = None,
                  academic_year: str | None = None) -> list[LearningAim]:
    """College-wide aims list (no backfill — call backfill_all first)."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if qualification_type:
        clauses.append("qualification_type = ?")
        args.append(_validate_type(qualification_type))
    if subject:
        clauses.append("subject = ?")
        args.append(subject.strip())
    if academic_year:
        clauses.append("academic_year = ?")
        args.append(academic_year.strip())
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            f"SELECT * FROM learning_aims {where} "
            "ORDER BY student_id, display_order, aim_id", args).fetchall()]


def aim_history(*, student_id: str | None = None,
                aim_id: int | None = None) -> list[AimChange]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    if aim_id is not None:
        clauses.append("(aim_id = ? OR new_aim_id = ?)")
        args.extend([int(aim_id), int(aim_id)])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        return [_row_change(r) for r in conn.execute(
            f"SELECT * FROM learning_aim_changes {where} "
            "ORDER BY recorded_at DESC, change_id DESC", args).fetchall()]


def qualification_type_for(student_id: str | None, subject: str | None
                           ) -> str | None:
    """The qualification type a learner takes ``subject`` as.

    Active aim first, then the most recent aim in any status, then the
    subject catalogue's qualification. None means "unknown" and every
    grade check then falls back to A*-U.
    """
    if not subject:
        return None
    subject = subject.strip()
    if student_id:
        try:
            init_db()
            with _connect() as conn:
                r = conn.execute(
                    """SELECT qualification_type FROM learning_aims
                        WHERE student_id = ? AND subject = ?
                        ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END,
                                 start_date DESC, aim_id DESC LIMIT 1""",
                    (student_id.strip(), subject)).fetchone()
            if r:
                return r["qualification_type"]
        except _sql.Error:
            logger.debug("qualification_type_for: aims lookup failed",
                         exc_info=True)
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        return _subjects.qualification_type_for_subject(subject)
    except Exception:
        logger.debug("qualification_type_for: catalogue lookup failed",
                     exc_info=True)
        return None


def grade_options(student_id: str | None = None, subject: str | None = None
                  ) -> tuple[str, ...]:
    """Grade list (best first) for a learner's subject; A*-U if unknown."""
    return grade_scales.grades_for(qualification_type_for(student_id, subject))


def validate_grade_for(student_id: str | None, subject: str | None,
                       grade: str) -> str:
    """Normalise ``grade`` against the learner's aim type, or raise ValueError."""
    return grade_scales.validate_grade(
        grade, qualification_type_for(student_id, subject))


def learners_on(*, subject: str | None = None,
                qualification_type: str | None = None,
                status: str | None = "Active") -> list[LearningAim]:
    return list_all_aims(status=status, subject=subject,
                         qualification_type=qualification_type)


# ── History helper ─────────────────────────────────────────────────

def _log_change(conn: _sql.Connection, *, aim: LearningAim | dict,
                action: str, effective_date: str | None = None,
                reason: str | None = None, approved_by: str | None = None,
                recorded_by: str | None = None, from_detail: str | None = None,
                to_detail: str | None = None, new_aim_id: int | None = None,
                check: QualifyingCheck | None = None) -> None:
    aim_id = aim.aim_id if isinstance(aim, LearningAim) else aim["aim_id"]
    sid = aim.student_id if isinstance(aim, LearningAim) else aim["student_id"]
    conn.execute(
        """INSERT INTO learning_aim_changes
               (aim_id, student_id, action, effective_date, reason,
                approved_by, recorded_by, from_detail, to_detail,
                new_aim_id, days_in_learning, qualifying_days, qualifying_met)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (aim_id, sid, action, effective_date, reason, approved_by,
         recorded_by, from_detail, to_detail, new_aim_id,
         check.days_in_learning if check else None,
         check.qualifying_days if check else None,
         (1 if check.met else 0) if check else None))


# ── Mirror into the legacy slots ───────────────────────────────────

def sync_mirror(student_id: str, conn: _sql.Connection | None = None) -> list[str]:
    """Write subject_1..3 from the first three active A-level-type aims."""
    own = conn is None
    if own:
        init_db()
        conn = _connect()
    try:
        placeholders = ",".join("?" * len(grade_scales.A_LEVEL_TYPES))
        rows = conn.execute(
            f"""SELECT subject FROM learning_aims
                 WHERE student_id = ? AND status = 'Active'
                   AND qualification_type IN ({placeholders})
                 ORDER BY display_order, start_date, aim_id""",
            (student_id, *grade_scales.A_LEVEL_TYPES)).fetchall()
        seen: list[str] = []
        for r in rows:
            if r["subject"] not in seen:
                seen.append(r["subject"])
        slots = (seen + [None, None, None])[:3]
        conn.execute(
            "UPDATE students SET subject_1 = ?, subject_2 = ?, subject_3 = ? "
            "WHERE student_id = ?", (*slots, student_id))
        if own:
            conn.commit()
        return [s for s in slots if s]
    finally:
        if own:
            conn.close()


# ── Backfill ───────────────────────────────────────────────────────

def _default_dates(conn: _sql.Connection, student_id: str
                   ) -> tuple[str, str | None]:
    """Start / planned end for an aim backfilled from a slot.

    Start: the learner's earliest enrolment (its start date, else 1 Sept
    of its academic year), else the date the student record was created.
    Planned end: 30 June of the year the A level finishes — two years on
    from a Year 12 start, one from a Year 13 start.
    """
    start: _dt.date | None = None
    year_group = 12
    try:
        r = conn.execute(
            """SELECT academic_year, year_group, start_date FROM enrolments
                WHERE student_id = ? AND archived_at IS NULL
                ORDER BY academic_year LIMIT 1""",
            (student_id,)).fetchone()
        if r:
            year_group = int(r["year_group"] or 12)
            if r["start_date"] and _DATE_RE.match(r["start_date"]):
                start = _dt.date.fromisoformat(r["start_date"])
            else:
                start = academic_year_start(r["academic_year"])
    except (_sql.Error, ValidationError, ValueError):
        start = None
    if start is None:
        r = conn.execute("SELECT created_at FROM students WHERE student_id = ?",
                         (student_id,)).fetchone()
        created = (r["created_at"] or "")[:10] if r else ""
        start = (_dt.date.fromisoformat(created)
                 if _DATE_RE.match(created) else _dt.date.today())
    first_year = start.year if start.month >= 8 else start.year - 1
    years = 2 if year_group <= 12 else 1
    planned_end = _dt.date(first_year + years, 6, 30)
    return start.isoformat(), planned_end.isoformat()


def ensure_backfilled(student_id: str, *, subjects: list[str] | None = None,
                      source: str = "backfill") -> int:
    """Create A-level aims for slot subjects that have never had one.

    Idempotent. ``subjects`` overrides the slots read from the record —
    the student-form save path passes the *previous* slots so a change
    made on the form is recorded against aims that existed before it.
    Returns the number of aims created.
    """
    init_db()
    created = 0
    with _connect() as conn:
        if subjects is None:
            r = conn.execute(
                "SELECT subject_1, subject_2, subject_3 FROM students "
                "WHERE student_id = ?", (student_id,)).fetchone()
            if r is None:
                return 0
            subjects = [r["subject_1"], r["subject_2"], r["subject_3"]]
        subjects = [s.strip() for s in subjects if s and s.strip()]
        if not subjects:
            return 0
        placeholders = ",".join("?" * len(grade_scales.A_LEVEL_TYPES))
        had = {r["subject"] for r in conn.execute(
            f"""SELECT subject FROM learning_aims WHERE student_id = ?
                  AND qualification_type IN ({placeholders})""",
            (student_id, *grade_scales.A_LEVEL_TYPES)).fetchall()}
        missing = [s for s in subjects if s not in had]
        if not missing:
            return 0
        start, planned_end = _default_dates(conn, student_id)
        board_for = _catalogue_boards(missing)
        for order, subj in enumerate(subjects):
            if subj not in missing:
                continue
            cur = conn.execute(
                """INSERT INTO learning_aims
                       (student_id, qualification_type, subject, awarding_body,
                        academic_year, start_date, planned_end_date, status,
                        display_order, source)
                   VALUES (?, 'A Level', ?, ?, ?, ?, ?, 'Active', ?, ?)""",
                (student_id, subj, board_for.get(subj),
                 academic_year_for(start), start, planned_end, order, source))
            _log_change(conn, aim={"aim_id": cur.lastrowid,
                                   "student_id": student_id},
                        action="Created", effective_date=start,
                        reason=("Backfilled from the student's subject slots"
                                if source == "backfill"
                                else "Added on the student record form"),
                        to_detail=f"A Level {subj}")
            created += 1
        conn.commit()
    if created:
        logger.info("Backfilled %d learning aim(s) for %s", created, student_id)
    return created


def backfill_all() -> int:
    """Backfill every learner (idempotent). Returns aims created."""
    init_db()
    with _connect() as conn:
        ids = [r["student_id"] for r in conn.execute(
            "SELECT student_id FROM students WHERE COALESCE(subject_1,'') != '' "
            "OR COALESCE(subject_2,'') != '' OR COALESCE(subject_3,'') != ''")]
    return sum(ensure_backfilled(sid) for sid in ids)


def _catalogue_boards(names: list[str]) -> dict[str, str | None]:
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import (
            subjects as _subjects,
        )
        out: dict[str, str | None] = {}
        for n in names:
            s = _subjects.get_subject_by_name(n)
            out[n] = s.exam_board if s else None
        return out
    except Exception:
        return {}


# ── Writes ─────────────────────────────────────────────────────────

#: Changing a learner's aims needs one of these; reading them is open.
WRITE_CAPABILITIES = ("students.manage", "admissions")


def _require_writer(action: str) -> Any:
    """Refuse an aim change unless the signed-in principal (or a
    ``_guard.system_actor`` block) holds ``students.manage`` or
    ``admissions``. Nobody signed in is refused, never trusted."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    return _guard.require_any(WRITE_CAPABILITIES, action)


def can_write() -> bool:
    """Whether the signed-in user may change learning aims (for screens)."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    return any(_guard.can(c) for c in WRITE_CAPABILITIES)


def _require_student(student_id: str) -> str:
    sid = (student_id or "").strip()
    if not sid:
        raise ValidationError("Student ID is required")
    if _students().get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    return sid


def _clear_other_core(conn: _sql.Connection, student_id: str, keep: int) -> None:
    conn.execute(
        "UPDATE learning_aims SET is_core_aim = 0 WHERE student_id = ? "
        "AND aim_id != ? AND status = 'Active'", (student_id, keep))


def add_aim(student_id: str, data: dict[str, Any], *,
            recorded_by: str | None = None,
            reason: str | None = None) -> LearningAim:
    """Add a learning aim to a learner's study programme."""
    _require_writer("adding learning aims")
    init_db()
    sid = _require_student(student_id)
    ensure_backfilled(sid)
    p = _validate_payload(data)
    with _connect() as conn:
        dup = conn.execute(
            """SELECT aim_id FROM learning_aims WHERE student_id = ?
                  AND qualification_type = ? AND subject = ?
                  AND status = 'Active'""",
            (sid, p["qualification_type"], p["subject"])).fetchone()
        if dup:
            raise ValidationError(
                f"{sid} already has an active {p['qualification_type']} "
                f"{p['subject']} aim (#{dup['aim_id']})")
        if "display_order" not in data:
            n = conn.execute(
                "SELECT COALESCE(MAX(display_order), -1) + 1 AS n "
                "FROM learning_aims WHERE student_id = ?", (sid,)).fetchone()
            p["display_order"] = int(n["n"])
        cur = conn.execute(
            """INSERT INTO learning_aims
                   (student_id, qualification_type, subject, awarding_body,
                    aim_code, academic_year, start_date, planned_end_date,
                    status, planned_hours, is_core_aim, display_order,
                    source, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?, ?, ?, ?)""",
            (sid, p["qualification_type"], p["subject"], p["awarding_body"],
             p["aim_code"], p["academic_year"], p["start_date"],
             p["planned_end_date"], p["planned_hours"], p["is_core_aim"],
             p["display_order"], p["source"], p["notes"]))
        new_id = cur.lastrowid
        if p["is_core_aim"]:
            _clear_other_core(conn, sid, new_id)
        _log_change(conn, aim={"aim_id": new_id, "student_id": sid},
                    action="Created", effective_date=p["start_date"],
                    reason=reason, recorded_by=recorded_by,
                    to_detail=f"{p['qualification_type']} {p['subject']}")
        sync_mirror(sid, conn)
        conn.commit()
    aim = get_aim(new_id)
    assert aim is not None
    logger.info("Added learning aim #%d (%s) for %s", new_id, aim.label, sid)
    return aim


#: Fields :func:`update_aim` may change. Status, dates of leaving and the
#: learner are changed only through the workflow functions below.
EDITABLE_FIELDS: tuple[str, ...] = (
    "awarding_body", "aim_code", "academic_year", "start_date",
    "planned_end_date", "planned_hours", "is_core_aim", "display_order",
    "notes",
)


def update_aim(aim_id: int, data: dict[str, Any], *,
               recorded_by: str | None = None) -> LearningAim:
    """Edit an aim's details (not its status, subject or type)."""
    _require_writer("changing learning aims")
    init_db()
    existing = get_aim(aim_id)
    if existing is None:
        raise ValidationError(f"No learning aim #{aim_id}")
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValidationError(
            "Use change_aim / withdraw_aim to change "
            + ", ".join(sorted(unknown)))
    p = _validate_payload({k: v for k, v in data.items()}, existing=existing)
    changed = [k for k in EDITABLE_FIELDS
               if k in data and p.get(k) != (
                   int(getattr(existing, k)) if k == "is_core_aim"
                   else getattr(existing, k))]
    if not changed:
        return existing
    with _connect() as conn:
        conn.execute(
            """UPDATE learning_aims SET
                   awarding_body = ?, aim_code = ?, academic_year = ?,
                   start_date = ?, planned_end_date = ?, planned_hours = ?,
                   is_core_aim = ?, display_order = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE aim_id = ?""",
            (p["awarding_body"], p["aim_code"], p["academic_year"],
             p["start_date"], p["planned_end_date"], p["planned_hours"],
             p["is_core_aim"], p["display_order"], p["notes"], aim_id))
        if p["is_core_aim"]:
            _clear_other_core(conn, existing.student_id, aim_id)
        _log_change(conn, aim=existing, action="Updated",
                    effective_date=_today(), recorded_by=recorded_by,
                    from_detail=", ".join(
                        f"{k}={getattr(existing, k)}" for k in changed),
                    to_detail=", ".join(f"{k}={p[k]}" for k in changed))
        sync_mirror(existing.student_id, conn)
        conn.commit()
    out = get_aim(aim_id)
    assert out is not None
    return out


def _require_text(value: Any, label: str) -> str:
    s = (str(value).strip() if value is not None else "")
    if not s:
        raise ValidationError(f"{label} is required")
    return s


def withdraw_aim(aim_id: int, *, effective_date: Any, reason: str,
                 approved_by: str, recorded_by: str | None = None,
                 status: str = "Withdrawn") -> QualifyingCheck:
    """Withdraw a learner from an aim.

    ``effective_date`` is the last day in learning. Returns the
    qualifying-period check, which is also stored on the history row so
    "withdrawn before qualifying period" can be reported later.
    """
    _require_writer("withdrawing learning aims")
    init_db()
    aim = get_aim(aim_id)
    if aim is None:
        raise ValidationError(f"No learning aim #{aim_id}")
    if aim.status != "Active":
        raise ValidationError(
            f"Aim #{aim_id} is {aim.status}, not Active — nothing to withdraw")
    if status not in ("Withdrawn", "Transferred"):
        raise ValidationError("Status must be Withdrawn or Transferred")
    eff = _parse_date(effective_date, "Effective date", required=True)
    if eff < aim.start_date:
        raise ValidationError(
            f"Effective date {eff} is before the aim started ({aim.start_date})")
    reason = _require_text(reason, "Reason")
    approved_by = _require_text(approved_by, "Approver")
    check = _qualifying(aim.start_date, aim.planned_end_date, eff, status,
                        aim.aim_id)
    with _connect() as conn:
        conn.execute(
            """UPDATE learning_aims SET status = ?, withdrawal_date = ?,
                   withdrawal_reason = ?, actual_end_date = ?,
                   updated_at = datetime('now')
               WHERE aim_id = ?""",
            (status, eff, reason, eff, aim_id))
        _log_change(conn, aim=aim, action=status, effective_date=eff,
                    reason=reason, approved_by=approved_by,
                    recorded_by=recorded_by, from_detail=aim.label,
                    check=check)
        sync_mirror(aim.student_id, conn)
        conn.commit()
    logger.info("Aim #%d (%s) %s for %s on %s — qualifying period %s",
                aim_id, aim.label, status.lower(), aim.student_id, eff,
                "met" if check.met else "NOT met")
    return check


def change_aim(aim_id: int, *, new_subject: str,
               new_qualification_type: str | None = None,
               effective_date: Any, reason: str, approved_by: str,
               recorded_by: str | None = None,
               new_awarding_body: str | None = None,
               new_aim_code: str | None = None,
               new_planned_end_date: Any = None,
               new_planned_hours: Any = None) -> tuple[LearningAim, QualifyingCheck]:
    """Course change: close the old aim as Transferred, open the new one.

    The learner's last day on the old aim is the day before
    ``effective_date`` (or the start date, if the change is on day one);
    the new aim starts on ``effective_date`` and inherits the old aim's
    planned end, hours and position unless given. Returns the new aim and
    the old aim's qualifying-period check.
    """
    _require_writer("changing a learner's course")
    init_db()
    aim = get_aim(aim_id)
    if aim is None:
        raise ValidationError(f"No learning aim #{aim_id}")
    if aim.status != "Active":
        raise ValidationError(f"Aim #{aim_id} is {aim.status}, not Active")
    eff = _parse_date(effective_date, "Effective date", required=True)
    if eff < aim.start_date:
        raise ValidationError(
            f"Effective date {eff} is before the aim started ({aim.start_date})")
    reason = _require_text(reason, "Reason")
    approved_by = _require_text(approved_by, "Approver")
    qtype = _validate_type(new_qualification_type or aim.qualification_type)
    subject = _validate_subject(new_subject, qtype)
    if qtype == aim.qualification_type and subject == aim.subject:
        raise ValidationError("The new aim is the same as the old one")
    last_day = max(
        aim.start_date,
        (_dt.date.fromisoformat(eff) - _dt.timedelta(days=1)).isoformat())
    new_payload = _validate_payload({
        "qualification_type": qtype, "subject": subject,
        "awarding_body": new_awarding_body,
        "aim_code": new_aim_code,
        "start_date": eff,
        "planned_end_date": (new_planned_end_date
                             if new_planned_end_date not in (None, "")
                             else (aim.planned_end_date
                                   if (aim.planned_end_date or "") >= eff
                                   else None)),
        "planned_hours": (new_planned_hours
                          if new_planned_hours not in (None, "")
                          else aim.planned_hours),
        "is_core_aim": aim.is_core_aim,
        "display_order": aim.display_order,
        "source": "change",
    })
    check = _qualifying(aim.start_date, aim.planned_end_date, last_day,
                        "Transferred", aim.aim_id)
    with _connect() as conn:
        dup = conn.execute(
            """SELECT aim_id FROM learning_aims WHERE student_id = ?
                  AND qualification_type = ? AND subject = ?
                  AND status = 'Active' AND aim_id != ?""",
            (aim.student_id, qtype, subject, aim_id)).fetchone()
        if dup:
            raise ValidationError(
                f"{aim.student_id} already has an active {qtype} {subject} aim")
        conn.execute(
            """UPDATE learning_aims SET status = 'Transferred',
                   withdrawal_date = ?, withdrawal_reason = ?,
                   actual_end_date = ?, is_core_aim = 0,
                   updated_at = datetime('now')
               WHERE aim_id = ?""",
            (last_day, reason, last_day, aim_id))
        cur = conn.execute(
            """INSERT INTO learning_aims
                   (student_id, qualification_type, subject, awarding_body,
                    aim_code, academic_year, start_date, planned_end_date,
                    status, planned_hours, is_core_aim, display_order,
                    source, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?, ?, 'change', ?)""",
            (aim.student_id, qtype, subject, new_payload["awarding_body"],
             new_payload["aim_code"], new_payload["academic_year"], eff,
             new_payload["planned_end_date"], new_payload["planned_hours"],
             new_payload["is_core_aim"], new_payload["display_order"],
             f"Changed from aim #{aim_id} ({aim.label})"))
        new_id = cur.lastrowid
        _log_change(conn, aim=aim, action="Changed", effective_date=eff,
                    reason=reason, approved_by=approved_by,
                    recorded_by=recorded_by, from_detail=aim.label,
                    to_detail=f"{qtype} {subject}", new_aim_id=new_id,
                    check=check)
        _log_change(conn, aim={"aim_id": new_id, "student_id": aim.student_id},
                    action="Created", effective_date=eff, reason=reason,
                    approved_by=approved_by, recorded_by=recorded_by,
                    from_detail=aim.label, to_detail=f"{qtype} {subject}")
        sync_mirror(aim.student_id, conn)
        conn.commit()
    new_aim = get_aim(new_id)
    assert new_aim is not None
    logger.info("Course change for %s: aim #%d (%s) -> #%d (%s) from %s",
                aim.student_id, aim_id, aim.label, new_id, new_aim.label, eff)
    return new_aim, check


def complete_aim(aim_id: int, *, end_date: Any = None,
                 recorded_by: str | None = None) -> LearningAim:
    """Mark an aim finished (the learner completed the learning)."""
    _require_writer("completing learning aims")
    init_db()
    aim = get_aim(aim_id)
    if aim is None:
        raise ValidationError(f"No learning aim #{aim_id}")
    if aim.status != "Active":
        raise ValidationError(f"Aim #{aim_id} is {aim.status}, not Active")
    end = _parse_date(end_date, "End date") or aim.planned_end_date or _today()
    if end < aim.start_date:
        raise ValidationError("End date is before the start date")
    with _connect() as conn:
        conn.execute(
            """UPDATE learning_aims SET status = 'Completed',
                   actual_end_date = ?, updated_at = datetime('now')
               WHERE aim_id = ?""", (end, aim_id))
        _log_change(conn, aim=aim, action="Completed", effective_date=end,
                    recorded_by=recorded_by, from_detail=aim.label)
        sync_mirror(aim.student_id, conn)
        conn.commit()
    out = get_aim(aim_id)
    assert out is not None
    return out


def reinstate_aim(aim_id: int, *, reason: str,
                  recorded_by: str | None = None) -> LearningAim:
    """Reopen an aim that was withdrawn or completed (an enrolment
    reinstated, a rollover undone). The aim goes back to Active with its
    end dates cleared; the withdrawal or completion stays in the change
    history. A *Transferred* aim is not reopened — its replacement aim is
    the live one."""
    _require_writer("reopening learning aims")
    init_db()
    aim = get_aim(aim_id)
    if aim is None:
        raise ValidationError(f"No learning aim #{aim_id}")
    if aim.status not in ("Withdrawn", "Completed"):
        raise ValidationError(
            f"Aim #{aim_id} is {aim.status} — only a withdrawn or completed "
            "aim can be reopened")
    reason = _require_text(reason, "Reason")
    with _connect() as conn:
        dup = conn.execute(
            """SELECT aim_id FROM learning_aims WHERE student_id = ?
                  AND qualification_type = ? AND subject = ?
                  AND status = 'Active' AND aim_id != ?""",
            (aim.student_id, aim.qualification_type, aim.subject,
             aim_id)).fetchone()
        if dup:
            raise ValidationError(
                f"{aim.student_id} already has an active {aim.label} aim "
                f"(#{dup['aim_id']})")
        conn.execute(
            """UPDATE learning_aims SET status = 'Active',
                   withdrawal_date = NULL, withdrawal_reason = NULL,
                   actual_end_date = NULL, updated_at = datetime('now')
               WHERE aim_id = ?""", (aim_id,))
        _log_change(conn, aim=aim, action="Reinstated", reason=reason,
                    recorded_by=recorded_by,
                    from_detail=f"{aim.label} ({aim.status})")
        sync_mirror(aim.student_id, conn)
        conn.commit()
    out = get_aim(aim_id)
    assert out is not None
    logger.info("Reopened aim #%d (%s) for %s: %s", aim_id, aim.label,
                aim.student_id, reason)
    return out


def delete_aim(aim_id: int) -> bool:
    """Remove an aim entered in error.

    Only an aim with nothing in its history but its creation can be
    deleted; anything that has been withdrawn, changed or completed is a
    funding record and must stay.
    """
    _require_writer("deleting learning aims")
    init_db()
    aim = get_aim(aim_id)
    if aim is None:
        return False
    with _connect() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM learning_aim_changes WHERE "
            "(aim_id = ? AND action != 'Created') OR new_aim_id = ?",
            (aim_id, aim_id)).fetchone()["n"]
        if n or aim.status != "Active":
            raise ValidationError(
                "This aim has a withdrawal / change history — withdraw it "
                "instead of deleting it")
        conn.execute("DELETE FROM learning_aims WHERE aim_id = ?", (aim_id,))
        sync_mirror(aim.student_id, conn)
        conn.commit()
    logger.info("Deleted learning aim #%d (%s) for %s (entered in error)",
                aim_id, aim.label, aim.student_id)
    return True


# ── Student-form save hook ─────────────────────────────────────────

FORM_APPROVER = "(student record form)"


def on_student_saved(student_id: str, *, previous_subjects: list[str],
                     recorded_by: str | None = None) -> None:
    """Reconcile aims with the slots just saved on the student form.

    1. Aims for the slots as they were *before* the save are backfilled,
       so a learner whose aims had never been read still gets history.
    2. A slot subject with no active A-level aim becomes a new A Level aim.
    3. A mirrored aim whose subject was taken off the form is withdrawn
       through :func:`withdraw_aim`, effective today.
    4. The slots are rewritten from the aims.
    """
    _require_writer("changing learning aims")
    init_db()
    ensure_backfilled(student_id, subjects=previous_subjects)
    with _connect() as conn:
        r = conn.execute(
            "SELECT subject_1, subject_2, subject_3 FROM students "
            "WHERE student_id = ?", (student_id,)).fetchone()
    if r is None:
        return
    now_slots = [s.strip() for s in (r["subject_1"], r["subject_2"],
                                     r["subject_3"]) if s and s.strip()]
    active_alevel = [a for a in list_aims(student_id, status="Active",
                                          backfill=False)
                     if a.is_a_level_type]
    mirrored = []
    for a in active_alevel:
        if a.subject not in [m.subject for m in mirrored]:
            mirrored.append(a)
        if len(mirrored) == 3:
            break
    previous = {s.strip() for s in previous_subjects if s and s.strip()}
    for a in mirrored:
        if a.subject in previous and a.subject not in now_slots:
            withdraw_aim(a.aim_id, effective_date=max(_today(), a.start_date),
                         reason="Removed from the student record form",
                         approved_by=recorded_by or FORM_APPROVER,
                         recorded_by=recorded_by)
    have = {a.subject for a in active_alevel}
    to_add = [s for s in now_slots if s not in have]
    if to_add:
        for order, subj in enumerate(now_slots):
            if subj in to_add:
                add_aim(student_id, {
                    "qualification_type": "A Level", "subject": subj,
                    "start_date": _form_start_date(student_id),
                    "display_order": order, "source": "form",
                    "awarding_body": _catalogue_boards([subj]).get(subj),
                }, recorded_by=recorded_by,
                    reason="Added on the student record form")
    # Keep the form's slot order: slot subjects take positions 0..2 and
    # any other active A-level aim (a fourth A level) sorts after them.
    with _connect() as conn:
        for idx, subj in enumerate(now_slots):
            conn.execute(
                f"""UPDATE learning_aims SET display_order = ?
                     WHERE student_id = ? AND subject = ? AND status = 'Active'
                       AND qualification_type IN ({",".join("?" * len(grade_scales.A_LEVEL_TYPES))})""",
                (idx, student_id, subj, *grade_scales.A_LEVEL_TYPES))
        if now_slots:
            conn.execute(
                f"""UPDATE learning_aims SET display_order = display_order + 3
                     WHERE student_id = ? AND status = 'Active'
                       AND display_order < 3
                       AND subject NOT IN ({",".join("?" * len(now_slots))})""",
                (student_id, *now_slots))
        conn.commit()
    sync_mirror(student_id)


def _form_start_date(student_id: str) -> str:
    """Start date for an aim added on the form: today, or the enrolment
    start if the learner has not started yet."""
    with _connect() as conn:
        start, _end = _default_dates(conn, student_id)
    return max(start, _today())


# ── Reports ────────────────────────────────────────────────────────

@dataclass
class WithdrawalRow:
    aim: LearningAim
    student_name: str
    check: QualifyingCheck
    approved_by: str | None


def withdrawals(*, academic_year: str | None = None,
                only_before_qualifying: bool = False) -> list[WithdrawalRow]:
    """Withdrawn / transferred aims with their qualifying-period check."""
    init_db()
    names = {s.student_id: s.full_name for s in _students().list_students()}
    rows: list[WithdrawalRow] = []
    aims = (list_all_aims(status="Withdrawn", academic_year=academic_year)
            + list_all_aims(status="Transferred", academic_year=academic_year))
    approvers: dict[int, str | None] = {}
    with _connect() as conn:
        for r in conn.execute(
                "SELECT aim_id, approved_by FROM learning_aim_changes "
                "WHERE action IN ('Withdrawn','Transferred','Changed') "
                "ORDER BY change_id"):
            approvers[r["aim_id"]] = r["approved_by"]
    for a in aims:
        chk = qualifying_check_for(a)
        if only_before_qualifying and not chk.withdrawn_before_qualifying:
            continue
        rows.append(WithdrawalRow(aim=a, student_name=names.get(a.student_id, "(unknown)"),
                                  check=chk, approved_by=approvers.get(a.aim_id)))
    rows.sort(key=lambda w: (w.aim.withdrawal_date or "", w.aim.student_id),
              reverse=True)
    return rows
