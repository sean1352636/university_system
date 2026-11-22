"""Off-the-job hours: the log, the approval queue, and one apprentice's own.

Exposes: menu, approval_menu, my_menu.

Three entry points over one service because three people want different
things from the same table. A programme manager reads the whole log to
find who is drifting; an approver works a queue and wants to clear it;
an apprentice wants their own total and the honest version of it — only
approved hours count, and every screen here says so rather than showing
a figure that will shrink at gateway.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.learning import training_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_ENTRY_COLUMNS = (
    ("Date", 12), ("Hours", -7), ("Activity", 24), ("Description", 38),
    ("KSBs", 12), ("Status", 11),
)

_QUEUE_COLUMNS = (
    ("Apprentice", 22), ("Date", 12), ("Hours", -7), ("Activity", 22),
    ("Description", 34), ("Submitted", 18),
)


# ═════════════════════════════════════════════════════════════════════
# The whole log
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List entries", partial(_list, actor)),
        ("One apprentice's summary", partial(_summary, actor)),
        ("Who is behind", partial(_behind, actor)),
    ]
    if actor.can("otj.approve"):
        entries.append(("Approval queue", partial(approval_menu, actor)))
    prompts.run_menu("Off-the-Job Hours", entries)


def _list(actor: Actor) -> None:
    summary = None
    if prompts.ask_yes_no("Filter to one apprentice?"):
        summary = apprentices.pick(actor)
    status = prompts.choose("Status filter", config.OTJ_STATUSES, allow_blank=True)
    date_from = prompts.ask("From date (YYYY-MM-DD)")
    date_to = prompts.ask("To date (YYYY-MM-DD)")

    rows = training_service.list_otj_entries(
        actor,
        apprentice_id=summary.apprentice.apprentice_id if summary else None,
        status=status, date_from=date_from or None, date_to=date_to or None,
    )
    prompts.title("Off-the-job hours")
    if summary is not None:
        _entry_table(rows)
    else:
        names = apprentices.names(actor)
        prompts.table(
            (("Apprentice", 22), *_ENTRY_COLUMNS),
            rows,
            lambda e: (names.get(e.apprentice_id, f"#{e.apprentice_id}"), e.activity_date,
                       e.hours, e.activity_type, e.description, e.ksb_codes, e.status),
            noun="entry",
        )
    approved = sum(e.hours for e in rows if e.counts_towards_target)
    prompts.note(f"\n  {approved:,.1f} approved hour(s) in this selection.")
    prompts.pause()


def _summary(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    show_summary(actor, summary.apprentice.apprentice_id, summary.full_name)
    prompts.pause()


def _behind(actor: Actor) -> None:
    """Everyone in scope whose approved hours trail the elapsed pace."""
    prompts.title("Behind on off-the-job hours")
    rows = [
        (s, training_service.otj_summary(actor, s.apprentice.apprentice_id))
        for s in apprentice_service.list_apprentices(actor, active_only=True)
    ]
    behind = [pair for pair in rows if not pair[1].target_met and not pair[1].is_on_track]
    behind.sort(key=lambda pair: pair[1].hours_behind, reverse=True)

    prompts.table(
        (("Apprentice", 24), ("Approved", -10), ("Target", -9), ("Done %", -8),
         ("Expected %", -11), ("Behind", -8), ("Per week", -9), ("RAG", 6)),
        behind,
        lambda pair: (
            pair[0].full_name, pair[1].approved_hours, pair[1].target_hours,
            pair[1].percent_complete, pair[1].expected_percent, pair[1].hours_behind,
            pair[1].weekly_hours_needed, pair[1].rag_rating,
        ),
        noun="apprentice",
        empty="everybody in scope is holding the pace",
    )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Approvals
# ═════════════════════════════════════════════════════════════════════

def approval_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List what is waiting", partial(_pending, actor)),
        ("Work through the queue", partial(_work_queue, actor)),
        ("Approve one entry", partial(_approve_one, actor)),
        ("Reject one entry", partial(_reject_one, actor)),
        ("Approve everything waiting", partial(_bulk_approve, actor)),
    ]
    prompts.run_menu("Off-the-Job Approvals", entries)


def _pending(actor: Actor) -> None:
    rows = training_service.pending_approvals(actor)
    prompts.title("Hours awaiting approval")
    _queue_table(actor, rows)
    prompts.note(f"\n  {sum(e.hours for e in rows):,.1f} hour(s) waiting on you.")
    prompts.pause()


def _work_queue(actor: Actor) -> None:
    """Take each submitted entry in turn: approve, reject, or skip."""
    rows = training_service.pending_approvals(actor)
    if not rows:
        prompts.ok("Nothing is waiting for approval.")
        prompts.pause()
        return

    names = apprentices.names(actor)
    approved = rejected = 0
    prompts.title(f"Working through {len(rows)} submitted entr(ies)")
    for entry in rows:
        prompts.rule()
        prompts.details([
            ("Apprentice", names.get(entry.apprentice_id, f"#{entry.apprentice_id}")),
            ("Date", entry.activity_date),
            ("Hours", entry.hours),
            ("Activity", entry.activity_type),
            ("Description", entry.description),
            ("KSBs", entry.ksb_codes),
            ("Submitted", entry.submitted_at),
        ])
        choice = prompts.choose_value(
            "Decision", ("Approve", "Reject", "Skip"), default="Approve"
        )
        if choice == "Skip":
            continue
        if choice == "Approve":
            note = prompts.ask("Note (optional)")
            training_service.approve_hours(actor, entry.entry_id, note=note or None)
            approved += 1
        else:
            reason = prompts.ask("Why is it going back?", required=True)
            training_service.reject_hours(actor, entry.entry_id, reason=reason)
            rejected += 1

    prompts.ok(f"{approved} approved, {rejected} sent back.")
    prompts.pause()


def _approve_one(actor: Actor) -> None:
    entry = _pick_pending(actor, "Entry to approve")
    note = prompts.ask("Note (optional)")
    updated = training_service.approve_hours(actor, entry.entry_id, note=note or None)
    prompts.ok(f"Approved {updated.hours} hour(s) on {updated.activity_date}.")
    prompts.pause()


def _reject_one(actor: Actor) -> None:
    entry = _pick_pending(actor, "Entry to send back")
    prompts.note(
        "A rejected entry becomes editable again, so say what needs changing — the "
        "apprentice cannot fix what they were not told about."
    )
    reason = prompts.ask("Reason", required=True)
    updated = training_service.reject_hours(actor, entry.entry_id, reason=reason)
    prompts.ok(f"Sent back {updated.hours} hour(s) on {updated.activity_date}.")
    prompts.pause()


def _bulk_approve(actor: Actor) -> None:
    rows = training_service.pending_approvals(actor)
    if not rows:
        prompts.ok("Nothing is waiting for approval.")
        prompts.pause()
        return

    prompts.title("Approve everything waiting")
    _queue_table(actor, rows)
    total = sum(e.hours for e in rows)
    if not prompts.ask_yes_no(
        f"Approve all {len(rows)} entr(ies), totalling {total:,.1f} hours?"
    ):
        raise prompts.Abort
    note = prompts.ask("Note to record against each (optional)")

    approved = training_service.bulk_approve(
        actor, [e.entry_id for e in rows], note=note or None
    )
    prompts.ok(f"{approved} of {len(rows)} entr(ies) approved.")
    if approved < len(rows):
        prompts.note(
            "The rest had already been decided by somebody else, so they were skipped."
        )
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# The apprentice's own log
# ═════════════════════════════════════════════════════════════════════

def my_menu(actor: Actor) -> None:
    apprentice_id = actor.apprentice_id
    if apprentice_id is None:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    entries: list[tuple[str, Callable[[], None]]] = [
        ("Where I am against my target", partial(_my_summary, actor, apprentice_id)),
        ("My entries", partial(_my_entries, actor, apprentice_id)),
    ]
    if actor.can("otj.log"):
        entries += [
            ("Log hours", partial(_log, actor)),
            ("Edit an entry", partial(_edit, actor, apprentice_id)),
            ("Submit for approval", partial(_submit, actor, apprentice_id)),
            ("Delete an entry", partial(_delete, actor, apprentice_id)),
        ]
    prompts.run_menu("My Off-the-Job Hours", entries)


def _my_summary(actor: Actor, apprentice_id: int) -> None:
    show_summary(actor, apprentice_id, "Your off-the-job hours")
    prompts.pause()


def _my_entries(actor: Actor, apprentice_id: int) -> None:
    status = prompts.choose("Status filter", config.OTJ_STATUSES, allow_blank=True)
    rows = training_service.list_otj_entries(
        actor, apprentice_id=apprentice_id, status=status
    )
    prompts.title("My off-the-job hours")
    _entry_table(rows)
    prompts.pause()


def _log(actor: Actor) -> None:
    prompts.title("Log off-the-job hours")
    prompts.note(
        "Saved as a draft. Submit it when you are ready and your approver signs it off "
        "— only approved hours count towards your target."
    )
    entry = training_service.log_hours(actor, _entry_payload(None))
    prompts.ok(f"Logged {entry.hours} hour(s) on {entry.activity_date} as a draft.")
    if prompts.ask_yes_no("Submit it for approval now?", default=True):
        training_service.submit_hours(actor, entry.entry_id)
        prompts.ok("Submitted.")
    prompts.pause()


def _edit(actor: Actor, apprentice_id: int) -> None:
    entry = _pick_own(actor, apprentice_id, "Entry to edit", editable_only=True)
    prompts.title(f"Edit {entry.hours} hour(s) on {entry.activity_date}")
    updated = training_service.update_entry(actor, entry.entry_id, _entry_payload(entry))
    prompts.ok(f"Updated: {updated.hours} hour(s) on {updated.activity_date}.")
    prompts.pause()


def _submit(actor: Actor, apprentice_id: int) -> None:
    entry = _pick_own(actor, apprentice_id, "Entry to submit", editable_only=True)
    updated = training_service.submit_hours(actor, entry.entry_id)
    prompts.ok(f"Submitted {updated.hours} hour(s) on {updated.activity_date} for approval.")
    prompts.pause()


def _delete(actor: Actor, apprentice_id: int) -> None:
    entry = _pick_own(actor, apprentice_id, "Entry to delete", editable_only=True)
    if not prompts.ask_yes_no(
        f"Delete the {entry.hours} hour(s) you logged on {entry.activity_date}?"
    ):
        raise prompts.Abort
    training_service.delete_entry(actor, entry.entry_id)
    prompts.ok("Deleted.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def show_summary(actor: Actor, apprentice_id: int, heading: str) -> None:
    """The target, the progress and the pace. Borrowed by the review screens."""
    summary = training_service.otj_summary(actor, apprentice_id)
    prompts.title(heading)
    if summary.target_hours <= 0:
        prompts.note(
            "The target comes from the programme dates, and those are not set yet — "
            "so there is nothing for these hours to count towards."
        )
        return

    prompts.note(
        f"Approved  {prompts.bar(summary.percent_complete)}  "
        f"{summary.approved_hours:,.1f} / {summary.target_hours:,.1f} hrs"
    )
    prompts.note(
        f"Expected  {prompts.bar(summary.expected_percent)}  "
        f"pace to date ({summary.rag_rating})"
    )
    prompts.details([
        ("Awaiting approval", f"{summary.pending_hours:,.1f} hrs"),
        ("Still in draft", f"{summary.draft_hours:,.1f} hrs"),
        ("Remaining", f"{summary.remaining_hours:,.1f} hrs"),
        ("Behind today's pace", f"{summary.hours_behind:,.1f} hrs"),
        ("Needed per week", f"{summary.weekly_hours_needed:,.1f} hrs"),
        ("Weeks elapsed", f"{summary.weeks_elapsed:,.1f} of {summary.weeks_total:,.1f}"),
        ("Entries", summary.entry_count),
        ("Target met", summary.target_met),
    ])


def _entry_table(rows: list) -> None:
    prompts.table(
        _ENTRY_COLUMNS,
        rows,
        lambda e: (e.activity_date, e.hours, e.activity_type, e.description,
                   e.ksb_codes, e.status),
        noun="entry",
    )


def _queue_table(actor: Actor, rows: list) -> None:
    names = apprentices.names(actor)
    prompts.table(
        _QUEUE_COLUMNS,
        rows,
        lambda e: (names.get(e.apprentice_id, f"#{e.apprentice_id}"), e.activity_date,
                   e.hours, e.activity_type, e.description, e.submitted_at),
        noun="entry",
        empty="nothing is waiting for approval",
    )


def _pick_pending(actor: Actor, heading: str):
    names = apprentices.names(actor)
    return prompts.choose(
        heading,
        training_service.pending_approvals(actor),
        render=lambda e: (
            f"{names.get(e.apprentice_id, f'#{e.apprentice_id}')} — {e.activity_date} "
            f"{e.hours}h {e.activity_type}: {e.description[:40]}"
        ),
    )


def _pick_own(actor: Actor, apprentice_id: int, heading: str, *, editable_only: bool):
    """Choose one of the apprentice's own entries.

    Approved hours are filtered out when the action would change them:
    offering an entry the service is bound to refuse wastes the choice
    and reads as a bug.
    """
    rows = training_service.list_otj_entries(actor, apprentice_id=apprentice_id)
    if editable_only:
        rows = [e for e in rows if e.is_editable]
        if not rows:
            prompts.fail(
                "You have no draft or returned entries. Approved and submitted hours "
                "are locked — ask your approver to send them back if they are wrong."
            )
            raise prompts.Abort
    return prompts.choose(
        heading, rows,
        render=lambda e: (
            f"{e.activity_date} — {e.hours}h {e.activity_type} "
            f"({e.status}): {e.description[:40]}"
        ),
    )


def _entry_payload(entry) -> dict[str, object]:
    return {
        "activity_date": prompts.ask(
            "Date the training happened (YYYY-MM-DD)",
            default=entry.activity_date if entry else date.today().isoformat(),
            required=True,
        ),
        "hours": prompts.ask_float(
            "Hours", default=entry.hours if entry else None, required=True
        ),
        "activity_type": prompts.choose_value(
            "Activity type", config.OTJ_ACTIVITY_TYPES,
            default=entry.activity_type if entry else None,
        ),
        "description": prompts.ask(
            "What you did", default=entry.description if entry else "", required=True
        ),
        "ksb_codes": prompts.ask(
            "KSBs covered (comma-separated, optional)",
            default=(entry.ksb_codes if entry else "") or "",
        ),
    }
