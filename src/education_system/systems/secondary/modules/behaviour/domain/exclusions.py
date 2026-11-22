"""Suspensions and exclusions: cases, the steps the law sets, and follow-up.

Kept from the old Disciplinary cases:

* One case per pupil with type (Internal exclusion, Fixed-term suspension,
  Permanent exclusion, Reduced timetable, Parental meeting, Governors panel,
  Behaviour contract, Restorative meeting, Other), severity (Low, Medium,
  High, Critical), incident date, start and end dates, days (filled in from
  the dates when left blank, 0-365), reason (required, 500 characters),
  decision maker, status (Open, InProgress, Closed, Appealed, Overturned),
  appeal decision (required when Appealed or Overturned), return date (not
  before the start) and notes.
* A dated log of events for each case (Meeting, Letter sent, Phone call,
  Return-to-school, Reintegration, Appeal lodged, Appeal decision, Governors
  decision, Decision, Other) with participants, summary (required), outcome,
  follow-up and notes.
* The case summary and the cohort summary (total, open, by status / type /
  severity, total days).

New, following the DfE guidance on suspension and permanent exclusion:

* **Who.** Only the headteacher suspends or excludes, so creating, changing
  and deciding cases is for :data:`EXCLUSION_EDITORS`; the decision maker is
  required on a suspension or permanent exclusion. All staff can see cases
  (they set work and need to know who is out); the pupil's head of year can
  add events. Every change is in ``exclusion_audit`` and the activity log
  (ids only).
* **School days.** Days are counted in school days from the school calendar
  (weekdays when it has none). Suspensions can't add up to more than
  :data:`MAX_SUSPENSION_DAYS` school days in a school year; a pupil's formal
  cases can't overlap; a suspension has an end date, a permanent exclusion
  doesn't. A suspension can't be extended or turned into a permanent
  exclusion once the family has been told - that is a new case.
* **Deadlines.** :func:`deadlines` lists the steps for a case with their due
  dates: tell the family without delay, tell the governors and the local
  authority, education from the sixth school day, the governors' meeting
  (within 15 school days for a permanent exclusion or more than 15 days'
  suspension in a term; on request above 5), the reintegration meeting and
  the window to ask for an independent review. :func:`due` lists what is
  outstanding across the school.
* **Decisions.** The governors' decision (upheld / reinstated) and the
  independent review panel (upheld / recommend reconsider / quash) are
  recorded on the case and in its events. A headteacher can withdraw a case.
* **Attendance.** :func:`mark_attendance` puts code E (or B once off-site
  education starts) on the register for the days the pupil is out.
* **Off roll.** A permanent exclusion takes the pupil off roll only once the
  governors have upheld it and the review window has passed (or the review
  upheld it) - through Enrolment & Leavers, with the reason "Permanent
  exclusion".
* **Families.** A notice e-mail to contacts with parental responsibility,
  with the dates, the reason and their right to make representations; the
  portal shows their child's suspensions.
* **From behaviour.** A case can be raised from a behaviour entry (its
  "action taken" says so); pupils suspended this school year feed the
  behaviour concerns and intervention suggestions.
* **Reports.** By type, reason category (the census list), year group,
  severity and month; CSV export.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH  # registers the FK target
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    EXCLUSION_EDITORS,
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

SUSPENSION = "Fixed-term suspension"
PERMANENT = "Permanent exclusion"
CASE_TYPES: tuple[str, ...] = (
    "Internal exclusion", SUSPENSION, PERMANENT, "Reduced timetable", "Parental meeting",
    "Governors panel", "Behaviour contract", "Restorative meeting", "Other")
DEFAULT_TYPE = SUSPENSION
#: The two the law calls exclusions: the pupil is out of school.
FORMAL = frozenset({SUSPENSION, PERMANENT})
CASE_STATUSES: tuple[str, ...] = ("Open", "InProgress", "Closed", "Appealed", "Overturned")
DEFAULT_STATUS = "Open"
#: Statuses where the case no longer counts (withdrawn or reinstated).
VOID = frozenset({"Overturned"})
SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY = "High"
EVENT_TYPES: tuple[str, ...] = (
    "Meeting", "Letter sent", "Phone call", "Return-to-school", "Reintegration",
    "Appeal lodged", "Appeal decision", "Governors decision", "Decision", "Other",
    "Work set", "Local authority informed", "Governors informed", "Independent review")
DEFAULT_EVENT_TYPE = "Meeting"
#: The reasons the school census asks for (suspensions and permanent exclusions).
REASON_CATEGORIES: tuple[str, ...] = (
    "Physical assault against a pupil", "Physical assault against an adult",
    "Verbal abuse or threatening behaviour against a pupil",
    "Verbal abuse or threatening behaviour against an adult",
    "Use or threat of use of an offensive weapon or prohibited item", "Bullying",
    "Racist abuse", "Abuse against sexual orientation and gender identity",
    "Abuse relating to disability", "Sexual misconduct", "Drug and alcohol related",
    "Damage", "Theft", "Inappropriate use of social media or online technology",
    "Persistent or general disruptive behaviour", "Wilful and repeated transgression of "
    "protective measures to protect public health", "Other")
GOVERNOR_DECISIONS: tuple[str, ...] = ("Upheld", "Reinstated")
REVIEW_OUTCOMES: tuple[str, ...] = ("Upheld", "Recommend reconsider", "Quash")

MAX_SUSPENSION_DAYS = 45      # school days in a school year
GOVERNORS_MUST_ABOVE = 15     # suspension days in a term: governors must meet
GOVERNORS_ON_REQUEST_ABOVE = 5  # ... and above this if the parents ask
GOVERNORS_WITHIN = 15         # school days from the notice
REVIEW_WITHIN = 15            # school days from the governors' decision
PROVISION_FROM_DAY = 6        # education must be arranged from this school day
MAX_REASON = 500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exclusion_cases (
    case_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id                INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year           TEXT NOT NULL,
    case_type               TEXT NOT NULL DEFAULT 'Fixed-term suspension',
    severity                TEXT NOT NULL DEFAULT 'High'
                            CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    incident_date           TEXT,
    start_date              TEXT NOT NULL,
    end_date                TEXT,
    days                    INTEGER CHECK (days IS NULL OR days BETWEEN 0 AND 365),
    reason                  TEXT NOT NULL,
    reason_category         TEXT,
    decision_maker          TEXT,
    status                  TEXT NOT NULL DEFAULT 'Open' CHECK (status IN
                            ('Open', 'InProgress', 'Closed', 'Appealed', 'Overturned')),
    appeal_decision         TEXT,
    return_date             TEXT,
    notes                   TEXT,
    related_entry_id        INTEGER REFERENCES behaviour_entries (entry_id) ON DELETE SET NULL,
    parents_notified_at     TEXT,
    governors_notified_at   TEXT,
    la_notified_at          TEXT,
    provision_from          TEXT,
    provision_details       TEXT,
    reintegration_date      TEXT,
    governors_meeting_date  TEXT,
    governors_decision      TEXT CHECK (governors_decision IS NULL OR
                            governors_decision IN ('Upheld', 'Reinstated')),
    review_requested_date   TEXT,
    review_date             TEXT,
    review_outcome          TEXT CHECK (review_outcome IS NULL OR review_outcome IN
                            ('Upheld', 'Recommend reconsider', 'Quash')),
    off_roll_date           TEXT,
    created_by              TEXT,
    created_at              TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by              TEXT,
    updated_at              TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_exclusion_cases_pupil ON exclusion_cases (pupil_id, academic_year);
CREATE INDEX IF NOT EXISTS ix_exclusion_cases_status ON exclusion_cases (status);
CREATE TABLE IF NOT EXISTS exclusion_events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id       INTEGER NOT NULL REFERENCES exclusion_cases (case_id) ON DELETE CASCADE,
    event_date    TEXT NOT NULL,
    event_type    TEXT NOT NULL DEFAULT 'Meeting',
    participants  TEXT,
    summary       TEXT NOT NULL,
    outcome       TEXT,
    follow_up     TEXT,
    notes         TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_exclusion_events_case ON exclusion_events (case_id);
CREATE TABLE IF NOT EXISTS exclusion_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id    INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("exclusions", _SCHEMA)


@dataclass(frozen=True)
class Case:
    case_id: int
    pupil_id: int
    academic_year: str
    case_type: str
    severity: str
    incident_date: str | None
    start_date: str
    end_date: str | None
    days: int | None
    reason: str
    reason_category: str | None
    decision_maker: str | None
    status: str
    appeal_decision: str | None
    return_date: str | None
    notes: str | None
    related_entry_id: int | None
    parents_notified_at: str | None
    governors_notified_at: str | None
    la_notified_at: str | None
    provision_from: str | None
    provision_details: str | None
    reintegration_date: str | None
    governors_meeting_date: str | None
    governors_decision: str | None
    review_requested_date: str | None
    review_date: str | None
    review_outcome: str | None
    off_roll_date: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def is_formal(self) -> bool:
        return self.case_type in FORMAL

    @property
    def counts(self) -> bool:
        """Still stands (not withdrawn or reinstated)."""
        return self.status not in VOID

    @property
    def period(self) -> str:
        if self.case_type == PERMANENT:
            return f"permanent from {self.start_date}"
        if self.end_date and self.end_date != self.start_date:
            return f"{self.start_date} to {self.end_date}"
        return self.start_date


@dataclass(frozen=True)
class Event:
    event_id: int
    case_id: int
    event_date: str
    event_type: str
    participants: str | None
    summary: str
    outcome: str | None
    follow_up: str | None
    notes: str | None
    created_by: str | None
    created_at: str


_SELECT = """
SELECT c.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group AS pupil_year, p.form_group
FROM exclusion_cases c JOIN pupils p USING (pupil_id)
"""
_BASE = tuple(f for f in Case.__dataclass_fields__ if f not in (
    "pupil_name", "admission_no", "pupil_year", "form_group"))
_SEVERITY_ORDER = "CASE c.severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 " \
                  "WHEN 'Medium' THEN 2 ELSE 3 END"


def _row(r) -> Case:
    return Case(**{k: r[k] for k in _BASE},
                pupil_name=f"{r['legal_last_name']}, "
                           f"{r['preferred_name'] or r['legal_first_name']}",
                admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                form_group=r["form_group"])


def _event_row(r) -> Event:
    return Event(**{k: r[k] for k in Event.__dataclass_fields__})


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in EXCLUSION_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"exclusions.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see suspensions and exclusions.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the headteacher's office (suspensions and "
                                     "exclusions lead) can do that.")


def can_add_event(actor: Principal, c: Case) -> bool:
    """Events: the lead, or the pupil's head of year."""
    return is_editor(actor) or (actor.role in STAFF_ROLES and
                                BH.is_head_of_year(actor, c.pupil_year))


