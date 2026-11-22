"""A pupil's linked learner record across the seven systems.

Every learner has one ``journey_id`` in the platform's identity registry
(``platform.cross_system.identity_service``); each system links its own
record into the journey. This module reads, for one secondary pupil:

* the **journey id** - found from this school's link (the pupil id in the
  ``secondary`` slot or the enrolment history). A pupil not linked yet is
  shown with the journeys that *might* be theirs (same UPN, or the same
  name and date of birth) for an administrator to link or register;
* **which systems hold a record** - primary, secondary, sixth form, FE
  college, apprenticeships, university (and nursery), from the journey's
  slots and enrolment history, in phase order;
* the **Learner 360** - ``learner_360.build_learner_360``, tiered by the
  viewer's role (staff see everything but safeguarding detail; only a
  safeguarding role sees that alerts exist; any role the platform doesn't
  know gets the narrowest view - this module never passes "no role", which
  would mean a trusted internal caller);
* **transfers in and out** with their status (``transitions``);
* **possible duplicates** of the journey (``find_duplicate_candidates``)
  for the data manager to review: link (merge) or mark as different people.

Nothing here imports another system: everything goes through the
platform's linked-platform layer. Reading is for staff; linking, merging
and dismissing duplicates are for :data:`access.DATA_MANAGERS`. Every
change is in ``student_journey_audit`` and the activity log (ids only), and
the platform writes its own audit for merges.

``db_path`` (the platform's auth.db) and ``db_paths`` (each system's
database) can be given for tests; by default the platform's own are used.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.paths import SYSTEM_LABELS, SYSTEM_ORDER
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    DATA_MANAGERS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

SYSTEM = "secondary"
#: The phase order shown on the journey strip.
PHASES: tuple[str, ...] = tuple(SYSTEM_ORDER)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS student_journey_audit (
    audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    pupil_id    INTEGER,
    journey_id  TEXT,
    action      TEXT NOT NULL,
    detail      TEXT,
    actor       TEXT NOT NULL,
    at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_student_journey_audit_pupil ON student_journey_audit (pupil_id);
"""
database.register_schema("student_journey", _SCHEMA)


def _identity():
    from education_system.platform.cross_system import identity_service
    return identity_service


def _transitions():
    from education_system.platform.cross_system import transitions
    return transitions


def _learner_360():
    from education_system.platform.cross_system import learner_360
    return learner_360


@dataclass(frozen=True)
class SystemRecord:
    system: str
    label: str
    student_ids: tuple[str, ...]
    current: bool
    statuses: tuple[str, ...] = ()

    @property
    def held(self) -> bool:
        return bool(self.student_ids)


@dataclass(frozen=True)
class Transfer:
    transition_id: str
    direction: str          # "in", "out" or "other"
    source_system: str | None
    destination_system: str
    status: str
    decision: str | None
    effective_date: str | None
    initiated_at: str | None
    reason: str | None

    @property
    def label(self) -> str:
        return (f"{SYSTEM_LABELS.get(self.source_system or '', self.source_system or '?')} -> "
                f"{SYSTEM_LABELS.get(self.destination_system, self.destination_system)}")


@dataclass
class Journey:
    pupil: P.Pupil
    journey_id: str | None
    journey: dict[str, Any] | None
    systems: list[SystemRecord] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def linked(self) -> bool:
        return self.journey_id is not None

    @property
    def held_in(self) -> list[str]:
        return [s.label for s in self.systems if s.held]


# ── Who may do what ──────────────────────────────────────────────────

def is_data_manager(actor: Principal) -> bool:
    return actor.role in DATA_MANAGERS


def viewer_role(actor: Principal) -> str:
    """The role the platform tiers the view by. Never None (None means a
    trusted platform caller and would show everything): no role becomes
    "unknown", which the platform treats as the narrowest view."""
    return (actor.role or "").strip().lower() or "unknown"


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"journey.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can see a pupil's learner journey.")


def _require_manager(actor: Principal, action: str, target: Any = None) -> None:
    if not is_data_manager(actor):
        _deny(actor, action, target, "Only the data manager can link, merge or dismiss "
                                     "learner records.")


def _audit(action: str, actor: Principal, *, pupil_id: int | None = None,
           journey_id: str | None = None, **detail: Any) -> None:
    with database.connect() as conn:
        conn.execute("INSERT INTO student_journey_audit (pupil_id, journey_id, action, detail, "
                     "actor) VALUES (?, ?, ?, ?, ?)",
                     (pupil_id, journey_id, action,
                      json.dumps(detail, default=str) if detail else None,
                      actor.username or "unknown"))


