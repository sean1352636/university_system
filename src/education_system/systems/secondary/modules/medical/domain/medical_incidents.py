"""Medical: the first aid / accident book and emergencies & drills.

Kept from the old First Aid window: one incident per person with date,
time, location, injury type, severity, body part, description, treatment,
treated by, outcome, parent contacted (and when), hospital referral,
accident book reference, RIDDOR reportable, follow-up and notes; the
summary (by severity / injury / outcome / location, pupils, parents
contacted, hospital, RIDDOR).

Kept from the old Emergency & Drills window: drills, real emergencies, tests
and false alarms with type, date, start / end time and duration, location,
trigger, reported by, incident commander, pupils and staff evacuated,
missing, injuries, emergency services (and who attended), outcome, status
(Logged, Under review, Actions outstanding, Closed), lessons learned,
follow-up actions and notes; Close; the summary.

New: the accident book also takes staff and visitors; how the parents were
told; a RIDDOR deadline (10 days) with the date reported and the HSE
reference; warnings when an injury needs the family told (head injuries,
hospital) or may be RIDDOR reportable; the family e-mailed about an
incident; an evacuation that leaves anyone missing can't be closed until
they're accounted for.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.medical.domain.medical_common import (
    PUPIL_COLS,
    NotFound,
    ValidationError,
    _audit,
    _blank,
    _bool,
    _choice,
    _date,
    _number,
    _pupil,
    _require_editor,
    _require_staff,
    _text,
    family_letter,
)
from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

INJURY_TYPES: tuple[str, ...] = (
    "Bump/Bruise", "Cut/Graze", "Sprain/Strain", "Fracture (suspected)", "Burn/Scald",
    "Bite/Sting", "Nose bleed", "Headache", "Stomach ache", "Asthma", "Allergic reaction",
    "Anaphylaxis", "Seizure", "Faint/Dizziness", "Concussion (suspected)", "Eye injury",
    "Dental", "Mental-health (panic)", "Head injury", "Other")
DEFAULT_INJURY = "Bump/Bruise"
SEVERITIES: tuple[str, ...] = ("Minor", "Moderate", "Severe", "Critical")
DEFAULT_SEVERITY = "Minor"
OUTCOMES: tuple[str, ...] = (
    "Returned to lesson", "Sent home", "Hospital — A&E", "Hospital — minor injuries",
    "Ambulance called", "GP referral", "School nurse referral", "Other")
DEFAULT_OUTCOME = "Returned to lesson"
HOSPITAL_OUTCOMES = frozenset({"Hospital — A&E", "Hospital — minor injuries",
                               "Ambulance called"})
PERSON_TYPES: tuple[str, ...] = ("Pupil", "Staff", "Visitor", "Contractor")
TOLD_HOW: tuple[str, ...] = ("Phone call", "E-mail", "Letter / note home", "In person")
RIDDOR_DAYS = 10
HEAD = frozenset({"Concussion (suspected)", "Head injury"})

EVENT_KINDS: tuple[str, ...] = ("Drill", "Real", "Test", "False alarm")
DEFAULT_KIND = "Drill"
EMERGENCY_TYPES: tuple[str, ...] = (
    "Fire", "Lockdown", "Invacuation", "Bomb threat", "Severe weather", "Power failure",
    "Gas leak", "Flood", "Medical — pupil", "Medical — staff", "Intruder", "Missing pupil",
    "Cyber/IT outage", "Other")
DEFAULT_EMERGENCY = "Fire"
EVENT_OUTCOMES: tuple[str, ...] = ("Successful", "Partial success", "Issues identified",
                                   "Aborted", "Under review")
EVENT_STATUSES: tuple[str, ...] = ("Logged", "Under review", "Actions outstanding", "Closed")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS first_aid_incidents (
    incident_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id             INTEGER REFERENCES pupils (pupil_id) ON DELETE SET NULL,
    person_type          TEXT NOT NULL DEFAULT 'Pupil',
    person_name          TEXT,
    incident_date        TEXT NOT NULL,
    incident_time        TEXT,
    location             TEXT NOT NULL,
    injury_type          TEXT NOT NULL DEFAULT 'Bump/Bruise',
    severity             TEXT NOT NULL DEFAULT 'Minor',
    body_part            TEXT,
    description          TEXT NOT NULL,
    treatment            TEXT NOT NULL,
    treated_by           TEXT NOT NULL,
    outcome              TEXT NOT NULL DEFAULT 'Returned to lesson',
    parent_contacted     INTEGER NOT NULL DEFAULT 0,
    parent_contact_time  TEXT,
    parent_contact_how   TEXT,
    hospital_referral    INTEGER NOT NULL DEFAULT 0,
    accident_book_ref    TEXT,
    riddor_reportable    INTEGER NOT NULL DEFAULT 0,
    riddor_reported_on   TEXT,
    riddor_reference     TEXT,
    follow_up            TEXT,
    notes                TEXT,
    created_by           TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by           TEXT,
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_first_aid_date ON first_aid_incidents (incident_date);
CREATE INDEX IF NOT EXISTS ix_first_aid_pupil ON first_aid_incidents (pupil_id);
CREATE TABLE IF NOT EXISTS medical_emergencies (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind                TEXT NOT NULL DEFAULT 'Drill',
    event_type          TEXT NOT NULL DEFAULT 'Fire',
    event_date          TEXT NOT NULL,
    start_time          TEXT,
    end_time            TEXT,
    duration_min        INTEGER,
    location            TEXT,
    trigger             TEXT,
    reported_by         TEXT,
    incident_commander  TEXT,
    pupils_evacuated    INTEGER,
    staff_evacuated     INTEGER,
    missing_count       INTEGER NOT NULL DEFAULT 0,
    injuries_count      INTEGER NOT NULL DEFAULT 0,
    emergency_services  INTEGER NOT NULL DEFAULT 0,
    services_attended   TEXT,
    outcome             TEXT NOT NULL DEFAULT 'Successful',
    status              TEXT NOT NULL DEFAULT 'Logged',
    lessons_learned     TEXT,
    follow_up_actions   TEXT,
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_medical_emergencies_date ON medical_emergencies (event_date);
"""
database.register_schema("medical_incidents", _SCHEMA)


