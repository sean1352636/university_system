"""GCSE exam-entries data layer for the Secondary School System.

One row per (pupil, subject) registration with an exam board. Captures
the spec code, tier, candidate number, entry status, fee, and notes.
Status workflow: Provisional → Final → Withdrawn.
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

EXAM_BOARDS: tuple[str, ...] = (
    "AQA", "Edexcel", "OCR", "WJEC", "Eduqas", "CIE", "Other")
DEFAULT_BOARD: str = "AQA"

TIERS: tuple[str, ...] = ("Foundation", "Higher", "N/A")
DEFAULT_TIER: str = "N/A"

ENTRY_STATUSES: tuple[str, ...] = (
    "Provisional", "Final", "Withdrawn", "Cancelled")
DEFAULT_ENTRY_STATUS: str = "Provisional"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SPEC_RE = re.compile(r"^[A-Za-z0-9/\- ]{2,16}$")
_CAND_RE = re.compile(r"^[A-Za-z0-9\- ]{1,16}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_entries (
    entry_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           TEXT NOT NULL,
    subject_id         INTEGER NOT NULL,
    exam_board         TEXT NOT NULL DEFAULT 'AQA',
    spec_code          TEXT,
    tier               TEXT NOT NULL DEFAULT 'N/A',
    candidate_number   TEXT,
    entry_status       TEXT NOT NULL DEFAULT 'Provisional',
    entry_date         TEXT NOT NULL DEFAULT (date('now')),
    fee                REAL,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE (pupil_id, subject_id),
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE INDEX IF NOT EXISTS idx_ee_pupil ON exam_entries(pupil_id);
CREATE INDEX IF NOT EXISTS idx_ee_subject ON exam_entries(subject_id);
CREATE INDEX IF NOT EXISTS idx_ee_board ON exam_entries(exam_board);
"""


@dataclass
class ExamEntry:
    entry_id: int
    pupil_id: str
    subject_id: int
    exam_board: str
    spec_code: str | None
    tier: str
    candidate_number: str | None
    entry_status: str
    entry_date: str
    fee: float | None
    notes: str | None
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


_DB_READY = False


