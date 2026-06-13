"""
Smart Notifications Hub GUI Interface

Provides a Tkinter-based graphical interface for managing notifications,
preferences, and notification center functionality.

Features:
- Notification list with filtering by channel, priority, and read status
- Detail panel for viewing full notification content
- Mark as read / mark all read / archive actions
- Settings dialog for channel preferences and quiet hours
- Notification statistics summary
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationsGUI:
    """GUI interface for Smart Notifications Hub."""

    CHANNELS = ["academic", "social", "financial", "health", "housing", "events", "system"]
    PRIORITIES = ["low", "medium", "high", "urgent"]
    PRIORITY_COLORS = {
        "urgent": "#dc3545",
        "high": "#fd7e14",
        "medium": "#ffc107",
        "low": "#0d6efd",
    }

    def __init__(self, parent=None):
        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        self.window.title("Smart Notifications Hub")
        self.window.geometry("1060x700")
        self.window.minsize(860, 550)

        try:
            from education_system.university_system.infrastructure.shared_context import get_auth
            self.auth = get_auth()
        except Exception:
            self.auth = None

        self.service = None
        self._init_service()
        self._build_ui()
        self._load_notifications()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _init_service(self):
        """Initialise the NotificationsService."""
        try:
            from education_system.university_system.modules.domain.operations.communications.notifications.services.notifications_service import (
                NotificationsService,
            )
            self.service = NotificationsService()
        except Exception as exc:
            logger.error("Failed to initialise NotificationsService: %s", exc)

    def _get_user_id(self) -> str:
        """Return the current user id, or 'unknown'."""
        if self.auth and hasattr(self.auth, "is_logged_in") and self.auth.is_logged_in():
            user = self.auth.get_current_user()
            if isinstance(user, dict):
                return user.get("user_id") or user.get("username") or "unknown"
        if self.auth and hasattr(self.auth, "current_user") and self.auth.current_user:
            user = self.auth.current_user
            if isinstance(user, dict):
                return user.get("user_id") or user.get("username") or "unknown"
            return getattr(user, "user_id", None) or getattr(user, "username", "unknown")
        return "unknown"

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Build the main user interface."""
        # --- Top toolbar ---
        toolbar = ttk.Frame(self.window)
        toolbar.pack(fill=tk.X, padx=8, pady=(8, 2))

        ttk.Button(toolbar, text="Refresh", command=self._load_notifications).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Mark as Read", command=self._mark_selected_read).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Mark All Read", command=self._mark_all_read).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Archive", command=self._archive_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Settings", command=self._open_settings_dialog).pack(side=tk.LEFT, padx=2)

        # Unread count label on the right
        self.unread_label = ttk.Label(toolbar, text="", font=("", 10, "bold"))
        self.unread_label.pack(side=tk.RIGHT, padx=6)

        # --- Filter bar ---
        filter_frame = ttk.LabelFrame(self.window, text="Filters", padding=4)
        filter_frame.pack(fill=tk.X, padx=8, pady=4)

        ttk.Label(filter_frame, text="Channel:").pack(side=tk.LEFT, padx=(4, 2))
        self.channel_var = tk.StringVar(value="All")
        channel_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.channel_var,
            values=["All"] + [c.title() for c in self.CHANNELS],
            state="readonly",
            width=12,
        )
        channel_combo.pack(side=tk.LEFT, padx=2)
        channel_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_notifications())

        ttk.Label(filter_frame, text="Priority:").pack(side=tk.LEFT, padx=(10, 2))
        self.priority_var = tk.StringVar(value="All")
        priority_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.priority_var,
            values=["All"] + [p.title() for p in self.PRIORITIES],
            state="readonly",
            width=10,
        )
        priority_combo.pack(side=tk.LEFT, padx=2)
        priority_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_notifications())

        self.unread_only_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filter_frame, text="Unread only", variable=self.unread_only_var,
            command=self._load_notifications,
        ).pack(side=tk.LEFT, padx=10)

        # --- Main paned window: list (top) + detail (bottom) ---
        paned = ttk.PanedWindow(self.window, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # Notification list
        list_frame = ttk.Frame(paned)
        paned.add(list_frame, weight=3)

        columns = ("id", "date", "subject", "priority", "channel", "read")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")

        col_config = [
            ("id", "ID", 50),
            ("date", "Date", 140),
            ("subject", "Subject", 350),
            ("priority", "Priority", 80),
            ("channel", "Channel", 90),
            ("read", "Read", 60),
        ]
        for col_id, heading, width in col_config:
            self.tree.heading(col_id, text=heading, command=lambda c=col_id: self._sort_column(c))
            anchor = tk.CENTER if col_id in ("id", "priority", "channel", "read") else tk.W
            self.tree.column(col_id, width=width, minwidth=40, anchor=anchor)

        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_notification_select)

        # Detail panel
        detail_frame = ttk.LabelFrame(paned, text="Notification Details", padding=8)
        paned.add(detail_frame, weight=2)

        self.detail_text = tk.Text(detail_frame, wrap=tk.WORD, state=tk.DISABLED, height=10)
        detail_scroll = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.detail_text.yview)
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        self.detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure text tags for styling
        self.detail_text.tag_configure("heading", font=("", 12, "bold"))
        self.detail_text.tag_configure("label", font=("", 10, "bold"))
        self.detail_text.tag_configure("body", font=("", 10))

        # --- Status bar ---
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.window, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(
            fill=tk.X, side=tk.BOTTOM, padx=8, pady=(0, 4),
        )

        # Internal data cache: maps tree item iid -> notification dict
        self._notif_cache: dict = {}
        self._sort_reverse: dict = {}

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_notifications(self):
        """Fetch notifications from the service and populate the treeview."""
        if not self.service:
            self.status_var.set("Service unavailable")
            return

        user_id = self._get_user_id()

        # Determine filter values
        channel_val = self.channel_var.get()
        channel = channel_val.lower() if channel_val != "All" else None

        priority_val = self.priority_var.get()
        priority = priority_val.lower() if priority_val != "All" else None

        unread_only = self.unread_only_var.get()

        try:
            notifications = self.service.get_notifications(
                user_id,
                unread_only=unread_only,
                channel=channel,
                priority=priority,
                limit=200,
            )
        except Exception as exc:
            logger.error("Failed to load notifications: %s", exc)
            self.status_var.set(f"Error loading notifications: {exc}")
            return

        # Clear existing items
        self.tree.delete(*self.tree.get_children())
        self._notif_cache.clear()

        for notif in notifications:
            created = notif.get("created_at", "")
            # Shorten timestamp for display if possible
            try:
                dt = datetime.strptime(created, "%Y-%m-%d %H:%M:%S")
                display_date = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                display_date = str(created)

            read_status = "Yes" if notif.get("is_read") else "No"
            values = (
                notif["notification_id"],
                display_date,
                notif["title"],
                notif["priority"].title(),
                notif["channel"].title(),
                read_status,
            )
            iid = self.tree.insert("", tk.END, values=values)
            self._notif_cache[iid] = notif

        # Update unread count
        try:
            unread = self.service.get_unread_count(user_id)
            self.unread_label.configure(text=f"Unread: {unread}")
        except Exception:
            self.unread_label.configure(text="")

        self.status_var.set(f"Loaded {len(notifications)} notification(s)")

        # Clear detail panel
        self._clear_detail()

    # ------------------------------------------------------------------
    # Treeview interaction
    # ------------------------------------------------------------------

    def _on_notification_select(self, _event):
        """Display the selected notification in the detail panel."""
        selection = self.tree.selection()
        if not selection:
            return

        iid = selection[0]
        notif = self._notif_cache.get(iid)
        if not notif:
            return

        self._show_detail(notif)

    def _show_detail(self, notif: dict):
        """Render notification details in the detail text widget."""
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        self.detail_text.insert(tk.END, notif.get("title", ""), "heading")
        self.detail_text.insert(tk.END, "\n\n")

        fields = [
            ("ID", str(notif.get("notification_id", ""))),
            ("Channel", notif.get("channel", "").upper()),
            ("Priority", notif.get("priority", "").upper()),
            ("Status", "READ" if notif.get("is_read") else "UNREAD"),
            ("Created", notif.get("created_at", "")),
            ("Read At", notif.get("read_at") or "N/A"),
            ("Source", notif.get("source_system") or "N/A"),
            ("Expires", notif.get("expires_at") or "N/A"),
        ]

        for label, value in fields:
            self.detail_text.insert(tk.END, f"{label}: ", "label")
            self.detail_text.insert(tk.END, f"{value}\n", "body")

        self.detail_text.insert(tk.END, "\n")
        self.detail_text.insert(tk.END, "Message:\n", "label")
        self.detail_text.insert(tk.END, notif.get("message", ""), "body")

        self.detail_text.configure(state=tk.DISABLED)

    def _clear_detail(self):
        """Clear the detail panel."""
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.configure(state=tk.DISABLED)

    def _sort_column(self, col):
        """Sort treeview by a column."""
        reverse = self._sort_reverse.get(col, False)
        items = [(self.tree.set(iid, col), iid) for iid in self.tree.get_children("")]

        # Try numeric sort for ID column
        if col == "id":
            try:
                items.sort(key=lambda t: int(t[0]), reverse=reverse)
            except ValueError:
                items.sort(key=lambda t: t[0], reverse=reverse)
        else:
            items.sort(key=lambda t: t[0], reverse=reverse)

        for index, (_val, iid) in enumerate(items):
            self.tree.move(iid, "", index)

        self._sort_reverse[col] = not reverse

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _get_selected_notification(self):
        """Return the notification dict for the currently selected row, or None."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select a notification first.", parent=self.window)
            return None
        return self._notif_cache.get(selection[0])

    def _mark_selected_read(self):
        """Mark the selected notification as read."""
        notif = self._get_selected_notification()
        if not notif:
            return

        if not self.service:
            return

        user_id = self._get_user_id()
        try:
            success = self.service.mark_as_read(notif["notification_id"], user_id)
            if success:
                self.status_var.set(f"Notification {notif['notification_id']} marked as read")
            else:
                self.status_var.set("Notification not found or already read")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to mark as read: {exc}", parent=self.window)
            return

        self._load_notifications()

    def _mark_all_read(self):
        """Mark all (optionally filtered) notifications as read."""
        if not self.service:
            return

        user_id = self._get_user_id()
        channel_val = self.channel_var.get()
        channel = channel_val.lower() if channel_val != "All" else None

        try:
            count = self.service.mark_all_as_read(user_id, channel)
            suffix = f" in {channel_val}" if channel else ""
            self.status_var.set(f"Marked {count} notification(s) as read{suffix}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to mark all as read: {exc}", parent=self.window)
            return

        self._load_notifications()

    def _archive_selected(self):
        """Archive the selected notification."""
        notif = self._get_selected_notification()
        if not notif:
            return

        if not self.service:
            return

        user_id = self._get_user_id()
        try:
            success = self.service.archive_notification(notif["notification_id"], user_id)
            if success:
                self.status_var.set(f"Notification {notif['notification_id']} archived")
            else:
                self.status_var.set("Notification not found")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to archive: {exc}", parent=self.window)
            return

        self._load_notifications()

    # ------------------------------------------------------------------
    # Settings dialog
    # ------------------------------------------------------------------

    def _open_settings_dialog(self):
        """Open a toplevel settings window with tabs for preferences and channels."""
        if not self.service:
            messagebox.showwarning("Warning", "Service unavailable.", parent=self.window)
            return

        user_id = self._get_user_id()

        dlg = tk.Toplevel(self.window)
        dlg.title("Notification Settings")
        dlg.geometry("580x480")
        dlg.transient(self.window)
        dlg.grab_set()

        notebook = ttk.Notebook(dlg)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ---- Quiet Hours & Digest tab ----
        prefs_tab = ttk.Frame(notebook, padding=12)
        notebook.add(prefs_tab, text="General")

        prefs = self.service.get_preferences(user_id)

        row = 0
        ttk.Label(prefs_tab, text="Quiet Hours", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6),
        )
        row += 1
        ttk.Label(prefs_tab, text="During quiet hours only urgent notifications are delivered.").grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 8),
        )

        row += 1
        ttk.Label(prefs_tab, text="Start (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=3)
        quiet_start_var = tk.StringVar(value=prefs.get("quiet_hours_start") or "22:00")
        ttk.Entry(prefs_tab, textvariable=quiet_start_var, width=8).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Label(prefs_tab, text="End (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=3)
        quiet_end_var = tk.StringVar(value=prefs.get("quiet_hours_end") or "08:00")
        ttk.Entry(prefs_tab, textvariable=quiet_end_var, width=8).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Separator(prefs_tab, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10,
        )

        row += 1
        ttk.Label(prefs_tab, text="Daily Digest", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6),
        )

        row += 1
        digest_enabled_var = tk.BooleanVar(value=bool(prefs.get("daily_digest_enabled")))
        ttk.Checkbutton(prefs_tab, text="Enable daily digest", variable=digest_enabled_var).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=3,
        )

        row += 1
        ttk.Label(prefs_tab, text="Digest time (HH:MM):").grid(row=row, column=0, sticky=tk.W, pady=3)
        digest_time_var = tk.StringVar(value=prefs.get("daily_digest_time") or "08:00")
        ttk.Entry(prefs_tab, textvariable=digest_time_var, width=8).grid(row=row, column=1, sticky=tk.W, pady=3)

        row += 1
        ttk.Separator(prefs_tab, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=tk.EW, pady=10,
        )

        row += 1
        ttk.Label(prefs_tab, text="Bundling", font=("", 11, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6),
        )

        row += 1
        bundle_var = tk.BooleanVar(value=bool(prefs.get("bundle_notifications")))
        ttk.Checkbutton(prefs_tab, text="Bundle related notifications", variable=bundle_var).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=3,
        )

        row += 1
        ttk.Label(prefs_tab, text="Bundle window (sec):").grid(row=row, column=0, sticky=tk.W, pady=3)
        bundle_window_var = tk.StringVar(value=str(prefs.get("bundle_time_window", 300)))
        ttk.Entry(prefs_tab, textvariable=bundle_window_var, width=8).grid(row=row, column=1, sticky=tk.W, pady=3)

        # ---- Channel Preferences tab ----
        chan_tab = ttk.Frame(notebook, padding=12)
        notebook.add(chan_tab, text="Channel Preferences")

        channel_settings = self.service.get_channel_settings(user_id)
        # Build a dict keyed by channel name for easy lookup
        chan_map = {s["channel"]: s for s in channel_settings}

        # Column headers
        headers = ["Channel", "Enabled", "Min Priority", "Push", "Email", "SMS"]
        for ci, h in enumerate(headers):
            ttk.Label(chan_tab, text=h, font=("", 9, "bold")).grid(row=0, column=ci, padx=4, pady=(0, 6))

        chan_widgets: dict = {}  # channel -> {enabled, min_priority, push, email, sms}

        for ri, channel_name in enumerate(self.CHANNELS, start=1):
            setting = chan_map.get(channel_name, {})

            ttk.Label(chan_tab, text=channel_name.title()).grid(row=ri, column=0, sticky=tk.W, padx=4, pady=2)

            enabled_var = tk.BooleanVar(value=bool(setting.get("enabled", 1)))
            ttk.Checkbutton(chan_tab, variable=enabled_var).grid(row=ri, column=1, padx=4, pady=2)

            prio_var = tk.StringVar(value=(setting.get("min_priority") or "low").title())
            prio_combo = ttk.Combobox(
                chan_tab, textvariable=prio_var,
                values=[p.title() for p in self.PRIORITIES],
                state="readonly", width=8,
            )
            prio_combo.grid(row=ri, column=2, padx=4, pady=2)

            push_var = tk.BooleanVar(value=bool(setting.get("push_enabled", 1)))
            ttk.Checkbutton(chan_tab, variable=push_var).grid(row=ri, column=3, padx=4, pady=2)

            email_var = tk.BooleanVar(value=bool(setting.get("email_enabled", 1)))
            ttk.Checkbutton(chan_tab, variable=email_var).grid(row=ri, column=4, padx=4, pady=2)

            sms_var = tk.BooleanVar(value=bool(setting.get("sms_enabled", 0)))
            ttk.Checkbutton(chan_tab, variable=sms_var).grid(row=ri, column=5, padx=4, pady=2)

            chan_widgets[channel_name] = {
                "enabled": enabled_var,
                "min_priority": prio_var,
                "push": push_var,
                "email": email_var,
                "sms": sms_var,
            }

        # ---- Save / Cancel buttons ----
        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=8, pady=8)

        def _save_settings():
            # Validate time formats
            for label_text, var in [("Quiet start", quiet_start_var), ("Quiet end", quiet_end_var),
                                    ("Digest time", digest_time_var)]:
                val = var.get().strip()
                if val:
                    try:
                        datetime.strptime(val, "%H:%M")
                    except ValueError:
                        messagebox.showerror(
                            "Invalid Time",
                            f"{label_text} must be in HH:MM format (e.g. 22:00).",
                            parent=dlg,
                        )
                        return

            # Validate bundle window
            try:
                bw = int(bundle_window_var.get())
                if bw < 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Invalid Value", "Bundle window must be a non-negative integer.", parent=dlg,
                )
                return

            # Save general preferences
            try:
                self.service.update_preferences(
                    user_id,
                    quiet_hours_start=quiet_start_var.get().strip(),
                    quiet_hours_end=quiet_end_var.get().strip(),
                    daily_digest_enabled=digest_enabled_var.get(),
                    daily_digest_time=digest_time_var.get().strip() if digest_enabled_var.get() else None,
                    bundle_notifications=bundle_var.get(),
                    bundle_time_window=bw,
                )
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to save preferences: {exc}", parent=dlg)
                return

            # Save channel settings
            for ch_name, widgets in chan_widgets.items():
                try:
                    self.service.update_channel_settings(
                        user_id,
                        ch_name,
                        enabled=widgets["enabled"].get(),
                        min_priority=widgets["min_priority"].get().lower(),
                        push_enabled=widgets["push"].get(),
                        email_enabled=widgets["email"].get(),
                        sms_enabled=widgets["sms"].get(),
                    )
                except Exception as exc:
                    logger.error("Failed to save channel %s: %s", ch_name, exc)

            self.status_var.set("Settings saved")
            dlg.destroy()

        ttk.Button(btn_frame, text="Save", command=_save_settings).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side=tk.RIGHT, padx=4)


def launch_notifications_gui(parent=None):
    """Convenience launcher matching the pattern used by other domain GUIs."""
    return NotificationsGUI(parent=parent)
