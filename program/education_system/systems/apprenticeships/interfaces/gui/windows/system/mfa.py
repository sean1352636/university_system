"""Multi-Factor Authentication.

Enrolment shows the recovery codes exactly once — only their hashes are
stored — so this screen keeps them on screen with a copy button rather
than in a dialog somebody dismisses on reflex.
"""

from __future__ import annotations

import logging
from tkinter import ttk
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.interfaces.gui import widgets
from education_system.systems.apprenticeships.services import account_service

logger = logging.getLogger(__name__)

TITLE = "Multi-Factor Authentication"
SUBTITLE = "Set up or remove the authenticator app on your account."


def render(gui) -> None:
    """Draw the multi-factor authentication screen into the content pane."""
    frame = gui.clear()
    widgets.heading(frame, TITLE, subtitle=SUBTITLE)

    status = account_service.mfa_status(gui.actor)
    if not status["available"]:
        widgets.empty_state(
            frame,
            "This session is not backed by an account in the shared login database, "
            "so account changes are not available here.",
        )
        return

    widgets.field_grid(frame, [
        ("Status", "On" if status["enabled"] else "Off"),
        ("Recovery codes left", status["recovery_codes_remaining"]
         if status["enabled"] else widgets.EMPTY),
    ], columns=4)

    if status["enabled"] and status["recovery_codes_remaining"] <= 2:
        ttk.Label(
            frame,
            text="Few recovery codes left. Enrol again to generate a fresh set — "
                 "losing the last one means an administrator has to unlock the account.",
            foreground=config.ERROR_FG, wraplength=760, justify="left",
        ).pack(anchor="w", pady=(0, 8))

    box = widgets.section(frame, "About the second factor")
    ttk.Label(
        box,
        text="Your login reaches five other systems with the same password. A second "
             "factor is what stops a leaked one being enough on its own.",
        foreground=config.MUTED_FG, wraplength=760, justify="left",
    ).pack(anchor="w")

    buttons: list[tuple[str, Any]] = [
        ("Enrol Authenticator" if not status["enabled"] else "Re-enrol Authenticator",
         lambda: _enrol(gui, status["enabled"])),
    ]
    if status["enabled"]:
        buttons += [
            ("Turn MFA Off", lambda: _disable(gui)),
            ("Lost Authenticator", lambda: _disable_with_recovery(gui)),
        ]
    widgets.button_bar(frame, buttons)


# ═════════════════════════════════════════════════════════════════════
# Enrolment
# ═════════════════════════════════════════════════════════════════════

def _enrol(gui, already_enabled: bool) -> None:
    if already_enabled and not widgets.confirm(
        "MFA is already on. Enrolling again replaces the secret and invalidates "
        "every existing recovery code.\n\nContinue?",
        title="Re-enrol",
    ):
        return

    ok, result = widgets.guard(lambda: account_service.enrol_mfa(gui.actor), title="Enrol")
    if not ok or result is None:
        return
    _show_enrolment(gui, result)


def _show_enrolment(gui, result: dict[str, Any]) -> None:
    """The secret and the recovery codes, on screen until they move on."""
    frame = gui.clear()
    widgets.heading(
        frame, "Enrol your authenticator",
        subtitle="Add this account to your authenticator app, then confirm a code.",
    )

    key_box = widgets.section(frame, "Setup key")
    _copyable(key_box, result["secret"])
    ttk.Label(
        key_box,
        text="Or paste this provisioning URI into an app that accepts one:",
        foreground=config.MUTED_FG,
    ).pack(anchor="w", pady=(8, 2))
    _copyable(key_box, result["provisioning_uri"])

    codes_box = widgets.section(frame, "Recovery codes — shown once")
    ttk.Label(
        codes_box,
        text="Write these down or store them somewhere other than the phone running "
             "the authenticator. Only their hashes are kept, so this screen is the "
             "only time they exist in readable form. Each one works once.",
        foreground=config.ERROR_FG, wraplength=760, justify="left",
    ).pack(anchor="w", pady=(0, 6))
    _copyable(codes_box, "\n".join(result["recovery_codes"]), height=len(
        result["recovery_codes"]
    ))

    confirm_box = widgets.section(frame, "Confirm it works")
    ttk.Label(
        confirm_box,
        text="Enter the six-digit code your app is showing. MFA is already active — "
             "this checks the app took the key before you rely on it at sign-in.",
        foreground=config.MUTED_FG, wraplength=760, justify="left",
    ).pack(anchor="w", pady=(0, 6))

    row = ttk.Frame(confirm_box)
    row.pack(anchor="w")
    entry = ttk.Entry(row, width=12)
    entry.pack(side="left", padx=(0, 8))
    outcome = ttk.Label(row, text="", wraplength=520)
    outcome.pack(side="left")

    def check() -> None:
        ok, valid = widgets.guard(
            lambda: account_service.confirm_mfa(gui.actor, entry.get()), title="Confirm"
        )
        if not ok:
            return
        if valid:
            outcome.config(
                text="Confirmed — you will be asked for a code at your next sign-in.",
                foreground="#0a6b2d",
            )
        else:
            outcome.config(
                text="Not accepted. Check the app's clock is right, or enrol again.",
                foreground=config.ERROR_FG,
            )

    ttk.Button(row, text="Confirm", command=check).pack(side="left")
    entry.focus_set()

    widgets.button_bar(frame, [("Done", lambda: render(gui))])


def _copyable(parent: Any, text: str, *, height: int = 1) -> None:
    """Read-only text the user can select and copy, but not edit."""
    import tkinter as tk

    widget = tk.Text(parent, height=height, wrap="char", relief="solid", borderwidth=1)
    widget.insert("1.0", text)
    widget.configure(state="disabled")
    widget.pack(fill="x", pady=2)

    def copy() -> None:
        parent.clipboard_clear()
        parent.clipboard_append(text)
        parent.update_idletasks()

    ttk.Button(parent, text="Copy", command=copy).pack(anchor="w", pady=(2, 0))


# ═════════════════════════════════════════════════════════════════════
# Turning it off
# ═════════════════════════════════════════════════════════════════════

def _disable(gui) -> None:
    """Off, once a current code proves the authenticator is to hand."""
    fields = [
        {"key": "code", "label": "Code from the app", "required": True,
         "help": "Required so an unlocked, unattended session cannot strip the "
                 "second factor off the account."},
    ]

    def save(values: dict[str, Any]) -> None:
        account_service.disable_mfa(gui.actor, values["code"])

    if widgets.FormDialog(gui.root, "Turn MFA off", fields, save).saved:
        widgets.inform("MFA is off. Your recovery codes have been discarded.")
        gui.refresh()


def _disable_with_recovery(gui) -> None:
    """Off using a recovery code, for a lost or replaced authenticator."""
    fields = [
        {"key": "code", "label": "Recovery code", "required": True,
         "help": "One of the XXXX-XXXX codes from enrolment. It is used up either way."},
    ]

    def save(values: dict[str, Any]) -> None:
        account_service.disable_mfa_with_recovery_code(gui.actor, values["code"])

    if widgets.FormDialog(gui.root, "Lost authenticator", fields, save).saved:
        widgets.inform("MFA is off. Enrol a new authenticator when you have one.")
        gui.refresh()
