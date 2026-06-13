"""Reading levels data layer for the Primary School System.

Tracks each pupil's current reading book band (the UK colour-band
progression) and an indicative status of *working at* vs *secure in*
that band. The current state lives in ``pupil_reading_levels`` (one
row per pupil, created lazily) and every change is appended to a
``reading_level_assessments`` history table.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.primarysch_system.modules.domain.pupils import (
    pupils as pupils_data,
)
from education_system.primarysch_system.modules.domain.pupils.pupils import (
    Pupil, ValidationError, YEAR_GROUPS,
    _connect as _pupils_connect, _DOB_RE,
)

logger = logging.getLogger(__name__)

# Ordered colour-band progression (lowest -> highest) plus "Free Reader".
BANDS: tuple[str, ...] = (
    "Pink", "Red", "Yellow", "Blue", "Green",
    "Orange", "Turquoise", "Purple", "Gold", "White",
    "Lime", "Brown", "Grey", "Dark Blue", "Free Reader",
)
BAND_ORDER: dict[str, int] = {b: i for i, b in enumerate(BANDS)}

STATUSES: tuple[str, ...] = ("working", "secure")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupil_reading_levels (
    pupil_id        TEXT PRIMARY KEY,
    band            TEXT NOT NULL,
    status          TEXT NOT NULL,
    last_assessed   TEXT,
    book_title      TEXT,
    notes           TEXT,
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS reading_level_assessments (
    assessment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    band            TEXT NOT NULL,
    status          TEXT NOT NULL,
    assessed_on     TEXT NOT NULL,
    book_title      TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reading_assess_pupil
    ON reading_level_assessments(pupil_id, assessed_on DESC);
"""


@dataclass
class ReadingLevelRecord:
    pupil_id: str
    band: str
    status: str
    last_assessed: str | None
    book_title: str | None
    notes: str | None
    updated_at: str | None


@dataclass
class ReadingLevelAssessment:
    assessment_id: int
    pupil_id: str
    band: str
    status: str
    assessed_on: str
    book_title: str | None
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
        logger.exception("Failed to initialise reading-levels tables")
        raise
    logger.info("Primary reading-levels tables ready")
    _DB_READY = True


def _row_record(r: sqlite3.Row) -> ReadingLevelRecord:
    return ReadingLevelRecord(
        pupil_id=r["pupil_id"],
        band=r["band"],
        status=r["status"],
        last_assessed=r["last_assessed"],
        book_title=r["book_title"],
        notes=r["notes"],
        updated_at=r["updated_at"],
    )


def _row_assessment(r: sqlite3.Row) -> ReadingLevelAssessment:
    return ReadingLevelAssessment(
        assessment_id=r["assessment_id"],
        pupil_id=r["pupil_id"],
        band=r["band"],
        status=r["status"],
        assessed_on=r["assessed_on"],
        book_title=r["book_title"],
        notes=r["notes"],
        created_at=r["created_at"],
    )


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    band = (data.get("band") or "").strip()
    if not band:
        raise ValidationError("Band is required")
    if band not in BAND_ORDER:
        raise ValidationError(
            f"Band must be one of: {', '.join(BANDS)}")
    out["band"] = band
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
    out["book_title"] = (data.get("book_title") or "").strip() or None
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def get_record(pupil_id: str) -> ReadingLevelRecord | None:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM pupil_reading_levels WHERE pupil_id = ?",
                (pupil_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_record(%s) failed", pupil_id)
        raise
    return _row_record(r) if r else None


def record_assessment(pupil_id: str, data: dict[str, Any]) -> ReadingLevelRecord:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    payload = _validate(data)
    assessed_on = payload["assessed_on"]
    try:
        with _connect() as conn:
            history_date = assessed_on or conn.execute(
                "SELECT date('now')"
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO reading_level_assessments
                       (pupil_id, band, status, assessed_on,
                        book_title, notes)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (pupil_id, payload["band"], payload["status"],
                 history_date, payload["book_title"], payload["notes"]),
            )
            conn.execute(
                "INSERT OR IGNORE INTO pupil_reading_levels"
                "(pupil_id, band, status) VALUES (?, ?, ?)",
                (pupil_id, payload["band"], payload["status"]),
            )
            conn.execute(
                """UPDATE pupil_reading_levels SET
                       band = ?, status = ?, last_assessed = ?,
                       book_title = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE pupil_id = ?""",
                (payload["band"], payload["status"], history_date,
                 payload["book_title"], payload["notes"], pupil_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("record_assessment(%s) failed", pupil_id)
        raise
    rec = get_record(pupil_id)
    assert rec is not None
    logger.info("Reading level: pupil %s -> %s (%s)",
                pupil_id, rec.band, rec.status)
    return rec


def list_history(pupil_id: str) -> list[ReadingLevelAssessment]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reading_level_assessments WHERE pupil_id = ? "
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
                "DELETE FROM reading_level_assessments "
                "WHERE assessment_id = ?",
                (assessment_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("delete_assessment(%s) failed", assessment_id)
        raise
    if deleted:
        logger.info("Deleted reading-level assessment #%d", assessment_id)
    return deleted


def clear_pupil(pupil_id: str) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM pupil_reading_levels WHERE pupil_id = ?",
                (pupil_id,),
            )
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("clear_pupil(%s) failed", pupil_id)
        raise
    if deleted:
        logger.info("Cleared reading-level record for pupil %s", pupil_id)
    return deleted


def list_records(
    *, year_group: str | None = None,
    band: str | None = None,
    status: str | None = None,
) -> list[tuple[Pupil, ReadingLevelRecord | None]]:
    init_db()
    if band and band not in BAND_ORDER:
        raise ValidationError(
            f"Band filter must be one of: {', '.join(BANDS)}")
    if status and status not in STATUSES:
        raise ValidationError(
            f"Status filter must be one of {', '.join(STATUSES)}")
    if year_group and year_group not in YEAR_GROUPS:
        raise ValidationError(
            f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupil_reading_levels"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("list_records failed")
        raise
    by_id: dict[str, ReadingLevelRecord] = {
        r["pupil_id"]: _row_record(r) for r in rows
    }
    out: list[tuple[Pupil, ReadingLevelRecord | None]] = []
    for p in pupils_data.list_pupils():
        if year_group and p.year_group != year_group:
            continue
        rec = by_id.get(p.pupil_id)
        if band and (rec is None or rec.band != band):
            continue
        if status and (rec is None or rec.status != status):
            continue
        out.append((p, rec))
    logger.debug(
        "reading_levels list_records(y=%s, b=%s, s=%s) -> %d row(s)",
        year_group, band, status, len(out),
    )
    return out


def band_summary() -> dict[str, int]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT band, COUNT(*) AS n FROM pupil_reading_levels "
                "GROUP BY band"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("reading_levels band_summary failed")
        raise
    counts = {b: 0 for b in BANDS}
    for r in rows:
        if r["band"] in counts:
            counts[r["band"]] = r["n"]
    return counts
