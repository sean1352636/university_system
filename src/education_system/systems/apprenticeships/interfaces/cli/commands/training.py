"""Training delivery: the timetable, the register, and one apprentice's plan.

Exposes: menu. ``plan_menu``, ``show_upcoming`` and ``show_attendance``
are also used by the learning-plan commands.

Marking a register is the only command here with a side effect outside
its own table — a Present or Late mark writes the session's hours into
the off-the-job log already approved. That is deliberate (see
``training_service._sync_register_hours``) and the register prompt says
so, because a tutor who does not realise it will also ask the apprentice
to log the same hours by hand.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.training import attendance as attendance_rules
from education_system.systems.apprenticeships.domain.training import sessions
from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (
    staff_repository,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    learning_plan_service,
    programme_service,
    training_service,
)
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_SESSION_COLUMNS = (
    ("When", 18), ("Title", 30), ("Mode", 16), ("Location", 16),
    ("Trainer", 18), ("OTJ hrs", -8), ("Booked", -7), ("Status", 11),
)

_PLAN_COLUMNS = (
    ("Title", 32), ("Mode", 16), ("From", 12), ("To", 12),
    ("Hours", -7), ("KSBs", 14), ("Status", 12),
)


# ═════════════════════════════════════════════════════════════════════
# Sessions
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List sessions", partial(_list, actor)),
        ("View a session and its register", partial(_view, actor)),
    ]
    if actor.can("training.manage"):
        entries += [
            ("Schedule a session", partial(_create, actor)),
            ("Edit a session", partial(_edit, actor)),
            ("Mark the register", partial(_register, actor)),
            ("Cancel a session", partial(_cancel, actor)),
            ("Delete a session", partial(_delete, actor)),
        ]
    entries.append(("An apprentice's training plan", partial(_open_plan, actor)))
    prompts.run_menu("Training Sessions", entries)


def _open_plan(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Whose training plan?")
    plan_menu(actor, summary.apprentice.apprentice_id, summary.full_name)


def _list(actor: Actor) -> None:
    status = prompts.choose("Status filter", sessions.SESSION_STATUSES, allow_blank=True)
    upcoming = status is None and prompts.ask_yes_no("Upcoming sessions only?", default=True)
    date_from = prompts.ask("From date (YYYY-MM-DD)")
    date_to = prompts.ask("To date (YYYY-MM-DD)")

    rows = training_service.list_sessions(
        actor, status=status, upcoming_only=upcoming,
        date_from=date_from or None, date_to=date_to or None,
    )
    prompts.title("Training Sessions")
    _session_table(rows)
    prompts.pause()


def _view(actor: Actor) -> None:
    session = _pick(actor)
    prompts.title(session.title)
    prompts.details([
        ("When", session.when),
        ("Delivery mode", session.delivery_mode),
        ("Location", session.location),
        ("Programme", session.programme_title),
        ("Trainer", session.trainer_name),
        ("Off-the-job hours", session.otj_hours),
        ("Capacity", session.capacity),
        ("Places left", session.places_left),
        ("KSBs covered", session.ksb_codes),
        ("Status", session.status),
        ("Notes", session.notes),
    ])

    prompts.note("\nRegister:")
    register = training_service.get_register(actor, session.session_id)
    prompts.table(
        (("Apprentice", 26), ("Mark", 10), ("OTJ hrs", -8), ("Reason", 20), ("Notes", 28)),
        register,
        lambda a: (a.apprentice_name, a.status, a.otj_hours, a.absence_reason, a.notes),
        noun="mark",
        empty="the register has not been marked",
    )
    prompts.pause()


def _create(actor: Actor) -> None:
    prompts.title("Schedule a training session")
    payload = _session_payload(actor, None)
    created = training_service.create_session(actor, payload)
    prompts.ok(f"Scheduled “{created.title}” for {created.when}.")
    prompts.note("Mark the register after it runs — that is what turns it into hours.")
    prompts.pause()


def _edit(actor: Actor) -> None:
    session = _pick(actor, heading="Session to edit")
    prompts.title(f"Edit {session.title}")
    updated = training_service.update_session(
        actor, session.session_id, _session_payload(actor, session)
    )
    prompts.ok(f"Updated “{updated.title}”.")
    prompts.pause()


def _cancel(actor: Actor) -> None:
    session = _pick(actor, heading="Session to cancel")
    prompts.note(
        "Cancelling keeps the session and the reason, which is what accounts for a "
        "dip in an apprentice's hours when the funding body asks."
    )
    reason = prompts.ask("Reason for cancelling", required=True)

    updated = training_service.cancel_session(actor, session.session_id, reason=reason)
    prompts.ok(f"“{updated.title}” is cancelled.")
    prompts.pause()


def _delete(actor: Actor) -> None:
    session = _pick(actor, heading="Session to delete")
    prompts.note(
        "Deleting erases the session and its register. For one that was scheduled "
        "and then called off, cancel it instead — that keeps the record. Hours the "
        "register already generated survive either way."
    )
    if not prompts.ask_yes_no(f"Really delete “{session.title}”?"):
        raise prompts.Abort
    reason = prompts.ask("Reason for deletion", required=True)

    training_service.delete_session(actor, session.session_id, reason=reason)
    prompts.ok(f"Deleted “{session.title}”.")
    prompts.pause()


def _register(actor: Actor) -> None:
    """Mark each apprentice in turn, writing the hours the mark earns."""
    session = _pick(actor, heading="Session to mark")
    cohort = apprentice_service.list_apprentices(actor, active_only=True)
    if not cohort:
        prompts.fail("There are no apprentices to mark.")
        prompts.pause()
        return

    prompts.title(f"Register — {session.title} ({session.when})")
    prompts.note(
        f"This session is worth {session.otj_hours} off-the-job hour(s). A Present or "
        "Late mark writes them into the apprentice's log already approved; Absent or "
        "Excused takes them away again."
    )
    existing = {a.apprentice_id: a for a in training_service.get_register(actor, session.session_id)}

    marked = 0
    for summary in cohort:
        apprentice_id = summary.apprentice.apprentice_id
        current = existing.get(apprentice_id)
        prompts.rule()
        prompts.note(
            f"{summary.full_name}"
            + (f"  (currently {current.status}, {current.otj_hours}h)" if current else "")
        )
        if not prompts.ask_yes_no("Mark this apprentice?", default=current is None):
            continue
        mark = prompts.choose_value(
            "Attendance", sessions.ATTENDANCE_STATUSES,
            default=current.status if current else "Present",
        )
        hours = None
        reason = None
        if mark in sessions.HOURS_EARNING_STATUSES and prompts.ask_yes_no(
            f"Override the {session.otj_hours} hours this session is worth?"
        ):
            hours = prompts.ask_float("Hours earned", required=True)
        if mark in attendance_rules.ABSENCE_MARKS:
            # Excused needs a real reason, so it does not default to the
            # one reason that cannot excuse an absence.
            fallback = (config.UNEXPLAINED_ABSENCE_REASON if mark == "Absent"
                        else attendance_rules.SICKNESS_REASON)
            reason = prompts.choose_value(
                "Absence reason", config.ABSENCE_REASONS,
                default=(current.absence_reason if current and current.absence_reason
                         else fallback),
            )
        note = prompts.ask("Note")

        training_service.mark_attendance(
            actor, session.session_id, apprentice_id,
            status=mark, otj_hours=hours, notes=note or None, absence_reason=reason,
        )
        marked += 1

    prompts.ok(f"{marked} mark(s) recorded on “{session.title}”.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# The training plan
# ═════════════════════════════════════════════════════════════════════

def show_upcoming(actor: Actor, programme_id: int | None) -> None:
    """The sessions coming up on one programme.

    Filtered to the programme because the timetable is not scoped per
    apprentice — unfiltered, it would list every session the provider runs.
    """
    if programme_id is None:
        prompts.note("  Not on a programme yet, so there is no timetable to show.")
        return
    _session_table(
        training_service.list_sessions(actor, programme_id=programme_id, upcoming_only=True)
    )


def show_attendance(actor: Actor, apprentice_id: int) -> None:
    """One apprentice's attendance record, as the apprentice reads it."""
    prompts.note("\nYour attendance so far:")
    attendance = training_service.attendance_summary(actor, apprentice_id)
    prompts.details([
        ("Sessions", attendance.total),
        ("Present", attendance.present),
        ("Late", attendance.late),
        ("Absent (unauthorised)", attendance.unauthorised),
        ("Excused (authorised)", attendance.authorised),
        ("Sickness", attendance.sickness),
        ("Attendance rate", f"{attendance.attendance_rate:.1f}%"),
        ("Rating", attendance.rag or "Not enough sessions marked yet"),
        ("Punctuality", f"{attendance.punctuality_rate:.1f}%"),
    ])
    if attendance.concern_reason:
        prompts.note(f"  Your tutor will follow this up: {attendance.concern_reason}.")


