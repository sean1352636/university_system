"""Behaviour & rewards: the school's log of positive and negative behaviour.

Kept from the old Behaviour Log:

* One entry per event, positive (Achievement, House points, Helping others,
  Above and beyond, Good attendance, Other positive) or negative
  (Disruption, Lateness, No homework, Uniform, Defiance, Bullying,
  Physical, Verbal abuse, Damage, Phone misuse, Other negative), with date,
  time (HH:MM), location, subject, points, severity (Low, Medium, High,
  Critical), description (required, 500 characters), raised by, action
  taken, status (Open, Resolved, Escalated, Withdrawn) and notes.
* Points carry the type's sign: +1 / -1 by default, -100..100, a positive
  type can't take negative points and vice versa - so totals just add up.
* The pupil summary, the cohort summary and the "pupils on the negative
  threshold" report (net points at or below -10).

New:

* **Types are the school's own.** The old types are there from the start;
  the behaviour lead (:data:`BEHAVIOUR_EDITORS`) can add types, change a
  type's default points or retire it.
* **Several pupils at once** - praise a whole group, or log the same
  incident for everyone involved.
* **Withdrawn entries don't count** towards any total.
* **Rewards.** Positive points in a school year reach Bronze (50), Silver
  (100), Gold (200) and Platinum (300); each milestone is recorded when it's
  reached and can be marked presented.
* **Houses.** Pupils belong to a house (singly, or a whole form at once);
  the house table adds up the year's positive points.
* **Concerns.** Pupils with several negative entries in a week, an open
  High / Critical incident, a net total on the threshold, or several missed
  detentions this term - for the head
  of year, and as "who needs an intervention?" suggestions.
* **Families.** A note home (e-mail to contacts with parental
  responsibility) for chosen entries; entries can be shared with the parent
  and pupil portal (positive ones are shared by default).
* **Who.** Any member of staff logs entries and edits or withdraws their
  own while they're open; the pupil's head of year and the behaviour lead
  can change any entry's status; only the lead deletes. Every change goes in
  ``behaviour_audit`` and the activity log (ids only).
* **Reports.** By type, subject, member of staff, day of week, hour and
  year group; the reward leaderboard; CSV export.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S  # registers the FK target
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    BEHAVIOUR_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import current_year, year_of
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

#: The old types (label -> polarity); they are the starting list.
INCIDENT_TYPES: dict[str, str] = {
    "Achievement": "positive", "House points": "positive", "Helping others": "positive",
    "Above and beyond": "positive", "Good attendance": "positive",
    "Other positive": "positive",
    "Disruption": "negative", "Lateness": "negative", "No homework": "negative",
    "Uniform": "negative", "Defiance": "negative", "Bullying": "negative",
    "Physical": "negative", "Verbal abuse": "negative", "Damage": "negative",
    "Phone misuse": "negative", "Other negative": "negative",
}
POLARITIES = ("positive", "negative")
SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY = "Low"
INCIDENT_STATUSES: tuple[str, ...] = ("Open", "Resolved", "Escalated", "Withdrawn")
DEFAULT_STATUS = "Open"
MAX_POINTS = 100
MAX_DESCRIPTION = 500
THRESHOLD = -10
#: (level, positive points in the school year)
REWARD_LEVELS: tuple[tuple[str, int], ...] = (("Bronze", 50), ("Silver", 100),
                                              ("Gold", 200), ("Platinum", 300))
#: A concern: this many negative entries in CONCERN_DAYS days.
CONCERN_COUNT = 3
CONCERN_DAYS = 7
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_COLOUR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS behaviour_types (
    type_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    polarity        TEXT NOT NULL CHECK (polarity IN ('positive', 'negative')),
    default_points  INTEGER NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    created_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS behaviour_entries (
    entry_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year       TEXT NOT NULL,
    entry_date          TEXT NOT NULL,
    entry_time          TEXT,
    location            TEXT,
    subject_id          INTEGER REFERENCES subjects (subject_id),
    incident_type       TEXT NOT NULL,
    polarity            TEXT NOT NULL CHECK (polarity IN ('positive', 'negative')),
    points              INTEGER NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'Low',
    description         TEXT NOT NULL,
    raised_by           TEXT,
    raised_by_username  TEXT,
    action_taken        TEXT,
    status              TEXT NOT NULL DEFAULT 'Open' CHECK (status IN
                        ('Open', 'Resolved', 'Escalated', 'Withdrawn')),
    escalated_to        TEXT,
    notes               TEXT,
    share_with_parents  INTEGER NOT NULL DEFAULT 0,
    parents_notified_at TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((polarity = 'positive' AND points >= 0) OR (polarity = 'negative' AND points <= 0))
);
CREATE INDEX IF NOT EXISTS ix_behaviour_pupil ON behaviour_entries (pupil_id, academic_year);
CREATE INDEX IF NOT EXISTS ix_behaviour_date ON behaviour_entries (entry_date);
CREATE TABLE IF NOT EXISTS houses (
    house_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    colour      TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS house_members (
    pupil_id    INTEGER PRIMARY KEY REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    house_id    INTEGER NOT NULL REFERENCES houses (house_id),
    assigned_by TEXT,
    assigned_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS reward_milestones (
    milestone_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id      INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year TEXT NOT NULL,
    level         TEXT NOT NULL,
    points        INTEGER NOT NULL,
    reached_at    TEXT NOT NULL DEFAULT (datetime('now')),
    presented_at  TEXT,
    presented_by  TEXT,
    UNIQUE (pupil_id, academic_year, level)
);
CREATE TABLE IF NOT EXISTS behaviour_audit (
    audit_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id  INTEGER,
    pupil_id  INTEGER,
    action    TEXT NOT NULL,
    detail    TEXT,
    actor     TEXT NOT NULL,
    at        TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("behaviour", _SCHEMA)


@dataclass(frozen=True)
class BehaviourType:
    type_id: int
    name: str
    polarity: str
    default_points: int
    active: bool


@dataclass(frozen=True)
class Entry:
    entry_id: int
    pupil_id: int
    academic_year: str
    entry_date: str
    entry_time: str | None
    location: str | None
    subject_id: int | None
    incident_type: str
    polarity: str
    points: int
    severity: str
    description: str
    raised_by: str | None
    raised_by_username: str | None
    action_taken: str | None
    status: str
    escalated_to: str | None
    notes: str | None
    share_with_parents: bool
    parents_notified_at: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    subject_code: str | None = None
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def counts(self) -> bool:
        return self.status != "Withdrawn"


@dataclass(frozen=True)
class House:
    house_id: int
    name: str
    colour: str | None
    active: bool


_SELECT = """
SELECT e.*, s.code AS subject_code, p.legal_last_name, p.legal_first_name, p.preferred_name,
       p.admission_no, p.year_group AS pupil_year, p.form_group
