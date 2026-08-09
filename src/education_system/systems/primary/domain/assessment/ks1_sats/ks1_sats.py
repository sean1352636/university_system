"""KS1 SATs data layer (Year 2).

One row per (pupil, academic_year, subject). Subjects assessed at end
of Key Stage 1 are Reading, Maths, and (optionally) English Grammar,
Punctuation & Spelling (EGPS). Each row carries an optional scaled
score (the DfE range is roughly 85-115) and an outcome marker:

    BLW — below expected standard
    PKS — pre-key-stage / working below the standard
    WTS — working towards expected standard
    EXS — expected standard
    GDS — greater depth / working at greater depth
    NS  — not submitted / absent
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

SUBJECTS: tuple[str, ...] = ("Reading", "Maths", "EGPS")
OUTCOMES: tuple[str, ...] = ("BLW", "PKS", "WTS", "EXS", "GDS", "NS")
OUTCOME_LABELS: dict[str, str] = {
    "BLW": "Below expected standard",
    "PKS": "Pre-key-stage standard",
    "WTS": "Working towards expected standard",
    "EXS": "Expected standard",
    "GDS": "Greater depth standard",
    "NS":  "Not submitted / absent",
}
# Scaled score range. Below 85 / above 115 are unusual and may indicate
# data-entry error; we accept the widened range but warn via validation.
SCALED_SCORE_MIN = 60
SCALED_SCORE_MAX = 130
EXPECTED_SCALED = 100

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ks1_sats_results (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    subject         TEXT NOT NULL,
    scaled_score    INTEGER,
    outcome         TEXT NOT NULL,
    assessed_on     TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(pupil_id, academic_year, subject),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ks1_pupil    ON ks1_sats_results(pupil_id);
CREATE INDEX IF NOT EXISTS idx_ks1_year     ON ks1_sats_results(academic_year);
CREATE INDEX IF NOT EXISTS idx_ks1_subject  ON ks1_sats_results(subject);
"""