def plan_menu(actor: Actor, apprentice_id: int, name: str) -> None:
    """Maintain one apprentice's plan. Reached from the caseload screens."""
    def show() -> None:
        items = training_service.list_plan_items(actor, apprentice_id)
        prompts.title(f"Training plan — {name}")
        prompts.table(
            _PLAN_COLUMNS,
            items,
            lambda i: (i.title, i.delivery_mode, i.planned_start, i.planned_end,
                       i.planned_hours, i.ksb_codes, i.status),
            noun="plan item",
        )
        prompts.pause()

    def add() -> None:
        item = training_service.add_plan_item(
            actor, apprentice_id, _plan_payload(None, _open_objectives(actor, apprentice_id))
        )
        prompts.ok(f"Added “{item.title}” to {name}'s plan.")
        prompts.pause()

    def edit() -> None:
        item = _pick_plan_item(actor, apprentice_id)
        updated = training_service.update_plan_item(
            actor, item.item_id, _plan_payload(item, _open_objectives(actor, apprentice_id))
        )
        prompts.ok(f"Updated “{updated.title}”.")
        prompts.pause()

    def remove() -> None:
        item = _pick_plan_item(actor, apprentice_id)
        if not prompts.ask_yes_no(f"Remove “{item.title}” from the plan?"):
            raise prompts.Abort
        training_service.delete_plan_item(actor, item.item_id)
        prompts.ok(f"Removed “{item.title}”.")
        prompts.pause()

    entries: list[tuple[str, Callable[[], None]]] = [("View plan", show)]
    if actor.can("training.manage"):
        entries += [("Add an item", add), ("Edit an item", edit), ("Remove an item", remove)]
    prompts.run_menu(f"Training plan — {name}", entries)


