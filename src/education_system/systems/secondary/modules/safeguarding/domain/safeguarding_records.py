"""Safeguarding records around the concerns: plans and flags, Prevent, the
pupil's chronology and file, and passing the file on when a pupil leaves.

Everything here is for the DSL and deputies (:func:`safeguarding.is_lead`);
every read of a pupil's record is logged (:func:`safeguarding.log_access`).
The tables are registered in :mod:`safeguarding` (one schema, one store).

* **Plans and flags.** Child protection plan (with its category), child in
  need plan, early help, looked after and previously looked after - dated,
  with the local authority, social worker and next review. :func:`flags`
  gives what is active today; looked-after status falls back to what the
  pupil's admission application said when no plan is recorded.
* **Prevent** (the old Prevent Duty screen): a radicalisation concern with
  its Prevent details - concern type, risk level, indicators, online
  activity, referral pathway, agencies, parents informed, next review,
  status (Open ... Channel panel ... Closed) and outcome. A Prevent referral
  *is* a safeguarding concern (category Radicalisation / Prevent); closing
  it closes the concern.
* **Chronology** of a pupil: concerns, actions, referrals and outcomes,
  plans starting and ending, transfers - in date order.
* **Transfer file.** When a pupil leaves, the whole record as one document
  for the new school's DSL (:func:`transfer_file`); :func:`record_transfer`
  notes when and how it was sent (open concerns become Transferred), and
  :func:`receipt_confirmed` when the new school confirmed it.
  :func:`leavers_to_transfer` lists leavers whose file hasn't gone.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any

from education_system.systems.secondary.modules.safeguarding.domain import safeguarding as SG  # registers the tables
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = SG.ValidationError
PermissionDenied = SG.PermissionDenied
NotFound = SG.NotFound

CP = "Child protection plan"
CIN = "Child in need plan"
EARLY_HELP = "Early help"
LAC = "Looked after"
PLAC = "Previously looked after"
PLAN_TYPES: tuple[str, ...] = (CP, CIN, EARLY_HELP, LAC, PLAC)
CP_CATEGORIES: tuple[str, ...] = ("Neglect", "Physical abuse", "Emotional abuse",
                                  "Sexual abuse", "Multiple")

# The old Prevent Duty lists.
PREVENT_TYPES: tuple[str, ...] = (
    "Far-right extremism", "Islamist extremism", "Far-left extremism", "Incel/Misogynistic",
    "Single-issue (animal rights, environmental, etc.)", "Conspiracy theories",
    "Vulnerability to radicalisation", "Hate speech / Online", "Other")
DEFAULT_PREVENT_TYPE = "Vulnerability to radicalisation"
RISK_LEVELS: tuple[str, ...] = ("Low", "Medium", "High", "Imminent")
DEFAULT_RISK = "Low"
PATHWAYS: tuple[str, ...] = (
    "Internal monitoring", "DSL only", "Channel referral (Prevent)", "Police referral",
    "Other agency", "No referral")
DEFAULT_PATHWAY = "Internal monitoring"
PREVENT_STATUSES: tuple[str, ...] = (
    "Open", "Monitoring", "Channel panel", "Closed — no further action",
    "Closed — supported", "Closed — escalated")
PREVENT_OUTCOMES: tuple[str, ...] = (
    "Pending", "Diverted", "Supported", "Charged", "No further action", "Other")
_RISK_SEVERITY = {"Low": "Low", "Medium": "Medium", "High": "High", "Imminent": "Critical"}
_PATHWAY_AGENCY = {"Channel referral (Prevent)": "Channel (Prevent)",
                   "Police referral": "Police", "Other agency": "External agency"}

TRANSFER_METHODS: tuple[str, ...] = (
    "Secure electronic transfer", "Secure e-mail", "By hand (signed for)",
    "Recorded post", "Other")
TRANSFER_DAYS = 5   # KCSIE: within five school days of the pupil leaving


@dataclass(frozen=True)
class Plan:
    plan_id: int
    pupil_id: int
    plan_type: str
    category: str | None
    start_date: str
    end_date: str | None
    local_authority: str | None
    social_worker: str | None
    contact: str | None
    next_review: str | None
    notes: str | None
    created_by: str | None
    created_at: str
    updated_by: str | None
    updated_at: str
    pupil_name: str = ""
    admission_no: str = ""

    def active_on(self, day: str) -> bool:
        return self.start_date <= day and (not self.end_date or self.end_date >= day)


@dataclass(frozen=True)
class Prevent:
    concern: SG.Concern
    prevent_type: str
    risk_level: str
    indicators: str | None
    online_activity: str | None
    pathway: str
    agencies_involved: str | None
    parents_informed_date: str | None
    next_review_date: str | None
    channel_status: str
    prevent_outcome: str
    closure_notes: str | None

    @property
    def referral_id(self) -> int:     # the old name
        return self.concern.concern_id


@dataclass(frozen=True)
class Transfer:
    transfer_id: int
    pupil_id: int
    destination: str
    method: str
    sent_date: str
    sent_by: str | None
    received_date: str | None
    received_by_name: str | None
    notes: str | None
    created_at: str
    pupil_name: str = ""
    admission_no: str = ""


_lead = SG._require_lead
_date = SG._date
_text = SG._text
_choice = SG._choice


def _pupil_or_raise(ref: Any) -> P.Pupil:
    p = SG._pupil(ref)
    if p is None:
        raise ValidationError(["Choose the pupil" if ref in (None, "") else f"No pupil {ref}"])
    return p


def _plan_row(r) -> Plan:
    base = {k: r[k] for k in Plan.__dataclass_fields__ if k not in ("pupil_name",
                                                                    "admission_no")}
    return Plan(**base, pupil_name=SG._name(r), admission_no=r["admission_no"])


_PLAN_SELECT = ("SELECT s.*, p.legal_last_name, p.legal_first_name, p.preferred_name, "
                "p.admission_no FROM safeguarding_plans s JOIN pupils p USING (pupil_id)")


# ── Plans and flags ──────────────────────────────────────────────────

def _clean_plan(data: dict[str, Any], cur: Plan | None) -> tuple[dict[str, Any], list[str]]:
    keys = ("plan_type", "category", "start_date", "end_date", "local_authority",
            "social_worker", "contact", "next_review", "notes")
    merged = {k: getattr(cur, k) for k in keys} if cur else {}
    merged.update({k: v for k, v in data.items() if k in keys})
    problems: list[str] = []
    out: dict[str, Any] = {}
    out["plan_type"] = _choice(merged.get("plan_type"), PLAN_TYPES, "Plan", problems, None)
    if not out["plan_type"]:
        problems.append("Choose the kind of plan")
    out["category"] = _choice(merged.get("category"), CP_CATEGORIES, "Category", problems, None)
    if out["plan_type"] == CP and not out["category"]:
        problems.append("A child protection plan has a category (neglect, physical, "
                        "emotional, sexual abuse or multiple)")
    if out["plan_type"] != CP:
        out["category"] = None
    for k, label in (("start_date", "Start date"), ("end_date", "End date"),
                     ("next_review", "Next review")):
        out[k] = _date(merged.get(k), label, problems)
    if not out["start_date"] and not any(p.startswith("Start date") for p in problems):
        problems.append("Start date is required")
    if out["start_date"] and out["end_date"] and out["end_date"] < out["start_date"]:
        problems.append("End date cannot be before start date")
    for k in ("local_authority", "social_worker", "contact"):
        out[k] = _text(merged.get(k), 120)
    out["notes"] = _text(merged.get("notes"), 4000)
    return out, problems


def get_plan(plan_id: int, *, actor: Principal) -> Plan:
    _lead(actor, "plan_view")
    with database.connect() as conn:
        r = conn.execute(_PLAN_SELECT + " WHERE s.plan_id = ?", (int(plan_id),)).fetchone()
    if r is None:
        raise NotFound(f"No plan #{plan_id}")
    return _plan_row(r)


def list_plans(*, actor: Principal, pupil_id: int | None = None, plan_type: str | None = None,
               active_only: bool = False, today: _dt.date | None = None) -> list[Plan]:
    _lead(actor, "plan_list")
    where, params = [], []
    if pupil_id is not None:
        where.append("s.pupil_id = ?")
        params.append(int(pupil_id))
    if plan_type:
        where.append("s.plan_type = ?")
        params.append(plan_type)
    sql = _PLAN_SELECT + (" WHERE " + " AND ".join(where) if where else "") + \
        " ORDER BY s.start_date DESC, s.plan_id DESC"
    with database.connect() as conn:
        rows = [_plan_row(r) for r in conn.execute(sql, params)]
    if active_only:
        day = (today or _today()).isoformat()
        rows = [x for x in rows if x.active_on(day)]
    if pupil_id is not None:
        SG.log_access(actor, "plans", pupil_id=int(pupil_id))
    return rows


def _overlapping(conn, pupil_id: int, c: dict[str, Any], skip: int = 0) -> list[str]:
    end = c["end_date"] or "9999-12-31"
    rows = conn.execute("SELECT plan_id, start_date, end_date FROM safeguarding_plans WHERE "
                        "pupil_id = ? AND plan_type = ? AND plan_id != ?",
                        (pupil_id, c["plan_type"], skip)).fetchall()
    return [f"Overlaps {c['plan_type'].lower()} #{r['plan_id']} from {r['start_date']}"
            for r in rows if r["start_date"] <= end and c["start_date"] <= (r["end_date"] or
                                                                          "9999-12-31")]


def add_plan(data: dict[str, Any], *, actor: Principal) -> Plan:
    """Record a plan or status. *data* carries ``pupil_id``."""
    _lead(actor, "plan")
    p = _pupil_or_raise(data.get("pupil_id") or data.get("pupil"))
    c, problems = _clean_plan(data, None)
    with database.connect() as conn:
        if not problems:
            problems += _overlapping(conn, p.pupil_id, c)
        if problems:
            raise ValidationError(problems)
        pid = conn.execute(
            "INSERT INTO safeguarding_plans (pupil_id, plan_type, category, start_date, "
            "end_date, local_authority, social_worker, contact, next_review, notes, created_by, "
            "updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (p.pupil_id, c["plan_type"], c["category"], c["start_date"], c["end_date"],
             c["local_authority"], c["social_worker"], c["contact"], c["next_review"],
             c["notes"], actor.username, actor.username)).lastrowid
        SG._audit(conn, "plan", actor, pupil_id=p.pupil_id, plan_id=pid, type=c["plan_type"])
    activity_log.record("safeguarding.plan", target=p.admission_no, principal=actor, plan=pid)
    return get_plan(pid, actor=actor)


def update_plan(plan_id: int, changes: dict[str, Any], *, actor: Principal) -> Plan:
    cur = get_plan(plan_id, actor=actor)
    c, problems = _clean_plan(changes, cur)
    with database.connect() as conn:
        if not problems:
            problems += _overlapping(conn, cur.pupil_id, c, cur.plan_id)
        if problems:
            raise ValidationError(problems)
        changed = [k for k, v in c.items() if v != getattr(cur, k)]
        if not changed:
            return cur
        conn.execute("UPDATE safeguarding_plans SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE plan_id = ?",
                     (*(c[k] for k in changed), actor.username, cur.plan_id))
        SG._audit(conn, "plan_update", actor, pupil_id=cur.pupil_id, plan_id=cur.plan_id,
                  fields=changed)
    activity_log.record("safeguarding.plan_update", target=cur.admission_no, principal=actor,
                        plan=cur.plan_id)
    return get_plan(cur.plan_id, actor=actor)


def end_plan(plan_id: int, *, actor: Principal, end_date: str | None = None,
             note: str | None = None) -> Plan:
    cur = get_plan(plan_id, actor=actor)
    if cur.end_date:
        raise ValidationError([f"That plan already ended on {cur.end_date}"])
    notes = cur.notes
    if note and note.strip():
        notes = ((notes + "\n") if notes else "") + f"Ended: {note.strip()}"
    return update_plan(cur.plan_id, {"end_date": end_date or _today().isoformat(),
                                     "notes": notes}, actor=actor)


def delete_plan(plan_id: int, *, actor: Principal) -> bool:
    """Only for a plan recorded in error (end a real one instead)."""
    cur = get_plan(plan_id, actor=actor)
    with database.connect() as conn:
        conn.execute("DELETE FROM safeguarding_plans WHERE plan_id = ?", (cur.plan_id,))
        SG._audit(conn, "plan_delete", actor, pupil_id=cur.pupil_id, plan_id=cur.plan_id,
                  type=cur.plan_type)
    activity_log.record("safeguarding.plan_delete", target=cur.admission_no, principal=actor,
                        plan=cur.plan_id)
    return True


def _admissions_looked_after(pupil_id: int) -> str | None:
    """'current' / 'previous' from the pupil's admission application."""
    try:
        from education_system.systems.secondary.modules.admissions.domain import admissions  # noqa: F401
        with database.connect() as conn:
            r = conn.execute("SELECT looked_after FROM applications WHERE admitted_pupil_id = ? "
                             "ORDER BY application_id DESC LIMIT 1",
                             (int(pupil_id),)).fetchone()
    except Exception:  # noqa: BLE001 - admissions is a help, not a gate
        return None
    v = r["looked_after"] if r else None
    return v if v in ("current", "previous") else None


