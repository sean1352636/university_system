"""Year 6 Transition: planning the whole incoming Year 7 cohort.

:mod:`incoming_primary` is the receiving end of the platform queue, one
transfer at a time. This module is the planning layer over the whole
September intake, whichever way each child is coming:

* **Cohort.** Everyone expected for an intake year (``"2026/27"``): pupils
  on the platform queue from primaries on the platform, plus Year 7
  admissions offers (offered / accepted / admitted) for children from
  schools that aren't. :func:`sync` reads both (the handover through
  ``incoming_primary.handover``, so the platform role-filters and audits
  it) into ``y6_cohort``; one row per child, with feeder primary, status,
  KS2, SEN / PP / LAC flags, the enhanced-transition flag, checklist
  progress and the form allocated.
* **Feeder schools and liaison.** Visits and calls to feeder primaries and
  per-pupil notes (the Year 6 teacher conversation); the primary's
  transition report (strengths, friendships, keep apart, worries, all
  about me, enhanced transition) read live through the handover.
* **Events.** Induction and taster days, new-parents' evening, summer
  school, enhanced-transition visits: date, time, type, audience, with
  per-pupil invitations and attendance.
* **Friendships and keep-apart.** Prefilled from the transition report
  (names resolved to children in the cohort), editable.
* **Form allocation.** Each child into a Year 7 form (the Form Groups
  module's forms). :func:`suggest` balances size, gender, KS2 band, SEN and
  feeder spread while honouring one friendship each and every keep-apart;
  manual moves; warnings; :func:`publish` locks the allocation and puts
  matched pupils in their forms (through the pupils domain).
* **Enhanced transition.** Vulnerable children (SEN K / E, PP, looked
  after, or the primary asked for it) with a plan: extra visits, key
  adult, social story sent, status.
* **September start.** Each child gets a secondary pupil record
  (``incoming_primary`` match / create, or admissions ``admit``), KS2 is
  imported and the platform transfer completed.
* **Exports.** Cohort CSV, event registers, form lists (``safe_cell``).

Events live in :mod:`year6_events` and form allocation in
:mod:`year6_allocation`; both build on the cohort, permissions and audit
trail here.

Who: all staff view; the admissions office / transition lead
(``incoming_primary.EDITORS``) edits. SEN / PP / FSM / LAC / EAL flags are
shown to them and the SENCO roles (``SEN_EDITORS`` / ``SEND_EDITORS``);
the SEND detail from the handover to the SENCO roles only; the
safeguarding flag to :data:`access.SAFEGUARDING_LEADS` only. Nothing here
imports the primary system.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.secondary.core.academic_calendar import school_year as SY
from education_system.systems.secondary.core.permissions.access import (
    SAFEGUARDING_LEADS,
    SEN_EDITORS,
    SEND_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.infrastructure.database import connection as database
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.modules.admissions.domain import admissions as AD
from education_system.systems.secondary.modules.progression.domain import incoming_primary as IP
from education_system.systems.secondary.modules.pupils.domain import pupils as P

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound
ENTRY_YEAR = 7
EDITORS = IP.EDITORS
SENCO_ROLES = SEN_EDITORS | SEND_EDITORS
#: Who sees the SEN / PP / FSM / LAC / EAL flags.
NEEDS_VIEWERS = SENCO_ROLES | EDITORS

#: Admissions statuses that put a child in the cohort.
ADMISSION_STATUSES = ("offered", "accepted", "admitted")
EVENT_TYPES: tuple[str, ...] = (
    "Induction day", "Taster day", "New parents' evening", "Summer school",
    "Enhanced transition visit", "SEN transition meeting", "Other",
)
#: Event types that count as "attended an induction" on the checklist.
INDUCTION_TYPES = frozenset({"Induction day", "Taster day", "Summer school",
                             "Enhanced transition visit"})
AUDIENCES: tuple[str, ...] = (
    "Whole cohort", "Pupils", "Parents / carers", "Pupils and parents",
    "Enhanced transition group", "Invited pupils",
)
ATTENDANCE: dict[str, str] = {"invited": "Invited", "attended": "Attended",
                              "absent": "Absent", "apologies": "Apologies"}
LIAISON_KINDS: tuple[str, ...] = (
    "Visit to primary", "Phone call", "Video call", "E-mail", "Meeting at our school",
    "Y6 teacher conversation", "Other",
)
ENHANCED_STATUSES: tuple[str, ...] = ("Identified", "Plan agreed", "In progress", "Completed")
RELATION_KINDS: dict[str, str] = {"friend": "Friendship request", "keep_apart": "Keep apart"}
KS2_BANDS: tuple[str, ...] = ("Higher", "Expected", "Working towards", "No KS2")
#: A friendship group the auto-suggest keeps together is at most this big.
MAX_CLUSTER = 4
TIMES: tuple[str, ...] = tuple(f"{h:02d}:{m:02d}" for h in range(7, 22) for m in (0, 15, 30, 45))
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
#: Row fields an editor can correct by hand (kept on the next sync).
ROW_FIELDS: tuple[str, ...] = ("feeder_school", "gender", "ks2_reading", "ks2_maths", "notes")
NEEDS_FIELDS: tuple[str, ...] = ("sen_status", "pupil_premium", "fsm", "lac", "eal")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS y6_cohort (
    cohort_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    intake_year        TEXT NOT NULL,
    source             TEXT NOT NULL CHECK (source IN ('platform', 'admissions')),
    transition_id      TEXT UNIQUE,
    application_id     INTEGER UNIQUE REFERENCES applications (application_id)
                       ON DELETE SET NULL,
    pupil_id           INTEGER REFERENCES pupils (pupil_id) ON DELETE SET NULL,
    first_name         TEXT NOT NULL,
    last_name          TEXT NOT NULL,
    preferred_name     TEXT,
    date_of_birth      TEXT,
    gender             TEXT,
    upn                TEXT,
    feeder_school      TEXT,
    source_status      TEXT,
    status_label       TEXT,
    active             INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    handover_state     TEXT,
    ks2_reading        INTEGER,
    ks2_maths          INTEGER,
    sen_status         TEXT CHECK (sen_status IS NULL OR sen_status IN ('N', 'K', 'E')),
    pupil_premium      INTEGER,
    fsm                INTEGER,
    lac                INTEGER,
    eal                INTEGER,
    report_enhanced    INTEGER NOT NULL DEFAULT 0,
    report_enhanced_reason TEXT,
    safeguarding_flag  INTEGER,
    manual_fields      TEXT,
    notes              TEXT,
    synced_at          TEXT,
    synced_by          TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_y6_cohort_year ON y6_cohort (intake_year, last_name);
CREATE TABLE IF NOT EXISTS y6_liaison (
    liaison_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    intake_year   TEXT NOT NULL,
    school        TEXT NOT NULL,
    cohort_id     INTEGER REFERENCES y6_cohort (cohort_id) ON DELETE CASCADE,
    kind          TEXT NOT NULL,
    held_on       TEXT NOT NULL,
    staff_name    TEXT,
    contact_name  TEXT,
    summary       TEXT NOT NULL,
    follow_up     TEXT,
    created_by    TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_y6_liaison ON y6_liaison (intake_year, school);
CREATE TABLE IF NOT EXISTS y6_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    intake_year  TEXT NOT NULL,
    title        TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    event_date   TEXT NOT NULL,
    start_time   TEXT,
    end_time     TEXT,
    audience     TEXT NOT NULL,
    location     TEXT,
    notes        TEXT,
    created_by   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_y6_events ON y6_events (intake_year, event_date);
CREATE TABLE IF NOT EXISTS y6_event_invites (
    event_id    INTEGER NOT NULL REFERENCES y6_events (event_id) ON DELETE CASCADE,
    cohort_id   INTEGER NOT NULL REFERENCES y6_cohort (cohort_id) ON DELETE CASCADE,
    attendance  TEXT NOT NULL DEFAULT 'invited'
                CHECK (attendance IN ('invited', 'attended', 'absent', 'apologies')),
    invited_by  TEXT,
    marked_by   TEXT,
    marked_at   TEXT,
    PRIMARY KEY (event_id, cohort_id)
);
CREATE TABLE IF NOT EXISTS y6_relationships (
    rel_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cohort_id       INTEGER NOT NULL REFERENCES y6_cohort (cohort_id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN ('friend', 'keep_apart')),
    other_name      TEXT NOT NULL COLLATE NOCASE,
    other_cohort_id INTEGER REFERENCES y6_cohort (cohort_id) ON DELETE SET NULL,
    source          TEXT NOT NULL DEFAULT 'staff' CHECK (source IN ('report', 'staff')),
    note            TEXT,
    created_by      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (cohort_id, kind, other_name)
);
CREATE TABLE IF NOT EXISTS y6_allocation (
    cohort_id     INTEGER PRIMARY KEY REFERENCES y6_cohort (cohort_id) ON DELETE CASCADE,
    form_name     TEXT NOT NULL,
    how           TEXT NOT NULL DEFAULT 'manual' CHECK (how IN ('auto', 'manual')),
    allocated_by  TEXT,
    allocated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS y6_allocation_publish (
    intake_year   TEXT PRIMARY KEY,
    published_at  TEXT NOT NULL,
    published_by  TEXT
);
CREATE TABLE IF NOT EXISTS y6_enhanced (
    cohort_id          INTEGER PRIMARY KEY REFERENCES y6_cohort (cohort_id) ON DELETE CASCADE,
    manual             INTEGER NOT NULL DEFAULT 0 CHECK (manual IN (0, 1)),
    manual_reason      TEXT,
    extra_visits       INTEGER NOT NULL DEFAULT 0,
    key_adult          TEXT,
    social_story_sent  INTEGER NOT NULL DEFAULT 0 CHECK (social_story_sent IN (0, 1)),
    plan               TEXT,
    status             TEXT NOT NULL DEFAULT 'Identified',
    updated_by         TEXT,
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS y6_audit (
    audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    intake_year  TEXT,
    cohort_id    INTEGER,
    action       TEXT NOT NULL,
    detail       TEXT,
    actor        TEXT NOT NULL,
    at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_y6_audit ON y6_audit (intake_year, audit_id);
"""
database.register_schema("year6_transition", _SCHEMA)


