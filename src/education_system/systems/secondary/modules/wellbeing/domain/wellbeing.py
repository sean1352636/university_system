"""Pupil wellbeing: check-ins and mood surveys, referrals, support plans.

Kept from the old Wellbeing:

* **Check-ins**: pupil, date, source (Self check-in, Form tutor, Pastoral
  team, Counsellor, Mental health lead, Other), three 1-5 ratings (mood,
  confidence, connection) and their average, stressors, supports, action
  needed (needs an action summary), recorded by, status (Open, InProgress,
  Closed, Escalated), follow-up date (not before the check-in) and with whom,
  notes. A check-in needs at least one rating or some text.
* List with filters (year, pupil, status, action only), log, edit, set
  status, delete, the pupil summary (averages, action count, by status), the
  cohort summary (averages, by status / source) and pupils with low ratings
  (latest check-in at or below a threshold, default 2).

New:

* **Mood surveys.** A survey round for a year group or form with open and
  close dates; responses are check-ins linked to it; response rate, averages
  and low scorers. :func:`self_check_in` is the hook for pupils to answer
  from the portal (a pupil login, only for themselves, only while a survey
  is open or as a free check-in).
* **Referrals** to the school counsellor, CAMHS, the mental health support
  team, the school nurse, young carers, bereavement support and others, with
  urgency, consent, status (Referred, Accepted, Waiting list, In progress,
  Declined, Completed, Withdrawn), dates and outcome.
* **Support plans** with need, strategies, actions for staff / pupil /
  family, key adult, review date and a dated review log.
* **Caseload**: every pupil with an open check-in, referral or plan - latest
  score, trend, open referrals, plan review due - optionally for one key adult.
* **Trend** per pupil (average score by check-in).
* **Safeguarding.** :func:`safeguarding_signs` spots words that suggest a
  safeguarding matter (harm, abuse, feeling unsafe...); the check-in is
  flagged and the screen tells the member of staff to use "Report a
  Safeguarding Concern" - wellbeing records are not the safeguarding record.
* **Who.** The wellbeing lead (:data:`WELLBEING_EDITORS`) sees and manages
  everything. Any member of staff can log a check-in; staff see the
  check-ins they recorded and those of pupils in their form / year (form
  tutors, heads of year), and those pupils' plans (to follow the
  strategies); referrals are for the lead and heads of year. Every change is
  in ``wellbeing_audit`` and the activity log (ids only).
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

from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    STAFF_ROLES,
    WELLBEING_EDITORS,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

CHECKIN_STATUSES: tuple[str, ...] = ("Open", "InProgress", "Closed", "Escalated")
DEFAULT_STATUS = "Open"
CHECKIN_SOURCES: tuple[str, ...] = (
    "Self check-in", "Form tutor", "Pastoral team", "Counsellor", "Mental health lead",
    "Other", "Mood survey")
DEFAULT_SOURCE = "Form tutor"
MIN_RATING, MAX_RATING = 1, 5
LOW_THRESHOLD = 2

SERVICES: tuple[str, ...] = (
    "School counsellor", "CAMHS", "Mental health support team", "School nurse",
    "Young carers", "Bereavement support", "Educational psychologist", "Early help",
    "GP", "Other")
URGENCIES: tuple[str, ...] = ("Routine", "Urgent", "Emergency")
CONSENTS: tuple[str, ...] = ("Pupil and parent", "Pupil", "Parent", "Not needed", "Refused")
REFERRAL_STATUSES: tuple[str, ...] = (
    "Referred", "Accepted", "Waiting list", "In progress", "Declined", "Completed",
    "Withdrawn")
REFERRAL_CLOSED = frozenset({"Declined", "Completed", "Withdrawn"})
REFERRAL_OUTCOMES: tuple[str, ...] = (
    "Improved", "Some improvement", "No change", "Worse", "Disengaged",
    "Transferred to another service", "Other")
PLAN_STATUSES: tuple[str, ...] = ("Active", "Closed")
SURVEY_STATUSES: tuple[str, ...] = ("Draft", "Open", "Closed")

#: Words that suggest a safeguarding matter (a prompt, not a decision).
_SAFEGUARDING_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bself[- ]?harm", "self-harm"), (r"\bcut(ting|s)? (my|him|her|them)sel", "self-harm"),
    (r"\bsuicid", "suicide"), (r"\bkill (my|him|her|them)sel", "suicide"),
    (r"\bend (my|it all|my life)", "suicide"), (r"\bwant(s)? to die\b", "suicide"),
    (r"\babus", "abuse"), (r"\bhit(s|ting)? me\b", "being hurt"), (r"\bhurt(s|ing)? me\b",
                                                                  "being hurt"),
    (r"\bbruis", "injury"), (r"\btouch(ed|ing)? me\b", "sexual harm"),
    (r"\bsexual", "sexual harm"), (r"\bgroom", "grooming"),
    (r"(\bnot|n'?t)( feel(s|ing)?)? safe\b", "feeling unsafe"), (r"\bunsafe\b", "feeling unsafe"),
    (r"\bscared (to go|of going) home\b", "feeling unsafe"),
    (r"\brun(ning)? away\b", "running away"), (r"\bno food\b|\bhungry all", "neglect"),
    (r"\bdomestic violence\b", "domestic abuse"), (r"\bknife|\bweapon", "weapons"),
    (r"\bexploit", "exploitation"), (r"\bdrugs?\b", "drugs"), (r"\bradicali", "radicalisation"),
    (r"\bforced marriage\b", "forced marriage"), (r"\bfgm\b", "FGM"))
SAFEGUARDING_ADVICE = ("This may be a safeguarding matter. Use \"Report a Safeguarding "
                       "Concern\" now so the designated safeguarding lead sees it - a wellbeing "
                       "record is not the safeguarding record.")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS wellbeing_surveys (
    survey_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    year_group    INTEGER,
    form_group    TEXT,
    open_date     TEXT NOT NULL,
    close_date    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN ('Draft', 'Open', 'Closed')),
    question      TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS wellbeing_checkins (
    checkin_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id           INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    checkin_date       TEXT NOT NULL,
    source             TEXT NOT NULL DEFAULT 'Form tutor',
    mood_rating        INTEGER CHECK (mood_rating IS NULL OR mood_rating BETWEEN 1 AND 5),
    confidence_rating  INTEGER CHECK (confidence_rating IS NULL OR
                                      confidence_rating BETWEEN 1 AND 5),
    connection_rating  INTEGER CHECK (connection_rating IS NULL OR
                                      connection_rating BETWEEN 1 AND 5),
    stressors          TEXT,
    supports           TEXT,
    action_needed      INTEGER NOT NULL DEFAULT 0,
    action_summary     TEXT,
    recorded_by        TEXT,
    status             TEXT NOT NULL DEFAULT 'Open'
                       CHECK (status IN ('Open', 'InProgress', 'Closed', 'Escalated')),
    follow_up_date     TEXT,
    follow_up_with     TEXT,
    notes              TEXT,
    survey_id          INTEGER REFERENCES wellbeing_surveys (survey_id) ON DELETE SET NULL,
    safeguarding_flag  INTEGER NOT NULL DEFAULT 0,
    created_by         TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_wb_checkins_pupil ON wellbeing_checkins (pupil_id, checkin_date);
CREATE TABLE IF NOT EXISTS wellbeing_referrals (
    referral_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    service          TEXT NOT NULL,
    referral_date    TEXT NOT NULL,
    reason           TEXT NOT NULL,
    urgency          TEXT NOT NULL DEFAULT 'Routine',
    consent          TEXT NOT NULL DEFAULT 'Pupil and parent',
    status           TEXT NOT NULL DEFAULT 'Referred',
    accepted_date    TEXT,
    first_appointment TEXT,
    closed_date      TEXT,
    outcome          TEXT,
    outcome_notes    TEXT,
    contact_name     TEXT,
    checkin_id       INTEGER REFERENCES wellbeing_checkins (checkin_id) ON DELETE SET NULL,
    referred_by      TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_wb_referrals_pupil ON wellbeing_referrals (pupil_id);
CREATE TABLE IF NOT EXISTS wellbeing_plans (
    plan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    start_date      TEXT NOT NULL,
    review_date     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Closed')),
    need            TEXT NOT NULL,
    strategies      TEXT,
    staff_actions   TEXT,
    pupil_actions   TEXT,
    family_actions  TEXT,
    key_adult       TEXT,
    closed_date     TEXT,
    outcome         TEXT,
    created_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS wellbeing_plan_reviews (
    review_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id      INTEGER NOT NULL REFERENCES wellbeing_plans (plan_id) ON DELETE CASCADE,
    review_date  TEXT NOT NULL,
    summary      TEXT NOT NULL,
    next_review  TEXT,
    reviewed_by  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS wellbeing_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    record_id  INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("wellbeing", _SCHEMA)


@dataclass(frozen=True)
class CheckIn:
    checkin_id: int
    pupil_id: int
    checkin_date: str
    source: str
    mood_rating: int | None
    confidence_rating: int | None
    connection_rating: int | None
    stressors: str | None
    supports: str | None
    action_needed: bool
    action_summary: str | None
    recorded_by: str | None
    status: str
    follow_up_date: str | None
    follow_up_with: str | None
    notes: str | None
    survey_id: int | None
    safeguarding_flag: bool
    created_by: str | None
    created_at: str
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def average_rating(self) -> float | None:
        vals = [v for v in (self.mood_rating, self.confidence_rating, self.connection_rating)
                if v is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    @property
    def lowest(self) -> int | None:
        vals = [v for v in (self.mood_rating, self.confidence_rating, self.connection_rating)
                if v is not None]
        return min(vals) if vals else None

    @property
    def follow_up_overdue(self) -> bool:
        return bool(self.status not in ("Closed",) and self.follow_up_date and
                    self.follow_up_date < _today().isoformat())


@dataclass(frozen=True)
class Referral:
    referral_id: int
    pupil_id: int
    service: str
    referral_date: str
    reason: str
    urgency: str
    consent: str
    status: str
    accepted_date: str | None
    first_appointment: str | None
    closed_date: str | None
    outcome: str | None
    outcome_notes: str | None
    contact_name: str | None
    checkin_id: int | None
    referred_by: str | None
    created_at: str
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status not in REFERRAL_CLOSED

    @property
    def waiting_days(self) -> int:
        end = self.first_appointment or self.closed_date or _today().isoformat()
        return (_dt.date.fromisoformat(end) - _dt.date.fromisoformat(self.referral_date)).days


@dataclass(frozen=True)
class Plan:
    plan_id: int
    pupil_id: int
    start_date: str
    review_date: str
    status: str
    need: str
    strategies: str | None
    staff_actions: str | None
    pupil_actions: str | None
    family_actions: str | None
    key_adult: str | None
    closed_date: str | None
    outcome: str | None
    created_by: str | None
    created_at: str
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None

    @property
    def review_due(self) -> bool:
        return self.status == "Active" and self.review_date <= _today().isoformat()


@dataclass(frozen=True)
class Survey:
    survey_id: int
    title: str
    year_group: int | None
    form_group: str | None
    open_date: str
    close_date: str
    status: str
    question: str | None
    created_by: str | None
    created_at: str

    @property
    def scope(self) -> str:
        if self.form_group:
            return f"Form {self.form_group}"
        return f"Year {self.year_group}" if self.year_group else "Whole school"

    def is_open_on(self, day: _dt.date | None = None) -> bool:
        iso = (day or _today()).isoformat()
        return self.status == "Open" and self.open_date <= iso <= self.close_date


_PUPIL_COLS = ("p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no, "
               "p.year_group AS pupil_year, p.form_group")
_EXTRA = ("pupil_name", "admission_no", "pupil_year", "form_group")


def _make(cls, r, bools: tuple[str, ...] = ()):
    vals = {k: r[k] for k in cls.__dataclass_fields__ if k not in _EXTRA}
    for b in bools:
        vals[b] = bool(vals[b])
    return cls(**vals, pupil_name=f"{r['legal_last_name']}, "
                                  f"{r['preferred_name'] or r['legal_first_name']}",
               admission_no=r["admission_no"], pupil_year=r["pupil_year"],
               form_group=r["form_group"])


def _checkin_row(r) -> CheckIn:
    return _make(CheckIn, r, ("action_needed", "safeguarding_flag"))


def _survey_row(r) -> Survey:
    return Survey(**{k: r[k] for k in Survey.__dataclass_fields__})


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in WELLBEING_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"wellbeing.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see wellbeing records.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the wellbeing lead can do that.")


def _scope(actor: Principal) -> tuple[set[int], set[str]] | None:
    """(years I'm head of, forms I tutor) - None for the lead (everything)."""
    if is_editor(actor):
        return None
    years: set[int] = set()
    forms: set[str] = set()
    try:
        from education_system.systems.secondary.modules.curriculum.domain import form_tutors as FT
        years = FT._head_of_years(actor)
        ids = {a.form_id for a in FT.my_assignments(actor)}
        for f in FT.FG.list_forms():
            if f.form_id in ids:
                forms |= {f.name.upper(), f"{f.year_group}{f.name}".upper()}
    except Exception:  # noqa: BLE001 - no form / year records: own records only
        pass
    return years, forms


def _mine(scope, year: int, form: str | None) -> bool:
    return scope is None or year in scope[0] or (form or "").upper() in scope[1]


def is_head_of_year_for(actor: Principal, year: int) -> bool:
    s = _scope(actor)
    return s is None or year in s[0]


def can_see_pupil(actor: Principal, pupil: P.Pupil) -> bool:
    return actor.role in STAFF_ROLES and _mine(_scope(actor), pupil.year_group, pupil.form_group)


def _is_recorder(actor: Principal, c: CheckIn) -> bool:
    return bool(actor.username) and (c.created_by or "").lower() == actor.username.lower()


def can_edit_checkin(actor: Principal, c: CheckIn) -> bool:
    return is_editor(actor) or (actor.role in STAFF_ROLES and _is_recorder(actor, c))


def _audit(conn, kind: str, action: str, actor: Principal, *, record_id: int | None = None,
           pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO wellbeing_audit (kind, record_id, pupil_id, action, detail, actor)"
                 " VALUES (?, ?, ?, ?, ?, ?)",
                 (kind, record_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(*, kind: str | None = None, record_id: int | None = None,
            pupil_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM wellbeing_audit", [], []
    for col, val in (("kind", kind), ("record_id", record_id), ("pupil_id", pupil_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "kind": r["kind"], "record_id": r["record_id"],
                 "pupil_id": r["pupil_id"], "action": r["action"], "actor": r["actor"],
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


def _rating(value: Any, label: str, problems: list[str]) -> int | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a whole number")
        return None
    if not MIN_RATING <= n <= MAX_RATING:
        problems.append(f"{label} must be between {MIN_RATING} and {MAX_RATING}")
        return None
    return n


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"} \
        if not isinstance(value, bool) else value


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


def _need_pupil(ref: Any, problems: list[str]) -> P.Pupil | None:
    p = _pupil(ref)
    if p is None:
        problems.append("Pupil ID is required" if ref in (None, "") else f"No pupil {ref}")
    return p


def safeguarding_signs(*texts: Any) -> list[str]:
    """What in the text looks like a safeguarding matter (deduplicated)."""
    blob = " ".join(str(t or "") for t in texts).lower()
    out: list[str] = []
    for pattern, label in _SAFEGUARDING_PATTERNS:
        if re.search(pattern, blob) and label not in out:
            out.append(label)
    return out


# ── Check-ins ────────────────────────────────────────────────────────

CHECKIN_FIELDS = ("checkin_date", "source", "mood_rating", "confidence_rating",
                  "connection_rating", "stressors", "supports", "action_needed",
                  "action_summary", "recorded_by", "status", "follow_up_date",
                  "follow_up_with", "notes")


def _clean_checkin(data: dict[str, Any], cur: CheckIn | None
                   ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(cur, k) for k in CHECKIN_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in CHECKIN_FIELDS})
    out: dict[str, Any] = {}
    out["checkin_date"] = _date(merged.get("checkin_date"), "Check-in date", problems) \
        or _today().isoformat()
    if out["checkin_date"] > _today().isoformat():
        problems.append("Check-in date can't be in the future")
    out["source"] = _choice(merged.get("source"), CHECKIN_SOURCES, "Source", problems,
                            DEFAULT_SOURCE)
    for k, label in (("mood_rating", "Mood rating"), ("confidence_rating", "Confidence rating"),
                     ("connection_rating", "Connection rating")):
        out[k] = _rating(merged.get(k), label, problems)
    for k, n in (("stressors", 2000), ("supports", 2000), ("action_summary", 2000),
                 ("recorded_by", 80), ("follow_up_with", 80), ("notes", 4000)):
        out[k] = _text(merged.get(k), n)
    out["action_needed"] = _bool(merged.get("action_needed") or False)
    out["status"] = _choice(merged.get("status"), CHECKIN_STATUSES, "Status", problems,
                            DEFAULT_STATUS)
    out["follow_up_date"] = _date(merged.get("follow_up_date"), "Follow-up date", problems)
    if out["action_needed"] and not out["action_summary"]:
        problems.append("Action summary is required when action is needed")
    if out["follow_up_date"] and out["follow_up_date"] < out["checkin_date"]:
        problems.append("Follow-up date cannot be before check-in date")
    if all(out[k] is None for k in ("mood_rating", "confidence_rating", "connection_rating")) \
            and not (out["stressors"] or out["supports"] or out["notes"]):
        problems.append("A check-in needs at least one rating, or stressors / supports / notes")
    return out, problems


_CI_SELECT = f"SELECT c.*, {_PUPIL_COLS} FROM wellbeing_checkins c JOIN pupils p USING (pupil_id)"


def get_checkin(checkin_id: int) -> CheckIn:
    with database.connect() as conn:
        r = conn.execute(_CI_SELECT + " WHERE c.checkin_id = ?", (int(checkin_id),)).fetchone()
    if r is None:
        raise NotFound(f"No check-in #{checkin_id}")
    return _checkin_row(r)


def get(checkin_id: int) -> CheckIn | None:
    """The old lookup: None when there is no such check-in."""
    try:
        return get_checkin(checkin_id)
    except NotFound:
        return None


def list_checkins(*, actor: Principal | None = None, pupil_id: int | None = None,
                  year_group: int | str | None = None, status: str | None = None,
                  source: str | None = None, survey_id: int | None = None,
                  action_only: bool = False, flagged_only: bool = False,
                  date_from: str | None = None, date_to: str | None = None,
                  limit: int = 3000) -> list[CheckIn]:
    """Newest first. With *actor*, only what that person may see."""
    if actor is not None:
        _require_staff(actor, "list")
    where, params = [], []
    for col, val in (("c.pupil_id", pupil_id), ("c.status", status), ("c.source", source),
                     ("c.survey_id", survey_id)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if year_group not in (None, ""):
        where.append("p.year_group = ?")
        params.append(int(year_group))
    if action_only:
        where.append("c.action_needed = 1")
    if flagged_only:
        where.append("c.safeguarding_flag = 1")
    if date_from:
        where.append("c.checkin_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("c.checkin_date <= ?")
        params.append(date_to)
    sql = _CI_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY c.checkin_date DESC, c.checkin_id DESC LIMIT ?"
    with database.connect() as conn:
        rows = [_checkin_row(r) for r in conn.execute(sql, (*params, int(limit)))]
    if actor is None:
        return rows
    scope = _scope(actor)
    return [c for c in rows if _mine(scope, c.pupil_year, c.form_group)
            or _is_recorder(actor, c)]


def check_checkin(data: dict[str, Any]) -> list[str]:
    """Warnings before saving: safeguarding words, low ratings."""
    out: list[str] = []
    signs = safeguarding_signs(data.get("stressors"), data.get("notes"),
                               data.get("action_summary"), data.get("supports"))
    if signs:
        out.append(f"{SAFEGUARDING_ADVICE} (Mentions: {', '.join(signs)}.)")
    probs: list[str] = []
    low = [r for r in (_rating(data.get(k), k, probs) for k in
                       ("mood_rating", "confidence_rating", "connection_rating"))
           if r is not None and r <= LOW_THRESHOLD]
    if low and not _bool(data.get("action_needed") or False):
        out.append("A rating is at or below 2 - consider ticking 'action needed' and setting a "
                   "follow-up.")
    return out


def log_checkin(data: dict[str, Any], *, actor: Principal) -> CheckIn:
    """The old Log check-in. *data* carries ``pupil_id`` (id or admission no.).
    Any member of staff may log one."""
    _require_staff(actor, "log")
    problems: list[str] = []
    p = _need_pupil(data.get("pupil_id") or data.get("pupil"), problems)
    if p is not None and p.roll_status != "on_roll":
        problems.append(f"{p.display_name} is not on roll")
    c, more = _clean_checkin(data, None)
    problems += more
    survey = _survey_for(data.get("survey_id"), p, c["checkin_date"], problems)
    if problems:
        activity_log.record("wellbeing.log", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    if not c["recorded_by"]:
        c["recorded_by"] = _staff_name(actor)
    flag = bool(safeguarding_signs(c["stressors"], c["notes"], c["action_summary"],
                                   c["supports"]))
    with database.connect() as conn:
        cid = conn.execute(
            f"INSERT INTO wellbeing_checkins (pupil_id, {', '.join(CHECKIN_FIELDS)}, survey_id, "
            f"safeguarding_flag, created_by) VALUES (?, {', '.join('?' * len(CHECKIN_FIELDS))}, "
            "?, ?, ?)",
            (p.pupil_id, *(int(c[k]) if k == "action_needed" else c[k] for k in CHECKIN_FIELDS),
             survey, int(flag), actor.username)).lastrowid
        _audit(conn, "checkin", "log", actor, record_id=cid, pupil_id=p.pupil_id, flag=flag)
    activity_log.record("wellbeing.log", target=p.admission_no, principal=actor, checkin=cid)
    return get_checkin(cid)


def update(checkin_id: int, changes: dict[str, Any], *, actor: Principal) -> CheckIn:
    """The old Edit check-in: the lead, or whoever recorded it."""
    cur = get_checkin(checkin_id)
    if not can_edit_checkin(actor, cur):
        _deny(actor, "update", cur.admission_no, "Only the wellbeing lead or the person who "
                                                 "recorded it can change a check-in.")
    c, problems = _clean_checkin(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in CHECKIN_FIELDS if c[k] != getattr(cur, k)]
    if not changed:
        return cur
    flag = cur.safeguarding_flag or bool(safeguarding_signs(
        c["stressors"], c["notes"], c["action_summary"], c["supports"]))
    with database.connect() as conn:
        conn.execute("UPDATE wellbeing_checkins SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", safeguarding_flag = ?, updated_at = datetime('now') "
                       "WHERE checkin_id = ?",
                     (*(int(c[k]) if k == "action_needed" else c[k] for k in changed),
                      int(flag), cur.checkin_id))
        _audit(conn, "checkin", "update", actor, record_id=cur.checkin_id,
               pupil_id=cur.pupil_id, fields=changed)
    activity_log.record("wellbeing.update", target=cur.admission_no, principal=actor,
                        checkin=cur.checkin_id)
    return get_checkin(cur.checkin_id)


def set_status(checkin_id: int, status: str, *, actor: Principal) -> CheckIn:
    cur = get_checkin(checkin_id)
    if not (can_edit_checkin(actor, cur) or (actor.role in STAFF_ROLES and _mine(
            _scope(actor), cur.pupil_year, cur.form_group))):
        _deny(actor, "status", cur.admission_no, "You can't change this check-in.")
    problems: list[str] = []
    st = _choice(status, CHECKIN_STATUSES, "Status", problems, None)
    if problems or st is None:
        raise ValidationError(problems or ["Choose a status"])
    with database.connect() as conn:
        conn.execute("UPDATE wellbeing_checkins SET status = ?, updated_at = datetime('now') "
                     "WHERE checkin_id = ?", (st, cur.checkin_id))
        _audit(conn, "checkin", "status", actor, record_id=cur.checkin_id,
               pupil_id=cur.pupil_id, status=st)
    return get_checkin(cur.checkin_id)


def delete(checkin_id: int, *, actor: Principal) -> bool:
    c = get_checkin(checkin_id)
    _require_editor(actor, "delete", c.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM wellbeing_checkins WHERE checkin_id = ?", (c.checkin_id,))
        _audit(conn, "checkin", "delete", actor, record_id=c.checkin_id, pupil_id=c.pupil_id)
    activity_log.record("wellbeing.delete", target=c.admission_no, principal=actor,
                        checkin=c.checkin_id)
    return True


def _staff_name(actor: Principal) -> str:
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    return BH._staff_name(actor)


def _avg(rows: list[CheckIn], key: str) -> float | None:
    vals = [getattr(r, key) for r in rows if getattr(r, key) is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def pupil_summary(pupil_id: int, *, actor: Principal | None = None) -> dict[str, Any]:
    """The old pupil summary, plus referrals, plans and the trend."""
    rows = list_checkins(pupil_id=int(pupil_id))
    if actor is not None:
        p = P.get_pupil(int(pupil_id))
        if p is None:
            raise NotFound(f"No pupil {pupil_id}")
        if not can_see_pupil(actor, p):
            rows = [r for r in rows if _is_recorder(actor, r)]
    return {"pupil_id": int(pupil_id), "count": len(rows),
            "avg_mood": _avg(rows, "mood_rating"),
            "avg_confidence": _avg(rows, "confidence_rating"),
            "avg_connection": _avg(rows, "connection_rating"),
            "action_needed": sum(1 for r in rows if r.action_needed),
            "by_status": dict(Counter(r.status for r in rows)), "checkins": rows,
            "trend": trend(int(pupil_id)),
            "referrals": list_referrals(pupil_id=int(pupil_id)),
            "plans": list_plans(pupil_id=int(pupil_id))}


def cohort_summary(*, year_group: int | str | None = None, date_from: str | None = None,
                   date_to: str | None = None) -> dict[str, Any]:
    rows = list_checkins(year_group=year_group, date_from=date_from, date_to=date_to)
    return {"total": len(rows), "avg_mood": _avg(rows, "mood_rating"),
            "avg_confidence": _avg(rows, "confidence_rating"),
            "avg_connection": _avg(rows, "connection_rating"),
            "action_needed": sum(1 for r in rows if r.action_needed),
            "by_status": dict(Counter(r.status for r in rows)),
            "by_source": dict(Counter(r.source for r in rows)),
            "pupils": len({r.pupil_id for r in rows}),
            "flagged": sum(1 for r in rows if r.safeguarding_flag),
            "open_referrals": sum(1 for r in list_referrals(year_group=year_group)
                                  if r.is_open),
            "active_plans": len(list_plans(year_group=year_group, status="Active"))}


def low_wellbeing(*, threshold: int = LOW_THRESHOLD, year_group: int | str | None = None,
                  actor: Principal | None = None) -> dict[int, list[CheckIn]]:
    """``{pupil_id: [latest check-in]}`` where any rating of the pupil's latest
    check-in is at or below *threshold*."""
    if not MIN_RATING <= int(threshold) <= MAX_RATING:
        raise ValidationError([f"Threshold must be between {MIN_RATING} and {MAX_RATING}"])
    latest: dict[int, CheckIn] = {}
    for r in list_checkins(year_group=year_group, actor=actor):
        latest.setdefault(r.pupil_id, r)
    return {pid: [r] for pid, r in latest.items()
            if r.lowest is not None and r.lowest <= int(threshold)}


def trend(pupil_id: int, *, limit: int = 20) -> list[tuple[str, float]]:
    """(date, average rating) per check-in, oldest first."""
    rows = [r for r in list_checkins(pupil_id=pupil_id, limit=limit)
            if r.average_rating is not None]
    return [(r.checkin_date, r.average_rating) for r in reversed(rows)]  # type: ignore[misc]


def follow_ups(*, actor: Principal, include_future: bool = True) -> list[CheckIn]:
    """Open check-ins with a follow-up date, soonest first (overdue first)."""
    rows = [c for c in list_checkins(actor=actor) if c.status != "Closed" and c.follow_up_date
            and (include_future or c.follow_up_overdue)]
    return sorted(rows, key=lambda c: c.follow_up_date or "")


# ── Mood surveys ─────────────────────────────────────────────────────

def _survey_for(ref: Any, p: P.Pupil | None, day: str, problems: list[str]) -> int | None:
    if ref in (None, "") or p is None:
        return None
    try:
        s = get_survey(int(str(ref).strip()))
    except (ValueError, NotFound):
        problems.append(f"No survey #{ref}")
        return None
    if not in_survey(s, p):
        problems.append(f"{p.display_name} isn't in the survey '{s.title}'")
    if not s.open_date <= day <= s.close_date:
        problems.append(f"The survey runs {s.open_date} to {s.close_date}")
    return s.survey_id


def in_survey(s: Survey, p: P.Pupil) -> bool:
    if s.form_group:
        return (p.form_group or "").upper() == s.form_group.upper()
    return not s.year_group or p.year_group == s.year_group


def get_survey(survey_id: int) -> Survey:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM wellbeing_surveys WHERE survey_id = ?",
                         (int(survey_id),)).fetchone()
    if r is None:
        raise NotFound(f"No survey #{survey_id}")
    return _survey_row(r)


def list_surveys(*, status: str | None = None) -> list[Survey]:
    sql, params = "SELECT * FROM wellbeing_surveys", []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    with database.connect() as conn:
        return [_survey_row(r) for r in conn.execute(
            sql + " ORDER BY open_date DESC, survey_id DESC", params)]


def save_survey(data: dict[str, Any], *, actor: Principal, survey_id: int | None = None
                ) -> Survey:
    """Create or change a survey round (the lead)."""
    _require_editor(actor, "survey")
    cur = get_survey(survey_id) if survey_id else None
    merged = {k: getattr(cur, k) for k in ("title", "year_group", "form_group", "open_date",
                                           "close_date", "status", "question")} if cur else {}
    merged.update(data)
    problems: list[str] = []
    title = _text(merged.get("title"), 120)
    if not title:
        problems.append("Title is required")
    yg = merged.get("year_group")
    year = None
    if yg not in (None, ""):
        try:
            year = int(str(yg).strip())
            if not 7 <= year <= 11:
                problems.append("Year group must be 7 to 11")
        except ValueError:
            problems.append("Year group must be a number")
    form = _text(merged.get("form_group"), 20)
    o = _date(merged.get("open_date"), "Opens", problems) or _today().isoformat()
    c = _date(merged.get("close_date"), "Closes", problems)
    if not c:
        c = (_dt.date.fromisoformat(o) + _dt.timedelta(days=7)).isoformat()
    if c < o:
        problems.append("The survey can't close before it opens")
    st = _choice(merged.get("status"), SURVEY_STATUSES, "Status", problems, "Draft")
    if problems:
        raise ValidationError(problems)
    vals = (title, year, form, o, c, st, _text(merged.get("question"), 300))
    with database.connect() as conn:
        if cur:
            conn.execute("UPDATE wellbeing_surveys SET title = ?, year_group = ?, form_group = ?,"
                         " open_date = ?, close_date = ?, status = ?, question = ? "
                         "WHERE survey_id = ?", (*vals, cur.survey_id))
            sid = cur.survey_id
        else:
            sid = conn.execute("INSERT INTO wellbeing_surveys (title, year_group, form_group, "
                               "open_date, close_date, status, question, created_by) VALUES "
                               "(?, ?, ?, ?, ?, ?, ?, ?)", (*vals, actor.username)).lastrowid
        _audit(conn, "survey", "save", actor, record_id=sid, status=st)
    return get_survey(sid)


def delete_survey(survey_id: int, *, actor: Principal) -> bool:
    s = get_survey(survey_id)
    _require_editor(actor, "survey_delete")
    with database.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM wellbeing_checkins WHERE survey_id = ?",
                         (s.survey_id,)).fetchone()[0]
        if n:
            raise ValidationError([f"{n} response(s) have been recorded - close the survey "
                                   "instead"])
        conn.execute("DELETE FROM wellbeing_surveys WHERE survey_id = ?", (s.survey_id,))
        _audit(conn, "survey", "delete", actor, record_id=s.survey_id)
    return True


def survey_pupils(s: Survey) -> list[P.Pupil]:
    return [p for p in P.list_pupils(year_group=s.year_group or None) if in_survey(s, p)]


def survey_results(survey_id: int, *, threshold: int = LOW_THRESHOLD) -> dict[str, Any]:
    """Response rate, averages, low scorers and who hasn't answered."""
    s = get_survey(survey_id)
    rows = list_checkins(survey_id=s.survey_id)
    latest: dict[int, CheckIn] = {}
    for r in rows:
        latest.setdefault(r.pupil_id, r)
    pupils = survey_pupils(s)
    answered = [r for r in latest.values()]
    return {"survey": s, "pupils": len(pupils), "responses": len(answered),
            "rate": round(100.0 * len(answered) / len(pupils), 1) if pupils else None,
            "avg_mood": _avg(answered, "mood_rating"),
            "avg_confidence": _avg(answered, "confidence_rating"),
            "avg_connection": _avg(answered, "connection_rating"),
            "low": [r for r in answered if r.lowest is not None and r.lowest <= threshold],
            "flagged": [r for r in answered if r.safeguarding_flag],
            "missing": [p for p in pupils if p.pupil_id not in latest]}


def open_surveys_for(pupil: P.Pupil, day: _dt.date | None = None) -> list[Survey]:
    return [s for s in list_surveys(status="Open") if s.is_open_on(day) and in_survey(s, pupil)]


def self_check_in(principal: Principal, pupil_id: int, data: dict[str, Any]) -> CheckIn:
    """A pupil answers for themselves from the portal (mood ratings and an
    optional note). Linked to the open survey for their year / form if any."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    if not principal.is_student or int(pupil_id) not in {
            p.pupil_id for p in PA.pupils_for(principal, "pupil")}:
        _deny(principal, "self", f"id:{pupil_id}", "You can only check in for yourself.")
    p = P.get_pupil(int(pupil_id))
    problems: list[str] = []
    c, more = _clean_checkin({k: data.get(k) for k in ("mood_rating", "confidence_rating",
                                                       "connection_rating", "notes")}, None)
    problems += more
    if problems:
        raise ValidationError(problems)
    surveys = open_surveys_for(p)
    flag = bool(safeguarding_signs(c["notes"]))
    low = c["mood_rating"] is not None and c["mood_rating"] <= LOW_THRESHOLD or (
        c["connection_rating"] is not None and c["connection_rating"] <= LOW_THRESHOLD)
    with database.connect() as conn:
        cid = conn.execute(
            "INSERT INTO wellbeing_checkins (pupil_id, checkin_date, source, mood_rating, "
            "confidence_rating, connection_rating, notes, action_needed, action_summary, "
            "recorded_by, status, survey_id, safeguarding_flag, created_by) VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?)",
            (p.pupil_id, _today().isoformat(), "Mood survey" if surveys else "Self check-in",
             c["mood_rating"], c["confidence_rating"], c["connection_rating"], c["notes"],
             int(low or flag), "Pupil self-report: low score or words to check" if
             (low or flag) else None, "Pupil (portal)",
             surveys[0].survey_id if surveys else None, int(flag), principal.username)
        ).lastrowid
        _audit(conn, "checkin", "self", principal, record_id=cid, pupil_id=p.pupil_id,
               flag=flag)
    activity_log.record("wellbeing.self", target=p.admission_no, principal=principal)
    return get_checkin(cid)


# ── Referrals ────────────────────────────────────────────────────────

REFERRAL_FIELDS = ("service", "referral_date", "reason", "urgency", "consent", "status",
                   "accepted_date", "first_appointment", "closed_date", "outcome",
                   "outcome_notes", "contact_name")
_RF_SELECT = f"SELECT r.*, {_PUPIL_COLS} FROM wellbeing_referrals r JOIN pupils p USING " \
             "(pupil_id)"


def _clean_referral(data: dict[str, Any], cur: Referral | None
                    ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(cur, k) for k in REFERRAL_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in REFERRAL_FIELDS})
    out: dict[str, Any] = {}
    out["service"] = _choice(merged.get("service"), SERVICES, "Service", problems, None)
    if not out["service"] and not any(p.startswith("Service") for p in problems):
        problems.append("Service is required")
    out["urgency"] = _choice(merged.get("urgency"), URGENCIES, "Urgency", problems, "Routine")
    out["consent"] = _choice(merged.get("consent"), CONSENTS, "Consent", problems,
                             "Pupil and parent")
    out["status"] = _choice(merged.get("status"), REFERRAL_STATUSES, "Status", problems,
                            "Referred")
    out["outcome"] = _choice(merged.get("outcome"), REFERRAL_OUTCOMES, "Outcome", problems,
                             None)
    for k, label in (("referral_date", "Referral date"), ("accepted_date", "Accepted"),
                     ("first_appointment", "First appointment"), ("closed_date", "Closed")):
        out[k] = _date(merged.get(k), label, problems)
    out["referral_date"] = out["referral_date"] or _today().isoformat()
    if out["referral_date"] > _today().isoformat():
        problems.append("Referral date can't be in the future")
    for k in ("accepted_date", "first_appointment", "closed_date"):
        if out[k] and out[k] < out["referral_date"]:
            problems.append(f"{k.replace('_', ' ').capitalize()} can't be before the referral")
    out["reason"] = _text(merged.get("reason"), 2000)
    if not out["reason"]:
        problems.append("Reason is required")
    out["outcome_notes"] = _text(merged.get("outcome_notes"), 2000)
    out["contact_name"] = _text(merged.get("contact_name"), 120)
    if out["consent"] == "Refused" and out["status"] not in ("Withdrawn", "Declined") and \
            out["urgency"] != "Emergency":
        problems.append("Consent was refused - the referral can't go ahead (record it as "
                        "Withdrawn), unless it is an emergency")
    if out["status"] in REFERRAL_CLOSED and not out["closed_date"]:
        out["closed_date"] = _today().isoformat()
    if out["status"] == "Completed" and not out["outcome"]:
        problems.append("Record the outcome when the referral is completed")
    if out["status"] in ("Accepted", "In progress") and not out["accepted_date"]:
        out["accepted_date"] = _today().isoformat()
    return out, problems


def get_referral(referral_id: int) -> Referral:
    with database.connect() as conn:
        r = conn.execute(_RF_SELECT + " WHERE r.referral_id = ?", (int(referral_id),)).fetchone()
    if r is None:
        raise NotFound(f"No referral #{referral_id}")
    return _make(Referral, r)


def can_see_referrals(actor: Principal, year: int) -> bool:
    return is_editor(actor) or (actor.role in STAFF_ROLES and is_head_of_year_for(actor, year))


def list_referrals(*, actor: Principal | None = None, pupil_id: int | None = None,
                   service: str | None = None, status: str | None = None,
                   year_group: int | str | None = None, open_only: bool = False
                   ) -> list[Referral]:
    where, params = [], []
    for col, val in (("r.pupil_id", pupil_id), ("r.service", service), ("r.status", status)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if year_group not in (None, ""):
        where.append("p.year_group = ?")
        params.append(int(year_group))
    if open_only:
        where.append("r.status NOT IN ('Declined', 'Completed', 'Withdrawn')")
    sql = _RF_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY CASE r.urgency WHEN 'Emergency' THEN 0 WHEN 'Urgent' THEN 1 ELSE 2 END, " \
        "r.referral_date DESC"
    with database.connect() as conn:
        rows = [_make(Referral, r) for r in conn.execute(sql, params)]
    if actor is None:
        return rows
    _require_staff(actor, "referrals")
    return [r for r in rows if can_see_referrals(actor, r.pupil_year)]


def create_referral(data: dict[str, Any], *, actor: Principal) -> Referral:
    _require_editor(actor, "referral")
    problems: list[str] = []
    p = _need_pupil(data.get("pupil_id") or data.get("pupil"), problems)
    c, more = _clean_referral(data, None)
    problems += more
    ci = data.get("checkin_id")
    checkin = None
    if ci not in (None, ""):
        try:
            checkin = get_checkin(int(str(ci)))
            if p and checkin.pupil_id != p.pupil_id:
                problems.append(f"Check-in #{ci} is for another pupil")
        except (ValueError, NotFound):
            problems.append(f"No check-in #{ci}")
    if p and c["service"] and not problems:
        dup = [r for r in list_referrals(pupil_id=p.pupil_id, service=c["service"],
                                         open_only=True)]
        if dup:
            problems.append(f"{p.display_name} already has an open referral to "
                            f"{c['service']} (#{dup[0].referral_id})")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        rid = conn.execute(
            f"INSERT INTO wellbeing_referrals (pupil_id, {', '.join(REFERRAL_FIELDS)}, "
            f"checkin_id, referred_by) VALUES (?, {', '.join('?' * len(REFERRAL_FIELDS))}, ?, ?)",
            (p.pupil_id, *(c[k] for k in REFERRAL_FIELDS),
             checkin.checkin_id if checkin else None, actor.username)).lastrowid
        if checkin and checkin.status == "Open":
            conn.execute("UPDATE wellbeing_checkins SET status = 'Escalated', "
                         "updated_at = datetime('now') WHERE checkin_id = ?",
                         (checkin.checkin_id,))
        _audit(conn, "referral", "create", actor, record_id=rid, pupil_id=p.pupil_id,
               service=c["service"])
    activity_log.record("wellbeing.referral", target=p.admission_no, principal=actor,
                        referral=rid)
    return get_referral(rid)


def update_referral(referral_id: int, changes: dict[str, Any], *, actor: Principal
                    ) -> Referral:
    cur = get_referral(referral_id)
    _require_editor(actor, "referral_update", cur.admission_no)
    c, problems = _clean_referral(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in REFERRAL_FIELDS if c[k] != getattr(cur, k)]
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE wellbeing_referrals SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_at = datetime('now') WHERE referral_id = ?",
                     (*(c[k] for k in changed), cur.referral_id))
        _audit(conn, "referral", "update", actor, record_id=cur.referral_id,
               pupil_id=cur.pupil_id, fields=changed)
    return get_referral(cur.referral_id)


def delete_referral(referral_id: int, *, actor: Principal) -> bool:
    r = get_referral(referral_id)
    _require_editor(actor, "referral_delete", r.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM wellbeing_referrals WHERE referral_id = ?", (r.referral_id,))
        _audit(conn, "referral", "delete", actor, record_id=r.referral_id, pupil_id=r.pupil_id)
    return True


def referral_report(*, year_group: int | str | None = None) -> list[dict[str, Any]]:
    """By service: referrals, open, accepted, average wait (days to first
    appointment), outcomes."""
    out: dict[str, dict[str, Any]] = {}
    for r in list_referrals(year_group=year_group):
        g = out.setdefault(r.service, {"service": r.service, "referrals": 0, "open": 0,
                                       "accepted": 0, "waits": [], "outcomes": Counter()})
        g["referrals"] += 1
        g["open"] += int(r.is_open)
        g["accepted"] += int(bool(r.accepted_date))
        if r.first_appointment:
            g["waits"].append(r.waiting_days)
        if r.outcome:
            g["outcomes"][r.outcome] += 1
    for g in out.values():
        w = g.pop("waits")
        g["avg_wait"] = round(sum(w) / len(w), 1) if w else None
        g["outcomes"] = dict(g["outcomes"])
    return sorted(out.values(), key=lambda g: -g["referrals"])


# ── Support plans ────────────────────────────────────────────────────

PLAN_FIELDS = ("start_date", "review_date", "status", "need", "strategies", "staff_actions",
               "pupil_actions", "family_actions", "key_adult", "closed_date", "outcome")
_PL_SELECT = f"SELECT w.*, {_PUPIL_COLS} FROM wellbeing_plans w JOIN pupils p USING (pupil_id)"


def _clean_plan(data: dict[str, Any], cur: Plan | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(cur, k) for k in PLAN_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in PLAN_FIELDS})
    out: dict[str, Any] = {}
    out["start_date"] = _date(merged.get("start_date"), "Start date", problems) \
        or _today().isoformat()
    out["review_date"] = _date(merged.get("review_date"), "Review date", problems) or (
        _dt.date.fromisoformat(out["start_date"]) + _dt.timedelta(weeks=6)).isoformat()
    if out["review_date"] <= out["start_date"]:
        problems.append("The review date must be after the start date")
    out["status"] = _choice(merged.get("status"), PLAN_STATUSES, "Status", problems, "Active")
    out["closed_date"] = _date(merged.get("closed_date"), "Closed date", problems)
    if out["status"] == "Closed" and not out["closed_date"]:
        out["closed_date"] = _today().isoformat()
    if out["status"] == "Active":
        out["closed_date"] = None
    out["need"] = _text(merged.get("need"), 2000)
    if not out["need"]:
        problems.append("Describe the need")
    for k in ("strategies", "staff_actions", "pupil_actions", "family_actions", "outcome"):
        out[k] = _text(merged.get(k), 4000)
    out["key_adult"] = _text(merged.get("key_adult"), 80)
    if out["status"] == "Active" and not (out["strategies"] or out["staff_actions"]):
        problems.append("Add the strategies or the staff actions")
    return out, problems


def get_plan(plan_id: int) -> Plan:
    with database.connect() as conn:
        r = conn.execute(_PL_SELECT + " WHERE w.plan_id = ?", (int(plan_id),)).fetchone()
    if r is None:
        raise NotFound(f"No support plan #{plan_id}")
    return _make(Plan, r)


def list_plans(*, actor: Principal | None = None, pupil_id: int | None = None,
               status: str | None = None, year_group: int | str | None = None,
               key_adult: str | None = None) -> list[Plan]:
    where, params = [], []
    for col, val in (("w.pupil_id", pupil_id), ("w.status", status), ("w.key_adult", key_adult)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if year_group not in (None, ""):
        where.append("p.year_group = ?")
        params.append(int(year_group))
    sql = _PL_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY w.status, w.review_date"
    with database.connect() as conn:
        rows = [_make(Plan, r) for r in conn.execute(sql, params)]
    if actor is None:
        return rows
    _require_staff(actor, "plans")
    scope = _scope(actor)
    return [w for w in rows if _mine(scope, w.pupil_year, w.form_group)]


def create_plan(data: dict[str, Any], *, actor: Principal) -> Plan:
    _require_editor(actor, "plan")
    problems: list[str] = []
    p = _need_pupil(data.get("pupil_id") or data.get("pupil"), problems)
    c, more = _clean_plan(data, None)
    problems += more
    if p and not problems and list_plans(pupil_id=p.pupil_id, status="Active"):
        problems.append(f"{p.display_name} already has an active support plan - review or "
                        "change it")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        pid = conn.execute(
            f"INSERT INTO wellbeing_plans (pupil_id, {', '.join(PLAN_FIELDS)}, created_by) "
            f"VALUES (?, {', '.join('?' * len(PLAN_FIELDS))}, ?)",
            (p.pupil_id, *(c[k] for k in PLAN_FIELDS), actor.username)).lastrowid
        _audit(conn, "plan", "create", actor, record_id=pid, pupil_id=p.pupil_id)
    activity_log.record("wellbeing.plan", target=p.admission_no, principal=actor, plan=pid)
    return get_plan(pid)


def update_plan(plan_id: int, changes: dict[str, Any], *, actor: Principal) -> Plan:
    cur = get_plan(plan_id)
    _require_editor(actor, "plan_update", cur.admission_no)
    c, problems = _clean_plan(changes, cur)
    if problems:
        raise ValidationError(problems)
    changed = [k for k in PLAN_FIELDS if c[k] != getattr(cur, k)]
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE wellbeing_plans SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_at = datetime('now') WHERE plan_id = ?",
                     (*(c[k] for k in changed), cur.plan_id))
        _audit(conn, "plan", "update", actor, record_id=cur.plan_id, pupil_id=cur.pupil_id,
               fields=changed)
    return get_plan(cur.plan_id)


def review_plan(plan_id: int, *, actor: Principal, summary: str,
                next_review: str | None = None, close: bool = False,
                outcome: str | None = None) -> Plan:
    """Record a review; sets the next review (default 6 weeks) or closes."""
    cur = get_plan(plan_id)
    _require_editor(actor, "plan_review", cur.admission_no)
    problems: list[str] = []
    text = " ".join(str(summary or "").split())
    if not text:
        problems.append("Summary is required")
    if cur.status != "Active":
        problems.append("The plan is closed")
    nxt = _date(next_review, "Next review", problems)
    today = _today().isoformat()
    if nxt and nxt <= today:
        problems.append("The next review must be in the future")
    if close and not (outcome or "").strip():
        problems.append("Give the outcome when closing the plan")
    if problems:
        raise ValidationError(problems)
    nxt = nxt or (_today() + _dt.timedelta(weeks=6)).isoformat()
    with database.connect() as conn:
        conn.execute("INSERT INTO wellbeing_plan_reviews (plan_id, review_date, summary, "
                     "next_review, reviewed_by) VALUES (?, ?, ?, ?, ?)",
                     (cur.plan_id, today, text[:2000], None if close else nxt, actor.username))
        if close:
            conn.execute("UPDATE wellbeing_plans SET status = 'Closed', closed_date = ?, "
                         "outcome = ?, updated_at = datetime('now') WHERE plan_id = ?",
                         (today, outcome.strip()[:4000], cur.plan_id))
        else:
            conn.execute("UPDATE wellbeing_plans SET review_date = ?, updated_at = "
                         "datetime('now') WHERE plan_id = ?", (nxt, cur.plan_id))
        _audit(conn, "plan", "review", actor, record_id=cur.plan_id, pupil_id=cur.pupil_id,
               closed=close)
    return get_plan(cur.plan_id)


def plan_reviews(plan_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM wellbeing_plan_reviews WHERE plan_id = ? ORDER BY review_id",
            (int(plan_id),))]


def delete_plan(plan_id: int, *, actor: Principal) -> bool:
    w = get_plan(plan_id)
    _require_editor(actor, "plan_delete", w.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM wellbeing_plans WHERE plan_id = ?", (w.plan_id,))
        _audit(conn, "plan", "delete", actor, record_id=w.plan_id, pupil_id=w.pupil_id)
    return True


# ── Caseload ─────────────────────────────────────────────────────────

def caseload(*, actor: Principal, key_adult: str | None = None,
             year_group: int | str | None = None) -> list[dict[str, Any]]:
    """Every pupil with an open check-in, open referral or active plan:
    {'pupil_id', 'pupil_name', 'admission_no', 'year', 'form', 'latest',
    'latest_date', 'trend' ('up', 'down', 'steady', ''), 'open_checkins',
    'follow_up', 'referrals' [service], 'plan' (Plan or None), 'review_due',
    'flagged', 'key_adult'}; most worrying first."""
    _require_staff(actor, "caseload")
    checkins = list_checkins(actor=actor, year_group=year_group)
    refs = list_referrals(actor=actor, year_group=year_group, open_only=True) \
        if is_editor(actor) or _scope(actor)[0] else []  # type: ignore[index]
    plans = list_plans(actor=actor, year_group=year_group, status="Active")
    out: dict[int, dict[str, Any]] = {}

    def entry(x) -> dict[str, Any]:
        return out.setdefault(x.pupil_id, {
            "pupil_id": x.pupil_id, "pupil_name": x.pupil_name, "admission_no": x.admission_no,
            "year": x.pupil_year, "form": x.form_group, "latest": None, "latest_date": None,
            "trend": "", "open_checkins": 0, "follow_up": None, "referrals": [], "plan": None,
            "review_due": False, "flagged": False, "key_adult": None})
    by_pupil: dict[int, list[CheckIn]] = {}
    for c in checkins:
        by_pupil.setdefault(c.pupil_id, []).append(c)
    for pid, rows in by_pupil.items():
        open_rows = [c for c in rows if c.status != "Closed"]
        if not open_rows:
            continue
        e = entry(rows[0])
        e["latest"], e["latest_date"] = rows[0].average_rating, rows[0].checkin_date
        scores = [c.average_rating for c in rows[:3] if c.average_rating is not None]
        if len(scores) >= 2:
            e["trend"] = "up" if scores[0] > scores[-1] else (
                "down" if scores[0] < scores[-1] else "steady")
        e["open_checkins"] = len(open_rows)
        fu = sorted(c.follow_up_date for c in open_rows if c.follow_up_date)
        e["follow_up"] = fu[0] if fu else None
        e["flagged"] = any(c.safeguarding_flag for c in open_rows)
        e["key_adult"] = next((c.follow_up_with for c in open_rows if c.follow_up_with), None)
    for r in refs:
        entry(r)["referrals"].append(r.service)
    for w in plans:
        e = entry(w)
        e["plan"], e["review_due"] = w, w.review_due
        e["key_adult"] = w.key_adult or e["key_adult"]
    rows = list(out.values())
    if key_adult:
        k = key_adult.strip().lower()
        rows = [e for e in rows if (e["key_adult"] or "").lower() == k]
    return sorted(rows, key=lambda e: (not e["flagged"], e["latest"] if e["latest"] is not None
                                       else 9, e["pupil_name"]))


def for_pupil(pupil_id: int, *, actor: Principal) -> dict[str, Any]:
    """The pupil profile box: latest score, open referrals, active plan."""
    p = P.get_pupil(int(pupil_id))
    if p is None or not can_see_pupil(actor, p):
        return {"visible": False}
    rows = list_checkins(pupil_id=p.pupil_id, limit=5)
    plans = list_plans(pupil_id=p.pupil_id, status="Active")
    return {"visible": True, "latest": rows[0] if rows else None,
            "trend": trend(p.pupil_id, limit=6),
            "referrals": [r for r in list_referrals(pupil_id=p.pupil_id, open_only=True)]
            if can_see_referrals(actor, p.year_group) else [],
            "plan": plans[0] if plans else None}


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_checkins(actor=actor, **filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "date", "admission_no", "pupil", "year", "form", "source", "mood",
                    "confidence", "connection", "average", "action_needed", "status",
                    "follow_up", "follow_up_with", "recorded_by", "survey", "flagged"])
        for c in rows:
            w.writerow([c.checkin_id, c.checkin_date, _safe(c.admission_no),
                        _safe(c.pupil_name), c.pupil_year, _safe(c.form_group), c.source,
                        c.mood_rating or "", c.confidence_rating or "", c.connection_rating or "",
                        c.average_rating if c.average_rating is not None else "",
                        "yes" if c.action_needed else "", c.status, c.follow_up_date or "",
                        _safe(c.follow_up_with), _safe(c.recorded_by), c.survey_id or "",
                        "yes" if c.safeguarding_flag else ""])
    activity_log.record("wellbeing.export", principal=actor, rows=len(rows))
    return len(rows)
