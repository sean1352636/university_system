"""Safeguarding: the DSL's child-protection record (one store for concerns).

Kept from the old Safeguarding screen:

* A concern per pupil with category, severity (Low, Medium, High, Critical),
  incident date and time (HH:MM), location, description (required), raised
  by, raised date (default today), DSL reviewer and review date, status
  (Open, Monitoring, Referred, Escalated, Closed, Transferred), referral body
  / date / reference, outcome (required to close), closed date (not before
  the raised date), confidential and notes.
* A dated log of actions on each concern (DSL meeting, Pupil interview,
  Parent contact, ... Other) with actioned by, summary (required), outcome
  and follow-up.
* The concern summary, the cohort summary and pupils with open concerns
  (in :mod:`safeguarding_reports`).

New, following Keeping Children Safe in Education:

* **Need to know.** Every member of staff can *report* a concern
  (:func:`report_concern`) and see the status of the concerns they reported
  (:func:`my_reports`) - never anyone else's, and never the DSL's notes.
  Everything else is for :data:`SAFEGUARDING_LEADS` (the DSL and deputies).
  Every read of a pupil's record by a lead is written to
  ``safeguarding_access`` (:func:`access_log`); every change to
  ``safeguarding_audit`` (:func:`history`). The activity log gets ids only.
* **Reporting.** What was seen or heard, the child's own words, when and
  where, a body-map note of any injury, the immediate action taken, who else
  was involved, and whether the child is in immediate danger (urgent). A new
  report is ``New`` until a lead triages it (:func:`triage`): category,
  severity and the level of need / action (:data:`LEVELS`).
* **Urgent.** An urgent report e-mails the safeguarding team through the
  school outbox (no details of the concern in the e-mail); when nobody on the
  team has an e-mail address the concern records that the DSL must be
  phoned.
* **Actions** have an owner and a due date; :func:`due` lists what is
  overdue or coming up (:mod:`safeguarding_reports`). **Referrals**
  (children's social care, police, LADO, Channel, early help...) are their own records with an outcome; the old
  referral fields on a concern read and write its latest referral.
* **Closing and reopening** a concern (reason required to reopen).
* The DSL's team (:func:`team`): who the leads are and how to reach them.

Plans and flags (child protection, child in need, early help, looked after),
the Prevent details of a radicalisation concern, the pupil's chronology and
the transfer file are in :mod:`safeguarding_records`; what's due, the
summaries, reports and CSV export in :mod:`safeguarding_reports`. Their
tables are all here, so there is one schema and one store.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P  # registers the FK target
from education_system.systems.secondary.core.permissions.access import (
    SAFEGUARDING_LEADS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

#: Keeping Children Safe in Education categories, then the old extra ones.
CONCERN_CATEGORIES: tuple[str, ...] = (
    "Physical abuse", "Emotional abuse", "Sexual abuse", "Neglect",
    "Child-on-child abuse", "Online safety", "CSE (Child Sexual Exploitation)",
    "CCE (Child Criminal Exploitation)", "Radicalisation / Prevent", "FGM",
    "Forced marriage", "Domestic abuse", "Mental health", "Self-harm",
    "Substance misuse", "Bullying", "Missing education", "Disclosure", "Other")
DEFAULT_CATEGORY = "Disclosure"
PREVENT = "Radicalisation / Prevent"
#: The old names, still accepted.
_CATEGORY_ALIASES = {"domestic abuse exposure": "Domestic abuse",
                     "prevent / radicalisation": PREVENT,
                     "missing from education": "Missing education"}

SEVERITIES: tuple[str, ...] = ("Low", "Medium", "High", "Critical")
DEFAULT_SEVERITY = "Medium"

NEW = "New"
CONCERN_STATUSES: tuple[str, ...] = (
    "Open", "Monitoring", "Referred", "Escalated", "Closed", "Transferred", NEW)
DEFAULT_STATUS = "Open"
#: A concern in one of these is finished with.
FINISHED = frozenset({"Closed", "Transferred"})

#: Level of need / the action the DSL decides on.
LEVELS: tuple[str, ...] = (
    "Monitor", "Early help", "Referral to children's social care", "Police",
    "LADO (allegation against staff)", "Prevent / Channel", "No further action")
LADO_LEVEL = "LADO (allegation against staff)"

REFERRAL_BODIES: tuple[str, ...] = (
    "MASH / Social Care", "Police", "CAMHS", "Early Help", "Channel (Prevent)",
    "Local Authority", "External agency", "Internal only", "Other", "LADO")
REFERRAL_OUTCOMES: tuple[str, ...] = (
    "Pending", "Accepted - assessment", "Section 47 enquiry", "Child in need (section 17)",
    "Child protection plan", "Early help", "Channel support", "Stepped down",
    "No further action", "Other")

ACTION_TYPES: tuple[str, ...] = (
    "DSL meeting", "Pupil interview", "Parent contact", "Multi-agency referral",
    "Police referral", "Strategy meeting", "Internal escalation", "Letter sent",
    "Phone call", "Home visit", "Follow-up review", "Other",
    "Triage", "Referral", "Referral outcome", "Further information", "Plan meeting",
    "Child protection conference", "Case closed", "Case reopened", "Record transferred")
DEFAULT_ACTION_TYPE = "DSL meeting"

TEAM_ROLES: tuple[str, ...] = ("DSL", "Deputy DSL", "Safeguarding officer")

#: What a member of staff sees for the concerns they reported.
REPORTER_STATUS = {NEW: "Received - waiting for the DSL", "Open": "With the DSL",
                   "Monitoring": "With the DSL", "Referred": "With the DSL",
                   "Escalated": "With the DSL", "Closed": "Closed",
                   "Transferred": "Closed"}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
MAX_TEXT = 8000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS safeguarding_concerns (
    concern_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id          INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE RESTRICT,
    category          TEXT NOT NULL DEFAULT 'Disclosure',
    severity          TEXT NOT NULL DEFAULT 'Medium'
                      CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    incident_date     TEXT,
    incident_time     TEXT,
    location          TEXT,
    description       TEXT NOT NULL,
    child_words       TEXT,
    body_map          TEXT,
    immediate_action  TEXT,
    people_involved   TEXT,
    immediate_danger  INTEGER NOT NULL DEFAULT 0,
    urgent            INTEGER NOT NULL DEFAULT 0,
    raised_by         TEXT,
    reported_by       TEXT,
    raised_date       TEXT NOT NULL DEFAULT (date('now')),
    dsl_reviewer      TEXT,
    review_date       TEXT,
    level_of_need     TEXT,
    status            TEXT NOT NULL DEFAULT 'Open' CHECK (status IN
                      ('Open', 'Monitoring', 'Referred', 'Escalated', 'Closed',
                       'Transferred', 'New')),
    allegation_about  TEXT,
    outcome           TEXT,
    closed_date       TEXT,
    confidential      INTEGER NOT NULL DEFAULT 1,
    notes             TEXT,
    notified_at       TEXT,
    notified_count    INTEGER NOT NULL DEFAULT 0,
    needs_phone_call  INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by        TEXT,
    updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_sg_concerns_pupil ON safeguarding_concerns (pupil_id);
CREATE INDEX IF NOT EXISTS ix_sg_concerns_status ON safeguarding_concerns (status);
CREATE INDEX IF NOT EXISTS ix_sg_concerns_reporter ON safeguarding_concerns (reported_by);
CREATE TABLE IF NOT EXISTS safeguarding_actions (
    action_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id     INTEGER NOT NULL REFERENCES safeguarding_concerns (concern_id)
                   ON DELETE CASCADE,
    action_date    TEXT NOT NULL DEFAULT (date('now')),
    action_type    TEXT NOT NULL DEFAULT 'DSL meeting',
    actioned_by    TEXT,
    summary        TEXT NOT NULL,
    outcome        TEXT,
    follow_up      TEXT,
    due_date       TEXT,
    assigned_to    TEXT,
    completed_date TEXT,
    created_by     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_sg_actions_concern ON safeguarding_actions (concern_id);
CREATE TABLE IF NOT EXISTS safeguarding_referrals (
    referral_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id     INTEGER NOT NULL REFERENCES safeguarding_concerns (concern_id)
                   ON DELETE CASCADE,
    agency         TEXT NOT NULL,
    referral_date  TEXT NOT NULL,
    reference      TEXT,
    reason         TEXT,
    made_by        TEXT,
    outcome        TEXT NOT NULL DEFAULT 'Pending',
    outcome_date   TEXT,
    outcome_notes  TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_sg_referrals_concern ON safeguarding_referrals (concern_id);
CREATE TABLE IF NOT EXISTS safeguarding_plans (
    plan_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id        INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE RESTRICT,
    plan_type       TEXT NOT NULL,
    category        TEXT,
    start_date      TEXT NOT NULL,
    end_date        TEXT,
    local_authority TEXT,
    social_worker   TEXT,
    contact         TEXT,
    next_review     TEXT,
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_sg_plans_pupil ON safeguarding_plans (pupil_id);
CREATE TABLE IF NOT EXISTS safeguarding_prevent (
    concern_id            INTEGER PRIMARY KEY REFERENCES safeguarding_concerns (concern_id)
                          ON DELETE CASCADE,
    prevent_type          TEXT NOT NULL,
    risk_level            TEXT NOT NULL DEFAULT 'Low',
    indicators            TEXT,
    online_activity       TEXT,
    pathway               TEXT NOT NULL DEFAULT 'Internal monitoring',
    agencies_involved     TEXT,
    parents_informed_date TEXT,
    next_review_date      TEXT,
    channel_status        TEXT NOT NULL DEFAULT 'Open',
    prevent_outcome       TEXT NOT NULL DEFAULT 'Pending',
    closure_notes         TEXT
);
CREATE TABLE IF NOT EXISTS safeguarding_transfers (
    transfer_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id         INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE RESTRICT,
    destination      TEXT NOT NULL,
    method           TEXT NOT NULL,
    sent_date        TEXT NOT NULL,
    sent_by          TEXT,
    received_date    TEXT,
    received_by_name TEXT,
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_sg_transfers_pupil ON safeguarding_transfers (pupil_id);
CREATE TABLE IF NOT EXISTS safeguarding_team (
    username     TEXT PRIMARY KEY,
    display_name TEXT,
    team_role    TEXT NOT NULL DEFAULT 'Deputy DSL',
    phone        TEXT,
    email        TEXT,
    added_by     TEXT,
    added_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS safeguarding_access (
    access_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL DEFAULT (datetime('now')),
    username   TEXT NOT NULL,
    role       TEXT,
    pupil_id   INTEGER,
    concern_id INTEGER,
    what       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sg_access_pupil ON safeguarding_access (pupil_id);
CREATE TABLE IF NOT EXISTS safeguarding_audit (
    audit_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id INTEGER,
    pupil_id   INTEGER,
    action     TEXT NOT NULL,
    detail     TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("safeguarding", _SCHEMA)


@dataclass(frozen=True)
class Concern:
    concern_id: int
    pupil_id: int
    category: str
    severity: str
    incident_date: str | None
    incident_time: str | None
    location: str | None
    description: str
    child_words: str | None
    body_map: str | None
    immediate_action: str | None
    people_involved: str | None
    immediate_danger: bool
    urgent: bool
    raised_by: str | None
    reported_by: str | None
    raised_date: str
    dsl_reviewer: str | None
    review_date: str | None
    level_of_need: str | None
    status: str
    allegation_about: str | None
    outcome: str | None
    closed_date: str | None
    confidential: bool
    notes: str | None
    notified_at: str | None
    notified_count: int
    needs_phone_call: bool
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None
    referral_body: str | None = None
    referral_date: str | None = None
    referral_reference: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status not in FINISHED


@dataclass(frozen=True)
class SGAction:
    action_id: int
    concern_id: int
    action_date: str
    action_type: str
    actioned_by: str | None
    summary: str
    outcome: str | None
    follow_up: str | None
    due_date: str | None
    assigned_to: str | None
    completed_date: str | None
    created_by: str | None
    created_at: str

    @property
    def outstanding(self) -> bool:
        return bool(self.due_date) and not self.completed_date


@dataclass(frozen=True)
class Referral:
    referral_id: int
    concern_id: int
    agency: str
    referral_date: str
    reference: str | None
    reason: str | None
    made_by: str | None
    outcome: str
    outcome_date: str | None
    outcome_notes: str | None
    created_at: str
    pupil_id: int = 0
    pupil_name: str = ""
    admission_no: str = ""

    @property
    def pending(self) -> bool:
        return self.outcome == "Pending"


@dataclass(frozen=True)
class MyReport:
    """What the member of staff who reported a concern may see."""
    concern_id: int
    raised_date: str
    pupil_name: str
    admission_no: str
    category: str
    urgent: bool
    status: str


_BOOLS = ("immediate_danger", "urgent", "confidential", "needs_phone_call")
_SELECT = """
SELECT c.*, p.legal_last_name, p.legal_first_name, p.preferred_name, p.admission_no,
       p.year_group AS pupil_year, p.form_group,
       (SELECT agency FROM safeguarding_referrals r WHERE r.concern_id = c.concern_id
        ORDER BY referral_date DESC, referral_id DESC LIMIT 1) AS referral_body,
       (SELECT referral_date FROM safeguarding_referrals r WHERE r.concern_id = c.concern_id
        ORDER BY referral_date DESC, referral_id DESC LIMIT 1) AS referral_date,
       (SELECT reference FROM safeguarding_referrals r WHERE r.concern_id = c.concern_id
        ORDER BY referral_date DESC, referral_id DESC LIMIT 1) AS referral_reference
