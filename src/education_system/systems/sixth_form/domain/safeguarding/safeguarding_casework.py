"""Safeguarding casework records for the Sixth Form System.

The concern log (:mod:`safeguarding`) says *what was worrying*. This
module holds what the DSL did about it, as records rather than free
text on the concern:

* ``safeguarding_referrals`` — one row per referral to an agency
  (MASH, children's / adult social care, police, Channel, CAMHS, early
  help, LADO) with reference, outcome, next action and a follow-up due
  date, so overdue follow-ups can be listed.
* ``safeguarding_plans`` + ``safeguarding_plan_meetings`` — child
  protection, child in need and early help plans per learner: start,
  review dates, lead professional, core group / review meetings and
  end or step-down. Overdue reviews are listed.
* ``lado_allegations`` — the register of allegations against staff,
  volunteers and contractors (KCSIE Part 4). Not tied to a learner;
  DSL / Principal only.
* ``safeguarding_file_transfers`` — files sent to a learner's next
  setting (with a generated transfer pack and receipt confirmation)
  and files received from a previous setting (KCSIE: within 5 school
  days, kept separately from the main file).

:func:`student_chronology` reads every dated entry on a learner's file,
including linked Prevent concerns (read-through; the stores stay
separate).

All records are DSL-only (``access.SAFEGUARDING``) and every call is
written to the sensitive-access log. Nothing here can be deleted:
records are closed with a reason, who and when.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import logging
from education_system.systems.sixth_form.infrastructure import database as _sql
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.domain.safeguarding import (
    safeguarding as sg,
)
from education_system.systems.sixth_form.domain.safeguarding.safeguarding import (
    ValidationError,
)

logger = logging.getLogger(__name__)

DB_PATH = sg.DB_PATH

#: Where transfer packs are written.
TRANSFER_DIR: Path = paths.SIXTH_FORM_DATA_DIR / "safeguarding_transfers"

# ── Vocabularies ──────────────────────────────────────────────────

REFERRAL_AGENCIES: tuple[str, ...] = (
    "MASH", "Children's Social Care", "Adult Social Care", "Police",
    "Channel", "CAMHS", "Early Help", "LADO", "Other",
)

REFERRAL_OUTCOMES: tuple[str, ...] = (
    "Awaiting decision",
    "No further action",
    "Advice / information only",
    "Early help offered",
    "Section 17 — Child in Need assessment",
    "Section 47 — Child Protection enquiry",
    "Strategy discussion",
    "Adult safeguarding enquiry (Care Act s42)",
    "Channel panel — support offered",
    "Channel — not adopted",
    "CAMHS — accepted",
    "CAMHS — declined",
    "Police — investigation",
    "Other",
)

REFERRAL_STATUSES: tuple[str, ...] = ("Open", "Closed")

PLAN_TYPES: tuple[str, ...] = (
    "Child Protection Plan", "Child in Need Plan",
    "Early Help Assessment", "Early Help Plan",
    "Adult Safeguarding Plan",
)
PLAN_STATUSES: tuple[str, ...] = ("Active", "Stepped Down", "Ended")
STEP_DOWN_TARGETS: tuple[str, ...] = (
    "Child in Need Plan", "Early Help Plan", "Universal services", "Other",
)
PLAN_END_REASONS: tuple[str, ...] = (
    "Plan objectives met", "Stepped down", "Learner moved local authority",
    "Learner turned 18", "Learner left the college", "Other",
)
#: Default review intervals in days (CP review conference 3 months after
#: the initial conference then every 6 months; CIN / early help reviews
#: commonly every 3 months).
DEFAULT_REVIEW_DAYS: dict[str, int] = {
    "Child Protection Plan": 91,
    "Child in Need Plan": 91,
    "Early Help Assessment": 42,
    "Early Help Plan": 91,
    "Adult Safeguarding Plan": 91,
}

MEETING_TYPES: tuple[str, ...] = (
    "Initial Child Protection Conference", "Review Conference",
    "Core Group", "Child in Need Review", "Team Around the Family",
    "Early Help Review", "Strategy Discussion", "Other",
)
#: Meetings that count as a plan review.
REVIEW_MEETING_TYPES: frozenset[str] = frozenset({
    "Review Conference", "Child in Need Review", "Early Help Review",
    "Initial Child Protection Conference",
})

LADO_SUBJECT_ROLES: tuple[str, ...] = (
    "Teacher", "Support staff", "Volunteer", "Contractor",
    "Supply / agency", "Governor / trustee", "Other",
)
LADO_OUTCOMES: tuple[str, ...] = (
    "Substantiated", "Unsubstantiated", "False", "Malicious", "Unfounded",
)
LADO_STATUSES: tuple[str, ...] = ("Open", "Closed")

TRANSFER_DIRECTIONS: tuple[str, ...] = ("Out", "In")
TRANSFER_METHODS: tuple[str, ...] = (
    "Secure electronic transfer (CPOMS / MyConcern)",
    "Secure email", "Hand delivered (signed for)",
    "Recorded / special delivery", "Other",
)
TRANSFER_STATUSES: tuple[str, ...] = (
    "Awaiting", "Sent", "Receipt confirmed", "Received",
)
#: KCSIE: files move within 5 school days.
TRANSFER_SCHOOL_DAYS: int = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS safeguarding_referrals (
    referral_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    concern_id     INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    agency         TEXT NOT NULL,
    referral_date  TEXT NOT NULL,
    reference      TEXT,
    referred_by    TEXT,
    reason         TEXT,
    outcome        TEXT,
    outcome_date   TEXT,
    next_action    TEXT,
    follow_up_due  TEXT,
    status         TEXT NOT NULL DEFAULT 'Open',
    closed_reason  TEXT,
    closed_by      TEXT,
    closed_at      TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (concern_id) REFERENCES safeguarding_concerns(concern_id)
);
CREATE INDEX IF NOT EXISTS idx_sgr_concern ON safeguarding_referrals(concern_id);
CREATE INDEX IF NOT EXISTS idx_sgr_student ON safeguarding_referrals(student_id);
CREATE INDEX IF NOT EXISTS idx_sgr_due     ON safeguarding_referrals(follow_up_due);

CREATE TABLE IF NOT EXISTS safeguarding_plans (
    plan_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id         TEXT NOT NULL,
    student_name       TEXT,
    plan_type          TEXT NOT NULL,
    concern_id         INTEGER,
    local_authority    TEXT,
    start_date         TEXT NOT NULL,
    lead_professional  TEXT,
    lead_agency        TEXT,
    college_contact    TEXT,
    last_review_date   TEXT,
    next_review_date   TEXT,
    status             TEXT NOT NULL DEFAULT 'Active',
    end_date           TEXT,
    end_reason         TEXT,
    stepped_down_to    TEXT,
    successor_plan_id  INTEGER,
    notes              TEXT,
    created_by         TEXT,
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (concern_id) REFERENCES safeguarding_concerns(concern_id)
);
CREATE INDEX IF NOT EXISTS idx_sgp_student ON safeguarding_plans(student_id);
CREATE INDEX IF NOT EXISTS idx_sgp_review  ON safeguarding_plans(next_review_date);

CREATE TABLE IF NOT EXISTS safeguarding_plan_meetings (
    meeting_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id           INTEGER NOT NULL,
    meeting_date      TEXT NOT NULL,
    meeting_type      TEXT NOT NULL,
    attendees         TEXT,
    college_attended  INTEGER NOT NULL DEFAULT 0,
    college_rep       TEXT,
    summary           TEXT,
    actions           TEXT,
    next_meeting_date TEXT,
    recorded_by       TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (plan_id) REFERENCES safeguarding_plans(plan_id)
);
CREATE INDEX IF NOT EXISTS idx_sgpm_plan ON safeguarding_plan_meetings(plan_id);

CREATE TABLE IF NOT EXISTS lado_allegations (
    allegation_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id               TEXT,
    subject_name           TEXT NOT NULL,
    subject_role           TEXT NOT NULL,
    allegation_date        TEXT NOT NULL,
    allegation             TEXT NOT NULL,
    reported_by            TEXT,
    received_by            TEXT,
    reported_to_lado_date  TEXT,
    lado_reference         TEXT,
    lado_officer           TEXT,
    strategy_meeting_date  TEXT,
    police_involved        INTEGER NOT NULL DEFAULT 0,
    suspended              INTEGER NOT NULL DEFAULT 0,
    outcome                TEXT,
    outcome_date           TEXT,
    dbs_referral           INTEGER NOT NULL DEFAULT 0,
    dbs_referral_date      TEXT,
    tra_referral           INTEGER NOT NULL DEFAULT 0,
    tra_referral_date      TEXT,
    actions                TEXT,
    status                 TEXT NOT NULL DEFAULT 'Open',
    closed_reason          TEXT,
    closed_by              TEXT,
    closed_at              TEXT,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_lado_staff  ON lado_allegations(staff_id);
CREATE INDEX IF NOT EXISTS idx_lado_status ON lado_allegations(status);

CREATE TABLE IF NOT EXISTS safeguarding_file_transfers (
    transfer_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    direction            TEXT NOT NULL,
    student_id           TEXT NOT NULL,
    student_name         TEXT,
    institution          TEXT NOT NULL,
    institution_contact  TEXT,
    trigger_date         TEXT,
    due_by               TEXT,
    date_sent            TEXT,
    date_received        TEXT,
    method               TEXT,
    sent_by              TEXT,
    received_by          TEXT,
    file_path            TEXT,
    file_ref             TEXT,
    kept_separately      INTEGER NOT NULL DEFAULT 1,
    receipt_confirmed    INTEGER NOT NULL DEFAULT 0,
    receipt_confirmed_on TEXT,
    receipt_confirmed_by TEXT,
    status               TEXT NOT NULL DEFAULT 'Awaiting',
    notes                TEXT,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sgft_student ON safeguarding_file_transfers(student_id);
CREATE INDEX IF NOT EXISTS idx_sgft_status  ON safeguarding_file_transfers(status);
"""


