"""Export dialog for the data backup GUI.

Provides the ExportDialog class for exporting backups to various formats
including CSV, JSON, XML, PDF, and plain text.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.university_system.modules.shared.gui.database.operations.backup_ops import list_available_backups
from education_system.university_system.modules.shared.gui.database.operations.export_ops import export_to_csv, export_to_json, export_to_xml, export_to_pdf, export_to_txt


class ExportDialog:
    """Dialog for exporting backups"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Backup")
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text="Select Backup to Export", padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)

        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var,
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)

        # Export format
        format_frame = ttk.LabelFrame(self.dialog, text="Export Format", padding=10)
        format_frame.pack(fill="x", padx=10, pady=5)

        self.format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV Files", variable=self.format_var, value="csv").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="JSON File", variable=self.format_var, value="json").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="XML File", variable=self.format_var, value="xml").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="PDF File", variable=self.format_var, value="pdf").pack(anchor="w")
        ttk.Radiobutton(format_frame, text="Text File", variable=self.format_var, value="txt").pack(anchor="w")

        # Output location
        output_frame = ttk.LabelFrame(self.dialog, text="Output Location", padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)

        self.output_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_var, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(output_frame, text="Browse", command=self.browse_output).pack(side="right", padx=(5,0))

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text="Export", command=self.export).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side="right")

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
            messagebox.showerror("Error", f"Failed to load backups: {e}")

    def browse_output(self):
        """Browse for output location"""
        if self.format_var.get() == "csv":
            path = filedialog.askdirectory(title="Select output directory for CSV files")
        else:
            format_type = self.format_var.get()
            filetypes_map = {
                "json": [("JSON files", "*.json")],
                "xml": [("XML files", "*.xml")],
                "pdf": [("PDF files", "*.pdf")],
                "txt": [("Text files", "*.txt")]
            }
            filetypes = filetypes_map.get(format_type, [("All files", "*.*")])
            path = filedialog.asksaveasfilename(title="Save export file", filetypes=filetypes)

        if path:
            self.output_var.set(path)

    def export(self):
        """Export selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning("No Selection", "Please select a backup to export")
            return

        if not self.output_var.get():
            messagebox.showwarning("No Output", "Please specify output location")
            return

        try:
            index = self.backup_combo.current()
            backup = self.backups[index]
            format_type = self.format_var.get()
            output_path = self.output_var.get()

            success = False
            if format_type == "csv":
                success = export_to_csv(backup['path'], output_path)
            elif format_type == "json":
                success = export_to_json(backup['path'], output_path)
            elif format_type == "xml":
                success = export_to_xml(backup['path'], output_path)
            elif format_type == "pdf":
                success = export_to_pdf(backup['path'], output_path)
            elif format_type == "txt":
                success = export_to_txt(backup['path'], output_path)

            if success:
                messagebox.showinfo("Success", f"Backup exported successfully to {output_path}")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Export operation failed. Check logs for details.")

        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")
