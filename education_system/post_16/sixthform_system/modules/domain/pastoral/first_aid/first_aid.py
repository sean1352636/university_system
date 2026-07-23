"""First Aid data layer for Sixth Form System.

One row per first aid incident. Student is required and FK-cascade
on student delete. Captures nature, severity, first-aider,
treatment, ambulance/hospital/parent flags, and a parent-informed +
follow-up workflow.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.post_16.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

NATURES: tuple[str, ...] = (
    "Headache / Migraine",
    "Head Bump",
    "Cut / Graze",
    "Bruise",
    "Sprain / Strain",
    "Fracture (suspected)",
    "Burn / Scald",
    "Nosebleed",
    "Allergic Reaction",
    "Anaphylaxis",
    "Asthma Attack",
    "Fainting / Dizziness",
    "Seizure",
    "Diabetic Episode",
    "Panic Attack",
    "Insect Sting / Bite",
    "Eye Injury",
    "Dental",
    "Stomach / Nausea",
    "Period Pain",
    "Other",
)
DEFAULT_NATURE = "Other"

SEVERITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_SEVERITY_LABELS = {
    1: "Minor", 2: "Mild", 3: "Moderate",
    4: "Serious", 5: "Critical",
}


def severity_label(s: int | None) -> str:
    if s is None:
        return "—"
    return _SEVERITY_LABELS.get(s, "Unknown")


STATUSES: tuple[str, ...] = (
    "Recorded",
    "Treated",
    "Parent Informed",
    "Follow-Up Pending",
    "Closed",
)
DEFAULT_STATUS = "Recorded"


class ValidationError(Exception):
    pass


@dataclass
class Incident:
    incident_id: int
    student_id: str
    incident_date: str
    incident_time: str | None
    location: str | None
    nature: str
    severity: int
    description: str | None
    first_aider: str
    treatment_given: str | None
    ambulance_called: bool
    hospital_referral: bool
    sent_home: bool
    parent_informed: bool
    parent_informed_on: str | None
    follow_up_required: bool
    follow_up_due: str | None
    follow_up_notes: str | None
    accident_book_ref: str | None
    status: str
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status != "Closed"

    @property
    def severity_label(self) -> str:
        return severity_label(self.severity)

    @property
    def follow_up_overdue(self) -> bool:
        if (not self.is_open or not self.follow_up_required
                or not self.follow_up_due):
            return False
        return self.follow_up_due < _dt.date.today().isoformat()


@dataclass
class FirstAidSummary:
    total: int = 0
    open_count: int = 0
    serious_or_critical: int = 0
    ambulance_called: int = 0
    sent_home: int = 0
    parent_pending: int = 0
    follow_up_pending: int = 0
    follow_up_overdue: int = 0
    distinct_students: int = 0
    average_severity: float | None = None
    by_nature: dict[str, int] = field(default_factory=dict)
    by_severity: dict[int, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.FIRST_AID_DB)
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
            CREATE TABLE IF NOT EXISTS first_aid_incidents (
                incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                incident_date TEXT NOT NULL,
                incident_time TEXT,
                location TEXT,
                nature TEXT NOT NULL,
                severity INTEGER NOT NULL,
                description TEXT,
                first_aider TEXT NOT NULL,
                treatment_given TEXT,
                ambulance_called INTEGER NOT NULL DEFAULT 0,
                hospital_referral INTEGER NOT NULL DEFAULT 0,
                sent_home INTEGER NOT NULL DEFAULT 0,
                parent_informed INTEGER NOT NULL DEFAULT 0,
                parent_informed_on TEXT,
                follow_up_required INTEGER NOT NULL DEFAULT 0,
                follow_up_due TEXT,
                follow_up_notes TEXT,
                accident_book_ref TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES students(student_id)
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


def _check_time(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.time.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be HH:MM")


def _student_exists(student_id: str) -> bool:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id=?",
                (student_id,)).fetchone()
        except sqlite3.OperationalError:
            return False
    return row is not None


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["student_id"] = (out.get("student_id") or "").strip()
    if not out["student_id"]:
        raise ValidationError("Student is required")
    if not _student_exists(out["student_id"]):
        raise ValidationError(
            f"No student with id {out['student_id']}")

    out["incident_date"] = (out.get("incident_date") or "").strip()
    if not out["incident_date"]:
        raise ValidationError("Incident date is required")
    _check_date("Incident date", out["incident_date"])
    _check_time("Incident time", out.get("incident_time"))
    _check_date("Parent informed", out.get("parent_informed_on"))
    _check_date("Follow-up due",   out.get("follow_up_due"))

    nature = (out.get("nature") or "").strip()
    if nature not in NATURES:
        raise ValidationError(
            f"Nature must be one of: {', '.join(NATURES)}")
    out["nature"] = nature

    try:
        sev = int(out.get("severity") or 1)
    except (TypeError, ValueError):
        raise ValidationError("Severity must be 1-5")
    if sev not in SEVERITIES:
        raise ValidationError("Severity must be 1-5")
    out["severity"] = sev

    out["first_aider"] = (out.get("first_aider") or "").strip()
    if not out["first_aider"]:
        raise ValidationError("First aider is required")

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("location", "description", "treatment_given",
               "follow_up_notes", "accident_book_ref", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("incident_time", "parent_informed_on",
               "follow_up_due"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v

    for k in ("ambulance_called", "hospital_referral", "sent_home",
               "parent_informed", "follow_up_required"):
        out[k] = bool(out.get(k))

    if out["follow_up_required"] and not out["follow_up_due"]:
        # not fatal — allow blank due date
        pass
    return out


def _row(r: sqlite3.Row) -> Incident:
    return Incident(
        incident_id=r["incident_id"],
        student_id=r["student_id"],
        incident_date=r["incident_date"],
        incident_time=r["incident_time"],
        location=r["location"],
        nature=r["nature"],
        severity=r["severity"],
        description=r["description"],
        first_aider=r["first_aider"],
        treatment_given=r["treatment_given"],
        ambulance_called=bool(r["ambulance_called"]),
        hospital_referral=bool(r["hospital_referral"]),
        sent_home=bool(r["sent_home"]),
        parent_informed=bool(r["parent_informed"]),
        parent_informed_on=r["parent_informed_on"],
        follow_up_required=bool(r["follow_up_required"]),
        follow_up_due=r["follow_up_due"],
        follow_up_notes=r["follow_up_notes"],
        accident_book_ref=r["accident_book_ref"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_incident(payload: dict[str, Any]) -> Incident:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO first_aid_incidents (
              student_id, incident_date, incident_time, location,
              nature, severity, description, first_aider,
              treatment_given, ambulance_called, hospital_referral,
              sent_home, parent_informed, parent_informed_on,
              follow_up_required, follow_up_due, follow_up_notes,
              accident_book_ref, status, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["student_id"], p["incident_date"],
            p["incident_time"], p["location"],
            p["nature"], p["severity"], p["description"],
            p["first_aider"], p["treatment_given"],
            1 if p["ambulance_called"] else 0,
            1 if p["hospital_referral"] else 0,
            1 if p["sent_home"] else 0,
            1 if p["parent_informed"] else 0,
            p["parent_informed_on"],
            1 if p["follow_up_required"] else 0,
            p["follow_up_due"], p["follow_up_notes"],
            p["accident_book_ref"], p["status"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_incident(new_id)


def update_incident(incident_id: int,
                       payload: dict[str, Any]) -> Incident:
    init_db()
    if get_incident(incident_id) is None:
        raise ValidationError(f"No incident with id {incident_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE first_aid_incidents SET
              student_id=?, incident_date=?, incident_time=?,
              location=?, nature=?, severity=?, description=?,
              first_aider=?, treatment_given=?,
              ambulance_called=?, hospital_referral=?, sent_home=?,
              parent_informed=?, parent_informed_on=?,
              follow_up_required=?, follow_up_due=?,
              follow_up_notes=?, accident_book_ref=?,
              status=?, notes=?, updated_on=?
            WHERE incident_id=?
        """, (
            p["student_id"], p["incident_date"],
            p["incident_time"], p["location"],
            p["nature"], p["severity"], p["description"],
            p["first_aider"], p["treatment_given"],
            1 if p["ambulance_called"] else 0,
            1 if p["hospital_referral"] else 0,
            1 if p["sent_home"] else 0,
            1 if p["parent_informed"] else 0,
            p["parent_informed_on"],
            1 if p["follow_up_required"] else 0,
            p["follow_up_due"], p["follow_up_notes"],
            p["accident_book_ref"], p["status"], p["notes"],
            now, incident_id,
        ))
    return get_incident(incident_id)


