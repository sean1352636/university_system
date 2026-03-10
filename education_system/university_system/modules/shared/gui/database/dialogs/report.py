"""Report dialog for generating comprehensive backup reports.

Provides the ReportDialog class which allows users to generate summary,
detailed, and statistics reports for the backup system, with export
capabilities in text, HTML, and PDF formats.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import datetime

from education_system.university_system.modules.shared.gui.database.config import config
from education_system.university_system.modules.shared.gui.database.shared_imports import logger
from education_system.university_system.modules.shared.gui.database.operations.backup_ops import list_available_backups
from education_system.university_system.modules.shared.gui.database.operations.stats_ops import generate_backup_statistics


class ReportDialog:
    """Dialog for generating comprehensive backup reports"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Report Generator")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)

        self.create_widgets()

    def create_widgets(self):
        """Create dialog widgets"""
        # Report options
        options_frame = ttk.LabelFrame(self.dialog, text="Report Options", padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        # Report type
        self.report_type_var = tk.StringVar(value="summary")
        ttk.Label(options_frame, text="Report Type:").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(options_frame, text="Summary Report", variable=self.report_type_var,
                       value="summary").grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(options_frame, text="Detailed Report", variable=self.report_type_var,
                       value="detailed").grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(options_frame, text="Statistics Report", variable=self.report_type_var,
                       value="statistics").grid(row=0, column=3, sticky="w")

        # Date range
        ttk.Label(options_frame, text="Date Range:").grid(row=1, column=0, sticky="w", pady=5)
        self.date_range_var = tk.StringVar(value="all")
        date_frame = ttk.Frame(options_frame)
        date_frame.grid(row=1, column=1, columnspan=3, sticky="w")

        ttk.Radiobutton(date_frame, text="All time", variable=self.date_range_var, value="all").pack(side="left")
        ttk.Radiobutton(date_frame, text="Last 30 days", variable=self.date_range_var, value="30days").pack(side="left")
        ttk.Radiobutton(date_frame, text="Last 90 days", variable=self.date_range_var, value="90days").pack(side="left")

        # Export options
        ttk.Label(options_frame, text="Export Format:").grid(row=2, column=0, sticky="w", pady=5)
        self.export_format_var = tk.StringVar(value="text")
        export_frame = ttk.Frame(options_frame)
        export_frame.grid(row=2, column=1, columnspan=3, sticky="w")

        ttk.Radiobutton(export_frame, text="Text", variable=self.export_format_var, value="text").pack(side="left")
        ttk.Radiobutton(export_frame, text="HTML", variable=self.export_format_var, value="html").pack(side="left")
        ttk.Radiobutton(export_frame, text="PDF", variable=self.export_format_var, value="pdf").pack(side="left")

        # Generate button
        ttk.Button(options_frame, text="Generate Report", command=self.generate_report).grid(row=3, column=1, pady=10)

        # Report display
        display_frame = ttk.LabelFrame(self.dialog, text="Report", padding=10)
        display_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.report_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD)
        self.report_text.pack(fill="both", expand=True)

        # Export button
        export_button_frame = ttk.Frame(self.dialog)
        export_button_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(export_button_frame, text="Export Report", command=self.export_report).pack(side="right", padx=5)
        ttk.Button(export_button_frame, text="Close", command=self.dialog.destroy).pack(side="right")

    def generate_report(self):
        """Generate the backup report"""
        try:
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(tk.END, "Generating report...\n")
            self.dialog.update()

            report_type = self.report_type_var.get()
            date_range = self.date_range_var.get()

            # Get backup data
            backups = list_available_backups()
            stats = generate_backup_statistics()

            # Filter by date range
            if date_range != "all":
                days = 30 if date_range == "30days" else 90
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)

                filtered_backups = []
                for backup in backups:
                    try:
                        backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                        if backup_date >= cutoff_date:
                            filtered_backups.append(backup)
                    except (ValueError, KeyError):
                        pass
                backups = filtered_backups

            # Generate report content
            report_content = self.create_report_content(report_type, backups, stats)

            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(1.0, report_content)

        except Exception as e:
            self.report_text.delete(1.0, tk.END)
            self.report_text.insert(1.0, f"Error generating report: {e}")

    def create_report_content(self, report_type, backups, stats):
        """Create report content based on type"""
        content = f"BACKUP SYSTEM REPORT\n"
        content += f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"Report Type: {report_type.title()}\n"
        content += "=" * 60 + "\n\n"

        if report_type == "summary":
            content += self.create_summary_report(backups, stats)
        elif report_type == "detailed":
            content += self.create_detailed_report(backups, stats)
        elif report_type == "statistics":
            content += self.create_statistics_report(backups, stats)

        return content

    def create_summary_report(self, backups, stats):
        """Create summary report"""
        content = "EXECUTIVE SUMMARY\n"
        content += "-" * 20 + "\n\n"

        content += f"Total Backups: {len(backups)}\n"
        content += f"Total Storage Used: {stats['total_size'] / (1024*1024*1024):.2f} GB\n"
        content += f"Average Backup Size: {stats['average_size'] / (1024*1024):.2f} MB\n"
        content += f"Recent Activity: {stats['recent_activity']} backups in last 30 days\n\n"

        # Latest backup info
        if backups:
            latest = backups[0]
            content += f"Latest Backup:\n"
            content += f"  Date: {latest['date_formatted']}\n"
            content += f"  Type: {latest.get('backup_type', 'full')}\n"
            content += f"  Size: {latest['size_formatted']}\n"
            content += f"  Status: {'✓ Valid' if os.path.exists(latest['path']) else '✗ Missing'}\n\n"

        # Backup health
        valid_backups = sum(1 for b in backups if os.path.exists(b['path']))
        health_percentage = (valid_backups / len(backups) * 100) if backups else 0
        content += f"Backup Health: {health_percentage:.1f}% ({valid_backups}/{len(backups)} valid)\n\n"

        # Recommendations
        content += "RECOMMENDATIONS\n"
        content += "-" * 15 + "\n"
        if health_percentage < 100:
            content += "• Some backup files are missing - investigate storage issues\n"
        if stats['recent_activity'] == 0:
            content += "• No recent backup activity - check scheduler\n"
        if stats['total_size'] > 5 * 1024 * 1024 * 1024:  # 5GB
            content += "• Consider cleanup of old backups to free space\n"
        if not config["encryption_enabled"]:
            content += "• Enable encryption for sensitive data protection\n"

        return content

    def create_detailed_report(self, backups, stats):
        """Create detailed report"""
        content = "DETAILED BACKUP ANALYSIS\n"
        content += "-" * 25 + "\n\n"

        # Configuration summary
        content += "CURRENT CONFIGURATION\n"
        content += "-" * 20 + "\n"
        content += f"Backup Directory: {config['backup_directory']}\n"
        content += f"Auto Backup: {'Enabled' if config['auto_backup_enabled'] else 'Disabled'}\n"
        content += f"Frequency: {config['backup_frequency']}\n"
        content += f"Scheduled Time: {config['scheduled_backup_time']}\n"
        content += f"Max Backups: {config['max_backups']}\n"
        content += f"Encryption: {'Enabled' if config['encryption_enabled'] else 'Disabled'}\n"
        content += f"Compression: {'Enabled' if config['compression_enabled'] else 'Disabled'}\n"
        content += f"Cloud Storage: {'Enabled' if config['cloud_enabled'] else 'Disabled'}\n\n"

        # Backup type distribution
        content += "BACKUP TYPE DISTRIBUTION\n"
        content += "-" * 25 + "\n"
        type_counts = {}
        for backup in backups:
            backup_type = backup.get('backup_type', 'full')
            type_counts[backup_type] = type_counts.get(backup_type, 0) + 1

        for backup_type, count in type_counts.items():
            percentage = (count / len(backups) * 100) if backups else 0
            content += f"{backup_type}: {count} ({percentage:.1f}%)\n"
        content += "\n"

        # Recent backup details
        content += "RECENT BACKUPS (Last 10)\n"
        content += "-" * 25 + "\n"
        content += f"{'Date':<20} {'Type':<12} {'Size':<10} {'Status':<8} {'File'}\n"
        content += "-" * 80 + "\n"

        for backup in backups[:10]:
            status = "Valid" if os.path.exists(backup['path']) else "Missing"
            content += f"{backup['date_formatted']:<20} {backup.get('backup_type', 'full'):<12} "
            content += f"{backup['size_formatted']:<10} {status:<8} {backup['filename']}\n"

        return content

    def create_statistics_report(self, backups, stats):
        """Create statistics report"""
        content = "BACKUP STATISTICS\n"
        content += "-" * 17 + "\n\n"

        # Overall statistics
        content += "OVERALL STATISTICS\n"
        content += "-" * 18 + "\n"
        content += f"Total Backups: {stats['total_backups']}\n"
        content += f"Total Size: {stats['total_size'] / (1024*1024*1024):.2f} GB\n"
        content += f"Average Size: {stats['average_size'] / (1024*1024):.2f} MB\n"
        content += f"Recent Activity: {stats['recent_activity']} backups (30 days)\n\n"

        # Size analysis
        if backups:
            sizes = [backup.get('size', 0) for backup in backups]
            content += "SIZE ANALYSIS\n"
            content += "-" * 13 + "\n"
            content += f"Smallest Backup: {min(sizes) / (1024*1024):.2f} MB\n"
            content += f"Largest Backup: {max(sizes) / (1024*1024):.2f} MB\n"
            content += f"Median Size: {sorted(sizes)[len(sizes)//2] / (1024*1024):.2f} MB\n\n"

        # Monthly trends
        if stats.get('storage_usage'):
            content += "MONTHLY STORAGE TRENDS\n"
            content += "-" * 22 + "\n"
            for month, size in sorted(stats['storage_usage'].items()):
                content += f"{month}: {size / (1024*1024):.2f} MB\n"
            content += "\n"

        # Backup type statistics
        if stats.get('backup_types'):
            content += "BACKUP TYPE STATISTICS\n"
            content += "-" * 22 + "\n"
            total = sum(stats['backup_types'].values())
            for backup_type, count in stats['backup_types'].items():
                percentage = (count / total * 100) if total else 0
                content += f"{backup_type}: {count} backups ({percentage:.1f}%)\n"

        return content

    def export_report(self):
        """Export integrity check report"""
        if not self.check_results:
            messagebox.showwarning("No Results", "No integrity check results to export")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Integrity Report"
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("BACKUP INTEGRITY CHECK REPORT\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                    passed = sum(1 for r in self.check_results if "PASS" in r['status'])
                    failed = len(self.check_results) - passed

                    f.write(f"SUMMARY:\n")
                    f.write(f"Total backups checked: {len(self.check_results)}\n")
                    f.write(f"Passed: {passed}\n")
                    f.write(f"Failed: {failed}\n\n")

                    f.write("DETAILED RESULTS:\n")
                    f.write("-" * 30 + "\n")

                    for result in self.check_results:
                        backup = result['backup']
                        results = result['results']
                        status = result['status']

                        f.write(f"\nBackup: {backup['filename']}\n")
                        f.write(f"Status: {status}\n")
                        f.write(f"File exists: {'Yes' if results.get('file_exists') else 'No'}\n")
                        f.write(f"Readable: {'Yes' if results.get('file_readable') else 'No'}\n")
                        f.write(f"Database valid: {'Yes' if results.get('database_valid') else 'No'}\n")
                        f.write(f"Tables accessible: {'Yes' if results.get('tables_accessible') else 'No'}\n")
                        f.write(f"Hash verified: {'Yes' if results.get('hash_verified') else 'No'}\n")

                        if results.get('errors'):
                            f.write("Errors:\n")
                            for error in results['errors']:
                                f.write(f"  - {error}\n")

                messagebox.showinfo("Export Complete", f"Report exported to {filename}")

            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export report: {e}")

    def convert_to_html(self, text_content):
        """Convert text report to HTML"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>Backup System Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; border-bottom: 2px solid #333; }
        h2 { color: #666; border-bottom: 1px solid #666; }
        pre { background-color: #f5f5f5; padding: 10px; border-radius: 5px; }
        .stats { background-color: #e8f4f8; padding: 15px; border-radius: 5px; }
    </style>
</head>
<body>
<pre>
""" + text_content + """
</pre>
</body>
</html>"""
        return html
