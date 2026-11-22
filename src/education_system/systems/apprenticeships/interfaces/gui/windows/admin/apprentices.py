"""The cohort: enrol apprentices, move them through the lifecycle, exit them."""

from __future__ import annotations

import logging
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.apprentices import apprentice_service
from education_system.systems.apprenticeships.application.employers import employer_service
from education_system.systems.apprenticeships.application.programmes import programme_service
from education_system.systems.apprenticeships.application.security import account_service
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

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
        buttons.append(("Create Login", lambda: _create_login_for_selected(gui, table)))
    if gui.actor.can("training.manage"):
        buttons.append(("Apply Curriculum", lambda: _apply_curriculum(gui, table)))
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
        widgets.section(body, "Personal details"),
        (
            ("Legal name", record.legal_name),
            ("Preferred name", record.preferred_name),
            ("Gender", record.gender),
            ("Address", record.address),
            ("Emergency contact", record.emergency_contact_name),
            ("Relationship", record.emergency_contact_relationship),
            ("Emergency phone", record.emergency_contact_phone),
            ("Learning difficulty / disability", "Yes" if record.has_lldd else "No"),
            ("EHC plan", "Yes" if record.has_ehcp else "No"),
        ),
        columns=3,
    )
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
            ("Medical notes", record.medical_notes),
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

    def save(values: dict[str, Any]) -> Any:
        payload = _payload(values, choices)
        try:
            return apprentice_service.create_apprentice(
                gui.actor, payload, check_duplicate=True,
            )
        except apprentice_service.DuplicateApprentice as dup:
            if not widgets.confirm(
                f"{dup}\n\nTwins and people with common names can match. "
                "Save this as a new apprentice anyway?",
                title="Possible duplicate",
            ):
                raise ValidationError(
                    "Not saved. Open the existing record from the cohort list instead."
                ) from dup
            return apprentice_service.create_apprentice(gui.actor, payload)

    fields = _fields(choices, None)
    fields += [
        {"kind": "section", "key": "_login", "label": "Login"},
        {"key": "create_login", "label": "Create their login", "kind": "check",
         "value": True,
         "help": "Creates a shared login and e-mails them a temporary password."},
    ]
    dialog = widgets.FormDialog(
        gui.root, "Enrol apprentice", fields, save,
        intro="New records start as an applicant. Use Start Programme once the "
              "eligibility checks and the signed training plan are in place.",
        save_label="Enrol",
    )
    if not dialog.saved:
        return
    created = dialog.result
    if created is not None and dialog.values_at_save.get("create_login"):
        _create_login(gui, created.apprentice_id, created.full_name)
    gui.refresh()


def _create_login_for_selected(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("create a login")
    if apprentice_id is None:
        return
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    if not ok or summary is None:
        return
    if not widgets.confirm(
        f"Create a login for {summary.full_name} and e-mail them a temporary password?",
        title="Create login",
    ):
        return
    _create_login(gui, apprentice_id, summary.full_name)
    gui.refresh()


def _create_login(gui, apprentice_id: int, name: str) -> None:
    """Create the login and show the sign-in details once."""
    ok, new = widgets.guard(
        lambda: account_service.create_apprentice_login(gui.actor, apprentice_id),
        title="Create login",
    )
    if not ok or new is None:
        return
    widgets.inform(
        f"Login created for {name}:\n\n"
        f"    Username:  {new.username}\n"
        f"    Password:  {new.password}\n\n"
        "Note the password now. It won't be shown again.\n\n"
        f"{new.welcome_detail}",
        title="Create login",
    )


def _edit(gui, table: widgets.DataTable) -> None:
    apprentice_id = table.require_selection_int("edit an apprentice")
    if apprentice_id is None:
        return
    ok, summary = widgets.guard(
        lambda: apprentice_service.get_apprentice(gui.actor, apprentice_id)
    )
    if not ok or summary is None:
        return
    choices = _choices(gui, keep_programme_id=summary.apprentice.programme_id)

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

    def value(attr: str, default: Any = "") -> Any:
        found = getattr(record, attr, None)
        return default if found is None else found

    return [
        {"kind": "section", "key": "_identity", "label": "Identity"},
        {"key": "given_name", "label": "Legal first name", "required": True,
         "value": value("given_name")},
        {"key": "middle_name", "label": "Middle name(s)", "value": value("middle_name")},
        {"key": "family_name", "label": "Legal last name", "required": True,
         "value": value("family_name")},
        {"key": "preferred_name", "label": "Preferred name", "value": value("preferred_name")},
        {"key": "date_of_birth", "label": "Date of birth",
         "value": value("date_of_birth"), "help": "YYYY-MM-DD"},
        {"key": "gender", "label": "Gender", "kind": "combo",
         "options": ("", *config.GENDERS), "value": value("gender")},
        {"key": "uln", "label": "ULN", "value": value("uln"),
         "help": "Ten digits. Leave blank until the number comes back."},
        {"kind": "section", "key": "_contact", "label": "Contact"},
        {"key": "email", "label": "Email", "value": value("email")},
        {"key": "phone", "label": "Phone", "value": value("phone")},
        {"kind": "section", "key": "_address", "label": "Home address"},
        {"key": "address_line1", "label": "Address line 1", "value": value("address_line1")},
        {"key": "address_line2", "label": "Address line 2", "value": value("address_line2")},
        {"key": "town", "label": "Town / city", "value": value("town")},
        {"key": "postcode", "label": "Postcode", "value": value("postcode")},
        {"kind": "section", "key": "_emergency", "label": "Emergency contact"},
        {"key": "emergency_contact_name", "label": "Name",
         "value": value("emergency_contact_name")},
        {"key": "emergency_contact_relationship", "label": "Relationship", "kind": "combo",
         "options": ("", *config.EMERGENCY_RELATIONSHIPS), "editable": True,
         "value": value("emergency_contact_relationship")},
        {"key": "emergency_contact_phone", "label": "Phone",
         "value": value("emergency_contact_phone")},
        {"kind": "section", "key": "_apprenticeship", "label": "Apprenticeship"},
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
         "value": value("prior_learning")},
        {"kind": "section", "key": "_needs", "label": "Needs and medical"},
        {"key": "has_lldd", "label": "Learning difficulty / disability", "kind": "check",
         "value": value("has_lldd", False)},
        {"key": "has_ehcp", "label": "Has an EHC plan", "kind": "check",
         "value": value("has_ehcp", False)},
        {"key": "support_needs", "label": "Support needs", "kind": "text",
         "value": value("support_needs")},
        {"key": "medical_notes", "label": "Medical notes", "kind": "text",
         "value": value("medical_notes"),
         "help": "Conditions, allergies or medication staff should know about."},
        {"key": "notes", "label": "Notes", "kind": "text", "value": value("notes")},
    ]


