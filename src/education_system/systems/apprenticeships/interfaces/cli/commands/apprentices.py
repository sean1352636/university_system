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
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.employers import employer_service
from education_system.systems.apprenticeships.application.programmes import programme_service
from education_system.systems.apprenticeships.application.security import account_service
from education_system.systems.apprenticeships.application.security.access import Actor

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
        ("Legal name", record.legal_name),
        ("Preferred name", record.preferred_name),
        ("Gender", record.gender),
        ("ULN", record.uln),
        ("Date of birth", record.date_of_birth),
        ("Address", record.address),
        ("Emergency contact", " · ".join(p for p in (
            record.emergency_contact_name, record.emergency_contact_relationship,
            record.emergency_contact_phone) if p) or None),
        ("Learning difficulty / disability", "Yes" if record.has_lldd else "No"),
        ("EHC plan", "Yes" if record.has_ehcp else "No"),
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
        ("Medical notes", record.medical_notes),
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
            ("Create a login", partial(_create_login_menu, actor)),
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


def _ask_personal(record=None) -> dict[str, object]:
    """Identity, address, emergency contact and needs: the same details the
    GUI form and the other systems' add-learner forms collect."""
    def d(attr: str) -> str:
        return (getattr(record, attr, None) or "") if record is not None else ""

    print("\n  Identity")
    payload: dict[str, object] = {
        "given_name": prompts.ask("Legal first name", default=d("given_name"), required=True),
        "middle_name": prompts.ask("Middle name(s)", default=d("middle_name")),
        "family_name": prompts.ask("Legal last name", default=d("family_name"), required=True),
        "preferred_name": prompts.ask("Preferred name", default=d("preferred_name")),
        "date_of_birth": prompts.ask("Date of birth (YYYY-MM-DD)", default=d("date_of_birth")),
    }
    gender = prompts.choose("Gender", config.GENDERS, allow_blank=True)
    payload["gender"] = gender if gender is not None else (d("gender") or None)
    payload["uln"] = prompts.ask("ULN (10 digits, optional)", default=d("uln"))
    print("\n  Contact")
    payload["email"] = prompts.ask("Email", default=d("email"))
    payload["phone"] = prompts.ask("Phone", default=d("phone"))
    print("\n  Home address")
    payload["address_line1"] = prompts.ask("Address line 1", default=d("address_line1"))
    payload["address_line2"] = prompts.ask("Address line 2", default=d("address_line2"))
    payload["town"] = prompts.ask("Town / city", default=d("town"))
    payload["postcode"] = prompts.ask("Postcode", default=d("postcode"))
    print("\n  Emergency contact")
    payload["emergency_contact_name"] = prompts.ask(
        "Name", default=d("emergency_contact_name"))
    if payload["emergency_contact_name"]:
        relation = prompts.choose("Relationship", config.EMERGENCY_RELATIONSHIPS,
                                  allow_blank=True)
        payload["emergency_contact_relationship"] = (
            relation if relation is not None else (d("emergency_contact_relationship") or None))
        payload["emergency_contact_phone"] = prompts.ask(
            "Phone", default=d("emergency_contact_phone"), required=True)
    else:
        payload["emergency_contact_relationship"] = ""
        payload["emergency_contact_phone"] = ""
    print("\n  Needs and medical")
    payload["has_lldd"] = prompts.ask_yes_no(
        "Learning difficulty or disability?", default=bool(getattr(record, "has_lldd", False)))
    payload["has_ehcp"] = prompts.ask_yes_no(
        "Has an EHC plan?", default=bool(getattr(record, "has_ehcp", False)))
    payload["support_needs"] = prompts.ask("Support needs", default=d("support_needs"))
    payload["medical_notes"] = prompts.ask("Medical notes", default=d("medical_notes"))
    return payload


def _create(actor: Actor) -> None:
    prompts.title("Enrol an apprentice")
    payload = _ask_personal()
    print("\n  Apprenticeship")
    payload.update({
        "username": prompts.ask("Login username (blank to make one)"),
        "weekly_hours": prompts.ask_float(
            "Contracted weekly hours", default=config.OTJ_STANDARD_WEEKLY_HOURS
        ),
        "prior_learning": prompts.ask("Recognised prior learning"),
        "notes": prompts.ask("Notes"),
    })
    programme = _pick_programme(actor)
    if programme is not None:
        payload["programme_id"] = programme.programme_id
    payload.update(_ask_employer(actor))
    tutor = _pick_tutor()
    if tutor is not None:
        payload["tutor_id"] = tutor.staff_id

    try:
        created = apprentice_service.create_apprentice(actor, payload, check_duplicate=True)
    except apprentice_service.DuplicateApprentice as dup:
        prompts.fail(str(dup))
        if not prompts.ask_yes_no("Twins and common names can match. Save as a new apprentice anyway?"):
            prompts.note("Not saved. Open the existing record from 'View an apprentice'.")
            prompts.pause()
            return
        created = apprentice_service.create_apprentice(actor, payload)
    prompts.ok(f"Enrolled {created.full_name} as an applicant (id {created.apprentice_id}).")
    prompts.note("Take them onto programme with 'Start programme' once the paperwork is signed.")
    if prompts.ask_yes_no("Create their login and e-mail them a temporary password?", default=True):
        _create_login(actor, created.apprentice_id, created.full_name)
    prompts.pause()


def _create_login_menu(actor: Actor) -> None:
    summary = pick(actor)
    if not prompts.ask_yes_no(
        f"Create a login for {summary.full_name} and e-mail them a temporary password?"
    ):
        return
    _create_login(actor, summary.apprentice.apprentice_id, summary.full_name)
    prompts.pause()


def _create_login(actor: Actor, apprentice_id: int, name: str) -> None:
    """Create the login and print the sign-in details once."""
    try:
        new = account_service.create_apprentice_login(actor, apprentice_id)
    except Exception as exc:  # ValidationError / AccountError: show and carry on
        prompts.fail(f"The login could not be created: {exc}")
        prompts.note("Use 'Create a login' from the menu to try again.")
        return
    prompts.ok(f"Login created for {name}.")
    prompts.details([("Username", new.username), ("Password", new.password)])
    prompts.note("Note the password now. It won't be shown again.")
    prompts.note(new.welcome_detail)


def _edit(actor: Actor) -> None:
    summary = pick(actor)
    record = summary.apprentice
    prompts.title(f"Edit {record.full_name}")
    payload = _ask_personal(record)
    print("\n  Apprenticeship")
    payload.update({
        "username": prompts.ask("Login username", default=record.username or ""),
        "weekly_hours": prompts.ask_float("Weekly hours", default=record.weekly_hours),
        "prior_learning": prompts.ask("Prior learning", default=record.prior_learning or ""),
        "notes": prompts.ask("Notes", default=record.notes or ""),
    })
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
