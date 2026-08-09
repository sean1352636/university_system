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

        # Load sample data
        self.load_sample_logs()

        # Bind double-click to view details
        self.logs_tree.bind('<Double-1>', self.view_log_details)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    def load_sample_logs(self):
        """Load sample audit log data"""
        # Clear existing items
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)

        # Sample log entries
        import random
        from datetime import datetime

        categories = ["Authentication", "Database", "API", "User Actions", "System"]
        levels = ["INFO", "WARNING", "ERROR"]
        users = ["admin", "john.doe", "jane.smith", "system", "api_user"]
        actions = [
            "User login successful",
            "Database backup completed",
            "API key generated",
            "Student record updated",
            "System maintenance started",
            "Failed login attempt",
            "Database query executed",
            "File uploaded",
            "Report generated",
            "Configuration changed"
        ]
        ips = ["192.168.1.100", "10.0.0.50", "172.16.0.25", "203.0.113.10", "198.51.100.5"]

        # Generate sample logs for the last 7 days
        base_time = datetime.now()
        for i in range(100):
            timestamp = (base_time - timedelta(minutes=random.randint(0, 10080))).strftime('%Y-%m-%d %H:%M:%S')
            level = random.choice(levels)
            category = random.choice(categories)
            user = random.choice(users)
            action = random.choice(actions)
            ip = random.choice(ips)
            details = f"Additional context for {action.lower()}"

            # Add some realistic error patterns
            if level == "ERROR":
                action = random.choice([
                    "Database connection failed",
                    "Authentication timeout",
                    "API rate limit exceeded",
                    "File not found",
                    "Permission denied"
                ])

            self.logs_tree.insert('', 'end', values=(timestamp, level, category, user, action, ip, details))

    def apply_filters(self):
        """Apply filters to log display"""
        messagebox.showinfo(_("admin_windows.audit.messages.filters_applied_title"),
                           _("admin_windows.audit.messages.filters_applied_body",
                             date_range=self.date_range_var.get(),
                             log_level=self.level_var.get(),
                             category=self.category_var.get(),
                             search=self.search_var.get()))

        # Reload logs with filters (in real implementation)
        self.load_sample_logs()

    def export_logs(self):
        """Export filtered logs"""
        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.audit.messages.export_title"),
            defaultextension=".csv",
            filetypes=[(_("admin_windows.filetypes.csv"), "*.csv"), (_("admin_windows.filetypes.json"), "*.json"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.messages.export_complete"), _("admin_windows.audit.messages.logs_exported", filename=filename))

    def clear_logs(self):
        """Clear old log entries"""
        result = messagebox.askyesno(_("admin_windows.audit.messages.confirm_clear_title"),
                                   _("admin_windows.audit.messages.confirm_clear_body"))
        if result:
            messagebox.showinfo(_("admin_windows.audit.messages.logs_cleared_title"), _("admin_windows.audit.messages.logs_cleared_body"))

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