@dataclass(frozen=True)
class Incident:
    incident_id: int
    pupil_id: int | None
    person_type: str
    person_name: str | None
    incident_date: str
    incident_time: str | None
    location: str
    injury_type: str
    severity: str
    body_part: str | None
    description: str
    treatment: str
    treated_by: str
    outcome: str
    parent_contacted: bool
    parent_contact_time: str | None
    parent_contact_how: str | None
    hospital_referral: bool
    accident_book_ref: str | None
    riddor_reportable: bool
    riddor_reported_on: str | None
    riddor_reference: str | None
    follow_up: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int | None = None

    @property
    def who(self) -> str:
        if self.pupil_id:
            return f"{self.pupil_name} ({self.admission_no})"
        return f"{self.person_name or '?'} ({self.person_type.lower()})"

    @property
    def riddor_due(self) -> str | None:
        if not self.riddor_reportable:
            return None
        return (_dt.date.fromisoformat(self.incident_date)
                + _dt.timedelta(days=RIDDOR_DAYS)).isoformat()


@dataclass(frozen=True)
class Emergency:
    event_id: int
    kind: str
    event_type: str
    event_date: str
    start_time: str | None
    end_time: str | None
    duration_min: int | None
    location: str | None
    trigger: str | None
    reported_by: str | None
    incident_commander: str | None
    pupils_evacuated: int | None
    staff_evacuated: int | None
    missing_count: int
    injuries_count: int
    emergency_services: bool
    services_attended: str | None
    outcome: str
    status: str
    lessons_learned: str | None
    follow_up_actions: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str


_BOOLS = ("parent_contacted", "hospital_referral", "riddor_reportable", "emergency_services")


def _incident(r) -> Incident:
    vals = {k: r[k] for k in Incident.__dataclass_fields__
            if k not in ("pupil_name", "admission_no", "pupil_year")}
    for k in _BOOLS:
        if k in vals:
            vals[k] = bool(vals[k])
    if r["admission_no"]:
        vals.update(pupil_name=f"{r['legal_last_name']}, "
                               f"{r['preferred_name'] or r['legal_first_name']}",
                    admission_no=r["admission_no"], pupil_year=r["pupil_year"])
    return Incident(**vals)