# ── Dataclasses ───────────────────────────────────────────────────

@dataclass
class Referral:
    referral_id: int
    concern_id: int
    student_id: str
    agency: str
    referral_date: str
    reference: str | None
    referred_by: str | None
    reason: str | None
    outcome: str | None
    outcome_date: str | None
    next_action: str | None
    follow_up_due: str | None
    status: str
    closed_reason: str | None
    closed_by: str | None
    closed_at: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status == "Open"

    def follow_up_overdue(self, on: str | None = None) -> bool:
        ref = on or _dt.date.today().isoformat()
        return bool(self.is_open and self.follow_up_due
                    and self.follow_up_due < ref)


@dataclass
class Plan:
    plan_id: int
    student_id: str
    student_name: str | None
    plan_type: str
    concern_id: int | None
    local_authority: str | None
    start_date: str
    lead_professional: str | None
    lead_agency: str | None
    college_contact: str | None
    last_review_date: str | None
    next_review_date: str | None
    status: str
    end_date: str | None
    end_reason: str | None
    stepped_down_to: str | None
    successor_plan_id: int | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_at: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    def review_overdue(self, on: str | None = None) -> bool:
        ref = on or _dt.date.today().isoformat()
        return bool(self.is_active and self.next_review_date
                    and self.next_review_date < ref)


@dataclass
class Meeting:
    meeting_id: int
    plan_id: int
    meeting_date: str
    meeting_type: str
    attendees: str | None
    college_attended: bool
    college_rep: str | None
    summary: str | None
    actions: str | None
    next_meeting_date: str | None
    recorded_by: str | None
    created_at: str


@dataclass
class Allegation:
    allegation_id: int
    staff_id: str | None
    subject_name: str
    subject_role: str
    allegation_date: str
    allegation: str
    reported_by: str | None
    received_by: str | None
    reported_to_lado_date: str | None
    lado_reference: str | None
    lado_officer: str | None
    strategy_meeting_date: str | None
    police_involved: bool
    suspended: bool
    outcome: str | None
    outcome_date: str | None
    dbs_referral: bool
    dbs_referral_date: str | None
    tra_referral: bool
    tra_referral_date: str | None
    actions: str | None
    status: str
    closed_reason: str | None
    closed_by: str | None
    closed_at: str | None
    created_at: str
    updated_at: str

    @property
    def is_open(self) -> bool:
        return self.status == "Open"


@dataclass
class Transfer:
    transfer_id: int
    direction: str
    student_id: str
    student_name: str | None
    institution: str
    institution_contact: str | None
    trigger_date: str | None
    due_by: str | None
    date_sent: str | None
    date_received: str | None
    method: str | None
    sent_by: str | None
    received_by: str | None
    file_path: str | None
    file_ref: str | None
    kept_separately: bool
    receipt_confirmed: bool
    receipt_confirmed_on: str | None
    receipt_confirmed_by: str | None
    status: str
    notes: str | None
    created_at: str
    updated_at: str

    def overdue(self, on: str | None = None) -> bool:
        ref = on or _dt.date.today().isoformat()
        return bool(self.status == "Awaiting" and self.due_by
                    and self.due_by < ref)


@dataclass
class ChronologyEntry:
    date: str
    kind: str          # Concern / Update / Referral / Plan / Meeting /
                       # Prevent / Transfer / Linked
    ref: str
    title: str
    detail: str = ""
    by: str | None = None
    retracted: bool = False


@dataclass
class CaseworkSummary:
    referrals_open: int = 0
    referrals_overdue: int = 0
    plans_active: int = 0
    plans_review_overdue: int = 0
    plans_by_type: dict[str, int] = field(default_factory=dict)
    lado_open: int = 0
    lado_not_reported: int = 0
    transfers_out_awaiting_receipt: int = 0
    transfers_in_overdue: int = 0


# ── DB plumbing ───────────────────────────────────────────────────

_DB_READY = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    sg.init_db()
    with sg._connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def _connect() -> _sql.Connection:
    init_db()
    return sg._connect()


def _from_row(cls, r: _sql.Row):
    vals = {}
    keys = r.keys()
    for f in dataclasses.fields(cls):
        v = r[f.name] if f.name in keys else None
        if f.type in ("bool",) or f.type is bool:
            v = bool(v)
        vals[f.name] = v
    return cls(**vals)


def _today() -> str:
    return _dt.date.today().isoformat()


def _date(value: Any, label: str, *, required: bool = False) -> str | None:
    v = sg._validate_date(value, label)
    if required and v is None:
        raise ValidationError(f"{label} is required")
    return v


def _text(value: Any) -> str | None:
    return (str(value).strip() if value is not None else "") or None


