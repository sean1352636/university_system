"""Extracted class implementation."""

from .. import admin_management_windows_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AuditLogsWindow:
    """Comprehensive Audit Logs Viewer"""

    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("admin_windows.audit.title"))
        self.window.geometry("1000x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("admin_windows.audit.center_title"),
                 font=('Arial', 16, 'bold')).pack()

        # Filters frame
        filters_frame = ttk.LabelFrame(self.window, text=_("admin_windows.audit.filters"), padding="15")
        filters_frame.pack(fill='x', padx=20, pady=(0, 15))

        # Filter controls
        filter_grid = ttk.Frame(filters_frame)
        filter_grid.pack(fill='x')

        # Date range
        ttk.Label(filter_grid, text=_("admin_windows.audit.date_range")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.date_range_var = tk.StringVar(value=_("admin_windows.audit.date_options.last_7_days"))
        ttk.Combobox(filter_grid, textvariable=self.date_range_var,
                    values=[_("admin_windows.audit.date_options.last_24_hours"), _("admin_windows.audit.date_options.last_7_days"), _("admin_windows.audit.date_options.last_30_days"), _("admin_windows.audit.date_options.custom")],
                    width=15).grid(row=0, column=1, sticky='w')

        # Log level
        ttk.Label(filter_grid, text=_("admin_windows.audit.log_level")).grid(row=0, column=2, sticky='w', padx=(20, 10))
        self.level_var = tk.StringVar(value=_("admin_windows.audit.level_options.all"))
        ttk.Combobox(filter_grid, textvariable=self.level_var,
                    values=[_("admin_windows.audit.level_options.all"), "INFO", "WARNING", "ERROR", "CRITICAL"],
                    width=15).grid(row=0, column=3, sticky='w')

        # Category
        ttk.Label(filter_grid, text=_("admin_windows.audit.category")).grid(row=0, column=4, sticky='w', padx=(20, 10))
        self.category_var = tk.StringVar(value=_("admin_windows.audit.category_options.all"))
        ttk.Combobox(filter_grid, textvariable=self.category_var,
                    values=[_("admin_windows.audit.category_options.all"), _("admin_windows.audit.category_options.authentication"), _("admin_windows.audit.category_options.database"), _("admin_windows.audit.category_options.api"), _("admin_windows.audit.category_options.user_actions"), _("admin_windows.audit.category_options.system")],
                    width=15).grid(row=0, column=5, sticky='w')

        # Search
        ttk.Label(filter_grid, text=_("common.search")).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.search_var = tk.StringVar()
        ttk.Entry(filter_grid, textvariable=self.search_var, width=30).grid(row=1, column=1, columnspan=2, sticky='ew', pady=(10, 0))

        # Filter button
        ttk.Button(filter_grid, text=_("admin_windows.audit.buttons.apply_filters"), command=self.apply_filters).grid(row=1, column=3, padx=(10, 0), pady=(10, 0))
        ttk.Button(filter_grid, text=_("admin_windows.audit.buttons.export_logs"), command=self.export_logs).grid(row=1, column=4, padx=(10, 0), pady=(10, 0))
        ttk.Button(filter_grid, text=_("admin_windows.audit.buttons.clear_logs"), command=self.clear_logs).grid(row=1, column=5, padx=(10, 0), pady=(10, 0))

        # Logs display
        logs_frame = ttk.LabelFrame(self.window, text=_("admin_windows.audit.log_entries"), padding="15")
        logs_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))

        # Logs treeview
        columns = ('Timestamp', 'Level', 'Category', 'User', 'Action', 'IP Address', 'Details')
        column_names = [
            _("admin_windows.audit.columns.timestamp"),
            _("admin_windows.audit.columns.level"),
            _("admin_windows.audit.columns.category"),
            _("admin_windows.audit.columns.user"),
            _("admin_windows.audit.columns.action"),
            _("admin_windows.audit.columns.ip_address"),
            _("admin_windows.audit.columns.details")
        ]
        self.logs_tree = ttk.Treeview(logs_frame, columns=columns, show='headings', height=20)

        for col, name in zip(columns, column_names):
            self.logs_tree.heading(col, text=name)
            self.logs_tree.column(col, width=120)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(logs_frame, orient='vertical', command=self.logs_tree.yview)
        v_scrollbar.pack(side='right', fill='y')
        self.logs_tree.config(yscrollcommand=v_scrollbar.set)

        h_scrollbar = ttk.Scrollbar(logs_frame, orient='horizontal', command=self.logs_tree.xview)
        h_scrollbar.pack(side='bottom', fill='x')
        self.logs_tree.config(xscrollcommand=h_scrollbar.set)

        self.logs_tree.pack(fill='both', expand=True)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.window, textvariable=self.status_var, foreground='#555555').pack(
            fill='x', padx=20)

        # Real entries from the university and platform audit stores
        self.entries = []
        self.custom_range = (None, None)
        self.load_logs()

        # Bind double-click to view details
        self.logs_tree.bind('<Double-1>', self.view_log_details)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    # ── data ──────────────────────────────────────────────────────────────
    def _filter_values(self):
        """Translate the combobox choices into reader arguments."""
        from education_system.systems.university.infrastructure.security.audit_log_reader import (
            CATEGORIES, since_for,
        )
        date_choice = self.date_range_var.get()
        ranges = {
            _("admin_windows.audit.date_options.last_24_hours"): "24h",
            _("admin_windows.audit.date_options.last_7_days"): "7d",
            _("admin_windows.audit.date_options.last_30_days"): "30d",
        }
        since, until = None, None
        if date_choice == _("admin_windows.audit.date_options.custom"):
            since, until = self.custom_range
        else:
            since = since_for(ranges.get(date_choice, "7d"))

        level = self.level_var.get()
        level = None if level == _("admin_windows.audit.level_options.all") else level

        category_labels = {
            _("admin_windows.audit.category_options.authentication"): CATEGORIES[0],
            _("admin_windows.audit.category_options.database"): CATEGORIES[1],
            _("admin_windows.audit.category_options.api"): CATEGORIES[2],
            _("admin_windows.audit.category_options.user_actions"): CATEGORIES[3],
            _("admin_windows.audit.category_options.system"): CATEGORIES[4],
        }
        category = category_labels.get(self.category_var.get())
        return since, until, level, category, self.search_var.get().strip() or None

    def load_logs(self):
        """Load real audit entries matching the current filters."""
        from education_system.systems.university.infrastructure.security.audit_log_reader import (
            read_audit_entries,
        )
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

        since, until, level, category, search = self._filter_values()
        errors = []
        try:
            self.entries = read_audit_entries(since=since, until=until, level=level,
                                              category=category, search=search,
                                              errors=errors)
        except Exception as exc:
            self.entries = []
            errors.append(str(exc))

        for entry in self.entries:
            details = entry["details"]
            if entry["resource"]:
                details = f"[{entry['resource']}] {details}".strip()
            self.logs_tree.insert('', 'end', values=(
                entry["timestamp"], entry["level"], entry["category"], entry["user"],
                entry["action"], entry["ip"] or "-", f"{details}  ({entry['source']})"))

        if self.entries:
            status = f"{len(self.entries)} entr{'y' if len(self.entries) == 1 else 'ies'} shown"
            if since:
                status += f" since {since}"
        else:
            status = "No audit entries match these filters."
        if errors:
            status += " - some stores could not be read: " + "; ".join(errors)
        self.status_var.set(status)

    # Older callers used this name.
    load_sample_logs = load_logs

    def apply_filters(self):
        """Re-read the audit stores with the chosen filters."""
        if self.date_range_var.get() == _("admin_windows.audit.date_options.custom"):
            from tkinter import simpledialog
            start = simpledialog.askstring(_("admin_windows.audit.date_range"),
                                           "From date (YYYY-MM-DD):", parent=self.window)
            if start is None:
                return
            end = simpledialog.askstring(_("admin_windows.audit.date_range"),
                                         "To date (YYYY-MM-DD, blank for today):",
                                         parent=self.window)
            try:
                since = datetime.strptime(start.strip(), "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00")
                until = (datetime.strptime(end.strip(), "%Y-%m-%d").strftime("%Y-%m-%d 23:59:59")
                         if end and end.strip() else None)
            except ValueError:
                messagebox.showerror(_("admin_windows.audit.date_range"),
                                     "Dates must be in YYYY-MM-DD form.", parent=self.window)
                return
            self.custom_range = (since, until)
        self.load_logs()

    def export_logs(self):
        """Export the entries currently shown to CSV or JSON."""
        if not self.entries:
            messagebox.showinfo(_("admin_windows.audit.messages.export_title"),
                                "There are no entries to export with these filters.",
                                parent=self.window)
            return
        filename = filedialog.asksaveasfilename(
            parent=self.window,
            title=_("admin_windows.audit.messages.export_title"),
            defaultextension=".csv",
            filetypes=[(_("admin_windows.filetypes.csv"), "*.csv"), (_("admin_windows.filetypes.json"), "*.json"), (_("admin_windows.filetypes.all"), "*.*")]
        )
        if not filename:
            return
        fields = ("timestamp", "level", "category", "user", "action", "resource", "ip",
                  "details", "source")
        try:
            if filename.lower().endswith(".json"):
                with open(filename, "w", encoding="utf-8") as handle:
                    json.dump([{k: e[k] for k in fields} for e in self.entries], handle, indent=2)
            else:
                import csv
                with open(filename, "w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(self.entries)
        except OSError as exc:
            messagebox.showerror(_("admin_windows.audit.messages.export_title"),
                                 f"Could not write {filename}: {exc}", parent=self.window)
            return
        messagebox.showinfo(_("admin_windows.messages.export_complete"),
                            _("admin_windows.audit.messages.logs_exported", filename=filename),
                            parent=self.window)

    def clear_logs(self):
        """Purge old rows from the operational activity log.

        Only ``activity_log`` is purged, through the activity logger's own
        retention call. The security audit trail, the hash-chained immutable
        log and the platform audit store are never cleared from here.
        """
        from tkinter import simpledialog
        days = simpledialog.askinteger(
            _("admin_windows.audit.messages.confirm_clear_title"),
            "Delete activity-log entries older than how many days?\n"
            "(minimum 90; the security audit trail and the immutable audit "
            "log are kept regardless)",
            parent=self.window, initialvalue=365, minvalue=90)
        if not days:
            return
        if not messagebox.askyesno(_("admin_windows.audit.messages.confirm_clear_title"),
                                   _("admin_windows.audit.messages.confirm_clear_body")
                                   + f"\n\nActivity-log entries older than {days} days will be deleted.",
                                   parent=self.window):
            return
        try:
            from education_system.systems.university.infrastructure.utils.activity_logger import get_logger_instance
            db_logger = getattr(get_logger_instance(), "db_logger", None)
            if db_logger is None:
                raise RuntimeError("the activity log database is not available")
            removed = db_logger.delete_old_logs(days)
        except Exception as exc:
            messagebox.showerror(_("admin_windows.audit.messages.logs_cleared_title"),
                                 f"Nothing was deleted: {exc}", parent=self.window)
            return
        messagebox.showinfo(_("admin_windows.audit.messages.logs_cleared_title"),
                            f"{removed or 0} activity-log entr{'y' if removed == 1 else 'ies'} "
                            f"older than {days} days deleted.", parent=self.window)
        self.load_logs()

    def view_log_details(self, event):
        """View detailed information about selected log entry"""
        selection = self.logs_tree.selection()
        if not selection:
            return

        item = self.logs_tree.item(selection[0])
        log_data = item['values']

        details_window = tk.Toplevel(self.window)
        details_window.title(_("admin_windows.audit.details.title"))
        details_window.geometry("600x500")
        details_window.transient(self.window)

        # Details display
        details_frame = ttk.LabelFrame(details_window, text=_("admin_windows.audit.details.title"), padding="15")
        details_frame.pack(fill='both', expand=True, padx=15, pady=15)

        details_text = scrolledtext.ScrolledText(details_frame, height=20, wrap='word')
        details_text.pack(fill='both', expand=True)

        detail_info = _("admin_windows.audit.details.body",
                       timestamp=log_data[0], level=log_data[1], category=log_data[2],
                       user=log_data[3], action=log_data[4], ip=log_data[5], details=log_data[6])

        details_text.insert('1.0', detail_info)
        details_text.config(state='disabled')

        ttk.Button(details_window, text=_("common.close"), command=details_window.destroy).pack(pady=10)