FROM behaviour_entries e JOIN pupils p USING (pupil_id)
LEFT JOIN subjects s ON s.subject_id = e.subject_id
"""
_BASE = tuple(f for f in Entry.__dataclass_fields__ if f not in (
    "subject_code", "pupil_name", "admission_no", "pupil_year", "form_group"))


def _row(r) -> Entry:
    d = {k: r[k] for k in _BASE}
    d["share_with_parents"] = bool(d["share_with_parents"])
    return Entry(**d, subject_code=r["subject_code"],
                 pupil_name=f"{r['legal_last_name']}, "
                            f"{r['preferred_name'] or r['legal_first_name']}",
                 admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                 form_group=r["form_group"])


# ── Helpers ──────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in BEHAVIOUR_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"behaviour.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can record behaviour.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the behaviour lead can do that.")


def _audit(conn, action: str, actor: Principal, entry_id: int | None, pupil_id: int | None,
           **detail: Any) -> None:
    conn.execute("INSERT INTO behaviour_audit (entry_id, pupil_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (entry_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(entry_id: int | None = None, *, pupil_id: int | None = None, limit: int = 300
            ) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM behaviour_audit", [], []
    if entry_id is not None:
        where.append("entry_id = ?")
        params.append(int(entry_id))
    if pupil_id is not None:
        where.append("pupil_id = ?")
        params.append(int(pupil_id))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "entry_id": r["entry_id"], "pupil_id": r["pupil_id"],
                 "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def _staff_name(actor: Principal) -> str:
    from education_system.systems.secondary.infrastructure.authentication import accounts
    try:
        for s in accounts.staff_logins():
            if s["username"].lower() == (actor.username or "").lower():
                return s["display_name"] or actor.username
    except Exception:  # noqa: BLE001 - the name is a convenience
        pass
    return actor.username or ""


def _me(actor: Principal) -> set[str]:
    from education_system.systems.secondary.infrastructure.authentication import accounts
    out = {(actor.username or "").lower()}
    try:
        for s in accounts.staff_logins():
            if s["username"].lower() == (actor.username or "").lower():
                out |= {(s["display_name"] or "").lower(), (s["email"] or "").lower()}
    except Exception:  # noqa: BLE001
        pass
    return {x for x in out if x}


def is_head_of_year(actor: Principal, year_group: int) -> bool:
    from education_system.systems.secondary.modules.curriculum.domain import year_groups as YG
    y = YG.get(year_group)
    return bool({(y.head_of_year or "").lower(), (y.head_of_year_email or "").lower()}
                & _me(actor) - {""})


def _is_raiser(actor: Principal, e: Entry) -> bool:
    return bool(actor.username) and (e.raised_by_username or "").lower() == \
        actor.username.lower()


def can_edit(actor: Principal, e: Entry) -> bool:
    """Details: the lead always; the person who raised it while it's open."""
    return is_editor(actor) or (_is_raiser(actor, e) and e.status == "Open")


def can_set_status(actor: Principal, e: Entry) -> bool:
    return is_editor(actor) or _is_raiser(actor, e) or (
        actor.role in STAFF_ROLES and is_head_of_year(actor, e.pupil_year))


# ── Types ────────────────────────────────────────────────────────────

def _ensure_types(conn) -> None:
    if conn.execute("SELECT 1 FROM behaviour_types LIMIT 1").fetchone():
        return
    conn.executemany("INSERT OR IGNORE INTO behaviour_types (name, polarity, default_points, "
                     "created_by) VALUES (?, ?, ?, 'system')",
                     [(n, pol, 1 if pol == "positive" else -1)
                      for n, pol in INCIDENT_TYPES.items()])


def list_types(*, include_retired: bool = False, polarity: str | None = None
               ) -> list[BehaviourType]:
    with database.connect() as conn:
        _ensure_types(conn)
        sql = "SELECT * FROM behaviour_types WHERE 1 = 1"
        params: list[Any] = []
        if not include_retired:
            sql += " AND active = 1"
        if polarity:
            sql += " AND polarity = ?"
            params.append(polarity)
        return [BehaviourType(r["type_id"], r["name"], r["polarity"], r["default_points"],
                              bool(r["active"]))
                for r in conn.execute(sql + " ORDER BY polarity DESC, type_id", params)]


def get_type(name: str) -> BehaviourType | None:
    return next((t for t in list_types(include_retired=True)
                 if t.name.lower() == str(name or "").strip().lower()), None)