FROM safeguarding_concerns c JOIN pupils p USING (pupil_id)
"""
_EXTRA = ("pupil_name", "admission_no", "pupil_year", "form_group", "referral_body",
          "referral_date", "referral_reference")
_BASE = tuple(f for f in Concern.__dataclass_fields__ if f not in _EXTRA)
_SEVERITY_ORDER = ("CASE c.severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 "
                   "WHEN 'Medium' THEN 2 ELSE 3 END")


def _name(r) -> str:
    return f"{r['legal_last_name']}, {r['preferred_name'] or r['legal_first_name']}"


def _row(r) -> Concern:
    vals = {k: r[k] for k in _BASE}
    for k in _BOOLS:
        vals[k] = bool(vals[k])
    return Concern(**vals, pupil_name=_name(r), admission_no=r["admission_no"],
                   pupil_year=r["pupil_year"], form_group=r["form_group"],
                   referral_body=r["referral_body"], referral_date=r["referral_date"],
                   referral_reference=r["referral_reference"])


def _action_row(r) -> SGAction:
    return SGAction(**{k: r[k] for k in SGAction.__dataclass_fields__})


def _referral_row(r) -> Referral:
    keys = r.keys()
    base = {k: r[k] for k in Referral.__dataclass_fields__
            if k not in ("pupil_id", "pupil_name", "admission_no")}
    if "legal_last_name" in keys:
        return Referral(**base, pupil_id=r["pupil_id"], pupil_name=_name(r),
                        admission_no=r["admission_no"])
    return Referral(**base)


# ── Who may do what ──────────────────────────────────────────────────

def is_lead(actor: Principal) -> bool:
    """The DSL and deputies: read and manage every record."""
    return actor.role in SAFEGUARDING_LEADS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"safeguarding.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only school staff can report a safeguarding concern.")


def _require_lead(actor: Principal, action: str, target: Any = None) -> None:
    if not is_lead(actor):
        _deny(actor, action, target, "Only the designated safeguarding lead and deputies can "
                                     "do that. To pass on a concern, use Report a "
                                     "Safeguarding Concern.")


def _audit(conn, action: str, actor: Principal, *, concern_id: int | None = None,
           pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO safeguarding_audit (concern_id, pupil_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (concern_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def log_access(actor: Principal, what: str, *, pupil_id: int | None = None,
               concern_id: int | None = None) -> None:
    """Record that *actor* read a pupil's safeguarding record."""
    with database.connect() as conn:
        conn.execute("INSERT INTO safeguarding_access (username, role, pupil_id, concern_id, "
                     "what) VALUES (?, ?, ?, ?, ?)",
                     (actor.username or "unknown", actor.role, pupil_id, concern_id, what))


