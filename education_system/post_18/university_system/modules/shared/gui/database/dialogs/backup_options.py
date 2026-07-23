"""Backup options and backup viewer dialogs for the data backup GUI."""
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
    get_database_tables,
    list_available_backups,
    validate_backup,
    secure_delete_file,
)


class BackupOptionsDialog:
    """Dialog for selecting backup options"""

    def __init__(self, parent):
        self.result = None
        self.backup_type = "full"
        self.selected_tables = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Options")
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.dialog.protocol("WM_DELETE_WINDOW", self.cancel)

        # Center dialog
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

        # Wait for dialog to close
        parent.wait_window(self.dialog)

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup type selection
        type_frame = ttk.LabelFrame(self.dialog, text="Backup Type", padding=10)
        type_frame.pack(fill="x", padx=10, pady=5)

        self.type_var = tk.StringVar(value="full")

        ttk.Radiobutton(type_frame, text="Full Backup", variable=self.type_var,
                       value="full").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Incremental Backup", variable=self.type_var,
                       value="incremental").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Schema Only", variable=self.type_var,
                       value="schema").pack(anchor="w")
        ttk.Radiobutton(type_frame, text="Selective Tables", variable=self.type_var,
                       value="selective", command=self.show_table_selection).pack(anchor="w")

        # Table selection frame (hidden initially)
        self.table_frame = ttk.LabelFrame(self.dialog, text="Select Tables", padding=10)

        # Get available tables
        try:
            tables = get_database_tables()
            self.table_vars = {}

            for table in tables:
                var = tk.BooleanVar()
                self.table_vars[table] = var
                ttk.Checkbutton(self.table_frame, text=table, variable=var).pack(anchor="w")
        except Exception:
            ttk.Label(self.table_frame, text="No tables found or database not accessible").pack()

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Create Backup", command=self.ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel).pack(side="right")

    def show_table_selection(self):
        """Show table selection frame"""
        self.table_frame.pack(fill="x", padx=10, pady=5)
        self.dialog.geometry("400x500")

    def ok(self):
        """OK button handler"""
        self.backup_type = self.type_var.get()

        if self.backup_type == "selective":
            self.selected_tables = [table for table, var in self.table_vars.items() if var.get()]
            if not self.selected_tables:
                messagebox.showwarning("No Tables", "Please select at least one table")
                return

        self.result = True
        self.dialog.destroy()

    def cancel(self):
        """Cancel button handler"""
        self.result = False
        self.dialog.destroy()