# ── Model ────────────────────────────────────────────────────────────

def ks2_band(reading: Any, maths: Any) -> str:
    have = [int(s) for s in (reading, maths) if s not in (None, "")]
    if not have:
        return "No KS2"
    avg = sum(have) / len(have)
    return "Higher" if avg >= 110 else "Expected" if avg >= 100 else "Working towards"


@dataclass(frozen=True)
class CohortRow:
    """One expected child, as one viewer may see them (flags they may not see are None)."""

    cohort_id: int
    intake_year: str
    source: str
    transition_id: str | None
    application_id: int | None
    pupil_id: int | None
    first_name: str
    last_name: str
    preferred_name: str | None
    date_of_birth: str | None
    gender: str | None
    upn: str | None
    feeder_school: str | None
    status_label: str
    active: bool
    handover_state: str | None
    ks2_reading: int | None
    ks2_maths: int | None
    sen_status: str | None = None
    pupil_premium: bool | None = None
    fsm: bool | None = None
    lac: bool | None = None
    eal: bool | None = None
    enhanced: bool = False
    enhanced_reasons: tuple[str, ...] = ()
    safeguarding: bool | None = None
    form_name: str | None = None
    form_how: str | None = None
    progress: tuple[int, int] = (0, 0)
    notes: str | None = None

    @property
    def name(self) -> str:
        first = self.preferred_name or self.first_name
        return f"{self.last_name}, {first}".strip(", ")

    @property
    def ks2_band(self) -> str:
        return ks2_band(self.ks2_reading, self.ks2_maths)

    @property
    def source_label(self) -> str:
        return "Platform (primary)" if self.source == "platform" else "Admissions"

    @property
    def progress_label(self) -> str:
        done, total = self.progress
        return f"{done}/{total}" if total else ""


@dataclass
class Suggestion:
    plan: dict[int, str]
    unplaced: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in EDITORS


def can_see_needs(actor: Principal) -> bool:
    return actor.role in NEEDS_VIEWERS


def is_senco(actor: Principal) -> bool:
    return actor.role in SENCO_ROLES


def is_safeguarding_lead(actor: Principal) -> bool:
    return actor.role in SAFEGUARDING_LEADS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"year6.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see the Year 6 transition.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    _require_staff(actor, action, target)
    if not is_editor(actor):
        _deny(actor, action, target, "Only the admissions office / transition lead can do "
                                     "that.")


def _require_plan_editor(actor: Principal, action: str, target: Any = None) -> None:
    """Enhanced-transition plans: the transition lead or the SENCO."""
    _require_staff(actor, action, target)
    if not (is_editor(actor) or is_senco(actor)):
        _deny(actor, action, target, "Only the transition lead or the SENCO can change "
                                     "enhanced-transition plans.")