def _emergency(r) -> Emergency:
    vals = {k: r[k] for k in Emergency.__dataclass_fields__}
    vals["emergency_services"] = bool(vals["emergency_services"])
    return Emergency(**vals)


def _time(value: Any, label: str, problems: list[str]) -> str | None:
    if _blank(value):
        return None
    v = str(value).strip()
    if not _TIME_RE.match(v):
        problems.append(f"{label} must be a time (HH:MM)")
        return None
    return v


def _int(value: Any, label: str, problems: list[str], hi: int = 100000) -> int | None:
    n = _number(value, label, problems, hi=hi, whole=True)
    return None if n is None else int(n)


# ── First aid / accident book ────────────────────────────────────────

_FA_FIELDS = ("person_type", "person_name", "incident_date", "incident_time", "location",
              "injury_type", "severity", "body_part", "description", "treatment", "treated_by",
              "outcome", "parent_contacted", "parent_contact_time", "parent_contact_how",
              "hospital_referral", "accident_book_ref", "riddor_reportable",
              "riddor_reported_on", "riddor_reference", "follow_up", "notes")
_FA_SELECT = (f"SELECT x.*, {PUPIL_COLS} FROM first_aid_incidents x "
              "LEFT JOIN pupils p ON p.pupil_id = x.pupil_id")


def get_incident(incident_id: int) -> Incident:
    with database.connect() as conn:
        r = conn.execute(_FA_SELECT + " WHERE x.incident_id = ?", (int(incident_id),)).fetchone()
    if r is None:
        raise NotFound(f"No incident #{incident_id}")
    return _incident(r)


