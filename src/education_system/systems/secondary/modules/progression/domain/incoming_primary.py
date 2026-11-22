"""Year 6 -> Year 7: pupils arriving from primary through the platform.

The primary school opens a transfer on the platform's transfer queue
(``platform.cross_system.transitions``), addressed to this school, and
approves a handover: identity, parents, KS2 results, attendance, SEN and
medical needs, interventions in flight and a pointer to the safeguarding
file. This module is the receiving end:

* **The queue.** Transfers from primary addressed to secondary, with their
  status (expected ... handover ready ... admitted / completed, or rejected)
  and where this school is with each pupil.
* **Acknowledge / reject.** Acknowledging tells primary the handover arrived
  (it ticks "Handover documents received"); rejecting needs a reason and
  goes back to primary. Both are the platform's own calls.
* **The handover.** Read only through ``transitions.get_handover_for`` with
  the viewer's role and the purpose ``transition_planning``, so the
  platform decides what each person sees (and audits it): routine fields
  for every member of staff, SEN and medical for the roles entitled to
  them. The **safeguarding flag** - that a safeguarding file exists - is
  shown only to the safeguarding leads (:data:`access.SAFEGUARDING_LEADS`);
  its detail travels DSL-to-DSL, never in the payload.
* **Match or create.** An incoming pupil is matched to an existing
  admissions application (Year 7, same name and date of birth) and/or a
  pupil record (same UPN, or name and date of birth), or a pupil record is
  created from the handover (``modules.pupils.domain.pupils.create_pupil``, so only
  :data:`access.PUPIL_EDITORS` can, with the parents added as contacts).
  Matching tells the platform the pupil is admitted here (step 6) and
  links this school's record to the pupil's journey.
* **Checklist.** The platform's checklist for the primary -> secondary
  boundary (transition report sent, transition day attended, SEND meeting,
  documents received) plus this school's: handover received, matched to a
  pupil, SEN information passed to the SENCO, safeguarding file received
  (safeguarding leads only), KS2 data imported into prior attainment
  (``headline_measures.set_ks2``).
* **Step log.** The platform's transfer events and this school's own
  ``incoming_primary_audit`` rows, merged in time order.
* **Complete.** Once the pupil has started, completing the transfer closes
  it on the platform (primary's record is closed by primary).

Pupils coming back from **alternative provision** as a new admission (after
sole registration at the AP - ``platform.cross_system.ap_referrals``) arrive
in the same queue, marked "from AP": same acknowledge / match / create /
complete steps, with the pupil's own year group instead of Year 7 and no
KS2 import.

Who: all staff see the queue; acknowledging, rejecting, matching, the
checklist, KS2 import and completing are for the admissions office
(``access.RESTRICTED["Admissions"]``). Nothing here imports the primary
system.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.admissions.domain import admissions as AD  # registers the FK target
from education_system.systems.secondary.modules.pupils.domain import contacts as C
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    PUPIL_EDITORS,
    RESTRICTED,
    SAFEGUARDING_LEADS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

SYSTEM = "secondary"
SOURCE = "primary"
AP_SOURCE = "alternative_provision"
#: A school place the local authority allocated (local_authority_links).
LA_SOURCE = "local_authority"
#: Systems whose pupils arrive in this queue.
SOURCES = frozenset({SOURCE, AP_SOURCE, LA_SOURCE})
SOURCE_LABELS = {SOURCE: "Primary", AP_SOURCE: "Alternative provision",
                 LA_SOURCE: "Local authority (school place)"}
PURPOSE = "transition_planning"
ENTRY_YEAR = 7
EDITORS = RESTRICTED.get("Admissions", frozenset({"admin", "superadmin"}))
SAFEGUARDING_KEY = "safeguarding_reference"

STATUS_LABELS = {"expected": "Expected", "applied": "Applied", "offered": "Offered",
                 "accepted": "Accepted", "handover_approved": "Handover ready",
                 "admitted": "Admitted", "completed": "Completed", "cancelled": "Cancelled"}
#: Steps after which the pupil is already admitted here.
ADMITTED = frozenset({"admitted", "completed"})
#: This school's own checklist items (the platform's come first).
LOCAL_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("handover_received", "Handover received and acknowledged", "admissions"),
    ("matched", "Matched to a pupil record", "admissions"),
    ("sen_to_senco", "SEN information passed to the SENCO", "admissions"),
    ("safeguarding_file", "Safeguarding file received (DSL to DSL)", "safeguarding"),
    ("ks2_imported", "KS2 data imported into prior attainment", "data manager"),
)
_LOCAL_KEYS = {k for k, _l, _o in LOCAL_ITEMS}
FIELD_LABELS = {"child_identity": "Identity", "guardians": "Parents / carers",
                "ks2_results": "KS2 results", "core_assessments": "Reading, writing, maths",
                "send_provision": "SEND provision", "support_indicators": "PP / FSM / LAC",
                "attendance_summary": "Attendance", "current_interventions": "Interventions",
                "medical_requirements": "Medical", "safeguarding_reference": "Safeguarding",
                "key_contacts": "Key contacts at primary",
                # From alternative provision
                "reintegration_plan": "Reintegration plan",
                "reintegration_support": "Support package",
                "progress_summary": "Progress at the AP", "qualifications": "Qualifications",
                "behaviour_summary": "Behaviour", "exclusion_history": "Exclusions"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incoming_primary_pupils (
    transition_id             TEXT PRIMARY KEY,
    journey_id                TEXT,
    pupil_id                  INTEGER REFERENCES pupils (pupil_id) ON DELETE SET NULL,
    application_id            INTEGER REFERENCES applications (application_id)
                              ON DELETE SET NULL,
    matched_by                TEXT,
    matched_at                TEXT,
    sen_passed_to             TEXT,
    sen_passed_by             TEXT,
    sen_passed_at             TEXT,
    safeguarding_received_by  TEXT,
    safeguarding_received_at  TEXT,
    ks2_imported_by           TEXT,
    ks2_imported_at           TEXT,
    notes                     TEXT,
    created_at                TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_incoming_primary_pupil ON incoming_primary_pupils (pupil_id);
CREATE TABLE IF NOT EXISTS incoming_primary_audit (
    audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    transition_id  TEXT,
    pupil_id       INTEGER,
    action         TEXT NOT NULL,
    detail         TEXT,
    actor          TEXT NOT NULL,
    at             TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_incoming_primary_audit ON incoming_primary_audit (transition_id);
"""
database.register_schema("incoming_primary", _SCHEMA)