def _audit(conn, action: str, actor: Principal, intake_year: str | None,
           cohort_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO y6_audit (intake_year, cohort_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?, ?)",
                 (intake_year, cohort_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(intake_year: str | None = None, *, cohort_id: int | None = None,
            limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM y6_audit WHERE 1 = 1", []
    if intake_year:
        sql += " AND intake_year = ?"
        params.append(intake_year)
    if cohort_id is not None:
        sql += " AND cohort_id = ?"
        params.append(int(cohort_id))
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                            (*params, int(limit))).fetchall()
    return [{"at": r["at"], "cohort_id": r["cohort_id"], "action": r["action"],
             "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")} for r in rows]


# ── Small helpers ────────────────────────────────────────────────────

def intake_choices(today: _dt.date | None = None) -> list[str]:
    return AD.academic_year_choices(today)


def default_intake(today: _dt.date | None = None) -> str:
    """The September intake being planned: next September's."""
    return AD.next_academic_year(today)


def _year(value: Any) -> str:
    text = str(value or "").strip()
    if not re.match(r"^\d{4}/\d{2}$", text) or (int(text[:4]) + 1) % 100 != int(text[5:]):
        raise ValidationError(["Intake year must look like 2026/27"])
    return text


def _intake_of(effective_date: str | None) -> str:
    try:
        return SY.year_of(str(effective_date)[:10]) if effective_date else default_intake()
    except ValueError:
        return default_intake()


def _text(value: Any, limit: int = 200) -> str | None:
    text = " ".join(str(value or "").split())
    return text[:limit] or None


def _long(value: Any, limit: int = 4000) -> str | None:
    text = str(value or "").strip()
    return text[:limit] or None


def _date(value: Any, label: str, problems: list[str], *, required: bool = True
          ) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            problems.append(f"{label} is required")
        return None
    try:
        return _dt.date.fromisoformat(text).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _int_or_none(value: Any, label: str, problems: list[str], lo: int, hi: int) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(str(value).strip())
    except ValueError:
        problems.append(f"{label} must be a whole number")
        return None
    if not lo <= n <= hi:
        problems.append(f"{label} must be between {lo} and {hi}")
        return None
    return n


def _bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _norm(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def _names(values: Any) -> list[str]:
    """A list of names from the report (a list, or a comma / newline list)."""
    if isinstance(values, str):
        values = re.split(r"[,;\n]", values)
    if not isinstance(values, (list, tuple)):
        return []
    out = []
    for v in values:
        if isinstance(v, dict):
            v = v.get("name") or " ".join(str(v.get(k) or "") for k in ("first_name",
                                                                         "last_name"))
        t = _text(v, 100)
        if t:
            out.append(t)
    return out


# ── Reading the cohort ───────────────────────────────────────────────

def _published(conn, intake_year: str) -> dict[str, Any] | None:
    r = conn.execute("SELECT * FROM y6_allocation_publish WHERE intake_year = ?",
                     (intake_year,)).fetchone()
    return dict(r) if r else None


def publication(intake_year: str) -> dict[str, Any] | None:
    """``{published_at, published_by}`` once the allocation is published."""
    with database.connect() as conn:
        return _published(conn, _year(intake_year))


def _raw_rows(conn, intake_year: str, include_inactive: bool = True) -> list[dict[str, Any]]:
    sql = ("SELECT c.*, a.form_name, a.how AS form_how FROM y6_cohort c "
           "LEFT JOIN y6_allocation a ON a.cohort_id = c.cohort_id WHERE c.intake_year = ?")
    if not include_inactive:
        sql += " AND c.active = 1"
    return [dict(r) for r in conn.execute(sql + " ORDER BY c.last_name, c.first_name",
                                          (intake_year,))]


def _enhanced_reasons(r: dict[str, Any], manual: dict[int, dict[str, Any]],
                      detail: bool) -> tuple[str, ...]:
    out = []
    if detail:
        if r.get("sen_status") == "E":
            out.append("EHC plan")
        elif r.get("sen_status") == "K":
            out.append("SEN support")
        if r.get("pupil_premium"):
            out.append("Pupil premium")
        if r.get("lac"):
            out.append("Looked after")
    elif r.get("sen_status") in ("K", "E") or r.get("pupil_premium") or r.get("lac"):
        out.append("Vulnerable (details: SENCO / transition lead)")
    if r.get("report_enhanced"):
        reason = r.get("report_enhanced_reason")
        out.append("Primary asked" + (f": {reason}" if reason else ""))
    m = manual.get(r["cohort_id"])
    if m and m.get("manual"):
        out.append("Added by staff" + (f": {m['manual_reason']}" if m.get("manual_reason")
                                       else ""))
    return tuple(out)


def _is_enhanced(r: dict[str, Any], manual: dict[int, dict[str, Any]]) -> bool:
    m = manual.get(r["cohort_id"])
    return bool(r.get("sen_status") in ("K", "E") or r.get("pupil_premium") or r.get("lac")
                or r.get("report_enhanced") or (m and m.get("manual")))


def _checklist_state(r: dict[str, Any], incoming: dict[str, dict[str, Any]],
                     attended: set[int], ks2_have: set[int]) -> list[tuple[str, bool]]:
    items: list[tuple[str, bool]] = []
    if r["source"] == "platform":
        loc = incoming.get(r.get("transition_id") or "", {})
        items.append(("Handover acknowledged", r.get("handover_state") == "acknowledged"))
        items.append(("Matched to a pupil record", bool(r.get("pupil_id"))))
        items.append(("KS2 imported", bool(loc.get("ks2_imported_at"))
                      or (r.get("pupil_id") in ks2_have)))
        if r.get("sen_status") in ("K", "E"):
            items.append(("SEN information passed to the SENCO", bool(loc.get("sen_passed_at"))))
    else:
        items.append(("Place accepted", r.get("source_status") in ("accepted", "admitted")))
        items.append(("Pupil record created", bool(r.get("pupil_id"))))
        items.append(("KS2 recorded", r.get("ks2_reading") is not None
                      or r.get("ks2_maths") is not None or r.get("pupil_id") in ks2_have))
    items.append(("Attended an induction / taster event", r["cohort_id"] in attended))
    items.append(("Form allocated", bool(r.get("form_name"))))
    return items


def _context(conn, intake_year: str) -> tuple[dict, set[int], set[int], dict]:
    incoming = {x["transition_id"]: dict(x) for x in conn.execute(
        "SELECT * FROM incoming_primary_pupils")}
    attended = {x["cohort_id"] for x in conn.execute(
        "SELECT i.cohort_id FROM y6_event_invites i JOIN y6_events e ON e.event_id = "
        "i.event_id WHERE e.intake_year = ? AND i.attendance = 'attended' AND e.event_type "
        f"IN ({', '.join('?' for _ in INDUCTION_TYPES)})",
        (intake_year, *sorted(INDUCTION_TYPES)))}
    ks2_have = {x["pupil_id"] for x in conn.execute(
        "SELECT pupil_id FROM ks2_prior_attainment WHERE reading_scaled IS NOT NULL OR "
        "maths_scaled IS NOT NULL")}
    manual = {x["cohort_id"]: dict(x) for x in conn.execute("SELECT * FROM y6_enhanced")}
    return incoming, attended, ks2_have, manual


def _ks2_tables_ready() -> None:
    # headline_measures owns ks2_prior_attainment; import it so the table exists.
    from education_system.systems.secondary.modules.assessment.domain import (  # noqa: F401
        headline_measures,
    )


def _view(r: dict[str, Any], actor: Principal, ctx: tuple) -> CohortRow:
    incoming, attended, ks2_have, manual = ctx
    needs = can_see_needs(actor)
    items = _checklist_state(r, incoming, attended, ks2_have)
    flag = (lambda k: None if r.get(k) is None else bool(r[k])) if needs else (lambda k: None)
    return CohortRow(
        r["cohort_id"], r["intake_year"], r["source"], r.get("transition_id"),
        r.get("application_id"), r.get("pupil_id"), r["first_name"], r["last_name"],
        r.get("preferred_name"), r.get("date_of_birth"), r.get("gender"), r.get("upn"),
        r.get("feeder_school"), r.get("status_label") or "", bool(r["active"]),
        r.get("handover_state"), r.get("ks2_reading"), r.get("ks2_maths"),
        sen_status=r.get("sen_status") if needs else None,
        pupil_premium=flag("pupil_premium"), fsm=flag("fsm"), lac=flag("lac"),
        eal=flag("eal"), enhanced=_is_enhanced(r, manual),
        enhanced_reasons=_enhanced_reasons(r, manual, needs),
        safeguarding=(bool(r["safeguarding_flag"]) if r.get("safeguarding_flag") is not None
                      else None) if is_safeguarding_lead(actor) else None,
        form_name=r.get("form_name"), form_how=r.get("form_how"),
        progress=(sum(1 for _l, d in items if d), len(items)), notes=r.get("notes"))


def cohort(intake_year: str, *, actor: Principal, include_inactive: bool = False,
           search: str | None = None, feeder: str | None = None,
           form: str | None = None) -> list[CohortRow]:
    """Everyone expected for *intake_year* (as :func:`sync` last saw them)."""
    _require_staff(actor, "view")
    year = _year(intake_year)
    _ks2_tables_ready()
    with database.connect() as conn:
        raw = _raw_rows(conn, year, include_inactive)
        ctx = _context(conn, year)
    rows = [_view(r, actor, ctx) for r in raw]
    if feeder:
        rows = [r for r in rows if _norm(r.feeder_school) == _norm(feeder)]
    if form:
        rows = [r for r in rows if (r.form_name or "") == ("" if form == "(none)" else form)]
    for term in (search or "").lower().split():
        rows = [r for r in rows if term in f"{r.first_name} {r.last_name} {r.preferred_name or ''}"
                f" {r.upn or ''} {r.feeder_school or ''}".lower()]
    activity_log.record("year6.view", principal=actor, intake=year, shown=len(rows))
    return rows


def get(cohort_id: int, *, actor: Principal) -> CohortRow:
    _require_staff(actor, "view", cohort_id)
    _ks2_tables_ready()
    with database.connect() as conn:
        r = conn.execute("SELECT c.*, a.form_name, a.how AS form_how FROM y6_cohort c "
                         "LEFT JOIN y6_allocation a ON a.cohort_id = c.cohort_id "
                         "WHERE c.cohort_id = ?", (int(cohort_id),)).fetchone()
        if r is None:
            raise NotFound(f"No child {cohort_id} in the Year 6 transition cohort")
        r = dict(r)
        ctx = _context(conn, r["intake_year"])
    return _view(r, actor, ctx)


def checklist(cohort_id: int, *, actor: Principal) -> list[tuple[str, bool]]:
    """This child's transition checklist: ``[(item, done)]``."""
    row = get(cohort_id, actor=actor)
    with database.connect() as conn:
        r = dict(conn.execute("SELECT c.*, a.form_name FROM y6_cohort c LEFT JOIN "
                              "y6_allocation a ON a.cohort_id = c.cohort_id WHERE "
                              "c.cohort_id = ?", (row.cohort_id,)).fetchone())
        incoming, attended, ks2_have, _m = _context(conn, row.intake_year)
    items = _checklist_state(r, incoming, attended, ks2_have)
    if not can_see_needs(actor):
        items = [i for i in items if "SENCO" not in i[0]]
    return items


def counts(intake_year: str, *, actor: Principal) -> dict[str, int]:
    rows = cohort(intake_year, actor=actor)
    out = {"Expected": len(rows),
           "From the platform": sum(1 for r in rows if r.source == "platform"),
           "From admissions": sum(1 for r in rows if r.source == "admissions"),
           "With a pupil record": sum(1 for r in rows if r.pupil_id),
           "Form allocated": sum(1 for r in rows if r.form_name),
           "Enhanced transition": sum(1 for r in rows if r.enhanced)}
    if can_see_needs(actor):
        out["SEN K / E"] = sum(1 for r in rows if r.sen_status in ("K", "E"))
        out["Pupil premium"] = sum(1 for r in rows if r.pupil_premium)
    return out


# ── Sync from the platform queue and admissions ──────────────────────

def _upsert(conn, key_col: str, key: Any, values: dict[str, Any]) -> tuple[int, bool]:
    r = conn.execute(f"SELECT cohort_id, manual_fields FROM y6_cohort WHERE {key_col} = ?",  # noqa: S608 - key_col is a fixed name
                     (key,)).fetchone()
    if r is None:
        cols = list(values)
        cur = conn.execute(f"INSERT INTO y6_cohort ({', '.join(cols)}) "  # noqa: S608 - fixed column names
                           f"VALUES ({', '.join('?' for _ in cols)})", list(values.values()))
        return int(cur.lastrowid), True
    keep = set(json.loads(r["manual_fields"] or "[]"))
    upd = {k: v for k, v in values.items() if k not in keep}
    if upd:
        conn.execute(f"UPDATE y6_cohort SET {', '.join(f'{k} = ?' for k in upd)}, "  # noqa: S608 - fixed column names
                     "updated_at = datetime('now') WHERE cohort_id = ?",
                     [*upd.values(), r["cohort_id"]])
    return int(r["cohort_id"]), False


def _merge(conn, keep: int, drop: int) -> None:
    """Fold an admissions-only row into the platform row for the same child."""
    for table in ("y6_liaison", "y6_relationships", "y6_event_invites", "y6_allocation",
                  "y6_enhanced"):
        conn.execute(f"UPDATE OR IGNORE {table} SET cohort_id = ? WHERE cohort_id = ?",  # noqa: S608 - fixed table names
                     (keep, drop))
    conn.execute("UPDATE y6_relationships SET other_cohort_id = ? WHERE other_cohort_id = ?",
                 (keep, drop))
    conn.execute("DELETE FROM y6_cohort WHERE cohort_id = ?", (drop,))


def _platform_values(item: IP.Incoming, h: dict[str, Any] | None, actor: Principal,
                     year: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    payload = (h or {}).get("payload") or {}
    ident = payload.get("child_identity") if isinstance(payload.get("child_identity"),
                                                         dict) else {}
    pupil = P.get_pupil(item.pupil_id) if item.pupil_id else None
    ks2 = IP.ks2_scores(h)
    report = IP.transition_report(h)
    values: dict[str, Any] = {
        "intake_year": year, "source": "platform", "transition_id": item.transition_id,
        "pupil_id": item.pupil_id,
        "first_name": ident.get("first_name") or item.first_name or "?",
        "last_name": ident.get("last_name") or item.last_name or "?",
        "preferred_name": ident.get("preferred_name") or None,
        "date_of_birth": ident.get("date_of_birth") or item.date_of_birth,
        "gender": IP._gender(ident.get("gender")) or (pupil.gender if pupil else None),
        "upn": ident.get("upn") or item.upn,
        "feeder_school": _text(ident.get("school_name")) or "Unknown primary (platform)",
        "source_status": "rejected" if item.status_label == "Rejected" else item.status,
        "status_label": item.status_label, "active": int(item.status != "cancelled"),
        "handover_state": ("acknowledged" if item.acknowledged_at else "ready")
        if item.handover_ready else "not yet",
        "ks2_reading": _ks2_int(ks2.get("reading_scaled")),
        "ks2_maths": _ks2_int(ks2.get("maths_scaled")),
        "report_enhanced": int(bool(report and report.get("enhanced_transition"))),
        "report_enhanced_reason": _text((report or {}).get("enhanced_reason"), 300),
        "synced_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "synced_by": actor.username,
    }
    if h is not None and "send_provision" not in (h.get("withheld") or []):
        values["sen_status"] = IP.sen_from(payload)   # withheld from this role: keep what we had
    support = IP.support_from(payload)
    for k_from, k_to in (("pupil_premium", "pupil_premium"), ("fsm", "fsm"), ("eal", "eal")):
        if k_from in support:
            values[k_to] = int(support[k_from])
    if "lac" in support or "plac" in support:
        values["lac"] = int(bool(support.get("lac") or support.get("plac")))
    sg = (h or {}).get("safeguarding")
    if sg is not None:                       # only a safeguarding lead's read carries it
        values["safeguarding_flag"] = int(bool(sg.get("exists")))
    return values, report


def _ks2_int(v: Any) -> int | None:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return None
    return n if 80 <= n <= 120 else None


def _admission_values(a: AD.Application, actor: Principal, year: str) -> dict[str, Any]:
    ks2r = ks2m = None
    if a.admitted_pupil_id:
        from education_system.systems.secondary.modules.assessment.domain import (
            headline_measures as HM,
        )
        k = HM.get_ks2(a.admitted_pupil_id)
        if k:
            ks2r, ks2m = k.reading_scaled, k.maths_scaled
    values: dict[str, Any] = {
        "intake_year": year, "source": "admissions", "application_id": a.application_id,
        "pupil_id": a.admitted_pupil_id, "first_name": a.legal_first_name,
        "last_name": a.legal_last_name, "preferred_name": a.preferred_name,
        "date_of_birth": a.date_of_birth, "gender": a.gender, "upn": a.upn,
        "feeder_school": _text(a.current_school) or "Unknown primary",
        "source_status": a.status, "status_label": a.status_label,
        "active": int(a.status in ADMISSION_STATUSES), "handover_state": None,
        "sen_status": a.sen_status, "lac": int(a.looked_after in ("current", "previous")),
        "synced_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "synced_by": actor.username,
    }
    if ks2r is not None or ks2m is not None:
        values.update(ks2_reading=ks2r, ks2_maths=ks2m)
    if a.admitted_pupil_id:
        p = P.get_pupil(a.admitted_pupil_id)
        if p:
            values.update(fsm=int(p.fsm_eligible), eal=int(p.eal))
    return values


def _prefill_relationships(conn, cohort_id: int, report: dict[str, Any] | None) -> int:
    if not report:
        return 0
    n = 0
    for kind, key in (("friend", "friendships"), ("keep_apart", "keep_apart")):
        for name in _names(report.get(key)):
            cur = conn.execute("INSERT OR IGNORE INTO y6_relationships (cohort_id, kind, "
                               "other_name, source, created_by) VALUES (?, ?, ?, 'report', "
                               "'primary transition report')", (cohort_id, kind, name))
            n += cur.rowcount or 0
    return n


def _resolve(rows: list[dict[str, Any]], name: str, feeder: str | None,
             exclude: int) -> int | None:
    n = _norm(name)
    others = [r for r in rows if r["cohort_id"] != exclude]
    full = [r for r in others if n in {_norm(f"{r['first_name']} {r['last_name']}"),
                                       _norm(f"{r.get('preferred_name') or ''} "
                                             f"{r['last_name']}")}]
    if len(full) == 1:
        return full[0]["cohort_id"]
    if " " not in n:
        first = [r for r in others if n in (_norm(r["first_name"]),
                                             _norm(r.get("preferred_name")))]
        same = [r for r in first if _norm(r.get("feeder_school")) == _norm(feeder)]
        for pool in (same, first):
            if len(pool) == 1:
                return pool[0]["cohort_id"]
    return None


def _resolve_all(conn, year: str) -> int:
    rows = _raw_rows(conn, year)
    by_id = {r["cohort_id"]: r for r in rows}
    n = 0
    for rel in conn.execute(
            "SELECT r.rel_id, r.cohort_id, r.other_name FROM y6_relationships r JOIN y6_cohort c "
            "ON c.cohort_id = r.cohort_id WHERE c.intake_year = ? AND r.other_cohort_id IS NULL",
            (year,)).fetchall():
        me = by_id.get(rel["cohort_id"])
        other = _resolve(rows, rel["other_name"], me.get("feeder_school") if me else None,
                         rel["cohort_id"])
        if other is not None:
            conn.execute("UPDATE y6_relationships SET other_cohort_id = ? WHERE rel_id = ?",
                         (other, rel["rel_id"]))
            n += 1
    return n


def sync(intake_year: str, *, actor: Principal, db_path: str | None = None) -> dict[str, int]:
    """Bring the cohort up to date from the platform queue (transfers from
    primary starting in *intake_year*) and Year 7 admissions offers. Rows
    whose transfer was rejected or whose offer was declined / withdrawn stay
    but are marked inactive. Hand corrections (:func:`update_row`) are kept."""
    _require_editor(actor, "sync")
    year = _year(intake_year)
    out = {"platform": 0, "admissions": 0, "new": 0, "merged": 0, "report_names": 0,
           "resolved": 0, "unreadable": 0}
    try:
        items = [i for i in IP.queue(actor=actor, include_closed=True, db_path=db_path)
                 if _intake_of(i.effective_date) == year]
    except (ValidationError, PermissionDenied, NotFound):
        raise
    except Exception:  # noqa: BLE001 - the platform unreachable: admissions still sync
        items = []
        out["unreadable"] += 1
    apps = AD.list_applications(academic_year=year, year_group=ENTRY_YEAR)
    by_app = {a.application_id: a for a in apps}
    claimed: set[int] = set()
    for item in items:
        try:
            h = IP.handover(item.transition_id, actor=actor, db_path=db_path)
        except (PermissionDenied, NotFound):
            h = None
            out["unreadable"] += 1
        values, report = _platform_values(item, h, actor, year)
        app_id = item.application_id
        if app_id is None:
            for a in apps:
                if a.date_of_birth == values["date_of_birth"] and \
                        _norm(a.legal_last_name) == _norm(values["last_name"]) and \
                        _norm(a.legal_first_name) == _norm(values["first_name"]):
                    app_id = a.application_id
                    break
        with database.connect() as conn:
            cid, new = _upsert(conn, "transition_id", item.transition_id, values)
            if app_id is not None and app_id not in claimed:
                claimed.add(app_id)
                other = conn.execute("SELECT cohort_id FROM y6_cohort WHERE application_id = ? "
                                     "AND cohort_id != ?", (app_id, cid)).fetchone()
                if other:
                    _merge(conn, cid, other["cohort_id"])
                    out["merged"] += 1
                conn.execute("UPDATE y6_cohort SET application_id = ? WHERE cohort_id = ?",
                             (app_id, cid))
                a = by_app.get(app_id)
                if a and a.admitted_pupil_id and not values.get("pupil_id"):
                    conn.execute("UPDATE y6_cohort SET pupil_id = ? WHERE cohort_id = ?",
                                 (a.admitted_pupil_id, cid))
            out["report_names"] += _prefill_relationships(conn, cid, report)
            if new:
                _audit(conn, "add", actor, year, cid, source="platform")
        out["platform"] += 1
        out["new"] += int(new)
    for a in apps:
        if a.application_id in claimed:
            continue
        with database.connect() as conn:
            r = conn.execute("SELECT cohort_id, source FROM y6_cohort WHERE application_id = ?",
                             (a.application_id,)).fetchone()
            if r is not None and r["source"] == "platform":
                continue                          # matched earlier through the transfer
            if r is None and a.status not in ADMISSION_STATUSES:
                continue
            cid, new = _upsert(conn, "application_id", a.application_id,
                               _admission_values(a, actor, year))
            if new:
                _audit(conn, "add", actor, year, cid, source="admissions")
        out["admissions"] += 1
        out["new"] += int(new)
    with database.connect() as conn:
        out["resolved"] = _resolve_all(conn, year)
        _audit(conn, "sync", actor, year, **out)
    activity_log.record("year6.sync", principal=actor, intake=year, **out)
    return out


def update_row(cohort_id: int, changes: dict[str, Any], *, actor: Principal) -> CohortRow:
    """Correct a child's planning details by hand (feeder school, gender,
    KS2, notes; needs flags for the SENCO / transition lead). The fields
    changed are kept on later syncs."""
    row = get(cohort_id, actor=actor)
    allowed = set(ROW_FIELDS)
    if not is_editor(actor):
        if not is_senco(actor):
            _deny(actor, "update", cohort_id, "Only the transition lead can change this.")
        allowed = set()
    if can_see_needs(actor):
        allowed |= set(NEEDS_FIELDS)
    unknown = set(changes) - allowed
    if unknown:
        raise ValidationError([f"You can't change: {', '.join(sorted(unknown))}"])
    problems: list[str] = []
    clean: dict[str, Any] = {}
    for k, v in changes.items():
        if k == "feeder_school":
            clean[k] = _text(v)
        elif k == "gender":
            g = IP._gender(v)
            if v not in (None, "") and not g:
                problems.append(f"Gender must be one of: {', '.join(P.GENDERS)}")
            clean[k] = g or None
        elif k in ("ks2_reading", "ks2_maths"):
            clean[k] = _int_or_none(v, "KS2 " + k[4:] + " scaled score", problems, 80, 120)
        elif k == "notes":
            clean[k] = _long(v, 2000)
        elif k == "sen_status":
            code = str(v or "").strip().upper()[:1] or None
            if code is not None and code not in P.SEN_STATUSES:
                problems.append("SEN status must be N, K or E")
            clean[k] = code
        else:
            clean[k] = int(_bool(v))
    if problems:
        raise ValidationError(problems)
    if not clean:
        return row
    with database.connect() as conn:
        r = conn.execute("SELECT manual_fields FROM y6_cohort WHERE cohort_id = ?",
                         (row.cohort_id,)).fetchone()
        manual = sorted(set(json.loads(r["manual_fields"] or "[]")) | set(clean))
        conn.execute(f"UPDATE y6_cohort SET {', '.join(f'{k} = ?' for k in clean)}, "  # noqa: S608 - keys checked against fixed lists
                     "manual_fields = ?, updated_at = datetime('now') WHERE cohort_id = ?",
                     [*clean.values(), json.dumps(manual), row.cohort_id])
        _audit(conn, "update", actor, row.intake_year, row.cohort_id, fields=sorted(clean))
    activity_log.record("year6.update", target=row.cohort_id, principal=actor,
                        fields=sorted(clean))
    return get(row.cohort_id, actor=actor)


# ── Feeder schools and liaison ───────────────────────────────────────

def feeder_schools(intake_year: str, *, actor: Principal) -> list[dict[str, Any]]:
    """Each feeder primary with how many are coming from it and the last contact."""
    rows = cohort(intake_year, actor=actor)
    needs = can_see_needs(actor)
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        name = r.feeder_school or "Unknown primary"
        d = out.setdefault(name, {"school": name, "expected": 0, "platform": 0,
                                  "admissions": 0, "enhanced": 0,
                                  "sen": 0 if needs else None,
                                  "pupil_premium": 0 if needs else None,
                                  "contacts": 0, "last_contact": None})
        d["expected"] += 1
        d["platform" if r.source == "platform" else "admissions"] += 1
        d["enhanced"] += int(r.enhanced)
        if needs:
            d["sen"] += int(r.sen_status in ("K", "E"))
            d["pupil_premium"] += int(bool(r.pupil_premium))
    with database.connect() as conn:
        for x in conn.execute("SELECT school, COUNT(*) AS n, MAX(held_on) AS last FROM "
                              "y6_liaison WHERE intake_year = ? AND cohort_id IS NULL "
                              "GROUP BY school", (_year(intake_year),)):
            key = next((k for k in out if _norm(k) == _norm(x["school"])), x["school"])
            d = out.setdefault(key, {"school": key, "expected": 0, "platform": 0,
                                     "admissions": 0, "enhanced": 0,
                                     "sen": 0 if needs else None,
                                     "pupil_premium": 0 if needs else None,
                                     "contacts": 0, "last_contact": None})
            d["contacts"] += x["n"]
            d["last_contact"] = max(filter(None, (d["last_contact"], x["last"])), default=None)
    return sorted(out.values(), key=lambda d: (-d["expected"], d["school"]))


def _clean_liaison(data: dict[str, Any], problems: list[str]) -> dict[str, Any]:
    out = {"school": _text(data.get("school")),
           "kind": data.get("kind"),
           "held_on": _date(data.get("held_on"), "Date", problems),
           "staff_name": _text(data.get("staff_name"), 120),
           "contact_name": _text(data.get("contact_name"), 120),
           "summary": _long(data.get("summary")),
           "follow_up": _long(data.get("follow_up"), 1000)}
    if not out["school"]:
        problems.append("Choose the primary school")
    if out["kind"] not in LIAISON_KINDS:
        problems.append("Choose what kind of contact it was")
    if not out["summary"]:
        problems.append("Write what was discussed")
    if out["held_on"] and out["held_on"] > _dt.date.today().isoformat():
        problems.append("A contact can't be recorded before it happens")
    return out


def add_liaison(intake_year: str, data: dict[str, Any], *, actor: Principal,
                cohort_id: int | None = None) -> int:
    """Record a visit / call to a feeder primary, or (with *cohort_id*) a
    note about one child (the Year 6 teacher conversation)."""
    _require_editor(actor, "liaison")
    year = _year(intake_year)
    data = dict(data)
    if cohort_id is not None:
        row = get(cohort_id, actor=actor)
        data.setdefault("school", row.feeder_school)
        data["school"] = data.get("school") or row.feeder_school
    problems: list[str] = []
    clean = _clean_liaison(data, problems)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        cur = conn.execute(
            "INSERT INTO y6_liaison (intake_year, school, cohort_id, kind, held_on, staff_name, "
            "contact_name, summary, follow_up, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (year, clean["school"], cohort_id, clean["kind"], clean["held_on"],
             clean["staff_name"], clean["contact_name"], clean["summary"], clean["follow_up"],
             actor.username))
        lid = int(cur.lastrowid)
        _audit(conn, "liaison_add", actor, year, cohort_id, liaison=lid, kind=clean["kind"])
    activity_log.record("year6.liaison_add", target=lid, principal=actor)
    return lid


def update_liaison(liaison_id: int, data: dict[str, Any], *, actor: Principal) -> None:
    _require_editor(actor, "liaison")
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM y6_liaison WHERE liaison_id = ?",
                         (int(liaison_id),)).fetchone()
        if r is None:
            raise NotFound(f"No liaison record {liaison_id}")
        problems: list[str] = []
        clean = _clean_liaison({**dict(r), **data}, problems)
        if problems:
            raise ValidationError(problems)
        conn.execute(f"UPDATE y6_liaison SET {', '.join(f'{k} = ?' for k in clean)}, "  # noqa: S608 - fixed keys
                     "updated_at = datetime('now') WHERE liaison_id = ?",
                     [*clean.values(), int(liaison_id)])
        _audit(conn, "liaison_update", actor, r["intake_year"], r["cohort_id"],
               liaison=liaison_id)
    activity_log.record("year6.liaison_update", target=liaison_id, principal=actor)


def delete_liaison(liaison_id: int, *, actor: Principal) -> None:
    _require_editor(actor, "liaison")
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM y6_liaison WHERE liaison_id = ?",
                         (int(liaison_id),)).fetchone()
        if r is None:
            raise NotFound(f"No liaison record {liaison_id}")
        conn.execute("DELETE FROM y6_liaison WHERE liaison_id = ?", (int(liaison_id),))
        _audit(conn, "liaison_delete", actor, r["intake_year"], r["cohort_id"],
               liaison=liaison_id, school=r["school"], held_on=r["held_on"])
    activity_log.record("year6.liaison_delete", target=liaison_id, principal=actor)