def _choice(value: Any, label: str, choices: tuple[str, ...]) -> str:
    s = (str(value or "")).strip()
    if s not in choices:
        raise ValidationError(f"{label} must be one of: {', '.join(choices)}")
    return s


def add_school_days(start: str, days: int) -> str:
    """*start* plus *days* weekdays (Saturday/Sunday skipped)."""
    d = _dt.date.fromisoformat(start)
    added = 0
    while added < days:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d.isoformat()


def _student(student_id: str):
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    return _students.get_student(student_id)


def _student_name(student_id: str) -> str | None:
    s = _student(student_id)
    if s is not None:
        return s.full_name
    # Left the college: fall back to the snapshot on any concern.
    with _connect() as conn:
        r = conn.execute(
            "SELECT student_name FROM safeguarding_concerns WHERE "
            "student_id = ? AND student_name IS NOT NULL LIMIT 1",
            (student_id,)).fetchone()
    return r[0] if r else None


# ── Referrals ─────────────────────────────────────────────────────

def _get_referral(referral_id: int) -> Referral | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM safeguarding_referrals "
                         "WHERE referral_id = ?", (referral_id,)).fetchone()
    return _from_row(Referral, r) if r else None


def create_referral(data: dict[str, Any], *,
                    principal: access.Principal | None = None) -> Referral:
    """Record a referral to an agency against a concern.

    Also marks the concern as *referral made* (date, reference, agency)
    if it was not already, so the concern log and the referral register
    agree.
    """
    init_db()
    try:
        cid = int(data.get("concern_id"))
    except (TypeError, ValueError):
        raise ValidationError("Concern id must be a number") from None
    concern = sg._get_concern(cid)
    if concern is None:
        raise ValidationError(f"No concern with id {cid}")
    p = sg.require_dsl(principal, action="create-referral",
                       student_id=concern.student_id,
                       record_ref=f"concern:{cid}")
    agency = _choice(data.get("agency"), "Agency", REFERRAL_AGENCIES)
    referral_date = _date(data.get("referral_date") or _today(),
                          "Referral date", required=True)
    outcome = _text(data.get("outcome"))
    if outcome and outcome not in REFERRAL_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of: {', '.join(REFERRAL_OUTCOMES)}")
    follow_up = _date(data.get("follow_up_due"), "Follow-up due")
    if follow_up and follow_up < referral_date:
        raise ValidationError("Follow-up cannot be before the referral date")
    warning = sg.agency_warning(concern.student_id, agency, referral_date)
    if warning:
        logger.warning("Referral for concern #%d: %s", cid, warning)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_referrals
                   (concern_id, student_id, agency, referral_date, reference,
                    referred_by, reason, outcome, outcome_date, next_action,
                    follow_up_due)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, concern.student_id, agency, referral_date,
             _text(data.get("reference")),
             _text(data.get("referred_by")) or sg._actor(p),
             _text(data.get("reason")), outcome,
             _date(data.get("outcome_date"), "Outcome date"),
             _text(data.get("next_action")), follow_up))
        new_id = cur.lastrowid
        agencies = [a.strip() for a in (concern.external_agencies or "")
                    .split(",") if a.strip()]
        if agency not in agencies:
            agencies.append(agency)
        conn.execute(
            "UPDATE safeguarding_concerns SET referral_made = 1, "
            "referral_date = COALESCE(referral_date, ?), "
            "referral_ref = COALESCE(referral_ref, ?), "
            "external_agencies = ?, updated_at = datetime('now') "
            "WHERE concern_id = ?",
            (referral_date, _text(data.get("reference")),
             ", ".join(agencies), cid))
        conn.commit()
    logger.info("Referral #%d to %s for concern #%d", new_id, agency, cid)
    out = _get_referral(new_id)
    assert out is not None
    return out


def update_referral(referral_id: int, data: dict[str, Any], *,
                    principal: access.Principal | None = None) -> Referral:
    existing = _get_referral(referral_id)
    if existing is None:
        raise ValidationError(f"No referral with id {referral_id}")
    sg.require_dsl(principal, action="update-referral",
                   student_id=existing.student_id,
                   record_ref=f"concern:{existing.concern_id}")
    merged = {**dataclasses.asdict(existing), **data}
    agency = _choice(merged["agency"], "Agency", REFERRAL_AGENCIES)
    referral_date = _date(merged["referral_date"], "Referral date",
                          required=True)
    outcome = _text(merged.get("outcome"))
    if outcome and outcome not in REFERRAL_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of: {', '.join(REFERRAL_OUTCOMES)}")
    follow_up = _date(merged.get("follow_up_due"), "Follow-up due")
    with _connect() as conn:
        conn.execute(
            """UPDATE safeguarding_referrals SET agency = ?,
                   referral_date = ?, reference = ?, referred_by = ?,
                   reason = ?, outcome = ?, outcome_date = ?,
                   next_action = ?, follow_up_due = ?,
                   updated_at = datetime('now')
               WHERE referral_id = ?""",
            (agency, referral_date, _text(merged.get("reference")),
             _text(merged.get("referred_by")), _text(merged.get("reason")),
             outcome, _date(merged.get("outcome_date"), "Outcome date"),
             _text(merged.get("next_action")), follow_up, referral_id))
        conn.commit()
    out = _get_referral(referral_id)
    assert out is not None
    return out


def record_referral_outcome(referral_id: int, *, outcome: str,
                            outcome_date: str | None = None,
                            next_action: str | None = None,
                            follow_up_due: str | None = None,
                            principal: access.Principal | None = None
                            ) -> Referral:
    return update_referral(referral_id, {
        "outcome": outcome,
        "outcome_date": outcome_date or _today(),
        "next_action": next_action,
        "follow_up_due": follow_up_due,
    }, principal=principal)


def close_referral(referral_id: int, *, reason: str,
                   principal: access.Principal | None = None) -> Referral:
    existing = _get_referral(referral_id)
    if existing is None:
        raise ValidationError(f"No referral with id {referral_id}")
    p = sg.require_dsl(principal, action="close-referral",
                       student_id=existing.student_id,
                       record_ref=f"concern:{existing.concern_id}")
    if not (reason or "").strip():
        raise ValidationError("A reason is required to close a referral")
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_referrals SET status = 'Closed', "
            "closed_reason = ?, closed_by = ?, closed_at = datetime('now'), "
            "updated_at = datetime('now') WHERE referral_id = ?",
            (reason.strip(), sg._actor(p), referral_id))
        conn.commit()
    out = _get_referral(referral_id)
    assert out is not None
    return out


def get_referral(referral_id: int, *,
                 principal: access.Principal | None = None
                 ) -> Referral | None:
    r = _get_referral(referral_id)
    sg.require_dsl(principal, action="view-referral",
                   student_id=r.student_id if r else None,
                   record_ref=f"concern:{r.concern_id}" if r else None)
    return r


def _list_referrals(*, concern_id: int | None = None,
                    student_id: str | None = None,
                    agency: str | None = None,
                    open_only: bool = False) -> list[Referral]:
    clauses, args = [], []
    if concern_id is not None:
        clauses.append("concern_id = ?")
        args.append(int(concern_id))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if agency:
        clauses.append("agency = ?")
        args.append(agency)
    if open_only:
        clauses.append("status = 'Open'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM safeguarding_referrals {where} "  # DBW001: where is built from fixed clauses
            "ORDER BY referral_date DESC, referral_id DESC", args).fetchall()
    return [_from_row(Referral, r) for r in rows]


