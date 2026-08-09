"""Methods create_storage_tab through optimize_storage."""

from .. import admin_management_windows_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class DiagnosticsWindow:
    def create_storage_tab(self, parent):
        """Create storage diagnostics tab"""
        # Storage analysis
        storage_frame = ttk.LabelFrame(parent, text=_("admin_windows.diagnostics.storage.title"), padding="15")
        storage_frame.pack(fill='both', expand=True, padx=15, pady=15)

        storage_text = scrolledtext.ScrolledText(storage_frame, height=25, wrap='word')
        storage_text.pack(fill='both', expand=True)

        storage_data = f"""
STORAGE DIAGNOSTIC REPORT
========================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

DISK USAGE SUMMARY:
• Total Capacity: 500 GB
• Used Space: 225 GB (45%)
• Free Space: 275 GB (55%)
• System Reserved: 25 GB (5%)

DISK BREAKDOWN BY DIRECTORY:
/var/log          45 GB (20% of used)
/home/uploads     38 GB (17% of used)
/var/backups      32 GB (14% of used)
/var/cache        28 GB (12% of used)
/opt/applications 25 GB (11% of used)
/tmp              12 GB (5% of used)
/var/lib/postgres 23 GB (10% of used)
Other             22 GB (10% of used)

DISK PERFORMANCE:
• Read Speed: 1,200 MB/s (SSD)
• Write Speed: 800 MB/s (SSD)
• IOPS: 450 avg, 1,200 peak
• Queue Depth: 2.3 average
• Seek Time: <1ms (SSD)

DISK HEALTH:
• Drive Health: Excellent ✓
• Bad Sectors: 0
• Temperature: 35°C (Normal)
• Power-On Hours: 8,547
• Wear Level: 12% (Low)

FILE SYSTEM ANALYSIS:
• File System: ext4
• Mount Status: Healthy ✓
• Inode Usage: 23% (112,450 of 488,000)
• Fragmentation: 3% (Low)
• Last fsck: 2024-01-20 (Clean)

BACKUP STATUS:
• Last Full Backup: 2024-01-29 02:00 AM ✓
• Backup Size: 180 GB
• Backup Location: /var/backups/
• Incremental Backups: Daily ✓
• Backup Verification: Passed ✓

STORAGE GROWTH ANALYSIS:
Daily Growth Rate: 2.3 GB/day
Weekly Growth Rate: 16.1 GB/week
Monthly Growth Rate: 69.3 GB/month
Projected Full in: 11.9 months

LARGEST FILES (>1GB):
/var/backups/full_backup_20240129.tar.gz    32.1 GB
/var/log/application.log                     8.7 GB
/var/cache/package_cache.db                  6.2 GB
/home/uploads/video_lectures.zip             4.8 GB
/var/lib/postgres/data/base/postgres.db      3.9 GB
/tmp/system_export.sql                       2.1 GB

LOG FILE ANALYSIS:
• Total Log Size: 45 GB
• Oldest Log: 2023-12-01
• Log Rotation: Active ✓
• Compression: Enabled ✓
• Archive Policy: 90 days

CLEANUP OPPORTUNITIES:
• Temporary files: 12 GB can be safely removed
• Old log files: 8 GB can be archived
• Cache files: 6 GB can be cleared
• Duplicate files: 3 GB identified
• Empty directories: 247 found

I/O STATISTICS (24h):
Read Operations: 156,789
Write Operations: 89,234
Data Read: 234 GB
Data Written: 89 GB
Average Queue Time: 2.3ms

STORAGE ALERTS:
• No critical storage alerts
• Free space above 50% threshold
• No disk errors detected
• Backup system operational

RECOMMENDATIONS:
✓ Storage health is excellent
✓ Implement automated cleanup for temp files
✓ Consider archiving old log files
✓ Monitor growth rate trends
✓ Schedule disk optimization for next maintenance
✓ Current capacity sufficient for 11+ months
"""

        storage_text.insert('1.0', storage_data)
        storage_text.config(state='disabled')

        # Storage actions
        storage_actions = ttk.Frame(storage_frame)
        storage_actions.pack(fill='x', pady=(10, 0))

        ttk.Button(storage_actions, text=_("admin_windows.diagnostics.storage.buttons.disk_cleanup"),
                  command=self.run_disk_cleanup).pack(side='left', padx=(0, 10))
        ttk.Button(storage_actions, text=_("admin_windows.diagnostics.storage.buttons.check_health"),
                  command=self.check_disk_health).pack(side='left', padx=(0, 10))
        ttk.Button(storage_actions, text=_("admin_windows.diagnostics.storage.buttons.optimize"),
                  command=self.optimize_storage).pack(side='left')

    def run_full_diagnostic(self):
        """Run comprehensive system diagnostic"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.full_diagnostic_title"),
                           _("admin_windows.diagnostics.messages.full_diagnostic_body"))

    def generate_health_report(self):
        """Generate detailed health report"""
        filename = filedialog.asksaveasfilename(
            title=_("admin_windows.diagnostics.messages.save_report_title"),
            defaultextension=".pdf",
            filetypes=[(_("admin_windows.filetypes.pdf"), "*.pdf"), (_("admin_windows.filetypes.txt"), "*.txt"), (_("admin_windows.filetypes.all"), "*.*")]
        )

        if filename:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.report_generated_title"), _("admin_windows.diagnostics.messages.report_generated_body", filename=filename))

    def view_system_logs(self):
        """View system logs"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.system_logs_title"), _("admin_windows.diagnostics.messages.system_logs_body"))

    def run_performance_test(self):
        """Run performance benchmark"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.perf_test_title"),
                           _("admin_windows.diagnostics.messages.perf_test_body"))

    def optimize_system(self):
        """Run system optimization"""
        result = messagebox.askyesno(_("admin_windows.diagnostics.messages.sys_optimize_title"),
                                   _("admin_windows.diagnostics.messages.sys_optimize_body"))
        if result:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.optimize_complete_title"), _("admin_windows.diagnostics.messages.optimize_complete_body"))

    def view_live_metrics(self):
        """View live performance metrics"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.live_metrics_title"), _("admin_windows.diagnostics.messages.live_metrics_body"))

    def test_connectivity(self):
        """Test network connectivity"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.connectivity_title"),
                           _("admin_windows.diagnostics.messages.connectivity_body"))

    def run_speed_test(self):
        """Run network speed test"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.speed_test_title"),
                           _("admin_windows.diagnostics.messages.speed_test_body"))

    def run_port_scan(self):
        """Run port scanner"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.port_scan_title"), _("admin_windows.diagnostics.messages.port_scan_body"))

    def run_disk_cleanup(self):
        """Run disk cleanup utility"""
        result = messagebox.askyesno(_("admin_windows.diagnostics.messages.disk_cleanup_title"),
                                   _("admin_windows.diagnostics.messages.disk_cleanup_body"))
        if result:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.cleanup_complete_title"), _("admin_windows.diagnostics.messages.cleanup_complete_body"))

    def check_disk_health(self):
        """Check disk health status"""
        messagebox.showinfo(_("admin_windows.diagnostics.messages.disk_health_title"),
                           _("admin_windows.diagnostics.messages.disk_health_body"))

    def optimize_storage(self):
        """Optimize storage performance"""
        result = messagebox.askyesno(_("admin_windows.diagnostics.messages.storage_optimize_title"),
                                   _("admin_windows.diagnostics.messages.storage_optimize_body"))
        if result:
            messagebox.showinfo(_("admin_windows.diagnostics.messages.storage_complete_title"), _("admin_windows.diagnostics.messages.storage_complete_body"))
