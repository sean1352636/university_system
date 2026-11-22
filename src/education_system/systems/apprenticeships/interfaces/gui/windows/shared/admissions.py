"""The admissions queue: accept or decline the people who have applied.

Applicants arrive two ways — created by hand when somebody walks in, or
handed over by a school, college or university through the cross-system
transfer. The queue shows both, distinguished only by an Origin column,
because the decision is the same either way. What differs is the side
effect: accepting a transfer also closes it off in the sending system,
and declining cancels it so they stop showing the learner as in-flight.
That is all handled in ``admissions_service``; this screen collects the
decision.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import messagebox
from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import admissions_service
from education_system.systems.apprenticeships.application.employers import employer_service
from education_system.systems.apprenticeships.application.programmes import programme_service

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Everyone waiting for a decision. Accepting takes them onto programme and "
    "closes off the transfer they came in on; declining keeps the record and "
    "the reason."
)

_COLUMNS = (
    ("name", "Applicant", 180),
    ("uln", "ULN", 100),
    ("origin", "Origin", 170),
    ("applied", "Applied", 100),
    ("admission", "Stage", 130),
    ("programme", "Programme", 190),
    ("employer", "Employer", 150),
    ("stage", "Transfer stage", 120),
)


def render(gui) -> None:
    """The queue, with the two decisions that act on it."""
    frame = gui.clear()
    widgets.heading(frame, "Admissions", subtitle=_SUBTITLE)

    table = widgets.DataTable(
        frame, _COLUMNS,
        on_activate=lambda chosen: _detail(gui, int(chosen)),
    )
    hint = widgets.empty_state(frame, "")

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: admissions_service.list_applications(gui.actor)
        )
        rows = rows or []
        table.populate(
            rows,
            lambda a: (
                a.full_name, a.summary.apprentice.uln, a.origin_label,
                (a.applied_at or "")[:10], a.stage_label, a.summary.programme_title,
                a.summary.employer_name, a.transition_status or "—",
            ),
            identity=lambda a: a.apprentice_id,
            noun="application",
        )
        transfers = sum(1 for a in rows if a.is_cross_system)
        hint.config(
            text=(
                "Nobody is waiting for a decision. Applicants appear here when "
                "somebody is enrolled as an applicant, or when another system "
                "hands a learner over."
            ) if not rows else (
                f"{len(rows)} waiting"
                + (f", {transfers} transferred in from another system."
                   if transfers else ".")
            ),
        )

    # Kept on the frame so the detail pane can call back into it.
    gui_reload = reload

    buttons: list[tuple[str, Any]] = [("View Detail", lambda: _view(gui, table))]
    if gui.actor.can("admission.decide"):
        buttons.insert(0, ("Make Offer…", lambda: _offer(gui, table, gui_reload)))
        buttons.insert(1, ("Record Enrolment…", lambda: _enrol(gui, table, gui_reload)))
        buttons.insert(2, ("Accept", lambda: _accept(gui, table, gui_reload)))
        buttons.insert(3, ("Decline", lambda: _decline(gui, table, gui_reload)))
    widgets.button_bar(frame, buttons)

    reload()


# ═════════════════════════════════════════════════════════════════════
# Detail pane
# ═════════════════════════════════════════════════════════════════════

def _view(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("open an application")
    if apprentice_id is not None:
        _detail(gui, apprentice_id)


def _detail(gui, apprentice_id: int) -> None:
    """One application in full, rendered over the queue."""
    frame = gui.clear()
    ok, application = widgets.guard(
        lambda: admissions_service.get_application(gui.actor, apprentice_id)
    )
    if not ok or application is None:
        widgets.heading(frame, "Application")
        widgets.button_bar(frame, [("← Back to queue", lambda: render(gui))])
        widgets.empty_state(frame, "That application could not be opened.")
        return

    record = application.summary.apprentice
    widgets.heading(frame, application.full_name,
                    subtitle=f"{application.origin_label} — {application.stage_label}")

    stage = application.stage
    widgets.field_grid(frame, [
        ("ULN", record.uln),
        ("Date of birth", record.date_of_birth),
        ("Email", record.email),
        ("Phone", record.phone),
        ("Applied", application.applied_at),
        ("Transfer stage", application.transition_status or "—"),
        ("Programme", application.summary.programme_title),
        ("Employer", application.summary.employer_name),
        ("Admission stage", application.stage_label),
        ("Offer date", stage.offer_date if stage else None),
        ("Offer conditions", stage.offer_conditions if stage else None),
        ("Enrolment date", stage.enrolment_date if stage else None),
    ])

    detail = widgets.section(frame, "What was handed over")
    widgets.field_grid(detail, [
        ("Prior learning", record.prior_learning),
        ("Support needs", record.support_needs),
        ("Notes", record.notes),
    ], columns=1)

    if application.is_cross_system:
        origin = (application.source_system or "the sending system").replace("_", " ")
        widgets.empty_state(
            frame,
            f"Accepting will close this transfer off in {origin}; declining "
            f"will cancel it so they can record a different destination.",
        )

    buttons: list[tuple[str, Any]] = [("← Back to queue", lambda: render(gui))]
    if application.journey_id:
        buttons.append(("View Learner Journey", lambda: _show_journey(
            gui, application.journey_id)))
    if gui.actor.can("admission.decide"):
        buttons.append(("Make Offer…", lambda: _offer_one(
            gui, apprentice_id, lambda: _detail(gui, apprentice_id))))
        buttons.append(("Record Enrolment…", lambda: _enrol_one(
            gui, apprentice_id, lambda: _detail(gui, apprentice_id))))
        buttons.append(("Accept", lambda: _accept_one(
            gui, apprentice_id, lambda: render(gui))))
        buttons.append(("Decline", lambda: _decline_one(
            gui, apprentice_id, lambda: render(gui))))
    widgets.button_bar(frame, buttons)


def _show_journey(gui, journey_id: str) -> None:
    """Open the reciprocal read-only college/apprenticeship history."""
    from education_system.platform.cross_system import student_view
    overview = student_view.build_overview(journey_id)
    messagebox.showinfo(
        "Learner Journey", student_view.format_overview_text(overview),
        parent=gui.root)


# ═════════════════════════════════════════════════════════════════════
# Stages: offer and enrolment
# ═════════════════════════════════════════════════════════════════════

def _offer(gui, table: widgets.DataTable, after) -> None:
    apprentice_id = table.require_selection_int("make an offer")
    if apprentice_id is not None:
        _offer_one(gui, apprentice_id, after)


def _offer_one(gui, apprentice_id: int, after) -> None:
    ok, application = widgets.guard(
        lambda: admissions_service.get_application(gui.actor, apprentice_id)
    )
    if not ok or application is None:
        return
    stage = application.stage

    def save(values: dict[str, Any]) -> object:
        return admissions_service.make_offer(
            gui.actor, apprentice_id,
            offer_date=values.get("offer_date") or None,
            conditions=values.get("conditions") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, f"Offer {application.full_name} a place",
        [
            {"key": "offer_date", "label": "Offer date",
             "value": (stage.offer_date if stage and stage.offer_date
                       else date.today().isoformat()),
             "help": "YYYY-MM-DD."},
            {"key": "conditions", "label": "Conditions", "kind": "text",
             "value": stage.offer_conditions if stage else "",
             "help": "Anything the offer depends on. Leave blank for an unconditional offer."},
        ],
        save,
        intro="An offer is a stage of admissions: they stay an applicant until accepted "
              "onto programme. An offer can be amended while it stands.",
        save_label="Make offer",
    )
    if dialog.saved:
        after()


def _enrol(gui, table: widgets.DataTable, after) -> None:
    apprentice_id = table.require_selection_int("record an enrolment")
    if apprentice_id is not None:
        _enrol_one(gui, apprentice_id, after)


def _enrol_one(gui, apprentice_id: int, after) -> None:
    ok, application = widgets.guard(
        lambda: admissions_service.get_application(gui.actor, apprentice_id)
    )
    if not ok or application is None:
        return

    def save(values: dict[str, Any]) -> object:
        return admissions_service.record_enrolment(
            gui.actor, apprentice_id, enrolment_date=values.get("enrolment_date") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, f"Record {application.full_name}'s enrolment",
        [{"key": "enrolment_date", "label": "Enrolment date",
          "value": date.today().isoformat(), "help": "YYYY-MM-DD. Not before the offer."}],
        save,
        intro="Enrolment follows an offer. Accept them onto programme when they start — "
              "that is when the start date and the funding clock begin.",
        save_label="Record enrolment",
    )
    if dialog.saved:
        after()


# ═════════════════════════════════════════════════════════════════════
# Decisions
# ═════════════════════════════════════════════════════════════════════

def _accept(gui, table: widgets.DataTable, after) -> None:
    apprentice_id = table.require_selection_int("accept an applicant")
    if apprentice_id is not None:
        _accept_one(gui, apprentice_id, after)


def _accept_one(gui, apprentice_id: int, after) -> None:
    ok, application = widgets.guard(
        lambda: admissions_service.get_application(gui.actor, apprentice_id)
    )
    if not ok or application is None:
        return
    choices = _choices(gui)
    summary = application.summary

    def save(values: dict[str, Any]) -> None:
        decision = admissions_service.accept(
            gui.actor, apprentice_id,
            start_date=values.get("start_date", ""),
            programme_id=_id_for(choices["programmes"], values.get("programme")),
            employer_id=_id_for(choices["employers"], values.get("employer")),
            workplace_id=None,
            tutor_id=_id_for(choices["tutors"], values.get("tutor")),
            notes=values.get("notes") or None,
        )
        _report(decision, accepted=True)

    dialog = widgets.FormDialog(
        gui.root, f"Accept {application.full_name}",
        [
            {"key": "start_date", "label": "Start date", "required": True,
             "value": date.today().isoformat(), "help": "YYYY-MM-DD"},
            {"key": "programme", "label": "Programme", "kind": "combo",
             "options": _labels(choices["programmes"]),
             "value": _label_for(choices["programmes"],
                                 summary.apprentice.programme_id),
             "help": "The off-the-job target and funding band derive from this."},
            {"key": "employer", "label": "Employer", "kind": "combo",
             "options": _labels(choices["employers"]),
             "value": _label_for(choices["employers"],
                                 summary.apprentice.employer_id),
             "help": "Required — the employer signs the training plan."},
            {"key": "tutor", "label": "Tutor", "kind": "combo",
             "options": _labels(choices["tutors"]),
             "help": "Who takes them onto their caseload. Can be set later."},
            {"key": "notes", "label": "Note", "kind": "text"},
        ],
        save,
        intro=(
            "Accepting takes them onto programme from the start date. The "
            "planned end date is derived from the standard, so it is not asked "
            "for."
        ),
        save_label="Accept",
    )
    if dialog.saved:
        after()


def _decline(gui, table: widgets.DataTable, after) -> None:
    apprentice_id = table.require_selection_int("decline an applicant")
    if apprentice_id is not None:
        _decline_one(gui, apprentice_id, after)


def _decline_one(gui, apprentice_id: int, after) -> None:
    ok, application = widgets.guard(
        lambda: admissions_service.get_application(gui.actor, apprentice_id)
    )
    if not ok or application is None:
        return

    def save(values: dict[str, Any]) -> None:
        decision = admissions_service.decline(
            gui.actor, apprentice_id,
            reason=values.get("reason", ""),
            effective_date=values.get("effective_date") or None,
        )
        _report(decision, accepted=False)

    dialog = widgets.FormDialog(
        gui.root, f"Decline {application.full_name}",
        [
            {"key": "reason", "label": "Reason", "kind": "text", "required": True,
             "help": "Kept on the record and sent to the system they applied from."},
            {"key": "effective_date", "label": "Effective date",
             "help": "YYYY-MM-DD. Today if left blank."},
        ],
        save,
        intro=(
            "The record is kept, not deleted — a declined application is part "
            "of the recruitment history and its reason is auditable."
        ),
        save_label="Decline",
    )
    if dialog.saved:
        after()


def _report(decision: admissions_service.Decision, *, accepted: bool) -> None:
    """Confirm the decision, flagging a cross-system problem separately.

    A platform failure is shown as a warning rather than an error: the
    decision itself succeeded and the record is correct locally.
    """
    if accepted:
        message = f"{decision.full_name} is now {decision.status}."
        if decision.transition_closed and not decision.source_closed:
            message += (
                "\n\nThe sending system's enrolment was left open — this is a "
                "concurrent registration, so they stay enrolled there too.")
    else:
        message = (f"{decision.full_name} was declined. The record and the "
                   f"reason are kept.")

    if decision.platform_error:
        widgets.warn(f"{message}\n\n{decision.platform_error}",
                     title="Decision recorded, transfer not closed")
    else:
        widgets.inform(message)


# ═════════════════════════════════════════════════════════════════════
# Combobox choices
# ═════════════════════════════════════════════════════════════════════

def _choices(gui) -> dict[str, list[tuple[str, int]]]:
    """Label/id pairs for the form comboboxes.

    Comboboxes hand back the label the user picked, so each list is kept
    as pairs and mapped back to an id on save.
    """
    _, programmes = widgets.guard(
        lambda: programme_service.list_programmes(gui.actor, active_only=True))
    _, employers = widgets.guard(
        lambda: employer_service.list_employers(gui.actor))
    tutors: list[tuple[str, int]] = []
    if gui.actor.can("staff.view"):
        from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (  # noqa: E501
            staff_repository,
        )

        _, staff = widgets.guard(lambda: staff_repository.list_all(active_only=True))
        tutors = [(f"{m.full_name} ({m.staff_role})", m.staff_id)
                  for m in (staff or [])]
    return {
        "programmes": [
            (f"{p.reference} — {p.title}", p.programme_id) for p in (programmes or [])
        ],
        "employers": [(e.name, e.employer.employer_id) for e in (employers or [])],
        "tutors": tutors,
    }


def _labels(pairs: list[tuple[str, int]]) -> tuple[str, ...]:
    """Option list with a blank first entry, which means "not set"."""
    return ("", *[label for label, _ in pairs])


def _label_for(pairs: list[tuple[str, int]], value: int | None) -> str:
    if value is None:
        return ""
    return next((label for label, key in pairs if key == value), "")


def _id_for(pairs: list[tuple[str, int]], label: str | None) -> int | None:
    if not label:
        return None
    return next((key for text, key in pairs if text == label), None)
