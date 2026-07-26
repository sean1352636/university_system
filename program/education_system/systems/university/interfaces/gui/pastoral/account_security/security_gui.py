"""Account Security Dashboard GUI (Feature 32).

Provides students with visibility into login history, MFA settings,
and active session information.
"""

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)


class AccountSecurityGUI:
    """Toplevel window for reviewing account security information."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.username = ''
        if auth and auth.current_user:
            self.username = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title("Account Security Dashboard")
        self.window.geometry("900x650")
        self.window.transient(parent)

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the three-tab notebook interface."""
        ttk.Label(
            self.window,
            text="Account Security Dashboard",
            font=("Arial", 16, "bold"),
        ).pack(pady=(15, 5))

        ttk.Label(
            self.window,
            text=f"Account: {self.username}",
            font=("Arial", 10),
        ).pack(pady=(0, 10))

        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self._create_login_history_tab()
        self._create_mfa_tab()
        self._create_sessions_tab()

        # Bottom close button
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Close", command=self.window.destroy).pack()

    # ------------------------------------------------------------------
    # Tab 1 — Login History
    # ------------------------------------------------------------------

    def _create_login_history_tab(self):
        """Create the login history tab with a colour-coded Treeview."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Login History")

        ttk.Label(
            tab, text="Recent Login Attempts (last 50)",
            font=("Arial", 11, "bold"),
        ).pack(pady=(10, 5))

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        cols = ("time", "success", "ip_address")
        self.history_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=18
        )
        self.history_tree.heading("time", text="Time")
        self.history_tree.heading("success", text="Result")
        self.history_tree.heading("ip_address", text="IP Address")
        self.history_tree.column("time", width=250)
        self.history_tree.column("success", width=120)
        self.history_tree.column("ip_address", width=200)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview
        )
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Row tags for colour coding
        self.history_tree.tag_configure("success", background="#d4edda")
        self.history_tree.tag_configure("failed", background="#f8d7da")

        ttk.Button(
            tab, text="Refresh", command=self._load_login_history
        ).pack(pady=5)

        self._load_login_history()

    def _load_login_history(self):
        """Query the login_attempts table and populate the Treeview."""
        self.history_tree.delete(*self.history_tree.get_children())

        if not self.username:
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT attempt_time, success, ip_address
                    FROM login_attempts
                    WHERE username = ?
                    ORDER BY attempt_time DESC
                    LIMIT 50
                    """,
                    (self.username,),
                ).fetchall()

            for row in rows:
                attempt_time = row["attempt_time"] if row["attempt_time"] else "N/A"
                success_val = row["success"]
                ip_addr = row["ip_address"] if row["ip_address"] else "N/A"

                result_text = "Success" if success_val else "Failed"
                tag = "success" if success_val else "failed"

                self.history_tree.insert(
                    "", tk.END,
                    values=(attempt_time, result_text, ip_addr),
                    tags=(tag,),
                )

            logger.info("Loaded %d login history entries for %s", len(rows), self.username)
        except Exception as exc:
            logger.error("Failed to load login history: %s", exc)

    # ------------------------------------------------------------------
    # Tab 2 — MFA Settings
    # ------------------------------------------------------------------

    def _create_mfa_tab(self):
        """Create the MFA settings tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="MFA Settings")

        ttk.Label(
            tab, text="Multi-Factor Authentication",
            font=("Arial", 14, "bold"),
        ).pack(pady=(20, 10))

        # Status display
        status_frame = ttk.LabelFrame(tab, text="Current Status", padding=15)
        status_frame.pack(padx=30, pady=10, fill=tk.X)

        self.mfa_status_var = tk.StringVar(value="Loading...")
        self.mfa_status_label = ttk.Label(
            status_frame, textvariable=self.mfa_status_var,
            font=("Arial", 13, "bold"),
        )
        self.mfa_status_label.pack(pady=5)

        # Toggle button
        self.mfa_toggle_btn = ttk.Button(
            tab, text="Toggle MFA", command=self._toggle_mfa
        )
        self.mfa_toggle_btn.pack(pady=15)

        # Info text
        info_frame = ttk.LabelFrame(tab, text="About MFA", padding=10)
        info_frame.pack(padx=30, pady=10, fill=tk.X)

        info_text = (
            "Multi-Factor Authentication (MFA) adds an extra layer of security "
            "to your account. When enabled, you will be required to provide a "
            "second form of verification in addition to your password each time "
            "you log in.\n\n"
            "Supported methods include TOTP authenticator apps, email OTP, "
            "and SMS OTP. Enabling MFA significantly reduces the risk of "
            "unauthorized access to your account."
        )
        ttk.Label(
            info_frame, text=info_text, wraplength=600, justify=tk.LEFT
        ).pack(padx=5, pady=5)

        self._load_mfa_status()

    def _load_mfa_status(self):
        """Read the current MFA status from user_accounts."""
        self.mfa_enabled = False

        if not self.username:
            self.mfa_status_var.set("N/A")
            return

        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT two_fa_enabled FROM user_accounts WHERE username = ?",
                    (self.username,),
                ).fetchone()

            if row:
                self.mfa_enabled = bool(row["two_fa_enabled"])
            else:
                self.mfa_enabled = False

        except Exception as exc:
            logger.error("Failed to load MFA status: %s", exc)

        self._refresh_mfa_display()

    def _refresh_mfa_display(self):
        """Update the MFA status label and button text."""
        if self.mfa_enabled:
            self.mfa_status_var.set("Enabled")
            try:
                self.mfa_status_label.configure(foreground="green")
            except Exception:
                pass
            self.mfa_toggle_btn.configure(text="Disable MFA")
        else:
            self.mfa_status_var.set("Disabled")
            try:
                self.mfa_status_label.configure(foreground="red")
            except Exception:
                pass
            self.mfa_toggle_btn.configure(text="Enable MFA")

    def _toggle_mfa(self):
        """Toggle the MFA setting for the current user."""
        if not self.username:
            messagebox.showwarning("Warning", "No account available.", parent=self.window)
            return

        new_state = 0 if self.mfa_enabled else 1
        action_word = "disable" if self.mfa_enabled else "enable"

        confirm = messagebox.askyesno(
            "Confirm",
            f"Are you sure you want to {action_word} MFA?",
            parent=self.window,
        )
        if not confirm:
            return

        try:
            with transaction() as conn:
                conn.execute(
                    "UPDATE user_accounts SET two_fa_enabled = ? WHERE username = ?",
                    (new_state, self.username),
                )

            self.mfa_enabled = bool(new_state)
            self._refresh_mfa_display()

            log_activity(
                self.username, self.username, 'student',
                'update', 'account_security',
                details=f"MFA {action_word}d for {self.username}",
            )

            logger.info("MFA %sd for user %s", action_word, self.username)
            messagebox.showinfo(
                "Success",
                f"MFA has been {action_word}d.",
                parent=self.window,
            )
        except Exception as exc:
            logger.error("Failed to toggle MFA: %s", exc)
            messagebox.showerror(
                "Error", f"Could not update MFA setting: {exc}", parent=self.window
            )

    # ------------------------------------------------------------------
    # Tab 3 — Active Sessions
    # ------------------------------------------------------------------

    def _create_sessions_tab(self):
        """Create the active sessions tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Active Sessions")

        ttk.Label(
            tab, text="Recent Successful Logins by IP",
            font=("Arial", 11, "bold"),
        ).pack(pady=(10, 5))

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        cols = ("ip_address", "login_count", "last_login")
        self.sessions_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=15
        )
        self.sessions_tree.heading("ip_address", text="IP Address")
        self.sessions_tree.heading("login_count", text="Login Count")
        self.sessions_tree.heading("last_login", text="Last Login")
        self.sessions_tree.column("ip_address", width=220)
        self.sessions_tree.column("login_count", width=120)
        self.sessions_tree.column("last_login", width=250)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.sessions_tree.yview
        )
        self.sessions_tree.configure(yscrollcommand=scrollbar.set)
        self.sessions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(
            tab, text="Refresh", command=self._load_sessions
        ).pack(pady=5)

        self._load_sessions()

    def _load_sessions(self):
        """Load successful login sessions grouped by IP address."""
        self.sessions_tree.delete(*self.sessions_tree.get_children())

        if not self.username:
            return

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT ip_address,
                           COUNT(*) AS login_count,
                           MAX(attempt_time) AS last_login
                    FROM login_attempts
                    WHERE username = ? AND success = 1
                    GROUP BY ip_address
                    ORDER BY last_login DESC
                    LIMIT 20
                    """,
                    (self.username,),
                ).fetchall()

            for row in rows:
                ip_addr = row["ip_address"] if row["ip_address"] else "Unknown"
                count = row["login_count"]
                last_login = row["last_login"] if row["last_login"] else "N/A"

                self.sessions_tree.insert(
                    "", tk.END,
                    values=(ip_addr, count, last_login),
                )

            logger.info("Loaded %d session groups for %s", len(rows), self.username)
        except Exception as exc:
            logger.error("Failed to load sessions: %s", exc)
