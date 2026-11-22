"""Interventions: extra support for a pupil, tracked to an outcome.

Kept from the old system: one intervention per pupil (optionally in a
subject) with its type (Catch-up, Mentoring, Tutoring, In-class support,
Small group, Pastoral, Behaviour, Attendance, Other), goal, start / end
date, who leads it, where and how often, baseline / target / current grade,
outcome and notes; the status workflow Planned / Active / Paused / Complete
/ Cancelled with an outcome required to close one; review checkpoints
(date, reviewer, attendance %, on track, progress notes, next action); the
per-intervention summary and the cohort summary (by status, type, outcome).

New:

* **Grades come from the school's data.** A blank baseline / target /
  current grade is filled in from the pupil's target grade and their newest
  assessment-point (or gradebook) grade in that subject; "Refresh grade"
  updates the current grade, and closing an intervention does it too.
* **Sessions.** Each session is registered (Present / Late / Absent /
  Cancelled); a review's attendance % defaults to the sessions so far.
* **Who needs one?** :func:`suggestions` lists pupils below or well below
  target in a subject, with a Progress 8 score of -0.5 or lower, or
  persistently absent - leaving out anyone already in an open intervention
  for it.
* **Groups.** :func:`create_many` starts the same intervention (a named
  programme, e.g. "Y11 maths Tuesday P6") for several pupils at once.
* **Rules.** The pupil must be on roll; no second open intervention of the
  same type in the same subject; the end date can't be before the start;
  moves follow the workflow (a closed one can only be reopened by the
  intervention lead for the school, :data:`INTERVENTION_EDITORS`); sessions
  and reviews can't be in the future or before the start.
* **Who.** Any member of staff can start one (they lead it unless they name
  someone else). The lead and the intervention lead can update it, register
  sessions, add reviews and change its status; only the intervention lead
  deletes. Every change is kept in ``intervention_audit`` and the activity
  log (ids only).
* **Impact**: per type (or subject) - how many, closed, successful, average
  grade change and session attendance. CSV export; the pupil profile shows
  a pupil's interventions.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.curriculum.domain import subjects as S
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    INTERVENTION_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

INTERVENTION_TYPES: tuple[str, ...] = (
    "Catch-up", "Mentoring", "Tutoring", "In-class support", "Small group", "Pastoral",
    "Behaviour", "Attendance", "Other")
DEFAULT_TYPE = "Catch-up"
INTERVENTION_STATUSES: tuple[str, ...] = ("Planned", "Active", "Paused", "Complete",
                                          "Cancelled")
DEFAULT_STATUS = "Planned"
OPEN_STATUSES = frozenset({"Planned", "Active", "Paused"})
CLOSED_STATUSES = frozenset({"Complete", "Cancelled"})
#: Allowed moves (a closed one is reopened by an editor only).
MOVES: dict[str, frozenset[str]] = {
    "Planned": frozenset({"Active", "Cancelled"}),
    "Active": frozenset({"Paused", "Complete", "Cancelled"}),
    "Paused": frozenset({"Active", "Complete", "Cancelled"}),
    "Complete": frozenset({"Active"}),
    "Cancelled": frozenset({"Planned", "Active"}),
}
FREQUENCIES: tuple[str, ...] = ("Daily", "Twice weekly", "Weekly", "Fortnightly", "Monthly",
                                "One-off", "Other")
DEFAULT_FREQUENCY = "Weekly"
OUTCOMES: tuple[str, ...] = ("Successful", "Partial", "Unsuccessful", "Pending")
ATTENDANCE: tuple[str, ...] = ("Present", "Late", "Absent", "Cancelled")
#: Progress 8 at or below this suggests an intervention.
P8_CONCERN = -0.5

FIELDS = ("pupil_id", "subject_id", "intervention_type", "programme", "reason", "goal",
          "start_date", "end_date", "status", "led_by", "lead_username", "location",
          "frequency", "baseline_grade", "target_grade", "current_grade", "outcome", "notes")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interventions (
    intervention_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    subject_id        INTEGER REFERENCES subjects (subject_id),
    intervention_type TEXT NOT NULL DEFAULT 'Catch-up',
    programme         TEXT,
    reason            TEXT,
    goal              TEXT,
    start_date        TEXT NOT NULL,
    end_date          TEXT,
    status            TEXT NOT NULL DEFAULT 'Planned' CHECK (status IN
                      ('Planned', 'Active', 'Paused', 'Complete', 'Cancelled')),
    led_by            TEXT,
    lead_username     TEXT,
    location          TEXT,
    frequency         TEXT NOT NULL DEFAULT 'Weekly',
    baseline_grade    TEXT,
    target_grade      TEXT,
    current_grade     TEXT,
    outcome           TEXT,
    notes             TEXT,
    created_by        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_interventions_pupil ON interventions (pupil_id, status);
CREATE TABLE IF NOT EXISTS intervention_reviews (
    review_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    intervention_id  INTEGER NOT NULL REFERENCES interventions (intervention_id)
                     ON DELETE CASCADE,
    review_date      TEXT NOT NULL,
    reviewer         TEXT,
    attendance_pct   REAL CHECK (attendance_pct IS NULL OR attendance_pct BETWEEN 0 AND 100),
    on_track         INTEGER NOT NULL DEFAULT 1,
    progress_notes   TEXT,
    next_action      TEXT,
    created_by       TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS intervention_sessions (
    session_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    intervention_id  INTEGER NOT NULL REFERENCES interventions (intervention_id)
                     ON DELETE CASCADE,
    session_date     TEXT NOT NULL,
    attendance       TEXT NOT NULL CHECK (attendance IN ('Present', 'Late', 'Absent',
                                                         'Cancelled')),
    notes            TEXT,
    recorded_by      TEXT,
    recorded_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (intervention_id, session_date)
);
CREATE TABLE IF NOT EXISTS intervention_audit (
    audit_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    intervention_id  INTEGER,
    pupil_id         INTEGER,
    action           TEXT NOT NULL,
    detail           TEXT,
    actor            TEXT NOT NULL,
    at               TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("interventions", _SCHEMA)


@dataclass(frozen=True)
class Intervention:
    intervention_id: int
    pupil_id: int
    subject_id: int | None
    intervention_type: str
    programme: str | None
    reason: str | None
    goal: str | None
    start_date: str
    end_date: str | None
    status: str
    led_by: str | None
    lead_username: str | None
    location: str | None
    frequency: str
    baseline_grade: str | None
    target_grade: str | None
    current_grade: str | None
    outcome: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    subject_code: str | None = None
    subject_name: str | None = None
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    @property
    def grade_change(self) -> float | None:
        return grade_change(self.baseline_grade, self.current_grade)


@dataclass(frozen=True)
class Review:
    review_id: int
    intervention_id: int
    review_date: str
    reviewer: str | None
    attendance_pct: float | None
    on_track: bool
    progress_notes: str | None
    next_action: str | None
    created_by: str | None
    created_at: str


@dataclass(frozen=True)
class Session:
    session_id: int
    intervention_id: int
    session_date: str
    attendance: str
    notes: str | None
    recorded_by: str | None
    recorded_at: str


_SELECT = """
SELECT i.*, s.code AS subject_code, s.name AS subject_name, p.legal_last_name,
       p.legal_first_name, p.preferred_name, p.admission_no, p.year_group AS pupil_year
