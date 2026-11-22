"""University implementation of the platform progression contract.

Destination side: sixth form, FE and apprenticeships progress learners in
as applicants. Source side: a university student who takes up a degree
apprenticeship exports the ``UNIVERSITY_TO_APPRENTICESHIPS`` dataset.

That source side is a *dual registration*, not a departure, so
:meth:`UniversityAdapter.close_enrolment` deliberately leaves the student
record alone. Withdrawing from the university is a university decision
made through its own learner records, never a side effect of the learner
joining somebody else's programme.
"""

from __future__ import annotations

import logging
# The university database layer's sqlite3 (for its error types): the domain
# layer doesn't import the SQL driver itself.
from education_system.systems.university.infrastructure.database.db import sqlite3
from typing import Any

from education_system.platform.cross_system.adapters import registry
from education_system.platform.cross_system.adapters.base import (
    AdapterError, ApplicantResult, EnrolmentResult, ExportResult, HandoverRequest,
    PhaseAdapter,
)
from education_system.systems.university.domains.admissions.domain import sixthform_intake

logger = logging.getLogger(__name__)


def _connection():
    """A connection to the university database, as a context manager.

    The one place this adapter's source side opens that database, imported
    on first use so registering the adapter never touches it — and a seam
    a test replaces with a temporary database.
    """
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    return get_connection()


