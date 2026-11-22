"""Prior attainment (GCSE results) and the 16-19 condition of funding.

``prior_gcse_results`` holds one row per GCSE a learner brings with
them: subject, grade (9-1, or a legacy A*-G letter), year and board.
From it this module works out

* the **average GCSE point score** — legacy letters converted with the
  DfE's 2017 transition points (A*=8.5, A=7, B=5.5, C=4, D=3, E=2,
  F=1.5, G=1, U=0), short courses at half weight;
* the learner's **best English and best maths grade**, as a 9-1 number;
* the **condition of funding** position for English and maths.

Condition of funding (ESFA 16-19 funding guidance — check the current
year's rules): a learner without a grade 4 (or legacy C) in English
and/or maths must be studying it as part of their programme —

* prior grade 3: a GCSE in that subject;
* prior grade 2 or below, or no GCSE at all: a GCSE or an approved
  Functional Skills qualification (stepping stone towards the GCSE).

A recorded exemption (for example a learner with an EHCP whose plan says
the qualification is not appropriate, or one holding an accepted
overseas equivalent) takes them out of scope. Exemptions are recorded in
``cof_exemptions`` with a reason and who agreed it.

Attendance at the resit lessons is read (only) from the attendance
module, through the class groups whose course teaches the resit.
"""

from __future__ import annotations

import logging
import re
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims,
)

logger = logging.getLogger(__name__)


#: Who may change prior attainment; reading it is open.
WRITE_CAPABILITIES = ('students.manage', 'admissions', 'exams')


def _require_writer(action: str) -> None:
    """Refuse a write unless the signed-in principal (or a
    ``_guard.system_actor`` block) holds one of :data:`WRITE_CAPABILITIES`.
    Nobody signed in is refused, never trusted."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    _guard.require_any(WRITE_CAPABILITIES, action)


def can_write() -> bool:
    """Whether the signed-in user may change prior attainment (for screens)."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    return any(_guard.can(c) for c in WRITE_CAPABILITIES)

#: None follows ``students.DB_PATH`` (see learning_aims.DB_PATH).
DB_PATH: Path | None = None

GRADE_SYSTEMS: tuple[str, ...] = ("9-1", "A*-G")
GCSE_91_GRADES: tuple[str, ...] = ("9", "8", "7", "6", "5", "4", "3", "2", "1", "U")
LEGACY_GRADES: tuple[str, ...] = ("A*", "A", "B", "C", "D", "E", "F", "G", "U")

#: DfE 2017 KS4 transition points for legacy letter grades.
LEGACY_POINTS: dict[str, float] = {
    "A*": 8.5, "A": 7.0, "B": 5.5, "C": 4.0, "D": 3.0,
    "E": 2.0, "F": 1.5, "G": 1.0, "U": 0.0,
}

QUALIFICATION_KINDS: tuple[str, ...] = ("GCSE", "GCSE short course", "IGCSE")
#: Weight in the average point score.
KIND_WEIGHTS: dict[str, float] = {
    "GCSE": 1.0, "GCSE short course": 0.5, "IGCSE": 1.0,
}

# The system's one awarding-body list (exams_office/boards.py).
from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (  # noqa: E402
    EXAM_BOARDS,
    normalise_board,
)

AREAS: tuple[str, ...] = ("English", "Maths")

