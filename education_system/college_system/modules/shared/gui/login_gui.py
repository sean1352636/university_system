"""Login GUI for the College Management System.

Delegates to a college-specific LoginFrame that uses the college auth
and i18n infrastructure.
"""

import tkinter as tk
from tkinter import ttk
import logging

from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.shared.auth.exceptions import AuthError
from education_system.college_system.core.i18n import t

logger = logging.getLogger(__name__)


class LoginFrame(tk.Frame):
    """Login screen with username and password fields.

    On successful authentication the *on_login* callback is invoked with the
    user-info dict returned by ``UserAuth.login()``.
    """

    def __init__(self, parent, db_path=None, auth=None, on_login=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth or UserAuth(db_path)
        self._on_login = on_login

        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#f0f0f0")

        outer = tk.Frame(self, bg="#f0f0f0")
        outer.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            outer, text=t("login.title"),
            font=("Helvetica", 22, "bold"), bg="#f0f0f0", fg="#2c3e50",
        ).pack(pady=(0, 5))

        tk.Label(
            outer, text=t("login.subtitle"),
            font=("Helvetica", 11), bg="#f0f0f0", fg="#7f8c8d",
        ).pack(pady=(0, 25))

        card = tk.Frame(outer, bg="white", bd=1, relief="solid", padx=40, pady=30)
        card.pack()

        tk.Label(
            card, text=t("login.username"), font=("Helvetica", 10, "bold"),
            bg="white", anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._username_var = tk.StringVar()
        username_entry = ttk.Entry(card, textvariable=self._username_var, width=32,
                                   font=("Helvetica", 11))
        username_entry.pack(fill="x", ipady=4, pady=(0, 14))
        username_entry.focus_set()

        tk.Label(
            card, text=t("login.password"), font=("Helvetica", 10, "bold"),
            bg="white", anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._password_var = tk.StringVar()
        password_entry = ttk.Entry(card, textvariable=self._password_var, width=32,
                                   show="*", font=("Helvetica", 11))
        password_entry.pack(fill="x", ipady=4, pady=(0, 20))

        password_entry.bind("<Return>", lambda _e: self._do_login())
        username_entry.bind("<Return>", lambda _e: self._do_login())

        ttk.Button(card, text=t("login.login_button"), command=self._do_login).pack(fill="x", ipady=6)

        self._error_var = tk.StringVar()
        self._error_lbl = tk.Label(
            card, textvariable=self._error_var,
            font=("Helvetica", 9), fg="red", bg="white", wraplength=260,
        )
        self._error_lbl.pack(fill="x", pady=(12, 0))

    def _do_login(self):
        username = self._username_var.get().strip()
        password = self._password_var.get().strip()

        if not username or not password:
            self._show_error(t("login.empty_fields"))
            return

        try:
            user_info = self._auth.login(username, password)
        except AuthError as exc:
            logger.warning("GUI login failed for '%s': %s", username, exc)
            self._show_error(str(exc))
            return
        except Exception as exc:
            logger.error("GUI login unexpected error: %s", exc)
            self._show_error(t("login.unexpected_error", error=str(exc)))
            return

        if user_info.get("mfa_required"):
            from education_system.college_system.modules.shared.gui.mfa_gui import MFAVerifyDialog
            dialog = MFAVerifyDialog(
                self.winfo_toplevel(), self._auth, user_info["user_id"],
                on_success=self._on_mfa_success,
            )
            self.wait_window(dialog)
            return

        self._error_var.set("")
        self._username_var.set("")
        self._password_var.set("")

        if self._on_login:
            self._on_login(user_info)

    def _on_mfa_success(self, user_info: dict):
        self._error_var.set("")
        self._username_var.set("")
        self._password_var.set("")
        if self._on_login:
            self._on_login(user_info)

    def _show_error(self, message: str):
        self._error_var.set(message)

    def reset(self):
        """Clear all fields and errors."""
        self._username_var.set("")
        self._password_var.set("")
        self._error_var.set("")