def _T():
    from education_system.platform.cross_system import transitions
    return transitions


def _ID():
    from education_system.platform.cross_system import identity_service
    return identity_service


def _HM():
    from education_system.systems.secondary.modules.assessment.domain import headline_measures
    return headline_measures


@dataclass(frozen=True)
class Incoming:
    transition_id: str
    journey_id: str
    status: str
    decision: str | None
    reason: str | None
    effective_date: str | None
    initiated_at: str | None
    handover_ready: bool
    acknowledged_at: str | None
    acknowledged_by: str | None
    first_name: str
    last_name: str
    date_of_birth: str | None
    upn: str | None
    pupil_id: int | None = None
    application_id: int | None = None
    local: dict[str, Any] = field(default_factory=dict)
    source: str = SOURCE

    @property
    def from_ap(self) -> bool:
        return self.source == AP_SOURCE

    @property
    def from_la(self) -> bool:
        return self.source == LA_SOURCE

    @property
    def tag(self) -> str:
        """" (from AP)" / " (from LA)" after the name in the queue."""
        return " (from AP)" if self.from_ap else " (from LA)" if self.from_la else ""

    @property
    def source_label(self) -> str:
        return SOURCE_LABELS.get(self.source, self.source)

    @property
    def name(self) -> str:
        return f"{self.last_name}, {self.first_name}".strip(", ") or self.journey_id

    @property
    def status_label(self) -> str:
        if self.status == "cancelled" and self.decision == "rejected":
            return "Rejected"
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def is_open(self) -> bool:
        return self.status not in ("completed", "cancelled")

    @property
    def admitted(self) -> bool:
        return self.status in ADMITTED


@dataclass
class Outcome:
    item: Incoming
    pupil: P.Pupil | None = None
    notes: list[str] = field(default_factory=list)


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in EDITORS


def is_safeguarding_lead(actor: Principal) -> bool:
    return actor.role in SAFEGUARDING_LEADS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"incoming.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see incoming pupils.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the admissions office can do that.")


def _platform_actor(actor: Principal) -> int | str:
    return actor.user_id if isinstance(actor.user_id, int) else (actor.username or "unknown")


