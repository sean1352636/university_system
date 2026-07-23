"""Validation dialog for the data backup GUI."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import datetime
import json
import threading
from pathlib import Path

from education_system.post_18.university_system.modules.shared.gui.database.config import config, save_config
from education_system.post_18.university_system.modules.shared.gui.database.shared_imports import logger
from education_system.post_18.university_system.modules.shared.gui.database.metadata import metadata_manager
from education_system.post_18.university_system.modules.shared.gui.database.operations.backup_ops import (
    list_available_backups,
    validate_backup,
)


class ValidationDialog:
    """Dialog for backup validation"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Validate Backup")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backup to Validate", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)

        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var,
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)

        ttk.Button(select_frame, text="Validate", command=self.validate).pack(pady=5)

        # Results
        results_frame = ttk.LabelFrame(self.dialog, text="Validation Results", padding=10)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD)
        self.results_text.pack(fill="both", expand=True)

    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups

            backup_names = [f"{backup['date_formatted']} - {backup['filename']}"
                           for backup in backups]
            self.backup_combo['values'] = backup_names

            if backup_names:
                self.backup_combo.current(0)

        except Exception as e:
            self.results_text.insert(tk.END, f"Error loading backups: {e}\n")

    def validate(self):
        """Validate selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning("No Selection", "Please select a backup to validate")
            return

        try:
            index = self.backup_combo.current()
            backup = self.backups[index]

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Validating backup: {backup['filename']}\n")
            self.results_text.insert(tk.END, "Please wait...\n\n")
            self.dialog.update()

            results = validate_backup(backup['path'])

            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Validation Results for: {backup['filename']}\n")
            self.results_text.insert(tk.END, "=" * 50 + "\n\n")

            passed = "\u2713 PASS"
            failed = "\u2717 FAIL"
            self.results_text.insert(tk.END, f"File exists: {passed if results['file_exists'] else failed}\n")
            self.results_text.insert(tk.END, f"File readable: {passed if results['file_readable'] else failed}\n")
            self.results_text.insert(tk.END, f"Database valid: {passed if results['database_valid'] else failed}\n")
            self.results_text.insert(tk.END, f"Tables accessible: {passed if results['tables_accessible'] else failed}\n")
            self.results_text.insert(tk.END, f"Hash verified: {passed if results['hash_verified'] else failed}\n\n")

            if results['errors']:
                self.results_text.insert(tk.END, "ERRORS FOUND:\n")
                for error in results['errors']:
                    self.results_text.insert(tk.END, f"\u2022 {error}\n")
            else:
                self.results_text.insert(tk.END, "\u2713 No errors found - backup is valid!\n")

        except Exception as e:
            self.results_text.delete(1.0, tk.END)
            self.results_text.insert(tk.END, f"Comparison failed: {e}\n")