def list_incidents(*, pupil_id: int | None = None, severity: str | None = None,
                   riddor_only: bool = False, hospital_only: bool = False,
                   from_date: str | None = None, to_date: str | None = None,
                   year_group: int | str | None = None, person_type: str | None = None,
                   limit: int = 2000) -> list[Incident]:
    """Incidents newest first (the old filters: severity, RIDDOR only,
    hospital only, dates)."""
    where, params = [], []
    for col, val in (("x.pupil_id", pupil_id), ("x.severity", severity),
                     ("x.person_type", person_type)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if riddor_only:
        where.append("x.riddor_reportable = 1")
    if hospital_only:
        where.append("x.hospital_referral = 1")
    if from_date:
        where.append("x.incident_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("x.incident_date <= ?")
        params.append(to_date)
    if not _blank(year_group):
        where.append("p.year_group = ?")
        params.append(int(year_group))  # type: ignore[arg-type]
    sql = _FA_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY x.incident_date DESC, x.incident_time DESC, x.incident_id DESC LIMIT ?"
    with database.connect() as conn:
        return [_incident(r) for r in conn.execute(sql, (*params, int(limit)))]


def _clean_incident(data: dict[str, Any], cur: Incident | None, problems: list[str]
                    ) -> dict[str, Any]:
    merged = {k: getattr(cur, k) for k in _FA_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _FA_FIELDS})
    out: dict[str, Any] = {
        "person_type": _choice(merged.get("person_type"), PERSON_TYPES, "Person", problems,
                               "Pupil"),
        "injury_type": _choice(merged.get("injury_type"), INJURY_TYPES, "Injury type",
                               problems, DEFAULT_INJURY),
        "severity": _choice(merged.get("severity"), SEVERITIES, "Severity", problems,
                            DEFAULT_SEVERITY),
        "outcome": _choice(merged.get("outcome"), OUTCOMES, "Outcome", problems,
                           DEFAULT_OUTCOME),
        "parent_contact_how": _choice(merged.get("parent_contact_how"), TOLD_HOW,
                                      "Parents told how", problems, None)}
    day = _date(merged.get("incident_date"), "Date", problems) or _today().isoformat()
    if day > _today().isoformat():
        problems.append("The incident date can't be in the future")
    out["incident_date"] = day
    out["incident_time"] = _time(merged.get("incident_time"), "Time", problems)
    out["parent_contact_time"] = _text(merged.get("parent_contact_time"), 20)
    for k, label, n in (("location", "Location", 120), ("description", "Description", 2000),
                        ("treatment", "Treatment", 2000), ("treated_by", "Treated by", 80)):
        out[k] = _text(merged.get(k), n)
        if not out[k]:
            problems.append(f"{label} is required")
    out["person_name"] = _text(merged.get("person_name"), 120)
    for k, n in (("body_part", 60), ("accident_book_ref", 40), ("riddor_reference", 40),
                 ("follow_up", 1000), ("notes", 2000)):
        out[k] = _text(merged.get(k), n)
    out["riddor_reported_on"] = _date(merged.get("riddor_reported_on"), "RIDDOR reported on",
                                      problems)
    out["parent_contacted"] = int(_bool(merged.get("parent_contacted")))
    out["hospital_referral"] = int(_bool(merged.get("hospital_referral")) or
                                   out["outcome"] in HOSPITAL_OUTCOMES)
    out["riddor_reportable"] = int(_bool(merged.get("riddor_reportable")))
    if out["riddor_reported_on"]:
        out["riddor_reportable"] = 1
        if out["riddor_reported_on"] < day:
            problems.append("RIDDOR can't be reported before the incident")
    if out["parent_contacted"] and not out["parent_contact_time"]:
        out["parent_contact_time"] = _dt.datetime.now().strftime("%H:%M")
    return out


def check_incident(data: dict[str, Any]) -> list[str]:
    """Things worth a second look before saving an incident."""
    problems: list[str] = []
    c = _clean_incident(data, None, problems)
    out: list[str] = []
    if problems:
        return out
    pupil = c["person_type"] == "Pupil"
    if pupil and not c["parent_contacted"] and (
            c["injury_type"] in HEAD or (c["body_part"] or "").lower() == "head" or
            c["severity"] in ("Severe", "Critical") or c["hospital_referral"]):
        out.append("Tell the parents the same day - head injuries, serious injuries and "
                   "hospital visits always need a call home.")
    if c["hospital_referral"] and not c["riddor_reportable"]:
        out.append("Taken to hospital: if the accident was connected with school premises, "
                   "equipment, an activity or supervision it is RIDDOR reportable (within "
                   f"{RIDDOR_DAYS} days).")
    if c["severity"] == "Critical" and c["outcome"] not in HOSPITAL_OUTCOMES:
        out.append("A critical injury usually means an ambulance or hospital - check the "
                   "outcome.")
    return out


def create_incident(data: dict[str, Any], *, actor: Principal) -> Incident:
    """The old New incident. *data* carries ``pupil_id`` (id or admission no.)
    for a pupil, or ``person_name`` for staff / visitors."""
    _require_editor(actor, "first_aid")
    problems: list[str] = []
    c = _clean_incident(data, None, problems)
    p = _pupil(data.get("pupil_id") or data.get("pupil"))
    if c["person_type"] == "Pupil":
        if p is None:
            problems.append("Pupil ID is required" if _blank(data.get("pupil_id") or
                                                             data.get("pupil"))
                            else f"No pupil {data.get('pupil_id') or data.get('pupil')}")
        c["person_name"] = None
    else:
        p = None
        if not c["person_name"]:
            problems.append("Name the person who was hurt")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        iid = conn.execute(
            f"INSERT INTO first_aid_incidents (pupil_id, {', '.join(_FA_FIELDS)}, created_by, "
            f"updated_by) VALUES (?, {', '.join('?' * len(_FA_FIELDS))}, ?, ?)",
            (p.pupil_id if p else None, *(c[k] for k in _FA_FIELDS), actor.username,
             actor.username)).lastrowid
        _audit(conn, actor, "first_aid", "create", pupil_id=p.pupil_id if p else None,
               item_id=iid)
    activity_log.record("medical.first_aid", target=p.admission_no if p else None,
                        principal=actor, incident=iid)
    return get_incident(iid)


def update_incident(incident_id: int, changes: dict[str, Any], *, actor: Principal
                    ) -> Incident:
    cur = get_incident(incident_id)
    _require_editor(actor, "first_aid_update", cur.admission_no or None)
    problems: list[str] = []
    c = _clean_incident(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _FA_FIELDS if c[k] != (int(getattr(cur, k)) if k in _BOOLS
                                                 else getattr(cur, k))]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE first_aid_incidents SET "
                         + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE incident_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.incident_id))
            _audit(conn, actor, "first_aid", "update", pupil_id=cur.pupil_id,
                   item_id=cur.incident_id, fields=changed)
        activity_log.record("medical.first_aid_update", principal=actor,
                            incident=cur.incident_id)
    return get_incident(cur.incident_id)


