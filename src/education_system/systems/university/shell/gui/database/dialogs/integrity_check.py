"""Integrity check and advanced settings dialogs for the data backup GUI."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import datetime
import json
import threading
from pathlib import Path

from education_system.systems.university.shell.gui.database.config import config, save_config
from education_system.systems.university.shell.gui.database.shared_imports import logger
from education_system.systems.university.shell.gui.database.metadata import metadata_manager
from education_system.systems.university.shell.gui.database.operations.backup_ops import (
    validate_backup,
    list_available_backups,
)


class IntegrityCheckDialog:
    """Dialog for running integrity checks on backups - missing class"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.integrity_check.windows.backup_integrity_check', default="Backup Integrity Check"))
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.check_results = []

    def create_widgets(self):
        """Create dialog widgets"""
        # Controls
        controls_frame = ttk.Frame(self.dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.check_all_backups', default="Check All Backups"),
                  command=self.check_all_backups).pack(side="left", padx=5)
        ttk.Button(controls_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.check_selected', default="Check Selected"),
                  command=self.check_selected).pack(side="left", padx=5)
        ttk.Button(controls_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.export_report', default="Export Report"),
                  command=self.export_report).pack(side="left", padx=5)

        # Results display
        results_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.integrity_check.labels.integrity_check_results', default="Integrity Check Results"), padding=10)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Treeview for results
        columns = ("Backup", "Status", "File Exists", "Readable", "DB Valid", "Hash Match")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=12)

        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)

        self.results_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.dialog, variable=self.progress_var,
                                          mode="determinate", length=400)
        self.progress_bar.pack(padx=10, pady=5)

        # Status label
        self.status_label = ttk.Label(self.dialog, text=_t('gui.shell.database.dialogs.integrity_check.labels.ready_to_check_backups', default="Ready to check backups"))
        self.status_label.pack(pady=5)

        # Close button
        ttk.Button(self.dialog, text=_t('gui.shell.database.dialogs.integrity_check.buttons.close', default="Close"), command=self.dialog.destroy).pack(pady=10)

    def check_all_backups(self):
        """Check integrity of all backups"""
        backups = list_available_backups()
        if not backups:
            messagebox.showinfo(_t('gui.shell.database.dialogs.integrity_check.dialogs.no_backups', default="No Backups"), _t('gui.shell.database.dialogs.integrity_check.dialogs.no_backups_found_to_check', default="No backups found to check"))
            return

        self.run_integrity_check(backups)

    def check_selected(self):
        """Check selected backups"""
        backups = list_available_backups()
        if not backups:
            messagebox.showinfo(_t('gui.shell.database.dialogs.integrity_check.dialogs.no_backups', default="No Backups"), _t('gui.shell.database.dialogs.integrity_check.dialogs.no_backups_found_to_check', default="No backups found to check"))
            return

        dialog = tk.Toplevel(self.dialog)
        dialog.title(_t('gui.shell.database.dialogs.integrity_check.windows.select_backups_to_check', default="Select Backups to Check"))
        dialog.transient(self.dialog)
        dialog.grab_set()

        ttk.Label(dialog, text=_t('gui.shell.database.dialogs.integrity_check.labels.select_one_or_more_backups_to_verify', default="Select one or more backups to verify:")).pack(anchor="w", padx=10, pady=(10, 5))

        listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, width=70, height=10)
        listbox.pack(fill="both", expand=True, padx=10)

        for backup in backups:
            display = f"{backup['date_formatted']} \u2022 {backup.get('backup_type', 'full').title()} \u2022 {backup['filename']}"
            listbox.insert(tk.END, display)

        selected_backups = []

        def confirm_selection():
            indices = listbox.curselection()
            if not indices:
                messagebox.showwarning(_t('gui.shell.database.dialogs.integrity_check.dialogs.no_selection', default="No Selection"), _t('gui.shell.database.dialogs.integrity_check.dialogs.please_choose_at_least_one_backup', default="Please choose at least one backup."), parent=dialog)
                return
            for idx in indices:
                selected_backups.append(backups[idx])
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.check', default="Check"), command=confirm_selection).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side="right")

        self.dialog.wait_window(dialog)

        if selected_backups:
            self.run_integrity_check(selected_backups)

    def run_integrity_check(self, backups):
        """Run integrity check on list of backups"""
        def check_worker():
            try:
                total = len(backups)
                self.check_results = []

                for i, backup in enumerate(backups):
                    self.status_label.config(text=f"Checking {backup['filename']}...")
                    self.progress_var.set((i / total) * 100)
                    self.dialog.update()

                    # Perform validation
                    results = validate_backup(backup['path'])

                    # Determine overall status
                    if all([results.get('file_exists', False),
                           results.get('file_readable', False),
                           results.get('database_valid', False),
                           results.get('tables_accessible', False)]):
                        status = "\u2705 PASS"
                    else:
                        status = "\u274c FAIL"

                    # Add to results
                    result_row = (
                        backup['filename'],
                        status,
                        "\u2705" if results.get('file_exists', False) else "\u274c",
                        "\u2705" if results.get('file_readable', False) else "\u274c",
                        "\u2705" if results.get('database_valid', False) else "\u274c",
                        "\u2705" if results.get('hash_verified', False) else "\u274c"
                    )

                    self.results_tree.insert("", "end", values=result_row)
                    self.check_results.append({
                        'backup': backup,
                        'results': results,
                        'status': status
                    })

                self.progress_var.set(100)
                self.status_label.config(text=_t('gui.shell.database.dialogs.integrity_check.text.integrity_check_completed', default="Integrity check completed"))

                # Show summary
                passed = sum(1 for r in self.check_results if "PASS" in r['status'])
                failed = len(self.check_results) - passed

                messagebox.showinfo(_t('gui.shell.database.dialogs.integrity_check.dialogs.check_complete', default="Check Complete"),
                                   f"Integrity check completed\n\n"
                                   f"Passed: {passed}\n"
                                   f"Failed: {failed}")

            except Exception as e:
                messagebox.showerror(_t('gui.shell.database.dialogs.integrity_check.dialogs.check_error', default="Check Error"), f"Integrity check failed: {e}")
                self.status_label.config(text=_t('gui.shell.database.dialogs.integrity_check.text.check_failed', default="Check failed"))
            finally:
                self.progress_var.set(0)

        # Run in separate thread
        check_thread = threading.Thread(target=check_worker)
        check_thread.daemon = True
        check_thread.start()