# ═════════════════════════════════════════════════════════════════════
# Shared helpers
# ═════════════════════════════════════════════════════════════════════

def _session_table(rows: list) -> None:
    prompts.table(
        _SESSION_COLUMNS,
        rows,
        lambda s: (s.when, s.title, s.delivery_mode, s.location, s.trainer_name,
                   s.otj_hours, s.attendee_count, s.status),
        noun="session",
    )


def _pick(actor: Actor, *, heading: str = "Session"):
    """Choose a session, defaulting the list to what is still to come."""
    upcoming = training_service.list_sessions(actor, upcoming_only=True)
    rows = upcoming or training_service.list_sessions(actor)
    return prompts.choose(
        heading, rows,
        render=lambda s: f"{s.when} — {s.title} ({s.status}, {s.attendee_count} booked)",
    )


def _pick_plan_item(actor: Actor, apprentice_id: int):
    items = training_service.list_plan_items(actor, apprentice_id)
    return prompts.choose(
        "Plan item", items,
        render=lambda i: f"{i.title} — {i.status} ({i.planned_hours:g} hrs)",
    )


def _session_payload(actor: Actor, session) -> dict[str, object]:
    """The session form, pre-filled when an existing one is being edited."""
    payload: dict[str, object] = {
        "title": prompts.ask(
            "Title", default=session.title if session else "", required=True
        ),
        "session_date": prompts.ask(
            "Date (YYYY-MM-DD)",
            default=(session.session_date if session else date.today().isoformat()),
            required=True,
        ),
        "start_time": prompts.ask(
            "Start time (HH:MM)", default=(session.start_time if session else "") or ""
        ),
        "end_time": prompts.ask(
            "End time (HH:MM)", default=(session.end_time if session else "") or ""
        ),
        "delivery_mode": prompts.choose_value(
            "Delivery mode", sessions.DELIVERY_MODES,
            default=session.delivery_mode if session else "Classroom",
        ),
        "location": prompts.ask(
            "Location", default=(session.location if session else "") or ""
        ),
        "otj_hours": prompts.ask_float(
            "Off-the-job hours this session is worth",
            default=session.otj_hours if session else 0.0,
        ),
        "capacity": prompts.ask_int(
            "Capacity (blank for no limit)", default=session.capacity if session else None
        ),
        "ksb_codes": prompts.ask(
            "KSBs covered (comma-separated)",
            default=(session.ksb_codes if session else "") or "",
        ),
        "notes": prompts.ask("Notes", default=(session.notes if session else "") or ""),
    }

    programme = prompts.choose(
        "Programme",
        programme_service.list_programmes(actor, in_delivery=True),
        render=lambda p: f"{p.reference} {p.title} (Level {p.level})",
        allow_blank=True,
    )
    payload["programme_id"] = programme.programme_id if programme else None

    trainer = prompts.choose(
        "Trainer",
        staff_repository.list_all(active_only=True),
        render=lambda s: f"{s.full_name} — {s.staff_role}",
        allow_blank=True,
    )
    payload["trainer_id"] = trainer.staff_id if trainer else None
    return payload