def list_referrals(*, concern_id: int | None = None,
                   student_id: str | None = None,
                   agency: str | None = None, open_only: bool = False,
                   principal: access.Principal | None = None
                   ) -> list[Referral]:
    sg.require_dsl(principal, action="list-referrals", student_id=student_id,
                   record_ref=f"concern:{concern_id}" if concern_id else None)
    return _list_referrals(concern_id=concern_id, student_id=student_id,
                           agency=agency, open_only=open_only)


def overdue_referral_follow_ups(*, on: str | None = None,
                                principal: access.Principal | None = None
                                ) -> list[Referral]:
    sg.require_dsl(principal, action="list-overdue-referrals")
    ref = on or _today()
    return sorted((r for r in _list_referrals(open_only=True)
                   if r.follow_up_overdue(ref)),
                  key=lambda r: r.follow_up_due or "")


# ── Plans ─────────────────────────────────────────────────────────

def _get_plan(plan_id: int) -> Plan | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM safeguarding_plans WHERE plan_id = ?",
                         (plan_id,)).fetchone()
    return _from_row(Plan, r) if r else None


def create_plan(data: dict[str, Any], *,
                principal: access.Principal | None = None) -> Plan:
    init_db()
    sid = (data.get("student_id") or "").strip()
    if not sid:
        raise ValidationError("Student ID is required")
    p = sg.require_dsl(principal, action="create-plan", student_id=sid)
    student = _student(sid)
    if student is None:
        raise ValidationError(f"No student with id {sid}")
    plan_type = _choice(data.get("plan_type"), "Plan type", PLAN_TYPES)
    start = _date(data.get("start_date") or _today(), "Start date",
                  required=True)
    next_review = _date(data.get("next_review_date"), "Next review date")
    if next_review is None:
        next_review = (_dt.date.fromisoformat(start) + _dt.timedelta(
            days=DEFAULT_REVIEW_DAYS.get(plan_type, 91))).isoformat()
    if next_review < start:
        raise ValidationError("Next review cannot be before the start date")
    if plan_type == "Adult Safeguarding Plan" and not sg.is_adult_learner(sid):
        raise ValidationError("An adult safeguarding plan is for learners "
                              "aged 18 or over")
    concern_id = data.get("concern_id")
    if concern_id not in (None, ""):
        concern_id = int(concern_id)
        if sg._get_concern(concern_id) is None:
            raise ValidationError(f"No concern with id {concern_id}")
    else:
        concern_id = None
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_plans
                   (student_id, student_name, plan_type, concern_id,
                    local_authority, start_date, lead_professional,
                    lead_agency, college_contact, next_review_date,
                    notes, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, student.full_name, plan_type, concern_id,
             _text(data.get("local_authority")), start,
             _text(data.get("lead_professional")),
             _text(data.get("lead_agency")),
             _text(data.get("college_contact")), next_review,
             _text(data.get("notes")), sg._actor(p)))
        conn.commit()
        new_id = cur.lastrowid
    logger.info("%s #%d opened for %s", plan_type, new_id, sid)
    out = _get_plan(new_id)
    assert out is not None
    return out


def update_plan(plan_id: int, data: dict[str, Any], *,
                principal: access.Principal | None = None) -> Plan:
    existing = _get_plan(plan_id)
    if existing is None:
        raise ValidationError(f"No plan with id {plan_id}")
    sg.require_dsl(principal, action="update-plan",
                   student_id=existing.student_id,
                   record_ref=f"plan:{plan_id}")
    m = {**dataclasses.asdict(existing), **data}
    start = _date(m["start_date"], "Start date", required=True)
    with _connect() as conn:
        conn.execute(
            """UPDATE safeguarding_plans SET local_authority = ?,
                   start_date = ?, lead_professional = ?, lead_agency = ?,
                   college_contact = ?, last_review_date = ?,
                   next_review_date = ?, notes = ?,
                   updated_at = datetime('now')
               WHERE plan_id = ?""",
            (_text(m.get("local_authority")), start,
             _text(m.get("lead_professional")), _text(m.get("lead_agency")),
             _text(m.get("college_contact")),
             _date(m.get("last_review_date"), "Last review date"),
             _date(m.get("next_review_date"), "Next review date"),
             _text(m.get("notes")), plan_id))
        conn.commit()
    out = _get_plan(plan_id)
    assert out is not None
    return out


def add_meeting(plan_id: int, data: dict[str, Any], *,
                principal: access.Principal | None = None) -> Meeting:
    """Record a core group / review meeting.

    A review-type meeting moves the plan's last review to the meeting
    date and its next review to the meeting's next date (or the default
    interval for the plan type).
    """
    plan = _get_plan(plan_id)
    if plan is None:
        raise ValidationError(f"No plan with id {plan_id}")
    p = sg.require_dsl(principal, action="add-plan-meeting",
                       student_id=plan.student_id,
                       record_ref=f"plan:{plan_id}")
    mtype = _choice(data.get("meeting_type"), "Meeting type", MEETING_TYPES)
    mdate = _date(data.get("meeting_date") or _today(), "Meeting date",
                  required=True)
    next_date = _date(data.get("next_meeting_date"), "Next meeting date")
    if next_date and next_date < mdate:
        raise ValidationError("Next meeting cannot be before this meeting")
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_plan_meetings
                   (plan_id, meeting_date, meeting_type, attendees,
                    college_attended, college_rep, summary, actions,
                    next_meeting_date, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (plan_id, mdate, mtype, _text(data.get("attendees")),
             sg._coerce_bool(data.get("college_attended")),
             _text(data.get("college_rep")), _text(data.get("summary")),
             _text(data.get("actions")), next_date, sg._actor(p)))
        if mtype in REVIEW_MEETING_TYPES and plan.is_active:
            nxt = next_date or (_dt.date.fromisoformat(mdate) + _dt.timedelta(
                days=DEFAULT_REVIEW_DAYS.get(plan.plan_type, 91))).isoformat()
            conn.execute(
                "UPDATE safeguarding_plans SET last_review_date = ?, "
                "next_review_date = ?, updated_at = datetime('now') "
                "WHERE plan_id = ?", (mdate, nxt, plan_id))
        conn.commit()
        mid = cur.lastrowid
    out = next(m for m in _meetings(plan_id) if m.meeting_id == mid)
    return out


def record_review(plan_id: int, *, review_date: str | None = None,
                  next_review_date: str | None = None,
                  summary: str | None = None, attendees: str | None = None,
                  principal: access.Principal | None = None) -> Plan:
    plan = _get_plan(plan_id)
    if plan is None:
        raise ValidationError(f"No plan with id {plan_id}")
    mtype = {"Child Protection Plan": "Review Conference",
             "Child in Need Plan": "Child in Need Review"}.get(
                 plan.plan_type, "Early Help Review")
    add_meeting(plan_id, {
        "meeting_type": mtype, "meeting_date": review_date or _today(),
        "next_meeting_date": next_review_date, "summary": summary,
        "attendees": attendees, "college_attended": True,
    }, principal=principal)
    out = _get_plan(plan_id)
    assert out is not None
    return out


def _meetings(plan_id: int) -> list[Meeting]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM safeguarding_plan_meetings WHERE plan_id = ? "
            "ORDER BY meeting_date, meeting_id", (plan_id,)).fetchall()
    return [_from_row(Meeting, r) for r in rows]


