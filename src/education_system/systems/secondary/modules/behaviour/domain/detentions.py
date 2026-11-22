"""Detentions: setting them, running the sessions and following up.

Kept from the old Detentions:

* One detention per pupil, with date, start time (HH:MM), duration (5-480
  minutes, 30 by default), type (Lunchtime, After school, Saturday, Friday,
  Departmental, SLT, Other), location, supervisor, reason (required, 200
  characters), set by, status (Scheduled, Attended, Missed, Excused,
  Cancelled, Rescheduled), the behaviour incident it came from and notes.
* Reschedule makes a new detention with the same details, links the two and
  marks the first one Rescheduled (only Scheduled or Missed ones).
* The daily register, the pupil summary (attended / missed / excused /
  scheduled, minutes served) and the cohort summary.

New:

* **Sessions.** The detentions lead (:data:`DETENTION_EDITORS`) can run
  sessions - e.g. Tuesday's after-school detention in room 12 with a
  supervisor and a capacity - and staff book pupils into them. A session
  can't be overbooked, and can't be cancelled while pupils are still booked:
  move them to another session first.
* **Checks.** A pupil must be on roll; no two of their detentions overlap;
  a Saturday detention is on a Saturday and others are on a school day
  (when the school calendar knows the date); attendance can't be marked
  before the detention happens. :func:`check` lists the warnings worth a
  second look - under 24 hours' notice for one outside the school day,
  another detention the same day - which the screens ask about.
* **From behaviour.** Set a detention from a negative behaviour entry; the
  entry's "action taken" says so.
* **Registers.** Mark a whole session or day at once (the supervisor, the
  person who set it, the head of year or the lead).
* **Follow-up.** Missed detentions not yet rescheduled or excused; pupils
  who missed :data:`MISSED_CONCERN` or more this term feed the behaviour
  concerns (and so the intervention suggestions).
* **Families.** A notice home (e-mail to contacts with parental
  responsibility) for new or missed detentions; families see upcoming and
  past detentions in the portal's Behaviour section.
* **Who.** Any member of staff sets lunchtime, after-school, Friday,
  departmental and other detentions; SLT and Saturday ones are for the lead.
  The person who set one changes it while it's scheduled; only the lead
  deletes (others cancel). Every change is in ``detention_audit`` and the
  activity log (ids only).
* **Reports.** By type, reason, member of staff, weekday and year group;
  CSV export.
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

from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH  # registers the FK target
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    DETENTION_EDITORS,
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

DETENTION_TYPES: tuple[str, ...] = ("Lunchtime", "After school", "Saturday", "Friday",
                                    "Departmental", "SLT", "Other")
DEFAULT_TYPE = "After school"
#: Types only the detentions lead sets.
LEAD_TYPES = frozenset({"SLT", "Saturday"})
#: Types outside the school day: families need notice (transport, caring).
OUT_OF_HOURS = frozenset({"After school", "Friday", "Saturday"})
DETENTION_STATUSES: tuple[str, ...] = ("Scheduled", "Attended", "Missed", "Excused",
                                       "Cancelled", "Rescheduled")
DEFAULT_STATUS = "Scheduled"
#: Statuses a register can record (Rescheduled only comes from reschedule()).
REGISTER_STATUSES: tuple[str, ...] = ("Scheduled", "Attended", "Missed", "Excused",
                                      "Cancelled")
DEFAULT_DURATION = 30
MIN_DURATION, MAX_DURATION = 5, 480
MAX_REASON = 200
NOTICE_HOURS = 24
#: Missed this many in a term -> a behaviour concern.
MISSED_CONCERN = 2
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS detention_sessions (
    session_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_date        TEXT NOT NULL,
    detention_type      TEXT NOT NULL,
    start_time          TEXT,
    duration_min        INTEGER NOT NULL DEFAULT 30,
    location            TEXT,
    supervisor          TEXT,
    supervisor_username TEXT,
    capacity            INTEGER,
    status              TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN ('Planned', 'Cancelled')),
    notes               TEXT,
    created_by          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_detention_sessions_date ON detention_sessions (session_date);
CREATE TABLE IF NOT EXISTS detentions (
    detention_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id            INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    session_id          INTEGER REFERENCES detention_sessions (session_id) ON DELETE SET NULL,
    academic_year       TEXT NOT NULL,
    detention_date      TEXT NOT NULL,
    start_time          TEXT,
    duration_min        INTEGER NOT NULL DEFAULT 30
                        CHECK (duration_min BETWEEN 5 AND 480),
    detention_type      TEXT NOT NULL DEFAULT 'After school',
    location            TEXT,
    supervisor          TEXT,
    supervisor_username TEXT,
    reason              TEXT NOT NULL,
    set_by              TEXT,
    set_by_username     TEXT,
    status              TEXT NOT NULL DEFAULT 'Scheduled' CHECK (status IN
                        ('Scheduled', 'Attended', 'Missed', 'Excused', 'Cancelled',
                         'Rescheduled')),
    related_entry_id    INTEGER REFERENCES behaviour_entries (entry_id) ON DELETE SET NULL,
    rescheduled_from    INTEGER REFERENCES detentions (detention_id) ON DELETE SET NULL,
    rescheduled_to      INTEGER REFERENCES detentions (detention_id) ON DELETE SET NULL,
    notes               TEXT,
    marked_by           TEXT,
    marked_at           TEXT,
    parents_notified_at TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by          TEXT,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_detentions_pupil ON detentions (pupil_id, academic_year);
CREATE INDEX IF NOT EXISTS ix_detentions_date ON detentions (detention_date);
CREATE INDEX IF NOT EXISTS ix_detentions_session ON detentions (session_id);
CREATE TABLE IF NOT EXISTS detention_audit (
    audit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    detention_id  INTEGER,
    session_id    INTEGER,
    pupil_id      INTEGER,
    action        TEXT NOT NULL,
    detail        TEXT,
    actor         TEXT NOT NULL,
    at            TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("detentions", _SCHEMA)


@dataclass(frozen=True)
class Session:
    session_id: int
    session_date: str
    detention_type: str
    start_time: str | None
    duration_min: int
    location: str | None
    supervisor: str | None
    supervisor_username: str | None
    capacity: int | None
    status: str
    notes: str | None
    created_by: str | None
    booked: int = 0

    @property
    def label(self) -> str:
        return (f"{self.session_date} {self.start_time or ''} {self.detention_type}"
                + (f" · {self.location}" if self.location else "")).replace("  ", " ")

    @property
    def places_left(self) -> int | None:
        return None if self.capacity is None else max(0, self.capacity - self.booked)


@dataclass(frozen=True)
class Detention:
    detention_id: int
    pupil_id: int
    session_id: int | None
    academic_year: str
    detention_date: str
    start_time: str | None
    duration_min: int
    detention_type: str
    location: str | None
    supervisor: str | None
    supervisor_username: str | None
    reason: str
    set_by: str | None
    set_by_username: str | None
    status: str
    related_entry_id: int | None
    rescheduled_from: int | None
    rescheduled_to: int | None
    notes: str | None
    marked_by: str | None
    marked_at: str | None
    parents_notified_at: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def is_open(self) -> bool:
        """Still owed: scheduled, or missed and not yet followed up."""
        return self.status in ("Scheduled", "Missed")

    @property
    def when(self) -> str:
        return f"{self.detention_date}" + (f" {self.start_time}" if self.start_time else "")


_SELECT = """
SELECT d.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group AS pupil_year, p.form_group
FROM detentions d JOIN pupils p USING (pupil_id)
"""
_BASE = tuple(f for f in Detention.__dataclass_fields__ if f not in (
    "pupil_name", "admission_no", "pupil_year", "form_group"))


def _row(r) -> Detention:
    return Detention(**{k: r[k] for k in _BASE},
                     pupil_name=f"{r['legal_last_name']}, "
                                f"{r['preferred_name'] or r['legal_first_name']}",
                     admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                     form_group=r["form_group"])


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in DETENTION_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"detentions.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can set detentions.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the detentions lead can do that.")


def _same(username: str | None, actor: Principal) -> bool:
    return bool(actor.username) and (username or "").lower() == actor.username.lower()


def can_edit(actor: Principal, d: Detention) -> bool:
    """Details: the lead always; whoever set it while it's scheduled."""
    return is_editor(actor) or (_same(d.set_by_username, actor) and d.status == "Scheduled")


