"""Emergency Incidents data layer for Sixth Form System.

Site-wide emergency incidents: fire alarms, lockdowns, intruders,
medical emergencies, drills, weather closures, etc. Not tied to
individual students (use FK-free schema) — `students_affected` is
a free-text list. Workflow Reported → Responding → Resolved →
Debriefed → Closed. Includes a timeline log and post-incident
debrief / lessons-learned.

Per-student emergency contacts (added): ``emergency_contacts`` is a
priority-ordered call list per student. A row can point at a
``parent_contacts`` record (read only — names and numbers come from
there when linked) or hold a contact typed in here. When a student has
no list yet, :func:`emergency_contacts_for` falls back to parent
contacts flagged as emergency contacts, then the medical profile's
single emergency contact. ``emergency_contact_attempts`` logs every
call made in an emergency (who, number, time, outcome), optionally
against an incident.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system import paths as _paths
from education_system.systems.sixth_form.domain.pastoral import _records

logger = logging.getLogger(__name__)

EMERGENCY_TYPES: tuple[str, ...] = (
    "Fire Alarm",
    "Lockdown",
    "Intruder",
    "Medical Emergency",
    "Evacuation Drill",
    "Lockdown Drill",
    "Weather Closure",
    "Power Outage",
    "IT Outage",
    "Gas Leak",
    "Bomb Threat",
    "Critical Incident",
    "Bereavement",
    "Safeguarding Critical",
    "Other",
)
DEFAULT_EMERGENCY_TYPE = "Fire Alarm"

SEVERITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_SEVERITY_LABELS = {
    1: "Drill / Minor", 2: "Low", 3: "Moderate",
    4: "Major", 5: "Critical",
}


def severity_label(s: int | None) -> str:
    if s is None:
        return "—"
    return _SEVERITY_LABELS.get(s, "Unknown")


STATUSES: tuple[str, ...] = (
    "Reported",
    "Responding",
    "Resolved",
    "Debriefed",
    "Closed",
)
DEFAULT_STATUS = "Reported"


class ValidationError(Exception):
    pass


@dataclass
class Emergency:
    incident_id: int
    incident_date: str
    incident_time: str | None
    incident_type: str
    severity: int
    title: str
    description: str | None
    location: str | None
    reported_by: str
    lead_responder: str | None
    evacuation: bool
    lockdown: bool
    police_called: bool
    fire_called: bool
    ambulance_called: bool
    students_affected: str | None
    staff_affected: str | None
    parents_informed: bool
    governors_informed: bool
    incident_log: str | None
    actions_taken: str | None
    resolved_on: str | None
    resolved_time: str | None
    follow_up_required: bool
    follow_up_notes: str | None
    debrief_notes: str | None
    lessons_learned: str | None
    debriefed_on: str | None
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
    def services_called(self) -> bool:
        return (self.police_called or self.fire_called
                  or self.ambulance_called)


@dataclass
class EmergencySummary:
    total: int = 0
    open_count: int = 0
    major_or_critical: int = 0
    services_called: int = 0
    evacuations: int = 0
    lockdowns: int = 0
    drills: int = 0
    awaiting_debrief: int = 0
    average_severity: float | None = None
    by_type: dict[str, int] = field(default_factory=dict)
    by_severity: dict[int, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(_paths.SIXTH_FORM_EMERGENCY_DB)
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
            CREATE TABLE IF NOT EXISTS emergency_incidents (
                incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_date TEXT NOT NULL,
                incident_time TEXT,
                incident_type TEXT NOT NULL,
                severity INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                location TEXT,
                reported_by TEXT NOT NULL,
                lead_responder TEXT,
                evacuation INTEGER NOT NULL DEFAULT 0,
                lockdown INTEGER NOT NULL DEFAULT 0,
                police_called INTEGER NOT NULL DEFAULT 0,
                fire_called INTEGER NOT NULL DEFAULT 0,
                ambulance_called INTEGER NOT NULL DEFAULT 0,
                students_affected TEXT,
                staff_affected TEXT,
                parents_informed INTEGER NOT NULL DEFAULT 0,
                governors_informed INTEGER NOT NULL DEFAULT 0,
                incident_log TEXT,
                actions_taken TEXT,
                resolved_on TEXT,
                resolved_time TEXT,
                follow_up_required INTEGER NOT NULL DEFAULT 0,
                follow_up_notes TEXT,
                debrief_notes TEXT,
                lessons_learned TEXT,
                debriefed_on TEXT,
                status TEXT NOT NULL,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)
    _init_contacts()


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


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["incident_date"] = (out.get("incident_date") or "").strip()
    if not out["incident_date"]:
        raise ValidationError("Incident date is required")
    _check_date("Incident date", out["incident_date"])
    _check_time("Incident time", out.get("incident_time"))
    _check_date("Resolved on",   out.get("resolved_on"))
    _check_time("Resolved time", out.get("resolved_time"))
    _check_date("Debriefed on",  out.get("debriefed_on"))

    et = (out.get("incident_type") or "").strip()
    if et not in EMERGENCY_TYPES:
        raise ValidationError(
            f"Type must be one of: {', '.join(EMERGENCY_TYPES)}")
    out["incident_type"] = et

    try:
        sev = int(out.get("severity") or 2)
    except (TypeError, ValueError):
        raise ValidationError("Severity must be 1-5")
    if sev not in SEVERITIES:
        raise ValidationError("Severity must be 1-5")
    out["severity"] = sev

    out["title"] = (out.get("title") or "").strip()
    if not out["title"]:
        raise ValidationError("Title is required")

    out["reported_by"] = (out.get("reported_by") or "").strip()
    if not out["reported_by"]:
        raise ValidationError("Reported by is required")

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("description", "location", "lead_responder",
               "students_affected", "staff_affected",
               "incident_log", "actions_taken", "follow_up_notes",
               "debrief_notes", "lessons_learned", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("incident_time", "resolved_on", "resolved_time",
               "debriefed_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v

    for k in ("evacuation", "lockdown",
               "police_called", "fire_called", "ambulance_called",
               "parents_informed", "governors_informed",
               "follow_up_required"):
        out[k] = bool(out.get(k))
    return out


def _row(r: sqlite3.Row) -> Emergency:
    return Emergency(
        incident_id=r["incident_id"],
        incident_date=r["incident_date"],
        incident_time=r["incident_time"],
        incident_type=r["incident_type"],
        severity=r["severity"],
        title=r["title"],
        description=r["description"],
        location=r["location"],
        reported_by=r["reported_by"],
        lead_responder=r["lead_responder"],
        evacuation=bool(r["evacuation"]),
        lockdown=bool(r["lockdown"]),
        police_called=bool(r["police_called"]),
        fire_called=bool(r["fire_called"]),
        ambulance_called=bool(r["ambulance_called"]),
        students_affected=r["students_affected"],
        staff_affected=r["staff_affected"],
        parents_informed=bool(r["parents_informed"]),
        governors_informed=bool(r["governors_informed"]),
        incident_log=r["incident_log"],
        actions_taken=r["actions_taken"],
        resolved_on=r["resolved_on"],
        resolved_time=r["resolved_time"],
        follow_up_required=bool(r["follow_up_required"]),
        follow_up_notes=r["follow_up_notes"],
        debrief_notes=r["debrief_notes"],
        lessons_learned=r["lessons_learned"],
        debriefed_on=r["debriefed_on"],
        status=r["status"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_incident(payload: dict[str, Any]) -> Emergency:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO emergency_incidents (
              incident_date, incident_time, incident_type,
              severity, title, description, location,
              reported_by, lead_responder,
              evacuation, lockdown, police_called, fire_called,
              ambulance_called,
              students_affected, staff_affected,
              parents_informed, governors_informed,
              incident_log, actions_taken,
              resolved_on, resolved_time,
              follow_up_required, follow_up_notes,
              debrief_notes, lessons_learned, debriefed_on,
              status, notes, created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["incident_date"], p["incident_time"],
            p["incident_type"], p["severity"], p["title"],
            p["description"], p["location"],
            p["reported_by"], p["lead_responder"],
            1 if p["evacuation"] else 0,
            1 if p["lockdown"] else 0,
            1 if p["police_called"] else 0,
            1 if p["fire_called"] else 0,
            1 if p["ambulance_called"] else 0,
            p["students_affected"], p["staff_affected"],
            1 if p["parents_informed"] else 0,
            1 if p["governors_informed"] else 0,
            p["incident_log"], p["actions_taken"],
            p["resolved_on"], p["resolved_time"],
            1 if p["follow_up_required"] else 0,
            p["follow_up_notes"], p["debrief_notes"],
            p["lessons_learned"], p["debriefed_on"],
            p["status"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_incident(new_id)


def update_incident(incident_id: int,
                       payload: dict[str, Any]) -> Emergency:
    init_db()
    if get_incident(incident_id) is None:
        raise ValidationError(f"No incident with id {incident_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE emergency_incidents SET
              incident_date=?, incident_time=?, incident_type=?,
              severity=?, title=?, description=?, location=?,
              reported_by=?, lead_responder=?,
              evacuation=?, lockdown=?, police_called=?, fire_called=?,
              ambulance_called=?,
              students_affected=?, staff_affected=?,
              parents_informed=?, governors_informed=?,
              incident_log=?, actions_taken=?,
              resolved_on=?, resolved_time=?,
              follow_up_required=?, follow_up_notes=?,
              debrief_notes=?, lessons_learned=?, debriefed_on=?,
              status=?, notes=?, updated_on=?
            WHERE incident_id=?
        """, (
            p["incident_date"], p["incident_time"],
            p["incident_type"], p["severity"], p["title"],
            p["description"], p["location"],
            p["reported_by"], p["lead_responder"],
            1 if p["evacuation"] else 0,
            1 if p["lockdown"] else 0,
            1 if p["police_called"] else 0,
            1 if p["fire_called"] else 0,
            1 if p["ambulance_called"] else 0,
            p["students_affected"], p["staff_affected"],
            1 if p["parents_informed"] else 0,
            1 if p["governors_informed"] else 0,
            p["incident_log"], p["actions_taken"],
            p["resolved_on"], p["resolved_time"],
            1 if p["follow_up_required"] else 0,
            p["follow_up_notes"], p["debrief_notes"],
            p["lessons_learned"], p["debriefed_on"],
            p["status"], p["notes"], now, incident_id,
        ))
    return get_incident(incident_id)


