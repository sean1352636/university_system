"""Tk views for Multi-Factor Authentication in the Secondary School System."""

from __future__ import annotations

import functools
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from education_system.nursery_system import SYSTEM_NAME
from education_system.shared.auth.email_mfa import EmailMFAService
from education_system.shared.auth.exceptions import MFAError

logger = logging.getLogger(__name__)


def _safe_view(func: Callable[..., None]) -> Callable[..., None]:
    @functools.wraps(func)
    def wrapper(host, *args, **kwargs):
        try:
            return func(host, *args, **kwargs)
        except MFAError as e:
            logger.warning("%s MFA: %s", func.__name__, e)
            try:
                messagebox.showerror("Multi-Factor Authentication", str(e),
                                     parent=getattr(host, "root", None))
            except Exception:
                pass
        except Exception as e:
            logger.exception("%s failed", func.__name__)
            try:
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\nSee logs for details.",
                    parent=getattr(host, "root", None),
                )
            except Exception:
                pass
    return wrapper


def _user_context(host) -> tuple[int, str, str | None]:
    auth = getattr(host, "auth", None)
    if auth is None or not getattr(auth, "current_user", None):
        raise MFAError("Not signed in.")
    cu = auth.current_user
    uid = cu.get("user_id") or cu.get("id")
    if uid is None:
        raise MFAError("Cannot find your user id in this session.")
    return int(uid), cu.get("username", "?"), cu.get("email") or None


