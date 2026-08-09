"""Change Password.

The password belongs to the shared platform account, not to this
system, so everything here goes through ``services.account_service``.
The one thing this screen owes the user beyond a form is the warning
that saving signs every session out — including the one they are
looking at.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import account_service

logger = logging.getLogger(__name__)

TITLE = "Change Password"
SUBTITLE = "Change the password on your shared platform account."


def render(gui) -> None:
    """Draw the change password screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    account = account_service.whoami(gui.actor)
    if account["user_id"] is None:
        widgets.empty_state(
            frame,
            "This session is not backed by an account in the shared login database, "
            "so account changes are not available here.",
        )
        return

    widgets.field_grid(frame, [
        ("Signed in as", account["username"]),
        ("Name", account["display_name"]),
        ("Email", account["email"]),
        ("Must change password", account["must_change_password"]),
    ], columns=4)

    rules = widgets.section(frame, "What the platform will accept")
    for rule in account_service.password_requirements():
        ttk.Label(rules, text=f"·  {rule}", foreground=config.MUTED_FG).pack(anchor="w")

    box = widgets.section(frame, "New password")
    ttk.Label(
        box,
        text="Saving signs out every session on this account, this one included — "
             "you will be returned to the login screen.",
        foreground=config.MUTED_FG, wraplength=760, justify="left",
    ).pack(anchor="w", pady=(0, 8))

    entries = _form(box)
    error = ttk.Label(frame, text="", foreground=config.ERROR_FG, wraplength=760)
    error.pack(anchor="w", pady=(6, 0))

    def save() -> None:
        error.config(text="")
        try:
            account_service.change_password(
                gui.actor,
                current=entries["current"].get(),
                new=entries["new"].get(),
                confirm=entries["confirm"].get(),
            )
        except Exception as exc:
            # Inline rather than a message box: the user still has three
            # fields filled in and a modal would put the message where
            # they cannot read it next to what they typed.
            error.config(text=str(exc))
            logger.debug("Password change refused", exc_info=True)
            return
        for entry in entries.values():
            entry.delete(0, "end")
        widgets.inform(
            "Password changed.\n\nEvery session on this account has been signed out. "
            "Sign in again with the new password.",
            title="Password changed",
        )
        gui.status_var.set("Password changed — sign in again")

    widgets.button_bar(frame, [("Change Password", save)])


def _form(parent: Any) -> dict[str, ttk.Entry]:
    """The three password boxes, with one show/hide toggle over all of them."""
    grid = ttk.Frame(parent)
    grid.pack(fill="x")
    grid.columnconfigure(1, weight=1)

    entries: dict[str, ttk.Entry] = {}
    for row, (key, label) in enumerate((
        ("current", "Current password"),
        ("new", "New password"),
        ("confirm", "Confirm new password"),
    )):
        ttk.Label(grid, text=label).grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
        entry = ttk.Entry(grid, show="•", width=36)
        entry.grid(row=row, column=1, sticky="w", pady=4)
        entries[key] = entry

    show = tk.BooleanVar(value=False)

    def toggle() -> None:
        character = "" if show.get() else "•"
        for entry in entries.values():
            entry.configure(show=character)

    ttk.Checkbutton(grid, text="Show passwords", variable=show, command=toggle).grid(
        row=3, column=1, sticky="w", pady=(4, 0)
    )
    entries["current"].focus_set()
    return entries