def _audit(conn, action: str, actor: Principal, transition_id: str | None,
           pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO incoming_primary_audit (transition_id, pupil_id, action, detail, "
                 "actor) VALUES (?, ?, ?, ?, ?)",
                 (transition_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(transition_id: str | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM incoming_primary_audit", []
    if transition_id:
        sql += " WHERE transition_id = ?"
        params.append(transition_id)
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                            (*params, int(limit))).fetchall()
    return [{"at": r["at"], "transition_id": r["transition_id"], "pupil_id": r["pupil_id"],
             "action": r["action"], "actor": r["actor"],
             "detail": json.loads(r["detail"] or "{}")} for r in rows]


# ── Reading the queue ────────────────────────────────────────────────

def _local(transition_id: str) -> dict[str, Any]:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM incoming_primary_pupils WHERE transition_id = ?",
                         (transition_id,)).fetchone()
    return dict(r) if r else {}


def _ensure_local(conn, transition_id: str, journey_id: str) -> None:
    conn.execute("INSERT OR IGNORE INTO incoming_primary_pupils (transition_id, journey_id) "
                 "VALUES (?, ?)", (transition_id, journey_id))


def register_arrival(transition_id: str, journey_id: str) -> None:
    """Start this school's record of an incoming pupil (idempotent). For
    the adapter's ``create_applicant`` hook; the screens call it too."""
    with database.connect() as conn:
        _ensure_local(conn, transition_id, journey_id)


def _item(row: dict[str, Any], local: dict[str, Any] | None = None, *,
          db_path: str | None = None) -> Incoming:
    try:
        j = _ID().get(row["journey_id"], db_path=db_path) or {}
    except Exception:  # noqa: BLE001
        j = {}
    loc = local if local is not None else _local(row["transition_id"])
    return Incoming(
        row["transition_id"], row["journey_id"], row["status"], row.get("decision"),
        row.get("decision_reason") or row.get("cancelled_reason"), row.get("effective_date"),
        row.get("initiated_at"), bool(row.get("handover_json")), row.get("acknowledged_at"),
        row.get("acknowledged_by"), j.get("legal_first_name") or "",
        j.get("legal_last_name") or "", j.get("date_of_birth"), j.get("upn"),
        loc.get("pupil_id"), loc.get("application_id"), loc,
        row.get("source_system") or SOURCE)


def _rows(include_closed: bool, db_path: str | None) -> list[dict[str, Any]]:
    T = _T()
    rows = T.pending_transitions(SYSTEM, db_path=db_path)
    if include_closed:
        for status in ("completed", "cancelled"):
            rows += T.pending_transitions(SYSTEM, status=status, db_path=db_path)
    return [r for r in rows if (r.get("source_system") or "") in SOURCES]


def queue(*, actor: Principal, include_closed: bool = False, status: str | None = None,
          search: str | None = None, db_path: str | None = None) -> list[Incoming]:
    """Transfers from primary addressed to this school, oldest first."""
    _require_staff(actor, "view")
    with database.connect() as conn:
        locals_ = {r["transition_id"]: dict(r) for r in conn.execute(
            "SELECT * FROM incoming_primary_pupils")}
    items = [_item(r, locals_.get(r["transition_id"], {}), db_path=db_path)
             for r in _rows(include_closed or (status or "").lower() in (
                 "completed", "cancelled", "rejected"), db_path)]
    if status:
        items = [i for i in items if status.lower() in (i.status, i.status_label.lower())]
    for term in (search or "").lower().split():
        items = [i for i in items if term in f"{i.first_name} {i.last_name} {i.upn or ''}"
                 .lower()]
    activity_log.record("incoming.view", principal=actor, shown=len(items))
    return items


def get(transition_id: str, *, actor: Principal, db_path: str | None = None) -> Incoming:
    _require_staff(actor, "view", transition_id)
    row = _T().get_transition(transition_id, db_path=db_path)
    if row is None or row["destination_system"] != SYSTEM or \
            (row.get("source_system") or "") not in SOURCES:
        raise NotFound(f"No incoming transfer {transition_id}")
    return _item(row, db_path=db_path)


def counts(*, actor: Principal, db_path: str | None = None) -> dict[str, int]:
    items = queue(actor=actor, include_closed=True, db_path=db_path)
    out: dict[str, int] = {}
    for i in items:
        out[i.status_label] = out.get(i.status_label, 0) + 1
    out["To match"] = sum(1 for i in items if i.is_open and i.handover_ready
                          and i.pupil_id is None)
    out["Not acknowledged"] = sum(1 for i in items if i.is_open and i.handover_ready
                                  and not i.acknowledged_at)
    return out


# ── The handover ─────────────────────────────────────────────────────

def handover(transition_id: str, *, actor: Principal, db_path: str | None = None
             ) -> dict[str, Any] | None:
    """The handover as *actor* may see it (None until primary approves it).

    ``payload`` holds the visible fields; ``withheld`` the ones the
    platform kept back for this role. The safeguarding pointer is removed
    for anyone but a safeguarding lead, and ``safeguarding`` says (to a
    lead only) whether a safeguarding file exists."""
    item = get(transition_id, actor=actor, db_path=db_path)
    T = _T()
    try:
        out = T.get_handover_for(transition_id, viewer_role=(actor.role or "unknown"),
                                 viewer_system=SYSTEM, purpose=PURPOSE,
                                 viewer_id=_platform_actor(actor), db_path=db_path)
    except PermissionError as e:
        _deny(actor, "handover", transition_id, str(e))
        return None
    if out is None:
        return None
    payload = dict(out["payload"])
    withheld = [k for k in out["withheld"] if k != SAFEGUARDING_KEY]
    lead = is_safeguarding_lead(actor)
    exists = SAFEGUARDING_KEY in payload or SAFEGUARDING_KEY in out["withheld"]
    reference = payload.pop(SAFEGUARDING_KEY, None)
    out = {**out, "payload": payload, "withheld": withheld,
           "released": sorted(payload), "name": item.name,
           "safeguarding": ({"exists": exists, "reference": reference} if lead else None)}
    activity_log.record("incoming.handover", target=transition_id, principal=actor,
                        fields=len(payload), withheld=len(withheld))
    return out


def _fmt(value: Any, indent: str = "    ") -> list[str]:
    if isinstance(value, dict):
        return [f"{indent}{k}: {v}" for k, v in value.items() if v not in (None, "", [], {})]
    if isinstance(value, list):
        out = []
        for v in value:
            out += _fmt(v, indent) if isinstance(v, dict) else [f"{indent}- {v}"]
            if isinstance(v, dict):
                out.append("")
        return out
    return [f"{indent}{value}"]


def handover_text(h: dict[str, Any] | None) -> str:
    if h is None:
        return "Primary hasn't approved the handover yet."
    lines = [f"Handover for {h.get('name', '')} (from {h['source_system']})"]
    for key, value in h["payload"].items():
        if value in (None, "", [], {}):
            continue
        lines.append(f"\n  {FIELD_LABELS.get(key, key.replace('_', ' ').title())}:")
        lines += _fmt(value)
    if h["withheld"]:
        lines.append("\n  Not shown to your role: " + ", ".join(
            FIELD_LABELS.get(k, k) for k in h["withheld"]))
    sg = h.get("safeguarding")
    if sg is not None:
        lines.append("\n  Safeguarding: " + (
            ("a safeguarding file exists" + (f" (ref {sg['reference']})" if sg["reference"]
                                             else " - request it DSL to DSL"))
            if sg["exists"] else "no safeguarding file flagged"))
    return "\n".join(lines)


# ── Acknowledge / reject / complete ──────────────────────────────────

def acknowledge(transition_id: str, *, actor: Principal, note: str | None = None,
                db_path: str | None = None) -> Incoming:
    """Tell primary the handover arrived (ticks "documents received")."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "acknowledge", transition_id)
    T = _T()
    try:
        T.acknowledge(transition_id, actor_user_id=_platform_actor(actor),
                      note=(note or "").strip() or None, db_path=db_path)
    except T.TransitionError as e:
        raise ValidationError([str(e)]) from None
    with database.connect() as conn:
        _ensure_local(conn, transition_id, item.journey_id)
        _audit(conn, "acknowledge", actor, transition_id, item.pupil_id)
    activity_log.record("incoming.acknowledge", target=transition_id, principal=actor)
    return get(transition_id, actor=actor, db_path=db_path)


def reject(transition_id: str, *, actor: Principal, reason: str,
           db_path: str | None = None) -> Incoming:
    """This school won't take the pupil: a reason is required; primary is told."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "reject", transition_id)
    why = " ".join(str(reason or "").split())
    if not why:
        raise ValidationError(["Give the reason for rejecting the transfer"])
    if item.pupil_id is not None:
        raise ValidationError(["The pupil is already matched to a record here - unmatch "
                               "them first"])
    T = _T()
    try:
        T.reject(transition_id, reason=why[:500], actor_user_id=_platform_actor(actor),
                 db_path=db_path)
    except T.TransitionError as e:
        raise ValidationError([str(e)]) from None
    with database.connect() as conn:
        _ensure_local(conn, transition_id, item.journey_id)
        _audit(conn, "reject", actor, transition_id, reason=why[:500])
    activity_log.record("incoming.reject", target=transition_id, principal=actor)
    return get(transition_id, actor=actor, db_path=db_path)


def complete(transition_id: str, *, actor: Principal, start_date: str | None = None,
             db_path: str | None = None) -> Incoming:
    """The pupil has started here: close the transfer on the platform."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "complete", transition_id)
    problems = []
    if item.pupil_id is None:
        problems.append("Match the pupil to a record here first")
    else:
        p = P.get_pupil(item.pupil_id)
        if p is None or p.roll_status != "on_roll":
            problems.append("The matched pupil isn't on roll")
    if item.status != "admitted":
        problems.append(f"The transfer is {item.status_label.lower()} - only an admitted "
                        "pupil's transfer can be completed")
    if problems:
        raise ValidationError(problems)
    T = _T()
    try:
        # A place from the local authority: the authority keeps its record.
        T.complete(transition_id, start_date=start_date or None,
                   close_source=not item.from_la,
                   actor_user_id=_platform_actor(actor), db_path=db_path)
    except T.TransitionError as e:
        raise ValidationError([str(e)]) from None
    with database.connect() as conn:
        _audit(conn, "complete", actor, transition_id, item.pupil_id)
    activity_log.record("incoming.complete", target=transition_id, principal=actor)
    return get(transition_id, actor=actor, db_path=db_path)


# ── Matching ─────────────────────────────────────────────────────────

def _gender(value: Any) -> str:
    """Primary's gender as this school records it (one of ``P.GENDERS``), or ""."""
    t = " ".join(str(value or "").split()).lower()
    if t in ("f", "female", "girl"):
        return "Female"
    if t in ("m", "male", "boy"):
        return "Male"
    return next((g for g in P.GENDERS if g.lower() == t), "")


def _identity_from(item: Incoming, h: dict[str, Any] | None) -> dict[str, Any]:
    ident = ((h or {}).get("payload") or {}).get("child_identity") or {}
    if not isinstance(ident, dict):
        ident = {}
    return {"first_name": ident.get("first_name") or item.first_name,
            "last_name": ident.get("last_name") or item.last_name,
            "middle_names": ident.get("middle_names"),
            "preferred_name": ident.get("preferred_name"),
            "date_of_birth": ident.get("date_of_birth") or item.date_of_birth,
            "upn": ident.get("upn") or item.upn,
            "gender": _gender(ident.get("gender")),
            "address_line1": ident.get("address_line1"),
            "address_line2": ident.get("address_line2"),
            "town": ident.get("town"),
            "postcode": ident.get("postcode"),
            "school_name": ident.get("school_name")}


def _same(a: Any, b: Any) -> bool:
    return " ".join(str(a or "").lower().split()) == " ".join(str(b or "").lower().split())


def match_candidates(transition_id: str, *, actor: Principal, db_path: str | None = None
                     ) -> list[dict[str, Any]]:
    """Admissions applications and pupil records that may be this pupil,
    best first: ``{kind, id, label, reason, score}``."""
    item = get(transition_id, actor=actor, db_path=db_path)
    who = _identity_from(item, None)
    out: list[dict[str, Any]] = []
    upn = (who["upn"] or "").replace(" ", "").upper()
    for p in P.list_pupils(roll_status=None, search=who["last_name"] or None):
        reasons, score = [], 0
        if upn and (p.upn or "") == upn:
            reasons.append("same UPN")
            score += 100
        if _same(p.legal_last_name, who["last_name"]) and p.date_of_birth == \
                who["date_of_birth"]:
            if _same(p.legal_first_name, who["first_name"]):
                reasons.append("same name and date of birth")
                score += 90
            else:
                reasons.append("same surname and date of birth")
                score += 50
        if score:
            out.append({"kind": "pupil", "id": p.pupil_id, "score": score,
                        "reason": ", ".join(reasons),
                        "label": f"{p.display_name} ({p.admission_no}), Year {p.year_group}, "
                                 f"{p.roll_status_label}"})
    if is_editor(actor) and not item.from_ap:   # Year 7 applications: primary only
        for a in AD.list_applications(year_group=ENTRY_YEAR, search=who["last_name"] or None):
            if a.date_of_birth != who["date_of_birth"]:
                continue
            same_first = _same(a.legal_first_name, who["first_name"])
            out.append({"kind": "application", "id": a.application_id,
                        "score": 85 if same_first else 45,
                        "reason": "same name and date of birth" if same_first
                        else "same surname and date of birth",
                        "label": f"{a.reference} {a.child_name} ({a.academic_year}, "
                                 f"{a.status_label})"})
    return sorted(out, key=lambda c: -c["score"])


def _attach(item: Incoming, pupil: P.Pupil, actor: Principal, *, how: str,
            application_id: int | None = None, db_path: str | None = None) -> list[str]:
    """Record the match here, admit on the platform and link the journey."""
    notes: list[str] = []
    with database.connect() as conn:
        _ensure_local(conn, item.transition_id, item.journey_id)
        other = conn.execute("SELECT transition_id FROM incoming_primary_pupils WHERE "
                             "pupil_id = ? AND transition_id != ?",
                             (pupil.pupil_id, item.transition_id)).fetchone()
        if other:
            raise ValidationError([f"{pupil.display_name} is already matched to another "
                                   "incoming transfer"])
        conn.execute("UPDATE incoming_primary_pupils SET pupil_id = ?, application_id = "
                     "COALESCE(?, application_id), matched_by = ?, matched_at = datetime('now'),"
                     " updated_at = datetime('now') WHERE transition_id = ?",
                     (pupil.pupil_id, application_id, actor.username, item.transition_id))
        _audit(conn, "match", actor, item.transition_id, pupil.pupil_id, how=how,
               application=application_id)
    T = _T()
    if item.status not in ADMITTED:
        try:
            T.admit(item.transition_id, local_student_id=str(pupil.pupil_id),
                    year_group=str(pupil.year_group), start_date=pupil.admission_date,
                    actor_user_id=_platform_actor(actor), db_path=db_path)
            notes.append("the platform has the pupil as admitted here")
        except T.TransitionError as e:
            notes.append(f"the platform couldn't record the admission: {e}")
    try:
        _ID().link_system(item.journey_id, SYSTEM, student_id=str(pupil.pupil_id),
                          db_path=db_path)
        notes.append("the pupil's learner journey now includes this school")
    except Exception as e:  # noqa: BLE001 - the match stands; the link can be redone
        notes.append(f"the learner journey couldn't be linked ({e})")
    activity_log.record("incoming.match", target=pupil.admission_no, principal=actor, how=how)
    return notes


def match_pupil(transition_id: str, pupil_id: int, *, actor: Principal,
                db_path: str | None = None) -> Outcome:
    """Match the incoming pupil to an existing pupil record."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "match", transition_id)
    if actor.role not in PUPIL_EDITORS:
        _deny(actor, "match", transition_id, "Your account can't change pupil records.")
    if item.status == "cancelled":
        raise ValidationError(["This transfer was rejected or cancelled"])
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil {pupil_id}")
    problems = []
    if item.date_of_birth and p.date_of_birth != item.date_of_birth:
        problems.append(f"{p.display_name}'s date of birth ({p.date_of_birth}) isn't the "
                        f"incoming pupil's ({item.date_of_birth})")
    if item.pupil_id not in (None, p.pupil_id):
        problems.append("This transfer is already matched to another pupil - unmatch first")
    if problems:
        raise ValidationError(problems)
    notes = _attach(item, p, actor, how="pupil", db_path=db_path)
    return Outcome(get(transition_id, actor=actor, db_path=db_path), p, notes)


def match_application(transition_id: str, application_id: int, *, actor: Principal,
                      db_path: str | None = None) -> Outcome:
    """Match to an admissions application. If it has been admitted, the
    pupil it created is matched too; otherwise the link waits for admission
    (:func:`refresh_matches`)."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "match", transition_id)
    a = AD.get_application(int(application_id))
    if a is None:
        raise NotFound(f"No application {application_id}")
    if item.date_of_birth and a.date_of_birth != item.date_of_birth:
        raise ValidationError([f"{a.reference}'s date of birth ({a.date_of_birth}) isn't the "
                               f"incoming pupil's ({item.date_of_birth})"])
    if item.status == "cancelled":
        raise ValidationError(["This transfer was rejected or cancelled"])
    notes: list[str] = []
    if a.admitted_pupil_id:
        p = P.get_pupil(a.admitted_pupil_id)
        if p is not None:
            notes = _attach(item, p, actor, how="application", application_id=a.application_id,
                            db_path=db_path)
            return Outcome(get(transition_id, actor=actor, db_path=db_path), p, notes)
    with database.connect() as conn:
        _ensure_local(conn, transition_id, item.journey_id)
        conn.execute("UPDATE incoming_primary_pupils SET application_id = ?, "
                     "updated_at = datetime('now') WHERE transition_id = ?",
                     (a.application_id, transition_id))
        _audit(conn, "match_application", actor, transition_id, application=a.application_id)
    activity_log.record("incoming.match_application", target=a.reference, principal=actor)
    notes.append(f"linked to application {a.reference} ({a.status_label}); the pupil record "
                 "is matched when the application is admitted")
    return Outcome(get(transition_id, actor=actor, db_path=db_path), None, notes)


def refresh_matches(*, actor: Principal, db_path: str | None = None) -> list[str]:
    """Match incoming pupils whose linked application has since been admitted."""
    _require_editor(actor, "refresh")
    done = []
    with database.connect() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT transition_id, application_id FROM incoming_primary_pupils WHERE "
            "pupil_id IS NULL AND application_id IS NOT NULL")]
    for r in rows:
        a = AD.get_application(r["application_id"])
        if a and a.admitted_pupil_id:
            try:
                out = match_application(r["transition_id"], a.application_id, actor=actor,
                                        db_path=db_path)
                if out.pupil:
                    done.append(out.pupil.admission_no)
            except (ValidationError, NotFound):
                continue
    return done


