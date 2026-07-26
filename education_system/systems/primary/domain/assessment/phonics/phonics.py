"""Phonics tracking data layer for the Primary School System.

Tracks each pupil's current phonics phase (Letters and Sounds, phases
1-6) and a status indicating whether they are *working at* or *secure
in* that phase. The current state lives in ``pupil_phonics`` (one row
per pupil, created lazily) and every change is appended to a
``phonics_assessments`` history table.
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

PHASES: tuple[str, ...] = ("1", "2", "3", "4", "5", "6")
STATUSES: tuple[str, ...] = ("working", "secure")
PHASE_LABELS: dict[str, str] = {
    "1": "Phase 1 — Listening & sounds",
    "2": "Phase 2 — Single letter sounds",
    "3": "Phase 3 — Digraphs & trigraphs",
    "4": "Phase 4 — Adjacent consonants",
    "5": "Phase 5 — Alternative spellings",
    "6": "Phase 6 — Fluency & spelling rules",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupil_phonics (
    pupil_id        TEXT PRIMARY KEY,
    phase           TEXT NOT NULL,
    status          TEXT NOT NULL,
    last_assessed   TEXT,
    notes           TEXT,
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS phonics_assessments (
    assessment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    phase           TEXT NOT NULL,
    status          TEXT NOT NULL,
    assessed_on     TEXT NOT NULL,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_phonics_assess_pupil
    ON phonics_assessments(pupil_id, assessed_on DESC);
"""


@dataclass
class PhonicsRecord:
    pupil_id: str
    phase: str
    status: str
    last_assessed: str | None
    notes: str | None
    updated_at: str | None


@dataclass
class PhonicsAssessment:
    assessment_id: int
    pupil_id: str
    phase: str
    status: str
    assessed_on: str
    notes: str | None
    created_at: str | None


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
        logger.exception("Failed to initialise phonics tables")
        raise
    logger.info("Primary phonics tables ready")
    _DB_READY = True


def _row_record(r: sqlite3.Row) -> PhonicsRecord:
    return PhonicsRecord(
        pupil_id=r["pupil_id"],
        phase=r["phase"],
        status=r["status"],
        last_assessed=r["last_assessed"],
        notes=r["notes"],
        updated_at=r["updated_at"],
    )


def _row_assessment(r: sqlite3.Row) -> PhonicsAssessment:
    return PhonicsAssessment(
        assessment_id=r["assessment_id"],
        pupil_id=r["pupil_id"],
        phase=r["phase"],
        status=r["status"],
        assessed_on=r["assessed_on"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    phase = (data.get("phase") or "").strip()
    if not phase:
        raise ValidationError("Phase is required")
    if phase not in PHASES:
        raise ValidationError(
            f"Phase must be one of {', '.join(PHASES)}")
    out["phase"] = phase
    status = (data.get("status") or "").strip().lower()
    if not status:
        raise ValidationError("Status is required")
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    assessed_on = (data.get("assessed_on") or "").strip()
    if assessed_on and not _DOB_RE.match(assessed_on):
        raise ValidationError("Assessed-on date must be YYYY-MM-DD")
    out["assessed_on"] = assessed_on or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def get_record(pupil_id: str) -> PhonicsRecord | None:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM pupil_phonics WHERE pupil_id = ?",
                (pupil_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", pupil_id)
        raise
    return _row_record(r) if r else None


def record_assessment(pupil_id: str, data: dict[str, Any]) -> PhonicsRecord:
    """Record a phonics assessment for a pupil.

    Updates the pupil's current state to the new phase/status and
    appends an immutable row to ``phonics_assessments``.
    """
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    payload = _validate(data)
    assessed_on = payload["assessed_on"]
    try:
        with _connect() as conn:
            # Use provided date for history; current record stores it too.
            history_date = assessed_on or conn.execute(
                "SELECT date('now')"
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO phonics_assessments
                       (pupil_id, phase, status, assessed_on, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (pupil_id, payload["phase"], payload["status"],
                 history_date, payload["notes"]),
            )
            conn.execute(
                "INSERT OR IGNORE INTO pupil_phonics(pupil_id, phase, status) "
                "VALUES (?, ?, ?)",
                (pupil_id, payload["phase"], payload["status"]),
            )
            conn.execute(
                """UPDATE pupil_phonics SET
                       phase = ?, status = ?, last_assessed = ?,
                       notes = ?, updated_at = datetime('now')
                   WHERE pupil_id = ?""",
                (payload["phase"], payload["status"], history_date,
                 payload["notes"], pupil_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("record_assessment(%s) failed", pupil_id)
        raise
    rec = get_record(pupil_id)
    assert rec is not None
    logger.info("Phonics: pupil %s -> phase %s (%s)",
                pupil_id, rec.phase, rec.status)
    return rec


def list_history(pupil_id: str) -> list[PhonicsAssessment]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM phonics_assessments WHERE pupil_id = ? "
                "ORDER BY assessed_on DESC, assessment_id DESC",
                (pupil_id,),
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_history(%s) failed", pupil_id)
        raise
    return [_row_assessment(r) for r in rows]


def delete_assessment(assessment_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM phonics_assessments WHERE assessment_id = ?",
                (assessment_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("delete_assessment(%s) failed", assessment_id)
        raise
    if deleted:
        logger.info("Deleted phonics assessment #%d", assessment_id)
    return deleted


def clear_pupil(pupil_id: str) -> bool:
    """Remove a pupil's current phonics record (history is kept)."""
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM pupil_phonics WHERE pupil_id = ?",
                (pupil_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("clear_pupil(%s) failed", pupil_id)
        raise
    if deleted:
        logger.info("Cleared phonics record for pupil %s", pupil_id)
    return deleted


def list_records(
    *, year_group: str | None = None,
    phase: str | None = None,
    status: str | None = None,
) -> list[tuple[Pupil, PhonicsRecord | None]]:
    """Return [(Pupil, PhonicsRecord|None), ...] for matching pupils.

    Pupils with no record yet get ``None``. Filters are AND-combined.
    """
    init_db()
    if phase and phase not in PHASES:
        raise ValidationError(
            f"Phase filter must be one of {', '.join(PHASES)}")
    if status and status not in STATUSES:
        raise ValidationError(
            f"Status filter must be one of {', '.join(STATUSES)}")
    if year_group and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupil_phonics"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    by_id: dict[str, PhonicsRecord] = {
        r["pupil_id"]: _row_record(r) for r in rows
    }
    out: list[tuple[Pupil, PhonicsRecord | None]] = []
    for p in pupils_data.list_pupils():
        if year_group and p.year_group != year_group:
            continue
        rec = by_id.get(p.pupil_id)
        if phase and (rec is None or rec.phase != phase):
            continue
        if status and (rec is None or rec.status != status):
            continue
        out.append((p, rec))
    logger.debug(
        "phonics list_records(y=%s, p=%s, s=%s) -> %d row(s)",
        year_group, phase, status, len(out),
    )
    return out


def phase_summary() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT phase, COUNT(*) AS n FROM pupil_phonics GROUP BY phase"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("phonics phase_summary failed")
        raise
    counts = {ph: 0 for ph in PHASES}
    for r in rows:
        if r["phase"] in counts:
            counts[r["phase"]] = r["n"]
    return counts
