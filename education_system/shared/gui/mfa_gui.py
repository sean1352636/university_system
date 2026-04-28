"""Shared MFA GUI components used by all education subsystems.

Provides:
- MFAVerifyDialog: modal dialog shown during login when MFA is required
- MFASettingsFrame: sidebar frame for managing MFA setup/disable

Both classes use the shared auth module and accept an ``auth`` parameter
that can be either a ``UserAuth`` instance or a user-info dict.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.shared.auth.core import UserAuth
from education_system.shared.auth.mfa_service import MFAService
from education_system.shared.auth.exceptions import AuthError


class MFAVerifyDialog(tk.Toplevel):
    """Modal dialog for MFA code entry during login.

    After successful verification the *on_success* callback is invoked
    with the user-info dict.  The ``result`` property holds the same
    dict (or ``None`` if cancelled).
    """

    def __init__(self, parent, auth: UserAuth, user_id: int, on_success=None):
        super().__init__(parent)
        self._auth = auth
        self._user_id = user_id
        self._on_success = on_success
        self._result = None

        self.title("Two-Factor Authentication")
        self.geometry("350x200")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self):
        frame = tk.Frame(self, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Enter MFA Code",
                 font=("Helvetica", 14, "bold")).pack(pady=(0, 5))
        tk.Label(frame, text="Enter your 6-digit authenticator code or recovery code",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(pady=(0, 15))

        self._code_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self._code_var, width=20,
                          font=("Helvetica", 12), justify="center")
        entry.pack(pady=(0, 15))
        entry.focus_set()
        entry.bind("<Return>", lambda _: self._verify())

        btn_frame = tk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Verify", command=self._verify).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="left", padx=5)

        self._error_var = tk.StringVar()
        tk.Label(frame, textvariable=self._error_var, fg="red",
                 font=("Helvetica", 9)).pack(pady=(10, 0))

    def _verify(self):
        code = self._code_var.get().strip()
        if not code:
            self._error_var.set("Please enter a code.")
            return

        try:
            user_info = self._auth.verify_mfa(self._user_id, code)
            self._result = user_info
            self.destroy()
            if self._on_success:
                self._on_success(user_info)
        except Exception as e:
            self._error_var.set(str(e))

    def _on_cancel(self):
        self._result = None
        self.destroy()

    @property
    def result(self):
        return self._result


class MFASettingsFrame(tk.Frame):
    """MFA settings management frame for embedding in a sidebar or settings area.

    Parameters
    ----------
    parent : tk widget
    db_path : str or None
        Path to the auth database (passed to MFAService).
    auth : UserAuth or dict
        Either a ``UserAuth`` instance (with ``current_user``) or a plain
        user-info dict containing ``user_id`` and ``username`` keys.
    """

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = MFAService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="MFA Settings",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        # Info
        info_frame = tk.Frame(self, bg="#ecf0f1", padx=20, pady=10)
        info_frame.pack(fill="x")
        tk.Label(info_frame,
                 text="Multi-Factor Authentication adds an extra layer of security\n"
                      "to your account using a TOTP authenticator app.",
                 font=("Helvetica", 10), bg="#ecf0f1", fg="#34495e",
                 justify="left").pack(anchor="w")

        # Status
        status_frame = tk.LabelFrame(self, text="Current Status", bg="#ecf0f1", padx=15, pady=10)
        status_frame.pack(fill="x", padx=20, pady=10)

        self._status_var = tk.StringVar(value="Checking...")
        tk.Label(status_frame, textvariable=self._status_var,
                 font=("Helvetica", 12, "bold"), bg="#ecf0f1").pack(anchor="w")

        self._recovery_var = tk.StringVar(value="")
        tk.Label(status_frame, textvariable=self._recovery_var,
                 font=("Helvetica", 10), bg="#ecf0f1", fg="#7f8c8d").pack(anchor="w")

        # Actions
        action_frame = tk.Frame(self, bg="#ecf0f1")
        action_frame.pack(fill="x", padx=20, pady=10)

        ttk.Button(action_frame, text="Setup MFA",
                   command=self._setup_mfa).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Disable MFA",
                   command=self._disable_mfa).pack(side="left", padx=5)
        ttk.Button(action_frame, text="Refresh",
                   command=self._refresh_status).pack(side="left", padx=5)

        # Setup result area
        self._result_frame = tk.LabelFrame(self, text="Setup Details", bg="#ecf0f1",
                                            padx=15, pady=10)
        self._result_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        self._result_text = tk.Text(self._result_frame, height=10, width=60,
                                     state="disabled", font=("Courier", 10))
        self._result_text.pack(fill="both", expand=True)

    def refresh(self):
        self._refresh_status()

    def _get_user_id(self):
        """Get the current user's auth-db ID from auth context.

        `mfa_secrets` is keyed on auth.db `users.id`.  The university
        launcher rewrites `current_user["user_id"]` to a system-local
        legacy id and stashes the real auth-db id under `shared_auth_id`
        — prefer that key when present.
        """
        def _from(d):
            return d.get("shared_auth_id") or d.get("user_id") or d.get("id")
        if isinstance(self._auth, dict):
            return _from(self._auth)
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return _from(self._auth.current_user)
        return None

    def _get_username(self):
        """Get the current user's username from auth context."""
        if isinstance(self._auth, dict):
            return self._auth.get("username", "user")
        if hasattr(self._auth, "current_user") and self._auth.current_user:
            return self._auth.current_user.get("username", "user")
        return "user"

    def _refresh_status(self):
        user_id = self._get_user_id()
        if not user_id:
            self._status_var.set("No user session")
            return
        try:
            enabled = self._svc.is_mfa_enabled(user_id)
            self._status_var.set("MFA Enabled" if enabled else "MFA Disabled")
            if enabled:
                remaining = self._svc.get_remaining_recovery_codes(user_id)
                self._recovery_var.set(f"{remaining} recovery code(s) remaining")
            else:
                self._recovery_var.set("")
        except Exception:
            self._status_var.set("Status unknown")

    def _setup_mfa(self):
        user_id = self._get_user_id()
        username = self._get_username()
        if not user_id:
            messagebox.showerror("Error", "No user session available.")
            return
        try:
            result = self._svc.setup_totp(user_id, username)

            self._result_text.config(state="normal")
            self._result_text.delete("1.0", "end")
            self._result_text.insert("end", f"TOTP Secret: {result['secret']}\n\n")
            self._result_text.insert("end", f"Provisioning URI (for QR code):\n{result['provisioning_uri']}\n\n")
            self._result_text.insert("end", "Recovery Codes (save these!):\n")
            for code in result["recovery_codes"]:
                self._result_text.insert("end", f"  {code}\n")
            self._result_text.config(state="disabled")

            messagebox.showinfo("Success",
                                "MFA has been enabled.\n\n"
                                "Add the secret to your authenticator app\n"
                                "and save the recovery codes securely.")
            self._refresh_status()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _disable_mfa(self):
        if not messagebox.askyesno("Confirm", "Are you sure you want to disable MFA?\n\n"
                                   "This will remove all TOTP secrets and recovery codes."):
            return
        user_id = self._get_user_id()
        if not user_id:
            messagebox.showerror("Error", "No user session available.")
            return
        try:
            self._svc.disable_mfa(user_id)
            messagebox.showinfo("Success", "MFA has been disabled.")
            self._refresh_status()

            self._result_text.config(state="normal")
            self._result_text.delete("1.0", "end")
            self._result_text.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))