def _points(raw: Any, polarity: str, label: str, problems: list[str]) -> int | None:
    try:
        pts = int(str(raw).strip())
    except (TypeError, ValueError):
        problems.append(f"{label} must be a whole number")
        return None
    if not -MAX_POINTS <= pts <= MAX_POINTS:
        problems.append(f"{label} must be between -{MAX_POINTS} and {MAX_POINTS}")
    elif polarity == "positive" and pts < 0:
        problems.append("Positive incident types cannot have negative points")
    elif polarity == "negative" and pts > 0:
        problems.append("Negative incident types cannot have positive points")
    return pts


def save_type(name: str, polarity: str, default_points: Any = None, *, actor: Principal,
              active: bool = True) -> BehaviourType:
    """Add a type, or change an existing type's default points / retire it.
    A type's polarity can't change once it's in use."""
    _require_editor(actor, "type.save")
    problems: list[str] = []
    label = " ".join(str(name or "").split())
    if not label or len(label) > 40:
        problems.append("A type name is 1-40 characters")
    pol = str(polarity or "").strip().lower()
    if pol not in POLARITIES:
        problems.append("Polarity must be positive or negative")
    pts = _points(default_points if default_points not in (None, "") else
                  (1 if pol == "positive" else -1), pol, "Default points", problems)
    if problems:
        raise ValidationError(problems)
    current = get_type(label)
    with database.connect() as conn:
        if current:
            if current.polarity != pol and conn.execute(
                    "SELECT 1 FROM behaviour_entries WHERE incident_type = ? LIMIT 1",
                    (current.name,)).fetchone():
                raise ValidationError([f"'{current.name}' is in use - it can't change from "
                                       f"{current.polarity} to {pol}"])
            conn.execute("UPDATE behaviour_types SET polarity = ?, default_points = ?, "
                         "active = ? WHERE type_id = ?", (pol, pts, int(active),
                                                          current.type_id))
        else:
            conn.execute("INSERT INTO behaviour_types (name, polarity, default_points, active, "
                         "created_by) VALUES (?, ?, ?, ?, ?)",
                         (label, pol, pts, int(active), actor.username))
        _audit(conn, "type.save", actor, None, None, name=label, polarity=pol, points=pts,
               active=active)
    activity_log.record("behaviour.type.save", principal=actor)
    return get_type(label)  # type: ignore[return-value]


# ── Reading ──────────────────────────────────────────────────────────

def get(entry_id: int) -> Entry:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE e.entry_id = ?", (int(entry_id),)).fetchone()
    if r is None:
        raise NotFound(f"No behaviour entry #{entry_id}")
    return _row(r)


def list_entries(*, pupil_id: int | None = None, year_group: int | str | None = None,
                 form_group: str | None = None, incident_type: str | None = None,
                 polarity: str | None = None, severity: str | None = None,
                 status: str | None = None, date_from: str | None = None,
                 date_to: str | None = None, academic_year: str | None = None,
                 subject_id: int | None = None, raised_by: str | None = None,
                 search: str | None = None, shared_only: bool = False,
                 include_withdrawn: bool = True, limit: int | None = None) -> list[Entry]:
    sql, where, params = _SELECT, [], []
    for col, val in (("e.pupil_id", pupil_id), ("p.year_group", year_group),
                     ("p.form_group", form_group), ("e.incident_type", incident_type),
                     ("e.polarity", polarity), ("e.severity", severity),
                     ("e.status", status), ("e.academic_year", academic_year),
                     ("e.subject_id", subject_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(int(val) if col in ("e.pupil_id", "p.year_group", "e.subject_id")
                          else val)
    problems: list[str] = []
    for op, val, label in ((">=", date_from, "From date"), ("<=", date_to, "To date")):
        d = _date(val, label, problems) if val else None
        if d:
            where.append(f"e.entry_date {op} ?")
            params.append(d)
    if problems:
        raise ValidationError(problems)
    if raised_by:
        where.append("lower(COALESCE(e.raised_by_username, e.raised_by, '')) = ?")
        params.append(raised_by.lower())
    if search:
        where.append("(e.description LIKE ? OR p.admission_no = ? OR p.legal_last_name LIKE ?)")
        params += [f"%{search}%", search.strip().upper(), f"{search.strip()}%"]
    if shared_only:
        where.append("e.share_with_parents = 1")
    if not include_withdrawn:
        where.append("e.status != 'Withdrawn'")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY e.entry_date DESC, COALESCE(e.entry_time, '') DESC, e.entry_id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql, params)]


def recent(limit: int = 8) -> list[Entry]:
    """The latest entries (for the home screen)."""
    return list_entries(include_withdrawn=False, limit=limit)


# ── Logging and changing ─────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str]) -> str | None:
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str) -> str:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _subject(ref: Any, problems: list[str]) -> int | None:
    if ref in (None, "") or (isinstance(ref, str) and not ref.strip()):
        return None
    try:
        s = S.get(int(ref)) if str(ref).strip().isdigit() else S.get_by_code(str(ref).strip())
    except Exception:  # noqa: BLE001 - shown as a problem
        s = None
    if s is None:
        problems.append(f"No subject {ref}")
        return None
    return s.subject_id


FIELDS = ("entry_date", "entry_time", "location", "subject_id", "incident_type", "polarity",
          "points", "severity", "description", "raised_by", "action_taken", "status",
          "escalated_to", "notes", "share_with_parents")


