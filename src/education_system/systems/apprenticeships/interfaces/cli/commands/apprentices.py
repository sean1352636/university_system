"""Apprentice records: the cohort list, one record in detail, the lifecycle.

Also the home of the cohort helpers the other command modules borrow —
:func:`pick`, :func:`label` and :func:`names`. Evidence and off-the-job
rows carry an ``apprentice_id`` and no name, so a queue screen needs the
cohort to caption itself, and putting that lookup here keeps one
definition of "an apprentice this actor may see" rather than eight.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices import lifecycle
from education_system.systems.apprenticeships.domain.apprentices.models import ApprenticeSummary
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    employer_service,
    programme_service,
)
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════
# Shared cohort helpers
# ═════════════════════════════════════════════════════════════════════

def label(summary: ApprenticeSummary) -> str:
    """One apprentice as a single line on a pick list."""
    parts = [summary.full_name]
    if summary.programme_reference:
        parts.append(summary.programme_reference)
    parts.append(summary.apprentice.status)
    return " — ".join(parts)


def pick(actor: Actor, *, heading: str = "Apprentice", **filters: object) -> ApprenticeSummary:
    """Choose one apprentice from the cohort *actor* may see."""
    return prompts.choose(
        heading, apprentice_service.list_apprentices(actor, **filters), render=label
    )


def names(actor: Actor) -> dict[int, str]:
    """``{apprentice_id: name}`` for captioning rows that carry only an id."""
    return {
        summary.apprentice.apprentice_id: summary.full_name
        for summary in apprentice_service.list_apprentices(actor)
    }


def table(summaries: list[ApprenticeSummary]) -> None:
    """The standard cohort table."""
    prompts.table(
        (("Name", 22), ("ULN", 11), ("Programme", 22), ("Employer", 18),
         ("Status", 16), ("OTJ %", -6), ("Done %", -6)),
        summaries,
        lambda s: (
            s.full_name, s.apprentice.uln, s.programme_title, s.employer_name,
            s.apprentice.status, s.otj_percent, s.progress_percent,
        ),
        noun="apprentice",
    )


def show(actor: Actor, summary: ApprenticeSummary) -> None:
    """One apprentice in full, with their progress and status history."""
    record = summary.apprentice
    prompts.title(summary.full_name)
    prompts.details([
        ("ULN", record.uln),
        ("Date of birth", record.date_of_birth),
        ("Email", record.email),
        ("Phone", record.phone),
        ("Login", record.username),
        ("Status", record.status),
        ("Programme", _programme_label(summary)),
        ("Level", summary.programme_level),
        ("Employer", summary.employer_name),
        ("Workplace", summary.workplace_name),
        ("Tutor", summary.tutor_name),
        ("Weekly hours", record.weekly_hours),
        ("Funding model", record.funding_model),
        ("Started", record.start_date),
        ("Planned end", record.planned_end_date),
        ("Actual end", record.actual_end_date),
        ("Gateway", summary.gateway_status),
        ("Open reviews", summary.open_reviews),
        ("Prior learning", record.prior_learning),
        ("Support needs", record.support_needs),
        ("Notes", record.notes),
    ])
    print()
    bars(summary)

    history = apprentice_service.status_history(actor, record.apprentice_id)
    prompts.table(
        (("Date", 12), ("From", 18), ("To", 18), ("Reason", 28), ("By", 14)),
        history,
        lambda h: (h.effective_date, h.from_status, h.to_status, h.reason, h.actor),
        noun="status change",
    )


def bars(summary: ApprenticeSummary) -> None:
    """The three progress bars every apprentice screen shows."""
    prompts.note(
        f"Off-the-job  {prompts.bar(summary.otj_percent)}  "
        f"{summary.otj_hours_logged:,.0f} / {summary.otj_hours_target:,.0f} hrs"
    )
    prompts.note(
        f"KSBs         {prompts.bar(summary.ksb_percent)}  "
        f"{summary.ksbs_competent} / {summary.ksbs_total}"
    )
    prompts.note(f"Elapsed      {prompts.bar(summary.progress_percent)}")
    if summary.is_behind:
        prompts.note("  ! Off-the-job hours are behind the elapsed pace.")


def _programme_label(summary: ApprenticeSummary) -> str | None:
    if not summary.programme_title:
        return None
    return f"{summary.programme_reference or ''} {summary.programme_title}".strip()


# ═════════════════════════════════════════════════════════════════════
# Menu
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List apprentices", partial(_list, actor)),
        ("View an apprentice", partial(_view, actor)),
    ]
    if actor.can("apprentice.manage"):
        entries += [
            ("Enrol an apprentice", partial(_create, actor)),
            ("Edit an apprentice", partial(_edit, actor)),
            ("Change status", partial(_change_status, actor)),
            ("Start programme", partial(_start_programme, actor)),
            ("Assign a tutor", partial(_assign_tutor, actor)),
        ]
    if actor.is_admin:
        entries.append(("Delete an apprentice", partial(_delete, actor)))
    prompts.run_menu("Apprentices", entries)


def caseload(actor: Actor) -> None:
    """The signed-in tutor's own caseload."""
    summaries = apprentice_service.list_apprentices(actor, active_only=True)
    prompts.title("My Caseload")
    if actor.staff_id is None:
        prompts.note("Your login is not linked to a staff record, so there is no caseload.")
        prompts.pause()
        return

    table(summaries)
    print()
    for summary in summaries:
        prompts.note(
            f"{summary.full_name[:22]:<22}  OTJ {prompts.bar(summary.otj_percent, width=16)}"
            f"   KSB {prompts.bar(summary.ksb_percent, width=16)}"
            + ("   BEHIND" if summary.is_behind else "")
        )
    if summaries and prompts.ask_yes_no("Open one in detail?"):
        show(actor, prompts.choose("Apprentice", summaries, render=label))
    prompts.pause()