def unmatch(transition_id: str, *, actor: Principal, reason: str,
            db_path: str | None = None) -> Incoming:
    """Undo a wrong match here (the platform's admission stays; correct the
    pupil's journey link in Student Journey if needed)."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "unmatch", transition_id)
    why = " ".join(str(reason or "").split())
    if not why:
        raise ValidationError(["Say why the match was wrong"])
    if item.pupil_id is None and item.application_id is None:
        raise ValidationError(["This transfer isn't matched"])
    with database.connect() as conn:
        conn.execute("UPDATE incoming_primary_pupils SET pupil_id = NULL, application_id = "
                     "NULL, matched_by = NULL, matched_at = NULL, updated_at = datetime('now') "
                     "WHERE transition_id = ?", (transition_id,))
        _audit(conn, "unmatch", actor, transition_id, item.pupil_id, reason=why)
    activity_log.record("incoming.unmatch", target=transition_id, principal=actor)
    return get(transition_id, actor=actor, db_path=db_path)


def _relationship(text: Any) -> str:
    t = str(text or "").lower()
    for rel in C.RELATIONSHIPS:
        if rel.lower() in t:
            return rel
    return "Carer" if "parent" in t or not t else "Other"


def _sen_from(payload: dict[str, Any]) -> str:
    """N / K / E from the handover's SEND block: its ``sen_status`` when it
    gives one, otherwise E for an EHC plan and K for anything recorded."""
    send = payload.get("send_provision")
    if not send:
        return "N"
    if isinstance(send, dict):
        code = str(send.get("sen_status") or "").strip().upper()
        if code in P.SEN_STATUSES:
            return code
        if send.get("ehcp") is True:
            return "E"
    text = json.dumps(send, default=str).lower()
    return "E" if "ehc" in text else "K"


sen_from = _sen_from


def support_from(payload: dict[str, Any]) -> dict[str, bool]:
    """The handover's support indicators (PP, FSM, LAC, PLAC, EAL) as
    booleans; empty when the viewer's role doesn't get them."""
    s = payload.get("support_indicators")
    if not isinstance(s, dict):
        return {}
    return {k: bool(s.get(k)) for k in ("pupil_premium", "fsm", "lac", "plac", "eal")
            if k in s}


def transition_report(h: dict[str, Any] | None) -> dict[str, Any] | None:
    """The primary's transition report from a handover (None if not sent)."""
    rep = ((h or {}).get("payload") or {}).get("transition_report")
    return rep if isinstance(rep, dict) and rep else None


