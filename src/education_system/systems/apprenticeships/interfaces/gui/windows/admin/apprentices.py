"""The cohort: enrol apprentices, move them through the lifecycle, exit them."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import (
    apprentice_service,
    employer_service,
    programme_service,
)

logger = logging.getLogger(__name__)

_SUBTITLE = (
    "Everyone the provider has on its books. Status moves through the lifecycle "
    "one step at a time — enrol here, then start them on programme."
)

_COLUMNS = (
    ("name", "Apprentice", 180),
    ("uln", "ULN", 100),
    ("programme", "Programme", 200),
    ("employer", "Employer", 160),
    ("tutor", "Tutor", 140),
    ("status", "Status", 120),
    ("otj", "Off-the-job", 90, "e"),
    ("ksb", "KSBs", 70, "e"),
    ("gateway", "Gateway", 100),
)


def render(gui) -> None:
    """The apprentice cohort, with the lifecycle actions that act on it."""
    frame = gui.clear()
    widgets.heading(frame, "Apprentices", subtitle=_SUBTITLE)

    filters = widgets.FilterBar(
        frame,
        (
            ("status", "Status", "combo", config.APPRENTICE_STATUSES),
            ("search", "Search", "entry"),
            ("active_only", "On programme only", "check"),
        ),
        lambda: reload(),
    )
    table = widgets.DataTable(
        frame, _COLUMNS,
        on_activate=lambda chosen: _detail(gui, int(chosen)),
    )
    hint = widgets.empty_state(frame, "")

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: apprentice_service.list_apprentices(gui.actor, **filters.values())
        )
        rows = rows or []
        table.populate(
            rows,
            lambda s: (
                s.full_name, s.apprentice.uln, s.programme_title, s.employer_name,
                s.tutor_name, s.apprentice.status,
                widgets.percent(s.otj_percent), widgets.percent(s.ksb_percent),
                s.gateway_status,
            ),
            identity=lambda s: s.apprentice.apprentice_id,
            tag=lambda s: s.apprentice.status,
            noun="apprentice",
        )
        hint.config(
            text="" if rows else
            "No apprentice matches these filters. Clear them to see the whole cohort, "
            "or use New to enrol somebody.",
        )

    buttons: list[tuple[str, Any]] = []
    if gui.actor.can("apprentice.manage"):
        buttons.append(("New", lambda: _create(gui)))
        buttons.append(("Edit", lambda: _edit(gui, table)))
        buttons.append(("Change Status", lambda: _change_status(gui, table)))
        buttons.append(("Start Programme", lambda: _start(gui, table)))
        buttons.append(("Assign Tutor", lambda: _assign_tutor(gui, table)))
    buttons.append(("View Detail", lambda: _view(gui, table)))
    if gui.actor.is_admin:
        buttons.append(("Delete", lambda: _delete(gui, table)))
    widgets.button_bar(frame, buttons)

    reload()


# ═════════════════════════════════════════════════════════════════════
# Detail pane
# ═════════════════════════════════════════════════════════════════════

def _view(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("view a record")
    if apprentice_id is not None:
        _detail(gui, apprentice_id)


def _detail(gui, apprentice_id: int) -> None:
    """One apprentice in full, rendered over the list."""
    frame = gui.clear()
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    if not ok or summary is None:
        widgets.heading(frame, "Apprentice")
        widgets.button_bar(frame, [("← Back to cohort", lambda: render(gui))])
        widgets.empty_state(frame, "That record could not be opened.")
        return

    record = summary.apprentice
    widgets.heading(
        frame, summary.full_name,
        subtitle=f"{summary.programme_title or 'No programme'} · "
                 f"{summary.employer_name or 'No employer'} · {record.status}",
    )
    widgets.button_bar(frame, [("← Back to cohort", lambda: render(gui))])

    body = widgets.scrollable(frame)
    widgets.field_grid(
        widgets.section(body, "Record"),
        (
            ("ULN", record.uln),
            ("Date of birth", record.date_of_birth),
            ("Age", record.age),
            ("Status", record.status),
            ("Programme", summary.programme_reference),
            ("Level", summary.programme_level),
            ("Employer", summary.employer_name),
            ("Workplace", summary.workplace_name),
            ("Tutor", summary.tutor_name),
            ("Start date", record.start_date),
            ("Planned end", record.planned_end_date),
            ("Actual end", record.actual_end_date),
            ("Weekly hours", record.weekly_hours),
            ("Funding model", record.funding_model),
            ("Email", record.email),
            ("Phone", record.phone),
            ("Username", record.username),
            ("Gateway", summary.gateway_status),
        ),
        columns=3,
    )
    widgets.field_grid(
        widgets.section(body, "Progress"),
        (
            ("Off-the-job logged", f"{summary.otj_hours_logged:,.1f} hrs"),
            ("Off-the-job target", f"{summary.otj_hours_target:,.1f} hrs"),
            ("Off-the-job", widgets.percent(summary.otj_percent)),
            ("Programme elapsed", widgets.percent(summary.progress_percent)),
            ("KSBs competent", f"{summary.ksbs_competent}/{summary.ksbs_total}"),
            ("Open reviews", summary.open_reviews),
        ),
        columns=3,
    )
    widgets.field_grid(
        widgets.section(body, "Notes"),
        (
            ("Prior learning", record.prior_learning),
            ("Support needs", record.support_needs),
            ("Notes", record.notes),
        ),
        columns=1,
    )
    _history(gui, body, apprentice_id)


def _history(gui, parent, apprentice_id: int) -> None:
    section = widgets.section(parent, "Status history")
    _, changes = widgets.guard(
        lambda: apprentice_service.status_history(gui.actor, apprentice_id)
    )
    changes = changes or []
    if not changes:
        widgets.empty_state(
            section, "No status changes are recorded against this apprentice yet."
        )
        return

    table = widgets.DataTable(
        section,
        (
            ("date", "Effective", 100),
            ("from", "From", 130),
            ("to", "To", 130),
            ("reason", "Reason", 300),
            ("actor", "Recorded by", 130),
        ),
        height=8,
    )
    table.populate(
        changes,
        lambda c: (c.effective_date, c.from_status, c.to_status, c.reason, c.actor),
        identity=lambda c: c.history_id,
        tag=lambda c: c.to_status,
        noun="change",
    )


# ═════════════════════════════════════════════════════════════════════
# Create and edit
# ═════════════════════════════════════════════════════════════════════

def _create(gui) -> None:
    choices = _choices(gui)

    def save(values: dict[str, Any]) -> None:
        apprentice_service.create_apprentice(gui.actor, _payload(values, choices))

    dialog = widgets.FormDialog(
        gui.root, "Enrol apprentice", _fields(choices, None), save,
        intro="New records start as an applicant. Use Start Programme once the "
              "eligibility checks and the signed training plan are in place.",
        save_label="Enrol",
    )
    if dialog.saved:
        gui.refresh()


def _edit(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("edit an apprentice")
    if apprentice_id is None:
        return
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    if not ok or summary is None:
        return
    choices = _choices(gui)

    def save(values: dict[str, Any]) -> None:
        apprentice_service.update_apprentice(
            gui.actor, apprentice_id, _payload(values, choices)
        )

    dialog = widgets.FormDialog(
        gui.root, f"Edit {summary.full_name}", _fields(choices, summary), save,
        intro="Status is not editable here — use Change Status, which enforces the "
              "lifecycle and writes the history an audit reads.",
    )
    if dialog.saved:
        gui.refresh()


def _fields(choices: dict[str, list], summary: Any) -> list[dict[str, Any]]:
    """The enrolment form. Dates are deliberately absent.

    Start and planned end are set by Start Programme, which derives the end
    from the standard's duration and the contracted hours — a hand-typed
    date that disagrees with the programme silently moves the off-the-job
    target.
    """
    record = getattr(summary, "apprentice", None)
    return [
        {"key": "given_name", "label": "First name", "required": True,
         "value": getattr(record, "given_name", "")},
        {"key": "family_name", "label": "Last name", "required": True,
         "value": getattr(record, "family_name", "")},
        {"key": "uln", "label": "ULN", "value": getattr(record, "uln", ""),
         "help": "Ten digits. Leave blank until the number comes back."},
        {"key": "date_of_birth", "label": "Date of birth",
         "value": getattr(record, "date_of_birth", ""), "help": "YYYY-MM-DD"},
        {"key": "email", "label": "Email", "value": getattr(record, "email", "")},
        {"key": "phone", "label": "Phone", "value": getattr(record, "phone", "")},
        {"key": "username", "label": "Login username",
         "value": getattr(record, "username", ""),
         "help": "Links this record to an apprentice login."},
        {"key": "weekly_hours", "label": "Weekly hours",
         "value": getattr(record, "weekly_hours", config.OTJ_STANDARD_WEEKLY_HOURS),
         "required": True,
         "help": "Contracted hours. Under 30 lengthens the practical period."},
        {"key": "programme", "label": "Programme", "kind": "combo",
         "options": _labels(choices["programmes"]),
         "value": _label_for(choices["programmes"], getattr(record, "programme_id", None))},
        {"key": "employer", "label": "Employer", "kind": "combo",
         "options": _labels(choices["employers"]),
         "value": _label_for(choices["employers"], getattr(record, "employer_id", None))},
        {"key": "tutor", "label": "Tutor", "kind": "combo",
         "options": _labels(choices["tutors"]),
         "value": _label_for(choices["tutors"], getattr(record, "tutor_id", None))},
        {"key": "funding_model", "label": "Funding model", "kind": "combo",
         "options": ("", *config.FUNDING_MODELS),
         "value": getattr(record, "funding_model", ""),
         "help": "Leave blank to let the funding screen derive it."},
        {"key": "prior_learning", "label": "Prior learning", "kind": "text",
         "value": getattr(record, "prior_learning", "")},
        {"key": "support_needs", "label": "Support needs", "kind": "text",
         "value": getattr(record, "support_needs", "")},
        {"key": "notes", "label": "Notes", "kind": "text",
         "value": getattr(record, "notes", "")},
    ]


def _payload(values: dict[str, Any], choices: dict[str, list]) -> dict[str, Any]:
    payload = {
        key: values.get(key, "")
        for key in (
            "given_name", "family_name", "uln", "date_of_birth", "email", "phone",
            "username", "weekly_hours", "funding_model", "prior_learning",
            "support_needs", "notes",
        )
    }
    payload["programme_id"] = _id_for(choices["programmes"], values.get("programme"))
    payload["employer_id"] = _id_for(choices["employers"], values.get("employer"))
    payload["tutor_id"] = _id_for(choices["tutors"], values.get("tutor"))
    return payload


# ═════════════════════════════════════════════════════════════════════
# Lifecycle
# ═════════════════════════════════════════════════════════════════════

def _change_status(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("change a status")
    if apprentice_id is None:
        return
    ok, transitions = widgets.guard(
        lambda: apprentice_service.available_transitions(gui.actor, apprentice_id)
    )
    if not ok:
        return
    if not transitions:
        widgets.inform(
            "This apprentice has reached a final status — there is nowhere left to "
            "move them to.",
            title="No moves available",
        )
        return

    def save(values: dict[str, Any]) -> None:
        apprentice_service.change_status(
            gui.actor, apprentice_id, values.get("new_status", ""),
            reason=values.get("reason") or None,
            effective_date=values.get("effective_date") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, "Change status",
        [
            {"key": "new_status", "label": "New status", "kind": "combo",
             "options": transitions, "value": transitions[0], "required": True},
            {"key": "effective_date", "label": "Effective date",
             "help": "YYYY-MM-DD. Today if left blank."},
            {"key": "reason", "label": "Reason", "kind": "text",
             "help": "Required for a break in learning, a withdrawal or a transfer."},
        ],
        save,
        intro="Only the moves the lifecycle allows from here are offered.",
    )
    if dialog.saved:
        gui.refresh()


def _start(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("start an apprenticeship")
    if apprentice_id is None:
        return
    choices = _choices(gui)

    def save(values: dict[str, Any]) -> None:
        apprentice_service.start_programme(
            gui.actor, apprentice_id,
            start_date=values.get("start_date", ""),
            programme_id=_id_for(choices["programmes"], values.get("programme")),
        )

    dialog = widgets.FormDialog(
        gui.root, "Start on programme",
        [
            {"key": "start_date", "label": "Start date", "required": True,
             "help": "YYYY-MM-DD"},
            {"key": "programme", "label": "Programme", "kind": "combo",
             "options": _labels(choices["programmes"]),
             "help": "Leave blank to keep the programme already on the record."},
        ],
        save,
        intro="The planned end date is derived from the standard's duration and the "
              "contracted hours, so it is not asked for.",
        save_label="Start",
    )
    if dialog.saved:
        gui.refresh()


def _assign_tutor(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("assign a tutor")
    if apprentice_id is None:
        return
    choices = _choices(gui)
    if not choices["tutors"]:
        widgets.inform(
            "There are no active staff to assign. Add one on the Staff & Caseloads "
            "screen first.",
            title="No tutors",
        )
        return

    def save(values: dict[str, Any]) -> None:
        apprentice_service.assign_tutor(
            gui.actor, apprentice_id, _id_for(choices["tutors"], values.get("tutor"))
        )

    dialog = widgets.FormDialog(
        gui.root, "Assign tutor",
        [{"key": "tutor", "label": "Tutor", "kind": "combo",
          "options": _labels(choices["tutors"]),
          "help": "Leave blank to take this apprentice off a caseload."}],
        save,
    )
    if dialog.saved:
        gui.refresh()


def _delete(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("delete a record")
    if apprentice_id is None:
        return
    if not widgets.confirm(
        "Delete this apprentice and everything attached to them?\n\n"
        "This is for correcting a duplicate or mistaken enrolment. Somebody who "
        "actually left should be withdrawn instead — that keeps the record the "
        "funding audit needs.",
        title="Delete apprentice",
    ):
        return
    reason = widgets.ask_reason("Why is this record being deleted?")
    if reason is None:
        return
    ok, _ = widgets.guard(
        lambda: apprentice_service.delete_apprentice(gui.actor, apprentice_id, reason=reason)
    )
    if ok:
        gui.refresh()


# ═════════════════════════════════════════════════════════════════════
# Lookups
# ═════════════════════════════════════════════════════════════════════

def _choices(gui) -> dict[str, list[tuple[str, int]]]:
    """Label/id pairs for the form comboboxes.

    Comboboxes hand back the label the user picked, so each list is kept as
    pairs and mapped back to an id on save.
    """
    _, programmes = widgets.guard(lambda: programme_service.list_programmes(gui.actor))
    _, employers = widgets.guard(lambda: employer_service.list_employers(gui.actor))
    tutors: list[tuple[str, int]] = []
    if gui.actor.can("staff.view"):
        from education_system.systems.apprenticeships.infrastructure.persistence.repositories import (  # noqa: E501
            staff_repository,
        )

        _, staff = widgets.guard(lambda: staff_repository.list_all(active_only=True))
        tutors = [(f"{m.full_name} ({m.staff_role})", m.staff_id) for m in (staff or [])]
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
