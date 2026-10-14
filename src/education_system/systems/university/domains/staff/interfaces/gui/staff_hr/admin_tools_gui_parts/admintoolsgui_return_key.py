"""Methods _return_key through _quick_check_in."""
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import admin_tools_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsGUI:
    def _return_key(self):
        """Mark key as returned."""
        selected = self.keys_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.please_select_a_key', default="Please select a key"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.mark_this_key_as_returned', default="Mark this key as returned?")):
            return

        item = self.keys_tree.item(selected[0])
        key_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE key_assignments
                    SET status = 'returned', return_date = ?
                    WHERE assignment_id = ?
                """, (datetime.now().strftime("%Y-%m-%d"), key_id))

            log_activity("update", "key_assignment", assignment_id=key_id, details={"action": "returned"})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.key_marked_as_returned', default="Key marked as returned"))
            self._load_keys()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.error', default="Error"), f"Failed to update: {e}")

    def _report_key_lost(self):
        """Report key as lost."""
        selected = self.keys_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.please_select_a_key', default="Please select a key"))
            return

        if not messagebox.askyesno(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.confirm', default="Confirm"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.report_this_key_as_lost', default="Report this key as lost?")):
            return

        item = self.keys_tree.item(selected[0])
        key_id = item["values"][0]

        try:
            with transaction() as conn:
                conn.execute("UPDATE key_assignments SET status = 'lost' WHERE assignment_id = ?", (key_id,))

            log_activity("update", "key_assignment", assignment_id=key_id, details={"action": "reported_lost"})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.key_reported_as_lost', default="Key reported as lost"))
            self._load_keys()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.error', default="Error"), f"Failed to update: {e}")

    def _create_visitors_tab(self):
        """Create visitor management tab."""
        self.visitors_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.visitors_tab, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.tabs.visitors', default="Visitors"))

        main_paned = ttk.PanedWindow(self.visitors_tab, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=2)

        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)

        # Left: Visitor list
        list_frame = ttk.LabelFrame(left_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.visitor_registrations', default="Visitor Registrations"))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Filter
        filter_frame = ttk.Frame(list_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.date', default="Date:")).pack(side=tk.LEFT)
        self.visitor_date = ttk.Entry(filter_frame, width=12)
        self.visitor_date.pack(side=tk.LEFT, padx=5)
        self.visitor_date.insert(0, datetime.now().strftime("%Y-%m-%d"))

        ttk.Label(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.status', default="Status:")).pack(side=tk.LEFT, padx=(15, 0))
        self.visitor_status_filter = ttk.Combobox(filter_frame, values=[
            "All", "scheduled", "checked_in", "checked_out", "cancelled"
        ], state="readonly", width=12)
        self.visitor_status_filter.set("All")
        self.visitor_status_filter.pack(side=tk.LEFT, padx=5)
        self.visitor_status_filter.bind("<<ComboboxSelected>>", lambda e: self._load_visitors())

        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.search', default="Search"), command=self._load_visitors).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.today', default="Today"), command=self._show_today_visitors).pack(side=tk.RIGHT)

        # Treeview
        columns = ("id", "name", "company", "host", "purpose", "time", "status")
        self.visitors_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        self.visitors_tree.heading("id", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.headings.id', default="ID"))
        self.visitors_tree.heading("name", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.headings.visitor_name', default="Visitor Name"))
        self.visitors_tree.heading("company", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.headings.company', default="Company"))
        self.visitors_tree.heading("host", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.headings.host', default="Host"))
        self.visitors_tree.heading("purpose", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.headings.purpose', default="Purpose"))
        self.visitors_tree.heading("time", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.headings.time', default="Time"))
        self.visitors_tree.heading("status", text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.headings.status', default="Status"))

        self.visitors_tree.column("id", width=50)
        self.visitors_tree.column("name", width=150)
        self.visitors_tree.column("company", width=120)
        self.visitors_tree.column("host", width=100)
        self.visitors_tree.column("purpose", width=150)
        self.visitors_tree.column("time", width=80)
        self.visitors_tree.column("status", width=90)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.visitors_tree.yview)
        self.visitors_tree.configure(yscrollcommand=scrollbar.set)

        self.visitors_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        self.visitors_tree.bind("<<TreeviewSelect>>", self._on_visitor_select)

        # Tag colors
        self.visitors_tree.tag_configure("scheduled", background="#cfe2ff")
        self.visitors_tree.tag_configure("checked_in", background="#d1e7dd")
        self.visitors_tree.tag_configure("checked_out", background="#e7e8e9")
        self.visitors_tree.tag_configure("cancelled", background="#f8d7da")

        # Buttons
        btn_frame = ttk.Frame(list_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.register_visitor', default="Register Visitor"), command=self._register_visitor).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.check_in', default="Check In"), command=self._check_in_visitor).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.check_out', default="Check Out"), command=self._check_out_visitor).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.cancel', default="Cancel"), command=self._cancel_visitor).pack(side=tk.LEFT, padx=2)

        # Right: Visitor details
        detail_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.visitor_details', default="Visitor Details"))
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.visitor_detail_text = tk.Text(detail_frame, wrap=tk.WORD, height=15)
        self.visitor_detail_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.visitor_detail_text.config(state=tk.DISABLED)

        # Quick check-in
        checkin_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.quick_check_in', default="Quick Check-In"))
        checkin_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(checkin_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.badge_number', default="Badge Number:")).pack(anchor=tk.W, padx=5, pady=2)
        self.badge_entry = ttk.Entry(checkin_frame)
        self.badge_entry.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(checkin_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.vehicle_registration_optional', default="Vehicle Registration (optional):")).pack(anchor=tk.W, padx=5, pady=2)
        self.vehicle_entry = ttk.Entry(checkin_frame)
        self.vehicle_entry.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(checkin_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.check_in_with_badge', default="Check In with Badge"), command=self._quick_check_in).pack(pady=5)

        # Stats
        stats_frame = ttk.LabelFrame(right_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.today_s_stats', default="Today's Stats"))
        stats_frame.pack(fill=tk.X, padx=5, pady=5)

        self.stats_label = ttk.Label(stats_frame, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.loading', default="Loading..."))
        self.stats_label.pack(padx=5, pady=5)

        self._load_visitors()
        self._update_visitor_stats()

    def _load_visitors(self):
        """Load visitor registrations."""
        for item in self.visitors_tree.get_children():
            self.visitors_tree.delete(item)

        date_filter = self.visitor_date.get().strip()
        status_filter = self.visitor_status_filter.get()

        try:
            with get_connection() as conn:
                query = "SELECT * FROM visitor_registrations WHERE 1=1"
                params = []

                if date_filter:
                    query += " AND scheduled_date = ?"
                    params.append(date_filter)

                if status_filter != "All":
                    query += " AND status = ?"
                    params.append(status_filter)

                query += " ORDER BY scheduled_time ASC, created_at DESC"

                cursor = conn.cursor()
                cursor.execute(query, params)

                for row in cursor.fetchall():
                    values = (
                        row[0],  # visitor_id
                        row[1] or "",  # visitor_name
                        row[4] or "",  # visitor_company
                        row[5] or "",  # host_id
                        row[6] or "",  # visit_purpose
                        row[8] or "",  # scheduled_time
                        row[11] or "scheduled"  # status
                    )
                    status = row[11] or "scheduled"
                    self.visitors_tree.insert("", tk.END, values=values, tags=(status,))

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        self._update_visitor_stats()

    def _show_today_visitors(self):
        """Show today's visitors."""
        self.visitor_date.delete(0, tk.END)
        self.visitor_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self._load_visitors()

    def _on_visitor_select(self, event):
        """Handle visitor selection."""
        selected = self.visitors_tree.selection()
        if not selected:
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM visitor_registrations WHERE visitor_id = ?", (visitor_id,))
                row = cursor.fetchone()

                if row:
                    self.visitor_detail_text.config(state=tk.NORMAL)
                    self.visitor_detail_text.delete(1.0, tk.END)

                    details = f"""Visitor ID: {row[0]}
Name: {row[1]}
Email: {row[2] or 'N/A'}
Phone: {row[3] or 'N/A'}
Company: {row[4] or 'N/A'}

Host: {row[5]}
Purpose: {row[6]}

Scheduled Date: {row[7]}
Scheduled Time: {row[8]}

Check-in Time: {row[9] or 'Not checked in'}
Check-out Time: {row[10] or 'Not checked out'}
Status: {row[11]}

Badge Number: {row[12] or 'N/A'}
Vehicle: {row[13] or 'N/A'}
Notes: {row[14] or 'None'}
"""
                    self.visitor_detail_text.insert(1.0, details)
                    self.visitor_detail_text.config(state=tk.DISABLED)

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _register_visitor(self):
        """Register a new visitor."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.windows.register_visitor', default="Register Visitor"))
        dialog.geometry("450x550")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.visitor_name', default="Visitor Name:")).pack(anchor=tk.W, padx=10, pady=5)
        name_entry = ttk.Entry(dialog)
        name_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.email', default="Email:")).pack(anchor=tk.W, padx=10, pady=5)
        email_entry = ttk.Entry(dialog)
        email_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.phone', default="Phone:")).pack(anchor=tk.W, padx=10, pady=5)
        phone_entry = ttk.Entry(dialog)
        phone_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.company_organization', default="Company/Organization:")).pack(anchor=tk.W, padx=10, pady=5)
        company_entry = ttk.Entry(dialog)
        company_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.host_user_id', default="Host (User ID):")).pack(anchor=tk.W, padx=10, pady=5)
        host_entry = ttk.Entry(dialog)
        host_entry.pack(fill=tk.X, padx=10)
        if self.current_user:
            host_entry.insert(0, self.current_user.get("user_id", ""))

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.purpose_of_visit', default="Purpose of Visit:")).pack(anchor=tk.W, padx=10, pady=5)
        purpose_entry = ttk.Entry(dialog)
        purpose_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.scheduled_date_yyyy_mm_dd', default="Scheduled Date (YYYY-MM-DD):")).pack(anchor=tk.W, padx=10, pady=5)
        date_entry = ttk.Entry(dialog)
        date_entry.pack(fill=tk.X, padx=10)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.scheduled_time_hh_mm', default="Scheduled Time (HH:MM):")).pack(anchor=tk.W, padx=10, pady=5)
        time_entry = ttk.Entry(dialog)
        time_entry.pack(fill=tk.X, padx=10)

        ttk.Label(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.labels.notes', default="Notes:")).pack(anchor=tk.W, padx=10, pady=5)
        notes_text = tk.Text(dialog, height=3)
        notes_text.pack(fill=tk.X, padx=10)

        def register():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.error', default="Error"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.visitor_name_is_required', default="Visitor name is required"))
                return

            host = host_entry.get().strip()
            if not host:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.error', default="Error"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.host_is_required', default="Host is required"))
                return

            try:
                with transaction() as conn:
                    conn.execute("""
                        INSERT INTO visitor_registrations
                        (visitor_name, visitor_email, visitor_phone, visitor_company,
                         host_id, visit_purpose, scheduled_date, scheduled_time,
                         status, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        name,
                        email_entry.get().strip() or None,
                        phone_entry.get().strip() or None,
                        company_entry.get().strip() or None,
                        host,
                        purpose_entry.get().strip(),
                        date_entry.get().strip(),
                        time_entry.get().strip() or None,
                        "scheduled",
                        notes_text.get(1.0, tk.END).strip() or None,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))

                log_activity("create", "visitor_registration", user_id=host, details={"visitor_name": name})
                messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.visitor_registered', default="Visitor registered"))
                dialog.destroy()
                self._load_visitors()

            except Exception as e:
                messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.error', default="Error"), f"Failed to register visitor: {e}")

        ttk.Button(dialog, text=_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.buttons.register', default="Register"), command=register).pack(pady=10)

    def _check_in_visitor(self):
        """Check in selected visitor."""
        selected = self.visitors_tree.selection()
        if not selected:
            messagebox.showwarning(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.warning', default="Warning"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.please_select_a_visitor', default="Please select a visitor"))
            return

        item = self.visitors_tree.item(selected[0])
        visitor_id = item["values"][0]
        current_status = item["values"][6]

        if current_status == "checked_in":
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.info', default="Info"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.visitor_is_already_checked_in', default="Visitor is already checked in"))
            return

        badge = self.badge_entry.get().strip()
        vehicle = self.vehicle_entry.get().strip()

        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE visitor_registrations
                    SET status = 'checked_in', check_in_time = ?,
                        badge_number = ?, vehicle_registration = ?
                    WHERE visitor_id = ?
                """, (
                    datetime.now().strftime("%H:%M:%S"),
                    badge or None,
                    vehicle or None,
                    visitor_id
                ))

            log_activity("update", "visitor_registration", visitor_id=visitor_id, details={"action": "checked_in"})
            messagebox.showinfo(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.success', default="Success"), _t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.visitor_checked_in', default="Visitor checked in"))
            self.badge_entry.delete(0, tk.END)
            self.vehicle_entry.delete(0, tk.END)
            self._load_visitors()

        except Exception as e:
            messagebox.showerror(_t('gui.staff.staff_hr.admin_tools_gui_parts.admintoolsgui_return_key.dialogs.error', default="Error"), f"Failed to check in: {e}")

    def _quick_check_in(self):
        """Quick check-in with badge for selected visitor."""
        self._check_in_visitor()
