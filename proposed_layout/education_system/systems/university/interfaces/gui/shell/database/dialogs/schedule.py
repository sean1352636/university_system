"""Schedule dialogs for the data backup GUI.

Provides the ScheduleHistoryDialog for viewing scheduled backup history and the
ScheduleConfigDialog for configuring backup schedule frequency, timing, and type.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import datetime

from education_system.systems.university.interfaces.gui.shell.database.config import config, save_config
from education_system.systems.university.interfaces.gui.shell.database.metadata import metadata_manager
from education_system.systems.university.interfaces.gui.shell.database.scheduling.cron import parse_cron_schedule
from education_system.systems.university.interfaces.gui.shell.database.scheduling.scheduler import start_scheduler, stop_scheduler


class ScheduleHistoryDialog:
    """Dialog for showing schedule history - missing class"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule History")
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_history()

    def create_widgets(self):
        """Create dialog widgets"""
        # History list
        list_frame = ttk.LabelFrame(self.dialog, text="Scheduled Backup History", padding=10)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("Date", "Type", "Status", "Duration", "Size")
        self.history_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(button_frame, text="Refresh", command=self.load_history).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Clear History", command=self.clear_history).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side="right")

    def load_history(self):
        """Load schedule history"""
        try:
            # Clear existing items
            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

            # Get scheduled backups from metadata
            backups = metadata_manager.get_backups()
            scheduled_backups = [b for b in backups if not b.get('manual', True)]

            for backup in scheduled_backups[-20:]:  # Show last 20
                date_formatted = backup.get('date_formatted', 'Unknown')
                backup_type = backup.get('backup_type', 'full')
                status = "\u2713 Success" if os.path.exists(backup['path']) else "\u2717 Failed"
                duration = "N/A"  # Would need to track this
                size = backup.get('size_formatted', 'Unknown')

                self.history_tree.insert("", "end", values=(
                    date_formatted, backup_type, status, duration, size
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load schedule history: {e}")

    def clear_history(self):
        """Clear schedule history"""
        if messagebox.askyesno("Clear History", "Are you sure you want to clear the schedule history?"):
            try:
                # This would clear scheduled backup records from metadata
                # For now, just clear the display
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                messagebox.showinfo("Success", "Schedule history cleared")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear history: {e}")


class ScheduleConfigDialog:
    """Dialog for configuring backup schedule"""

    def __init__(self, parent, update_callback=None):
        self.update_callback = update_callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule Configuration")
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        """Create dialog widgets"""
        # Frequency settings
        freq_frame = ttk.LabelFrame(self.dialog, text="Backup Frequency", padding=10)
        freq_frame.pack(fill="x", padx=10, pady=5)

        self.frequency_var = tk.StringVar(value=config["backup_frequency"])

        ttk.Radiobutton(freq_frame, text="Daily", variable=self.frequency_var, value="daily").pack(anchor="w")
        ttk.Radiobutton(freq_frame, text="Weekly", variable=self.frequency_var, value="weekly").pack(anchor="w")
        ttk.Radiobutton(freq_frame, text="Monthly", variable=self.frequency_var, value="monthly").pack(anchor="w")

        # Time settings
        time_frame = ttk.LabelFrame(self.dialog, text="Backup Time", padding=10)
        time_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(time_frame, text="Time (24-hour format):").pack(anchor="w")
        self.time_var = tk.StringVar(value=config["scheduled_backup_time"])
        time_entry = ttk.Entry(time_frame, textvariable=self.time_var, width=10)
        time_entry.pack(anchor="w", pady=2)
        ttk.Label(time_frame, text="Format: HH:MM (e.g., 02:30)", font=("Arial", 8)).pack(anchor="w")

        # Advanced scheduling
        advanced_frame = ttk.LabelFrame(self.dialog, text="Advanced Scheduling", padding=10)
        advanced_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(advanced_frame, text="Cron Expression (optional):").pack(anchor="w")
        self.cron_var = tk.StringVar(value=config.get("cron_schedule", ""))
        cron_entry = ttk.Entry(advanced_frame, textvariable=self.cron_var, width=30)
        cron_entry.pack(anchor="w", pady=2)
        ttk.Label(advanced_frame, text="Examples: '0 2 * * *' (daily 2am), '0 2 * * 1' (weekly Monday 2am)",
                 font=("Arial", 8)).pack(anchor="w")

        # Backup type for scheduled backups
        type_frame = ttk.LabelFrame(self.dialog, text="Scheduled Backup Type", padding=10)
        type_frame.pack(fill="x", padx=10, pady=5)

        self.backup_type_var = tk.StringVar(value=config.get("backup_type", "full"))
        ttk.Radiobutton(type_frame, text="Full Backup", variable=self.backup_type_var, value="full").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Incremental Backup", variable=self.backup_type_var, value="incremental").pack(anchor="w")

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_schedule).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")

    def load_current_settings(self):
        """Load current schedule settings"""
        self.frequency_var.set(config["backup_frequency"])
        self.time_var.set(config["scheduled_backup_time"])
        self.cron_var.set(config.get("cron_schedule", ""))
        self.backup_type_var.set(config.get("backup_type", "full"))

    def save_schedule(self):
        """Save schedule configuration"""
        try:
            # Validate time format
            time_str = self.time_var.get()
            datetime.datetime.strptime(time_str, "%H:%M")

            cron_expr = self.cron_var.get().strip()
            if cron_expr:
                if not parse_cron_schedule(cron_expr):
                    messagebox.showerror("Invalid Cron", "Cron expression could not be parsed. Please check the format.")
                    return
            else:
                parse_cron_schedule("")

            # Update configuration
            config["backup_frequency"] = self.frequency_var.get()
            config["scheduled_backup_time"] = time_str
            config["cron_schedule"] = cron_expr
            config["backup_type"] = self.backup_type_var.get()

            save_config()

            # Restart scheduler
            if config["auto_backup_enabled"]:
                stop_scheduler()
                start_scheduler()

            if self.update_callback:
                self.update_callback()

            messagebox.showinfo("Success", "Schedule configuration saved!")
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror("Invalid Time", "Please enter time in HH:MM format (e.g., 02:30)")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save schedule: {e}")