def can_mark(actor: Principal, d: Detention) -> bool:
    """Attendance / status: the lead, whoever set it, the supervisor, the head of year."""
    return is_editor(actor) or _same(d.set_by_username, actor) or \
        _same(d.supervisor_username, actor) or (
            actor.role in STAFF_ROLES and BH.is_head_of_year(actor, d.pupil_year))


def _audit(conn, action: str, actor: Principal, *, detention_id: int | None = None,
           session_id: int | None = None, pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO detention_audit (detention_id, session_id, pupil_id, action, "
                 "detail, actor) VALUES (?, ?, ?, ?, ?, ?)",
                 (detention_id, session_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(detention_id: int | None = None, *, session_id: int | None = None,
            pupil_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM detention_audit", [], []
    for col, val in (("detention_id", detention_id), ("session_id", session_id),
                     ("pupil_id", pupil_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(int(val))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "detention_id": r["detention_id"],
                 "session_id": r["session_id"], "pupil_id": r["pupil_id"],
                 "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Staff names ──────────────────────────────────────────────────────

def staff_names() -> list[str]:
    """Staff to choose a supervisor from (display names)."""
    from education_system.systems.secondary.infrastructure.authentication import accounts
    try:
        return [s["display_name"] or s["username"] for s in accounts.staff_logins()]
    except Exception:  # noqa: BLE001 - the list is a convenience
        return []


def _staff_username(name: str | None) -> str | None:
    """The login behind a typed supervisor name (display name, username or e-mail)."""
    from education_system.systems.secondary.infrastructure.authentication import accounts
    want = (name or "").strip().lower()
    if not want:
        return None
    try:
        for s in accounts.staff_logins():
            if want in {(s["username"] or "").lower(), (s["display_name"] or "").lower(),
                        (s["email"] or "").lower()}:
                return s["username"]
    except Exception:  # noqa: BLE001
        pass
    return None


# ── Cleaning ─────────────────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str]) -> str | None:
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _time(value: Any, problems: list[str]) -> str | None:
    t = str(value or "").strip()
    if t and not _TIME_RE.match(t):
        problems.append("Start time must be HH:MM (24-hour)")
    return t or None


def _duration(value: Any, problems: list[str]) -> int:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return DEFAULT_DURATION
    try:
        d = int(str(value).strip())
    except ValueError:
        problems.append("Duration must be a whole number")
        return DEFAULT_DURATION
    if not MIN_DURATION <= d <= MAX_DURATION:
        problems.append(f"Duration must be between {MIN_DURATION} and {MAX_DURATION} minutes")
    return d


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


def _day_problems(day: str, dtype: str) -> list[str]:
    """A Saturday detention is on a Saturday; the others on a school day."""
    d = _dt.date.fromisoformat(day)
    if dtype == "Saturday":
        return [] if d.weekday() == 5 else ["A Saturday detention must be on a Saturday"]
    if dtype == "Friday" and d.weekday() != 4:
        return ["A Friday detention must be on a Friday"]
    if d.weekday() >= 5:
        return [f"{d.strftime('%A')} isn't a school day - use a Saturday detention"]
    try:
        from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
        info = AY.day_info(d)
    except Exception:  # noqa: BLE001 - the calendar is a help, not a gate
        return []
    if info.year is not None and not info.is_school_day:
        return [f"{day} isn't a school day ({info.label})"]
    return []


def _minutes(t: str | None) -> int | None:
    return int(t[:2]) * 60 + int(t[3:]) if t else None


def _overlaps(a_time: str | None, a_dur: int, b_time: str | None, b_dur: int) -> bool:
    a, b = _minutes(a_time), _minutes(b_time)
    if a is None or b is None:
        return True   # no times: the same day counts as a clash
    return a < b + b_dur and b < a + a_dur


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


FIELDS = ("detention_date", "start_time", "duration_min", "detention_type", "location",
          "supervisor", "supervisor_username", "reason", "set_by", "notes")


def _clean(data: dict[str, Any], current: Detention | None, actor: Principal, *,
           keep_type: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Checked values; *keep_type* is a lead-only type the actor may keep
    (rescheduling an SLT detention they may mark)."""
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}
    out["detention_date"] = _date(merged.get("detention_date"), "Detention date", problems) \
        if merged.get("detention_date") not in (None, "") else None
    if out["detention_date"] is None and not problems:
        problems.append("Detention date is required")
    out["start_time"] = _time(merged.get("start_time"), problems)
    out["duration_min"] = _duration(merged.get("duration_min"), problems)
    out["detention_type"] = _choice(merged.get("detention_type"), DETENTION_TYPES,
                                    "Detention type", problems, DEFAULT_TYPE)
    out["location"] = (str(merged.get("location") or "").strip()[:60]) or None
    sup = (str(merged.get("supervisor") or "").strip()[:80]) or None
    out["supervisor"] = sup
    out["supervisor_username"] = _staff_username(sup) if "supervisor" in data or current is \
        None else merged.get("supervisor_username")
    reason = " ".join(str(merged.get("reason") or "").split())
    if not reason:
        problems.append("Reason is required")
    elif len(reason) > MAX_REASON:
        problems.append(f"Reason must be {MAX_REASON} chars or fewer")
    out["reason"] = reason
    out["set_by"] = (str(merged.get("set_by") or "").strip()[:80]) or (
        BH._staff_name(actor) if current is None else None)
    out["notes"] = (str(merged.get("notes") or "").strip()[:2000]) or None
    if out["detention_date"]:
        problems += _day_problems(out["detention_date"], out["detention_type"])
    allowed = keep_type or (current.detention_type if current else None)
    if out["detention_type"] in LEAD_TYPES and not is_editor(actor) and \
            out["detention_type"] != allowed:
        problems.append(f"Only the detentions lead sets {out['detention_type']} detentions")
    return out, problems


def _clashes(conn, pupil_id: int, c: dict[str, Any], skip: int | None = None) -> list[str]:
    rows = conn.execute("SELECT detention_id, start_time, duration_min, detention_type FROM "
                        "detentions WHERE pupil_id = ? AND detention_date = ? AND status = "
                        "'Scheduled' AND detention_id != ?",
                        (pupil_id, c["detention_date"], skip or 0)).fetchall()
    return [f"Already has detention #{r['detention_id']} ({r['detention_type']}"
            + (f" {r['start_time']}" if r["start_time"] else "") + f") on {c['detention_date']}"
            for r in rows if _overlaps(c["start_time"], c["duration_min"], r["start_time"],
                                       r["duration_min"])]


def _entry(ref: Any, pupil_id: int, problems: list[str]) -> int | None:
    if ref in (None, "") or (isinstance(ref, str) and not ref.strip()):
        return None
    try:
        e = BH.get(int(str(ref).strip()))
    except (ValueError, BH.NotFound):
        problems.append(f"No behaviour entry #{ref}")
        return None
    if e.pupil_id != pupil_id:
        problems.append(f"Behaviour entry #{e.entry_id} is for another pupil")
    elif e.polarity != "negative":
        problems.append(f"Behaviour entry #{e.entry_id} isn't a negative entry")
    return e.entry_id


# ── Sessions ─────────────────────────────────────────────────────────

_SESSION_SELECT = ("SELECT s.*, (SELECT COUNT(*) FROM detentions d WHERE d.session_id = "
                   "s.session_id AND d.status IN ('Scheduled', 'Attended', 'Missed', "
                   "'Excused')) AS booked FROM detention_sessions s")


def _session_row(r) -> Session:
    return Session(**{k: r[k] for k in Session.__dataclass_fields__})


def get_session(session_id: int) -> Session:
    with database.connect() as conn:
        r = conn.execute(_SESSION_SELECT + " WHERE s.session_id = ?",
                         (int(session_id),)).fetchone()
    if r is None:
        raise NotFound(f"No detention session #{session_id}")
    return _session_row(r)


def list_sessions(*, date_from: str | None = None, date_to: str | None = None,
                  detention_type: str | None = None, include_cancelled: bool = False,
                  upcoming: bool = False) -> list[Session]:
    sql, where, params = _SESSION_SELECT, [], []
    if upcoming:
        date_from = date_from or _today().isoformat()
    for op, val in ((">=", date_from), ("<=", date_to)):
        if val:
            where.append(f"s.session_date {op} ?")
            params.append(val)
    if detention_type:
        where.append("s.detention_type = ?")
        params.append(detention_type)
    if not include_cancelled:
        where.append("s.status = 'Planned'")
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_session_row(r) for r in conn.execute(
            sql + " ORDER BY s.session_date, COALESCE(s.start_time, ''), s.session_id",
            params)]


def save_session(data: dict[str, Any], *, actor: Principal,
                 session_id: int | None = None) -> Session:
    """Add a session, or change one. Changing a session's date, time, room or
    supervisor changes it for every pupil still booked into it."""
    _require_editor(actor, "session.save")
    current = get_session(session_id) if session_id else None
    problems: list[str] = []
    day = _date(data.get("session_date", current.session_date if current else ""),
                "Session date", problems)
    dtype = _choice(data.get("detention_type", current.detention_type if current else ""),
                    DETENTION_TYPES, "Detention type", problems, DEFAULT_TYPE)
    start = _time(data.get("start_time", current.start_time if current else ""), problems)
    dur = _duration(data.get("duration_min", current.duration_min if current else ""),
                    problems)
    loc = (str(data.get("location", current.location if current else "") or "")
           .strip()[:60]) or None
    sup = (str(data.get("supervisor", current.supervisor if current else "") or "")
           .strip()[:80]) or None
    cap_raw = data.get("capacity", current.capacity if current else None)
    cap = None
    if cap_raw not in (None, "") and str(cap_raw).strip():
        try:
            cap = int(str(cap_raw).strip())
            if not 1 <= cap <= 300:
                problems.append("Capacity must be between 1 and 300")
        except ValueError:
            problems.append("Capacity must be a whole number")
    if day:
        problems += _day_problems(day, dtype)
        if current is None and day < _today().isoformat():
            problems.append("A new session can't be in the past")
    if current and cap is not None and current.booked > cap:
        problems.append(f"{current.booked} pupils are already booked - capacity can't be "
                        f"below that")
    notes = (str(data.get("notes", current.notes if current else "") or "").strip()[:500]) \
        or None
    if problems:
        raise ValidationError(problems)
    vals = {"session_date": day, "detention_type": dtype, "start_time": start,
            "duration_min": dur, "location": loc, "supervisor": sup,
            "supervisor_username": _staff_username(sup), "capacity": cap, "notes": notes}
    with database.connect() as conn:
        if current:
            conn.execute("UPDATE detention_sessions SET " + ", ".join(f"{k} = ?" for k in vals)
                         + " WHERE session_id = ?", (*vals.values(), current.session_id))
            sid = current.session_id
            # Pupils still booked follow the session.
            conn.execute("UPDATE detentions SET detention_date = ?, start_time = ?, "
                         "duration_min = ?, detention_type = ?, location = ?, supervisor = ?, "
                         "supervisor_username = ?, academic_year = ?, updated_by = ?, "
                         "updated_at = datetime('now') WHERE session_id = ? AND status = "
                         "'Scheduled'", (day, start, dur, dtype, loc, sup,
                                         vals["supervisor_username"], year_of(day),
                                         actor.username, sid))
            _audit(conn, "session.update", actor, session_id=sid)
        else:
            sid = conn.execute(
                "INSERT INTO detention_sessions (" + ", ".join(vals) + ", created_by) VALUES ("
                + ", ".join("?" * len(vals)) + ", ?)", (*vals.values(), actor.username)
            ).lastrowid
            _audit(conn, "session.add", actor, session_id=sid, date=day, type=dtype)
    activity_log.record("detentions.session.save", target=sid, principal=actor)
    return get_session(sid)


def cancel_session(session_id: int, *, actor: Principal) -> Session:
    """Only once nobody is still booked into it (move them first)."""
    _require_editor(actor, "session.cancel", session_id)
    s = get_session(session_id)
    with database.connect() as conn:
        left = conn.execute("SELECT COUNT(*) FROM detentions WHERE session_id = ? AND "
                            "status = 'Scheduled'", (s.session_id,)).fetchone()[0]
        if left:
            raise ValidationError([f"{left} pupil(s) are still booked - move them to another "
                                   "session first"])
        conn.execute("UPDATE detention_sessions SET status = 'Cancelled' WHERE session_id = ?",
                     (s.session_id,))
        _audit(conn, "session.cancel", actor, session_id=s.session_id)
    activity_log.record("detentions.session.cancel", target=s.session_id, principal=actor)
    return get_session(s.session_id)


def move_session(session_id: int, to_session_id: int, *, actor: Principal) -> int:
    """Reschedule every pupil still booked into a session to another one."""
    _require_editor(actor, "session.move", session_id)
    rows = list_detentions(session_id=session_id, status="Scheduled")
    target = get_session(to_session_id)
    if target.session_id == int(session_id):
        raise ValidationError(["Choose a different session"])
    if target.places_left is not None and target.places_left < len(rows):
        raise ValidationError([f"{target.label} has {target.places_left} place(s) left - "
                               f"{len(rows)} needed"])
    for d in rows:
        reschedule(d.detention_id, session_id=target.session_id, actor=actor,
                   notes=f"Moved from session #{session_id}")
    return len(rows)


# ── Reading ──────────────────────────────────────────────────────────

def get(detention_id: int) -> Detention:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE d.detention_id = ?", (int(detention_id),)).fetchone()
    if r is None:
        raise NotFound(f"No detention #{detention_id}")
    return _row(r)


def list_detentions(*, pupil_id: int | None = None, year_group: int | str | None = None,
                    form_group: str | None = None, status: str | None = None,
                    detention_type: str | None = None, date_from: str | None = None,
                    date_to: str | None = None, supervisor: str | None = None,
                    session_id: int | None = None, academic_year: str | None = None,
                    set_by: str | None = None, related_entry_id: int | None = None,
                    limit: int | None = None) -> list[Detention]:
    sql, where, params = _SELECT, [], []
    problems: list[str] = []
    if status and status not in DETENTION_STATUSES:
        problems.append(f"Status filter must be one of {', '.join(DETENTION_STATUSES)}")
    if detention_type and detention_type not in DETENTION_TYPES:
        problems.append(f"Type filter must be one of {', '.join(DETENTION_TYPES)}")
    for col, val in (("d.pupil_id", pupil_id), ("p.year_group", year_group),
                     ("p.form_group", form_group), ("d.status", status),
                     ("d.detention_type", detention_type), ("d.session_id", session_id),
                     ("d.academic_year", academic_year),
                     ("d.related_entry_id", related_entry_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(int(val) if col in ("d.pupil_id", "p.year_group", "d.session_id",
                                              "d.related_entry_id") else val)
    for op, val, label in ((">=", date_from, "From date"), ("<=", date_to, "To date")):
        d = _date(val, label, problems) if val else None
        if d:
            where.append(f"d.detention_date {op} ?")
            params.append(d)
    if problems:
        raise ValidationError(problems)
    if supervisor:
        where.append("(lower(COALESCE(d.supervisor_username, '')) = ? OR "
                     "lower(COALESCE(d.supervisor, '')) = ?)")
        params += [supervisor.strip().lower()] * 2
    if set_by:
        where.append("(lower(COALESCE(d.set_by_username, '')) = ? OR "
                     "lower(COALESCE(d.set_by, '')) = ?)")
        params += [set_by.strip().lower()] * 2
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d.detention_date DESC, COALESCE(d.start_time, '') DESC, " \
           "d.detention_id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql, params)]


def daily_register(date_iso: str, *, detention_type: str | None = None) -> list[Detention]:
    """The old daily register: everyone due on a day, in time order."""
    rows = list_detentions(date_from=date_iso, date_to=date_iso, detention_type=detention_type)
    return sorted((r for r in rows if r.status != "Rescheduled"),
                  key=lambda r: (r.start_time or "", r.pupil_name))


def session_register(session_id: int) -> list[Detention]:
    return sorted((r for r in list_detentions(session_id=session_id)
                   if r.status != "Rescheduled"), key=lambda r: r.pupil_name)


def supervising(actor: Principal, day: _dt.date | None = None) -> list[Detention]:
    """Detentions this person supervises on *day* (for My Day)."""
    if not actor.username:
        return []
    iso = (day or _today()).isoformat()
    return [r for r in daily_register(iso) if _same(r.supervisor_username, actor)
            and r.status == "Scheduled"]


# ── Setting and changing ─────────────────────────────────────────────

def check(data: dict[str, Any], *, actor: Principal, pupils: list[Any] | None = None,
          now: _dt.datetime | None = None) -> list[str]:
    """Warnings worth a second look before saving (not refusals)."""
    c, problems = _clean(_with_session(data), None, actor)
    if problems or not c["detention_date"]:
        return []
    out: list[str] = []
    now = now or _dt.datetime.now()
    if c["detention_type"] in OUT_OF_HOURS:
        start = _dt.datetime.combine(_dt.date.fromisoformat(c["detention_date"]),
                                     _dt.time(*(divmod(_minutes(c["start_time"]), 60)
                                                if c["start_time"] else (15, 30))))
        if start - now < _dt.timedelta(hours=NOTICE_HOURS):
            out.append(f"Less than {NOTICE_HOURS} hours' notice for a detention outside the "
                       "school day - make sure the family knows and the pupil can get home "
                       "(transport, caring responsibilities).")
    refs = pupils if pupils is not None else [data.get("pupil_id") or data.get("pupil")]
    for ref in refs:
        p = _pupil(ref)
        if p is None:
            continue
        same_day = [r for r in list_detentions(pupil_id=p.pupil_id, date_from=c["detention_date"],
                                               date_to=c["detention_date"], status="Scheduled")]
        if same_day:
            out.append(f"{p.display_name} already has a detention that day.")
        missed = len(list_detentions(pupil_id=p.pupil_id, status="Missed",
                                     academic_year=year_of(c["detention_date"])))
        if missed:
            out.append(f"{p.display_name} has {missed} missed detention(s) not yet followed up.")
    return out


def _with_session(data: dict[str, Any]) -> dict[str, Any]:
    """A booking into a session takes the session's date, time, room and supervisor."""
    sid = data.get("session_id")
    if sid in (None, "") or (isinstance(sid, str) and not sid.strip()):
        return {k: v for k, v in data.items() if k != "session_id"}
    s = get_session(int(sid))
    return {**data, "session_id": s.session_id, "detention_date": s.session_date,
            "start_time": s.start_time, "duration_min": s.duration_min,
            "detention_type": s.detention_type, "location": s.location,
            "supervisor": s.supervisor}


def set_many(pupils: list[Any], data: dict[str, Any], *, actor: Principal) -> list[Detention]:
    """The same detention for several pupils (ids or admission numbers). All
    or nothing."""
    _require_staff(actor, "set")
    data = _with_session(data)
    sid = data.get("session_id")
    session = get_session(sid) if sid else None
    c, problems = _clean(data, None, actor)
    if session and session.status != "Planned":
        problems.append(f"Session #{session.session_id} has been cancelled")
    if c["detention_date"] and c["detention_date"] < _today().isoformat():
        problems.append("A new detention can't be set for a date that has passed")
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
    if session and session.places_left is not None and session.places_left < len(found):
        problems.append(f"{session.label} has {session.places_left} place(s) left")
    entry_ids = {p.pupil_id: _entry(data.get("related_entry_id"), p.pupil_id, problems)
                 for p in found} if data.get("related_entry_id") not in (None, "") else {}
    with database.connect() as conn:
        if c["detention_date"]:
            for p in found:
                problems += [f"{p.display_name}: {x}" for x in _clashes(conn, p.pupil_id, c)]
        if problems:
            activity_log.record("detentions.set", outcome="invalid", principal=actor,
                                problems=len(problems))
            raise ValidationError(problems)
        ids = []
        for p in found:
            did = conn.execute(
                f"INSERT INTO detentions (pupil_id, session_id, academic_year, set_by_username, "
                f"related_entry_id, {', '.join(FIELDS)}, updated_by) VALUES (?, ?, ?, ?, ?, "
                f"{', '.join('?' * len(FIELDS))}, ?)",
                (p.pupil_id, sid, year_of(c["detention_date"]), actor.username,
                 entry_ids.get(p.pupil_id), *(c[k] for k in FIELDS), actor.username)).lastrowid
            _audit(conn, "set", actor, detention_id=did, session_id=sid, pupil_id=p.pupil_id,
                   date=c["detention_date"], type=c["detention_type"])
            ids.append(did)
    for p in found:
        if entry_ids.get(p.pupil_id):
            BH.add_action(entry_ids[p.pupil_id], f"Detention set for {c['detention_date']} "
                                                 f"({c['detention_type']})", actor=actor)
    activity_log.record("detentions.set", principal=actor, pupils=len(found),
                        type=c["detention_type"])
    return [get(i) for i in ids]


def create(data: dict[str, Any], *, actor: Principal) -> Detention:
    """The old Schedule: one detention. *data* carries ``pupil_id`` or ``pupil``."""
    return set_many([data.get("pupil_id") or data.get("pupil")],
                    {k: v for k, v in data.items() if k not in ("pupil_id", "pupil")},
                    actor=actor)[0]


def from_behaviour(entry_id: int, data: dict[str, Any], *, actor: Principal) -> Detention:
    """Set a detention for a negative behaviour entry's pupil, linked to it."""
    e = BH.get(entry_id)
    return create({**data, "pupil_id": e.pupil_id, "related_entry_id": e.entry_id,
                   "reason": data.get("reason") or f"{e.incident_type}: {e.description}"[
                       :MAX_REASON]}, actor=actor)


def update(detention_id: int, changes: dict[str, Any], *, actor: Principal) -> Detention:
    """The old Edit. Status changes go through :func:`set_status`."""
    d = get(detention_id)
    if not can_edit(actor, d):
        _deny(actor, "update", d.admission_no,
              "Only the person who set it (while it's scheduled) or the detentions lead can "
              "change it.")
    if "status" in changes and changes["status"] not in (None, "", d.status):
        d = set_status(d.detention_id, changes["status"], actor=actor)
        changes = {k: v for k, v in changes.items() if k != "status"}
    if d.session_id and any(k in changes and str(changes[k] or "") != str(getattr(d, k) or "")
                            for k in ("detention_date", "start_time", "duration_min",
                                      "detention_type", "location", "supervisor")):
        raise ValidationError(["This detention is part of a session - reschedule it to change "
                               "the date, time, room or supervisor"])
    c, problems = _clean(changes, d, actor)
    entry = _entry(changes["related_entry_id"], d.pupil_id, problems) \
        if "related_entry_id" in changes else d.related_entry_id
    changed = [k for k in FIELDS if c[k] != getattr(d, k)]
    if entry != d.related_entry_id:
        changed.append("related_entry_id")
    if any(k in changed for k in ("detention_date", "start_time", "duration_min")):
        if d.status == "Scheduled" and c["detention_date"] and \
                c["detention_date"] < _today().isoformat():
            problems.append("A scheduled detention can't be moved into the past")
        with database.connect() as conn:
            problems += _clashes(conn, d.pupil_id, c, skip=d.detention_id)
    if problems:
        raise ValidationError(problems)
    if not changed:
        return d
    vals = {**{k: c[k] for k in changed if k in FIELDS}}
    if "related_entry_id" in changed:
        vals["related_entry_id"] = entry
    with database.connect() as conn:
        conn.execute("UPDATE detentions SET " + ", ".join(f"{k} = ?" for k in vals)
                     + ", academic_year = ?, updated_by = ?, updated_at = datetime('now') "
                       "WHERE detention_id = ?",
                     (*vals.values(), year_of(c["detention_date"]), actor.username,
                      d.detention_id))
        _audit(conn, "update", actor, detention_id=d.detention_id, pupil_id=d.pupil_id,
               fields=changed)
    activity_log.record("detentions.update", target=d.admission_no, principal=actor,
                        fields=",".join(changed))
    return get(d.detention_id)


def _status_problems(d: Detention, status: str, actor: Principal) -> list[str]:
    if status == "Rescheduled":
        return ["Use Reschedule to move a detention to another date"]
    if d.status == "Rescheduled":
        return [f"#{d.detention_id} was rescheduled to #{d.rescheduled_to} - change that one"]
    if status in ("Attended", "Missed") and d.detention_date > _today().isoformat():
        return [f"#{d.detention_id} hasn't happened yet ({d.detention_date})"]
    if d.status in ("Attended", "Excused", "Cancelled") and status == "Scheduled" and \
            not is_editor(actor):
        return ["Only the detentions lead can reopen a detention"]
    return []


def set_status(detention_id: int, status: str, *, actor: Principal,
               note: str | None = None) -> Detention:
    """The old "Mark attended / missed / excused"."""
    return mark_register({int(detention_id): status}, actor=actor, note=note)[0]


def mark_register(marks: dict[int, str], *, actor: Principal,
                  note: str | None = None) -> list[Detention]:
    """Record several detentions' statuses at once (a session or day
    register). All or nothing."""
    problems: list[str] = []
    todo: list[tuple[Detention, str]] = []
    for did, raw in marks.items():
        d = get(did)
        if not can_mark(actor, d):
            _deny(actor, "status", d.admission_no,
                  "Only the person who set it, the supervisor, the head of year or the "
                  "detentions lead can record this.")
        st = _choice(raw, DETENTION_STATUSES, "Status", problems, "")
        if not st:
            problems.append("Status is required")
            continue
        if st != d.status:
            problems += _status_problems(d, st, actor)
            todo.append((d, st))
    if problems:
        raise ValidationError(problems)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with database.connect() as conn:
        for d, st in todo:
            extra = (((d.notes + "\n") if d.notes else "") + note.strip()) \
                if note and note.strip() else d.notes
            conn.execute("UPDATE detentions SET status = ?, notes = ?, marked_by = ?, "
                         "marked_at = ?, updated_by = ?, updated_at = datetime('now') "
                         "WHERE detention_id = ?",
                         (st, extra, actor.username if st in ("Attended", "Missed", "Excused")
                          else d.marked_by, now if st in ("Attended", "Missed", "Excused")
                          else d.marked_at, actor.username, d.detention_id))
            _audit(conn, "status", actor, detention_id=d.detention_id, pupil_id=d.pupil_id,
                   frm=d.status, to=st)
    for d, st in todo:
        activity_log.record("detentions.status", target=d.admission_no, principal=actor,
                            status=st)
    return [get(d) for d in marks]


def reschedule(detention_id: int, *, actor: Principal, new_date: str | None = None,
               new_start_time: str | None = None, new_location: str | None = None,
               new_supervisor: str | None = None, session_id: int | None = None,
               notes: str | None = None) -> Detention:
    """The old Reschedule: a new detention with the same details (or booked
    into *session_id*), the two linked, the first marked Rescheduled."""
    d = get(detention_id)
    if not can_mark(actor, d):
        _deny(actor, "reschedule", d.admission_no,
              "Only the person who set it, the supervisor, the head of year or the detentions "
              "lead can reschedule it.")
    if d.status not in ("Scheduled", "Missed"):
        raise ValidationError([f"Cannot reschedule a detention with status {d.status}"])
    data: dict[str, Any] = {
        "detention_date": new_date, "start_time": new_start_time or d.start_time,
        "duration_min": d.duration_min, "detention_type": d.detention_type,
        "location": new_location or d.location, "supervisor": new_supervisor or d.supervisor,
        "reason": d.reason, "set_by": d.set_by,
        "notes": notes or f"Rescheduled from #{d.detention_id}"}
    if session_id:
        data["session_id"] = session_id
    elif not new_date:
        raise ValidationError(["Give a new date or a session"])
    data = _with_session(data)
    c, problems = _clean(data, None, actor, keep_type=d.detention_type)
    if c["detention_date"] and c["detention_date"] < _today().isoformat():
        problems.append("The new date has passed")
    session = get_session(session_id) if session_id else None
    if session and session.places_left is not None and session.places_left < 1:
        problems.append(f"{session.label} is full")
    with database.connect() as conn:
        if c["detention_date"]:
            problems += _clashes(conn, d.pupil_id, c, skip=d.detention_id)
        if problems:
            raise ValidationError(problems)
        new_id = conn.execute(
            f"INSERT INTO detentions (pupil_id, session_id, academic_year, set_by_username, "
            f"related_entry_id, rescheduled_from, {', '.join(FIELDS)}, updated_by) VALUES "
            f"(?, ?, ?, ?, ?, ?, {', '.join('?' * len(FIELDS))}, ?)",
            (d.pupil_id, data.get("session_id"), year_of(c["detention_date"]),
             d.set_by_username, d.related_entry_id, d.detention_id, *(c[k] for k in FIELDS),
             actor.username)).lastrowid
        conn.execute("UPDATE detentions SET status = 'Rescheduled', rescheduled_to = ?, "
                     "updated_by = ?, updated_at = datetime('now') WHERE detention_id = ?",
                     (new_id, actor.username, d.detention_id))
        _audit(conn, "reschedule", actor, detention_id=d.detention_id, pupil_id=d.pupil_id,
               to=new_id, date=c["detention_date"])
    activity_log.record("detentions.reschedule", target=d.admission_no, principal=actor)
    return get(new_id)


def delete(detention_id: int, *, actor: Principal, reason: str | None = None) -> bool:
    """The old Delete - the detentions lead only (others cancel)."""
    d = get(detention_id)
    _require_editor(actor, "delete", d.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM detentions WHERE detention_id = ?", (d.detention_id,))
        _audit(conn, "delete", actor, detention_id=d.detention_id, pupil_id=d.pupil_id,
               date=d.detention_date, reason=(reason or "")[:300] or None)
    activity_log.record("detentions.delete", target=d.admission_no, principal=actor)
    return True


# ── Summaries (old) and follow-up ────────────────────────────────────

def pupil_summary(pupil_id: int, *, academic_year: str | None = None) -> dict[str, Any]:
    rows = list_detentions(pupil_id=pupil_id, academic_year=academic_year)
    by = Counter(r.status for r in rows)
    return {"pupil_id": int(pupil_id),
            "total": sum(1 for r in rows if r.status != "Rescheduled"),
            "attended": by["Attended"], "missed": by["Missed"], "excused": by["Excused"],
            "scheduled": by["Scheduled"], "cancelled": by["Cancelled"],
            "rescheduled": by["Rescheduled"],
            "minutes_served": sum(r.duration_min for r in rows if r.status == "Attended"),
            "upcoming": sorted((r for r in rows if r.status == "Scheduled"),
                               key=lambda r: (r.detention_date, r.start_time or "")),
            "detentions": rows}


def cohort_summary(*, year_group: int | str | None = None, date_from: str | None = None,
                   date_to: str | None = None, academic_year: str | None = None
                   ) -> dict[str, Any]:
    rows = [r for r in list_detentions(year_group=year_group, date_from=date_from,
                                       date_to=date_to, academic_year=academic_year)
            if r.status != "Rescheduled"]
    done = [r for r in rows if r.status in ("Attended", "Missed")]
    return {"total": len(rows),
            "by_status": dict(Counter(r.status for r in rows)),
            "by_type": dict(Counter(r.detention_type for r in rows)),
            "missed": sum(1 for r in rows if r.status == "Missed"),
            "attended": sum(1 for r in rows if r.status == "Attended"),
            "minutes_served": sum(r.duration_min for r in rows if r.status == "Attended"),
            "attendance_pct": round(100 * sum(1 for r in done if r.status == "Attended")
                                    / len(done)) if done else None,
            "pupils": len({r.pupil_id for r in rows})}


def missed_to_follow_up(*, year_group: int | str | None = None) -> list[Detention]:
    """Missed detentions not yet rescheduled or excused, oldest first."""
    return sorted(list_detentions(status="Missed", year_group=year_group),
                  key=lambda r: (r.detention_date, r.pupil_name))


def _term_start(day: _dt.date) -> str:
    try:
        from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
        t = AY.term_for(day)
        if t:
            return t.start_date
    except Exception:  # noqa: BLE001
        pass
    return (day - _dt.timedelta(days=84)).isoformat()   # about a term


def concerns(*, year_group: int | str | None = None, today: _dt.date | None = None
             ) -> list[dict[str, Any]]:
    """Pupils who missed MISSED_CONCERN or more detentions this term (counting
    ones later rescheduled - the miss still happened)."""
    day = today or _today()
    since = _term_start(day)
    counts: Counter[int] = Counter()
    who: dict[int, Detention] = {}
    with database.connect() as conn:
        missed = {r[0] for r in conn.execute(
            "SELECT DISTINCT detention_id FROM detention_audit WHERE action = 'status' AND "
            "json_extract(detail, '$.to') = 'Missed'")}
    for r in list_detentions(year_group=year_group, date_from=since,
                             date_to=day.isoformat()):
        if r.status == "Missed" or (r.status == "Rescheduled" and r.detention_id in missed):
            counts[r.pupil_id] += 1
            who[r.pupil_id] = r
    return [{"pupil_id": pid, "pupil_name": who[pid].pupil_name,
             "admission_no": who[pid].admission_no, "year_group": who[pid].pupil_year,
             "missed": n, "reason": f"missed {n} detentions this term"}
            for pid, n in sorted(counts.items(), key=lambda x: -x[1]) if n >= MISSED_CONCERN]


def analysis(*, by: str = "type", year_group: int | str | None = None,
             academic_year: str | None = None, date_from: str | None = None,
             date_to: str | None = None) -> list[dict[str, Any]]:
    """Counts grouped by type, reason, member of staff, weekday or year group."""
    keys = {"type": lambda r: r.detention_type,
            "reason": lambda r: r.reason.split(":")[0][:40],
            "staff": lambda r: r.set_by or r.set_by_username or "(unknown)",
            "weekday": lambda r: _dt.date.fromisoformat(r.detention_date).strftime("%A"),
            "year": lambda r: f"Year {r.pupil_year}"}
    if by not in keys:
        raise ValidationError([f"Group by one of {', '.join(keys)}"])
    groups: dict[str, dict[str, Any]] = {}
    for r in list_detentions(year_group=year_group, academic_year=academic_year,
                             date_from=date_from, date_to=date_to):
        if r.status == "Rescheduled":
            continue
        k = keys[by](r)
        g = groups.setdefault(k, {"group": k, "total": 0, "attended": 0, "missed": 0,
                                  "minutes": 0, "pupils": set()})
        g["total"] += 1
        g["attended"] += r.status == "Attended"
        g["missed"] += r.status == "Missed"
        g["minutes"] += r.duration_min if r.status == "Attended" else 0
        g["pupils"].add(r.pupil_id)
    return sorted(({**g, "pupils": len(g["pupils"])} for g in groups.values()),
                  key=lambda g: (-g["total"], g["group"]))


# ── Families ─────────────────────────────────────────────────────────

def notify_parents(detention_ids: list[int], *, actor: Principal, note: str | None = None
                   ) -> dict[str, Any]:
    """E-mail a notice of the chosen detentions (new ones, or missed ones) to
    each pupil's contacts with parental responsibility - one e-mail per pupil
    and contact. Returns {'message_id', 'emails', 'no_email'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    _require_staff(actor, "notify")
    rows = [get(i) for i in dict.fromkeys(int(x) for x in detention_ids)]
    rows = [r for r in rows if r.status in ("Scheduled", "Missed")]
    if not rows:
        raise ValidationError(["Choose at least one scheduled or missed detention"])
    by_pupil: dict[int, list[Detention]] = {}
    for r in rows:
        by_pupil.setdefault(r.pupil_id, []).append(r)
    contacts = C.emailable_for_pupils(list(by_pupil))
    template = email_templates.load_template("detention_notice")
    sender = BH._staff_name(actor)
    letters, no_email = [], []
    for pid, mine in by_pupil.items():
        p = P.get_pupil(pid)
        to = [(c.email, c.full_name) for c in contacts.get(pid, [])
              if c.email and c.parental_responsibility]
        if not to:
            no_email.append(p)
            continue
        first = p.preferred_name or p.legal_first_name
        missed = all(r.status == "Missed" for r in mine)
        lines = "\n".join(
            f"  {_dt.date.fromisoformat(r.detention_date).strftime('%A %d %B %Y')}"
            + (f" at {r.start_time}" if r.start_time else "")
            + f" - {r.detention_type} detention, {r.duration_min} minutes"
            + (f", {r.location}" if r.location else "")
            + ("  (missed)" if r.status == "Missed" else "")
            + f"\n    Reason: {r.reason}"
            for r in sorted(mine, key=lambda r: r.detention_date))
        for address, name in to:
            subject, body = template.render({
                "recipient_name": name, "pupil_name": p.display_name,
                "headline": "Missed detention" if missed else "Detention",
                "intro": (f"{first} did not attend the detention below." if missed else
                          f"{first} has been given the detention below."),
                "details": lines + (f"\n\n{note.strip()}" if note and note.strip() else ""),
                "closing": ("We will arrange a new date. If there was a reason, please let "
                            f"{first}'s form tutor know." if missed else
                            "If there is a reason this time is a problem - for example "
                            f"getting home - please contact {first}'s form tutor."),
                "sender_name": sender})
            letters.append((address, name, subject, body))
    mid = E.save_prepared("detention_notice", "Detention notice", "Detention notice",
                          "(one notice per pupil)", letters, actor=actor) if letters else None
    now = _dt.datetime.now().isoformat(timespec="seconds")
    reached = {pid for pid in by_pupil if pid not in {p.pupil_id for p in no_email}}
    with database.connect() as conn:
        for r in rows:
            if r.pupil_id in reached:
                conn.execute("UPDATE detentions SET parents_notified_at = ? WHERE "
                             "detention_id = ?", (now, r.detention_id))
                _audit(conn, "notify", actor, detention_id=r.detention_id, pupil_id=r.pupil_id)
    activity_log.record("detentions.notify", principal=actor, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "no_email": no_email}


def for_family(pupil_id: int, academic_year: str | None = None) -> dict[str, Any]:
    """What the portal shows: upcoming detentions and this year's past ones."""
    rows = [r for r in list_detentions(pupil_id=pupil_id,
                                       academic_year=academic_year or current_year())
            if r.status not in ("Rescheduled", "Cancelled")]
    return {"upcoming": sorted((r for r in rows if r.status == "Scheduled"),
                               key=lambda r: (r.detention_date, r.start_time or "")),
            "past": [r for r in rows if r.status != "Scheduled"]}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_detentions(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "date", "time", "minutes", "type", "admission_no", "pupil", "year",
                    "form", "location", "supervisor", "reason", "set_by", "status",
                    "behaviour_entry", "session", "rescheduled_to", "parents_notified"])
        for r in rows:
            w.writerow([r.detention_id, r.detention_date, r.start_time or "", r.duration_min,
                        r.detention_type, _safe(r.admission_no), _safe(r.pupil_name),
                        r.pupil_year, _safe(r.form_group), _safe(r.location),
                        _safe(r.supervisor), _safe(r.reason), _safe(r.set_by), r.status,
                        r.related_entry_id or "", r.session_id or "", r.rescheduled_to or "",
                        r.parents_notified_at or ""])
    activity_log.record("detentions.export", principal=actor, rows=len(rows))
    return len(rows)
