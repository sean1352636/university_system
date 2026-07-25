"""Parental leave-of-absence request data layer.

Tracks parental requests for term-time leave-of-absence with the
standard workflow:
Pending → (Approved | Declined) → optional Cancelled.
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
    ValidationError, _connect as _pupils_connect,
)

logger = logging.getLogger(__name__)

REQUEST_STATUSES: tuple[str, ...] = (
    "Pending", "Approved", "Declined", "Cancelled")
DEFAULT_STATUS: str = "Pending"

ABSENCE_CATEGORIES: tuple[str, ...] = (
    "Family holiday", "Religious observance",
    "Family event (wedding/funeral)",
    "Bereavement", "Medical appointment",
    "Educational visit", "Sporting commitment",
    "Performing arts", "Exceptional circumstance", "Other")
DEFAULT_CATEGORY: str = "Family holiday"

AUTHORISATIONS: tuple[str, ...] = (
    "Authorised", "Unauthorised", "Not yet decided")
DEFAULT_AUTHORISATION: str = "Not yet decided"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS absence_requests (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        TEXT NOT NULL,
    requested_by    TEXT NOT NULL,
    relationship    TEXT,
    submitted_date  TEXT NOT NULL DEFAULT (date('now')),
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    school_days     INTEGER,
    category        TEXT NOT NULL DEFAULT 'Family holiday',
    reason          TEXT NOT NULL,
    destination     TEXT,
    status          TEXT NOT NULL DEFAULT 'Pending',
    authorisation   TEXT NOT NULL DEFAULT 'Not yet decided',
    decided_by      TEXT,
    decided_date    TEXT,
    decision_notes  TEXT,
    contact_phone   TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ar_pupil
    ON absence_requests(pupil_id);
CREATE INDEX IF NOT EXISTS idx_ar_status
    ON absence_requests(status);
CREATE INDEX IF NOT EXISTS idx_ar_start
    ON absence_requests(start_date);
"""


@dataclass
class Request:
    request_id: int
    pupil_id: str
    requested_by: str
    relationship: str | None
    submitted_date: str
    start_date: str
    end_date: str
    school_days: int | None
    category: str
    reason: str
    destination: str | None
    status: str
    authorisation: str
    decided_by: str | None
    decided_date: str | None
    decision_notes: str | None
    contact_phone: str | None
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
            "Failed to initialise absence_requests tables")
        raise
    logger.info("Secondary absence_requests tables ready")
    _DB_READY = True