def access_log(*, actor: Principal, pupil_id: int | None = None, username: str | None = None,
               limit: int = 500) -> list[dict[str, Any]]:
    """Who read which pupil's record, newest first (leads only)."""
    _require_lead(actor, "access_log")
    sql = ("SELECT a.*, p.legal_last_name, p.legal_first_name, p.preferred_name, "
           "p.admission_no FROM safeguarding_access a LEFT JOIN pupils p USING (pupil_id)")
    where, params = [], []
    if pupil_id is not None:
        where.append("a.pupil_id = ?")
        params.append(int(pupil_id))
    if username:
        where.append("lower(a.username) = lower(?)")
        params.append(username.strip())
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY a.access_id DESC LIMIT ?",
                            (*params, int(limit))).fetchall()
    return [{"at": r["at"], "username": r["username"], "role": r["role"],
             "pupil_id": r["pupil_id"], "concern_id": r["concern_id"], "what": r["what"],
             "pupil": (f"{_name(r)} ({r['admission_no']})" if r["admission_no"] else "")}
            for r in rows]


def history(concern_id: int | None = None, *, actor: Principal, pupil_id: int | None = None,
            limit: int = 300) -> list[dict[str, Any]]:
    """Changes to the records (leads only)."""
    _require_lead(actor, "history")
    sql, where, params = "SELECT * FROM safeguarding_audit", [], []
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


def staff_name(actor: Principal | str) -> str:
    """A login's display name (the username when it isn't known)."""
    from education_system.systems.secondary.infrastructure.authentication import accounts
    username = actor if isinstance(actor, str) else (actor.username or "")
    try:
        for s in accounts.staff_logins():
            if s["username"].lower() == username.lower():
                return s["display_name"] or username
    except Exception:  # noqa: BLE001 - the name is a convenience
        pass
    return username


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
            default: str | None, aliases: dict[str, str] | None = None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    if aliases and v.lower() in aliases:
        return aliases[v.lower()]
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _text(value: Any, limit: int = 500) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def _flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "y", "yes", "true", "on"}
    return bool(value)


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    text = str(ref).strip()
    m = re.search(r"\(([^()]+)\)\s*$", text)     # "Surname, First (ADM123)"
    return P.find_by_reference(m.group(1) if m else text)


FIELDS = ("category", "severity", "incident_date", "incident_time", "location", "description",
          "child_words", "body_map", "immediate_action", "people_involved", "immediate_danger",
          "urgent", "raised_by", "raised_date", "dsl_reviewer", "review_date",
          "level_of_need", "status", "allegation_about", "outcome", "closed_date",
          "confidential", "notes")
REFERRAL_FIELDS = ("referral_body", "referral_date", "referral_reference")


def _clean(data: dict[str, Any], current: Concern | None) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}
    out["category"] = _choice(merged.get("category"), CONCERN_CATEGORIES, "Category", problems,
                              DEFAULT_CATEGORY, _CATEGORY_ALIASES)
    out["severity"] = _choice(merged.get("severity"), SEVERITIES, "Severity", problems,
                              DEFAULT_SEVERITY)
    out["status"] = _choice(merged.get("status"), CONCERN_STATUSES, "Status", problems,
                            DEFAULT_STATUS)
    out["level_of_need"] = _choice(merged.get("level_of_need"), LEVELS, "Level of need",
                                   problems, None)
    for k, label in (("incident_date", "Incident date"), ("raised_date", "Raised date"),
                     ("review_date", "Review date"), ("closed_date", "Closed date")):
        out[k] = _date(merged.get(k), label, problems)
    out["raised_date"] = out["raised_date"] or _today().isoformat()
    t = str(merged.get("incident_time") or "").strip()
    if t and not _TIME_RE.match(t):
        problems.append("Incident time must be HH:MM (24-hour)")
    out["incident_time"] = t or None
    today = _today().isoformat()
    if out["incident_date"] and out["incident_date"] > today:
        problems.append("The incident date can't be in the future")
    description = str(merged.get("description") or "").strip()
    if not description:
        problems.append("Description is required (what you saw or heard)")
    out["description"] = description[:MAX_TEXT]
    for k in ("child_words", "body_map", "immediate_action", "people_involved", "outcome",
              "notes"):
        out[k] = _text(merged.get(k), MAX_TEXT)
    for k in ("location", "raised_by", "dsl_reviewer", "allegation_about"):
        out[k] = _text(merged.get(k), 120)
    out["immediate_danger"] = _flag(merged.get("immediate_danger"))
    out["urgent"] = _flag(merged.get("urgent")) or out["immediate_danger"]
    conf = merged.get("confidential")
    out["confidential"] = True if conf is None or conf == "" else _flag(conf)
    if out["status"] == "Closed" and not out["outcome"]:
        problems.append("Outcome is required when status is Closed")
    if out["status"] in FINISHED and not out["closed_date"]:
        out["closed_date"] = today
    if out["status"] not in FINISHED:
        out["closed_date"] = None
    if out["closed_date"] and out["closed_date"] < out["raised_date"]:
        problems.append("Closed date cannot be before raised date")
    if out["level_of_need"] == LADO_LEVEL and not out["allegation_about"]:
        problems.append("Say which member of staff (or adult) the allegation is about")
    return out, problems


