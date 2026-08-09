"""End-Point Assessment: organisations, bookings, results and resits.

Exposes: menu, booking_menu, results_menu, resit_menu, my_menu.

Grading is the one action in this system a provider administrator
cannot take, however senior. ``epa.grade`` belongs to the end-point
assessor alone, so :func:`results_menu` is empty for everyone else
except the read-only progress view — a training provider grading the
apprentices it is paid for completing is exactly what independent
end-point assessment exists to prevent.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.services import epa_service
from education_system.systems.apprenticeships.services.access import Actor

logger = logging.getLogger(__name__)

_BOOKING_COLUMNS = (
    ("Apprentice", 22), ("Method", 24), ("When", 18), ("Location", 16),
    ("Assessor", 18), ("EPAO", 18), ("Status", 12),
)

_RESULT_COLUMNS = (
    ("Assessed", 12), ("Method", 24), ("Grade", 12), ("Attempt", -8),
    ("Assessor", 20), ("Feedback", 34),
)

_RESIT_COLUMNS = (
    ("Apprentice", 22), ("Requested", 20), ("Type", 8), ("Status", 11),
    ("Reason", 30), ("Booking", -8),
)


# ═════════════════════════════════════════════════════════════════════
# Top-level
# ═════════════════════════════════════════════════════════════════════

def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Bookings", partial(booking_menu, actor)),
        ("Results", partial(results_menu, actor)),
        ("Resits", partial(resit_menu, actor)),
        ("An apprentice's EPA progress", partial(_progress, actor)),
        ("Assessment organisations", partial(_epao_menu, actor)),
    ]
    prompts.run_menu("End-Point Assessment", entries)


def _progress(actor: Actor) -> None:
    summary = apprentices.pick(actor)
    show_progress(actor, summary.apprentice.apprentice_id, summary.full_name)
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Assessment organisations
# ═════════════════════════════════════════════════════════════════════

def _epao_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [("List EPAOs", partial(_list_epaos, actor))]
    if actor.is_admin:
        entries += [
            ("Add an EPAO", partial(_create_epao, actor)),
            ("Edit an EPAO", partial(_edit_epao, actor)),
            ("Retire an EPAO", partial(_deactivate_epao, actor)),
        ]
    prompts.run_menu("Assessment organisations", entries)


def _list_epaos(actor: Actor) -> None:
    rows = epa_service.list_epaos(actor)
    prompts.title("End-Point Assessment Organisations")
    prompts.table(
        (("Name", 30), ("Contact", 22), ("Email", 28), ("Phone", 16),
         ("Standards", 24), ("Active", 7)),
        rows,
        lambda e: (e.name, e.contact_name, e.contact_email, e.phone,
                   e.standards, e.active),
        noun="organisation",
    )
    prompts.pause()


def _create_epao(actor: Actor) -> None:
    prompts.title("Add an assessment organisation")
    created = epa_service.create_epao(actor, _epao_payload(None))
    prompts.ok(f"Added {created.name}.")
    prompts.pause()


def _edit_epao(actor: Actor) -> None:
    epao = _pick_epao(actor, "EPAO to edit")
    updated = epa_service.update_epao(actor, epao.epao_id, _epao_payload(epao))
    prompts.ok(f"Updated {updated.name}.")
    prompts.pause()


def _deactivate_epao(actor: Actor) -> None:
    epao = _pick_epao(actor, "EPAO to retire")
    prompts.note(
        "Retiring keeps the organisation and every booking already placed with it — "
        "an assessment history that loses the name of the grader is worthless at audit."
    )
    if not prompts.ask_yes_no(f"Retire {epao.name}?"):
        raise prompts.Abort
    epa_service.deactivate_epao(actor, epao.epao_id)
    prompts.ok(f"{epao.name} is retired.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Bookings
# ═════════════════════════════════════════════════════════════════════

def booking_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List bookings", partial(_list_bookings, actor)),
        ("View one booking", partial(_view_booking, actor)),
    ]
    if actor.role == config.END_POINT_ASSESSOR:
        entries.insert(0, ("My diary", partial(_diary, actor)))
    if actor.can("epa.book"):
        entries += [
            ("Book an assessment", partial(_book, actor)),
            ("Schedule a booking", partial(_schedule, actor)),
            ("Edit a booking", partial(_edit_booking, actor)),
            ("Cancel a booking", partial(_cancel_booking, actor)),
        ]
    prompts.run_menu("EPA Bookings", entries)


def _diary(actor: Actor) -> None:
    date_from = prompts.ask("From date (YYYY-MM-DD)", default=date.today().isoformat())
    date_to = prompts.ask("To date (YYYY-MM-DD)")
    rows = epa_service.assessor_schedule(
        actor, date_from=date_from or None, date_to=date_to or None
    )
    prompts.title("My diary")
    _booking_table(rows, empty="nothing booked in that window")
    prompts.pause()


def _list_bookings(actor: Actor) -> None:
    status = prompts.choose("Status filter", config.EPA_BOOKING_STATUSES, allow_blank=True)
    method = prompts.choose("Method filter", config.EPA_METHODS, allow_blank=True)
    open_only = status is None and prompts.ask_yes_no("Only bookings still to be graded?")
    mine = actor.role == config.END_POINT_ASSESSOR and prompts.ask_yes_no("Mine only?")

    rows = epa_service.list_bookings(
        actor, status=status, method=method, open_only=open_only, mine_only=mine
    )
    prompts.title("EPA bookings")
    _booking_table(rows)
    prompts.pause()


def _view_booking(actor: Actor) -> None:
    row = _pick_booking(actor, "Booking to open")
    prompts.title(f"{row.get('apprentice_name')} — {row.get('method')}")
    prompts.details([
        ("Apprentice", row.get("apprentice_name")),
        ("ULN", row.get("apprentice_uln")),
        ("Programme", row.get("programme_title")),
        ("Standard", row.get("programme_reference")),
        ("Method", row.get("method")),
        ("EPAO", row.get("epao_name")),
        ("Scheduled", row.get("scheduled_date")),
        ("Time", row.get("scheduled_time")),
        ("Location", row.get("location")),
        ("Assessor", row.get("assessor_name")),
        ("Assessor login", row.get("assessor_username")),
        ("Status", row.get("status")),
        ("Resit of", row.get("resit_of")),
        ("Notes", row.get("notes")),
    ])
    prompts.pause()


def _book(actor: Actor) -> None:
    """Book one method. Refused until the EPAO has approved gateway."""
    summary = apprentices.pick(actor, heading="Apprentice to book")
    prompts.title(f"Book an assessment — {summary.full_name}")
    prompts.note(
        "Only a method the standard's EPA plan lists, and only after the EPAO has "
        "approved gateway."
    )
    payload = _booking_payload(actor, None)
    row = epa_service.book_assessment(actor, summary.apprentice.apprentice_id, payload)
    prompts.ok(f"{row['method']} booked for {summary.full_name}.")
    if not row.get("scheduled_date"):
        prompts.note("It has no date yet — schedule it when the assessor confirms one.")
    prompts.pause()


def _schedule(actor: Actor) -> None:
    row = _pick_booking(actor, "Booking to schedule", open_only=True)
    prompts.title(f"Schedule — {row.get('apprentice_name')}, {row.get('method')}")
    when = prompts.ask(
        "Date (YYYY-MM-DD)", default=row.get("scheduled_date") or "", required=True
    )
    time = prompts.ask("Time (HH:MM)", default=row.get("scheduled_time") or "")
    location = prompts.ask("Location", default=row.get("location") or "")
    assessor = prompts.ask("Assessor name", default=row.get("assessor_name") or actor.name)
    login = prompts.ask(
        "Assessor login (so it lands in their diary)",
        default=row.get("assessor_username") or (
            actor.username if actor.role == config.END_POINT_ASSESSOR else ""
        ),
    )

    updated = epa_service.schedule_assessment(
        actor, int(row["booking_id"]),
        scheduled_date=when, scheduled_time=time or None, location=location or None,
        assessor_name=assessor or None, assessor_username=login or None,
    )
    prompts.ok(f"Scheduled for {updated['scheduled_date']}.")
    prompts.pause()


def _edit_booking(actor: Actor) -> None:
    row = _pick_booking(actor, "Booking to edit")
    prompts.title(f"Edit — {row.get('apprentice_name')}, {row.get('method')}")
    prompts.note("Status moves through scheduling, cancelling and grading, not here.")
    updated = epa_service.update_booking(
        actor, int(row["booking_id"]), _booking_payload(actor, row)
    )
    prompts.ok(f"Updated the {updated['method']} booking.")
    prompts.pause()


def _cancel_booking(actor: Actor) -> None:
    row = _pick_booking(actor, "Booking to cancel", open_only=True)
    reason = prompts.ask("Reason for cancelling", required=True)
    epa_service.cancel_booking(actor, int(row["booking_id"]), reason=reason)
    prompts.ok(f"Cancelled the {row.get('method')} booking for {row.get('apprentice_name')}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Results
# ═════════════════════════════════════════════════════════════════════

def results_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("An apprentice's EPA progress", partial(_progress, actor)),
    ]
    if actor.can("epa.grade"):
        entries.insert(0, ("Sittings waiting to be graded", partial(_to_grade, actor)))
        entries.insert(1, ("Record a result", partial(_record_result, actor)))
    else:
        entries.append(("Why can't I grade?", _grading_note))
    prompts.run_menu("EPA Results", entries)


def _grading_note() -> None:
    prompts.title("Grading is the assessor's alone")
    prompts.note(
        "End-Point Assessment is independent by design. The organisation that\n"
        "  delivered the training does not decide that its own apprentice has passed,\n"
        "  so 'epa.grade' is held by the end-point assessor role and by nobody else —\n"
        "  the provider administrator deliberately included."
    )
    prompts.pause()


def _to_grade(actor: Actor) -> None:
    rows = _gradable(actor)
    prompts.title("Sittings waiting to be graded")
    _booking_table(rows, empty="nothing is waiting on a grade")
    prompts.pause()


def _record_result(actor: Actor) -> None:
    """Grade a sitting. Final — a correction is a new sitting, not an edit."""
    rows = _gradable(actor)
    if not rows:
        prompts.fail("No booking is at a point where it can be graded.")
        prompts.note("A booking has to be scheduled or in progress first.")
        prompts.pause()
        return

    row = prompts.choose(
        "Sitting to grade", rows,
        render=lambda r: (
            f"{r.get('apprentice_name')} — {r.get('method')} on "
            f"{r.get('scheduled_date') or 'no date'} ({r.get('status')})"
        ),
    )
    prompts.title(f"Grade — {row.get('apprentice_name')}, {row.get('method')}")
    prompts.note("Grading is final. A correction means another sitting, not an edit.")

    grade = prompts.choose_value("Grade", config.EPA_GRADES, default="Pass")
    assessed = prompts.ask(
        "Assessed on (YYYY-MM-DD)",
        default=row.get("scheduled_date") or date.today().isoformat(),
    )
    feedback = prompts.ask("Feedback")
    if not prompts.ask_yes_no(f"Record {grade} for {row.get('apprentice_name')}?"):
        raise prompts.Abort

    result = epa_service.record_result(
        actor, int(row["booking_id"]),
        grade=grade, assessed_date=assessed or None, feedback=feedback or None,
    )
    prompts.ok(f"{result.method}: {result.grade} (attempt {result.attempt}).")

    progress = epa_service.epa_progress(actor, result.apprentice_id)
    if progress.is_complete:
        prompts.ok(f"Every required method is passed — overall grade {progress.overall}.")
        prompts.note("The apprenticeship is complete and the withheld payment is released.")
    elif not result.is_pass:
        prompts.note(
            f"{progress.resits_remaining(result.method)} further attempt(s) at "
            f"{result.method} are permitted."
        )
    else:
        prompts.note(f"Still to pass: {', '.join(progress.methods_outstanding)}.")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# Resits
# ═════════════════════════════════════════════════════════════════════

def resit_menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("List resits", partial(_list_resits, actor)),
    ]
    if actor.can("epa.resit"):
        entries.append(("Request a resit", partial(_request_resit, actor)))
    if actor.can("epa.book"):
        entries.append(("Turn a resit into a booking", partial(_book_resit, actor)))
    prompts.run_menu("EPA Resits", entries)


def _list_resits(actor: Actor) -> None:
    rows = epa_service.list_resits(actor)
    names = apprentices.names(actor)
    prompts.title("Resits and retakes")
    prompts.table(
        _RESIT_COLUMNS,
        rows,
        lambda r: (names.get(r.apprentice_id, f"#{r.apprentice_id}"), r.requested_at,
                   r.resit_type, r.status, r.reason, r.booking_id),
        noun="resit",
        empty="none requested",
    )
    prompts.pause()


def _request_resit(actor: Actor) -> None:
    """Ask to sit a failed method again."""
    summary = apprentices.pick(actor, heading="Apprentice to resit")
    apprentice_id = summary.apprentice.apprentice_id
    progress = epa_service.epa_progress(actor, apprentice_id)
    failed = [r for r in progress.results if not r.is_pass]
    if not failed:
        prompts.fail(f"{summary.full_name} has no failed method to resit.")
        prompts.pause()
        return

    result = prompts.choose(
        "Failed sitting", failed,
        render=lambda r: (
            f"{r.method} — {r.grade} on {r.assessed_date} (attempt {r.attempt}, "
            f"{progress.resits_remaining(r.method)} left)"
        ),
    )
    prompts.note(
        "A resit goes straight back to assessment. A retake needs further training "
        "first, which is why it cannot be requested without a plan for that training."
    )
    kind = prompts.choose_value("Type", config.RESIT_TYPES, default="Resit")
    reason = prompts.ask("Reason")
    plan = prompts.ask("Training plan", required=kind == "Retake") if kind == "Retake" else ""

    resit = epa_service.request_resit(
        actor, apprentice_id, result.result_id,
        resit_type=kind, reason=reason or None, training_plan=plan or None,
    )
    prompts.ok(f"{resit.resit_type} requested for {result.method}.")
    prompts.pause()


def _book_resit(actor: Actor) -> None:
    rows = [r for r in epa_service.list_resits(actor) if r.booking_id is None]
    if not rows:
        prompts.fail("There are no unbooked resit requests.")
        prompts.pause()
        return

    names = apprentices.names(actor)
    resit = prompts.choose(
        "Resit to book", rows,
        render=lambda r: (
            f"{names.get(r.apprentice_id, f'#{r.apprentice_id}')} — {r.resit_type} "
            f"requested {r.requested_at} ({r.status})"
        ),
    )
    prompts.title("Book the resit")
    payload = _booking_payload(actor, None, ask_method=False)
    row = epa_service.book_resit(actor, resit.resit_id, payload)
    prompts.ok(f"Booked as booking {row['booking_id']} ({row['method']}).")
    prompts.pause()


# ═════════════════════════════════════════════════════════════════════
# The apprentice's view
# ═════════════════════════════════════════════════════════════════════

def my_menu(actor: Actor) -> None:
    apprentice_id = actor.apprentice_id
    if apprentice_id is None:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
        prompts.pause()
        return

    def mine() -> None:
        show_progress(actor, apprentice_id, "My End-Point Assessment")
        prompts.pause()

    prompts.run_menu("My End-Point Assessment", [("Where I am", mine)])


# ═════════════════════════════════════════════════════════════════════
# Shared
# ═════════════════════════════════════════════════════════════════════

def show_progress(actor: Actor, apprentice_id: int, heading: str) -> None:
    """One apprentice across every required method: booked, sat, graded."""
    progress = epa_service.epa_progress(actor, apprentice_id)
    prompts.title(heading)
    prompts.details([
        ("Required methods", ", ".join(progress.required_methods) or prompts.EMPTY),
        ("Passed", ", ".join(progress.methods_passed) or prompts.EMPTY),
        ("Outstanding", ", ".join(progress.methods_outstanding) or prompts.EMPTY),
        ("Complete", progress.is_complete),
        ("Overall grade", progress.overall),
    ])

    prompts.note("\nBookings:")
    prompts.table(
        (("Method", 24), ("When", 18), ("Location", 18), ("Assessor", 20), ("Status", 12)),
        progress.bookings,
        lambda b: (b.method, b.when, b.location, b.assessor_name, b.status),
        noun="booking",
        empty="nothing booked",
    )

    prompts.note("\nResults:")
    prompts.table(
        _RESULT_COLUMNS,
        progress.results,
        lambda r: (r.assessed_date, r.method, r.grade, r.attempt, r.assessor_name,
                   r.feedback),
        noun="result",
        empty="nothing graded yet",
    )

    if progress.resits:
        prompts.note("\nResits:")
        prompts.table(
            (("Requested", 20), ("Type", 8), ("Status", 11), ("Reason", 34), ("Booking", -8)),
            progress.resits,
            lambda r: (r.requested_at, r.resit_type, r.status, r.reason, r.booking_id),
            noun="resit",
        )


def _booking_table(rows: list, *, empty: str | None = None) -> None:
    prompts.table(
        _BOOKING_COLUMNS,
        rows,
        lambda r: (
            r.get("apprentice_name"), r.get("method"),
            f"{r.get('scheduled_date') or prompts.EMPTY} "
            f"{r.get('scheduled_time') or ''}".strip(),
            r.get("location"), r.get("assessor_name"), r.get("epao_name"), r.get("status"),
        ),
        noun="booking",
        empty=empty,
    )


def _gradable(actor: Actor) -> list[dict]:
    """Bookings a grade can legally be recorded against.

    ``require_booking_status`` allows Assessed only from Scheduled or In
    Progress, so a Requested sitting with no date is filtered out here
    rather than offered and then refused.
    """
    return [
        r for r in epa_service.list_bookings(actor, open_only=True)
        if r.get("status") in ("Scheduled", "In Progress")
    ]


def _pick_booking(actor: Actor, heading: str, *, open_only: bool = False) -> dict:
    rows = epa_service.list_bookings(actor, open_only=open_only)
    return prompts.choose(
        heading, rows,
        render=lambda r: (
            f"{r.get('apprentice_name')} — {r.get('method')} on "
            f"{r.get('scheduled_date') or 'no date'} ({r.get('status')})"
        ),
    )


def _pick_epao(actor: Actor, heading: str):
    return prompts.choose(
        heading, epa_service.list_epaos(actor),
        render=lambda e: f"{e.name}" + ("" if e.active else " (retired)"),
    )


def _booking_payload(actor: Actor, row: dict | None, *, ask_method: bool = True) -> dict[str, object]:
    payload: dict[str, object] = {}
    if ask_method:
        payload["method"] = prompts.choose_value(
            "Assessment method", config.EPA_METHODS,
            default=(row or {}).get("method"),
        )
    epao = prompts.choose(
        "EPAO", epa_service.list_epaos(actor, active_only=True),
        render=lambda e: e.name, allow_blank=True,
    )
    payload["epao_id"] = epao.epao_id if epao else None
    payload["scheduled_date"] = prompts.ask(
        "Date (YYYY-MM-DD, blank for later)", default=(row or {}).get("scheduled_date") or ""
    )
    payload["scheduled_time"] = prompts.ask(
        "Time (HH:MM)", default=(row or {}).get("scheduled_time") or ""
    )
    payload["location"] = prompts.ask("Location", default=(row or {}).get("location") or "")
    payload["assessor_name"] = prompts.ask(
        "Assessor name", default=(row or {}).get("assessor_name") or ""
    )
    payload["assessor_username"] = prompts.ask(
        "Assessor login", default=(row or {}).get("assessor_username") or ""
    )
    payload["notes"] = prompts.ask("Notes", default=(row or {}).get("notes") or "")
    return payload


def _epao_payload(epao) -> dict[str, object]:
    return {
        "name": prompts.ask("Name", default=epao.name if epao else "", required=True),
        "contact_name": prompts.ask(
            "Contact name", default=(epao.contact_name if epao else "") or ""
        ),
        "contact_email": prompts.ask(
            "Contact email", default=(epao.contact_email if epao else "") or ""
        ),
        "phone": prompts.ask("Phone", default=(epao.phone if epao else "") or ""),
        "standards": prompts.ask(
            "Approved standards (comma-separated references, blank for any)",
            default=(epao.standards if epao else "") or "",
        ),
        "active": prompts.ask_yes_no("Active?", default=epao.active if epao else True),
    }