def flags(pupil_id: int, *, actor: Principal, today: _dt.date | None = None,
          log: bool = True) -> dict[str, Any]:
    """What is true for the pupil today: ``{'cp', 'cp_category', 'cin',
    'early_help', 'looked_after', 'previously_looked_after', 'from_admissions',
    'open_concerns', 'labels'}``."""
    _lead(actor, "flags")
    day = (today or _today()).isoformat()
    with database.connect() as conn:
        plans = [_plan_row(r) for r in conn.execute(_PLAN_SELECT + " WHERE s.pupil_id = ?",
                                                    (int(pupil_id),))]
        open_n = conn.execute("SELECT count(*) FROM safeguarding_concerns WHERE pupil_id = ? "
                              "AND status NOT IN ('Closed', 'Transferred')",
                              (int(pupil_id),)).fetchone()[0]
    active = [x for x in plans if x.active_on(day)]
    kinds = {x.plan_type for x in active}
    cp = next((x for x in active if x.plan_type == CP), None)
    out = {"cp": cp is not None, "cp_category": cp.category if cp else None,
           "cin": CIN in kinds, "early_help": EARLY_HELP in kinds,
           "looked_after": LAC in kinds, "previously_looked_after": PLAC in kinds,
           "from_admissions": False, "open_concerns": int(open_n)}
    if not any(x.plan_type in (LAC, PLAC) for x in plans):
        adm = _admissions_looked_after(pupil_id)
        if adm:
            out["looked_after" if adm == "current" else "previously_looked_after"] = True
            out["from_admissions"] = True
    labels = []
    if out["cp"]:
        labels.append(f"CP plan ({out['cp_category']})" if out["cp_category"] else "CP plan")
    labels += [lab for key, lab in (("cin", "CIN plan"), ("early_help", "Early help"),
                                    ("looked_after", "Looked after"),
                                    ("previously_looked_after", "Previously looked after"))
               if out[key]]
    if out["from_admissions"]:
        labels[-1] += " (from admissions)"
    if open_n:
        labels.append(f"{open_n} open concern(s)")
    out["labels"] = labels
    if log and (labels or plans):
        SG.log_access(actor, "flags", pupil_id=int(pupil_id))
    return out


