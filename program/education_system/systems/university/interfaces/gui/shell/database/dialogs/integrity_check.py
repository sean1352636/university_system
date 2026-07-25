"""Integrity check and advanced settings dialogs for the data backup GUI."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import datetime
import json
import threading
from pathlib import Path

from education_system.systems.university.interfaces.gui.shell.database.config import config, save_config
from education_system.systems.university.interfaces.gui.shell.database.shared_imports import logger
from education_system.systems.university.interfaces.gui.shell.database.metadata import metadata_manager
from education_system.systems.university.interfaces.gui.shell.database.operations.backup_ops import (
    validate_backup,
    list_available_backups,
)


class IntegrityCheckDialog:
    """Dialog for running integrity checks on backups - missing class"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Integrity Check")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.check_results = []

    def create_widgets(self):
        """Create dialog widgets"""
        # Controls
        controls_frame = ttk.Frame(self.dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text="Check All Backups",
                  command=self.check_all_backups).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Check Selected",
                  command=self.check_selected).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Export Report",
                  command=self.export_report).pack(side="left", padx=5)

        # Results display
        results_frame = ttk.LabelFrame(self.dialog, text="Integrity Check Results", padding=10)
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
        self.status_label = ttk.Label(self.dialog, text="Ready to check backups")
        self.status_label.pack(pady=5)

        # Close button
        ttk.Button(self.dialog, text="Close", command=self.dialog.destroy).pack(pady=10)

    def check_all_backups(self):
        """Check integrity of all backups"""
        backups = list_available_backups()
        if not backups:
            messagebox.showinfo("No Backups", "No backups found to check")
            return

        self.run_integrity_check(backups)

    def check_selected(self):
        """Check selected backups"""
        backups = list_available_backups()
        if not backups:
            messagebox.showinfo("No Backups", "No backups found to check")
            return

        dialog = tk.Toplevel(self.dialog)
        dialog.title("Select Backups to Check")
        dialog.transient(self.dialog)
        dialog.grab_set()

        ttk.Label(dialog, text="Select one or more backups to verify:").pack(anchor="w", padx=10, pady=(10, 5))

        listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, width=70, height=10)
        listbox.pack(fill="both", expand=True, padx=10)

        for backup in backups:
            display = f"{backup['date_formatted']} \u2022 {backup.get('backup_type', 'full').title()} \u2022 {backup['filename']}"
            listbox.insert(tk.END, display)

        selected_backups = []

        def confirm_selection():
            indices = listbox.curselection()
            if not indices:
                messagebox.showwarning("No Selection", "Please choose at least one backup.", parent=dialog)
                return
            for idx in indices:
                selected_backups.append(backups[idx])
            dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        ttk.Button(button_frame, text="Check", command=confirm_selection).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="right")

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
                self.status_label.config(text="Integrity check completed")

                # Show summary
                passed = sum(1 for r in self.check_results if "PASS" in r['status'])
                failed = len(self.check_results) - passed

                messagebox.showinfo("Check Complete",
                                   f"Integrity check completed\n\n"
                                   f"Passed: {passed}\n"
                                   f"Failed: {failed}")

            except Exception as e:
                messagebox.showerror("Check Error", f"Integrity check failed: {e}")
                self.status_label.config(text="Check failed")
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
        self.dialog.title("Advanced Backup Settings")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_current_settings()

    def create_widgets(self):
        """Create dialog widgets"""
        # Change detection settings
        change_frame = ttk.LabelFrame(self.dialog, text="Change Detection", padding=10)
        change_frame.pack(fill="x", padx=10, pady=5)

        self.change_detection_var = tk.BooleanVar()
        ttk.Checkbutton(change_frame, text="Enable Change Detection",
                       variable=self.change_detection_var).pack(anchor="w")

        # Deduplication settings
        dedup_frame = ttk.LabelFrame(self.dialog, text="Deduplication", padding=10)
        dedup_frame.pack(fill="x", padx=10, pady=5)

        self.deduplication_var = tk.BooleanVar()
        ttk.Checkbutton(dedup_frame, text="Enable Deduplication",
                       variable=self.deduplication_var).pack(anchor="w")

        # Performance settings
        perf_frame = ttk.LabelFrame(self.dialog, text="Performance", padding=10)
        perf_frame.pack(fill="x", padx=10, pady=5)

        self.parallel_var = tk.BooleanVar()
        ttk.Checkbutton(perf_frame, text="Enable Parallel Processing",
                       variable=self.parallel_var).pack(anchor="w")

        ttk.Label(perf_frame, text="Max Threads:").pack(anchor="w")
        self.threads_var = tk.StringVar()
        ttk.Spinbox(perf_frame, textvariable=self.threads_var,
                   from_=1, to=8, width=10).pack(anchor="w")

        ttk.Label(perf_frame, text="Bandwidth Limit (Mbps, 0=unlimited):").pack(anchor="w")
        self.bandwidth_var = tk.StringVar()
        ttk.Entry(perf_frame, textvariable=self.bandwidth_var, width=10).pack(anchor="w")

        # Storage quota
        storage_frame = ttk.LabelFrame(self.dialog, text="Storage Management", padding=10)
        storage_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(storage_frame, text="Storage Quota (GB):").pack(anchor="w")
        self.quota_var = tk.StringVar()
        ttk.Entry(storage_frame, textvariable=self.quota_var, width=10).pack(anchor="w")

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_settings).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")

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
            messagebox.showinfo("Success", "Advanced settings saved!")
            self.dialog.destroy()
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your input values: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