FROM interventions i JOIN pupils p ON p.pupil_id = i.pupil_id
LEFT JOIN subjects s ON s.subject_id = i.subject_id
"""
_BASE = tuple(f for f in Intervention.__dataclass_fields__ if f not in (
    "subject_code", "subject_name", "pupil_name", "admission_no", "pupil_year"))


def _row(r) -> Intervention:
    return Intervention(**{k: r[k] for k in _BASE}, subject_code=r["subject_code"],
                        subject_name=r["subject_name"],
                        pupil_name=f"{r['legal_last_name']}, "
                                   f"{r['preferred_name'] or r['legal_first_name']}",
                        admission_no=r["admission_no"], pupil_year=r["pupil_year"])


def _review(r) -> Review:
    d = {k: r[k] for k in Review.__dataclass_fields__}
    d["on_track"] = bool(d["on_track"])
    return Review(**d)


def _session(r) -> Session:
    return Session(**{k: r[k] for k in Session.__dataclass_fields__})


# ── Helpers ──────────────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in INTERVENTION_EDITORS


def is_lead(actor: Principal, iv: Intervention) -> bool:
    return bool(actor.username) and (iv.lead_username or "").lower() == \
        (actor.username or "").lower()


def can_manage(actor: Principal, iv: Intervention) -> bool:
    """Update, register sessions, review and move it: its lead, or an editor."""
    return is_editor(actor) or is_lead(actor, iv)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        activity_log.record(f"interventions.{action}", target=target, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only staff can work with interventions.")


def _require_manage(actor: Principal, iv: Intervention, action: str) -> None:
    if not can_manage(actor, iv):
        activity_log.record(f"interventions.{action}", target=iv.admission_no,
                            outcome="denied", principal=actor)
        raise PermissionDenied("Only the member of staff leading this intervention or the "
                               "intervention lead can change it.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        activity_log.record(f"interventions.{action}", target=target, outcome="denied",
                            principal=actor)
        raise PermissionDenied("Only the intervention lead can do that.")


def _audit(conn, action: str, actor: Principal, intervention_id: int | None,
           pupil_id: int | None, **detail: Any) -> None:
    conn.execute("INSERT INTO intervention_audit (intervention_id, pupil_id, action, detail, "
                 "actor) VALUES (?, ?, ?, ?, ?)",
                 (intervention_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(intervention_id: int | None = None, *, pupil_id: int | None = None,
            limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM intervention_audit", [], []
    if intervention_id is not None:
        where.append("intervention_id = ?")
        params.append(int(intervention_id))
    if pupil_id is not None:
        where.append("pupil_id = ?")
        params.append(int(pupil_id))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "intervention_id": r["intervention_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


def _date(value: Any, label: str, problems: list[str], *, required: bool = False
          ) -> str | None:
    if value in (None, ""):
        if required:
            problems.append(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None = None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
    return hit


def _text(value: Any, limit: int = 1000) -> str | None:
    t = str(value or "").strip()
    return t[:limit] or None


def _grade(value: Any, label: str, problems: list[str]) -> str | None:
    g = str(value or "").strip()
    if not g:
        return None
    if len(g) > 12:
        problems.append(f"{label} is too long")
        return None
    return g


def _subject(ref: Any) -> S.Subject | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).isdigit():
        try:
            return S.get(int(ref))
        except Exception:  # noqa: BLE001 - shown as a validation problem
            return None
    return S.get_by_code(str(ref).strip())


def _staff() -> list[dict]:
    from education_system.systems.secondary.infrastructure.authentication import accounts
    try:
        return accounts.staff_logins()
    except Exception:  # noqa: BLE001 - the login list is a convenience
        return []


def staff_names() -> list[str]:
    """"Display name (username)" for picking a lead."""
    return [f"{s['display_name']} ({s['username']})" for s in _staff()]


def _lead(value: Any, actor: Principal | None = None) -> tuple[str | None, str | None]:
    """(led_by text, lead_username) from a typed name, username or the
    "Name (username)" pick-list form. The person signed in always matches
    their own username."""
    text = _text(value, 120)
    if not text:
        return None, None
    key = text.lower()
    if key.endswith(")") and "(" in key:
        key = key[key.rindex("(") + 1:-1].strip()
    for s in _staff():
        if key in (s["username"].lower(), (s["display_name"] or "").lower()):
            return s["display_name"] or s["username"], s["username"]
    if actor is not None and actor.username and key == actor.username.lower():
        return actor.username, actor.username
    return text, None


# ── Grades from the school's data ────────────────────────────────────

def _numeric(grade: str | None) -> tuple[str, float] | None:
    """(scale, value) for comparing two grades."""
    from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    if not grade:
        return None
    g = grade.strip()
    v = MX.grade_value(g)
    if v is not None:
        return "GCSE 9-1", v
    scale = TGR.scale_of(g)
    r = TGR.rank(g) if scale else None
    return (scale, float(r)) if scale and r is not None else None


def grade_change(before: str | None, after: str | None) -> float | None:
    """Steps up (+) or down (-) on the same scale; None if not comparable."""
    a, b = _numeric(before), _numeric(after)
    if a is None or b is None or a[0] != b[0]:
        return None
    return round(b[1] - a[1], 1)


def latest_grades(pupil_id: int, subject_id: int) -> dict[str, str | None]:
    """{'target', 'current', 'from'} for a pupil in a subject."""
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    rows = TGR.progress(pupil_id=pupil_id, subject_id=subject_id)
    if rows:
        r = rows[0]
        return {"target": r["target"].target_grade, "current": r["current"], "from": r["from"]}
    cur = TGR._current_grades(pupil_id).get((int(pupil_id), int(subject_id)))
    return {"target": None, "current": cur[0] if cur else None, "from": cur[1] if cur else None}


# ── Reading ──────────────────────────────────────────────────────────

def get(intervention_id: int) -> Intervention:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE i.intervention_id = ?",
                         (int(intervention_id),)).fetchone()
    if r is None:
        raise NotFound(f"No intervention #{intervention_id}")
    return _row(r)


def list_interventions(*, year_group: int | str | None = None, status: str | None = None,
                       intervention_type: str | None = None, pupil_id: int | None = None,
                       subject_id: int | None = None, lead: str | None = None,
                       programme: str | None = None, open_only: bool = False
                       ) -> list[Intervention]:
    sql, where, params = _SELECT, [], []
    for col, val in (("p.year_group", year_group), ("i.status", status),
                     ("i.intervention_type", intervention_type), ("i.pupil_id", pupil_id),
                     ("i.subject_id", subject_id), ("i.programme", programme)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(int(val) if col in ("p.year_group", "i.pupil_id", "i.subject_id")
                          else val)
    if lead:
        where.append("lower(i.lead_username) = ?")
        params.append(lead.lower())
    if open_only:
        where.append("i.status IN ('Planned', 'Active', 'Paused')")
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(
            sql + " ORDER BY CASE i.status WHEN 'Active' THEN 0 WHEN 'Planned' THEN 1 WHEN "
                  "'Paused' THEN 2 ELSE 3 END, i.start_date DESC, i.intervention_id DESC",
            params)]


def for_pupil(pupil_id: int) -> list[Intervention]:
    return list_interventions(pupil_id=pupil_id)


def programmes() -> list[str]:
    with database.connect() as conn:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT programme FROM interventions WHERE programme IS NOT NULL "
            "ORDER BY programme COLLATE NOCASE")]


# ── Creating and changing ────────────────────────────────────────────

def _clean(data: dict[str, Any], current: Intervention | None, actor: Principal
           ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS or k in ("pupil", "subject")})
    out: dict[str, Any] = {}
    p = None
    ref = merged.get("pupil_id") or merged.get("pupil")
    if ref in (None, ""):
        problems.append("Pupil is required")
    else:
        p = P.get_pupil(int(ref)) if str(ref).isdigit() else P.find_by_reference(str(ref))
        if p is None:
            problems.append(f"No pupil {ref}")
        elif current is None and p.roll_status != "on_roll":
            problems.append(f"{p.display_name} is not on roll")
    out["pupil_id"] = p.pupil_id if p else None
    sref = merged.get("subject_id") if "subject" not in data else data.get("subject")
    if sref in (None, "") and "subject_id" in data:
        sref = data.get("subject_id")
    s = _subject(sref)
    if sref not in (None, "") and s is None:
        problems.append(f"No subject {sref}")
    out["subject_id"] = s.subject_id if s else None
    out["intervention_type"] = _choice(merged.get("intervention_type"), INTERVENTION_TYPES,
                                       "Type", problems, DEFAULT_TYPE)
    out["frequency"] = _choice(merged.get("frequency"), FREQUENCIES, "Frequency", problems,
                               DEFAULT_FREQUENCY)
    out["status"] = _choice(merged.get("status"), INTERVENTION_STATUSES, "Status", problems,
                            DEFAULT_STATUS)
    out["outcome"] = _choice(merged.get("outcome"), OUTCOMES, "Outcome", problems)
    out["start_date"] = _date(merged.get("start_date") or _today().isoformat(), "Start date",
                              problems, required=True)
    out["end_date"] = _date(merged.get("end_date"), "End date", problems)
    if out["start_date"] and out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date cannot be before start date")
    for k, limit in (("programme", 80), ("reason", 300), ("goal", 1000), ("location", 80),
                     ("notes", 2000)):
        out[k] = _text(merged.get(k), limit)
    for k, label in (("baseline_grade", "Baseline grade"), ("target_grade", "Target grade"),
                     ("current_grade", "Current grade")):
        out[k] = _grade(merged.get(k), label, problems)
    if "led_by" in data or current is None:
        led = data.get("led_by") if "led_by" in data else None
        if current is not None and led and str(led).strip() == (current.led_by or ""):
            out["led_by"], out["lead_username"] = current.led_by, current.lead_username
        else:
            out["led_by"], out["lead_username"] = _lead(led, actor) if led else (
                (None, None) if current else _lead(actor.username, actor))
    else:
        out["led_by"], out["lead_username"] = current.led_by, current.lead_username
    if out["status"] in CLOSED_STATUSES and not out["outcome"]:
        problems.append("Outcome is required when the status is Complete or Cancelled")
    if current is None and out["status"] in CLOSED_STATUSES:
        problems.append("A new intervention starts Planned or Active")
    if not problems and out["subject_id"] and out["pupil_id"]:
        g = latest_grades(out["pupil_id"], out["subject_id"])
        if current is None and not out["baseline_grade"]:
            out["baseline_grade"] = g["current"]
        if not out["target_grade"]:
            out["target_grade"] = g["target"]
        if not out["current_grade"]:
            out["current_grade"] = g["current"]
    return out, problems


def _duplicate(conn, c: dict[str, Any], exclude: int | None = None) -> bool:
    if c["status"] not in OPEN_STATUSES:
        return False
    r = conn.execute(
        "SELECT 1 FROM interventions WHERE pupil_id = ? AND intervention_type = ? AND "
        "COALESCE(subject_id, 0) = COALESCE(?, 0) AND status IN ('Planned', 'Active', "
        "'Paused') AND intervention_id != ?",
        (c["pupil_id"], c["intervention_type"], c["subject_id"], exclude or 0)).fetchone()
    return r is not None


def _insert(conn, c: dict[str, Any], actor: Principal) -> int:
    cols = [k for k in FIELDS]
    iid = conn.execute(
        f"INSERT INTO interventions ({', '.join(cols)}, created_by, updated_by) VALUES "
        f"({', '.join('?' * len(cols))}, ?, ?)",
        (*(c[k] for k in cols), actor.username, actor.username)).lastrowid
    _audit(conn, "create", actor, iid, c["pupil_id"], type=c["intervention_type"],
           status=c["status"])
    return iid


def create(data: dict[str, Any], *, actor: Principal) -> Intervention:
    """Start an intervention (the old New)."""
    _require_staff(actor, "create")
    c, problems = _clean(data, None, actor)
    with database.connect() as conn:
        if not problems and _duplicate(conn, c):
            problems.append("This pupil already has an open intervention of that type"
                            + (" in that subject" if c["subject_id"] else ""))
        if problems:
            activity_log.record("interventions.create", outcome="invalid", principal=actor,
                                problems=len(problems))
            raise ValidationError(problems)
        iid = _insert(conn, c, actor)
    iv = get(iid)
    activity_log.record("interventions.create", target=iv.admission_no, principal=actor,
                        type=iv.intervention_type)
    return iv


def create_many(pupil_ids: list[int], data: dict[str, Any], *, actor: Principal
                ) -> dict[str, Any]:
    """The same intervention for several pupils (a group / programme).
    Returns {'created': [Intervention], 'skipped': {admission_no: why}}."""
    _require_staff(actor, "create_many")
    if not pupil_ids:
        raise ValidationError(["Choose at least one pupil"])
    rows, skipped = [], {}
    for pid in dict.fromkeys(int(x) for x in pupil_ids):
        c, problems = _clean({**data, "pupil_id": pid}, None, actor)
        p = P.get_pupil(pid)
        name = p.admission_no if p else str(pid)
        if problems:
            if any(not x.startswith(("No pupil", "Pupil")) and "not on roll" not in x
                   for x in problems):
                raise ValidationError(problems)  # a problem with the details, not the pupil
            skipped[name] = "; ".join(problems)
            continue
        rows.append((name, c))
    created = []
    with database.connect() as conn:
        for name, c in rows:
            if _duplicate(conn, c):
                skipped[name] = "already has an open intervention of that type"
                continue
            created.append(_insert(conn, c, actor))
    activity_log.record("interventions.create_many", principal=actor, created=len(created),
                        skipped=len(skipped))
    return {"created": [get(i) for i in created], "skipped": skipped}


def update(intervention_id: int, changes: dict[str, Any], *, actor: Principal
           ) -> Intervention:
    """Edit an intervention (the old Edit). A status change goes through
    the workflow (:func:`set_status`)."""
    iv = get(intervention_id)
    _require_manage(actor, iv, "update")
    if "status" in changes and changes["status"] not in (None, "", iv.status):
        _check_move(iv, str(changes["status"]), actor)
    if "pupil_id" in changes and int(changes["pupil_id"] or 0) != iv.pupil_id or \
            "pupil" in changes and changes["pupil"] not in (iv.admission_no, iv.pupil_id):
        raise ValidationError(["An intervention can't move to another pupil - start one for "
                               "them instead"])
    c, problems = _clean(changes, iv, actor)
    with database.connect() as conn:
        if not problems and _duplicate(conn, c, iv.intervention_id):
            problems.append("This pupil already has an open intervention of that type"
                            + (" in that subject" if c["subject_id"] else ""))
        if problems:
            activity_log.record("interventions.update", target=iv.admission_no,
                                outcome="invalid", principal=actor, problems=len(problems))
            raise ValidationError(problems)
        changed = [k for k in FIELDS if c[k] != getattr(iv, k)]
        if not changed:
            return iv
        conn.execute(
            "UPDATE interventions SET " + ", ".join(f"{k} = ?" for k in changed)
            + ", updated_by = ?, updated_at = datetime('now') WHERE intervention_id = ?",
            (*(c[k] for k in changed), actor.username, iv.intervention_id))
        _audit(conn, "update", actor, iv.intervention_id, iv.pupil_id, fields=changed)
    activity_log.record("interventions.update", target=iv.admission_no, principal=actor,
                        fields=",".join(changed))
    return get(iv.intervention_id)


def _check_move(iv: Intervention, status: str, actor: Principal) -> str:
    st = next((s for s in INTERVENTION_STATUSES if s.lower() == status.lower()), None)
    if st is None:
        raise ValidationError([f"Status must be one of {', '.join(INTERVENTION_STATUSES)}"])
    if st != iv.status and st not in MOVES[iv.status]:
        raise ValidationError([f"An intervention that is {iv.status} can't be moved to {st}"])
    if iv.status in CLOSED_STATUSES and st in OPEN_STATUSES and not is_editor(actor):
        raise PermissionDenied("Only the intervention lead can reopen a closed intervention.")
    return st


def set_status(intervention_id: int, status: str, *, actor: Principal,
               outcome: str | None = None, notes: str | None = None) -> Intervention:
    """Move it through the workflow (the old Status). Closing needs an
    outcome, sets the end date (today, if none) and refreshes the current
    grade; reopening clears the outcome."""
    iv = get(intervention_id)
    _require_manage(actor, iv, "status")
    st = _check_move(iv, status, actor)
    problems: list[str] = []
    out = _choice(outcome, OUTCOMES, "Outcome", problems)
    if st in CLOSED_STATUSES and not out:
        problems.append("Outcome is required when the status is Complete or Cancelled")
    if problems:
        raise ValidationError(problems)
    fields: dict[str, Any] = {"status": st}
    if st in CLOSED_STATUSES:
        fields["outcome"] = out
        if not iv.end_date:
            fields["end_date"] = max(_today().isoformat(), iv.start_date)
        if iv.subject_id:
            cur = latest_grades(iv.pupil_id, iv.subject_id)["current"]
            if cur:
                fields["current_grade"] = cur
    else:
        fields["outcome"] = None
        if iv.status in CLOSED_STATUSES:
            fields["end_date"] = None
    if notes:
        fields["notes"] = ((iv.notes + "\n") if iv.notes else "") + \
            f"{_today().isoformat()} {st}: {notes.strip()}"
    with database.connect() as conn:
        conn.execute("UPDATE interventions SET " + ", ".join(f"{k} = ?" for k in fields)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE "
                       "intervention_id = ?", (*fields.values(), actor.username,
                                               iv.intervention_id))
        _audit(conn, "status", actor, iv.intervention_id, iv.pupil_id, frm=iv.status, to=st,
               outcome=fields.get("outcome"))
    activity_log.record("interventions.status", target=iv.admission_no, principal=actor,
                        status=st)
    return get(iv.intervention_id)


def refresh_grade(intervention_id: int, *, actor: Principal) -> Intervention:
    """Update the current (and blank target) grade from the school's data."""
    iv = get(intervention_id)
    _require_manage(actor, iv, "refresh_grade")
    if not iv.subject_id:
        raise ValidationError(["This intervention has no subject, so there's no grade"])
    g = latest_grades(iv.pupil_id, iv.subject_id)
    if not g["current"]:
        raise ValidationError([f"{iv.pupil_name} has no assessment-point or gradebook grade "
                               f"in {iv.subject_name} yet"])
    fields = {"current_grade": g["current"]}
    if not iv.target_grade and g["target"]:
        fields["target_grade"] = g["target"]
    with database.connect() as conn:
        conn.execute("UPDATE interventions SET " + ", ".join(f"{k} = ?" for k in fields)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE "
                       "intervention_id = ?", (*fields.values(), actor.username,
                                               iv.intervention_id))
        _audit(conn, "refresh_grade", actor, iv.intervention_id, iv.pupil_id,
               source=g["from"])
    activity_log.record("interventions.refresh_grade", target=iv.admission_no,
                        principal=actor)
    return get(iv.intervention_id)


