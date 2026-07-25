"""Main BackupGUI class for the enhanced backup system."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import os
import re
import json
import queue
import datetime
import threading
import logging
import shutil
from pathlib import Path
import posixpath

from education_system.systems.university.interfaces.gui.shell.database.shared_imports import (
    DEFAULT_DB_PATH, logger, _t,
)
from education_system.systems.university.interfaces.gui.shell.database.config import (
    config, save_config, load_config, GUI_CONFIG,
    _backup_context_lock, _last_incremental_context, _last_differential_context,
)
from education_system.systems.university.interfaces.gui.shell.database.metadata import metadata_manager
from education_system.systems.university.interfaces.gui.shell.database.scheduling.scheduler import (
    start_scheduler, stop_scheduler, get_connection,
)
from education_system.systems.university.interfaces.gui.shell.database.scheduling.cron import parse_cron_schedule
import education_system.systems.university.interfaces.gui.shell.database.config as cfg

# Late imports for operations to avoid circular dependencies
from education_system.systems.university.interfaces.gui.shell.database.operations.backup_ops import create_enhanced_backup, create_selective_backup, create_schema_only_backup, create_incremental_backup, create_differential_backup, calculate_file_hash, compress_file, encrypt_file, upload_to_aws_s3, upload_to_ftp, upload_to_sftp, cleanup_old_backups, notify_backup_result, get_database_tables, get_database_tables_from_connection, has_database_changed, ensure_backup_directory, list_available_backups, validate_backup, deduplicate_backups, send_email_notification
from education_system.systems.university.interfaces.gui.shell.database.operations.stats_ops import (
    generate_backup_statistics, get_log_file,
)
from education_system.systems.university.interfaces.gui.shell.database.operations.template_ops import (
    list_backup_templates, save_backup_template, load_backup_template,
)

# Import dialogs
from education_system.systems.university.interfaces.gui.shell.database.dialogs.integrity_check import (
    IntegrityCheckDialog, AdvancedSettingsDialog,
)
from education_system.systems.university.interfaces.gui.shell.database.dialogs.backup_options import (
    BackupOptionsDialog, BackupViewerDialog,
)
from education_system.systems.university.interfaces.gui.shell.database.dialogs.restore import (
    RestoreDialog, TableSelectionDialog,
)
from education_system.systems.university.interfaces.gui.shell.database.dialogs.validation import ValidationDialog
from education_system.systems.university.interfaces.gui.shell.database.dialogs.report import ReportDialog
from education_system.systems.university.interfaces.gui.shell.database.dialogs.notifications import (
    EmailConfigDialog, WebhookConfigDialog,
)
from education_system.systems.university.interfaces.gui.shell.database.dialogs.cloud import (
    UploadDialog, DownloadDialog,
)
from education_system.systems.university.interfaces.gui.shell.database.dialogs.export import ExportDialog
from education_system.systems.university.interfaces.gui.shell.database.dialogs.templates import (
    TemplateSelectionDialog, TemplateManagerDialog,
)
from education_system.systems.university.interfaces.gui.shell.database.dialogs.schedule import (
    ScheduleConfigDialog, ScheduleHistoryDialog,
)
from education_system.systems.university.interfaces.gui.shell.database.dialogs.storage import StorageUsageDialog
from education_system.systems.university.interfaces.gui.shell.database.dialogs.comparison import ComparisonDialog


class BackupGUI:
    """Main GUI class for the enhanced backup system"""

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
        self.status_var = tk.StringVar(value="Ready")
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

    def create_logs_tab(self):
        """Create the logs and monitoring tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text=_t("backup.tab_logs", default="Logs"))

        # Log controls
        controls_frame = ttk.Frame(logs_frame)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text=_t("backup.refresh_logs", default="Refresh Logs"),
                  command=self.refresh_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text=_t("backup.clear_logs", default="Clear Logs"),
                  command=self.clear_logs).pack(side="left", padx=5)
        ttk.Button(controls_frame, text=_t("backup.export_logs", default="Export Logs"),
                  command=self.export_logs).pack(side="left", padx=5)

        # Log level filter
        ttk.Label(controls_frame, text=_t("backup.filter", default="Filter:")).pack(side="left", padx=(20, 5))
        self.log_level_var = tk.StringVar(value="All")
        level_combo = ttk.Combobox(controls_frame, textvariable=self.log_level_var,
                                 values=["All", "ERROR", "WARNING", "INFO", "DEBUG"],
                                 state="readonly", width=10)
        level_combo.pack(side="left", padx=5)
        level_combo.bind("<<ComboboxSelected>>", self.filter_logs)

        # Log display
        self.log_text = scrolledtext.ScrolledText(logs_frame, height=25, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

        # Load initial logs
        self.refresh_logs()

    def create_status_bar(self):
        """Create the status bar"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom")

        # Status label
        status_label = ttk.Label(status_frame, textvariable=self.status_var, relief="sunken")
        status_label.pack(side="left", fill="x", expand=True)

        # Progress bar
        self.progress_bar = ttk.Progressbar(status_frame, variable=self.progress_var,
                                          length=200, mode="determinate")
        self.progress_bar.pack(side="right", padx=5, pady=2)

    def setup_logging(self):
        """
        Setup logging to capture log messages in GUI

        Configures a queue handler to capture log messages from the backup
        operations and display them in the GUI's log text widget.
        This allows real-time monitoring of backup activities in the interface.
        """
        try:
            # Create a custom handler that writes to the log queue
            class QueueHandler(logging.Handler):
                def __init__(self, log_queue):
                    super().__init__()
                    self.log_queue = log_queue

                def emit(self, record):
                    try:
                        # Format the log record
                        msg = self.format(record)
                        self.log_queue.put(msg)
                    except Exception:
                        pass  # Ignore errors in logging

            # Create and configure the queue handler
            queue_handler = QueueHandler(self.log_queue)
            queue_handler.setLevel(logging.DEBUG)

            # Set formatter
            formatter = logging.Formatter(
                '[%(asctime)s] %(levelname)-8s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            queue_handler.setFormatter(formatter)

            # Add handler to logger
            logger.addHandler(queue_handler)

            # Start monitoring the log queue
            self.monitor_logs()

        except Exception as e:
            print(f"Warning: Could not setup GUI logging: {e}")

    def monitor_logs(self):
        """Monitor log queue for new messages"""
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        try:
            while True:
                record = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, f"{record}\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        except tk.TclError:
            # Widget torn down between get_nowait() and insert(); stop.
            return

        # Schedule next check
        try:
            self.root.after(1000, self.monitor_logs)
        except tk.TclError:
            return

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.systems.university.interfaces.gui.shell.gui_launcher import return_to_main_menu
            return_to_main_menu(self, self.auth)
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    # Main operations methods
    def create_manual_backup(self):
        """Create a manual backup with options"""
        dialog = BackupOptionsDialog(self.root)
        if dialog.result:
            self.run_backup_operation(
                lambda: create_enhanced_backup(
                    manual=True,
                    backup_type=dialog.backup_type,
                    tables=dialog.selected_tables
                ),
                "Creating manual backup..."
            )

    def quick_backup(self):
        """Create a quick full backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True),
            "Creating quick backup..."
        )

    def view_backups(self):
        """Open backup viewer dialog"""
        BackupViewerDialog(self.root)

    def restore_backup(self):
        """Open restore dialog"""
        RestoreDialog(self.root, self.refresh_backup_list)

    def validate_backup_gui(self):
        """Open backup validation dialog"""
        ValidationDialog(self.root)

    def export_backup_gui(self):
        """Open backup export dialog"""
        ExportDialog(self.root)

    # Advanced operations methods
    def create_incremental_backup(self):
        """Create incremental backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="incremental"),
            "Creating incremental backup..."
        )

    def create_selective_backup(self):
        """Create selective table backup"""
        tables = get_database_tables()
        dialog = TableSelectionDialog(self.root, tables)
        if dialog.selected_tables:
            self.run_backup_operation(
                lambda: create_enhanced_backup(
                    manual=True,
                    backup_type="selective",
                    tables=dialog.selected_tables
                ),
                "Creating selective backup..."
            )

    def create_schema_backup(self):
        """Create schema-only backup"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="schema"),
            "Creating schema backup..."
        )

    def save_template_gui(self):
        """Save current configuration as template"""
        name = tk.simpledialog.askstring("Save Template", "Enter template name:")
        if name:
            # Get current configuration
            self.save_configuration()  # Save current GUI settings to config
            template_config = {k: v for k, v in config.items() if k != "backup_templates"}

            if save_backup_template(name, template_config):
                messagebox.showinfo("Success", f"Template '{name}' saved successfully!")
            else:
                messagebox.showerror("Error", "Failed to save template")

    def load_template_gui(self):
        """Load configuration from template"""
        # Use new list_backup_templates function to get all templates
        templates = list_backup_templates()
        if not templates:
            messagebox.showinfo("No Templates", "No templates available")
            return

        dialog = TemplateSelectionDialog(self.root, list(templates.keys()), templates)
        if dialog.selected_template:
            if load_backup_template(dialog.selected_template):
                self.refresh_config_gui()
                messagebox.showinfo("Success", f"Template '{dialog.selected_template}' loaded!")
            else:
                messagebox.showerror("Error", "Failed to load template")

    def manage_templates_gui(self):
        """Open template management dialog"""
        TemplateManagerDialog(self.root)

    def toggle_scheduling(self):
        """Toggle backup scheduling"""
        config["auto_backup_enabled"] = not config["auto_backup_enabled"]

        if config["auto_backup_enabled"]:
            start_scheduler()
            self.schedule_btn.config(text="Disable Scheduling")
        else:
            stop_scheduler()
            self.schedule_btn.config(text="Enable Scheduling")

        self.update_schedule_status()
        save_config()

    def configure_schedule_gui(self):
        """Open schedule configuration dialog"""
        ScheduleConfigDialog(self.root, self.update_schedule_status)

    # Configuration methods
    def browse_backup_dir(self):
        """Browse for backup directory"""
        directory = filedialog.askdirectory(initialdir=self.backup_dir_var.get())
        if directory:
            self.backup_dir_var.set(directory)

    def toggle_encryption(self):
        """Toggle encryption settings"""
        if self.encryption_var.get() and not self.encryption_pass_var.get():
            password = tk.simpledialog.askstring("Encryption Password",
                                                "Enter encryption password:", show="*")
            if password:
                self.encryption_pass_var.set(password)
            else:
                self.encryption_var.set(False)

    def toggle_email_notifications(self):
        """Toggle email notifications"""
        if self.email_notify_var.get():
            self.configure_email_gui()

    def configure_email_gui(self):
        """Configure email settings"""
        EmailConfigDialog(self.root)

    def configure_webhooks_gui(self):
        """Configure webhook settings"""
        WebhookConfigDialog(self.root)

    def toggle_cloud_storage(self):
        """
        Toggle cloud storage

        Enables or disables cloud storage settings based on the cloud storage toggle.
        When enabled, activates AWS S3 configuration fields. When disabled, disables
        them to prevent accidental misconfiguration.
        """
        if self.cloud_enabled_var.get():
            # Enable AWS settings
            try:
                # Enable all AWS-related entry widgets
                if hasattr(self, 'aws_bucket_entry'):
                    self.aws_bucket_entry.config(state='normal')
                if hasattr(self, 'aws_access_entry'):
                    self.aws_access_entry.config(state='normal')
                if hasattr(self, 'aws_secret_entry'):
                    self.aws_secret_entry.config(state='normal')
                if hasattr(self, 'aws_region_combo'):
                    self.aws_region_combo.config(state='readonly')

                # Update status
                self.status_var.set("Cloud storage enabled - configure AWS S3 settings")

            except AttributeError:
                # Widgets not yet created, that's ok
                pass
        else:
            # Disable AWS settings
            try:
                # Disable all AWS-related entry widgets
                if hasattr(self, 'aws_bucket_entry'):
                    self.aws_bucket_entry.config(state='disabled')
                if hasattr(self, 'aws_access_entry'):
                    self.aws_access_entry.config(state='disabled')
                if hasattr(self, 'aws_secret_entry'):
                    self.aws_secret_entry.config(state='disabled')
                if hasattr(self, 'aws_region_combo'):
                    self.aws_region_combo.config(state='disabled')

                # Update status
                self.status_var.set("Cloud storage disabled - backups will be stored locally only")

            except AttributeError:
                # Widgets not yet created, that's ok
                pass

    def save_configuration(self):
        """Save all configuration settings"""
        try:
            # Update config from GUI
            config["backup_directory"] = self.backup_dir_var.get()
            config["max_backups"] = int(self.max_backups_var.get())
            config["auto_backup_enabled"] = self.auto_backup_var.get()
            config["encryption_enabled"] = self.encryption_var.get()
            config["encryption_password"] = self.encryption_pass_var.get()
            config["secure_deletion"] = self.secure_delete_var.get()
            config["verify_integrity"] = self.verify_integrity_var.get()
            config["compression_enabled"] = self.compression_var.get()
            config["compression_format"] = self.compression_format_var.get()
            config["compression_level"] = int(self.compression_level_var.get())
            config["email_notifications"] = self.email_notify_var.get()
            config["cloud_enabled"] = self.cloud_enabled_var.get()
            config["aws_bucket"] = self.aws_bucket_var.get()
            config["aws_access_key"] = self.aws_access_var.get()
            config["aws_secret_key"] = self.aws_secret_var.get()
            config["aws_region"] = self.aws_region_var.get()
            config["remote_enabled"] = self.remote_enabled_var.get()
            config["remote_type"] = self.remote_type_var.get()
            config["remote_host"] = self.remote_host_var.get()
            config["remote_username"] = self.remote_user_var.get()
            config["remote_password"] = self.remote_pass_var.get()

            save_config()

            # Restart scheduler if needed
            if config["auto_backup_enabled"]:
                stop_scheduler()
                start_scheduler()

            messagebox.showinfo("Success", "Configuration saved successfully!")

        except ValueError as e:
            messagebox.showerror("Error", f"Invalid configuration value: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")

    def refresh_config_gui(self):
        """Refresh GUI with current configuration"""
        self.backup_dir_var.set(config["backup_directory"])
        self.max_backups_var.set(str(config["max_backups"]))
        self.auto_backup_var.set(config["auto_backup_enabled"])
        self.encryption_var.set(config["encryption_enabled"])
        self.encryption_pass_var.set(config["encryption_password"])
        self.secure_delete_var.set(config["secure_deletion"])
        self.verify_integrity_var.set(config["verify_integrity"])
        self.compression_var.set(config["compression_enabled"])
        self.compression_format_var.set(config["compression_format"])
        self.compression_level_var.set(str(config["compression_level"]))
        self.email_notify_var.set(config["email_notifications"])
        self.cloud_enabled_var.set(config["cloud_enabled"])
        self.aws_bucket_var.set(config["aws_bucket"])
        self.aws_access_var.set(config["aws_access_key"])
        self.aws_secret_var.set(config["aws_secret_key"])
        self.aws_region_var.set(config["aws_region"])
        self.remote_enabled_var.set(config["remote_enabled"])
        self.remote_type_var.set(config["remote_type"])
        self.remote_host_var.set(config["remote_host"])
        self.remote_user_var.set(config["remote_username"])
        self.remote_pass_var.set(config["remote_password"])

    # Analysis methods
    def compare_backups_gui(self):
        """Open backup comparison dialog"""
        ComparisonDialog(self.root)

    def generate_statistics_gui(self):
        """Generate and display statistics"""
        self.refresh_statistics()

    def generate_report_gui(self):
        """Generate comprehensive backup report"""
        ReportDialog(self.root)

    def refresh_statistics(self):
        """Refresh statistics display"""
        try:
            stats = generate_backup_statistics()

            stats_text = "BACKUP STATISTICS REPORT\n"
            stats_text += "=" * 40 + "\n\n"
            stats_text += f"Total Backups: {stats['total_backups']}\n"
            stats_text += f"Total Size: {stats['total_size'] / (1024*1024*1024):.2f} GB\n"
            stats_text += f"Average Size: {stats['average_size'] / (1024*1024):.2f} MB\n"
            stats_text += f"Recent Activity (30 days): {stats['recent_activity']} backups\n\n"

            if stats['backup_types']:
                stats_text += "Backup Types:\n"
                for backup_type, count in stats['backup_types'].items():
                    stats_text += f"  {backup_type}: {count}\n"
                stats_text += "\n"

            if stats['storage_usage']:
                stats_text += "Monthly Storage Usage:\n"
                for month, size in sorted(stats['storage_usage'].items()):
                    stats_text += f"  {month}: {size / (1024*1024):.2f} MB\n"

            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, stats_text)

        except Exception as e:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(1.0, f"Error generating statistics: {e}")

    # Cloud operations
    def upload_backup_gui(self):
        """Upload backup to cloud"""
        if not config["cloud_enabled"]:
            messagebox.showwarning("Cloud Storage", "Cloud storage is not configured")
            return

        UploadDialog(self.root)

    def download_backup_gui(self):
        """Download backup from cloud"""
        if not config["cloud_enabled"]:
            messagebox.showwarning("Cloud Storage", "Cloud storage is not configured")
            return

        DownloadDialog(self.root)

    def sync_storage_gui(self):
        """Sync with remote storage"""
        if not config["remote_enabled"]:
            messagebox.showwarning("Remote Storage", "Remote storage is not configured")
            return

        host = self.remote_host_var.get().strip()
        username = self.remote_user_var.get().strip()
        password = self.remote_pass_var.get().strip()
        remote_type = self.remote_type_var.get()
        remote_path = config.get("remote_path", "/backups")

        if not host or not username or not password:
            messagebox.showwarning("Remote Storage", "Please provide host, username, and password for remote storage.")
            return

        backups = list_available_backups()
        if not backups:
            messagebox.showinfo("Remote Storage", "No backups available to sync.")
            return

        to_sync = [b for b in backups if not b.get("remote_uploaded", False)]
        if not to_sync:
            messagebox.showinfo("Remote Storage", "All backups are already synced with the remote location.")
            return

        # Persist the latest credentials in config
        config["remote_host"] = host
        config["remote_username"] = username
        config["remote_password"] = password

        def update_status(progress, status_text):
            self.progress_var.set(progress)
            self.status_var.set(status_text)

        def finish_sync(successes, failures):
            self.progress_var.set(0)
            self.status_var.set("Remote sync complete")

            if successes:
                message = f"Synchronized {len(successes)} backup(s) successfully."
            else:
                message = "No backups were synchronized."

            if failures:
                message += "\n\nFailed uploads:\n" + "\n".join(
                    f"- {item['filename']}: {reason}" for item, reason in failures
                )

            messagebox.showinfo("Remote Sync", message)
            self.refresh_backup_list()

        def sync_worker():
            successes = []
            failures = []
            total = len(to_sync)

            for index, backup in enumerate(to_sync, start=1):
                progress = (index - 1) / total * 100
                self.root.after(0, update_status, progress, f"Uploading {backup['filename']} ({index}/{total})")

                remote_target = posixpath.join(remote_path.rstrip('/'), backup['filename'])

                try:
                    if remote_type == "ftp":
                        result = upload_to_ftp(
                            backup["path"], host, username, password, remote_target
                        )
                    else:
                        result = upload_to_sftp(
                            backup["path"], host, username, password, remote_target
                        )
                except Exception as exc:
                    result = False
                    failures.append((backup, str(exc)))
                else:
                    if result:
                        successes.append(backup)
                        for record in metadata_manager.metadata["backups"]:
                            if record["path"] == backup["path"]:
                                record["remote_uploaded"] = True
                                break
                    else:
                        failures.append((backup, "Upload failed"))

                self.root.after(0, update_status, index / total * 100, f"Processed {index}/{total} backups")

            metadata_manager.save_metadata()
            self.root.after(0, finish_sync, successes, failures)

        threading.Thread(target=sync_worker, daemon=True).start()

    # Log operations
    def refresh_logs(self):
        """Refresh log display"""
        try:
            log_file = get_log_file('backup.log')
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = f.read()

                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, logs)
                self.log_text.see(tk.END)
            else:
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, "No log file found")
        except Exception as e:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, f"Error loading logs: {e}")

    def clear_logs(self):
        """Clear log display and file"""
        if messagebox.askyesno("Clear Logs", "Are you sure you want to clear all logs?"):
            try:
                log_file = get_log_file('backup.log')
                if os.path.exists(log_file):
                    open(log_file, 'w').close()
                self.log_text.delete(1.0, tk.END)
                messagebox.showinfo("Success", "Logs cleared successfully")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear logs: {e}")

    def create_differential_backup(self):
        """Create differential backup - missing method"""
        self.run_backup_operation(
            lambda: create_enhanced_backup(manual=True, backup_type="differential"),
            "Creating differential backup..."
        )

    def refresh_backup_list(self):
        """Refresh the backup list in main tab"""
        try:
            # Clear existing items
            for item in self.backup_tree.get_children():
                self.backup_tree.delete(item)

            # Get backup list
            backups = list_available_backups()

            # Populate tree
            for backup in backups[:20]:  # Show last 20 backups
                status = "\u2713" if os.path.exists(backup['path']) else "\u2717"
                encrypted = "\U0001f512" if backup.get('encrypted', False) else ""
                cloud = "\u2601" if backup.get('cloud_uploaded', False) else ""

                self.backup_tree.insert("", "end", values=(
                    backup['id'],
                    backup.get('backup_type', 'full'),
                    backup['date_formatted'],
                    backup['size_formatted'],
                    f"{status} {encrypted} {cloud}"
                ))

        except Exception as e:
            logger.error(f"Error refreshing backup list: {e}")

    def auto_refresh_backup_list(self):
        """Auto-refresh backup list every 30 seconds"""
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        self.refresh_backup_list()
        self.root.after(30000, self.auto_refresh_backup_list)

    def configure_advanced_settings(self):
        """Configure advanced backup settings - missing method"""
        AdvancedSettingsDialog(self.root)

    def backup_database_specific_settings(self):
        """Configure database-specific backup settings - missing method"""
        DatabaseSettingsDialog(self.root)

    def create_backup_report(self):
        """Create comprehensive backup report - missing method"""
        ReportGeneratorDialog(self.root)

    def backup_integrity_check(self):
        """Run integrity check on all backups - missing method"""
        IntegrityCheckDialog(self.root)

    def backup_migration_tools(self):
        """Tools for migrating backups between storage types - missing method"""
        MigrationToolsDialog(self.root)

    def create_enhanced_backup(manual=False, operation_name=None, backup_type="full", tables=None):
        """Enhanced backup creation with all new features - missing from GUI"""
        try:
            # Check if database has changed (if change detection is enabled)
            if config.get("enable_change_detection", False) and not manual and not has_database_changed():
                logger.info("No changes detected since last backup. Skipping backup.")
                return None

            # Ensure backup directory exists
            backup_dir = ensure_backup_directory()

            # Generate backup filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            if operation_name:
                filename = f"student_records_before_{operation_name}_{timestamp}.db"
            elif manual:
                filename = f"student_records_manual_{backup_type}_{timestamp}.db"
            else:
                filename = f"student_records_scheduled_{backup_type}_{timestamp}.db"

            backup_path = backup_dir / filename

            # Check if source database exists (use DEFAULT_DB_PATH from db module)
            db_path = DEFAULT_DB_PATH
            if not os.path.exists(str(db_path)):
                logger.warning(f"Database file not found at {db_path}. Nothing to backup.")
                messagebox.showerror("Backup Error", f"Database file not found at:\n{db_path}\n\nPlease ensure the database exists before creating a backup.")
                return None

            logger.info(f"Creating backup from database: {db_path}")

            # Create backup based on type
            success = False
            if backup_type == "schema":
                success = create_schema_only_backup(str(backup_path))
            elif backup_type == "selective" and tables:
                success = create_selective_backup(tables, str(backup_path))
            elif backup_type == "incremental":
                success = create_incremental_backup(str(backup_path))
            elif backup_type == "differential":
                success = create_differential_backup(str(backup_path))
            else:  # full backup
                shutil.copy2(str(DEFAULT_DB_PATH), backup_path)
                success = True

            if not success:
                logger.error("Backup creation failed")
                return None

            # Calculate file hash for integrity
            file_hash = calculate_file_hash(str(backup_path))

            # Compress if enabled
            if config.get("compression_enabled", False):
                compressed_path = compress_file(
                    str(backup_path),
                    config.get("compression_format", "gzip"),
                    config.get("compression_level", 6)
                )
                if compressed_path:
                    backup_path = Path(compressed_path)

            # Encrypt if enabled
            if config.get("encryption_enabled", False) and config.get("encryption_password"):
                encrypted_path = encrypt_file(str(backup_path), config["encryption_password"])
                if encrypted_path:
                    backup_path = Path(encrypted_path)

            # Upload to cloud/remote if enabled
            upload_success = True
            if config.get("cloud_enabled", False):
                if config.get("cloud_provider") == "aws":
                    upload_success = upload_to_aws_s3(
                        str(backup_path),
                        config.get("aws_bucket", ""),
                        f"backups/{backup_path.name}"
                    )

            if config.get("remote_enabled", False):
                if config.get("remote_type") == "ftp":
                    upload_success = upload_to_ftp(
                        str(backup_path),
                        config.get("remote_host", ""),
                        config.get("remote_username", ""),
                        config.get("remote_password", ""),
                        config.get("remote_path", "/backups")
                    )
                elif config.get("remote_type") == "sftp":
                    upload_success = upload_to_sftp(
                        str(backup_path),
                        config.get("remote_host", ""),
                        config.get("remote_username", ""),
                        config.get("remote_password", ""),
                        config.get("remote_path", "/backups")
                    )

            # Record backup metadata
            backup_info = {
                "path": str(backup_path),
                "filename": backup_path.name,
                "type": backup_type,
                "manual": manual,
                "operation": operation_name,
                "timestamp": timestamp,
                "size": os.path.getsize(backup_path),
                "file_hash": file_hash,
                "compressed": config.get("compression_enabled", False),
                "encrypted": config.get("encryption_enabled", False),
                "cloud_uploaded": config.get("cloud_enabled", False) and upload_success,
                "remote_uploaded": config.get("remote_enabled", False) and upload_success,
                "backup_type": backup_type
            }

            # Thread-safe read of backup context
            with cfg._backup_context_lock:
                if backup_type == "incremental" and cfg._last_incremental_context:
                    backup_info.update(cfg._last_incremental_context.copy())
                if backup_type == "differential" and cfg._last_differential_context:
                    backup_info.update(cfg._last_differential_context.copy())

            metadata_manager.add_backup(backup_info)

            logger.info(f"Backup created: {backup_path}")

            # Clean up old backups
            cleanup_old_backups()

            # Send notifications
            notify_backup_result(True, str(backup_path), f"{backup_type} backup")

            return str(backup_path)

        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            notify_backup_result(False, "", f"{backup_type} backup")
            return None

    def import_template_gui(self):
        """Import template from file - missing method"""
        file_path = filedialog.askopenfilename(
            title="Import Template",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'r') as f:
                    template_data = json.load(f)

                name = tk.simpledialog.askstring("Template Name", "Enter name for imported template:")
                if name and save_backup_template(name, template_data):
                    messagebox.showinfo("Success", f"Template '{name}' imported successfully!")
                else:
                    messagebox.showerror("Error", "Failed to import template")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import template: {e}")

    def export_template_gui(self):
        """Export template to file - missing method"""
        templates = config.get("backup_templates", {})
        if not templates:
            messagebox.showinfo("No Templates", "No templates available to export")
            return

        dialog = TemplateSelectionDialog(self.root, list(templates.keys()))
        if dialog.selected_template:
            file_path = filedialog.asksaveasfilename(
                title="Export Template",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )

            if file_path:
                try:
                    template_data = templates[dialog.selected_template]
                    with open(file_path, 'w') as f:
                        json.dump(template_data, f, indent=4)
                    messagebox.showinfo("Success", f"Template exported to {file_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export template: {e}")

    def show_schedule_history(self):
        """Show scheduling history - missing method"""
        ScheduleHistoryDialog(self.root)

    def test_schedule(self):
        """Test schedule configuration - missing method"""
        if not config["auto_backup_enabled"]:
            messagebox.showwarning("Schedule Disabled", "Automatic backup scheduling is currently disabled.")
            return

        # Calculate next scheduled run
        try:
            current_time = datetime.datetime.now()
            scheduled_time = datetime.datetime.strptime(config["scheduled_backup_time"], "%H:%M").time()

            today_scheduled = datetime.datetime.combine(current_time.date(), scheduled_time)
            if today_scheduled <= current_time:
                # If today's time has passed, show tomorrow's schedule
                tomorrow = current_time.date() + datetime.timedelta(days=1)
                next_run = datetime.datetime.combine(tomorrow, scheduled_time)
            else:
                next_run = today_scheduled

            frequency = config["backup_frequency"]
            message = "Schedule Configuration Test:\n\n"
            message += f"Frequency: {frequency.title()}\n"
            message += f"Time: {config['scheduled_backup_time']}\n"
            message += f"Next Run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"Status: {'Active' if cfg.scheduler_running else 'Inactive'}\n"

            messagebox.showinfo("Schedule Test", message)
        except Exception as e:
            messagebox.showerror("Error", f"Schedule test failed: {e}")

    def enable_backup_deduplication():
        """Enable backup deduplication - missing from GUI"""
        try:
            logger.info("Enabling backup deduplication")
            config["enable_deduplication"] = True
            save_config()

            removed = deduplicate_backups()
            if removed:
                logger.info(f"Deduplication removed {removed} duplicate backup(s).")
            else:
                logger.info("No duplicate backups detected during deduplication.")
            return True
        except Exception as e:
            logger.error(f"Error enabling deduplication: {e}")
            return False

    def deduplicate_backups():
        """Remove duplicate backup files - missing from GUI"""
        try:
            if not config.get("enable_deduplication", False):
                return 0

            backups = list_available_backups()
            duplicates_removed = 0

            # Group backups by hash
            hash_groups = {}
            for backup in backups:
                file_hash = backup.get("file_hash")
                if file_hash:
                    if file_hash not in hash_groups:
                        hash_groups[file_hash] = []
                    hash_groups[file_hash].append(backup)

            # Remove duplicates (keep the newest)
            for file_hash, backup_group in hash_groups.items():
                if len(backup_group) > 1:
                    # Sort by timestamp, keep the newest
                    backup_group.sort(key=lambda x: x["timestamp"], reverse=True)
                    for duplicate in backup_group[1:]:  # Skip the first (newest)
                        try:
                            # Use centralized delete_backup function
                            try:
                                from education_system.systems.university.infrastructure.database.data_backup import delete_backup as delete_backup_func
                                if delete_backup_func(duplicate["path"]):
                                    duplicates_removed += 1
                                    logger.info(f"Removed duplicate backup: {duplicate['filename']}")
                            except ImportError:
                                # Fallback implementation
                                if os.path.exists(duplicate["path"]):
                                    os.remove(duplicate["path"])
                                    duplicates_removed += 1
                                    logger.info(f"Removed duplicate backup: {duplicate['filename']}")

                                # Remove from metadata
                                metadata_manager.metadata["backups"] = [
                                    b for b in metadata_manager.metadata["backups"]
                                    if b["path"] != duplicate["path"]
                                ]
                                metadata_manager.save_metadata()
                        except Exception as e:
                            logger.error(f"Error removing duplicate {duplicate['filename']}: {e}")

            return duplicates_removed

        except Exception as e:
            logger.error(f"Error during deduplication: {e}")
            return 0

    def check_storage_quota():
        """Check if storage quota is exceeded - missing from GUI"""
        try:
            quota_gb = config.get("storage_quota_gb", 10)
            quota_bytes = quota_gb * 1024 * 1024 * 1024

            # Calculate total backup size
            total_size = 0
            backup_dir = Path(config["backup_directory"])

            if backup_dir.exists():
                for file_path in backup_dir.glob("*"):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size

            usage_percentage = (total_size / quota_bytes) * 100 if quota_bytes > 0 else 0

            return {
                "total_size_bytes": total_size,
                "total_size_gb": total_size / (1024**3),
                "quota_gb": quota_gb,
                "quota_bytes": quota_bytes,
                "usage_percentage": usage_percentage,
                "quota_exceeded": total_size > quota_bytes
            }

        except Exception as e:
            logger.error(f"Error checking storage quota: {e}")
            return {"quota_exceeded": False, "usage_percentage": 0}

    def show_storage_usage(self):
        """Show storage usage dialog - missing method"""
        StorageUsageDialog(self.root)

    def export_logs(self):
        """Export logs to file"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                content = self.log_text.get(1.0, tk.END)
                with open(filename, 'w') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Logs exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export logs: {e}")

    def filter_logs(self, event=None):
        """Filter logs by level"""
        try:
            log_file = get_log_file('backup.log')
            if not os.path.exists(log_file):
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, "No log file found")
                return

            with open(log_file, 'r') as f:
                lines = f.readlines()

            selected_level = self.log_level_var.get()
            if selected_level == "All":
                filtered_lines = lines
            else:
                pattern = re.compile(rf'\\b{selected_level}\\b', re.IGNORECASE)
                filtered_lines = [line for line in lines if pattern.search(line)]

            self.log_text.delete(1.0, tk.END)
            if filtered_lines:
                self.log_text.insert(1.0, "".join(filtered_lines))
            else:
                self.log_text.insert(1.0, f"No log entries found for level {selected_level}.")
        except Exception as e:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, f"Error filtering logs: {e}")

    def list_available_backups(filter_type=None, search_term=None):
        """List all available backup files with enhanced filtering - missing from GUI"""
        try:
            backups = metadata_manager.get_backups()

            # Apply filters
            if filter_type:
                backups = [b for b in backups if b.get("backup_type") == filter_type]

            if search_term:
                backups = [b for b in backups if search_term.lower() in b["filename"].lower()]

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x["timestamp"], reverse=True)

            # Add calculated fields
            for i, backup in enumerate(backups):
                backup["id"] = i + 1

                # Format size
                size_bytes = backup.get("size", 0)
                if size_bytes > 1024*1024*1024:
                    backup["size_formatted"] = f"{size_bytes/(1024*1024*1024):.2f} GB"
                elif size_bytes > 1024*1024:
                    backup["size_formatted"] = f"{size_bytes/(1024*1024):.2f} MB"
                else:
                    backup["size_formatted"] = f"{size_bytes/1024:.2f} KB"

                # Format date
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    backup["date_formatted"] = backup_date.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, KeyError):
                    backup["date_formatted"] = "Unknown"

            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    # Utility methods
    def run_backup_operation(self, operation, status_message):
        """Run backup operation in separate thread"""
        def run_operation():
            try:
                self.status_var.set(status_message)
                self.progress_var.set(0)

                result = operation()

                if result:
                    self.status_var.set("Backup completed successfully")
                    self.refresh_backup_list()
                    messagebox.showinfo("Success", f"Backup created: {os.path.basename(result)}")
                else:
                    self.status_var.set("Backup failed")
                    messagebox.showerror("Error", "Backup operation failed")

            except Exception as e:
                self.status_var.set("Backup failed")
                messagebox.showerror("Error", f"Backup operation failed: {e}")
            finally:
                self.progress_var.set(0)

        # Run in separate thread to prevent GUI freezing
        thread = threading.Thread(target=run_operation)
        thread.daemon = True
        thread.start()


class ReportGeneratorDialog:
    """Dialog that generates a comprehensive backup & database report.

    Summarises the live database (path, size, journal mode, table count) and
    the contents of the configured backup directory (each backup file's size
    and modification time, plus totals). The report can be saved to a text
    file. All values are read live; nothing is fabricated.
    """

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup & Database Report")
        self.dialog.geometry("600x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.generate_report()

    def create_widgets(self):
        """Create dialog widgets."""
        report_frame = ttk.LabelFrame(self.dialog, text="Report", padding=10)
        report_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.output = scrolledtext.ScrolledText(report_frame, wrap="word", height=18)
        self.output.pack(fill="both", expand=True)

        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(button_frame, text="Refresh",
                   command=self.generate_report).pack(side="left")
        ttk.Button(button_frame, text="Save to File...",
                   command=self.save_report).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Close",
                   command=self.dialog.destroy).pack(side="right")

    def _write(self, line=""):
        self.output.insert("end", line + "\n")

    def generate_report(self):
        """Build the report from live database and backup-directory state."""
        self.output.delete("1.0", "end")
        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._write("=" * 60)
        self._write("COMPREHENSIVE BACKUP & DATABASE REPORT")
        self._write(f"Generated: {generated_at}")
        self._write("=" * 60)
        self._write()

        # --- Live database section ---
        self._write("DATABASE")
        self._write("-" * 60)
        db_path = str(DEFAULT_DB_PATH)
        self._write(f"Path: {db_path}")
        try:
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                self._write(f"Size: {db_size / (1024 * 1024):.2f} MB")
            else:
                self._write("Size: (database file not found)")
        except Exception as e:
            self._write(f"Size: (unavailable - {e})")

        try:
            conn = get_connection()
            try:
                mode = conn.execute("PRAGMA journal_mode").fetchone()
                if mode:
                    self._write(f"Journal mode: {str(mode[0]).upper()}")
                tables = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type = ?",
                    ("table",),
                ).fetchone()
                self._write(f"Tables: {tables[0] if tables else 0}")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Report: could not read database info: {e}")
            self._write(f"Database stats: (unavailable - {e})")

        self._write()

        # --- Backups section ---
        self._write("BACKUPS")
        self._write("-" * 60)
        backup_dir = config.get("backup_directory", "")
        self._write(f"Backup directory: {backup_dir or '(not configured)'}")

        try:
            if backup_dir and os.path.isdir(backup_dir):
                backups = [
                    f for f in os.listdir(backup_dir)
                    if f.endswith(".db") and os.path.isfile(os.path.join(backup_dir, f))
                ]
                backups.sort(reverse=True)

                if backups:
                    total_size = 0
                    self._write(f"Backup count: {len(backups)}")
                    self._write()
                    for name in backups:
                        path = os.path.join(backup_dir, name)
                        size = os.path.getsize(path)
                        total_size += size
                        mtime = datetime.datetime.fromtimestamp(
                            os.path.getmtime(path)
                        ).strftime("%Y-%m-%d %H:%M:%S")
                        self._write(f"  {name}")
                        self._write(f"      {size / (1024 * 1024):.2f} MB   |   {mtime}")
                    self._write()
                    self._write(f"Total backup size: {total_size / (1024 * 1024):.2f} MB")
                else:
                    self._write("No backup files (*.db) found in the backup directory.")
            else:
                self._write("Backup directory does not exist or is not configured.")
        except Exception as e:
            logger.error(f"Report: could not read backup directory: {e}")
            self._write(f"Backups: (unavailable - {e})")

        self.output.see("1.0")

    def save_report(self):
        """Save the current report text to a file."""
        file_path = filedialog.asksaveasfilename(
            title="Save Report",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            parent=self.dialog,
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(self.output.get("1.0", "end"))
            messagebox.showinfo("Saved", f"Report saved to:\n{file_path}", parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save report: {e}", parent=self.dialog)


class DatabaseSettingsDialog:
    """Dialog to view and edit database-related backup settings.

    Fields are wired to the real ``config`` dictionary persisted by
    ``save_config()`` (``backup_config.json``). The live database path and
    journal mode are read directly from the running database and shown
    read-only, since those are managed by the infrastructure DB layer.
    """

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Database Backup Settings")
        self.dialog.geometry("600x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        """Create dialog widgets."""
        # Live database info (read-only)
        info_frame = ttk.LabelFrame(self.dialog, text="Database (read-only)", padding=10)
        info_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(info_frame, text="Database path:").grid(row=0, column=0, sticky="w", pady=2)
        self.db_path_var = tk.StringVar(value=str(DEFAULT_DB_PATH))
        ttk.Entry(info_frame, textvariable=self.db_path_var, width=55,
                  state="readonly").grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(info_frame, text="Journal mode:").grid(row=1, column=0, sticky="w", pady=2)
        self.journal_mode_var = tk.StringVar(value="(unknown)")
        ttk.Entry(info_frame, textvariable=self.journal_mode_var, width=20,
                  state="readonly").grid(row=1, column=1, sticky="w", padx=5)

        # Editable backup settings
        settings_frame = ttk.LabelFrame(self.dialog, text="Backup Settings", padding=10)
        settings_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(settings_frame, text="Backup directory:").grid(row=0, column=0, sticky="w", pady=4)
        self.backup_dir_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=self.backup_dir_var,
                  width=45).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Button(settings_frame, text="Browse...",
                   command=self.browse_directory).grid(row=0, column=2, padx=5)

        ttk.Label(settings_frame, text="Max backups to keep:").grid(row=1, column=0, sticky="w", pady=4)
        self.max_backups_var = tk.StringVar()
        ttk.Spinbox(settings_frame, textvariable=self.max_backups_var,
                    from_=1, to=999, width=10).grid(row=1, column=1, sticky="w", padx=5)

        self.auto_backup_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Enable automatic scheduled backups",
                        variable=self.auto_backup_var).grid(row=2, column=0, columnspan=2,
                                                            sticky="w", pady=4)

        self.verify_var = tk.BooleanVar()
        ttk.Checkbutton(settings_frame, text="Verify backup integrity after creation",
                        variable=self.verify_var).grid(row=3, column=0, columnspan=2,
                                                       sticky="w", pady=4)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side="right")

    def load_current_settings(self):
        """Populate widgets from the live config and database."""
        self.backup_dir_var.set(str(config.get("backup_directory", "")))
        self.max_backups_var.set(str(config.get("max_backups", 10)))
        self.auto_backup_var.set(bool(config.get("auto_backup_enabled", True)))
        self.verify_var.set(bool(config.get("verify_integrity", True)))

        # Read the live journal mode from the running database
        try:
            conn = get_connection()
            try:
                cursor = conn.execute("PRAGMA journal_mode")
                row = cursor.fetchone()
                if row:
                    self.journal_mode_var.set(str(row[0]).upper())
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Could not read journal mode: {e}")
            self.journal_mode_var.set("(unavailable)")

    def browse_directory(self):
        """Choose a backup directory."""
        directory = filedialog.askdirectory(
            title="Select Backup Directory",
            initialdir=self.backup_dir_var.get() or str(DEFAULT_DB_PATH),
            parent=self.dialog,
        )
        if directory:
            self.backup_dir_var.set(directory)

    def save_settings(self):
        """Persist edited settings via the shared config mechanism."""
        try:
            backup_dir = self.backup_dir_var.get().strip()
            if not backup_dir:
                messagebox.showwarning("Invalid Input",
                                       "Backup directory cannot be empty.",
                                       parent=self.dialog)
                return

            config["backup_directory"] = backup_dir
            config["max_backups"] = int(self.max_backups_var.get())
            config["auto_backup_enabled"] = self.auto_backup_var.get()
            config["verify_integrity"] = self.verify_var.get()

            save_config()
            messagebox.showinfo("Success", "Database settings saved.", parent=self.dialog)
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Invalid Input",
                                 f"Please check your input values: {e}",
                                 parent=self.dialog)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}", parent=self.dialog)


class MigrationToolsDialog:
    """Dialog exposing real database maintenance/migration actions.

    Each button runs a genuine SQLite maintenance command against the live
    database via ``get_connection()`` and reports the result in the output
    area. All statements are fixed maintenance PRAGMAs / VACUUM (no user
    input is interpolated into SQL).
    """

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Database Maintenance & Migration Tools")
        self.dialog.geometry("600x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets."""
        controls_frame = ttk.LabelFrame(self.dialog, text="Maintenance Actions", padding=10)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text="Integrity Check",
                   command=self.run_integrity_check).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text="Quick Check",
                   command=self.run_quick_check).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text="VACUUM (compact)",
                   command=self.run_vacuum).grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text="Checkpoint WAL",
                   command=self.run_checkpoint).grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text="Foreign Key Check",
                   command=self.run_foreign_key_check).grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        ttk.Button(controls_frame, text="Show Schema Info",
                   command=self.show_schema_info).grid(row=1, column=2, padx=4, pady=4, sticky="ew")

        for col in range(3):
            controls_frame.columnconfigure(col, weight=1)

        output_frame = ttk.LabelFrame(self.dialog, text="Output", padding=10)
        output_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.output = scrolledtext.ScrolledText(output_frame, wrap="word", height=14)
        self.output.pack(fill="both", expand=True)

        ttk.Button(self.dialog, text="Close",
                   command=self.dialog.destroy).pack(pady=8)

    def _log(self, message):
        """Append a timestamped line to the output area."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.output.insert("end", f"[{timestamp}] {message}\n")
        self.output.see("end")
        self.dialog.update_idletasks()

    def _run_maintenance(self, label, sql):
        """Run a fixed maintenance statement and report all returned rows."""
        self._log(f"Running: {label} ...")
        try:
            conn = get_connection()
            try:
                cursor = conn.execute(sql)
                rows = cursor.fetchall()
                conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            if rows:
                for row in rows:
                    self._log("  " + " | ".join(str(v) for v in row))
            else:
                self._log("  (no rows returned)")
            self._log(f"{label}: done.")
        except Exception as e:
            logger.error(f"{label} failed: {e}")
            self._log(f"{label}: ERROR - {e}")
            messagebox.showerror("Maintenance Error",
                                 f"{label} failed: {e}", parent=self.dialog)

    def run_integrity_check(self):
        """PRAGMA integrity_check on the live database."""
        self._run_maintenance("Integrity check", "PRAGMA integrity_check")

    def run_quick_check(self):
        """PRAGMA quick_check (faster, lighter than integrity_check)."""
        self._run_maintenance("Quick check", "PRAGMA quick_check")

    def run_vacuum(self):
        """Rebuild/compact the database file."""
        if not messagebox.askyesno("Confirm VACUUM",
                                    "VACUUM rebuilds the entire database file and may "
                                    "take a while.\n\nContinue?", parent=self.dialog):
            return
        self._run_maintenance("VACUUM", "VACUUM")

    def run_checkpoint(self):
        """Checkpoint the write-ahead log back into the main database."""
        self._run_maintenance("WAL checkpoint", "PRAGMA wal_checkpoint(TRUNCATE)")

    def run_foreign_key_check(self):
        """Report any foreign-key constraint violations."""
        self._run_maintenance("Foreign key check", "PRAGMA foreign_key_check")

    def show_schema_info(self):
        """List tables and row counts from the live database schema."""
        self._log("Reading schema info ...")
        try:
            conn = get_connection()
            try:
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = ? ORDER BY name",
                    ("table",),
                )
                tables = [r[0] for r in cursor.fetchall()]
                self._log(f"  {len(tables)} table(s) found.")
                for name in tables:
                    # Validate the identifier before embedding it in a
                    # count query (table names cannot be bound as params).
                    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                        self._log(f"  {name}: (skipped - invalid identifier)")
                        continue
                    try:
                        c = conn.execute(f'SELECT COUNT(*) FROM "{name}"')
                        count = c.fetchone()[0]
                        self._log(f"  {name}: {count} row(s)")
                    except Exception as inner:
                        self._log(f"  {name}: (count failed - {inner})")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            self._log("Schema info: done.")
        except Exception as e:
            logger.error(f"Schema info failed: {e}")
            self._log(f"Schema info: ERROR - {e}")
            messagebox.showerror("Schema Error",
                                 f"Could not read schema: {e}", parent=self.dialog)