def delete_incident(incident_id: int, *, actor: Principal, reason: str = "") -> bool:
    """Delete an incident entered in error (a RIDDOR-reported one is kept)."""
    cur = get_incident(incident_id)
    _require_editor(actor, "first_aid_delete")
    if cur.riddor_reported_on:
        raise ValidationError(["This incident was reported under RIDDOR - keep the record"])
    with database.connect() as conn:
        conn.execute("DELETE FROM first_aid_incidents WHERE incident_id = ?",
                     (cur.incident_id,))
        _audit(conn, actor, "first_aid", "delete", pupil_id=cur.pupil_id,
               item_id=cur.incident_id, reason=reason[:200] or None)
    activity_log.record("medical.first_aid_delete", principal=actor, incident=cur.incident_id)
    return True


def record_parents_told(incident_id: int, *, actor: Principal, how: str = "Phone call",
                        when: str | None = None) -> Incident:
    return update_incident(incident_id, {"parent_contacted": True, "parent_contact_how": how,
                                         "parent_contact_time": when or
                                         _dt.datetime.now().strftime("%H:%M")}, actor=actor)


def record_riddor(incident_id: int, *, actor: Principal, reported_on: str | None = None,
                  reference: str = "") -> Incident:
    """Record the RIDDOR report to the HSE."""
    if not reference.strip():
        raise ValidationError(["Give the HSE reference"])
    return update_incident(incident_id, {"riddor_reportable": True,
                                         "riddor_reported_on": reported_on or
                                         _today().isoformat(),
                                         "riddor_reference": reference}, actor=actor)


def riddor_outstanding(today: _dt.date | None = None) -> list[Incident]:
    """RIDDOR-reportable incidents not reported yet, oldest first."""
    rows = [i for i in list_incidents(riddor_only=True) if not i.riddor_reported_on]
    return sorted(rows, key=lambda i: i.incident_date)


def notify_parents(incident_id: int, *, actor: Principal, note: str = "") -> dict[str, Any]:
    """E-mail the family about a pupil's first aid incident; marks the parents
    as contacted by e-mail."""
    i = get_incident(incident_id)
    _require_editor(actor, "first_aid_notify")
    if not i.pupil_id:
        raise ValidationError(["Only a pupil's incident goes to their family"])
    p = P.get_pupil(i.pupil_id)
    res = family_letter("medical_first_aid_notice", "First aid notice", p, {
        "incident_date": i.incident_date, "incident_time": i.incident_time or "",
        "injury": f"{i.injury_type} ({i.severity.lower()})",
        "treatment": i.treatment, "outcome": i.outcome, "note": note.strip()}, actor)
    if res["emails"]:
        update_incident(i.incident_id, {"parent_contacted": True,
                                        "parent_contact_how": "E-mail"}, actor=actor)
    activity_log.record("medical.first_aid_notify", principal=actor, incident=i.incident_id,
                        emails=res["emails"])
    return res


def first_aid_summary(*, from_date: str | None = None, to_date: str | None = None
                      ) -> dict[str, Any]:
    """The old summary report, plus by month and RIDDOR outstanding."""
    rows = list_incidents(from_date=from_date, to_date=to_date)
    return {"total": len(rows), "by_severity": dict(Counter(r.severity for r in rows)),
            "by_injury": dict(Counter(r.injury_type for r in rows)),
            "by_outcome": dict(Counter(r.outcome for r in rows)),
            "by_location": dict(Counter(r.location for r in rows)),
            "by_month": dict(sorted(Counter(r.incident_date[:7] for r in rows).items())),
            "pupils": len({r.pupil_id for r in rows if r.pupil_id}),
            "parent_contacted": sum(1 for r in rows if r.parent_contacted),
            "hospital": sum(1 for r in rows if r.hospital_referral),
            "riddor": sum(1 for r in rows if r.riddor_reportable),
            "riddor_outstanding": sum(1 for r in rows if r.riddor_reportable and
                                      not r.riddor_reported_on)}


# ── Emergencies & drills ─────────────────────────────────────────────