def profile_line(pupil_id: int, *, actor: Principal) -> str | None:
    """One line for the pupil profile - leads only, and only when there is
    something on record. Everyone else gets None (need to know)."""
    if not SG.is_lead(actor):
        return None
    f = flags(pupil_id, actor=actor)
    return "Safeguarding: " + ", ".join(f["labels"]) if f["labels"] else None


def plan_reviews_due(*, actor: Principal, within_days: int = 14,
                     today: _dt.date | None = None) -> list[Plan]:
    day = today or _today()
    horizon = (day + _dt.timedelta(days=within_days)).isoformat()
    return sorted((x for x in list_plans(actor=actor, active_only=True, today=day)
                   if x.next_review and x.next_review <= horizon),
                  key=lambda x: x.next_review or "")


# ── Prevent (the old Prevent Duty screen) ───────────────────────────

_PREVENT_FIELDS = ("prevent_type", "risk_level", "indicators", "online_activity", "pathway",
                   "agencies_involved", "parents_informed_date", "next_review_date",
                   "channel_status", "prevent_outcome", "closure_notes")


def _clean_prevent(data: dict[str, Any], cur: Prevent | None
                   ) -> tuple[dict[str, Any], list[str]]:
    merged = {k: getattr(cur, k) for k in _PREVENT_FIELDS} if cur else {}
    merged.update({k: v for k, v in data.items() if k in _PREVENT_FIELDS})
    problems: list[str] = []
    out: dict[str, Any] = {
        "prevent_type": _choice(merged.get("prevent_type") or merged.get("concern_type"),
                                PREVENT_TYPES, "Concern type", problems, DEFAULT_PREVENT_TYPE),
        "risk_level": _choice(merged.get("risk_level"), RISK_LEVELS, "Risk level", problems,
                              DEFAULT_RISK),
        "pathway": _choice(merged.get("pathway") or merged.get("referral_pathway"), PATHWAYS,
                           "Referral pathway", problems, DEFAULT_PATHWAY),
        "channel_status": _choice(merged.get("channel_status") or merged.get("status"),
                                  PREVENT_STATUSES, "Status", problems, "Open"),
        "prevent_outcome": _choice(merged.get("prevent_outcome") or merged.get("outcome"),
                                   PREVENT_OUTCOMES, "Outcome", problems, "Pending")}
    for k in ("indicators", "online_activity", "agencies_involved", "closure_notes"):
        out[k] = _text(merged.get(k), 4000)
    for k, label in (("parents_informed_date", "Parents informed date"),
                     ("next_review_date", "Next review date")):
        out[k] = _date(merged.get(k), label, problems)
    return out, problems


