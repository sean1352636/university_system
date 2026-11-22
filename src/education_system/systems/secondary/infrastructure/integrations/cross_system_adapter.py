"""Secondary School side of the platform transition contract.

Year 11 leavers export to the sixth form (and other post-16 destinations)
through :meth:`SecondaryAdapter.export_handover`, and the platform closes
them off roll through :meth:`SecondaryAdapter.close_enrolment` once the
destination enrols them. Closing never deletes: the pupil is recorded as a
leaver, so history and the audit trail stay.

Year 7 intake from primary arrives through :meth:`create_applicant`, which
starts this school's record of the incoming pupil (Incoming from Primary,
:mod:`incoming_primary`) - idempotent on the transition. Making the pupil
record is done on that screen, so ``create_enrolment`` only reports the
pupil matched there (and refuses until one is).

Alternative provision (``platform.cross_system.ap_referrals``): a referral
exports the extra sections the AP needs (parents, attendance, behaviour,
exclusions, SEN, medical); a sole-registered placement closes the pupil as
a leaver (Permanent exclusion, or moved to the AP); and a pupil coming
back from the AP as a new admission lands in the same incoming queue.

The local authority (``platform.cross_system.local_authority_links``): a
notification exports the same sections; a school place the authority
allocated lands in the incoming queue too; its EHC decisions arrive
through ``receive_send_update``.
"""

from __future__ import annotations

import logging
from typing import Any

from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    ApplicantResult,
    EnrolmentResult,
    ExportResult,
    HandoverRequest,
    PhaseAdapter,
)

logger = logging.getLogger(__name__)

SYSTEM_KEY = "secondary"


def _section(name: str, gather, *args):
    """One export section; a module that fails must not stop the referral."""
    try:
        return gather(*args)
    except Exception:  # noqa: BLE001
        logger.exception("Secondary export: %s section failed", name)
        return None


def _guardians(pupil_id: int):
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    out = [{"name": c.full_name, "relationship": c.relationship, "phone": c.phone,
            "email": c.email, "parental_responsibility": bool(c.parental_responsibility)}
           for c in C.list_for_pupil(pupil_id)
           if (c.relationship or "").lower() != "social worker"]
    return out or None


def _attendance(pupil_id: int):
    from education_system.systems.secondary.modules.attendance.domain import attendance as A
    s = A.pupil_summary(pupil_id)
    if not s.possible:
        return None
    return {"percent": s.attendance_pct, "sessions_possible": s.possible,
            "unauthorised": s.unauthorised, "persistent_absence": s.band in ("persistent",
                                                                              "severe"),
            "band": s.band}


def _behaviour(pupil_id: int):
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as B
    s = B.pupil_summary(pupil_id)
    if not s.get("total"):
        return None
    return {"incidents": s.get("negative"), "positive": s.get("positive"),
            "negative_points": s.get("negative_points"), "by_severity": s.get("by_severity"),
            "by_type": s.get("by_type")}


def _exclusions(pupil_id: int):
    from education_system.systems.secondary.modules.behaviour.domain import exclusions as X
    cases = X.list_cases(pupil_id=pupil_id, formal_only=True)
    return [{"type": c.case_type, "start_date": c.start_date, "end_date": c.end_date,
             "days": c.days, "reason": c.reason, "status": c.status} for c in cases] or None


def _medical(pupil_id: int):
    from education_system.systems.secondary.modules.medical.domain import medical as M
    m = M.for_pupil(pupil_id)
    conditions = [{"condition": c.condition, "severity": c.severity,
                   "what_to_do": c.what_to_do} for c in m.get("conditions") or []]
    allergies = [{"allergen": a.allergen, "severity": a.severity,
                  "anaphylaxis": bool(a.anaphylaxis)} for a in m.get("allergies") or []]
    if not conditions and not allergies:
        return None
    return {"conditions": conditions, "allergies": allergies}


def _pupil(local_student_id: str):
    from education_system.systems.secondary.modules.pupils.domain import pupils as P
    try:
        return P.get_pupil(int(str(local_student_id).strip()))
    except ValueError:
        return P.find_by_reference(str(local_student_id))


def identity_block(pupil) -> dict[str, Any]:
    """The pupil's full name and matching details."""
    return {
        "first_name": pupil.legal_first_name,
        "middle_names": pupil.middle_names,
        "last_name": pupil.legal_last_name,
        "preferred_name": pupil.preferred_name,
        "full_name": " ".join(x for x in (pupil.legal_first_name, pupil.middle_names,
                                          pupil.legal_last_name) if x),
        "date_of_birth": pupil.date_of_birth,
        "gender": pupil.gender,
        "upn": pupil.upn,
        "admission_no": pupil.admission_no,
        "secondary_pupil_id": str(pupil.pupil_id),
    }


