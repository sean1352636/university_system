"""End-Point Assessment Organisations: the directory of who assesses.

Everyone who can see EPA can read the directory. Only an admin adds,
edits or retires an organisation. Retiring keeps the organisation and
every booking already placed with it, so the assessment history still
names who graded it.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.assessments import epa_service

TITLE = "Assessment Organisations"
SUBTITLE = (
    "The End-Point Assessment Organisations bookings can be placed with. "
    "A retired organisation keeps its history but takes no new bookings."
)

COLUMNS = (
    ("name", "Name", 220),
    ("contact", "Contact", 160),
    ("email", "Email", 210),
    ("phone", "Phone", 120),
    ("standards", "Standards", 200),
    ("active", "Status", 80),
)


def render(gui) -> None:
    """Draw the organisation directory into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    if not gui.actor.can("epa.view"):
        widgets.empty_state(frame, "Your role may not see assessment organisations.")
        return

    filters = widgets.FilterBar(
        frame,
        (("active_only", "Active only", "check"),),
        lambda: reload(),
    )
    table = widgets.DataTable(
        frame, COLUMNS,
        on_activate=(lambda ident: _edit(gui, int(ident), reload)) if gui.actor.is_admin else None,
    )

    def reload() -> None:
        _, rows = widgets.guard(
            lambda: epa_service.list_epaos(
                gui.actor, active_only=bool(filters.values().get("active_only")),
            )
        )
        table.populate(
            rows or [],
            lambda e: (
                e.name, e.contact_name, e.contact_email, e.phone, e.standards,
                "Active" if e.active else "Retired",
            ),
            identity=lambda e: e.epao_id,
            tag=lambda e: None if e.active else "Withdrawn",
            noun="organisation",
        )

    def edit_selected() -> None:
        epao_id = table.require_selection_int("edit")
        if epao_id is not None:
            _edit(gui, epao_id, reload)

    def retire_selected() -> None:
        epao_id = table.require_selection_int("retire")
        if epao_id is not None:
            _retire(gui, epao_id, reload)

    if gui.actor.is_admin:
        widgets.button_bar(frame, [
            ("Add Organisation…", lambda: _add(gui, reload)),
            ("Edit…", edit_selected),
            ("Retire…", retire_selected),
            ("Refresh", reload),
        ])
    else:
        widgets.button_bar(frame, [("Refresh", reload)])
    reload()


def _fields(epao: Any | None) -> list[dict[str, Any]]:
    def value(attr: str) -> Any:
        if epao is None:
            return ""
        return getattr(epao, attr, None) or ""

    return [
        {"key": "name", "label": "Name", "required": True, "value": value("name")},
        {"key": "contact_name", "label": "Contact name", "value": value("contact_name")},
        {"key": "contact_email", "label": "Contact email", "value": value("contact_email")},
        {"key": "phone", "label": "Phone", "value": value("phone")},
        {"key": "standards", "label": "Standards", "value": value("standards"),
         "help": "Standard references, separated by commas (e.g. ST0116, ST0787)."},
    ]


def _add(gui, reload) -> None:
    dialog = widgets.FormDialog(
        gui.root, "Add an assessment organisation", _fields(None),
        lambda values: epa_service.create_epao(gui.actor, values),
    )
    if dialog.saved:
        reload()


def _edit(gui, epao_id: int, reload) -> None:
    ok, epao = widgets.guard(lambda: epa_service.get_epao(gui.actor, epao_id))
    if not ok:
        return
    fields = _fields(epao)
    fields.append({"key": "active", "label": "Active", "kind": "check", "value": bool(epao.active)})
    dialog = widgets.FormDialog(
        gui.root, f"Edit {epao.name}", fields,
        lambda values: epa_service.update_epao(gui.actor, epao_id, values),
    )
    if dialog.saved:
        reload()


def _retire(gui, epao_id: int, reload) -> None:
    ok, epao = widgets.guard(lambda: epa_service.get_epao(gui.actor, epao_id))
    if not ok:
        return
    if not epao.active:
        widgets.inform(f"{epao.name} is already retired.", title="Retire")
        return
    if not widgets.confirm(
        f"Retire {epao.name}?\n\nThe organisation and every booking already placed "
        "with it are kept; it just takes no new bookings.",
        title="Retire organisation",
    ):
        return
    if widgets.guard(lambda: epa_service.deactivate_epao(gui.actor, epao_id))[0]:
        reload()