def new_pupil_defaults(transition_id: str, *, actor: Principal,
                       db_path: str | None = None) -> dict[str, Any]:
    """What a new pupil record would start from (for the create form)."""
    item = get(transition_id, actor=actor, db_path=db_path)
    h = handover(transition_id, actor=actor, db_path=db_path)
    who = _identity_from(item, h)
    payload = (h or {}).get("payload") or {}
    support = support_from(payload)
    start = item.effective_date or _dt.date.today().isoformat()
    year = ENTRY_YEAR
    if item.from_ap or item.from_la:   # not a Year 6 move: their own year group
        ident = payload.get("child_identity") if isinstance(payload, dict) else None
        try:
            got = int((ident or {}).get("year_group") or 0)
        except (TypeError, ValueError):
            got = 0
        year = got if got in P.YEAR_GROUPS else ENTRY_YEAR
    return {"legal_first_name": who["first_name"], "middle_names": who["middle_names"] or "",
            "legal_last_name": who["last_name"], "preferred_name": who["preferred_name"] or "",
            "date_of_birth": who["date_of_birth"] or "", "upn": who["upn"] or "",
            "gender": who["gender"] or "", "year_group": year, "form_group": "",
            "admission_date": start,
            "address_line1": who["address_line1"] or "",
            "address_line2": who["address_line2"] or "",
            "town": who["town"] or "", "postcode": who["postcode"] or "",
            "sen_status": _sen_from(payload),
            "fsm_eligible": bool(support.get("fsm")), "eal": bool(support.get("eal"))}


