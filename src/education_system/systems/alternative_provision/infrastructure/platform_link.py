"""The AP's own screens drive the platform for pupils a linked school referred.

Each function is a record type's ``after_commit`` hook: it runs once the AP
save has committed and returns lines for the person who saved (the form
shows them). If the platform call fails, the AP record still stands; the
failure becomes a notice and is logged (see ``core.records``).

* **Referrals** (from Primary / Secondary, ``transition_id`` set):
  Accepted → the school is told and the handover approved; Declined /
  Withdrawn → the school is told why.
* **Placements**: the first one going Active completes the school's
  referral - dual registration leaves the pupil on the school's roll, sole
  (single) registration has the school record a leaver.
* **Reintegration plans** going Completed hand the pupil back, as the
  plan's *Where on the platform* says: home school (dual), a new primary or
  secondary admission, or a school not on the platform.
* **Permanent exclusion from the AP**, or a pupil set to Left by hand,
  closes the AP's record on the platform.

Pupils the AP took on itself (no school on the platform) are untouched.
"""

from __future__ import annotations

from education_system.systems.alternative_provision.core import records as r
from education_system.systems.alternative_provision.infrastructure import database as db

SCHOOL_NAMES = {"primary": "Primary School", "secondary": "Secondary School"}


def _service():
    from education_system.platform.cross_system import ap_referrals
    return ap_referrals


def _pupil(learner_id: int) -> dict:
    from education_system.systems.alternative_provision.modules import learners
    return r.get(learners.LEARNERS, int(learner_id)) or {}


def _linked_referral(learner_id: int, referral_id: int | None = None) -> dict | None:
    """The placement's own referral if a school sent it, else the pupil's
    latest accepted school referral."""
    with db.connect() as conn:
        if referral_id:
            row = conn.execute("SELECT * FROM referrals WHERE id = ? AND transition_id IS "
                               "NOT NULL AND transition_id != ''", (referral_id,)).fetchone()
            if row:
                return dict(row)
        row = conn.execute(
            "SELECT * FROM referrals WHERE learner_id = ? AND transition_id IS NOT NULL AND "
            "transition_id != '' ORDER BY (status = 'Accepted') DESC, received DESC, id DESC "
            "LIMIT 1", (learner_id,)).fetchone()
    return dict(row) if row else None


def _school(row: dict) -> str:
    return SCHOOL_NAMES.get(row.get("source_system"), "The school")


# ── hooks ────────────────────────────────────────────────────────────

def referral_saved(row: dict, old: dict | None) -> list[str] | None:
    tid = row.get("transition_id")
    new, was = row.get("status"), (old or {}).get("status")
    if not tid or old is None or new == was:
        return None
    svc, school = _service(), _school(row)
    if new == "Accepted":
        svc.accept(tid, accepted_by="alternative provision",
                   consent=bool(row.get("consent_to_share")),
                   safeguarding_reference=row.get("safeguarding_ref") or None)
        return [f"{school} has been told the referral was accepted. Starting the "
                "placement completes the move."]
    if new == "Declined":
        svc.decline(tid, reason=row.get("decision_reason") or "Declined")
        return [f"{school} has been told the referral was declined, with the reason."]
    if new == "Withdrawn":
        svc.withdraw(tid, reason=row.get("decision_reason") or "Withdrawn")
        return [f"{school} has been told the referral was withdrawn."]
    return None


