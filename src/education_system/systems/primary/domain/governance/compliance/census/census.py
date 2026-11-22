"""School Census data layer for the Primary School System.

Tracks statutory data returns - the DfE School Census (autumn / spring /
summer), the workforce census and similar. A return is a submission
window; it moves through Draft → Validated → Submitted → Accepted (or
Rejected). Submitting records the number of pupils on roll.

The ILR learner-aim half of the sixth-form original was taken out on
2026-11-05 (FE only); the ``learner_aims`` table is left in existing
databases but no longer used.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths as _paths

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
class CensusSummary:
    total_returns: int = 0
    planned: int = 0
    in_progress: int = 0
    submitted: int = 0
    accepted: int = 0
    rejected: int = 0
    overdue: int = 0
    open_windows: int = 0
    pupils_on_roll: int = 0
    by_return_type: dict[str, int] = field(default_factory=dict)
    by_return_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_primary_directories()
    conn = sqlite3.connect(_paths.PRIMARY_CENSUS_DB)
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


def _pupils_on_roll() -> int:
    """Pupils currently on roll - the headcount a school census return
    is made for."""
    from education_system.systems.primary.domain.learners.pupils import pupils
    return len(pupils.list_pupils())


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
    data["learner_count"] = _pupils_on_roll()
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

def summary() -> CensusSummary:
    returns = list_returns()
    out = CensusSummary(total_returns=len(returns),
                        pupils_on_roll=_pupils_on_roll())
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
    return out


__all__ = [
    "RETURN_TYPES", "DEFAULT_RETURN_TYPE",
    "RETURN_STATUSES", "DEFAULT_RETURN_STATUS",
    "ValidationError",
    "CensusReturn", "CensusSummary",
    "init_db",
    "create_return", "update_return", "delete_return",
    "get_return", "list_returns",
    "validate_return", "submit_return", "accept_return",
    "reject_return", "resubmit_return", "archive_return",
    "set_return_status", "record_validation_counts",
    "summary",
]