def _clean_referral(data: dict[str, Any], raised_date: str, problems: list[str]
                    ) -> dict[str, Any] | None:
    """The old referral fields on a concern -> a referral (or None)."""
    body = _choice(data.get("referral_body"), REFERRAL_BODIES, "Referral body", problems, None)
    rdate = _date(data.get("referral_date"), "Referral date", problems)
    ref = _text(data.get("referral_reference"), 80)
    if not body:
        if rdate or ref:
            problems.append("Choose the referral body for the referral date / reference")
        return None
    rdate = rdate or _today().isoformat()
    if rdate < raised_date:
        problems.append("Referral date cannot be before raised date")
    return {"agency": body, "referral_date": rdate, "reference": ref}


# ── Reading (leads) ──────────────────────────────────────────────────

def _get(concern_id: int) -> Concern:
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE c.concern_id = ?", (int(concern_id),)).fetchone()
    if r is None:
        raise NotFound(f"No safeguarding concern #{concern_id}")
    return _row(r)


def get(concern_id: int, *, actor: Principal, log: bool = True) -> Concern:
    """One concern in full (leads only; the read is logged)."""
    _require_lead(actor, "view", f"concern:{concern_id}")
    c = _get(concern_id)
    if log:
        log_access(actor, "concern", pupil_id=c.pupil_id, concern_id=c.concern_id)
        activity_log.record("safeguarding.view", target=c.admission_no, principal=actor,
                            concern=c.concern_id)
    return c


def list_concerns(*, actor: Principal, pupil_id: int | None = None,
                  year_group: int | str | None = None, category: str | None = None,
                  severity: str | None = None, status: str | None = None,
                  level: str | None = None, urgent_only: bool = False,
                  open_only: bool = False, date_from: str | None = None,
                  date_to: str | None = None, limit: int = 2000) -> list[Concern]:
    """Concerns, most severe first then newest (the old order). Leads only;
    a list for one pupil is logged as a read of their record."""
    _require_lead(actor, "list")
    problems: list[str] = []
    where, params = [], []
    if category:
        category = _choice(category, CONCERN_CATEGORIES, "Category filter", problems, None,
                           _CATEGORY_ALIASES)
    for col, val, opts, label in (("c.severity", severity, SEVERITIES, "Severity filter"),
                                  ("c.status", status, CONCERN_STATUSES, "Status filter"),
                                  ("c.level_of_need", level, LEVELS, "Level filter")):
        if val:
            val = _choice(val, opts, label, problems, None)
            where.append(f"{col} = ?")
            params.append(val)
    if category:
        where.append("c.category = ?")
        params.append(category)
    if pupil_id not in (None, ""):
        where.append("c.pupil_id = ?")
        params.append(int(pupil_id))
    if year_group not in (None, ""):
        try:
            where.append("p.year_group = ?")
            params.append(int(year_group))
        except ValueError:
            problems.append("Year filter must be a year group number")
    if urgent_only:
        where.append("c.urgent = 1")
    if open_only:
        where.append("c.status NOT IN ('Closed', 'Transferred')")
    for col, val, label, op in (("c.raised_date", date_from, "From date", ">="),
                                ("c.raised_date", date_to, "To date", "<=")):
        d = _date(val, label, problems)
        if d:
            where.append(f"{col} {op} ?")
            params.append(d)
    if problems:
        raise ValidationError(problems)
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        f" ORDER BY {_SEVERITY_ORDER}, c.raised_date DESC, c.concern_id DESC LIMIT ?"
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute(sql, (*params, int(limit)))]
    if pupil_id not in (None, ""):
        log_access(actor, "concern list", pupil_id=int(pupil_id))
    return rows


def awaiting_triage(*, actor: Principal) -> list[Concern]:
    """New reports, urgent first then oldest."""
    rows = list_concerns(actor=actor, status=NEW)
    return sorted(rows, key=lambda c: (not c.urgent, c.created_at, c.concern_id))


# ── Writing ──────────────────────────────────────────────────────────

def _insert(conn, pupil: P.Pupil, c: dict[str, Any], actor: Principal) -> int:
    cid = conn.execute(
        f"INSERT INTO safeguarding_concerns (pupil_id, reported_by, updated_by, "
        f"{', '.join(FIELDS)}) VALUES (?, ?, ?, {', '.join('?' * len(FIELDS))})",
        (pupil.pupil_id, actor.username, actor.username,
         *(int(c[k]) if k in _BOOLS else c[k] for k in FIELDS))).lastrowid
    return int(cid)


def _find_pupil(data: dict[str, Any], problems: list[str]) -> P.Pupil | None:
    ref = data.get("pupil_id") or data.get("pupil")
    p = _pupil(ref)
    if p is None:
        problems.append("Choose the pupil" if not ref else f"No pupil {ref}")
    return p