def history(pupil_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM student_journey_audit", []
    if pupil_id is not None:
        sql += " WHERE pupil_id = ?"
        params.append(int(pupil_id))
    with database.connect() as conn:
        rows = conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                            (*params, int(limit))).fetchall()
    return [{"at": r["at"], "pupil_id": r["pupil_id"], "journey_id": r["journey_id"],
             "action": r["action"], "actor": r["actor"],
             "detail": json.loads(r["detail"] or "{}")} for r in rows]


# ── Finding the journey ──────────────────────────────────────────────

def _pupil(ref: Any) -> P.Pupil:
    p = None
    if isinstance(ref, P.Pupil):
        return ref
    if isinstance(ref, int) or str(ref).strip().isdigit():
        p = P.get_pupil(int(ref))
    if p is None and ref not in (None, ""):
        p = P.find_by_reference(str(ref))
    if p is None:
        raise NotFound(f"No pupil {ref}")
    return p


def journey_id_for(pupil_id: int, *, db_path: str | None = None) -> str | None:
    """The journey this school's record is linked to (None if not linked)."""
    try:
        row = _identity().find_by_student(SYSTEM, str(int(pupil_id)), db_path=db_path)
    except Exception:  # noqa: BLE001 - the registry unreachable reads as "not linked"
        return None
    return row["journey_id"] if row else None


def possible_journeys(pupil: P.Pupil, *, db_path: str | None = None) -> list[dict[str, Any]]:
    """Journeys that might be this pupil's (not linked yet): same UPN first,
    then the same legal name and date of birth."""
    ids = _identity()
    out: dict[str, dict[str, Any]] = {}
    try:
        if pupil.upn:
            row = ids.find_by_strong_id(upn=pupil.upn, db_path=db_path)
            if row:
                out[row["journey_id"]] = {**row, "_reason": "same UPN"}
        for row in ids.find_identity_candidates(pupil.legal_first_name, pupil.legal_last_name,
                                                pupil.date_of_birth, db_path=db_path):
            out.setdefault(row["journey_id"], {**row, "_reason": "same name and date of birth"})
    except Exception:  # noqa: BLE001
        return []
    return list(out.values())


def _systems(journey: dict[str, Any], *, db_path: str | None) -> list[SystemRecord]:
    ids = _identity()
    by: dict[str, list[str]] = {}
    statuses: dict[str, list[str]] = {}
    for system, (_pk, col) in ids.SYSTEM_SLOTS.items():
        if journey.get(col):
            by.setdefault(system, []).append(str(journey[col]))
    try:
        from education_system.platform.cross_system import enrolments
        for e in enrolments.list_enrolments(journey["journey_id"], db_path=db_path):
            sid = str(e.get("local_student_id") or "")
            if sid and sid not in by.setdefault(e["system"], []):
                by[e["system"]].append(sid)
            statuses.setdefault(e["system"], []).append(str(e.get("status") or ""))
    except Exception:  # noqa: BLE001 - slots alone still answer "where"
        pass
    order = list(PHASES) + [s for s in by if s not in PHASES]
    return [SystemRecord(s, SYSTEM_LABELS.get(s, s), tuple(by.get(s, ())),
                         journey.get("current_system") == s, tuple(statuses.get(s, ())))
            for s in order]


def journey(pupil_ref: Any, *, actor: Principal, db_path: str | None = None) -> Journey:
    """The pupil's journey id, the systems that hold them and (if not
    linked) the journeys that might be theirs."""
    p = _pupil(pupil_ref)
    _require_staff(actor, "view", p.admission_no)
    jid = journey_id_for(p.pupil_id, db_path=db_path)
    row = _identity().get(jid, db_path=db_path) if jid else None
    activity_log.record("journey.view", target=p.admission_no, principal=actor,
                        linked="yes" if jid else "no")
    if row is None:
        return Journey(p, None, None, [], possible_journeys(p, db_path=db_path))
    return Journey(p, jid, row, _systems(row, db_path=db_path), [])


