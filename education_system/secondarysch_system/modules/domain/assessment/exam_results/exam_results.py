"""Results-Day data layer for the Secondary School System.

Final GCSE results, linked to ``exam_entries`` rows. Each result row
captures the final grade (and optionally marks, UMS), with a status
workflow that lets schools record post-results day changes:

* ``Pending``      — entry exists, result not yet received
* ``Final``        — result received and confirmed
* ``Remarked``     — submitted for review of marking
* ``Adjusted``     — grade changed after remark
* ``Withheld``     — board has withheld the result

One row per entry — unique on ``entry_id``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.secondarysch_system.modules.domain.pupils.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

RESULT_STATUSES: tuple[str, ...] = (
    "Pending", "Final", "Remarked", "Adjusted", "Withheld")
DEFAULT_STATUS: str = "Pending"

PASS_GRADES_9_1: tuple[str, ...] = ("9", "8", "7", "6", "5", "4")
STRONG_PASS_GRADES: tuple[str, ...] = ("9", "8", "7", "6", "5")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_GRADE_RE = re.compile(r"^[A-Za-z0-9*+\-]{1,3}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_results (
    result_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id         INTEGER NOT NULL UNIQUE,
    pupil_id         TEXT NOT NULL,
    subject_id       INTEGER NOT NULL,
    final_grade      TEXT,
    marks_awarded    REAL,
    ums              REAL,
    result_date      TEXT NOT NULL DEFAULT (date('now')),
    status           TEXT NOT NULL DEFAULT 'Pending',
    remark_outcome   TEXT,
    notes            TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (entry_id) REFERENCES exam_entries(entry_id)
);

CREATE INDEX IF NOT EXISTS idx_er_pupil ON exam_results(pupil_id);
CREATE INDEX IF NOT EXISTS idx_er_subject ON exam_results(subject_id);
CREATE INDEX IF NOT EXISTS idx_er_status ON exam_results(status);
"""