def _clean(data: dict[str, Any], current: Entry | None, actor: Principal
           ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}
    out["entry_date"] = _date(merged.get("entry_date") or _today().isoformat(), "Date",
                              problems)
    if out["entry_date"] and out["entry_date"] > _today().isoformat():
        problems.append("Behaviour can't be logged for a future date")
    t = str(merged.get("entry_time") or "").strip()
    if t and not _TIME_RE.match(t):
        problems.append("Time must be HH:MM (24-hour)")
    out["entry_time"] = t or None
    out["location"] = (str(merged.get("location") or "").strip()[:80]) or None
    out["subject_id"] = _subject(data.get("subject", merged.get("subject_id")), problems) \
        if "subject" in data or merged.get("subject_id") else None
    type_name = str(merged.get("incident_type") or "").strip()
    bt = get_type(type_name) if type_name else None
    if not type_name:
        problems.append("Incident type is required")
    elif bt is None or (not bt.active and (current is None
                                           or current.incident_type != bt.name)):
        problems.append(f"'{type_name}' isn't a behaviour type in use")
    out["incident_type"] = bt.name if bt else type_name
    out["polarity"] = bt.polarity if bt else (current.polarity if current else "negative")
    raw = merged.get("points")
    if current and "incident_type" in data and data["incident_type"] != current.incident_type \
            and "points" not in data:
        raw = None  # new type: its default points
    out["points"] = (bt.default_points if bt else 0) if raw in (None, "") or (
        isinstance(raw, str) and not raw.strip()) else _points(raw, out["polarity"], "Points",
                                                                problems)
    out["severity"] = _choice(merged.get("severity"), SEVERITIES, "Severity", problems,
                              DEFAULT_SEVERITY)
    desc = " ".join(str(merged.get("description") or "").split())
    if not desc:
        problems.append("Description is required")
    elif len(desc) > MAX_DESCRIPTION:
        problems.append(f"Description must be {MAX_DESCRIPTION} chars or fewer")
    out["description"] = desc
    out["raised_by"] = (str(merged.get("raised_by") or "").strip()[:80]) or (
        _staff_name(actor) if current is None else None)
    out["action_taken"] = (str(merged.get("action_taken") or "").strip()[:1000]) or None
    out["status"] = _choice(merged.get("status"), INCIDENT_STATUSES, "Status", problems,
                            DEFAULT_STATUS)
    out["escalated_to"] = (str(merged.get("escalated_to") or "").strip()[:80]) or None
    if out["status"] == "Escalated" and not out["escalated_to"]:
        problems.append("Say who it was escalated to")
    out["notes"] = (str(merged.get("notes") or "").strip()[:2000]) or None
    share = merged.get("share_with_parents")
    if share in (None, "") and current is None:
        share = out["polarity"] == "positive"
    out["share_with_parents"] = int(str(share).strip().lower() in ("1", "true", "yes", "y")
                                    if isinstance(share, str) else bool(share))
    return out, problems


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


def _insert(conn, pupil: P.Pupil, c: dict[str, Any], actor: Principal) -> int:
    eid = conn.execute(
        f"INSERT INTO behaviour_entries (pupil_id, academic_year, raised_by_username, "
        f"{', '.join(FIELDS)}, updated_by) VALUES (?, ?, ?, {', '.join('?' * len(FIELDS))}, ?)",
        (pupil.pupil_id, year_of(c["entry_date"]), actor.username,
         *(c[k] for k in FIELDS), actor.username)).lastrowid
    _audit(conn, "log", actor, eid, pupil.pupil_id, type=c["incident_type"],
           points=c["points"])
    return eid


def log_many(pupils: list[Any], data: dict[str, Any], *, actor: Principal) -> list[Entry]:
    """The same entry for several pupils (ids or admission numbers). All or
    nothing."""
    _require_staff(actor, "log")
    c, problems = _clean(data, None, actor)
    found: list[P.Pupil] = []
    for ref in dict.fromkeys(pupils or []):
        p = _pupil(ref)
        if p is None:
            problems.append(f"No pupil {ref}")
        elif p.roll_status != "on_roll":
            problems.append(f"{p.display_name} is not on roll")
        else:
            found.append(p)
    if not pupils:
        problems.append("Pupil is required")
    if problems:
        activity_log.record("behaviour.log", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        ids = [_insert(conn, p, c, actor) for p in found]
    for p in found:
        _check_milestones(p.pupil_id, year_of(c["entry_date"]), actor)
    activity_log.record("behaviour.log", principal=actor, pupils=len(found),
                        type=c["incident_type"], polarity=c["polarity"])
    return [get(i) for i in ids]


def log_incident(data: dict[str, Any], *, actor: Principal) -> Entry:
    """Log one entry (the old Log). *data* carries ``pupil_id`` or ``pupil``."""
    return log_many([data.get("pupil_id") or data.get("pupil")],
                    {k: v for k, v in data.items() if k not in ("pupil_id", "pupil")},
                    actor=actor)[0]


def update(entry_id: int, changes: dict[str, Any], *, actor: Principal) -> Entry:
    """The old Edit. The person who raised it can edit it while it's open."""
    e = get(entry_id)
    if not can_edit(actor, e):
        _deny(actor, "update", e.admission_no,
              "Only the person who logged it (while it's open) or the behaviour lead can "
              "change it.")
    if "status" in changes and changes["status"] not in (None, "", e.status):
        return set_status(e.entry_id, changes["status"], actor=actor,
                          escalated_to=changes.get("escalated_to"))
    c, problems = _clean(changes, e, actor)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in FIELDS if c[k] != (int(getattr(e, k)) if k == "share_with_parents"
                                             else getattr(e, k))]
    if not changed:
        return e
    with database.connect() as conn:
        conn.execute("UPDATE behaviour_entries SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", academic_year = ?, updated_by = ?, updated_at = datetime('now') "
                       "WHERE entry_id = ?",
                     (*(c[k] for k in changed), year_of(c["entry_date"]), actor.username,
                      e.entry_id))
        _audit(conn, "update", actor, e.entry_id, e.pupil_id, fields=changed)
    _check_milestones(e.pupil_id, year_of(c["entry_date"]), actor)
    activity_log.record("behaviour.update", target=e.admission_no, principal=actor,
                        fields=",".join(changed))
    return get(e.entry_id)