class AdvancedSettingsDialog:
    """Dialog for advanced backup settings - missing class"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.integrity_check.windows.advanced_backup_settings', default="Advanced Backup Settings"))
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        """Create dialog widgets"""
        # Change detection settings
        change_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.integrity_check.labels.change_detection', default="Change Detection"), padding=10)
        change_frame.pack(fill="x", padx=10, pady=5)

        self.change_detection_var = tk.BooleanVar()
        ttk.Checkbutton(change_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.enable_change_detection', default="Enable Change Detection"),
                       variable=self.change_detection_var).pack(anchor="w")

        # Deduplication settings
        dedup_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.integrity_check.labels.deduplication', default="Deduplication"), padding=10)
        dedup_frame.pack(fill="x", padx=10, pady=5)

        self.deduplication_var = tk.BooleanVar()
        ttk.Checkbutton(dedup_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.enable_deduplication', default="Enable Deduplication"),
                       variable=self.deduplication_var).pack(anchor="w")

        # Performance settings
        perf_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.integrity_check.labels.performance', default="Performance"), padding=10)
        perf_frame.pack(fill="x", padx=10, pady=5)

        self.parallel_var = tk.BooleanVar()
        ttk.Checkbutton(perf_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.enable_parallel_processing', default="Enable Parallel Processing"),
                       variable=self.parallel_var).pack(anchor="w")

        ttk.Label(perf_frame, text=_t('gui.shell.database.dialogs.integrity_check.labels.max_threads', default="Max Threads:")).pack(anchor="w")
        self.threads_var = tk.StringVar()
        ttk.Spinbox(perf_frame, textvariable=self.threads_var,
                   from_=1, to=8, width=10).pack(anchor="w")

        ttk.Label(perf_frame, text=_t('gui.shell.database.dialogs.integrity_check.labels.bandwidth_limit_mbps_0_unlimited', default="Bandwidth Limit (Mbps, 0=unlimited):")).pack(anchor="w")
        self.bandwidth_var = tk.StringVar()
        ttk.Entry(perf_frame, textvariable=self.bandwidth_var, width=10).pack(anchor="w")

        # Storage quota
        storage_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.integrity_check.labels.storage_management', default="Storage Management"), padding=10)
        storage_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(storage_frame, text=_t('gui.shell.database.dialogs.integrity_check.labels.storage_quota_gb', default="Storage Quota (GB):")).pack(anchor="w")
        self.quota_var = tk.StringVar()
        ttk.Entry(storage_frame, textvariable=self.quota_var, width=10).pack(anchor="w")

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.save', default="Save"), command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.integrity_check.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side="right")

    def load_current_settings(self):
        """Load current advanced settings"""
        self.change_detection_var.set(config.get("enable_change_detection", False))
        self.deduplication_var.set(config.get("enable_deduplication", False))
        self.parallel_var.set(config.get("parallel_backup", False))
        self.threads_var.set(str(config.get("max_threads", 4)))
        self.bandwidth_var.set(str(config.get("bandwidth_limit_mbps", 0)))
        self.quota_var.set(str(config.get("storage_quota_gb", 10)))

    def save_settings(self):
        """Save advanced settings"""
        try:
            config["enable_change_detection"] = self.change_detection_var.get()
            config["enable_deduplication"] = self.deduplication_var.get()
            config["parallel_backup"] = self.parallel_var.get()
            config["max_threads"] = int(self.threads_var.get())
            config["bandwidth_limit_mbps"] = int(self.bandwidth_var.get())
            config["storage_quota_gb"] = int(self.quota_var.get())

            save_config()
            messagebox.showinfo(_t('gui.shell.database.dialogs.integrity_check.dialogs.success', default="Success"), _t('gui.shell.database.dialogs.integrity_check.dialogs.advanced_settings_saved', default="Advanced settings saved!"))
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.integrity_check.dialogs.invalid_input', default="Invalid Input"), f"Please check your input values: {e}")
        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.integrity_check.dialogs.error', default="Error"), f"Failed to save settings: {e}")