def delete(intervention_id: int, *, actor: Principal, reason: str | None = None) -> bool:
    iv = get(intervention_id)
    _require_editor(actor, "delete", iv.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM interventions WHERE intervention_id = ?",
                     (iv.intervention_id,))
        _audit(conn, "delete", actor, iv.intervention_id, iv.pupil_id,
               reason=_text(reason, 300), type=iv.intervention_type, status=iv.status)
    activity_log.record("interventions.delete", target=iv.admission_no, principal=actor)
    return True


# ── Sessions ─────────────────────────────────────────────────────────

def sessions(intervention_id: int) -> list[Session]:
    with database.connect() as conn:
        return [_session(r) for r in conn.execute(
            "SELECT * FROM intervention_sessions WHERE intervention_id = ? ORDER BY "
            "session_date DESC", (int(intervention_id),))]


def session_attendance(intervention_id: int) -> dict[str, Any]:
    """Counts by mark and attendance % (Present + Late over sessions that
    ran - cancelled ones don't count)."""
    c = Counter(s.attendance for s in sessions(intervention_id))
    ran = c["Present"] + c["Late"] + c["Absent"]
    return {**{a: c.get(a, 0) for a in ATTENDANCE}, "ran": ran,
            "pct": round(100 * (c["Present"] + c["Late"]) / ran, 1) if ran else None}