#: Subjects that satisfy the English / maths requirement. English
#: literature counts as well as language under the condition of funding;
#: statistics does not count as maths.
_AREA_PATTERNS: dict[str, re.Pattern[str]] = {
    "English": re.compile(r"^english( language| literature| lang(uage)? ?(and|&) ?lit(erature)?)?$", re.I),
    "Maths": re.compile(r"^(math|maths|mathematics)$", re.I),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prior_gcse_results (
    result_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT NOT NULL,
    subject        TEXT NOT NULL,
    grade          TEXT NOT NULL,
    grade_system   TEXT NOT NULL DEFAULT '9-1',
    kind           TEXT NOT NULL DEFAULT 'GCSE',
    year           INTEGER,
    exam_board     TEXT,
    notes          TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE (student_id, subject, kind, year),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_prior_gcse_student ON prior_gcse_results(student_id);

CREATE TABLE IF NOT EXISTS cof_exemptions (
    exemption_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    area          TEXT NOT NULL,
    reason        TEXT NOT NULL,
    agreed_by     TEXT NOT NULL,
    agreed_on     TEXT DEFAULT (date('now')),
    UNIQUE (student_id, area),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
"""


class ValidationError(ValueError):
    """Raised for invalid prior-attainment input."""


@dataclass
class GCSEResult:
    result_id: int
    student_id: str
    subject: str
    grade: str
    grade_system: str
    kind: str
    year: int | None
    exam_board: str | None
    notes: str | None

    @property
    def points(self) -> float | None:
        return grade_points(self.grade, self.grade_system)


@dataclass
class Exemption:
    exemption_id: int
    student_id: str
    area: str
    reason: str
    agreed_by: str
    agreed_on: str | None


@dataclass
class PriorAttainment:
    student_id: str
    results: list[GCSEResult]
    average_point_score: float | None
    gcse_count: float                 # weighted count used in the average
    best_english: float | None        # 9-1 points (legacy converted)
    best_english_grade: str | None
    best_maths: float | None
    best_maths_grade: str | None


@dataclass
class AreaStatus:
    area: str
    best_points: float | None
    best_grade: str | None
    requirement: str          # "None", "GCSE", "GCSE or Functional Skills"
    compliant: bool
    status: str               # human-readable
    aim_id: int | None = None
    aim_label: str | None = None
    exemption: Exemption | None = None
    resit_attendance_pct: float | None = None
    resit_sessions: int = 0


@dataclass
class FundingCondition:
    student_id: str
    english: AreaStatus
    maths: AreaStatus

    @property
    def compliant(self) -> bool:
        return self.english.compliant and self.maths.compliant

    @property
    def areas(self) -> list[AreaStatus]:
        return [self.english, self.maths]


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


def _row(r: _sql.Row) -> GCSEResult:
    return GCSEResult(
        result_id=r["result_id"], student_id=r["student_id"],
        subject=r["subject"], grade=r["grade"],
        grade_system=r["grade_system"], kind=r["kind"], year=r["year"],
        exam_board=r["exam_board"], notes=r["notes"])


def _row_ex(r: _sql.Row) -> Exemption:
    return Exemption(exemption_id=r["exemption_id"], student_id=r["student_id"],
                     area=r["area"], reason=r["reason"],
                     agreed_by=r["agreed_by"], agreed_on=r["agreed_on"])


# ── Grade helpers ──────────────────────────────────────────────────

def grade_points(grade: str | None, grade_system: str | None = None) -> float | None:
    """9-1 point value of a GCSE grade (legacy letters converted)."""
    if not grade:
        return None
    g = grade.strip().upper()
    system = grade_system or ("9-1" if g in GCSE_91_GRADES else "A*-G")
    if system == "9-1":
        if g == "U":
            return 0.0
        return float(g) if g in GCSE_91_GRADES else None
    return LEGACY_POINTS.get(g)


def area_for_subject(subject: str | None) -> str | None:
    """'English' / 'Maths' if the subject meets that requirement."""
    s = (subject or "").strip()
    for area, pat in _AREA_PATTERNS.items():
        if pat.match(s):
            return area
    return None


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    subject = (data.get("subject") or "").strip()
    if not subject:
        raise ValidationError("Subject is required")
    out["subject"] = subject
    system = (data.get("grade_system") or "").strip()
    grade = (data.get("grade") or "").strip().upper()
    if not grade:
        raise ValidationError("Grade is required")
    if not system:
        system = "9-1" if grade in GCSE_91_GRADES else "A*-G"
    if system not in GRADE_SYSTEMS:
        raise ValidationError(f"Grade system must be one of: {', '.join(GRADE_SYSTEMS)}")
    allowed = GCSE_91_GRADES if system == "9-1" else LEGACY_GRADES
    if grade not in allowed:
        raise ValidationError(
            f"A {system} grade must be one of: {', '.join(allowed)}")
    out["grade"], out["grade_system"] = grade, system
    kind = (data.get("kind") or "GCSE").strip()
    if kind not in QUALIFICATION_KINDS:
        raise ValidationError(f"Kind must be one of: {', '.join(QUALIFICATION_KINDS)}")
    out["kind"] = kind
    year = data.get("year")
    if year in (None, ""):
        out["year"] = None
    else:
        try:
            y = int(year)
        except (TypeError, ValueError):
            raise ValidationError("Year must be a four-digit year") from None
        if y < 1980 or y > 2100:
            raise ValidationError("Year must be between 1980 and 2100")
        out["year"] = y
    raw_board = (data.get("exam_board") or "").strip()
    # Canonical spelling when it is a known board; free text otherwise
    # (a GCSE from abroad, an old board name on a certificate).
    out["exam_board"] = (normalise_board(raw_board) or raw_board) or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


# ── GCSE results CRUD ──────────────────────────────────────────────

def add_result(student_id: str, data: dict[str, Any]) -> GCSEResult:
    """Record (or replace) a prior GCSE result for a learner."""
    _require_writer("recording prior attainment")
    init_db()
    sid = (student_id or "").strip()
    if _students().get_student(sid) is None:
        raise ValidationError(f"No student with id {sid}")
    p = _validate(data)
    with _connect() as conn:
        conn.execute(
            """INSERT INTO prior_gcse_results
                   (student_id, subject, grade, grade_system, kind, year,
                    exam_board, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(student_id, subject, kind, year) DO UPDATE SET
                   grade = excluded.grade, grade_system = excluded.grade_system,
                   exam_board = excluded.exam_board, notes = excluded.notes""",
            (sid, p["subject"], p["grade"], p["grade_system"], p["kind"],
             p["year"], p["exam_board"], p["notes"]))
        conn.commit()
        r = conn.execute(
            """SELECT * FROM prior_gcse_results WHERE student_id = ?
                  AND subject = ? AND kind = ? AND year IS ?
                ORDER BY result_id DESC LIMIT 1""",
            (sid, p["subject"], p["kind"], p["year"])).fetchone()
    logger.info("Recorded prior %s %s for %s", p["kind"], p["subject"], sid)
    return _row(r)


def list_results(student_id: str) -> list[GCSEResult]:
    init_db()
    with _connect() as conn:
        return [_row(r) for r in conn.execute(
            "SELECT * FROM prior_gcse_results WHERE student_id = ? "
            "ORDER BY subject, year", (student_id,)).fetchall()]


def delete_result(result_id: int) -> bool:
    _require_writer("deleting prior attainment")
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM prior_gcse_results WHERE result_id = ?",
                           (int(result_id),))
        conn.commit()
    return cur.rowcount > 0


# ── Prior attainment summary ───────────────────────────────────────

def prior_attainment(student_id: str) -> PriorAttainment:
    """Average GCSE point score and best English / maths grades."""
    results = list_results(student_id)
    weighted = 0.0
    total = 0.0
    best: dict[str, tuple[float, str] | None] = {a: None for a in AREAS}
    for r in results:
        pts = r.points
        if pts is None:
            continue
        w = KIND_WEIGHTS.get(r.kind, 1.0)
        weighted += pts * w
        total += w
        area = area_for_subject(r.subject)
        if area and r.kind != "GCSE short course":
            cur = best[area]
            if cur is None or pts > cur[0]:
                best[area] = (pts, r.grade)
    eng, mat = best["English"], best["Maths"]
    return PriorAttainment(
        student_id=student_id, results=results,
        average_point_score=(round(weighted / total, 2) if total else None),
        gcse_count=total,
        best_english=eng[0] if eng else None,
        best_english_grade=eng[1] if eng else None,
        best_maths=mat[0] if mat else None,
        best_maths_grade=mat[1] if mat else None,
    )


def average_gcse_score(student_id: str) -> float | None:
    return prior_attainment(student_id).average_point_score


# ── Exemptions ─────────────────────────────────────────────────────

def set_exemption(student_id: str, area: str, *, reason: str,
                  agreed_by: str) -> Exemption:
    _require_writer("recording English/maths exemptions")
    init_db()
    if area not in AREAS:
        raise ValidationError(f"Area must be one of: {', '.join(AREAS)}")
    if not (reason or "").strip():
        raise ValidationError("Reason is required")
    if not (agreed_by or "").strip():
        raise ValidationError("Agreed by is required")
    if _students().get_student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO cof_exemptions (student_id, area, reason, agreed_by)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(student_id, area) DO UPDATE SET
                   reason = excluded.reason, agreed_by = excluded.agreed_by,
                   agreed_on = date('now')""",
            (student_id, area, reason.strip(), agreed_by.strip()))
        conn.commit()
        r = conn.execute("SELECT * FROM cof_exemptions WHERE student_id = ? "
                         "AND area = ?", (student_id, area)).fetchone()
    logger.info("Condition-of-funding exemption for %s (%s) agreed by %s",
                student_id, area, agreed_by)
    return _row_ex(r)


def clear_exemption(student_id: str, area: str) -> bool:
    _require_writer("clearing English/maths exemptions")
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM cof_exemptions WHERE student_id = ? "
                           "AND area = ?", (student_id, area))
        conn.commit()
    return cur.rowcount > 0


def list_exemptions(student_id: str | None = None) -> list[Exemption]:
    init_db()
    with _connect() as conn:
        if student_id:
            rows = conn.execute("SELECT * FROM cof_exemptions WHERE student_id = ?",
                                (student_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM cof_exemptions "
                                "ORDER BY student_id, area").fetchall()
    return [_row_ex(r) for r in rows]


# ── Condition of funding ───────────────────────────────────────────

def _resit_attendance(student_id: str, aim: learning_aims.LearningAim
                      ) -> tuple[float | None, int]:
    """Attendance % at the class groups teaching this resit (read-only).

    A group counts when its course teaches the aim's subject as the
    aim's qualification type and the learner is a member. Returns
    (percentage, sessions marked).
    """
    try:
        from education_system.systems.sixth_form.domain.academics.attendance import (
            attendance as _att,
        )
        from education_system.systems.sixth_form.domain.academics.class_groups import (
            class_groups as _cg,
        )
        from education_system.systems.sixth_form.domain.academics.courses import (
            courses as _courses,
        )
        from education_system.systems.sixth_form.domain.academics.timetable import (
            timetable as _tt,
        )
        total = attending = 0
        for g in _cg.groups_for_student(student_id):
            c = _courses.get_course(g.course_id)
            if c is None or c.subject != aim.subject:
                continue
            if _courses.effective_qualification_type(c) != aim.qualification_type:
                continue
            for slot in _tt.list_slots(group_id=g.group_id):
                s = _att.summary_for_student(
                    student_id, slot_id=slot.slot_id, date_from=aim.start_date)
                total += s.total
                attending += s.attending
        if total == 0:
            return None, 0
        return round(100.0 * attending / total, 1), total
    except Exception:
        logger.debug("Resit attendance unavailable for %s", student_id,
                     exc_info=True)
        return None, 0


def _area_status(student_id: str, area: str, best: float | None,
                 best_grade: str | None, aims: list[learning_aims.LearningAim],
                 exemption: Exemption | None) -> AreaStatus:
    if best is not None and best >= 4:
        return AreaStatus(area=area, best_points=best, best_grade=best_grade,
                          requirement="None", compliant=True,
                          status=f"Met — grade {best_grade} held")
    if exemption is not None:
        return AreaStatus(area=area, best_points=best, best_grade=best_grade,
                          requirement="None", compliant=True,
                          status=f"Exempt — {exemption.reason}",
                          exemption=exemption)
    needs_gcse = best is not None and best >= 3
    requirement = "GCSE" if needs_gcse else "GCSE or Functional Skills"
    matching = [a for a in aims
                if area_for_subject(_strip_prefix(a.subject)) == area
                and a.status in ("Active", "Completed")]
    gcse = [a for a in matching if a.qualification_type == "GCSE"]
    fs = [a for a in matching if a.qualification_type == "Functional Skills"]
    chosen = gcse[0] if gcse else (fs[0] if (fs and not needs_gcse) else None)
    held = (f"grade {best_grade}" if best_grade else "no GCSE recorded")
    if chosen is None:
        if needs_gcse and fs:
            status = (f"Non-compliant — {held}: must be on a GCSE, "
                      "Functional Skills does not meet the condition")
        else:
            status = f"Non-compliant — {held}: needs a {requirement} {area} aim"
        return AreaStatus(area=area, best_points=best, best_grade=best_grade,
                          requirement=requirement, compliant=False,
                          status=status)
    pct, sessions = _resit_attendance(student_id, chosen)
    return AreaStatus(
        area=area, best_points=best, best_grade=best_grade,
        requirement=requirement, compliant=True,
        status=f"Compliant — {held}, on {chosen.label}",
        aim_id=chosen.aim_id, aim_label=chosen.label,
        resit_attendance_pct=pct, resit_sessions=sessions)


def _strip_prefix(subject: str) -> str:
    """'GCSE English Language' -> 'English Language' for matching."""
    return re.sub(r"^(gcse|functional skills|fs)\s+", "", subject.strip(),
                  flags=re.I)


def funding_condition(student_id: str) -> FundingCondition:
    """English and maths condition-of-funding status for one learner."""
    pa = prior_attainment(student_id)
    aims = learning_aims.list_aims(student_id)
    ex = {e.area: e for e in list_exemptions(student_id)}
    return FundingCondition(
        student_id=student_id,
        english=_area_status(student_id, "English", pa.best_english,
                             pa.best_english_grade, aims, ex.get("English")),
        maths=_area_status(student_id, "Maths", pa.best_maths,
                           pa.best_maths_grade, aims, ex.get("Maths")),
    )


@dataclass
class ComplianceRow:
    student_id: str
    student_name: str
    condition: FundingCondition


def compliance_report(*, only_non_compliant: bool = False,
                      active_only: bool = True) -> list[ComplianceRow]:
    """Condition-of-funding position for every learner on roll."""
    students = _students().list_students()
    rows: list[ComplianceRow] = []
    for s in students:
        if active_only and s.status != "Active":
            continue
        cond = funding_condition(s.student_id)
        if only_non_compliant and cond.compliant:
            continue
        rows.append(ComplianceRow(student_id=s.student_id,
                                  student_name=s.full_name, condition=cond))
    return rows


def non_compliant_learners() -> list[ComplianceRow]:
    return compliance_report(only_non_compliant=True)
