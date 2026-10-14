"""Tripartite progress reviews: scheduling, recording, signing, targets.

Exposes: menu, my_menu, feedback_menu.

Signing is the whole point of the module and the reason the menus look
the way they do. A review is worth nothing as funding evidence until the
provider, the apprentice and the employer have all signed, and each may
only sign their own line — so every screen shows who is still missing
rather than a bare status, and the sign command never asks which party
you are.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import review_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_REVIEW_COLUMNS = (
    ("Apprentice", 22), ("Scheduled", 12), ("Held", 12), ("Status", 19),
    ("Rating", 8), ("Still to sign", 26),
)

_TARGET_COLUMNS = (
    ("Due", 12), ("Target", 38), ("Owner", 10), ("Pri", 6), ("KSBs", 12), ("Status", 16),
    ("Outcome", 22),
)

_FEEDBACK_COLUMNS = (
    ("When", 20), ("Employer", 24), ("Satisfaction", 18), ("Comments", 34),
)


# ═════════════════════════════════════════════════════════════════════
# The provider's view
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("What needs attention", partial(_queue, actor)),
        ("List reviews", partial(_list, actor)),
        ("View a review", partial(_view, actor)),
        ("Targets", partial(_target_menu, actor)),
    ]
    if actor.can("review.conduct"):
        entries += [
            ("Schedule a review", partial(_schedule, actor)),
            ("Schedule the next one", partial(_schedule_next, actor)),
            ("Start a review", partial(_start, actor)),
            ("Record the outcome", partial(_record, actor)),
            ("Mark one as missed", partial(_missed, actor)),
        ]
    if actor.can("review.sign"):
        entries.append((f"Sign as {_signatory_label(actor)}", partial(_sign, actor)))
    if actor.is_admin:
        entries.append(("Remove a signature", partial(_unsign, actor)))
    if actor.can("review.feedback") or actor.can("review.view"):
        entries.append(("Employer feedback", partial(feedback_menu, actor)))
    prompts.run_menu("Progress Reviews", entries)


def _queue(actor: Actor) -> None:
    queue = review_service.review_queue(actor)
    prompts.title("Reviews needing attention")

    prompts.note("\nOverdue:")
    _review_table(queue["overdue"], empty="nothing overdue")
    prompts.note("\nAwaiting signatures:")
    _review_table(queue["awaiting_signature"], empty="nothing waiting on a signature")
    prompts.note("\nComing up:")
    _review_table(queue["upcoming"], empty="nothing in the diary")
    prompts.pause()


def _list(actor: Actor) -> None:
    summary = apprentices.pick(actor) if prompts.ask_yes_no("Filter to one apprentice?") else None
    status = prompts.choose("Status filter", config.REVIEW_STATUSES, allow_blank=True)
    overdue = status is None and prompts.ask_yes_no("Overdue only?")

    rows = review_service.list_reviews(
        actor,
        apprentice_id=summary.apprentice.apprentice_id if summary else None,
        status=status, overdue_only=overdue, with_children=True,
    )
    prompts.title("Progress reviews")
    _review_table(rows)
    prompts.pause()


def _view(actor: Actor) -> None:
    show_review(review_service.get_review(actor, _pick(actor).review_id))
    prompts.pause()


def _schedule(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Whose review?")
    when = prompts.ask(
        "Scheduled date (YYYY-MM-DD)", default=date.today().isoformat(), required=True
    )
    review = review_service.schedule_review(
        actor, summary.apprentice.apprentice_id, scheduled_date=when
    )
    prompts.ok(f"Review booked for {summary.full_name} on {review.scheduled_date}.")
    prompts.pause()


def _schedule_next(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Whose next review?")
    prompts.note(
        f"Counted {config.REVIEW_INTERVAL_WEEKS} weeks from the last meeting that "
        "actually happened, so a review that slipped moves the whole cycle with it."
    )
    review = review_service.schedule_next(actor, summary.apprentice.apprentice_id)
    prompts.ok(f"Next review for {summary.full_name} is {review.scheduled_date}.")
    prompts.pause()


def _start(actor: Actor) -> None:
    review = _pick(actor, status="Scheduled", heading="Review to start")
    started = review_service.start_review(actor, review.review_id)
    prompts.ok(f"{started.apprentice_name}'s review is under way.")
    prompts.pause()


def _record(actor: Actor) -> None:
    """Write the meeting up and send it out for signature."""
    review = _pick(actor, heading="Review to write up")
    prompts.title(f"Write up — {review.apprentice_name}")
    prompts.note(
        "Recording an outcome sends the review out for signature. It is not evidence "
        "until the provider, the apprentice and the employer have all signed."
    )
    payload = {
        "held_date": prompts.ask(
            "Date held (YYYY-MM-DD)",
            default=review.held_date or date.today().isoformat(), required=True,
        ),
        "progress_rating": prompts.choose_value(
            "Progress rating", config.RAG_RATINGS, default=review.progress_rating or "Green"
        ),
        "otj_on_track": _tristate("Off-the-job hours on track?", review.otj_on_track),
        "summary": prompts.ask("Summary", default=review.summary or ""),
        "apprentice_comments": prompts.ask(
            "Apprentice's comments", default=review.apprentice_comments or ""
        ),
        "employer_comments": prompts.ask(
            "Employer's comments", default=review.employer_comments or ""
        ),
        "next_review_date": prompts.ask(
            "Next review (YYYY-MM-DD, blank for the standard interval)",
            default=review.next_review_date or "",
        ),
    }
    recorded = review_service.record_review(actor, review.review_id, payload)
    prompts.ok(f"Recorded. Awaiting: {', '.join(recorded.missing_signatures) or 'nobody'}.")

    while prompts.ask_yes_no("Add a target agreed at this review?"):
        target = review_service.add_target(actor, review.review_id, _target_payload(None))
        prompts.ok(f"Target added, due {target.due_date or 'no date'}.")
    prompts.pause()


def _missed(actor: Actor) -> None:
    review = _pick(actor, heading="Review that did not happen")
    reason = prompts.ask("Why was it missed?", required=True)
    review_service.mark_missed(actor, review.review_id, reason=reason)
    prompts.ok(f"{review.apprentice_name}'s review is recorded as missed.")
    prompts.note("Book a replacement — a gap in the review cycle is a funding-audit finding.")
    prompts.pause()


def _sign(actor: Actor) -> None:
    """Sign the line belonging to the party *actor* actually is."""
    review = _pick(actor, heading="Review to sign", signable_only=True)
    show_review(review)
    party = _signatory_label(actor)
    if not prompts.ask_yes_no(
        f"Sign {review.apprentice_name}'s review of {review.held_date} as the {party}?"
    ):
        raise prompts.Abort

    signed = review_service.sign_review(actor, review.review_id)
    if signed.is_complete:
        prompts.ok("Signed — all three parties have now signed and the review is complete.")
    else:
        prompts.ok(f"Signed. Still waiting on: {', '.join(signed.missing_signatures)}.")
    prompts.pause()


def _unsign(actor: Actor) -> None:
    review = _pick(actor, heading="Review to correct")
    if not review.signed_by:
        prompts.fail("Nobody has signed that review.")
        prompts.pause()
        return
    prompts.note(
        "For a signature added in error. A complete review stands as evidence and "
        "cannot be unpicked — hold another one instead."
    )
    who = prompts.choose_value("Signature to remove", tuple(sorted(review.signed_by)))
    review_service.unsign_review(actor, review.review_id, who)
    prompts.ok(f"Removed the {who} signature.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Targets
# ═════════════════════════════════════════════════════════════════════

def _target_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List open targets", partial(_list_targets, actor, True)),
        ("List all targets", partial(_list_targets, actor, False)),
    ]
    if actor.can("review.conduct"):
        entries += [
            ("Add a target", partial(_add_target, actor)),
            ("Edit a target", partial(_edit_target, actor)),
            ("Close a target", partial(_close_target, actor)),
            ("Delete a target", partial(_delete_target, actor)),
        ]
    prompts.run_menu("Review targets", entries)


def _list_targets(actor: Actor, open_only: bool) -> None:
    summary = apprentices.pick(actor) if prompts.ask_yes_no("Filter to one apprentice?") else None
    targets = review_service.list_targets(
        actor,
        apprentice_id=summary.apprentice.apprentice_id if summary else None,
        open_only=open_only,
    )
    prompts.title("Open targets" if open_only else "All targets")
    _target_table(targets)
    overdue = sum(1 for t in targets if t.is_overdue)
    if overdue:
        prompts.note(f"\n  ! {overdue} target(s) past their due date.")
    prompts.pause()


def _add_target(actor: Actor) -> None:
    review = _pick(actor, heading="Review the target was agreed at")
    target = review_service.add_target(actor, review.review_id, _target_payload(None))
    prompts.ok(f"Target added to {review.apprentice_name}'s review.")
    prompts.note(f"  {target.description}")
    prompts.pause()


def _edit_target(actor: Actor) -> None:
    target = _pick_target(actor)
    updated = review_service.update_target(actor, target.target_id, _target_payload(target))
    prompts.ok(f"Updated: {updated.description[:60]}")
    prompts.pause()


def _close_target(actor: Actor) -> None:
    target = _pick_target(actor, open_only=True)
    outcome = prompts.choose_value(
        "Outcome", tuple(s for s in config.TARGET_STATUSES if s != "Open"), default="Met"
    )
    note = prompts.ask("Outcome note")
    closed = review_service.close_target(
        actor, target.target_id, status=outcome, note=note or None
    )
    prompts.ok(f"Target closed as {closed.status}.")
    prompts.pause()


def _delete_target(actor: Actor) -> None:
    target = _pick_target(actor)
    if not prompts.ask_yes_no(f"Delete “{target.description[:50]}”?"):
        raise prompts.Abort
    review_service.delete_target(actor, target.target_id)
    prompts.ok("Deleted.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# The apprentice's own reviews
# ═════════════════════════════════════════════════════════════════════

def my_menu(actor: Actor) -> None:
    if actor.apprentice_id is None and actor.role == config.APPRENTICE:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    entries: list[tuple[str, Callable[[], None]]] = [
        ("My reviews", partial(_my_list, actor)),
        ("View one", partial(_view, actor)),
        ("My targets", partial(_list_targets, actor, True)),
    ]
    if actor.can("review.sign"):
        entries.append((f"Sign as {_signatory_label(actor)}", partial(_sign, actor)))
    prompts.run_menu("My Progress Reviews", entries)


def _my_list(actor: Actor) -> None:
    rows = review_service.list_reviews(actor, with_children=True)
    prompts.title("My progress reviews")
    _review_table(rows, empty="you have no reviews yet")
    unsigned = [r for r in rows if _signatory_for(actor) in r.missing_signatures and r.held_date]
    if unsigned:
        prompts.note(f"\n  ! {len(unsigned)} review(s) are waiting on your signature.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Employer feedback
# ═════════════════════════════════════════════════════════════════════

def feedback_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List feedback", partial(_list_feedback, actor)),
        ("Average satisfaction", partial(_average, actor)),
    ]
    if actor.can("review.feedback"):
        entries.append(("Give feedback", partial(_give_feedback, actor)))
    prompts.run_menu("Employer Feedback", entries)


def _list_feedback(actor: Actor) -> None:
    rows = review_service.list_feedback(actor)
    names = _employer_names(actor)
    prompts.title("Employer feedback")
    prompts.table(
        _FEEDBACK_COLUMNS,
        rows,
        lambda f: (f.submitted_at, names.get(f.employer_id, f"#{f.employer_id}"),
                   f.satisfaction, f.comments),
        noun="rating",
        empty="nobody has rated the provider yet",
    )
    prompts.pause()


def _employer_names(actor: Actor) -> dict[int, str]:
    """``{employer_id: name}`` for captioning feedback rows.

    Feedback carries an id and no name. An actor who may not list
    employers still sees their own ratings, so a refusal here falls back
    to bare ids rather than emptying the table.
    """
    from education_system.systems.apprenticeships.services import employer_service

    try:
        return {
            s.employer.employer_id: s.name for s in employer_service.list_employers(actor)
        }
    except Exception:
        logger.debug("Could not list employers for feedback captions", exc_info=True)
        return {}


def _average(actor: Actor) -> None:
    score = review_service.satisfaction_average(actor)
    prompts.title("Employer satisfaction")
    if score is None:
        prompts.note("Nobody has rated the provider yet.")
    else:
        prompts.note(f"  {score:.2f} out of 5 across the ratings you can see.")
    prompts.pause()


def _give_feedback(actor: Actor) -> None:
    prompts.title("How are we doing?")
    prompts.note("Your rating is about the training provider, not the apprentice.")
    payload: dict[str, object] = {
        "satisfaction": prompts.choose_value(
            "Satisfaction", config.SATISFACTION_SCALE, default="Satisfied"
        ),
        "comments": prompts.ask("Comments"),
    }
    if prompts.ask_yes_no("Is this about one apprentice in particular?"):
        summary = apprentices.pick(actor)
        payload["apprentice_id"] = summary.apprentice.apprentice_id

    feedback = review_service.submit_feedback(actor, payload)
    prompts.ok(f"Thank you — recorded as “{feedback.satisfaction}”.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def show_review(review) -> None:
    """One review in full, with its signatures and targets."""
    prompts.title(f"{review.apprentice_name} — review of {review.held_date or 'not yet held'}")
    prompts.details([
        ("Scheduled", review.scheduled_date),
        ("Held", review.held_date),
        ("Status", review.status),
        ("Conducted by", review.conductor_name),
        ("Progress rating", review.progress_rating),
        ("Off-the-job on track", review.otj_on_track),
        ("Next review", review.next_review_date),
        ("Summary", review.summary),
        ("Apprentice's comments", review.apprentice_comments),
        ("Employer's comments", review.employer_comments),
    ])

    prompts.note("\nSignatures:")
    prompts.table(
        (("Party", 14), ("Signed by", 22), ("When", 20)),
        review.signatures,
        lambda s: (s.signatory, s.signed_by, s.signed_at),
        noun="signature",
        empty="nobody has signed yet",
    )
    if review.missing_signatures:
        prompts.note(f"  Still to sign: {', '.join(review.missing_signatures)}")

    prompts.note("\nTargets:")
    _target_table(review.targets)


def _review_table(rows: list, *, empty: str | None = None) -> None:
    prompts.table(
        _REVIEW_COLUMNS,
        rows,
        lambda r: (r.apprentice_name, r.scheduled_date, r.held_date, r.status,
                   r.progress_rating, ", ".join(r.missing_signatures)),
        noun="review",
        empty=empty,
    )


def _target_table(rows: list) -> None:
    prompts.table(
        _TARGET_COLUMNS,
        rows,
        lambda t: (t.due_date, t.description, t.owner, t.priority, t.ksb_codes,
                   f"{t.status}{' (overdue)' if t.is_overdue else ''}", t.outcome_note),
        noun="target",
        empty="no targets set",
    )


def _pick(actor: Actor, *, status: str | None = None, heading: str = "Review",
          signable_only: bool = False):
    """Choose a review in scope, optionally only ones *actor* may still sign."""
    rows = review_service.list_reviews(actor, status=status, with_children=True)
    if signable_only:
        party = _signatory_for(actor)
        rows = [r for r in rows if party and r.can_sign(party)]
        if not rows:
            prompts.fail("There are no reviews waiting on your signature.")
            prompts.note("A review can only be signed once it has actually been held.")
            raise prompts.Abort
    return prompts.choose(
        heading, rows,
        render=lambda r: (
            f"{r.apprentice_name} — {r.held_date or r.scheduled_date} ({r.status})"
            + (f", awaiting {', '.join(r.missing_signatures)}" if r.missing_signatures else "")
        ),
    )


def _pick_target(actor: Actor, *, open_only: bool = False):
    targets = review_service.list_targets(actor, open_only=open_only)
    return prompts.choose(
        "Target", targets,
        render=lambda t: f"{t.due_date or 'no date'} — {t.description[:56]} ({t.status})",
    )


def _target_payload(target) -> dict[str, object]:
    return {
        "description": prompts.ask(
            "Target", default=target.description if target else "", required=True
        ),
        "due_date": prompts.ask(
            "Due date (YYYY-MM-DD)", default=(target.due_date if target else "") or ""
        ),
        "ksb_codes": prompts.ask(
            "KSBs it works towards", default=(target.ksb_codes if target else "") or ""
        ),
        "owner": prompts.choose_value(
            "Owner (who has to do it)", config.ACTION_OWNERS,
            default=target.owner if target else config.ACTION_DEFAULT_OWNER,
        ),
        "priority": prompts.choose_value(
            "Priority", config.ACTION_PRIORITIES,
            default=target.priority if target else config.ACTION_DEFAULT_PRIORITY,
        ),
    }


def _tristate(question: str, current: bool | None) -> str:
    """Yes, no, or leave unjudged — NULL is meaningful on this column."""
    answer = prompts.choose_value(
        question, ("Yes", "No", "Not judged"),
        default="Yes" if current else ("No" if current is not None else "Not judged"),
    )
    return {"Yes": "yes", "No": "no", "Not judged": ""}[answer]


def _signatory_for(actor: Actor) -> str | None:
    """Which line of a review this actor signs, if any."""
    return {
        config.ADMIN: "provider",
        config.STAFF: "provider",
        config.APPRENTICE: "apprentice",
        config.EMPLOYER: "employer",
    }.get(actor.role)


def _signatory_label(actor: Actor) -> str:
    return _signatory_for(actor) or "a party to the review"
