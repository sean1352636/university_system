"""CPD data layer for Primary School System.

Two tables:
- `cpd_activities`: catalogue of CPD activities (internal /
  external / online / conference / course) with provider, date,
  hours, cost and certificated flag.
- `cpd_records`: per-staff attendance / completion record.
  FK cascade on activity delete and on staff delete. Captures
  hours completed, evaluation rating (1-5), impact-on-practice
  notes and certificate filing status.
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

ACTIVITY_TYPES: tuple[str, ...] = (
    "Internal Training",
    "External Course",
    "Online Course",
    "Webinar",
    "Conference",
    "Seminar",
    "Workshop",
    "Twilight",
    "INSET Day",
    "Coaching / Mentoring",
    "Reading / Research",
    "Cross-School Visit",
    "Qualification",
    "Other",
)
DEFAULT_ACTIVITY_TYPE = "Internal Training"

ACTIVITY_STATUSES: tuple[str, ...] = (
    "Planned",
    "Confirmed",
    "Open for Booking",
    "Cancelled",
    "Completed",
    "Archived",
)
DEFAULT_ACTIVITY_STATUS = "Planned"

RECORD_STATUSES: tuple[str, ...] = (
    "Booked",
    "Confirmed",
    "Attended",
    "Completed",
    "Cancelled",
    "No-Show",
    "Declined",
)
DEFAULT_RECORD_STATUS = "Booked"

RATINGS: tuple[int, ...] = (1, 2, 3, 4, 5)
_RATING_LABELS = {
    1: "Poor", 2: "Below Expectation", 3: "Good",
    4: "Very Good", 5: "Excellent",
}


def rating_label(r: int | None) -> str:
    if r is None:
        return "—"
    return _RATING_LABELS.get(r, "Unknown")


class ValidationError(Exception):
    pass


@dataclass
class Activity:
    activity_id: int
    title: str
    provider: str | None
    activity_type: str
    activity_date: str
    end_date: str | None
    hours: float | None
    cost: float | None
    certificated: bool
    accreditor: str | None
    location: str | None
    capacity: int | None
    organiser: str | None
    description: str | None
    outcomes: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status not in ("Cancelled", "Archived")

    @property
    def is_completed(self) -> bool:
        return self.status == "Completed"


@dataclass
class Record:
    record_id: int
    activity_id: int | None
    activity_title_cache: str | None
    staff_id: str
    booked_on: str
    attended_on: str | None
    hours_completed: float | None
    evaluation_rating: int | None
    evaluation_notes: str | None
    impact_on_practice: str | None
    certificate_received: bool
    certificate_filed: bool
    certificate_ref: str | None
    cost_to_staff: float | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status in ("Booked", "Confirmed",
                                       "Attended")

    @property
    def is_completed(self) -> bool:
        return self.status == "Completed"


@dataclass
class CPDSummary:
    total_activities: int = 0
    upcoming_activities: int = 0
    completed_activities: int = 0
    total_records: int = 0
    completed_records: int = 0
    total_hours_logged: float = 0.0
    awaiting_certificate: int = 0
    distinct_staff: int = 0
    average_rating: float | None = None
    by_activity_type: dict[str, int] = field(default_factory=dict)
    by_activity_status: dict[str, int] = field(default_factory=dict)
    by_record_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.CPD_DB)
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
            CREATE TABLE IF NOT EXISTS cpd_activities (
                activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                provider TEXT,
                activity_type TEXT NOT NULL,
                activity_date TEXT NOT NULL,
                end_date TEXT,
                hours REAL,
                cost REAL,
                certificated INTEGER NOT NULL DEFAULT 0,
                accreditor TEXT,
                location TEXT,
                capacity INTEGER,
                organiser TEXT,
                description TEXT,
                outcomes TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cpd_records (
                record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id INTEGER,
                staff_id TEXT NOT NULL,
                booked_on TEXT NOT NULL,
                attended_on TEXT,
                hours_completed REAL,
                evaluation_rating INTEGER,
                evaluation_notes TEXT,
                impact_on_practice TEXT,
                certificate_received INTEGER NOT NULL DEFAULT 0,
                certificate_filed INTEGER NOT NULL DEFAULT 0,
                certificate_ref TEXT,
                cost_to_staff REAL,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(activity_id)
                  REFERENCES cpd_activities(activity_id)
                  ON DELETE SET NULL,
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


# ── Activities ──────────────────────────────────────────

def _validate_activity(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")
    at = (out.get("activity_type")
            or DEFAULT_ACTIVITY_TYPE).strip()
    if at not in ACTIVITY_TYPES:
        raise ValidationError(
            f"Activity type must be one of: "
            f"{', '.join(ACTIVITY_TYPES)}")
    out["activity_type"] = at

    out["activity_date"] = (out.get("activity_date") or "").strip()
    if not out["activity_date"]:
        raise ValidationError("Activity date is required")
    _check_date("Activity date", out["activity_date"])
    _check_date("End date",      out.get("end_date"))
    if (out.get("end_date")
            and out["end_date"] < out["activity_date"]):
        raise ValidationError(
            "End date must be on or after activity date")

    status = (out.get("status") or DEFAULT_ACTIVITY_STATUS).strip()
    if status not in ACTIVITY_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ACTIVITY_STATUSES)}")
    out["status"] = status

    for k in ("provider", "accreditor", "location",
               "organiser", "description", "outcomes", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("end_date",):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v

    for key in ("hours", "cost"):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None
        else:
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key} must be a number")
            if out[key] < 0:
                raise ValidationError(f"{key} must be >= 0")
    cap = out.get("capacity")
    if cap in (None, ""):
        out["capacity"] = None
    else:
        try:
            out["capacity"] = int(cap)
        except (TypeError, ValueError):
            raise ValidationError("Capacity must be an integer")
        if out["capacity"] < 0:
            raise ValidationError("Capacity must be >= 0")
    out["certificated"] = bool(out.get("certificated"))
    return out


def _row_activity(r: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=r["activity_id"],
        title=r["title"],
        provider=r["provider"],
        activity_type=r["activity_type"],
        activity_date=r["activity_date"],
        end_date=r["end_date"],
        hours=r["hours"],
        cost=r["cost"],
        certificated=bool(r["certificated"]),
        accreditor=r["accreditor"],
        location=r["location"],
        capacity=r["capacity"],
        organiser=r["organiser"],
        description=r["description"],
        outcomes=r["outcomes"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_activity(payload: dict[str, Any]) -> Activity:
    init_db()
    p = _validate_activity(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO cpd_activities (
              title, provider, activity_type,
              activity_date, end_date, hours, cost,
              certificated, accreditor, location, capacity,
              organiser, description, outcomes,
              status, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?)
        """, (
            p["title"], p["provider"], p["activity_type"],
            p["activity_date"], p["end_date"], p["hours"],
            p["cost"], 1 if p["certificated"] else 0,
            p["accreditor"], p["location"], p["capacity"],
            p["organiser"], p["description"], p["outcomes"],
            p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_activity(new_id)


def update_activity(activity_id: int,
                        payload: dict[str, Any]) -> Activity:
    init_db()
    if get_activity(activity_id) is None:
        raise ValidationError(
            f"No activity with id {activity_id}")
    p = _validate_activity(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE cpd_activities SET
              title=?, provider=?, activity_type=?,
              activity_date=?, end_date=?, hours=?, cost=?,
              certificated=?, accreditor=?, location=?,
              capacity=?, organiser=?, description=?, outcomes=?,
              status=?, notes=?, updated_on=?
            WHERE activity_id=?
        """, (
            p["title"], p["provider"], p["activity_type"],
            p["activity_date"], p["end_date"], p["hours"],
            p["cost"], 1 if p["certificated"] else 0,
            p["accreditor"], p["location"], p["capacity"],
            p["organiser"], p["description"], p["outcomes"],
            p["status"], p["notes"], now, activity_id,
        ))
    return get_activity(activity_id)


def delete_activity(activity_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM cpd_activities WHERE activity_id=?",
            (activity_id,))
        return cur.rowcount > 0


def get_activity(activity_id: int) -> Activity | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM cpd_activities WHERE activity_id=?",
            (activity_id,)).fetchone()
        return _row_activity(r) if r else None


def list_activities(*,
                         activity_type: str | None = None,
                         status: str | None = None,
                         provider_like: str | None = None,
                         title_like: str | None = None,
                         upcoming_only: bool = False,
                         completed_only: bool = False,
                         date_from: str | None = None,
                         date_to: str | None = None,
                         ) -> list[Activity]:
    init_db()
    sql = "SELECT * FROM cpd_activities WHERE 1=1"
    params: list[Any] = []
    if activity_type:
        sql += " AND activity_type=?"
        params.append(activity_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if provider_like:
        sql += " AND provider LIKE ?"
        params.append(f"%{provider_like}%")
    if title_like:
        sql += " AND title LIKE ?"
        params.append(f"%{title_like}%")
    if upcoming_only:
        today = _dt.date.today().isoformat()
        sql += (" AND activity_date >= ?"
                  " AND status NOT IN ('Cancelled','Archived')")
        params.append(today)
    if completed_only:
        sql += " AND status='Completed'"
    if date_from:
        _check_date("From", date_from)
        sql += " AND activity_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND activity_date <= ?"
        params.append(date_to)
    sql += " ORDER BY activity_date DESC, activity_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_activity(r) for r in rows]


def _to_activity_dict(a: Activity) -> dict[str, Any]:
    return {
        "title": a.title,
        "provider": a.provider,
        "activity_type": a.activity_type,
        "activity_date": a.activity_date,
        "end_date": a.end_date,
        "hours": a.hours,
        "cost": a.cost,
        "certificated": a.certificated,
        "accreditor": a.accreditor,
        "location": a.location,
        "capacity": a.capacity,
        "organiser": a.organiser,
        "description": a.description,
        "outcomes": a.outcomes,
        "status": a.status,
        "notes": a.notes,
    }


def mark_activity_completed(activity_id: int) -> Activity:
    a = get_activity(activity_id)
    if a is None:
        raise ValidationError(
            f"No activity with id {activity_id}")
    return update_activity(activity_id,
                                 {**_to_activity_dict(a),
                                   "status": "Completed"})


def set_activity_status(activity_id: int,
                              new_status: str) -> Activity:
    if new_status not in ACTIVITY_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ACTIVITY_STATUSES)}")
    a = get_activity(activity_id)
    if a is None:
        raise ValidationError(
            f"No activity with id {activity_id}")
    return update_activity(activity_id,
                                 {**_to_activity_dict(a),
                                   "status": new_status})


def record_count(activity_id: int) -> int:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM cpd_records "
            "WHERE activity_id=?", (activity_id,)).fetchone()
    return int(row["c"]) if row else 0


# ── Records ──────────────────────────────────────────────

def _validate_record(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["staff_id"] = (out.get("staff_id") or "").strip()
    if not out["staff_id"]:
        raise ValidationError("Staff is required")
    if not _staff_exists(out["staff_id"]):
        raise ValidationError(
            f"No staff with id {out['staff_id']}")

    aid = out.get("activity_id")
    if aid in (None, ""):
        out["activity_id"] = None
    else:
        try:
            out["activity_id"] = int(aid)
        except (TypeError, ValueError):
            raise ValidationError(
                "Activity id must be an integer")
        if get_activity(out["activity_id"]) is None:
            raise ValidationError(
                f"No activity with id {out['activity_id']}")

    out["booked_on"] = (out.get("booked_on") or "").strip()
    if not out["booked_on"]:
        out["booked_on"] = _dt.date.today().isoformat()
    _check_date("Booked on",   out["booked_on"])
    _check_date("Attended on", out.get("attended_on"))

    status = (out.get("status") or DEFAULT_RECORD_STATUS).strip()
    if status not in RECORD_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(RECORD_STATUSES)}")
    out["status"] = status

    rating = out.get("evaluation_rating")
    if rating in (None, ""):
        out["evaluation_rating"] = None
    else:
        try:
            rv = int(rating)
        except (TypeError, ValueError):
            raise ValidationError(
                "Evaluation rating must be 1-5")
        if rv not in RATINGS:
            raise ValidationError(
                "Evaluation rating must be 1-5")
        out["evaluation_rating"] = rv

    for key in ("hours_completed", "cost_to_staff"):
        v = out.get(key)
        if v in (None, ""):
            out[key] = None
        else:
            try:
                out[key] = float(v)
            except (TypeError, ValueError):
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be a number")
            if out[key] < 0:
                raise ValidationError(
                    f"{key.replace('_', ' ')} must be >= 0")

    for k in ("evaluation_notes", "impact_on_practice",
               "certificate_ref", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    out["attended_on"] = (
        (out.get("attended_on") or "").strip() or None
        if isinstance(out.get("attended_on"), str)
        else out.get("attended_on"))
    for k in ("certificate_received", "certificate_filed"):
        out[k] = bool(out.get(k))
    return out


def _row_record(r: sqlite3.Row) -> Record:
    return Record(
        record_id=r["record_id"],
        activity_id=r["activity_id"],
        activity_title_cache=(r["activity_title_cache"]
                                  if "activity_title_cache"
                                  in r.keys() else None),
        staff_id=r["staff_id"],
        booked_on=r["booked_on"],
        attended_on=r["attended_on"],
        hours_completed=r["hours_completed"],
        evaluation_rating=r["evaluation_rating"],
        evaluation_notes=r["evaluation_notes"],
        impact_on_practice=r["impact_on_practice"],
        certificate_received=bool(r["certificate_received"]),
        certificate_filed=bool(r["certificate_filed"]),
        certificate_ref=r["certificate_ref"],
        cost_to_staff=r["cost_to_staff"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


_RECORD_SELECT = """
    SELECT r.*, a.title AS activity_title_cache
    FROM cpd_records r
    LEFT JOIN cpd_activities a ON a.activity_id = r.activity_id
"""


def create_record(payload: dict[str, Any]) -> Record:
    init_db()
    p = _validate_record(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO cpd_records (
              activity_id, staff_id, booked_on, attended_on,
              hours_completed, evaluation_rating,
              evaluation_notes, impact_on_practice,
              certificate_received, certificate_filed,
              certificate_ref, cost_to_staff,
              status, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?)
        """, (
            p["activity_id"], p["staff_id"], p["booked_on"],
            p["attended_on"], p["hours_completed"],
            p["evaluation_rating"], p["evaluation_notes"],
            p["impact_on_practice"],
            1 if p["certificate_received"] else 0,
            1 if p["certificate_filed"] else 0,
            p["certificate_ref"], p["cost_to_staff"],
            p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_record(new_id)


def update_record(record_id: int,
                       payload: dict[str, Any]) -> Record:
    init_db()
    if get_record(record_id) is None:
        raise ValidationError(f"No record with id {record_id}")
    p = _validate_record(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE cpd_records SET
              activity_id=?, staff_id=?, booked_on=?,
              attended_on=?, hours_completed=?,
              evaluation_rating=?, evaluation_notes=?,
              impact_on_practice=?,
              certificate_received=?, certificate_filed=?,
              certificate_ref=?, cost_to_staff=?,
              status=?, notes=?, updated_on=?
            WHERE record_id=?
        """, (
            p["activity_id"], p["staff_id"], p["booked_on"],
            p["attended_on"], p["hours_completed"],
            p["evaluation_rating"], p["evaluation_notes"],
            p["impact_on_practice"],
            1 if p["certificate_received"] else 0,
            1 if p["certificate_filed"] else 0,
            p["certificate_ref"], p["cost_to_staff"],
            p["status"], p["notes"], now, record_id,
        ))
    return get_record(record_id)


def delete_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM cpd_records WHERE record_id=?",
            (record_id,))
        return cur.rowcount > 0


def get_record(record_id: int) -> Record | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            _RECORD_SELECT + " WHERE r.record_id=?",
            (record_id,)).fetchone()
        return _row_record(r) if r else None


def list_records(*,
                      staff_id: str | None = None,
                      activity_id: int | None = None,
                      status: str | None = None,
                      awaiting_certificate: bool = False,
                      completed_only: bool = False,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      ) -> list[Record]:
    init_db()
    sql = _RECORD_SELECT + " WHERE 1=1"
    params: list[Any] = []
    if staff_id:
        sql += " AND r.staff_id=?"
        params.append(staff_id)
    if activity_id is not None:
        sql += " AND r.activity_id=?"
        params.append(activity_id)
    if status:
        sql += " AND r.status=?"
        params.append(status)
    if awaiting_certificate:
        sql += (" AND r.certificate_received=0"
                  " AND r.status IN ('Attended','Completed')")
    if completed_only:
        sql += " AND r.status='Completed'"
    if date_from:
        _check_date("From", date_from)
        sql += " AND r.booked_on >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND r.booked_on <= ?"
        params.append(date_to)
    sql += " ORDER BY r.booked_on DESC, r.record_id DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_record(r) for r in rows]


def records_for_staff(staff_id: str) -> list[Record]:
    return list_records(staff_id=staff_id)


def _to_record_dict(r: Record) -> dict[str, Any]:
    return {
        "activity_id": r.activity_id,
        "staff_id": r.staff_id,
        "booked_on": r.booked_on,
        "attended_on": r.attended_on,
        "hours_completed": r.hours_completed,
        "evaluation_rating": r.evaluation_rating,
        "evaluation_notes": r.evaluation_notes,
        "impact_on_practice": r.impact_on_practice,
        "certificate_received": r.certificate_received,
        "certificate_filed": r.certificate_filed,
        "certificate_ref": r.certificate_ref,
        "cost_to_staff": r.cost_to_staff,
        "status": r.status,
        "notes": r.notes,
    }


def mark_attended(record_id: int, *,
                       attended_on: str | None = None,
                       hours: float | None = None
                       ) -> Record:
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No record with id {record_id}")
    data = _to_record_dict(r)
    data["attended_on"] = (attended_on
                                or _dt.date.today().isoformat())
    if hours is not None:
        data["hours_completed"] = hours
    data["status"] = "Attended"
    return update_record(record_id, data)


def record_evaluation(record_id: int, *,
                          rating: int | None = None,
                          notes: str | None = None,
                          impact: str | None = None
                          ) -> Record:
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No record with id {record_id}")
    data = _to_record_dict(r)
    if rating is not None:
        data["evaluation_rating"] = rating
    if notes is not None:
        data["evaluation_notes"] = notes
    if impact is not None:
        data["impact_on_practice"] = impact
    data["status"] = "Completed"
    return update_record(record_id, data)


def file_certificate(record_id: int, *,
                          ref: str | None = None) -> Record:
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No record with id {record_id}")
    data = _to_record_dict(r)
    data["certificate_received"] = True
    data["certificate_filed"] = True
    if ref:
        data["certificate_ref"] = ref
    return update_record(record_id, data)


def set_record_status(record_id: int,
                            new_status: str) -> Record:
    if new_status not in RECORD_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(RECORD_STATUSES)}")
    r = get_record(record_id)
    if r is None:
        raise ValidationError(f"No record with id {record_id}")
    return update_record(record_id,
                              {**_to_record_dict(r),
                                "status": new_status})


# ── Summary ──────────────────────────────────────────────

def summary() -> CPDSummary:
    activities = list_activities()
    records = list_records()
    out = CPDSummary(
        total_activities=len(activities),
        total_records=len(records),
    )
    today = _dt.date.today().isoformat()
    for a in activities:
        if (a.activity_date >= today
                and a.status not in ("Cancelled", "Archived")):
            out.upcoming_activities += 1
        if a.status == "Completed":
            out.completed_activities += 1
        out.by_activity_type[a.activity_type] = (
            out.by_activity_type.get(a.activity_type, 0) + 1)
        out.by_activity_status[a.status] = (
            out.by_activity_status.get(a.status, 0) + 1)

    ratings: list[int] = []
    staff: set[str] = set()
    for r in records:
        staff.add(r.staff_id)
        if r.status == "Completed":
            out.completed_records += 1
        if (r.status in ("Attended", "Completed")
                and not r.certificate_received):
            out.awaiting_certificate += 1
        if r.hours_completed:
            out.total_hours_logged += r.hours_completed
        if r.evaluation_rating is not None:
            ratings.append(r.evaluation_rating)
        out.by_record_status[r.status] = (
            out.by_record_status.get(r.status, 0) + 1)
    out.total_hours_logged = round(out.total_hours_logged, 2)
    out.distinct_staff = len(staff)
    if ratings:
        out.average_rating = round(
            sum(ratings) / len(ratings), 2)
    return out


__all__ = [
    "ACTIVITY_TYPES", "DEFAULT_ACTIVITY_TYPE",
    "ACTIVITY_STATUSES", "DEFAULT_ACTIVITY_STATUS",
    "RECORD_STATUSES", "DEFAULT_RECORD_STATUS",
    "RATINGS", "rating_label",
    "ValidationError",
    "Activity", "Record", "CPDSummary",
    "init_db",
    "create_activity", "update_activity", "delete_activity",
    "get_activity", "list_activities",
    "mark_activity_completed", "set_activity_status",
    "record_count",
    "create_record", "update_record", "delete_record",
    "get_record", "list_records", "records_for_staff",
    "mark_attended", "record_evaluation",
    "file_certificate", "set_record_status",
    "summary",
]