class SecondaryAdapter(PhaseAdapter):
    """Secondary School's side of the four-method transition contract."""

    system = SYSTEM_KEY

    def export_handover(self, local_student_id: str, consent=None, *,
                        destination_system: str | None = None) -> ExportResult:
        from education_system.systems.secondary.modules.examinations.domain import gcse_results
        from education_system.systems.secondary.modules.pupils.domain import sen_details

        pupil = _pupil(local_student_id)
        if pupil is None:
            raise AdapterError(f"No secondary pupil {local_student_id}")
        identity = identity_block(pupil)
        record: dict[str, Any] = {
            "student_identity": dict(identity),
            "learner_identity": dict(identity),
        }
        results = gcse_results.handover_list(pupil.pupil_id)
        if results:
            record["gcse_results"] = results
        from education_system.systems.secondary.modules.examinations.domain import exam_results
        entries = exam_results.entries_for_handover(pupil.pupil_id)
        if entries:
            record["gcse_entries"] = entries
        sen = sen_details.handover_block(pupil)
        if sen:
            # The platform withholds this unless consent covers it.
            record["access_arrangements"] = sen
        if destination_system in ("alternative_provision", "special_education",
                                  "local_authority"):
            pid = pupil.pupil_id
            for ident in (record["student_identity"], record["learner_identity"]):
                ident["year_group"] = pupil.year_group
                ident["school_name"] = "Secondary School"
                ident.update({k: getattr(pupil, k) for k in ("address_line1", "town",
                                                            "postcode")})
            record["guardians"] = _section("guardians", _guardians, pid)
            record["attendance_summary"] = _section("attendance", _attendance, pid)
            record["behaviour_summary"] = _section("behaviour", _behaviour, pid)
            record["exclusion_history"] = _section("exclusions", _exclusions, pid)
            record["medical_requirements"] = _section("medical", _medical, pid)
            record["send_provision"] = sen
            record["support_indicators"] = {"fsm": bool(pupil.fsm_eligible),
                                            "eal": bool(pupil.eal)}
        return ExportResult(record=record, local_student_id=str(pupil.pupil_id))

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """A primary school's Year 6 handover, or a pupil coming back from
        alternative provision: list them under Incoming pupils (no pupil
        record yet - admissions make or match it there)."""
        from education_system.systems.secondary.modules.progression.domain import incoming_primary
        if not handover.transition_id:
            raise AdapterError("A handover to secondary needs its transition id")
        incoming_primary.register_arrival(handover.transition_id, handover.journey_id)
        if handover.source_system in ("alternative_provision", "local_authority"):
            ident = handover.get("child_identity") or {}
            year = str(ident.get("year_group") or "") if isinstance(ident, dict) else ""
            what = ("from AP" if handover.source_system == "alternative_provision"
                    else "a school place from the local authority")
            return ApplicantResult(local_applicant_id=str(handover.transition_id),
                                   year_group=year or None,
                                   notes=f"Listed under Incoming pupils ({what})")
        return ApplicantResult(local_applicant_id=str(handover.transition_id),
                               year_group="7", notes="Listed under Incoming from Primary")

    def create_enrolment(self, journey_id: str, application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """The pupil admissions matched (or created) for an incoming transfer
        on the Incoming pupils screen - that screen is where a pupil record
        is made, so this only reports it, and refuses until it's done.
        *application_id* is the transfer (``create_applicant``'s id)."""
        from education_system.systems.secondary.infrastructure.database import (
            connection as database,
        )
        from education_system.systems.secondary.modules.progression.domain import (  # noqa: F401
            incoming_primary,  # its table
        )
        from education_system.systems.secondary.modules.pupils.domain import pupils as P

        with database.connect() as conn:
            row = conn.execute(
                "SELECT pupil_id FROM incoming_primary_pupils WHERE pupil_id IS NOT NULL "
                "AND (transition_id = ? OR journey_id = ?) ORDER BY transition_id = ? DESC "
                "LIMIT 1", (application_id or "", journey_id, application_id or "")
            ).fetchone()
        pupil = P.get_pupil(int(row[0])) if row else None
        if pupil is None:
            raise AdapterError("Match or create the pupil under Incoming pupils first - "
                               "that is where this school makes the pupil record")
        if pupil.roll_status != "on_roll":
            raise AdapterError(f"{pupil.display_name} isn't on roll here")
        return EnrolmentResult(local_student_id=str(pupil.pupil_id),
                               year_group=str(pupil.year_group),
                               start_date=details.get("start_date") or pupil.admission_date,
                               notes="matched under Incoming pupils")

    def close_enrolment(self, local_student_id: str, reason: str, **details: Any) -> None:
        from education_system.systems.secondary.modules.progression.domain import (
            sixth_form_progression,
        )

        pupil = _pupil(local_student_id)
        if pupil is None:
            logger.warning("close_enrolment: no secondary pupil %s", local_student_id)
            return
        if details.get("destination_school"):
            # A change of school within the phase (route_support.
            # transfer_within_phase): recorded as "Moved to another school"
            # so the leaver shows the CTF-due action, not as a sixth-form
            # leaver.
            self._close_moved_school(pupil, reason, details)
            return
        if not sixth_form_progression.close_for_sixth_form(
                pupil.pupil_id, end_date=details.get("end_date"), reason=reason):
            logger.info("Secondary pupil %s already off roll - not re-closing",
                        pupil.pupil_id)

    @staticmethod
    def _close_moved_school(pupil, reason: str, details: dict[str, Any]) -> None:
        import datetime as _dt
        import re

        from education_system.systems.secondary.modules.progression.domain.sixth_form_progression import (  # noqa: E501
            SYSTEM_ACTOR,
        )
        from education_system.systems.secondary.modules.pupils.domain import enrolment as E

        if pupil.roll_status != "on_roll":
            logger.info("Secondary pupil %s already off roll - not re-closing",
                        pupil.pupil_id)
            return
        today = _dt.date.today()
        when = str(details.get("end_date") or today.isoformat())[:10]
        try:
            if _dt.date.fromisoformat(when) > today:
                when = today.isoformat()
        except ValueError:
            when = today.isoformat()
        urn = str(details.get("destination_urn") or "").strip()
        # A sole-registered AP placement: a permanent exclusion, or a move.
        leaving = E.EXCLUSION if details.get("exclusion") else E.MOVED_SCHOOL
        E.record_leaver(
            pupil.pupil_id, leaving_date=when, reason=leaving,
            details={"destination_school": str(details["destination_school"])[:120],
                     "destination_urn": urn if re.fullmatch(r"\d{6}", urn) else None,
                     "notes": reason[:2000]},
            actor=SYSTEM_ACTOR, today=today)

    # ── The SEND service (platform.cross_system.send_referrals) ─────

    def receive_send_update(self, local_student_id: str, update: dict[str, Any]) -> str | None:
        """An EHCP decision from the SEND service (or the local authority's
        EHC team, ``update["by"]``), onto the SENCO's register:
        the EHC needs assessment status and dates, and the SEN status (EHC
        plan when the final plan is issued, SEN support when it ceases).
        Returns what changed."""
        from education_system.systems.secondary.core.permissions.access import Principal
        from education_system.systems.secondary.modules.pupils.domain import sen_details
        from education_system.systems.secondary.modules.send.domain import send

        if update.get("kind") != "ehcp":
            return None
        pupil = _pupil(local_student_id)
        if pupil is None:
            raise AdapterError(f"No secondary pupil {local_student_id}")
        stage = update.get("stage")
        current = send.get(pupil.pupil_id)
        data: dict[str, Any] = {}
        status = _EHCNA_STATUS.get(stage)
        if status:
            data["ehcna_status"] = status
            data["ehcna_requested_on"] = (update.get("request_date")
                                          or current.ehcna_requested_on)
            if update.get("decision_date"):
                data["ehcna_decision_on"] = update["decision_date"]
            if stage == "Final issued" and update.get("final_date"):
                data["ehcna_plan_on"] = update["final_date"]
        if stage == "Final issued":
            data["stage"] = send.EHCP
            details = sen_details.get(pupil.pupil_id)
            if details is not None and details.primary_need and update.get("final_date"):
                data["ehcp_issued_on"] = update["final_date"]
        elif stage == "Ceased" and pupil.sen_status == "E":
            data["stage"] = send.SUPPORT
        if not data:
            return None
        who = ("system:local-authority" if update.get("by") == "Local authority"
               else "system:send-service")
        send.save_record(pupil.pupil_id, data, actor=Principal(username=who, role="admin"))
        if stage == "Final issued":
            return "SEN status is now EHC plan"
        if stage == "Ceased" and data.get("stage"):
            return "SEN status is back to SEN support"
        return f"EHC needs assessment: {status.lower()}" if status else None


#: The SEND service's EHCP stage → the SENCO register's assessment status.
_EHCNA_STATUS = {"Requested": "Requested", "Assessing": "Agreed to assess",
                 "Draft issued": "Agreed to assess", "Refused to assess": "Refused to assess",
                 "Final issued": "Plan issued", "Not issued": "Plan not issued"}


ADAPTER = SecondaryAdapter()


def register() -> SecondaryAdapter:
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SecondaryAdapter", "ADAPTER", "identity_block", "register"]
