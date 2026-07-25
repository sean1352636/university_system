"""Target setting data layer.

One row per (pupil, academic_year, subject). Tracks an end-of-year
attainment target — the grade the school/teacher expects the pupil to
reach by the end of the year — along with optional review date and a
status that's updated once the target is reviewed.
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

# Re-use the primary attainment grade vocabulary.
TARGET_GRADES: tuple[str, ...] = ("BLW", "WTS", "EXS", "GDS")
TARGET_GRADE_LABELS: dict[str, str] = {
    "BLW": "Below — working below expected standard",
    "WTS": "Working Towards expected standard",
    "EXS": "Expected Standard",
    "GDS": "Greater Depth Standard",
}
GRADE_RANK: dict[str, int] = {"BLW": 1, "WTS": 2, "EXS": 3, "GDS": 4}

STATUSES: tuple[str, ...] = ("open", "met", "not_met", "exceeded", "withdrawn")
STATUS_LABELS: dict[str, str] = {
    "open":      "Open — not yet reviewed",
    "met":       "Met — pupil reached the target",
    "not_met":   "Not met — pupil fell short",
    "exceeded":  "Exceeded — pupil surpassed the target",
    "withdrawn": "Withdrawn — target retired",
}

_ACADEMIC_YEAR_RE = re.compile(r"^\d{4}(-\d{2}|-\d{4})?$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pupil_targets (
    target_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    subject         TEXT NOT NULL,
    target_grade    TEXT NOT NULL,
    target_score    REAL,
    set_on          TEXT,
    review_date     TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(pupil_id, academic_year, subject),
    FOREIGN KEY(pupil_id) REFERENCES pupils(pupil_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_targets_pupil   ON pupil_targets(pupil_id);
CREATE INDEX IF NOT EXISTS idx_targets_year    ON pupil_targets(academic_year);
CREATE INDEX IF NOT EXISTS idx_targets_status  ON pupil_targets(status);
"""


