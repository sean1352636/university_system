"""Attendance-concern case data layer for the Secondary School System.

One row per pupil per concern episode: who is on the PA (persistent
absence) watch-list, what their attendance %, threshold, intervention,
status workflow (Open → Monitoring → Improving → Closed → Escalated).
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
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

CONCERN_STATUSES: tuple[str, ...] = (
    "Open", "Monitoring", "Improving", "Closed", "Escalated")
DEFAULT_STATUS: str = "Open";

CONCERN_LEVELS: tuple[str, ...] = (
    "Low (90-94%)", "Moderate (85-89%)", "High (80-84%)",
    "Severe (<80%)", "PA threshold (<90%)")
DEFAULT_LEVEL: str = "PA threshold (<90%)"

CONCERN_TYPES: tuple[str, ...] = (
    "Persistent absence", "Severe absence", "Unauthorised pattern",
    "Lateness pattern", "Medical", "Emotional/Anxiety",
    "Family/Domestic", "Bereavement", "Other")
DEFAULT_TYPE: str = "Persistent absence"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AY_RE   = re.compile(r"^\d{4}/\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_concerns (
    concern_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    academic_year   TEXT NOT NULL,
    concern_type    TEXT NOT NULL DEFAULT 'Persistent absence',
    level           TEXT NOT NULL DEFAULT 'PA threshold (<90%)',
    attendance_pct  REAL,
    threshold_pct   REAL NOT NULL DEFAULT 90.0,
    opened_date     TEXT NOT NULL DEFAULT (date('now')),
    next_review_date TEXT,
    closed_date     TEXT,
    status          TEXT NOT NULL DEFAULT 'Open',
    key_worker      TEXT,
    intervention    TEXT,
    parent_contact  TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ac_pupil
    ON attendance_concerns(pupil_id);
CREATE INDEX IF NOT EXISTS idx_ac_status
    ON attendance_concerns(status);
CREATE INDEX IF NOT EXISTS idx_ac_year
    ON attendance_concerns(academic_year);
"""