def record_session(intervention_id: int, data: dict[str, Any], *, actor: Principal
                   ) -> Session:
    """Register one session (a second mark on the same date replaces it)."""
    iv = get(intervention_id)
    _require_manage(actor, iv, "session")
    problems: list[str] = []
    day = _date(data.get("session_date") or _today().isoformat(), "Session date", problems,
                required=True)
    mark = _choice(data.get("attendance"), ATTENDANCE, "Attendance", problems)
    if mark is None and not problems:
        problems.append("Attendance is required")
    if iv.status not in ("Active", "Paused"):
        problems.append(f"Sessions are registered while an intervention is Active (it's "
                        f"{iv.status})")
    if day and day > _today().isoformat():
        problems.append("A session can't be registered for a future date")
    if day and day < iv.start_date:
        problems.append("That's before the intervention started")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO intervention_sessions (intervention_id, session_date, attendance, "
            "notes, recorded_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT (intervention_id, "
            "session_date) DO UPDATE SET attendance = excluded.attendance, notes = "
            "excluded.notes, recorded_by = excluded.recorded_by, recorded_at = "
            "datetime('now')", (iv.intervention_id, day, mark, _text(data.get("notes"), 500),
                                actor.username))
        _audit(conn, "session", actor, iv.intervention_id, iv.pupil_id, date=day, mark=mark)
        r = conn.execute("SELECT * FROM intervention_sessions WHERE intervention_id = ? AND "
                         "session_date = ?", (iv.intervention_id, day)).fetchone()
    activity_log.record("interventions.session", target=iv.admission_no, principal=actor)
    return _session(r)


