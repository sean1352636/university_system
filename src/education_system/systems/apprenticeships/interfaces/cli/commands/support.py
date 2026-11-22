"""Reasonable adjustments and support arrangements.

Exposes: menu, support_menu.

Provider staff agree and review arrangements; the apprentice sees all of
their own; an employer only those shared with them, without the history.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.learner_support.support_arrangements import (
    SupportArrangement,
)
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.application.support import support_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (("Need", 20), ("Adjustment", 30), ("Responsible", 16), ("Review", 12),
            ("Status", 12), ("Shared", 6))
_DUE_COLUMNS = (("Apprentice", 20), ("Need", 20), ("Adjustment", 26), ("Review", 12),
                ("Responsible", 16))
_NOTE_COLUMNS = (("When", 17), ("Arrangement", 24), ("From", 22), ("Note", 36))


def menu(actor: Actor) -> None:
    if actor.role == config.APPRENTICE:
        if actor.apprentice_id is None:
            prompts.fail("Your login is not linked to an apprentice record yet.")
            prompts.pause()
            return
        prompts.title("My Support & Adjustments")
        _show(actor, actor.apprentice_id)
        prompts.pause()
        return

    def one() -> None:
        summary = apprentices.pick(actor, heading="Whose support?", active_only=True)
        support_menu(actor, summary.apprentice.apprentice_id, summary.full_name)

    entries: list[tuple[str, Callable[[], None]]] = [("An apprentice's support", one)]
    if actor.can("support.manage"):
        entries.insert(0, ("Reviews overdue or due soon", lambda: _due(actor)))
    prompts.run_menu("Support & Adjustments", entries)


def support_menu(actor: Actor, apprentice_id: int, name: str) -> None:
    def view() -> None:
        prompts.title(f"Support — {name}")
        _show(actor, apprentice_id)
        prompts.pause()

    entries: list[tuple[str, Callable[[], None]]] = [("View", view)]
    if actor.can("support.manage"):
        entries += [
            ("Add an arrangement", lambda: _add(actor, apprentice_id)),
            ("Edit an arrangement", lambda: _edit(actor, apprentice_id)),
            ("Record a review", lambda: _review(actor, apprentice_id)),
            ("Add a note", lambda: _note(actor, apprentice_id)),
            ("Delete an arrangement", lambda: _delete(actor, apprentice_id)),
        ]
    prompts.run_menu(f"Support — {name}", entries)


def _due(actor: Actor) -> None:
    prompts.title("Support reviews overdue or due soon")
    today = date.today()
    prompts.table(
        _DUE_COLUMNS, support_service.due_for_review(actor),
        lambda a: (a.apprentice_name, a.need_category, a.adjustment,
                   (a.review_date or "") + (" OVERDUE" if a.is_review_overdue(today) else ""),
                   a.responsible_staff_name),
        noun="arrangement",
        empty="nothing is due for review",
    )
    prompts.pause()


def _show(actor: Actor, apprentice_id: int) -> None:
    record = support_service.get_record(actor, apprentice_id)
    today = date.today()
    if actor.role != config.EMPLOYER:
        prompts.details([("Support needs at enrolment", record.support_needs or "none recorded")])
    prompts.table(
        _COLUMNS, record.arrangements,
        lambda a: (a.need_category, a.adjustment, a.responsible_staff_name,
                   (a.review_date or "") + (" OVERDUE" if a.is_review_overdue(today) else ""),
                   a.status, a.share_with_employer),
        noun="arrangement",
        empty="no arrangements shared with you" if actor.role == config.EMPLOYER
        else "no arrangements recorded",
    )
    for arrangement in record.arrangements:
        if arrangement.arrangements:
            prompts.note(f"  {arrangement.need_category}: {arrangement.arrangements}")
    notes = [(n, a) for a in record.arrangements for n in a.notes]
    if notes:
        notes.sort(key=lambda pair: (pair[0].created_at, pair[0].note_id), reverse=True)
        prompts.note("\nHistory, newest first:")
        prompts.table(
            _NOTE_COLUMNS, notes,
            lambda pair: (pair[0].created_at, pair[1].adjustment, pair[0].author_label,
                          pair[0].body),
            noun="note",
        )


def _add(actor: Actor, apprentice_id: int) -> None:
    prompts.title("Add an arrangement")
    created = support_service.add_arrangement(actor, apprentice_id, _payload(None))
    prompts.ok(f"Added — review by {created.review_date}.")
    prompts.pause()


def _edit(actor: Actor, apprentice_id: int) -> None:
    arrangement = _pick(actor, apprentice_id)
    payload = _payload(arrangement)
    payload["note"] = prompts.ask("Note for the history (optional)")
    support_service.update_arrangement(actor, arrangement.arrangement_id, payload)
    prompts.ok("Arrangement updated.")
    prompts.pause()


def _review(actor: Actor, apprentice_id: int) -> None:
    arrangement = _pick(actor, apprentice_id)
    outcome = prompts.ask("What the review found", required=True)
    status = prompts.choose_value("Status", config.SUPPORT_STATUSES, default=arrangement.status)
    next_date = None
    if status != "Ended":
        next_date = prompts.ask("Next review by (YYYY-MM-DD)", required=True)
    updated = support_service.record_review(
        actor, arrangement.arrangement_id, outcome=outcome,
        next_review_date=next_date, status=status,
    )
    prompts.ok(f"Review recorded — {updated.status}"
               + (f", next by {updated.review_date}." if updated.review_date else "."))
    prompts.pause()


def _note(actor: Actor, apprentice_id: int) -> None:
    arrangement = _pick(actor, apprentice_id)
    support_service.add_note(actor, arrangement.arrangement_id,
                             prompts.ask("Note", required=True))
    prompts.ok("Note added.")
    prompts.pause()


def _delete(actor: Actor, apprentice_id: int) -> None:
    arrangement = _pick(actor, apprentice_id)
    prompts.note("Deleting is for an arrangement recorded by mistake. For one that no "
                 "longer applies, edit it to Ended instead.")
    if not prompts.ask_yes_no("Really delete it?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)
    support_service.delete_arrangement(actor, arrangement.arrangement_id, reason=reason)
    prompts.ok("Arrangement deleted.")
    prompts.pause()


def _pick(actor: Actor, apprentice_id: int) -> SupportArrangement:
    rows = support_service.list_arrangements(actor, apprentice_id=apprentice_id)
    if not rows:
        prompts.fail("There are no arrangements on record.")
        raise prompts.Abort
    return prompts.choose(
        "Arrangement", rows,
        render=lambda a: f"{a.need_category}: {a.adjustment} — {a.status}",
    )


def _payload(existing: SupportArrangement | None) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(existing, attr, None) if existing is not None else None
        return "" if value is None else str(value)

    staff = staff_repository.list_all(active_only=True)
    owner = prompts.choose(
        "Responsible (blank for yourself)" if existing is None else "Responsible (blank to keep)",
        staff, render=lambda m: f"{m.full_name} ({m.staff_role})", allow_blank=True,
    )
    payload: dict[str, object] = {
        "need_category": prompts.choose_value(
            "Need", config.SUPPORT_NEED_CATEGORIES, default=current("need_category") or None,
        ),
        "adjustment": prompts.ask("Adjustment", default=current("adjustment"), required=True),
        "arrangements": prompts.ask("How it is delivered", default=current("arrangements")),
        "review_date": prompts.ask("Review by (YYYY-MM-DD)", default=current("review_date")),
        "status": prompts.choose_value(
            "Status", config.SUPPORT_STATUSES, default=current("status") or "Active",
        ),
        "share_with_employer": prompts.ask_yes_no(
            "Share with the employer (only with the apprentice's agreement)?",
            default=bool(existing and existing.share_with_employer),
        ),
    }
    if owner is not None:
        payload["responsible_staff_id"] = owner.staff_id
    return payload
