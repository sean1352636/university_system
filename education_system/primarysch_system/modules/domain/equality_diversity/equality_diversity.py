"""Equality & Diversity data layer for Primary School System.

Per-incident log of discrimination / harassment / bullying / hate
incidents tagged with the Equality Act 2010 protected
characteristic. Free-text subject (could be a student id, a staff
name, or 'anonymous') so the same table covers student↔student,
student↔staff and staff↔staff incidents without coupling to the
students table.
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

INCIDENT_TYPES: tuple[str, ...] = (
    "Direct Discrimination",
    "Indirect Discrimination",
    "Harassment",
    "Victimisation",
    "Hate Incident",
    "Hate Crime",
    "Bullying",
    "Microaggression",
    "Inappropriate Language",
    "Stereotyping",
    "Other",
)
DEFAULT_INCIDENT_TYPE = "Other"

PROTECTED_CHARACTERISTICS: tuple[str, ...] = (
    "Age",
    "Disability",
    "Gender Reassignment",
    "Marriage / Civil Partnership",
    "Pregnancy / Maternity",
    "Race",
    "Religion / Belief",
    "Sex",
    "Sexual Orientation",
    "Multiple Characteristics",
    "Not Applicable",
    "Other",
)
DEFAULT_CHARACTERISTIC = "Not Applicable"

SUBJECT_ROLES: tuple[str, ...] = (
    "Student",
    "Staff",
    "Parent / Visitor",
    "Anonymous",
    "Group",
    "Other",
)
DEFAULT_SUBJECT_ROLE = "Student"

SEVERITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
_SEVERITY_LABELS = {
    1: "Low", 2: "Moderate", 3: "Serious",
    4: "Severe", 5: "Critical",
}


def severity_label(s: int | None) -> str:
    if s is None:
        return "—"
    return _SEVERITY_LABELS.get(s, "Unknown")


STATUSES: tuple[str, ...] = (
    "Reported",
    "Under Investigation",
    "Substantiated",
    "Unsubstantiated",
    "Actions Set",
    "Resolved",
    "Closed",
)
DEFAULT_STATUS = "Reported"


class ValidationError(Exception):
    pass


@dataclass
class EDIncident:
    incident_id: int
    incident_date: str
    incident_time: str | None
    reported_on: str
    reporter: str
    reporter_role: str
    anonymous: bool
    subject_name: str | None
    subject_role: str
    alleged_perpetrator: str | None
    perpetrator_role: str
    incident_type: str
    protected_characteristic: str
    severity: int
    location: str | None
    description: str | None
    witnesses: str | None
    investigated_by: str | None
    investigation_notes: str | None
    outcome: str | None
    actions_taken: str | None
    training_required: bool
    complainant_informed: bool
    perpetrator_informed: bool
    escalated_to_head: bool
    escalated_to_dsl: bool
    governors_informed: bool
    status: str
    closed_on: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_open(self) -> bool:
        return self.status not in ("Resolved", "Closed",
                                          "Unsubstantiated")

    @property
    def severity_label(self) -> str:
        return severity_label(self.severity)


@dataclass
class EDSummary:
    total: int = 0
    open_count: int = 0
    serious_or_critical: int = 0
    substantiated: int = 0
    awaiting_action: int = 0
    governors_informed: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_characteristic: dict[str, int] = field(default_factory=dict)
    by_severity: dict[int, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.EQUALITY_DIVERSITY_DB)
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
            CREATE TABLE IF NOT EXISTS ed_incidents (
                incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_date TEXT NOT NULL,
                incident_time TEXT,
                reported_on TEXT NOT NULL,
                reporter TEXT NOT NULL,
                reporter_role TEXT NOT NULL,
                anonymous INTEGER NOT NULL DEFAULT 0,
                subject_name TEXT,
                subject_role TEXT NOT NULL,
                alleged_perpetrator TEXT,
                perpetrator_role TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                protected_characteristic TEXT NOT NULL,
                severity INTEGER NOT NULL,
                location TEXT,
                description TEXT,
                witnesses TEXT,
                investigated_by TEXT,
                investigation_notes TEXT,
                outcome TEXT,
                actions_taken TEXT,
                training_required INTEGER NOT NULL DEFAULT 0,
                complainant_informed INTEGER NOT NULL DEFAULT 0,
                perpetrator_informed INTEGER NOT NULL DEFAULT 0,
                escalated_to_head INTEGER NOT NULL DEFAULT 0,
                escalated_to_dsl INTEGER NOT NULL DEFAULT 0,
                governors_informed INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                closed_on TEXT,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
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


def _validate_payload(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["incident_date"] = (out.get("incident_date") or "").strip()
    if not out["incident_date"]:
        raise ValidationError("Incident date is required")
    _check_date("Incident date", out["incident_date"])
    _check_time("Incident time", out.get("incident_time"))
    out["reported_on"] = (out.get("reported_on") or "").strip()
    if not out["reported_on"]:
        out["reported_on"] = _dt.date.today().isoformat()
    _check_date("Reported on", out["reported_on"])
    _check_date("Closed on",   out.get("closed_on"))

    out["reporter"] = (out.get("reporter") or "").strip()
    if not out["reporter"]:
        raise ValidationError("Reporter is required")

    rr = (out.get("reporter_role") or "").strip()
    if rr not in SUBJECT_ROLES:
        raise ValidationError(
            f"Reporter role must be one of: "
            f"{', '.join(SUBJECT_ROLES)}")
    out["reporter_role"] = rr

    sr = (out.get("subject_role") or DEFAULT_SUBJECT_ROLE).strip()
    if sr not in SUBJECT_ROLES:
        raise ValidationError(
            f"Subject role must be one of: "
            f"{', '.join(SUBJECT_ROLES)}")
    out["subject_role"] = sr

    pr = (out.get("perpetrator_role") or DEFAULT_SUBJECT_ROLE).strip()
    if pr not in SUBJECT_ROLES:
        raise ValidationError(
            f"Perpetrator role must be one of: "
            f"{', '.join(SUBJECT_ROLES)}")
    out["perpetrator_role"] = pr

    it = (out.get("incident_type") or "").strip()
    if it not in INCIDENT_TYPES:
        raise ValidationError(
            f"Incident type must be one of: "
            f"{', '.join(INCIDENT_TYPES)}")
    out["incident_type"] = it

    pc = (out.get("protected_characteristic")
           or DEFAULT_CHARACTERISTIC).strip()
    if pc not in PROTECTED_CHARACTERISTICS:
        raise ValidationError(
            f"Protected characteristic must be one of: "
            f"{', '.join(PROTECTED_CHARACTERISTICS)}")
    out["protected_characteristic"] = pc

    try:
        sev = int(out.get("severity") or 2)
    except (TypeError, ValueError):
        raise ValidationError("Severity must be 1-5")
    if sev not in SEVERITIES:
        raise ValidationError("Severity must be 1-5")
    out["severity"] = sev

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    for k in ("subject_name", "alleged_perpetrator", "location",
               "description", "witnesses", "investigated_by",
               "investigation_notes", "outcome", "actions_taken",
               "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("incident_time", "closed_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None) if isinstance(v, str) else v
    for k in ("anonymous", "training_required",
               "complainant_informed", "perpetrator_informed",
               "escalated_to_head", "escalated_to_dsl",
               "governors_informed"):
        out[k] = bool(out.get(k))
    return out


def _row(r: sqlite3.Row) -> EDIncident:
    return EDIncident(
        incident_id=r["incident_id"],
        incident_date=r["incident_date"],
        incident_time=r["incident_time"],
        reported_on=r["reported_on"],
        reporter=r["reporter"],
        reporter_role=r["reporter_role"],
        anonymous=bool(r["anonymous"]),
        subject_name=r["subject_name"],
        subject_role=r["subject_role"],
        alleged_perpetrator=r["alleged_perpetrator"],
        perpetrator_role=r["perpetrator_role"],
        incident_type=r["incident_type"],
        protected_characteristic=r["protected_characteristic"],
        severity=r["severity"],
        location=r["location"],
        description=r["description"],
        witnesses=r["witnesses"],
        investigated_by=r["investigated_by"],
        investigation_notes=r["investigation_notes"],
        outcome=r["outcome"],
        actions_taken=r["actions_taken"],
        training_required=bool(r["training_required"]),
        complainant_informed=bool(r["complainant_informed"]),
        perpetrator_informed=bool(r["perpetrator_informed"]),
        escalated_to_head=bool(r["escalated_to_head"]),
        escalated_to_dsl=bool(r["escalated_to_dsl"]),
        governors_informed=bool(r["governors_informed"]),
        status=r["status"],
        closed_on=r["closed_on"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_incident(payload: dict[str, Any]) -> EDIncident:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO ed_incidents (
              incident_date, incident_time, reported_on,
              reporter, reporter_role, anonymous,
              subject_name, subject_role,
              alleged_perpetrator, perpetrator_role,
              incident_type, protected_characteristic, severity,
              location, description, witnesses,
              investigated_by, investigation_notes,
              outcome, actions_taken, training_required,
              complainant_informed, perpetrator_informed,
              escalated_to_head, escalated_to_dsl,
              governors_informed, status, closed_on, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["incident_date"], p["incident_time"],
            p["reported_on"], p["reporter"], p["reporter_role"],
            1 if p["anonymous"] else 0,
            p["subject_name"], p["subject_role"],
            p["alleged_perpetrator"], p["perpetrator_role"],
            p["incident_type"], p["protected_characteristic"],
            p["severity"],
            p["location"], p["description"], p["witnesses"],
            p["investigated_by"], p["investigation_notes"],
            p["outcome"], p["actions_taken"],
            1 if p["training_required"] else 0,
            1 if p["complainant_informed"] else 0,
            1 if p["perpetrator_informed"] else 0,
            1 if p["escalated_to_head"] else 0,
            1 if p["escalated_to_dsl"] else 0,
            1 if p["governors_informed"] else 0,
            p["status"], p["closed_on"], p["notes"],
            now, now,
        ))
        new_id = cur.lastrowid
    return get_incident(new_id)


def update_incident(incident_id: int,
                       payload: dict[str, Any]) -> EDIncident:
    init_db()
    if get_incident(incident_id) is None:
        raise ValidationError(f"No incident with id {incident_id}")
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE ed_incidents SET
              incident_date=?, incident_time=?, reported_on=?,
              reporter=?, reporter_role=?, anonymous=?,
              subject_name=?, subject_role=?,
              alleged_perpetrator=?, perpetrator_role=?,
              incident_type=?, protected_characteristic=?,
              severity=?,
              location=?, description=?, witnesses=?,
              investigated_by=?, investigation_notes=?,
              outcome=?, actions_taken=?, training_required=?,
              complainant_informed=?, perpetrator_informed=?,
              escalated_to_head=?, escalated_to_dsl=?,
              governors_informed=?, status=?, closed_on=?, notes=?,
              updated_on=?
            WHERE incident_id=?
        """, (
            p["incident_date"], p["incident_time"],
            p["reported_on"], p["reporter"], p["reporter_role"],
            1 if p["anonymous"] else 0,
            p["subject_name"], p["subject_role"],
            p["alleged_perpetrator"], p["perpetrator_role"],
            p["incident_type"], p["protected_characteristic"],
            p["severity"],
            p["location"], p["description"], p["witnesses"],
            p["investigated_by"], p["investigation_notes"],
            p["outcome"], p["actions_taken"],
            1 if p["training_required"] else 0,
            1 if p["complainant_informed"] else 0,
            1 if p["perpetrator_informed"] else 0,
            1 if p["escalated_to_head"] else 0,
            1 if p["escalated_to_dsl"] else 0,
            1 if p["governors_informed"] else 0,
            p["status"], p["closed_on"], p["notes"],
            now, incident_id,
        ))
    return get_incident(incident_id)