def create_pupil(transition_id: str, data: dict[str, Any] | None = None, *,
                 actor: Principal, allow_duplicate: bool = False,
                 db_path: str | None = None) -> Outcome:
    """Create the pupil's record from the handover (*data* overrides it -
    gender, form, admission date...), add the parents as contacts, then
    match. Raises :class:`pupils.DuplicatePupil` if one already exists."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "create", transition_id)
    if not actor.can_edit_pupils:
        _deny(actor, "create", transition_id, "Your account can't create pupil records.")
    if item.status == "cancelled":
        raise ValidationError(["This transfer was rejected or cancelled"])
    if item.pupil_id is not None:
        raise ValidationError(["This transfer is already matched to a pupil"])
    base = new_pupil_defaults(transition_id, actor=actor, db_path=db_path)
    base.update({k: v for k, v in (data or {}).items() if k in P.EDITABLE_FIELDS})
    fields = {k: v for k, v in base.items() if k in P.EDITABLE_FIELDS and v not in (None, "")}
    fields["notes"] = (str(fields.get("notes") or "") +
                       f" Joined from {item.source_label.lower()} through the platform "
                       "transfer.").strip()
    pupil = P.create_pupil(fields, actor=actor, allow_duplicate=allow_duplicate)
    notes: list[str] = [f"pupil record {pupil.admission_no} created"]
    h = handover(transition_id, actor=actor, db_path=db_path)
    guardians = ((h or {}).get("payload") or {}).get("guardians") or []
    if isinstance(guardians, dict):
        guardians = [guardians]
    for n, g in enumerate(gg for gg in guardians if isinstance(gg, dict)):
        name = g.get("name") or g.get("full_name")
        if not name:
            continue
        try:
            C.add_contact(pupil.pupil_id, {
                "full_name": name, "relationship": _relationship(g.get("relationship")),
                "priority": n + 1, "email": g.get("email") or None,
                "phone": g.get("phone") or None,
                "parental_responsibility": bool(g.get("parental_responsibility", n == 0)),
                "receives_email": bool(g.get("email"))}, actor=actor)
            notes.append(f"{name} added as a contact")
        except Exception as e:  # noqa: BLE001 - the pupil stands; the contact can be added
            notes.append(f"{name} couldn't be added as a contact: {e}")
    notes += _attach(item, pupil, actor, how="created", db_path=db_path)
    return Outcome(get(transition_id, actor=actor, db_path=db_path), pupil, notes)


# ── Checklist ────────────────────────────────────────────────────────

def checklist(transition_id: str, *, actor: Principal, db_path: str | None = None
              ) -> list[dict[str, Any]]:
    """The platform's items, then this school's: ``{key, label, owner, done,
    done_by, done_at, source}``."""
    item = get(transition_id, actor=actor, db_path=db_path)
    try:
        platform = [{**i, "source": "platform"} for i in _T().get_checklist(
            transition_id, db_path=db_path)]
    except Exception:  # noqa: BLE001
        platform = []
    loc = item.local
    state = {
        "handover_received": (item.acknowledged_at, item.acknowledged_by),
        "matched": (loc.get("matched_at") if item.pupil_id else None, loc.get("matched_by")),
        "sen_to_senco": (loc.get("sen_passed_at"), loc.get("sen_passed_by")),
        "safeguarding_file": (loc.get("safeguarding_received_at"),
                              loc.get("safeguarding_received_by")),
        "ks2_imported": (loc.get("ks2_imported_at"), loc.get("ks2_imported_by")),
    }
    mine = []
    for key, label, owner in LOCAL_ITEMS:
        if key == "safeguarding_file" and not is_safeguarding_lead(actor):
            continue
        at, by = state[key]
        if key == "sen_to_senco" and loc.get("sen_passed_to") and at:
            label = f"{label} ({loc['sen_passed_to']})"
        mine.append({"key": key, "label": label, "owner": owner, "done": bool(at),
                     "done_by": by if at else None, "done_at": at, "source": "school"})
    return platform + mine


def tick(transition_id: str, key: str, *, actor: Principal, done: bool = True,
         note: str | None = None, db_path: str | None = None) -> list[dict[str, Any]]:
    """Tick (or untick) one item. The platform's items go to the platform;
    "handover received" acknowledges; "matched" and "KS2 imported" are
    ticked by doing them."""
    item = get(transition_id, actor=actor, db_path=db_path)
    if key == "safeguarding_file":
        return record_safeguarding_file(transition_id, actor=actor, done=done,
                                        db_path=db_path)
    _require_editor(actor, "tick", transition_id)
    if key == "handover_received":
        if not done:
            raise ValidationError(["An acknowledgement can't be taken back"])
        acknowledge(transition_id, actor=actor, note=note, db_path=db_path)
    elif key in ("matched", "ks2_imported"):
        raise ValidationError(["That is ticked by doing it: "
                               + ("match or create the pupil" if key == "matched"
                                  else "Import KS2")])
    elif key == "sen_to_senco":
        pass_sen_to_senco(transition_id, to=note or "", actor=actor, done=done,
                          db_path=db_path)
    else:
        T = _T()
        try:
            T.tick_checklist_item(transition_id, key, actor_user_id=_platform_actor(actor),
                                  done=done, note=note, db_path=db_path)
        except T.TransitionError as e:
            raise ValidationError([str(e)]) from None
        with database.connect() as conn:
            _ensure_local(conn, transition_id, item.journey_id)
            _audit(conn, "tick", actor, transition_id, item.pupil_id, item=key, done=done)
        activity_log.record("incoming.tick", target=transition_id, principal=actor, item=key)
    return checklist(transition_id, actor=actor, db_path=db_path)


def pass_sen_to_senco(transition_id: str, *, to: str, actor: Principal, done: bool = True,
                      db_path: str | None = None) -> list[dict[str, Any]]:
    """Record that the SEN information went to the SENCO (who, when)."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "sen", transition_id)
    who = " ".join(str(to or "").split())[:100]
    if done and not who:
        raise ValidationError(["Say who it was passed to (the SENCO's name)"])
    with database.connect() as conn:
        _ensure_local(conn, transition_id, item.journey_id)
        conn.execute("UPDATE incoming_primary_pupils SET sen_passed_to = ?, sen_passed_by = ?, "
                     "sen_passed_at = ?, updated_at = datetime('now') WHERE transition_id = ?",
                     (who or None, actor.username if done else None,
                      _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if done else None,
                      transition_id))
        _audit(conn, "sen_to_senco", actor, transition_id, item.pupil_id, done=done)
    activity_log.record("incoming.sen_to_senco", target=transition_id, principal=actor)
    return checklist(transition_id, actor=actor, db_path=db_path)


