"""The contract each education system implements to join a transition.

The point of the adapter is containment. Without one, a nursery→primary
progression means nursery code importing primary's database module, and
sixth_form→university means the college knowing the shape of the
university's applicant table. Five systems and eight boundaries is a lot
of places for that coupling to grow.

With one, the platform orchestrates and each system answers four
questions about *itself only*:

``create_applicant``   here is a handover — make me a pending admission
``create_enrolment``   the offer was accepted — make the local learner id
``export_handover``    this learner is leaving — what may I release?
``close_enrolment``    they have gone — close the local record

An adapter never talks to another system's adapter. The workflow in
``transitions`` is what connects them, and it addresses each by its
system key.

Subclass :class:`PhaseAdapter`, implement the four methods, and register
the instance::

    from education_system.platform.cross_system.adapters import registry

    class PrimaryAdapter(PhaseAdapter):
        system = "primary"
        ...

    registry.register(PrimaryAdapter())

Unimplemented methods raise :class:`AdapterNotImplemented` rather than
returning ``None``, so a half-wired system fails loudly at the boundary
instead of silently dropping a learner mid-transfer.
"""

from __future__ import annotations

import abc
import logging
from typing import Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class AdapterError(RuntimeError):
    """An adapter could not carry out a request."""


class AdapterNotImplemented(AdapterError, NotImplementedError):
    """This system has not implemented that side of the contract yet."""


@dataclass
class HandoverRequest:
    """What the platform passes into ``create_applicant``."""

    journey_id: str
    source_system: str
    destination_system: str
    payload: dict = field(default_factory=dict)
    transition_id: str | None = None
    consent_reference: str | None = None
    year_group: str | None = None
    institution_id: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)

    @property
    def boundary(self) -> str:
        return f"{self.source_system}->{self.destination_system}"


@dataclass
class ApplicantResult:
    """What ``create_applicant`` returns."""

    local_applicant_id: str
    institution_id: str | None = None
    year_group: str | None = None
    notes: str | None = None


@dataclass
class EnrolmentResult:
    """What ``create_enrolment`` returns."""

    local_student_id: str
    institution_id: str | None = None
    year_group: str | None = None
    start_date: str | None = None
    notes: str | None = None


@dataclass
class ExportResult:
    """What ``export_handover`` returns.

    ``record`` is keyed by the boundary's :class:`~..handover.HandoverSpec`
    field keys. The adapter gathers, the platform filters — an adapter
    should return everything it holds for those keys and let
    ``handover.build_handover`` apply consent and strip restricted
    fields, rather than each system reimplementing that policy.
    """

    record: dict = field(default_factory=dict)
    safeguarding_reference: str | None = None
    local_student_id: str | None = None