def liaison(intake_year: str, *, actor: Principal, school: str | None = None,
            cohort_id: int | None = None, pupil_notes: bool | None = None
            ) -> list[dict[str, Any]]:
    """Liaison records, newest first. *pupil_notes* True = per-child notes
    only, False = school contacts only, None = both."""
    _require_staff(actor, "view")
    sql = ("SELECT l.*, c.first_name, c.last_name, c.preferred_name FROM y6_liaison l "
           "LEFT JOIN y6_cohort c ON c.cohort_id = l.cohort_id WHERE l.intake_year = ?")
    params: list[Any] = [_year(intake_year)]
    if school:
        sql += " AND lower(l.school) = lower(?)"
        params.append(school)
    if cohort_id is not None:
        sql += " AND l.cohort_id = ?"
        params.append(int(cohort_id))
    if pupil_notes is True:
        sql += " AND l.cohort_id IS NOT NULL"
    elif pupil_notes is False:
        sql += " AND l.cohort_id IS NULL"
    with database.connect() as conn:
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY l.held_on DESC, l.liaison_id "
                                              "DESC", params)]
    for r in rows:
        r["pupil"] = (f"{r['last_name']}, {r.get('preferred_name') or r['first_name']}"
                      if r.get("cohort_id") else "")
    return rows


