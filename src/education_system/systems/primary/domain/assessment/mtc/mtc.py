"""Multiplication Tables Check data layer.

The MTC is a 25-question on-screen statutory check taken in Year 4.
There is no formal pass mark — DfE reports the average mark — but
schools often track an internal "expected" threshold (20+). We store
the raw score and let the UI report whether it met the configurable
``EXPECTED_THRESHOLD`` (20/25 = 80%).
"""

from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils import (
    pupils as pupils_data,
)
from education_system.systems.primary.domain.learners.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

MAX_SCORE = 25
EXPECTED_THRESHOLD = 20  # internal "met expected standard" marker

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mtc_results (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    score           INTEGER NOT NULL,
    assessed_on     TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(pupil_id, academic_year),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_mtc_pupil ON mtc_results(pupil_id);
CREATE INDEX IF NOT EXISTS idx_mtc_year  ON mtc_results(academic_year);
"""


@dataclass
class MTCResult:
    result_id: int
    pupil_id: str
    academic_year: str
    score: int
    assessed_on: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def met_expected(self) -> bool:
        return self.score >= EXPECTED_THRESHOLD

    @property
    def full_marks(self) -> bool:
        return self.score == MAX_SCORE


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    pupils_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise mtc_results table")
        raise
    logger.info("Primary mtc_results table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> MTCResult:
    return MTCResult(
        result_id=r["result_id"],
        pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        score=r["score"],
        assessed_on=r["assessed_on"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    out["pupil_id"] = pid
    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError("Academic year is required (e.g. 2025-26)")
    if not _ACADEMIC_YEAR_RE.match(ay):
        raise ValidationError("Academic year must look like 2025 or 2025-26")
    out["academic_year"] = ay
    score_raw = data.get("score")
    if score_raw in (None, ""):
        raise ValidationError("Score is required")
    try:
        score = int(score_raw)
    except (TypeError, ValueError) as e:
        raise ValidationError("Score must be an integer") from e
    if not (0 <= score <= MAX_SCORE):
        raise ValidationError(f"Score must be between 0 and {MAX_SCORE}")
    out["score"] = score
    assessed_on = (data.get("assessed_on") or "").strip()
    if assessed_on and not _DOB_RE.match(assessed_on):
        raise ValidationError("Assessed-on date must be YYYY-MM-DD")
    out["assessed_on"] = assessed_on or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> MTCResult:
    init_db()
    payload = _validate(data)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT result_id FROM mtc_results "
                "WHERE pupil_id = ? AND academic_year = ?",
                (payload["pupil_id"], payload["academic_year"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A result for pupil {payload['pupil_id']} in "
                    f"{payload['academic_year']} already exists "
                    f"(#{dup['result_id']})")
            cur = conn.execute(
                """INSERT INTO mtc_results
                       (pupil_id, academic_year, score, assessed_on, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["score"], payload["assessed_on"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create MTC result")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created MTC result #%d (pupil %s, %s, %d/%d%s)",
                rec.result_id, rec.pupil_id, rec.academic_year,
                rec.score, MAX_SCORE,
                ", full marks" if rec.full_marks else "")
    return rec


def get(result_id: int) -> MTCResult | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM mtc_results WHERE result_id = ?",
                (result_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get MTC(%s) failed", result_id)
        raise
    return _row(r) if r else None


def update(result_id: int, data: dict[str, Any]) -> MTCResult:
    init_db()
    existing = get(result_id)
    if existing is None:
        raise ValidationError(f"No MTC result #{result_id}")
    merged = {
        "pupil_id":      data.get("pupil_id", existing.pupil_id),
        "academic_year": data.get("academic_year", existing.academic_year),
        "score":         data.get("score", existing.score),
        "assessed_on":   data.get("assessed_on", existing.assessed_on),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT result_id FROM mtc_results "
                "WHERE pupil_id = ? AND academic_year = ? AND result_id <> ?",
                (payload["pupil_id"], payload["academic_year"], result_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another result for that pupil / year already exists "
                    f"(#{dup['result_id']})")
            conn.execute(
                """UPDATE mtc_results SET
                       pupil_id = ?, academic_year = ?, score = ?,
                       assessed_on = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE result_id = ?""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["score"], payload["assessed_on"],
                 payload["notes"], result_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update MTC #%d", result_id)
        raise
    rec = get(result_id)
    assert rec is not None
    logger.info("Updated MTC result #%d", result_id)
    return rec


def delete(result_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM mtc_results WHERE result_id = ?", (result_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete MTC #%d", result_id)
        raise
    if deleted:
        logger.info("Deleted MTC result #%d", result_id)
    return deleted


def list_results(
    *, academic_year: str | None = None,
    pupil_id: str | None = None,
    met_expected: bool | None = None,
    year_group: str | None = None,
) -> list[tuple[MTCResult, Pupil | None]]:
    init_db()
    if year_group and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    where: list[str] = []
    params: list[Any] = []
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    if met_expected is True:
        where.append(f"score >= {EXPECTED_THRESHOLD}")
    elif met_expected is False:
        where.append(f"score < {EXPECTED_THRESHOLD}")
    sql = "SELECT * FROM mtc_results"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, pupil_id"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_results failed")
        raise
    out: list[tuple[MTCResult, Pupil | None]] = []
    for r in rows:
        rec = _row(r)
        p = pupils_data.get_pupil(rec.pupil_id)
        if year_group and (p is None or p.year_group != year_group):
            continue
        out.append((rec, p))
    return out


def list_for_pupil(pupil_id: str) -> list[MTCResult]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM mtc_results WHERE pupil_id = ? "
                "ORDER BY academic_year DESC",
                (pupil_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_pupil(%s) failed", pupil_id)
        raise
    return [_row(r) for r in rows]


def year_summary(academic_year: str) -> dict[str, Any]:
    init_db()
    ay = (academic_year or "").strip()
    if not ay:
        raise ValidationError("Academic year is required")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT score FROM mtc_results WHERE academic_year = ?",
                (ay,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("year_summary(%s) failed", ay)
        raise
    scores = [r["score"] for r in rows]
    total = len(scores)
    met = sum(1 for s in scores if s >= EXPECTED_THRESHOLD)
    full = sum(1 for s in scores if s == MAX_SCORE)
    avg = (sum(scores) / total) if total else 0.0
    return {
        "academic_year": ay,
        "total": total,
        "met_expected": met,
        "below_expected": total - met,
        "met_pct": (met / total * 100.0) if total else 0.0,
        "full_marks": full,
        "full_marks_pct": (full / total * 100.0) if total else 0.0,
        "average_score": avg,
    }


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year FROM mtc_results "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]