def set_status(entry_id: int, status: str, *, actor: Principal,
               escalated_to: str | None = None, action_taken: str | None = None) -> Entry:
    """The old Status. Escalated needs who it went to; Withdrawn entries stop
    counting (and can be restored by setting another status)."""
    e = get(entry_id)
    if not can_set_status(actor, e):
        _deny(actor, "status", e.admission_no,
              "Only the person who logged it, the head of year or the behaviour lead can "
              "change its status.")
    problems: list[str] = []
    st = _choice(status, INCIDENT_STATUSES, "Status", problems, "")
    to = (escalated_to or "").strip() or e.escalated_to
    if st == "Escalated" and not to:
        problems.append("Say who it was escalated to")
    if problems or not st:
        raise ValidationError(problems or ["Status is required"])
    sets: dict[str, Any] = {"status": st, "escalated_to": to if st == "Escalated" else
                            e.escalated_to}
    if action_taken:
        sets["action_taken"] = ((e.action_taken + "\n") if e.action_taken else "") + \
            action_taken.strip()
    with database.connect() as conn:
        conn.execute("UPDATE behaviour_entries SET " + ", ".join(f"{k} = ?" for k in sets)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE entry_id = ?",
                     (*sets.values(), actor.username, e.entry_id))
        _audit(conn, "status", actor, e.entry_id, e.pupil_id, frm=e.status, to=st)
    _check_milestones(e.pupil_id, e.academic_year, actor)
    activity_log.record("behaviour.status", target=e.admission_no, principal=actor, status=st)
    return get(e.entry_id)


def add_action(entry_id: int, text: str, *, actor: Principal) -> Entry:
    """Add a line to an entry's "action taken" (e.g. a detention set for it).
    Any member of staff - the line says who and is audited."""
    _require_staff(actor, "action")
    e = get(entry_id)
    line = " ".join(str(text or "").split())[:300]
    if not line:
        raise ValidationError(["Say what action was taken"])
    with database.connect() as conn:
        conn.execute("UPDATE behaviour_entries SET action_taken = ?, updated_by = ?, "
                     "updated_at = datetime('now') WHERE entry_id = ?",
                     (((e.action_taken + "\n") if e.action_taken else "") + line,
                      actor.username, e.entry_id))
        _audit(conn, "action", actor, e.entry_id, e.pupil_id)
    activity_log.record("behaviour.action", target=e.admission_no, principal=actor)
    return get(e.entry_id)


