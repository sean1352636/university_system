"""MFA verification dialog for the shared auth system."""

import tkinter as tk
from tkinter import ttk

from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.exceptions import AuthError


class MFAVerifyDialog(tk.Toplevel):
    """Modal dialog for MFA code entry."""

    def __init__(self, parent, auth: UserAuth, user_id: int,
                 on_success=None):
        super().__init__(parent)
        self.title("Two-Factor Authentication")
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)

        self._auth = auth
        self._user_id = user_id
        self._on_success = on_success

        body = tk.Frame(self, padx=30, pady=20)
        body.pack()

        tk.Label(body, text="Enter your authentication code:",
                 font=("Helvetica", 11)).pack(pady=(0, 10))

        self._code_var = tk.StringVar()
        entry = ttk.Entry(body, textvariable=self._code_var, width=20,
                          font=("Helvetica", 14), justify="center")
        entry.pack(ipady=4, pady=(0, 15))
        entry.focus_set()
        entry.bind("<Return>", lambda _: self._verify())

        self._error_var = tk.StringVar()
        tk.Label(body, textvariable=self._error_var, fg="red",
                 font=("Helvetica", 9)).pack(pady=(0, 10))

        ttk.Button(body, text="Verify", command=self._verify).pack(fill="x", ipady=4)

        # Centre on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def _verify(self):
        code = self._code_var.get().strip()
        if not code:
            self._error_var.set("Please enter a code.")
            return

        try:
            user_info = self._auth.verify_mfa(self._user_id, code)
        except AuthError as exc:
            self._error_var.set(str(exc))
            return

        if self._on_success:
            self._on_success(user_info)
        self.destroy()