def list_meetings(plan_id: int, *,
                  principal: access.Principal | None = None) -> list[Meeting]:
    sg.require_dsl(principal, action="list-plan-meetings",
                   record_ref=f"plan:{plan_id}")
    return _meetings(plan_id)


def step_down_plan(plan_id: int, *, to: str, on: str | None = None,
                   reason: str | None = None,
                   principal: access.Principal | None = None) -> Plan:
    """End a plan by stepping down; opens the successor plan if there is one."""
    plan = _get_plan(plan_id)
    if plan is None:
        raise ValidationError(f"No plan with id {plan_id}")
    p = sg.require_dsl(principal, action="step-down-plan",
                       student_id=plan.student_id,
                       record_ref=f"plan:{plan_id}")
    if not plan.is_active:
        raise ValidationError("Only an active plan can be stepped down")
    to = _choice(to, "Step down to", STEP_DOWN_TARGETS)
    end = _date(on or _today(), "Step-down date", required=True)
    successor_id = None
    if to in PLAN_TYPES:
        succ = create_plan({
            "student_id": plan.student_id, "plan_type": to,
            "start_date": end, "local_authority": plan.local_authority,
            "lead_professional": plan.lead_professional,
            "lead_agency": plan.lead_agency,
            "college_contact": plan.college_contact,
            "concern_id": plan.concern_id,
            "notes": f"Stepped down from {plan.plan_type} #{plan_id}",
        }, principal=p)
        successor_id = succ.plan_id
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_plans SET status = 'Stepped Down', "
            "end_date = ?, end_reason = ?, stepped_down_to = ?, "
            "successor_plan_id = ?, updated_at = datetime('now') "
            "WHERE plan_id = ?",
            (end, _text(reason) or "Stepped down", to, successor_id,
             plan_id))
        conn.commit()
    out = _get_plan(plan_id)
    assert out is not None
    return out


def end_plan(plan_id: int, *, reason: str, on: str | None = None,
             principal: access.Principal | None = None) -> Plan:
    plan = _get_plan(plan_id)
    if plan is None:
        raise ValidationError(f"No plan with id {plan_id}")
    sg.require_dsl(principal, action="end-plan", student_id=plan.student_id,
                   record_ref=f"plan:{plan_id}")
    if not plan.is_active:
        raise ValidationError("This plan has already ended")
    reason = _choice(reason, "End reason", PLAN_END_REASONS)
    end = _date(on or _today(), "End date", required=True)
    if end < plan.start_date:
        raise ValidationError("End date cannot be before the start date")
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_plans SET status = 'Ended', end_date = ?, "
            "end_reason = ?, updated_at = datetime('now') WHERE plan_id = ?",
            (end, reason, plan_id))
        conn.commit()
    out = _get_plan(plan_id)
    assert out is not None
    return out


def get_plan(plan_id: int, *,
             principal: access.Principal | None = None) -> Plan | None:
    plan = _get_plan(plan_id)
    sg.require_dsl(principal, action="view-plan",
                   student_id=plan.student_id if plan else None,
                   record_ref=f"plan:{plan_id}")
    return plan


def _list_plans(*, student_id: str | None = None,
                plan_type: str | None = None,
                active_only: bool = False) -> list[Plan]:
    clauses, args = [], []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if plan_type:
        clauses.append("plan_type = ?")
        args.append(plan_type)
    if active_only:
        clauses.append("status = 'Active'")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM safeguarding_plans {where} "  # DBW001: where is built from fixed clauses
            "ORDER BY CASE status WHEN 'Active' THEN 0 ELSE 1 END, "
            "next_review_date, plan_id", args).fetchall()
    return [_from_row(Plan, r) for r in rows]


def list_plans(*, student_id: str | None = None,
               plan_type: str | None = None, active_only: bool = False,
               principal: access.Principal | None = None) -> list[Plan]:
    sg.require_dsl(principal, action="list-plans", student_id=student_id)
    return _list_plans(student_id=student_id, plan_type=plan_type,
                       active_only=active_only)


def overdue_plan_reviews(*, on: str | None = None,
                         principal: access.Principal | None = None
                         ) -> list[Plan]:
    sg.require_dsl(principal, action="list-overdue-reviews")
    ref = on or _today()
    return [pl for pl in _list_plans(active_only=True)
            if pl.review_overdue(ref)]


# ── LADO register ─────────────────────────────────────────────────

def require_lado_access(principal: access.Principal | None = None, *,
                        action: str = "lado-view") -> access.Principal:
    """DSL (safeguarding capability), the Principal, or an administrator."""
    p = sg._principal(principal)
    allowed = p.can(access.SAFEGUARDING) or (
        p.is_staff and p.job_role == "Principal")
    access.log_sensitive_access(p, sg.AREA, action, record_ref="lado",
                                allowed=bool(allowed))
    if not allowed:
        raise access.AccessDenied(
            "The LADO register is restricted to the DSL and the Principal.")
    return p


def _get_allegation(allegation_id: int) -> Allegation | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM lado_allegations "
                         "WHERE allegation_id = ?",
                         (allegation_id,)).fetchone()
    return _from_row(Allegation, r) if r else None


def _validate_allegation(m: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    staff_id = _text(m.get("staff_id"))
    name = _text(m.get("subject_name"))
    if staff_id:
        from education_system.systems.sixth_form.domain.staff import (
            staff as _staff,
        )
        member = _staff.get_staff(staff_id)
        if member is None:
            raise ValidationError(f"No staff member with id {staff_id}")
        name = name or member.full_name
    if not name:
        raise ValidationError("Name of the person the allegation is about "
                              "is required")
    out["staff_id"] = staff_id
    out["subject_name"] = name
    out["subject_role"] = _choice(m.get("subject_role") or "Other",
                                  "Role", LADO_SUBJECT_ROLES)
    out["allegation_date"] = _date(m.get("allegation_date") or _today(),
                                   "Allegation date", required=True)
    allegation = _text(m.get("allegation"))
    if not allegation:
        raise ValidationError("The allegation is required")
    out["allegation"] = allegation
    for k in ("reported_by", "received_by", "lado_reference",
              "lado_officer", "actions"):
        out[k] = _text(m.get(k))
    out["reported_to_lado_date"] = _date(m.get("reported_to_lado_date"),
                                         "Reported to LADO")
    if out["reported_to_lado_date"] and \
            out["reported_to_lado_date"] < out["allegation_date"]:
        raise ValidationError("LADO cannot be told before the allegation")
    out["strategy_meeting_date"] = _date(m.get("strategy_meeting_date"),
                                         "Strategy meeting date")
    out["police_involved"] = sg._coerce_bool(m.get("police_involved"))
    out["suspended"] = sg._coerce_bool(m.get("suspended"))
    outcome = _text(m.get("outcome"))
    if outcome and outcome not in LADO_OUTCOMES:
        raise ValidationError(
            f"Outcome must be one of: {', '.join(LADO_OUTCOMES)}")
    out["outcome"] = outcome
    out["outcome_date"] = _date(m.get("outcome_date"), "Outcome date")
    out["dbs_referral"] = sg._coerce_bool(m.get("dbs_referral"))
    out["dbs_referral_date"] = _date(m.get("dbs_referral_date"),
                                     "DBS referral date") \
        if out["dbs_referral"] else None
    out["tra_referral"] = sg._coerce_bool(m.get("tra_referral"))
    out["tra_referral_date"] = _date(m.get("tra_referral_date"),
                                     "TRA referral date") \
        if out["tra_referral"] else None
    return out


_LADO_COLS = ("staff_id", "subject_name", "subject_role", "allegation_date",
              "allegation", "reported_by", "received_by",
              "reported_to_lado_date", "lado_reference", "lado_officer",
              "strategy_meeting_date", "police_involved", "suspended",
              "outcome", "outcome_date", "dbs_referral", "dbs_referral_date",
              "tra_referral", "tra_referral_date", "actions")


def create_allegation(data: dict[str, Any], *,
                      principal: access.Principal | None = None
                      ) -> Allegation:
    init_db()
    p = require_lado_access(principal, action="lado-create")
    v = _validate_allegation({**data,
                              "received_by": data.get("received_by")
                              or sg._actor(p)})
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO lado_allegations ({', '.join(_LADO_COLS)}) "  # DBW001: fixed column list
            f"VALUES ({', '.join('?' * len(_LADO_COLS))})",
            tuple(v[c] for c in _LADO_COLS))
        conn.commit()
        new_id = cur.lastrowid
    logger.warning("LADO allegation #%d recorded", new_id)
    out = _get_allegation(new_id)
    assert out is not None
    return out