def my_details(actor: Actor) -> None:
    """The signed-in apprentice's own record."""
    summary = apprentice_service.get_own_record(actor)
    if summary is None:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return
    show(actor, summary)
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Commands
# ═════════════════════════════════════════════════════════════════════

def _list(actor: Actor) -> None:
    status = prompts.choose("Status filter", config.APPRENTICE_STATUSES, allow_blank=True)
    search = prompts.ask("Name, ULN or email contains")
    active_only = status is None and prompts.ask_yes_no("Active apprentices only?")
    summaries = apprentice_service.list_apprentices(
        actor, status=status, search=search or None, active_only=active_only
    )
    prompts.title("Apprentices")
    table(summaries)
    prompts.pause()


def _view(actor: Actor) -> None:
    show(actor, pick(actor))
    prompts.pause()


def _create(actor: Actor) -> None:
    prompts.title("Enrol an apprentice")
    payload: dict[str, object] = {
        "given_name": prompts.ask("First name", required=True),
        "family_name": prompts.ask("Last name", required=True),
        "uln": prompts.ask("ULN (10 digits, optional)"),
        "date_of_birth": prompts.ask("Date of birth (YYYY-MM-DD)"),
        "email": prompts.ask("Email"),
        "phone": prompts.ask("Phone"),
        "username": prompts.ask("Login username (for their portal)"),
        "weekly_hours": prompts.ask_float(
            "Contracted weekly hours", default=config.OTJ_STANDARD_WEEKLY_HOURS
        ),
        "support_needs": prompts.ask("Support needs"),
        "prior_learning": prompts.ask("Recognised prior learning"),
    }
    programme = _pick_programme(actor)
    if programme is not None:
        payload["programme_id"] = programme.programme_id
    payload.update(_ask_employer(actor))
    tutor = _pick_tutor()
    if tutor is not None:
        payload["tutor_id"] = tutor.staff_id

    created = apprentice_service.create_apprentice(actor, payload)
    prompts.ok(f"Enrolled {created.full_name} as an applicant (id {created.apprentice_id}).")
    prompts.note("Take them onto programme with 'Start programme' once the paperwork is signed.")
    prompts.pause()


def _edit(actor: Actor) -> None:
    summary = pick(actor)
    record = summary.apprentice
    prompts.title(f"Edit {record.full_name}")
    payload: dict[str, object] = {
        "given_name": prompts.ask("First name", default=record.given_name, required=True),
        "family_name": prompts.ask("Last name", default=record.family_name, required=True),
        "uln": prompts.ask("ULN", default=record.uln or ""),
        "date_of_birth": prompts.ask("Date of birth", default=record.date_of_birth or ""),
        "email": prompts.ask("Email", default=record.email or ""),
        "phone": prompts.ask("Phone", default=record.phone or ""),
        "username": prompts.ask("Login username", default=record.username or ""),
        "weekly_hours": prompts.ask_float("Weekly hours", default=record.weekly_hours),
        "prior_learning": prompts.ask("Prior learning", default=record.prior_learning or ""),
        "support_needs": prompts.ask("Support needs", default=record.support_needs or ""),
        "notes": prompts.ask("Notes", default=record.notes or ""),
    }
    if prompts.ask_yes_no("Change the employer or workplace?"):
        payload.update(_ask_employer(actor))

    updated = apprentice_service.update_apprentice(actor, record.apprentice_id, payload)
    prompts.ok(f"Updated {updated.full_name}.")
    prompts.pause()