@dataclass
class Concern:
    concern_id: int
    pupil_id: str
    academic_year: str
    concern_type: str
    level: str
    attendance_pct: float | None
    threshold_pct: float
    opened_date: str
    next_review_date: str | None
    closed_date: str | None
    status: str
    key_worker: str | None
    intervention: str | None
    parent_contact: str | None
    notes: str | None
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
    try:
        with _connect() as conn:
            conn.executescript(_SCHEMA)
    except sqlite3.Error:
        logger.exception(
            "Failed to initialise attendance_concerns tables")
        raise
    logger.info("Secondary attendance_concerns tables ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Concern:
    keys = r.keys()
    return Concern(
        concern_id=r["concern_id"], pupil_id=r["pupil_id"],
        academic_year=r["academic_year"],
        concern_type=r["concern_type"], level=r["level"],
        attendance_pct=r["attendance_pct"],
        threshold_pct=r["threshold_pct"],
        opened_date=r["opened_date"],
        next_review_date=r["next_review_date"],
        closed_date=r["closed_date"], status=r["status"],
        key_worker=r["key_worker"],
        intervention=r["intervention"],
        parent_contact=r["parent_contact"],
        notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            return _dt.date.today().isoformat()
        return None
    s = str(value).strip()
    if not _DATE_RE.match(s):
        raise ValidationError(f"{label} must be YYYY-MM-DD")
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} is not a real date") from None
    return s


def _validate_pct(value: Any, label: str, *,
                   required: bool = False,
                   default: float | None = None) -> float | None:
    if value in (None, "") or (isinstance(value, str)
                                  and not value.strip()):
        if required:
            if default is not None:
                return default
            raise ValidationError(f"{label} is required")
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{label} must be a number") from None
    if f < 0 or f > 100:
        raise ValidationError(
            f"{label} must be between 0 and 100")
    return round(f, 2)


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

    ay = (data.get("academic_year") or "").strip()
    if not ay:
        raise ValidationError(
            "Academic year is required (e.g. 2025/26)")
    if not _AY_RE.match(ay):
        raise ValidationError(
            "Academic year must be in form YYYY/YY (e.g. 2025/26)")
    out["academic_year"] = ay

    ctype = (data.get("concern_type") or DEFAULT_TYPE).strip()
    if ctype not in CONCERN_TYPES:
        raise ValidationError(
            f"Concern type must be one of {', '.join(CONCERN_TYPES)}")
    out["concern_type"] = ctype

    level = (data.get("level") or DEFAULT_LEVEL).strip()
    if level not in CONCERN_LEVELS:
        raise ValidationError(
            f"Level must be one of {', '.join(CONCERN_LEVELS)}")
    out["level"] = level

    out["attendance_pct"] = _validate_pct(
        data.get("attendance_pct"), "Attendance %", required=False)
    out["threshold_pct"]  = _validate_pct(
        data.get("threshold_pct"), "Threshold %",
        required=True, default=90.0)

    out["opened_date"]      = _validate_date(
        data.get("opened_date"), "Opened date")
    out["next_review_date"] = _validate_date(
        data.get("next_review_date"), "Next review date",
        required=False)
    out["closed_date"]      = _validate_date(
        data.get("closed_date"), "Closed date", required=False)

    if (out["next_review_date"]
            and out["next_review_date"] < out["opened_date"]):
        raise ValidationError(
            "Next review date cannot be before opened date")
    if (out["closed_date"]
            and out["closed_date"] < out["opened_date"]):
        raise ValidationError(
            "Closed date cannot be before opened date")

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in CONCERN_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(CONCERN_STATUSES)}")
    if status == "Closed" and not out["closed_date"]:
        out["closed_date"] = _dt.date.today().isoformat()
    if status != "Closed" and out["closed_date"]:
        raise ValidationError(
            "Closed date should only be set when status is Closed")
    out["status"] = status

    out["key_worker"]     = (data.get("key_worker") or "").strip() or None
    out["intervention"]   = (data.get("intervention") or "").strip() or None
    out["parent_contact"] = (data.get("parent_contact") or "").strip() or None
    out["notes"]          = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Concern:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO attendance_concerns
                       (pupil_id, academic_year, concern_type, level,
                        attendance_pct, threshold_pct,
                        opened_date, next_review_date, closed_date,
                        status, key_worker, intervention,
                        parent_contact, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["concern_type"], payload["level"],
                 payload["attendance_pct"], payload["threshold_pct"],
                 payload["opened_date"], payload["next_review_date"],
                 payload["closed_date"], payload["status"],
                 payload["key_worker"], payload["intervention"],
                 payload["parent_contact"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create attendance concern")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created attendance concern #%d pupil=%s year=%s "
        "type=%s level=%s status=%s att=%.1f%%",
        rec.concern_id, rec.pupil_id, rec.academic_year,
        rec.concern_type, rec.level, rec.status,
        rec.attendance_pct if rec.attendance_pct is not None else -1)
    return rec


def get(concern_id: int) -> Concern | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT ac.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM attendance_concerns ac
                   LEFT JOIN pupils p ON p.pupil_id = ac.pupil_id
                   WHERE ac.concern_id = ?""",
                (concern_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", concern_id)
        raise
    return _row(r) if r else None


def list_concerns(*, pupil_id: str | None = None,
                   academic_year: str | None = None,
                   status: str | None = None,
                   concern_type: str | None = None,
                   level: str | None = None,
                   key_worker: str | None = None,
                   open_only: bool = False) -> list[Concern]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("ac.pupil_id = ?")
        params.append(pupil_id.strip())
    if academic_year:
        where.append("ac.academic_year = ?")
        params.append(academic_year.strip())
    if status:
        if status not in CONCERN_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(CONCERN_STATUSES)}")
        where.append("ac.status = ?")
        params.append(status)
    if concern_type:
        if concern_type not in CONCERN_TYPES:
            raise ValidationError(
                f"Concern type filter must be one of "
                f"{', '.join(CONCERN_TYPES)}")
        where.append("ac.concern_type = ?")
        params.append(concern_type)
    if level:
        if level not in CONCERN_LEVELS:
            raise ValidationError(
                f"Level filter must be one of "
                f"{', '.join(CONCERN_LEVELS)}")
        where.append("ac.level = ?")
        params.append(level)
    if key_worker:
        where.append("ac.key_worker = ?")
        params.append(key_worker.strip())
    if open_only:
        where.append("ac.status NOT IN ('Closed')")
    sql = ("""SELECT ac.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM attendance_concerns ac
              LEFT JOIN pupils p ON p.pupil_id = ac.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ac.opened_date DESC, ac.concern_id DESC"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_concerns failed")
        raise