def _prevent_row(c: SG.Concern, r) -> Prevent:
    return Prevent(concern=c, **{k: r[k] for k in _PREVENT_FIELDS})


def get_prevent(concern_id: int, *, actor: Principal) -> Prevent:
    c = SG.get(concern_id, actor=actor)
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM safeguarding_prevent WHERE concern_id = ?",
                         (c.concern_id,)).fetchone()
    if r is None:
        raise NotFound(f"Concern #{concern_id} has no Prevent details")
    return _prevent_row(c, r)


def list_prevent(*, actor: Principal, status: str | None = None, risk_level: str | None = None,
                 open_only: bool = False) -> list[Prevent]:
    """The old Prevent list (Status, Risk and Open only filters)."""
    rows = {c.concern_id: c for c in SG.list_concerns(actor=actor, category=SG.PREVENT)}
    with database.connect() as conn:
        details = conn.execute("SELECT * FROM safeguarding_prevent").fetchall()
    out = [_prevent_row(rows[r["concern_id"]], r) for r in details if r["concern_id"] in rows]
    have = {x.concern.concern_id for x in out}
    for c in rows.values():           # a radicalisation concern with no details yet
        if c.concern_id not in have:
            out.append(Prevent(c, DEFAULT_PREVENT_TYPE, DEFAULT_RISK, None, None,
                               DEFAULT_PATHWAY, None, None, None,
                               "Closed — no further action" if c.status in SG.FINISHED
                               else "Open", "Pending", None))
    if status:
        out = [x for x in out if x.channel_status == status]
    if risk_level:
        out = [x for x in out if x.risk_level == risk_level]
    if open_only:
        out = [x for x in out if not x.channel_status.startswith("Closed")]
    out.sort(key=lambda x: (x.concern.raised_date, x.concern.concern_id), reverse=True)
    return sorted(out, key=lambda x: -RISK_LEVELS.index(x.risk_level))


