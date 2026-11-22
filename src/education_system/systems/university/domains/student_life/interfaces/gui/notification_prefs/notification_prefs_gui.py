"""Notification Preferences GUI (Feature 33).

Allows students to configure notification preferences including
quiet hours, daily digest settings, and notification bundling.
Saved on the user's ``user_preferences`` row (keyed on users.id as text, as the
announcement screens read it): the settings go in ``preferences_json`` under
``notifications`` and the digest switch also sets ``digest_frequency``.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import json
import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

# Hour choices for quiet hours / digest time
HOUR_CHOICES = [f"{h:02d}:00" for h in range(24)]

# Bundle time window choices (in minutes)
BUNDLE_WINDOW_CHOICES = ["5", "10", "15", "30", "60"]

# Key inside user_preferences.preferences_json
_PREFS_KEY = "notifications"


class NotificationPrefsGUI:
    """Toplevel window for managing notification preferences."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.user_id = ''
        if auth and auth.current_user:
            self.user_id = auth.current_user.get('username', '')

        self.window = tk.Toplevel(parent)
        self.window.title(_t('gui.pastoral.notification_prefs.notification_prefs.windows.notification_preferences', default="Notification Preferences"))
        self.window.geometry("600x450")
        self.window.transient(parent)

        self._setup_ui()
        self._load_preferences()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the preferences form."""
        ttk.Label(
            self.window,
            text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.notification_preferences', default="Notification Preferences"),
            font=("Arial", 16, "bold"),
        ).pack(pady=(15, 5))

        ttk.Label(
            self.window,
            text=f"User: {self.user_id}",
            font=("Arial", 10),
        ).pack(pady=(0, 10))

        form_frame = ttk.Frame(self.window)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        row = 0

        # ---- Quiet Hours ----
        ttk.Label(
            form_frame,
            text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.quiet_hours', default="Quiet Hours"),
            font=("Arial", 12, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        row += 1

        ttk.Label(form_frame, text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.start', default="Start:")).grid(
            row=row, column=0, sticky=tk.W, padx=(0, 10), pady=4
        )
        self.quiet_start_var = tk.StringVar(value="22:00")
        ttk.Combobox(
            form_frame,
            textvariable=self.quiet_start_var,
            values=HOUR_CHOICES,
            state="readonly",
            width=10,
        ).grid(row=row, column=1, sticky=tk.W, pady=4)
        row += 1

        ttk.Label(form_frame, text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.end', default="End:")).grid(
            row=row, column=0, sticky=tk.W, padx=(0, 10), pady=4
        )
        self.quiet_end_var = tk.StringVar(value="08:00")
        ttk.Combobox(
            form_frame,
            textvariable=self.quiet_end_var,
            values=HOUR_CHOICES,
            state="readonly",
            width=10,
        ).grid(row=row, column=1, sticky=tk.W, pady=4)
        row += 1

        ttk.Separator(form_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=10
        )
        row += 1

        # ---- Daily Digest ----
        ttk.Label(
            form_frame,
            text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.daily_digest', default="Daily Digest"),
            font=("Arial", 12, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        row += 1

        self.digest_enabled_var = tk.IntVar(value=0)
        ttk.Checkbutton(
            form_frame,
            text=_t('gui.pastoral.notification_prefs.notification_prefs.buttons.enable_daily_digest', default="Enable daily digest"),
            variable=self.digest_enabled_var,
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        ttk.Label(form_frame, text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.digest_time', default="Digest Time:")).grid(
            row=row, column=0, sticky=tk.W, padx=(0, 10), pady=4
        )
        self.digest_time_var = tk.StringVar(value="08:00")
        ttk.Combobox(
            form_frame,
            textvariable=self.digest_time_var,
            values=HOUR_CHOICES,
            state="readonly",
            width=10,
        ).grid(row=row, column=1, sticky=tk.W, pady=4)
        row += 1

        ttk.Separator(form_frame, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=10
        )
        row += 1

        # ---- Notification Bundling ----
        ttk.Label(
            form_frame,
            text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.notification_bundling', default="Notification Bundling"),
            font=("Arial", 12, "bold"),
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        row += 1

        self.bundle_var = tk.IntVar(value=0)
        ttk.Checkbutton(
            form_frame,
            text=_t('gui.pastoral.notification_prefs.notification_prefs.buttons.enable_notification_bundling', default="Enable notification bundling"),
            variable=self.bundle_var,
        ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=4)
        row += 1

        ttk.Label(form_frame, text=_t('gui.pastoral.notification_prefs.notification_prefs.labels.bundle_window_min', default="Bundle Window (min):")).grid(
            row=row, column=0, sticky=tk.W, padx=(0, 10), pady=4
        )
        self.bundle_window_var = tk.StringVar(value="15")
        ttk.Combobox(
            form_frame,
            textvariable=self.bundle_window_var,
            values=BUNDLE_WINDOW_CHOICES,
            state="readonly",
            width=10,
        ).grid(row=row, column=1, sticky=tk.W, pady=4)
        row += 1

        # Status label
        self.status_var = tk.StringVar(value="")
        ttk.Label(
            self.window, textvariable=self.status_var, foreground="gray"
        ).pack(pady=(5, 0))

        # Buttons
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(pady=15)

        ttk.Button(btn_frame, text=_t('gui.pastoral.notification_prefs.notification_prefs.buttons.save', default="Save"), command=self._save_preferences).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text=_t('gui.pastoral.notification_prefs.notification_prefs.buttons.refresh', default="Refresh"), command=self._load_preferences).pack(
            side=tk.LEFT, padx=10
        )
        ttk.Button(btn_frame, text=_t('gui.pastoral.notification_prefs.notification_prefs.buttons.close', default="Close"), command=self.window.destroy).pack(
            side=tk.LEFT, padx=10
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _preference_key(self, conn):
        """The user_preferences key for the signed-in username."""
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?", (self.user_id,)
        ).fetchone()
        return str(row[0]) if row else self.user_id

    @staticmethod
    def _stored_settings(raw):
        """The row's preferences_json as a dict (empty if absent or unreadable)."""
        try:
            settings = json.loads(raw) if raw else {}
        except ValueError:
            return {}
        return settings if isinstance(settings, dict) else {}

    def _load_preferences(self):
        """Load stored preferences from the database."""
        if not self.user_id:
            self.status_var.set("No user ID available.")
            return

        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT preferences_json FROM user_preferences WHERE user_id = ?",
                    (self._preference_key(conn),),
                ).fetchone()
            prefs = self._stored_settings(row[0] if row else None).get(_PREFS_KEY)

            if prefs:
                self.quiet_start_var.set(prefs.get("quiet_hours_start") or "22:00")
                self.quiet_end_var.set(prefs.get("quiet_hours_end") or "08:00")
                self.digest_enabled_var.set(1 if prefs.get("daily_digest_enabled") else 0)
                self.digest_time_var.set(prefs.get("daily_digest_time") or "08:00")
                self.bundle_var.set(1 if prefs.get("bundle_notifications") else 0)
                self.bundle_window_var.set(str(prefs.get("bundle_time_window") or 15))
            else:
                # Defaults when no record exists yet
                self.quiet_start_var.set("22:00")
                self.quiet_end_var.set("08:00")
                self.digest_enabled_var.set(0)
                self.digest_time_var.set("08:00")
                self.bundle_var.set(0)
                self.bundle_window_var.set("15")

        except Exception as exc:
            logger.error("Failed to load notification preferences: %s", exc)
            self.status_var.set("Error loading preferences.")
            return

        self.status_var.set("Preferences loaded.")
        logger.info("Loaded notification preferences for %s", self.user_id)

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def _save_preferences(self):
        """Upsert preferences into the database."""
        if not self.user_id:
            messagebox.showwarning(_t('gui.pastoral.notification_prefs.notification_prefs.dialogs.warning', default="Warning"), _t('gui.pastoral.notification_prefs.notification_prefs.dialogs.no_user_id_available', default="No user ID available."), parent=self.window)
            return

        quiet_start = self.quiet_start_var.get()
        quiet_end = self.quiet_end_var.get()
        digest_enabled = self.digest_enabled_var.get()
        digest_time = self.digest_time_var.get()
        bundle = self.bundle_var.get()
        try:
            bundle_window = int(self.bundle_window_var.get())
        except (ValueError, tk.TclError):
            bundle_window = 15

        try:
            with transaction() as conn:
                key = self._preference_key(conn)
                row = conn.execute(
                    "SELECT preferences_json, digest_frequency FROM user_preferences "
                    "WHERE user_id = ?", (key,),
                ).fetchone()
                settings = self._stored_settings(row[0] if row else None)
                settings[_PREFS_KEY] = {
                    "quiet_hours_start": quiet_start,
                    "quiet_hours_end": quiet_end,
                    "daily_digest_enabled": digest_enabled,
                    "daily_digest_time": digest_time,
                    "bundle_notifications": bundle,
                    "bundle_time_window": bundle_window,
                }
                # Keep a weekly digest chosen elsewhere; this switch only turns it on/off.
                current = row[1] if row else None
                frequency = "immediate"
                if digest_enabled:
                    frequency = current if current in ("daily", "weekly") else "daily"
                conn.execute(
                    "INSERT INTO user_preferences (user_id, digest_frequency, preferences_json) "
                    "VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                    "digest_frequency = excluded.digest_frequency, "
                    "preferences_json = excluded.preferences_json",
                    (key, frequency, json.dumps(settings)),
                )

            log_activity(
                self.user_id, self.user_id, 'student',
                'update', 'notification_preferences',
                details=f"Notification preferences updated for {self.user_id}",
            )

            logger.info("Notification preferences saved for %s", self.user_id)
            self.status_var.set("Preferences saved.")
            messagebox.showinfo(
                _t('gui.pastoral.notification_prefs.notification_prefs.dialogs.success', default="Success"), _t('gui.pastoral.notification_prefs.notification_prefs.dialogs.notification_preferences_saved', default="Notification preferences saved."), parent=self.window
            )
        except Exception as exc:
            logger.error("Failed to save notification preferences: %s", exc)
            messagebox.showerror(
                _t('gui.pastoral.notification_prefs.notification_prefs.dialogs.error', default="Error"),
                f"Could not save preferences: {exc}",
                parent=self.window,
            )
