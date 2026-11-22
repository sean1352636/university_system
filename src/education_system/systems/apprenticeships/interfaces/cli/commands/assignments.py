"""Assignments: set, submit, mark and moderate.

Exposes: menu.

An apprentice sees and hands in their own work. Provider staff get the
two piles that need them — work to mark and marked work to moderate —
then the full list and the setting commands. The moderation pile leaves
out work the signed-in user marked: moderation needs a second person.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.progress.assignments import Assignment
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.application.assessments import portfolio_service
from education_system.systems.apprenticeships.application.learning import assignment_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("Apprentice", 18), ("Assignment", 28), ("Type", 18), ("Due", 11), ("Status", 10),
    ("Try", 6), ("Grade", 11), ("Late", 4),
)
_SUBMISSION_COLUMNS = (
    ("Try", -3), ("Submitted", 19), ("Late", 4), ("Grade", 11), ("Marked by", 12),
    ("Feedback", 36),
)
_MODERATION_COLUMNS = (
    ("Try", -3), ("When", 19), ("Moderator", 12), ("Outcome", 9), ("Grade", 18), ("Notes", 30),
)


def menu(actor: Actor) -> None:
    if not actor.can("assignment.view"):
        prompts.fail("Assignments are the training provider's own assessments.")
        prompts.pause()
        return
    if actor.role == config.APPRENTICE:
        if actor.apprentice_id is None:
            prompts.fail("Your login is not linked to an apprentice record yet.")
            prompts.note("Ask your provider to link it, then sign in again.")
            prompts.pause()
            return
        entries: list[tuple[str, Callable[[], None]]] = [
            ("My assignments", partial(_list, actor, False)),
            ("View one", partial(_view, actor)),
        ]
        if actor.can("assignment.submit"):
            entries.append(("Hand in work", partial(_submit, actor)))
        prompts.run_menu("My Assignments", entries)
        return

    entries = []
    if actor.can("assignment.set"):
        entries.append(("Work to mark", partial(_marking_queue, actor)))
    if actor.can("assignment.moderate"):
        entries.append(("Work to moderate", partial(_moderation_queue, actor)))
    entries += [
        ("List assignments", partial(_list, actor, True)),
        ("View one", partial(_view, actor)),
    ]
    if actor.can("assignment.set"):
        entries += [
            ("Set an assignment", partial(_set, actor)),
            ("Mark a submission", partial(_mark, actor)),
            ("Edit an assignment", partial(_edit, actor)),
            ("Withdraw an assignment", partial(_withdraw, actor)),
        ]
    if actor.can("assignment.moderate"):
        entries.append(("Moderate a marked attempt", partial(_moderate, actor)))
    if actor.can("assignment.submit"):
        entries.append(("Record a submission on an apprentice's behalf", partial(_submit, actor)))
    prompts.run_menu("Assignments", entries)


# ═════════════════════════════════════════════════════════════════════
# Reading
# ═════════════════════════════════════════════════════════════════════

def _list(actor: Actor, ask_filters: bool) -> None:
    status = kind = None
    overdue = False
    if ask_filters:
        status = prompts.choose("Status filter", config.ASSIGNMENT_STATUSES, allow_blank=True)
        kind = prompts.choose("Type filter", config.ASSIGNMENT_TYPES, allow_blank=True)
        overdue = status is None and prompts.ask_yes_no("Overdue only?")
    rows = assignment_service.list_assignments(
        actor, status=status, assignment_type=kind, overdue_only=overdue, with_children=True,
    )
    prompts.title("Assignments")
    _table(rows)
    prompts.pause()


def _marking_queue(actor: Actor) -> None:
    prompts.title("Work to mark")
    _table(assignment_service.marking_queue(actor), empty="nothing is waiting to be marked")
    prompts.pause()


def _moderation_queue(actor: Actor) -> None:
    prompts.title("Work to moderate")
    prompts.note("Work you marked yourself is left out: moderation needs a second person.")
    _table(assignment_service.moderation_queue(actor), empty="nothing is waiting for moderation")
    prompts.pause()


def _view(actor: Actor) -> None:
    item = _pick(actor)
    show(assignment_service.get_assignment(actor, item.assignment_id))
    prompts.pause()


def show(item: Assignment) -> None:
    """One assignment in full, every attempt and moderation included."""
    prompts.title(f"{item.title} — {item.apprentice_name}")
    prompts.details([
        ("Type", item.assignment_type),
        ("Status", item.status),
        ("Due", item.due_date),
        ("Attempt", f"{item.attempt} of {item.max_attempts}"),
        ("Attempts left", item.attempts_left),
        ("Grade", item.grade),
        ("Marked by", item.marked_by),
        ("KSBs", item.ksb_codes),
        ("Set by", item.set_by),
        ("Brief", item.brief),
        ("Latest feedback", item.feedback),
    ])
    prompts.note("\nAttempts:")
    prompts.table(
        _SUBMISSION_COLUMNS,
        item.submissions,
        lambda s: (s.attempt, s.submitted_at, s.is_late, s.grade, s.marked_by, s.feedback),
        noun="attempt",
        empty="nothing handed in yet",
    )
    if item.moderations:
        prompts.note("\nModeration:")
        prompts.table(
            _MODERATION_COLUMNS,
            item.moderations,
            lambda m: (m.attempt, m.moderated_at, m.moderator, m.outcome,
                       f"{m.original_grade} -> {m.adjusted_grade}" if m.adjusted_grade
                       else m.original_grade, m.notes),
            noun="moderation",
        )


# ═════════════════════════════════════════════════════════════════════
# Writing
# ═════════════════════════════════════════════════════════════════════

def _set(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Set work for", active_only=True)
    created = assignment_service.set_assignment(
        actor, summary.apprentice.apprentice_id, _payload(None)
    )
    prompts.ok(f"Set “{created.title}” for {summary.full_name}, due {created.due_date or 'no date'}.")
    prompts.pause()


def _edit(actor: Actor) -> None:
    item = _pick(actor, statuses=("Set", "Referred"))
    if item.attempts_used:
        prompts.note("Work has been handed in against this brief, so only the due date may change.")
        payload: dict[str, object] = {
            "due_date": prompts.ask("Due date (YYYY-MM-DD)", default=item.due_date or ""),
        }
    else:
        payload = _payload(item)
    updated = assignment_service.update_assignment(actor, item.assignment_id, payload)
    prompts.ok(f"Updated “{updated.title}”.")
    prompts.pause()


def _withdraw(actor: Actor) -> None:
    item = _pick(actor, statuses=("Set", "Referred"))
    reason = prompts.ask("Why is it being withdrawn?", required=True)
    assignment_service.withdraw_assignment(actor, item.assignment_id, reason=reason)
    prompts.ok(f"Withdrew “{item.title}”. It stays on the record.")
    prompts.pause()


def _submit(actor: Actor) -> None:
    item = _pick(actor, statuses=("Set", "Referred"))
    prompts.note(f"Attempt {item.next_attempt} of {item.max_attempts}.")
    if item.is_overdue(date.today()):
        prompts.note(f"It was due {item.due_date}: it will be accepted, and marked as late.")
    body = prompts.ask("Your work (or blank to attach portfolio evidence only)")
    evidence_id = None
    evidence = portfolio_service.list_evidence(actor, apprentice_id=item.apprentice_id)
    if evidence and prompts.ask_yes_no("Attach a piece of portfolio evidence?"):
        chosen = prompts.choose(
            "Evidence", evidence, render=lambda e: f"{e.title} ({e.status})", allow_blank=True
        )
        evidence_id = chosen.evidence_id if chosen else None
    updated = assignment_service.submit(
        actor, item.assignment_id, body=body or None, evidence_id=evidence_id
    )
    prompts.ok("Handed in" + (" — recorded as late." if updated.is_late else "."))
    prompts.pause()


def _mark(actor: Actor) -> None:
    rows = assignment_service.marking_queue(actor)
    if not rows:
        prompts.fail("Nothing is waiting to be marked.")
        prompts.pause()
        return
    item = prompts.choose("Submission to mark", rows, render=_label)
    show(item)
    final = item.attempt >= item.max_attempts
    prompts.note(
        "This is the final attempt: a Refer stands." if final
        else "A Refer sends the work back for another attempt."
    )
    grade = prompts.choose_value("Grade", config.ASSIGNMENT_GRADES, default="Pass")
    feedback = prompts.ask("Feedback", required=grade == config.ASSIGNMENT_REFER_GRADE)
    resubmit_by = None
    if grade == config.ASSIGNMENT_REFER_GRADE and not final:
        resubmit_by = prompts.ask("Resubmit by (YYYY-MM-DD, blank to keep the due date)")
    updated = assignment_service.mark(
        actor, item.assignment_id, grade=grade, feedback=feedback or None,
        resubmit_by=resubmit_by or None,
    )
    prompts.ok(f"Marked {updated.grade} — now {updated.status}.")
    prompts.pause()


def _moderate(actor: Actor) -> None:
    rows = assignment_service.moderation_queue(actor)
    if not rows:
        prompts.fail("Nothing is waiting for you to moderate.")
        prompts.note("Work you marked yourself is not yours to moderate.")
        prompts.pause()
        return
    item = prompts.choose("Attempt to moderate", rows, render=_label)
    show(item)
    outcome = prompts.choose_value(
        "Outcome", config.ASSIGNMENT_MODERATION_OUTCOMES, default="Agreed"
    )
    adjusted = None
    if outcome == "Adjusted":
        adjusted = prompts.choose_value("Adjusted grade", config.ASSIGNMENT_GRADES)
    notes = prompts.ask("Notes", required=outcome == "Adjusted")
    updated = assignment_service.moderate(
        actor, item.assignment_id, outcome=outcome, adjusted_grade=adjusted, notes=notes or None,
    )
    prompts.ok(f"Moderated — grade {updated.grade}, now {updated.status}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def _table(rows: list[Assignment], *, empty: str | None = None) -> None:
    today = date.today()
    prompts.table(
        _COLUMNS,
        rows,
        lambda a: (
            a.apprentice_name, a.title, a.assignment_type, a.due_date,
            a.status + ("!" if a.is_overdue(today) else ""),
            f"{a.attempt}/{a.max_attempts}", a.grade, a.is_late,
        ),
        noun="assignment",
        empty=empty,
    )


def _label(item: Assignment) -> str:
    return (f"{item.apprentice_name} — {item.title} ({item.status}, attempt "
            f"{item.attempt} of {item.max_attempts}{', due ' + item.due_date if item.due_date else ''})")


def _pick(actor: Actor, *, statuses: tuple[str, ...] | None = None) -> Assignment:
    rows = assignment_service.list_assignments(actor, with_children=True)
    if statuses:
        rows = [r for r in rows if r.status in statuses]
    return prompts.choose("Assignment", rows, render=_label)


def _payload(item: Assignment | None) -> dict[str, object]:
    def current(attr: str) -> str:
        value = getattr(item, attr, None) if item is not None else None
        return "" if value is None else str(value)

    return {
        "title": prompts.ask("Title", default=current("title"), required=True),
        "assignment_type": prompts.choose_value(
            "Type", config.ASSIGNMENT_TYPES,
            default=item.assignment_type if item else config.ASSIGNMENT_TYPES[0],
        ),
        "brief": prompts.ask("Brief", default=current("brief")),
        "ksb_codes": prompts.ask("KSBs (comma-separated)", default=current("ksb_codes")),
        "due_date": prompts.ask("Due date (YYYY-MM-DD)", default=current("due_date")),
        "max_attempts": prompts.ask_int(
            f"Attempts allowed (1-{config.ASSIGNMENT_MAX_ATTEMPTS})",
            default=item.max_attempts if item else config.ASSIGNMENT_MAX_ATTEMPTS,
        ),
    }