def register_programme(programme: str, day: Any, marks: dict[int, str], *, actor: Principal
                       ) -> int:
    """Register a group session: {intervention_id: mark} for one date. All
    or nothing."""
    problems: list[str] = []
    todo = []
    for iid, mark in marks.items():
        if not mark:
            continue
        iv = get(iid)
        if iv.programme != programme:
            problems.append(f"#{iid} isn't in {programme}")
        elif not can_manage(actor, iv):
            problems.append(f"You don't lead {iv.pupil_name}'s intervention")
        todo.append(iid)
    if problems:
        raise ValidationError(problems)
    n = 0
    errors: list[str] = []
    for iid in todo:
        try:
            record_session(iid, {"session_date": day, "attendance": marks[iid]}, actor=actor)
            n += 1
        except ValidationError as e:
            errors.extend(f"{get(iid).pupil_name}: {p}" for p in e.problems)
    if errors:
        raise ValidationError(errors)
    return n


def delete_session(session_id: int, *, actor: Principal) -> bool:
    with database.connect() as conn:
        r = conn.execute("SELECT intervention_id FROM intervention_sessions WHERE "
                         "session_id = ?", (int(session_id),)).fetchone()
    if r is None:
        raise NotFound(f"No session {session_id}")
    iv = get(r[0])
    _require_manage(actor, iv, "session_delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM intervention_sessions WHERE session_id = ?",
                     (int(session_id),))
        _audit(conn, "session_delete", actor, iv.intervention_id, iv.pupil_id)
    activity_log.record("interventions.session_delete", target=iv.admission_no,
                        principal=actor)
    return True