def update_allegation(allegation_id: int, data: dict[str, Any], *,
                      principal: access.Principal | None = None
                      ) -> Allegation:
    existing = _get_allegation(allegation_id)
    if existing is None:
        raise ValidationError(f"No allegation with id {allegation_id}")
    require_lado_access(principal, action="lado-update")
    v = _validate_allegation({**dataclasses.asdict(existing), **data})
    sets = ", ".join(f"{c} = ?" for c in _LADO_COLS)
    with _connect() as conn:
        conn.execute(
            f"UPDATE lado_allegations SET {sets}, "  # DBW001: fixed column list
            "updated_at = datetime('now') WHERE allegation_id = ?",
            (*[v[c] for c in _LADO_COLS], allegation_id))
        conn.commit()
    out = _get_allegation(allegation_id)
    assert out is not None
    return out


def record_lado_outcome(allegation_id: int, *, outcome: str,
                        outcome_date: str | None = None,
                        dbs_referral: bool = False,
                        dbs_referral_date: str | None = None,
                        tra_referral: bool = False,
                        tra_referral_date: str | None = None,
                        actions: str | None = None,
                        principal: access.Principal | None = None
                        ) -> Allegation:
    data: dict[str, Any] = {
        "outcome": outcome, "outcome_date": outcome_date or _today(),
        "dbs_referral": dbs_referral,
        "dbs_referral_date": dbs_referral_date or (
            _today() if dbs_referral else None),
        "tra_referral": tra_referral,
        "tra_referral_date": tra_referral_date or (
            _today() if tra_referral else None),
    }
    if actions is not None:
        data["actions"] = actions
    return update_allegation(allegation_id, data, principal=principal)


def close_allegation(allegation_id: int, *, reason: str,
                     principal: access.Principal | None = None
                     ) -> Allegation:
    existing = _get_allegation(allegation_id)
    if existing is None:
        raise ValidationError(f"No allegation with id {allegation_id}")
    p = require_lado_access(principal, action="lado-close")
    if not existing.outcome:
        raise ValidationError("Record the LADO outcome before closing")
    if not (reason or "").strip():
        raise ValidationError("A reason is required to close")
    with _connect() as conn:
        conn.execute(
            "UPDATE lado_allegations SET status = 'Closed', "
            "closed_reason = ?, closed_by = ?, closed_at = datetime('now'), "
            "updated_at = datetime('now') WHERE allegation_id = ?",
            (reason.strip(), sg._actor(p), allegation_id))
        conn.commit()
    out = _get_allegation(allegation_id)
    assert out is not None
    return out


def get_allegation(allegation_id: int, *,
                   principal: access.Principal | None = None
                   ) -> Allegation | None:
    require_lado_access(principal, action="lado-view")
    return _get_allegation(allegation_id)


def list_allegations(*, open_only: bool = False,
                     staff_id: str | None = None,
                     principal: access.Principal | None = None
                     ) -> list[Allegation]:
    require_lado_access(principal, action="lado-list")
    clauses, args = [], []
    if open_only:
        clauses.append("status = 'Open'")
    if staff_id:
        clauses.append("staff_id = ?")
        args.append(staff_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM lado_allegations {where} "  # DBW001: where is built from fixed clauses
            "ORDER BY allegation_date DESC, allegation_id DESC",
            args).fetchall()
    return [_from_row(Allegation, r) for r in rows]


def lado_not_reported(*, on: str | None = None,
                      principal: access.Principal | None = None
                      ) -> list[Allegation]:
    """Open allegations not passed to the LADO within one working day."""
    ref = on or _today()
    return [a for a in list_allegations(open_only=True, principal=principal)
            if not a.reported_to_lado_date
            and add_school_days(a.allegation_date, 1) < ref]


# ── File transfers ────────────────────────────────────────────────

def _get_transfer(transfer_id: int) -> Transfer | None:
    with _connect() as conn:
        r = conn.execute("SELECT * FROM safeguarding_file_transfers "
                         "WHERE transfer_id = ?", (transfer_id,)).fetchone()
    return _from_row(Transfer, r) if r else None


def _pack_lines(student_id: str, entries: list[ChronologyEntry],
                principal: access.Principal) -> list[str]:
    name = _student_name(student_id) or "(name not held)"
    s = _student(student_id)
    dob = getattr(s, "date_of_birth", None) if s else None
    age = sg.age_on(dob)
    lines = [
        "CONFIDENTIAL — SAFEGUARDING / CHILD PROTECTION FILE",
        "Transfer to receiving DSL only. Keep separately from the main "
        "pupil file.",
        "",
        f"Learner      : {name} ({student_id})",
        f"Date of birth: {dob or '—'}"
        + (f"  (age {age})" if age is not None else ""),
        f"Generated    : {_dt.datetime.now().isoformat(timespec='seconds')}"
        f" by {sg._actor(principal)}",
        f"Entries      : {len(entries)}",
        "",
        "CHRONOLOGY",
        "=" * 70,
    ]
    for e in entries:
        mark = " [RETRACTED]" if e.retracted else ""
        lines.append(f"{e.date}  {e.kind:<9} {e.ref:<14} {e.title}{mark}")
        if e.by:
            lines.append(f"            by {e.by}")
        for line in (e.detail or "").splitlines():
            lines.append(f"            {line}")
        lines.append("")
    return lines


def build_transfer_pack(student_id: str, *,
                        principal: access.Principal | None = None) -> Path:
    """Write the learner's full chronology to a .txt and a .json file.

    Files go under ``SIXTH_FORM_DATA_DIR/safeguarding_transfers``.
    Returns the .txt path (the .json sits beside it).
    """
    p = sg.require_dsl(principal, action="build-transfer-pack",
                       student_id=student_id)
    entries = _chronology(student_id, p)
    paths.ensure_sixth_form_directories()
    TRANSFER_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_id = "".join(ch for ch in student_id if ch.isalnum() or ch in "-_")
    txt = TRANSFER_DIR / f"safeguarding_{safe_id}_{stamp}.txt"
    txt.write_text("\n".join(_pack_lines(student_id, entries, p)) + "\n",
                   encoding="utf-8")
    txt.with_suffix(".json").write_text(json.dumps({
        "student_id": student_id,
        "student_name": _student_name(student_id),
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "generated_by": sg._actor(p),
        "chronology": [dataclasses.asdict(e) for e in entries],
    }, indent=2), encoding="utf-8")
    try:
        txt.chmod(0o600)
        txt.with_suffix(".json").chmod(0o600)
    except OSError:
        pass
    logger.info("Safeguarding transfer pack for %s written to %s",
                student_id, txt)
    return txt