_EM_FIELDS = ("kind", "event_type", "event_date", "start_time", "end_time", "duration_min",
              "location", "trigger", "reported_by", "incident_commander", "pupils_evacuated",
              "staff_evacuated", "missing_count", "injuries_count", "emergency_services",
              "services_attended", "outcome", "status", "lessons_learned",
              "follow_up_actions", "notes")


def get_emergency(event_id: int) -> Emergency:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM medical_emergencies WHERE event_id = ?",
                         (int(event_id),)).fetchone()
    if r is None:
        raise NotFound(f"No event #{event_id}")
    return _emergency(r)


def list_emergencies(*, kind: str | None = None, event_type: str | None = None,
                     status: str | None = None, outstanding_only: bool = False,
                     from_date: str | None = None, to_date: str | None = None
                     ) -> list[Emergency]:
    where, params = [], []
    for col, val in (("kind", kind), ("event_type", event_type), ("status", status)):
        if not _blank(val):
            where.append(f"{col} = ?")
            params.append(val)
    if outstanding_only:
        where.append("status IN ('Under review', 'Actions outstanding')")
    if from_date:
        where.append("event_date >= ?")
        params.append(from_date)
    if to_date:
        where.append("event_date <= ?")
        params.append(to_date)
    sql = "SELECT * FROM medical_emergencies" + (" WHERE " + " AND ".join(where)
                                                 if where else "")
    with database.connect() as conn:
        return [_emergency(r) for r in conn.execute(
            sql + " ORDER BY event_date DESC, event_id DESC", params)]


def _clean_emergency(data: dict[str, Any], cur: Emergency | None, problems: list[str]
                     ) -> dict[str, Any]:
    merged = {k: getattr(cur, k) for k in _EM_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _EM_FIELDS})
    out: dict[str, Any] = {
        "kind": _choice(merged.get("kind"), EVENT_KINDS, "Kind", problems, DEFAULT_KIND),
        "event_type": _choice(merged.get("event_type"), EMERGENCY_TYPES, "Type", problems,
                              DEFAULT_EMERGENCY),
        "outcome": _choice(merged.get("outcome"), EVENT_OUTCOMES, "Outcome", problems,
                           EVENT_OUTCOMES[0]),
        "status": _choice(merged.get("status"), EVENT_STATUSES, "Status", problems,
                          EVENT_STATUSES[0])}
    day = _date(merged.get("event_date"), "Date", problems) or _today().isoformat()
    if day > _today().isoformat() and out["kind"] != "Drill":
        problems.append("Only a drill can be logged ahead of time")
    out["event_date"] = day
    out["start_time"] = _time(merged.get("start_time"), "Start time", problems)
    out["end_time"] = _time(merged.get("end_time"), "End time", problems)
    dur = _int(merged.get("duration_min"), "Duration (min)", problems, hi=1440)
    if out["start_time"] and out["end_time"]:
        if out["end_time"] < out["start_time"]:
            problems.append("End time cannot be before start time")
        elif dur is None or (cur is not None and "duration_min" not in data):
            h1, m1 = map(int, out["start_time"].split(":"))
            h2, m2 = map(int, out["end_time"].split(":"))
            dur = (h2 * 60 + m2) - (h1 * 60 + m1)
    out["duration_min"] = dur
    for k in ("pupils_evacuated", "staff_evacuated"):
        out[k] = _int(merged.get(k), k.replace("_", " ").capitalize(), problems)
    for k in ("missing_count", "injuries_count"):
        out[k] = _int(merged.get(k), k.replace("_", " ").capitalize(), problems) or 0
    for k, n in (("location", 120), ("trigger", 200), ("reported_by", 80),
                 ("incident_commander", 80), ("services_attended", 200),
                 ("lessons_learned", 2000), ("follow_up_actions", 2000), ("notes", 2000)):
        out[k] = _text(merged.get(k), n)
    out["emergency_services"] = int(_bool(merged.get("emergency_services")) or
                                    bool(out["services_attended"]))
    if out["status"] == "Closed" and out["missing_count"]:
        problems.append("People are still recorded as missing - account for everyone "
                        "(set missing to 0) before closing")
    if out["status"] == "Actions outstanding" and not out["follow_up_actions"]:
        problems.append("List the follow-up actions")
    return out


