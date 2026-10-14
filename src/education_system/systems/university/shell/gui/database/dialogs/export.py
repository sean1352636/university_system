"""Export dialog for the data backup GUI.

Provides the ExportDialog class for exporting backups to various formats
including CSV, JSON, XML, PDF, and plain text.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.systems.university.shell.gui.database.operations.backup_ops import list_available_backups
from education_system.systems.university.shell.gui.database.operations.export_ops import export_to_csv, export_to_json, export_to_xml, export_to_pdf, export_to_txt


class ExportDialog:
    """Dialog for exporting backups"""

    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.database.dialogs.export.windows.export_backup', default="Export Backup"))
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_backups()

    def create_widgets(self):
        """Create dialog widgets"""
        # Backup selection
        select_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.export.labels.select_backup_to_export', default="Select Backup to Export"), padding=10)
        select_frame.pack(fill="x", padx=10, pady=5)

        self.backup_var = tk.StringVar()
        self.backup_combo = ttk.Combobox(select_frame, textvariable=self.backup_var,
                                        state="readonly", width=50)
        self.backup_combo.pack(fill="x", pady=5)

        # Export format
        format_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.export.labels.export_format', default="Export Format"), padding=10)
        format_frame.pack(fill="x", padx=10, pady=5)

        self.format_var = tk.StringVar(value=_t('gui.shell.database.dialogs.export.values.csv', default="csv"))
        ttk.Radiobutton(format_frame, text=_t('gui.shell.database.dialogs.export.buttons.csv_files', default="CSV Files"), variable=self.format_var, value="csv").pack(anchor="w")
        ttk.Radiobutton(format_frame, text=_t('gui.shell.database.dialogs.export.buttons.json_file', default="JSON File"), variable=self.format_var, value="json").pack(anchor="w")
        ttk.Radiobutton(format_frame, text=_t('gui.shell.database.dialogs.export.buttons.xml_file', default="XML File"), variable=self.format_var, value="xml").pack(anchor="w")
        ttk.Radiobutton(format_frame, text=_t('gui.shell.database.dialogs.export.buttons.pdf_file', default="PDF File"), variable=self.format_var, value="pdf").pack(anchor="w")
        ttk.Radiobutton(format_frame, text=_t('gui.shell.database.dialogs.export.buttons.text_file', default="Text File"), variable=self.format_var, value="txt").pack(anchor="w")

        # Output location
        output_frame = ttk.LabelFrame(self.dialog, text=_t('gui.shell.database.dialogs.export.labels.output_location', default="Output Location"), padding=10)
        output_frame.pack(fill="x", padx=10, pady=5)

        self.output_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_var, width=40).pack(side="left", fill="x", expand=True)
        ttk.Button(output_frame, text=_t('gui.shell.database.dialogs.export.buttons.browse', default="Browse"), command=self.browse_output).pack(side="right", padx=(5,0))

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.export.buttons.export', default="Export"), command=self.export).pack(side="right", padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.database.dialogs.export.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side="right")

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
            messagebox.showerror(_t('gui.shell.database.dialogs.export.dialogs.error', default="Error"), f"Failed to load backups: {e}")

    def browse_output(self):
        """Browse for output location"""
        if self.format_var.get() == "csv":
            path = filedialog.askdirectory(title=_t('gui.shell.database.dialogs.export.dialogs.select_output_directory_for_csv_files', default="Select output directory for CSV files"))
        else:
            format_type = self.format_var.get()
            filetypes_map = {
                "json": [("JSON files", "*.json")],
                "xml": [("XML files", "*.xml")],
                "pdf": [("PDF files", "*.pdf")],
                "txt": [("Text files", "*.txt")]
            }
            filetypes = filetypes_map.get(format_type, [("All files", "*.*")])
            path = filedialog.asksaveasfilename(title=_t('gui.shell.database.dialogs.export.dialogs.save_export_file', default="Save export file"), filetypes=filetypes)

        if path:
            self.output_var.set(path)

    def export(self):
        """Export selected backup"""
        if not self.backup_combo.get():
            messagebox.showwarning(_t('gui.shell.database.dialogs.export.dialogs.no_selection', default="No Selection"), _t('gui.shell.database.dialogs.export.dialogs.please_select_a_backup_to_export', default="Please select a backup to export"))
            return

        if not self.output_var.get():
            messagebox.showwarning(_t('gui.shell.database.dialogs.export.dialogs.no_output', default="No Output"), _t('gui.shell.database.dialogs.export.dialogs.please_specify_output_location', default="Please specify output location"))
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
                messagebox.showinfo(_t('gui.shell.database.dialogs.export.dialogs.success', default="Success"), f"Backup exported successfully to {output_path}")
                self.dialog.destroy()
            else:
                messagebox.showerror(_t('gui.shell.database.dialogs.export.dialogs.error', default="Error"), _t('gui.shell.database.dialogs.export.dialogs.export_operation_failed_check_logs_for_details', default="Export operation failed. Check logs for details."))

        except Exception as e:
            messagebox.showerror(_t('gui.shell.database.dialogs.export.dialogs.error', default="Error"), f"Export failed: {e}")
