"""Census / ILR data layer for Primary School System.

Tracks statutory data returns:
 - DfE School Census (autumn / spring / summer)
 - ESFA Individualised Learner Record (ILR) submissions

A `Return` row is the overall submission window; `LearnerAim`
rows are the per-student ILR aim entries which roll up into
the return. Returns move through Draft → Validated → Submitted
→ Accepted (or Rejected) status workflow.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.systems.primary.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

RETURN_TYPES: tuple[str, ...] = (
    "School Census - Autumn",
    "School Census - Spring",
    "School Census - Summer",
    "Workforce Census",
    "Alternative Provision Census",
    "Pupil Premium Return",
    "Other",
)
DEFAULT_RETURN_TYPE = "School Census - Autumn"

RETURN_STATUSES: tuple[str, ...] = (
    "Planned",
    "Draft",
    "Under Review",
    "Validated",
    "Submitted",
    "Accepted",
    "Rejected",
    "Resubmitted",
    "Archived",
)
DEFAULT_RETURN_STATUS = "Planned"

AIM_TYPES: tuple[str, ...] = (
    "Programme Aim",
    "Component Aim",
    "Core Aim",
    "Maths",
    "English",
    "Tutorial",
    "Work Placement",
    "Enrichment",
    "Other",
)
DEFAULT_AIM_TYPE = "Programme Aim"

FUNDING_MODELS: tuple[str, ...] = (
    "16-19 (excluding Apprenticeships)",
    "Apprenticeship",
    "Adult Skills",
    "Advanced Learner Loans",
    "Community Learning",
    "ESFA Other",
    "Other",
)
DEFAULT_FUNDING_MODEL = "16-19 (excluding Apprenticeships)"

LEARNER_AIM_STATUSES: tuple[str, ...] = (
    "Continuing",
    "Completed",
    "Withdrawn",
    "Transferred",
    "Achieved",
    "Partially Achieved",
    "Not Achieved",
    "Temporarily Withdrawn",
)
DEFAULT_LEARNER_AIM_STATUS = "Continuing"

COMPLETION_CODES: tuple[int, ...] = (1, 2, 3, 6, 7, 10)
# 1 Continuing, 2 Completed (achieved), 3 Withdrawn,
# 6 Temporarily withdrawn, 7 Transferred, 10 Completed
# (not achieved)


class ValidationError(Exception):
    pass


@dataclass
class CensusReturn:
    return_id: int
    return_type: str
    academic_year: str
    reference_date: str | None
    window_opens: str | None
    window_closes: str | None
    submission_deadline: str | None
    status: str
    submitted_on: str | None
    submitted_by: str | None
    accepted_on: str | None
    learner_count: int
    error_count: int
    warning_count: int
    file_ref: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_overdue(self) -> bool:
        if not self.submission_deadline:
            return False
        if self.status in ("Submitted", "Accepted",
                                  "Resubmitted", "Archived"):
            return False
        return (self.submission_deadline
                  < _dt.date.today().isoformat())

    @property
    def is_open_window(self) -> bool:
        today = _dt.date.today().isoformat()
        if not (self.window_opens and self.window_closes):
            return False
        return self.window_opens <= today <= self.window_closes


@dataclass
class LearnerAim:
    aim_id: int
    return_id: int | None
    learner_ref: str
    learner_name: str | None
    ukprn: str | None
    uln: str | None
    aim_type: str
    aim_reference: str
    aim_title: str | None
    funding_model: str
    start_date: str
    planned_end_date: str | None
    actual_end_date: str | None
    completion_code: int | None
    outcome_code: str | None
    status: str
    planned_hours: int | None
    actual_hours: int | None
    funding_band_value: float | None
    delivery_location: str | None
    partner_ukprn: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status in ("Continuing",
                                       "Temporarily Withdrawn")


@dataclass
class CensusIlrSummary:
    total_returns: int = 0
    planned: int = 0
    in_progress: int = 0
    submitted: int = 0
    accepted: int = 0
    rejected: int = 0
    overdue: int = 0
    open_windows: int = 0
    total_aims: int = 0
    continuing_aims: int = 0
    completed_aims: int = 0
    withdrawn_aims: int = 0
    achieved_aims: int = 0
    distinct_learners: int = 0
    total_planned_hours: int = 0
    total_funding_value: float = 0.0
    by_return_type: dict[str, int] = field(default_factory=dict)
    by_return_status: dict[str, int] = field(default_factory=dict)
    by_funding_model: dict[str, int] = field(default_factory=dict)
    by_aim_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.CENSUS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS census_returns (
              return_id           INTEGER PRIMARY KEY AUTOINCREMENT,
              return_type         TEXT NOT NULL,
              academic_year       TEXT NOT NULL,
              reference_date      TEXT,
              window_opens        TEXT,
              window_closes       TEXT,
              submission_deadline TEXT,
              status              TEXT NOT NULL,
              submitted_on        TEXT,
              submitted_by        TEXT,
              accepted_on         TEXT,
              learner_count       INTEGER NOT NULL DEFAULT 0,
              error_count         INTEGER NOT NULL DEFAULT 0,
              warning_count       INTEGER NOT NULL DEFAULT 0,
              file_ref            TEXT,
              notes               TEXT,
              created_on          TEXT NOT NULL,
              updated_on          TEXT NOT NULL,
              UNIQUE (return_type, academic_year)
            );

            CREATE TABLE IF NOT EXISTS learner_aims (
              aim_id              INTEGER PRIMARY KEY AUTOINCREMENT,
              return_id           INTEGER REFERENCES census_returns(return_id) ON DELETE SET NULL,
              learner_ref         TEXT NOT NULL,
              learner_name        TEXT,
              ukprn               TEXT,
              uln                 TEXT,
              aim_type            TEXT NOT NULL,
              aim_reference       TEXT NOT NULL,
              aim_title           TEXT,
              funding_model       TEXT NOT NULL,
              start_date          TEXT NOT NULL,
              planned_end_date    TEXT,
              actual_end_date     TEXT,
              completion_code     INTEGER,
              outcome_code        TEXT,
              status              TEXT NOT NULL,
              planned_hours       INTEGER,
              actual_hours        INTEGER,
              funding_band_value  REAL,
              delivery_location   TEXT,
              partner_ukprn       TEXT,
              notes               TEXT,
              created_on          TEXT NOT NULL,
              updated_on          TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_aims_learner
              ON learner_aims(learner_ref);
            CREATE INDEX IF NOT EXISTS ix_aims_return
              ON learner_aims(return_id);
            CREATE INDEX IF NOT EXISTS ix_aims_status
              ON learner_aims(status);
        """)


