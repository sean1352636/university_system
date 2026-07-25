"""Appraisals data layer for Sixth Form System.

Two tables:
- `appraisals`: per-staff per-cycle appraisal (FK cascade on staff)
  with appraiser, mid-year & end-year review dates, overall
  4-point grade, pay-progression decision and standards uphold.
  Unique on (staff_id, cycle).
- `appraisal_objectives`: per-appraisal SMART objectives (FK
  cascade) with target metric, progress notes and achievement
  status.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.systems.sixth_form.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

GRADES: tuple[int, ...] = (1, 2, 3, 4)
_GRADE_LABELS = {
    1: "Outstanding",
    2: "Good",
    3: "Requires Improvement",
    4: "Unsatisfactory",
}


def grade_label(g: int | None) -> str:
    if g is None:
        return "—"
    return _GRADE_LABELS.get(g, "Unknown")


PAY_PROGRESSION: tuple[str, ...] = (
    "Yes",
    "No",
    "Deferred",
    "Not Applicable",
    "Pending",
)
DEFAULT_PAY_PROGRESSION = "Pending"

STATUSES: tuple[str, ...] = (
    "Setting Objectives",
    "In Progress",
    "Mid-Year Review",
    "Awaiting End Year",
    "End Year Review",
    "Completed",
    "Closed",
    "Archived",
)
DEFAULT_STATUS = "Setting Objectives"

OBJECTIVE_TYPES: tuple[str, ...] = (
    "Pupil Outcomes",
    "Subject / Curriculum",
    "Pastoral",
    "Personal Development",
    "Whole-School Priority",
    "Department Priority",
    "Leadership",
    "CPD",
    "Other",
)
DEFAULT_OBJECTIVE_TYPE = "Pupil Outcomes"

OBJECTIVE_STATUSES: tuple[str, ...] = (
    "Not Started",
    "In Progress",
    "On Track",
    "At Risk",
    "Achieved",
    "Partially Achieved",
    "Not Achieved",
    "Removed",
)
DEFAULT_OBJECTIVE_STATUS = "Not Started"


class ValidationError(Exception):
    pass


@dataclass
class Appraisal:
    appraisal_id: int
    staff_id: str
    cycle: str
    appraiser_id: str | None
    appraiser_name: str | None
    job_role: str | None
    objectives_set_on: str | None
    mid_year_review_on: str | None
    end_year_review_on: str | None
    self_review_completed: bool
    overall_grade: int | None
    upholding_standards: bool
    pay_progression: str
    strengths: str | None
    areas_to_develop: str | None
    cpd_needs: str | None
    appraiser_comments: str | None
    appraisee_comments: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Closed", "Archived")

    @property
    def grade_label(self) -> str:
        return grade_label(self.overall_grade)

    @property
    def mid_year_overdue(self) -> bool:
        if not self.is_open or self.mid_year_review_on:
            return False
        if not self.objectives_set_on:
            return False
        # Mid-year ~ 6 months after objectives
        try:
            start = _dt.date.fromisoformat(
                self.objectives_set_on)
        except ValueError:
            return False
        due = start + _dt.timedelta(days=183)
        return _dt.date.today() > due


@dataclass
class Objective:
    objective_id: int
    appraisal_id: int
    objective_number: int
    objective_type: str
    title: str
    description: str | None
    target_metric: str | None
    success_criteria: str | None
    progress_notes: str | None
    mid_year_progress: str | None
    end_year_evidence: str | None
    status: str
    reviewed_on: str | None
    weighting: float | None
    notes: str | None
    created_on: str

    @property
    def is_complete(self) -> bool:
        return self.status in ("Achieved",
                                       "Partially Achieved",
                                       "Not Achieved",
                                       "Removed")


@dataclass
class AppraisalsSummary:
    total: int = 0
    open_count: int = 0
    mid_year_overdue: int = 0
    completed: int = 0
    upholding_standards: int = 0
    pay_progression_yes: int = 0
    pay_progression_deferred: int = 0
    total_objectives: int = 0
    objectives_achieved: int = 0
    distinct_cycles: int = 0
    average_grade: float | None = None
    by_cycle: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_grade: dict[int, int] = field(default_factory=dict)
    by_pay_progression: dict[str, int] = field(default_factory=dict)
    by_objective_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.APPRAISALS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appraisals (
                appraisal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                cycle TEXT NOT NULL,
                appraiser_id TEXT,
                appraiser_name TEXT,
                job_role TEXT,
                objectives_set_on TEXT,
                mid_year_review_on TEXT,
                end_year_review_on TEXT,
                self_review_completed INTEGER NOT NULL DEFAULT 0,
                overall_grade INTEGER,
                upholding_standards INTEGER NOT NULL DEFAULT 1,
                pay_progression TEXT NOT NULL,
                strengths TEXT,
                areas_to_develop TEXT,
                cpd_needs TEXT,
                appraiser_comments TEXT,
                appraisee_comments TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                UNIQUE(staff_id, cycle),
                FOREIGN KEY(staff_id) REFERENCES staff(staff_id)
                  ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appraisal_objectives (
                objective_id INTEGER PRIMARY KEY AUTOINCREMENT,
                appraisal_id INTEGER NOT NULL,
                objective_number INTEGER NOT NULL,
                objective_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                target_metric TEXT,
                success_criteria TEXT,
                progress_notes TEXT,
                mid_year_progress TEXT,
                end_year_evidence TEXT,
                status TEXT NOT NULL,
                reviewed_on TEXT,
                weighting REAL,
                notes TEXT,
                created_on TEXT NOT NULL,
                FOREIGN KEY(appraisal_id)
                  REFERENCES appraisals(appraisal_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _staff_exists(staff_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM staff WHERE staff_id=?",
                (staff_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


# ── Appraisals ───────────────────────────────────────────

def _validate_appraisal(p: dict[str, Any], *,
                              existing_id: int | None = None
                              ) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")

    out["cycle"] = (out.get("cycle") or "").strip()
    if not out["cycle"]:
        raise ValidationError("Cycle is required (e.g. 2025-26)")

    _check_date("Objectives set on",
                  out.get("objectives_set_on"))
    _check_date("Mid-year review",
                  out.get("mid_year_review_on"))
    _check_date("End-year review",
                  out.get("end_year_review_on"))

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    grade = out.get("overall_grade")
    if grade in (None, ""):
        out["overall_grade"] = None
    else:
        try:
            gv = int(grade)
        except (TypeError, ValueError):
            raise ValidationError("Grade must be 1-4")
        if gv not in GRADES:
            raise ValidationError("Grade must be 1-4")
        out["overall_grade"] = gv

    pp = (out.get("pay_progression")
            or DEFAULT_PAY_PROGRESSION).strip()
    if pp not in PAY_PROGRESSION:
        raise ValidationError(
            f"Pay progression must be one of: "
            f"{', '.join(PAY_PROGRESSION)}")
    out["pay_progression"] = pp

    appr = (out.get("appraiser_id") or "").strip()
    if appr and not _staff_exists(appr):
        raise ValidationError(
            f"No staff with id {appr} (appraiser)")
    out["appraiser_id"] = appr or None

    for k in ("appraiser_name", "job_role", "strengths",
               "areas_to_develop", "cpd_needs",
               "appraiser_comments", "appraisee_comments",
               "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("objectives_set_on", "mid_year_review_on",
               "end_year_review_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    out["self_review_completed"] = bool(
        out.get("self_review_completed"))
    out["upholding_standards"] = bool(
        out.get("upholding_standards", True))

    # Uniqueness (staff, cycle)
    with _connect() as conn:
        row = conn.execute(
            "SELECT appraisal_id FROM appraisals "
            "WHERE staff_id=? AND cycle=?",
            (out["staff_id"], out["cycle"])).fetchone()
    if row and row["appraisal_id"] != existing_id:
        raise ValidationError(
            f"Staff {out['staff_id']} already has an appraisal "
            f"for cycle {out['cycle']!r}")
    return out


def _row_appraisal(r: sqlite3.Row) -> Appraisal:
    return Appraisal(
        appraisal_id=r["appraisal_id"],
        staff_id=r["staff_id"],
        cycle=r["cycle"],
        appraiser_id=r["appraiser_id"],
        appraiser_name=r["appraiser_name"],
        job_role=r["job_role"],
        objectives_set_on=r["objectives_set_on"],
        mid_year_review_on=r["mid_year_review_on"],
        end_year_review_on=r["end_year_review_on"],
        self_review_completed=bool(r["self_review_completed"]),
        overall_grade=r["overall_grade"],
        upholding_standards=bool(r["upholding_standards"]),
        pay_progression=r["pay_progression"],
        strengths=r["strengths"],
        areas_to_develop=r["areas_to_develop"],
        cpd_needs=r["cpd_needs"],
        appraiser_comments=r["appraiser_comments"],
        appraisee_comments=r["appraisee_comments"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_appraisal(payload: dict[str, Any]) -> Appraisal:
    init_db()
    p = _validate_appraisal(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO appraisals (
              staff_id, cycle, appraiser_id, appraiser_name,
              job_role, objectives_set_on, mid_year_review_on,
              end_year_review_on, self_review_completed,
              overall_grade, upholding_standards, pay_progression,
              strengths, areas_to_develop, cpd_needs,
              appraiser_comments, appraisee_comments,
              status, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?)
        """, (
            p["staff_id"], p["cycle"], p["appraiser_id"],
            p["appraiser_name"], p["job_role"],
            p["objectives_set_on"], p["mid_year_review_on"],
            p["end_year_review_on"],
            1 if p["self_review_completed"] else 0,
            p["overall_grade"],
            1 if p["upholding_standards"] else 0,
            p["pay_progression"],
            p["strengths"], p["areas_to_develop"],
            p["cpd_needs"], p["appraiser_comments"],
            p["appraisee_comments"], p["status"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_appraisal(new_id)


def update_appraisal(appraisal_id: int,
                          payload: dict[str, Any]) -> Appraisal:
    init_db()
    if get_appraisal(appraisal_id) is None:
        raise ValidationError(
            f"No appraisal with id {appraisal_id}")
    p = _validate_appraisal(payload, existing_id=appraisal_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE appraisals SET
              staff_id=?, cycle=?, appraiser_id=?, appraiser_name=?,
              job_role=?, objectives_set_on=?,
              mid_year_review_on=?, end_year_review_on=?,
              self_review_completed=?, overall_grade=?,
              upholding_standards=?, pay_progression=?,
              strengths=?, areas_to_develop=?, cpd_needs=?,
              appraiser_comments=?, appraisee_comments=?,
              status=?, notes=?, updated_on=?
            WHERE appraisal_id=?
        """, (
            p["staff_id"], p["cycle"], p["appraiser_id"],
            p["appraiser_name"], p["job_role"],
            p["objectives_set_on"], p["mid_year_review_on"],
            p["end_year_review_on"],
            1 if p["self_review_completed"] else 0,
            p["overall_grade"],
            1 if p["upholding_standards"] else 0,
            p["pay_progression"],
            p["strengths"], p["areas_to_develop"],
            p["cpd_needs"], p["appraiser_comments"],
            p["appraisee_comments"], p["status"], p["notes"],
            now, appraisal_id,
        ))
    return get_appraisal(appraisal_id)


def delete_appraisal(appraisal_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM appraisals WHERE appraisal_id=?",
            (appraisal_id,))
        return cur.rowcount > 0


def get_appraisal(appraisal_id: int) -> Appraisal | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM appraisals WHERE appraisal_id=?",
            (appraisal_id,)).fetchone()
        return _row_appraisal(r) if r else None


def list_appraisals(*,
                         staff_id: str | None = None,
                         cycle: str | None = None,
                         status: str | None = None,
                         grade: int | None = None,
                         pay_progression: str | None = None,
                         open_only: bool = False,
                         mid_year_overdue: bool = False,
                         appraiser_id: str | None = None,
                         ) -> list[Appraisal]:
    init_db()
    sql = "SELECT * FROM appraisals WHERE 1=1"
    params: list[Any] = []
    if staff_id:
        sql += " AND staff_id=?"
        params.append(staff_id)
    if cycle:
        sql += " AND cycle=?"
        params.append(cycle)
    if status:
        sql += " AND status=?"
        params.append(status)
    if grade is not None:
        sql += " AND overall_grade=?"
        params.append(grade)
    if pay_progression:
        sql += " AND pay_progression=?"
        params.append(pay_progression)
    if open_only:
        sql += " AND status NOT IN ('Closed','Archived')"
    if appraiser_id:
        sql += " AND appraiser_id=?"
        params.append(appraiser_id)
    sql += (" ORDER BY cycle DESC, staff_id ASC,"
              " appraisal_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    rows_a = [_row_appraisal(r) for r in rows]
    if mid_year_overdue:
        rows_a = [a for a in rows_a if a.mid_year_overdue]
    return rows_a


def list_cycles() -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT cycle FROM appraisals "
            "ORDER BY cycle DESC").fetchall()
    return [r["cycle"] for r in rows]


def _to_appraisal_dict(a: Appraisal) -> dict[str, Any]:
    return {
        "staff_id": a.staff_id,
        "cycle": a.cycle,
        "appraiser_id": a.appraiser_id,
        "appraiser_name": a.appraiser_name,
        "job_role": a.job_role,
        "objectives_set_on": a.objectives_set_on,
        "mid_year_review_on": a.mid_year_review_on,
        "end_year_review_on": a.end_year_review_on,
        "self_review_completed": a.self_review_completed,
        "overall_grade": a.overall_grade,
        "upholding_standards": a.upholding_standards,
        "pay_progression": a.pay_progression,
        "strengths": a.strengths,
        "areas_to_develop": a.areas_to_develop,
        "cpd_needs": a.cpd_needs,
        "appraiser_comments": a.appraiser_comments,
        "appraisee_comments": a.appraisee_comments,
        "status": a.status,
        "notes": a.notes,
    }


def set_objectives(appraisal_id: int, *,
                        objectives_set_on: str | None = None
                        ) -> Appraisal:
    a = get_appraisal(appraisal_id)
    if a is None:
        raise ValidationError(
            f"No appraisal with id {appraisal_id}")
    data = _to_appraisal_dict(a)
    data["objectives_set_on"] = (objectives_set_on
                                       or _dt.date.today().isoformat())
    if a.status == "Setting Objectives":
        data["status"] = "In Progress"
    return update_appraisal(appraisal_id, data)


def record_mid_year(appraisal_id: int, *,
                         reviewed_on: str | None = None
                         ) -> Appraisal:
    a = get_appraisal(appraisal_id)
    if a is None:
        raise ValidationError(
            f"No appraisal with id {appraisal_id}")
    data = _to_appraisal_dict(a)
    data["mid_year_review_on"] = (reviewed_on
                                        or _dt.date.today().isoformat())
    data["status"] = "Awaiting End Year"
    return update_appraisal(appraisal_id, data)


def record_end_year(appraisal_id: int, *,
                         reviewed_on: str | None = None,
                         overall_grade: int | None = None,
                         pay_progression: str | None = None,
                         upholding_standards: bool | None = None,
                         strengths: str | None = None,
                         areas_to_develop: str | None = None,
                         cpd_needs: str | None = None,
                         appraiser_comments: str | None = None
                         ) -> Appraisal:
    a = get_appraisal(appraisal_id)
    if a is None:
        raise ValidationError(
            f"No appraisal with id {appraisal_id}")
    data = _to_appraisal_dict(a)
    data["end_year_review_on"] = (reviewed_on
                                        or _dt.date.today().isoformat())
    if overall_grade is not None:
        data["overall_grade"] = overall_grade
    if pay_progression is not None:
        data["pay_progression"] = pay_progression
    if upholding_standards is not None:
        data["upholding_standards"] = upholding_standards
    if strengths is not None:
        data["strengths"] = strengths
    if areas_to_develop is not None:
        data["areas_to_develop"] = areas_to_develop
    if cpd_needs is not None:
        data["cpd_needs"] = cpd_needs
    if appraiser_comments is not None:
        data["appraiser_comments"] = appraiser_comments
    data["status"] = "Completed"
    return update_appraisal(appraisal_id, data)


def close_appraisal(appraisal_id: int) -> Appraisal:
    a = get_appraisal(appraisal_id)
    if a is None:
        raise ValidationError(
            f"No appraisal with id {appraisal_id}")
    return update_appraisal(appraisal_id,
                                  {**_to_appraisal_dict(a),
                                    "status": "Closed"})


def set_appraisal_status(appraisal_id: int,
                              new_status: str) -> Appraisal:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    a = get_appraisal(appraisal_id)
    if a is None:
        raise ValidationError(
            f"No appraisal with id {appraisal_id}")
    return update_appraisal(appraisal_id,
                                  {**_to_appraisal_dict(a),
                                    "status": new_status})


def objective_count(appraisal_id: int) -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM appraisal_objectives "
            "WHERE appraisal_id=?",
            (appraisal_id,)).fetchone()
    return int(row["c"]) if row else 0


# ── Objectives ───────────────────────────────────────────

def _next_objective_number(appraisal_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT MAX(objective_number) m "
            "FROM appraisal_objectives WHERE appraisal_id=?",
            (appraisal_id,)).fetchone()
    return int(row["m"] or 0) + 1


def _validate_objective(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Objective title is required")
    ot = (out.get("objective_type")
            or DEFAULT_OBJECTIVE_TYPE).strip()
    if ot not in OBJECTIVE_TYPES:
        raise ValidationError(
            f"Objective type must be one of: "
            f"{', '.join(OBJECTIVE_TYPES)}")
    out["objective_type"] = ot
    status = (out.get("status")
              or DEFAULT_OBJECTIVE_STATUS).strip()
    if status not in OBJECTIVE_STATUSES:
        raise ValidationError(
            f"Objective status must be one of: "
            f"{', '.join(OBJECTIVE_STATUSES)}")
    out["status"] = status
    _check_date("Reviewed on", out.get("reviewed_on"))
    for k in ("description", "target_metric",
               "success_criteria", "progress_notes",
               "mid_year_progress", "end_year_evidence",
               "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    out["reviewed_on"] = (
        (out.get("reviewed_on") or "").strip() or None
        if isinstance(out.get("reviewed_on"), str)
        else out.get("reviewed_on"))
    w = out.get("weighting")
    if w in (None, ""):
        out["weighting"] = None
    else:
        try:
            wv = float(w)
        except (TypeError, ValueError):
            raise ValidationError("Weighting must be a number")
        if not (0 <= wv <= 100):
            raise ValidationError(
                "Weighting must be 0-100 (percent)")
        out["weighting"] = wv
    return out


def _row_objective(r: sqlite3.Row) -> Objective:
    return Objective(
        objective_id=r["objective_id"],
        appraisal_id=r["appraisal_id"],
        objective_number=r["objective_number"],
        objective_type=r["objective_type"],
        title=r["title"],
        description=r["description"],
        target_metric=r["target_metric"],
        success_criteria=r["success_criteria"],
        progress_notes=r["progress_notes"],
        mid_year_progress=r["mid_year_progress"],
        end_year_evidence=r["end_year_evidence"],
        status=r["status"],
        reviewed_on=r["reviewed_on"],
        weighting=r["weighting"],
        notes=r["notes"],
        created_on=r["created_on"],
    )


def add_objective(appraisal_id: int,
                       payload: dict[str, Any]) -> Objective:
    init_db()
    if get_appraisal(appraisal_id) is None:
        raise ValidationError(
            f"No appraisal with id {appraisal_id}")
    p = _validate_objective(payload)
    number = _next_objective_number(appraisal_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO appraisal_objectives (
              appraisal_id, objective_number, objective_type,
              title, description, target_metric,
              success_criteria, progress_notes, mid_year_progress,
              end_year_evidence, status, reviewed_on, weighting,
              notes, created_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            appraisal_id, number, p["objective_type"],
            p["title"], p["description"], p["target_metric"],
            p["success_criteria"], p["progress_notes"],
            p["mid_year_progress"], p["end_year_evidence"],
            p["status"], p["reviewed_on"], p["weighting"],
            p["notes"], now,
        ))
        new_id = cur.lastrowid
    return get_objective(new_id)


def update_objective(objective_id: int,
                          payload: dict[str, Any]) -> Objective:
    init_db()
    if get_objective(objective_id) is None:
        raise ValidationError(
            f"No objective with id {objective_id}")
    p = _validate_objective(payload)
    with _connect() as conn:
        conn.execute("""
            UPDATE appraisal_objectives SET
              objective_type=?, title=?, description=?,
              target_metric=?, success_criteria=?,
              progress_notes=?, mid_year_progress=?,
              end_year_evidence=?, status=?, reviewed_on=?,
              weighting=?, notes=?
            WHERE objective_id=?
        """, (
            p["objective_type"], p["title"], p["description"],
            p["target_metric"], p["success_criteria"],
            p["progress_notes"], p["mid_year_progress"],
            p["end_year_evidence"], p["status"],
            p["reviewed_on"], p["weighting"], p["notes"],
            objective_id,
        ))
    return get_objective(objective_id)


def delete_objective(objective_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM appraisal_objectives "
            "WHERE objective_id=?", (objective_id,))
        return cur.rowcount > 0


def get_objective(objective_id: int) -> Objective | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM appraisal_objectives "
            "WHERE objective_id=?",
            (objective_id,)).fetchone()
        return _row_objective(r) if r else None


def list_objectives(appraisal_id: int) -> list[Objective]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM appraisal_objectives "
            "WHERE appraisal_id=? "
            "ORDER BY objective_number ASC",
            (appraisal_id,)).fetchall()
    return [_row_objective(r) for r in rows]


def set_objective_status(objective_id: int,
                              new_status: str) -> Objective:
    if new_status not in OBJECTIVE_STATUSES:
        raise ValidationError(
            f"Objective status must be one of: "
            f"{', '.join(OBJECTIVE_STATUSES)}")
    o = get_objective(objective_id)
    if o is None:
        raise ValidationError(
            f"No objective with id {objective_id}")
    payload = {
        "objective_type": o.objective_type,
        "title": o.title,
        "description": o.description,
        "target_metric": o.target_metric,
        "success_criteria": o.success_criteria,
        "progress_notes": o.progress_notes,
        "mid_year_progress": o.mid_year_progress,
        "end_year_evidence": o.end_year_evidence,
        "status": new_status,
        "reviewed_on": o.reviewed_on,
        "weighting": o.weighting,
        "notes": o.notes,
    }
    return update_objective(objective_id, payload)


# ── Summary ──────────────────────────────────────────────

def summary() -> AppraisalsSummary:
    appraisals = list_appraisals()
    out = AppraisalsSummary(total=len(appraisals))
    if not appraisals:
        return out
    grades: list[int] = []
    cycles: set[str] = set()
    obj_total = 0
    obj_achieved = 0
    obj_by_status: dict[str, int] = {}
    for a in appraisals:
        cycles.add(a.cycle)
        if a.is_open:
            out.open_count += 1
            if a.mid_year_overdue:
                out.mid_year_overdue += 1
        if a.status == "Completed":
            out.completed += 1
        if a.upholding_standards:
            out.upholding_standards += 1
        if a.pay_progression == "Yes":
            out.pay_progression_yes += 1
        if a.pay_progression == "Deferred":
            out.pay_progression_deferred += 1
        if a.overall_grade is not None:
            grades.append(a.overall_grade)
            out.by_grade[a.overall_grade] = (
                out.by_grade.get(a.overall_grade, 0) + 1)
        out.by_cycle[a.cycle] = (
            out.by_cycle.get(a.cycle, 0) + 1)
        out.by_status[a.status] = (
            out.by_status.get(a.status, 0) + 1)
        out.by_pay_progression[a.pay_progression] = (
            out.by_pay_progression.get(a.pay_progression, 0) + 1)
        for o in list_objectives(a.appraisal_id):
            obj_total += 1
            if o.status == "Achieved":
                obj_achieved += 1
            obj_by_status[o.status] = (
                obj_by_status.get(o.status, 0) + 1)
    out.distinct_cycles = len(cycles)
    out.total_objectives = obj_total
    out.objectives_achieved = obj_achieved
    out.by_objective_status = obj_by_status
    if grades:
        out.average_grade = round(sum(grades) / len(grades), 2)
    return out


__all__ = [
    "GRADES", "grade_label",
    "PAY_PROGRESSION", "DEFAULT_PAY_PROGRESSION",
    "STATUSES", "DEFAULT_STATUS",
    "OBJECTIVE_TYPES", "DEFAULT_OBJECTIVE_TYPE",
    "OBJECTIVE_STATUSES", "DEFAULT_OBJECTIVE_STATUS",
    "ValidationError",
    "Appraisal", "Objective", "AppraisalsSummary",
    "init_db",
    "create_appraisal", "update_appraisal",
    "delete_appraisal", "get_appraisal",
    "list_appraisals", "list_cycles",
    "set_objectives", "record_mid_year", "record_end_year",
    "close_appraisal", "set_appraisal_status",
    "objective_count",
    "add_objective", "update_objective",
    "delete_objective", "get_objective", "list_objectives",
    "set_objective_status",
    "summary",
]
