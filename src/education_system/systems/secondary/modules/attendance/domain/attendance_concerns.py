"""Attendance concerns: the attendance lead's casework.

Built on :mod:`modules.attendance.domain.attendance` - the registers are the
only attendance data; this module reads them (summaries, persistent
absentees, pupil history) and never stores marks of its own.

Kept from the old Attendance Concerns:

* One case per pupil per concern episode with academic year, concern type
  (Persistent absence, Severe absence, Unauthorised pattern, Lateness pattern,
  Medical, Emotional/Anxiety, Family/Domestic, Bereavement, Other), level
  (Low 90-94%, Moderate 85-89%, High 80-84%, Severe <80%, PA threshold <90%),
  attendance %, threshold % (default 90), opened / next review / closed
  dates, status (Open, Monitoring, Improving, Closed, Escalated), key worker,
  intervention, parent contact and notes. Closed sets the closed date; a
  closed date only with Closed; reviews and closing not before opening.
* List with filters (year, status, type, level, key worker, open only),
  view, edit, set status, close, delete and the cohort summary (total, open,
  by status / level / type, pupils, average attendance).

New, following the DfE "Working together to improve school attendance"
(statutory from August 2024):

* **From the registers.** Attendance % is read from the registers (this
  school year to date); :func:`candidates` lists pupils who are persistently
  (below 90%) or severely (50% or less) absent with no open case, and
  :func:`open_from_attendance` opens cases for them in one go.
* **Stages.** Concern noted -> Letter 1 -> Attendance meeting / support plan
  -> Letter 2 -> Early help / formal support -> Parenting contract / notice
  to improve -> LA referral. Stages move forward; support has to be offered
  (a meeting) before a notice to improve, and a notice to improve before a
  referral for a penalty notice (unless it is leave in term time).
* **Penalty-notice threshold.** :func:`penalty_threshold` counts unauthorised
  sessions in a rolling 10 school weeks (the national threshold is 10).
* **Targets and reviews.** A target %, review dates and :func:`record_review`
  (attendance since the case opened against the target).
* **Letters home** through the school outbox (letter 1, meeting invitation,
  letter 2, notice to improve, improvement letter) to contacts with parental
  responsibility.
* **Children missing education.** A CME flag with the date the local
  authority was told; :func:`unexplained_run` counts consecutive school days
  of unexplained absence (10 or more: tell the local authority).
* **Trend.** :func:`weekly_trend` - attendance % week by week.
* **Dashboard** by year group and form (pupils, average %, persistent,
  severe, open cases).
* **Who.** The attendance lead (:data:`ATTENDANCE_CONCERN_EDITORS`) opens,
  changes and escalates cases. All staff can read them; the pupil's form
  tutor and head of year can add notes. Every change is in
  ``attendance_concern_audit`` and the activity log (ids only).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    ATTENDANCE_CONCERN_EDITORS,
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

CONCERN_STATUSES: tuple[str, ...] = ("Open", "Monitoring", "Improving", "Closed", "Escalated")
DEFAULT_STATUS = "Open"
CONCERN_LEVELS: tuple[str, ...] = (
    "Low (90-94%)", "Moderate (85-89%)", "High (80-84%)", "Severe (<80%)",
    "PA threshold (<90%)", "Severe absence (50% or less)")
DEFAULT_LEVEL = "PA threshold (<90%)"
CONCERN_TYPES: tuple[str, ...] = (
    "Persistent absence", "Severe absence", "Unauthorised pattern", "Lateness pattern",
    "Medical", "Emotional/Anxiety", "Family/Domestic", "Bereavement", "Other")
DEFAULT_TYPE = "Persistent absence"

STAGES: tuple[str, ...] = (
    "Concern noted", "Letter 1", "Attendance meeting", "Letter 2",
    "Early help / formal support", "Parenting contract / notice to improve", "LA referral")
FIRST_STAGE = STAGES[0]
MEETING, NOTICE, REFERRAL = STAGES[2], STAGES[5], STAGES[6]
REFERRAL_TYPES: tuple[str, ...] = (
    "Penalty notice", "Prosecution", "Education supervision order", "Other")
LA_OUTCOMES: tuple[str, ...] = (
    "Penalty notice issued", "Penalty notice paid", "Prosecution started", "Fined by court",
    "Parenting order", "Education supervision order made", "Referral declined",
    "Withdrawn", "Other")

ACTION_TYPES: tuple[str, ...] = (
    "Note", "Phone call", "Home visit", "Meeting", "Conversation with pupil", "Letter sent",
    "Stage", "Review", "Target set", "CME", "LA referral", "LA outcome", "Other")
#: What form tutors and heads of year may add.
NOTE_TYPES: tuple[str, ...] = ("Note", "Phone call", "Home visit", "Meeting",
                               "Conversation with pupil")

#: letter key -> (stage it marks, template, label)
LETTERS: dict[str, tuple[str | None, str, str]] = {
    "letter_1": ("Letter 1", "attendance_letter_1", "First attendance letter"),
    "meeting": (MEETING, "attendance_meeting", "Invitation to an attendance meeting"),
    "letter_2": ("Letter 2", "attendance_letter_2", "Second attendance letter"),
    "notice_to_improve": (NOTICE, "attendance_notice_to_improve", "Notice to improve"),
    "improved": (None, "attendance_improved", "Attendance has improved"),
}

PERSISTENT_BELOW = 100.0 - AT.PERSISTENT_ABSENCE   # 90%
SEVERE_AT_OR_BELOW = 100.0 - AT.SEVERE_ABSENCE     # 50%
PENALTY_SESSIONS = 10        # unauthorised sessions ...
PENALTY_WEEKS = 10           # ... in a rolling 10 school weeks
CME_DAYS = 10                # consecutive school days of unexplained absence
DEFAULT_REVIEW_WEEKS = 4
UNEXPLAINED = frozenset({"N", "O"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_concerns (
    concern_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    academic_year     TEXT NOT NULL,
    concern_type      TEXT NOT NULL DEFAULT 'Persistent absence',
    level             TEXT NOT NULL DEFAULT 'PA threshold (<90%)',
    attendance_pct    REAL CHECK (attendance_pct IS NULL OR attendance_pct BETWEEN 0 AND 100),
    threshold_pct     REAL NOT NULL DEFAULT 90.0,
    target_pct        REAL CHECK (target_pct IS NULL OR target_pct BETWEEN 0 AND 100),
    stage             TEXT NOT NULL DEFAULT 'Concern noted',
    stage_date        TEXT,
    opened_date       TEXT NOT NULL,
    next_review_date  TEXT,
    closed_date       TEXT,
    status            TEXT NOT NULL DEFAULT 'Open' CHECK (status IN
                      ('Open', 'Monitoring', 'Improving', 'Closed', 'Escalated')),
    key_worker        TEXT,
    intervention      TEXT,
    parent_contact    TEXT,
    notes             TEXT,
    meeting_date      TEXT,
    support_plan      TEXT,
    cme               INTEGER NOT NULL DEFAULT 0,
    cme_reported_date TEXT,
    cme_notes         TEXT,
    la_referral_date  TEXT,
    la_referral_type  TEXT,
    la_outcome        TEXT,
    la_outcome_date   TEXT,
    created_by        TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_att_concerns_pupil ON attendance_concerns (pupil_id);
CREATE INDEX IF NOT EXISTS ix_att_concerns_status ON attendance_concerns (status);
CREATE TABLE IF NOT EXISTS attendance_concern_actions (
    action_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id     INTEGER NOT NULL REFERENCES attendance_concerns (concern_id)
                   ON DELETE CASCADE,
    action_date    TEXT NOT NULL,
    action_type    TEXT NOT NULL DEFAULT 'Note',
    summary        TEXT NOT NULL,
    outcome        TEXT,
    attendance_pct REAL,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_att_concern_actions ON attendance_concern_actions (concern_id);
CREATE TABLE IF NOT EXISTS attendance_concern_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("attendance_concerns", _SCHEMA)


@dataclass(frozen=True)
class Concern:
    concern_id: int
    pupil_id: int
    academic_year: str
    concern_type: str
    level: str
    attendance_pct: float | None
    threshold_pct: float
    target_pct: float | None
    stage: str
    stage_date: str | None
    opened_date: str
    next_review_date: str | None
    closed_date: str | None
    status: str
    key_worker: str | None
    intervention: str | None
    parent_contact: str | None
    notes: str | None
    meeting_date: str | None
    support_plan: str | None
    cme: bool
    cme_reported_date: str | None
    cme_notes: str | None
    la_referral_date: str | None
    la_referral_type: str | None
    la_outcome: str | None
    la_outcome_date: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status != "Closed"

    @property
    def stage_no(self) -> int:
        return STAGES.index(self.stage) + 1 if self.stage in STAGES else 0

    @property
    def review_overdue(self) -> bool:
        return bool(self.is_open and self.next_review_date and
                    self.next_review_date < _today().isoformat())


@dataclass(frozen=True)
class Action:
    action_id: int
    concern_id: int
    action_date: str
    action_type: str
    summary: str
    outcome: str | None
    attendance_pct: float | None
    created_by: str | None
    created_at: str


_SELECT = """
SELECT c.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group AS pupil_year, p.form_group
FROM attendance_concerns c JOIN pupils p USING (pupil_id)
"""
_EXTRA = ("pupil_name", "admission_no", "pupil_year", "form_group")
_BASE = tuple(f for f in Concern.__dataclass_fields__ if f not in _EXTRA)


def _row(r) -> Concern:
    vals = {k: r[k] for k in _BASE}
    vals["cme"] = bool(vals["cme"])
    return Concern(**vals, pupil_name=f"{r['legal_last_name']}, "
                                      f"{r['preferred_name'] or r['legal_first_name']}",
                   admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                   form_group=r["form_group"])


def _action_row(r) -> Action:
    return Action(**{k: r[k] for k in Action.__dataclass_fields__})


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in ATTENDANCE_CONCERN_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"attendance_concerns.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see attendance concerns.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the attendance lead can do that.")


def is_tutor_or_head_of_year(actor: Principal, pupil_year: int, form_group: str | None
                             ) -> bool:
    """The pupil's form tutor (this year) or head of year."""
    if actor.role not in STAFF_ROLES:
        return False
    try:
        from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
        if BH.is_head_of_year(actor, pupil_year):
            return True
        from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
        names = {n.upper() for f in FT.my_forms(actor)
                 for n in (f.name, f"{f.year_group}{f.name}")}
        return bool(form_group) and form_group.upper() in names
    except Exception:  # noqa: BLE001 - no year / form records: not theirs
        return False


