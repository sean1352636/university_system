"""Primary School side of the platform transition contract.

Both ends of the primary phase meet the platform here. Reception places
arrive from the nursery (``create_applicant`` then ``create_enrolment``);
Year 6 leavers export to secondary and are closed off roll
(``export_handover`` / ``close_enrolment``).

An arriving child is an *applicant* until the destination admits them:
the pupil row exists at ``roll_status='applicant'`` and stays out of the
class lists until ``create_enrolment`` puts them on roll. Leaving is the
reverse, and never a delete — the leaver is written to the school's own
leavers register and the pupil row is kept at ``left``.

The handover arrives already filtered by ``handover.build_handover``. If
the parent did not consent to medical detail crossing, it is simply not in
the payload, and nothing here goes looking for it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
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

SYSTEM_KEY = "primary"
ENTRY_YEAR = "R"


@dataclass
class PupilEnrolmentResult(EnrolmentResult):
    """``EnrolmentResult`` plus the pupil's school email address."""

    email: str | None = None


def _identity(handover: HandoverRequest) -> dict[str, Any]:
    raw = (handover.get("child_identity") or handover.get("student_identity")
           or handover.get("learner_identity") or {})
    return raw if isinstance(raw, dict) else {}


def _first_guardian(handover: HandoverRequest) -> dict[str, Any]:
    guardians = handover.get("guardians") or []
    if isinstance(guardians, dict):
        guardians = [guardians]
    for guardian in guardians:
        if isinstance(guardian, dict):
            return guardian
    return {}


def _medical_notes(handover: HandoverRequest) -> str:
    """Medical alerts as the primary record holds them: one notes field.

    Allergies are folded in explicitly — the pupil record has no separate
    allergies column, and an allergy lost on the way into Reception is a
    safeguarding failure.
    """
    alerts = handover.get("medical_alerts")
    if isinstance(alerts, dict):
        parts = []
        if alerts.get("allergies"):
            parts.append(f"Allergies: {str(alerts['allergies']).strip()}")
        if alerts.get("medical_notes"):
            parts.append(str(alerts["medical_notes"]).strip())
        return ("\n".join(parts)
                or "No allergies or medical alerts recorded by the previous setting")
    if alerts:
        return str(alerts).strip()
    requirements = handover.get("medical_requirements")
    return str(requirements).strip() if requirements else ""


def _editable(pupil: Any) -> dict[str, Any]:
    """The fields ``update_pupil`` re-validates, taken from a pupil."""
    return {
        "first_name": pupil.first_name, "last_name": pupil.last_name,
        "year_group": pupil.year_group, "class_name": pupil.class_name or "",
        "date_of_birth": pupil.date_of_birth or "",
        "parent_name": pupil.parent_name or "",
        "parent_phone": pupil.parent_phone or "",
        "medical_notes": pupil.medical_notes or "",
        "send_status": pupil.send_status or "",
    }


def leaver_id_for(pupil_id: str) -> str | None:
    """The leavers-register entry for a pupil, if one has been written."""
    from education_system.systems.primary.domain.learners.pupils.leavers import leavers

    leavers.init_db()
    conn = leavers._connect()
    try:
        row = conn.execute(
            "SELECT leaver_id FROM leavers WHERE pupil_id = ? "
            "ORDER BY created_at DESC LIMIT 1", (pupil_id,)).fetchone()
    finally:
        conn.close()
    return row["leaver_id"] if row else None


