"""Methods __init__ through create_cloud_tab."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import backup_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class BackupGUI:
    def __init__(self, root, auth=None):
        self.root = root
        self.auth = auth  # Store authentication instance
        # When ``root`` is a workspace tab Frame (passed by
        # ``open_in_workspace``), it has no ``wm_title`` — skip the
        # window-chrome calls. Same shape as Library (8.117.34).
        if hasattr(self.root, "wm_title"):
            self.root.title(_t("backup.window_title", default="Enhanced Data Backup System"))
            self.root.geometry("1200x800")
            self.root.minsize(1000, 600)

        # Initialize GUI state
        self.backup_thread = None
        self.log_queue = queue.Queue()
        self.status_var = tk.StringVar(value=_t('gui.shell.database.backup_gui_parts.backupgui_init.values.ready', default="Ready"))
        self.progress_var = tk.DoubleVar()

        # Load configuration
        load_config()

        # Create GUI
        self.create_widgets()
        self.setup_logging()

        # Start scheduler if enabled
        if config["auto_backup_enabled"]:
            start_scheduler()

        # Start log monitoring
        self.monitor_logs()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Create main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Create tabs
        self.create_main_tab()
        self.create_advanced_tab()
        self.create_config_tab()
        self.create_analysis_tab()
        self.create_cloud_tab()
        self.create_logs_tab()

        # Create status bar
        self.create_status_bar()

    def create_main_tab(self):
        """Create the main backup operations tab"""
        main_frame = ttk.Frame(self.notebook)
        self.notebook.add(main_frame, text=_t("backup.tab_main_operations", default="Main Operations"))

        # Title and menu button frame
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill="x", pady=10, padx=10)

        title_label = ttk.Label(title_frame, text=_t("backup.title", default="Data Backup System"),
                               font=("Arial", 16, "bold"))
        title_label.pack(side="left")

        ttk.Button(title_frame, text=_t("backup.return_to_main_menu", default="\U0001f3e0 Return to Main Menu"),
                  command=self.return_to_main_menu).pack(side="right")

        # Main operations frame
        ops_frame = ttk.LabelFrame(main_frame, text=_t("backup.basic_operations", default="Basic Operations"), padding=10)
        ops_frame.pack(fill="x", padx=10, pady=5)

        # Buttons frame
        btn_frame1 = ttk.Frame(ops_frame)
        btn_frame1.pack(fill="x", pady=5)

        ttk.Button(btn_frame1, text=_t("backup.create_manual_backup", default="Create Manual Backup"),
                  command=self.create_manual_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text=_t("backup.view_backups", default="View Backups"),
                  command=self.view_backups).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text=_t("backup.restore_from_backup", default="Restore from Backup"),
                  command=self.restore_backup).pack(side="left", padx=5)

        btn_frame2 = ttk.Frame(ops_frame)
        btn_frame2.pack(fill="x", pady=5)

        ttk.Button(btn_frame2, text=_t("backup.quick_backup", default="Quick Backup"),
                  command=self.quick_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text=_t("backup.validate_backup", default="Validate Backup"),
                  command=self.validate_backup_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text=_t("backup.export_backup", default="Export Backup"),
                  command=self.export_backup_gui).pack(side="left", padx=5)

        # Backup list frame
        list_frame = ttk.LabelFrame(main_frame, text=_t("backup.recent_backups", default="Recent Backups"), padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Treeview for backup list
        columns = ("ID", "Type", "Date", "Size", "Status")
        self.backup_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)

        for col in columns:
            self.backup_tree.heading(col, text=col)
            self.backup_tree.column(col, width=100)

        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.backup_tree.yview)
        self.backup_tree.configure(yscrollcommand=scrollbar.set)

        self.backup_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate backup list
        self.refresh_backup_list()

        # Auto-refresh every 30 seconds
        self.root.after(30000, self.auto_refresh_backup_list)

    def create_advanced_tab(self):
        """Create the advanced backup operations tab - ADD MISSING ITEMS"""
        advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(advanced_frame, text=_t("backup.tab_advanced", default="Advanced"))

        # Advanced backup types
        types_frame = ttk.LabelFrame(advanced_frame, text=_t("backup.advanced_backup_types", default="Advanced Backup Types"), padding=10)
        types_frame.pack(fill="x", padx=10, pady=5)

        btn_frame1 = ttk.Frame(types_frame)
        btn_frame1.pack(fill="x", pady=5)

        ttk.Button(btn_frame1, text=_t("backup.incremental_backup", default="Incremental Backup"),
                  command=self.create_incremental_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text=_t("backup.selective_backup", default="Selective Backup"),
                  command=self.create_selective_backup).pack(side="left", padx=5)
        ttk.Button(btn_frame1, text=_t("backup.schema_only", default="Schema Only"),
                  command=self.create_schema_backup).pack(side="left", padx=5)

        # ADD MISSING: Differential backup button
        ttk.Button(btn_frame1, text=_t("backup.differential_backup", default="Differential Backup"),
                  command=self.create_differential_backup).pack(side="left", padx=5)

        # Templates frame
        template_frame = ttk.LabelFrame(advanced_frame, text=_t("backup.templates", default="Templates"), padding=10)
        template_frame.pack(fill="x", padx=10, pady=5)

        btn_frame2 = ttk.Frame(template_frame)
        btn_frame2.pack(fill="x", pady=5)

        ttk.Button(btn_frame2, text=_t("backup.save_template", default="Save Template"),
                  command=self.save_template_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text=_t("backup.load_template", default="Load Template"),
                  command=self.load_template_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text=_t("backup.manage_templates", default="Manage Templates"),
                  command=self.manage_templates_gui).pack(side="left", padx=5)

        # ADD MISSING: Import/Export templates
        ttk.Button(btn_frame2, text=_t("backup.import_template", default="Import Template"),
                  command=self.import_template_gui).pack(side="left", padx=5)
        ttk.Button(btn_frame2, text=_t("backup.export_template", default="Export Template"),
                  command=self.export_template_gui).pack(side="left", padx=5)

        # Schedule frame (existing code with update_schedule_status fix)
        schedule_frame = ttk.LabelFrame(advanced_frame, text=_t("backup.scheduling", default="Scheduling"), padding=10)
        schedule_frame.pack(fill="x", padx=10, pady=5)

        self.schedule_var = tk.StringVar()
        ttk.Label(schedule_frame, textvariable=self.schedule_var).pack(pady=5)

        btn_frame3 = ttk.Frame(schedule_frame)
        btn_frame3.pack(fill="x", pady=5)

        self.schedule_btn = ttk.Button(btn_frame3, text=_t("backup.enable_scheduling", default="Enable Scheduling"),
                                     command=self.toggle_scheduling)
        self.schedule_btn.pack(side="left", padx=5)

        ttk.Button(btn_frame3, text=_t("backup.configure_schedule", default="Configure Schedule"),
                  command=self.configure_schedule_gui).pack(side="left", padx=5)

        # ADD MISSING: Advanced scheduling options
        ttk.Button(btn_frame3, text=_t("backup.schedule_history", default="Schedule History"),
                  command=self.show_schedule_history).pack(side="left", padx=5)
        ttk.Button(btn_frame3, text=_t("backup.test_schedule", default="Test Schedule"),
                  command=self.test_schedule).pack(side="left", padx=5)

        self.update_schedule_status()

    def update_schedule_status(self):
        """Update schedule status display"""
        if config["auto_backup_enabled"]:
            status = f"Scheduling: Enabled ({config['backup_frequency']} at {config['scheduled_backup_time']})"
            button_text = "Disable Scheduling"
        else:
            status = "Scheduling: Disabled"
            button_text = "Enable Scheduling"

        self.schedule_var.set(status)

        # Only update button if it exists
        if hasattr(self, 'schedule_btn'):
            self.schedule_btn.config(text=button_text)

    def create_config_tab(self):
        """Create the configuration tab"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text=_t("backup.tab_configuration", default="Configuration"))

        # Create scrollable frame
        canvas = tk.Canvas(config_frame)
        scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Basic settings
        basic_frame = ttk.LabelFrame(scrollable_frame, text=_t("backup.basic_settings", default="Basic Settings"), padding=10)
        basic_frame.pack(fill="x", padx=10, pady=5)

        # Backup directory
        ttk.Label(basic_frame, text=_t("backup.backup_directory", default="Backup Directory:")).grid(row=0, column=0, sticky="w", pady=2)
        self.backup_dir_var = tk.StringVar(value=config["backup_directory"])
        ttk.Entry(basic_frame, textvariable=self.backup_dir_var, width=40).grid(row=0, column=1, padx=5)
        ttk.Button(basic_frame, text=_t("common.browse", default="Browse"),
                  command=self.browse_backup_dir).grid(row=0, column=2)

        # Max backups
        ttk.Label(basic_frame, text=_t("backup.max_backups", default="Max Backups:")).grid(row=1, column=0, sticky="w", pady=2)
        self.max_backups_var = tk.StringVar(value=str(config["max_backups"]))
        ttk.Entry(basic_frame, textvariable=self.max_backups_var, width=10).grid(row=1, column=1, sticky="w", padx=5)

        # Auto backup
        self.auto_backup_var = tk.BooleanVar(value=config["auto_backup_enabled"])
        ttk.Checkbutton(basic_frame, text=_t("backup.enable_auto_backup", default="Enable Auto Backup"),
                       variable=self.auto_backup_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=5)

        # Security settings
        security_frame = ttk.LabelFrame(scrollable_frame, text=_t("backup.security_settings", default="Security Settings"), padding=10)
        security_frame.pack(fill="x", padx=10, pady=5)

        self.encryption_var = tk.BooleanVar(value=config["encryption_enabled"])
        ttk.Checkbutton(security_frame, text=_t("backup.enable_encryption", default="Enable Encryption"),
                       variable=self.encryption_var,
                       command=self.toggle_encryption).grid(row=0, column=0, sticky="w")

        ttk.Label(security_frame, text=_t("backup.encryption_password", default="Encryption Password:")).grid(row=1, column=0, sticky="w", pady=2)
        self.encryption_pass_var = tk.StringVar(value=config["encryption_password"])
        self.encryption_entry = ttk.Entry(security_frame, textvariable=self.encryption_pass_var,
                                        show="*", width=30)
        self.encryption_entry.grid(row=1, column=1, padx=5)

        self.secure_delete_var = tk.BooleanVar(value=config["secure_deletion"])
        ttk.Checkbutton(security_frame, text=_t("backup.secure_deletion", default="Secure Deletion"),
                       variable=self.secure_delete_var).grid(row=2, column=0, sticky="w")

        self.verify_integrity_var = tk.BooleanVar(value=config["verify_integrity"])
        ttk.Checkbutton(security_frame, text=_t("backup.verify_integrity", default="Verify Integrity"),
                       variable=self.verify_integrity_var).grid(row=2, column=1, sticky="w")

        # Compression settings
        compression_frame = ttk.LabelFrame(scrollable_frame, text=_t("backup.compression_settings", default="Compression Settings"), padding=10)
        compression_frame.pack(fill="x", padx=10, pady=5)

        self.compression_var = tk.BooleanVar(value=config["compression_enabled"])
        ttk.Checkbutton(compression_frame, text=_t("backup.enable_compression", default="Enable Compression"),
                       variable=self.compression_var).grid(row=0, column=0, sticky="w")

        ttk.Label(compression_frame, text=_t("backup.format", default="Format:")).grid(row=1, column=0, sticky="w", pady=2)
        self.compression_format_var = tk.StringVar(value=config["compression_format"])
        format_combo = ttk.Combobox(compression_frame, textvariable=self.compression_format_var,
                                   values=["gzip", "zip"], state="readonly", width=10)
        format_combo.grid(row=1, column=1, padx=5, sticky="w")

        ttk.Label(compression_frame, text=_t("backup.level", default="Level:")).grid(row=1, column=2, sticky="w", padx=(20,5))
        self.compression_level_var = tk.StringVar(value=str(config["compression_level"]))
        level_spin = ttk.Spinbox(compression_frame, textvariable=self.compression_level_var,
                               from_=1, to=9, width=5)
        level_spin.grid(row=1, column=3, padx=5, sticky="w")

        # Notifications
        notify_frame = ttk.LabelFrame(scrollable_frame, text=_t("backup.notifications", default="Notifications"), padding=10)
        notify_frame.pack(fill="x", padx=10, pady=5)

        self.email_notify_var = tk.BooleanVar(value=config["email_notifications"])
        ttk.Checkbutton(notify_frame, text=_t("backup.email_notifications", default="Email Notifications"),
                       variable=self.email_notify_var,
                       command=self.toggle_email_notifications).grid(row=0, column=0, sticky="w")

        ttk.Button(notify_frame, text=_t("backup.configure_email", default="Configure Email"),
                  command=self.configure_email_gui).grid(row=0, column=1, padx=10)
        ttk.Button(notify_frame, text=_t("backup.configure_webhooks", default="Configure Webhooks"),
                  command=self.configure_webhooks_gui).grid(row=0, column=2, padx=10)

        # Save button
        ttk.Button(scrollable_frame, text=_t("backup.save_configuration", default="Save Configuration"),
                  command=self.save_configuration).pack(pady=20)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_analysis_tab(self):
        """Create the analysis and comparison tab"""
        analysis_frame = ttk.Frame(self.notebook)
        self.notebook.add(analysis_frame, text=_t("backup.tab_analysis", default="Analysis"))

        # Comparison frame
        compare_frame = ttk.LabelFrame(analysis_frame, text=_t("backup.backup_comparison", default="Backup Comparison"), padding=10)
        compare_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(compare_frame, text=_t("backup.compare_backups", default="Compare Backups"),
                  command=self.compare_backups_gui).pack(side="left", padx=5)
        ttk.Button(compare_frame, text=_t("backup.generate_statistics", default="Generate Statistics"),
                  command=self.generate_statistics_gui).pack(side="left", padx=5)
        ttk.Button(compare_frame, text=_t("backup.backup_report", default="Backup Report"),
                  command=self.generate_report_gui).pack(side="left", padx=5)

        # Statistics display
        stats_frame = ttk.LabelFrame(analysis_frame, text=_t("backup.current_statistics", default="Current Statistics"), padding=10)
        stats_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.stats_text = scrolledtext.ScrolledText(stats_frame, height=15, wrap=tk.WORD)
        self.stats_text.pack(fill="both", expand=True)

        # Load initial statistics
        self.refresh_statistics()

    def create_cloud_tab(self):
        """Create the cloud and remote storage tab"""
        cloud_frame = ttk.Frame(self.notebook)
        self.notebook.add(cloud_frame, text=_t("backup.tab_cloud_remote", default="Cloud & Remote"))

        # Cloud storage frame
        cloud_storage_frame = ttk.LabelFrame(cloud_frame, text=_t("backup.cloud_storage", default="Cloud Storage"), padding=10)
        cloud_storage_frame.pack(fill="x", padx=10, pady=5)

        self.cloud_enabled_var = tk.BooleanVar(value=config["cloud_enabled"])
        ttk.Checkbutton(cloud_storage_frame, text=_t("backup.enable_cloud_storage", default="Enable Cloud Storage"),
                       variable=self.cloud_enabled_var,
                       command=self.toggle_cloud_storage).grid(row=0, column=0, sticky="w")

        # AWS S3 settings
        aws_frame = ttk.LabelFrame(cloud_storage_frame, text=_t("backup.aws_s3_settings", default="AWS S3 Settings"), padding=5)
        aws_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)

        ttk.Label(aws_frame, text=_t("backup.bucket", default="Bucket:")).grid(row=0, column=0, sticky="w")
        self.aws_bucket_var = tk.StringVar(value=config["aws_bucket"])
        ttk.Entry(aws_frame, textvariable=self.aws_bucket_var, width=20).grid(row=0, column=1, padx=5)

        ttk.Label(aws_frame, text=_t("backup.access_key", default="Access Key:")).grid(row=1, column=0, sticky="w")
        self.aws_access_var = tk.StringVar(value=config["aws_access_key"])
        ttk.Entry(aws_frame, textvariable=self.aws_access_var, width=20).grid(row=1, column=1, padx=5)

        ttk.Label(aws_frame, text=_t("backup.secret_key", default="Secret Key:")).grid(row=2, column=0, sticky="w")
        self.aws_secret_var = tk.StringVar(value=config["aws_secret_key"])
        ttk.Entry(aws_frame, textvariable=self.aws_secret_var, show="*", width=20).grid(row=2, column=1, padx=5)

        ttk.Label(aws_frame, text=_t("backup.region", default="Region:")).grid(row=3, column=0, sticky="w")
        self.aws_region_var = tk.StringVar(value=config["aws_region"])
        ttk.Entry(aws_frame, textvariable=self.aws_region_var, width=20).grid(row=3, column=1, padx=5)

        # Remote storage frame
        remote_frame = ttk.LabelFrame(cloud_frame, text=_t("backup.remote_storage", default="Remote Storage"), padding=10)
        remote_frame.pack(fill="x", padx=10, pady=5)

        self.remote_enabled_var = tk.BooleanVar(value=config["remote_enabled"])
        ttk.Checkbutton(remote_frame, text=_t("backup.enable_remote_storage", default="Enable Remote Storage"),
                       variable=self.remote_enabled_var).grid(row=0, column=0, sticky="w")

        ttk.Label(remote_frame, text=_t("backup.type", default="Type:")).grid(row=1, column=0, sticky="w")
        self.remote_type_var = tk.StringVar(value=config["remote_type"])
        type_combo = ttk.Combobox(remote_frame, textvariable=self.remote_type_var,
                                values=["ftp", "sftp"], state="readonly", width=10)
        type_combo.grid(row=1, column=1, padx=5, sticky="w")

        ttk.Label(remote_frame, text=_t("backup.host", default="Host:")).grid(row=2, column=0, sticky="w")
        self.remote_host_var = tk.StringVar(value=config["remote_host"])
        ttk.Entry(remote_frame, textvariable=self.remote_host_var, width=20).grid(row=2, column=1, padx=5)

        ttk.Label(remote_frame, text=_t("backup.username", default="Username:")).grid(row=3, column=0, sticky="w")
        self.remote_user_var = tk.StringVar(value=config["remote_username"])
        ttk.Entry(remote_frame, textvariable=self.remote_user_var, width=20).grid(row=3, column=1, padx=5)

        ttk.Label(remote_frame, text=_t("backup.password", default="Password:")).grid(row=4, column=0, sticky="w")
        self.remote_pass_var = tk.StringVar(value=config["remote_password"])
        ttk.Entry(remote_frame, textvariable=self.remote_pass_var, show="*", width=20).grid(row=4, column=1, padx=5)

        # Cloud operations
        operations_frame = ttk.LabelFrame(cloud_frame, text=_t("backup.cloud_operations", default="Cloud Operations"), padding=10)
        operations_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(operations_frame, text=_t("backup.upload_backup", default="Upload Backup"),
                  command=self.upload_backup_gui).pack(side="left", padx=5)
        ttk.Button(operations_frame, text=_t("backup.download_backup", default="Download Backup"),
                  command=self.download_backup_gui).pack(side="left", padx=5)
        ttk.Button(operations_frame, text=_t("backup.sync_storage", default="Sync Storage"),
                  command=self.sync_storage_gui).pack(side="left", padx=5)