def _row(r: sqlite3.Row) -> Request:
    keys = r.keys()
    return Request(
        request_id=r["request_id"], pupil_id=r["pupil_id"],
        requested_by=r["requested_by"],
        relationship=r["relationship"],
        submitted_date=r["submitted_date"],
        start_date=r["start_date"], end_date=r["end_date"],
        school_days=r["school_days"],
        category=r["category"], reason=r["reason"],
        destination=r["destination"], status=r["status"],
        authorisation=r["authorisation"],
        decided_by=r["decided_by"],
        decided_date=r["decided_date"],
        decision_notes=r["decision_notes"],
        contact_phone=r["contact_phone"], notes=r["notes"],
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


def _school_days_between(start: str, end: str) -> int:
    """Mon-Fri count between two ISO dates inclusive."""
    s = _dt.date.fromisoformat(start)
    e = _dt.date.fromisoformat(end)
    if e < s:
        return 0
    days = 0
    cur = s
    while cur <= e:
        if cur.weekday() < 5:
            days += 1
        cur += _dt.timedelta(days=1)
    return days


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

    requested_by = (data.get("requested_by") or "").strip()
    if not requested_by:
        raise ValidationError("Requested by is required")
    out["requested_by"] = requested_by
    out["relationship"] = (data.get("relationship") or "").strip() or None

    out["submitted_date"] = _validate_date(
        data.get("submitted_date"), "Submitted date")
    out["start_date"]     = _validate_date(
        data.get("start_date"), "Start date", required=True)
    out["end_date"]       = _validate_date(
        data.get("end_date"), "End date", required=True)
    if out["end_date"] < out["start_date"]:
        raise ValidationError("End date cannot be before start date")

    sd_raw = data.get("school_days")
    if sd_raw in (None, "") or (isinstance(sd_raw, str)
                                   and not sd_raw.strip()):
        out["school_days"] = _school_days_between(
            out["start_date"], out["end_date"])
    else:
        try:
            d = int(sd_raw)
        except (TypeError, ValueError):
            raise ValidationError(
                "School days must be a whole number") from None
        if d < 0:
            raise ValidationError(
                "School days cannot be negative")
        if d > 60:
            raise ValidationError(
                "School days seems unreasonable (>60)")
        out["school_days"] = d

    cat = (data.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in ABSENCE_CATEGORIES:
        raise ValidationError(
            f"Category must be one of "
            f"{', '.join(ABSENCE_CATEGORIES)}")
    out["category"] = cat

    reason = (data.get("reason") or "").strip()
    if not reason:
        raise ValidationError("Reason is required")
    if len(reason) > 1000:
        raise ValidationError(
            "Reason is too long (max 1000 chars)")
    out["reason"] = reason

    out["destination"] = (data.get("destination") or "").strip() or None

    status = (data.get("status") or DEFAULT_STATUS).strip()
    if status not in REQUEST_STATUSES:
        raise ValidationError(
            f"Status must be one of {', '.join(REQUEST_STATUSES)}")
    out["status"] = status

    auth = (data.get("authorisation") or DEFAULT_AUTHORISATION).strip()
    if auth not in AUTHORISATIONS:
        raise ValidationError(
            f"Authorisation must be one of "
            f"{', '.join(AUTHORISATIONS)}")
    if status == "Approved" and auth == "Unauthorised":
        raise ValidationError(
            "Approved requests cannot be marked Unauthorised")
    if status == "Declined" and auth == "Authorised":
        raise ValidationError(
            "Declined requests cannot be marked Authorised")
    out["authorisation"] = auth

    decided_by    = (data.get("decided_by") or "").strip() or None
    decision_notes = (data.get("decision_notes") or "").strip() or None
    decided_date_in = data.get("decided_date")
    if status in ("Approved", "Declined"):
        if not decided_by:
            raise ValidationError(
                f"Decided-by is required when status is {status}")
        decided = _validate_date(
            decided_date_in, "Decided date",
            required=False)
        if decided is None:
            decided = _dt.date.today().isoformat()
        out["decided_date"] = decided
        out["decided_by"]   = decided_by
        out["decision_notes"] = decision_notes
    else:
        out["decided_date"]   = _validate_date(
            decided_date_in, "Decided date", required=False)
        out["decided_by"]     = decided_by
        out["decision_notes"] = decision_notes
        if (out["decided_date"] or out["decided_by"]) and \
                status == "Pending":
            # Allow but warn-only; keep data but make sure it doesn't
            # contradict workflow.
            pass

    out["contact_phone"] = (data.get("contact_phone") or "").strip() or None
    out["notes"]         = (data.get("notes") or "").strip() or None
    return out


def create(data: dict[str, Any]) -> Request:
    init_db()
    payload = _validate(data)
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO absence_requests
                       (pupil_id, requested_by, relationship,
                        submitted_date, start_date, end_date,
                        school_days, category, reason, destination,
                        status, authorisation, decided_by,
                        decided_date, decision_notes,
                        contact_phone, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (payload["pupil_id"], payload["requested_by"],
                 payload["relationship"], payload["submitted_date"],
                 payload["start_date"], payload["end_date"],
                 payload["school_days"], payload["category"],
                 payload["reason"], payload["destination"],
                 payload["status"], payload["authorisation"],
                 payload["decided_by"], payload["decided_date"],
                 payload["decision_notes"], payload["contact_phone"],
                 payload["notes"]),
            )
            conn.commit()
            new_id = cur.lastrowid
    except sqlite3.Error:
        logger.exception("Failed to create absence request")
        raise
    rec = get(new_id)
    assert rec is not None
    logger.info(
        "Created absence request #%d pupil=%s %s→%s "
        "(%d days, %s, %s)",
        rec.request_id, rec.pupil_id, rec.start_date, rec.end_date,
        rec.school_days or 0, rec.category, rec.status)
    return rec


def get(request_id: int) -> Request | None:
    init_db()
    try:
        with _connect() as conn:
            r = conn.execute(
                """SELECT ar.*,
                          (p.first_name || ' ' || p.last_name) AS pupil_name,
                          p.year_group AS pupil_year
                   FROM absence_requests ar
                   LEFT JOIN pupils p ON p.pupil_id = ar.pupil_id
                   WHERE ar.request_id = ?""",
                (request_id,),
            ).fetchone()
    except sqlite3.Error:
        logger.exception("get(%s) failed", request_id)
        raise
    return _row(r) if r else None


def list_requests(*, pupil_id: str | None = None,
                   status: str | None = None,
                   category: str | None = None,
                   authorisation: str | None = None,
                   pending_only: bool = False,
                   year_group: str | None = None,
                   from_date: str | None = None,
                   to_date: str | None = None) -> list[Request]:
    init_db()
    where: list[str] = []
    params: list[Any] = []
    if pupil_id:
        where.append("ar.pupil_id = ?")
        params.append(pupil_id.strip())
    if status:
        if status not in REQUEST_STATUSES:
            raise ValidationError(
                f"Status filter must be one of "
                f"{', '.join(REQUEST_STATUSES)}")
        where.append("ar.status = ?")
        params.append(status)
    if category:
        if category not in ABSENCE_CATEGORIES:
            raise ValidationError(
                f"Category filter must be one of "
                f"{', '.join(ABSENCE_CATEGORIES)}")
        where.append("ar.category = ?")
        params.append(category)
    if authorisation:
        if authorisation not in AUTHORISATIONS:
            raise ValidationError(
                f"Authorisation filter must be one of "
                f"{', '.join(AUTHORISATIONS)}")
        where.append("ar.authorisation = ?")
        params.append(authorisation)
    if pending_only:
        where.append("ar.status = 'Pending'")
    if year_group:
        where.append("p.year_group = ?")
        params.append(year_group.strip())
    if from_date:
        if not _DATE_RE.match(from_date):
            raise ValidationError("From date must be YYYY-MM-DD")
        where.append("ar.end_date >= ?")
        params.append(from_date)
    if to_date:
        if not _DATE_RE.match(to_date):
            raise ValidationError("To date must be YYYY-MM-DD")
        where.append("ar.start_date <= ?")
        params.append(to_date)
    sql = ("""SELECT ar.*,
                     (p.first_name || ' ' || p.last_name) AS pupil_name,
                     p.year_group AS pupil_year
              FROM absence_requests ar
              LEFT JOIN pupils p ON p.pupil_id = ar.pupil_id""")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ar.start_date DESC, ar.request_id DESC"
    try:
        with _connect() as conn:
            return [_row(r)
                    for r in conn.execute(sql, tuple(params)).fetchall()]
    except sqlite3.Error:
        logger.exception("list_requests failed")
        raise


def update(request_id: int, data: dict[str, Any]) -> Request:
    init_db()
    existing = get(request_id)
    if existing is None:
        raise ValidationError(f"No absence request #{request_id}")
    merged = {k: data.get(k, getattr(existing, k))
              for k in ("pupil_id", "requested_by", "relationship",
                         "submitted_date", "start_date", "end_date",
                         "school_days", "category", "reason",
                         "destination", "status", "authorisation",
                         "decided_by", "decided_date",
                         "decision_notes", "contact_phone", "notes")}
    # When status moves away from a decision, clear decision fields
    # if caller didn't supply them.
    if (merged["status"] == "Pending"
            and data.get("decided_date") in (None, "")
            and data.get("decided_by") in (None, "")):
        merged["decided_date"] = None
        merged["decided_by"]   = None
    payload = _validate(merged)
    try:
        with _connect() as conn:
            conn.execute(
                """UPDATE absence_requests SET
                       pupil_id = ?, requested_by = ?, relationship = ?,
                       submitted_date = ?, start_date = ?, end_date = ?,
                       school_days = ?, category = ?, reason = ?,
                       destination = ?, status = ?, authorisation = ?,
                       decided_by = ?, decided_date = ?,
                       decision_notes = ?, contact_phone = ?, notes = ?,
                       updated_at = datetime('now')
                   WHERE request_id = ?""",
                (payload["pupil_id"], payload["requested_by"],
                 payload["relationship"], payload["submitted_date"],
                 payload["start_date"], payload["end_date"],
                 payload["school_days"], payload["category"],
                 payload["reason"], payload["destination"],
                 payload["status"], payload["authorisation"],
                 payload["decided_by"], payload["decided_date"],
                 payload["decision_notes"], payload["contact_phone"],
                 payload["notes"], request_id),
            )
            conn.commit()
    except sqlite3.Error:
        logger.exception(
            "Failed to update absence request #%d", request_id)
        raise
    rec = get(request_id)
    assert rec is not None
    logger.info(
        "Updated absence request #%d (status %s, auth %s)",
        rec.request_id, rec.status, rec.authorisation)
    return rec


def decide(request_id: int, *, approve: bool,
            decided_by: str,
            authorisation: str | None = None,
            decision_notes: str | None = None,
            decided_date: str | None = None) -> Request:
    """Move a request to Approved or Declined with required fields."""
    decided_by = (decided_by or "").strip()
    if not decided_by:
        raise ValidationError("Decided-by is required")
    status = "Approved" if approve else "Declined"
    if authorisation is None:
        authorisation = "Authorised" if approve else "Unauthorised"
    return update(request_id, {
        "status": status,
        "authorisation": authorisation,
        "decided_by": decided_by,
        "decided_date": decided_date or _dt.date.today().isoformat(),
        "decision_notes": decision_notes,
    })


def cancel(request_id: int,
            decision_notes: str | None = None) -> Request:
    return update(request_id, {
        "status": "Cancelled",
        "decision_notes": decision_notes,
    })


def delete(request_id: int) -> bool:
    init_db()
    existing = get(request_id)
    if existing is None:
        return False
    try:
        with _connect() as conn:
            cur = conn.execute(
                "DELETE FROM absence_requests WHERE request_id = ?",
                (request_id,))
            conn.commit()
            deleted = cur.rowcount > 0
    except sqlite3.Error:
        logger.exception(
            "Failed to delete absence request #%d", request_id)
        raise
    if deleted:
        logger.info("Deleted absence request #%d", request_id)
    return deleted


def cohort_summary(*, from_date: str | None = None,
                    to_date: str | None = None) -> dict[str, Any]:
    rows = list_requests(from_date=from_date, to_date=to_date)
    approved = [r for r in rows if r.status == "Approved"]
    declined = [r for r in rows if r.status == "Declined"]
    pending  = [r for r in rows if r.status == "Pending"]
    total_days = sum((r.school_days or 0) for r in rows)
    approved_days = sum((r.school_days or 0) for r in approved)
    return {
        "total":         len(rows),
        "pending":       len(pending),
        "approved":      len(approved),
        "declined":      len(declined),
        "cancelled":     sum(1 for r in rows if r.status == "Cancelled"),
        "by_category":   dict(Counter(r.category for r in rows)),
        "by_auth":       dict(Counter(r.authorisation for r in rows)),
        "pupils":        len({r.pupil_id for r in rows}),
        "total_school_days":    total_days,
        "approved_school_days": approved_days,
    }
