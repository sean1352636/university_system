"""Welfare and risk: the at-risk list, concerns and case notes.

Exposes: menu, apprentice_menu, concern_menu.

Provider staff only — an administrator across the provider, a tutor for
their own caseload. Formal safeguarding referrals still go to the
designated safeguarding lead; nothing here makes one.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.learner_support.welfare import (
    WelfareConcern,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import welfare_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_RISK_COLUMNS = (("Apprentice", 20), ("Tutor", 16), ("Risk", 6), ("Score", -5), ("Why", 40))
_CONCERN_COLUMNS = (("Raised", 17), ("Apprentice", 18), ("Category", 16), ("Severity", 8),
                    ("Status", 10), ("Assigned to", 16))
_NOTE_COLUMNS = (("When", 17), ("From", 24), ("Note", 50))


def menu(actor: Actor) -> None:
    if not actor.can("welfare.view"):
        prompts.fail("Welfare records are for provider staff only.")
        prompts.pause()
        return

    def one() -> None:
        summary = apprentices.pick(actor, heading="Which apprentice?", active_only=True)
        apprentice_menu(actor, summary.apprentice.apprentice_id, summary.full_name)

    entries: list[tuple[str, Callable[[], None]]] = [
        ("At-risk list", lambda: _at_risk(actor)),
        ("Open concerns", lambda: _open_concerns(actor)),
        ("An apprentice's welfare", one),
    ]
    prompts.run_menu("Welfare & Risk", entries)


def apprentice_menu(actor: Actor, apprentice_id: int, name: str) -> None:
    def profile() -> None:
        prompts.title(f"Risk profile — {name}")
        _profile(actor, apprentice_id)
        prompts.pause()

    def concerns() -> None:
        prompts.title(f"Welfare concerns — {name}")
        _concerns_table(welfare_service.list_concerns(actor, apprentice_id=apprentice_id))
        prompts.pause()

    def open_one() -> None:
        concern = _pick(welfare_service.list_concerns(actor, apprentice_id=apprentice_id))
        concern_menu(actor, concern.concern_id)

    entries: list[tuple[str, Callable[[], None]]] = [
        ("Risk profile", profile), ("Concerns", concerns), ("Open a concern", open_one),
    ]
    if actor.can("welfare.manage"):
        entries.append(("Raise a concern", lambda: _raise(actor, apprentice_id)))
    prompts.run_menu(f"Welfare — {name}", entries)


def concern_menu(actor: Actor, concern_id: int) -> None:
    def view() -> None:
        _show_concern(welfare_service.get_concern(actor, concern_id))
        prompts.pause()

    entries: list[tuple[str, Callable[[], None]]] = [("View with case notes", view)]
    if actor.can("welfare.manage"):
        entries += [
            ("Add a case note", lambda: _note(actor, concern_id)),
            ("Change status", lambda: _status(actor, concern_id)),
            ("Edit category, severity or assignee", lambda: _edit(actor, concern_id)),
        ]
    prompts.run_menu(f"Welfare concern {concern_id}", entries)


# ═════════════════════════════════════════════════════════════════════
# Lists
# ═════════════════════════════════════════════════════════════════════

def _at_risk(actor: Actor) -> None:
    prompts.title("Apprentices at risk, highest first")
    profiles = welfare_service.at_risk(actor)
    prompts.table(
        _RISK_COLUMNS, profiles,
        lambda p: (p.apprentice_name, p.tutor_name, p.level, p.score, "; ".join(p.reasons)),
        noun="apprentice",
        empty="nobody on your caseload is showing warning signs",
    )
    prompts.pause()


def _open_concerns(actor: Actor) -> None:
    prompts.title("Open welfare concerns")
    concerns = welfare_service.list_concerns(actor, open_only=True)
    _concerns_table(concerns)
    if concerns and prompts.ask_yes_no("\nOpen one?"):
        concern_menu(actor, _pick(concerns).concern_id)
    else:
        prompts.pause()


def _profile(actor: Actor, apprentice_id: int) -> None:
    profile = welfare_service.risk_profile(actor, apprentice_id)
    prompts.details([("Risk", profile.level), ("Score", profile.score)])
    if profile.reasons:
        for reason in profile.reasons:
            prompts.note(f"  - {reason}")
    else:
        prompts.note("  No warning signs at the moment.")


def _concerns_table(concerns: list[WelfareConcern]) -> None:
    prompts.table(
        _CONCERN_COLUMNS, concerns,
        lambda c: (c.raised_at, c.apprentice_name, c.category, c.severity, c.status,
                   c.assigned_name),
        noun="concern",
        empty="no concerns",
    )


def _show_concern(concern: WelfareConcern) -> None:
    prompts.title(f"{concern.category} concern — {concern.apprentice_name}")
    prompts.details([
        ("Severity", concern.severity),
        ("Status", concern.status),
        ("Raised", f"{concern.raised_at} by {concern.raised_by}"),
        ("Assigned to", concern.assigned_name),
        ("Escalated to", concern.escalated_to),
        ("Closed", concern.closed_at),
        ("Outcome", concern.outcome),
    ])
    prompts.note(f"\n  What was noticed: {concern.description}")
    prompts.note("\nCase notes, oldest first:")
    prompts.table(
        _NOTE_COLUMNS, concern.notes,
        lambda n: (n.created_at, n.author_label, n.note),
        noun="note",
        empty="no case notes yet",
    )


# ═════════════════════════════════════════════════════════════════════
# Changes
# ═════════════════════════════════════════════════════════════════════

def _raise(actor: Actor, apprentice_id: int) -> None:
    prompts.title("Raise a welfare concern")
    prompts.note("A safeguarding or Prevent concern must also go to the designated "
                 "safeguarding lead straight away.")
    owner = _pick_staff("Assigned to (blank for yourself)")
    created = welfare_service.raise_concern(actor, apprentice_id, {
        "category": prompts.choose_value("Category", config.WELFARE_CATEGORIES),
        "severity": prompts.choose_value("Severity", config.WELFARE_SEVERITIES, default="Medium"),
        "description": prompts.ask("What was noticed", required=True),
        "assigned_to": owner,
    })
    prompts.ok(f"Concern {created.concern_id} raised ({created.severity}).")
    prompts.pause()


def _note(actor: Actor, concern_id: int) -> None:
    prompts.note("Case notes cannot be edited or deleted afterwards.")
    welfare_service.add_note(actor, concern_id, prompts.ask("Case note", required=True))
    prompts.ok("Case note added.")
    prompts.pause()


def _status(actor: Actor, concern_id: int) -> None:
    concern = welfare_service.get_concern(actor, concern_id)
    choices = [s for s in config.WELFARE_STATUSES if s != concern.status]
    status = prompts.choose_value(f"Move from {concern.status} to", choices)
    escalated_to = outcome = None
    if status == "Escalated":
        escalated_to = prompts.ask("Escalated to (person or agency)", required=True)
    if status == "Closed":
        outcome = prompts.ask("Outcome", required=True)
    note = prompts.ask("Case note (optional)")
    updated = welfare_service.change_status(
        actor, concern_id, status, note=note, escalated_to=escalated_to, outcome=outcome,
    )
    prompts.ok(f"Concern is now {updated.status}.")
    prompts.pause()


def _edit(actor: Actor, concern_id: int) -> None:
    concern = welfare_service.get_concern(actor, concern_id)
    payload: dict[str, object] = {
        "category": prompts.choose_value("Category", config.WELFARE_CATEGORIES,
                                         default=concern.category),
        "severity": prompts.choose_value("Severity", config.WELFARE_SEVERITIES,
                                         default=concern.severity),
    }
    owner = _pick_staff("Assigned to (blank to keep)")
    if owner is not None:
        payload["assigned_to"] = owner
    payload["note"] = prompts.ask("Note for the case (optional)")
    welfare_service.update_concern(actor, concern_id, payload)
    prompts.ok("Concern updated; the change is in the case notes.")
    prompts.pause()


def _pick(concerns: list[WelfareConcern]) -> WelfareConcern:
    if not concerns:
        prompts.fail("There are no concerns to choose from.")
        raise prompts.Abort
    return prompts.choose(
        "Concern", concerns,
        render=lambda c: f"{c.raised_at[:10]} {c.apprentice_name} — {c.category}, "
                         f"{c.severity}, {c.status}",
    )


def _pick_staff(label: str) -> int | None:
    member = prompts.choose(
        label, staff_repository.list_all(active_only=True),
        render=lambda m: f"{m.full_name} ({m.staff_role})", allow_blank=True,
    )
    return member.staff_id if member is not None else None