def _change_status(actor: Actor) -> None:
    summary = pick(actor)
    apprentice_id = summary.apprentice.apprentice_id
    options = apprentice_service.available_transitions(actor, apprentice_id)
    prompts.title(f"{summary.full_name} — currently {summary.apprentice.status}")
    if not options:
        prompts.fail(f"{summary.apprentice.status} is a final status; there is nowhere to move.")
        prompts.pause()
        return

    new_status = prompts.choose_value("Move to", options)
    if new_status == "Withdrawn":
        reason = prompts.choose_value("Withdrawal reason", config.WITHDRAWAL_REASONS)
    elif new_status == "Break in Learning":
        reason = prompts.choose_value("Break reason", config.BREAK_REASONS)
    else:
        reason = prompts.ask("Reason", required=new_status in lifecycle.REASON_REQUIRED)
    notes = None
    if lifecycle.reason_options(new_status):
        notes = prompts.ask("Details", required=reason == lifecycle.OTHER_REASON) or None
    effective = prompts.ask("Effective date (YYYY-MM-DD)", default=date.today().isoformat())
    expected_return = last_day = None
    if new_status == "Break in Learning":
        expected_return = prompts.ask("Expected return (YYYY-MM-DD)") or None
    elif new_status == "Withdrawn":
        last_day = prompts.ask("Last day of learning (YYYY-MM-DD)", default=effective) or None

    updated = apprentice_service.change_status(
        actor, apprentice_id, new_status, reason=reason or None, effective_date=effective,
        notes=notes, expected_return=expected_return, last_activity_date=last_day,
    )
    prompts.ok(f"{updated.full_name} is now {updated.status}.")
    prompts.pause()


def _start_programme(actor: Actor) -> None:
    summary = pick(actor, heading="Applicant to start", status="Applicant")
    programme = _pick_programme(actor)
    start = prompts.ask("Start date (YYYY-MM-DD)", required=True)

    updated = apprentice_service.start_programme(
        actor,
        summary.apprentice.apprentice_id,
        start_date=start,
        programme_id=programme.programme_id if programme else None,
    )
    prompts.ok(f"{updated.full_name} started on {updated.start_date}.")
    prompts.note(
        f"Planned end {updated.planned_end_date} — the off-the-job target is derived from it."
    )
    prompts.pause()


def _assign_tutor(actor: Actor) -> None:
    summary = pick(actor)
    prompts.note(f"Current tutor: {summary.tutor_name or prompts.EMPTY}")
    tutor = _pick_tutor()

    updated = apprentice_service.assign_tutor(
        actor, summary.apprentice.apprentice_id, tutor.staff_id if tutor else None
    )
    if tutor is None:
        prompts.ok(f"{updated.full_name} is no longer on a caseload.")
    else:
        prompts.ok(f"{updated.full_name} is now on {tutor.full_name}'s caseload.")
    prompts.pause()


def _delete(actor: Actor) -> None:
    summary = pick(actor, heading="Apprentice to delete")
    prompts.note(
        "Deleting erases the record and everything attached to it. To record somebody "
        "leaving, change their status to Withdrawn instead."
    )
    if not prompts.ask_yes_no(f"Really delete {summary.full_name}?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)

    apprentice_service.delete_apprentice(actor, summary.apprentice.apprentice_id, reason=reason)
    prompts.ok(f"Deleted {summary.full_name}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Pickers
# ═════════════════════════════════════════════════════════════════════

def _pick_programme(actor: Actor):
    programmes = programme_service.list_programmes(actor, active_only=True)
    return prompts.choose(
        "Programme",
        programmes,
        render=lambda p: f"{p.reference} {p.title} (Level {p.level})",
        allow_blank=True,
    )


def _pick_tutor():
    staff = staff_repository.list_all(active_only=True)
    return prompts.choose(
        "Tutor",
        staff,
        render=lambda s: f"{s.full_name} — {s.staff_role}",
        allow_blank=True,
    )


def _ask_employer(actor: Actor) -> dict[str, object]:
    """Pick an employer and, within it, the site the apprentice works at."""
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