def raise_concern(data: dict[str, Any], *, actor: Principal) -> Concern:
    """The old Raise concern (a lead recording a concern in full). *data*
    carries ``pupil_id`` (id or admission no.)."""
    _require_lead(actor, "create")
    problems: list[str] = []
    p = _find_pupil(data, problems)
    c, more = _clean(data, None)
    problems += more
    c["raised_by"] = c["raised_by"] or staff_name(actor)
    ref = _clean_referral(data, c["raised_date"], problems)
    if ref is None and c["status"] == "Referred":
        problems.append("Referral body is required when status is Referred")
    if problems:
        activity_log.record("safeguarding.create", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    with database.connect() as conn:
        cid = _insert(conn, p, c, actor)
        if ref:
            _add_referral(conn, cid, ref, actor)
        _audit(conn, "create", actor, concern_id=cid, pupil_id=p.pupil_id,
               category=c["category"], severity=c["severity"])
    activity_log.record("safeguarding.create", target=p.admission_no, principal=actor,
                        concern=cid)
    return _get(cid)


def report_concern(data: dict[str, Any], *, actor: Principal) -> tuple[MyReport, dict]:
    """Any member of staff reports a concern. It goes to the DSL as ``New``;
    the reporter is the signed-in person. Returns ``(report, alert)``:
    *alert* is :func:`alert_leads`'s result for an urgent concern, else
    ``{}``."""
    _require_staff(actor, "report")
    problems: list[str] = []
    p = _find_pupil(data, problems)
    allowed = ("category", "incident_date", "incident_time", "location", "description",
               "child_words", "body_map", "immediate_action", "people_involved",
               "immediate_danger", "urgent")
    c, more = _clean({k: v for k, v in data.items() if k in allowed}, None)
    problems += more
    if p is not None and p.roll_status != "on_roll":
        # Still accepted: concerns about a leaver matter (the DSL passes them on).
        pass
    if problems:
        activity_log.record("safeguarding.report", outcome="invalid", principal=actor,
                            problems=len(problems))
        raise ValidationError(problems)
    c.update(status=NEW, raised_by=staff_name(actor), severity="High" if c["urgent"]
             else DEFAULT_SEVERITY, raised_date=_today().isoformat())
    with database.connect() as conn:
        cid = _insert(conn, p, c, actor)
        _audit(conn, "report", actor, concern_id=cid, pupil_id=p.pupil_id,
               urgent=c["urgent"])
    activity_log.record("safeguarding.report", target=p.admission_no, principal=actor,
                        concern=cid, urgent=int(c["urgent"]))
    alert = alert_leads(cid, actor=actor) if c["urgent"] else {}
    return my_report(cid, actor=actor), alert


def update(concern_id: int, changes: dict[str, Any], *, actor: Principal) -> Concern:
    """The old Edit concern. The referral fields change the latest referral
    (or add one)."""
    cur = _get(concern_id)
    _require_lead(actor, "update", cur.admission_no)
    c, problems = _clean(changes, cur)
    ref_changes = {k: changes[k] for k in REFERRAL_FIELDS if k in changes and
                   str(changes[k] or "") != str(getattr(cur, k) or "")}
    ref = None
    if ref_changes:
        ref = _clean_referral({**{k: getattr(cur, k) for k in REFERRAL_FIELDS}, **ref_changes},
                              c["raised_date"], problems)
    if c["status"] == "Referred" and not (ref or cur.referral_body):
        problems.append("Referral body is required when status is Referred")
    if "pupil_id" in changes and changes["pupil_id"] not in (None, ""):
        p = _pupil(changes["pupil_id"])
        if p is None:
            problems.append(f"No pupil {changes['pupil_id']}")
        elif p.pupil_id != cur.pupil_id:
            problems.append("A concern can't be moved to another pupil - record it again for "
                            "the right pupil and delete this one as logged in error")
    if problems:
        raise ValidationError(problems)
    changed = [k for k in FIELDS if c[k] != getattr(cur, k)]
    if not changed and not ref_changes:
        return cur
    with database.connect() as conn:
        if changed:
            conn.execute("UPDATE safeguarding_concerns SET "
                         + ", ".join(f"{k} = ?" for k in changed)
                         + ", updated_by = ?, updated_at = datetime('now') WHERE concern_id = ?",
                         (*(int(c[k]) if k in _BOOLS else c[k] for k in changed),
                          actor.username, cur.concern_id))
        if ref_changes:
            latest = conn.execute("SELECT referral_id FROM safeguarding_referrals WHERE "
                                  "concern_id = ? ORDER BY referral_date DESC, referral_id DESC "
                                  "LIMIT 1", (cur.concern_id,)).fetchone()
            if ref is None and latest:
                pass    # clearing the body keeps the referral (it happened)
            elif latest:
                conn.execute("UPDATE safeguarding_referrals SET agency = ?, referral_date = ?, "
                             "reference = ? WHERE referral_id = ?",
                             (ref["agency"], ref["referral_date"], ref["reference"],
                              latest["referral_id"]))
            elif ref:
                _add_referral(conn, cur.concern_id, ref, actor)
        _audit(conn, "update", actor, concern_id=cur.concern_id, pupil_id=cur.pupil_id,
               fields=changed + sorted(ref_changes))
    activity_log.record("safeguarding.update", target=cur.admission_no, principal=actor,
                        concern=cur.concern_id, fields=",".join(changed + sorted(ref_changes)))
    return _get(cur.concern_id)


def set_status(concern_id: int, status: str, *, actor: Principal,
               outcome: str | None = None, referral_body: str | None = None) -> Concern:
    """The old Set status (Closed needs the outcome, Referred a referral body)."""
    changes: dict[str, Any] = {"status": status}
    if outcome not in (None, ""):
        changes["outcome"] = outcome
    if referral_body not in (None, ""):
        changes["referral_body"] = referral_body
    return update(concern_id, changes, actor=actor)


def triage(concern_id: int, *, actor: Principal, level: str, severity: str | None = None,
           category: str | None = None, status: str | None = None,
           note: str | None = None, allegation_about: str | None = None) -> Concern:
    """The DSL's first look: level of need, severity and category. The
    concern leaves ``New`` (Monitoring for Monitor, otherwise Open unless a
    status is given) and the triage is in its actions."""
    cur = _get(concern_id)
    _require_lead(actor, "triage", cur.admission_no)
    problems: list[str] = []
    lvl = _choice(level, LEVELS, "Level of need", problems, None)
    if not lvl:
        problems.append("Choose the level of need / action")
    if problems:
        raise ValidationError(problems)
    new_status = status or (cur.status if cur.status != NEW else
                            ("Monitoring" if lvl == "Monitor" else "Open"))
    if lvl == "No further action" and not status:
        new_status = "Closed"
    changes: dict[str, Any] = {"level_of_need": lvl, "status": new_status,
                               "dsl_reviewer": staff_name(actor),
                               "review_date": _today().isoformat()}
    if new_status == "Closed" and not cur.outcome:
        changes["outcome"] = note or "No further action after DSL review"
    for k, v in (("severity", severity), ("category", category),
                 ("allegation_about", allegation_about)):
        if v:
            changes[k] = v
    c = update(cur.concern_id, changes, actor=actor)
    _log_action(c, "Triage", f"Level of need: {lvl}" + (f". {note.strip()}"
                                                        if note and note.strip() else ""),
                actor)
    return c


def close_concern(concern_id: int, *, actor: Principal, outcome: str,
                  closed_date: str | None = None) -> Concern:
    cur = _get(concern_id)
    _require_lead(actor, "close", cur.admission_no)
    if cur.status in FINISHED:
        raise ValidationError([f"Concern #{cur.concern_id} is already {cur.status.lower()}"])
    open_actions = [a for a in list_actions(cur.concern_id, actor=actor, log=False)
                    if a.outstanding]
    c = update(cur.concern_id, {"status": "Closed", "outcome": outcome,
                                "closed_date": closed_date or ""}, actor=actor)
    _log_action(c, "Case closed", f"Closed: {outcome}"[:2000], actor)
    if open_actions:
        with database.connect() as conn:
            conn.execute("UPDATE safeguarding_actions SET completed_date = ? WHERE "
                         "concern_id = ? AND due_date IS NOT NULL AND completed_date IS NULL",
                         (c.closed_date, c.concern_id))
    return c


def reopen(concern_id: int, *, actor: Principal, reason: str) -> Concern:
    """Reopen a closed (or transferred) concern; the reason is required."""
    cur = _get(concern_id)
    _require_lead(actor, "reopen", cur.admission_no)
    why = " ".join(str(reason or "").split())
    problems = []
    if cur.status not in FINISHED:
        problems.append(f"Concern #{cur.concern_id} is still open")
    if not why:
        problems.append("Say why the concern is reopened")
    if problems:
        raise ValidationError(problems)
    c = update(cur.concern_id, {"status": "Open"}, actor=actor)
    with database.connect() as conn:
        conn.execute("UPDATE safeguarding_prevent SET channel_status = 'Open' WHERE "
                     "concern_id = ?", (c.concern_id,))
    _log_action(c, "Case reopened", f"Reopened: {why}"[:2000], actor)
    return c


def delete(concern_id: int, *, actor: Principal, reason: str = "") -> bool:
    """The old Delete concern - only for one logged in error (its actions go
    with it). A concern with a referral or one that was transferred is kept."""
    c = _get(concern_id)
    _require_lead(actor, "delete", c.admission_no)
    why = " ".join(str(reason or "").split())
    problems = []
    if not why:
        problems.append("Say why the concern is deleted (e.g. logged for the wrong pupil)")
    if c.referral_body:
        problems.append("A referral was made on this concern - close it instead of deleting")
    if c.status == "Transferred":
        problems.append("This record has been transferred - it must be kept")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("DELETE FROM safeguarding_concerns WHERE concern_id = ?", (c.concern_id,))
        _audit(conn, "delete", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               reason=why, category=c.category)
    activity_log.record("safeguarding.delete", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return True


# ── Actions ──────────────────────────────────────────────────────────

def _log_action(c: Concern, action_type: str, summary: str, actor: Principal, *,
                day: str | None = None, conn=None) -> int:
    sql = ("INSERT INTO safeguarding_actions (concern_id, action_date, action_type, "
           "actioned_by, summary, created_by) VALUES (?, ?, ?, ?, ?, ?)")
    args = (c.concern_id, day or _today().isoformat(), action_type, staff_name(actor),
            summary[:MAX_TEXT], actor.username)
    if conn is not None:
        return conn.execute(sql, args).lastrowid
    with database.connect() as db:
        return db.execute(sql, args).lastrowid


def _get_action(action_id: int) -> SGAction:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM safeguarding_actions WHERE action_id = ?",
                         (int(action_id),)).fetchone()
    if r is None:
        raise NotFound(f"No action #{action_id}")
    return _action_row(r)


def get_action(action_id: int, *, actor: Principal) -> SGAction | None:
    _require_lead(actor, "action_view")
    try:
        return _get_action(action_id)
    except NotFound:
        return None


def add_action(data: dict[str, Any], *, actor: Principal) -> SGAction:
    """The old Add action, with an owner and due date. *data* carries
    ``concern_id``."""
    _require_lead(actor, "action")
    try:
        c = _get(int(str(data.get("concern_id") or "").strip()))
    except ValueError:
        raise ValidationError(["Concern ID is required" if not data.get("concern_id")
                               else "Concern ID must be a number"]) from None
    problems: list[str] = []
    day = _date(data.get("action_date"), "Action date", problems) or _today().isoformat()
    atype = _choice(data.get("action_type"), ACTION_TYPES, "Action type", problems,
                    DEFAULT_ACTION_TYPE)
    due = _date(data.get("due_date"), "Due date", problems)
    done = _date(data.get("completed_date"), "Done date", problems)
    summary = str(data.get("summary") or "").strip()
    if not summary:
        problems.append("Summary is required")
    if due and due < c.raised_date:
        problems.append("Due date can't be before the concern was raised")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = conn.execute(
            "INSERT INTO safeguarding_actions (concern_id, action_date, action_type, "
            "actioned_by, summary, outcome, follow_up, due_date, assigned_to, completed_date, "
            "created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (c.concern_id, day, atype, _text(data.get("actioned_by"), 120) or staff_name(actor),
             summary[:MAX_TEXT], _text(data.get("outcome"), MAX_TEXT),
             _text(data.get("follow_up"), MAX_TEXT), due, _text(data.get("assigned_to"), 120),
             done, actor.username)).lastrowid
        _audit(conn, "action", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               action_id=aid, type=atype)
    activity_log.record("safeguarding.action", target=c.admission_no, principal=actor,
                        concern=c.concern_id, item=aid)
    return _get_action(aid)