def create_prevent(data: dict[str, Any], *, actor: Principal) -> Prevent:
    """The old New referral: a Radicalisation / Prevent concern with its
    Prevent details. *data* has the concern's fields (pupil_id, description,
    raised_by, raised_date, notes...) and the Prevent ones."""
    det, problems = _clean_prevent(data, None)
    if problems:
        raise ValidationError(problems)
    concern = {k: v for k, v in data.items() if k in SG.FIELDS or k in ("pupil_id", "pupil")}
    concern.update(category=SG.PREVENT, severity=_RISK_SEVERITY[det["risk_level"]],
                   level_of_need="Prevent / Channel" if det["pathway"] ==
                   "Channel referral (Prevent)" else concern.get("level_of_need"))
    if data.get("dsl_name") and not data.get("dsl_reviewer"):
        concern["dsl_reviewer"] = data["dsl_name"]
    if data.get("dsl_informed_date") and not data.get("review_date"):
        concern["review_date"] = data["dsl_informed_date"]
    agency = _PATHWAY_AGENCY.get(det["pathway"])
    if agency and data.get("referral_date"):
        concern.update(referral_body=agency, referral_date=data["referral_date"],
                       referral_reference=data.get("referral_ref") or
                       data.get("referral_reference"))
    if det["channel_status"].startswith("Closed"):
        raise ValidationError(["Record the referral first, then close it"])
    c = SG.raise_concern(concern, actor=actor)
    with database.connect() as conn:
        conn.execute(f"INSERT INTO safeguarding_prevent (concern_id, {', '.join(_PREVENT_FIELDS)})"
                     f" VALUES (?, {', '.join('?' * len(_PREVENT_FIELDS))})",
                     (c.concern_id, *(det[k] for k in _PREVENT_FIELDS)))
        SG._audit(conn, "prevent", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
                  risk=det["risk_level"])
    return get_prevent(c.concern_id, actor=actor)


def update_prevent(concern_id: int, changes: dict[str, Any], *, actor: Principal) -> Prevent:
    """The old Edit referral / Set status: the Prevent details (and the
    concern's own fields, if given). A Closed status closes the concern."""
    c = SG.get(concern_id, actor=actor, log=False)
    if c.category != SG.PREVENT:
        raise ValidationError(["That concern isn't a radicalisation / Prevent concern"])
    try:
        cur: Prevent | None = get_prevent(concern_id, actor=actor)
    except NotFound:
        cur = None
    det, problems = _clean_prevent(changes, cur)
    if problems:
        raise ValidationError(problems)
    closing = det["channel_status"].startswith("Closed") and c.is_open
    concern_changes = {k: v for k, v in changes.items() if k in SG.FIELDS and k not in (
        "status", "outcome", "category")}
    if "risk_level" in changes:
        concern_changes["severity"] = _RISK_SEVERITY[det["risk_level"]]
    if concern_changes:
        SG.update(c.concern_id, concern_changes, actor=actor)
    with database.connect() as conn:
        conn.execute(f"INSERT INTO safeguarding_prevent (concern_id, {', '.join(_PREVENT_FIELDS)})"
                     f" VALUES (?, {', '.join('?' * len(_PREVENT_FIELDS))}) ON CONFLICT "
                     "(concern_id) DO UPDATE SET "
                     + ", ".join(f"{k} = excluded.{k}" for k in _PREVENT_FIELDS),
                     (c.concern_id, *(det[k] for k in _PREVENT_FIELDS)))
        SG._audit(conn, "prevent_update", actor, concern_id=c.concern_id, pupil_id=c.pupil_id,
                  status=det["channel_status"])
    if closing:
        SG.close_concern(c.concern_id, actor=actor,
                         outcome=f"{det['channel_status']} ({det['prevent_outcome']})"
                         + (f": {det['closure_notes']}" if det["closure_notes"] else ""))
    elif det["channel_status"] == "Channel panel" and c.status in (SG.NEW, "Open", "Monitoring"):
        SG.update(c.concern_id, {"status": "Escalated", "level_of_need": "Prevent / Channel"},
                  actor=actor)
    activity_log.record("safeguarding.prevent", target=c.admission_no, principal=actor,
                        concern=c.concern_id)
    return get_prevent(c.concern_id, actor=actor)


def close_prevent(concern_id: int, *, actor: Principal, status: str = "Closed — supported",
                  outcome: str = "Supported", notes: str | None = None) -> Prevent:
    """The old Close referral."""
    if not str(status).startswith("Closed"):
        raise ValidationError(["Choose one of the Closed statuses"])
    return update_prevent(concern_id, {"channel_status": status, "prevent_outcome": outcome,
                                       "closure_notes": notes}, actor=actor)


def prevent_summary(*, actor: Principal) -> dict[str, Any]:
    """The old Prevent cohort summary."""
    from collections import Counter
    rows = list_prevent(actor=actor)
    return {"total": len(rows),
            "open": sum(1 for x in rows if not x.channel_status.startswith("Closed")),
            "by_status": dict(Counter(x.channel_status for x in rows)),
            "by_risk": dict(Counter(x.risk_level for x in rows)),
            "by_type": dict(Counter(x.prevent_type for x in rows)),
            "by_pathway": dict(Counter(x.pathway for x in rows)),
            "channel": sum(1 for x in rows if x.pathway == "Channel referral (Prevent)")}


# ── Chronology and the pupil's file ──────────────────────────────────