def record_transfer_out(student_id: str, *, institution: str,
                        method: str, date_sent: str | None = None,
                        leaving_date: str | None = None,
                        institution_contact: str | None = None,
                        notes: str | None = None, build_pack: bool = True,
                        principal: access.Principal | None = None
                        ) -> Transfer:
    """Record a file sent to the learner's next setting."""
    init_db()
    p = sg.require_dsl(principal, action="transfer-out",
                       student_id=student_id)
    if not _text(institution):
        raise ValidationError("Receiving institution is required")
    method = _choice(method, "Method", TRANSFER_METHODS)
    sent = _date(date_sent, "Date sent")
    trigger = _date(leaving_date or _today(), "Leaving date", required=True)
    pack = str(build_transfer_pack(student_id, principal=p)) \
        if build_pack else None
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_file_transfers
                   (direction, student_id, student_name, institution,
                    institution_contact, trigger_date, due_by, date_sent,
                    method, sent_by, file_path, status, notes)
               VALUES ('Out', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (student_id, _student_name(student_id), institution.strip(),
             _text(institution_contact), trigger,
             add_school_days(trigger, TRANSFER_SCHOOL_DAYS), sent, method,
             sg._actor(p), pack, "Sent" if sent else "Awaiting",
             _text(notes)))
        conn.commit()
        new_id = cur.lastrowid
    out = _get_transfer(new_id)
    assert out is not None
    return out


def mark_transfer_sent(transfer_id: int, *, date_sent: str | None = None,
                       principal: access.Principal | None = None) -> Transfer:
    t = _get_transfer(transfer_id)
    if t is None or t.direction != "Out":
        raise ValidationError(f"No outgoing transfer #{transfer_id}")
    p = sg.require_dsl(principal, action="transfer-sent",
                       student_id=t.student_id)
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_file_transfers SET date_sent = ?, "
            "sent_by = COALESCE(sent_by, ?), status = 'Sent', "
            "updated_at = datetime('now') WHERE transfer_id = ?",
            (_date(date_sent or _today(), "Date sent"), sg._actor(p),
             transfer_id))
        conn.commit()
    out = _get_transfer(transfer_id)
    assert out is not None
    return out


def confirm_receipt(transfer_id: int, *, confirmed_on: str | None = None,
                    confirmed_by: str | None = None,
                    principal: access.Principal | None = None) -> Transfer:
    """The receiving DSL has confirmed they hold the file."""
    t = _get_transfer(transfer_id)
    if t is None or t.direction != "Out":
        raise ValidationError(f"No outgoing transfer #{transfer_id}")
    sg.require_dsl(principal, action="transfer-receipt",
                   student_id=t.student_id)
    if not t.date_sent:
        raise ValidationError("Mark the file as sent first")
    who = _text(confirmed_by)
    if not who:
        raise ValidationError("Name the person at the receiving setting "
                              "who confirmed receipt")
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_file_transfers SET receipt_confirmed = 1, "
            "receipt_confirmed_on = ?, receipt_confirmed_by = ?, "
            "status = 'Receipt confirmed', updated_at = datetime('now') "
            "WHERE transfer_id = ?",
            (_date(confirmed_on or _today(), "Confirmed on"), who,
             transfer_id))
        conn.commit()
    out = _get_transfer(transfer_id)
    assert out is not None
    return out


def expect_incoming(student_id: str, *, institution: str,
                    start_date: str | None = None,
                    institution_contact: str | None = None,
                    notes: str | None = None,
                    principal: access.Principal | None = None) -> Transfer:
    """A new learner joined: expect their file within 5 school days."""
    init_db()
    p = sg.require_dsl(principal, action="transfer-expect",
                       student_id=student_id)
    if _student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    if not _text(institution):
        raise ValidationError("Previous institution is required")
    start = _date(start_date or _today(), "Start date", required=True)
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO safeguarding_file_transfers
                   (direction, student_id, student_name, institution,
                    institution_contact, trigger_date, due_by, status,
                    received_by, notes)
               VALUES ('In', ?, ?, ?, ?, ?, ?, 'Awaiting', NULL, ?)""",
            (student_id, _student_name(student_id), institution.strip(),
             _text(institution_contact), start,
             add_school_days(start, TRANSFER_SCHOOL_DAYS), _text(notes)))
        conn.commit()
        new_id = cur.lastrowid
    logger.info("Expecting safeguarding file for %s from %s (by %s)",
                student_id, institution, sg._actor(p))
    out = _get_transfer(new_id)
    assert out is not None
    return out


def record_received(transfer_id: int, *, date_received: str | None = None,
                    method: str | None = None, file_ref: str | None = None,
                    kept_separately: bool = True,
                    notes: str | None = None,
                    principal: access.Principal | None = None) -> Transfer:
    """A previous setting's file arrived (kept apart from the main file)."""
    t = _get_transfer(transfer_id)
    if t is None or t.direction != "In":
        raise ValidationError(f"No incoming transfer #{transfer_id}")
    p = sg.require_dsl(principal, action="transfer-received",
                       student_id=t.student_id)
    if method:
        method = _choice(method, "Method", TRANSFER_METHODS)
    if not kept_separately:
        raise ValidationError("KCSIE: a received child protection file "
                              "must be kept separately from the main file")
    with _connect() as conn:
        conn.execute(
            "UPDATE safeguarding_file_transfers SET date_received = ?, "
            "method = COALESCE(?, method), file_ref = ?, "
            "kept_separately = 1, received_by = ?, status = 'Received', "
            "notes = COALESCE(?, notes), updated_at = datetime('now') "
            "WHERE transfer_id = ?",
            (_date(date_received or _today(), "Date received"), method,
             _text(file_ref), sg._actor(p), _text(notes), transfer_id))
        conn.commit()
    out = _get_transfer(transfer_id)
    assert out is not None
    return out


def list_transfers(*, direction: str | None = None,
                   student_id: str | None = None,
                   principal: access.Principal | None = None
                   ) -> list[Transfer]:
    sg.require_dsl(principal, action="list-transfers", student_id=student_id)
    return _list_transfers(direction=direction, student_id=student_id)


def _list_transfers(*, direction: str | None = None,
                    student_id: str | None = None) -> list[Transfer]:
    clauses, args = [], []
    if direction:
        clauses.append("direction = ?")
        args.append(_choice(direction, "Direction", TRANSFER_DIRECTIONS))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM safeguarding_file_transfers {where} "  # DBW001: where is built from fixed clauses
            "ORDER BY COALESCE(date_sent, date_received, trigger_date) DESC, "
            "transfer_id DESC", args).fetchall()
    return [_from_row(Transfer, r) for r in rows]


def outgoing_awaiting_receipt(*, principal: access.Principal | None = None
                              ) -> list[Transfer]:
    sg.require_dsl(principal, action="list-transfers-awaiting")
    return [t for t in _list_transfers(direction="Out")
            if not t.receipt_confirmed]