@dataclass
class ExamResult:
    result_id: int
    entry_id: int
    pupil_id: str
    subject_id: int
    final_grade: str | None
    marks_awarded: float | None
    ums: float | None
    result_date: str
    status: str
    remark_outcome: str | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str | None = None
    pupil_year: str | None = None
    exam_board: str | None = None
    tier: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def is_pass(self) -> bool | None:
        if self.final_grade is None:
            return None
        return self.final_grade.upper() in PASS_GRADES_9_1

    @property
    def is_strong_pass(self) -> bool | None:
        if self.final_grade is None:
            return None
        return self.final_grade.upper() in STRONG_PASS_GRADES


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.secondarysch_system.modules.domain.assessment.exam_entries import (
        exam_entries as entries_data,
    )
    entries_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise exam_results table")
        raise
    logger.info("Secondary exam_results table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> ExamResult:
    keys = r.keys()
    return ExamResult(
        result_id=r["result_id"], entry_id=r["entry_id"],
        pupil_id=r["pupil_id"], subject_id=r["subject_id"],
        final_grade=r["final_grade"],
        marks_awarded=r["marks_awarded"], ums=r["ums"],
        result_date=r["result_date"], status=r["status"],
        remark_outcome=r["remark_outcome"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        exam_board=r["exam_board"] if "exam_board" in keys else None,
        tier=r["tier"] if "tier" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str) -> str:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return _dt.date.today().isoformat()
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    eid_raw = data.get("entry_id")
    if eid_raw in (None, ""):
        raise ValidationError("Entry ID is required")
    try:
        out["entry_id"] = int(eid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Entry ID must be a number") from None

    from education_system.secondarysch_system.modules.domain.assessment.exam_entries import (
        exam_entries as entries_data,
    )
    entry = entries_data.get(out["entry_id"])
    if entry is None:
        raise ValidationError(f"No exam entry #{out['entry_id']}")
    out["pupil_id"]   = entry.pupil_id
    out["subject_id"] = entry.subject_id

    grade = (data.get("final_grade") or "").strip()
    if grade:
        if not _GRADE_RE.match(grade):
            raise ValidationError(
                "Final grade must be 1–3 chars (letters/digits/* + -)")
        out["final_grade"] = grade.upper()
    else:
        out["final_grade"] = None

    def _opt_float(value, label, *, mn, mx):
        if value in (None, "") or (isinstance(value, str)
                                    and not value.strip()):
            return None
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{label} must be a number") from None
        if v < mn or v > mx:
            raise ValidationError(
                f"{label} must be between {mn} and {mx}")
        return v

    out["marks_awarded"] = _opt_float(data.get("marks_awarded"),
                                        "Marks awarded", mn=0, mx=10000)
    out["ums"] = _opt_float(data.get("ums"), "UMS", mn=0, mx=600)
    out["result_date"] = _validate_date(data.get("result_date"),
                                          "Result date")

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in RESULT_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(RESULT_STATUSES)}")
    out["status"] = status

    out["remark_outcome"] = (data.get("remark_outcome") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None

    if (out["status"] in ("Final", "Adjusted")
            and out["final_grade"] is None):
        raise ValidationError(
            f"Final grade is required when status is {out['status']}")
    return out


def upsert(data: dict[str, Any]) -> ExamResult:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT result_id FROM exam_results WHERE entry_id = ?",
                (payload["entry_id"],),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE exam_results SET
                           final_grade = ?, marks_awarded = ?, ums = ?,
                           result_date = ?, status = ?,
                           remark_outcome = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE result_id = ?""",
                    (payload["final_grade"], payload["marks_awarded"],
                     payload["ums"], payload["result_date"],
                     payload["status"], payload["remark_outcome"],
                     payload["notes"], row["result_id"]),
                )
                rid = row["result_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO exam_results
                           (entry_id, pupil_id, subject_id,
                            final_grade, marks_awarded, ums,
                            result_date, status, remark_outcome, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload["entry_id"], payload["pupil_id"],
                     payload["subject_id"], payload["final_grade"],
                     payload["marks_awarded"], payload["ums"],
                     payload["result_date"], payload["status"],
                     payload["remark_outcome"], payload["notes"]),
                )
                rid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert exam result for entry %d",
            payload["entry_id"])
        raise
    logger.info(
        "Exam result %s: entry=#%d pupil=%s subject=#%d grade=%s status=%s",
        action, payload["entry_id"], payload["pupil_id"],
        payload["subject_id"], payload["final_grade"],
        payload["status"])
    rec = get(rid)
    assert rec is not None
    return rec


def get(result_id: int) -> ExamResult | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT r.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year,
                          e.exam_board AS exam_board, e.tier AS tier
                   FROM exam_results r
                   LEFT JOIN subjects s ON s.subject_id = r.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = r.pupil_id
                   LEFT JOIN exam_entries e ON e.entry_id = r.entry_id
                   WHERE r.result_id = ?""",
                (result_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", result_id)
        raise
    return _row(r) if r else None


def get_for_entry(entry_id: int) -> ExamResult | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT r.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year,
                          e.exam_board AS exam_board, e.tier AS tier
                   FROM exam_results r
                   LEFT JOIN subjects s ON s.subject_id = r.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = r.pupil_id
                   LEFT JOIN exam_entries e ON e.entry_id = r.entry_id
                   WHERE r.entry_id = ?""",
                (int(entry_id),),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_for_entry(%s) failed", entry_id)
        raise
    return _row(r) if r else None


def list_results(*, year_group: str | None = None,
                 subject_id: int | None = None,
                 status: str | None = None,
                 pupil_id: str | None = None) -> list[ExamResult]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if subject_id is not None:
        where.append("r.subject_id = ?")
        params.append(int(subject_id))
    if status:
        if status not in RESULT_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(RESULT_STATUSES)}")
        where.append("r.status = ?")
        params.append(status)
    if pupil_id:
        where.append("r.pupil_id = ?")
        params.append(pupil_id.strip())
    sql = ("""SELECT r.*, s.code AS subject_code,
                     s.name AS subject_name,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year,
                     e.exam_board AS exam_board, e.tier AS tier
              FROM exam_results r
              LEFT JOIN subjects s ON s.subject_id = r.subject_id
              LEFT JOIN pupils p ON p.pupil_id = r.pupil_id
              LEFT JOIN exam_entries e ON e.entry_id = r.entry_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.year_group, p.last_name, s.name"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_results failed")
        raise


def list_pending_for_entries(year_group: str | None = None
                              ) -> list[Any]:
    """Return ``exam_entries`` rows that do not yet have a result.
    Returned objects are ``ExamEntry`` (from the entries module)."""
    init_db()
    from education_system.secondarysch_system.modules.domain.assessment.exam_entries import (
        exam_entries as entries_data,
    )
    entries = entries_data.list_entries(year_group=year_group,
                                          entry_status="Final")
    try:
        with _connect() as conn:
            done = {r[0] for r in conn.execute(
                "SELECT entry_id FROM exam_results").fetchall()}
    except sqlite3.Error:
        logger.exception("list_pending_for_entries failed")
        raise
    return [e for e in entries if e.entry_id not in done]


def delete(result_id: int) -> bool:
    init_db()
    existing = get(result_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM exam_results WHERE result_id = ?",
                (result_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete result #%d", result_id)
        raise
    if deleted:
        logger.info("Deleted exam result #%d (entry #%d)",
                    result_id, existing.entry_id)
    return deleted


def cohort_summary(*, year_group: str | None = None,
                   subject_id: int | None = None) -> dict[str, Any]:
    rows = list_results(year_group=year_group, subject_id=subject_id)
    graded = [r for r in rows if r.final_grade is not None]
    pass_count = sum(1 for r in graded if r.is_pass)
    strong_count = sum(1 for r in graded if r.is_strong_pass)
    return {
        "total":           len(rows),
        "graded":          len(graded),
        "by_status":       dict(Counter(r.status for r in rows)),
        "by_grade":        dict(Counter(r.final_grade for r in graded)),
        "pass_rate_pct":   (round(100.0 * pass_count / len(graded), 2)
                              if graded else None),
        "strong_pass_pct": (round(100.0 * strong_count / len(graded), 2)
                              if graded else None),
    }


def pupil_results(pupil_id: str) -> dict[str, Any]:
    rows = list_results(pupil_id=pupil_id)
    graded = [r for r in rows if r.final_grade is not None]
    pass_count = sum(1 for r in graded if r.is_pass)
    strong_count = sum(1 for r in graded if r.is_strong_pass)
    return {
        "pupil_id": (pupil_id or "").strip(),
        "results":  rows,
        "graded":   len(graded),
        "passes":   pass_count,
        "strong_passes": strong_count,
    }
