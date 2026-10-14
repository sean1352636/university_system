"""Appeals: lodge and follow your own, or hear the ones routed to you.

Exposes: menu.

An apprentice lodges, follows and withdraws their own appeals. The
provider admin hears every type except EPA results; the end-point
assessor hears EPA results only. The service enforces that routing; the
menu offers each actor only the actions it will allow.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.quality import appeals as rules
from education_system.systems.apprenticeships.domain.quality.appeals import Appeal
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.services import appeal_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (("Ref", 8), ("Apprentice", 18), ("Type", 19), ("Against", 28), ("Lodged", 10),
            ("Decide by", 10), ("Status", 16))


def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = []
    if actor.role == config.APPRENTICE:
        entries += [
            ("My appeals", partial(_list, actor)),
            ("Open one of my appeals", partial(_open, actor)),
            ("Lodge an appeal", partial(_lodge, actor)),
        ]
    elif actor.can("appeal.decide"):
        heard = ("EPA-result appeals" if actor.role == config.END_POINT_ASSESSOR
                 else "Appeals against provider decisions")
        entries += [
            (f"Open {heard[0].lower()}{heard[1:]}", partial(_list, actor, open_only=True)),
            ("Overdue appeals", partial(_list, actor, overdue_only=True)),
            ("Every appeal", partial(_list, actor)),
            ("Open an appeal", partial(_open, actor)),
        ]
    prompts.run_menu("Appeals", entries)


def _list(actor: Actor, **filters: object) -> None:
    prompts.title("Appeals")
    if actor.role == config.ADMIN:
        prompts.note("Appeals against EPA results are heard by the End-Point Assessment "
                     "Organisation and are not shown here.")
    today = date.today()
    prompts.table(
        _COLUMNS,
        appeal_service.list_appeals(actor, **filters),  # type: ignore[arg-type]
        lambda a: (a.reference, a.apprentice_name, a.appeal_type, a.decision_ref, a.lodged_at,
                   a.deadline, a.status + (" (late)" if a.is_overdue(today) else "")),
        noun="appeal",
    )
    prompts.pause()


def _show(appeal: Appeal) -> None:
    prompts.title(f"{appeal.reference} — {appeal.appeal_type}")
    prompts.details([
        ("Status", appeal.status),
        ("Apprentice", appeal.apprentice_name),
        ("Heard by", appeal.decider_label),
        ("Against", appeal.decision_ref),
        ("Decision made", appeal.decision_date),
        ("Lodged", appeal.lodged_at),
        ("Decide by", appeal.deadline),
        ("Decided by", appeal.decided_by),
        ("Decided", appeal.decided_at),
    ])
    prompts.note("\nGrounds:")
    prompts.note(appeal.grounds)
    if appeal.decision:
        prompts.note("\nReason for withdrawal:" if appeal.status == "Withdrawn" else "\nDecision:")
        prompts.note(appeal.decision)


def _open(actor: Actor) -> None:
    rows = appeal_service.list_appeals(actor)
    if not rows:
        prompts.fail("There are no appeals to show.")
        raise prompts.Abort
    appeal = prompts.choose("Appeal", rows,
                            render=lambda a: f"{a.reference}  {a.appeal_type} — {a.status}")
    _show(appeal)

    actions: dict[str, Callable[[], None]] = {}
    if appeal.is_open and appeal_service.may_decide(actor, appeal):
        if appeal.status == "Lodged":
            actions["Start review"] = lambda: _done(
                appeal_service.start_review(actor, appeal.appeal_id))
        actions["Decide"] = lambda: _decide(actor, appeal)
    if (appeal.is_open and actor.role == config.APPRENTICE
            and appeal.apprentice_id == actor.apprentice_id):
        actions["Withdraw"] = lambda: _withdraw(actor, appeal)
    if not actions:
        prompts.pause()
        return
    chosen = prompts.choose("Do what?", list(actions), allow_blank=True)
    if chosen is not None:
        actions[chosen]()
        prompts.pause()


def _lodge(actor: Actor) -> None:
    prompts.title("Lodge an appeal")
    prompts.note(f"Appeals must be lodged within {config.APPEAL_WINDOW_DAYS} days of the "
                 "decision. EPA results go to the End-Point Assessment Organisation; "
                 "everything else to your training provider.")
    appeal_type = prompts.choose_value("What are you appealing?", config.APPEAL_TYPES)
    payload: dict[str, object] = {"appeal_type": appeal_type}
    if rules.is_epa_result(appeal_type):
        results = appeal_service.appealable_epa_results(actor)
        if not results:
            prompts.fail(f"You have no EPA results from the last {config.APPEAL_WINDOW_DAYS} "
                         "days to appeal.")
            raise prompts.Abort
        result = prompts.choose(
            "EPA result", results,
            render=lambda r: f"{r.method}: {r.grade} — assessed {r.assessed_date} "
                             f"(attempt {r.attempt})",
        )
        payload["result_id"] = result.result_id
    else:
        payload["decision_ref"] = prompts.ask("The decision you are appealing", required=True)
        payload["decision_date"] = prompts.ask("Date of the decision (YYYY-MM-DD)",
                                               required=True)
    payload["grounds"] = prompts.ask("Why you are appealing", required=True)
    created = appeal_service.lodge(actor, payload)
    prompts.ok(f"{created.reference} lodged. A decision is due by {created.deadline}.")
    prompts.pause()


def _decide(actor: Actor, appeal: Appeal) -> None:
    outcome = prompts.choose_value("Outcome", rules.DECISION_STATUSES)
    reasons = prompts.ask("Reasons (the apprentice reads this)", required=True)
    _done(appeal_service.decide(actor, appeal.appeal_id, outcome=outcome, decision=reasons))


def _withdraw(actor: Actor, appeal: Appeal) -> None:
    if not prompts.ask_yes_no(f"Withdraw {appeal.reference}? This cannot be undone."):
        raise prompts.Abort
    reason = prompts.ask("Why (optional)")
    _done(appeal_service.withdraw(actor, appeal.appeal_id, reason=reason or None))


def _done(appeal: Appeal) -> None:
    prompts.ok(f"{appeal.reference} is now {appeal.status}.")