class PhaseAdapter(abc.ABC):
    """One education system's side of the transition contract."""

    #: The system key this adapter serves — one of the five phase keys,
    #: matching ``identity_service.SYSTEM_SLOTS``.
    system: str = ""

    def __init__(self) -> None:
        if not self.system:
            raise AdapterError(
                f"{type(self).__name__} must set a class-level `system` key")

    # ── Destination side ────────────────────────────────────────────

    def create_applicant(self, handover: HandoverRequest) -> ApplicantResult:
        """Create a pending admission record from an approved handover.

        Called at workflow step 3. Must be idempotent on
        ``handover.journey_id``: a redelivered bus event has to find the
        existing applicant rather than create a second one.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet receive applicants "
            f"({type(self).__name__}.create_applicant)")

    def create_enrolment(self, journey_id: str,
                         application_id: str | None = None,
                         **details: Any) -> EnrolmentResult:
        """Turn an accepted applicant into a local enrolled learner.

        Called at workflow step 6, and this — not the applicant record —
        is what mints the system's local student id. Must be idempotent
        on ``journey_id``.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet create enrolments "
            f"({type(self).__name__}.create_enrolment)")

    # ── Source side ─────────────────────────────────────────────────

    def export_handover(self, local_student_id: str,
                        consent: bool | set[str] | None = None,
                        *, destination_system: str | None = None
                        ) -> ExportResult:
        """Gather the information this system holds for a departing
        learner, keyed by the boundary spec's field keys.

        Called at workflow step 5. Consent is passed through so an
        adapter may skip an expensive lookup it knows will be withheld;
        the authoritative filtering happens in ``handover.build_handover``.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet export handovers "
            f"({type(self).__name__}.export_handover)")

    def close_enrolment(self, local_student_id: str,
                        reason: str, **details: Any) -> None:
        """Close the local record when a learner leaves.

        Called at workflow step 7. Must not delete: the local record is
        marked as left/transferred so the system's own history, statutory
        returns and audit trail stay intact.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot yet close enrolments "
            f"({type(self).__name__}.close_enrolment)")

    # ── Learner logins ──────────────────────────────────────────────
    #
    # Optional, and deliberately outside the four-method transition
    # contract (so ``capabilities()`` keeps its shape). Implemented, it
    # lets ``cross_system.login_links`` link a learner's own login to their
    # platform learner record without the platform knowing how this
    # system pairs the two.

    #: ``user_systems`` roles in this system that are a learner's *own*
    #: login. Never a parent, guardian or staff role: a login holding one
    #: of these is linked to whichever learner record it resolves to.
    learner_login_roles: tuple[str, ...] = ()

    def learner_ids_for_login(self, account: dict) -> list[str]:
        """Local student ids this login belongs to — normally one.

        *account* is the platform ``users`` row (``id``, ``username``,
        ``email``, ``display_name``). Answer with the rule this system's own
        sign-in uses to find the learner, so the platform link can never
        disagree with what the login actually sees, and return ids in the
        journey-slot id space (what ``identity_service.find_by_student``
        takes). Return every match: two learners behind one login is a data
        problem the caller must see, not have hidden by a ``LIMIT 1``.
        """
        raise AdapterNotImplemented(
            f"{self.system} cannot pair logins with learners "
            f"({type(self).__name__}.learner_ids_for_login)")

    def learner_ids_for_logins(self, accounts: list[dict]) -> dict[int, list[str]]:
        """:meth:`learner_ids_for_login` for many logins: ``{account id: ids}``.

        The start-up catch-up asks this for every learner login a system
        has, so a system with thousands of them should answer in one query.
        Must give exactly what :meth:`learner_ids_for_login` gives for each
        account; the default simply asks one login at a time.
        """
        return {int(a["id"]): list(self.learner_ids_for_login(a)) for a in accounts}

    def pairs_logins(self) -> bool:
        """Does this adapter implement :meth:`learner_ids_for_login`?"""
        own = getattr(type(self), "learner_ids_for_login", None)
        return (bool(self.learner_login_roles)
                and own is not PhaseAdapter.learner_ids_for_login)

    # ── Admissions reads (optional) ─────────────────────────────────
    #
    # Outside the four-method transition contract, like learner logins.
    # They let a destination system's admissions office read what a
    # sending system holds about its applicants — UCAS choices, exam
    # results, the learner — without importing that system. Every value
    # returned is plain data (dicts, lists, strings), except where a method
    # says otherwise. Writes go on the cross-system bus, not through here,
    # apart from the few the sending system must make synchronously
    # (a reply, an application status, closing logins).

    def _not_implemented(self, name: str) -> AdapterNotImplemented:
        return AdapterNotImplemented(
            f"{self.system} does not provide {name} "
            f"({type(self).__name__}.{name})")

    def ucas_choices_for_institution(self, institution_names: set[str] | None = None,
                                     *, include_placed: bool = False
                                     ) -> list[dict]:
        """UCAS choices naming one of *institution_names* (``None`` = all).

        Keys: choice_id, application_id, student_id, student_name,
        ucas_personal_id, university, course_name, course_code,
        decision_status, reply_status ("Firm"/"Insurance"/None), entry_year,
        deferred (bool), choice_status ("Open"/"Placed"), application_status.
        Placed choices (already enrolled) only with ``include_placed``.
        """
        raise self._not_implemented("ucas_choices_for_institution")

    def ucas_choice(self, choice_id: int) -> dict | None:
        """One choice, same keys as :meth:`ucas_choices_for_institution`."""
        raise self._not_implemented("ucas_choice")

    def ucas_application(self, application_id: int) -> dict | None:
        """An application with its learner and every choice (``choices``)."""
        raise self._not_implemented("ucas_application")

    def ucas_record_reply(self, choice_id: int,
                          final_decision: str | None) -> dict:
        """Record the applicant's Firm/Insurance/Declined reply (or clear
        it). Raises :class:`AdapterError` with the reason when refused."""
        raise self._not_implemented("ucas_record_reply")

    def ucas_set_application_status(self, application_id: int,
                                    status: str) -> dict:
        """Set a UCAS application's status (Replied/Confirmed/Clearing)."""
        raise self._not_implemented("ucas_set_application_status")

    def exam_results_for_admissions(self, student_id: str, *,
                                    year: int | None = None) -> list[dict]:
        """Exam results for an applicant. Keys: subject, grade,
        qualification_type, released (bool), release_at (ISO or None),
        season, year. Embargoed results are included with
        ``released=False`` so the caller decides what it may show."""
        raise self._not_implemented("exam_results_for_admissions")

    def update_applicant_results(self, handover: HandoverRequest) -> None:
        """Exam results for an applicant this system already received
        (``create_applicant``), sent again after results day or a review.
        The payload holds ``gcse_results`` (the full current list - a grade
        no longer in it was withdrawn) and optionally ``gcse_entries`` (each
        with ``result``: awaited / under review / withheld / issued)."""
        raise self._not_implemented("update_applicant_results")

    def update_applicant_choices(self, handover: HandoverRequest) -> None:
        """New subject choices for an applicant this system already
        received: ``application_details.subjects`` in the payload."""
        raise self._not_implemented("update_applicant_choices")

    def learner_summary(self, student_id: str) -> dict | None:
        """id, names, dob, email, journey_id, status for an import screen."""
        raise self._not_implemented("learner_summary")

    def notify_learner(self, student_id: str, *, subject: str, body: str,
                       sender: str) -> bool:
        """Message a learner through this system's own messaging."""
        raise self._not_implemented("notify_learner")

    def send_learner_template(self, student_id: str, template: str,
                              context: dict) -> int | None:
        """Send one of this system's e-mail templates to a learner.
        Returns the message id, or None for an unknown learner."""
        raise self._not_implemented("send_learner_template")

    def close_leaver_logins(self, student_id: str) -> None:
        """Close the learner's login (and parent logins kept only for them)
        once their place onward is confirmed."""
        raise self._not_implemented("close_leaver_logins")

    def mark_transferred(self, student_id: str, *, moved_by: str) -> None:
        """Mark a learner as having left for the destination system."""
        raise self._not_implemented("mark_transferred")

    def handover_readiness(self, student_id: str) -> Any:
        """This system's readiness assessment for handing a learner over.
        Returns its own assessment object (``ready``, ``checks``,
        ``warnings``, ``record`` …), read by attribute."""
        raise self._not_implemented("handover_readiness")

    def build_handover(self, student_id: str) -> Any:
        """The consent-filtered handover payload for a learner, as built by
        this system for the university boundary (``included``,
        ``missing_required``, ``withheld_no_consent`` …)."""
        raise self._not_implemented("build_handover")

    def right_to_study_note(self) -> str:
        """The note shown where a right-to-study check is the destination's."""
        raise self._not_implemented("right_to_study_note")

    # ── Published facts and records another system may ask for ──────
    # (systems never import each other; these are how they ask instead)

    def institution_name(self) -> str | None:
        """What this institution calls itself, or None if it cannot say."""
        raise self._not_implemented("institution_name")

    def published_courses(self) -> list[dict]:
        """Courses this system recruits to, name-sorted. Keys: code, name,
        min_tariff, duration."""
        raise self._not_implemented("published_courses")

    def offer_terms_for_choices(self, choice_ids: list[int]) -> dict[int, dict]:
        """``{choice_id: terms}`` for offers this system issued on those UCAS
        choices. Keys: terms_id, grade_requirement, grade_alternative,
        reply_deadline, expiry_date, scholarship, accommodation_guaranteed,
        notes, issued_at, updated_at, issued_by, conditions."""
        raise self._not_implemented("offer_terms_for_choices")

    def record_school_visit(self, tour: dict, attendees: list[dict]) -> dict:
        """File a school's visit as a campus tour with one prospect per
        attendee, idempotently. ``tour``: tour_id (existing, or None),
        tour_date, tour_time, tour_guide, max_attendees, meeting_point,
        duration_minutes, status. Each attendee: key, prospect_id (existing,
        or None), first_name, last_name, email, date_of_birth, high_school,
        source, attended. Returns tour_id, prospects ({key: {prospect_id,
        created}}) and registrations_created."""
        raise self._not_implemented("record_school_visit")

    def list_learners(self) -> list[dict]:
        """Every learner on file, for a picker. Keys: student_id, full_name,
        first_name, last_name, status, date_of_birth."""
        raise self._not_implemented("list_learners")

    def handover_consent(self, student_id: str) -> dict | None:
        """The learner's active consent to hand their record to the next
        provider (consent_id, granted_date, expires_date …), or None."""
        raise self._not_implemented("handover_consent")

    def medical_record(self, student_id: str) -> dict:
        """The learner's medical record for a consented onward transfer:
        profile (dict or None), conditions, medications, allergies (lists of
        dicts). The caller must have checked consent first."""
        raise self._not_implemented("medical_record")

    # ── Capability reporting ────────────────────────────────────────

    def capabilities(self) -> dict[str, bool]:
        """Which sides of the contract this adapter actually implements.

        Lets a dashboard show that, say, primary can receive but not yet
        export, instead of that only surfacing when a transfer fails.
        """
        out = {}
        for name in ("create_applicant", "create_enrolment",
                     "export_handover", "close_enrolment"):
            own = getattr(type(self), name, None)
            base = getattr(PhaseAdapter, name, None)
            out[name] = own is not None and own is not base
        return out

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        done = sum(self.capabilities().values())
        return f"<{type(self).__name__} system={self.system} {done}/4>"


__all__ = [
    "AdapterError",
    "AdapterNotImplemented",
    "HandoverRequest",
    "ApplicantResult",
    "EnrolmentResult",
    "ExportResult",
    "PhaseAdapter",
]