def complete_action(action_id: int, *, actor: Principal, outcome: str | None = None,
                    day: str | None = None) -> SGAction:
    a = _get_action(action_id)
    c = _get(a.concern_id)
    _require_lead(actor, "action_done", c.admission_no)
    problems: list[str] = []
    d = _date(day, "Done date", problems) or _today().isoformat()
    if a.completed_date:
        problems.append(f"Action #{a.action_id} is already done")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE safeguarding_actions SET completed_date = ?, outcome = "
                     "COALESCE(?, outcome) WHERE action_id = ?",
                     (d, _text(outcome, MAX_TEXT), a.action_id))
        _audit(conn, "action_done", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               action_id=a.action_id)
    activity_log.record("safeguarding.action_done", target=c.admission_no, principal=actor,
                        concern=c.concern_id, item=a.action_id)
    return _get_action(a.action_id)


def list_actions(concern_id: int, *, actor: Principal, log: bool = True) -> list[SGAction]:
    """A concern's actions, newest first (the old order)."""
    c = get(concern_id, actor=actor, log=log)
    with database.connect() as conn:
        return [_action_row(r) for r in conn.execute(
            "SELECT * FROM safeguarding_actions WHERE concern_id = ? "
            "ORDER BY action_date DESC, action_id DESC", (c.concern_id,))]