def delete(entry_id: int, *, actor: Principal, reason: str | None = None) -> bool:
    """The old Delete - the behaviour lead only (others withdraw)."""
    e = get(entry_id)
    _require_editor(actor, "delete", e.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM behaviour_entries WHERE entry_id = ?", (e.entry_id,))
        _audit(conn, "delete", actor, e.entry_id, e.pupil_id, type=e.incident_type,
               points=e.points, reason=(reason or "")[:300] or None)
    activity_log.record("behaviour.delete", target=e.admission_no, principal=actor)
    return True


# ── Summaries (old) ──────────────────────────────────────────────────

def pupil_summary(pupil_id: int, *, date_from: str | None = None, date_to: str | None = None,
                  academic_year: str | None = None) -> dict[str, Any]:
    rows = list_entries(pupil_id=pupil_id, date_from=date_from, date_to=date_to,
                        academic_year=academic_year)
    live = [r for r in rows if r.counts]
    return {"pupil_id": int(pupil_id), "total": len(live),
            "positive": sum(1 for r in live if r.polarity == "positive"),
            "negative": sum(1 for r in live if r.polarity == "negative"),
            "positive_points": sum(r.points for r in live if r.points > 0),
            "negative_points": sum(r.points for r in live if r.points < 0),
            "total_points": sum(r.points for r in live),
            "by_type": dict(Counter(r.incident_type for r in live)),
            "by_status": dict(Counter(r.status for r in rows)),
            "by_severity": dict(Counter(r.severity for r in live)),
            "incidents": rows, "house": house_of(pupil_id),
            "milestones": milestones(pupil_id=pupil_id,
                                     academic_year=academic_year or current_year())}


def cohort_summary(*, year_group: int | str | None = None, date_from: str | None = None,
                   date_to: str | None = None, academic_year: str | None = None
                   ) -> dict[str, Any]:
    rows = [r for r in list_entries(year_group=year_group, date_from=date_from,
                                    date_to=date_to, academic_year=academic_year) if r.counts]
    return {"total": len(rows),
            "positive": sum(1 for r in rows if r.polarity == "positive"),
            "negative": sum(1 for r in rows if r.polarity == "negative"),
            "open": sum(1 for r in rows if r.status == "Open"),
            "ratio": (round(sum(1 for r in rows if r.polarity == "positive")
                            / max(1, sum(1 for r in rows if r.polarity == "negative")), 1)),
            "by_type": dict(Counter(r.incident_type for r in rows)),
            "by_severity": dict(Counter(r.severity for r in rows)),
            "by_status": dict(Counter(r.status for r in rows)),
            "pupils": len({r.pupil_id for r in rows})}


def _totals(**filters: Any) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for r in list_entries(include_withdrawn=False, **filters):
        t = out.setdefault(r.pupil_id, {"pupil_id": r.pupil_id, "admission_no": r.admission_no,
                                        "pupil_name": r.pupil_name, "year_group": r.pupil_year,
                                        "form_group": r.form_group, "net": 0, "positive": 0,
                                        "negative": 0, "entries": 0})
        t["net"] += r.points
        t["positive" if r.points > 0 else "negative"] += r.points
        t["entries"] += 1
    return out


def pupils_above_threshold(*, points_below: int = THRESHOLD,
                           year_group: int | str | None = None,
                           academic_year: str | None = None) -> list[dict[str, Any]]:
    """The old threshold report: pupils whose net points are at or below
    *points_below* (default -10), worst first."""
    rows = [t for t in _totals(year_group=year_group, academic_year=academic_year).values()
            if t["net"] <= points_below]
    return sorted(rows, key=lambda t: (t["net"], t["pupil_name"]))


def leaderboard(*, year_group: int | str | None = None, academic_year: str | None = None,
                limit: int = 20) -> list[dict[str, Any]]:
    """Most positive points this year."""
    rows = [t for t in _totals(year_group=year_group,
                               academic_year=academic_year or current_year()).values()
            if t["positive"] > 0]
    return sorted(rows, key=lambda t: (-t["positive"], t["pupil_name"]))[:limit]


def concerns(*, year_group: int | str | None = None, today: _dt.date | None = None
             ) -> list[dict[str, Any]]:
    """Pupils needing a look: CONCERN_COUNT+ negative entries in the last
    CONCERN_DAYS days, an open High / Critical incident, or net points on
    the threshold this year."""
    day = today or _today()
    since = (day - _dt.timedelta(days=CONCERN_DAYS - 1)).isoformat()
    year = current_year(day)
    out: dict[int, dict[str, Any]] = {}

    def add(pid: int, name: str, adm: str, yg: int, reason: str, severity: int) -> None:
        x = out.setdefault(pid, {"pupil_id": pid, "pupil_name": name, "admission_no": adm,
                                 "year_group": yg, "reasons": [], "severity": 0})
        x["reasons"].append(reason)
        x["severity"] = max(x["severity"], severity)

    week = Counter()
    who: dict[int, Entry] = {}
    for r in list_entries(year_group=year_group, academic_year=year, polarity="negative",
                          include_withdrawn=False):
        who[r.pupil_id] = r
        if r.entry_date >= since:
            week[r.pupil_id] += 1
        if r.status in ("Open", "Escalated") and r.severity in ("High", "Critical"):
            add(r.pupil_id, r.pupil_name, r.admission_no, r.pupil_year,
                f"{r.severity} {r.incident_type.lower()} on {r.entry_date} ({r.status.lower()})",
                2)
    for pid, n in week.items():
        if n >= CONCERN_COUNT:
            r = who[pid]
            add(pid, r.pupil_name, r.admission_no, r.pupil_year,
                f"{n} negative entries in {CONCERN_DAYS} days", 1)
    for t in pupils_above_threshold(year_group=year_group, academic_year=year):
        add(t["pupil_id"], t["pupil_name"], t["admission_no"], t["year_group"],
            f"net {t['net']} points this year", 1)
    from education_system.systems.secondary.modules.behaviour.domain import detentions as DT
    for c in DT.concerns(year_group=year_group, today=day):
        add(c["pupil_id"], c["pupil_name"], c["admission_no"], c["year_group"], c["reason"], 1)
    from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
    for c in EX.concerns(year_group=year_group, today=day):
        add(c["pupil_id"], c["pupil_name"], c["admission_no"], c["year_group"], c["reason"], 2)
    return sorted(out.values(), key=lambda x: (-x["severity"], x["pupil_name"]))


def analysis(*, by: str = "type", year_group: int | str | None = None,
             academic_year: str | None = None, date_from: str | None = None,
             date_to: str | None = None) -> list[dict[str, Any]]:
    """Counts and points grouped by type, subject, staff, weekday, hour or
    year group (withdrawn entries left out)."""
    keys = {"type": lambda r: r.incident_type,
            "subject": lambda r: r.subject_code or "(no subject)",
            "staff": lambda r: r.raised_by or r.raised_by_username or "(unknown)",
            "weekday": lambda r: _dt.date.fromisoformat(r.entry_date).strftime("%A"),
            "hour": lambda r: (r.entry_time or "--")[:2] + ":00" if r.entry_time else
            "(no time)",
            "year": lambda r: f"Year {r.pupil_year}"}
    if by not in keys:
        raise ValidationError([f"Group by one of {', '.join(keys)}"])
    groups: dict[str, dict[str, Any]] = {}
    for r in list_entries(year_group=year_group, academic_year=academic_year,
                          date_from=date_from, date_to=date_to, include_withdrawn=False):
        g = groups.setdefault(keys[by](r), {"group": keys[by](r), "positive": 0, "negative": 0,
                                            "points": 0, "pupils": set()})
        g[r.polarity] += 1
        g["points"] += r.points
        g["pupils"].add(r.pupil_id)
    return sorted(({**g, "pupils": len(g["pupils"])} for g in groups.values()),
                  key=lambda g: (-(g["positive"] + g["negative"]), g["group"]))


# ── Rewards ──────────────────────────────────────────────────────────

def _positive_points(pupil_id: int, year: str) -> int:
    with database.connect() as conn:
        return conn.execute("SELECT COALESCE(SUM(points), 0) FROM behaviour_entries WHERE "
                            "pupil_id = ? AND academic_year = ? AND polarity = 'positive' AND "
                            "status != 'Withdrawn'", (int(pupil_id), year)).fetchone()[0]


def _check_milestones(pupil_id: int, year: str, actor: Principal) -> list[str]:
    """Record any reward level newly reached (levels once reached stay)."""
    pts = _positive_points(pupil_id, year)
    new = []
    with database.connect() as conn:
        for level, need in REWARD_LEVELS:
            if pts >= need and conn.execute(
                    "INSERT OR IGNORE INTO reward_milestones (pupil_id, academic_year, level, "
                    "points) VALUES (?, ?, ?, ?)", (pupil_id, year, level, pts)).rowcount:
                new.append(level)
                _audit(conn, "milestone", actor, None, pupil_id, level=level, points=pts)
    return new


def milestones(*, pupil_id: int | None = None, academic_year: str | None = None,
               level: str | None = None, unpresented: bool = False) -> list[dict[str, Any]]:
    sql = ("SELECT m.*, p.admission_no, p.legal_last_name, p.legal_first_name, "
           "p.preferred_name, p.year_group, p.form_group FROM reward_milestones m JOIN pupils p "
           "USING (pupil_id) WHERE 1 = 1")
    params: list[Any] = []
    for col, val in (("m.pupil_id", pupil_id), ("m.academic_year", academic_year),
                     ("m.level", level)):
        if val not in (None, ""):
            sql += f" AND {col} = ?"
            params.append(val)
    if unpresented:
        sql += " AND m.presented_at IS NULL"
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY m.reached_at DESC, m.milestone_id DESC",
                            params).fetchall()
    return [{"milestone_id": r["milestone_id"], "pupil_id": r["pupil_id"],
             "admission_no": r["admission_no"],
             "pupil_name": f"{r['legal_last_name']}, "
                           f"{r['preferred_name'] or r['legal_first_name']}",
             "year_group": r["year_group"], "form_group": r["form_group"],
             "academic_year": r["academic_year"], "level": r["level"], "points": r["points"],
             "reached_at": r["reached_at"], "presented_at": r["presented_at"],
             "presented_by": r["presented_by"]} for r in rows]