class UniversityAdapter(PhaseAdapter):
    system = "university"

    # ── Learner logins ──────────────────────────────────────────────

    learner_login_roles = ("student", "alumni")

    def learner_ids_for_login(self, account: dict) -> list[str]:
        """The student id the university's own sign-in resolves this login to.

        Mirrors ``session_user.resolve_local_identity``: the local
        ``users`` row with this username, and its ``student_id``. Logins
        are provisioned with ``username = student_id``, so for those this
        is the id itself; an account an administrator made with a separate
        student id resolves to that id, exactly as it does at sign-in.
        """
        username = str(account.get("username") or "").strip()
        if not username:
            return []
        with _connection() as conn:
            rows = conn.execute(
                "SELECT student_id FROM users WHERE username = ? "
                "AND student_id IS NOT NULL AND TRIM(student_id) != ''",
                (username,)).fetchall()
        return [str(r[0]) for r in rows]

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None, *,
                        destination_system: str | None = None) -> ExportResult:
        """What the university holds for a student starting a degree
        apprenticeship, keyed by the UNIVERSITY_TO_APPRENTICESHIPS spec."""
        progress = None
        with _connection() as conn:
            row = conn.execute(
                "SELECT * FROM students WHERE student_id = ?",
                (local_student_id,)).fetchone()
            if row is None:
                raise AdapterError(f"No university student {local_student_id} to export")
            try:
                progress = conn.execute(
                    """SELECT total_credits_earned, completion_percentage, status
                         FROM student_degree_progress WHERE student_id = ?
                        ORDER BY last_updated DESC LIMIT 1""",
                    (local_student_id,)).fetchone()
            except sqlite3.Error:
                logger.debug("No degree progress table for %s", local_student_id,
                             exc_info=True)
        student = dict(row)
        record: dict[str, Any] = {
            "learner_identity": {
                "first_name": student.get("first_name"),
                "last_name": student.get("last_name"),
                "date_of_birth": student.get("dob"),
                "university_student_id": student.get("student_id"),
            },
            "contact_details": {
                "email": student.get("email_address"),
                "phone": student.get("phone"),
                "address": student.get("address"),
            },
            "programme_registration": {
                "university_student_id": student.get("student_id"),
                "course": student.get("course"),
                "program": student.get("program"),
                "year_of_study": student.get("year_of_study") or student.get("year"),
                "academic_year": student.get("academic_year"),
                "mode_of_study": student.get("mode_of_study"),
                "status": student.get("status"),
                "enrollment_date": student.get("enrollment_date"),
            },
            "achieved_qualifications": student.get("entry_qualifications"),
            "prior_attainment": student.get("entry_qualifications"),
        }
        if progress is not None:
            record["module_credits"] = {
                "credits_earned": progress["total_credits_earned"],
                "completion_percentage": progress["completion_percentage"],
                "academic_status": progress["status"],
            }
        logger.info("Exported university student %s for handover to %s",
                    local_student_id, destination_system or "(unspecified)")
        return ExportResult(record=record, local_student_id=str(local_student_id))

    def close_enrolment(self, local_student_id: str, reason: str,
                        **details: Any) -> None:
        """Leave the student record open. Never closes, never deletes.

        Every boundary out of the university today is concurrent — a
        degree apprentice studies here *and* trains with the provider — so
        the transition is completed with ``close_source=False`` and this is
        only reached if a caller forgets that. Treating it as a no-op is
        the safe failure: a learner wrongly shown as still enrolled is a
        correction; one wrongly withdrawn loses their registration.
        """
        logger.info(
            "University student %s left open (%s): a university enrolment "
            "runs concurrently with the destination, and withdrawal is made "
            "through the university's own records", local_student_id, reason)

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        application_id, _created = sixthform_intake._create_applicant(
            handover.journey_id, handover.payload)
        return ApplicantResult(local_applicant_id=str(application_id))

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        if not application_id:
            existing = sixthform_intake.find_application_for_journey(journey_id)
            application_id = str(existing["application_id"]) if existing else None
        if not application_id:
            raise AdapterError(f"No university application for journey {journey_id}")
        from education_system.systems.university.domains.admissions.domain.services import (
            admissions_lifecycle,
        )
        student_id = admissions_lifecycle.convert_to_student(
            int(application_id), actor_id=str(details.get("actor_id") or "platform"))
        return EnrolmentResult(
            local_student_id=student_id, start_date=details.get("start_date"))

    # ── Admissions operations the platform's application board drives ──
    #
    # Outside the four-method contract, but still the university answering
    # for itself: the board in ``platform.cross_system.university_applications``
    # reaches them through the registry instead of importing admissions.

    def find_application(self, journey_id: str) -> dict | None:
        """The university's application for a journey, if any."""
        return sixthform_intake.find_application_for_journey(journey_id)

    def find_applications(self, journey_ids, *, strict: bool = False) -> dict[str, dict]:
        """The university's application for each journey, in one query."""
        return sixthform_intake.find_applications_for_journeys(journey_ids, strict=strict)

    def record_decision(self, application_id: int, *, unconditional: bool,
                        conditions: list[dict[str, Any]] | None = None) -> None:
        """Record the university's offer and any conditions on it."""
        from education_system.systems.university.domains.admissions.domain.services import (
            admissions_lifecycle,
        )
        status = (admissions_lifecycle.UNCONDITIONAL_OFFER if unconditional
                  else admissions_lifecycle.CONDITIONAL_OFFER)
        admissions_lifecycle.transition(application_id, status, force=True,
                                        reason="University decision")
        for condition in conditions or []:
            admissions_lifecycle.add_condition(
                application_id, condition.get("type") or "academic",
                condition.get("description") or "Offer condition",
                due_date=condition.get("due_date") or "")

    def accept_choice(self, application_id: int, choice_id: int, *,
                      accepted_by: str) -> None:
        """Record the learner's firm choice against the application."""
        from education_system.systems.university.domains.admissions.domain.services import (
            admissions_lifecycle,
        )
        admissions_lifecycle.accept_choice(application_id, choice_id)
        admissions_lifecycle.transition(
            application_id, admissions_lifecycle.ACCEPTED, force=True,
            reason=f"Firm choice selected by {accepted_by}")


    # ── Published facts and records other systems may ask for ──────────

    def institution_name(self) -> str | None:
        """What this university calls itself (the prospectus's name)."""
        from education_system.systems.university.application.programmes import prospectus

        return prospectus.institution_name()

    def published_courses(self) -> list[dict]:
        """The courses the prospectus publishes, as plain dicts."""
        from education_system.systems.university.application.programmes import prospectus

        return [{"code": c.code, "name": c.name, "min_tariff": c.min_tariff,
                 "duration": c.duration} for c in prospectus.published_courses()]

    def offer_terms_for_choices(self, choice_ids: list[int]) -> dict[int, dict]:
        """``{choice_id: terms}`` for the offer terms this university issued."""
        from education_system.systems.university.domains.admissions.domain.ucas import (
            offer_terms,
        )

        fields = ("terms_id", "grade_requirement", "grade_alternative", "reply_deadline",
                  "expiry_date", "scholarship", "accommodation_guaranteed", "notes",
                  "issued_at", "updated_at", "issued_by")
        out: dict[int, dict] = {}
        for cid, t in offer_terms.terms_for_choices(list(choice_ids)).items():
            row = {f: getattr(t, f, None) for f in fields}
            row["conditions"] = list(getattr(t, "conditions", None) or [])
            out[cid] = row
        return out

    def record_school_visit(self, tour: dict, attendees: list[dict]) -> dict:
        """File a school's visit in the Admissions CRM (tour, prospects,
        registrations); see :mod:`.school_visits`."""
        from education_system.systems.university.domains.admissions.domain import (
            school_visits,
        )

        return school_visits.record_school_visit(tour, attendees)


ADAPTER = UniversityAdapter()


def register() -> UniversityAdapter:
    registry.register(ADAPTER, replace=True)
    return ADAPTER


__all__ = ["UniversityAdapter", "ADAPTER", "register"]