# ── Reviews ──────────────────────────────────────────────────────────

def list_reviews(intervention_id: int) -> list[Review]:
    with database.connect() as conn:
        return [_review(r) for r in conn.execute(
            "SELECT * FROM intervention_reviews WHERE intervention_id = ? ORDER BY "
            "review_date DESC, review_id DESC", (int(intervention_id),))]


def get_review(review_id: int) -> Review:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM intervention_reviews WHERE review_id = ?",
                         (int(review_id),)).fetchone()
    if r is None:
        raise NotFound(f"No review {review_id}")
    return _review(r)


def add_review(intervention_id: int, data: dict[str, Any], *, actor: Principal) -> Review:
    """A review checkpoint (the old Add review). Attendance % defaults to
    the sessions registered so far; reviewer to the person adding it."""
    iv = get(intervention_id)
    _require_manage(actor, iv, "review")
    problems: list[str] = []
    day = _date(data.get("review_date") or _today().isoformat(), "Review date", problems,
                required=True)
    if day and day > _today().isoformat():
        problems.append("A review can't be dated in the future")
    if day and day < iv.start_date:
        problems.append("That's before the intervention started")
    att_raw = data.get("attendance_pct")
    att = None
    if att_raw not in (None, ""):
        try:
            att = float(str(att_raw).strip().rstrip("%"))
            if not 0 <= att <= 100:
                raise ValueError
        except ValueError:
            problems.append("Attendance % must be between 0 and 100")
    else:
        att = session_attendance(iv.intervention_id)["pct"]
    on_track = data.get("on_track", True)
    if isinstance(on_track, str):
        on_track = on_track.strip().lower() in ("1", "y", "yes", "true", "on track")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        rid = conn.execute(
            "INSERT INTO intervention_reviews (intervention_id, review_date, reviewer, "
            "attendance_pct, on_track, progress_notes, next_action, created_by) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?)",
            (iv.intervention_id, day, _text(data.get("reviewer"), 120) or actor.username,
             att, int(bool(on_track)), _text(data.get("progress_notes"), 2000),
             _text(data.get("next_action"), 500), actor.username)).lastrowid
        _audit(conn, "review", actor, iv.intervention_id, iv.pupil_id, on_track=bool(on_track))
    activity_log.record("interventions.review", target=iv.admission_no, principal=actor)
    return get_review(rid)