@dataclass
class KS1Result:
    result_id: int
    pupil_id: str
    academic_year: str
    subject: str
    scaled_score: int | None
    outcome: str
    assessed_on: str | None
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def at_or_above_expected(self) -> bool:
        return self.outcome in ("EXS", "GDS")


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
        logger.exception("Failed to initialise ks1_sats_results table")
        raise
    logger.info("Primary ks1_sats_results table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> KS1Result:
    return KS1Result(
        result_id=r["result_id"],
        pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        subject=r["subject"],
        scaled_score=r["scaled_score"],
        outcome=r["outcome"],
        assessed_on=r["assessed_on"],
        notes=r["notes"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def suggest_outcome(scaled_score: int | None) -> str | None:
    """Derive a likely outcome from a scaled score, or None if no input."""
    if scaled_score is None:
        return None
    if scaled_score < 85:
        return "WTS"
    if scaled_score < 100:
        return "WTS"
    if scaled_score < 110:
        return "EXS"
    return "GDS"


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
    subj = (data.get("subject") or "").strip()
    if not subj:
        raise ValidationError("Subject is required")
    if subj not in SUBJECTS:
        raise ValidationError(
            f"Subject must be one of {', '.join(SUBJECTS)}")
    out["subject"] = subj
    score_raw = data.get("scaled_score")
    if score_raw in (None, ""):
        out["scaled_score"] = None
    else:
        try:
            score = int(score_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Scaled score must be an integer") from e
        if not (SCALED_SCORE_MIN <= score <= SCALED_SCORE_MAX):
            raise ValidationError(
                f"Scaled score must be between {SCALED_SCORE_MIN} and "
                f"{SCALED_SCORE_MAX}")
        out["scaled_score"] = score
    outcome = (data.get("outcome") or "").strip().upper()
    if not outcome:
        raise ValidationError("Outcome is required")
    if outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of {', '.join(OUTCOMES)}")
    out["outcome"] = outcome
    assessed_on = (data.get("assessed_on") or "").strip()
    if assessed_on and not _DOB_RE.match(assessed_on):
        raise ValidationError("Assessed-on date must be YYYY-MM-DD")
    out["assessed_on"] = assessed_on or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> KS1Result:
    init_db()
    payload = _validate(data)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT result_id FROM ks1_sats_results "
                "WHERE pupil_id = ? AND academic_year = ? AND subject = ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A KS1 result for pupil {payload['pupil_id']} in "
                    f"{payload['academic_year']} {payload['subject']} "
                    f"already exists (#{dup['result_id']})")
            cur = conn.execute(
                """INSERT INTO ks1_sats_results
                       (pupil_id, academic_year, subject, scaled_score,
                        outcome, assessed_on, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"], payload["scaled_score"],
                 payload["outcome"], payload["assessed_on"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create KS1 SATs result")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created KS1 result #%d (pupil %s, %s %s, %s, score=%s)",
                rec.result_id, rec.pupil_id, rec.academic_year,
                rec.subject, rec.outcome, rec.scaled_score)
    return rec


def get(result_id: int) -> KS1Result | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM ks1_sats_results WHERE result_id = ?",
                (result_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get KS1(%s) failed", result_id)
        raise
    return _row(r) if r else None


def update(result_id: int, data: dict[str, Any]) -> KS1Result:
    init_db()
    existing = get(result_id)
    if existing is None:
        raise ValidationError(f"No KS1 SATs result #{result_id}")
    merged = {
        "pupil_id":      data.get("pupil_id", existing.pupil_id),
        "academic_year": data.get("academic_year", existing.academic_year),
        "subject":       data.get("subject", existing.subject),
        "scaled_score":  data.get("scaled_score", existing.scaled_score),
        "outcome":       data.get("outcome", existing.outcome),
        "assessed_on":   data.get("assessed_on", existing.assessed_on),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT result_id FROM ks1_sats_results "
                "WHERE pupil_id = ? AND academic_year = ? AND subject = ? "
                "AND result_id <> ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"], result_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another KS1 result for that pupil / year / subject "
                    f"already exists (#{dup['result_id']})")
            conn.execute(
                """UPDATE ks1_sats_results SET
                       pupil_id = ?, academic_year = ?, subject = ?,
                       scaled_score = ?, outcome = ?, assessed_on = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE result_id = ?""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"], payload["scaled_score"],
                 payload["outcome"], payload["assessed_on"],
                 payload["notes"], result_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update KS1 #%d", result_id)
        raise
    rec = get(result_id)
    assert rec is not None
    logger.info("Updated KS1 result #%d", result_id)
    return rec


def delete(result_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM ks1_sats_results WHERE result_id = ?",
                (result_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete KS1 #%d", result_id)
        raise
    if deleted:
        logger.info("Deleted KS1 result #%d", result_id)
    return deleted


def list_results(
    *, academic_year: str | None = None,
    subject: str | None = None,
    outcome: str | None = None,
    pupil_id: str | None = None,
    year_group: str | None = None,
) -> list[tuple[KS1Result, Pupil | None]]:
    init_db()
    if subject is not None and subject not in SUBJECTS:
        raise ValidationError(
            f"Subject filter must be one of {', '.join(SUBJECTS)}")
    if outcome is not None and outcome not in OUTCOMES:
        raise ValidationError(
            f"Outcome filter must be one of {', '.join(OUTCOMES)}")
    if year_group is not None and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    where: list[str] = []
    params: list[Any] = []
    if academic_year:
        where.append("academic_year = ?")
        params.append(academic_year.strip())
    if subject:
        where.append("subject = ?")
        params.append(subject)
    if outcome:
        where.append("outcome = ?")
        params.append(outcome)
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    sql = "SELECT * FROM ks1_sats_results"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, subject, pupil_id"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_results failed")
        raise
    out: list[tuple[KS1Result, Pupil | None]] = []
    for r in rows:
        rec = _row(r)
        p = pupils_data.get_pupil(rec.pupil_id)
        if year_group and (p is None or p.year_group != year_group):
            continue
        out.append((rec, p))
    return out


def list_for_pupil(pupil_id: str) -> list[KS1Result]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ks1_sats_results WHERE pupil_id = ? "
                "ORDER BY academic_year DESC, subject",
                (pupil_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_for_pupil(%s) failed", pupil_id)
        raise
    return [_row(r) for r in rows]


def summary(
    *, academic_year: str | None = None,
    subject: str | None = None,
) -> dict[str, Any]:
    init_db()
    rows = list_results(academic_year=academic_year, subject=subject)
    total = len(rows)
    by_outcome = {o: 0 for o in OUTCOMES}
    scores: list[int] = []
    for rec, _p in rows:
        by_outcome[rec.outcome] = by_outcome.get(rec.outcome, 0) + 1
        if rec.scaled_score is not None:
            scores.append(rec.scaled_score)
    at_or_above = by_outcome["EXS"] + by_outcome["GDS"]
    return {
        "total": total,
        "by_outcome": by_outcome,
        "at_or_above_exs": at_or_above,
        "at_or_above_exs_pct": (at_or_above / total * 100.0) if total else 0.0,
        "average_scaled": (sum(scores) / len(scores)) if scores else None,
        "scaled_count": len(scores),
    }


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year FROM ks1_sats_results "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]