def placement_saved(row: dict, old: dict | None) -> list[str] | None:
    from education_system.systems.alternative_provision.modules import learners
    if row.get("status") != "Active":
        return None
    ref = _linked_referral(row["learner_id"], row.get("referral_id"))
    if ref is None:
        return None
    if (old or {}).get("status") == "Active":
        # Already active: only retry a move the school refused last time.
        from education_system.platform.cross_system import transitions
        t = transitions.get_transition(ref["transition_id"]) or {}
        if t.get("status") != "admitted":
            return None
    if ref.get("status") != "Accepted":
        return [f"{_school(ref)} referred this pupil, but the referral is "
                f"{str(ref.get('status')).lower()}: accept it on Referrals so the school "
                "is told."]
    sole = row.get("registration") == "Single registration"
    with db.connect() as conn:   # a returning pupil goes back on roll
        learners.set_status(conn, row["learner_id"], "On roll",
                            only_if=("Left", "Reintegrated"), on=row.get("start_date"),
                            actor="platform", why="placement started")
        conn.execute("UPDATE learners SET registration = ? WHERE id = ?",
                     (learners.REGISTRATION[0 if sole else 1], row["learner_id"]))
    pupil = _pupil(row["learner_id"])
    done = _service().place(ref["transition_id"], local_student_id=str(row["learner_id"]),
                            registration="sole" if sole else "dual",
                            start_date=row.get("start_date"),
                            year_group=pupil.get("year_group"))
    if done.get("status") != "completed":
        return None
    if sole:
        return [f"Placed. {_school(ref)} has recorded the pupil as a leaver (single "
                "registration)."]
    return [f"Placed. The pupil stays on the {_school(ref)} roll (dual registration)."]


_ENDINGS = ("home_school", "primary", "secondary", "left")


def reintegration_saved(row: dict, old: dict | None) -> list[str] | None:
    from education_system.systems.alternative_provision.modules import reintegration
    if row.get("status") != "Completed" or (old or {}).get("status") == "Completed":
        return None
    pupil = _pupil(row["learner_id"])
    if not pupil.get("journey_id"):
        return None
    choice = row.get("return_to") or reintegration.RETURN_TO[0]
    ending = _ENDINGS[reintegration.RETURN_TO.index(choice)] \
        if choice in reintegration.RETURN_TO else "home_school"
    ref = _linked_referral(row["learner_id"]) or {}
    plan = {k: row.get(k) for k in ("target_school", "school_contact", "readiness",
                                    "phased_start", "full_return", "transition_meeting")}
    out = _service().end_placement(
        str(row["learner_id"]), ending=ending, journey_id=pupil["journey_id"],
        reason=f"Reintegrated to {row.get('target_school') or 'school'}",
        end_date=row.get("full_return"), reintegration_plan=plan,
        consent=bool(ref.get("consent_to_share")),
        safeguarding_reference=ref.get("safeguarding_ref") or None)
    return [f"Platform: {out['note']}."]


def suspension_saved(row: dict, old: dict | None) -> list[str] | None:
    if not (row.get("kind") == "Permanent exclusion" and row.get("status") == "Confirmed"
            and (old or {}).get("status") != "Confirmed"):
        return None
    pupil = _pupil(row["learner_id"])
    if not pupil.get("journey_id"):
        return None
    out = _service().end_placement(str(pupil["id"]), ending="left",
                                   journey_id=pupil["journey_id"],
                                   reason="Permanently excluded from the AP",
                                   end_date=row.get("start_date"))
    return [f"Platform: {out['note']}."]


def pupil_saved(row: dict, old: dict | None) -> list[str] | None:
    """A linked pupil's status set by hand (the generic form)."""
    if old is None or not row.get("journey_id"):
        return None
    new, was = row.get("status"), old.get("status")
    if new == was or was not in ("On roll", "Referred"):
        return None
    svc = _service()
    if new == "Left":
        out = svc.end_placement(str(row["id"]), ending="left", journey_id=row["journey_id"],
                                reason="Left alternative provision",
                                end_date=row.get("leave_date"))
        return [f"Platform: {out['note']}."]
    if new == "Reintegrated":
        try:
            out = svc.end_placement(str(row["id"]), ending="home_school",
                                    journey_id=row["journey_id"],
                                    reason="Reintegrated to the home school",
                                    end_date=row.get("leave_date"))
        except svc.ReferralError as exc:
            return [f"Not passed to a school: {exc}. Record a reintegration plan as "
                    "Completed saying where the pupil went."]
        return [f"Platform: {out['note']}."]
    return None


__all__ = ["referral_saved", "placement_saved", "reintegration_saved", "suspension_saved",
           "pupil_saved"]