def incoming_overdue(*, on: str | None = None,
                     principal: access.Principal | None = None
                     ) -> list[Transfer]:
    sg.require_dsl(principal, action="list-transfers-overdue")
    ref = on or _today()
    return [t for t in _list_transfers(direction="In") if t.overdue(ref)]


# ── Chronology ────────────────────────────────────────────────────

def _chronology(student_id: str,
                p: access.Principal) -> list[ChronologyEntry]:
    out: list[ChronologyEntry] = []
    restricted_ok = sg.can_see_restricted(p)
    concerns = sg._list_concerns(student_id=student_id)
    for c in concerns:
        linked_note = "" if c.student_id == student_id else \
            f" (linked; subject {c.student_id})"
        detail = c.description
        if c.action_taken:
            detail += f"\nAction taken: {c.action_taken}"
        if c.body_map_ref or c.body_map_notes:
            detail += (f"\nBody map: {c.body_map_ref or '—'} "
                       f"{c.body_map_notes or ''}").rstrip()
        if c.restricted_notes:
            detail += ("\nRestricted notes: " + c.restricted_notes
                       if restricted_ok else
                       "\nRestricted notes held — DSL only")
        if c.adult_safeguarding:
            detail += "\nAdult safeguarding (learner 18+ at the time)"
        out.append(ChronologyEntry(
            date=c.concern_date, kind="Concern", ref=f"#{c.concern_id}",
            title=f"{c.category} — {c.risk_level} ({c.status}){linked_note}",
            detail=detail, by=c.reported_by))
        for u in sg._list_updates(c.concern_id):
            text = u.update_text
            if u.retracted:
                text += f"\nRetracted by {u.retracted_by}: {u.retracted_reason}"
            out.append(ChronologyEntry(
                date=u.update_date, kind="Update",
                ref=f"#{c.concern_id}/{u.update_id}",
                title=f"Update on concern #{c.concern_id}", detail=text,
                by=u.updated_by, retracted=u.retracted))
        for r in _list_referrals(concern_id=c.concern_id):
            out.append(ChronologyEntry(
                date=r.referral_date, kind="Referral",
                ref=f"R{r.referral_id}",
                title=f"Referral to {r.agency}"
                      + (f" ({r.reference})" if r.reference else ""),
                detail="\n".join(x for x in (
                    r.reason, r.outcome and f"Outcome: {r.outcome} "
                    f"({r.outcome_date or '—'})",
                    r.next_action and f"Next action: {r.next_action}",
                    r.follow_up_due and f"Follow up by {r.follow_up_due}",
                    r.closed_reason and f"Closed: {r.closed_reason}")
                    if x), by=r.referred_by))
        for pid in sg._prevent_ids(c.concern_id):
            out.append(ChronologyEntry(
                date=c.concern_date, kind="Linked", ref=f"P{pid}",
                title=f"Prevent concern #{pid} linked to concern "
                      f"#{c.concern_id}"))
    for pl in _list_plans(student_id=student_id):
        out.append(ChronologyEntry(
            date=pl.start_date, kind="Plan", ref=f"PL{pl.plan_id}",
            title=f"{pl.plan_type} started ({pl.status})",
            detail="\n".join(x for x in (
                pl.lead_professional and
                f"Lead professional: {pl.lead_professional}",
                pl.local_authority and f"Local authority: {pl.local_authority}",
                pl.notes) if x)))
        if pl.end_date:
            out.append(ChronologyEntry(
                date=pl.end_date, kind="Plan", ref=f"PL{pl.plan_id}",
                title=f"{pl.plan_type} {pl.status.lower()}"
                      + (f" to {pl.stepped_down_to}"
                         if pl.stepped_down_to else ""),
                detail=pl.end_reason or ""))
        for m in _meetings(pl.plan_id):
            out.append(ChronologyEntry(
                date=m.meeting_date, kind="Meeting",
                ref=f"PL{pl.plan_id}/M{m.meeting_id}",
                title=f"{m.meeting_type} ({pl.plan_type})",
                detail="\n".join(x for x in (
                    m.summary, m.actions and f"Actions: {m.actions}")
                    if x), by=m.recorded_by))
    # Prevent concerns: read-through from their own store.
    try:
        from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
            prevent_duty as _pd,
        )
        token = _pd._AUTHORISED.set(True)
        try:
            for pc in _pd.list_concerns(student_id=student_id):
                out.append(ChronologyEntry(
                    date=pc.report_date, kind="Prevent",
                    ref=f"P{pc.concern_id}",
                    title=f"Prevent: {pc.concern_type} — {pc.risk_level} "
                          f"({pc.status})",
                    detail="\n".join(x for x in (pc.summary, pc.details,
                                                 pc.outcome) if x),
                    by=pc.reported_by))
                for pr in _pd.list_referrals(concern_id=pc.concern_id):
                    out.append(ChronologyEntry(
                        date=pr.referral_date, kind="Prevent",
                        ref=f"P{pc.concern_id}/R{pr.referral_id}",
                        title=f"Channel referral ({pr.authority}) — "
                              f"{pr.status}",
                        detail=pr.outcome or ""))
        finally:
            _pd._AUTHORISED.reset(token)
    except Exception:
        logger.exception("Prevent read-through failed for %s", student_id)
    for t in _list_transfers(student_id=student_id):
        when = t.date_sent or t.date_received or t.trigger_date or ""
        verb = "sent to" if t.direction == "Out" else "from"
        out.append(ChronologyEntry(
            date=when, kind="Transfer", ref=f"T{t.transfer_id}",
            title=f"Safeguarding file {verb} {t.institution} ({t.status})",
            detail=t.notes or "", by=t.sent_by or t.received_by))
    out.sort(key=lambda e: (e.date or "", e.kind, e.ref))
    return out


def student_chronology(student_id: str, *,
                       principal: access.Principal | None = None
                       ) -> list[ChronologyEntry]:
    """Every dated entry on the learner's safeguarding file, oldest first."""
    p = sg.require_dsl(principal, action="chronology", student_id=student_id)
    return _chronology(student_id, p)


# ── Summary ───────────────────────────────────────────────────────

def casework_summary(*, principal: access.Principal | None = None
                     ) -> CaseworkSummary:
    p = sg.require_dsl(principal, action="casework-summary")
    today = _today()
    out = CaseworkSummary()
    refs = _list_referrals(open_only=True)
    out.referrals_open = len(refs)
    out.referrals_overdue = sum(1 for r in refs if r.follow_up_overdue(today))
    plans = _list_plans(active_only=True)
    out.plans_active = len(plans)
    out.plans_review_overdue = sum(1 for pl in plans
                                   if pl.review_overdue(today))
    for pl in plans:
        out.plans_by_type[pl.plan_type] = \
            out.plans_by_type.get(pl.plan_type, 0) + 1
    try:
        allegations = list_allegations(open_only=True, principal=p)
        out.lado_open = len(allegations)
        out.lado_not_reported = sum(
            1 for a in allegations if not a.reported_to_lado_date
            and add_school_days(a.allegation_date, 1) < today)
    except access.AccessDenied:
        pass
    transfers = _list_transfers()
    out.transfers_out_awaiting_receipt = sum(
        1 for t in transfers if t.direction == "Out"
        and not t.receipt_confirmed)
    out.transfers_in_overdue = sum(
        1 for t in transfers if t.direction == "In" and t.overdue(today))
    return out
