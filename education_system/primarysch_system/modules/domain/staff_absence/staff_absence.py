"""Staff Absence data layer for Primary School System.

Operational daily-absence tracker: who's out today, expected back,
cover arranged, parents informed, return-to-work meeting. FK
cascade on staff. Distinct from the HR leave log (`staff_hr_events`)
which captures planned / approved leave — this module focuses on
the day-to-day operational picture.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.primarysch_system.core import paths as _paths

logger = logging.getLogger(__name__)

ABSENCE_TYPES: tuple[str, ...] = (
    "Sickness",
    "Sickness — Long Term",
    "Medical Appointment",
    "Hospital Appointment",
    "Bereavement",
    "Compassionate",
    "Domestic Emergency",
    "Childcare Emergency",
    "Strike",
    "Bad Weather",
    "Travel Disruption",
    "Jury Service",
    "Public Duty",
    "Other",
)
DEFAULT_ABSENCE_TYPE = "Sickness"

NOTIFICATION_METHODS: tuple[str, ...] = (
    "Phone Call",
    "Text",
    "Email",
    "In Person",
    "Via Manager",
    "Not Recorded",
)
DEFAULT_NOTIFICATION_METHOD = "Phone Call"

CERTIFICATE_TYPES: tuple[str, ...] = (
    "Self-Cert",
    "Medical Cert",
    "Hospital Letter",
    "Not Required",
)
DEFAULT_CERTIFICATE_TYPE = "Self-Cert"

COVER_SOURCES: tuple[str, ...] = (
    "Internal",
    "Supply Agency",
    "Class Split",
    "Cover Supervisor",
    "Cancelled",
    "Not Required",
    "Pending",
)
DEFAULT_COVER_SOURCE = "Pending"

STATUSES: tuple[str, ...] = (
    "Reported",
    "Confirmed",
    "Active",
    "Returned",
    "Closed",
    "Cancelled",
)
DEFAULT_STATUS = "Reported"


class ValidationError(Exception):
    pass


@dataclass
class Absence:
    absence_id: int
    staff_id: str
    absence_date: str
    expected_return: str | None
    actual_return: str | None
    absence_type: str
    reason: str | None
    notified_on: str | None
    notification_method: str
    notified_by: str | None
    certificate_type: str
    cert_received_on: str | None
    cover_required: bool
    cover_source: str
    cover_arranged_by: str | None
    cover_notes: str | None
    critical: bool
    parents_informed: bool
    slt_informed: bool
    rtw_required: bool
    rtw_meeting_on: str | None
    rtw_completed_by: str | None
    days_lost: float | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status in ("Reported", "Confirmed", "Active")

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def cover_outstanding(self) -> bool:
        return (self.is_open and self.cover_required
                  and self.cover_source == "Pending")

    @property
    def rtw_overdue(self) -> bool:
        if (not self.rtw_required
                or self.rtw_meeting_on
                or self.status != "Returned"):
            return False
        if not self.actual_return:
            return False
        # Overdue if returned more than 7 days ago without meeting
        try:
            r = _dt.date.fromisoformat(self.actual_return)
        except ValueError:
            return False
        return (_dt.date.today() - r).days > 7

    @property
    def return_overdue(self) -> bool:
        if not self.is_open or not self.expected_return:
            return False
        return self.expected_return < _dt.date.today().isoformat()


@dataclass
class AbsenceSummary:
    total: int = 0
    open_count: int = 0
    active_today: int = 0
    cover_outstanding: int = 0
    critical_open: int = 0
    rtw_overdue: int = 0
    return_overdue: int = 0
    awaiting_cert: int = 0
    parents_pending: int = 0
    distinct_staff: int = 0
    total_days_lost: float = 0.0
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_cover_source: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.STAFF_ABSENCE_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS staff_absences (
                absence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT NOT NULL,
                absence_date TEXT NOT NULL,
                expected_return TEXT,
                actual_return TEXT,
                absence_type TEXT NOT NULL,
                reason TEXT,
                notified_on TEXT,
                notification_method TEXT NOT NULL,
                notified_by TEXT,
                certificate_type TEXT NOT NULL,
                cert_received_on TEXT,
                cover_required INTEGER NOT NULL DEFAULT 1,
                cover_source TEXT NOT NULL,
                cover_arranged_by TEXT,
                cover_notes TEXT,
                critical INTEGER NOT NULL DEFAULT 0,
                parents_informed INTEGER NOT NULL DEFAULT 0,
                slt_informed INTEGER NOT NULL DEFAULT 0,
                rtw_required INTEGER NOT NULL DEFAULT 0,
                rtw_meeting_on TEXT,
                rtw_completed_by TEXT,
                days_lost REAL,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(staff_id) REFERENCES staff(staff_id)
                  ON DELETE CASCADE
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _staff_exists(staff_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM staff WHERE staff_id=?",
                (staff_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")

    out["absence_date"] = (out.get("absence_date") or "").strip()
    if not out["absence_date"]:
        raise ValidationError("Absence date is required")
    _check_date("Absence date",    out["absence_date"])
    _check_date("Expected return", out.get("expected_return"))
    _check_date("Actual return",   out.get("actual_return"))
    _check_date("Notified on",     out.get("notified_on"))
    _check_date("Cert received",   out.get("cert_received_on"))
    _check_date("RTW meeting",     out.get("rtw_meeting_on"))

    if (out.get("expected_return")
            and out["expected_return"] < out["absence_date"]):
        raise ValidationError(
            "Expected return must be on or after absence date")
    if (out.get("actual_return")
            and out["actual_return"] < out["absence_date"]):
        raise ValidationError(
            "Actual return must be on or after absence date")

    at = (out.get("absence_type") or "").strip()
    if at not in ABSENCE_TYPES:
        raise ValidationError(
            f"Absence type must be one of: "
            f"{', '.join(ABSENCE_TYPES)}")
    out["absence_type"] = at

    nm = (out.get("notification_method")
            or DEFAULT_NOTIFICATION_METHOD).strip()
    if nm not in NOTIFICATION_METHODS:
        raise ValidationError(
            f"Notification method must be one of: "
            f"{', '.join(NOTIFICATION_METHODS)}")
    out["notification_method"] = nm

    ct = (out.get("certificate_type")
            or DEFAULT_CERTIFICATE_TYPE).strip()
    if ct not in CERTIFICATE_TYPES:
        raise ValidationError(
            f"Certificate type must be one of: "
            f"{', '.join(CERTIFICATE_TYPES)}")
    out["certificate_type"] = ct

    cs = (out.get("cover_source") or DEFAULT_COVER_SOURCE).strip()
    if cs not in COVER_SOURCES:
        raise ValidationError(
            f"Cover source must be one of: "
            f"{', '.join(COVER_SOURCES)}")
    out["cover_source"] = cs

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("reason", "notified_by", "cover_arranged_by",
               "cover_notes", "rtw_completed_by", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("expected_return", "actual_return", "notified_on",
               "cert_received_on", "rtw_meeting_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("cover_required", "critical", "parents_informed",
               "slt_informed", "rtw_required"):
        out[k] = bool(out.get(k))

    dl = out.get("days_lost")
    if dl in (None, ""):
        out["days_lost"] = None
    else:
        try:
            out["days_lost"] = float(dl)
        except (TypeError, ValueError):
            raise ValidationError("Days lost must be a number")
        if out["days_lost"] < 0:
            raise ValidationError("Days lost must be >= 0")
    return out


def _row(r: sqlite3.Row) -> Absence:
    return Absence(
        absence_id=r["absence_id"],
        staff_id=r["staff_id"],
        absence_date=r["absence_date"],
        expected_return=r["expected_return"],
        actual_return=r["actual_return"],
        absence_type=r["absence_type"],
        reason=r["reason"],
        notified_on=r["notified_on"],
        notification_method=r["notification_method"],
        notified_by=r["notified_by"],
        certificate_type=r["certificate_type"],
        cert_received_on=r["cert_received_on"],
        cover_required=bool(r["cover_required"]),
        cover_source=r["cover_source"],
        cover_arranged_by=r["cover_arranged_by"],
        cover_notes=r["cover_notes"],
        critical=bool(r["critical"]),
        parents_informed=bool(r["parents_informed"]),
        slt_informed=bool(r["slt_informed"]),
        rtw_required=bool(r["rtw_required"]),
        rtw_meeting_on=r["rtw_meeting_on"],
        rtw_completed_by=r["rtw_completed_by"],
        days_lost=r["days_lost"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_absence(payload: dict[str, Any]) -> Absence:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO staff_absences (
              staff_id, absence_date, expected_return,
              actual_return, absence_type, reason,
              notified_on, notification_method, notified_by,
              certificate_type, cert_received_on,
              cover_required, cover_source, cover_arranged_by,
              cover_notes, critical, parents_informed,
              slt_informed, rtw_required, rtw_meeting_on,
              rtw_completed_by, days_lost, status, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["staff_id"], p["absence_date"],
            p["expected_return"], p["actual_return"],
            p["absence_type"], p["reason"],
            p["notified_on"], p["notification_method"],
            p["notified_by"], p["certificate_type"],
            p["cert_received_on"],
            1 if p["cover_required"] else 0,
            p["cover_source"], p["cover_arranged_by"],
            p["cover_notes"],
            1 if p["critical"] else 0,
            1 if p["parents_informed"] else 0,
            1 if p["slt_informed"] else 0,
            1 if p["rtw_required"] else 0,
            p["rtw_meeting_on"], p["rtw_completed_by"],
            p["days_lost"], p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_absence(new_id)


def update_absence(absence_id: int,
                       payload: dict[str, Any]) -> Absence:
    init_db()
    if get_absence(absence_id) is None:
        raise ValidationError(f"No absence with id {absence_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE staff_absences SET
              staff_id=?, absence_date=?, expected_return=?,
              actual_return=?, absence_type=?, reason=?,
              notified_on=?, notification_method=?, notified_by=?,
              certificate_type=?, cert_received_on=?,
              cover_required=?, cover_source=?, cover_arranged_by=?,
              cover_notes=?, critical=?, parents_informed=?,
              slt_informed=?, rtw_required=?, rtw_meeting_on=?,
              rtw_completed_by=?, days_lost=?, status=?, notes=?,
              updated_on=?
            WHERE absence_id=?
        """, (
            p["staff_id"], p["absence_date"],
            p["expected_return"], p["actual_return"],
            p["absence_type"], p["reason"],
            p["notified_on"], p["notification_method"],
            p["notified_by"], p["certificate_type"],
            p["cert_received_on"],
            1 if p["cover_required"] else 0,
            p["cover_source"], p["cover_arranged_by"],
            p["cover_notes"],
            1 if p["critical"] else 0,
            1 if p["parents_informed"] else 0,
            1 if p["slt_informed"] else 0,
            1 if p["rtw_required"] else 0,
            p["rtw_meeting_on"], p["rtw_completed_by"],
            p["days_lost"], p["status"], p["notes"],
            now, absence_id,
        ))
    return get_absence(absence_id)