def update(concern_id: int, data: dict[str, Any]) -> Concern:
    init_db()
    existing = get(concern_id)
    if existing is None:
        raise ValidationError(f"No attendance concern #{concern_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "academic_year", "concern_type",
                         "level", "attendance_pct", "threshold_pct",
                         "opened_date", "next_review_date",
                         "closed_date", "status", "key_worker",
                         "intervention", "parent_contact", "notes")}
    # When status flips away from Closed via update, drop closed_date.
    if (merged["status"] != "Closed"
            and data.get("closed_date") in (None, "")):
        merged["closed_date"] = None
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE attendance_concerns SET
                       pupil_id = ?, academic_year = ?,
                       concern_type = ?, level = ?,
                       attendance_pct = ?, threshold_pct = ?,
                       opened_date = ?, next_review_date = ?,
                       closed_date = ?, status = ?,
                       key_worker = ?, intervention = ?,
                       parent_contact = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE concern_id = ?""",
                (payload["pupil_id"], payload["academic_year"],
                 payload["concern_type"], payload["level"],
                 payload["attendance_pct"], payload["threshold_pct"],
                 payload["opened_date"], payload["next_review_date"],
                 payload["closed_date"], payload["status"],
                 payload["key_worker"], payload["intervention"],
                 payload["parent_contact"], payload["notes"],
                 concern_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update concern #%d", concern_id)
        raise
    rec = get(concern_id)
    assert rec is not None
    logger.info("Updated attendance concern #%d (status %s, level %s)",
                rec.concern_id, rec.status, rec.level)
    return rec


def set_status(concern_id: int, status: str) -> Concern:
    return update(concern_id, {"status": status})


def close(concern_id: int,
           closed_date: str | None = None) -> Concern:
    return update(concern_id, {
        "status": "Closed",
        "closed_date": closed_date or _dt.date.today().isoformat(),
    })


def delete(concern_id: int) -> bool:
    init_db()
    existing = get(concern_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM attendance_concerns WHERE concern_id = ?",
                (concern_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete concern #%d", concern_id)
        raise
    if deleted:
        logger.info("Deleted attendance concern #%d", concern_id)
    return deleted


def cohort_summary(*, academic_year: str | None = None) -> dict[str, Any]:
    rows = list_concerns(academic_year=academic_year)
    open_rows = [r for r in rows if r.status != "Closed"]
    att_values = [r.attendance_pct for r in rows
                    if r.attendance_pct is not None]
    avg = (sum(att_values) / len(att_values)) if att_values else None
    return {
        "total":      len(rows),
        "open":       len(open_rows),
        "by_status":  dict(Counter(r.status for r in rows)),
        "by_level":   dict(Counter(r.level for r in rows)),
        "by_type":    dict(Counter(r.concern_type for r in rows)),
        "pupils":     len({r.pupil_id for r in rows}),
        "avg_attendance": round(avg, 2) if avg is not None else None,
    }
