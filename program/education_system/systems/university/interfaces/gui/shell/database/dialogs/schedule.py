"""Schedule dialogs for the data backup GUI.

Provides the ScheduleHistoryDialog for viewing scheduled backup history and the
ScheduleConfigDialog for configuring backup schedule frequency, timing, and type.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

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
        self.dialog.title(_t('gui.shell.database.dialogs.schedule.windows.schedule_history', default="Schedule History"))
        self.dialog.geometry("600x400")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_history()

    def create_widgets(self):
        """Create dialog widgets"""
        # History list
        list_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.schedule.labels.scheduled_backup_history', default="Scheduled Backup History"), padding=10)
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

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.refresh', default="Refresh"), command=self.load_history).pack(side="left", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.clear_history', default="Clear History"), command=self.clear_history).pack(side="left", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.close', default="Close"), command=self.dialog.destroy).pack(side="right")

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
            messagebox.showerror(_t('gui.shell.database.dialogs.schedule.dialogs.error', default="Error"), f"Failed to load schedule history: {e}")

    def clear_history(self):
        """Clear schedule history"""
        if messagebox.askyesno(_t('gui.shell.database.dialogs.schedule.dialogs.clear_history', default="Clear History"), _t('gui.shell.database.dialogs.schedule.dialogs.are_you_sure_you_want_to_clear_the_schedule_history', default="Are you sure you want to clear the schedule history?")):
            try:
                # This would clear scheduled backup records from metadata
                # For now, just clear the display
                for item in self.history_tree.get_children():
                    self.history_tree.delete(item)
                messagebox.showinfo(_t('gui.shell.database.dialogs.schedule.dialogs.success', default="Success"), _t('gui.shell.database.dialogs.schedule.dialogs.schedule_history_cleared', default="Schedule history cleared"))
            except Exception as e:
                messagebox.showerror(_t('gui.shell.database.dialogs.schedule.dialogs.error', default="Error"), f"Failed to clear history: {e}")


class ScheduleConfigDialog:
    """Dialog for configuring backup schedule"""

    def __init__(self, parent, update_callback=None):
        self.update_callback = update_callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.schedule.windows.schedule_configuration', default="Schedule Configuration"))
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        """Create dialog widgets"""
        # Frequency settings
        freq_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.schedule.labels.backup_frequency', default="Backup Frequency"), padding=10)
        freq_frame.pack(fill="x", padx=10, pady=5)

        self.frequency_var = tk.StringVar(value=config["backup_frequency"])

        ttk.Radiobutton(freq_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.daily', default="Daily"), variable=self.frequency_var, value="daily").pack(anchor="w")
        ttk.Radiobutton(freq_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.weekly', default="Weekly"), variable=self.frequency_var, value="weekly").pack(anchor="w")
        ttk.Radiobutton(freq_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.monthly', default="Monthly"), variable=self.frequency_var, value="monthly").pack(anchor="w")

        # Time settings
        time_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.schedule.labels.backup_time', default="Backup Time"), padding=10)
        time_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(time_frame, text=_t('gui.shell.database.dialogs.schedule.labels.time_24_hour_format', default="Time (24-hour format):")).pack(anchor="w")
        self.time_var = tk.StringVar(value=config["scheduled_backup_time"])
        time_entry = ttk.Entry(time_frame, textvariable=self.time_var, width=10)
        time_entry.pack(anchor="w", pady=2)
        ttk.Label(time_frame, text=_t('gui.shell.database.dialogs.schedule.labels.format_hh_mm_e_g_02_30', default="Format: HH:MM (e.g., 02:30)"), font=("Arial", 8)).pack(anchor="w")

        # Advanced scheduling
        advanced_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.schedule.labels.advanced_scheduling', default="Advanced Scheduling"), padding=10)
        advanced_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(advanced_frame, text=_t('gui.shell.database.dialogs.schedule.labels.cron_expression_optional', default="Cron Expression (optional):")).pack(anchor="w")
        self.cron_var = tk.StringVar(value=config.get("cron_schedule", ""))
        cron_entry = ttk.Entry(advanced_frame, textvariable=self.cron_var, width=30)
        cron_entry.pack(anchor="w", pady=2)
        ttk.Label(advanced_frame, text=_t('gui.shell.database.dialogs.schedule.labels.examples_0_2_daily_2am_0_2_1_weekly_monday_2am', default="Examples: '0 2 * * *' (daily 2am), '0 2 * * 1' (weekly Monday 2am)"),
                 font=("Arial", 8)).pack(anchor="w")

        # Backup type for scheduled backups
        type_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.schedule.labels.scheduled_backup_type', default="Scheduled Backup Type"), padding=10)
        type_frame.pack(fill="x", padx=10, pady=5)

        self.backup_type_var = tk.StringVar(value=config.get("backup_type", "full"))
        ttk.Radiobutton(type_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.full_backup', default="Full Backup"), variable=self.backup_type_var, value="full").pack(anchor="w")
        ttk.Radiobutton(type_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.incremental_backup', default="Incremental Backup"), variable=self.backup_type_var, value="incremental").pack(anchor="w")

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.save', default="Save"), command=self.save_schedule).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.schedule.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side="right")

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
                    messagebox.showerror(_t('gui.shell.database.dialogs.schedule.dialogs.invalid_cron', default="Invalid Cron"), _t('gui.shell.database.dialogs.schedule.dialogs.cron_expression_could_not_be_parsed_please_check_the_format', default="Cron expression could not be parsed. Please check the format."))
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

            messagebox.showinfo(_t('gui.shell.database.dialogs.schedule.dialogs.success', default="Success"), _t('gui.shell.database.dialogs.schedule.dialogs.schedule_configuration_saved', default="Schedule configuration saved!"))
            self.dialog.destroy()

        except ValueError:
            messagebox.showerror(_t('gui.shell.database.dialogs.schedule.dialogs.invalid_time', default="Invalid Time"), _t('gui.shell.database.dialogs.schedule.dialogs.please_enter_time_in_hh_mm_format_e_g_02_30', default="Please enter time in HH:MM format (e.g., 02:30)"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.schedule.dialogs.error', default="Error"), f"Failed to save schedule: {e}")
