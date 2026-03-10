"""Login GUI for the College Management System."""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.shared.auth.exceptions import AuthError

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

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Build the login form widgets."""
        self.configure(bg="#f0f0f0")

        # Centre the form within the frame
        outer = tk.Frame(self, bg="#f0f0f0")
        outer.place(relx=0.5, rely=0.5, anchor="center")

        # Title
        title_lbl = tk.Label(
            outer,
            text="College Management System",
            font=("Helvetica", 22, "bold"),
            bg="#f0f0f0",
            fg="#2c3e50",
        )
        title_lbl.pack(pady=(0, 5))

        subtitle_lbl = tk.Label(
            outer,
            text="Please sign in to continue",
            font=("Helvetica", 11),
            bg="#f0f0f0",
            fg="#7f8c8d",
        )
        subtitle_lbl.pack(pady=(0, 25))

        # Card-style container
        card = tk.Frame(outer, bg="white", bd=1, relief="solid", padx=40, pady=30)
        card.pack()

        # Username
        tk.Label(
            card, text="Username", font=("Helvetica", 10, "bold"),
            bg="white", anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._username_var = tk.StringVar()
        username_entry = ttk.Entry(card, textvariable=self._username_var, width=32,
                                   font=("Helvetica", 11))
        username_entry.pack(fill="x", ipady=4, pady=(0, 14))
        username_entry.focus_set()

        # Password
        tk.Label(
            card, text="Password", font=("Helvetica", 10, "bold"),
            bg="white", anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._password_var = tk.StringVar()
        password_entry = ttk.Entry(card, textvariable=self._password_var, width=32,
                                   show="*", font=("Helvetica", 11))
        password_entry.pack(fill="x", ipady=4, pady=(0, 20))

        # Bind Enter key to submit
        password_entry.bind("<Return>", lambda _e: self._do_login())
        username_entry.bind("<Return>", lambda _e: self._do_login())

        # Login button
        login_btn = ttk.Button(card, text="Login", command=self._do_login)
        login_btn.pack(fill="x", ipady=6)

        # Error message label (initially hidden)
        self._error_var = tk.StringVar()
        self._error_lbl = tk.Label(
            card, textvariable=self._error_var,
            font=("Helvetica", 9), fg="red", bg="white", wraplength=260,
        )
        self._error_lbl.pack(fill="x", pady=(12, 0))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _do_login(self):
        """Validate inputs and attempt to log in."""
        username = self._username_var.get().strip()
        password = self._password_var.get().strip()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        try:
            user_info = self._auth.login(username, password)
        except AuthError as exc:
            logger.warning("GUI login failed for '%s': %s", username, exc)
            self._show_error(str(exc))
            return
        except Exception as exc:
            logger.error("GUI login unexpected error: %s", exc)
            self._show_error(f"Unexpected error: {exc}")
            return

        # Handle MFA challenge
        if user_info.get("mfa_required"):
            from education_system.college_system.modules.shared.gui.mfa_gui import MFAVerifyDialog
            dialog = MFAVerifyDialog(
                self.winfo_toplevel(), self._auth, user_info["user_id"],
                on_success=self._on_mfa_success,
            )
            self.wait_window(dialog)
            return

        # Clear error and fields
        self._error_var.set("")
        self._username_var.set("")
        self._password_var.set("")

        if self._on_login:
            self._on_login(user_info)

    def _on_mfa_success(self, user_info: dict):
        """Called when MFA verification succeeds."""
        self._error_var.set("")
        self._username_var.set("")
        self._password_var.set("")

        if self._on_login:
            self._on_login(user_info)

    def _show_error(self, message: str):
        """Display an error message below the login button."""
        self._error_var.set(message)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def reset(self):
        """Clear all fields and errors (useful when returning to this frame)."""
        self._username_var.set("")
        self._password_var.set("")
        self._error_var.set("")