def _open_objectives(actor: Actor, apprentice_id: int) -> list:
    """The objectives an activity can be put under."""
    plan = learning_plan_service.get_plan(actor, apprentice_id)
    return [o for o in plan.objectives if o.is_open]


def _plan_payload(item, objectives=()) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": prompts.ask("Title", default=item.title if item else "", required=True),
        "description": prompts.ask(
            "Description", default=(item.description if item else "") or ""
        ),
        "delivery_mode": prompts.choose_value(
            "Delivery mode", sessions.DELIVERY_MODES,
            default=(item.delivery_mode if item else None) or "Classroom",
        ),
        "planned_start": prompts.ask(
            "Planned start (YYYY-MM-DD)", default=(item.planned_start if item else "") or ""
        ),
        "planned_end": prompts.ask(
            "Planned end (YYYY-MM-DD)", default=(item.planned_end if item else "") or ""
        ),
        "planned_hours": prompts.ask_float(
            "Planned hours", default=item.planned_hours if item else 0.0
        ),
        "ksb_codes": prompts.ask(
            "KSBs covered (comma-separated)", default=(item.ksb_codes if item else "") or ""
        ),
        "status": prompts.choose_value(
            "Status", _plan_status_options(item),
            default=(item.status if item else None) or "Planned",
        ),
    }
    # Keeping the current link is the default, so editing an activity's
    # dates does not quietly unhook it from the objective it delivers.
    if item is not None and item.objective_id is not None and prompts.ask_yes_no(
        "Keep it under the objective it currently delivers?", default=True
    ):
        return payload
    if objectives:
        chosen = prompts.choose(
            "Objective this delivers (blank for none)", list(objectives),
            render=lambda o: f"{o.title} — due {o.target_date or 'no date'}",
            allow_blank=True,
        )
        payload["objective_id"] = chosen.objective_id if chosen else None
    elif item is not None:
        payload["objective_id"] = None
    return payload


def _plan_status_options(item) -> tuple[str, ...]:
    """The plan statuses, including whatever an existing item already holds.

    Plans written before the status list existed stored free text, and
    the service keeps an unchanged status as it is. Keeping it in the
    options means editing such an item does not force a rewrite.
    """
    options = config.PLAN_ITEM_STATUSES
    current = getattr(item, "status", None)
    if current and current not in options:
        return (*options, current)
    return options