def learner_view(pupil_ref: Any, *, actor: Principal, db_path: str | None = None,
                 db_paths: dict[str, Any] | None = None) -> dict[str, Any]:
    """The platform's Learner 360 for the pupil, tiered by *actor*'s role."""
    p = _pupil(pupil_ref)
    _require_staff(actor, "learner_360", p.admission_no)
    jid = journey_id_for(p.pupil_id, db_path=db_path)
    if jid is None:
        return {"found": False, "journey_id": None, "restricted_sections": []}
    view = _learner_360().build_learner_360(jid, viewer_role=viewer_role(actor),
                                            viewer_system=SYSTEM, db_paths=db_paths,
                                            auth_db=db_path)
    activity_log.record("journey.learner_360", target=p.admission_no, principal=actor,
                        tier=(view.get("viewer") or {}).get("tier"))
    return view


def learner_text(view: dict[str, Any]) -> str:
    return _learner_360().format_learner_360_text(view)


SECTION_TITLES: tuple[tuple[str, str], ...] = (
    ("overview", "Overview"), ("current_education", "Current education"),
    ("records", "Records"), ("timeline", "Timeline"), ("qualifications", "Qualifications"),
    ("attendance", "Attendance"), ("achievements", "Achievements"),
    ("progression", "Progression"), ("transfers", "Transfers"), ("documents", "Documents"),
    ("support", "Support"), ("system_access", "System access"), ("lineage", "Lineage"))


def section_titles() -> tuple[tuple[str, str], ...]:
    try:
        return tuple(_learner_360().SECTION_TITLES)
    except Exception:  # noqa: BLE001
        return SECTION_TITLES


# ── Transfers ────────────────────────────────────────────────────────

def _transfer(row: dict[str, Any]) -> Transfer:
    src, dst = row.get("source_system"), row["destination_system"]
    direction = "in" if dst == SYSTEM else "out" if src == SYSTEM else "other"
    return Transfer(row["transition_id"], direction, src, dst, row["status"],
                    row.get("decision"), row.get("effective_date"), row.get("initiated_at"),
                    row.get("reason") or row.get("cancelled_reason"))


def transfers(pupil_ref: Any, *, actor: Principal, db_path: str | None = None
              ) -> list[Transfer]:
    """Every move on the pupil's journey, oldest first, marked in / out."""
    p = _pupil(pupil_ref)
    _require_staff(actor, "transfers", p.admission_no)
    jid = journey_id_for(p.pupil_id, db_path=db_path)
    if jid is None:
        return []
    return [_transfer(r) for r in _transitions().list_transitions(jid, db_path=db_path)]


def transfer_events(transition_id: str, *, actor: Principal, db_path: str | None = None
                    ) -> list[dict[str, Any]]:
    _require_staff(actor, "transfer_events", transition_id)
    return _transitions().list_transition_events(transition_id, db_path=db_path)


# ── Duplicates (data manager) ────────────────────────────────────────

def duplicates(pupil_ref: Any | None = None, *, actor: Principal,
               db_path: str | None = None, min_score: int = 50) -> list[dict[str, Any]]:
    """Possible duplicate journeys: those involving the pupil's journey (or,
    with no pupil, the whole registry), best first."""
    _require_manager(actor, "duplicates")
    jid = None
    if pupil_ref not in (None, ""):
        p = _pupil(pupil_ref)
        jid = journey_id_for(p.pupil_id, db_path=db_path)
        if jid is None:
            return []
    rows = [c.as_dict() for c in _identity().find_duplicate_candidates(
        limit=500, min_score=min_score, db_path=db_path)]
    if jid:
        rows = [r for r in rows if jid in (r["journey_id"], r["duplicate_id"])]
    activity_log.record("journey.duplicates", principal=actor, found=len(rows))
    return rows


def _audit_db(db_path: str | None) -> str:
    """The platform audit DB beside the auth DB in use (the live one in the
    app, a scratch one in tests)."""
    from education_system.platform.identity.auth import db as auth_db
    return str(Path(db_path or auth_db.PLATFORM_AUTH_DB_FILE).with_name("audit.db"))


def merge(survivor_id: str, duplicate_id: str, *, actor: Principal, reason: str,
          force: bool = False, db_path: str | None = None,
          system_db_paths: dict[str, Any] | None = None) -> dict[str, Any]:
    """Link two journeys that are one person: *duplicate_id* folds into
    *survivor_id* (the platform repoints every record and keeps a snapshot
    for reversal). A reason is required."""
    _require_manager(actor, "merge", survivor_id)
    why = " ".join(str(reason or "").split())
    if not why:
        raise ValidationError(["Say why these are the same person"])
    ids = _identity()
    try:
        out = ids.merge_journeys(survivor_id, duplicate_id, actor=actor.username or "unknown",
                                 reason=why, force=force, db_path=db_path,
                                 audit_db_path=_audit_db(db_path),
                                 system_db_paths=system_db_paths)
    except ids.MergeError as e:
        activity_log.record("journey.merge", target=survivor_id, outcome="invalid",
                            principal=actor)
        raise ValidationError([str(e)]) from None
    _audit("merge", actor, journey_id=survivor_id, duplicate=duplicate_id, reason=why,
           force=force)
    activity_log.record("journey.merge", target=survivor_id, principal=actor,
                        duplicate=duplicate_id)
    return out