def delete_incident(incident_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM ed_incidents WHERE incident_id=?",
            (incident_id,))
        return cur.rowcount > 0


def get_incident(incident_id: int) -> EDIncident | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM ed_incidents WHERE incident_id=?",
            (incident_id,)).fetchone()
        return _row(r) if r else None


def list_incidents(*,
                       incident_type: str | None = None,
                       characteristic: str | None = None,
                       status: str | None = None,
                       severity: int | None = None,
                       severity_min: int | None = None,
                       reporter_like: str | None = None,
                       subject_like: str | None = None,
                       open_only: bool = False,
                       substantiated_only: bool = False,
                       escalated_only: bool = False,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       ) -> list[EDIncident]:
    init_db()
    sql = "SELECT * FROM ed_incidents WHERE 1=1"
    params: list[Any] = []
    if incident_type:
        sql += " AND incident_type=?"
        params.append(incident_type)
    if characteristic:
        sql += " AND protected_characteristic=?"
        params.append(characteristic)
    if status:
        sql += " AND status=?"
        params.append(status)
    if severity is not None:
        sql += " AND severity=?"
        params.append(severity)
    if severity_min is not None:
        sql += " AND severity >= ?"
        params.append(severity_min)
    if reporter_like:
        sql += " AND reporter LIKE ?"
        params.append(f"%{reporter_like}%")
    if subject_like:
        sql += (" AND (subject_name LIKE ?"
                  " OR alleged_perpetrator LIKE ?)")
        params.extend([f"%{subject_like}%",
                          f"%{subject_like}%"])
    if open_only:
        sql += (" AND status NOT IN "
                  "('Resolved','Closed','Unsubstantiated')")
    if substantiated_only:
        sql += " AND status='Substantiated'"
    if escalated_only:
        sql += (" AND (escalated_to_head=1 OR escalated_to_dsl=1"
                  " OR governors_informed=1)")
    if date_from:
        _check_date("From", date_from)
        sql += " AND incident_date >= ?"
        params.append(date_from)
    if date_to:
        _check_date("To", date_to)
        sql += " AND incident_date <= ?"
        params.append(date_to)
    sql += (" ORDER BY incident_date DESC, incident_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


# ── Workflow ─────────────────────────────────────────────────────

def _to_dict(i: EDIncident) -> dict[str, Any]:
    return {
        "incident_date": i.incident_date,
        "incident_time": i.incident_time,
        "reported_on": i.reported_on,
        "reporter": i.reporter,
        "reporter_role": i.reporter_role,
        "anonymous": i.anonymous,
        "subject_name": i.subject_name,
        "subject_role": i.subject_role,
        "alleged_perpetrator": i.alleged_perpetrator,
        "perpetrator_role": i.perpetrator_role,
        "incident_type": i.incident_type,
        "protected_characteristic": i.protected_characteristic,
        "severity": i.severity,
        "location": i.location,
        "description": i.description,
        "witnesses": i.witnesses,
        "investigated_by": i.investigated_by,
        "investigation_notes": i.investigation_notes,
        "outcome": i.outcome,
        "actions_taken": i.actions_taken,
        "training_required": i.training_required,
        "complainant_informed": i.complainant_informed,
        "perpetrator_informed": i.perpetrator_informed,
        "escalated_to_head": i.escalated_to_head,
        "escalated_to_dsl": i.escalated_to_dsl,
        "governors_informed": i.governors_informed,
        "status": i.status,
        "closed_on": i.closed_on,
        "notes": i.notes,
    }


def start_investigation(incident_id: int, *,
                              investigated_by: str) -> EDIncident:
    if not investigated_by:
        raise ValidationError("Investigator is required")
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["investigated_by"] = investigated_by
    data["status"] = "Under Investigation"
    return update_incident(incident_id, data)


def record_outcome(incident_id: int, *,
                       substantiated: bool,
                       outcome: str,
                       investigation_notes: str | None = None
                       ) -> EDIncident:
    if not outcome:
        raise ValidationError("Outcome is required")
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["outcome"] = outcome
    if investigation_notes:
        data["investigation_notes"] = investigation_notes
    data["status"] = ("Substantiated" if substantiated
                          else "Unsubstantiated")
    if not substantiated:
        data["closed_on"] = (data["closed_on"]
                                  or _dt.date.today().isoformat())
    return update_incident(incident_id, data)


def set_actions(incident_id: int, *,
                    actions_taken: str,
                    training_required: bool = False) -> EDIncident:
    if not actions_taken:
        raise ValidationError("Actions taken is required")
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["actions_taken"] = actions_taken
    data["training_required"] = training_required
    data["status"] = "Actions Set"
    return update_incident(incident_id, data)


def resolve(incident_id: int) -> EDIncident:
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["status"] = "Resolved"
    data["closed_on"] = (data["closed_on"]
                              or _dt.date.today().isoformat())
    return update_incident(incident_id, data)


def close_incident(incident_id: int) -> EDIncident:
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    data = _to_dict(i)
    data["status"] = "Closed"
    data["closed_on"] = (data["closed_on"]
                              or _dt.date.today().isoformat())
    return update_incident(incident_id, data)


def set_status(incident_id: int, new_status: str) -> EDIncident:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    i = get_incident(incident_id)
    if i is None:
        raise ValidationError(f"No incident with id {incident_id}")
    return update_incident(incident_id,
                                {**_to_dict(i), "status": new_status})


# ── Summary ───────────────────────────────────────────────────────

def summary() -> EDSummary:
    rows = list_incidents()
    out = EDSummary(total=len(rows))
    if not rows:
        return out
    for i in rows:
        if i.is_open:
            out.open_count += 1
        if i.severity >= 4:
            out.serious_or_critical += 1
        if i.status == "Substantiated":
            out.substantiated += 1
            if not i.actions_taken:
                out.awaiting_action += 1
        if i.governors_informed:
            out.governors_informed += 1
        out.by_type[i.incident_type] = (
            out.by_type.get(i.incident_type, 0) + 1)
        out.by_characteristic[i.protected_characteristic] = (
            out.by_characteristic.get(
                i.protected_characteristic, 0) + 1)
        out.by_severity[i.severity] = (
            out.by_severity.get(i.severity, 0) + 1)
        out.by_status[i.status] = (
            out.by_status.get(i.status, 0) + 1)
    return out


__all__ = [
    "INCIDENT_TYPES", "DEFAULT_INCIDENT_TYPE",
    "PROTECTED_CHARACTERISTICS", "DEFAULT_CHARACTERISTIC",
    "SUBJECT_ROLES", "DEFAULT_SUBJECT_ROLE",
    "SEVERITIES", "severity_label",
    "STATUSES", "DEFAULT_STATUS",
    "ValidationError",
    "EDIncident", "EDSummary",
    "init_db",
    "create_incident", "update_incident", "delete_incident",
    "get_incident", "list_incidents",
    "start_investigation", "record_outcome", "set_actions",
    "resolve", "close_incident", "set_status",
    "summary",
]
