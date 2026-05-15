"""Tkinter dialog for email-based Multi-Factor Authentication."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.shared import branding
from education_system.sixthform_system.modules.shared.mfa import (
    CODE_TTL_MINUTES,
    MFASetupError,
    confirm_code,
    disable,
    get_email,
    is_enabled,
    send_code,
)

logger = logging.getLogger(__name__)


def open_mfa_dialog(parent=None, *, auth) -> None:
    if auth is None or not getattr(auth, "current_user", None):
        messagebox.showerror(
            "Multi-Factor Authentication",
            "No active session — please sign in again.")
        return
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    MFADialog(win, auth)


class MFADialog:
    def __init__(self, root: tk.Misc, auth) -> None:
        self.root = root
        self.auth = auth
        root.title(f"Multi-Factor Authentication — {branding.SYSTEM_NAME}")
        root.resizable(False, False)
        try:
            root.transient(root.master)
        except tk.TclError:
            pass
        root.after_idle(root.grab_set)
        self._build()
        self._refresh()

    def _build(self) -> None:
        self.outer = ttk.Frame(self.root)
        self.outer.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(self.outer, text="Multi-Factor Authentication",
                  font=("", 13, "bold")).pack(anchor="w")
        ttk.Label(
            self.outer,
            text=("Adds a second sign-in step using your email: a 6-digit "
                  "code is emailed to you and you type it back here to "
                  "confirm."),
            wraplength=460, justify="left", foreground="#555",
        ).pack(anchor="w", pady=(2, 12))

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.outer, textvariable=self.status_var,
                  font=("", 11, "bold")).pack(anchor="w")

        self.email_var = tk.StringVar(value="")
        ttk.Label(self.outer, textvariable=self.email_var,
                  foreground="#555").pack(anchor="w", pady=(0, 10))

        self.body = ttk.Frame(self.outer)
        self.body.pack(fill="both", expand=True)

        bar = ttk.Frame(self.outer)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text="Close",
                   command=self.root.destroy).pack(side="right")

    def _clear_body(self) -> None:
        for w in self.body.winfo_children():
            w.destroy()

    def _refresh(self) -> None:
        self._clear_body()
        try:
            enabled = is_enabled(self.auth)
        except MFASetupError as e:
            messagebox.showerror("MFA", str(e), parent=self.root)
            self.root.destroy()
            return
        email = get_email(self.auth)
        if enabled:
            self.status_var.set("Status: ENABLED")
            self.email_var.set(f"Verified email: {email or '(none)'}")
            self._render_enabled(email or "")
        else:
            self.status_var.set("Status: disabled")
            self.email_var.set(f"Stored email: {email}" if email else "")
            self._render_disabled(email or "")

    def _render_disabled(self, prefill: str) -> None:
        ttk.Label(
            self.body,
            text="Enter the email address you want codes sent to:",
        ).pack(anchor="w", pady=(4, 2))
        self.email_entry = ttk.Entry(self.body, width=42)
        self.email_entry.insert(0, prefill)
        self.email_entry.pack(anchor="w", pady=(0, 8))
        self.email_entry.focus_set()
        ttk.Button(self.body, text="Send verification code",
                   command=self._on_send).pack(anchor="w")

    def _render_enabled(self, prefill: str) -> None:
        ttk.Label(
            self.body,
            text=("MFA is active. You can re-verify (e.g. to change the "
                  "email on file) or turn it off."),
            wraplength=460, justify="left",
        ).pack(anchor="w", pady=(4, 6))

        ttk.Label(self.body, text="Email to re-verify with:").pack(anchor="w")
        self.email_entry = ttk.Entry(self.body, width=42)
        self.email_entry.insert(0, prefill)
        self.email_entry.pack(anchor="w", pady=(2, 8))

        row = ttk.Frame(self.body)
        row.pack(anchor="w")
        ttk.Button(row, text="Send verification code",
                   command=self._on_send).pack(side="left")
        ttk.Button(row, text="Disable MFA",
                   command=self._on_disable).pack(side="left", padx=8)

    def _on_send(self) -> None:
        email = self.email_entry.get().strip()
        try:
            send_code(self.auth, email)
        except MFASetupError as e:
            messagebox.showerror("MFA", str(e), parent=self.root)
            return
        self._render_confirm(email)

    def _render_confirm(self, email: str) -> None:
        self._clear_body()
        self.status_var.set("Status: awaiting code")
        self.email_var.set(f"Sent to: {email}")

        ttk.Label(
            self.body,
            text=(f"We've sent a 6-digit code to {email}. "
                  f"It expires in {CODE_TTL_MINUTES} minutes."),
            wraplength=460, justify="left",
        ).pack(anchor="w", pady=(4, 6))

        ttk.Label(self.body, text="Enter the code:").pack(anchor="w")
        code_e = ttk.Entry(self.body, width=12, justify="center")
        code_e.pack(anchor="w", pady=(2, 6))
        code_e.focus_set()

        msg_var = tk.StringVar(value="")
        ttk.Label(self.body, textvariable=msg_var,
                  foreground="#a00", wraplength=460,
                  justify="left").pack(anchor="w")

        def _confirm() -> None:
            try:
                ok = confirm_code(self.auth, code_e.get())
            except MFASetupError as e:
                msg_var.set(str(e))
                return
            if not ok:
                msg_var.set("That code didn't match — try again.")
                code_e.delete(0, "end")
                code_e.focus_set()
                return
            messagebox.showinfo(
                "MFA",
                "MFA enabled.\n\nYour email is now linked as a second "
                "factor — keep it accessible, you'll get a fresh code "
                "next time MFA is required.",
                parent=self.root)
            self._refresh()

        def _resend() -> None:
            try:
                send_code(self.auth, email)
            except MFASetupError as e:
                msg_var.set(str(e))
                return
            msg_var.set(f"A fresh code has been sent to {email}.")
            code_e.delete(0, "end")
            code_e.focus_set()

        bar = ttk.Frame(self.body)
        bar.pack(anchor="w", pady=(6, 0))
        ttk.Button(bar, text="Confirm", command=_confirm).pack(side="left")
        ttk.Button(bar, text="Resend code", command=_resend).pack(
            side="left", padx=8)
        ttk.Button(bar, text="Back", command=self._refresh).pack(
            side="left")

        self.root.bind("<Return>", lambda _e: _confirm())

    def _on_disable(self) -> None:
        if not messagebox.askyesno(
                "Disable MFA",
                "Turn MFA off? Sign-ins will no longer require a code.",
                parent=self.root):
            return
        try:
            disable(self.auth)
        except MFASetupError as e:
            messagebox.showerror("MFA", str(e), parent=self.root)
            return
        self._refresh()
