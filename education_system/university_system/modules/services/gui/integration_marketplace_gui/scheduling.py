"""Scheduling and automation methods for IntegrationMarketplaceGUI."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json
import logging

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.activity_logger import log_activity
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)


class SchedulingMixin:
    """Mixin providing scheduling and automation methods."""

    def schedule_sync(self):
        """Set up scheduled sync jobs with cron-like configuration"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to schedule")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Schedule Sync: {integration_name}")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Configure Sync Schedule for: {integration_name}",
                     style='Title.TLabel').pack(pady=10)

            # Frequency selection
            ttk.Label(dialog, text="Sync Frequency:").pack(anchor='w', padx=10, pady=5)
            frequency_var = tk.StringVar(value='daily')
            freq_frame = ttk.Frame(dialog)
            freq_frame.pack(fill='x', padx=10, pady=5)

            for freq in ['hourly', 'daily', 'weekly', 'monthly', 'manual']:
                ttk.Radiobutton(freq_frame, text=freq.title(), variable=frequency_var,
                               value=freq).pack(side='left', padx=10)

            # Time of day
            ttk.Label(dialog, text="Time of Day (HH:MM):").pack(anchor='w', padx=10, pady=5)
            time_var = tk.StringVar(value="02:00")
            ttk.Entry(dialog, textvariable=time_var, width=10).pack(anchor='w', padx=10, pady=5)

            # Days of week (for weekly)
            ttk.Label(dialog, text="Days (for weekly, comma-separated 0-6):").pack(anchor='w', padx=10, pady=5)
            days_var = tk.StringVar(value="1,3,5")
            ttk.Entry(dialog, textvariable=days_var, width=20).pack(anchor='w', padx=10, pady=5)

            # Cron expression (advanced)
            ttk.Label(dialog, text="Cron Expression (advanced, optional):").pack(anchor='w', padx=10, pady=5)
            cron_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=cron_var, width=30).pack(anchor='w', padx=10, pady=5)

            def save_schedule():
                try:
                    frequency = frequency_var.get()
                    time_of_day = time_var.get()
                    cron_expression = cron_var.get().strip() or None

                    schedule_config = {
                        'frequency': frequency,
                        'time_of_day': time_of_day,
                        'cron_expression': cron_expression,
                        'created_at': datetime.now().isoformat()
                    }

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET sync_frequency = ?, configuration = json_set(
                                COALESCE(configuration, '{}'),
                                '$.schedule', ?
                            )
                            WHERE install_id = ?
                        ''', (frequency, json.dumps(schedule_config), install_id))

                    log_activity('schedule', 'installed_integration', install_id,
                                details={'frequency': frequency, 'time': time_of_day})

                    messagebox.showinfo(_t("common.success"), f"Sync schedule configured!\n\nFrequency: {frequency}\nTime: {time_of_day}")
                    dialog.destroy()
                    self.load_installed()

                except Exception as e:
                    logger.error(f"Error saving schedule: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to save schedule: {e}")

            ttk.Button(dialog, text="Save Schedule", command=save_schedule).pack(pady=20)

        except Exception as e:
            logger.error(f"Error opening schedule dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open schedule dialog: {e}")

    def view_scheduled_tasks(self):
        """View/manage all scheduled sync tasks"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("integration_marketplace.dialogs.view_scheduled_tasks"))
            dialog.geometry("900x500")
            dialog.transient(self.root)

            ttk.Label(dialog, text="Scheduled Sync Tasks",
                     style='Title.TLabel').pack(pady=10)

            # Tasks tree
            tree_frame = ttk.Frame(dialog)
            tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

            columns = ('install_id', 'integration', 'frequency', 'time', 'enabled', 'last_sync', 'paused')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

            for col in columns:
                tree.heading(col, text=col.replace('_', ' ').title())
                tree.column(col, width=110)

            tree.column('integration', width=180)

            vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)

            tree.pack(side='left', fill='both', expand=True)
            vsb.pack(side='right', fill='y')

            # Load scheduled tasks
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ii.install_id, ic.integration_name, ii.sync_frequency,
                           ii.configuration, ii.is_enabled, ii.last_sync_date
                    FROM installed_integrations ii
                    JOIN integration_catalog ic ON ii.integration_id = ic.integration_id
                    WHERE ii.status = 'active' AND ii.sync_frequency != 'manual'
                ''')
                tasks = cursor.fetchall()

            for task in tasks:
                config = json.loads(task[3]) if task[3] else {}
                schedule = config.get('schedule', {})
                tree.insert('', 'end', values=(
                    task[0], task[1], task[2],
                    schedule.get('time_of_day', 'Not set'),
                    _t("common.yes") if task[4] else _t("common.no"),
                    task[5][:16] if task[5] else _t("common.never"),
                    _t("common.yes") if schedule.get('paused') else _t("common.no")
                ))

            ttk.Button(dialog, text=_t("common.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing scheduled tasks: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to view scheduled tasks: {e}")

    def pause_scheduled_syncs(self):
        """Temporarily pause all scheduled syncs"""
        try:
            selected = self.installed_tree.selection()

            if selected:
                # Pause selected integrations
                install_ids = [self.installed_tree.item(item)['values'][0] for item in selected]
                msg = f"Pause scheduled syncs for {len(install_ids)} selected integration(s)?"
            else:
                # Pause all
                install_ids = None
                msg = "Pause ALL scheduled syncs?\n\nThis will pause syncs for all integrations."

            if not messagebox.askyesno("Confirm Pause", msg):
                return

            with transaction() as conn:
                cursor = conn.cursor()

                if install_ids:
                    for install_id in install_ids:
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET configuration = json_set(
                                COALESCE(configuration, '{}'),
                                '$.schedule.paused', 1
                            )
                            WHERE install_id = ?
                        ''', (install_id,))
                    paused_count = len(install_ids)
                else:
                    cursor.execute('''
                        UPDATE installed_integrations
                        SET configuration = json_set(
                            COALESCE(configuration, '{}'),
                            '$.schedule.paused', 1
                        )
                        WHERE sync_frequency != 'manual'
                    ''')
                    paused_count = cursor.rowcount

            log_activity('pause', 'scheduled_syncs', None,
                        details={'paused_count': paused_count})

            messagebox.showinfo("Syncs Paused", f"Paused {paused_count} scheduled sync(s)")
            self.load_installed()

        except Exception as e:
            logger.error(f"Error pausing syncs: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to pause syncs: {e}")

    def set_maintenance_window(self):
        """Define maintenance windows when syncs won't run"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Set Maintenance Window")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Configure Maintenance Window",
                     style='Title.TLabel').pack(pady=10)

            ttk.Label(dialog, text="Start Time (HH:MM):").pack(anchor='w', padx=10, pady=5)
            start_var = tk.StringVar(value="22:00")
            ttk.Entry(dialog, textvariable=start_var, width=10).pack(anchor='w', padx=10)

            ttk.Label(dialog, text="End Time (HH:MM):").pack(anchor='w', padx=10, pady=5)
            end_var = tk.StringVar(value="06:00")
            ttk.Entry(dialog, textvariable=end_var, width=10).pack(anchor='w', padx=10)

            ttk.Label(dialog, text="Days of Week:").pack(anchor='w', padx=10, pady=5)
            days_frame = ttk.Frame(dialog)
            days_frame.pack(fill='x', padx=10, pady=5)

            day_vars = {}
            for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                day_vars[day] = tk.BooleanVar(value=day in ['Saturday', 'Sunday'])
                ttk.Checkbutton(days_frame, text=day[:3], variable=day_vars[day]).pack(side='left', padx=5)

            def save_window():
                try:
                    start_time = start_var.get()
                    end_time = end_var.get()
                    days_of_week = [day for day, var in day_vars.items() if var.get()]

                    window = {
                        'start_time': start_time,
                        'end_time': end_time,
                        'days_of_week': days_of_week,
                        'created_at': datetime.now().isoformat()
                    }

                    config_path = str(paths.MAINTENANCE_WINDOWS_FILE)
                    os.makedirs(os.path.dirname(config_path), exist_ok=True)

                    windows = []
                    if os.path.exists(config_path):
                        with open(config_path, 'r') as f:
                            windows = json.load(f)

                    windows.append(window)

                    with open(config_path, 'w') as f:
                        json.dump(windows, f, indent=2)

                    log_activity('create', 'maintenance_window', None,
                                details={'start': start_time, 'end': end_time, 'days': days_of_week})

                    messagebox.showinfo(_t("common.success"),
                                       f"Maintenance window configured!\n\n"
                                       f"Time: {start_time} - {end_time}\n"
                                       f"Days: {', '.join(days_of_week)}")
                    dialog.destroy()

                except Exception as e:
                    logger.error(f"Error saving maintenance window: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to save: {e}")

            ttk.Button(dialog, text="Save Maintenance Window", command=save_window).pack(pady=20)

        except Exception as e:
            logger.error(f"Error opening maintenance window dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")

    def configure_retry_policy(self):
        """Set retry attempts and backoff for failed syncs"""
        try:
            selected = self.installed_tree.selection()
            if not selected:
                messagebox.showwarning(_t("common.warning"), "Please select an integration to configure retry policy")
                return

            install_id = self.installed_tree.item(selected[0])['values'][0]
            integration_name = self.installed_tree.item(selected[0])['values'][1]

            dialog = tk.Toplevel(self.root)
            dialog.title(f"Retry Policy: {integration_name}")
            dialog.geometry("400x300")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Configure Retry Policy",
                     style='Title.TLabel').pack(pady=10)

            ttk.Label(dialog, text="Max Retry Attempts:").pack(anchor='w', padx=10, pady=5)
            retries_var = tk.StringVar(value="3")
            ttk.Spinbox(dialog, from_=0, to=10, textvariable=retries_var, width=10).pack(anchor='w', padx=10)

            ttk.Label(dialog, text="Initial Backoff (seconds):").pack(anchor='w', padx=10, pady=5)
            backoff_var = tk.StringVar(value="60")
            ttk.Entry(dialog, textvariable=backoff_var, width=10).pack(anchor='w', padx=10)

            ttk.Label(dialog, text="Backoff Multiplier:").pack(anchor='w', padx=10, pady=5)
            multiplier_var = tk.StringVar(value="2.0")
            ttk.Entry(dialog, textvariable=multiplier_var, width=10).pack(anchor='w', padx=10)

            def save_policy():
                try:
                    policy = {
                        'max_retries': int(retries_var.get()),
                        'backoff_seconds': int(backoff_var.get()),
                        'backoff_multiplier': float(multiplier_var.get())
                    }

                    with transaction() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE installed_integrations
                            SET configuration = json_set(
                                COALESCE(configuration, '{}'),
                                '$.retry_policy', ?
                            )
                            WHERE install_id = ?
                        ''', (json.dumps(policy), install_id))

                    log_activity('configure', 'retry_policy', install_id, details=policy)

                    messagebox.showinfo(_t("common.success"),
                                       f"Retry policy configured!\n\n"
                                       f"Max Retries: {policy['max_retries']}\n"
                                       f"Backoff: {policy['backoff_seconds']}s x {policy['backoff_multiplier']}")
                    dialog.destroy()

                except Exception as e:
                    logger.error(f"Error saving retry policy: {e}")
                    messagebox.showerror(_t("common.error"), f"Failed to save: {e}")

            ttk.Button(dialog, text="Save Retry Policy", command=save_policy).pack(pady=20)

        except Exception as e:
            logger.error(f"Error opening retry policy dialog: {e}")
            messagebox.showerror(_t("common.error"), f"Failed to open dialog: {e}")