class BackupViewerDialog:
    """Dialog for viewing backup details"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Backup Viewer")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        # Controls frame
        controls_frame = ttk.Frame(self.dialog)
        controls_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(controls_frame, text="Refresh", command=self.load_backups).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Delete Selected", command=self.delete_backup).pack(side="left", padx=5)
        ttk.Button(controls_frame, text="Validate Selected", command=self.validate_backup).pack(side="left", padx=5)

        # Filter frame
        filter_frame = ttk.Frame(self.dialog)
        filter_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(filter_frame, text="Filter by type:").pack(side="left")
        self.filter_var = tk.StringVar(value="All")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self.filter_var,
                                   values=["All", "full", "incremental", "schema", "selective"],
                                   state="readonly", width=15)
        filter_combo.pack(side="left", padx=5)
        filter_combo.bind("<<ComboboxSelected>>", self.apply_filter)

        # Backup list
        list_frame = ttk.Frame(self.dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("ID", "Type", "Date", "Size", "File", "Encrypted", "Cloud", "Status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=80)

        # Scrollbars
        v_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        # Details frame
        details_frame = ttk.LabelFrame(self.dialog, text="Backup Details", padding=10)
        details_frame.pack(fill="x", padx=10, pady=5)

        self.details_text = scrolledtext.ScrolledText(details_frame, height=8, wrap=tk.WORD)
        self.details_text.pack(fill="both", expand=True)

        # Bind selection event
        self.tree.bind("<<TreeviewSelect>>", self.show_details)

    def load_backups(self):
        """Load backup list"""
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Get backup list
            backups = list_available_backups()

            # Store backups for reference
            self.backups = backups
            self.backup_items = {}  # Map tree items to backup data

            # Populate tree
            for backup in backups:
                encrypted = "Yes" if backup.get('encrypted', False) else "No"
                cloud = "Yes" if backup.get('cloud_uploaded', False) else "No"
                status = "Exists" if os.path.exists(backup['path']) else "Missing"

                item = self.tree.insert("", "end", values=(
                    backup['id'],
                    backup.get('backup_type', 'full'),
                    backup['date_formatted'],
                    backup['size_formatted'],
                    backup['filename'],
                    encrypted,
                    cloud,
                    status
                ))

                # Store backup data with item ID
                self.backup_items[item] = backup

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load backups: {e}")

    def apply_filter(self, event=None):
        """Apply filter to backup list"""
        filter_type = self.filter_var.get()

        # Clear current items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Filter and populate
        for backup in self.backups:
            if filter_type == "All" or backup.get('backup_type', 'full') == filter_type:
                encrypted = "Yes" if backup.get('encrypted', False) else "No"
                cloud = "Yes" if backup.get('cloud_uploaded', False) else "No"
                status = "Exists" if os.path.exists(backup['path']) else "Missing"

                self.tree.insert("", "end", values=(
                    backup['id'],
                    backup.get('backup_type', 'full'),
                    backup['date_formatted'],
                    backup['size_formatted'],
                    backup['filename'],
                    encrypted,
                    cloud,
                    status
                ))

    def show_details(self, event=None):
        """Show details for selected backup"""
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        values = self.tree.item(item, "values")

        # Find the backup data
        backup_id = int(values[0])
        backup = None
        for b in self.backups:
            if b['id'] == backup_id:
                backup = b
                break

        if backup:
            details = "Backup Details:\n"
            details += f"File: {backup['filename']}\n"
            details += f"Path: {backup['path']}\n"
            details += f"Type: {backup.get('backup_type', 'full')}\n"
            details += f"Date: {backup['date_formatted']}\n"
            details += f"Size: {backup['size_formatted']}\n"
            details += f"Manual: {'Yes' if backup.get('manual', False) else 'No'}\n"
            details += f"Encrypted: {'Yes' if backup.get('encrypted', False) else 'No'}\n"
            details += f"Compressed: {'Yes' if backup.get('compressed', False) else 'No'}\n"
            details += f"Cloud Uploaded: {'Yes' if backup.get('cloud_uploaded', False) else 'No'}\n"
            details += f"Remote Uploaded: {'Yes' if backup.get('remote_uploaded', False) else 'No'}\n"

            if backup.get('file_hash'):
                details += f"File Hash: {backup['file_hash']}\n"

            if backup.get('operation'):
                details += f"Operation: {backup['operation']}\n"

            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(1.0, details)

    def delete_backup(self):
        """Delete selected backup"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup to delete")
            return

        item = selection[0]
        values = self.tree.item(item, "values")
        filename = values[4]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            try:
                backup_id = int(values[0])
                backup = None
                for b in self.backups:
                    if b['id'] == backup_id:
                        backup = b
                        break

                if backup:
                    # Use centralized delete_backup function from data_backup module
                    # This ensures consistent behavior between CLI and GUI
                    try:
                        from education_system.post_18.university_system.infrastructure.database.data_backup import delete_backup as delete_backup_func
                        success = delete_backup_func(backup['path'])
                    except ImportError:
                        # Fallback to inline implementation if import fails
                        if os.path.exists(backup['path']):
                            if config["secure_deletion"]:
                                secure_delete_file(backup['path'])
                            else:
                                os.remove(backup['path'])

                            # Remove from metadata
                            metadata_manager.metadata["backups"] = [
                                b for b in metadata_manager.metadata["backups"]
                                if b['path'] != backup['path']
                            ]
                            metadata_manager.save_metadata()
                            success = True
                        else:
                            success = False

                    if success:
                        messagebox.showinfo("Success", "Backup deleted successfully and removed from list")
                        self.load_backups()
                    else:
                        messagebox.showerror("Error", "Failed to delete backup")
                else:
                    messagebox.showerror("Error", "Backup not found")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete backup: {e}")

    def validate_backup(self):
        """Validate selected backup"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a backup to validate")
            return

        item = selection[0]
        values = self.tree.item(item, "values")

        try:
            backup_id = int(values[0])
            backup = None
            for b in self.backups:
                if b['id'] == backup_id:
                    backup = b
                    break

            if backup:
                results = validate_backup(backup['path'])

                check = "\u2713"
                cross = "\u2717"
                message = "Validation Results:\n\n"
                message += f"File exists: {check if results['file_exists'] else cross}\n"
                message += f"File readable: {check if results['file_readable'] else cross}\n"
                message += f"Database valid: {check if results['database_valid'] else cross}\n"
                message += f"Tables accessible: {check if results['tables_accessible'] else cross}\n"
                message += f"Hash verified: {check if results['hash_verified'] else cross}\n"

                if results['errors']:
                    message += "\nErrors:\n"
                    for error in results['errors']:
                        message += f"\u2022 {error}\n"

                messagebox.showinfo("Validation Results", message)

        except Exception as e:
            messagebox.showerror("Error", f"Validation failed: {e}")
