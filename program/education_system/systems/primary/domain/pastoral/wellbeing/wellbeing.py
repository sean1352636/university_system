"""Pupil-wellbeing data layer for the Primary School System.

One row per ``wellbeing_checkins`` event. Each check-in captures three
1–5 ratings (mood / confidence / sense of connection), a free-text
list of stressors and supports, an ``action_needed`` flag, the
recorder, and a follow-up date + status workflow:

    Open → InProgress → Closed   (or Escalated)
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.primary.domain.learners.pupils.pupils import (
    ValidationError, YEAR_GROUPS, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

CHECKIN_STATUSES: tuple[str, ...] = (
    "Open", "InProgress", "Closed", "Escalated")
DEFAULT_STATUS: str = "Open"

CHECKIN_SOURCES: tuple[str, ...] = (
    "Self check-in", "Form tutor", "Pastoral team",
    "Counsellor", "Mental health lead", "Other")
DEFAULT_SOURCE: str = "Form tutor"

MIN_RATING = 1
MAX_RATING = 5

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wellbeing_checkins (
    checkin_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          TEXT NOT NULL,
    checkin_date      TEXT NOT NULL DEFAULT (date('now')),
    source            TEXT NOT NULL DEFAULT 'Form tutor',
    mood_rating       INTEGER,
    confidence_rating INTEGER,
    connection_rating INTEGER,
    stressors         TEXT,
    supports          TEXT,
    action_needed     INTEGER NOT NULL DEFAULT 0,
    action_summary    TEXT,
    recorded_by       TEXT,
    status            TEXT NOT NULL DEFAULT 'Open',
    follow_up_date    TEXT,
    follow_up_with    TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_wb_pupil
    ON wellbeing_checkins(pupil_id);
CREATE INDEX IF NOT EXISTS idx_wb_date
    ON wellbeing_checkins(checkin_date);
CREATE INDEX IF NOT EXISTS idx_wb_status
    ON wellbeing_checkins(status);
"""


