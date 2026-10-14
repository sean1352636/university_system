"""Employers, their workplaces, and the managers who sign for them."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.employers.models import EmployerSummary
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import employer_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)


def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List employers", partial(_list, actor)),
        ("View an employer", partial(_view, actor)),
        ("Workplaces", partial(_workplace_menu, actor)),
        ("Managers and contacts", partial(_manager_menu, actor)),
        ("Levy position", partial(_levy, actor)),
    ]
    if actor.can("employer.manage"):
        entries.insert(2, ("Add an employer", partial(_create, actor)))
        entries.insert(3, ("Edit an employer", partial(_edit, actor)))
    if actor.is_admin:
        entries.append(("Delete an employer", partial(_delete, actor)))
    prompts.run_menu("Employers", entries)


# ═════════════════════════════════════════════════════════════════════
# Employers
# ═════════════════════════════════════════════════════════════════════

def _list(actor: Actor) -> None:
    status = prompts.choose("Status filter", config.EMPLOYER_STATUSES, allow_blank=True)
    search = prompts.ask("Name contains")
    summaries = employer_service.list_employers(actor, status=status, search=search or None)
    prompts.title("Employers")
    _table(summaries)
    prompts.pause()


def _view(actor: Actor) -> None:
    summary = _pick(actor)
    employer = summary.employer
    prompts.title(summary.name)
    prompts.details([
        ("Company number", employer.company_number),
        ("Sector", employer.sector),
        ("Size", employer.size),
        ("Headcount", employer.headcount),
        ("Pay bill", prompts.money(employer.paybill)),
        ("Levy payer", employer.is_levy_payer),
        ("Small employer", employer.is_small_employer),
        ("Default funding", employer.default_funding_model),
        ("Address", employer.address),
        ("Postcode", employer.postcode),
        ("Status", employer.status),
        ("Contract", f"{employer.contract_start or prompts.EMPTY} to "
                     f"{employer.contract_end or prompts.EMPTY}"),
        ("Contract live", employer.contract_is_current),
        ("Apprentices", f"{summary.active_apprentices} active of {summary.apprentice_count}"),
        ("Completed", summary.completed_apprentices),
        ("Withdrawn", summary.withdrawn_apprentices),
        ("Retention", prompts.EMPTY if summary.retention_rate is None
                      else f"{summary.retention_rate:.1f}%"),
        ("Hours to approve", summary.pending_otj_approvals),
        ("Reviews to sign", summary.reviews_awaiting_signature),
        ("Notes", employer.notes),
    ])

    prompts.note("\nWorkplaces:")
    _workplace_table(employer_service.list_workplaces(actor, employer.employer_id))
    prompts.note("\nContacts:")
    _manager_table(employer_service.list_managers(actor, employer.employer_id))
    prompts.pause()


def _create(actor: Actor) -> None:
    prompts.title("Add an employer")
    payload = {
        "name": prompts.ask("Employer name", required=True),
        "company_number": prompts.ask("Companies House number"),
        "sector": prompts.ask("Sector"),
        "headcount": prompts.ask_int("Headcount"),
        "paybill": prompts.ask_float("Annual pay bill"),
        "address": prompts.ask("Address"),
        "postcode": prompts.ask("Postcode"),
        "status": prompts.choose_value("Status", config.EMPLOYER_STATUSES, default="Prospect"),
        "contract_start": prompts.ask("Contract start (YYYY-MM-DD)"),
        "contract_end": prompts.ask("Contract end (YYYY-MM-DD)"),
        "notes": prompts.ask("Notes"),
    }
    created = employer_service.create_employer(actor, payload)
    prompts.ok(f"Added {created.name} (id {created.employer_id}).")
    prompts.note(f"Size band {created.size or prompts.EMPTY}, "
                 f"funding route {created.default_funding_model}.")
    prompts.pause()


def _edit(actor: Actor) -> None:
    summary = _pick(actor)
    employer = summary.employer
    prompts.title(f"Edit {employer.name}")
    payload = {
        "name": prompts.ask("Employer name", default=employer.name, required=True),
        "company_number": prompts.ask("Companies House number",
                                      default=employer.company_number or ""),
        "sector": prompts.ask("Sector", default=employer.sector or ""),
        "headcount": prompts.ask_int("Headcount", default=employer.headcount),
        "paybill": prompts.ask_float("Annual pay bill", default=employer.paybill),
        "address": prompts.ask("Address", default=employer.address or ""),
        "postcode": prompts.ask("Postcode", default=employer.postcode or ""),
        "status": prompts.choose_value("Status", config.EMPLOYER_STATUSES,
                                       default=employer.status),
        "contract_start": prompts.ask("Contract start", default=employer.contract_start or ""),
        "contract_end": prompts.ask("Contract end", default=employer.contract_end or ""),
        "notes": prompts.ask("Notes", default=employer.notes or ""),
    }
    updated = employer_service.update_employer(actor, employer.employer_id, payload)
    prompts.ok(f"Updated {updated.name}.")
    prompts.pause()


def _delete(actor: Actor) -> None:
    summary = _pick(actor, heading="Employer to delete")
    prompts.note(
        "Deleting erases the organisation, its sites and its contacts. To end the "
        "relationship, set the status to 'Ended' instead."
    )
    if not prompts.ask_yes_no(f"Really delete {summary.name}?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)

    employer_service.delete_employer(actor, summary.employer.employer_id, reason=reason)
    prompts.ok(f"Deleted {summary.name}.")
    prompts.pause()


def _levy(actor: Actor) -> None:
    summary = _pick(actor)
    position = employer_service.funding_position(actor, summary.employer.employer_id)
    prompts.title(f"Levy position — {summary.name}")
    prompts.details([
        ("Annual pay bill", prompts.money(position.paybill)),
        ("Levy payer", position.is_levy_payer),
        ("Allowance used", prompts.money(position.allowance_used)),
        ("Levy due for the year", prompts.money(position.levy_due)),
        ("Levy due monthly", prompts.money(position.monthly_levy)),
    ])
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Workplaces
# ═════════════════════════════════════════════════════════════════════

def _workplace_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List workplaces", partial(_list_workplaces, actor)),
    ]
    if actor.can("employer.manage"):
        entries += [
            ("Add a workplace", partial(_add_workplace, actor)),
            ("Edit a workplace", partial(_edit_workplace, actor)),
            ("Record a health and safety check", partial(_hs_check, actor)),
            ("Deactivate a workplace", partial(_deactivate_workplace, actor)),
        ]
    prompts.run_menu("Workplaces", entries)


def _list_workplaces(actor: Actor) -> None:
    summary = _pick(actor)
    prompts.title(f"Workplaces — {summary.name}")
    _workplace_table(employer_service.list_workplaces(actor, summary.employer.employer_id))
    prompts.pause()


def _add_workplace(actor: Actor) -> None:
    summary = _pick(actor)
    payload = {
        "name": prompts.ask("Site name", required=True),
        "address": prompts.ask("Address"),
        "postcode": prompts.ask("Postcode"),
        "hs_checked_date": prompts.ask("Health and safety checked (YYYY-MM-DD)"),
        "hs_expiry_date": prompts.ask("Check expires (YYYY-MM-DD, blank never)"),
    }
    created = employer_service.add_workplace(actor, summary.employer.employer_id, payload)
    prompts.ok(f"Added {created.name} to {summary.name}.")
    prompts.pause()


def _edit_workplace(actor: Actor) -> None:
    workplace = _pick_workplace(actor)
    payload = {
        "name": prompts.ask("Site name", default=workplace.name, required=True),
        "address": prompts.ask("Address", default=workplace.address or ""),
        "postcode": prompts.ask("Postcode", default=workplace.postcode or ""),
    }
    updated = employer_service.update_workplace(actor, workplace.workplace_id, payload)
    prompts.ok(f"Updated {updated.name}.")
    prompts.pause()


def _hs_check(actor: Actor) -> None:
    workplace = _pick_workplace(actor)
    checked = prompts.ask("Check date (YYYY-MM-DD)", required=True)
    expiry = prompts.ask("Expires (YYYY-MM-DD, blank never)")

    updated = employer_service.record_hs_check(
        actor, workplace.workplace_id, checked_date=checked, expiry_date=expiry or None
    )
    prompts.ok(f"Recorded a check on {updated.name}.")
    prompts.note(f"Usable for placements: {'yes' if updated.can_host_apprentices else 'no'}.")
    prompts.pause()


def _deactivate_workplace(actor: Actor) -> None:
    workplace = _pick_workplace(actor)
    if not prompts.ask_yes_no(f"Stop new placements at {workplace.name}?"):
        raise prompts.Abort

    updated = employer_service.deactivate_workplace(actor, workplace.workplace_id)
    prompts.ok(f"{updated.name} is no longer taking placements.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Managers
# ═════════════════════════════════════════════════════════════════════

def _manager_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List contacts", partial(_list_managers, actor)),
    ]
    if actor.can("employer.manage"):
        entries += [
            ("Add a contact", partial(_add_manager, actor)),
            ("Edit a contact", partial(_edit_manager, actor)),
            ("Set the primary signatory", partial(_set_primary, actor)),
            ("Deactivate a contact", partial(_deactivate_manager, actor)),
        ]
    prompts.run_menu("Managers and contacts", entries)


def _list_managers(actor: Actor) -> None:
    summary = _pick(actor)
    prompts.title(f"Contacts — {summary.name}")
    _manager_table(employer_service.list_managers(actor, summary.employer.employer_id))
    prompts.pause()


def _add_manager(actor: Actor) -> None:
    summary = _pick(actor)
    payload = {
        "full_name": prompts.ask("Contact name", required=True),
        "contact_role": prompts.choose("Role (blank for none)", config.EMPLOYER_CONTACT_ROLES,
                                       allow_blank=True),
        "job_title": prompts.ask("Job title"),
        "email": prompts.ask("Email"),
        "phone": prompts.ask("Phone"),
        "username": prompts.ask("Login username (links their employer portal)"),
    }
    created = employer_service.add_manager(actor, summary.employer.employer_id, payload)
    prompts.ok(f"Added {created.full_name} at {summary.name}.")
    prompts.note("Use 'Set the primary signatory' to make them the one who signs.")
    prompts.pause()


def _edit_manager(actor: Actor) -> None:
    summary, manager = _pick_manager(actor)
    prompts.note(f"Role now: {manager.contact_role or prompts.EMPTY}")
    role = prompts.choose("Role (blank keeps it)", config.EMPLOYER_CONTACT_ROLES,
                          allow_blank=True)
    payload = {
        "full_name": prompts.ask("Contact name", default=manager.full_name, required=True),
        "contact_role": role or manager.contact_role,
        "job_title": prompts.ask("Job title", default=manager.job_title or ""),
        "email": prompts.ask("Email", default=manager.email or ""),
        "phone": prompts.ask("Phone", default=manager.phone or ""),
        "username": prompts.ask("Login username", default=manager.username or ""),
    }
    updated = employer_service.update_manager(actor, manager.manager_id, payload)
    prompts.ok(f"Updated {updated.full_name} at {summary.name}.")
    prompts.pause()


def _set_primary(actor: Actor) -> None:
    summary, manager = _pick_manager(actor)
    updated = employer_service.set_primary_manager(
        actor, summary.employer.employer_id, manager.manager_id
    )
    prompts.ok(f"{updated.full_name} now signs for {summary.name}.")
    prompts.pause()


def _deactivate_manager(actor: Actor) -> None:
    _, manager = _pick_manager(actor)
    prompts.note("Their login will stop resolving to this employer.")
    if not prompts.ask_yes_no(f"Retire {manager.full_name}?"):
        raise prompts.Abort

    updated = employer_service.deactivate_manager(actor, manager.manager_id)
    prompts.ok(f"Retired {updated.full_name}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Pickers and tables
# ═════════════════════════════════════════════════════════════════════

def _pick(actor: Actor, *, heading: str = "Employer") -> EmployerSummary:
    return prompts.choose(
        heading,
        employer_service.list_employers(actor),
        render=lambda e: f"{e.name} — {e.employer.status}, {e.active_apprentices} active",
    )


def _pick_workplace(actor: Actor):
    summary = _pick(actor)
    workplaces = employer_service.list_workplaces(actor, summary.employer.employer_id)
    return prompts.choose(
        "Workplace",
        workplaces,
        render=lambda w: f"{w.name} — {w.postcode or prompts.EMPTY}"
                         + ("" if w.active else " (inactive)"),
    )


def _pick_manager(actor: Actor):
    summary = _pick(actor)
    managers = employer_service.list_managers(actor, summary.employer.employer_id)
    manager = prompts.choose(
        "Contact",
        managers,
        render=lambda m: f"{m.full_name} — {m.job_title or prompts.EMPTY}"
                         + (" (primary)" if m.is_primary else ""),
    )
    return summary, manager


def _table(summaries: list[EmployerSummary]) -> None:
    prompts.table(
        (("Employer", 28), ("Sector", 18), ("Size", 8), ("Status", 10),
         ("Active", -7), ("Total", -6), ("To approve", -11)),
        summaries,
        lambda e: (e.name, e.employer.sector, e.employer.size, e.employer.status,
                   e.active_apprentices, e.apprentice_count, e.pending_otj_approvals),
        noun="employer",
    )


def _workplace_table(workplaces: list) -> None:
    prompts.table(
        (("Site", 26), ("Postcode", 10), ("H&S checked", 13), ("H&S expires", 13),
         ("Active", 7), ("Usable", 7)),
        workplaces,
        lambda w: (w.name, w.postcode, w.hs_checked_date, w.hs_expiry_date,
                   w.active, w.can_host_apprentices),
        noun="workplace",
    )


def _manager_table(managers: list) -> None:
    prompts.table(
        (("Name", 22), ("Role", 20), ("Job title", 18), ("Email", 24), ("Login", 12),
         ("Primary", 8), ("Active", 7)),
        managers,
        lambda m: (m.full_name, m.contact_role, m.job_title, m.email, m.username,
                   m.is_primary, m.active),
        noun="contact",
    )
