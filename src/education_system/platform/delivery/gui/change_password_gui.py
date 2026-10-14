"""Shared change-password UI for every system using the platform login.

Two entry points, because the shells want different shapes:

* :class:`ChangePasswordFrame` — embeddable panel (apprenticeships and
  fe_college pack it straight into their content pane)
* :func:`open_change_password_dialog` — modal ``Toplevel`` wrapper (the
  school systems open it over their main window)

All validation lives in ``platform/identity/auth/change_password.py``,
so the CLI and both GUI shapes enforce exactly one set of rules.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.platform import branding
from education_system.platform.identity.auth.change_password import (
    ChangePasswordError,
    change_password,
    current_username,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ChangePasswordFrame",
    "open_change_password_dialog",
]


class ChangePasswordFrame(ttk.Frame):
    """An embeddable password form backed only by the shared auth service."""

    def __init__(self, parent: tk.Misc, *, auth: Any, **kwargs: Any) -> None:
        super().__init__(parent, **kwargs)
        self.auth = auth
        self._entries: list[ttk.Entry] = []
        self._build()

    def _build(self) -> None:
        ttk.Label(self, text="Change Password", font=("", 15, "bold")).pack(anchor="w")
        ttk.Label(
            self,
            text=f"Shared platform account: {current_username(self.auth)}",
            foreground="#555",
        ).pack(anchor="w", pady=(2, 14))

        form = ttk.Frame(self)
        form.pack(anchor="w", fill="x")
        form.columnconfigure(1, weight=1)
        for row, label in enumerate(
            ("Current password", "New password", "Confirm new password")
        ):
            ttk.Label(form, text=label).grid(
                row=row, column=0, sticky="e", padx=(0, 8), pady=4
            )
            entry = ttk.Entry(form, show="•", width=36)
            entry.grid(row=row, column=1, sticky="w", pady=4)
            self._entries.append(entry)

        show = tk.BooleanVar(value=False)

        def toggle() -> None:
            marker = "" if show.get() else "•"
            for entry in self._entries:
                entry.configure(show=marker)

        ttk.Checkbutton(
            form, text="Show passwords", variable=show, command=toggle
        ).grid(row=3, column=1, sticky="w", pady=(3, 10))

        ttk.Label(
            self,
            text="Your new password must meet the platform password policy and must "
            "not match any of your five most recent passwords.",
            foreground="#555",
            wraplength=650,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        self._status = ttk.Label(self, text="", foreground="#a00", wraplength=650)
        self._status.pack(anchor="w", pady=(0, 8))
        ttk.Button(self, text="Change Password", command=self._save).pack(anchor="w")
        self._entries[0].focus_set()
        # Bind per-entry, not with bind_all: this frame is embedded in a
        # long-lived shell, and a global Return binding would fire the
        # save from anywhere in the application.
        for entry in self._entries:
            entry.bind("<Return>", lambda _event: self._save())

    def _save(self) -> None:
        current, new, confirm = (entry.get() for entry in self._entries)
        self._status.configure(text="")
        try:
            change_password(
                self.auth,
                current_password=current,
                new_password=new,
                confirm_password=confirm,
            )
        except ChangePasswordError as exc:
            self._status.configure(text=str(exc))
            return
        except Exception as exc:
            logger.exception("Change password failed")
            self._status.configure(text=f"Unexpected error: {exc}")
            return
        for entry in self._entries:
            entry.delete(0, tk.END)
        messagebox.showinfo(
            "Password Changed",
            "Your shared platform password has been changed successfully.\n\n"
            "You may need to sign in again on other devices.",
            parent=self.winfo_toplevel(),
        )


def open_change_password_dialog(parent: tk.Misc | None = None, *, auth: Any) -> None:
    """Open the shared form as a modal dialog.

    ``parent`` may be a Tk widget or a shell object holding one on
    ``.root`` — the school shells pass either, so unwrap before use.
    """
    if auth is None or not (
        isinstance(auth, dict) or getattr(auth, "current_user", None)
    ):
        messagebox.showerror(
            "Change Password", "No active session — please sign in again."
        )
        return

    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Change Password — {branding.SYSTEM_NAME}")
    win.resizable(False, False)
    try:
        win.transient(master)
    except tk.TclError:
        pass

    frame = ChangePasswordFrame(win, auth=auth, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Button(win, text="Close", command=win.destroy).pack(
        anchor="e", padx=20, pady=(0, 16)
    )
    win.after_idle(win.grab_set)