@dataclass
class CheckIn:
    checkin_id: int
    pupil_id: str
    checkin_date: str
    source: str
    mood_rating: int | None
    confidence_rating: int | None
    connection_rating: int | None
    stressors: str | None
    supports: str | None
    action_needed: bool
    action_summary: str | None
    recorded_by: str | None
    status: str
    follow_up_date: str | None
    follow_up_with: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def average_rating(self) -> float | None:
        vals = [v for v in (self.mood_rating,
                             self.confidence_rating,
                             self.connection_rating)
                if v is not None]
        return round(sum(vals) / len(vals), 2) if vals else None


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
        logger.exception("Failed to initialise wellbeing table")
        raise
    logger.info("Secondary wellbeing table ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> CheckIn:
    keys = r.keys()
    return CheckIn(
        checkin_id=r["checkin_id"], pupil_id=r["pupil_id"],
        checkin_date=r["checkin_date"], source=r["source"],
        mood_rating=r["mood_rating"],
        confidence_rating=r["confidence_rating"],
        connection_rating=r["connection_rating"],
        stressors=r["stressors"], supports=r["supports"],
        action_needed=bool(r["action_needed"]),
        action_summary=r["action_summary"],
        recorded_by=r["recorded_by"],
        status=r["status"],
        follow_up_date=r["follow_up_date"],
        follow_up_with=r["follow_up_with"],
        notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _validate_date(value: Any, label: str, *,
                   required: bool = True) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
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


def _opt_rating(value, label):
    if value in (None, "") or (isinstance(value, str)
                                and not value.strip()):
        return None
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"{label} must be a whole number") from None
    if v < MIN_RATING or v > MAX_RATING:
        raise ValidationError(
            f"{label} must be between {MIN_RATING} and {MAX_RATING}")
    return v


def _validate(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    pid = (data.get("pupil_id") or "").strip()
    if not pid:
        raise ValidationError("Pupil ID is required")
    from education_system.systems.primary.domain.learners.pupils import (
        pupils as pupils_data,
    )
    if pupils_data.get_pupil(pid) is None:
        raise ValidationError(f"No pupil with id {pid}")
    out["pupil_id"] = pid

    out["checkin_date"] = _validate_date(
        data.get("checkin_date"), "Check-in date")

    source = (data.get("source") or DEFAULT_SOURCE).strip()
    if source not in CHECKIN_SOURCES:
        raise ValidationError(
            f"Source must be one of {', '.join(CHECKIN_SOURCES)}")
    out["source"] = source

    out["mood_rating"]       = _opt_rating(data.get("mood_rating"),
                                              "Mood rating")
    out["confidence_rating"] = _opt_rating(
        data.get("confidence_rating"), "Confidence rating")
    out["connection_rating"] = _opt_rating(
        data.get("connection_rating"), "Connection rating")

    out["stressors"]      = (data.get("stressors") or "").strip() or None
    out["supports"]       = (data.get("supports") or "").strip() or None

    out["action_needed"]  = bool(data.get("action_needed"))
    out["action_summary"] = (
        data.get("action_summary") or "").strip() or None
    out["recorded_by"]    = (
        data.get("recorded_by") or "").strip() or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in CHECKIN_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(CHECKIN_STATUSES)}")
    out["status"] = status

    out["follow_up_date"] = _validate_date(
        data.get("follow_up_date"), "Follow-up date",
        required=False)
    out["follow_up_with"] = (
        data.get("follow_up_with") or "").strip() or None
    out["notes"]          = (data.get("notes") or "").strip() or None

    if out["action_needed"] and not out["action_summary"]:
        raise ValidationError(
            "Action summary is required when action_needed is set")
    if (out["follow_up_date"]
            and out["follow_up_date"] < out["checkin_date"]):
        raise ValidationError(
            "Follow-up date cannot be before check-in date")
    if (out["mood_rating"] is None
            and out["confidence_rating"] is None
            and out["connection_rating"] is None
            and not (out["stressors"] or out["supports"]
                      or out["notes"])):
        raise ValidationError(
            "Provide at least one rating or free-text field")
    return out


def log_checkin(data: dict[str, Any]) -> CheckIn:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO wellbeing_checkins
                       (pupil_id, checkin_date, source,
                        mood_rating, confidence_rating,
                        connection_rating, stressors, supports,
                        action_needed, action_summary, recorded_by,
                        status, follow_up_date, follow_up_with,
                        notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["checkin_date"],
                 payload["source"], payload["mood_rating"],
                 payload["confidence_rating"],
                 payload["connection_rating"],
                 payload["stressors"], payload["supports"],
                 1 if payload["action_needed"] else 0,
                 payload["action_summary"], payload["recorded_by"],
                 payload["status"], payload["follow_up_date"],
                 payload["follow_up_with"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to log wellbeing check-in")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Logged wellbeing check-in #%d pupil=%s mood=%s conf=%s "
        "conn=%s action_needed=%s status=%s",
        rec.checkin_id, rec.pupil_id, rec.mood_rating,
        rec.confidence_rating, rec.connection_rating,
        rec.action_needed, rec.status)
    return rec


def get(checkin_id: int) -> CheckIn | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT w.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM wellbeing_checkins w
                   LEFT JOIN pupils p ON p.pupil_id = w.pupil_id
                   WHERE w.checkin_id = ?""",
                (checkin_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", checkin_id)
        raise
    return _row(r) if r else None


def list_checkins(*, pupil_id: str | None = None,
                  year_group: str | None = None,
                  status: str | None = None,
                  source: str | None = None,
                  action_needed: bool | None = None,
                  date_from: str | None = None,
                  date_to: str | None = None) -> list[CheckIn]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("w.pupil_id = ?")
        params.append(pupil_id.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if status:
        if status not in CHECKIN_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(CHECKIN_STATUSES)}")
        where.append("w.status = ?")
        params.append(status)
    if source:
        if source not in CHECKIN_SOURCES:
            raise ValidationError(
                f"Source filter must be one of "
                f"{', '.join(CHECKIN_SOURCES)}")
        where.append("w.source = ?")
        params.append(source)
    if action_needed is not None:
        where.append("w.action_needed = ?")
        params.append(1 if action_needed else 0)
    if date_from:
        where.append("w.checkin_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("w.checkin_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT w.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM wellbeing_checkins w
              LEFT JOIN pupils p ON p.pupil_id = w.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY w.checkin_date DESC, w.checkin_id DESC"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_checkins failed")
        raise


def update(checkin_id: int, data: dict[str, Any]) -> CheckIn:
    init_db()
    existing = get(checkin_id)
    if existing is None:
        raise ValidationError(
            f"No wellbeing check-in #{checkin_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "checkin_date", "source",
                         "mood_rating", "confidence_rating",
                         "connection_rating", "stressors", "supports",
                         "action_needed", "action_summary",
                         "recorded_by", "status", "follow_up_date",
                         "follow_up_with", "notes")}
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE wellbeing_checkins SET
                       pupil_id = ?, checkin_date = ?, source = ?,
                       mood_rating = ?, confidence_rating = ?,
                       connection_rating = ?, stressors = ?,
                       supports = ?, action_needed = ?,
                       action_summary = ?, recorded_by = ?,
                       status = ?, follow_up_date = ?,
                       follow_up_with = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE checkin_id = ?""",
                (payload["pupil_id"], payload["checkin_date"],
                 payload["source"], payload["mood_rating"],
                 payload["confidence_rating"],
                 payload["connection_rating"],
                 payload["stressors"], payload["supports"],
                 1 if payload["action_needed"] else 0,
                 payload["action_summary"], payload["recorded_by"],
                 payload["status"], payload["follow_up_date"],
                 payload["follow_up_with"], payload["notes"],
                 checkin_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to update check-in #%d", checkin_id)
        raise
    rec = get(checkin_id)
    assert rec is not None
    logger.info("Updated wellbeing check-in #%d (status %s)",
                rec.checkin_id, rec.status)
    return rec


def set_status(checkin_id: int, status: str) -> CheckIn:
    return update(checkin_id, {"status": status})


def delete(checkin_id: int) -> bool:
    init_db()
    existing = get(checkin_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM wellbeing_checkins "
                "WHERE checkin_id = ?", (checkin_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete check-in #%d", checkin_id)
        raise
    if deleted:
        logger.info("Deleted wellbeing check-in #%d (pupil %s)",
                    checkin_id, existing.pupil_id)
    return deleted


def pupil_summary(pupil_id: str,
                   *, date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_checkins(pupil_id=pupil_id,
                            date_from=date_from, date_to=date_to)

    def _avg(attr: str) -> float | None:
        vals = [getattr(r, attr) for r in rows
                if getattr(r, attr) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "pupil_id":      (pupil_id or "").strip(),
        "count":         len(rows),
        "avg_mood":      _avg("mood_rating"),
        "avg_confidence": _avg("confidence_rating"),
        "avg_connection": _avg("connection_rating"),
        "action_needed":  sum(1 for r in rows if r.action_needed),
        "by_status":     dict(Counter(r.status for r in rows)),
        "checkins":      rows,
    }


def cohort_summary(*, year_group: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_checkins(year_group=year_group,
                            date_from=date_from, date_to=date_to)

    def _avg(attr: str) -> float | None:
        vals = [getattr(r, attr) for r in rows
                if getattr(r, attr) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    return {
        "total":          len(rows),
        "avg_mood":       _avg("mood_rating"),
        "avg_confidence": _avg("confidence_rating"),
        "avg_connection": _avg("connection_rating"),
        "action_needed":  sum(1 for r in rows if r.action_needed),
        "by_status":      dict(Counter(r.status for r in rows)),
        "by_source":      dict(Counter(r.source for r in rows)),
    }


def low_wellbeing(*, threshold: int = 2,
                   year_group: str | None = None
                   ) -> dict[str, list[CheckIn]]:
    """Return ``{pupil_id: [check-ins]}`` for pupils whose latest
    check-in scores any rating at or below ``threshold`` (default 2)."""
    init_db()
    if threshold < MIN_RATING or threshold > MAX_RATING:
        raise ValidationError(
            f"Threshold must be between {MIN_RATING} and {MAX_RATING}")
    rows = list_checkins(year_group=year_group)
    latest: dict[str, CheckIn] = {}
    for r in rows:
        # rows are date-DESC so first hit per pupil is the latest
        if r.pupil_id not in latest:
            latest[r.pupil_id] = r
    out: dict[str, list[CheckIn]] = {}
    for pid, r in latest.items():
        scores = [v for v in (r.mood_rating,
                                r.confidence_rating,
                                r.connection_rating)
                  if v is not None]
        if scores and min(scores) <= threshold:
            out[pid] = [r]
    return out
