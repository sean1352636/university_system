"""MFA GUI components: verification dialog and settings frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.infrastructure.auth.mfa_service import MFAService
from education_system.college_system.infrastructure.auth.core import UserAuth


class MFAVerifyDialog(tk.Toplevel):
    """Dialog shown during login when MFA is required."""

    def __init__(self, parent, auth: UserAuth, user_id: int, on_success=None):
        super().__init__(parent)
        self._auth = auth
        self._user_id = user_id
        self._on_success = on_success
        self._result = None

        self.title("MFA Verification")
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
        tk.Label(frame, text="Enter your TOTP code or a recovery code.",
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
    """MFA settings management frame."""

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

        # Status
        status_frame = tk.LabelFrame(self, text="Status", bg="#ecf0f1", padx=15, pady=10)
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

    def _refresh_status(self):
        try:
            user_id = self._auth.current_user["user_id"]
            enabled = self._svc.is_mfa_enabled(user_id)
            self._status_var.set("MFA: Enabled" if enabled else "MFA: Disabled")
            if enabled:
                remaining = self._svc.get_remaining_recovery_codes(user_id)
                self._recovery_var.set(f"Recovery codes remaining: {remaining}")
            else:
                self._recovery_var.set("")
        except Exception:
            self._status_var.set("MFA: Unknown")

    def _setup_mfa(self):
        try:
            user_id = self._auth.current_user["user_id"]
            username = self._auth.current_user["username"]
            result = self._svc.setup_totp(user_id, username)

            self._result_text.config(state="normal")
            self._result_text.delete("1.0", "end")
            self._result_text.insert("end", f"TOTP Secret: {result['secret']}\n\n")
            self._result_text.insert("end", f"Provisioning URI:\n{result['provisioning_uri']}\n\n")
            self._result_text.insert("end", "Recovery Codes (save securely!):\n")
            for code in result["recovery_codes"]:
                self._result_text.insert("end", f"  {code}\n")
            self._result_text.config(state="disabled")

            messagebox.showinfo("Success", "MFA has been enabled. Save your recovery codes!")
            self._refresh_status()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _disable_mfa(self):
        if not messagebox.askyesno("Confirm", "Disable MFA for your account?"):
            return
        try:
            user_id = self._auth.current_user["user_id"]
            self._svc.disable_mfa(user_id)
            messagebox.showinfo("Success", "MFA has been disabled.")
            self._refresh_status()

            self._result_text.config(state="normal")
            self._result_text.delete("1.0", "end")
            self._result_text.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", str(e))