@dataclass
class Target:
    target_id: int
    pupil_id: str
    academic_year: str
    subject: str
    target_grade: str
    target_score: float | None
    set_on: str | None
    review_date: str | None
    status: str
    notes: str | None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status == "open"


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
        logger.exception("Failed to initialise pupil_targets table")
        raise
    logger.info("Primary pupil_targets table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Target:
    return Target(
        target_id=r["target_id"],
        pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        subject=r["subject"],
        target_grade=r["target_grade"],
        target_score=r["target_score"],
        set_on=r["set_on"],
        review_date=r["review_date"],
        status=r["status"],
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
    subj = (data.get("subject") or "").strip()
    if not subj:
        raise ValidationError("Subject is required")
    if len(subj) > 64:
        raise ValidationError("Subject must be 64 characters or fewer")
    out["subject"] = subj
    grade = (data.get("target_grade") or "").strip().upper()
    if not grade:
        raise ValidationError("Target grade is required")
    if grade not in TARGET_GRADES:
        raise ValidationError(
            f"Target grade must be one of {', '.join(TARGET_GRADES)}")
    out["target_grade"] = grade
    score_raw = data.get("target_score")
    if score_raw in (None, ""):
        out["target_score"] = None
    else:
        try:
            score = float(score_raw)
        except (TypeError, ValueError) as e:
            raise ValidationError("Target score must be a number") from e
        if not (0.0 <= score <= 130.0):
            raise ValidationError("Target score must be between 0 and 130")
        out["target_score"] = score
    set_on = (data.get("set_on") or "").strip()
    if set_on and not _DOB_RE.match(set_on):
        raise ValidationError("Set-on date must be YYYY-MM-DD")
    out["set_on"] = set_on or None
    review_date = (data.get("review_date") or "").strip()
    if review_date and not _DOB_RE.match(review_date):
        raise ValidationError("Review date must be YYYY-MM-DD")
    if set_on and review_date and review_date < set_on:
        raise ValidationError("Review date cannot be before the set-on date")
    out["review_date"] = review_date or None
    status = (data.get("status") or "open").strip().lower() or "open"
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    out["status"] = status
    out["notes"] = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Target:
    init_db()
    payload = _validate(data)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT target_id FROM pupil_targets "
                "WHERE pupil_id = ? AND academic_year = ? AND subject = ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"]),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"A target for pupil {payload['pupil_id']} in "
                    f"{payload['academic_year']} {payload['subject']!r} "
                    f"already exists (#{dup['target_id']})")
            cur = conn.execute(
                """INSERT INTO pupil_targets
                       (pupil_id, academic_year, subject, target_grade,
                        target_score, set_on, review_date, status, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"], payload["target_grade"],
                 payload["target_score"], payload["set_on"],
                 payload["review_date"], payload["status"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create target")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info("Created target #%d (pupil %s, %s %s -> %s)",
                rec.target_id, rec.pupil_id, rec.academic_year,
                rec.subject, rec.target_grade)
    return rec


def get(target_id: int) -> Target | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM pupil_targets WHERE target_id = ?",
                (target_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get target(%s) failed", target_id)
        raise
    return _row(r) if r else None


def update(target_id: int, data: dict[str, Any]) -> Target:
    init_db()
    existing = get(target_id)
    if existing is None:
        raise ValidationError(f"No target #{target_id}")
    merged = {
        "pupil_id":      data.get("pupil_id", existing.pupil_id),
        "academic_year": data.get("academic_year", existing.academic_year),
        "subject":       data.get("subject", existing.subject),
        "target_grade":  data.get("target_grade", existing.target_grade),
        "target_score":  data.get("target_score", existing.target_score),
        "set_on":        data.get("set_on", existing.set_on),
        "review_date":   data.get("review_date", existing.review_date),
        "status":        data.get("status", existing.status),
        "notes":         data.get("notes", existing.notes),
    }
    payload = _validate(merged)
    if pupils_data.get_pupil(payload["pupil_id"]) is None:
        raise ValidationError(f"No pupil with id {payload['pupil_id']}")
    try:
        with _connect() as conn:
            dup = conn.execute(
                "SELECT target_id FROM pupil_targets "
                "WHERE pupil_id = ? AND academic_year = ? AND subject = ? "
                "AND target_id <> ?",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"], target_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    f"Another target for that pupil / year / subject "
                    f"already exists (#{dup['target_id']})")
            conn.execute(
                """UPDATE pupil_targets SET
                       pupil_id = ?, academic_year = ?, subject = ?,
                       target_grade = ?, target_score = ?, set_on = ?,
                       review_date = ?, status = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE target_id = ?""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["subject"], payload["target_grade"],
                 payload["target_score"], payload["set_on"],
                 payload["review_date"], payload["status"],
                 payload["notes"], target_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update target #%d", target_id)
        raise
    rec = get(target_id)
    assert rec is not None
    logger.info("Updated target #%d", target_id)
    return rec


def set_status(target_id: int, new_status: str) -> Target:
    init_db()
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(STATUSES)}")
    existing = get(target_id)
    if existing is None:
        raise ValidationError(f"No target #{target_id}")
    try:
        with _connect() as conn:
            conn.execute(
                "UPDATE pupil_targets SET status = ?, "
                "updated_at = datetime('now') WHERE target_id = ?",
                (new_status, target_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to set_status target #%d", target_id)
        raise
    logger.info("Target #%d %s -> %s",
                target_id, existing.status, new_status)
    rec = get(target_id)
    assert rec is not None
    return rec


def delete(target_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM pupil_targets WHERE target_id = ?",
                (target_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception("Failed to delete target #%d", target_id)
        raise
    if deleted:
        logger.info("Deleted target #%d", target_id)
    return deleted


def list_targets(
    *, academic_year: str | None = None,
    subject: str | None = None,
    status: str | None = None,
    pupil_id: str | None = None,
    year_group: str | None = None,
) -> list[tuple[Target, Pupil | None]]:
    init_db()
    if status is not None and status not in STATUSES:
        raise ValidationError(
            f"Status filter must be one of {', '.join(STATUSES)}")
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
        params.append(subject.strip())
    if status:
        where.append("status = ?")
        params.append(status)
    if pupil_id:
        where.append("pupil_id = ?")
        params.append(pupil_id.strip())
    sql = "SELECT * FROM pupil_targets"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY academic_year DESC, subject, pupil_id"
    try:
        with _connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.Error:
        logger.exception("list_targets failed")
        raise
    out: list[tuple[Target, Pupil | None]] = []
    for r in rows:
        rec = _row(r)
        p = pupils_data.get_pupil(rec.pupil_id)
        if year_group and (p is None or p.year_group != year_group):
            continue
        out.append((rec, p))
    return out


def list_for_pupil(pupil_id: str) -> list[Target]:
    init_db()
    if pupils_data.get_pupil(pupil_id) is None:
        raise ValidationError(f"No pupil with id {pupil_id}")
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pupil_targets WHERE pupil_id = ? "
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
    rows = list_targets(academic_year=academic_year, subject=subject)
    total = len(rows)
    by_status = {s: 0 for s in STATUSES}
    by_grade = {g: 0 for g in TARGET_GRADES}
    for rec, _p in rows:
        by_status[rec.status] = by_status.get(rec.status, 0) + 1
        by_grade[rec.target_grade] = by_grade.get(rec.target_grade, 0) + 1
    met_or_exceeded = by_status["met"] + by_status["exceeded"]
    return {
        "total": total,
        "by_status": by_status,
        "by_grade": by_grade,
        "met_or_exceeded": met_or_exceeded,
        "met_or_exceeded_pct": (met_or_exceeded / total * 100.0) if total else 0.0,
    }


def known_years() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT academic_year FROM pupil_targets "
                "ORDER BY academic_year DESC"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_years failed")
        raise
    return [r["academic_year"] for r in rows]


def known_subjects() -> list[str]:
    init_db()
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT subject FROM pupil_targets "
                "ORDER BY subject COLLATE NOCASE"
            ).fetchall()
    except sqlite3.Error:
        logger.exception("known_subjects failed")
        raise
    return [r["subject"] for r in rows]