def delete_action(action_id: int, *, actor: Principal) -> bool:
    a = _get_action(action_id)
    c = _get(a.concern_id)
    _require_lead(actor, "action_delete", c.admission_no)
    with database.connect() as conn:
        conn.execute("DELETE FROM safeguarding_actions WHERE action_id = ?", (a.action_id,))
        _audit(conn, "action_delete", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               action_id=a.action_id, type=a.action_type)
    activity_log.record("safeguarding.action_delete", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return True


# ── Referrals ────────────────────────────────────────────────────────

def _add_referral(conn, concern_id: int, ref: dict[str, Any], actor: Principal) -> int:
    rid = conn.execute(
        "INSERT INTO safeguarding_referrals (concern_id, agency, referral_date, reference, "
        "reason, made_by) VALUES (?, ?, ?, ?, ?, ?)",
        (concern_id, ref["agency"], ref["referral_date"], ref.get("reference"),
         ref.get("reason"), staff_name(actor))).lastrowid
    conn.execute("INSERT INTO safeguarding_actions (concern_id, action_date, action_type, "
                 "actioned_by, summary, created_by) VALUES (?, ?, 'Referral', ?, ?, ?)",
                 (concern_id, ref["referral_date"], staff_name(actor),
                  f"Referred to {ref['agency']}"
                  + (f" (ref {ref['reference']})" if ref.get("reference") else ""),
                  actor.username))
    return int(rid)


def add_referral(concern_id: int, data: dict[str, Any], *, actor: Principal) -> Referral:
    """Record a referral (children's social care, police, LADO, Channel...).
    An open concern becomes Referred."""
    c = _get(concern_id)
    _require_lead(actor, "referral", c.admission_no)
    problems: list[str] = []
    ref = _clean_referral({"referral_body": data.get("agency") or data.get("referral_body"),
                           "referral_date": data.get("referral_date"),
                           "referral_reference": data.get("reference")
                           or data.get("referral_reference")}, c.raised_date, problems)
    if ref is None and not problems:
        problems.append("Choose who the referral is to")
    if ref and ref["referral_date"] > _today().isoformat():
        problems.append("Record the referral once it has been made")
    if ref and ref["agency"] == "LADO" and not (c.allegation_about or
                                                data.get("allegation_about")):
        problems.append("Say which member of staff (or adult) the allegation is about")
    if problems:
        raise ValidationError(problems)
    ref["reason"] = _text(data.get("reason"), MAX_TEXT)
    with database.connect() as conn:
        rid = _add_referral(conn, c.concern_id, ref, actor)
        sets, args = ["updated_by = ?", "updated_at = datetime('now')"], [actor.username]
        if c.status in (NEW, "Open", "Monitoring"):
            sets.append("status = 'Referred'")
        if data.get("allegation_about") and not c.allegation_about:
            sets.append("allegation_about = ?")
            args.append(_text(data["allegation_about"], 120))
        conn.execute(f"UPDATE safeguarding_concerns SET {', '.join(sets)} WHERE concern_id = ?",
                     (*args, c.concern_id))
        _audit(conn, "referral", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               referral_id=rid, agency=ref["agency"])
    activity_log.record("safeguarding.referral", target=c.admission_no, principal=actor,
                        concern=c.concern_id, referral=rid)
    return get_referral(rid, actor=actor)


def get_referral(referral_id: int, *, actor: Principal) -> Referral:
    _require_lead(actor, "referral_view")
    with database.connect() as conn:
        r = conn.execute("SELECT r.*, c.pupil_id, p.legal_last_name, p.legal_first_name, "
                         "p.preferred_name, p.admission_no FROM safeguarding_referrals r "
                         "JOIN safeguarding_concerns c USING (concern_id) "
                         "JOIN pupils p ON p.pupil_id = c.pupil_id WHERE r.referral_id = ?",
                         (int(referral_id),)).fetchone()
    if r is None:
        raise NotFound(f"No referral #{referral_id}")
    return _referral_row(r)


def list_referrals(*, actor: Principal, concern_id: int | None = None,
                   pupil_id: int | None = None, pending_only: bool = False,
                   agency: str | None = None) -> list[Referral]:
    _require_lead(actor, "referral_list")
    where, params = [], []
    for col, val in (("r.concern_id", concern_id), ("c.pupil_id", pupil_id),
                     ("r.agency", agency or None)):
        if val not in (None, ""):
            where.append(f"{col} = ?")
            params.append(val)
    if pending_only:
        where.append("r.outcome = 'Pending'")
    sql = ("SELECT r.*, c.pupil_id, p.legal_last_name, p.legal_first_name, p.preferred_name, "
           "p.admission_no FROM safeguarding_referrals r JOIN safeguarding_concerns c "
           "USING (concern_id) JOIN pupils p ON p.pupil_id = c.pupil_id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        rows = [_referral_row(r) for r in conn.execute(
            sql + " ORDER BY r.referral_date DESC, r.referral_id DESC", params)]
    if pupil_id is not None:
        log_access(actor, "referrals", pupil_id=int(pupil_id))
    return rows


def record_referral_outcome(referral_id: int, *, actor: Principal, outcome: str,
                            day: str | None = None, notes: str | None = None) -> Referral:
    r = get_referral(referral_id, actor=actor)
    c = _get(r.concern_id)
    _require_lead(actor, "referral_outcome", c.admission_no)
    problems: list[str] = []
    out = _choice(outcome, REFERRAL_OUTCOMES, "Outcome", problems, None)
    if not out or out == "Pending":
        problems.append("Choose the outcome of the referral")
    d = _date(day, "Outcome date", problems) or _today().isoformat()
    if d < r.referral_date:
        problems.append("The outcome can't be before the referral")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute("UPDATE safeguarding_referrals SET outcome = ?, outcome_date = ?, "
                     "outcome_notes = ? WHERE referral_id = ?",
                     (out, d, _text(notes, MAX_TEXT), r.referral_id))
        _log_action(c, "Referral outcome", f"{r.agency}: {out}"
                    + (f". {notes.strip()}" if notes and notes.strip() else ""), actor, day=d,
                    conn=conn)
        _audit(conn, "referral_outcome", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               referral_id=r.referral_id, outcome=out)
    activity_log.record("safeguarding.referral_outcome", target=c.admission_no,
                        principal=actor, concern=c.concern_id, referral=r.referral_id)
    return get_referral(r.referral_id, actor=actor)


# ── Staff who reported ───────────────────────────────────────────────

def _my_report(r) -> MyReport:
    return MyReport(concern_id=r["concern_id"], raised_date=r["raised_date"],
                    pupil_name=_name(r), admission_no=r["admission_no"],
                    category=r["category"], urgent=bool(r["urgent"]),
                    status=REPORTER_STATUS.get(r["status"], "With the DSL"))


def my_reports(*, actor: Principal) -> list[MyReport]:
    """The concerns *actor* reported, with their status only."""
    _require_staff(actor, "my_reports")
    with database.connect() as conn:
        rows = conn.execute(_SELECT + " WHERE lower(c.reported_by) = lower(?) "
                                      "ORDER BY c.concern_id DESC",
                            (actor.username or "",)).fetchall()
    return [_my_report(r) for r in rows]


def my_report(concern_id: int, *, actor: Principal) -> MyReport:
    _require_staff(actor, "my_report")
    with database.connect() as conn:
        r = conn.execute(_SELECT + " WHERE c.concern_id = ?", (int(concern_id),)).fetchone()
    if r is None or (r["reported_by"] or "").lower() != (actor.username or "").lower():
        if r is not None and is_lead(actor):
            return _my_report(r)
        _deny(actor, "my_report", f"concern:{concern_id}",
              "You can only see the concerns you reported.")
    return _my_report(r)