def not_duplicate(journey_a: str, journey_b: str, *, actor: Principal, reason: str = "",
                  db_path: str | None = None) -> None:
    """Record that two journeys are different people (twins, two pupils
    sharing a name and birthday) so they stop being suggested."""
    _require_manager(actor, "not_duplicate", journey_a)
    try:
        _identity().mark_not_duplicate(journey_a, journey_b, actor=actor.username or "unknown",
                                       reason=(reason or "").strip() or None, db_path=db_path)
    except ValueError as e:
        raise ValidationError([str(e)]) from None
    _audit("not_duplicate", actor, journey_id=journey_a, other=journey_b)
    activity_log.record("journey.not_duplicate", target=journey_a, principal=actor,
                        other=journey_b)


# ── Linking this school's record ─────────────────────────────────────

def link(pupil_ref: Any, journey_id: str, *, actor: Principal,
         db_path: str | None = None) -> dict[str, Any]:
    """Link the pupil to an existing journey (one of :func:`possible_journeys`)."""
    p = _pupil(pupil_ref)
    _require_manager(actor, "link", p.admission_no)
    current = journey_id_for(p.pupil_id, db_path=db_path)
    if current and current != journey_id:
        raise ValidationError([f"{p.display_name} is already linked to journey {current} - "
                               "merge the two journeys instead"])
    ids = _identity()
    row = ids.get(journey_id, db_path=db_path)
    if row is None:
        raise NotFound(f"No journey {journey_id}")
    if row.get("date_of_birth") and row["date_of_birth"] != p.date_of_birth:
        raise ValidationError([f"Journey {journey_id} has a different date of birth "
                               f"({row['date_of_birth']}) - check before linking"])
    out = ids.link_system(journey_id, SYSTEM, student_id=str(p.pupil_id), set_current=(
        p.roll_status == "on_roll"), db_path=db_path)
    _audit("link", actor, pupil_id=p.pupil_id, journey_id=journey_id)
    activity_log.record("journey.link", target=p.admission_no, principal=actor)
    return out


def register(pupil_ref: Any, *, actor: Principal, db_path: str | None = None) -> str:
    """Register the pupil in the identity registry: the platform links them
    to the journey that matches (UPN, then name and date of birth) or opens a
    new one. Returns the journey id."""
    p = _pupil(pupil_ref)
    _require_manager(actor, "register", p.admission_no)
    current = journey_id_for(p.pupil_id, db_path=db_path)
    if current:
        return current
    jid = _identity().get_or_create_journey(
        first_name=p.legal_first_name, last_name=p.legal_last_name,
        date_of_birth=p.date_of_birth, system=SYSTEM, student_id=str(p.pupil_id),
        pk=p.pupil_id, upn=p.upn, db_path=db_path)
    _audit("register", actor, pupil_id=p.pupil_id, journey_id=jid)
    activity_log.record("journey.register", target=p.admission_no, principal=actor)
    return jid


# ── Text (CLI, Save…) ────────────────────────────────────────────────

def journey_text(j: Journey) -> str:
    p = j.pupil
    lines = [f"{p.display_name} ({p.admission_no}), Year {p.year_group}, "
             f"{p.roll_status_label}", f"Journey: {j.journey_id or 'not linked'}"]
    if j.linked:
        strip = []
        for s in j.systems:
            mark = "*" if s.current else ("+" if s.held else "-")
            strip.append(f"[{mark}] {s.label}" + (f" ({', '.join(s.student_ids)})"
                                                  if s.held else ""))
        lines.append("Systems (+ holds a record, * current):")
        lines += [f"  {x}" for x in strip]
    elif j.candidates:
        lines.append("Possible journeys:")
        for c in j.candidates:
            lines.append(f"  {c['journey_id']}  {c.get('legal_first_name')} "
                         f"{c.get('legal_last_name')}  {c.get('date_of_birth')}  "
                         f"({c['_reason']})")
    return "\n".join(lines)