def delete_incident(incident_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM first_aid_incidents WHERE incident_id=?",
            (incident_id,))
        return cur.rowcount > 0


def get_incident(incident_id: int) -> Incident | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM first_aid_incidents WHERE incident_id=?",
            (incident_id,)).fetchone()
        return _row(r) if r else None


def list_incidents(*,
                       student_id: str | None = None,
                       nature: str | None = None,
                       status: str | None = None,
                       severity: int | None = None,
                       severity_min: int | None = None,
                       first_aider_like: str | None = None,
                       location_like: str | None = None,
                       open_only: bool = False,
                       parent_pending: bool = False,
                       follow_up_pending: bool = False,
                       follow_up_overdue: bool = False,
                       ambulance_only: bool = False,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       ) -> list[Incident]:
    init_db()
    sql = "SELECT * FROM first_aid_incidents WHERE 1=1"
    params: list[Any] = []
    if student_id:
        sql += " AND student_id=?"
        params.append(student_id)
    if nature:
        sql += " AND nature=?"
        params.append(nature)
    if status:
        sql += " AND status=?"
        params.append(status)
    if severity is not None:
        sql += " AND severity=?"
        params.append(severity)
    if severity_min is not None:
        sql += " AND severity >= ?"
        params.append(severity_min)
    if first_aider_like:
        sql += " AND first_aider LIKE ?"
        params.append(f"%{first_aider_like}%")
    if location_like:
        sql += " AND location LIKE ?"
        params.append(f"%{location_like}%")
    if open_only:
        sql += " AND status != 'Closed'"
    if parent_pending:
        sql += (" AND parent_informed=0"
                  " AND status != 'Closed'")
    if follow_up_pending:
        sql += (" AND follow_up_required=1"
                  " AND status != 'Closed'")
    if follow_up_overdue:
        today = _dt.date.today().isoformat()
        sql += (" AND follow_up_required=1"
                  " AND follow_up_due IS NOT NULL"
                  " AND follow_up_due < ?"
                  " AND status != 'Closed'")
        params.append(today)
    if ambulance_only:
        sql += " AND ambulance_called=1"
    if date_from:
        _check_date("From", date_from)
        sql += " AND incident_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND incident_date <= ?"
        params.append(date_to)
    sql += (" ORDER BY incident_date DESC, "
              " incident_time DESC, incident_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


def incidents_for_student(student_id: str) -> list[Incident]:
    return list_incidents(student_id=student_id)


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(i: Incident) -> dict[str, Any]:
    return {
        "student_id": i.student_id,
        "incident_date": i.incident_date,
        "incident_time": i.incident_time,
        "location": i.location,
        "nature": i.nature,
        "severity": i.severity,
        "description": i.description,
        "first_aider": i.first_aider,
        "treatment_given": i.treatment_given,
        "ambulance_called": i.ambulance_called,
        "hospital_referral": i.hospital_referral,
        "sent_home": i.sent_home,
        "parent_informed": i.parent_informed,
        "parent_informed_on": i.parent_informed_on,
        "follow_up_required": i.follow_up_required,
        "follow_up_due": i.follow_up_due,
        "follow_up_notes": i.follow_up_notes,
        "accident_book_ref": i.accident_book_ref,
        "status": i.status,
        "notes": i.notes,
    }


def inform_parent(incident_id: int, *,
                      informed_on: str | None = None) -> Incident:
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["parent_informed"] = True
    data["parent_informed_on"] = (
        informed_on or _dt.date.today().isoformat())
    if i.status in ("Recorded", "Treated"):
        data["status"] = "Parent Informed"
    return update_incident(incident_id, data)


def mark_follow_up_complete(incident_id: int, *,
                                  notes: str | None = None
                                  ) -> Incident:
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["follow_up_required"] = False
    if notes:
        existing = data["follow_up_notes"] or ""
        prefix = (existing + "\n") if existing else ""
        data["follow_up_notes"] = (
            prefix + f"{_dt.date.today().isoformat()}: {notes}")
    return update_incident(incident_id, data)


def close_incident(incident_id: int) -> Incident:
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["status"] = "Closed"
    return update_incident(incident_id, data)


def set_status(incident_id: int, new_status: str) -> Incident:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    return update_incident(incident_id,
                                {**_to_dict(i), "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> FirstAidSummary:
    rows = list_incidents()
    out = FirstAidSummary(total=len(rows))
    if not rows:
        return out
    s_total = 0
    students: set[str] = set()
    today = _dt.date.today().isoformat()
    for i in rows:
        students.add(i.student_id)
        s_total += i.severity
        if i.is_open:
            out.open_count += 1
            if not i.parent_informed:
                out.parent_pending += 1
            if i.follow_up_required:
                out.follow_up_pending += 1
                if (i.follow_up_due
                        and i.follow_up_due < today):
                    out.follow_up_overdue += 1
        if i.severity >= 4:
            out.serious_or_critical += 1
        if i.ambulance_called:
            out.ambulance_called += 1
        if i.sent_home:
            out.sent_home += 1
        out.by_nature[i.nature] = (
            out.by_nature.get(i.nature, 0) + 1)
        out.by_severity[i.severity] = (
            out.by_severity.get(i.severity, 0) + 1)
        out.by_status[i.status] = (
            out.by_status.get(i.status, 0) + 1)
    out.distinct_students = len(students)
    out.average_severity = round(s_total / len(rows), 2)
    return out


__all__ = [
    "NATURES", "DEFAULT_NATURE",
    "SEVERITIES", "severity_label",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Incident", "FirstAidSummary",
    "init_db",
    "create_incident", "update_incident", "delete_incident",
    "get_incident", "list_incidents", "incidents_for_student",
    "inform_parent", "mark_follow_up_complete",
    "close_incident", "set_status",
    "summary",
]
