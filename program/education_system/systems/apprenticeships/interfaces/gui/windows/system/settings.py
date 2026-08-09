"""Settings.

Three preferences, each with one place it actually takes effect — the
cell formatter, the table height, and the shell's idle timer. Nothing
here is cosmetic-only: a setting a screen quietly ignores is worse than
no setting at all, so this screen offers only what the system reads.

They are stored against the login rather than the interface, so a change
made here shows up in the CLI too.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import preferences

logger = logging.getLogger(__name__)

TITLE = "Settings"
SUBTITLE = "Your preferences for this system, in the CLI as well as here."

_EFFECT = {
    preferences.DATE_FORMAT:
        "How every date is rendered, in tables and detail panes alike.",
    preferences.ROWS_PER_PAGE:
        "How many rows a list screen shows before it scrolls, and how many a CLI "
        "table prints before it says how many were held back.",
    preferences.IDLE_TIMEOUT_MINUTES:
        "How long this window may sit untouched before it signs you out. A provider "
        "workstation with an employer's whole cohort on screen should not stay open "
        "all afternoon.",
}


def render(gui) -> None:
    """Draw the settings screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    ok, values = widgets.guard(lambda: preferences.get(gui.actor), title="Settings")
    if not ok or values is None:
        return

    date_labels = tuple(preferences.DATE_FORMATS)
    row_labels = tuple(str(n) for n in preferences.ROWS_PER_PAGE_CHOICES)
    idle_labels = {
        preferences.idle_timeout_label(n): n for n in preferences.IDLE_TIMEOUT_CHOICES
    }

    controls: dict[str, Any] = {}
    for key, label, options, current in (
        (preferences.DATE_FORMAT, "Date format", date_labels,
         preferences.date_format_label(values[preferences.DATE_FORMAT])),
        (preferences.ROWS_PER_PAGE, "Rows per table", row_labels,
         str(values[preferences.ROWS_PER_PAGE])),
        (preferences.IDLE_TIMEOUT_MINUTES, "Sign me out after", tuple(idle_labels),
         preferences.idle_timeout_label(values[preferences.IDLE_TIMEOUT_MINUTES])),
    ):
        box = widgets.section(frame, label)
        combo = ttk.Combobox(box, values=list(options), state="readonly", width=28)
        combo.set(current)
        combo.pack(anchor="w")
        ttk.Label(
            box, text=_EFFECT[key], foreground=config.MUTED_FG,
            wraplength=760, justify="left",
        ).pack(anchor="w", pady=(4, 0))
        controls[key] = combo

    ttk.Label(
        frame,
        text="A change to the idle timeout takes effect at your next sign-in — the "
             "timer for this session is already running.",
        foreground=config.MUTED_FG, wraplength=760, justify="left",
    ).pack(anchor="w", pady=(8, 0))

    def save() -> None:
        payload = {
            preferences.DATE_FORMAT: controls[preferences.DATE_FORMAT].get(),
            preferences.ROWS_PER_PAGE: controls[preferences.ROWS_PER_PAGE].get(),
            preferences.IDLE_TIMEOUT_MINUTES: idle_labels[
                controls[preferences.IDLE_TIMEOUT_MINUTES].get()
            ],
        }
        ok, _ = widgets.guard(
            lambda: preferences.set_preferences(gui.actor, payload), title="Settings"
        )
        if ok:
            widgets.inform("Settings saved.")
            gui.refresh()

    def reset() -> None:
        if not widgets.confirm(
            "Put every setting back to its default?", title="Reset settings"
        ):
            return
        ok, _ = widgets.guard(lambda: preferences.reset(gui.actor), title="Settings")
        if ok:
            gui.refresh()

    widgets.button_bar(frame, [("Save", save), ("Reset to Defaults", reset)])
