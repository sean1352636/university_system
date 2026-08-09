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

        status_items = [
            (_("admin_windows.database.status.connection"), _("admin_windows.database.status.values.connected"), "green"),
            (_("admin_windows.database.status.health"), _("admin_windows.diagnostics.health.status.excellent"), "green"),
            (_("admin_windows.database.status.size"), "2.3 GB", "blue"),
            (_("admin_windows.database.status.tables"), "47", "blue"),
            (_("admin_windows.database.status.connections"), "8/20", "green"),
            (_("admin_windows.database.status.uptime"), "15d 7h", "blue")
        ]

        for i, (label, value, color) in enumerate(status_items):
            status_item = ttk.LabelFrame(status_grid, text=label, padding="10")
            status_item.grid(row=i//3, column=i%3, padx=5, pady=5, sticky='ew')
            ttk.Label(status_item, text=value, font=('Arial', 12, 'bold')).pack()
            status_grid.grid_columnconfigure(i%3, weight=1)

        # Detailed status
        details_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.status.detailed_info"), padding="15")
        details_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        status_text = scrolledtext.ScrolledText(details_frame, height=18, wrap='word')
        status_text.pack(fill='both', expand=True)

        status_info = f"""
DATABASE STATUS REPORT
=====================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CONNECTION INFORMATION:
• Database Type: PostgreSQL 13.2
• Server Status: Online ✓
• Connection Pool: 8/20 active connections
• Response Time: 12ms average
• Last Restart: 2024-01-14 09:30:00

DATABASE STATISTICS:
• Total Size: 2.3 GB
• Number of Tables: 47
• Number of Indexes: 89
• Number of Views: 12
• Number of Procedures: 23

TABLE ANALYSIS:
Largest Tables:
1. student_records     - 890 MB (456,789 rows)
2. attendance_logs     - 234 MB (1,234,567 rows)
3. assignment_submissions - 189 MB (89,234 rows)
4. audit_logs         - 156 MB (567,890 rows)
5. course_enrollments - 123 MB (234,567 rows)

INDEX STATISTICS:
• Total Indexes: 89
• Index Size: 456 MB
• Index Usage: 94.7% (85/89 used)
• Unused Indexes: 4
• Missing Indexes: None detected

PERFORMANCE METRICS:
• Query Response Time: 12ms average
• Slow Queries (>1s): 3 in last 24h
• Cache Hit Ratio: 96.8%
• Buffer Usage: 78%
• Lock Contention: None

CONNECTION ANALYSIS:
Active Connections: 8
• user_app: 3 connections
• backup_service: 1 connection
• monitoring: 1 connection
• admin: 1 connection
• readonly: 2 connections

Idle Connections: 2
Max Connections: 20
Connection Efficiency: 95%

RECENT ACTIVITY:
• Last Query: 2 seconds ago
• Queries/Minute: 145 average
• Peak QPS: 389 (at 10:30 AM)
• Data Modifications: 89 in last hour
• Schema Changes: None in last 24h

MAINTENANCE STATUS:
• Last VACUUM: 2024-01-28 02:00:00
• Last ANALYZE: 2024-01-29 02:15:00
• Last REINDEX: 2024-01-27 02:30:00
• Auto-vacuum: Enabled ✓
• Statistics Collection: Enabled ✓

BACKUP STATUS:
• Last Full Backup: 2024-01-29 02:00:00 ✓
• Last Incremental: 2024-01-29 14:00:00 ✓
• Backup Size: 1.8 GB compressed
• Backup Location: /var/backups/db/
• Backup Verification: Passed ✓

ERROR LOG SUMMARY:
• Errors (24h): 0
• Warnings (24h): 2
• Deadlocks (24h): 0
• Connection Failures: 0
• Disk Full Events: 0

RECOMMENDATIONS:
✓ Database is performing excellently
✓ All maintenance tasks up to date
✓ Backup system functioning properly
✓ No immediate action required
✓ Continue monitoring query performance
"""

        status_text.insert('1.0', status_info)
        status_text.config(state='disabled')

        # Status actions
        actions_frame = ttk.Frame(details_frame)
        actions_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.refresh"),
                  command=self.refresh_status).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.test_connection"),
                  command=self.test_connection).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text=_("admin_windows.database.status.buttons.export"),
                  command=self.export_status).pack(side='left')

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

        # Sample backup history
        backup_history = [
            ("2024-01-29 02:00", "Full", "1.8 GB", "12m 34s", "Success", "/var/backups/db/full_20240129.sql.gz"),
            ("2024-01-28 14:00", "Incremental", "245 MB", "3m 21s", "Success", "/var/backups/db/inc_20240128_14.sql.gz"),
            ("2024-01-28 02:00", "Full", "1.7 GB", "11m 45s", "Success", "/var/backups/db/full_20240128.sql.gz"),
            ("2024-01-27 14:00", "Incremental", "189 MB", "2m 56s", "Success", "/var/backups/db/inc_20240127_14.sql.gz"),
            ("2024-01-27 02:00", "Full", "1.7 GB", "12m 12s", "Success", "/var/backups/db/full_20240127.sql.gz")
        ]

        for backup_data in backup_history:
            self.backup_tree.insert('', 'end', values=backup_data)

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

        opt_text = scrolledtext.ScrolledText(results_frame, height=18, wrap='word')
        opt_text.pack(fill='both', expand=True)

        opt_results = f"""
DATABASE OPTIMIZATION REPORT
===========================
Last Optimization: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

VACUUM ANALYSIS:
• Dead Tuples Removed: 12,456
• Pages Reclaimed: 234
• Storage Freed: 45.7 MB
• Tables Processed: 47
• Duration: 8m 23s

ANALYZE RESULTS:
• Statistics Updated: All tables ✓
• Query Plans Refreshed: 89 plans
• Histogram Updated: All columns
• Duration: 2m 45s

INDEX ANALYSIS:
• Total Indexes: 89
• Indexes Rebuilt: 4 (outdated)
• Index Bloat Removed: 12.3 MB
• Query Performance Improved: 15%
• Duration: 5m 12s

PERFORMANCE IMPROVEMENTS:
Before Optimization:
• Average Query Time: 156ms
• Cache Hit Ratio: 93.2%
• Index Usage: 91.4%
• Buffer Efficiency: 76%

After Optimization:
• Average Query Time: 89ms (43% improvement)
• Cache Hit Ratio: 96.8% (3.6% improvement)
• Index Usage: 94.7% (3.3% improvement)
• Buffer Efficiency: 89% (13% improvement)

TABLE MAINTENANCE SUMMARY:
student_records:
  - Vacuum: 8,234 dead tuples removed
  - Analyze: Statistics updated
  - Storage: 12.3 MB reclaimed

attendance_logs:
  - Vacuum: 3,567 dead tuples removed
  - Analyze: Statistics updated
  - Storage: 8.9 MB reclaimed

assignment_submissions:
  - Vacuum: 1,234 dead tuples removed
  - Analyze: Statistics updated
  - Storage: 5.6 MB reclaimed

SLOW QUERY OPTIMIZATION:
• Queries analyzed: 15
• Queries optimized: 8
• Performance gain: 67% average
• New indexes suggested: 2

INDEX RECOMMENDATIONS:
✓ Create index on attendance_logs(student_id, date)
✓ Create index on submissions(assignment_id, status)
✓ Drop unused index on old_table(deprecated_column)

MAINTENANCE SCHEDULE:
• Auto-vacuum: Enabled (threshold: 20%)
• Auto-analyze: Enabled (threshold: 10%)
• Full maintenance: Weekly (Sundays 2:00 AM)
• Index rebuild: Monthly
• Statistics update: Daily

OPTIMIZATION WARNINGS:
• No critical issues detected
• All optimizations completed successfully
• Database performance is excellent

NEXT SCHEDULED MAINTENANCE:
• Date: 2024-02-04 02:00:00
• Type: Full maintenance
• Estimated Duration: 15-20 minutes
• Impact: Minimal (scheduled during low usage)

RECOMMENDATIONS:
✓ Optimization completed successfully
✓ Query performance significantly improved
✓ All maintenance tasks up to date
✓ Continue regular maintenance schedule
✓ Monitor query patterns for future optimization
"""

        opt_text.insert('1.0', opt_results)
        opt_text.config(state='disabled')
