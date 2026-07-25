"""Storage usage dialog for the data backup GUI.

Provides the StorageUsageDialog class for displaying storage usage information,
managing storage quotas, cleaning old backups, and removing duplicate backup files.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import os
import datetime
from pathlib import Path

from education_system.systems.university.interfaces.gui.shell.database.config import config, save_config
from education_system.systems.university.interfaces.gui.shell.database.shared_imports import logger
from education_system.systems.university.interfaces.gui.shell.database.metadata import metadata_manager
from education_system.systems.university.interfaces.gui.shell.database.operations.backup_ops import check_storage_quota, list_available_backups, deduplicate_backups, secure_delete_file


class StorageUsageDialog:
    """Dialog for showing storage usage and quota information - missing class"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Storage Usage")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_usage_data()

    def create_widgets(self):
        """Create dialog widgets"""
        # Usage summary
        summary_frame = ttk.LabelFrame(self.dialog, text="Storage Summary", padding=10)
        summary_frame.pack(fill="x", padx=10, pady=5)

        self.usage_text = scrolledtext.ScrolledText(summary_frame, height=8, wrap=tk.WORD)
        self.usage_text.pack(fill="both", expand=True)

        # Actions
        actions_frame = ttk.LabelFrame(self.dialog, text="Storage Actions", padding=10)
        actions_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(actions_frame, text="Clean Old Backups",
                  command=self.clean_old_backups).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="Remove Duplicates",
                  command=self.remove_duplicates).pack(side="left", padx=5)
        ttk.Button(actions_frame, text="Adjust Quota",
                  command=self.adjust_quota).pack(side="left", padx=5)

        # Close button
        ttk.Button(self.dialog, text="Close", command=self.dialog.destroy).pack(pady=10)

    def load_usage_data(self):
        """Load and display storage usage data"""
        try:
            quota_info = check_storage_quota()
            backups = list_available_backups()

            usage_report = "STORAGE USAGE REPORT\n"
            usage_report += "=" * 30 + "\n\n"

            usage_report += f"Total Backups: {len(backups)}\n"
            usage_report += f"Total Size: {quota_info['total_size_gb']:.2f} GB\n"
            usage_report += f"Storage Quota: {quota_info['quota_gb']} GB\n"
            usage_report += f"Usage: {quota_info['usage_percentage']:.1f}%\n"

            if quota_info['quota_exceeded']:
                usage_report += "\n\u26a0\ufe0f WARNING: Storage quota exceeded!\n"

            usage_report += f"\nBackup Directory: {config['backup_directory']}\n"

            # Backup breakdown by type
            type_usage = {}
            for backup in backups:
                backup_type = backup.get('backup_type', 'unknown')
                size = backup.get('size', 0)
                if backup_type not in type_usage:
                    type_usage[backup_type] = {'count': 0, 'size': 0}
                type_usage[backup_type]['count'] += 1
                type_usage[backup_type]['size'] += size

            if type_usage:
                usage_report += "\nBreakdown by Type:\n"
                for backup_type, info in type_usage.items():
                    size_mb = info['size'] / (1024 * 1024)
                    usage_report += f"  {backup_type}: {info['count']} backups, {size_mb:.1f} MB\n"

            # Recent activity
            recent_backups = [b for b in backups[:5]]  # Last 5
            if recent_backups:
                usage_report += "\nRecent Backups:\n"
                for backup in recent_backups:
                    usage_report += f"  {backup['date_formatted']} - {backup['size_formatted']}\n"

            self.usage_text.delete(1.0, tk.END)
            self.usage_text.insert(1.0, usage_report)

        except Exception as e:
            self.usage_text.delete(1.0, tk.END)
            self.usage_text.insert(1.0, f"Error loading usage data: {e}")

    def cleanup_old_backups_enhanced():
        """Enhanced cleanup with retention policies - missing from GUI"""
        try:
            backup_dir = Path(config["backup_directory"])
            retention = config["retention_policy"]

            # Get all backup files grouped by type
            all_backups = metadata_manager.get_backups()

            now = datetime.datetime.now()

            # Group backups by age
            daily_backups = []
            weekly_backups = []
            monthly_backups = []
            yearly_backups = []

            for backup in all_backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    age_days = (now - backup_date).days

                    if age_days <= 7:
                        daily_backups.append(backup)
                    elif age_days <= 30:
                        weekly_backups.append(backup)
                    elif age_days <= 365:
                        monthly_backups.append(backup)
                    else:
                        yearly_backups.append(backup)
                except (ValueError, KeyError):
                    # If timestamp parsing fails, treat as old backup
                    yearly_backups.append(backup)

            # Apply retention policy
            backups_to_keep = []

            # Keep recent daily backups
            daily_backups.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(daily_backups[:retention["daily_keep"]])

            # Keep weekly backups (one per week)
            weekly_by_week = {}
            for backup in weekly_backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    week_key = backup_date.strftime("%Y-W%U")
                    if week_key not in weekly_by_week:
                        weekly_by_week[week_key] = backup
                except (ValueError, KeyError):
                    pass

            weekly_kept = list(weekly_by_week.values())
            weekly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(weekly_kept[:retention["weekly_keep"]])

            # Keep monthly backups (one per month)
            monthly_by_month = {}
            for backup in monthly_backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    month_key = backup_date.strftime("%Y-%m")
                    if month_key not in monthly_by_month:
                        monthly_by_month[month_key] = backup
                except (ValueError, KeyError):
                    pass

            monthly_kept = list(monthly_by_month.values())
            monthly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(monthly_kept[:retention["monthly_keep"]])

            # Keep yearly backups (one per year)
            yearly_by_year = {}
            for backup in yearly_backups:
                try:
                    backup_date = datetime.datetime.strptime(backup["timestamp"], "%Y%m%d_%H%M%S")
                    year_key = backup_date.strftime("%Y")
                    if year_key not in yearly_by_year:
                        yearly_by_year[year_key] = backup
                except (ValueError, KeyError):
                    pass

            yearly_kept = list(yearly_by_year.values())
            yearly_kept.sort(key=lambda x: x["timestamp"], reverse=True)
            backups_to_keep.extend(yearly_kept[:retention["yearly_keep"]])

            # Remove backups not in keep list
            kept_paths = {backup["path"] for backup in backups_to_keep}

            removed_count = 0
            for backup in all_backups:
                if backup["path"] not in kept_paths:
                    try:
                        if os.path.exists(backup["path"]):
                            if config["secure_deletion"]:
                                secure_delete_file(backup["path"])
                            else:
                                os.remove(backup["path"])
                            logger.info(f"Removed old backup: {backup['path']}")
                            removed_count += 1
                    except Exception as e:
                        logger.error(f"Error removing backup {backup['path']}: {e}")

            # Update metadata
            metadata_manager.metadata["backups"] = backups_to_keep
            metadata_manager.save_metadata()

            return removed_count

        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
            return 0

    def clean_old_backups(self):
        """Clean old backups using enhanced cleanup with retention policies"""
        if messagebox.askyesno("Clean Old Backups", "Remove old backups based on retention policy?"):
            removed = StorageUsageDialog.cleanup_old_backups_enhanced()
            messagebox.showinfo("Cleanup Complete", f"Removed {removed} old backups")
            self.load_usage_data()

    def remove_duplicates(self):
        """Remove duplicate backups"""
        if messagebox.askyesno("Remove Duplicates", "Remove duplicate backup files?"):
            removed = deduplicate_backups()
            messagebox.showinfo("Deduplication Complete", f"Removed {removed} duplicate backups")
            self.load_usage_data()

    def adjust_quota(self):
        """Adjust storage quota"""
        current_quota = config.get("storage_quota_gb", 10)
        new_quota = tk.simpledialog.askfloat("Adjust Quota",
                                           f"Current quota: {current_quota} GB\nEnter new quota (GB):",
                                           minvalue=1.0, maxvalue=1000.0)
        if new_quota:
            config["storage_quota_gb"] = new_quota
            save_config()
            messagebox.showinfo("Quota Updated", f"Storage quota set to {new_quota} GB")
            self.load_usage_data()
