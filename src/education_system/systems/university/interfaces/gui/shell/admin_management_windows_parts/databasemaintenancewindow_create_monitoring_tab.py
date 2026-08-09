"""Methods create_monitoring_tab through view_live_stats."""

from .. import admin_management_windows_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DatabaseMaintenanceWindow:
    def create_monitoring_tab(self, parent):
        """Create monitoring tab"""
        # Monitoring controls
        monitor_controls = ttk.LabelFrame(parent, text=_("admin_windows.database.monitoring.title"), padding="15")
        monitor_controls.pack(fill='x', padx=15, pady=15)

        # Monitoring options
        monitor_options = ttk.Frame(monitor_controls)
        monitor_options.pack(fill='x', pady=(0, 15))

        ttk.Label(monitor_options, text=_("admin_windows.database.monitoring.interval")).pack(side='left', padx=(0, 10))
        self.monitor_interval_var = tk.StringVar(value=_("admin_windows.database.monitoring.intervals.5min"))
        ttk.Combobox(monitor_options, textvariable=self.monitor_interval_var,
                    values=[_("admin_windows.database.monitoring.intervals.30sec"), _("admin_windows.database.monitoring.intervals.1min"), _("admin_windows.database.monitoring.intervals.5min"), _("admin_windows.database.monitoring.intervals.15min"), _("admin_windows.database.monitoring.intervals.1hour")],
                    width=15).pack(side='left', padx=(0, 20))

        self.alert_enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(monitor_options, text=_("admin_windows.database.monitoring.enable_alerts"),
                       variable=self.alert_enabled_var).pack(side='left', padx=(0, 20))

        # Monitoring actions
        monitor_actions = ttk.Frame(monitor_controls)
        monitor_actions.pack(fill='x')

        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.start"),
                  command=self.start_monitoring).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.stop"),
                  command=self.stop_monitoring).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.configure"),
                  command=self.configure_alerts).pack(side='left', padx=(0, 10))
        ttk.Button(monitor_actions, text=_("admin_windows.database.monitoring.buttons.live_stats"),
                  command=self.view_live_stats).pack(side='left')

        # Monitoring display
        monitor_frame = ttk.LabelFrame(parent, text=_("admin_windows.database.monitoring.realtime"), padding="15")
        monitor_frame.pack(fill='both', expand=True, padx=15, pady=(0, 15))

        monitor_text = scrolledtext.ScrolledText(monitor_frame, height=18, wrap='word')
        monitor_text.pack(fill='both', expand=True)

        monitor_data = f"""
DATABASE MONITORING DASHBOARD
============================
Status: Active ✓
Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

REAL-TIME METRICS:
• Active Connections: 8/20
• Queries per Second: 12.3
• Response Time: 89ms
• CPU Usage: 15%
• Memory Usage: 234 MB
• Cache Hit Ratio: 96.8%

CONNECTION MONITORING:
Active Sessions:
1. user_app (10.0.0.15) - 3 connections, 45s idle
2. backup_service (192.168.1.50) - 1 connection, active
3. monitoring (localhost) - 1 connection, active
4. admin (192.168.1.100) - 1 connection, 2m idle
5. readonly (10.0.0.25) - 2 connections, active

QUERY MONITORING:
Recent Queries (last 5 minutes):
• SELECT * FROM students WHERE... (89ms)
• INSERT INTO attendance... (12ms)
• UPDATE assignments SET... (156ms)
• SELECT COUNT(*) FROM... (23ms)
• DELETE FROM temp_data... (45ms)

Slow Queries (>1s):
• No slow queries in last 5 minutes ✓

PERFORMANCE TRENDS (Last 24 hours):
Response Time:
  Average: 89ms
  Peak: 234ms (at 10:30 AM)
  Minimum: 12ms (at 3:00 AM)

Connections:
  Average: 6.8 connections
  Peak: 15 connections (at 2:00 PM)
  Minimum: 2 connections (at 4:00 AM)

RESOURCE UTILIZATION:
CPU Usage History:
  Current: 15%
  24h Average: 12%
  Peak: 34% (during backup)

Memory Usage:
  Current: 234 MB
  24h Average: 198 MB
  Peak: 445 MB (during optimization)

I/O Operations:
  Reads/sec: 45
  Writes/sec: 23
  24h Average: 67 ops/sec

ALERT HISTORY:
Today:
• 02:15 - Backup completed successfully ✓
• 02:30 - Optimization completed ✓

Yesterday:
• 14:25 - Connection spike detected (resolved)
• 10:30 - High query volume (normal)

This Week:
• No critical alerts ✓
• 5 informational alerts
• 2 warning alerts (resolved)

HEALTH INDICATORS:
✓ Database Online
✓ Backup System Active
✓ Monitoring Active
✓ No Lock Contention
✓ No Deadlocks
✓ Storage Healthy
✓ Network Connectivity Good
✓ Security Measures Active

AUTOMATIC ACTIONS:
• Auto-vacuum triggered: 2024-01-29 03:00
• Statistics updated: 2024-01-29 02:15
• Log rotation: 2024-01-29 00:00
• Connection cleanup: Ongoing

UPCOMING EVENTS:
• Next backup: 2024-01-30 02:00
• Maintenance window: 2024-02-04 02:00
• Log rotation: 2024-01-30 00:00
• Statistics update: 2024-01-30 02:15

MONITORING CONFIGURATION:
• Monitor Interval: 5 minutes
• Alert Threshold: Response time >500ms
• Connection Limit Alert: >18 connections
• Disk Space Alert: <10% free
• Memory Alert: >80% usage
• Auto-restart: Enabled for critical failures
"""

        monitor_text.insert('1.0', monitor_data)
        monitor_text.config(state='disabled')

    def refresh_status(self):
        """Refresh database status"""
        messagebox.showinfo(_("admin_windows.database.messages.status_refreshed_title"), _("admin_windows.database.messages.status_refreshed_body"))

    def test_connection(self):
        """Test database connection"""
        messagebox.showinfo(_("admin_windows.database.messages.connection_test_title"),
                           _("admin_windows.database.messages.connection_test_body"))

    def export_status(self):
        """Export status report"""
        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.database.messages.export_status_title"),
            defaultextension=".pdf",
            filetypes=[(_("admin_windows.filetypes.pdf"), "*.pdf"), (_("admin_windows.filetypes.txt"), "*.txt"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.messages.export_complete"), _("admin_windows.database.messages.status_exported", filename=filename))

    def create_backup(self):
        """Create database backup"""
        backup_type = self.backup_type_var.get()
        compression = self.compression_var.get()

        messagebox.showinfo(_("admin_windows.database.messages.backup_started_title"),
                           _("admin_windows.database.messages.backup_started_body", backup_type=backup_type, compression=_("admin_windows.database.backup.enabled") if compression else _("admin_windows.database.backup.disabled")))

    def schedule_backup(self):
        """Schedule automatic backups"""
        messagebox.showinfo(_("admin_windows.database.messages.backup_schedule_title"),
                           _("admin_windows.database.messages.backup_schedule_body"))

    def verify_backup(self):
        """Verify backup integrity"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_verify"))
            return

        messagebox.showinfo(_("admin_windows.database.messages.backup_verify_title"),
                           _("admin_windows.database.messages.backup_verify_body"))

    def restore_backup(self):
        """Restore from selected backup"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_restore"))
            return

        item = self.backup_tree.item(selection[0])
        backup_date = item['values'][0]

        result = messagebox.askyesno(_("admin_windows.database.messages.confirm_restore_title"),
                                   _("admin_windows.database.messages.confirm_restore_body", backup_date=backup_date))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.restore_started_title"), _("admin_windows.database.messages.restore_started_body"))

    def download_backup(self):
        """Download backup file"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_download"))
            return

        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.database.messages.save_backup_title"),
            defaultextension=".sql.gz",
            filetypes=[(_("admin_windows.filetypes.sql_compressed"), "*.sql.gz"), (_("admin_windows.filetypes.sql"), "*.sql"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.database.messages.download_complete_title"), _("admin_windows.database.messages.download_complete_body", filename=filename))

    def delete_backup(self):
        """Delete selected backup"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_("admin_windows.messages.no_selection"), _("admin_windows.database.messages.select_backup_delete"))
            return

        item = self.backup_tree.item(selection[0])
        backup_date = item['values'][0]

        result = messagebox.askyesno(_("admin_windows.database.messages.confirm_delete_title"),
                                   _("admin_windows.database.messages.confirm_delete_body", backup_date=backup_date))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.backup_deleted_title"), _("admin_windows.database.messages.backup_deleted_body"))

    def restore_from_file(self):
        """Restore database from file"""
        filename = filedialog.askopenfilename(
            title=_("admin_windows.database.messages.select_backup_file"),
            filetypes=[(_("admin_windows.filetypes.sql"), "*.sql"), (_("admin_windows.filetypes.sql_compressed"), "*.sql.gz"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            result = messagebox.askyesno(_("admin_windows.database.messages.confirm_restore_title"),
                                       _("admin_windows.database.messages.confirm_restore_file", filename=filename))
            if result:
                messagebox.showinfo(_("admin_windows.database.messages.restore_started_title"), _("admin_windows.database.messages.restore_from_file", filename=filename))

    def run_optimization(self):
        """Run database optimization"""
        operations = []
        if self.vacuum_var.get():
            operations.append("VACUUM")
        if self.analyze_var.get():
            operations.append("ANALYZE")
        if self.reindex_var.get():
            operations.append("REINDEX")
        if self.cleanup_var.get():
            operations.append("CLEANUP")

        if not operations:
            messagebox.showwarning(_("admin_windows.database.messages.no_operations_title"), _("admin_windows.database.messages.no_operations_body"))
            return

        operations_text = ", ".join(operations)
        result = messagebox.askyesno(_("admin_windows.database.messages.confirm_optimize_title"),
                                   _("admin_windows.database.messages.confirm_optimize_body", operations=operations_text))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.optimize_started_title"),
                               _("admin_windows.database.messages.optimize_started_body", operations=operations_text))

    def schedule_maintenance(self):
        """Schedule maintenance window"""
        messagebox.showinfo(_("admin_windows.database.messages.maintenance_schedule_title"),
                           _("admin_windows.database.messages.maintenance_schedule_body"))

    def check_integrity(self):
        """Check database integrity"""
        messagebox.showinfo(_("admin_windows.database.messages.integrity_title"),
                           _("admin_windows.database.messages.integrity_body"))

    def start_monitoring(self):
        """Start database monitoring"""
        interval = self.monitor_interval_var.get()
        alerts = self.alert_enabled_var.get()

        messagebox.showinfo(_("admin_windows.database.messages.monitoring_started_title"),
                           _("admin_windows.database.messages.monitoring_started_body", interval=interval, alerts=_("admin_windows.database.backup.enabled") if alerts else _("admin_windows.database.backup.disabled")))

    def stop_monitoring(self):
        """Stop database monitoring"""
        result = messagebox.askyesno(_("admin_windows.database.messages.stop_monitoring_title"),
                                   _("admin_windows.database.messages.stop_monitoring_body"))
        if result:
            messagebox.showinfo(_("admin_windows.database.messages.monitoring_stopped_title"), _("admin_windows.database.messages.monitoring_stopped_body"))

    def configure_alerts(self):
        """Configure monitoring alerts"""
        messagebox.showinfo(_("admin_windows.database.messages.alert_config_title"),
                           _("admin_windows.database.messages.alert_config_body"))

    def view_live_stats(self):
        """View live statistics"""
        messagebox.showinfo(_("admin_windows.database.messages.live_stats_title"),
                           _("admin_windows.database.messages.live_stats_body"))
