"""Individual learning plans: objectives, activities and the conversation.

Exposes: menu, my_plan.

Staff build the plan and record progress; the apprentice and their
employer read it and comment. The activities themselves are training
plan items, maintained through :func:`training.plan_menu`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records import signatures as sig_rules
from education_system.systems.apprenticeships.domain.training.learning_plan import (
    LearningObjective,
    LearningPlan,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import (
    apprentices,
    signatures,
    training,
)
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import learning_plan_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_OBJECTIVE_COLUMNS = (
    ("Objective", 30), ("KSBs", 12), ("Target", 11), ("Status", 22), ("Done", -5),
)
_ACTIVITY_COLUMNS = (
    ("Activity", 28), ("Delivers", 24), ("From", 11), ("To", 11), ("Hours", -6), ("Status", 12),
)
_COMMENT_COLUMNS = (("When", 17), ("From", 24), ("About", 20), ("%", -4), ("Comment", 40))
_REVIEW_COLUMNS = (("Date", 11), ("Status", 20), ("Rating", 8), ("Conducted by", 20),
                   ("Summary", 30))


def menu(actor: Actor) -> None:
    """Pick an apprentice, then work on their plan."""
    summary = apprentices.pick(actor, heading="Whose learning plan?", active_only=True)
    plan_menu(actor, summary.apprentice.apprentice_id, summary.full_name)


def my_plan(actor: Actor) -> None:
    """The signed-in apprentice's plan, timetable and attendance."""
    summary = apprentice_service.get_own_record(actor)
    if summary is None:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    apprentice_id = summary.apprentice.apprentice_id
    prompts.title("My Learning Plan")
    prompts.note("What you will achieve, how, and by when.")
    _show(actor, apprentice_id)

    prompts.note("\nUpcoming sessions:")
    training.show_upcoming(actor, summary.apprentice.programme_id)
    training.show_attendance(actor, apprentice_id)

    if _awaits_my_signature(actor, apprentice_id) and prompts.ask_yes_no(
        "\nYour plan is waiting for your signature. Sign it now?"
    ):
        prompts.run_action(lambda: _sign(actor, apprentice_id))
    if actor.can("plan.comment") and prompts.ask_yes_no("\nAdd a comment to your plan?"):
        _comment(actor, apprentice_id)
    else:
        prompts.pause()


def plan_menu(actor: Actor, apprentice_id: int, name: str) -> None:
    """Everything this actor may do with one apprentice's plan."""
    def view() -> None:
        prompts.title(f"Learning plan — {name}")
        _show(actor, apprentice_id)
        prompts.pause()

    entries: list[tuple[str, Callable[[], None]]] = [("View the plan", view)]
    if actor.can("training.manage"):
        entries += [
            ("Add an objective", lambda: _add_objective(actor, apprentice_id)),
            ("Edit an objective", lambda: _edit_objective(actor, apprentice_id)),
            ("Record progress", lambda: _record_progress(actor, apprentice_id)),
            ("Delete an objective", lambda: _delete_objective(actor, apprentice_id)),
            ("Activities", lambda: training.plan_menu(actor, apprentice_id, name)),
        ]
    if actor.can("plan.comment"):
        entries.append(("Add a comment", lambda: _comment(actor, apprentice_id)))
    if actor.can("signature.sign"):
        entries.append(("Sign the plan", lambda: _sign(actor, apprentice_id)))
    if actor.can("review.view"):
        entries.append(("Review history", lambda: _reviews(actor, apprentice_id)))
    prompts.run_menu(f"Learning plan — {name}", entries)


# ═════════════════════════════════════════════════════════════════════
# Sign-off
# ═════════════════════════════════════════════════════════════════════

def _sign(actor: Actor, apprentice_id: int) -> None:
    """Sign the plan as it stands, as this login's signatory."""
    state = learning_plan_service.plan_signatures(actor, apprentice_id)
    prompts.title("Sign the plan")
    signatures.show_signoff(state)
    signatory = sig_rules.signatory_for(actor.role)
    if state.state(signatory or "") == sig_rules.SIGNED:
        prompts.ok(f"You have already signed this plan as {signatory}, as it stands now.")
        prompts.pause()
        return
    prompts.note(
        f"\nYou are signing as {signatory}. The signature covers the objectives and "
        "activities as they are now; if either changes afterwards, it lapses and the plan "
        "needs signing again."
    )
    statement = prompts.ask("Statement", default=config.SIGNATURE_DEFAULT_STATEMENT)
    if not prompts.ask_yes_no("Sign the plan now?", default=True):
        raise prompts.Abort
    learning_plan_service.sign_plan(actor, apprentice_id, statement=statement)
    prompts.ok(f"Signed as {signatory}.")
    prompts.pause()


def _awaits_my_signature(actor: Actor, apprentice_id: int) -> bool:
    if not actor.can("signature.sign"):
        return False
    try:
        state = learning_plan_service.plan_signatures(actor, apprentice_id)
        plan = learning_plan_service.get_plan(actor, apprentice_id)
    except Exception:
        logger.debug("Could not read plan sign-off", exc_info=True)
        return False
    signatory = sig_rules.signatory_for(actor.role)
    return bool(plan.objectives or plan.activities) and signatory in state.required and (
        state.state(signatory) != sig_rules.SIGNED
    )


# ═════════════════════════════════════════════════════════════════════
# Showing the plan
# ═════════════════════════════════════════════════════════════════════