def delete_review(review_id: int, *, actor: Principal) -> bool:
    rv = get_review(review_id)
    iv = get(rv.intervention_id)
    _require_manage(actor, iv, "review_delete")
    with database.connect() as conn:
        conn.execute("DELETE FROM intervention_reviews WHERE review_id = ?", (rv.review_id,))
        _audit(conn, "review_delete", actor, iv.intervention_id, iv.pupil_id)
    activity_log.record("interventions.review_delete", target=iv.admission_no, principal=actor)
    return True


# ── Summaries ────────────────────────────────────────────────────────

def intervention_summary(intervention_id: int) -> dict[str, Any]:
    """One intervention with its reviews, sessions and how it's going."""
    iv = get(intervention_id)
    reviews = list_reviews(intervention_id)
    atts = [r.attendance_pct for r in reviews if r.attendance_pct is not None]
    on = sum(1 for r in reviews if r.on_track)
    return {"intervention": iv, "reviews": reviews, "review_count": len(reviews),
            "avg_attendance": round(sum(atts) / len(atts), 2) if atts else None,
            "on_track": on, "off_track": len(reviews) - on,
            "sessions": session_attendance(intervention_id),
            "grade_change": iv.grade_change,
            "last_review": reviews[0] if reviews else None}


def cohort_summary(*, year_group: int | str | None = None, **filters: Any) -> dict[str, Any]:
    """The old Summary: totals by status, type and outcome."""
    rows = list_interventions(year_group=year_group, **filters)
    return {"total": len(rows), "open": sum(1 for r in rows if r.is_open),
            "by_status": dict(Counter(r.status for r in rows)),
            "by_type": dict(Counter(r.intervention_type for r in rows)),
            "by_outcome": dict(Counter(r.outcome for r in rows if r.outcome)),
            "pupils": len({r.pupil_id for r in rows})}


def impact(*, by: str = "type", year_group: int | str | None = None,
           start: str | None = None, end: str | None = None) -> list[dict[str, Any]]:
    """Per type (``by='type'``), subject or programme: how many, closed,
    successful (of closed), average grade change (where comparable),
    average session attendance."""
    rows = list_interventions(year_group=year_group)
    if start:
        rows = [r for r in rows if r.start_date >= start]
    if end:
        rows = [r for r in rows if r.start_date <= end]
    key = {"type": lambda r: r.intervention_type,
           "subject": lambda r: r.subject_name or "(no subject)",
           "programme": lambda r: r.programme or "(no group)"}[by]
    groups: dict[str, list[Intervention]] = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    with database.connect() as conn:
        att = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT intervention_id, SUM(attendance IN ('Present', 'Late')), "
            "SUM(attendance != 'Cancelled') FROM intervention_sessions GROUP BY "
            "intervention_id")}
    out = []
    for name, rs in sorted(groups.items()):
        closed = [r for r in rs if r.status == "Complete"]
        changes = [c for c in (r.grade_change for r in rs) if c is not None]
        came = sum(att.get(r.intervention_id, (0, 0))[0] for r in rs)
        ran = sum(att.get(r.intervention_id, (0, 0))[1] for r in rs)
        out.append({
            "group": name, "count": len(rs), "open": sum(1 for r in rs if r.is_open),
            "complete": len(closed),
            "successful": sum(1 for r in closed if r.outcome == "Successful"),
            "success_pct": (round(100 * sum(1 for r in closed if r.outcome == "Successful")
                                  / len(closed), 1) if closed else None),
            "avg_grade_change": round(sum(changes) / len(changes), 2) if changes else None,
            "with_grades": len(changes),
            "attendance_pct": round(100 * came / ran, 1) if ran else None})
    return out


def due_for_review(*, days: int = 28, lead: str | None = None) -> list[dict[str, Any]]:
    """Active interventions with no review in the last *days* days."""
    cutoff = (_today() - _dt.timedelta(days=days)).isoformat()
    out = []
    for iv in list_interventions(status="Active", lead=lead):
        last = list_reviews(iv.intervention_id)
        last_date = last[0].review_date if last else None
        if (last_date or iv.start_date) < cutoff:
            out.append({"intervention": iv, "last_review": last_date})
    return out


# ── Who needs one? ───────────────────────────────────────────────────