def chronology(pupil_id: int, *, actor: Principal, log: bool = True) -> list[dict[str, Any]]:
    """Everything on the pupil's record in date order:
    ``{'date', 'kind', 'concern_id', 'text', 'by'}``."""
    _lead(actor, "chronology")
    p = _pupil_or_raise(pupil_id)
    out: list[dict[str, Any]] = []
    with database.connect() as conn:
        concerns = conn.execute("SELECT * FROM safeguarding_concerns WHERE pupil_id = ?",
                                (p.pupil_id,)).fetchall()
        for c in concerns:
            out.append({"date": c["incident_date"] or c["raised_date"], "kind": "Concern",
                        "concern_id": c["concern_id"], "by": c["raised_by"] or "",
                        "text": ("URGENT - " if c["urgent"] else "") + f"{c['category']} "
                                f"({c['severity']}): {c['description']}"
                                + (f"\n  Child's words: \"{c['child_words']}\""
                                   if c["child_words"] else "")
                                + (f"\n  Injury / body map: {c['body_map']}"
                                   if c["body_map"] else "")
                                + (f"\n  Immediate action: {c['immediate_action']}"
                                   if c["immediate_action"] else "")})
            if c["closed_date"]:
                out.append({"date": c["closed_date"], "kind": c["status"],
                            "concern_id": c["concern_id"], "by": "",
                            "text": f"Concern {c['status'].lower()}: {c['outcome'] or ''}"})
        ids = [c["concern_id"] for c in concerns]
        if ids:
            marks = ", ".join("?" * len(ids))
            for a in conn.execute(f"SELECT * FROM safeguarding_actions WHERE concern_id IN "
                                  f"({marks})", ids):
                if a["action_type"] in ("Case closed",):
                    continue
                out.append({"date": a["action_date"], "kind": a["action_type"],
                            "concern_id": a["concern_id"], "by": a["actioned_by"] or "",
                            "text": a["summary"]
                            + (f"\n  Outcome: {a['outcome']}" if a["outcome"] else "")
                            + (f"\n  Follow-up: {a['follow_up']}" if a["follow_up"] else "")
                            + (f"\n  Due {a['due_date']}" + (f", done {a['completed_date']}"
                                                            if a["completed_date"] else "")
                               if a["due_date"] else "")})
        for r in conn.execute(_PLAN_SELECT + " WHERE s.pupil_id = ?", (p.pupil_id,)):
            x = _plan_row(r)
            what = x.plan_type + (f" ({x.category})" if x.category else "")
            out.append({"date": x.start_date, "kind": "Plan", "concern_id": None,
                        "by": x.social_worker or "",
                        "text": f"{what} started" + (f", {x.local_authority}"
                                                     if x.local_authority else "")})
            if x.end_date:
                out.append({"date": x.end_date, "kind": "Plan", "concern_id": None, "by": "",
                            "text": f"{what} ended"})
        for r in conn.execute("SELECT * FROM safeguarding_transfers WHERE pupil_id = ?",
                              (p.pupil_id,)):
            out.append({"date": r["sent_date"], "kind": "Transfer", "concern_id": None,
                        "by": r["sent_by"] or "",
                        "text": f"Record sent to {r['destination']} ({r['method']})"
                                + (f"; receipt confirmed {r['received_date']}"
                                   if r["received_date"] else "")})
    if log:
        SG.log_access(actor, "chronology", pupil_id=p.pupil_id)
        activity_log.record("safeguarding.chronology", target=p.admission_no, principal=actor)
    order = {"Concern": 0, "Plan": 1}
    return sorted(out, key=lambda x: (x["date"] or "", order.get(x["kind"], 2),
                                      x["concern_id"] or 0))


def chronology_text(pupil_id: int, *, actor: Principal) -> str:
    p = _pupil_or_raise(pupil_id)
    lines = [f"CONFIDENTIAL - safeguarding chronology: {p.display_name} ({p.admission_no})", ""]
    for e in chronology(p.pupil_id, actor=actor):
        ref = f"#{e['concern_id']} " if e["concern_id"] else ""
        lines.append(f"{e['date'] or '':<10}  {e['kind']:<20} {ref}{e['text']}"
                     + (f"  [{e['by']}]" if e["by"] else ""))
    if len(lines) == 2:
        lines.append("Nothing on record.")
    return "\n".join(lines)


def pupil_file(pupil_id: int, *, actor: Principal) -> dict[str, Any]:
    """The pupil's whole record (logged once as a file read)."""
    _lead(actor, "file")
    p = _pupil_or_raise(pupil_id)
    SG.log_access(actor, "file", pupil_id=p.pupil_id)
    activity_log.record("safeguarding.file", target=p.admission_no, principal=actor)
    concerns = SG.list_concerns(actor=actor, pupil_id=p.pupil_id)
    return {"pupil": p, "flags": flags(p.pupil_id, actor=actor, log=False),
            "concerns": concerns,
            "referrals": SG.list_referrals(actor=actor, pupil_id=p.pupil_id),
            "plans": list_plans(actor=actor, pupil_id=p.pupil_id),
            "transfers": list_transfers(actor=actor, pupil_id=p.pupil_id)}


# ── Transfers ────────────────────────────────────────────────────────

def _transfer_row(r) -> Transfer:
    base = {k: r[k] for k in Transfer.__dataclass_fields__ if k not in ("pupil_name",
                                                                        "admission_no")}
    return Transfer(**base, pupil_name=SG._name(r), admission_no=r["admission_no"])