def _audit(conn, action: str, actor: Principal, *, case_id: int | None = None,
           pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO exclusion_audit (case_id, pupil_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (case_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(case_id: int | None = None, *, pupil_id: int | None = None,
            limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM exclusion_audit", [], []
    for col, val in (("case_id", case_id), ("pupil_id", pupil_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(int(val))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "case_id": r["case_id"], "pupil_id": r["pupil_id"],
                 "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── School days ──────────────────────────────────────────────────────

def _AT():
    from education_system.systems.secondary.modules.attendance.domain import attendance
    return attendance


def school_days(start: str | _dt.date, end: str | _dt.date) -> list[_dt.date]:
    """School days from *start* to *end* inclusive (calendar, else weekdays)."""
    s = _dt.date.fromisoformat(str(start)) if not isinstance(start, _dt.date) else start
    e = _dt.date.fromisoformat(str(end)) if not isinstance(end, _dt.date) else end
    return _AT().school_days(s, e) if e >= s else []


def is_school_day(day: str | _dt.date) -> tuple[bool, str]:
    d = _dt.date.fromisoformat(str(day)) if not isinstance(day, _dt.date) else day
    try:
        return _AT().school_day(d)
    except Exception:  # noqa: BLE001 - the calendar is a help, not a gate
        return d.weekday() < 5, ""


def nth_school_day(start: str | _dt.date, n: int) -> _dt.date:
    """The *n*-th school day counting *start* as day 1 if it is one."""
    s = _dt.date.fromisoformat(str(start)) if not isinstance(start, _dt.date) else start
    span = max(14, n * 3)
    while True:
        days = school_days(s, s + _dt.timedelta(days=span))
        if len(days) >= n:
            return days[n - 1]
        if span > 800:      # no school days ahead in the calendar: count weekdays
            d, k = s, 0
            while True:
                if d.weekday() < 5:
                    k += 1
                    if k == n:
                        return d
                d += _dt.timedelta(days=1)
        span *= 2


def school_days_after(day: str | _dt.date, n: int) -> _dt.date:
    """The *n*-th school day after *day* (not counting *day*)."""
    d = _dt.date.fromisoformat(str(day)) if not isinstance(day, _dt.date) else day
    return nth_school_day(d + _dt.timedelta(days=1), n)


def _term_bounds(day: _dt.date) -> tuple[str, str]:
    try:
        from education_system.systems.secondary.modules.curriculum.domain import academic_year as AY
        t = AY.term_for(day)
        if t:
            return t.start_date, t.end_date
    except Exception:  # noqa: BLE001
        pass
    return (day - _dt.timedelta(days=84)).isoformat(), (day + _dt.timedelta(days=84)).isoformat()


# ── Cleaning ─────────────────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _text(value: Any, limit: int) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


FIELDS = ("case_type", "severity", "incident_date", "start_date", "end_date", "days", "reason",
          "reason_category", "decision_maker", "status", "appeal_decision", "return_date",
          "notes", "provision_from", "provision_details", "reintegration_date")


def _clean(data: dict[str, Any], current: Case | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}
    out["case_type"] = _choice(merged.get("case_type"), CASE_TYPES, "Case type", problems,
                               DEFAULT_TYPE)
    out["severity"] = _choice(merged.get("severity"), SEVERITIES, "Severity", problems,
                              DEFAULT_SEVERITY)
    out["status"] = _choice(merged.get("status"), CASE_STATUSES, "Status", problems,
                            DEFAULT_STATUS)
    for k, label in (("incident_date", "Incident date"), ("start_date", "Start date"),
                     ("end_date", "End date"), ("return_date", "Return date"),
                     ("provision_from", "Education from"),
                     ("reintegration_date", "Reintegration meeting")):
        out[k] = _date(merged.get(k), label, problems)
    if out["start_date"] is None and not any(p.startswith("Start date") for p in problems):
        problems.append("Start date is required")
    s, e = out["start_date"], out["end_date"]
    formal = out["case_type"] in FORMAL
    if s and e and e < s:
        problems.append("End date cannot be before start date")
    if out["case_type"] == PERMANENT and e:
        problems.append("A permanent exclusion has no end date")
    if out["case_type"] == SUSPENSION and s and not e:
        problems.append("A suspension needs an end date (the last day the pupil is out)")
    if out["incident_date"] and s and out["incident_date"] > s:
        problems.append("The incident can't be after the start date")
    if out["return_date"] and s and out["return_date"] < s:
        problems.append("Return date cannot be before start date")
    if out["return_date"] and e and out["return_date"] <= e:
        problems.append("Return date must be after the end date")
    if out["provision_from"] and s and out["provision_from"] < s:
        problems.append("Education from can't be before the start date")
    if formal and s and not problems:
        ok, label = is_school_day(s)
        if not ok:
            problems.append(f"{s} isn't a school day ({label}) - start on the next school day")
    raw = merged.get("days")
    if raw in (None, "") or (isinstance(raw, str) and not raw.strip()) or (
            current is not None and "days" not in data and
            any(k in data for k in ("start_date", "end_date"))):
        out["days"] = len(school_days(s, e)) if s and e and not problems else None
    else:
        try:
            n = int(str(raw).strip())
            if not 0 <= n <= 365:
                problems.append("Days must be between 0 and 365")
            out["days"] = n
        except ValueError:
            problems.append("Days must be a whole number")
            out["days"] = None
    reason = " ".join(str(merged.get("reason") or "").split())
    if not reason:
        problems.append("Reason is required")
    elif len(reason) > MAX_REASON:
        problems.append(f"Reason must be {MAX_REASON} chars or fewer")
    out["reason"] = reason
    out["reason_category"] = _choice(merged.get("reason_category"), REASON_CATEGORIES,
                                     "Reason category", problems, None)
    if formal and not out["reason_category"]:
        problems.append("Choose the reason category (the census asks for it)")
    out["decision_maker"] = _text(merged.get("decision_maker"), 80)
    if formal and not out["decision_maker"]:
        problems.append("Record who decided - only the headteacher can suspend or exclude")
    out["appeal_decision"] = _text(merged.get("appeal_decision"), 500)
    if out["status"] in ("Appealed", "Overturned") and not out["appeal_decision"]:
        problems.append(f"Appeal decision is required when status is {out['status']}")
    out["notes"] = _text(merged.get("notes"), 4000)
    out["provision_details"] = _text(merged.get("provision_details"), 500)
    return out, problems


def _formal_rows(conn, pupil_id: int, skip: int | None = None):
    return conn.execute(
        "SELECT * FROM exclusion_cases WHERE pupil_id = ? AND case_type IN (?, ?) AND "
        "status != 'Overturned' AND case_id != ?",
        (pupil_id, SUSPENSION, PERMANENT, skip or 0)).fetchall()


def _rule_problems(conn, pupil_id: int, c: dict[str, Any], skip: int | None = None
                   ) -> list[str]:
    """Overlaps and the 45-day limit, for a formal case that still stands."""
    if c["case_type"] not in FORMAL or c["status"] in VOID or not c["start_date"]:
        return []
    out: list[str] = []
    end = c["end_date"] or "9999-12-31"
    rows = _formal_rows(conn, pupil_id, skip)
    for r in rows:
        r_end = r["end_date"] or ("9999-12-31" if not r["off_roll_date"] else r["off_roll_date"])
        if r["case_type"] == PERMANENT and r["governors_decision"] == "Reinstated":
            continue
        if c["start_date"] <= r_end and r["start_date"] <= end:
            out.append(f"Overlaps case #{r['case_id']} ({r['case_type'].lower()}, "
                       f"{r['start_date']}" + (f" to {r['end_date']}" if r["end_date"] else "")
                       + ")")
    if c["case_type"] == SUSPENSION:
        year = year_of(c["start_date"])
        used = sum(int(r["days"] or 0) for r in rows if r["case_type"] == SUSPENSION and
                   r["academic_year"] == year)
        total = used + int(c["days"] or 0)
        if total > MAX_SUSPENSION_DAYS:
            out.append(f"That would make {total} school days of suspension in {year} - "
                       f"the limit is {MAX_SUSPENSION_DAYS}")
    return out


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
    return e.entry_id


# ── Reading ──────────────────────────────────────────────────────────

def get(case_id: int) -> Case:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE c.case_id = ?", (int(case_id),)).fetchone()
    if r is None:
        raise NotFound(f"No case #{case_id}")
    return _row(r)


def get_case(case_id: int) -> Case | None:
    """The old lookup: None when there is no such case."""
    try:
        return get(case_id)
    except NotFound:
        return None


def list_cases(*, pupil_id: int | None = None, year_group: int | str | None = None,
               case_type: str | None = None, severity: str | None = None,
               status: str | None = None, academic_year: str | None = None,
               formal_only: bool = False, date_from: str | None = None,
               date_to: str | None = None, limit: int = 2000) -> list[Case]:
    """Cases, most severe first then newest (the old order)."""
    where, params = [], []
    for col, val in (("c.pupil_id", pupil_id), ("c.case_type", case_type),
                     ("c.severity", severity), ("c.status", status),
                     ("c.academic_year", academic_year)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if year_group not in (None, ""):
        where.append("p.year_group = ?")
        params.append(int(year_group))
    if formal_only:
        where.append("c.case_type IN (?, ?)")
        params += [SUSPENSION, PERMANENT]
    if date_from:
        where.append("COALESCE(c.end_date, '9999-12-31') >= ?")
        params.append(date_from)
    if date_to:
        where.append("c.start_date <= ?")
        params.append(date_to)
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        f" ORDER BY {_SEVERITY_ORDER}, c.start_date DESC, c.case_id DESC LIMIT ?"
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql, (*params, int(limit)))]


def out_on(day: _dt.date | None = None, *, year_group: int | str | None = None) -> list[Case]:
    """Pupils out of school on *day*: suspensions covering it and permanent
    exclusions still on roll."""
    iso = (day or _today()).isoformat()
    return [c for c in list_cases(year_group=year_group, formal_only=True, date_from=iso,
                                  date_to=iso)
            if c.counts and not c.off_roll_date and c.governors_decision != "Reinstated"]


def list_events(case_id: int) -> list[Event]:
    with database.connect() as conn:
        return [_event_row(r) for r in conn.execute(
            "SELECT * FROM exclusion_events WHERE case_id = ? ORDER BY event_date, event_id",
            (int(case_id),))]


def suspension_days(pupil_id: int, *, academic_year: str | None = None,
                    skip: int | None = None) -> int:
    """School days of suspension that still stand in a school year."""
    year = academic_year or current_year()
    return sum(int(c.days or 0) for c in list_cases(pupil_id=pupil_id, case_type=SUSPENSION,
                                                    academic_year=year)
               if c.counts and c.case_id != skip)


def term_days(pupil_id: int, day: str | _dt.date) -> int:
    """School days of suspension in the term holding *day*."""
    d = _dt.date.fromisoformat(str(day)) if not isinstance(day, _dt.date) else day
    lo, hi = _term_bounds(d)
    return sum(int(c.days or 0) for c in list_cases(pupil_id=pupil_id, case_type=SUSPENSION,
                                                    date_from=lo, date_to=hi)
               if c.counts and lo <= c.start_date <= hi)


def check(data: dict[str, Any], *, actor: Principal, case_id: int | None = None
          ) -> list[str]:
    """Warnings worth a second look before saving (the save still checks the
    rules): the pupil's other suspensions, a governors' meeting it triggers, a
    pupil with SEN or an EHC plan, a long gap since the incident."""
    _require_staff(actor, "check")
    current = get(case_id) if case_id else None
    c, problems = _clean(data, current)
    p = _pupil(data.get("pupil_id") or data.get("pupil")) if current is None else \
        P.get_pupil(current.pupil_id)
    if problems or p is None or c["case_type"] not in FORMAL:
        return []
    out: list[str] = []
    used = suspension_days(p.pupil_id, academic_year=year_of(c["start_date"]), skip=case_id)
    if c["case_type"] == SUSPENSION:
        if used:
            out.append(f"{p.display_name} already has {used} school day(s) of suspension "
                       f"this school year (limit {MAX_SUSPENSION_DAYS}).")
        in_term = term_days(p.pupil_id, c["start_date"]) - (current.days or 0 if current
                                                            else 0) + int(c["days"] or 0)
        if in_term > GOVERNORS_MUST_ABOVE:
            out.append(f"This makes {in_term} days this term: the governors must meet to "
                       f"consider reinstatement within {GOVERNORS_WITHIN} school days.")
        elif in_term > GOVERNORS_ON_REQUEST_ABOVE:
            out.append(f"This makes {in_term} days this term: the governors must meet if the "
                       "parents ask.")
        if int(c["days"] or 0) >= PROVISION_FROM_DAY:
            out.append(f"Over 5 school days: the school must arrange full-time education from "
                       f"day {PROVISION_FROM_DAY} ({nth_school_day(c['start_date'], 6)}).")
    sen = getattr(p, "sen_status", None)
    if sen == "E":
        out.append(f"{p.display_name} has an EHC plan - consider whether the plan needs an "
                   "early review, and involve the local authority.")
    elif sen == "K":
        out.append(f"{p.display_name} has SEN support - make sure the SENCO is involved.")
    if c["incident_date"] and (_dt.date.fromisoformat(c["start_date"]) -
                               _dt.date.fromisoformat(c["incident_date"])).days > 14:
        out.append("The start date is more than two weeks after the incident.")
    return out


# ── Writing ──────────────────────────────────────────────────────────

def create_case(data: dict[str, Any], *, actor: Principal) -> Case:
    """The old New case. *data* carries ``pupil_id`` (id or admission no.)."""
    _require_editor(actor, "create")
    problems: list[str] = []
    p = _pupil(data.get("pupil_id") or data.get("pupil"))
    if p is None:
        problems.append("Pupil ID is required" if not (data.get("pupil_id") or
                                                       data.get("pupil"))
                        else f"No pupil {data.get('pupil_id') or data.get('pupil')}")
    elif p.roll_status != "on_roll":
        problems.append(f"{p.display_name} is not on roll")
    c, more = _clean(data, None)
    problems += more
    entry = _entry(data.get("related_entry_id"), p.pupil_id, problems) if p else None
    with database.connect() as conn:
        if p and not problems:
            problems += _rule_problems(conn, p.pupil_id, c)
        if problems:
            activity_log.record("exclusions.create", outcome="invalid", principal=actor,
                                problems=len(problems))
            raise ValidationError(problems)
        cid = conn.execute(
            f"INSERT INTO exclusion_cases (pupil_id, academic_year, related_entry_id, "
            f"{', '.join(FIELDS)}, created_by, updated_by) VALUES (?, ?, ?, "
            f"{', '.join('?' * len(FIELDS))}, ?, ?)",
            (p.pupil_id, year_of(c["start_date"]), entry, *(c[k] for k in FIELDS),
             actor.username, actor.username)).lastrowid
        _audit(conn, "create", actor, case_id=cid, pupil_id=p.pupil_id, type=c["case_type"],
               days=c["days"])
    if entry:
        BH.add_action(entry, f"{c['case_type']} ({c['start_date']}"
                             + (f" to {c['end_date']}" if c["end_date"] else "") + ")",
                      actor=actor)
    activity_log.record("exclusions.create", target=p.admission_no, principal=actor,
                        case=cid, type=c["case_type"])
    return get(cid)


def from_behaviour(entry_id: int, data: dict[str, Any], *, actor: Principal) -> Case:
    """A case for a behaviour entry's pupil, linked to it."""
    e = BH.get(entry_id)
    return create_case({**data, "pupil_id": e.pupil_id, "related_entry_id": e.entry_id,
                        "incident_date": data.get("incident_date") or e.entry_date,
                        "reason": data.get("reason") or
                        f"{e.incident_type}: {e.description}"[:MAX_REASON]}, actor=actor)


def update_case(case_id: int, changes: dict[str, Any], *, actor: Principal) -> Case:
    """The old Edit case."""
    cur = get(case_id)
    _require_editor(actor, "update", cur.admission_no)
    c, problems = _clean(changes, cur)
    entry = _entry(changes["related_entry_id"], cur.pupil_id, problems) \
        if "related_entry_id" in changes else cur.related_entry_id
    if cur.off_roll_date:
        problems.append("The pupil has been taken off roll for this exclusion - the case "
                        "can't be changed")
    if cur.is_formal and cur.parents_notified_at and (
            c["case_type"] != cur.case_type or (c["end_date"] or "") > (cur.end_date or "")):
        problems.append("The family has been told - a suspension can't be extended or "
                        "turned into a permanent exclusion. Record a new case instead.")
    changed = [k for k in FIELDS if c[k] != getattr(cur, k)]
    if entry != cur.related_entry_id:
        changed.append("related_entry_id")
    with database.connect() as conn:
        if not problems and any(k in changed for k in ("case_type", "start_date", "end_date",
                                                       "days", "status")):
            problems += _rule_problems(conn, cur.pupil_id, c, skip=cur.case_id)
        if problems:
            raise ValidationError(problems)
        if not changed:
            return cur
        vals = {k: c[k] for k in changed if k in FIELDS}
        if "related_entry_id" in changed:
            vals["related_entry_id"] = entry
        conn.execute("UPDATE exclusion_cases SET " + ", ".join(f"{k} = ?" for k in vals)
                     + ", academic_year = ?, updated_by = ?, updated_at = datetime('now') "
                       "WHERE case_id = ?",
                     (*vals.values(), year_of(c["start_date"]), actor.username, cur.case_id))
        _audit(conn, "update", actor, case_id=cur.case_id, pupil_id=cur.pupil_id,
               fields=changed)
    activity_log.record("exclusions.update", target=cur.admission_no, principal=actor,
                        case=cur.case_id, fields=",".join(changed))
    return get(cur.case_id)


def set_status(case_id: int, status: str, *, actor: Principal,
               appeal_decision: str | None = None) -> Case:
    """The old Set status (Appealed / Overturned need the appeal decision)."""
    changes: dict[str, Any] = {"status": status}
    if appeal_decision not in (None, ""):
        changes["appeal_decision"] = appeal_decision
    return update_case(case_id, changes, actor=actor)


def withdraw(case_id: int, *, actor: Principal, reason: str) -> Case:
    """The headteacher withdraws a case (it stops counting)."""
    why = " ".join(str(reason or "").split())
    if not why:
        raise ValidationError(["Say why the case is withdrawn"])
    c = set_status(case_id, "Overturned", actor=actor,
                   appeal_decision=f"Withdrawn by the headteacher: {why}"[:500])
    _event(c, "Decision", f"Withdrawn: {why}", actor)
    return c


def delete_case(case_id: int, *, actor: Principal) -> bool:
    """The old Delete case (its events go with it)."""
    c = get(case_id)
    _require_editor(actor, "delete", c.admission_no)
    if c.off_roll_date:
        raise ValidationError(["The pupil was taken off roll for this exclusion - keep the "
                               "case (withdraw it if it was made in error)"])
    with database.connect() as conn:
        conn.execute("DELETE FROM exclusion_cases WHERE case_id = ?", (c.case_id,))
        _audit(conn, "delete", actor, case_id=c.case_id, pupil_id=c.pupil_id,
               type=c.case_type)
    activity_log.record("exclusions.delete", target=c.admission_no, principal=actor,
                        case=c.case_id)
    return True


# ── Events ───────────────────────────────────────────────────────────

def _event(c: Case, event_type: str, summary: str, actor: Principal, *,
           outcome: str | None = None, day: str | None = None, conn=None) -> int:
    sql = ("INSERT INTO exclusion_events (case_id, event_date, event_type, summary, outcome, "
           "created_by) VALUES (?, ?, ?, ?, ?, ?)")
    args = (c.case_id, day or _today().isoformat(), event_type, summary[:2000], outcome,
            actor.username)
    if conn is not None:
        return conn.execute(sql, args).lastrowid
    with database.connect() as db:
        return db.execute(sql, args).lastrowid


def add_event(data: dict[str, Any], *, actor: Principal) -> Event:
    """The old Add event. *data* carries ``case_id``."""
    problems: list[str] = []
    try:
        c = get(int(str(data.get("case_id") or "").strip()))
    except ValueError:
        raise ValidationError(["Case ID is required" if not data.get("case_id")
                               else "Case ID must be a number"]) from None
    if not can_add_event(actor, c):
        _deny(actor, "event", c.admission_no,
              "Only the suspensions and exclusions lead or the pupil's head of year can add "
              "events.")
    day = _date(data.get("event_date"), "Event date", problems) or _today().isoformat()
    etype = _choice(data.get("event_type"), EVENT_TYPES, "Event type", problems,
                    DEFAULT_EVENT_TYPE)
    summary = str(data.get("summary") or "").strip()
    if not summary:
        problems.append("Summary is required")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        eid = conn.execute(
            "INSERT INTO exclusion_events (case_id, event_date, event_type, participants, "
            "summary, outcome, follow_up, notes, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (c.case_id, day, etype, _text(data.get("participants"), 300), summary[:2000],
             _text(data.get("outcome"), 2000), _text(data.get("follow_up"), 1000),
             _text(data.get("notes"), 2000), actor.username)).lastrowid
        _audit(conn, "event", actor, case_id=c.case_id, pupil_id=c.pupil_id, event=eid,
               type=etype)
    activity_log.record("exclusions.event", target=c.admission_no, principal=actor,
                        case=c.case_id, type=etype)
    with database.connect() as conn:
        return _event_row(conn.execute("SELECT * FROM exclusion_events WHERE event_id = ?",
                                       (eid,)).fetchone())


def delete_event(event_id: int, *, actor: Principal) -> bool:
    with database.connect() as conn:
        r = conn.execute("SELECT case_id FROM exclusion_events WHERE event_id = ?",
                         (int(event_id),)).fetchone()
    if r is None:
        raise NotFound(f"No event #{event_id}")
    c = get(r["case_id"])
    _require_editor(actor, "event_delete", c.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM exclusion_events WHERE event_id = ?", (int(event_id),))
        _audit(conn, "event_delete", actor, case_id=c.case_id, pupil_id=c.pupil_id,
               event=int(event_id))
    activity_log.record("exclusions.event_delete", target=c.admission_no, principal=actor,
                        case=c.case_id)
    return True


# ── Steps the law sets ───────────────────────────────────────────────

_NOTIFY = {"governors": ("governors_notified_at", "Governors informed"),
           "la": ("la_notified_at", "Local authority informed")}


def record_notified(case_id: int, who: str, *, actor: Principal, day: str | None = None,
                    note: str | None = None) -> Case:
    """Record that the governing board or the local authority was told."""
    c = get(case_id)
    _require_editor(actor, "notified", c.admission_no)
    if who not in _NOTIFY:
        raise ValidationError(["Choose governors or la"])
    problems: list[str] = []
    d = _date(day, "Date", problems) or _today().isoformat()
    if d > _today().isoformat():
        problems.append("The date can't be in the future")
    if problems:
        raise ValidationError(problems)
    col, etype = _NOTIFY[who]
    with database.connect() as conn:
        conn.execute(f"UPDATE exclusion_cases SET {col} = ?, updated_by = ?, "
                     "updated_at = datetime('now') WHERE case_id = ?",
                     (d, actor.username, c.case_id))
        _event(c, etype, note or f"{etype} of the {c.case_type.lower()}", actor, day=d,
               conn=conn)
        _audit(conn, "notified", actor, case_id=c.case_id, pupil_id=c.pupil_id, who=who)
    activity_log.record("exclusions.notified", target=c.admission_no, principal=actor,
                        case=c.case_id, who=who)
    return get(c.case_id)


def governors_required(c: Case) -> str | None:
    """"must", "on request" or None: whether the governors meet to consider
    reinstatement."""
    if not c.is_formal or not c.counts:
        return None
    if c.case_type == PERMANENT:
        return "must"
    n = term_days(c.pupil_id, c.start_date)
    if n > GOVERNORS_MUST_ABOVE:
        return "must"
    if n > GOVERNORS_ON_REQUEST_ABOVE:
        return "on request"
    return None


def record_governors(case_id: int, *, decision: str, meeting_date: str | None = None,
                     actor: Principal, note: str | None = None) -> Case:
    """The governing board's decision: Upheld or Reinstated. Reinstating
    overturns the case. A permanent exclusion that is upheld waits for the
    review window (status InProgress)."""
    c = get(case_id)
    _require_editor(actor, "governors", c.admission_no)
    problems: list[str] = []
    dec = _choice(decision, GOVERNOR_DECISIONS, "Decision", problems, None)
    if not dec:
        problems.append("Choose Upheld or Reinstated")
    d = _date(meeting_date, "Meeting date", problems) or _today().isoformat()
    if d > _today().isoformat():
        problems.append("Record the decision once the meeting has happened")
    if not c.is_formal:
        problems.append("Only a suspension or permanent exclusion goes to the governors")
    if c.off_roll_date:
        problems.append("The pupil is already off roll")
    if c.status == "Overturned" and c.governors_decision != "Reinstated":
        problems.append("The case has been withdrawn")
    if problems:
        raise ValidationError(problems)
    status = "Overturned" if dec == "Reinstated" else (
        "InProgress" if c.case_type == PERMANENT else c.status)
    appeal = f"Reinstated by the governing board on {d}" if dec == "Reinstated" else \
        c.appeal_decision
    with database.connect() as conn:
        conn.execute("UPDATE exclusion_cases SET governors_meeting_date = ?, "
                     "governors_decision = ?, status = ?, appeal_decision = ?, "
                     "updated_by = ?, updated_at = datetime('now') WHERE case_id = ?",
                     (d, dec, status, appeal, actor.username, c.case_id))
        _event(c, "Governors decision", f"Governing board: {dec.lower()}"
               + (f". {note.strip()}" if note and note.strip() else ""), actor, outcome=dec,
               day=d, conn=conn)
        _audit(conn, "governors", actor, case_id=c.case_id, pupil_id=c.pupil_id, decision=dec)
    activity_log.record("exclusions.governors", target=c.admission_no, principal=actor,
                        case=c.case_id, decision=dec)
    return get(c.case_id)


def review_deadline(c: Case) -> _dt.date | None:
    """Last day the parents can ask for an independent review."""
    if c.case_type != PERMANENT or c.governors_decision != "Upheld" or \
            not c.governors_meeting_date:
        return None
    return school_days_after(c.governors_meeting_date, REVIEW_WITHIN)


def record_review(case_id: int, *, actor: Principal, requested_date: str | None = None,
                  review_date: str | None = None, outcome: str | None = None,
                  note: str | None = None) -> Case:
    """An independent review of a permanent exclusion: when it was asked for,
    and (later) the panel's date and outcome. Quash or Recommend reconsider
    send it back to the governors."""
    c = get(case_id)
    _require_editor(actor, "review", c.admission_no)
    problems: list[str] = []
    if c.case_type != PERMANENT or c.governors_decision != "Upheld":
        problems.append("Only a permanent exclusion the governors have upheld can be reviewed")
    if c.off_roll_date:
        problems.append("The pupil is already off roll")
    req = _date(requested_date, "Requested", problems) or c.review_requested_date or \
        _today().isoformat()
    rdate = _date(review_date, "Review date", problems)
    out = _choice(outcome, REVIEW_OUTCOMES, "Outcome", problems, None)
    if out and not rdate:
        rdate = _today().isoformat()
    if rdate and rdate < req:
        problems.append("The review can't be before it was asked for")
    if problems:
        raise ValidationError(problems)
    status, appeal = "Appealed", f"Independent review requested on {req}"
    governors = c.governors_decision
    if out:
        appeal = f"Independent review panel ({rdate}): {out.lower()}"
        if out == "Upheld":
            status = "InProgress"
        else:   # the governors must reconsider
            governors = None
    with database.connect() as conn:
        conn.execute("UPDATE exclusion_cases SET review_requested_date = ?, review_date = ?, "
                     "review_outcome = ?, status = ?, appeal_decision = ?, "
                     "governors_decision = ?, updated_by = ?, updated_at = datetime('now') "
                     "WHERE case_id = ?",
                     (req, rdate, out, status, appeal, governors, actor.username, c.case_id))
        _event(c, "Appeal decision" if out else "Appeal lodged",
               appeal + (f". {note.strip()}" if note and note.strip() else ""), actor,
               outcome=out, day=rdate or req, conn=conn)
        _audit(conn, "review", actor, case_id=c.case_id, pupil_id=c.pupil_id, outcome=out)
    activity_log.record("exclusions.review", target=c.admission_no, principal=actor,
                        case=c.case_id, outcome=out or "requested")
    return get(c.case_id)


def off_roll_problems(c: Case, today: _dt.date | None = None) -> list[str]:
    day = today or _today()
    out: list[str] = []
    if c.case_type != PERMANENT:
        out.append("Only a permanent exclusion takes a pupil off roll")
    elif c.off_roll_date:
        out.append("The pupil is already off roll")
    elif c.status == "Overturned":
        out.append("The exclusion has been withdrawn or the pupil reinstated")
    elif c.governors_decision != "Upheld":
        out.append("The governors must consider it and uphold it first")
    elif c.review_requested_date and c.review_outcome != "Upheld":
        out.append("An independent review has been asked for - wait for its outcome")
    elif not c.review_requested_date:
        due = review_deadline(c)
        if due and day <= due:
            out.append(f"The family can ask for an independent review until {due} - the "
                       "pupil stays on roll until then")
    return out


def remove_from_roll(case_id: int, *, actor: Principal, leaving_date: str | None = None,
                     notes: str | None = None) -> Case:
    """Take a permanently excluded pupil off roll (Enrolment & Leavers,
    reason "Permanent exclusion") once the steps are done."""
    from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
    c = get(case_id)
    _require_editor(actor, "off_roll", c.admission_no)
    problems = off_roll_problems(c)
    if problems:
        raise ValidationError(problems)
    when = leaving_date or _today().isoformat()
    EN.record_leaver(c.pupil_id, leaving_date=when, reason=EN.EXCLUSION, actor=actor,
                     details={"notes": (notes or f"Permanent exclusion, case #{c.case_id}")})
    with database.connect() as conn:
        conn.execute("UPDATE exclusion_cases SET off_roll_date = ?, status = 'Closed', "
                     "updated_by = ?, updated_at = datetime('now') WHERE case_id = ?",
                     (when, actor.username, c.case_id))
        _event(c, "Decision", f"Taken off roll on {when}", actor, day=when, conn=conn)
        _audit(conn, "off_roll", actor, case_id=c.case_id, pupil_id=c.pupil_id)
    activity_log.record("exclusions.off_roll", target=c.admission_no, principal=actor,
                        case=c.case_id)
    return get(c.case_id)


def deadlines(case_id: int | Case, today: _dt.date | None = None) -> list[dict[str, Any]]:
    """The steps for a case: {'step', 'due', 'done', 'overdue', 'note'}."""
    c = case_id if isinstance(case_id, Case) else get(case_id)
    day = today or _today()
    if not c.is_formal or not c.counts or c.off_roll_date:
        return []
    out: list[dict[str, Any]] = []

    def add(step: str, due: _dt.date | str | None, done: str | None, note: str = "") -> None:
        d = due if isinstance(due, _dt.date) or due is None else _dt.date.fromisoformat(due)
        out.append({"step": step, "due": d.isoformat() if d else None, "done": done,
                    "overdue": bool(d and not done and d < day), "note": note})

    start = c.start_date
    notified = (c.parents_notified_at or "")[:10] or None
    add("Tell the family (without delay)", start, notified,
        "Reason, dates, their right to make representations to the governors")
    add("Tell the governing board", start, c.governors_notified_at)
    add("Tell the local authority", start, c.la_notified_at)
    long_out = c.case_type == PERMANENT or int(c.days or 0) >= PROVISION_FROM_DAY
    if long_out:
        add(f"Education from day {PROVISION_FROM_DAY}",
            nth_school_day(start, PROVISION_FROM_DAY), c.provision_from,
            "The local authority arranges it" if c.case_type == PERMANENT
            else "The school arranges suitable full-time education")
    need = governors_required(c)
    if need:
        base = notified or start
        add("Governors consider reinstatement" + (" (if the parents ask)"
                                                  if need == "on request" else ""),
            school_days_after(base, GOVERNORS_WITHIN), c.governors_meeting_date
            if c.governors_decision else None,
            f"Within {GOVERNORS_WITHIN} school days of the notice")
    if c.case_type == SUSPENSION and c.end_date:
        back = c.return_date or school_days_after(c.end_date, 1).isoformat()
        add("Reintegration meeting", back, c.reintegration_date,
            "Plan the return with the pupil and family")
    due = review_deadline(c)
    if due:
        add("Independent review window closes", due, c.review_requested_date or (
            day.isoformat() if day > due else None),
            "Then take the pupil off roll (if no review was asked for)")
    return out


def due(*, today: _dt.date | None = None, year_group: int | str | None = None
        ) -> list[tuple[Case, dict[str, Any]]]:
    """Outstanding steps across the school, soonest first."""
    rows = []
    for c in list_cases(formal_only=True, year_group=year_group):
        if c.status == "Closed" and c.case_type == SUSPENSION and c.reintegration_date:
            continue
        for d in deadlines(c, today):
            if not d["done"]:
                rows.append((c, d))
    return sorted(rows, key=lambda x: (x[1]["due"] or "9999", x[0].case_id))


def ready_for_off_roll(today: _dt.date | None = None) -> list[Case]:
    return [c for c in list_cases(case_type=PERMANENT)
            if not off_roll_problems(c, today)]


# ── Attendance ───────────────────────────────────────────────────────

def mark_attendance(case_id: int, *, actor: Principal, until: str | None = None
                    ) -> dict[str, int]:
    """Put E (out, no education arranged) or B (off-site education from the
    "education from" date) on the AM and PM registers for the school days the
    pupil is out, up to today. Marks already there (other than N) are kept."""
    c = get(case_id)
    _require_editor(actor, "attendance", c.admission_no)
    if not c.is_formal or not c.counts:
        raise ValidationError(["Only a suspension or permanent exclusion that stands is "
                               "marked on the register"])
    AT = _AT()
    last = min(x for x in (c.end_date, until, _today().isoformat(),
                           c.off_roll_date) if x)
    if last < c.start_date:
        raise ValidationError(["Nothing to mark yet - the case starts on " + c.start_date])
    ranges = [(c.start_date, last, "E")]
    if c.provision_from and c.provision_from <= last:
        ranges = [(c.start_date, (_dt.date.fromisoformat(c.provision_from) -
                                  _dt.timedelta(days=1)).isoformat(), "E"),
                  (c.provision_from, last, "B")]
    saved = skipped = 0
    for s, e, code in ranges:
        if e < s:
            continue
        a, b = AT.record_range(c.pupil_id, s, e, code, actor=actor,
                               notes=f"Exclusions case #{c.case_id}")
        saved, skipped = saved + a, skipped + b
    with database.connect() as conn:
        _audit(conn, "attendance", actor, case_id=c.case_id, pupil_id=c.pupil_id,
               saved=saved, skipped=skipped)
    activity_log.record("exclusions.attendance", target=c.admission_no, principal=actor,
                        case=c.case_id, saved=saved)
    return {"saved": saved, "skipped": skipped}


# ── Summaries ────────────────────────────────────────────────────────

def case_summary(pupil_id: int, *, academic_year: str | None = None) -> dict[str, Any]:
    """One pupil: their cases, suspension days this year and what's left."""
    year = academic_year or current_year()
    cases = list_cases(pupil_id=pupil_id)
    days = suspension_days(pupil_id, academic_year=year)
    this_year = [c for c in cases if c.academic_year == year]
    return {"cases": cases, "this_year": this_year, "suspension_days": days,
            "days_left": max(0, MAX_SUSPENSION_DAYS - days),
            "suspensions": sum(1 for c in this_year if c.case_type == SUSPENSION and c.counts),
            "permanent": next((c for c in cases if c.case_type == PERMANENT and c.counts),
                              None),
            "open": [c for c in cases if c.status in ("Open", "InProgress", "Appealed")]}


def cohort_summary(*, year_group: int | str | None = None,
                   academic_year: str | None = None) -> dict[str, Any]:
    """The old cohort summary (total, open, by_status/type/severity,
    total_days) plus suspensions, permanent exclusions and pupils."""
    rows = list_cases(year_group=year_group, academic_year=academic_year)
    standing = [c for c in rows if c.counts]
    return {"total": len(rows),
            "open": sum(1 for c in rows if c.status in ("Open", "InProgress", "Appealed")),
            "by_status": dict(Counter(c.status for c in rows)),
            "by_type": dict(Counter(c.case_type for c in rows)),
            "by_severity": dict(Counter(c.severity for c in rows)),
            "total_days": sum(int(c.days or 0) for c in standing),
            "suspensions": sum(1 for c in standing if c.case_type == SUSPENSION),
            "permanent": sum(1 for c in standing if c.case_type == PERMANENT),
            "pupils": len({c.pupil_id for c in standing if c.is_formal})}


_GROUPS = {"type": lambda c: c.case_type,
           "reason": lambda c: c.reason_category or "(not given)",
           "year": lambda c: f"Year {c.pupil_year}",
           "severity": lambda c: c.severity,
           "month": lambda c: c.start_date[:7]}


def analysis(*, by: str = "type", year_group: int | str | None = None,
             academic_year: str | None = None) -> list[dict[str, Any]]:
    """Cases that stand, grouped: {'group', 'cases', 'days', 'pupils'}."""
    if by not in _GROUPS:
        raise ValidationError([f"Group by one of {', '.join(_GROUPS)}"])
    groups: dict[str, list[Case]] = {}
    for c in list_cases(year_group=year_group, academic_year=academic_year):
        if c.counts:
            groups.setdefault(_GROUPS[by](c), []).append(c)
    return sorted(({"group": g, "cases": len(v), "days": sum(int(c.days or 0) for c in v),
                    "pupils": len({c.pupil_id for c in v})} for g, v in groups.items()),
                  key=lambda x: (-x["cases"], x["group"]))


def concerns(*, year_group: int | str | None = None, today: _dt.date | None = None
             ) -> list[dict[str, Any]]:
    """Pupils suspended this school year (fed into the behaviour concerns)."""
    year = current_year(today) if today else current_year()
    out: dict[int, dict[str, Any]] = {}
    for c in list_cases(year_group=year_group, academic_year=year, formal_only=True):
        if not c.counts:
            continue
        x = out.setdefault(c.pupil_id, {"pupil_id": c.pupil_id, "pupil_name": c.pupil_name,
                                        "admission_no": c.admission_no,
                                        "year_group": c.pupil_year, "cases": 0, "days": 0,
                                        "permanent": False})
        x["cases"] += 1
        x["days"] += int(c.days or 0)
        x["permanent"] = x["permanent"] or c.case_type == PERMANENT
    for x in out.values():
        x["reason"] = ("permanently excluded" if x["permanent"] else
                       f"suspended {x['cases']} time(s), {x['days']} school day(s) this year")
    return sorted(out.values(), key=lambda x: (not x["permanent"], -x["days"]))


# ── Families ─────────────────────────────────────────────────────────

def _notice_text(c: Case, first: str) -> tuple[str, str, str]:
    if c.case_type == PERMANENT:
        intro = (f"The headteacher has decided to permanently exclude {first} from "
                 f"{c.start_date}.")
        rights = ("The governing board must consider whether {first} should be reinstated, "
                  "within 15 school days. You may make representations to them and attend "
                  "the meeting. From the sixth school day the local authority will arrange "
                  "full-time education.")
    else:
        intro = f"The headteacher has decided to suspend {first} for {c.days or 'the'} " \
                f"school day(s): {c.period}."
        rights = ("You may make representations about this decision to the governing board."
                  + (" From the sixth school day the school will arrange full-time "
                     "education elsewhere, and will tell you where." if int(c.days or 0)
                     >= PROVISION_FROM_DAY else ""))
    details = f"Reason: {c.reason}"
    if c.return_date:
        details += f"\nReturn to school: {c.return_date}"
    details += ("\n\nDuring the first five school days you must make sure "
                f"{first} is not in a public place during school hours without a good "
                "reason. Work will be set for each day.")
    return intro, details, rights.format(first=first)


def notify_parents(case_id: int, *, actor: Principal, note: str | None = None
                   ) -> dict[str, Any]:
    """E-mail the formal notice to the pupil's contacts with parental
    responsibility; records it on the case and in its events.
    Returns {'message_id', 'emails', 'no_email'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    c = get(case_id)
    _require_editor(actor, "notify", c.admission_no)
    if not c.is_formal or not c.counts:
        raise ValidationError(["Only a suspension or permanent exclusion that stands has a "
                               "notice"])
    p = P.get_pupil(c.pupil_id)
    to = [(x.email, x.full_name) for x in C.emailable_for_pupils([c.pupil_id]).get(
        c.pupil_id, []) if x.email and x.parental_responsibility]
    if not to:
        return {"message_id": None, "emails": 0, "no_email": [p]}
    first = p.preferred_name or p.legal_first_name
    intro, details, closing = _notice_text(c, first)
    if note and note.strip():
        details += f"\n\n{note.strip()}"
    template = email_templates.load_template("exclusion_notice")
    letters = []
    for address, name in to:
        subject, body = template.render({
            "recipient_name": name, "pupil_name": p.display_name,
            "headline": "Permanent exclusion" if c.case_type == PERMANENT else "Suspension",
            "intro": intro, "details": details, "closing": closing,
            "sender_name": c.decision_maker or BH._staff_name(actor)})
        letters.append((address, name, subject, body))
    mid = E.save_prepared("exclusion_notice", "Suspension / exclusion notice",
                          "Suspension / exclusion notice", "(one notice per contact)", letters,
                          actor=actor)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with database.connect() as conn:
        conn.execute("UPDATE exclusion_cases SET parents_notified_at = ? WHERE case_id = ?",
                     (now, c.case_id))
        _event(c, "Letter sent", f"Notice e-mailed to {len(letters)} contact(s)", actor,
               conn=conn)
        _audit(conn, "notify", actor, case_id=c.case_id, pupil_id=c.pupil_id,
               emails=len(letters))
    activity_log.record("exclusions.notify", target=c.admission_no, principal=actor,
                        case=c.case_id, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "no_email": []}


def record_parents_told(case_id: int, *, actor: Principal, how: str = "Phone call",
                        day: str | None = None) -> Case:
    """The family was told another way (phone, letter, in person)."""
    c = get(case_id)
    _require_editor(actor, "notify", c.admission_no)
    problems: list[str] = []
    d = _date(day, "Date", problems) or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE exclusion_cases SET parents_notified_at = ? WHERE case_id = ?",
                     (d, c.case_id))
        _event(c, how if how in EVENT_TYPES else "Other", "Family told of the decision",
               actor, day=d, conn=conn)
        _audit(conn, "notify", actor, case_id=c.case_id, pupil_id=c.pupil_id, how=how)
    activity_log.record("exclusions.notify", target=c.admission_no, principal=actor,
                        case=c.case_id, how=how)
    return get(c.case_id)


def for_family(pupil_id: int, academic_year: str | None = None) -> list[dict[str, Any]]:
    """What the portal shows: this year's suspensions / permanent exclusion
    (dates, reason, return date, reintegration meeting, decisions)."""
    rows = [c for c in list_cases(pupil_id=pupil_id, formal_only=True,
                                  academic_year=academic_year or current_year())
            if c.counts and c.parents_notified_at]
    return [{"type": c.case_type, "period": c.period, "days": c.days, "reason": c.reason,
             "return_date": c.return_date, "reintegration_date": c.reintegration_date,
             "governors_decision": c.governors_decision, "status": c.status}
            for c in sorted(rows, key=lambda c: c.start_date)]


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_cases(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "admission_no", "pupil", "year", "form", "type", "severity",
                    "incident", "start", "end", "days", "reason_category", "reason",
                    "decision_maker", "status", "appeal_decision", "return", "parents_told",
                    "governors_told", "la_told", "education_from", "reintegration",
                    "governors_decision", "review_outcome", "off_roll"])
        for c in rows:
            w.writerow([c.case_id, _safe(c.admission_no), _safe(c.pupil_name), c.pupil_year,
                        _safe(c.form_group), c.case_type, c.severity, c.incident_date or "",
                        c.start_date, c.end_date or "", c.days if c.days is not None else "",
                        c.reason_category or "", _safe(c.reason), _safe(c.decision_maker),
                        c.status, _safe(c.appeal_decision), c.return_date or "",
                        (c.parents_notified_at or "")[:10], c.governors_notified_at or "",
                        c.la_notified_at or "", c.provision_from or "",
                        c.reintegration_date or "", c.governors_decision or "",
                        c.review_outcome or "", c.off_roll_date or ""])
    activity_log.record("exclusions.export", principal=actor, rows=len(rows))
    return len(rows)