def record_safeguarding_file(transition_id: str, *, actor: Principal, done: bool = True,
                             db_path: str | None = None) -> list[dict[str, Any]]:
    """The DSL records that the safeguarding file arrived (DSL to DSL)."""
    item = get(transition_id, actor=actor, db_path=db_path)
    if not is_safeguarding_lead(actor):
        _deny(actor, "safeguarding", transition_id,
              "Only the designated safeguarding lead can record the safeguarding file.")
    with database.connect() as conn:
        _ensure_local(conn, transition_id, item.journey_id)
        conn.execute("UPDATE incoming_primary_pupils SET safeguarding_received_by = ?, "
                     "safeguarding_received_at = ?, updated_at = datetime('now') "
                     "WHERE transition_id = ?",
                     (actor.username if done else None,
                      _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S") if done else None,
                      transition_id))
        _audit(conn, "safeguarding_file", actor, transition_id, item.pupil_id, done=done)
    activity_log.record("incoming.safeguarding_file", target=transition_id, principal=actor)
    return checklist(transition_id, actor=actor, db_path=db_path)


# ── KS2 into prior attainment ────────────────────────────────────────

_READING_KEYS = ("reading_scaled", "reading_scaled_score", "reading", "ks2_reading")
_MATHS_KEYS = ("maths_scaled", "maths_scaled_score", "maths", "mathematics", "ks2_maths")