def can_add_note(actor: Principal, c: Concern) -> bool:
    return is_editor(actor) or is_tutor_or_head_of_year(actor, c.pupil_year, c.form_group)


def _audit(conn, action: str, actor: Principal, *, concern_id: int | None = None,
           pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO attendance_concern_audit (concern_id, pupil_id, action, detail, "
                 "actor) VALUES (?, ?, ?, ?, ?)",
                 (concern_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(concern_id: int | None = None, *, pupil_id: int | None = None,
            limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM attendance_concern_audit", [], []
    for col, val in (("concern_id", concern_id), ("pupil_id", pupil_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(int(val))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "concern_id": r["concern_id"], "pupil_id": r["pupil_id"],
                 "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


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


def _pct(value: Any, label: str, problems: list[str]) -> float | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        f = float(str(value).strip().rstrip("%"))
    except ValueError:
        problems.append(f"{label} must be a number")
        return None
    if not 0 <= f <= 100:
        problems.append(f"{label} must be between 0 and 100")
        return None
    return round(f, 2)


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


def suggest_level(pct: float | None) -> str:
    """The old levels, from an attendance %."""
    if pct is None:
        return DEFAULT_LEVEL
    if pct <= SEVERE_AT_OR_BELOW:
        return "Severe absence (50% or less)"
    if pct < 80:
        return "Severe (<80%)"
    if pct < 85:
        return "High (80-84%)"
    if pct < 90:
        return "Moderate (85-89%)"
    return "Low (90-94%)"


FIELDS = ("concern_type", "level", "attendance_pct", "threshold_pct", "target_pct",
          "opened_date", "next_review_date", "closed_date", "status", "key_worker",
          "intervention", "parent_contact", "notes", "meeting_date", "support_plan")


def _clean(data: dict[str, Any], current: Concern | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}
    out["concern_type"] = _choice(merged.get("concern_type"), CONCERN_TYPES, "Concern type",
                                  problems, DEFAULT_TYPE)
    out["status"] = _choice(merged.get("status"), CONCERN_STATUSES, "Status", problems,
                            DEFAULT_STATUS)
    out["attendance_pct"] = _pct(merged.get("attendance_pct"), "Attendance %", problems)
    out["threshold_pct"] = _pct(merged.get("threshold_pct"), "Threshold %", problems) \
        or PERSISTENT_BELOW
    out["target_pct"] = _pct(merged.get("target_pct"), "Target %", problems)
    out["level"] = _choice(merged.get("level"), CONCERN_LEVELS, "Level", problems,
                           suggest_level(out["attendance_pct"]))
    for k, label in (("opened_date", "Opened date"), ("next_review_date", "Next review date"),
                     ("closed_date", "Closed date"), ("meeting_date", "Meeting date")):
        out[k] = _date(merged.get(k), label, problems)
    today = _today().isoformat()
    if out["opened_date"] is None:
        out["opened_date"] = today
    elif out["opened_date"] > today:
        problems.append("Opened date can't be in the future")
    if out["next_review_date"] and out["next_review_date"] < out["opened_date"]:
        problems.append("Next review date cannot be before opened date")
    if out["closed_date"] and out["closed_date"] < out["opened_date"]:
        problems.append("Closed date cannot be before opened date")
    if out["status"] == "Closed" and not out["closed_date"]:
        out["closed_date"] = today
    if out["status"] != "Closed" and out["closed_date"]:
        if current is not None and current.status == "Closed" and "closed_date" not in data:
            out["closed_date"] = None      # reopened
        else:
            problems.append("Closed date should only be set when status is Closed")
    if out["target_pct"] is not None and out["attendance_pct"] is not None and \
            out["target_pct"] <= out["attendance_pct"] and current is None:
        problems.append("The target should be above the current attendance %")
    for k, n in (("key_worker", 80), ("parent_contact", 200), ("intervention", 2000),
                 ("notes", 4000), ("support_plan", 4000)):
        out[k] = _text(merged.get(k), n)
    return out, problems


# ── Figures from the registers ───────────────────────────────────────

def figures(pupil_id: int, start: Any = None, end: Any = None) -> AT.Summary:
    """The pupil's register figures (this school year to date by default)."""
    return AT.pupil_summary(pupil_id, start, end)


def band(pct: float | None) -> str:
    """'severe', 'persistent' or '' from an attendance %."""
    if pct is None:
        return ""
    return "severe" if pct <= SEVERE_AT_OR_BELOW else (
        "persistent" if pct < PERSISTENT_BELOW else "")


def _monday(d: _dt.date) -> _dt.date:
    return d - _dt.timedelta(days=d.weekday())


def weekly_trend(pupil_id: int, *, weeks: int = 12, end: _dt.date | None = None
                 ) -> list[dict[str, Any]]:
    """Attendance week by week, oldest first: {'week', 'possible', 'attended',
    'unauthorised', 'pct'} (weeks with no possible sessions left out)."""
    last = end or _today()
    first = _monday(last) - _dt.timedelta(weeks=max(1, int(weeks)) - 1)
    by: dict[str, Counter] = {}
    for m in AT.pupil_history(pupil_id, first, last):
        wk = _monday(_dt.date.fromisoformat(m.date)).isoformat()
        c = by.setdefault(wk, Counter())
        cat = m.category
        if cat == AT.NOT_COUNTED:
            continue
        c["possible"] += 1
        if cat in (AT.PRESENT, AT.AEA):
            c["attended"] += 1
        elif cat == AT.UNAUTHORISED:
            c["unauthorised"] += 1
    return [{"week": wk, "possible": c["possible"], "attended": c["attended"],
             "unauthorised": c["unauthorised"],
             "pct": round(100.0 * c["attended"] / c["possible"], 1)}
            for wk, c in sorted(by.items()) if c["possible"]]


def rolling_weeks(end: _dt.date | None = None, weeks: int = PENALTY_WEEKS
                  ) -> tuple[_dt.date, _dt.date]:
    """(first day, last day) of the last *weeks* school weeks to *end*
    (weeks with no school days - holidays - don't count)."""
    last = end or _today()
    mon, found, guard = _monday(last), 0, 0
    start = mon
    while found < weeks and guard < 60:
        if AT.school_days(mon, min(mon + _dt.timedelta(days=6), last)):
            found += 1
            start = mon
        mon -= _dt.timedelta(weeks=1)
        guard += 1
    return start, last


def penalty_threshold(pupil_id: int, *, end: _dt.date | None = None) -> dict[str, Any]:
    """Unauthorised sessions in the rolling 10 school weeks:
    {'sessions', 'from', 'to', 'met'}."""
    s, e = rolling_weeks(end)
    n = sum(1 for m in AT.pupil_history(pupil_id, s, e) if m.category == AT.UNAUTHORISED)
    return {"sessions": n, "from": s.isoformat(), "to": e.isoformat(),
            "met": n >= PENALTY_SESSIONS}


def unexplained_run(pupil_id: int, *, end: _dt.date | None = None) -> int:
    """Consecutive school days, back from *end*, on which every mark is an
    unexplained absence (N or O) - the children-missing-education check."""
    last = end or _today()
    marks: dict[str, list[str]] = {}
    for m in AT.pupil_history(pupil_id, last - _dt.timedelta(days=70), last):
        marks.setdefault(m.date, []).append(m.code)
    n = 0
    for d in reversed(AT.school_days(last - _dt.timedelta(days=70), last)):
        codes = marks.get(d.isoformat())
        if not codes:
            if n == 0 and d == last:
                continue          # today not marked yet
            break
        if all(c in UNEXPLAINED for c in codes):
            n += 1
        else:
            break
    return n


# ── Reading ──────────────────────────────────────────────────────────

def get(concern_id: int) -> Concern:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE c.concern_id = ?", (int(concern_id),)).fetchone()
    if r is None:
        raise NotFound(f"No attendance concern #{concern_id}")
    return _row(r)


def get_concern(concern_id: int) -> Concern | None:
    try:
        return get(concern_id)
    except NotFound:
        return None


def list_concerns(*, pupil_id: int | None = None, academic_year: str | None = None,
                  status: str | None = None, concern_type: str | None = None,
                  level: str | None = None, key_worker: str | None = None,
                  stage: str | None = None, year_group: int | str | None = None,
                  form_group: str | None = None, open_only: bool = False,
                  cme_only: bool = False, limit: int = 3000) -> list[Concern]:
    """Cases, newest opened first (the old order)."""
    where, params = [], []
    for col, val in (("c.pupil_id", pupil_id), ("c.academic_year", academic_year),
                     ("c.status", status), ("c.concern_type", concern_type),
                     ("c.level", level), ("c.key_worker", key_worker), ("c.stage", stage)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if year_group not in (None, ""):
        where.append("p.year_group = ?")
        params.append(int(year_group))
    if form_group:
        where.append("upper(p.form_group) = upper(?)")
        params.append(form_group)
    if open_only:
        where.append("c.status != 'Closed'")
    if cme_only:
        where.append("c.cme = 1")
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY c.opened_date DESC, c.concern_id DESC LIMIT ?"
    with database.connect() as conn:
        return [_row(r) for r in conn.execute(sql, (*params, int(limit)))]


def open_for(pupil_id: int) -> Concern | None:
    rows = list_concerns(pupil_id=pupil_id, open_only=True)
    return rows[0] if rows else None


def list_actions(concern_id: int) -> list[Action]:
    with database.connect() as conn:
        return [_action_row(r) for r in conn.execute(
            "SELECT * FROM attendance_concern_actions WHERE concern_id = ? "
            "ORDER BY action_date, action_id", (int(concern_id),))]


def candidates(*, year_group: int | str | None = None, form: str | None = None
               ) -> list[tuple[P.Pupil, AT.Summary]]:
    """Persistently or severely absent pupils (this year) with no open case."""
    have = {c.pupil_id for c in list_concerns(open_only=True)}
    return [(p, s) for p, s in AT.persistent_absentees(
        year_group=int(year_group) if year_group not in (None, "") else None, form=form)
        if p.pupil_id not in have]


def check(data: dict[str, Any], *, actor: Principal, concern_id: int | None = None
          ) -> list[str]:
    """Things worth knowing before saving (the save still checks the rules)."""
    _require_staff(actor, "check")
    cur = get(concern_id) if concern_id else None
    p = P.get_pupil(cur.pupil_id) if cur else _pupil(data.get("pupil_id") or data.get("pupil"))
    if p is None:
        return []
    out: list[str] = []
    try:
        s = figures(p.pupil_id)
        pct = s.attendance_pct
        if pct is not None and pct >= PERSISTENT_BELOW and cur is None:
            out.append(f"{p.display_name}'s attendance this year is {pct}% - not below "
                       f"{PERSISTENT_BELOW:.0f}%.")
        if s.possible == 0:
            out.append("No attendance has been recorded for this pupil this year.")
        pt = penalty_threshold(p.pupil_id)
        if pt["met"]:
            out.append(f"{pt['sessions']} unauthorised sessions since {pt['from']} - the "
                       "national threshold for considering a penalty notice is met.")
        run = unexplained_run(p.pupil_id)
        if run >= CME_DAYS:
            out.append(f"{run} consecutive school days of unexplained absence - tell the "
                       "local authority (children missing education).")
    except Exception:  # noqa: BLE001 - figures are advice only
        pass
    if p.sen_status == "E":
        out.append(f"{p.display_name} has an EHC plan - involve the SENCO and the local "
                   "authority; consider reasonable adjustments.")
    elif p.sen_status == "K":
        out.append(f"{p.display_name} has SEN support - involve the SENCO.")
    if cur is None:
        other = open_for(p.pupil_id)
        if other:
            out.append(f"{p.display_name} already has open case #{other.concern_id}.")
    return out


# ── Writing ──────────────────────────────────────────────────────────

def _act(conn, c_id: int, action_type: str, summary: str, actor: Principal, *,
         day: str | None = None, outcome: str | None = None,
         pct: float | None = None) -> int:
    return conn.execute(
        "INSERT INTO attendance_concern_actions (concern_id, action_date, action_type, summary, "
        "outcome, attendance_pct, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (c_id, day or _today().isoformat(), action_type, summary[:2000], outcome, pct,
         actor.username)).lastrowid


def create(data: dict[str, Any], *, actor: Principal) -> Concern:
    """The old New concern. *data* carries ``pupil_id`` (id or admission no.).
    Attendance % is read from the registers when left blank."""
    _require_editor(actor, "create")
    problems: list[str] = []
    ref = data.get("pupil_id") or data.get("pupil")
    p = _pupil(ref)
    if p is None:
        problems.append("Pupil ID is required" if not ref else f"No pupil {ref}")
    elif p.roll_status != "on_roll":
        problems.append(f"{p.display_name} is not on roll")
    d = dict(data)
    if p is not None and d.get("attendance_pct") in (None, ""):
        try:
            d["attendance_pct"] = figures(p.pupil_id).attendance_pct
        except Exception:  # noqa: BLE001 - no figures yet
            d["attendance_pct"] = None
    c, more = _clean(d, None)
    problems += more
    if c["status"] == "Closed":
        problems.append("A new case can't start closed")
    if p is not None and not problems:
        other = open_for(p.pupil_id)
        if other:
            problems.append(f"{p.display_name} already has an open case (#{other.concern_id})"
                            " - add to that one")
    if not c["next_review_date"]:
        c["next_review_date"] = (_dt.date.fromisoformat(c["opened_date"]) +
                                 _dt.timedelta(weeks=DEFAULT_REVIEW_WEEKS)).isoformat()
    year = str(data.get("academic_year") or "").strip() or year_of(c["opened_date"])
    if len(year) != 7 or year[4] != "/":
        problems.append("Academic year must be in form YYYY/YY (e.g. 2025/26)")
    if problems:
        activity_log.record("attendance_concerns.create", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        cid = conn.execute(
            f"INSERT INTO attendance_concerns (pupil_id, academic_year, stage, stage_date, "
            f"{', '.join(FIELDS)}, created_by, updated_by) VALUES (?, ?, ?, ?, "
            f"{', '.join('?' * len(FIELDS))}, ?, ?)",
            (p.pupil_id, year, FIRST_STAGE, c["opened_date"], *(c[k] for k in FIELDS),
             actor.username, actor.username)).lastrowid
        _act(conn, cid, "Stage", f"{FIRST_STAGE}: case opened", actor, day=c["opened_date"],
             pct=c["attendance_pct"])
        _audit(conn, "create", actor, concern_id=cid, pupil_id=p.pupil_id,
               type=c["concern_type"])
    activity_log.record("attendance_concerns.create", target=p.admission_no, principal=actor,
                        concern=cid)
    return get(cid)


def open_from_attendance(pupil_ids: list[int], *, actor: Principal,
                         key_worker: str | None = None) -> dict[str, Any]:
    """Open a case for each chosen pupil from the registers (type and level
    from their figures). Returns {'created': [Concern], 'skipped': [str]}."""
    _require_editor(actor, "create")
    created, skipped = [], []
    for pid in dict.fromkeys(int(x) for x in pupil_ids):
        try:
            s = figures(pid)
            ctype = "Severe absence" if band(s.attendance_pct) == "severe" else DEFAULT_TYPE
            created.append(create({"pupil_id": pid, "concern_type": ctype,
                                   "attendance_pct": s.attendance_pct,
                                   "key_worker": key_worker,
                                   "target_pct": PERSISTENT_BELOW if (s.attendance_pct or 0)
                                   < PERSISTENT_BELOW else None}, actor=actor))
        except (ValidationError, NotFound) as e:
            p = P.get_pupil(pid)
            skipped.append(f"{p.display_name if p else pid}: {e}")
    return {"created": created, "skipped": skipped}


def update(concern_id: int, changes: dict[str, Any], *, actor: Principal) -> Concern:
    """The old Edit concern."""
    cur = get(concern_id)
    _require_editor(actor, "update", cur.admission_no)
    c, problems = _clean(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in FIELDS if c[k] != getattr(cur, k)]
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE attendance_concerns SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE concern_id = ?",
                     (*(c[k] for k in changed), actor.username, cur.concern_id))
        if "status" in changed:
            _act(conn, cur.concern_id, "Note", f"Status: {cur.status} -> {c['status']}", actor)
        if "target_pct" in changed and c["target_pct"] is not None:
            _act(conn, cur.concern_id, "Target set", f"Target {c['target_pct']}%", actor)
        _audit(conn, "update", actor, concern_id=cur.concern_id, pupil_id=cur.pupil_id,
               fields=changed)
    activity_log.record("attendance_concerns.update", target=cur.admission_no,
                        principal=actor, concern=cur.concern_id, fields=",".join(changed))
    return get(cur.concern_id)


def set_status(concern_id: int, status: str, *, actor: Principal) -> Concern:
    return update(concern_id, {"status": status}, actor=actor)


def close(concern_id: int, closed_date: str | None = None, *, actor: Principal,
          reason: str | None = None) -> Concern:
    c = update(concern_id, {"status": "Closed",
                            "closed_date": closed_date or _today().isoformat()}, actor=actor)
    if reason and reason.strip():
        with database.connect() as conn:
            _act(conn, c.concern_id, "Note", f"Closed: {reason.strip()}", actor,
                 day=c.closed_date)
    return c


def delete(concern_id: int, *, actor: Principal) -> bool:
    c = get(concern_id)
    _require_editor(actor, "delete", c.admission_no)
    if c.la_referral_date:
        raise ValidationError(["The case has been referred to the local authority - close it "
                               "rather than delete it"])
    with database.connect() as conn:
        conn.execute("DELETE FROM attendance_concerns WHERE concern_id = ?", (c.concern_id,))
        _audit(conn, "delete", actor, concern_id=c.concern_id, pupil_id=c.pupil_id)
    activity_log.record("attendance_concerns.delete", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return True


# ── Notes, stages, reviews ───────────────────────────────────────────

def add_note(concern_id: int, data: dict[str, Any], *, actor: Principal) -> Action:
    """A dated note on the case. Form tutors and heads of year add notes,
    calls, home visits and meetings; the lead any type."""
    c = get(concern_id)
    if not can_add_note(actor, c):
        _deny(actor, "note", c.admission_no, "Only the attendance lead or the pupil's form "
                                             "tutor / head of year can add notes.")
    problems: list[str] = []
    allowed = ACTION_TYPES if is_editor(actor) else NOTE_TYPES
    atype = _choice(data.get("action_type"), allowed, "Type", problems, "Note")
    day = _date(data.get("action_date"), "Date", problems) or _today().isoformat()
    if day > _today().isoformat():
        problems.append("The date can't be in the future")
    summary = str(data.get("summary") or "").strip()
    if not summary:
        problems.append("Summary is required")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = _act(conn, c.concern_id, atype, summary, actor, day=day,
                   outcome=_text(data.get("outcome"), 2000))
        _audit(conn, "note", actor, concern_id=c.concern_id, pupil_id=c.pupil_id, entry=aid,
               type=atype)
    activity_log.record("attendance_concerns.note", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    with database.connect() as conn:
        return _action_row(conn.execute("SELECT * FROM attendance_concern_actions WHERE "
                                        "action_id = ?", (aid,)).fetchone())


def delete_action(action_id: int, *, actor: Principal) -> bool:
    with database.connect() as conn:
        r = conn.execute("SELECT concern_id FROM attendance_concern_actions WHERE action_id = ?",
                         (int(action_id),)).fetchone()
    if r is None:
        raise NotFound(f"No entry #{action_id}")
    c = get(r["concern_id"])
    _require_editor(actor, "note_delete", c.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM attendance_concern_actions WHERE action_id = ?",
                     (int(action_id),))
        _audit(conn, "note_delete", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               entry=int(action_id))
    return True


def stage_problems(c: Concern, stage: str, *, leave_in_term_time: bool = False) -> list[str]:
    """Why a case can't move to *stage* yet."""
    out: list[str] = []
    if stage not in STAGES:
        return [f"Stage must be one of {', '.join(STAGES)}"]
    if not c.is_open:
        out.append("The case is closed - reopen it first")
    if STAGES.index(stage) <= STAGES.index(c.stage):
        out.append(f"The case is already at '{c.stage}' - stages only move forward")
    reached = STAGES.index(c.stage)
    if stage == NOTICE and reached < STAGES.index(MEETING) and not leave_in_term_time:
        out.append("Offer support first: hold an attendance meeting / agree a support plan "
                   "before a notice to improve")
    return out


def advance_stage(concern_id: int, stage: str, *, actor: Principal, day: str | None = None,
                  note: str | None = None, meeting_date: str | None = None,
                  support_plan: str | None = None, leave_in_term_time: bool = False
                  ) -> Concern:
    """Move the case on to a later stage (an LA referral goes through
    :func:`refer_to_la`)."""
    c = get(concern_id)
    _require_editor(actor, "stage", c.admission_no)
    problems = stage_problems(c, stage, leave_in_term_time=leave_in_term_time)
    if stage == REFERRAL:
        problems.append("Use 'Refer to the local authority' for an LA referral")
    d = _date(day, "Date", problems) or _today().isoformat()
    md = _date(meeting_date, "Meeting date", problems)
    if problems:
        raise ValidationError(problems)
    sets = {"stage": stage, "stage_date": d}
    if md:
        sets["meeting_date"] = md
    if support_plan and support_plan.strip():
        sets["support_plan"] = support_plan.strip()[:4000]
    if c.status == "Open" and STAGES.index(stage) >= STAGES.index(MEETING):
        sets["status"] = "Monitoring"
    with database.connect() as conn:
        conn.execute("UPDATE attendance_concerns SET " + ", ".join(f"{k} = ?" for k in sets)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE concern_id = ?",
                     (*sets.values(), actor.username, c.concern_id))
        _act(conn, c.concern_id, "Stage", f"{stage}" + (f": {note.strip()}" if note and
                                                        note.strip() else ""), actor, day=d)
        _audit(conn, "stage", actor, concern_id=c.concern_id, pupil_id=c.pupil_id, stage=stage)
    activity_log.record("attendance_concerns.stage", target=c.admission_no, principal=actor,
                        concern=c.concern_id, stage=STAGES.index(stage) + 1)
    return get(c.concern_id)


def referral_problems(c: Concern, referral_type: str, *, leave_in_term_time: bool = False
                      ) -> list[str]:
    out: list[str] = []
    if referral_type not in REFERRAL_TYPES:
        return [f"Referral type must be one of {', '.join(REFERRAL_TYPES)}"]
    if not c.is_open:
        out.append("The case is closed - reopen it first")
    if c.la_referral_date:
        out.append(f"Already referred on {c.la_referral_date}")
    reached = STAGES.index(c.stage) if c.stage in STAGES else 0
    if referral_type == "Penalty notice":
        if not penalty_threshold(c.pupil_id)["met"]:
            out.append(f"The penalty-notice threshold isn't met ({PENALTY_SESSIONS} "
                       f"unauthorised sessions in {PENALTY_WEEKS} school weeks)")
        if reached < STAGES.index(NOTICE) and not leave_in_term_time:
            out.append("Issue a notice to improve first (leave in term time is the exception)")
    elif referral_type in ("Prosecution", "Education supervision order") and \
            reached < STAGES.index("Early help / formal support"):
        out.append("Formal support (early help) should have been tried first")
    return out


def refer_to_la(concern_id: int, referral_type: str, *, actor: Principal,
                day: str | None = None, note: str | None = None,
                leave_in_term_time: bool = False) -> Concern:
    """Refer the case to the local authority (penalty notice, prosecution,
    education supervision order): stage LA referral, status Escalated."""
    c = get(concern_id)
    _require_editor(actor, "refer", c.admission_no)
    problems = referral_problems(c, referral_type, leave_in_term_time=leave_in_term_time)
    d = _date(day, "Date", problems) or _today().isoformat()
    if d > _today().isoformat():
        problems.append("The date can't be in the future")
    if problems:
        raise ValidationError(problems)
    pt = penalty_threshold(c.pupil_id)
    with database.connect() as conn:
        conn.execute("UPDATE attendance_concerns SET stage = ?, stage_date = ?, status = "
                     "'Escalated', la_referral_date = ?, la_referral_type = ?, updated_by = ?, "
                     "updated_at = datetime('now') WHERE concern_id = ?",
                     (REFERRAL, d, d, referral_type, actor.username, c.concern_id))
        _act(conn, c.concern_id, "LA referral",
             f"Referred to the local authority: {referral_type} ({pt['sessions']} "
             f"unauthorised sessions since {pt['from']})"
             + (f". {note.strip()}" if note and note.strip() else ""), actor, day=d)
        _audit(conn, "refer", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               type=referral_type)
    activity_log.record("attendance_concerns.refer", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return get(c.concern_id)


def record_la_outcome(concern_id: int, outcome: str, *, actor: Principal,
                      day: str | None = None, note: str | None = None) -> Concern:
    c = get(concern_id)
    _require_editor(actor, "la_outcome", c.admission_no)
    problems: list[str] = []
    if not c.la_referral_date:
        problems.append("The case hasn't been referred to the local authority")
    out = _choice(outcome, LA_OUTCOMES, "Outcome", problems, None)
    if not out and not problems:
        problems.append("Choose the outcome")
    d = _date(day, "Date", problems) or _today().isoformat()
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE attendance_concerns SET la_outcome = ?, la_outcome_date = ?, "
                     "updated_by = ?, updated_at = datetime('now') WHERE concern_id = ?",
                     (out, d, actor.username, c.concern_id))
        _act(conn, c.concern_id, "LA outcome", out + (f". {note.strip()}" if note and
                                                     note.strip() else ""), actor, day=d,
             outcome=out)
        _audit(conn, "la_outcome", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               outcome=out)
    return get(c.concern_id)


def set_cme(concern_id: int, flag: bool, *, actor: Principal, reported_date: str | None = None,
            notes: str | None = None) -> Concern:
    """Children missing education: flag the case (and the date the local
    authority was told), or clear the flag once the pupil is found."""
    c = get(concern_id)
    _require_editor(actor, "cme", c.admission_no)
    problems: list[str] = []
    d = _date(reported_date, "Reported to the LA", problems)
    if d and d > _today().isoformat():
        problems.append("The date can't be in the future")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE attendance_concerns SET cme = ?, cme_reported_date = ?, "
                     "cme_notes = ?, updated_by = ?, updated_at = datetime('now') "
                     "WHERE concern_id = ?",
                     (1 if flag else 0, d if flag else c.cme_reported_date,
                      _text(notes, 2000) or c.cme_notes, actor.username, c.concern_id))
        _act(conn, c.concern_id, "CME", ("Flagged as a child missing education"
                                         + (f"; LA told {d}" if d else "")) if flag
             else "No longer missing education", actor)
        _audit(conn, "cme", actor, concern_id=c.concern_id, pupil_id=c.pupil_id, flag=flag)
    activity_log.record("attendance_concerns.cme", target=c.admission_no, principal=actor,
                        concern=c.concern_id, flag=int(flag))
    return get(c.concern_id)


def record_review(concern_id: int, *, actor: Principal, summary: str = "",
                  next_review_date: str | None = None, status: str | None = None,
                  day: str | None = None) -> dict[str, Any]:
    """Review the case: attendance since it opened (and this year) against the
    target; sets the next review (default in 4 weeks) and, unless a status is
    given, Improving when the target is met. Returns {'concern', 'since',
    'year', 'met'}."""
    c = get(concern_id)
    _require_editor(actor, "review", c.admission_no)
    problems: list[str] = []
    d = _date(day, "Review date", problems) or _today().isoformat()
    nxt = _date(next_review_date, "Next review", problems)
    st = _choice(status, CONCERN_STATUSES, "Status", problems, None)
    if not c.is_open and st != "Closed" and st is None:
        problems.append("The case is closed")
    if nxt and nxt <= d:
        problems.append("The next review must be after this one")
    if problems:
        raise ValidationError(problems)
    since = figures(c.pupil_id, c.opened_date, d).attendance_pct
    year = figures(c.pupil_id, None, d).attendance_pct
    target = c.target_pct or c.threshold_pct
    met = since is not None and since >= target
    if st is None and c.status in ("Open", "Monitoring", "Improving"):
        st = "Improving" if met else ("Monitoring" if c.status == "Improving" else c.status)
    st = st or c.status
    nxt = nxt or (None if st == "Closed" else
                  (_dt.date.fromisoformat(d) +
                   _dt.timedelta(weeks=DEFAULT_REVIEW_WEEKS)).isoformat())
    text = (f"Review: {since if since is not None else '-'}% since {c.opened_date} "
            f"(target {target}%), {year if year is not None else '-'}% this year"
            + (" - target met" if met else "") + (f". {summary.strip()}" if summary and
                                                  summary.strip() else ""))
    with database.connect() as conn:
        conn.execute("UPDATE attendance_concerns SET attendance_pct = ?, next_review_date = ?, "
                     "status = ?, closed_date = ?, level = ?, updated_by = ?, "
                     "updated_at = datetime('now') WHERE concern_id = ?",
                     (year, nxt, st, d if st == "Closed" else None,
                      suggest_level(year) if year is not None else c.level,
                      actor.username, c.concern_id))
        _act(conn, c.concern_id, "Review", text, actor, day=d, pct=since,
             outcome="Target met" if met else "Below target")
        _audit(conn, "review", actor, concern_id=c.concern_id, pupil_id=c.pupil_id, met=met)
    activity_log.record("attendance_concerns.review", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return {"concern": get(c.concern_id), "since": since, "year": year, "met": met}


def refresh_figures(*, actor: Principal) -> int:
    """Re-read the attendance % of every open case from the registers."""
    _require_editor(actor, "refresh")
    n = 0
    for c in list_concerns(open_only=True):
        try:
            pct = figures(c.pupil_id).attendance_pct
        except Exception:  # noqa: BLE001
            continue
        if pct != c.attendance_pct:
            with database.connect() as conn:
                conn.execute("UPDATE attendance_concerns SET attendance_pct = ? WHERE "
                             "concern_id = ?", (pct, c.concern_id))
            n += 1
    activity_log.record("attendance_concerns.refresh", principal=actor, changed=n)
    return n


# ── Letters home ─────────────────────────────────────────────────────

def letter_problems(c: Concern, letter: str, *, leave_in_term_time: bool = False
                    ) -> list[str]:
    if letter not in LETTERS:
        return [f"Letter must be one of {', '.join(LETTERS)}"]
    stage = LETTERS[letter][0]
    if stage is None:
        return []
    if STAGES.index(stage) <= STAGES.index(c.stage):
        return []                       # resending at the same stage is fine
    return stage_problems(c, stage, leave_in_term_time=leave_in_term_time)


def send_letter(concern_id: int, letter: str, *, actor: Principal, note: str | None = None,
                meeting_date: str | None = None, leave_in_term_time: bool = False
                ) -> dict[str, Any]:
    """E-mail a letter to contacts with parental responsibility through the
    school outbox; moves the case on to the letter's stage. Returns
    {'message_id', 'emails', 'no_email'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    c = get(concern_id)
    _require_editor(actor, "letter", c.admission_no)
    problems = letter_problems(c, letter, leave_in_term_time=leave_in_term_time)
    md = _date(meeting_date, "Meeting date", problems) if meeting_date else None
    if letter == "meeting" and not (md or c.meeting_date):
        problems.append("Give the meeting date")
    s = figures(c.pupil_id)
    if s.possible == 0:
        problems.append("No attendance has been recorded for this pupil this year")
    if problems:
        raise ValidationError(problems)
    stage, template_name, label = LETTERS[letter]
    p = P.get_pupil(c.pupil_id)
    to = [(x.email, x.full_name) for x in C.emailable_for_pupils([c.pupil_id]).get(
        c.pupil_id, []) if x.email and x.parental_responsibility]
    if not to:
        return {"message_id": None, "emails": 0, "no_email": [p]}
    first = p.preferred_name or p.legal_first_name
    details = []
    when = md or c.meeting_date
    if letter == "meeting" and when:
        details.append("Meeting: " + _dt.date.fromisoformat(when).strftime("%A %d %B %Y"))
    if c.target_pct and letter != "improved":
        details.append(f"The target we have agreed is {c.target_pct:g}% attendance.")
    if note and note.strip():
        details.append(note.strip())
    template = email_templates.load_template(template_name)
    start = P.academic_year_start(_today()).isoformat()
    letters = []
    for address, name in to:
        subject, body = template.render({
            "recipient_name": name, "pupil_name": p.display_name, "first_name": first,
            "attendance_pct": f"{s.attendance_pct:g}" if s.attendance_pct is not None else "-",
            "sessions_missed": s.absent, "unauthorised": s.unauthorised,
            "period": f"{start} to {_today().isoformat()}",
            "details": "\n".join(details), "sender_name": c.key_worker or BH._staff_name(actor)})
        letters.append((address, name, subject, body))
    mid = E.save_prepared(f"attendance_{letter}", label, label, "(one letter per contact)",
                          letters, actor=actor)
    sets: dict[str, Any] = {}
    if stage and STAGES.index(stage) > STAGES.index(c.stage):
        sets.update(stage=stage, stage_date=_today().isoformat())
        if c.status == "Open" and STAGES.index(stage) >= STAGES.index(MEETING):
            sets["status"] = "Monitoring"
    if md:
        sets["meeting_date"] = md
    with database.connect() as conn:
        if sets:
            conn.execute("UPDATE attendance_concerns SET " + ", ".join(f"{k} = ?" for k in sets)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE "
                           "concern_id = ?", (*sets.values(), actor.username, c.concern_id))
        if "stage" in sets:
            _act(conn, c.concern_id, "Stage", stage, actor)
        _act(conn, c.concern_id, "Letter sent", f"{label} e-mailed to {len(letters)} "
                                                "contact(s)", actor, pct=s.attendance_pct)
        _audit(conn, "letter", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               letter=letter, emails=len(letters))
    activity_log.record("attendance_concerns.letter", target=c.admission_no, principal=actor,
                        concern=c.concern_id, letter=letter, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "no_email": []}


# ── Lists and summaries ──────────────────────────────────────────────

def due_reviews(*, today: _dt.date | None = None, within_days: int = 7) -> list[Concern]:
    """Open cases with a review due within *within_days* (or overdue, or none set)."""
    limit = ((today or _today()) + _dt.timedelta(days=within_days)).isoformat()
    rows = [c for c in list_concerns(open_only=True)
            if not c.next_review_date or c.next_review_date <= limit]
    return sorted(rows, key=lambda c: c.next_review_date or "")


def penalty_watch(*, year_group: int | str | None = None) -> list[tuple[Concern, dict]]:
    """Open cases where the 10-session threshold is met."""
    out = []
    for c in list_concerns(open_only=True, year_group=year_group):
        t = penalty_threshold(c.pupil_id)
        if t["met"]:
            out.append((c, t))
    return sorted(out, key=lambda x: -x[1]["sessions"])


def cme_watch(*, year_group: int | str | None = None) -> list[tuple[P.Pupil, int]]:
    """On-roll pupils with 10 or more consecutive days of unexplained absence."""
    out = []
    for p in P.list_pupils(year_group=int(year_group) if year_group not in (None, "")
                           else None):
        run = unexplained_run(p.pupil_id)
        if run >= CME_DAYS:
            out.append((p, run))
    return sorted(out, key=lambda x: -x[1])


def cohort_summary(*, academic_year: str | None = None,
                   year_group: int | str | None = None) -> dict[str, Any]:
    """The old cohort summary plus by stage, CME and referrals."""
    rows = list_concerns(academic_year=academic_year, year_group=year_group)
    vals = [r.attendance_pct for r in rows if r.attendance_pct is not None]
    return {"total": len(rows), "open": sum(1 for r in rows if r.is_open),
            "by_status": dict(Counter(r.status for r in rows)),
            "by_level": dict(Counter(r.level for r in rows)),
            "by_type": dict(Counter(r.concern_type for r in rows)),
            "by_stage": dict(Counter(r.stage for r in rows)),
            "pupils": len({r.pupil_id for r in rows}),
            "avg_attendance": round(sum(vals) / len(vals), 2) if vals else None,
            "cme": sum(1 for r in rows if r.cme),
            "referrals": sum(1 for r in rows if r.la_referral_date)}


def dashboard(*, year_group: int | str | None = None) -> dict[str, Any]:
    """This year by year group and by form: pupils, average attendance,
    persistent and severe absentees, open cases. {'by_year', 'by_form',
    'school'}."""
    rows = AT.summaries(year_group=int(year_group) if year_group not in (None, "") else None)
    open_by = Counter(c.pupil_id for c in list_concerns(open_only=True, year_group=year_group))

    def group(key) -> list[dict[str, Any]]:
        g: dict[Any, list] = {}
        for p, s in rows:
            g.setdefault(key(p), []).append((p, s))
        return [_figures(k, v, open_by) for k, v in sorted(g.items(), key=lambda x: str(x[0]))]
    return {"by_year": group(lambda p: p.year_group),
            "by_form": group(lambda p: p.form_group or "(none)"),
            "school": _figures("School", rows, open_by)}


def _figures(name: Any, rows: list, open_by: Counter) -> dict[str, Any]:
    possible = sum(s.possible for _p, s in rows)
    attended = sum(s.attended for _p, s in rows)
    return {"group": name, "pupils": len(rows),
            "pct": round(100.0 * attended / possible, 1) if possible else None,
            "persistent": sum(1 for _p, s in rows if s.band in ("persistent", "severe")),
            "severe": sum(1 for _p, s in rows if s.band == "severe"),
            "open": sum(open_by[p.pupil_id] for p, _s in rows)}


def for_pupil(pupil_id: int) -> dict[str, Any]:
    """For the pupil profile: {'open', 'cases', 'pct', 'band', 'threshold'}."""
    cases = list_concerns(pupil_id=pupil_id)
    try:
        pct = figures(pupil_id).attendance_pct
        t = penalty_threshold(pupil_id)
    except Exception:  # noqa: BLE001
        pct, t = None, {"sessions": 0, "met": False}
    return {"open": next((c for c in cases if c.is_open), None), "cases": cases, "pct": pct,
            "band": band(pct), "threshold": t}


def for_staff(actor: Principal) -> list[Concern]:
    """Open cases for pupils in my form(s) / year (all for the lead) - My Day."""
    if actor.role not in STAFF_ROLES:
        return []
    rows = list_concerns(open_only=True)
    if is_editor(actor):
        return rows
    return [c for c in rows if is_tutor_or_head_of_year(actor, c.pupil_year, c.form_group)]


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_concerns(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "admission_no", "pupil", "year", "form", "academic_year", "type",
                    "level", "attendance_pct", "threshold_pct", "target_pct", "stage",
                    "stage_date", "status", "opened", "next_review", "closed", "key_worker",
                    "meeting", "cme", "la_referral", "la_referral_type", "la_outcome"])
        for c in rows:
            w.writerow([c.concern_id, _safe(c.admission_no), _safe(c.pupil_name), c.pupil_year,
                        _safe(c.form_group), c.academic_year, c.concern_type, c.level,
                        c.attendance_pct if c.attendance_pct is not None else "",
                        c.threshold_pct, c.target_pct if c.target_pct is not None else "",
                        c.stage, c.stage_date or "", c.status, c.opened_date,
                        c.next_review_date or "", c.closed_date or "", _safe(c.key_worker),
                        c.meeting_date or "", "yes" if c.cme else "", c.la_referral_date or "",
                        c.la_referral_type or "", c.la_outcome or ""])
    activity_log.record("attendance_concerns.export", principal=actor, rows=len(rows))
    return len(rows)

