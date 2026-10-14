"""The admissions queue: accept or decline the people who have applied.

Applicants reach this screen two ways — created by hand when somebody
walks in, or handed over by a school, college or university through the
cross-system transfer. The queue does not distinguish them beyond an
Origin column, because the decision is the same either way; what differs
is that accepting a transfer also closes the transfer off in the sending
system, and that is handled in the service.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships.domain.apprentices.models import (
    ValidationError,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import (
    admissions_service,
    employer_service,
    programme_service,
)
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Menu
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("View the queue", partial(_queue, actor)),
        ("Open an application", partial(_view, actor)),
    ]
    if actor.can("admission.decide"):
        entries += [
            ("Make an offer", partial(_offer, actor)),
            ("Record an enrolment", partial(_enrol, actor)),
            ("Accept an applicant", partial(_accept, actor)),
            ("Decline an applicant", partial(_decline, actor)),
        ]
    prompts.run_menu("Admissions", entries)


# ═════════════════════════════════════════════════════════════════════
# Shared helpers
# ═════════════════════════════════════════════════════════════════════

def _label(application: admissions_service.Application) -> str:
    """One application as a single line on a pick list."""
    parts = [application.full_name, application.origin_label]
    if application.applied_at:
        parts.append(application.applied_at[:10])
    return " — ".join(parts)


def _table(applications: list[admissions_service.Application]) -> None:
    prompts.table(
        (("Name", 22), ("ULN", 11), ("Origin", 20), ("Applied", 11), ("Stage", 12),
         ("Programme", 20), ("Employer", 16)),
        applications,
        lambda a: (
            a.full_name, a.summary.apprentice.uln, a.origin_label,
            (a.applied_at or "")[:10], a.stage_label, a.summary.programme_title,
            a.summary.employer_name,
        ),
        noun="application",
    )


def _load(actor: Actor) -> list[admissions_service.Application]:
    return admissions_service.list_applications(actor)


def _pick(actor: Actor, heading: str) -> admissions_service.Application | None:
    """Choose one waiting application, or None when the queue is empty."""
    applications = _load(actor)
    if not applications:
        prompts.note("Nobody is waiting for a decision.")
        prompts.pause()
        return None
    return prompts.choose(heading, applications, render=_label)


def _show(application: admissions_service.Application) -> None:
    """One application in full, with what the sending system passed over."""
    record = application.summary.apprentice
    prompts.title(f"{application.full_name} — application")
    prompts.details([
        ("ULN", record.uln),
        ("Date of birth", record.date_of_birth),
        ("Email", record.email),
        ("Phone", record.phone),
        ("Origin", application.origin_label),
        ("Applied", application.applied_at),
        ("Transfer stage", application.transition_status),
        ("Programme", application.summary.programme_title),
        ("Employer", application.summary.employer_name),
        ("Admission stage", application.stage_label),
        ("Offer date", application.stage.offer_date if application.stage else None),
        ("Offer conditions",
         application.stage.offer_conditions if application.stage else None),
        ("Enrolment date", application.stage.enrolment_date if application.stage else None),
        ("Prior learning", record.prior_learning),
        ("Support needs", record.support_needs),
        ("Notes", record.notes),
    ])
    if application.is_cross_system:
        prompts.note(
            "Accepting will also close this transfer off in "
            f"{(application.source_system or 'the sending system').replace('_', ' ')}.")


# ═════════════════════════════════════════════════════════════════════
# Commands
# ═════════════════════════════════════════════════════════════════════

def _queue(actor: Actor) -> None:
    applications = _load(actor)
    prompts.title("Admissions queue")
    _table(applications)
    if applications:
        waiting = sum(1 for a in applications if a.is_cross_system)
        if waiting:
            prompts.note(
                f"{waiting} of {len(applications)} arrived from another system.")
    prompts.pause()


def _view(actor: Actor) -> None:
    application = _pick(actor, "Application")
    if application is None:
        return
    _show(application)
    prompts.pause()


def _offer(actor: Actor) -> None:
    application = _pick(actor, "Applicant to offer a place")
    if application is None:
        return
    _show(application)
    stage = application.stage
    offer_date = prompts.ask(
        "Offer date (YYYY-MM-DD)",
        default=(stage.offer_date if stage and stage.offer_date else date.today().isoformat()),
    )
    conditions = prompts.ask(
        "Conditions (blank for unconditional)",
        default=(stage.offer_conditions or "") if stage else "",
    )
    saved = admissions_service.make_offer(
        actor, application.apprentice_id, offer_date=offer_date, conditions=conditions or None,
    )
    prompts.ok(f"{application.full_name} has an offer dated {saved.offer_date}"
               + (" (conditional)." if saved.offer_conditions else "."))
    prompts.pause()


def _enrol(actor: Actor) -> None:
    application = _pick(actor, "Applicant who has enrolled")
    if application is None:
        return
    _show(application)
    when = prompts.ask("Enrolment date (YYYY-MM-DD)", default=date.today().isoformat())
    saved = admissions_service.record_enrolment(
        actor, application.apprentice_id, enrolment_date=when,
    )
    prompts.ok(f"Enrolment recorded for {application.full_name} on {saved.enrolment_date}.")
    prompts.note("Accept them onto programme when they start.")
    prompts.pause()


def _accept(actor: Actor) -> None:
    application = _pick(actor, "Applicant to accept")
    if application is None:
        return
    _show(application)
    print()

    if not prompts.ask_yes_no(f"Accept {application.full_name}?"):
        prompts.note("No decision recorded.")
        prompts.pause()
        return

    programme = _pick_programme(actor, application)
    employer = _ask_employer(actor, application)
    tutor = _pick_tutor()
    start = prompts.ask("Start date (YYYY-MM-DD)",
                        default=date.today().isoformat(), required=True)
    notes = prompts.ask("Note for the record")

    try:
        decision = admissions_service.accept(
            actor, application.apprentice_id,
            start_date=start,
            programme_id=programme.programme_id if programme else None,
            employer_id=employer.get("employer_id"),
            workplace_id=employer.get("workplace_id"),
            tutor_id=tutor.staff_id if tutor else None,
            notes=notes or None,
        )
    except ValidationError as exc:
        prompts.fail(str(exc))
        prompts.pause()
        return

    prompts.ok(f"{decision.full_name} is now {decision.status}, from {start}.")
    _report_platform(decision)
    prompts.pause()


def _decline(actor: Actor) -> None:
    application = _pick(actor, "Applicant to decline")
    if application is None:
        return
    _show(application)
    print()

    reason = prompts.ask("Reason for declining", required=True)
    if not prompts.ask_yes_no(f"Decline {application.full_name}?"):
        prompts.note("No decision recorded.")
        prompts.pause()
        return

    try:
        decision = admissions_service.decline(
            actor, application.apprentice_id, reason=reason)
    except ValidationError as exc:
        prompts.fail(str(exc))
        prompts.pause()
        return

    prompts.ok(f"{decision.full_name} declined; the record and reason are kept.")
    _report_platform(decision)
    prompts.pause()


def _report_platform(decision: admissions_service.Decision) -> None:
    """Surface a cross-system problem without implying the decision failed."""
    if decision.platform_error:
        prompts.note(f"! {decision.platform_error}")
        return
    if decision.transition_closed and not decision.source_closed:
        prompts.note(
            "The sending system's enrolment was left open — this is a "
            "concurrent registration, so they remain enrolled there too.")


# ═════════════════════════════════════════════════════════════════════
# Pickers — defaulted from what the handover already carried
# ═════════════════════════════════════════════════════════════════════

def _pick_programme(actor: Actor, application: admissions_service.Application):
    if application.summary.programme_title:
        prompts.note(
            f"The application already names {application.summary.programme_title}. "
            "Leave blank to keep it.")
    programmes = programme_service.list_programmes(actor, active_only=True)
    return prompts.choose(
        "Programme",
        programmes,
        render=lambda p: f"{p.reference} {p.title} (Level {p.level})",
        allow_blank=True,
    )


def _ask_employer(actor: Actor,
                  application: admissions_service.Application) -> dict[str, object]:
    """Pick the employer and, within it, the site they work at."""
    if application.summary.employer_name:
        prompts.note(
            f"The application already names {application.summary.employer_name}. "
            "Leave blank to keep it.")
    employers = employer_service.list_employers(actor)
    chosen = prompts.choose(
        "Employer",
        employers,
        render=lambda e: f"{e.name} ({e.employer.status})",
        allow_blank=True,
    )
    if chosen is None:
        return {}
    employer_id = chosen.employer.employer_id
    workplaces = employer_service.list_workplaces(actor, employer_id, active_only=True)
    workplace = prompts.choose(
        "Workplace", workplaces, render=lambda w: w.name, allow_blank=True
    )
    return {
        "employer_id": employer_id,
        "workplace_id": workplace.workplace_id if workplace else None,
    }


def _pick_tutor():
    staff = staff_repository.list_all(active_only=True)
    return prompts.choose(
        "Tutor", staff, render=lambda s: f"{s.full_name} — {s.staff_role}",
        allow_blank=True,
    )
