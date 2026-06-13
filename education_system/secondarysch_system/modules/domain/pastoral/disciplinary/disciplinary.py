"""Disciplinary-case data layer for the Secondary School System.

Two tables:

* ``disciplinary_cases``  — one row per formal case (internal
                             exclusion, fixed-term suspension,
                             permanent exclusion, parental meeting,
                             governors' panel, etc.). Captures the
                             reason, decision-maker, dates, and a
                             status workflow.
* ``disciplinary_events`` — chronological log of events attached to a
                             case (meetings, letters sent, return-to-
                             school, reintegration, appeal,
                             decisions).
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

CASE_TYPES: tuple[str, ...] = (
    "Internal exclusion", "Fixed-term suspension",
    "Permanent exclusion", "Reduced timetable",
    "Parental meeting", "Governors panel",
    "Behaviour contract", "Restorative meeting", "Other")
DEFAULT_TYPE: str = "Fixed-term suspension"

CASE_STATUSES: tuple[str, ...] = (
    "Open", "InProgress", "Closed", "Appealed", "Overturned")
DEFAULT_STATUS: str = "Open"

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY: str = "High"

EVENT_TYPES: tuple[str, ...] = (
    "Meeting", "Letter sent", "Phone call", "Return-to-school",
    "Reintegration", "Appeal lodged", "Appeal decision",
    "Governors decision", "Decision", "Other")
DEFAULT_EVENT_TYPE: str = "Meeting"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS disciplinary_cases (
    case_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          TEXT NOT NULL,
    case_type         TEXT NOT NULL DEFAULT 'Fixed-term suspension',
    severity          TEXT NOT NULL DEFAULT 'High',
    incident_date     TEXT,
    start_date        TEXT NOT NULL,
    end_date          TEXT,
    days              INTEGER,
    reason            TEXT NOT NULL,
    decision_maker    TEXT,
    status            TEXT NOT NULL DEFAULT 'Open',
    appeal_decision   TEXT,
    return_date       TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS disciplinary_events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id       INTEGER NOT NULL,
    event_date    TEXT NOT NULL DEFAULT (date('now')),
    event_type    TEXT NOT NULL DEFAULT 'Meeting',
    participants  TEXT,
    summary       TEXT NOT NULL,
    outcome       TEXT,
    follow_up     TEXT,
    notes         TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (case_id) REFERENCES disciplinary_cases(case_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_disc_pupil
    ON disciplinary_cases(pupil_id);
CREATE INDEX IF NOT EXISTS idx_disc_status
    ON disciplinary_cases(status);
CREATE INDEX IF NOT EXISTS idx_disc_events_case
    ON disciplinary_events(case_id);
"""


@dataclass
class DisciplinaryCase:
    case_id: int
    pupil_id: str
    case_type: str
    severity: str
    incident_date: str | None
    start_date: str
    end_date: str | None
    days: int | None
    reason: str
    decision_maker: str | None
    status: str
    appeal_decision: str | None
    return_date: str | None
    notes: str | None
    pupil_name: str | None = None
    pupil_year: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class DisciplinaryEvent:
    event_id: int
    case_id: int
    event_date: str
    event_type: str
    participants: str | None
    summary: str
    outcome: str | None
    follow_up: str | None
    notes: str | None
    created_at: str | None = None


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
        logger.exception("Failed to initialise disciplinary tables")
        raise
    logger.info("Secondary disciplinary tables ready")
    _DB_READY = True