def present(milestone_ids: list[int], *, actor: Principal, undo: bool = False) -> int:
    """Mark reward certificates as presented (any member of staff)."""
    _require_staff(actor, "present")
    n = 0
    with database.connect() as conn:
        for mid in milestone_ids:
            n += conn.execute("UPDATE reward_milestones SET presented_at = ?, presented_by = ? "
                              "WHERE milestone_id = ?",
                              (None if undo else _dt.datetime.now().isoformat(
                                  timespec="seconds"), None if undo else actor.username,
                               int(mid))).rowcount
            _audit(conn, "present.undo" if undo else "present", actor, None, None,
                   milestone=int(mid))
    activity_log.record("behaviour.present", principal=actor, count=n)
    return n


def next_level(pupil_id: int, academic_year: str | None = None) -> dict[str, Any]:
    pts = _positive_points(pupil_id, academic_year or current_year())
    for level, need in REWARD_LEVELS:
        if pts < need:
            return {"points": pts, "next": level, "needed": need - pts}
    return {"points": pts, "next": None, "needed": 0}


# ── Houses ───────────────────────────────────────────────────────────

def list_houses(*, include_retired: bool = False) -> list[House]:
    with database.connect() as conn:
        return [House(r["house_id"], r["name"], r["colour"], bool(r["active"]))
                for r in conn.execute("SELECT * FROM houses" + ("" if include_retired else
                                                                " WHERE active = 1")
                                      + " ORDER BY name COLLATE NOCASE")]


def save_house(name: str, *, actor: Principal, colour: str | None = None,
               active: bool = True) -> House:
    _require_editor(actor, "house.save")
    label = " ".join(str(name or "").split())
    problems = []
    if not label or len(label) > 30:
        problems.append("A house name is 1-30 characters")
    col = (colour or "").strip() or None
    if col and not _COLOUR_RE.match(col):
        problems.append("Colour must look like #1E90FF")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        r = conn.execute("SELECT house_id FROM houses WHERE name = ?", (label,)).fetchone()
        if r:
            if not active and conn.execute("SELECT 1 FROM house_members WHERE house_id = ?",
                                           (r[0],)).fetchone():
                raise ValidationError([f"{label} still has pupils - move them first"])
            conn.execute("UPDATE houses SET colour = ?, active = ? WHERE house_id = ?",
                         (col, int(active), r[0]))
        else:
            conn.execute("INSERT INTO houses (name, colour, active) VALUES (?, ?, ?)",
                         (label, col, int(active)))
        _audit(conn, "house.save", actor, None, None, name=label, active=active)
    return next(h for h in list_houses(include_retired=True) if h.name.lower() == label.lower())


def house_of(pupil_id: int) -> House | None:
    with database.connect() as conn:
        r = conn.execute("SELECT h.* FROM house_members m JOIN houses h USING (house_id) WHERE "
                         "m.pupil_id = ?", (int(pupil_id),)).fetchone()
    return House(r["house_id"], r["name"], r["colour"], bool(r["active"])) if r else None


def assign_house(pupil_ids: list[int], house: str | None, *, actor: Principal) -> int:
    """Put pupils in a house (``None`` takes them out)."""
    _require_editor(actor, "house.assign")
    h = None
    if house:
        h = next((x for x in list_houses() if x.name.lower() == house.strip().lower()), None)
        if h is None:
            raise ValidationError([f"No house {house}"])
    with database.connect() as conn:
        for pid in pupil_ids:
            if h is None:
                conn.execute("DELETE FROM house_members WHERE pupil_id = ?", (int(pid),))
            else:
                conn.execute("INSERT INTO house_members (pupil_id, house_id, assigned_by) "
                             "VALUES (?, ?, ?) ON CONFLICT (pupil_id) DO UPDATE SET house_id = "
                             "excluded.house_id, assigned_by = excluded.assigned_by, "
                             "assigned_at = datetime('now')", (int(pid), h.house_id,
                                                               actor.username))
        _audit(conn, "house.assign", actor, None, None, house=h.name if h else None,
               pupils=len(pupil_ids))
    activity_log.record("behaviour.house.assign", principal=actor, pupils=len(pupil_ids))
    return len(pupil_ids)