def _payload(values: dict[str, Any], choices: dict[str, list]) -> dict[str, Any]:
    payload = {
        key: values.get(key, "")
        for key in (
            "given_name", "family_name", "uln", "date_of_birth", "email", "phone",
            "username", "weekly_hours", "funding_model", "prior_learning",
            "support_needs", "notes", "middle_name", "preferred_name", "gender",
            "address_line1", "address_line2", "town", "postcode",
            "emergency_contact_name", "emergency_contact_relationship",
            "emergency_contact_phone", "has_lldd", "has_ehcp", "medical_notes",
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
            notes=values.get("notes") or None,
            expected_return=values.get("expected_return") or None,
            last_activity_date=values.get("last_activity_date") or None,
        )

    dialog = widgets.FormDialog(
        gui.root, "Change status",
        [
            {"key": "new_status", "label": "New status", "kind": "combo",
             "options": transitions, "value": transitions[0], "required": True},
            {"key": "effective_date", "label": "Effective date",
             "help": "YYYY-MM-DD. Today if left blank."},
            {"key": "reason", "label": "Reason", "kind": "text",
             "help": "Required for a break in learning, a withdrawal or a transfer. "
                     "For a break or withdrawal, a standard reason such as "
                     "'Long-term sickness' or 'Left employment' is filed under it; "
                     "anything else is filed as Other."},
            {"key": "notes", "label": "Details",
             "help": "Anything the reason alone does not say. Needed for Other."},
            {"key": "expected_return", "label": "Expected return",
             "help": "Breaks only. YYYY-MM-DD."},
            {"key": "last_activity_date", "label": "Last day of learning",
             "help": "Withdrawals only. YYYY-MM-DD; the effective date if left blank."},
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


def _apply_curriculum(gui, table: widgets.DataTable) -> None:
    """Put the programme's curriculum modules on the apprentice's learning plan."""
    apprentice_id = table.require_selection_int("apply a curriculum")
    if apprentice_id is None:
        return
    if not widgets.confirm(
        "Add one learning-plan objective for each module of this apprentice's programme?\n\n"
        "Modules already on the plan are left alone, so this only adds what is new.",
        title="Apply curriculum",
    ):
        return
    ok, result = widgets.guard(
        lambda: programme_service.apply_curriculum(gui.actor, apprentice_id)
    )
    if ok:
        widgets.inform(f"Learning plan updated: {result.summary}.")


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

def _choices(gui, *, keep_programme_id: int | None = None) -> dict[str, list[tuple[str, int]]]:
    """Label/id pairs for the form comboboxes.

    Comboboxes hand back the label the user picked, so each list is kept as
    pairs and mapped back to an id on save.

    Programmes are the Active versions a new start may go on, plus — when
    editing — the version already on the record even if it has since been
    superseded. Without it, the combo would open blank and saving the form
    would quietly take the apprentice off their programme.
    """
    _, programmes = widgets.guard(lambda: programme_service.enrolment_options(
        gui.actor, keep_programme_id=keep_programme_id,
    ))
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
            (f"{p.reference} v{getattr(p, 'version', '1.0')} — {p.title}", p.programme_id)
            for p in (programmes or [])
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