def delete_absence(absence_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM staff_absences WHERE absence_id=?",
            (absence_id,))
        return cur.rowcount > 0


def get_absence(absence_id: int) -> Absence | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM staff_absences WHERE absence_id=?",
            (absence_id,)).fetchone()
        return _row(r) if r else None


def list_absences(*,
                       staff_id: str | None = None,
                       absence_type: str | None = None,
                       status: str | None = None,
                       cover_source: str | None = None,
                       open_only: bool = False,
                       active_today: bool = False,
                       critical_only: bool = False,
                       cover_outstanding: bool = False,
                       rtw_overdue: bool = False,
                       return_overdue: bool = False,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       ) -> list[Absence]:
    init_db()
    sql = "SELECT * FROM staff_absences WHERE 1=1"
    params: list[Any] = []
    if staff_id:
        sql += " AND staff_id=?"
        params.append(staff_id)
    if absence_type:
        sql += " AND absence_type=?"
        params.append(absence_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if cover_source:
        sql += " AND cover_source=?"
        params.append(cover_source)
    if open_only:
        sql += (" AND status IN "
                  "('Reported','Confirmed','Active')")
    if active_today:
        today = _dt.date.today().isoformat()
        sql += (" AND absence_date <= ?"
                  " AND (actual_return IS NULL"
                  " OR actual_return >= ?)"
                  " AND status IN ('Reported','Confirmed','Active')")
        params.extend([today, today])
    if critical_only:
        sql += " AND critical=1"
    if cover_outstanding:
        sql += (" AND cover_required=1"
                  " AND cover_source='Pending'"
                  " AND status IN ('Reported','Confirmed','Active')")
    if rtw_overdue:
        cutoff = (_dt.date.today()
                    - _dt.timedelta(days=7)).isoformat()
        sql += (" AND rtw_required=1"
                  " AND rtw_meeting_on IS NULL"
                  " AND status='Returned'"
                  " AND actual_return IS NOT NULL"
                  " AND actual_return < ?")
        params.append(cutoff)
    if return_overdue:
        today = _dt.date.today().isoformat()
        sql += (" AND expected_return IS NOT NULL"
                  " AND expected_return < ?"
                  " AND status IN ('Reported','Confirmed','Active')")
        params.append(today)
    if date_from:
        _check_date("From", date_from)
        sql += " AND absence_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND absence_date <= ?"
        params.append(date_to)
    sql += " ORDER BY absence_date DESC, absence_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def absences_for_staff(staff_id: str) -> list[Absence]:
    return list_absences(staff_id=staff_id)


# ── Workflow ──────────────────────────────────────────────

def _to_dict(a: Absence) -> dict[str, Any]:
    return {
        "staff_id": a.staff_id,
        "absence_date": a.absence_date,
        "expected_return": a.expected_return,
        "actual_return": a.actual_return,
        "absence_type": a.absence_type,
        "reason": a.reason,
        "notified_on": a.notified_on,
        "notification_method": a.notification_method,
        "notified_by": a.notified_by,
        "certificate_type": a.certificate_type,
        "cert_received_on": a.cert_received_on,
        "cover_required": a.cover_required,
        "cover_source": a.cover_source,
        "cover_arranged_by": a.cover_arranged_by,
        "cover_notes": a.cover_notes,
        "critical": a.critical,
        "parents_informed": a.parents_informed,
        "slt_informed": a.slt_informed,
        "rtw_required": a.rtw_required,
        "rtw_meeting_on": a.rtw_meeting_on,
        "rtw_completed_by": a.rtw_completed_by,
        "days_lost": a.days_lost,
        "status": a.status,
        "notes": a.notes,
    }


def confirm_absence(absence_id: int) -> Absence:
    a = get_absence(absence_id)
    if a is None:
        raise ValidationError(f"No absence with id {absence_id}")
    data = _to_dict(a)
    data["status"] = "Active" if a.status == "Reported" \
        else "Confirmed"
    return update_absence(absence_id, data)


def arrange_cover(absence_id: int, *,
                       source: str,
                       arranged_by: str | None = None,
                       notes: str | None = None) -> Absence:
    if source not in COVER_SOURCES:
        raise ValidationError(
            f"Cover source must be one of: "
            f"{', '.join(COVER_SOURCES)}")
    a = get_absence(absence_id)
    if a is None:
        raise ValidationError(f"No absence with id {absence_id}")
    data = _to_dict(a)
    data["cover_source"] = source
    if arranged_by:
        data["cover_arranged_by"] = arranged_by
    if notes:
        data["cover_notes"] = notes
    return update_absence(absence_id, data)


def record_return(absence_id: int, *,
                       returned_on: str | None = None,
                       days_lost: float | None = None
                       ) -> Absence:
    a = get_absence(absence_id)
    if a is None:
        raise ValidationError(f"No absence with id {absence_id}")
    data = _to_dict(a)
    data["actual_return"] = (returned_on
                                  or _dt.date.today().isoformat())
    if days_lost is not None:
        data["days_lost"] = days_lost
    else:
        # Auto-calc business days assumed not — just calendar diff
        try:
            start = _dt.date.fromisoformat(a.absence_date)
            end = _dt.date.fromisoformat(data["actual_return"])
            data["days_lost"] = (end - start).days or 1
        except ValueError:
            pass
    data["status"] = "Returned"
    return update_absence(absence_id, data)


def complete_rtw(absence_id: int, *,
                      completed_by: str,
                      meeting_on: str | None = None
                      ) -> Absence:
    if not completed_by:
        raise ValidationError("Completed-by is required")
    a = get_absence(absence_id)
    if a is None:
        raise ValidationError(f"No absence with id {absence_id}")
    data = _to_dict(a)
    data["rtw_completed_by"] = completed_by
    data["rtw_meeting_on"] = (meeting_on
                                  or _dt.date.today().isoformat())
    return update_absence(absence_id, data)


def close_absence(absence_id: int) -> Absence:
    a = get_absence(absence_id)
    if a is None:
        raise ValidationError(f"No absence with id {absence_id}")
    return update_absence(absence_id,
                              {**_to_dict(a), "status": "Closed"})


def cancel_absence(absence_id: int) -> Absence:
    a = get_absence(absence_id)
    if a is None:
        raise ValidationError(f"No absence with id {absence_id}")
    return update_absence(absence_id,
                              {**_to_dict(a),
                                "status": "Cancelled"})


def set_status(absence_id: int, new_status: str) -> Absence:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    a = get_absence(absence_id)
    if a is None:
        raise ValidationError(f"No absence with id {absence_id}")
    return update_absence(absence_id,
                              {**_to_dict(a),
                                "status": new_status})


# ── Summary ───────────────────────────────────────────────

def summary() -> AbsenceSummary:
    rows = list_absences()
    out = AbsenceSummary(total=len(rows))
    if not rows:
        return out
    today = _dt.date.today().isoformat()
    rtw_cutoff = (_dt.date.today()
                       - _dt.timedelta(days=7)).isoformat()
    staff: set[str] = set()
    for a in rows:
        staff.add(a.staff_id)
        if a.is_open:
            out.open_count += 1
            if a.parents_informed is False:
                pass  # not tracked here
            if (a.absence_date <= today
                    and (a.actual_return is None
                          or a.actual_return >= today)):
                out.active_today += 1
            if (a.cover_required
                    and a.cover_source == "Pending"):
                out.cover_outstanding += 1
            if a.critical:
                out.critical_open += 1
            if (a.certificate_type == "Self-Cert"
                    and not a.cert_received_on
                    and a.days_lost
                    and a.days_lost > 7):
                out.awaiting_cert += 1
            if (a.expected_return
                    and a.expected_return < today):
                out.return_overdue += 1
            if not a.parents_informed:
                out.parents_pending += 1
        if (a.rtw_required and not a.rtw_meeting_on
                and a.status == "Returned"
                and a.actual_return
                and a.actual_return < rtw_cutoff):
            out.rtw_overdue += 1
        if a.days_lost:
            out.total_days_lost += a.days_lost
        out.by_type[a.absence_type] = (
            out.by_type.get(a.absence_type, 0) + 1)
        out.by_status[a.status] = (
            out.by_status.get(a.status, 0) + 1)
        out.by_cover_source[a.cover_source] = (
            out.by_cover_source.get(a.cover_source, 0) + 1)
    out.distinct_staff = len(staff)
    out.total_days_lost = round(out.total_days_lost, 1)
    return out


__all__ = [
    "ABSENCE_TYPES", "DEFAULT_ABSENCE_TYPE",
    "NOTIFICATION_METHODS", "DEFAULT_NOTIFICATION_METHOD",
    "CERTIFICATE_TYPES", "DEFAULT_CERTIFICATE_TYPE",
    "COVER_SOURCES", "DEFAULT_COVER_SOURCE",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Absence", "AbsenceSummary",
    "init_db",
    "create_absence", "update_absence", "delete_absence",
    "get_absence", "list_absences", "absences_for_staff",
    "confirm_absence", "arrange_cover", "record_return",
    "complete_rtw", "close_absence", "cancel_absence",
    "set_status",
    "summary",
]