def _check_date(label: str, value: str | None) -> None:
    if not value:
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            f"{label} must be YYYY-MM-DD")


def _opt_int(out: dict, key: str, label: str) -> None:
    v = out.get(key)
    if v in (None, ""):
        out[key] = None
        return
    try:
        out[key] = int(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be an integer")
    if out[key] < 0:
        raise ValidationError(f"{label} must be >= 0")


def _opt_float(out: dict, key: str, label: str) -> None:
    v = out.get(key)
    if v in (None, ""):
        out[key] = None
        return
    try:
        out[key] = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number")
    if out[key] < 0:
        raise ValidationError(f"{label} must be >= 0")


def _validate_return(p: dict[str, Any], *,
                          existing_id: int | None = None
                          ) -> dict[str, Any]:
    out = dict(p)
    rt = (out.get("return_type") or DEFAULT_RETURN_TYPE).strip()
    if rt not in RETURN_TYPES:
        raise ValidationError(
            f"Return type must be one of: "
            f"{', '.join(RETURN_TYPES)}")
    out["return_type"] = rt

    out["academic_year"] = (out.get("academic_year") or "").strip()
    if not out["academic_year"]:
        raise ValidationError("Academic year is required")

    status = (out.get("status") or DEFAULT_RETURN_STATUS).strip()
    if status not in RETURN_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(RETURN_STATUSES)}")
    out["status"] = status

    for k, lbl in (
            ("reference_date", "Reference date"),
            ("window_opens", "Window opens"),
            ("window_closes", "Window closes"),
            ("submission_deadline", "Submission deadline"),
            ("submitted_on", "Submitted on"),
            ("accepted_on", "Accepted on")):
        _check_date(lbl, out.get(k))

    if (out.get("window_opens") and out.get("window_closes")
            and out["window_closes"] < out["window_opens"]):
        raise ValidationError(
            "Window closes cannot be before window opens")

    for k, lbl in (
            ("learner_count", "Learner count"),
            ("error_count", "Error count"),
            ("warning_count", "Warning count")):
        v = out.get(k)
        if v in (None, ""):
            out[k] = 0
        else:
            try:
                out[k] = int(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{lbl} must be an integer")
            if out[k] < 0:
                raise ValidationError(
                    f"{lbl} must be >= 0")

    for k in ("submitted_by", "file_ref", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("reference_date", "window_opens",
               "window_closes", "submission_deadline",
               "submitted_on", "accepted_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None
                    if isinstance(v, str) else v)

    # Uniqueness on (type, academic_year)
    with _connect() as conn:
        row = conn.execute(
            "SELECT return_id FROM census_returns "
            "WHERE return_type=? AND academic_year=?",
            (out["return_type"],
              out["academic_year"])).fetchone()
    if row and row["return_id"] != existing_id:
        raise ValidationError(
            f"A {out['return_type']} return for "
            f"{out['academic_year']} already exists")
    return out


def _validate_aim(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["learner_ref"] = (out.get("learner_ref") or "").strip()
    if not out["learner_ref"]:
        raise ValidationError("Learner ref is required")

    at = (out.get("aim_type") or DEFAULT_AIM_TYPE).strip()
    if at not in AIM_TYPES:
        raise ValidationError(
            f"Aim type must be one of: {', '.join(AIM_TYPES)}")
    out["aim_type"] = at

    out["aim_reference"] = (out.get("aim_reference")
                                    or "").strip()
    if not out["aim_reference"]:
        raise ValidationError("Aim reference is required")

    fm = (out.get("funding_model")
            or DEFAULT_FUNDING_MODEL).strip()
    if fm not in FUNDING_MODELS:
        raise ValidationError(
            f"Funding model must be one of: "
            f"{', '.join(FUNDING_MODELS)}")
    out["funding_model"] = fm

    status = (out.get("status")
                  or DEFAULT_LEARNER_AIM_STATUS).strip()
    if status not in LEARNER_AIM_STATUSES:
        raise ValidationError(
            f"Aim status must be one of: "
            f"{', '.join(LEARNER_AIM_STATUSES)}")
    out["status"] = status

    out["start_date"] = (out.get("start_date") or "").strip()
    if not out["start_date"]:
        raise ValidationError("Start date is required")
    _check_date("Start date", out["start_date"])
    _check_date("Planned end date",
                    out.get("planned_end_date"))
    _check_date("Actual end date", out.get("actual_end_date"))

    if (out.get("planned_end_date")
            and out["planned_end_date"] < out["start_date"]):
        raise ValidationError(
            "Planned end date cannot be before start date")
    if (out.get("actual_end_date")
            and out["actual_end_date"] < out["start_date"]):
        raise ValidationError(
            "Actual end date cannot be before start date")

    cc = out.get("completion_code")
    if cc in (None, ""):
        out["completion_code"] = None
    else:
        try:
            out["completion_code"] = int(cc)
        except (TypeError, ValueError):
            raise ValidationError(
                "Completion code must be an integer")
        if out["completion_code"] not in COMPLETION_CODES:
            raise ValidationError(
                f"Completion code must be one of "
                f"{COMPLETION_CODES}")

    rid = out.get("return_id")
    if rid in (None, "", 0):
        out["return_id"] = None
    else:
        try:
            out["return_id"] = int(rid)
        except (TypeError, ValueError):
            raise ValidationError(
                "Return id must be an integer")

    _opt_int(out, "planned_hours", "Planned hours")
    _opt_int(out, "actual_hours", "Actual hours")
    _opt_float(out, "funding_band_value", "Funding band value")

    for k in ("learner_name", "ukprn", "uln", "aim_title",
               "outcome_code", "delivery_location",
               "partner_ukprn", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("planned_end_date", "actual_end_date"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None
                    if isinstance(v, str) else v)
    return out


def _row_return(r: sqlite3.Row) -> CensusReturn:
    return CensusReturn(
        return_id=r["return_id"],
        return_type=r["return_type"],
        academic_year=r["academic_year"],
        reference_date=r["reference_date"],
        window_opens=r["window_opens"],
        window_closes=r["window_closes"],
        submission_deadline=r["submission_deadline"],
        status=r["status"],
        submitted_on=r["submitted_on"],
        submitted_by=r["submitted_by"],
        accepted_on=r["accepted_on"],
        learner_count=r["learner_count"],
        error_count=r["error_count"],
        warning_count=r["warning_count"],
        file_ref=r["file_ref"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def _row_aim(r: sqlite3.Row) -> LearnerAim:
    return LearnerAim(
        aim_id=r["aim_id"],
        return_id=r["return_id"],
        learner_ref=r["learner_ref"],
        learner_name=r["learner_name"],
        ukprn=r["ukprn"],
        uln=r["uln"],
        aim_type=r["aim_type"],
        aim_reference=r["aim_reference"],
        aim_title=r["aim_title"],
        funding_model=r["funding_model"],
        start_date=r["start_date"],
        planned_end_date=r["planned_end_date"],
        actual_end_date=r["actual_end_date"],
        completion_code=r["completion_code"],
        outcome_code=r["outcome_code"],
        status=r["status"],
        planned_hours=r["planned_hours"],
        actual_hours=r["actual_hours"],
        funding_band_value=r["funding_band_value"],
        delivery_location=r["delivery_location"],
        partner_ukprn=r["partner_ukprn"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


# ── CRUD: returns ─────────────────────────────────────────

def create_return(payload: dict[str, Any]) -> CensusReturn:
    init_db()
    p = _validate_return(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO census_returns (
              return_type, academic_year, reference_date,
              window_opens, window_closes,
              submission_deadline, status, submitted_on,
              submitted_by, accepted_on, learner_count,
              error_count, warning_count, file_ref, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?)
        """, (
            p["return_type"], p["academic_year"],
            p["reference_date"], p["window_opens"],
            p["window_closes"], p["submission_deadline"],
            p["status"], p["submitted_on"],
            p["submitted_by"], p["accepted_on"],
            p["learner_count"], p["error_count"],
            p["warning_count"], p["file_ref"], p["notes"],
            now, now,
        ))
        rid = cur.lastrowid
    return get_return(rid)  # type: ignore[return-value]


def update_return(return_id: int,
                       payload: dict[str, Any]) -> CensusReturn:
    init_db()
    if get_return(return_id) is None:
        raise ValidationError(
            f"No return with id {return_id}")
    p = _validate_return(payload, existing_id=return_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE census_returns SET
              return_type=?, academic_year=?,
              reference_date=?, window_opens=?,
              window_closes=?, submission_deadline=?,
              status=?, submitted_on=?, submitted_by=?,
              accepted_on=?, learner_count=?,
              error_count=?, warning_count=?, file_ref=?,
              notes=?, updated_on=?
            WHERE return_id=?
        """, (
            p["return_type"], p["academic_year"],
            p["reference_date"], p["window_opens"],
            p["window_closes"], p["submission_deadline"],
            p["status"], p["submitted_on"],
            p["submitted_by"], p["accepted_on"],
            p["learner_count"], p["error_count"],
            p["warning_count"], p["file_ref"], p["notes"],
            now, return_id,
        ))
    return get_return(return_id)  # type: ignore[return-value]


def delete_return(return_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM census_returns WHERE return_id=?",
            (return_id,))
        return cur.rowcount > 0


def get_return(return_id: int) -> CensusReturn | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM census_returns WHERE return_id=?",
            (return_id,)).fetchone()
    return _row_return(r) if r else None


def list_returns(*,
                       return_type: str | None = None,
                       academic_year: str | None = None,
                       status: str | None = None,
                       overdue_only: bool = False,
                       open_window_only: bool = False,
                       ) -> list[CensusReturn]:
    init_db()
    sql = "SELECT * FROM census_returns WHERE 1=1"
    params: list[Any] = []
    if return_type:
        sql += " AND return_type=?"
        params.append(return_type)
    if academic_year:
        sql += " AND academic_year=?"
        params.append(academic_year)
    if status:
        sql += " AND status=?"
        params.append(status)
    if overdue_only:
        today = _dt.date.today().isoformat()
        sql += (" AND submission_deadline IS NOT NULL"
                  " AND submission_deadline < ?"
                  " AND status NOT IN "
                  "('Submitted','Accepted',"
                  "'Resubmitted','Archived')")
        params.append(today)
    if open_window_only:
        today = _dt.date.today().isoformat()
        sql += (" AND window_opens IS NOT NULL"
                  " AND window_closes IS NOT NULL"
                  " AND window_opens <= ?"
                  " AND window_closes >= ?")
        params.extend([today, today])
    sql += (" ORDER BY academic_year DESC,"
              " submission_deadline,"
              " return_type")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_return(r) for r in rows]


# ── CRUD: aims ───────────────────────────────────────────

def create_aim(payload: dict[str, Any]) -> LearnerAim:
    init_db()
    p = _validate_aim(payload)
    if p["return_id"] is not None:
        if get_return(p["return_id"]) is None:
            raise ValidationError(
                f"No return with id {p['return_id']}")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO learner_aims (
              return_id, learner_ref, learner_name, ukprn,
              uln, aim_type, aim_reference, aim_title,
              funding_model, start_date, planned_end_date,
              actual_end_date, completion_code, outcome_code,
              status, planned_hours, actual_hours,
              funding_band_value, delivery_location,
              partner_ukprn, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["return_id"], p["learner_ref"],
            p["learner_name"], p["ukprn"], p["uln"],
            p["aim_type"], p["aim_reference"], p["aim_title"],
            p["funding_model"], p["start_date"],
            p["planned_end_date"], p["actual_end_date"],
            p["completion_code"], p["outcome_code"],
            p["status"], p["planned_hours"],
            p["actual_hours"], p["funding_band_value"],
            p["delivery_location"], p["partner_ukprn"],
            p["notes"], now, now,
        ))
        aid = cur.lastrowid
    return get_aim(aid)  # type: ignore[return-value]


def update_aim(aim_id: int,
                    payload: dict[str, Any]) -> LearnerAim:
    init_db()
    if get_aim(aim_id) is None:
        raise ValidationError(f"No aim with id {aim_id}")
    p = _validate_aim(payload)
    if p["return_id"] is not None:
        if get_return(p["return_id"]) is None:
            raise ValidationError(
                f"No return with id {p['return_id']}")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE learner_aims SET
              return_id=?, learner_ref=?, learner_name=?,
              ukprn=?, uln=?, aim_type=?, aim_reference=?,
              aim_title=?, funding_model=?, start_date=?,
              planned_end_date=?, actual_end_date=?,
              completion_code=?, outcome_code=?, status=?,
              planned_hours=?, actual_hours=?,
              funding_band_value=?, delivery_location=?,
              partner_ukprn=?, notes=?, updated_on=?
            WHERE aim_id=?
        """, (
            p["return_id"], p["learner_ref"],
            p["learner_name"], p["ukprn"], p["uln"],
            p["aim_type"], p["aim_reference"], p["aim_title"],
            p["funding_model"], p["start_date"],
            p["planned_end_date"], p["actual_end_date"],
            p["completion_code"], p["outcome_code"],
            p["status"], p["planned_hours"],
            p["actual_hours"], p["funding_band_value"],
            p["delivery_location"], p["partner_ukprn"],
            p["notes"], now, aim_id,
        ))
    return get_aim(aim_id)  # type: ignore[return-value]


def delete_aim(aim_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM learner_aims WHERE aim_id=?",
            (aim_id,))
        return cur.rowcount > 0


def get_aim(aim_id: int) -> LearnerAim | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM learner_aims WHERE aim_id=?",
            (aim_id,)).fetchone()
    return _row_aim(r) if r else None


def list_aims(*,
                  return_id: int | None = None,
                  learner_ref: str | None = None,
                  aim_type: str | None = None,
                  funding_model: str | None = None,
                  status: str | None = None,
                  active_only: bool = False,
                  ) -> list[LearnerAim]:
    init_db()
    sql = "SELECT * FROM learner_aims WHERE 1=1"
    params: list[Any] = []
    if return_id is not None:
        sql += " AND return_id=?"
        params.append(return_id)
    if learner_ref:
        sql += " AND learner_ref=?"
        params.append(learner_ref)
    if aim_type:
        sql += " AND aim_type=?"
        params.append(aim_type)
    if funding_model:
        sql += " AND funding_model=?"
        params.append(funding_model)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += (" AND status IN "
                  "('Continuing','Temporarily Withdrawn')")
    sql += (" ORDER BY learner_ref, start_date,"
              " aim_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_aim(r) for r in rows]


def aims_for_learner(learner_ref: str) -> list[LearnerAim]:
    return list_aims(learner_ref=learner_ref)


def aims_for_return(return_id: int) -> list[LearnerAim]:
    return list_aims(return_id=return_id)


# ── Workflow ──────────────────────────────────────────────

def _ret_dict(r: CensusReturn) -> dict[str, Any]:
    return {
        "return_type": r.return_type,
        "academic_year": r.academic_year,
        "reference_date": r.reference_date,
        "window_opens": r.window_opens,
        "window_closes": r.window_closes,
        "submission_deadline": r.submission_deadline,
        "status": r.status,
        "submitted_on": r.submitted_on,
        "submitted_by": r.submitted_by,
        "accepted_on": r.accepted_on,
        "learner_count": r.learner_count,
        "error_count": r.error_count,
        "warning_count": r.warning_count,
        "file_ref": r.file_ref,
        "notes": r.notes,
    }


def validate_return(return_id: int) -> CensusReturn:
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    return update_return(return_id,
                                {**_ret_dict(r),
                                  "status": "Validated"})


def submit_return(return_id: int, *,
                          submitted_by: str | None = None,
                          file_ref: str | None = None
                          ) -> CensusReturn:
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    data = _ret_dict(r)
    data["status"] = "Submitted"
    data["submitted_on"] = _dt.date.today().isoformat()
    if submitted_by:
        data["submitted_by"] = submitted_by
    if file_ref:
        data["file_ref"] = file_ref
    aim_rows = aims_for_return(return_id)
    data["learner_count"] = len({a.learner_ref
                                            for a in aim_rows})
    return update_return(return_id, data)


def accept_return(return_id: int, *,
                          accepted_on: str | None = None
                          ) -> CensusReturn:
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    data = _ret_dict(r)
    data["status"] = "Accepted"
    data["accepted_on"] = (accepted_on
                                  or _dt.date.today().isoformat())
    return update_return(return_id, data)


def reject_return(return_id: int) -> CensusReturn:
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    return update_return(return_id,
                                {**_ret_dict(r),
                                  "status": "Rejected"})


def resubmit_return(return_id: int, *,
                            submitted_by: str | None = None,
                            file_ref: str | None = None
                            ) -> CensusReturn:
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    data = _ret_dict(r)
    data["status"] = "Resubmitted"
    data["submitted_on"] = _dt.date.today().isoformat()
    if submitted_by:
        data["submitted_by"] = submitted_by
    if file_ref:
        data["file_ref"] = file_ref
    return update_return(return_id, data)


def archive_return(return_id: int) -> CensusReturn:
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    return update_return(return_id,
                                {**_ret_dict(r),
                                  "status": "Archived"})


def set_return_status(return_id: int,
                                  new_status: str) -> CensusReturn:
    if new_status not in RETURN_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(RETURN_STATUSES)}")
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    return update_return(return_id,
                                {**_ret_dict(r),
                                  "status": new_status})


def record_validation_counts(return_id: int, *,
                                              errors: int = 0,
                                              warnings: int = 0
                                              ) -> CensusReturn:
    r = get_return(return_id)
    if r is None:
        raise ValidationError(
            f"No return with id {return_id}")
    data = _ret_dict(r)
    data["error_count"] = max(int(errors), 0)
    data["warning_count"] = max(int(warnings), 0)
    return update_return(return_id, data)


# ── Summary ─────────────────────────────────────────────

def summary() -> CensusIlrSummary:
    returns = list_returns()
    aims = list_aims()
    out = CensusIlrSummary(
        total_returns=len(returns),
        total_aims=len(aims))
    for r in returns:
        if r.status == "Planned":
            out.planned += 1
        elif r.status in ("Draft", "Under Review",
                                 "Validated"):
            out.in_progress += 1
        elif r.status in ("Submitted", "Resubmitted"):
            out.submitted += 1
        elif r.status == "Accepted":
            out.accepted += 1
        elif r.status == "Rejected":
            out.rejected += 1
        if r.is_overdue:
            out.overdue += 1
        if r.is_open_window:
            out.open_windows += 1
        out.by_return_type[r.return_type] = (
            out.by_return_type.get(r.return_type, 0) + 1)
        out.by_return_status[r.status] = (
            out.by_return_status.get(r.status, 0) + 1)
    learners: set[str] = set()
    for a in aims:
        learners.add(a.learner_ref)
        if a.status == "Continuing":
            out.continuing_aims += 1
        elif a.status == "Completed":
            out.completed_aims += 1
        elif a.status == "Withdrawn":
            out.withdrawn_aims += 1
        elif a.status == "Achieved":
            out.achieved_aims += 1
        if a.planned_hours:
            out.total_planned_hours += a.planned_hours
        if a.funding_band_value:
            out.total_funding_value += a.funding_band_value
        out.by_funding_model[a.funding_model] = (
            out.by_funding_model.get(a.funding_model, 0) + 1)
        out.by_aim_status[a.status] = (
            out.by_aim_status.get(a.status, 0) + 1)
    out.distinct_learners = len(learners)
    return out


__all__ = [
    "RETURN_TYPES", "DEFAULT_RETURN_TYPE",
    "RETURN_STATUSES", "DEFAULT_RETURN_STATUS",
    "AIM_TYPES", "DEFAULT_AIM_TYPE",
    "FUNDING_MODELS", "DEFAULT_FUNDING_MODEL",
    "LEARNER_AIM_STATUSES", "DEFAULT_LEARNER_AIM_STATUS",
    "COMPLETION_CODES",
    "ValidationError",
    "CensusReturn", "LearnerAim", "CensusIlrSummary",
    "init_db",
    "create_return", "update_return", "delete_return",
    "get_return", "list_returns",
    "create_aim", "update_aim", "delete_aim",
    "get_aim", "list_aims",
    "aims_for_learner", "aims_for_return",
    "validate_return", "submit_return", "accept_return",
    "reject_return", "resubmit_return", "archive_return",
    "set_return_status", "record_validation_counts",
    "summary",
]
