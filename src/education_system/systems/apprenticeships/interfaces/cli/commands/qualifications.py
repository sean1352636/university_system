"""Qualifications and achievements.

Exposes: menu, qualifications_menu.

Provider staff record them (``qualification.manage``); the apprentice
and their employer read them.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.learner_support.qualifications import (
    Qualification,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.application.assessments import qualification_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (("Qualification", 28), ("Level", 8), ("Awarding body", 14), ("Status", 12),
            ("Grade", 6), ("Achieved", 11), ("Cert", 10), ("RPL", 4))


def menu(actor: Actor) -> None:
    """An apprentice sees their own; everyone else picks an apprentice first."""
    if actor.role == config.APPRENTICE:
        if actor.apprentice_id is None:
            prompts.fail("Your login is not linked to an apprentice record yet.")
            prompts.pause()
            return
        prompts.title("My Qualifications")
        _show(actor, actor.apprentice_id)
        prompts.pause()
        return
    summary = apprentices.pick(actor, heading="Whose qualifications?", active_only=True)
    qualifications_menu(actor, summary.apprentice.apprentice_id, summary.full_name)


def qualifications_menu(actor: Actor, apprentice_id: int, name: str) -> None:
    def view() -> None:
        prompts.title(f"Qualifications — {name}")
        _show(actor, apprentice_id)
        prompts.pause()

    entries: list[tuple[str, Callable[[], None]]] = [("View", view)]
    if actor.can("qualification.manage"):
        entries += [
            ("Add a qualification", lambda: _add(actor, apprentice_id)),
            ("Edit a qualification", lambda: _edit(actor, apprentice_id)),
            ("Delete a qualification", lambda: _delete(actor, apprentice_id)),
        ]
    prompts.run_menu(f"Qualifications — {name}", entries)


def _show(actor: Actor, apprentice_id: int) -> None:
    rows = qualification_service.list_qualifications(actor, apprentice_id=apprentice_id)
    prompts.table(
        _COLUMNS, rows,
        lambda q: (q.title, q.level, q.awarding_body, q.status, q.grade, q.achieved_date,
                   q.certificate_ref, "Yes" if q.relevant_prior_learning else ""),
        noun="qualification",
        empty="no qualifications recorded yet",
    )


def _add(actor: Actor, apprentice_id: int) -> None:
    prompts.title("Add a qualification")
    created = qualification_service.add_qualification(actor, apprentice_id, _payload(None))
    prompts.ok(f"Added “{created.title}” ({created.status}).")
    prompts.pause()


def _edit(actor: Actor, apprentice_id: int) -> None:
    qualification = _pick(actor, apprentice_id)
    updated = qualification_service.update_qualification(
        actor, qualification.qualification_id, _payload(qualification)
    )
    prompts.ok(f"Updated “{updated.title}” — {updated.status}.")
    prompts.pause()


def _delete(actor: Actor, apprentice_id: int) -> None:
    qualification = _pick(actor, apprentice_id)
    if not prompts.ask_yes_no(f"Really delete “{qualification.title}”?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)
    qualification_service.delete_qualification(
        actor, qualification.qualification_id, reason=reason
    )
    prompts.ok(f"Deleted “{qualification.title}”.")
    prompts.pause()


def _pick(actor: Actor, apprentice_id: int) -> Qualification:
    rows = qualification_service.list_qualifications(actor, apprentice_id=apprentice_id)
    if not rows:
        prompts.fail("There are no qualifications on record.")
        raise prompts.Abort
    return prompts.choose("Qualification", rows, render=lambda q: f"{q.title} — {q.status}")


def _payload(existing: Qualification | None) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(existing, attr, None) if existing is not None else None
        return "" if value is None else str(value)

    status = prompts.choose_value(
        "Status", config.QUALIFICATION_STATUSES,
        default=existing.status if existing else "In progress",
    )
    level = prompts.choose("Level (blank if not stated)", config.QUALIFICATION_LEVELS,
                           allow_blank=True)
    payload: dict[str, object] = {
        "title": prompts.ask("Qualification", default=current("title"), required=True),
        "level": level or current("level"),
        "awarding_body": prompts.ask("Awarding body", default=current("awarding_body")),
        "reference": prompts.ask("QAN / reference", default=current("reference")),
        "status": status,
        "grade": prompts.ask("Grade", default=current("grade")),
        "start_date": prompts.ask("Started (YYYY-MM-DD)", default=current("start_date")),
        "achieved_date": prompts.ask("Achieved (YYYY-MM-DD, blank for today if achieved)",
                                     default=current("achieved_date")),
        "certificate_ref": prompts.ask("Certificate reference", default=current("certificate_ref")),
        "notes": prompts.ask("Notes", default=current("notes")),
        "relevant_prior_learning": False,
    }
    if status == "Held (prior)":
        payload["relevant_prior_learning"] = prompts.ask_yes_no(
            "Counts as recognised prior learning?",
            default=bool(existing and existing.relevant_prior_learning),
        )
    return payload