def _score(block: Any, keys: tuple[str, ...]) -> Any:
    if not isinstance(block, dict):
        return None
    for k in keys:
        v = block.get(k)
        if isinstance(v, dict):
            v = v.get("scaled_score") or v.get("scaled") or v.get("score")
        if v not in (None, ""):
            return v
    return None


def ks2_scores(h: dict[str, Any] | None) -> dict[str, Any]:
    """Reading and maths scaled scores from the handover's KS2 results
    (a dict, or a list of ``{subject, scaled_score}``)."""
    ks2 = ((h or {}).get("payload") or {}).get("ks2_results")
    if isinstance(ks2, list):
        flat: dict[str, Any] = {}
        for row in ks2:
            if isinstance(row, dict):
                subj = str(row.get("subject") or "").lower()
                val = row.get("scaled_score") or row.get("score") or row.get("result")
                if "read" in subj:
                    flat["reading_scaled"] = val
                elif "math" in subj:
                    flat["maths_scaled"] = val
        ks2 = flat
    return {"reading_scaled": _score(ks2, _READING_KEYS),
            "maths_scaled": _score(ks2, _MATHS_KEYS)}


def import_ks2(transition_id: str, *, actor: Principal, db_path: str | None = None):
    """Put the handover's KS2 scaled scores into the pupil's prior
    attainment (``headline_measures.set_ks2``, source "Primary school")."""
    item = get(transition_id, actor=actor, db_path=db_path)
    _require_editor(actor, "ks2", transition_id)
    if item.pupil_id is None:
        raise ValidationError(["Match the pupil to a record here first"])
    scores = ks2_scores(handover(transition_id, actor=actor, db_path=db_path))
    if scores["reading_scaled"] is None and scores["maths_scaled"] is None:
        raise ValidationError(["The handover has no KS2 reading or maths scaled scores"])
    HM = _HM()
    ks2 = HM.set_ks2(item.pupil_id, {**scores, "source": "Primary school",
                                     "notes": "From the primary handover"}, actor=actor)
    with database.connect() as conn:
        conn.execute("UPDATE incoming_primary_pupils SET ks2_imported_by = ?, ks2_imported_at = "
                     "datetime('now'), updated_at = datetime('now') WHERE transition_id = ?",
                     (actor.username, transition_id))
        _audit(conn, "ks2_import", actor, transition_id, item.pupil_id)
    activity_log.record("incoming.ks2_import", target=transition_id, principal=actor)
    return ks2


# ── Step log ─────────────────────────────────────────────────────────

def step_log(transition_id: str, *, actor: Principal, db_path: str | None = None
             ) -> list[dict[str, Any]]:
    """The platform's transfer events and this school's steps, oldest first:
    ``{at, who, step, note, source}``."""
    get(transition_id, actor=actor, db_path=db_path)
    out = []
    try:
        for e in _T().list_transition_events(transition_id, db_path=db_path):
            note = e.get("note") or ""
            if e.get("released_fields"):
                note = (note + " released: " + ", ".join(e["released_fields"])).strip()
            out.append({"at": e.get("at") or "", "who": e.get("actor") or "",
                        "step": e.get("step") or "", "note": note, "source": "platform"})
    except Exception:  # noqa: BLE001
        pass
    for h in history(transition_id):
        out.append({"at": h["at"], "who": h["actor"], "step": h["action"],
                    "note": ", ".join(f"{k}={v}" for k, v in h["detail"].items()),
                    "source": "school"})
    return sorted(out, key=lambda r: r["at"])


# ── Export ───────────────────────────────────────────────────────────

def export_csv(path: str | Path, *, actor: Principal, include_closed: bool = True,
               db_path: str | None = None) -> int:
    rows = queue(actor=actor, include_closed=include_closed, db_path=db_path)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["transition", "surname", "first name", "date of birth", "upn", "status",
                    "starts", "acknowledged", "pupil", "application", "sen to senco",
                    "ks2 imported"])
        for i in rows:
            p = P.get_pupil(i.pupil_id) if i.pupil_id else None
            w.writerow([i.transition_id, _safe(i.last_name), _safe(i.first_name),
                        i.date_of_birth or "", _safe(i.upn), i.status_label,
                        i.effective_date or "", (i.acknowledged_at or "")[:10],
                        p.admission_no if p else "", i.application_id or "",
                        (i.local.get("sen_passed_at") or "")[:10],
                        (i.local.get("ks2_imported_at") or "")[:10]])
    activity_log.record("incoming.export", principal=actor, rows=len(rows))
    return len(rows)
