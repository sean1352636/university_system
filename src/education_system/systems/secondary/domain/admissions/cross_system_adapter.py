"""Secondary School side of the platform progression contract.

Both ends of the secondary phase meet the platform here. Year 7 places
arrive from primary (``create_applicant`` then ``create_enrolment``);
Year 11 leavers export to sixth form, FE or an apprenticeship and are
closed off roll (``export_handover`` / ``close_enrolment``).

Closing keeps the pupil. It records the leaver on the school's alumni
register and marks the pupil row ``left``, so attendance history,
statutory returns and the audit trail survive the move. It used to delete
the pupil, which the adapter contract forbids.
"""

from __future__ import annotations

import logging
import secrets
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

SYSTEM_KEY = "secondary"
ENTRY_YEAR = "7"
LOGIN_ROLE = "student"


@dataclass
class PupilEnrolmentResult(EnrolmentResult):
    """``EnrolmentResult`` plus the school login made for the pupil.

    ``initial_password`` is set only when this call created the login; an
    existing login is left alone and its password is never reset.
    """

    email: str | None = None
    auth_user_id: int | None = None
    initial_password: str | None = None


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


def _editable(pupil: Any) -> dict[str, Any]:
    """The fields ``update_pupil`` re-validates, taken from a pupil."""
    return {
        "first_name": pupil.first_name, "last_name": pupil.last_name,
        "year_group": pupil.year_group, "form_group": pupil.form_group or "",
        "date_of_birth": pupil.date_of_birth or "", "phone": pupil.phone or "",
        "parent_name": pupil.parent_name or "",
        "parent_phone": pupil.parent_phone or "",
        "send_status": pupil.send_status or "",
    }


def _provision_login(pupil: Any) -> tuple[int | None, str | None]:
    """Create the pupil's school login, named by their school email.

    Returns ``(auth_user_id, password)``, or ``(None, None)`` when a login
    with that username already exists — a retried transfer must not reset
    a password the pupil may already be using.
    """
    from education_system.platform.identity.auth.core import UserAuth
    from education_system.platform.identity.auth.exceptions import AuthError
    from education_system.platform.identity.auth.schema import initialise_auth_db

    password = f"Sec-{secrets.token_urlsafe(9)}1!"
    initialise_auth_db()
    try:
        user_id = UserAuth().create_user(
            username=pupil.email, password=password,
            display_name=pupil.full_name, email=pupil.email,
            systems=[(SYSTEM_KEY, LOGIN_ROLE)])
    except AuthError as exc:
        if "already exists" in str(exc):
            logger.info("Login %s already exists — leaving it untouched",
                        pupil.email)
            return None, None
        raise
    # The pupil arrived through a transfer, so their journey exists: link
    # the new login to it. Best-effort, never raises.
    from education_system.platform.cross_system import login_links
    login_links.try_sync_username(pupil.email)
    return int(user_id), password


def alumni_id_for(pupil_id: str) -> str | None:
    """The alumni-register entry for a pupil, if one has been written."""
    from education_system.systems.secondary.domain.learners.alumni import alumni

    alumni.init_db()
    conn = alumni._connect()
    try:
        row = conn.execute(
            "SELECT alumni_id FROM alumni WHERE pupil_id = ? "
            "ORDER BY created_at DESC LIMIT 1", (pupil_id,)).fetchone()
    finally:
        conn.close()
    return row["alumni_id"] if row else None


