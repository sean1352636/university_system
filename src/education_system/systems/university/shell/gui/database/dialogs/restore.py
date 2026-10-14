"""Restore and table selection dialogs for the data backup GUI."""

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
    list_available_backups,
    _prepare_backup_for_read,
    _cleanup_temp_paths,
    get_database_tables_from_connection,
)
from education_system.systems.university.shell.gui.database.operations.restore_ops import (
    restore_from_backup,
)
from education_system.systems.university.infrastructure.database.db import sqlite3


class RestoreDialog:
    """Dialog for restoring from backup"""

    def __init__(self, parent, refresh_callback=None):
        self.refresh_callback = refresh_callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.restore.windows.restore_from_backup', default="Restore from Backup"))
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.restore.labels.select_backup', default="Select Backup"), padding=10)
        select_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("Date", "Type", "Size", "File")
        self.backup_tree = ttk.Treeview(select_frame, columns=columns, show="headings", height=8)

        for col in columns:
            self.backup_tree.heading(col, text=col)
            self.backup_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(select_frame, orient="vertical", command=self.backup_tree.yview)
        self.backup_tree.configure(yscrollcommand=scrollbar.set)

        self.backup_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Restore options
        options_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.restore.labels.restore_options', default="Restore Options"), padding=10)
        options_frame.pack(fill="x", padx=10, pady=5)

        self.restore_type_var = tk.StringVar(value=_t('gui.shell.database.dialogs.restore.values.full', default="full"))

        ttk.Radiobutton(options_frame, text=_t('gui.shell.database.dialogs.restore.buttons.full_restore', default="Full Restore"), variable=self.restore_type_var,
                       value="full").pack(anchor="w")
        ttk.Radiobutton(options_frame, text=_t('gui.shell.database.dialogs.restore.buttons.partial_restore_select_tables', default="Partial Restore (Select Tables)"),
                       variable=self.restore_type_var, value="partial",
                       command=self.show_table_selection).pack(anchor="w")

        # Table selection (hidden initially)
        self.table_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.restore.labels.select_tables_to_restore', default="Select Tables to Restore"), padding=10)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.restore.buttons.restore', default="Restore"), command=self.restore).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.restore.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side="right")

    def load_backups(self):
        """Load available backups"""
        try:
            backups = list_available_backups()
            self.backups = backups

            for backup in backups:
                self.backup_tree.insert("", "end", values=(
                    backup['date_formatted'],
                    backup.get('backup_type', 'full'),
                    backup['size_formatted'],
                    backup['filename']
                ))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.restore.dialogs.error', default="Error"), f"Failed to load backups: {e}")

    def show_table_selection(self):
        """Show table selection frame"""
        # Get tables from selected backup
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.shell.database.dialogs.restore.dialogs.no_selection', default="No Selection"), _t('gui.shell.database.dialogs.restore.dialogs.please_select_a_backup_first', default="Please select a backup first"))
            self.restore_type_var.set("full")
            return

        try:
            # Clear existing checkboxes
            for widget in self.table_frame.winfo_children():
                widget.destroy()

            # Get selected backup
            item = selection[0]
            index = self.backup_tree.index(item)
            backup = self.backups[index]

            readable_path = None
            temp_paths = []
            tables = []
            try:
                readable_path, temp_paths = _prepare_backup_for_read(backup['path'])
                conn = sqlite3.connect(readable_path)
                tables = get_database_tables_from_connection(conn)
                conn.close()
            finally:
                _cleanup_temp_paths(temp_paths)

            self.table_vars = {}
            for table in tables:
                var = tk.BooleanVar()
                self.table_vars[table] = var
                ttk.Checkbutton(self.table_frame, text=table, variable=var).pack(anchor="w")

            self.table_frame.pack(fill="x", padx=10, pady=5)
            self.dialog.geometry("600x700")

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.restore.dialogs.error', default="Error"), f"Failed to load tables: {e}")

    def restore(self):
        """Perform restore operation"""
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.shell.database.dialogs.restore.dialogs.no_selection', default="No Selection"), _t('gui.shell.database.dialogs.restore.dialogs.please_select_a_backup_to_restore', default="Please select a backup to restore"))
            return

        item = selection[0]
        index = self.backup_tree.index(item)
        backup = self.backups[index]

        # Confirm restore
        if not messagebox.askyesno(_t('gui.shell.database.dialogs.restore.dialogs.confirm_restore', default="Confirm Restore"),
                                  f"Are you sure you want to restore from '{backup['filename']}'?\n\n"
                                  "This will overwrite the current database!"):
            return

        try:
            target_tables = None
            if self.restore_type_var.get() == "partial":
                if hasattr(self, 'table_vars'):
                    target_tables = [table for table, var in self.table_vars.items() if var.get()]
                    if not target_tables:
                        messagebox.showwarning(_t('gui.shell.database.dialogs.restore.dialogs.no_tables', default="No Tables"), _t('gui.shell.database.dialogs.restore.dialogs.please_select_at_least_one_table_to_restore', default="Please select at least one table to restore"))
                        return

            # Perform restore
            success = restore_from_backup(backup['path'], target_tables=target_tables)

            if success:
                messagebox.showinfo(_t('gui.shell.database.dialogs.restore.dialogs.success', default="Success"), _t('gui.shell.database.dialogs.restore.dialogs.database_restored_successfully', default="Database restored successfully!"))
                if self.refresh_callback:
                    self.refresh_callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_t('gui.shell.database.dialogs.restore.dialogs.error', default="Error"), _t('gui.shell.database.dialogs.restore.dialogs.restore_operation_failed', default="Restore operation failed!"))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.restore.dialogs.error', default="Error"), f"Restore failed: {e}")

# Additional dialog classes would continue here...
# For brevity, I'll include key ones and indicate where others would be implemented

class TableSelectionDialog:
    """Dialog for selecting tables"""

    def __init__(self, parent, tables):
        self.selected_tables = []

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.restore.windows.select_tables', default="Select Tables"))
        self.dialog.geometry("300x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Table selection
        frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.restore.labels.available_tables', default="Available Tables"), padding=10)
        frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.table_vars = {}
        for table in tables:
            var = tk.BooleanVar()
            self.table_vars[table] = var
            ttk.Checkbutton(frame, text=table, variable=var).pack(anchor="w")

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.restore.buttons.select_all', default="Select All"), command=self.select_all).pack(side="left")
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.restore.buttons.clear_all', default="Clear All"), command=self.clear_all).pack(side="left", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.restore.buttons.ok', default="OK"), command=self.ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.restore.buttons.cancel', default="Cancel"), command=self.cancel).pack(side="right")

        parent.wait_window(self.dialog)

    def select_all(self):
        """Select all tables"""
        for var in self.table_vars.values():
            var.set(True)

    def clear_all(self):
        """Clear all selections"""
        for var in self.table_vars.values():
            var.set(False)

    def ok(self):
        """OK button handler"""
        self.selected_tables = [table for table, var in self.table_vars.items() if var.get()]
        self.dialog.destroy()

    def cancel(self):
        """Cancel button handler"""
        self.selected_tables = []
        self.dialog.destroy()