class PrimaryAdapter(PhaseAdapter):
    """Primary School's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Learner logins ──────────────────────────────────────────────

    learner_login_roles = ("student",)

    def learner_ids_for_login(self, account: dict) -> list[str]:
        """The pupil this login is named after: pupil id or school email.

        Primary never provisions pupil logins itself, so there is no
        sign-in rule to mirror; a login an administrator makes is paired
        only when its username is unmistakably one pupil's — the pupil id,
        or the pupil's (unique) school email.
        """
        from education_system.systems.primary.domain.learners.pupils import pupils

        username = str(account.get("username") or "").strip()
        if not username:
            return []
        pupils.init_db()
        with pupils._connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id FROM pupils WHERE UPPER(pupil_id) = UPPER(?) "
                "OR LOWER(email) = LOWER(?)", (username, username)).fetchall()
        return [str(r[0]) for r in rows]

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """Hold a place for an arriving child. Idempotent on journey_id."""
        from education_system.systems.primary.domain.learners.pupils import pupils

        existing = pupils.find_by_journey(handover.journey_id)
        if existing is not None:
            return ApplicantResult(
                local_applicant_id=existing.pupil_id,
                year_group=existing.year_group,
                notes=f"existing record, {existing.roll_status}")

        identity = _identity(handover)
        first = identity.get("first_name") or identity.get("given_name")
        last = identity.get("last_name") or identity.get("family_name")
        if not first or not last:
            raise AdapterError(
                f"Handover for journey {handover.journey_id} carries no usable "
                f"name; primary cannot create an applicant without one")
        year = (handover.year_group or ENTRY_YEAR).strip()
        if year not in pupils.YEAR_GROUPS:
            raise AdapterError(
                f"Year group must be one of {', '.join(pupils.YEAR_GROUPS)}")
        guardian = _first_guardian(handover)
        send = handover.get("send_support") or handover.get("send_provision")
        try:
            pupil = pupils.create_pupil({
                "first_name": first,
                "last_name": last,
                "year_group": year,
                "class_name": handover.get("class_name") or "",
                "date_of_birth": identity.get("date_of_birth") or "",
                "parent_name": guardian.get("name") or "",
                "parent_phone": guardian.get("phone") or "",
                "medical_notes": _medical_notes(handover),
                "send_status": "yes" if send else "",
            }, roll_status="applicant", journey_id=handover.journey_id)
        except pupils.ValidationError as exc:
            raise AdapterError(
                f"Primary could not create an applicant for journey "
                f"{handover.journey_id}: {exc}") from exc
        logger.info("Created primary applicant %s for journey %s (from %s)",
                    pupil.pupil_id, handover.journey_id, handover.source_system)
        return ApplicantResult(local_applicant_id=pupil.pupil_id, year_group=year,
                               notes=f"applicant created from {handover.boundary}")

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """Put the applicant on roll. Idempotent on journey_id."""
        from education_system.systems.primary.domain.learners.pupils import pupils

        pupil = pupils.find_by_journey(journey_id)
        if pupil is None and application_id:
            pupil = pupils.get_pupil(str(application_id))
        if pupil is None:
            raise AdapterError(
                f"No primary applicant for journey {journey_id}; "
                f"create_applicant must run before create_enrolment")
        if pupil.roll_status == "left":
            raise AdapterError(
                f"Primary pupil {pupil.pupil_id} has left; re-admission is a "
                f"new application")
        if pupil.roll_status == "applicant":
            overrides = {key: str(details[key]).strip()
                         for key in ("year_group", "class_name")
                         if details.get(key)}
            if overrides:
                try:
                    pupils.update_pupil(pupil.pupil_id,
                                        {**_editable(pupil), **overrides})
                except pupils.ValidationError as exc:
                    raise AdapterError(str(exc)) from exc
            pupil = pupils.set_roll_status(pupil.pupil_id, pupils.ON_ROLL)
            logger.info("Primary pupil %s on roll (journey %s)",
                        pupil.pupil_id, journey_id)
        return PupilEnrolmentResult(
            local_student_id=pupil.pupil_id, year_group=pupil.year_group,
            start_date=details.get("start_date"), email=pupil.email,
            notes="on roll")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """What the school holds for the PRIMARY_TO_SECONDARY keys."""
        from education_system.systems.primary.domain.learners.pupils import pupils

        pupil = pupils.get_pupil(local_student_id)
        if pupil is None:
            raise AdapterError(f"No primary pupil {local_student_id} to export")
        has_guardian = bool(pupil.parent_name or pupil.parent_phone)
        record: dict[str, Any] = {
            "child_identity": {
                "first_name": pupil.first_name,
                "last_name": pupil.last_name,
                "date_of_birth": pupil.date_of_birth,
                "primary_pupil_id": pupil.pupil_id,
                "year_group": pupil.year_group,
            },
            "guardians": ([{"name": pupil.parent_name, "phone": pupil.parent_phone,
                            "relationship": "Parent/Carer"}]
                          if has_guardian else None),
            "send_provision": ({"send_status": "yes"}
                               if pupil.send_status == "yes" else None),
            "medical_requirements": pupil.medical_notes or None,
        }
        return ExportResult(record=record, local_student_id=pupil.pupil_id)

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """Record the leaver and take the pupil off roll. Never deletes."""
        from education_system.systems.primary.domain.learners.pupils import pupils
        from education_system.systems.primary.domain.learners.pupils.leavers import leavers

        pupil = pupils.get_pupil(local_student_id)
        if pupil is None:
            logger.warning("close_enrolment: no primary pupil %s", local_student_id)
            return
        if pupil.roll_status == "left":
            logger.info("Primary pupil %s has already left — not re-closing",
                        local_student_id)
            return
        end_date = details.get("end_date") or date.today().isoformat()
        if leaver_id_for(pupil.pupil_id) is None:
            leavers.create_leaver({
                "pupil_id": pupil.pupil_id,
                "first_name": pupil.first_name,
                "last_name": pupil.last_name,
                "date_of_birth": pupil.date_of_birth or "",
                "year_left": pupil.year_group,
                "leaving_date": end_date,
                "destination_school": (details.get("destination_school")
                                       or details.get("destination") or ""),
                "current_email": details.get("current_email") or "",
                "parent_phone": pupil.parent_phone or "",
                "reason": reason,
                "status": "active",
                "notes": details.get("notes") or "",
            })
        pupils.set_roll_status(pupil.pupil_id, "left", left_date=end_date,
                               exit_reason=reason)
        logger.info("Primary pupil %s taken off roll (%s)", pupil.pupil_id, reason)


ADAPTER = PrimaryAdapter()


def register() -> PrimaryAdapter:
    """Register this adapter with the platform. Idempotent."""
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SYSTEM_KEY", "PrimaryAdapter", "PupilEnrolmentResult", "ADAPTER",
           "leaver_id_for", "register"]