def transition_report(cohort_id: int, *, actor: Principal, db_path: str | None = None
                      ) -> dict[str, Any] | None:
    """The primary's transition report for a child coming through the
    platform (read live through the handover; None if not sent)."""
    row = get(cohort_id, actor=actor)
    if row.source != "platform" or not row.transition_id:
        return None
    h = IP.handover(row.transition_id, actor=actor, db_path=db_path)
    activity_log.record("year6.report", target=cohort_id, principal=actor)
    return IP.transition_report(h)


REPORT_LABELS = (("strengths", "Strengths"), ("interests", "Interests"),
                 ("learning_style", "How they learn best"), ("worries", "Worries"),
                 ("friendships", "Friendships"), ("keep_apart", "Keep apart from"),
                 ("all_about_me", "All about me"), ("teacher_comments", "Teacher's comments"),
                 ("enhanced_transition", "Enhanced transition asked for"),
                 ("enhanced_reason", "Why"), ("written_by", "Written by"),
                 ("written_on", "Written on"))


def report_text(report: dict[str, Any] | None) -> str:
    if not report:
        return "No transition report from the primary school."
    lines = []
    for key, label in REPORT_LABELS:
        v = report.get(key)
        if v in (None, "", [], {}):
            continue
        if isinstance(v, bool):
            v = "Yes" if v else "No"
        elif isinstance(v, (list, tuple)):
            v = ", ".join(_names(v))
        lines.append(f"{label}:\n    {v}")
    return "\n\n".join(lines) or "The transition report is empty."