def create_emergency(data: dict[str, Any], *, actor: Principal) -> Emergency:
    _require_editor(actor, "emergency")
    problems: list[str] = []
    c = _clean_emergency(data, None, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        eid = conn.execute(
            f"INSERT INTO medical_emergencies ({', '.join(_EM_FIELDS)}, created_by, updated_by) "
            f"VALUES ({', '.join('?' * len(_EM_FIELDS))}, ?, ?)",
            (*(c[k] for k in _EM_FIELDS), actor.username, actor.username)).lastrowid
        _audit(conn, actor, "emergency", "create", pupil_id=None, item_id=eid,
               kind=c["kind"], type=c["event_type"])
    activity_log.record("medical.emergency", principal=actor, event=eid)
    return get_emergency(eid)


def update_emergency(event_id: int, changes: dict[str, Any], *, actor: Principal
                     ) -> Emergency:
    cur = get_emergency(event_id)
    _require_editor(actor, "emergency_update")
    problems: list[str] = []
    c = _clean_emergency(changes, cur, problems)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in _EM_FIELDS if c[k] != (int(getattr(cur, k)) if k in _BOOLS
                                                 else getattr(cur, k))]
    if changed:
        with database.connect() as conn:
            conn.execute("UPDATE medical_emergencies SET "
                         + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE event_id = ?",
                         (*(c[k] for k in changed), actor.username, cur.event_id))
            _audit(conn, actor, "emergency", "update", pupil_id=None, item_id=cur.event_id,
                   fields=changed)
        activity_log.record("medical.emergency_update", principal=actor, event=cur.event_id)
    return get_emergency(cur.event_id)


def set_emergency_status(event_id: int, status: str, *, actor: Principal) -> Emergency:
    return update_emergency(event_id, {"status": status}, actor=actor)


def close_emergency(event_id: int, *, actor: Principal) -> Emergency:
    """The old Close event."""
    return set_emergency_status(event_id, "Closed", actor=actor)


def delete_emergency(event_id: int, *, actor: Principal) -> bool:
    cur = get_emergency(event_id)
    _require_editor(actor, "emergency_delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM medical_emergencies WHERE event_id = ?", (cur.event_id,))
        _audit(conn, actor, "emergency", "delete", pupil_id=None, item_id=cur.event_id)
    activity_log.record("medical.emergency_delete", principal=actor, event=cur.event_id)
    return True


def emergency_summary(*, from_date: str | None = None, to_date: str | None = None
                      ) -> dict[str, Any]:
    """The old Emergency & Drills summary report."""
    rows = list_emergencies(from_date=from_date, to_date=to_date)
    durations = [r.duration_min for r in rows if r.duration_min is not None]
    return {"total": len(rows), "drills": sum(1 for r in rows if r.kind == "Drill"),
            "real": sum(1 for r in rows if r.kind == "Real"),
            "outstanding": sum(1 for r in rows if r.status in ("Under review",
                                                                "Actions outstanding")),
            "by_type": dict(Counter(r.event_type for r in rows)),
            "by_outcome": dict(Counter(r.outcome for r in rows)),
            "by_status": dict(Counter(r.status for r in rows)),
            "total_missing": sum(r.missing_count for r in rows),
            "total_injuries": sum(r.injuries_count for r in rows),
            "services_called": sum(1 for r in rows if r.emergency_services),
            "avg_duration_min": round(sum(durations) / len(durations), 1)
            if durations else None}


def drills_this_term(today: _dt.date | None = None) -> dict[str, Any]:
    """Fire drills: the last one and whether one has been held this term
    (schools hold one at least once a term)."""
    day = today or _today()
    drills = [e for e in list_emergencies(kind="Drill", event_type="Fire")
              if e.event_date <= day.isoformat()]
    last = drills[0].event_date if drills else None
    start = day - _dt.timedelta(days=84)
    try:
        from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
        t = AY.term_for(day)
        if t:
            start = _dt.date.fromisoformat(t.start_date)
    except Exception:  # noqa: BLE001 - the calendar is a help, not a gate
        pass
    return {"last": last, "this_term": bool(last and last >= start.isoformat()),
            "term_start": start.isoformat()}


def _staff_check(actor: Principal) -> None:
    _require_staff(actor, "view")