def _connect() -> sqlite3.Connection:
    return _pupils_connect()


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    from education_system.secondarysch_system.modules.domain.academics.subjects import (
        subjects as subjects_data,
    )
    subjects_data.init_db()
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception("Failed to initialise exam_entries table")
        raise
    logger.info("Secondary exam_entries table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> ExamEntry:
    keys = r.keys()
    return ExamEntry(
        entry_id=r["entry_id"], pupil_id=r["pupil_id"],
        subject_id=r["subject_id"], exam_board=r["exam_board"],
        spec_code=r["spec_code"], tier=r["tier"],
        candidate_number=r["candidate_number"],
        entry_status=r["entry_status"], entry_date=r["entry_date"],
        fee=r["fee"], notes=r["notes"],
        subject_code=r["subject_code"] if "subject_code" in keys else None,
        subject_name=r["subject_name"] if "subject_name" in keys else None,
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
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
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.secondarysch_system.modules.domain.pupils.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    sid_raw = data.get("subject_id")
    if sid_raw in (None, ""):
        raise ValidationError("Subject is required")
    try:
        out["subject_id"] = int(sid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Subject ID must be a number") from None
    from education_system.secondarysch_system.modules.domain.academics.subjects import (
        subjects as subjects_data,
    )
    if subjects_data.get(out["subject_id"]) is None:
        raise ValidationError(f"No subject #{out['subject_id']}")

    board = (data.get("exam_board") or DEFAULT_BOARD).strip()
    if board not in EXAM_BOARDS:
        raise ValidationError(
            f"Exam board must be one of {', '.join(EXAM_BOARDS)}")
    out["exam_board"] = board

    spec = (data.get("spec_code") or "").strip()
    if spec:
        if not _SPEC_RE.match(spec):
            raise ValidationError(
                "Spec code must be 2–16 chars (letters/digits/-/space)")
    out["spec_code"] = spec or None

    tier = (data.get("tier") or DEFAULT_TIER).strip()
    if tier not in TIERS:
        raise ValidationError(
            f"Tier must be one of {', '.join(TIERS)}")
    out["tier"] = tier

    cand = (data.get("candidate_number") or "").strip()
    if cand:
        if not _CAND_RE.match(cand):
            raise ValidationError(
                "Candidate number must be 1–16 alphanumeric chars")
    out["candidate_number"] = cand or None

    status = (data.get("entry_status") or DEFAULT_ENTRY_STATUS).strip()
    if status not in ENTRY_STATUSES:
        raise ValidationError(
            f"Entry status must be one of "
            f"{', '.join(ENTRY_STATUSES)}")
    out["entry_status"] = status

    out["entry_date"] = _validate_date(data.get("entry_date"),
                                         "Entry date")

    fee = data.get("fee")
    if fee in (None, "") or (isinstance(fee, str) and not fee.strip()):
        out["fee"] = None
    else:
        try:
            v = float(fee)
        except (TypeError, ValueError):
            raise ValidationError("Fee must be a number") from None
        if v < 0 or v > 10000:
            raise ValidationError("Fee must be between 0 and 10000")
        out["fee"] = v

    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def upsert(data: dict[str, Any]) -> ExamEntry:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            row = conn.execute(
                "SELECT entry_id FROM exam_entries "
                "WHERE pupil_id = ? AND subject_id = ?",
                (payload["pupil_id"], payload["subject_id"]),
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE exam_entries SET
                           exam_board = ?, spec_code = ?, tier = ?,
                           candidate_number = ?, entry_status = ?,
                           entry_date = ?, fee = ?, notes = ?,
                           updated_at = datetime('now')
                       WHERE entry_id = ?""",
                    (payload["exam_board"], payload["spec_code"],
                     payload["tier"], payload["candidate_number"],
                     payload["entry_status"], payload["entry_date"],
                     payload["fee"], payload["notes"], row["entry_id"]),
                )
                eid = row["entry_id"]
                action = "updated"
            else:
                cur = conn.execute(
                    """INSERT INTO exam_entries
                           (pupil_id, subject_id, exam_board,
                            spec_code, tier, candidate_number,
                            entry_status, entry_date, fee, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (payload["pupil_id"], payload["subject_id"],
                     payload["exam_board"], payload["spec_code"],
                     payload["tier"], payload["candidate_number"],
                     payload["entry_status"], payload["entry_date"],
                     payload["fee"], payload["notes"]),
                )
                eid = cur.lastrowid
                action = "inserted"
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to upsert exam entry for pupil %s subject %d",
            payload["pupil_id"], payload["subject_id"])
        raise
    logger.info(
        "Exam entry %s: pupil=%s subject=#%d board=%s tier=%s status=%s",
        action, payload["pupil_id"], payload["subject_id"],
        payload["exam_board"], payload["tier"],
        payload["entry_status"])
    rec = get(eid)
    assert rec is not None
    return rec


def get(entry_id: int) -> ExamEntry | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT e.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM exam_entries e
                   LEFT JOIN subjects s ON s.subject_id = e.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = e.pupil_id
                   WHERE e.entry_id = ?""",
                (entry_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", entry_id)
        raise
    return _row(r) if r else None


def get_for(pupil_id: str, subject_id: int) -> ExamEntry | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT e.*, s.code AS subject_code,
                          s.name AS subject_name,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM exam_entries e
                   LEFT JOIN subjects s ON s.subject_id = e.subject_id
                   LEFT JOIN pupils p ON p.pupil_id = e.pupil_id
                   WHERE e.pupil_id = ? AND e.subject_id = ?""",
                ((pupil_id or "").strip(), int(subject_id)),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_for(%s, %s) failed", pupil_id, subject_id)
        raise
    return _row(r) if r else None


def list_entries(*, year_group: str | None = None,
                 subject_id: int | None = None,
                 exam_board: str | None = None,
                 entry_status: str | None = None,
                 tier: str | None = None,
                 pupil_id: str | None = None) -> list[ExamEntry]:
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
        where.append("e.subject_id = ?")
        params.append(int(subject_id))
    if exam_board:
        if exam_board not in EXAM_BOARDS:
            raise ValidationError(
                f"Board filter must be one of {', '.join(EXAM_BOARDS)}")
        where.append("e.exam_board = ?")
        params.append(exam_board)
    if entry_status:
        if entry_status not in ENTRY_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(ENTRY_STATUSES)}")
        where.append("e.entry_status = ?")
        params.append(entry_status)
    if tier:
        if tier not in TIERS:
            raise ValidationError(
                f"Tier filter must be one of {', '.join(TIERS)}")
        where.append("e.tier = ?")
        params.append(tier)
    if pupil_id:
        where.append("e.pupil_id = ?")
        params.append(pupil_id.strip())
    sql = ("""SELECT e.*, s.code AS subject_code,
                     s.name AS subject_name,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM exam_entries e
              LEFT JOIN subjects s ON s.subject_id = e.subject_id
              LEFT JOIN pupils p ON p.pupil_id = e.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.year_group, p.last_name, s.name"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_entries failed")
        raise


def set_status(entry_id: int, new_status: str) -> ExamEntry:
    init_db()
    if new_status not in ENTRY_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(ENTRY_STATUSES)}")
    existing = get(entry_id)
    if existing is None:
        raise ValidationError(f"No exam entry #{entry_id}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE exam_entries SET entry_status = ?, "
                "updated_at = datetime('now') WHERE entry_id = ?",
                (new_status, entry_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to set status for entry #%d", entry_id)
        raise
    rec = get(entry_id)
    assert rec is not None
    logger.info("Exam entry #%d status %s -> %s",
                entry_id, existing.entry_status, new_status)
    return rec


def delete(entry_id: int) -> bool:
    init_db()
    existing = get(entry_id)
    if existing is None:
        return False
    # Block delete if a final result references this entry.
    try:
        with _connect() as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            if "exam_results" in tables:
                row = conn.execute(
                    "SELECT COUNT(*) FROM exam_results WHERE entry_id = ?",
                    (entry_id,),
                ).fetchone()
                if row and row[0] > 0:
                    raise ValidationError(
                        f"Entry #{entry_id} has {row[0]} linked result(s) "
                        f"— delete those first or withdraw the entry")
            cur = conn.execute(
                "DELETE FROM exam_entries WHERE entry_id = ?",
                (entry_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete exam entry #%d", entry_id)
        raise
    if deleted:
        logger.info("Deleted exam entry #%d (pupil %s subject #%d)",
                    entry_id, existing.pupil_id, existing.subject_id)
    return deleted


def cohort_summary(*, year_group: str | None = None) -> dict[str, Any]:
    rows = list_entries(year_group=year_group)
    return {
        "total":      len(rows),
        "by_status":  dict(Counter(r.entry_status for r in rows)),
        "by_board":   dict(Counter(r.exam_board for r in rows)),
        "by_tier":    dict(Counter(r.tier for r in rows)),
        "total_fees": round(sum((r.fee or 0) for r in rows), 2),
    }