def _row_case(r: sqlite3.Row) -> DisciplinaryCase:
    keys = r.keys()
    return DisciplinaryCase(
        case_id=r["case_id"], pupil_id=r["pupil_id"],
        case_type=r["case_type"], severity=r["severity"],
        incident_date=r["incident_date"],
        start_date=r["start_date"], end_date=r["end_date"],
        days=r["days"], reason=r["reason"],
        decision_maker=r["decision_maker"],
        status=r["status"],
        appeal_decision=r["appeal_decision"],
        return_date=r["return_date"], notes=r["notes"],
        pupil_name=r["pupil_name"] if "pupil_name" in keys else None,
        pupil_year=r["pupil_year"] if "pupil_year" in keys else None,
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


def _row_event(r: sqlite3.Row) -> DisciplinaryEvent:
    return DisciplinaryEvent(
        event_id=r["event_id"], case_id=r["case_id"],
        event_date=r["event_date"], event_type=r["event_type"],
        participants=r["participants"], summary=r["summary"],
        outcome=r["outcome"], follow_up=r["follow_up"],
        notes=r["notes"], created_at=r["created_at"],
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


def _validate_case(data: dict[str, Any]) -> dict[str, Any]:
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

    ctype = (data.get("case_type") or DEFAULT_TYPE).strip()
    if ctype not in CASE_TYPES:
        raise ValidationError(
            f"Case type must be one of {', '.join(CASE_TYPES)}")
    out["case_type"] = ctype

    severity = (data.get("severity") or DEFAULT_SEVERITY).strip()
    if severity not in SEVERITIES:
        raise ValidationError(
            f"Severity must be one of {', '.join(SEVERITIES)}")
    out["severity"] = severity

    out["incident_date"] = _validate_date(
        data.get("incident_date"), "Incident date", required=False)

    out["start_date"] = _validate_date(data.get("start_date"),
                                         "Start date")
    out["end_date"]   = _validate_date(data.get("end_date"),
                                         "End date", required=False)
    if out["end_date"] and out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    days_raw = data.get("days")
    if days_raw in (None, "") or (isinstance(days_raw, str)
                                    and not days_raw.strip()):
        # Auto-fill from start..end if both present.
        if out["end_date"]:
            try:
                sd = _dt.date.fromisoformat(out["start_date"])
                ed = _dt.date.fromisoformat(out["end_date"])
                out["days"] = (ed - sd).days + 1
            except ValueError:
                out["days"] = None
        else:
            out["days"] = None
    else:
        try:
            n = int(days_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "Days must be a whole number") from None
        if n < 0 or n > 365:
            raise ValidationError("Days must be between 0 and 365")
        out["days"] = n

    reason = (data.get("reason") or "").strip()
    if not reason:
        raise ValidationError("Reason is required")
    if len(reason) > 500:
        raise ValidationError("Reason must be 500 chars or fewer")
    out["reason"] = reason

    out["decision_maker"] = (data.get("decision_maker") or "").strip() or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in CASE_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(CASE_STATUSES)}")
    out["status"] = status

    out["appeal_decision"] = (data.get("appeal_decision") or "").strip() or None
    out["return_date"]     = _validate_date(
        data.get("return_date"), "Return date", required=False)
    out["notes"]           = (data.get("notes") or "").strip() or None

    if out["status"] in ("Appealed", "Overturned"):
        if not out["appeal_decision"]:
            raise ValidationError(
                f"Appeal decision is required when status is "
                f"{out['status']}")
    if (out["return_date"]
            and out["return_date"] < out["start_date"]):
        raise ValidationError(
            "Return date cannot be before start date")
    return out


def _validate_event(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    cid_raw = data.get("case_id")
    if cid_raw in (None, ""):
        raise ValidationError("Case ID is required")
    try:
        out["case_id"] = int(cid_raw)
    except (TypeError, ValueError):
        raise ValidationError("Case ID must be a number") from None

    out["event_date"] = _validate_date(data.get("event_date"),
                                         "Event date")
    etype = (data.get("event_type") or DEFAULT_EVENT_TYPE).strip()
    if etype not in EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of {', '.join(EVENT_TYPES)}")
    out["event_type"] = etype

    summary = (data.get("summary") or "").strip()
    if not summary:
        raise ValidationError("Summary is required")
    out["summary"] = summary

    out["participants"] = (data.get("participants") or "").strip() or None
    out["outcome"]      = (data.get("outcome") or "").strip() or None
    out["follow_up"]    = (data.get("follow_up") or "").strip() or None
    out["notes"]        = (data.get("notes") or "").strip() or None
    return out


# ── Case CRUD ────────────────────────────────────────────────────

def create_case(data: dict[str, Any]) -> DisciplinaryCase:
    init_db()
    payload = _validate_case(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO disciplinary_cases
                       (pupil_id, case_type, severity,
                        incident_date, start_date, end_date, days,
                        reason, decision_maker, status,
                        appeal_decision, return_date, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["case_type"],
                 payload["severity"], payload["incident_date"],
                 payload["start_date"], payload["end_date"],
                 payload["days"], payload["reason"],
                 payload["decision_maker"], payload["status"],
                 payload["appeal_decision"], payload["return_date"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create disciplinary case")
        raise
    rec = get_case(new_id)
    assert rec is not None
    logger.info("Created disciplinary case #%d pupil=%s type=%s "
                "severity=%s days=%s status=%s",
                rec.case_id, rec.pupil_id, rec.case_type,
                rec.severity, rec.days, rec.status)
    return rec


def get_case(case_id: int) -> DisciplinaryCase | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT c.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM disciplinary_cases c
                   LEFT JOIN pupils p ON p.pupil_id = c.pupil_id
                   WHERE c.case_id = ?""",
                (case_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_case(%s) failed", case_id)
        raise
    return _row_case(r) if r else None


def list_cases(*, pupil_id: str | None = None,
               year_group: str | None = None,
               case_type: str | None = None,
               severity: str | None = None,
               status: str | None = None,
               date_from: str | None = None,
               date_to: str | None = None
               ) -> list[DisciplinaryCase]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("c.pupil_id = ?")
        params.append(pupil_id.strip())
    if year_group:
        if year_group not in YEAR_GROUPS:
            raise ValidationError(
                f"Year filter must be one of {', '.join(YEAR_GROUPS)}")
        where.append("p.year_group = ?")
        params.append(year_group)
    if case_type:
        if case_type not in CASE_TYPES:
            raise ValidationError(
                f"Type filter must be one of {', '.join(CASE_TYPES)}")
        where.append("c.case_type = ?")
        params.append(case_type)
    if severity:
        if severity not in SEVERITIES:
            raise ValidationError(
                f"Severity filter must be one of "
                f"{', '.join(SEVERITIES)}")
        where.append("c.severity = ?")
        params.append(severity)
    if status:
        if status not in CASE_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(CASE_STATUSES)}")
        where.append("c.status = ?")
        params.append(status)
    if date_from:
        where.append("c.start_date >= ?")
        params.append(_validate_date(date_from, "From date"))
    if date_to:
        where.append("c.start_date <= ?")
        params.append(_validate_date(date_to, "To date"))
    sql = ("""SELECT c.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM disciplinary_cases c
              LEFT JOIN pupils p ON p.pupil_id = c.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += (" ORDER BY CASE c.severity "
            " WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 "
            " WHEN 'Medium' THEN 3 WHEN 'Low' THEN 4 END, "
            "c.start_date DESC, c.case_id DESC")
    try:
        with _connect() as conn:
            return [_row_case(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_cases failed")
        raise


def update_case(case_id: int,
                 data: dict[str, Any]) -> DisciplinaryCase:
    init_db()
    existing = get_case(case_id)
    if existing is None:
        raise ValidationError(f"No disciplinary case #{case_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "case_type", "severity",
                         "incident_date", "start_date", "end_date",
                         "days", "reason", "decision_maker", "status",
                         "appeal_decision", "return_date", "notes")}
    payload = _validate_case(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE disciplinary_cases SET
                       pupil_id = ?, case_type = ?, severity = ?,
                       incident_date = ?, start_date = ?, end_date = ?,
                       days = ?, reason = ?, decision_maker = ?,
                       status = ?, appeal_decision = ?,
                       return_date = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE case_id = ?""",
                (payload["pupil_id"], payload["case_type"],
                 payload["severity"], payload["incident_date"],
                 payload["start_date"], payload["end_date"],
                 payload["days"], payload["reason"],
                 payload["decision_maker"], payload["status"],
                 payload["appeal_decision"], payload["return_date"],
                 payload["notes"], case_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update disciplinary case #%d", case_id)
        raise
    rec = get_case(case_id)
    assert rec is not None
    logger.info("Updated disciplinary case #%d (status %s)",
                rec.case_id, rec.status)
    return rec


def set_status(case_id: int, status: str,
                *, appeal_decision: str | None = None
                ) -> DisciplinaryCase:
    payload: dict[str, Any] = {"status": status}
    if appeal_decision is not None:
        payload["appeal_decision"] = appeal_decision
    return update_case(case_id, payload)


def delete_case(case_id: int) -> bool:
    init_db()
    existing = get_case(case_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            cur = conn.execute(
                "DELETE FROM disciplinary_cases WHERE case_id = ?",
                (case_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete disciplinary case #%d", case_id)
        raise
    if deleted:
        logger.info("Deleted disciplinary case #%d "
                    "(cascade: events)", case_id)
    return deleted


# ── Events ──────────────────────────────────────────────────────

def add_event(data: dict[str, Any]) -> DisciplinaryEvent:
    init_db()
    payload = _validate_event(data)
    if get_case(payload["case_id"]) is None:
        raise ValidationError(
            f"No disciplinary case #{payload['case_id']}")
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO disciplinary_events
                       (case_id, event_date, event_type, participants,
                        summary, outcome, follow_up, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["case_id"], payload["event_date"],
                 payload["event_type"], payload["participants"],
                 payload["summary"], payload["outcome"],
                 payload["follow_up"], payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception(
            "Failed to add event to case %d", payload["case_id"])
        raise
    logger.info(
        "Added disciplinary event #%d to case #%d (%s, %s)",
        new_id, payload["case_id"], payload["event_date"],
        payload["event_type"])
    rec = get_event(new_id)
    assert rec is not None
    return rec


def get_event(event_id: int) -> DisciplinaryEvent | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM disciplinary_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get_event(%s) failed", event_id)
        raise
    return _row_event(r) if r else None


def list_events(case_id: int) -> list[DisciplinaryEvent]:
    init_db()
    try:
        with _connect() as conn:
            return [_row_event(r) for r in conn.execute(
                "SELECT * FROM disciplinary_events WHERE case_id = ? "
                "ORDER BY event_date DESC, event_id DESC",
                (case_id,),
            ).fetchall()]
    except sqlite3.Error:
        logger.exception("list_events(%s) failed", case_id)
        raise


def delete_event(event_id: int) -> bool:
    init_db()
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM disciplinary_events WHERE event_id = ?",
                (event_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete disciplinary event #%d", event_id)
        raise
    if deleted:
        logger.info("Deleted disciplinary event #%d", event_id)
    return deleted


def case_summary(case_id: int) -> dict[str, Any]:
    init_db()
    rec = get_case(case_id)
    if rec is None:
        raise ValidationError(f"No disciplinary case #{case_id}")
    events = list_events(case_id)
    return {
        "case":         rec,
        "events":       events,
        "event_count":  len(events),
        "by_type":      dict(Counter(e.event_type for e in events)),
    }


def cohort_summary(*, year_group: str | None = None,
                   date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_cases(year_group=year_group,
                        date_from=date_from, date_to=date_to)
    total_days = sum(r.days or 0 for r in rows)
    return {
        "total":       len(rows),
        "open":        sum(1 for r in rows
                           if r.status not in ("Closed", "Overturned")),
        "by_status":   dict(Counter(r.status for r in rows)),
        "by_type":     dict(Counter(r.case_type for r in rows)),
        "by_severity": dict(Counter(r.severity for r in rows)),
        "total_days":  total_days,
    }