def pupil_text(cohort_id: int, *, actor: Principal, db_path: str | None = None) -> str:
    """Everything this viewer may see about one expected child."""
    row = get(cohort_id, actor=actor)
    lines = [f"{row.name} ({row.first_name} {row.last_name})",
             f"  Born {row.date_of_birth or '-'}   Gender {row.gender or '-'}   "
             f"UPN {row.upn or '-'}",
             f"  From {row.feeder_school or '-'} via {row.source_label}; status "
             f"{row.status_label}{'' if row.active else ' (not coming)'}",
             f"  KS2 reading {row.ks2_reading or '-'}, maths {row.ks2_maths or '-'} "
             f"({row.ks2_band})",
             f"  Form: {row.form_name or 'not allocated'}"]
    if row.sen_status is not None or can_see_needs(actor):
        yn = lambda v: "-" if v is None else "yes" if v else "no"  # noqa: E731
        lines.append(f"  SEN {row.sen_status or '-'}   PP {yn(row.pupil_premium)}   "
                     f"FSM {yn(row.fsm)}   LAC {yn(row.lac)}   EAL {yn(row.eal)}")
    if row.safeguarding is not None:
        lines.append("  Safeguarding: " + ("a safeguarding file exists - request it DSL to DSL"
                                           if row.safeguarding else "none flagged"))
    if row.enhanced:
        lines.append("  Enhanced transition: " + "; ".join(row.enhanced_reasons))
    lines.append("\nChecklist:")
    lines += [f"  [{'x' if d else ' '}] {label}" for label, d in checklist(cohort_id,
                                                                            actor=actor)]
    if row.source == "platform" and row.transition_id:
        try:
            h = IP.handover(row.transition_id, actor=actor, db_path=db_path)
        except (PermissionDenied, NotFound):
            h = None
        lines.append("\nTransition report:\n" + "\n".join(
            "  " + ln for ln in report_text(IP.transition_report(h)).splitlines()))
        send = ((h or {}).get("payload") or {}).get("send_provision")
        if send and is_senco(actor):
            lines.append("\nSEND provision (SENCO):")
            lines += [f"  {k}: {v}" for k, v in (send.items() if isinstance(send, dict)
                                                  else [("detail", send)])
                      if v not in (None, "", [], {})]
    rels = relationships(row.intake_year, actor=actor, cohort_id=cohort_id)
    if rels:
        lines.append("\nFriendships / keep apart:")
        lines += [f"  {RELATION_KINDS[r['kind']]}: {r['other_label']}" for r in rels]
    notes = liaison(row.intake_year, actor=actor, cohort_id=cohort_id)
    if notes:
        lines.append("\nLiaison notes:")
        lines += [f"  {n['held_on']} {n['kind']} ({n.get('staff_name') or n['created_by']}): "
                  f"{n['summary']}" for n in notes]
    ev = events_for(cohort_id, actor=actor)
    if ev:
        lines.append("\nEvents:")
        lines += [f"  {e['event_date']} {e['title']} - {ATTENDANCE[e['attendance']]}"
                  for e in ev]
    if row.notes:
        lines.append(f"\nNotes: {row.notes}")
    activity_log.record("year6.pupil", target=cohort_id, principal=actor)
    return "\n".join(lines)


def events_for(cohort_id: int, *, actor: Principal) -> list[dict[str, Any]]:
    _require_staff(actor, "view", cohort_id)
    with database.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT e.*, i.attendance FROM y6_event_invites i JOIN y6_events e ON e.event_id = "
            "i.event_id WHERE i.cohort_id = ? ORDER BY e.event_date", (int(cohort_id),))]


# ── Friendships and keep-apart ───────────────────────────────────────

def relationships(intake_year: str, *, actor: Principal, cohort_id: int | None = None,
                  kind: str | None = None) -> list[dict[str, Any]]:
    _require_staff(actor, "view")
    sql = ("SELECT r.*, c.first_name, c.last_name, c.preferred_name, o.first_name AS o_first, "
           "o.last_name AS o_last, o.preferred_name AS o_pref, a.form_name AS my_form, "
           "oa.form_name AS other_form FROM y6_relationships r JOIN y6_cohort c ON "
           "c.cohort_id = r.cohort_id LEFT JOIN y6_cohort o ON o.cohort_id = r.other_cohort_id "
           "LEFT JOIN y6_allocation a ON a.cohort_id = r.cohort_id LEFT JOIN y6_allocation oa "
           "ON oa.cohort_id = r.other_cohort_id WHERE c.intake_year = ?")
    params: list[Any] = [_year(intake_year)]
    if cohort_id is not None:
        sql += " AND (r.cohort_id = ? OR r.other_cohort_id = ?)"
        params += [int(cohort_id), int(cohort_id)]
    if kind:
        sql += " AND r.kind = ?"
        params.append(kind)
    with database.connect() as conn:
        rows = [dict(r) for r in conn.execute(sql + " ORDER BY c.last_name, c.first_name, "
                                              "r.kind, r.other_name", params)]
    for r in rows:
        r["pupil"] = f"{r['last_name']}, {r.get('preferred_name') or r['first_name']}"
        r["other_label"] = (f"{r['o_last']}, {r.get('o_pref') or r['o_first']}"
                            if r.get("other_cohort_id") else f"{r['other_name']} (not matched)")
        r["kind_label"] = RELATION_KINDS[r["kind"]]
        r["source_label"] = "Primary report" if r["source"] == "report" else "Staff"
    return rows