def delete_incident(incident_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM emergency_incidents WHERE incident_id=?",
            (incident_id,))
        return cur.rowcount > 0


def get_incident(incident_id: int) -> Emergency | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM emergency_incidents WHERE incident_id=?",
            (incident_id,)).fetchone()
        return _row(r) if r else None


def list_incidents(*,
                       incident_type: str | None = None,
                       status: str | None = None,
                       severity: int | None = None,
                       severity_min: int | None = None,
                       open_only: bool = False,
                       awaiting_debrief: bool = False,
                       services_only: bool = False,
                       evacuation_only: bool = False,
                       lockdown_only: bool = False,
                       reported_by_like: str | None = None,
                       location_like: str | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       ) -> list[Emergency]:
    init_db()
    sql = "SELECT * FROM emergency_incidents WHERE 1=1"
    params: list[Any] = []
    if incident_type:
        sql += " AND incident_type=?"
        params.append(incident_type)
    if status:
        sql += " AND status=?"
        params.append(status)
    if severity is not None:
        sql += " AND severity=?"
        params.append(severity)
    if severity_min is not None:
        sql += " AND severity >= ?"
        params.append(severity_min)
    if open_only:
        sql += " AND status != 'Closed'"
    if awaiting_debrief:
        sql += " AND status = 'Resolved'"
    if services_only:
        sql += (" AND (police_called=1 OR fire_called=1"
                  " OR ambulance_called=1)")
    if evacuation_only:
        sql += " AND evacuation=1"
    if lockdown_only:
        sql += " AND lockdown=1"
    if reported_by_like:
        sql += " AND reported_by LIKE ?"
        params.append(f"%{reported_by_like}%")
    if location_like:
        sql += " AND location LIKE ?"
        params.append(f"%{location_like}%")
    if date_from:
        _check_date("From", date_from)
        sql += " AND incident_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND incident_date <= ?"
        params.append(date_to)
    sql += (" ORDER BY incident_date DESC,"
              " incident_time DESC, incident_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(e: Emergency) -> dict[str, Any]:
    return {
        "incident_date": e.incident_date,
        "incident_time": e.incident_time,
        "incident_type": e.incident_type,
        "severity": e.severity,
        "title": e.title,
        "description": e.description,
        "location": e.location,
        "reported_by": e.reported_by,
        "lead_responder": e.lead_responder,
        "evacuation": e.evacuation,
        "lockdown": e.lockdown,
        "police_called": e.police_called,
        "fire_called": e.fire_called,
        "ambulance_called": e.ambulance_called,
        "students_affected": e.students_affected,
        "staff_affected": e.staff_affected,
        "parents_informed": e.parents_informed,
        "governors_informed": e.governors_informed,
        "incident_log": e.incident_log,
        "actions_taken": e.actions_taken,
        "resolved_on": e.resolved_on,
        "resolved_time": e.resolved_time,
        "follow_up_required": e.follow_up_required,
        "follow_up_notes": e.follow_up_notes,
        "debrief_notes": e.debrief_notes,
        "lessons_learned": e.lessons_learned,
        "debriefed_on": e.debriefed_on,
        "status": e.status,
        "notes": e.notes,
    }


def append_log(incident_id: int, *, entry: str) -> Emergency:
    if not entry:
        raise ValidationError("Log entry is required")
    e = get_incident(incident_id)
    if e is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(e)
    stamp = _dt.datetime.now().isoformat(timespec="minutes")
    existing = data["incident_log"] or ""
    prefix = (existing + "\n") if existing else ""
    data["incident_log"] = prefix + f"{stamp}  {entry}"
    return update_incident(incident_id, data)


def start_response(incident_id: int, *,
                       lead_responder: str | None = None
                       ) -> Emergency:
    e = get_incident(incident_id)
    if e is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(e)
    data["status"] = "Responding"
    if lead_responder:
        data["lead_responder"] = lead_responder
    return update_incident(incident_id, data)


def resolve(incident_id: int, *,
                actions_taken: str | None = None,
                resolved_on: str | None = None,
                resolved_time: str | None = None
                ) -> Emergency:
    e = get_incident(incident_id)
    if e is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(e)
    data["status"] = "Resolved"
    data["resolved_on"] = (resolved_on
                                or _dt.date.today().isoformat())
    if resolved_time:
        data["resolved_time"] = resolved_time
    if actions_taken:
        data["actions_taken"] = actions_taken
    return update_incident(incident_id, data)


def record_debrief(incident_id: int, *,
                       debrief_notes: str,
                       lessons_learned: str | None = None,
                       debriefed_on: str | None = None
                       ) -> Emergency:
    if not debrief_notes:
        raise ValidationError("Debrief notes are required")
    e = get_incident(incident_id)
    if e is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(e)
    data["status"] = "Debriefed"
    data["debrief_notes"] = debrief_notes
    if lessons_learned:
        data["lessons_learned"] = lessons_learned
    data["debriefed_on"] = (debriefed_on
                                 or _dt.date.today().isoformat())
    return update_incident(incident_id, data)


def close_incident(incident_id: int) -> Emergency:
    e = get_incident(incident_id)
    if e is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(e)
    data["status"] = "Closed"
    return update_incident(incident_id, data)


def set_status(incident_id: int, new_status: str) -> Emergency:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    e = get_incident(incident_id)
    if e is None:
        raise ValidationError(f"No incident with id {incident_id}")
    return update_incident(incident_id,
                                {**_to_dict(e), "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> EmergencySummary:
    rows = list_incidents()
    out = EmergencySummary(total=len(rows))
    if not rows:
        return out
    s_total = 0
    for e in rows:
        s_total += e.severity
        if e.is_open:
            out.open_count += 1
        if e.severity >= 4:
            out.major_or_critical += 1
        if e.services_called:
            out.services_called += 1
        if e.evacuation:
            out.evacuations += 1
        if e.lockdown:
            out.lockdowns += 1
        if e.incident_type in ("Evacuation Drill",
                                       "Lockdown Drill"):
            out.drills += 1
        if e.status == "Resolved":
            out.awaiting_debrief += 1
        out.by_type[e.incident_type] = (
            out.by_type.get(e.incident_type, 0) + 1)
        out.by_severity[e.severity] = (
            out.by_severity.get(e.severity, 0) + 1)
        out.by_status[e.status] = (
            out.by_status.get(e.status, 0) + 1)
    out.average_severity = round(s_total / len(rows), 2)
    return out


__all__ = [
    "EMERGENCY_TYPES", "DEFAULT_EMERGENCY_TYPE",
    "SEVERITIES", "severity_label",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "Emergency", "EmergencySummary",
    "init_db",
    "create_incident", "update_incident", "delete_incident",
    "get_incident", "list_incidents",
    "append_log", "start_response", "resolve",
    "record_debrief", "close_incident", "set_status",
    "summary",
    # Per-student emergency contacts + contact-attempt log
    "ATTEMPT_METHODS", "ATTEMPT_OUTCOMES", "SUCCESSFUL_OUTCOMES",
    "EmergencyContact", "ContactAttempt", "CallListEntry",
    "CONTACT_SPEC", "ATTEMPT_SPEC",
    "add_contact", "get_contact", "list_contacts", "update_contact",
    "delete_contact", "move_contact", "import_parent_contacts",
    "emergency_contacts_for", "log_attempt", "list_attempts",
    "update_attempt", "delete_attempt", "call_sheet", "CallSheetLine",
]


# ══ Per-student emergency contacts and contact-attempt log ════════

ATTEMPT_METHODS: tuple[str, ...] = (
    "Phone call", "SMS", "E-mail", "In person",
)
ATTEMPT_OUTCOMES: tuple[str, ...] = (
    "Answered — informed",
    "Answered — coming to college",
    "No answer",
    "Voicemail left",
    "Message left with someone else",
    "Wrong number",
    "Number unavailable",
)
#: Outcomes that mean the contact was actually reached.
SUCCESSFUL_OUTCOMES: frozenset[str] = frozenset({
    "Answered — informed", "Answered — coming to college",
})

_CONTACTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS emergency_contacts (
    contact_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    priority           INTEGER NOT NULL,
    parent_contact_id  INTEGER,
    name               TEXT NOT NULL,
    relationship       TEXT,
    phone              TEXT,
    alt_phone          TEXT,
    email              TEXT,
    language           TEXT,
    can_collect        INTEGER NOT NULL DEFAULT 1,
    notes              TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_contact_id) REFERENCES parent_contacts(contact_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS emergency_contact_attempts (
    attempt_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    incident_id     INTEGER,
    contact_id      INTEGER,
    contact_name    TEXT NOT NULL,
    phone_dialled   TEXT,
    attempted_on    TEXT NOT NULL,
    attempted_time  TEXT NOT NULL,
    method          TEXT NOT NULL DEFAULT 'Phone call',
    outcome         TEXT NOT NULL,
    reason          TEXT,
    attempted_by    TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (incident_id) REFERENCES emergency_incidents(incident_id)
        ON DELETE SET NULL,
    FOREIGN KEY (contact_id) REFERENCES emergency_contacts(contact_id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ec_student  ON emergency_contacts(student_id, priority);
CREATE INDEX IF NOT EXISTS idx_eca_student ON emergency_contact_attempts(student_id);
CREATE INDEX IF NOT EXISTS idx_eca_inc     ON emergency_contact_attempts(incident_id);
"""


@dataclass
class EmergencyContact:
    contact_id: int
    student_id: str
    priority: int
    parent_contact_id: int | None
    name: str
    relationship: str | None
    phone: str | None
    alt_phone: str | None
    email: str | None
    language: str | None
    can_collect: bool
    notes: str | None
    created_at: str | None
    updated_at: str | None


@dataclass
class ContactAttempt:
    attempt_id: int
    student_id: str
    incident_id: int | None
    contact_id: int | None
    contact_name: str
    phone_dialled: str | None
    attempted_on: str
    attempted_time: str
    method: str
    outcome: str
    reason: str | None
    attempted_by: str | None
    notes: str | None
    created_at: str | None
    updated_at: str | None

    @property
    def reached(self) -> bool:
        return self.outcome in SUCCESSFUL_OUTCOMES


@dataclass
class CallListEntry:
    """One line of a student's emergency call list, whatever its source."""
    order: int
    source: str                    # "Emergency list" / "Parent contacts" / "Medical profile"
    name: str
    relationship: str | None
    phone: str | None
    alt_phone: str | None
    contact_id: int | None = None
    parent_contact_id: int | None = None
    can_collect: bool = True
    notes: str | None = None


def _hhmm() -> str:
    return _dt.datetime.now().strftime("%H:%M")


_C = _records.Col

CONTACT_SPEC = _records.TableSpec(
    table="emergency_contacts", id_col="contact_id",
    row_type=EmergencyContact, label="Emergency contact",
    order_by="student_id, priority",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("priority", "Priority (1 = call first)", "int", min_value=1),
        _C("parent_contact_id", "Parent contact # (links, read only)",
           "int", listed=False),
        _C("name", "Name"),
        _C("relationship", "Relationship"),
        _C("phone", "Phone"),
        _C("alt_phone", "Alternative phone"),
        _C("email", "E-mail", listed=False),
        _C("language", "Language", listed=False),
        _C("can_collect", "May collect the student", "bool", default=True),
        _C("notes", "Notes", "multiline", listed=False),
    ))

ATTEMPT_SPEC = _records.TableSpec(
    table="emergency_contact_attempts", id_col="attempt_id",
    row_type=ContactAttempt, label="Contact attempt",
    order_by="attempted_on DESC, attempted_time DESC, attempt_id DESC",
    cols=(
        _C("student_id", "Student", "student", required=True, fixed=True),
        _C("incident_id", "Incident # (optional)", "int"),
        _C("contact_id", "Emergency contact #", "int", listed=False),
        _C("contact_name", "Contact name"),
        _C("phone_dialled", "Number used"),
        _C("attempted_on", "Date", "date", required=True,
           default=_records.today),
        _C("attempted_time", "Time", "time", required=True, default=_hhmm),
        _C("method", "Method", "choice", choices=ATTEMPT_METHODS,
           default="Phone call"),
        _C("outcome", "Outcome", "choice", required=True,
           choices=ATTEMPT_OUTCOMES),
        _C("reason", "Reason for contact"),
        _C("attempted_by", "Made by"),
        _C("notes", "Notes", "multiline", listed=False),
    ))


def _init_contacts() -> None:
    # parent_contacts must exist for the FK (read-only reuse).
    from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
        parent_contacts as _pc,
    )
    _pc.init_db()
    with _connect() as conn:
        conn.executescript(_CONTACTS_SCHEMA)


def _student_ok(sid: str) -> bool:
    with _connect() as conn:
        try:
            return conn.execute("SELECT 1 FROM students WHERE student_id=?",
                                (sid,)).fetchone() is not None
        except sqlite3.OperationalError:
            return False


def _parent_contact(conn: sqlite3.Connection, pcid: int) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM parent_contacts WHERE contact_id = ?",
                     (pcid,)).fetchone()
    if r is None:
        raise ValidationError(f"No parent contact #{pcid}")
    return r


def _fill_from_parent(conn: sqlite3.Connection,
                      p: dict[str, Any]) -> None:
    """A linked parent contact supplies blank name / numbers."""
    if p.get("parent_contact_id") is None:
        return
    r = _parent_contact(conn, p["parent_contact_id"])
    if r["student_id"] != p["student_id"]:
        raise ValidationError("That parent contact belongs to another student")
    full = " ".join(x for x in (r["title"], r["first_name"], r["last_name"])
                    if x)
    p["name"] = p.get("name") or full
    p["relationship"] = p.get("relationship") or r["relationship"]
    p["phone"] = p.get("phone") or r["primary_phone"]
    p["alt_phone"] = p.get("alt_phone") or r["secondary_phone"]
    p["email"] = p.get("email") or r["email"]
    p["language"] = p.get("language") or r["preferred_language"]


def _renumber(conn: sqlite3.Connection, student_id: str,
              first_id: int | None = None) -> None:
    """Close gaps so priorities run 1..n; *first_id* wins ties."""
    rows = conn.execute(
        "SELECT contact_id, priority FROM emergency_contacts "
        "WHERE student_id = ? ORDER BY priority, "
        "CASE WHEN contact_id = ? THEN 0 ELSE 1 END, contact_id",
        (student_id, first_id or -1)).fetchall()
    for i, r in enumerate(rows, 1):
        if r["priority"] != i:
            conn.execute("UPDATE emergency_contacts SET priority = ? "
                         "WHERE contact_id = ?", (i, r["contact_id"]))


def add_contact(data: dict[str, Any]) -> EmergencyContact:
    init_db()
    p = _records.validate(CONTACT_SPEC, data, error=ValidationError,
                          student_exists=_student_ok)
    with _connect() as conn:
        _fill_from_parent(conn, p)
        if not p.get("name"):
            raise ValidationError("Name is required")
        if not p.get("phone") and not p.get("alt_phone"):
            raise ValidationError("An emergency contact needs a phone number")
        if p["priority"] is None:
            p["priority"] = (conn.execute(
                "SELECT COALESCE(MAX(priority), 0) FROM emergency_contacts "
                "WHERE student_id = ?", (p["student_id"],)).fetchone()[0]
                + 1)
        new_id = _records.insert(conn, CONTACT_SPEC, p)
        _renumber(conn, p["student_id"], new_id)
    logger.info("Added emergency contact #%d for %s", new_id,
                p["student_id"])
    return get_contact(new_id)


def get_contact(contact_id: int) -> EmergencyContact | None:
    init_db()
    with _connect() as conn:
        return _records.fetch(conn, CONTACT_SPEC, contact_id)


def list_contacts(student_id: str | None = None) -> list[EmergencyContact]:
    init_db()
    with _connect() as conn:
        return _records.select(conn, CONTACT_SPEC,
                               equals={"student_id": student_id})


def update_contact(contact_id: int,
                   data: dict[str, Any]) -> EmergencyContact:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, CONTACT_SPEC, contact_id)
        if existing is None:
            raise ValidationError(f"No emergency contact #{contact_id}")
        p = _records.validate(CONTACT_SPEC, data, error=ValidationError,
                              existing=existing)
        _fill_from_parent(conn, p)
        if not p.get("name"):
            raise ValidationError("Name is required")
        if not p.get("phone") and not p.get("alt_phone"):
            raise ValidationError("An emergency contact needs a phone number")
        if p["priority"] is None:
            p["priority"] = existing.priority
        _records.update(conn, CONTACT_SPEC, contact_id, p)
        _renumber(conn, existing.student_id, contact_id)
    return get_contact(contact_id)


def move_contact(contact_id: int, direction: int) -> EmergencyContact:
    """Move a contact up (-1) or down (+1) the call order."""
    c = get_contact(contact_id)
    if c is None:
        raise ValidationError(f"No emergency contact #{contact_id}")
    with _connect() as conn:
        other = conn.execute(
            "SELECT contact_id, priority FROM emergency_contacts "
            "WHERE student_id = ? AND priority = ?",
            (c.student_id, c.priority + (1 if direction > 0 else -1))
        ).fetchone()
        if other is None:
            return c
        conn.execute("UPDATE emergency_contacts SET priority = ?, "
                     "updated_at = datetime('now') WHERE contact_id = ?",
                     (c.priority, other["contact_id"]))
        conn.execute("UPDATE emergency_contacts SET priority = ?, "
                     "updated_at = datetime('now') WHERE contact_id = ?",
                     (other["priority"], contact_id))
    return get_contact(contact_id)


def delete_contact(contact_id: int) -> bool:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, CONTACT_SPEC, contact_id)
        if existing is None:
            return False
        ok = _records.delete(conn, CONTACT_SPEC, contact_id)
        _renumber(conn, existing.student_id)
        return ok


def import_parent_contacts(student_id: str) -> list[EmergencyContact]:
    """Add the student's parent contacts flagged as emergency contacts
    (primary first) to the end of their call list, skipping any already
    linked. Returns the full list."""
    init_db()
    with _connect() as conn:
        linked = {r[0] for r in conn.execute(
            "SELECT parent_contact_id FROM emergency_contacts "
            "WHERE student_id = ? AND parent_contact_id IS NOT NULL",
            (student_id,))}
        pcs = conn.execute(
            "SELECT contact_id FROM parent_contacts WHERE student_id = ? "
            "AND is_emergency_contact = 1 "
            "AND (COALESCE(primary_phone, '') <> '' "
            "     OR COALESCE(secondary_phone, '') <> '') "
            "ORDER BY is_primary DESC, contact_id", (student_id,)).fetchall()
    for r in pcs:
        if r["contact_id"] not in linked:
            add_contact({"student_id": student_id,
                         "parent_contact_id": r["contact_id"]})
    return list_contacts(student_id)


def emergency_contacts_for(student_id: str) -> list[CallListEntry]:
    """The order to ring people in an emergency.

    The student's own list when it exists (linked rows show the live
    parent-contact details). Otherwise parent contacts flagged as
    emergency contacts, primary first, then the medical profile's
    emergency contact if it is not already on the list.
    """
    init_db()
    out: list[CallListEntry] = []
    with _connect() as conn:
        rows = _records.select(conn, CONTACT_SPEC,
                               equals={"student_id": student_id})
        for c in rows:
            name, rel, ph, alt = c.name, c.relationship, c.phone, c.alt_phone
            if c.parent_contact_id is not None:
                r = conn.execute(
                    "SELECT * FROM parent_contacts WHERE contact_id = ?",
                    (c.parent_contact_id,)).fetchone()
                if r is not None:
                    name = " ".join(x for x in (r["title"], r["first_name"],
                                                r["last_name"]) if x)
                    rel = r["relationship"]
                    ph = r["primary_phone"] or ph
                    alt = r["secondary_phone"] or alt
            out.append(CallListEntry(
                order=c.priority, source="Emergency list", name=name,
                relationship=rel, phone=ph, alt_phone=alt,
                contact_id=c.contact_id,
                parent_contact_id=c.parent_contact_id,
                can_collect=c.can_collect, notes=c.notes))
        if not out:
            for r in conn.execute(
                    "SELECT * FROM parent_contacts WHERE student_id = ? "
                    "AND is_emergency_contact = 1 "
                    "ORDER BY is_primary DESC, contact_id", (student_id,)):
                out.append(CallListEntry(
                    order=len(out) + 1, source="Parent contacts",
                    name=" ".join(x for x in (r["title"], r["first_name"],
                                              r["last_name"]) if x),
                    relationship=r["relationship"], phone=r["primary_phone"],
                    alt_phone=r["secondary_phone"],
                    parent_contact_id=r["contact_id"]))
        if _records.table_exists(conn, "med_profiles"):
            m = conn.execute(
                "SELECT emergency_contact_name, emergency_contact_phone, "
                "emergency_contact_rel FROM med_profiles "
                "WHERE student_id = ?", (student_id,)).fetchone()
            if m and m["emergency_contact_phone"]:
                digits = "".join(ch for ch in m["emergency_contact_phone"]
                                 if ch.isdigit())
                known = {"".join(ch for ch in (e.phone or "") if ch.isdigit())
                         for e in out} | {
                    "".join(ch for ch in (e.alt_phone or "") if ch.isdigit())
                    for e in out}
                if digits not in known:
                    out.append(CallListEntry(
                        order=len(out) + 1, source="Medical profile",
                        name=m["emergency_contact_name"] or "(no name)",
                        relationship=m["emergency_contact_rel"],
                        phone=m["emergency_contact_phone"], alt_phone=None))
    return out


# ── Contact attempts ──────────────────────────────────────────────

def log_attempt(data: dict[str, Any]) -> ContactAttempt:
    init_db()
    p = _records.validate(ATTEMPT_SPEC, data, error=ValidationError,
                          student_exists=_student_ok)
    with _connect() as conn:
        if p["incident_id"] is not None and conn.execute(
                "SELECT 1 FROM emergency_incidents WHERE incident_id = ?",
                (p["incident_id"],)).fetchone() is None:
            raise ValidationError(f"No emergency incident #{p['incident_id']}")
        if p["contact_id"] is not None:
            c = _records.fetch(conn, CONTACT_SPEC, p["contact_id"])
            if c is None:
                raise ValidationError(
                    f"No emergency contact #{p['contact_id']}")
            if c.student_id != p["student_id"]:
                raise ValidationError(
                    "That emergency contact belongs to another student")
            p["contact_name"] = p["contact_name"] or c.name
            p["phone_dialled"] = p["phone_dialled"] or c.phone or c.alt_phone
        if not p["contact_name"]:
            raise ValidationError("Contact name is required")
        p["attempted_by"] = p["attempted_by"] or _records.current_username()
        new_id = _records.insert(conn, ATTEMPT_SPEC, p)
        out = _records.fetch(conn, ATTEMPT_SPEC, new_id)
    logger.info("Logged contact attempt #%d for %s: %s (%s)", new_id,
                p["student_id"], p["contact_name"], p["outcome"])
    return out


def list_attempts(*, student_id: str | None = None,
                  incident_id: int | None = None) -> list[ContactAttempt]:
    init_db()
    with _connect() as conn:
        return _records.select(conn, ATTEMPT_SPEC, equals={
            "student_id": student_id, "incident_id": incident_id})


def update_attempt(attempt_id: int, data: dict[str, Any]) -> ContactAttempt:
    init_db()
    with _connect() as conn:
        existing = _records.fetch(conn, ATTEMPT_SPEC, attempt_id)
        if existing is None:
            raise ValidationError(f"No contact attempt #{attempt_id}")
        p = _records.validate(ATTEMPT_SPEC, data, error=ValidationError,
                              existing=existing)
        _records.update(conn, ATTEMPT_SPEC, attempt_id, p)
        return _records.fetch(conn, ATTEMPT_SPEC, attempt_id)


def delete_attempt(attempt_id: int) -> bool:
    init_db()
    with _connect() as conn:
        return _records.delete(conn, ATTEMPT_SPEC, attempt_id)


@dataclass
class CallSheetLine:
    entry: CallListEntry
    attempts: list[ContactAttempt]

    @property
    def reached(self) -> bool:
        return any(a.reached for a in self.attempts)


def call_sheet(student_id: str, *, incident_id: int | None = None,
               since: str | None = None) -> list[CallSheetLine]:
    """The call list with the attempts made so far (for an incident, or
    since a date — default today) against each line."""
    since = _records.check_date(since, "Since", ValidationError) \
        or _records.today()
    attempts = [a for a in list_attempts(student_id=student_id,
                                         incident_id=incident_id)
                if incident_id is not None or a.attempted_on >= since]
    lines = []
    for e in emergency_contacts_for(student_id):
        mine = [a for a in attempts
                if (e.contact_id and a.contact_id == e.contact_id)
                or (not a.contact_id and a.contact_name == e.name)]
        lines.append(CallSheetLine(e, mine))
    return lines