def list_transfers(*, actor: Principal, pupil_id: int | None = None) -> list[Transfer]:
    _lead(actor, "transfer_list")
    sql = ("SELECT t.*, p.legal_last_name, p.legal_first_name, p.preferred_name, "
           "p.admission_no FROM safeguarding_transfers t JOIN pupils p USING (pupil_id)")
    params: list[Any] = []
    if pupil_id is not None:
        sql += " WHERE t.pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        return [_transfer_row(r) for r in conn.execute(
            sql + " ORDER BY t.sent_date DESC, t.transfer_id DESC", params)]


def _leaving(pupil_id: int):
    try:
        from education_system.systems.secondary.modules.pupils.domain import enrolment as EN
        return EN.current_leaving(pupil_id)
    except Exception:  # noqa: BLE001 - leaving details are a help
        return None


def transfer_file(pupil_id: int, *, actor: Principal) -> str:
    """The child protection file for the new school's DSL, as one document."""
    f = pupil_file(pupil_id, actor=actor)
    p: P.Pupil = f["pupil"]
    lv = _leaving(p.pupil_id)
    SG.log_access(actor, "transfer file", pupil_id=p.pupil_id)
    team = SG.team()
    lines = ["CONFIDENTIAL - CHILD PROTECTION FILE",
             "To be opened only by the designated safeguarding lead.", "",
             f"Pupil:          {p.full_name}" + (f" (known as {p.preferred_name})"
                                                 if p.preferred_name else ""),
             f"Date of birth:  {p.date_of_birth}", f"UPN:            {p.upn or '-'}",
             f"Admission no.:  {p.admission_no}",
             f"Year / form:    {p.year_group} / {p.form_group or '-'}",
             "Address:        " + (", ".join(x for x in (p.address_line1, p.address_line2,
                                                           p.town, p.postcode) if x) or "-")]
    if lv:
        lines += [f"Left:           {lv.leaving_date} ({lv.reason})",
                  f"Destination:    {lv.destination_school or '-'}"
                  + (f" (URN {lv.destination_urn})" if lv.destination_urn else "")]
    lines += [f"Prepared:       {_today().isoformat()} by {SG.staff_name(actor)}"]
    if team:
        lines += ["Our DSL team:   " + "; ".join(
            f"{m['name']} ({m['team_role']})" + (f" {m['phone']}" if m["phone"] else "")
            + (f" {m['email']}" if m["email"] else "") for m in team)]
    lines += ["", "CURRENT STATUS", "  " + (", ".join(f["flags"]["labels"]) or "None recorded")]
    lines += ["", "PLANS"]
    for x in f["plans"]:
        lines.append(f"  {x.plan_type}" + (f" ({x.category})" if x.category else "")
                     + f": {x.start_date} to {x.end_date or 'now'}"
                     + (f"; {x.local_authority}" if x.local_authority else "")
                     + (f"; social worker {x.social_worker}" if x.social_worker else "")
                     + (f" {x.contact}" if x.contact else ""))
    if not f["plans"]:
        lines.append("  None")
    lines += ["", "REFERRALS"]
    for r in f["referrals"]:
        lines.append(f"  {r.referral_date}  {r.agency}" + (f" ref {r.reference}"
                                                            if r.reference else "")
                     + f" - {r.outcome}" + (f" ({r.outcome_date})" if r.outcome_date else ""))
    if not f["referrals"]:
        lines.append("  None")
    lines += ["", "CONCERNS"]
    for c in sorted(f["concerns"], key=lambda c: c.raised_date):
        lines += [f"  #{c.concern_id}  raised {c.raised_date} by {c.raised_by or '-'}: "
                  f"{c.category}, {c.severity}, {c.status}"
                  + (f", level {c.level_of_need}" if c.level_of_need else ""),
                  f"      Incident: {c.incident_date or '-'} {c.incident_time or ''} "
                  f"{c.location or ''}".rstrip(),
                  f"      {c.description}"]
        for label, v in (("Child's words", c.child_words), ("Injury / body map", c.body_map),
                         ("Immediate action", c.immediate_action),
                         ("Others involved", c.people_involved),
                         ("Allegation about", c.allegation_about),
                         ("DSL notes", c.notes), ("Outcome", c.outcome)):
            if v:
                lines.append(f"      {label}: {v}")
    if not f["concerns"]:
        lines.append("  None")
    lines += ["", "CHRONOLOGY", chronology_text(p.pupil_id, actor=actor).split("\n", 2)[-1],
              "", "Please confirm receipt to the sending school's DSL."]
    activity_log.record("safeguarding.transfer_file", target=p.admission_no, principal=actor)
    return "\n".join(lines)