@_safe_view
def open_mfa(host) -> None:
    logger.debug("GUI: open_mfa")
    uid, username, account_email = _user_context(host)
    svc = EmailMFAService()

    host._clear_content()
    root = host.content_frame
    ttk.Label(root, text="Multi-Factor Authentication",
              font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(
        root,
        text=("Email-based MFA — a 6-digit code is sent to the address "
              "below. Set / change the address, then send and verify a "
              "code to enable."),
        wraplength=720, foreground="#555", justify="left",
    ).pack(anchor="w", pady=(0, 12))

    # Status strip
    status_frame = ttk.LabelFrame(root, text="Status", padding=10)
    status_frame.pack(fill="x", pady=(0, 12))
    status_var       = tk.StringVar()
    email_status_var = tk.StringVar()
    account_var      = tk.StringVar(
        value=f"Signed in as {username} (user_id={uid})"
              + (f" — account email: {account_email}" if account_email else ""))
    ttk.Label(status_frame, textvariable=status_var,
              font=("", 12, "bold")).pack(anchor="w")
    ttk.Label(status_frame, textvariable=email_status_var,
              foreground="#555").pack(anchor="w", pady=(2, 0))
    ttk.Label(status_frame, textvariable=account_var,
              foreground="#888", font=("", 9)).pack(anchor="w", pady=(2, 0))

    # Address form
    addr = ttk.LabelFrame(root, text="MFA email address", padding=10)
    addr.pack(fill="x", pady=(0, 12))
    email_var = tk.StringVar()
    row = ttk.Frame(addr)
    row.pack(fill="x")
    ttk.Label(row, text="Send codes to:").pack(side="left", padx=(0, 6))
    ttk.Entry(row, textvariable=email_var, width=36).pack(
        side="left", fill="x", expand=True)
    ttk.Button(row, text="Save",
               command=lambda: _do_set_email()).pack(side="left", padx=(8, 0))

    # Code form
    code_frame = ttk.LabelFrame(root, text="Verification code", padding=10)
    code_frame.pack(fill="x", pady=(0, 12))
    code_var = tk.StringVar()
    crow = ttk.Frame(code_frame)
    crow.pack(fill="x")
    ttk.Button(crow, text="Send code",
               command=lambda: _do_send_code()).pack(side="left")
    ttk.Label(crow, text="    Enter code:").pack(side="left", padx=(8, 6))
    code_entry = ttk.Entry(crow, textvariable=code_var, width=12,
                            font=("", 12))
    code_entry.pack(side="left")
    code_entry.bind("<Return>", lambda _e: _do_verify())
    ttk.Button(crow, text="Verify",
               command=lambda: _do_verify()).pack(side="left", padx=(8, 0))
    code_status_var = tk.StringVar(value="No code outstanding.")
    ttk.Label(code_frame, textvariable=code_status_var,
              foreground="#666").pack(anchor="w", pady=(8, 0))

    # Bottom actions
    bottom = ttk.Frame(root)
    bottom.pack(fill="x", pady=(4, 0))
    ttk.Button(bottom, text="Disable MFA",
               command=lambda: _do_disable()).pack(side="right")

    # ── Behaviour ─────────────────────────────────────────────────

    def _refresh_status() -> None:
        enabled = svc.is_enabled(uid)
        on_file = svc.get_email(uid)
        status_var.set("MFA is ENABLED" if enabled else "MFA is disabled")
        if on_file:
            email_status_var.set(f"Codes go to: {on_file}")
            email_var.set(on_file)
        else:
            email_status_var.set("No MFA email set yet.")
            if account_email and not email_var.get().strip():
                email_var.set(account_email)
        host.status_var.set(
            f"MFA: {'enabled' if enabled else 'disabled'}"
            + (f" ({on_file})" if on_file else ""))

    def _action(func: Callable[[], None]) -> Callable[[], None]:
        """Local closure-scoped error wrapper for the button handlers."""
        @functools.wraps(func)
        def inner() -> None:
            try:
                return func()
            except MFAError as e:
                logger.warning("%s MFA: %s", func.__name__, e)
                messagebox.showerror("Multi-Factor Authentication",
                                     str(e), parent=host.root)
            except Exception as e:
                logger.exception("%s failed", func.__name__)
                messagebox.showerror(
                    "Error",
                    f"An unexpected error occurred:\n\n{e}\n\n"
                    "See logs for details.",
                    parent=host.root,
                )
        return inner

    @_action
    def _do_set_email() -> None:
        addr_text = email_var.get().strip()
        if not addr_text:
            messagebox.showerror("MFA", "Enter an email address.",
                                 parent=host.root)
            return
        email = svc.set_email(uid, addr_text)
        code_status_var.set("Address updated — request a new code to verify.")
        _refresh_status()
        messagebox.showinfo("MFA",
                            f"MFA email set to {email}.",
                            parent=host.root)

    @_action
    def _do_send_code() -> None:
        addr_text = email_var.get().strip() or None
        # If the user typed something different from what's on file,
        # treat that as an override (don't silently persist).
        result = svc.send_code(uid,
                               override_email=addr_text,
                               username=username,
                               system_name=SYSTEM_NAME)
        # send_code either succeeded or raised MFAError (caught by @_action).
        code_status_var.set(
            f"Code sent to {result['sent_to']} — check your inbox.")
        messagebox.showinfo(
            "MFA",
            f"Code sent to {result['sent_to']}.\n\n"
            "Enter the 6-digit code below to verify and enable MFA.",
            parent=host.root,
        )

    @_action
    def _do_verify() -> None:
        code = code_var.get().strip()
        if not code:
            messagebox.showerror("MFA", "Enter the code first.",
                                 parent=host.root)
            return
        if svc.verify_code(uid, code):
            code_var.set("")
            code_status_var.set("Code verified.")
            _refresh_status()
            messagebox.showinfo(
                "MFA",
                "Code verified. MFA is now ENABLED on your account."
                if svc.is_enabled(uid) else "Code verified.",
                parent=host.root,
            )

    @_action
    def _do_disable() -> None:
        if not svc.is_enabled(uid) and svc.get_email(uid) is None:
            messagebox.showinfo("MFA", "MFA is not set up — nothing to disable.",
                                parent=host.root)
            return
        if not messagebox.askyesno("Disable MFA",
                                    "Really disable MFA on your account?",
                                    parent=host.root):
            return
        svc.disable(uid)
        email_var.set("")
        code_status_var.set("MFA disabled.")
        _refresh_status()

    _refresh_status()
