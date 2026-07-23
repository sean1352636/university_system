"""Alert & Notification Configuration Console.

Admin UI to configure notification triggers, manage alert rules,
set delivery channels, and manage alert suppression/scheduling.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)


class AlertConfigConsole(tk.Toplevel):
    """Admin console for managing alert and notification rules."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Alert & Notification Configuration")
        self.geometry("1000x700")
        self.transient(parent)

        self._create_widgets()
        self._load_all_data()

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (self.winfo_width() // 2)
        y = (self.winfo_screenheight() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create the console UI."""
        # Header
        header = tk.Frame(self, bg="#2C3E50", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Alert & Notification Configuration",
                 font=("Arial", 14, "bold"), bg="#2C3E50", fg="white").pack(pady=12)

        # Notebook tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_templates_tab()
        self._create_schedules_tab()
        self._create_preferences_tab()
        self._create_queue_tab()

    # ------------------------------------------------------------------
    # Notification Templates Tab
    # ------------------------------------------------------------------
    def _create_templates_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Notification Templates")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Template",
                   command=self._add_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Edit Selected",
                   command=self._edit_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Toggle Active",
                   command=self._toggle_template_active).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_templates).pack(side=tk.LEFT, padx=5)

        cols = ("template_id", "template_name", "template_type", "send_method", "is_active")
        self.templates_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        self.templates_tree.heading("template_id", text="ID")
        self.templates_tree.heading("template_name", text="Name")
        self.templates_tree.heading("template_type", text="Type")
        self.templates_tree.heading("send_method", text="Channel")
        self.templates_tree.heading("is_active", text="Active")
        self.templates_tree.column("template_id", width=50)
        self.templates_tree.column("template_name", width=250)
        self.templates_tree.column("template_type", width=200)
        self.templates_tree.column("send_method", width=100)
        self.templates_tree.column("is_active", width=80)

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.templates_tree.yview)
        self.templates_tree.configure(yscrollcommand=scroll.set)
        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

    def _load_templates(self):
        for item in self.templates_tree.get_children():
            self.templates_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT template_id, template_name, template_type, send_method, "
                    "CASE WHEN is_active THEN 'Yes' ELSE 'No' END "
                    "FROM notification_templates ORDER BY template_name"
                ).fetchall()
                for r in rows:
                    self.templates_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            logger.debug(f"Could not load templates: {e}")

    def _add_template(self):
        self._show_template_editor(None)

    def _edit_template(self):
        sel = self.templates_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a template first.")
            return
        template_id = self.templates_tree.item(sel[0])['values'][0]
        self._show_template_editor(template_id)

    def _show_template_editor(self, template_id):
        dialog = tk.Toplevel(self)
        dialog.title("Edit Template" if template_id else "New Template")
        dialog.geometry("550x500")
        dialog.transient(self)
        dialog.grab_set()

        fields = {}
        row = 0
        for label, key, width in [
            ("Name:", "template_name", 40),
            ("Type:", "template_type", 40),
            ("Subject:", "subject_template", 40),
        ]:
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=5)
            e = ttk.Entry(dialog, width=width)
            e.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
            fields[key] = e
            row += 1

        ttk.Label(dialog, text="Channel:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        channel = ttk.Combobox(dialog, values=["email", "sms", "push"], state="readonly", width=15)
        channel.set("email")
        channel.grid(row=row, column=1, padx=10, pady=5, sticky="w")
        fields['send_method'] = channel
        row += 1

        ttk.Label(dialog, text="Body:").grid(row=row, column=0, sticky="nw", padx=10, pady=5)
        body = scrolledtext.ScrolledText(dialog, height=10, width=50)
        body.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        fields['body_template'] = body
        row += 1

        dialog.columnconfigure(1, weight=1)

        # Load existing data
        if template_id:
            try:
                with get_connection() as conn:
                    r = conn.execute(
                        "SELECT template_name, template_type, subject_template, "
                        "body_template, send_method FROM notification_templates "
                        "WHERE template_id = ?", (template_id,)
                    ).fetchone()
                    if r:
                        fields['template_name'].insert(0, r['template_name'] or '')
                        fields['template_type'].insert(0, r['template_type'] or '')
                        fields['subject_template'].insert(0, r['subject_template'] or '')
                        fields['send_method'].set(r['send_method'] or 'email')
                        fields['body_template'].insert('1.0', r['body_template'] or '')
            except Exception:
                pass

        def save():
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            vals = {
                'template_name': fields['template_name'].get().strip(),
                'template_type': fields['template_type'].get().strip(),
                'subject_template': fields['subject_template'].get().strip(),
                'send_method': fields['send_method'].get(),
                'body_template': fields['body_template'].get('1.0', tk.END).strip(),
            }
            if not vals['template_name'] or not vals['template_type']:
                messagebox.showerror("Error", "Name and type are required.")
                return
            try:
                with transaction() as conn:
                    if template_id:
                        conn.execute(
                            "UPDATE notification_templates SET template_name=?, template_type=?, "
                            "subject_template=?, body_template=?, send_method=?, updated_at=? "
                            "WHERE template_id=?",
                            (vals['template_name'], vals['template_type'],
                             vals['subject_template'], vals['body_template'],
                             vals['send_method'], now, template_id)
                        )
                    else:
                        conn.execute(
                            "INSERT INTO notification_templates (template_name, template_type, "
                            "subject_template, body_template, send_method, is_active, "
                            "created_at, updated_at) VALUES (?,?,?,?,?,1,?,?)",
                            (vals['template_name'], vals['template_type'],
                             vals['subject_template'], vals['body_template'],
                             vals['send_method'], now, now)
                        )
                dialog.destroy()
                self._load_templates()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dialog, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=10)

    def _toggle_template_active(self):
        sel = self.templates_tree.selection()
        if not sel:
            return
        tid = self.templates_tree.item(sel[0])['values'][0]
        try:
            with transaction() as conn:
                conn.execute(
                    "UPDATE notification_templates SET is_active = NOT is_active, "
                    "updated_at = ? WHERE template_id = ?",
                    (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), tid)
                )
            self._load_templates()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # Notification Schedules Tab
    # ------------------------------------------------------------------
    def _create_schedules_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Alert Schedules")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Add Schedule",
                   command=self._add_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Toggle Active",
                   command=self._toggle_schedule_active).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Delete Selected",
                   command=self._delete_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_schedules).pack(side=tk.LEFT, padx=5)

        cols = ("schedule_id", "template_id", "trigger_condition",
                "days_before", "max_reminders", "interval_days", "is_active")
        self.schedules_tree = ttk.Treeview(tab, columns=cols, show="headings", height=12)
        self.schedules_tree.heading("schedule_id", text="ID")
        self.schedules_tree.heading("template_id", text="Template ID")
        self.schedules_tree.heading("trigger_condition", text="Trigger Condition")
        self.schedules_tree.heading("days_before", text="Days Before")
        self.schedules_tree.heading("max_reminders", text="Max Reminders")
        self.schedules_tree.heading("interval_days", text="Interval (Days)")
        self.schedules_tree.heading("is_active", text="Active")
        self.schedules_tree.column("schedule_id", width=50)
        self.schedules_tree.column("template_id", width=80)
        self.schedules_tree.column("trigger_condition", width=250)
        self.schedules_tree.column("days_before", width=80)
        self.schedules_tree.column("max_reminders", width=90)
        self.schedules_tree.column("interval_days", width=90)
        self.schedules_tree.column("is_active", width=60)

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.schedules_tree.yview)
        self.schedules_tree.configure(yscrollcommand=scroll.set)
        self.schedules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

    def _load_schedules(self):
        for item in self.schedules_tree.get_children():
            self.schedules_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT schedule_id, template_id, trigger_condition, "
                    "days_before_due, max_reminders, reminder_interval_days, "
                    "CASE WHEN is_active THEN 'Yes' ELSE 'No' END "
                    "FROM notification_schedules ORDER BY schedule_id"
                ).fetchall()
                for r in rows:
                    self.schedules_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            logger.debug(f"Could not load schedules: {e}")

    def _add_schedule(self):
        dialog = tk.Toplevel(self)
        dialog.title("New Alert Schedule")
        dialog.geometry("450x350")
        dialog.transient(self)
        dialog.grab_set()

        entries = {}
        for i, (label, key, default) in enumerate([
            ("Template ID:", "template_id", ""),
            ("Trigger Condition (JSON):", "trigger_condition", '{"event": "due_date_approaching"}'),
            ("Days Before Due:", "days_before_due", "7"),
            ("Max Reminders:", "max_reminders", "3"),
            ("Reminder Interval (Days):", "reminder_interval_days", "7"),
        ]):
            ttk.Label(dialog, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=5)
            e = ttk.Entry(dialog, width=40)
            e.insert(0, default)
            e.grid(row=i, column=1, padx=10, pady=5)
            entries[key] = e

        def save():
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            try:
                with transaction() as conn:
                    conn.execute(
                        "INSERT INTO notification_schedules "
                        "(template_id, trigger_condition, days_before_due, "
                        "max_reminders, reminder_interval_days, is_active, "
                        "created_at, updated_at) VALUES (?,?,?,?,?,1,?,?)",
                        (int(entries['template_id'].get()),
                         entries['trigger_condition'].get(),
                         int(entries['days_before_due'].get()),
                         int(entries['max_reminders'].get()),
                         int(entries['reminder_interval_days'].get()),
                         now, now)
                    )
                dialog.destroy()
                self._load_schedules()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dialog, text="Save", command=save).grid(
            row=5, column=0, columnspan=2, pady=10)

    def _toggle_schedule_active(self):
        sel = self.schedules_tree.selection()
        if not sel:
            return
        sid = self.schedules_tree.item(sel[0])['values'][0]
        try:
            with transaction() as conn:
                conn.execute(
                    "UPDATE notification_schedules SET is_active = NOT is_active, "
                    "updated_at = ? WHERE schedule_id = ?",
                    (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), sid)
                )
            self._load_schedules()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _delete_schedule(self):
        sel = self.schedules_tree.selection()
        if not sel:
            return
        sid = self.schedules_tree.item(sel[0])['values'][0]
        if messagebox.askyesno("Confirm", f"Delete schedule {sid}?"):
            try:
                with transaction() as conn:
                    conn.execute(
                        "DELETE FROM notification_schedules WHERE schedule_id = ?", (sid,)
                    )
                self._load_schedules()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------
    # User Notification Preferences Tab
    # ------------------------------------------------------------------
    def _create_preferences_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="User Preferences")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_preferences).pack(side=tk.LEFT, padx=5)

        cols = ("user_id", "notification_type", "enabled", "method", "advance_time")
        self.prefs_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        self.prefs_tree.heading("user_id", text="User ID")
        self.prefs_tree.heading("notification_type", text="Notification Type")
        self.prefs_tree.heading("enabled", text="Enabled")
        self.prefs_tree.heading("method", text="Method")
        self.prefs_tree.heading("advance_time", text="Advance (min)")
        self.prefs_tree.column("user_id", width=120)
        self.prefs_tree.column("notification_type", width=200)
        self.prefs_tree.column("enabled", width=80)
        self.prefs_tree.column("method", width=100)
        self.prefs_tree.column("advance_time", width=100)

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.prefs_tree.yview)
        self.prefs_tree.configure(yscrollcommand=scroll.set)
        self.prefs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

    def _load_preferences(self):
        for item in self.prefs_tree.get_children():
            self.prefs_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT user_id, notification_type, "
                    "CASE WHEN enabled THEN 'Yes' ELSE 'No' END, "
                    "method, advance_time "
                    "FROM notification_preferences ORDER BY user_id, notification_type"
                ).fetchall()
                for r in rows:
                    self.prefs_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            logger.debug(f"Could not load preferences: {e}")

    # ------------------------------------------------------------------
    # Notification Queue Tab
    # ------------------------------------------------------------------
    def _create_queue_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Notification Queue")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="Refresh",
                   command=self._load_queue).pack(side=tk.LEFT, padx=5)

        cols = ("id", "user_id", "notification_type", "scheduled_time", "status", "sent_at")
        self.queue_tree = ttk.Treeview(tab, columns=cols, show="headings", height=15)
        self.queue_tree.heading("id", text="ID")
        self.queue_tree.heading("user_id", text="User ID")
        self.queue_tree.heading("notification_type", text="Type")
        self.queue_tree.heading("scheduled_time", text="Scheduled")
        self.queue_tree.heading("status", text="Status")
        self.queue_tree.heading("sent_at", text="Sent At")
        self.queue_tree.column("id", width=80)
        self.queue_tree.column("user_id", width=120)
        self.queue_tree.column("notification_type", width=180)
        self.queue_tree.column("scheduled_time", width=160)
        self.queue_tree.column("status", width=80)
        self.queue_tree.column("sent_at", width=160)

        scroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=scroll.set)
        self.queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=5)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 10), pady=5)

    def _load_queue(self):
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, user_id, notification_type, scheduled_time, status, sent_at "
                    "FROM notification_queue ORDER BY scheduled_time DESC LIMIT 200"
                ).fetchall()
                for r in rows:
                    self.queue_tree.insert('', tk.END, values=tuple(r))
        except Exception as e:
            logger.debug(f"Could not load queue: {e}")

    def _load_all_data(self):
        self._load_templates()
        self._load_schedules()
        self._load_preferences()
        self._load_queue()