def suggestions(*, year_group: int | None = None, include: tuple[str, ...] = (
        "below target", "progress 8", "attendance", "behaviour", "attendance concerns",
        "wellbeing")) -> list[dict[str, Any]]:
    """Pupils the school's data says may need support, not already in an
    open intervention for it: {'pupil', 'subject' (or None), 'reason',
    'type', 'current', 'target'}."""
    from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
    open_ = list_interventions(year_group=year_group, open_only=True)
    covered = {(i.pupil_id, i.subject_id) for i in open_ if i.subject_id}
    covered_type = {(i.pupil_id, i.intervention_type) for i in open_}
    out: list[dict[str, Any]] = []
    if "below target" in include:
        for r in TGR.progress(year_group=year_group):
            if r["status"] not in ("Below", "Well below"):
                continue
            t = r["target"]
            if (t.pupil_id, t.subject_id) in covered:
                continue
            p = P.get_pupil(t.pupil_id)
            if p is None or p.roll_status != "on_roll":
                continue
            out.append({"pupil": p, "subject_id": t.subject_id, "subject": t.subject_code,
                        "reason": f"{r['status']} target in {t.subject_code} "
                                  f"({r['current']} vs {t.target_grade}, {r['from']})",
                        "type": "Catch-up", "current": r["current"],
                        "target": t.target_grade, "severity": 2 if r["status"] ==
                        "Well below" else 1})
    if "progress 8" in include:
        from education_system.systems.secondary.modules.assessment.domain import (
            headline_measures as HM,
        )
        year = HM.current_year()
        for r in HM.list_p8(year_group=year_group, academic_year=year):
            if r.progress_8 is None or r.progress_8 > P8_CONCERN:
                continue
            p = P.get_pupil(r.pupil_id)
            if p is None or (p.pupil_id, "Mentoring") in covered_type:
                continue
            out.append({"pupil": p, "subject_id": None, "subject": None,
                        "reason": f"Progress 8 {r.progress_8:+.2f} ({r.a8_source})",
                        "type": "Mentoring", "current": None, "target": None,
                        "severity": 2 if r.progress_8 <= -1 else 1})
    if "attendance" in include:
        from education_system.systems.secondary.modules.attendance.domain import attendance as AT
        for p, s in AT.persistent_absentees(year_group=year_group):
            if (p.pupil_id, "Attendance") in covered_type:
                continue
            out.append({"pupil": p, "subject_id": None, "subject": None,
                        "reason": f"Attendance {s.attendance_pct}% ({s.band})",
                        "type": "Attendance", "current": None, "target": None,
                        "severity": 2 if s.band == "severe" else 1})
    if "behaviour" in include:
        from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
        for c in BH.concerns(year_group=year_group):
            p = P.get_pupil(c["pupil_id"])
            if p is None or p.roll_status != "on_roll" or \
                    (p.pupil_id, "Behaviour") in covered_type:
                continue
            out.append({"pupil": p, "subject_id": None, "subject": None,
                        "reason": "Behaviour: " + "; ".join(c["reasons"]),
                        "type": "Behaviour", "current": None, "target": None,
                        "severity": c["severity"]})
    if "attendance concerns" in include:
        # Formal attendance cases at stage 3 or later (meeting / plan and beyond).
        from education_system.systems.secondary.modules.attendance.domain import (
            attendance_concerns as AC,
        )
        listed = {x["pupil"].pupil_id for x in out if x["type"] == "Attendance"}
        for c in AC.list_concerns(open_only=True, year_group=year_group):
            if c.stage_no < 3 or c.pupil_id in listed or \
                    (c.pupil_id, "Attendance") in covered_type:
                continue
            p = P.get_pupil(c.pupil_id)
            if p is None or p.roll_status != "on_roll":
                continue
            listed.add(c.pupil_id)
            out.append({"pupil": p, "subject_id": None, "subject": None,
                        "reason": f"Attendance case at '{c.stage}'"
                                  + (f" ({c.attendance_pct:.1f}%)"
                                     if c.attendance_pct is not None else ""),
                        "type": "Attendance", "current": None, "target": None,
                        "severity": 2})
    if "wellbeing" in include:
        # The latest check-in has a rating at or below the low threshold.
        from education_system.systems.secondary.modules.wellbeing.domain import wellbeing as WB
        for pid, rows in WB.low_wellbeing(year_group=year_group).items():
            if (pid, "Pastoral") in covered_type:
                continue
            p = P.get_pupil(pid)
            if p is None or p.roll_status != "on_roll":
                continue
            r = rows[0]
            out.append({"pupil": p, "subject_id": None, "subject": None,
                        "reason": f"Low wellbeing check-in ({r.lowest}/{WB.MAX_RATING} on "
                                  f"{r.checkin_date})",
                        "type": "Pastoral", "current": None, "target": None,
                        "severity": 1})
    return sorted(out, key=lambda x: (-x["severity"], x["pupil"].legal_last_name.lower(),
                                      x["subject"] or ""))


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    rows = list_interventions(**filters)
    with database.connect() as conn:
        att = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT intervention_id, SUM(attendance IN ('Present', 'Late')), "
            "SUM(attendance != 'Cancelled') FROM intervention_sessions GROUP BY "
            "intervention_id")}
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "admission_no", "pupil", "year", "subject", "type", "programme",
                    "reason", "start", "end", "status", "led_by", "frequency", "baseline",
                    "target", "current", "grade_change", "outcome", "sessions_attended",
                    "sessions_run"])
        for r in rows:
            came, ran = att.get(r.intervention_id, (0, 0))
            w.writerow([r.intervention_id, _safe(r.admission_no), _safe(r.pupil_name),
                        r.pupil_year, _safe(r.subject_code), r.intervention_type,
                        _safe(r.programme), _safe(r.reason), r.start_date, r.end_date or "",
                        r.status, _safe(r.led_by), r.frequency, _safe(r.baseline_grade),
                        _safe(r.target_grade), _safe(r.current_grade),
                        "" if r.grade_change is None else r.grade_change, r.outcome or "",
                        came or 0, ran or 0])
    activity_log.record("interventions.export", principal=actor, rows=len(rows))
    return len(rows)