def add_relationship(cohort_id: int, kind: str, *, actor: Principal,
                     other_cohort_id: int | None = None, other_name: str | None = None,
                     note: str | None = None) -> int:
    _require_editor(actor, "relationship", cohort_id)
    me = get(cohort_id, actor=actor)
    if kind not in RELATION_KINDS:
        raise ValidationError(["Choose friendship request or keep apart"])
    name = _text(other_name, 100)
    if other_cohort_id is not None:
        if int(other_cohort_id) == me.cohort_id:
            raise ValidationError(["Choose another child"])
        other = get(other_cohort_id, actor=actor)
        if other.intake_year != me.intake_year:
            raise ValidationError(["The other child isn't in the same intake"])
        name = f"{other.first_name} {other.last_name}"
    if not name:
        raise ValidationError(["Choose the other child"])
    with database.connect() as conn:
        clash = conn.execute(
            "SELECT kind FROM y6_relationships WHERE ((cohort_id = ? AND other_cohort_id = ?) OR "
            "(cohort_id = ? AND other_cohort_id = ?)) AND kind != ?",
            (me.cohort_id, other_cohort_id, other_cohort_id, me.cohort_id, kind)).fetchone() \
            if other_cohort_id is not None else None
        if clash:
            raise ValidationError(["These two are already recorded as "
                                   f"{RELATION_KINDS[clash['kind']].lower()} - remove that "
                                   "first"])
        cur = conn.execute("INSERT OR IGNORE INTO y6_relationships (cohort_id, kind, other_name, "
                           "other_cohort_id, source, note, created_by) VALUES (?, ?, ?, ?, "
                           "'staff', ?, ?)", (me.cohort_id, kind, name, other_cohort_id,
                                              _long(note, 500), actor.username))
        if not cur.rowcount:
            raise ValidationError(["That is already recorded"])
        rid = int(cur.lastrowid)
        _audit(conn, "relationship_add", actor, me.intake_year, me.cohort_id, kind=kind,
               other=other_cohort_id)
    activity_log.record("year6.relationship_add", target=me.cohort_id, principal=actor, kind=kind)
    return rid


def link_relationship(rel_id: int, other_cohort_id: int, *, actor: Principal) -> None:
    """Point a report name that wasn't matched at the right child."""
    _require_editor(actor, "relationship", rel_id)
    with database.connect() as conn:
        r = conn.execute("SELECT r.*, c.intake_year FROM y6_relationships r JOIN y6_cohort c ON "
                         "c.cohort_id = r.cohort_id WHERE rel_id = ?", (int(rel_id),)).fetchone()
        if r is None:
            raise NotFound(f"No relationship {rel_id}")
        o = conn.execute("SELECT intake_year FROM y6_cohort WHERE cohort_id = ?",
                         (int(other_cohort_id),)).fetchone()
        if o is None or o["intake_year"] != r["intake_year"] or \
                int(other_cohort_id) == r["cohort_id"]:
            raise ValidationError(["Choose another child in the same intake"])
        conn.execute("UPDATE y6_relationships SET other_cohort_id = ? WHERE rel_id = ?",
                     (int(other_cohort_id), int(rel_id)))
        _audit(conn, "relationship_link", actor, r["intake_year"], r["cohort_id"], rel=rel_id,
               other=other_cohort_id)


def remove_relationship(rel_id: int, *, actor: Principal) -> None:
    _require_editor(actor, "relationship", rel_id)
    with database.connect() as conn:
        r = conn.execute("SELECT r.*, c.intake_year FROM y6_relationships r JOIN y6_cohort c ON "
                         "c.cohort_id = r.cohort_id WHERE rel_id = ?", (int(rel_id),)).fetchone()
        if r is None:
            raise NotFound(f"No relationship {rel_id}")
        conn.execute("DELETE FROM y6_relationships WHERE rel_id = ?", (int(rel_id),))
        _audit(conn, "relationship_remove", actor, r["intake_year"], r["cohort_id"],
               kind=r["kind"], other=r["other_name"])
    activity_log.record("year6.relationship_remove", target=rel_id, principal=actor)


def _set_form(pupil_id: int, form: str, actor: Principal) -> str | None:
    p = P.get_pupil(pupil_id)
    if p is None:
        return "pupil record not found"
    if p.roll_status != "on_roll" or p.year_group != ENTRY_YEAR:
        return f"not set - the record is Year {p.year_group}, {p.roll_status_label.lower()}"
    if (p.form_group or "") == form:
        return None
    try:
        P.update_pupil(pupil_id, {"form_group": form}, actor=actor)
    except (ValidationError, PermissionDenied) as e:
        return str(e)
    return None


# ── Enhanced transition ──────────────────────────────────────────────

def enhanced(intake_year: str, *, actor: Principal) -> list[dict[str, Any]]:
    """Children needing an enhanced transition, with their plan."""
    rows = [r for r in cohort(intake_year, actor=actor) if r.enhanced]
    with database.connect() as conn:
        plans = {x["cohort_id"]: dict(x) for x in conn.execute("SELECT * FROM y6_enhanced")}
        visits = {x["cohort_id"]: x["n"] for x in conn.execute(
            "SELECT i.cohort_id, COUNT(*) AS n FROM y6_event_invites i JOIN y6_events e ON "
            "e.event_id = i.event_id WHERE i.attendance = 'attended' AND e.event_type = "
            "'Enhanced transition visit' GROUP BY i.cohort_id")}
    out = []
    for r in rows:
        p = plans.get(r.cohort_id, {})
        out.append({"row": r, "status": p.get("status") or "Identified",
                    "extra_visits": p.get("extra_visits") or 0,
                    "visits_attended": visits.get(r.cohort_id, 0),
                    "key_adult": p.get("key_adult"),
                    "social_story_sent": bool(p.get("social_story_sent")),
                    "plan": p.get("plan"), "manual": bool(p.get("manual")),
                    "updated_by": p.get("updated_by"), "updated_at": p.get("updated_at")})
    return out


def set_plan(cohort_id: int, data: dict[str, Any], *, actor: Principal) -> None:
    """Save an enhanced-transition plan: extra visits planned, key adult,
    social story sent, plan notes, status."""
    _require_plan_editor(actor, "plan", cohort_id)
    row = get(cohort_id, actor=actor)
    problems: list[str] = []
    visits = _int_or_none(data.get("extra_visits"), "Extra visits", problems, 0, 20) or 0
    status = data.get("status") or "Identified"
    if status not in ENHANCED_STATUSES:
        problems.append("Choose the plan's status")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO y6_enhanced (cohort_id, extra_visits, key_adult, social_story_sent, "
            "plan, status, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (cohort_id) DO "
            "UPDATE SET extra_visits = excluded.extra_visits, key_adult = excluded.key_adult, "
            "social_story_sent = excluded.social_story_sent, plan = excluded.plan, status = "
            "excluded.status, updated_by = excluded.updated_by, updated_at = datetime('now')",
            (row.cohort_id, visits, _text(data.get("key_adult"), 120),
             int(_bool(data.get("social_story_sent"))), _long(data.get("plan"), 2000), status,
             actor.username))
        _audit(conn, "plan", actor, row.intake_year, row.cohort_id, status=status)
    activity_log.record("year6.plan", target=row.cohort_id, principal=actor, status=status)


def add_to_enhanced(cohort_id: int, *, actor: Principal, reason: str) -> None:
    """Put a child on the enhanced-transition list who isn't on it by the rules."""
    _require_plan_editor(actor, "plan", cohort_id)
    row = get(cohort_id, actor=actor)
    why = _text(reason, 300)
    if not why:
        raise ValidationError(["Say why the child needs an enhanced transition"])
    with database.connect() as conn:
        conn.execute("INSERT INTO y6_enhanced (cohort_id, manual, manual_reason, updated_by) "
                     "VALUES (?, 1, ?, ?) ON CONFLICT (cohort_id) DO UPDATE SET manual = 1, "
                     "manual_reason = excluded.manual_reason, updated_by = excluded.updated_by, "
                     "updated_at = datetime('now')", (row.cohort_id, why, actor.username))
        _audit(conn, "enhanced_add", actor, row.intake_year, row.cohort_id)


