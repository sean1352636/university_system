"""Audit Log — admin screen.

Who did what, to which record, when — and, for an edit, what each field
said before and after. Filter by entity, by who acted, by the kind of
action and by date range; double-click an entry to see its changes in
full.

Administrators only. The log records every user's actions, so a scoped
view would still show a tutor who else touched their records.

:func:`audit_panel` is the whole screen minus its heading, so the
Compliance screen's audit tab shows exactly the same view.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.records.audit import AuditRecord
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.application.compliance import compliance_service

logger = logging.getLogger(__name__)

# How many entries one search returns. The screen is for finding things,
# not reading the whole log; narrow the filters to go further back.
ROW_LIMIT = 500

AUDIT_COLUMNS = (
    ("ts", "When", 145),
    ("actor", "Who", 110),
    ("role", "Role", 110),
    ("action", "Action", 75),
    ("entity", "Entity", 130),
    ("entity_id", "Record", 80),
    ("changes", "Changes", 420),
    ("detail", "Detail", 320),
)

CHANGE_COLUMNS = (
    ("field", "Field", 200),
    ("before", "Before", 300),
    ("after", "After", 300),
)


def render(gui: Any) -> None:
    frame = gui.clear()
    widgets.heading(
        frame,
        "Audit Log",
        subtitle="Every change to the records: who made it, when, and what each field said "
                 "before and after.",
    )
    if not gui.actor.is_admin:
        widgets.empty_state(frame, "The audit log is for administrators only.")
        return
    audit_panel(gui, frame)


def audit_panel(gui: Any, parent: Any) -> None:
    """Filters, the entry list and the drill-down, packed into *parent*."""
    ok, options = widgets.guard(lambda: compliance_service.audit_filter_options(gui.actor))
    if not ok:
        return

    ttk.Label(
        parent,
        text="Dates are YYYY-MM-DD and include the whole day. Press Enter in a box or "
             f"Refresh to search; the newest {ROW_LIMIT} matching entries are shown.",
        foreground=config.MUTED_FG, wraplength=900, justify="left",
    ).pack(anchor="w", pady=(0, 6))
    filters = widgets.FilterBar(
        parent,
        (
            ("entity", "Entity", "combo", options["entities"]),
            ("actor_username", "Who", "combo", options["actors"]),
            ("action", "Action", "combo", options["actions"]),
            ("entity_id", "Record id", "entry"),
            ("since", "From", "entry"),
            ("until", "To", "entry"),
            ("changes_only", "Edits only", "check"),
        ),
        lambda: reload(),
    )
    rows: dict[int, AuditRecord] = {}
    table: widgets.DataTable | None = None

    def show_selected() -> None:
        ident = table.require_selection_int("see its changes") if table else None
        if ident is not None and ident in rows:
            _entry_window(gui, rows[ident])

    widgets.button_bar(parent, [("Show changes…", show_selected)])
    table = widgets.DataTable(parent, AUDIT_COLUMNS, on_activate=lambda _i: show_selected())

    def reload() -> None:
        ok, found = widgets.guard(lambda: compliance_service.audit_trail(
            gui.actor, limit=ROW_LIMIT, **filters.values()
        ))
        found = found if ok and found else []
        rows.clear()
        rows.update({e.audit_id: e for e in found})
        assert table is not None
        table.populate(
            found,
            lambda e: (e.ts, e.actor, config.ROLE_LABELS.get(e.actor_role or "", e.actor_role),
                       e.action, e.entity, e.entity_id, _changes(e), e.detail),
            identity=lambda e: e.audit_id,
            noun="entry",
        )

    reload()


def _changes(entry: Any) -> str:
    """``field: before → after; …`` — blank for an entry that is not an edit."""
    return entry.changes_text if isinstance(entry, AuditRecord) else ""


def _entry_window(gui: Any, entry: AuditRecord) -> None:
    win = widgets.open_window(gui, f"Audit entry {entry.audit_id}", geometry="900x460")
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    widgets.heading(body, f"{entry.action.title()} — {entry.entity} {entry.entity_id or ''}")
    widgets.field_grid(body, [
        ("When", entry.ts),
        ("Who", entry.actor),
        ("Role", config.ROLE_LABELS.get(entry.actor_role or "", entry.actor_role)),
        ("Detail", entry.detail),
    ])
    widgets.button_bar(body, [("Close", win.destroy)])
    if not entry.changes:
        widgets.empty_state(body, "This entry records an event, not an edit to fields.")
        return
    table = widgets.DataTable(body, CHANGE_COLUMNS, height=min(10, len(entry.changes)))
    table.populate(
        list(enumerate(entry.changes)),
        lambda pair: (pair[1].field, _show(pair[1].before), _show(pair[1].after)),
        identity=lambda pair: pair[0],
        noun="change",
    )


def _show(value: Any) -> str:
    return config.EMPTY_CELL if value in (None, "") else str(value)