def add_information(concern_id: int, text: str, *, actor: Principal) -> MyReport:
    """The reporter adds something they have since seen or heard (a report
    can't be changed once it is in, only added to)."""
    rep = my_report(concern_id, actor=actor)
    body = str(text or "").strip()
    if not body:
        raise ValidationError(["Write what you want to add"])
    c = _get(rep.concern_id)
    with database.connect() as conn:
        _log_action(c, "Further information", body, actor, conn=conn)
        _audit(conn, "information", actor, concern_id=c.concern_id, pupil_id=c.pupil_id)
    activity_log.record("safeguarding.information", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return rep


# ── The safeguarding team and urgent alerts ──────────────────────────

def team(*, actor: Principal | None = None) -> list[dict[str, Any]]:
    """The DSL and deputies with how to reach them. Staff see it too (they
    need to know who to go to); falls back to the logins with a lead role."""
    from education_system.systems.secondary.infrastructure.authentication import accounts
    try:
        logins = {s["username"].lower(): s for s in accounts.staff_logins()}
    except Exception:  # noqa: BLE001 - the auth database may be unavailable
        logins = {}
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM safeguarding_team ORDER BY CASE team_role "
                            "WHEN 'DSL' THEN 0 WHEN 'Deputy DSL' THEN 1 ELSE 2 END, "
                            "display_name").fetchall()
    out = []
    for r in rows:
        login = logins.get(r["username"].lower(), {})
        out.append({"username": r["username"],
                    "name": r["display_name"] or login.get("display_name") or r["username"],
                    "team_role": r["team_role"], "phone": r["phone"] or "",
                    "email": r["email"] or login.get("email") or "", "listed": True})
    if not out:
        out = [{"username": s["username"], "name": s["display_name"], "team_role": "DSL",
                "phone": "", "email": s.get("email") or "", "listed": False}
               for s in logins.values() if s.get("role") in SAFEGUARDING_LEADS]
    return out


def set_team_member(username: str, data: dict[str, Any], *, actor: Principal) -> dict:
    """Add or change a team member (a staff login)."""
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    from education_system.systems.secondary.infrastructure.authentication import accounts
    _require_lead(actor, "team")
    problems: list[str] = []
    user = str(username or "").strip()
    logins = {s["username"].lower(): s for s in accounts.staff_logins()}
    if not user:
        problems.append("Choose the member of staff")
    elif user.lower() not in logins:
        problems.append(f"No staff login {user}")
    role = _choice(data.get("team_role"), TEAM_ROLES, "Role", problems, "Deputy DSL")
    email = _text(data.get("email"), 120)
    if email and not C.valid_email(email):
        problems.append("E-mail address doesn't look right")
    phone = _text(data.get("phone"), 30)
    if problems:
        raise ValidationError(problems)
    login = logins[user.lower()]
    with database.connect() as conn:
        conn.execute("INSERT INTO safeguarding_team (username, display_name, team_role, phone, "
                     "email, added_by) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (username) DO "
                     "UPDATE SET team_role = excluded.team_role, phone = excluded.phone, "
                     "email = excluded.email, display_name = excluded.display_name",
                     (login["username"], login["display_name"], role, phone, email,
                      actor.username))
        _audit(conn, "team", actor, member=login["username"], role=role)
    activity_log.record("safeguarding.team", target=login["username"], principal=actor)
    return next(m for m in team() if m["username"] == login["username"])


def remove_team_member(username: str, *, actor: Principal) -> bool:
    _require_lead(actor, "team_remove")
    with database.connect() as conn:
        n = conn.execute("DELETE FROM safeguarding_team WHERE lower(username) = lower(?)",
                         (str(username or "").strip(),)).rowcount
        if n:
            _audit(conn, "team_remove", actor, member=username)
    if not n:
        raise NotFound(f"{username} isn't on the safeguarding team")
    activity_log.record("safeguarding.team_remove", target=username, principal=actor)
    return True


def alert_leads(concern_id: int, *, actor: Principal) -> dict[str, Any]:
    """E-mail the safeguarding team that an urgent concern is waiting (no
    details of the concern - it says where to look). Returns
    ``{'message_id', 'emails', 'phone': [team members without e-mail]}``; when
    nobody can be e-mailed the concern records that the DSL must be phoned."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    _require_staff(actor, "alert")
    c = _get(concern_id)
    if (c.reported_by or "").lower() != (actor.username or "").lower() and not is_lead(actor):
        _deny(actor, "alert", c.admission_no, "You can only alert the DSL about your own "
                                             "report.")
    members = team()
    to = [(m["email"], m["name"]) for m in members if m["email"] and C.valid_email(m["email"])]
    phone = [m for m in members if not (m["email"] and C.valid_email(m["email"]))]
    mid = None
    if to:
        template = email_templates.load_template("safeguarding_urgent_alert")
        reporter = staff_name(actor)
        letters = []
        for address, name in to:
            subject, body = template.render({
                "recipient_name": name, "concern_id": c.concern_id,
                "year_group": c.pupil_year, "reporter": reporter,
                "reported_at": c.created_at[:16]})
            letters.append((address, name, subject, body))
        mid = E.save_prepared("safeguarding_alert", "Urgent safeguarding concern",
                              "Urgent safeguarding concern", "(one alert per team member)",
                              letters, actor=actor)
    with database.connect() as conn:
        conn.execute("UPDATE safeguarding_concerns SET notified_at = datetime('now'), "
                     "notified_count = ?, needs_phone_call = ? WHERE concern_id = ?",
                     (len(to), 0 if to else 1, c.concern_id))
        _log_action(c, "Internal escalation",
                    f"Urgent: safeguarding team e-mailed ({len(to)})" if to else
                    "Urgent: nobody on the safeguarding team has an e-mail address - the DSL "
                    "must be phoned", actor, conn=conn)
        _audit(conn, "alert", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
               emails=len(to))
    activity_log.record("safeguarding.alert", target=c.admission_no, principal=actor,
                        concern=c.concern_id, emails=len(to))
    return {"message_id": mid, "emails": len(to), "phone": phone}


def record_phoned(concern_id: int, *, actor: Principal, who: str) -> Concern:
    """The DSL was phoned about an urgent concern that couldn't be e-mailed."""
    c = _get(concern_id)
    if (c.reported_by or "").lower() != (actor.username or "").lower():
        _require_lead(actor, "phoned", c.admission_no)
    _require_staff(actor, "phoned")
    whom = _text(who, 120)
    if not whom:
        raise ValidationError(["Say who you spoke to"])
    with database.connect() as conn:
        conn.execute("UPDATE safeguarding_concerns SET needs_phone_call = 0 WHERE "
                     "concern_id = ?", (c.concern_id,))
        _log_action(c, "Phone call", f"Urgent concern passed on by phone to {whom}", actor,
                    conn=conn)
        _audit(conn, "phoned", actor, concern_id=c.concern_id, pupil_id=c.pupil_id)
    activity_log.record("safeguarding.phoned", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return _get(c.concern_id)
