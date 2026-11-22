"""Action plans: the actions agreed at progress reviews, and moving them along.

Exposes: menu.

The same screen for every role that owns actions. What the menu offers
follows the actor's permissions: owners update status and add notes;
provider staff who conduct reviews also add, edit and carry actions.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.reviews.action_plans import CARRIED_FORWARD
from education_system.systems.apprenticeships.domain.reviews.progress_reviews import ReviewTarget
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.learning import (
    action_plan_service,
    review_service,
)
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("Apprentice", 18), ("Action", 34), ("Owner", 10), ("Priority", 8), ("Due", 11),
    ("Status", 20), ("Review", 11), ("Carried", -7),
)
_NOTE_COLUMNS = (("When", 19), ("From", 24), ("Status change", 22), ("Note", 40))

_HAND_STATUSES = tuple(s for s in config.TARGET_STATUSES if s != CARRIED_FORWARD)


def menu(actor: Actor) -> None:
    if (actor.role == config.APPRENTICE and actor.apprentice_id is None) or (
        actor.role == config.EMPLOYER and actor.employer_id is None
    ):
        prompts.fail("Your login is not linked to a record in this system yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    entries: list[tuple[str, Callable[[], None]]] = [
        ("What is due or overdue", partial(_due, actor)),
        ("List actions", partial(_list, actor)),
        ("An action's history", partial(_history, actor)),
    ]
    if actor.can("action.update"):
        entries += [
            ("Update an action's status", partial(_update_status, actor)),
            ("Add a progress note", partial(_add_note, actor)),
        ]
    if actor.can("review.conduct"):
        entries += [
            ("Add an action to a review", partial(_add, actor)),
            ("Edit an action", partial(_edit, actor)),
            ("Carry an action to the next review", partial(_carry, actor)),
        ]
    prompts.run_menu("Action Plans", entries)


# ═════════════════════════════════════════════════════════════════════
# Reading
# ═════════════════════════════════════════════════════════════════════

def _due(actor: Actor) -> None:
    summary = action_plan_service.action_summary(actor)
    rows = action_plan_service.list_actions(
        actor, due_within_days=config.ACTION_DUE_SOON_DAYS
    )
    prompts.title("Due or overdue")
    prompts.details([
        ("Open actions", summary["open"]),
        ("Overdue", summary["overdue"]),
        (f"Due within {config.ACTION_DUE_SOON_DAYS} days", summary["due_soon"]),
        ("Carried forward at least once", summary["carried"]),
    ])
    _table(rows, empty="nothing is due or overdue")
    prompts.pause()


def _list(actor: Actor) -> None:
    status = prompts.choose("Status filter", config.TARGET_STATUSES, allow_blank=True)
    owner = prompts.choose("Owner filter", config.ACTION_OWNERS, allow_blank=True)
    overdue = status is None and prompts.ask_yes_no("Overdue only?")
    mine = owner is None and prompts.ask_yes_no("Only the actions you own?")
    rows = action_plan_service.list_actions(
        actor, status=status, owner=owner, overdue_only=overdue, mine_only=mine,
    )
    if status is None:
        # A carried-forward action lives on as its copy on the later
        # review; listing both would show every slipped action twice.
        rows = [r for r in rows if r.status != CARRIED_FORWARD]
    prompts.title("Actions")
    _table(rows)
    prompts.pause()


def _history(actor: Actor) -> None:
    target = _pick(actor, open_only=False)
    notes = action_plan_service.history(actor, target.target_id)
    prompts.title(f"History — {target.description[:50]}")
    prompts.details([
        ("Apprentice", target.apprentice_name),
        ("Owner", target.owner),
        ("Priority", target.priority),
        ("Due", target.due_date),
        ("Status", target.status),
        ("Carried forward", f"{target.carry_count} time(s)" if target.carry_count else "No"),
        ("Outcome note", target.outcome_note),
    ])
    prompts.table(
        _NOTE_COLUMNS,
        notes,
        lambda n: (n.created_at, n.author_label,
                   f"{n.from_status} -> {n.to_status}" if n.is_status_change else "", n.body),
        noun="entry",
        empty="nobody has added a note or moved this action yet",
    )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Moving actions along
# ═════════════════════════════════════════════════════════════════════

def _update_status(actor: Actor) -> None:
    target = _pick(actor, updatable_only=True, open_only=False)
    prompts.note(f"“{target.description}” is {target.status}.")
    status = prompts.choose_value(
        "New status", tuple(s for s in _HAND_STATUSES if s != target.status)
    )
    note = prompts.ask("What has happened (kept in the history)")
    updated = action_plan_service.update_status(
        actor, target.target_id, status=status, note=note or None
    )
    prompts.ok(f"Now {updated.status}.")
    prompts.pause()


def _add_note(actor: Actor) -> None:
    target = _pick(actor, updatable_only=True)
    body = prompts.ask("Progress note", required=True)
    action_plan_service.add_note(actor, target.target_id, body)
    prompts.ok("Note added.")
    prompts.pause()


def _add(actor: Actor) -> None:
    reviews = action_plan_service.reviews_taking_actions(actor)
    if not reviews:
        prompts.fail("There is no open review to add an action to. Schedule one first.")
        prompts.pause()
        return
    review = prompts.choose(
        "Review the action was agreed at", reviews,
        render=lambda r: f"{r.apprentice_name} — {r.held_date or r.scheduled_date} ({r.status})",
    )
    created = action_plan_service.add_action(actor, review.review_id, _payload(None))
    prompts.ok(f"Added for the {created.owner.lower()}, due {created.due_date or 'no date'}.")
    prompts.pause()


def _edit(actor: Actor) -> None:
    target = _pick(actor)
    updated = review_service.update_target(actor, target.target_id, _payload(target))
    prompts.ok(f"Updated: {updated.description[:60]}")
    prompts.pause()


def _carry(actor: Actor) -> None:
    target = _pick(actor)
    prompts.note(
        "The action closes here as Carried Forward and a copy opens on the apprentice's "
        "next review. Open actions are also carried automatically when a review starts."
    )
    if not prompts.ask_yes_no(f"Carry “{target.description[:50]}” forward now?"):
        raise prompts.Abort
    action_plan_service.carry_to_next_review(actor, target.target_id)
    prompts.ok("Carried onto the next review.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def _table(rows: list[ReviewTarget], *, empty: str | None = None) -> None:
    today = date.today()
    prompts.table(
        _COLUMNS,
        rows,
        lambda t: (
            t.apprentice_name, t.description, t.owner, t.priority, t.due_date,
            t.status + (" (overdue)" if t.overdue_on(today) else
                        " (due soon)" if t.is_due_soon(today) else ""),
            t.review_date, t.carry_count or "",
        ),
        noun="action",
        empty=empty,
    )


def _pick(actor: Actor, *, updatable_only: bool = False, open_only: bool = True) -> ReviewTarget:
    rows = action_plan_service.list_actions(actor, open_only=open_only)
    if not open_only:
        rows = [r for r in rows if r.status != CARRIED_FORWARD] + [
            r for r in rows if r.status == CARRIED_FORWARD
        ]
    if updatable_only:
        rows = [r for r in rows if action_plan_service.may_update(actor, r)]
        if not rows:
            prompts.fail("There are no actions you can update.")
            prompts.note("You may move only the actions you own.")
            raise prompts.Abort
    return prompts.choose(
        "Action", rows,
        render=lambda t: (
            f"{t.apprentice_name} — {t.description[:50]} "
            f"({t.owner}, {t.status}{', due ' + t.due_date if t.due_date else ''})"
        ),
    )


def _payload(target: ReviewTarget | None) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(target, attr, None) if target is not None else None
        return "" if value is None else str(value)

    return {
        "description": prompts.ask("Action", default=current("description"), required=True),
        "owner": prompts.choose_value(
            "Owner", config.ACTION_OWNERS,
            default=target.owner if target else config.ACTION_DEFAULT_OWNER,
        ),
        "priority": prompts.choose_value(
            "Priority", config.ACTION_PRIORITIES,
            default=target.priority if target else config.ACTION_DEFAULT_PRIORITY,
        ),
        "due_date": prompts.ask("Due date (YYYY-MM-DD)", default=current("due_date")),
        "ksb_codes": prompts.ask("KSBs (comma-separated)", default=current("ksb_codes")),
    }