def remove_from_enhanced(cohort_id: int, *, actor: Principal) -> None:
    """Take off a child added by hand (one on the list by the rules stays)."""
    _require_plan_editor(actor, "plan", cohort_id)
    row = get(cohort_id, actor=actor)
    with database.connect() as conn:
        conn.execute("UPDATE y6_enhanced SET manual = 0, manual_reason = NULL, updated_by = ?, "
                     "updated_at = datetime('now') WHERE cohort_id = ?",
                     (actor.username, row.cohort_id))
        _audit(conn, "enhanced_remove", actor, row.intake_year, row.cohort_id)
    if get(row.cohort_id, actor=actor).enhanced:
        raise ValidationError(["Taken off by hand, but the child still meets the rules "
                               "(SEN / PP / looked after / the primary asked)"])


# ── September start ──────────────────────────────────────────────────

def start_pupil(cohort_id: int, *, actor: Principal, start_date: str | None = None,
                db_path: str | None = None) -> list[str]:
    """Make sure the child has a pupil record here (match or create from
    the handover, or admit the accepted admissions offer), import KS2, put
    them in their published form and complete the platform transfer."""
    _require_editor(actor, "start", cohort_id)
    row = get(cohort_id, actor=actor)
    if not row.active:
        raise ValidationError([f"{row.name} isn't coming ({row.status_label})"])
    date = start_date or _dt.date.today().isoformat()
    problems: list[str] = []
    date = _date(date, "Start date", problems)
    if problems:
        raise ValidationError(problems)
    pub = publication(row.intake_year)
    form = row.form_name if pub else None
    notes: list[str] = []
    pupil_id = row.pupil_id
    if row.source == "platform" and row.transition_id:
        tid = row.transition_id
        item = IP.get(tid, actor=actor, db_path=db_path)
        pupil_id = item.pupil_id or pupil_id
        if pupil_id is None and item.application_id:
            a = AD.get_application(item.application_id)
            if a and a.admitted_pupil_id:
                out = IP.match_application(tid, a.application_id, actor=actor, db_path=db_path)
                notes += out.notes
                pupil_id = out.pupil.pupil_id if out.pupil else None
        if pupil_id is None:
            best = [c for c in IP.match_candidates(tid, actor=actor, db_path=db_path)
                    if c["kind"] == "pupil" and c["score"] >= 90]
            if best:
                out = IP.match_pupil(tid, best[0]["id"], actor=actor, db_path=db_path)
                notes.append("matched to an existing pupil record")
            else:
                try:
                    out = IP.create_pupil(tid, {"admission_date": date, "form_group": form or ""},
                                          actor=actor, db_path=db_path)
                except P.DuplicatePupil as e:
                    out = IP.match_pupil(tid, e.existing.pupil_id, actor=actor, db_path=db_path)
                    notes.append("matched to the existing record with the same name and "
                                 "date of birth")
            notes += out.notes
            pupil_id = out.pupil.pupil_id if out.pupil else out.item.pupil_id
        item = IP.get(tid, actor=actor, db_path=db_path)
        if pupil_id and not item.local.get("ks2_imported_at"):
            try:
                IP.import_ks2(tid, actor=actor, db_path=db_path)
                notes.append("KS2 imported into prior attainment")
            except ValidationError as e:
                notes.append("KS2 not imported: " + "; ".join(getattr(e, "problems", [str(e)])))
    elif row.application_id:
        a = AD.get_application(row.application_id)
        if a is None:
            raise NotFound("The admissions application has gone")
        if a.admitted_pupil_id:
            pupil_id = a.admitted_pupil_id
        elif a.status == "accepted":
            out = AD.admit(a.application_id, actor=actor, admission_date=date,
                           form_group=form or None)
            pupil_id = out.pupil.pupil_id if out.pupil else None
            notes.append("admitted from the accepted offer")
            notes += list(getattr(out, "notes", []))
        else:
            raise ValidationError([f"The offer is {a.status_label.lower()} - the parent must "
                                   "accept it before the child can start"])
        if pupil_id and (row.ks2_reading is not None or row.ks2_maths is not None):
            from education_system.systems.secondary.modules.assessment.domain import (
                headline_measures as HM,
            )
            if HM.get_ks2(pupil_id) is None:
                HM.set_ks2(pupil_id, {"reading_scaled": row.ks2_reading,
                                      "maths_scaled": row.ks2_maths,
                                      "source": "Primary school",
                                      "notes": "From Year 6 transition"}, actor=actor)
                notes.append("KS2 saved as prior attainment")
    if pupil_id is None:
        raise ValidationError(["No pupil record could be made"])
    if form:
        note = _set_form(pupil_id, form, actor)
        notes.append(f"form {form}" + (f" not set: {note}" if note else " set"))
    with database.connect() as conn:
        conn.execute("UPDATE y6_cohort SET pupil_id = ?, updated_at = datetime('now') "
                     "WHERE cohort_id = ?", (pupil_id, row.cohort_id))
        _audit(conn, "start", actor, row.intake_year, row.cohort_id, pupil=pupil_id)
    if row.source == "platform" and row.transition_id:
        item = IP.get(row.transition_id, actor=actor, db_path=db_path)
        if item.status == "admitted":
            try:
                IP.complete(row.transition_id, actor=actor, start_date=date, db_path=db_path)
                notes.append("platform transfer completed")
                with database.connect() as conn:
                    conn.execute("UPDATE y6_cohort SET source_status = 'completed', "
                                 "status_label = ? WHERE cohort_id = ?",
                                 (IP.STATUS_LABELS["completed"], row.cohort_id))
            except ValidationError as e:
                notes.append("transfer not completed: " +
                             "; ".join(getattr(e, "problems", [str(e)])))
    activity_log.record("year6.start", target=row.cohort_id, principal=actor)
    return notes


def start_all(intake_year: str, *, actor: Principal, start_date: str | None = None,
              db_path: str | None = None) -> dict[str, list[str]]:
    """:func:`start_pupil` for every active child not yet completed:
    ``{name: notes}`` (a refusal is the note)."""
    _require_editor(actor, "start")
    out: dict[str, list[str]] = {}
    for r in cohort(intake_year, actor=actor):
        if r.status_label in ("Completed",) and r.pupil_id:
            continue
        try:
            out[r.name] = start_pupil(r.cohort_id, actor=actor, start_date=start_date,
                                      db_path=db_path)
        except (ValidationError, PermissionDenied, NotFound, P.DuplicatePupil) as e:
            out[r.name] = ["not started: " + "; ".join(getattr(e, "problems", None)
                                                        or [str(e)])]
    return out


# ── Exports ──────────────────────────────────────────────────────────

def export_cohort_csv(intake_year: str, path: str | Path, *, actor: Principal) -> int:
    rows = cohort(intake_year, actor=actor, include_inactive=True)
    needs = can_see_needs(actor)
    yn = lambda v: "" if v is None else "Y" if v else "N"  # noqa: E731
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        head = ["surname", "first name", "preferred", "date of birth", "gender", "upn",
                "feeder school", "via", "status", "coming", "ks2 reading", "ks2 maths",
                "ks2 band", "enhanced", "form", "checklist", "pupil record"]
        if needs:
            head += ["sen", "pupil premium", "fsm", "lac", "eal"]
        w.writerow(head)
        for r in rows:
            line = [_safe(r.last_name), _safe(r.first_name), _safe(r.preferred_name),
                    r.date_of_birth or "", r.gender or "", _safe(r.upn), _safe(r.feeder_school),
                    r.source_label, r.status_label, yn(r.active), r.ks2_reading or "",
                    r.ks2_maths or "", r.ks2_band, yn(r.enhanced), _safe(r.form_name),
                    r.progress_label, r.pupil_id or ""]
            if needs:
                line += [r.sen_status or "", yn(r.pupil_premium), yn(r.fsm), yn(r.lac),
                         yn(r.eal)]
            w.writerow(line)
    activity_log.record("year6.export", principal=actor, rows=len(rows), what="cohort")
    return len(rows)


def export_form_lists(intake_year: str, path: str | Path, *, actor: Principal) -> int:
    rows = sorted(cohort(intake_year, actor=actor),
                  key=lambda r: (r.form_name or "~", r.last_name, r.first_name))
    needs = can_see_needs(actor)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["form", "surname", "first name", "gender", "feeder school", "ks2 band",
                    "enhanced"] + (["sen"] if needs else []))
        for r in rows:
            w.writerow([_safe(r.form_name or "(not allocated)"), _safe(r.last_name),
                        _safe(r.preferred_name or r.first_name), r.gender or "",
                        _safe(r.feeder_school), r.ks2_band, "Y" if r.enhanced else ""]
                       + ([r.sen_status or ""] if needs else []))
    activity_log.record("year6.export", principal=actor, rows=len(rows), what="forms")
    return len(rows)