class SecondaryAdapter(PhaseAdapter):
    """Secondary School's side of the four-method transition contract."""

    system = SYSTEM_KEY

    # ── Learner logins ──────────────────────────────────────────────

    learner_login_roles = (LOGIN_ROLE,)

    def learner_ids_for_login(self, account: dict) -> list[str]:
        """The pupil this login is named after.

        Pupil logins are provisioned with ``username = pupil.email``
        (:func:`_provision_login`), and the school email is unique; a login
        an administrator names after the pupil id is taken as that pupil's
        too. Anything else is not paired.
        """
        from education_system.systems.secondary.domain.learners.pupils import pupils

        username = str(account.get("username") or "").strip()
        if not username:
            return []
        pupils.init_db()
        with pupils._connect() as conn:
            rows = conn.execute(
                "SELECT pupil_id FROM pupils WHERE LOWER(email) = LOWER(?) "
                "OR UPPER(pupil_id) = UPPER(?)", (username, username)).fetchall()
        return [str(r[0]) for r in rows]

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """Hold a Year 7 place for an arriving pupil. Idempotent on journey_id."""
        from education_system.systems.secondary.domain.learners.pupils import pupils

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
                f"name; secondary cannot create an applicant without one")
        year = (handover.year_group or ENTRY_YEAR).strip()
        if year not in pupils.YEAR_GROUPS:
            raise AdapterError(
                f"Year group must be one of {', '.join(pupils.YEAR_GROUPS)}")
        guardian = _first_guardian(handover)
        send = handover.get("send_provision") or handover.get("send_support")
        try:
            pupil = pupils.create_pupil({
                "first_name": first,
                "last_name": last,
                "year_group": year,
                "form_group": handover.get("form_group") or "",
                "date_of_birth": identity.get("date_of_birth") or "",
                "phone": "",
                "parent_name": guardian.get("name") or "",
                "parent_phone": guardian.get("phone") or "",
                "send_status": "yes" if send else "",
            }, roll_status="applicant", journey_id=handover.journey_id)
        except pupils.ValidationError as exc:
            raise AdapterError(
                f"Secondary could not create an applicant for journey "
                f"{handover.journey_id}: {exc}") from exc
        if handover.get("medical_requirements"):
            # The pupil record has no medical column. The detail is on the
            # approved handover of this transition, which is where the
            # school's medical lead reads it — not copied into free text.
            logger.info("Medical requirements for pupil %s are held on the "
                        "approved handover of transition %s", pupil.pupil_id,
                        handover.transition_id)
        logger.info("Created secondary applicant %s for journey %s (from %s)",
                    pupil.pupil_id, handover.journey_id, handover.source_system)
        return ApplicantResult(local_applicant_id=pupil.pupil_id, year_group=year,
                               notes=f"applicant created from {handover.boundary}")

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """Put the applicant on roll and, if asked, make their login.

        ``provision_login=True`` creates the pupil's school sign-in, which
        the old primary→secondary transfer used to do from inside the
        primary system. Idempotent on journey_id.
        """
        from education_system.systems.secondary.domain.learners.pupils import pupils

        pupil = pupils.find_by_journey(journey_id)
        if pupil is None and application_id:
            pupil = pupils.get_pupil(str(application_id))
        if pupil is None:
            raise AdapterError(
                f"No secondary applicant for journey {journey_id}; "
                f"create_applicant must run before create_enrolment")
        if pupil.roll_status == "left":
            raise AdapterError(
                f"Secondary pupil {pupil.pupil_id} has left; re-admission is a "
                f"new application")
        if pupil.roll_status == "applicant":
            form_group = str(details.get("form_group") or "").strip()
            if form_group and form_group != (pupil.form_group or ""):
                try:
                    pupils.update_pupil(pupil.pupil_id,
                                        {**_editable(pupil), "form_group": form_group})
                except pupils.ValidationError as exc:
                    raise AdapterError(str(exc)) from exc
            pupil = pupils.set_roll_status(pupil.pupil_id, pupils.ON_ROLL)
            logger.info("Secondary pupil %s on roll (journey %s)",
                        pupil.pupil_id, journey_id)
        auth_user_id = password = None
        if details.get("provision_login"):
            auth_user_id, password = _provision_login(pupil)
        return PupilEnrolmentResult(
            local_student_id=pupil.pupil_id, year_group=pupil.year_group,
            start_date=details.get("start_date"), email=pupil.email,
            auth_user_id=auth_user_id, initial_password=password,
            notes="on roll")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str, consent=None, *,
                        destination_system: str | None = None) -> ExportResult:
        from education_system.systems.secondary.domain.learners.pupils import pupils
        pupil = pupils.get_pupil(local_student_id)
        if pupil is None:
            raise AdapterError(f"No secondary pupil {local_student_id}")
        identity = {
            "first_name": pupil.first_name,
            "last_name": pupil.last_name,
            "date_of_birth": pupil.date_of_birth,
            "secondary_pupil_id": pupil.pupil_id,
        }
        return ExportResult(record={
            "student_identity": dict(identity),
            "learner_identity": dict(identity),
            "contact_details": {
                "email": pupil.email, "phone": pupil.phone,
                "parent_name": pupil.parent_name,
                "parent_phone": pupil.parent_phone,
            },
            "send_support": "SEND support recorded" if pupil.send_status == "yes" else None,
        }, local_student_id=pupil.pupil_id)

    def close_enrolment(self, local_student_id: str, reason: str, **details) -> None:
        """Record the leaver on the alumni register and take the pupil off
        roll. Never deletes: the pupil row is kept at ``left``."""
        from education_system.systems.secondary.domain.learners.alumni import alumni
        from education_system.systems.secondary.domain.learners.pupils import pupils

        pupil = pupils.get_pupil(local_student_id)
        if pupil is None:
            logger.warning("close_enrolment: no secondary pupil %s", local_student_id)
            return
        if pupil.roll_status == "left":
            logger.info("Secondary pupil %s has already left — not re-closing",
                        local_student_id)
            return
        end_date = details.get("end_date") or date.today().isoformat()
        if alumni_id_for(pupil.pupil_id) is None:
            alumni.create_alumnus({
                "pupil_id": pupil.pupil_id, "first_name": pupil.first_name,
                "last_name": pupil.last_name,
                "date_of_birth": pupil.date_of_birth or "",
                "year_left": pupil.year_group, "leaving_date": end_date,
                "current_email": details.get("current_email") or pupil.email,
                "current_phone": pupil.phone or "",
                "destination": details.get("destination") or reason,
                "status": "active", "notes": details.get("notes") or reason,
            })
        pupils.set_roll_status(pupil.pupil_id, "left", left_date=end_date,
                               exit_reason=reason)
        logger.info("Secondary pupil %s taken off roll (%s)", pupil.pupil_id, reason)


ADAPTER = SecondaryAdapter()


def register() -> SecondaryAdapter:
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["SecondaryAdapter", "PupilEnrolmentResult", "ADAPTER",
           "alumni_id_for", "register"]