def record_transfer(pupil_id: int, data: dict[str, Any], *, actor: Principal) -> Transfer:
    """The file was sent: destination (defaults to the leaving record's),
    method and date. Open concerns become Transferred."""
    _lead(actor, "transfer")
    p = _pupil_or_raise(pupil_id)
    problems: list[str] = []
    lv = _leaving(p.pupil_id)
    dest = _text(data.get("destination"), 160) or (lv.destination_school if lv else None)
    if not dest:
        problems.append("Say which school (or setting) the file went to")
    method = _choice(data.get("method"), TRANSFER_METHODS, "Method", problems, None)
    if not method:
        problems.append("Say how it was sent (it must go securely)")
    sent = _date(data.get("sent_date"), "Sent date", problems) or _today().isoformat()
    if sent > _today().isoformat():
        problems.append("Record the transfer once it has been sent")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = conn.execute("INSERT INTO safeguarding_transfers (pupil_id, destination, method, "
                           "sent_date, sent_by, notes) VALUES (?, ?, ?, ?, ?, ?)",
                           (p.pupil_id, dest, method, sent, SG.staff_name(actor),
                            _text(data.get("notes"), 2000))).lastrowid
        open_ids = [r[0] for r in conn.execute(
            "SELECT concern_id FROM safeguarding_concerns WHERE pupil_id = ? AND status NOT IN "
            "('Closed', 'Transferred')", (p.pupil_id,))]
        for cid in open_ids:
            conn.execute("UPDATE safeguarding_concerns SET status = 'Transferred', "
                         "closed_date = ?, outcome = COALESCE(outcome, ?), updated_by = ?, "
                         "updated_at = datetime('now') WHERE concern_id = ?",
                         (sent, f"File transferred to {dest}", actor.username, cid))
        all_ids = [r[0] for r in conn.execute(
            "SELECT concern_id FROM safeguarding_concerns WHERE pupil_id = ?", (p.pupil_id,))]
        for cid in all_ids:
            conn.execute("INSERT INTO safeguarding_actions (concern_id, action_date, "
                         "action_type, actioned_by, summary, created_by) VALUES "
                         "(?, ?, 'Record transferred', ?, ?, ?)",
                         (cid, sent, SG.staff_name(actor), f"File sent to {dest} ({method})",
                          actor.username))
        SG._audit(conn, "transfer", actor, pupil_id=p.pupil_id, transfer_id=tid,
                  closed=len(open_ids))
    activity_log.record("safeguarding.transfer", target=p.admission_no, principal=actor,
                        transfer=tid)
    return next(t for t in list_transfers(actor=actor, pupil_id=p.pupil_id)
                if t.transfer_id == tid)


def receipt_confirmed(transfer_id: int, *, actor: Principal, received_by: str,
                      day: str | None = None) -> Transfer:
    _lead(actor, "transfer_receipt")
    problems: list[str] = []
    d = _date(day, "Date", problems) or _today().isoformat()
    who = _text(received_by, 120)
    if not who:
        problems.append("Who at the new school confirmed it?")
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM safeguarding_transfers WHERE transfer_id = ?",
                         (int(transfer_id),)).fetchone()
        if r is None:
            raise NotFound(f"No transfer #{transfer_id}")
        if d < r["sent_date"]:
            problems.append("Receipt can't be before the file was sent")
        if problems:
            raise ValidationError(problems)
        conn.execute("UPDATE safeguarding_transfers SET received_date = ?, received_by_name = ? "
                     "WHERE transfer_id = ?", (d, who, r["transfer_id"]))
        SG._audit(conn, "transfer_receipt", actor, pupil_id=r["pupil_id"],
                  transfer_id=r["transfer_id"])
    activity_log.record("safeguarding.transfer_receipt", principal=actor,
                        transfer=r["transfer_id"])
    return next(t for t in list_transfers(actor=actor, pupil_id=r["pupil_id"])
                if t.transfer_id == r["transfer_id"])


def _weekdays_after(day: str, n: int) -> str:
    d = _dt.date.fromisoformat(day)
    while n:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.isoformat()


def leavers_to_transfer(*, actor: Principal, today: _dt.date | None = None
                        ) -> list[dict[str, Any]]:
    """Pupils who have left with a safeguarding record (concerns or plans)
    and no transfer recorded since they left: ``{'pupil', 'leaving_date',
    'destination', 'due', 'overdue'}``."""
    _lead(actor, "transfer_due")
    day = (today or _today()).isoformat()
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT p.pupil_id FROM pupils p WHERE p.roll_status = 'left' AND ("
            "EXISTS (SELECT 1 FROM safeguarding_concerns c WHERE c.pupil_id = p.pupil_id) OR "
            "EXISTS (SELECT 1 FROM safeguarding_plans s WHERE s.pupil_id = p.pupil_id))"
        ).fetchall()
        sent = {r["pupil_id"]: r["last"] for r in conn.execute(
            "SELECT pupil_id, max(sent_date) AS last FROM safeguarding_transfers "
            "GROUP BY pupil_id")}
    out = []
    for r in rows:
        p = P.get_pupil(r["pupil_id"])
        left = p.leaving_date or day
        if sent.get(p.pupil_id) and sent[p.pupil_id] >= left:
            continue
        lv = _leaving(p.pupil_id)
        due_day = _weekdays_after(left, TRANSFER_DAYS)
        out.append({"pupil": p, "leaving_date": left,
                    "destination": (lv.destination_school if lv else None) or "",
                    "due": due_day, "overdue": due_day < day})
    return sorted(out, key=lambda x: x["due"])
