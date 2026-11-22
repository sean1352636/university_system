"""Methods __init__ through create_optimization_tab."""

from .. import admin_management_windows_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DatabaseMaintenanceWindow:
    def __init__(self, parent):
        self.parent = parent

        self.window = tk.Toplevel(parent)
        self.window.title(_("admin_windows.database.title"))
        self.window.geometry("900x700")
        self.window.transient(parent)
        self.window.grab_set()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self.window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("admin_windows.database.center_title"),
                 font=('Arial', 16, 'bold')).pack()

        # Create notebook for different maintenance sections
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        # Database Status Tab
        status_frame = ttk.Frame(notebook)
        notebook.add(status_frame, text=_("admin_windows.database.tabs.status"))
        self.create_status_tab(status_frame)

        # Backup & Restore Tab
        backup_frame = ttk.Frame(notebook)
        notebook.add(backup_frame, text=_("admin_windows.database.tabs.backup"))
        self.create_backup_tab(backup_frame)

        # Optimization Tab
        optimization_frame = ttk.Frame(notebook)
        notebook.add(optimization_frame, text=_("admin_windows.database.tabs.optimization"))
        self.create_optimization_tab(optimization_frame)

        # Monitoring Tab
        monitoring_frame = ttk.Frame(notebook)
        notebook.add(monitoring_frame, text=_("admin_windows.database.tabs.monitoring"))
        self.create_monitoring_tab(monitoring_frame)

        # Close button
        ttk.Button(self.window, text=_("common.close"), command=self.window.destroy).pack(pady=10)

    def create_status_tab(self, parent):
        """Create database status tab"""
        # Status overview
        overview_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.status.overview"), padding="15")
        overview_frame.pack(fill='x', padx=15, pady=15)

        # Status indicators
        status_grid = ttk.Frame(overview_frame)
        status_grid.pack(fill='x')

        # Filled from the real database by refresh_status() (PRAGMAs,
        # sqlite_master and the files on disk).
        self._status_labels = {}
        status_keys = [
            ("connection", _("admin_windows.database.status.connection")),
            ("health", _("admin_windows.database.status.health")),
            ("size", _("admin_windows.database.status.size")),
            ("tables", _("admin_windows.database.status.tables")),
            ("connections", "Other processes"),
            ("wal", "WAL file"),
        ]
        for i, (key, label) in enumerate(status_keys):
            status_item = ttk.LabelFrame(status_grid, text=label, padding="10")
            status_item.grid(row=i//3, column=i%3, padx=5, pady=5, sticky='ew')
            value_label = ttk.Label(status_item, text="...", font=('Arial', 12, 'bold'))
            value_label.pack()
            self._status_labels[key] = value_label
            status_grid.grid_columnconfigure(i%3, weight=1)

        # Detailed status
        details_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.status.detailed_info"), padding="15")
        details_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        self.status_text = scrolledtext.ScrolledText(details_frame, height=18, wrap='word')
        self.status_text.pack(fill='both', expand=True)
        self.status_text.config(state='disabled')

        # Status actions
        actions_frame = ttk.Frame(details_frame)
        actions_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.refresh"),
                  command=self.refresh_status).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.test_connection"),
                  command=self.test_connection).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.export"),
                  command=self.export_status).pack(side='left')

        self._render_status(show_message=False)

    def create_backup_tab(self, parent):
        """Create backup and restore tab"""
        # Backup controls
        backup_controls = ttk.LabelFrame(parent, text=_("admin_windows.database.backup.operations"), padding="15")
        backup_controls.pack(fill='x', padx=15, pady=15)

        # Backup type selection
        backup_type_frame = ttk.Frame(backup_controls)
        backup_type_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(backup_type_frame, text=_("admin_windows.database.backup.type")).pack(side='left', padx=(0, 10))
        self.backup_type_var = tk.StringVar(value=_("admin_windows.database.backup.types.full"))
        ttk.Combobox(backup_type_frame, textvariable=self.backup_type_var,
                    values=[_("admin_windows.database.backup.types.full"), _("admin_windows.database.backup.types.incremental"), _("admin_windows.database.backup.types.schema"), _("admin_windows.database.backup.types.data")],
                    width=20).pack(side='left', padx=(0, 20))

        ttk.Label(backup_type_frame, text=_("admin_windows.database.backup.compression")).pack(side='left', padx=(0, 10))
        self.compression_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_type_frame, text=_("admin_windows.database.backup.enable"), variable=self.compression_var).pack(side='left')

        # Backup actions
        backup_actions = ttk.Frame(backup_controls)
        backup_actions.pack(fill='x')

        ttk.Button(backup_actions, text=_("admin_windows.database.backup.buttons.create"),
                  command=self.create_backup).pack(side='left', padx=(0, 10))
        ttk.Button(backup_actions, text=_("admin_windows.database.backup.buttons.schedule"),
                  command=self.schedule_backup).pack(side='left', padx=(0, 10))
        ttk.Button(backup_actions, text=_("admin_windows.database.backup.buttons.verify"),
                  command=self.verify_backup).pack(side='left')

        # Backup history
        history_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.backup.history"), padding="15")
        history_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        # Backup history tree
        columns = ('Date', 'Type', 'Size', 'Duration', 'Status', 'Location')
        column_names = [
            _("common.date"),
            _("admin_windows.database.backup.columns.type"),
            _("admin_windows.database.backup.columns.size"),
            _("admin_windows.database.backup.columns.duration"),
            _("common.status"),
            _("admin_windows.database.backup.columns.location")
        ]
        self.backup_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=12)

        for col, name in zip(columns, column_names):
            self.backup_tree.heading(col, text=name)
            self.backup_tree.column(col, width=120)

        self.backup_tree.pack(fill='both', expand=True, pady=(0, 15))

        # Real backups on disk (var/backups via the paths helpers); the row's
        # tag carries the file path the restore/verify/download/delete
        # buttons act on.
        self.backup_status_var = tk.StringVar(value="")
        ttk.Label(history_frame, textvariable=self.backup_status_var,
                  foreground='#555555', wraplength=800).pack(fill='x', pady=(0, 8))
        self.refresh_backup_history()

        # Restore controls
        restore_frame = ttk.Frame(history_frame)
        restore_frame.pack(fill='x')

        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.restore"),
                  command=self.restore_backup).pack(side='left', padx=(0, 10))
        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.download"),
                  command=self.download_backup).pack(side='left', padx=(0, 10))
        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.delete"),
                  command=self.delete_backup).pack(side='left', padx=(0, 10))
        ttk.Button(restore_frame, text=_("admin_windows.database.backup.buttons.restore_file"),
                  command=self.restore_from_file).pack(side='left')

    def create_optimization_tab(self, parent):
        """Create optimization tab"""
        # Optimization controls
        opt_controls = ttk.LabelFrame(parent, text=_("admin_windows.database.optimization.title"), padding="15")
        opt_controls.pack(fill='x', padx=15, pady=15)

        # Optimization options
        opt_grid = ttk.Frame(opt_controls)
        opt_grid.pack(fill='x', pady=(0, 15))

        self.vacuum_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.vacuum"),
                       variable=self.vacuum_var).grid(row=0, column=0, sticky='w', padx=(0, 20))

        self.analyze_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.analyze"),
                       variable=self.analyze_var).grid(row=0, column=1, sticky='w')

        self.reindex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.reindex"),
                       variable=self.reindex_var).grid(row=1, column=0, sticky='w', padx=(0, 20))

        self.cleanup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_grid, text=_("admin_windows.database.optimization.cleanup"),
                       variable=self.cleanup_var).grid(row=1, column=1, sticky='w')

        # Optimization actions
        opt_actions = ttk.Frame(opt_controls)
        opt_actions.pack(fill='x')

        ttk.Button(opt_actions, text=_("admin_windows.database.optimization.buttons.run"),
                  command=self.run_optimization).pack(side='left', padx=(0, 10))
        ttk.Button(opt_actions, text=_("admin_windows.database.optimization.buttons.schedule"),
                  command=self.schedule_maintenance).pack(side='left', padx=(0, 10))
        ttk.Button(opt_actions, text=_("admin_windows.database.optimization.buttons.integrity"),
                  command=self.check_integrity).pack(side='left')

        # Optimization results
        results_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.optimization.results"), padding="15")
        results_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        self.opt_text = scrolledtext.ScrolledText(results_frame, height=18, wrap='word')
        self.opt_text.pack(fill='both', expand=True)
        self._show_optimization_overview()
