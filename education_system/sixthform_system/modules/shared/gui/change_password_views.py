"""Tkinter change-password dialog."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from education_system.sixthform_system.modules.shared.change_password import (
    ChangePasswordError,
    change_password,
    current_username,
)

logger = logging.getLogger(__name__)


def open_change_password_dialog(parent=None, *, auth) -> None:
    if auth is None or not getattr(auth, "current_user", None):
        messagebox.showerror(
            "Change Password",
            "No active session — please sign in again.")
        return
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    ChangePasswordDialog(win, auth)


class ChangePasswordDialog:
    def __init__(self, root: tk.Misc, auth) -> None:
        self.root = root
        self.auth = auth
        root.title("Change Password — Sixth Form System")
        root.resizable(False, False)
        try:
            root.transient(root.master)
        except tk.TclError:
            pass
        root.grab_set()
        self._build()

    def _build(self) -> None:
        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(outer, text="Change Password",
                   font=("", 13, "bold")).pack(anchor="w")
        ttk.Label(outer,
                   text=f"Signed in as: {current_username(self.auth)}",
                   foreground="#555").pack(anchor="w", pady=(0, 12))

        form = ttk.Frame(outer)
        form.pack(fill="x")
        r = 0

        def field(label_text: str) -> ttk.Entry:
            nonlocal r
            ttk.Label(form, text=label_text).grid(
                row=r, column=0, sticky="e", pady=4, padx=(0, 8))
            e = ttk.Entry(form, show="•", width=28)
            e.grid(row=r, column=1, sticky="w")
            r += 1
            return e

        self.cur_e = field("Current password:")
        self.new_e = field("New password:")
        self.conf_e = field("Confirm new password:")

        self.show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Show passwords",
                          variable=self.show_var,
                          command=self._toggle_show).grid(
            row=r, column=1, sticky="w", pady=(2, 8))
        r += 1

        self.status_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.status_var,
                   foreground="#a00",
                   wraplength=320, justify="left").pack(
            fill="x", pady=(4, 8))

        bar = ttk.Frame(outer)
        bar.pack(fill="x")
        ttk.Button(bar, text="Change Password",
                    command=self._save).pack(side="left")
        ttk.Button(bar, text="Cancel",
                    command=self.root.destroy).pack(side="left", padx=8)

        self.cur_e.focus_set()
        self.root.bind("<Return>", lambda _e: self._save())

    def _toggle_show(self) -> None:
        ch = "" if self.show_var.get() else "•"
        for e in (self.cur_e, self.new_e, self.conf_e):
            e.configure(show=ch)

    def _save(self) -> None:
        self.status_var.set("")
        try:
            change_password(
                self.auth,
                current_password=self.cur_e.get(),
                new_password=self.new_e.get(),
                confirm_password=self.conf_e.get(),
            )
        except ChangePasswordError as e:
            self.status_var.set(str(e))
            return
        except Exception as e:
            logger.exception("Change password failed")
            self.status_var.set(f"Unexpected error: {e}")
            return
        messagebox.showinfo(
            "Change Password",
            "Password changed.\n\n"
            "You may need to sign in again on other devices.")
        self.root.destroy()