def house_table(academic_year: str | None = None) -> list[dict[str, Any]]:
    """Positive points per house this year (withdrawn left out), top first."""
    year = academic_year or current_year()
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT h.house_id, h.name, h.colour, COUNT(DISTINCT m.pupil_id) AS pupils, "
            "COALESCE((SELECT SUM(e.points) FROM behaviour_entries e JOIN house_members m2 "
            "USING (pupil_id) WHERE m2.house_id = h.house_id AND e.academic_year = ? AND "
            "e.polarity = 'positive' AND e.status != 'Withdrawn'), 0) AS points "
            "FROM houses h LEFT JOIN house_members m ON m.house_id = h.house_id "
            "WHERE h.active = 1 GROUP BY h.house_id", (year,)).fetchall()
    out = [{"house": r["name"], "colour": r["colour"], "pupils": r["pupils"],
            "points": r["points"],
            "per_pupil": round(r["points"] / r["pupils"], 1) if r["pupils"] else 0}
           for r in rows]
    return sorted(out, key=lambda x: (-x["points"], x["house"]))


def without_house() -> list[P.Pupil]:
    with database.connect() as conn:
        ids = {r[0] for r in conn.execute("SELECT pupil_id FROM house_members")}
    return [p for p in P.list_pupils() if p.pupil_id not in ids]


# ── Families ─────────────────────────────────────────────────────────

def notify_parents(entry_ids: list[int], *, actor: Principal, note: str | None = None
                   ) -> dict[str, Any]:
    """E-mail the chosen entries to each pupil's contacts with parental
    responsibility (one e-mail per pupil and contact). The entries become
    visible in the portal. Returns {'message_id', 'emails', 'no_email'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    _require_staff(actor, "notify")
    entries = [get(i) for i in dict.fromkeys(int(x) for x in entry_ids)]
    entries = [e for e in entries if e.counts]
    if not entries:
        raise ValidationError(["Choose at least one entry that hasn't been withdrawn"])
    by_pupil: dict[int, list[Entry]] = {}
    for e in entries:
        by_pupil.setdefault(e.pupil_id, []).append(e)
    contacts = C.emailable_for_pupils(list(by_pupil))
    template = email_templates.load_template("behaviour_note")
    sender = _staff_name(actor)
    letters, no_email = [], []
    for pid, rows in by_pupil.items():
        p = P.get_pupil(pid)
        to = [(c.email, c.full_name) for c in contacts.get(pid, [])
              if c.email and c.parental_responsibility]
        if not to:
            no_email.append(p)
            continue
        good = all(r.polarity == "positive" for r in rows)
        first = p.preferred_name or p.legal_first_name
        lines = "\n".join(f"  {r.entry_date}  {r.incident_type}"
                          + (f" ({r.subject_code})" if r.subject_code else "")
                          + (f" {r.points:+d} point(s)" if r.points else "")
                          + f"\n    {r.description}" for r in sorted(rows,
                                                                    key=lambda r: r.entry_date))
        for address, name in to:
            subject, body = template.render({
                "recipient_name": name, "pupil_name": p.display_name,
                "headline": "Good news from school" if good else "A note about behaviour",
                "intro": (f"We wanted to let you know how well {first} has been doing."
                          if good else f"We'd like to let you know about {first}'s "
                                       "behaviour at school."),
                "entries": lines + (f"\n\n{note.strip()}" if note and note.strip() else ""),
                "closing": ("Please pass on our congratulations!" if good else
                            "If you'd like to talk about this, please contact "
                            f"{first}'s form tutor or reply to this e-mail."),
                "sender_name": sender})
            letters.append((address, name, subject, body))
    mid = E.save_prepared("behaviour_note", "Behaviour note home", "Behaviour note home",
                          "(one note per pupil)", letters, actor=actor) if letters else None
    now = _dt.datetime.now().isoformat(timespec="seconds")
    sent = {pid for pid in by_pupil if pid not in {p.pupil_id for p in no_email}}
    with database.connect() as conn:
        for e in entries:
            if e.pupil_id in sent:
                conn.execute("UPDATE behaviour_entries SET parents_notified_at = ?, "
                             "share_with_parents = 1 WHERE entry_id = ?", (now, e.entry_id))
                _audit(conn, "notify", actor, e.entry_id, e.pupil_id)
    activity_log.record("behaviour.notify", principal=actor, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "no_email": no_email}


def for_family(pupil_id: int, academic_year: str | None = None) -> dict[str, Any]:
    """What the portal shows: shared entries this year, points, house,
    reward levels."""
    year = academic_year or current_year()
    shared = list_entries(pupil_id=pupil_id, academic_year=year, shared_only=True,
                          include_withdrawn=False)
    return {"entries": shared, "positive_points": _positive_points(pupil_id, year),
            "house": house_of(pupil_id), "next": next_level(pupil_id, year),
            "milestones": milestones(pupil_id=pupil_id, academic_year=year)}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_entries(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "date", "time", "admission_no", "pupil", "year", "form", "type",
                    "polarity", "points", "severity", "subject", "location", "description",
                    "raised_by", "action_taken", "status", "escalated_to", "shared",
                    "parents_notified"])
        for r in rows:
            w.writerow([r.entry_id, r.entry_date, r.entry_time or "", _safe(r.admission_no),
                        _safe(r.pupil_name), r.pupil_year, _safe(r.form_group),
                        r.incident_type, r.polarity, r.points, r.severity,
                        _safe(r.subject_code), _safe(r.location), _safe(r.description),
                        _safe(r.raised_by), _safe(r.action_taken), r.status,
                        _safe(r.escalated_to), "yes" if r.share_with_parents else "",
                        r.parents_notified_at or ""])
    activity_log.record("behaviour.export", principal=actor, rows=len(rows))
    return len(rows)