def _show(actor: Actor, apprentice_id: int) -> None:
    plan = learning_plan_service.get_plan(actor, apprentice_id)
    today = date.today()
    upcoming = plan.next_target(today)
    prompts.details([
        ("Overall progress", f"{plan.overall_progress:.0f}%  {prompts.bar(plan.overall_progress)}"),
        ("Objectives", len(plan.counted_objectives)),
        ("Achieved", plan.achieved),
        ("Overdue", len(plan.overdue(today))),
        ("Next target", f"{upcoming.target_date} — {upcoming.title}" if upcoming else "—"),
    ])

    prompts.note("\nObjectives:")
    prompts.table(
        _OBJECTIVE_COLUMNS,
        plan.objectives,
        lambda o: (
            o.title, o.ksb_codes, o.target_date,
            o.status + (" (overdue)" if o.is_overdue(today) else ""), f"{o.progress}%",
        ),
        noun="objective",
        empty="no objectives have been set yet",
    )

    titles = {o.objective_id: o.title for o in plan.objectives}
    prompts.note("\nActivities:")
    prompts.table(
        _ACTIVITY_COLUMNS,
        plan.activities,
        lambda i: (i.title, titles.get(i.objective_id, "—"), i.planned_start,
                   i.planned_end, i.planned_hours, i.status),
        noun="activity",
        empty="no activities are planned yet",
    )

    if plan.objectives or plan.activities:
        signatures.show_signoff(learning_plan_service.plan_signatures(actor, apprentice_id))

    prompts.note("\nComments, newest first:")
    prompts.table(
        _COMMENT_COLUMNS,
        plan.comments[:15],
        lambda c: (c.created_at, c.author_label, titles.get(c.objective_id, "Whole plan"),
                   c.progress if c.progress is not None else "", c.body),
        noun="comment",
        empty="nobody has commented yet",
    )


def _reviews(actor: Actor, apprentice_id: int) -> None:
    prompts.title("Review history")
    prompts.table(
        _REVIEW_COLUMNS,
        learning_plan_service.review_history(actor, apprentice_id),
        lambda r: (r.held_date or r.scheduled_date, r.status, r.progress_rating,
                   r.conductor_name, r.summary),
        noun="review",
        empty="no progress reviews yet",
    )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Changing the plan
# ═════════════════════════════════════════════════════════════════════

def _add_objective(actor: Actor, apprentice_id: int) -> None:
    prompts.title("Add an objective")
    created = learning_plan_service.add_objective(actor, apprentice_id, _objective_payload(None))
    prompts.ok(f"Added “{created.title}”.")
    prompts.pause()


def _edit_objective(actor: Actor, apprentice_id: int) -> None:
    objective = _pick_objective(learning_plan_service.get_plan(actor, apprentice_id))
    updated = learning_plan_service.update_objective(
        actor, objective.objective_id, _objective_payload(objective)
    )
    prompts.ok(f"Updated “{updated.title}” — {updated.status}, {updated.progress}%.")
    prompts.pause()


def _record_progress(actor: Actor, apprentice_id: int) -> None:
    objective = _pick_objective(learning_plan_service.get_plan(actor, apprentice_id))
    prompts.note(f"“{objective.title}” is at {objective.progress}% ({objective.status}).")
    progress = prompts.ask_int("New progress %", default=objective.progress, required=True)
    status = prompts.choose(
        "Status (blank works it out from the progress)", config.OBJECTIVE_STATUSES,
        allow_blank=True,
    )
    comment = prompts.ask("What has changed")
    updated = learning_plan_service.record_progress(
        actor, objective.objective_id, progress=progress, status=status, comment=comment,
    )
    prompts.ok(f"“{updated.title}” is now {updated.progress}% — {updated.status}.")
    prompts.pause()


def _delete_objective(actor: Actor, apprentice_id: int) -> None:
    objective = _pick_objective(learning_plan_service.get_plan(actor, apprentice_id))
    prompts.note(
        "Deleting is for an objective set by mistake; its activities and comments stay on "
        "the plan. For one that no longer applies, edit it to Withdrawn instead."
    )
    if not prompts.ask_yes_no(f"Really delete “{objective.title}”?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)
    learning_plan_service.delete_objective(actor, objective.objective_id, reason=reason)
    prompts.ok(f"Deleted “{objective.title}”.")
    prompts.pause()


def _comment(actor: Actor, apprentice_id: int) -> None:
    plan = learning_plan_service.get_plan(actor, apprentice_id)
    about = None
    if plan.objectives:
        about = prompts.choose(
            "About which objective? (blank for the plan as a whole)", plan.objectives,
            render=lambda o: f"{o.title} — {o.status}", allow_blank=True,
        )
    body = prompts.ask("Comment", required=True)
    learning_plan_service.add_comment(
        actor, apprentice_id, body, objective_id=about.objective_id if about else None,
    )
    prompts.ok("Comment added to the plan.")
    prompts.pause()


def _pick_objective(plan: LearningPlan) -> LearningObjective:
    if not plan.objectives:
        prompts.fail("There are no objectives on this plan yet.")
        raise prompts.Abort
    return prompts.choose(
        "Objective", plan.objectives,
        render=lambda o: f"{o.title} — {o.status}, {o.progress}%",
    )


def _objective_payload(objective: LearningObjective | None) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(objective, attr, None) if objective is not None else None
        return "" if value is None else str(value)

    return {
        "title": prompts.ask("Objective", default=current("title"), required=True),
        "description": prompts.ask("Description", default=current("description")),
        "ksb_codes": prompts.ask("KSBs (comma-separated)", default=current("ksb_codes")),
        "target_date": prompts.ask("Target date (YYYY-MM-DD)", default=current("target_date")),
        "status": prompts.choose_value(
            "Status", config.OBJECTIVE_STATUSES,
            default=objective.status if objective else "Not started",
        ),
        "progress": prompts.ask_int(
            "Progress %", default=objective.progress if objective else 0
        ),
    }
