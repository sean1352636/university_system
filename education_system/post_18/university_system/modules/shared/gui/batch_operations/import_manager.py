"""Import operations manager for batch operations GUI."""
import os
import datetime
import json
import threading
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from education_system.post_18.university_system.modules.shared.gui.batch_operations.constants import (
    _t, logger,
    compulsory_module_1, compulsory_module_2,
    CS_optional_module_1, CS_optional_module_2,
    DS_optional_module_1, DS_optional_module_2,
)
from education_system.post_18.university_system.modules.shared.gui.batch_operations.progress_dialog import GUIProgressDialog


class ImportManager:
    """Manages import operations for BatchOperationsGUI."""

    def __init__(self, gui):
        self.gui = gui

    # ========================================
    # IMPORT OPERATIONS (GUI IMPLEMENTATIONS)
    # ========================================

    def import_from_csv(self):
        """GUI version of CSV import"""
        file_path = filedialog.askopenfilename(
            title=_t("batch_ops.dialogs.select_csv"),
            filetypes=[(_t("batch_ops.filetypes.csv"), "*.csv"), (_t("batch_ops.filetypes.all"), "*.*")]
        )

        if not file_path:
            return

        # Run import in separate thread
        def import_worker():
            try:
                self.gui.message_queue.put({'type': 'status', 'text': f'Importing from {os.path.basename(file_path)}...'})

                # Create progress dialog
                progress_dialog = GUIProgressDialog(self.gui.root, "CSV Import", "Importing CSV data")

                # Use backend method for actual import
                result = self.gui.backend.import_from_csv_file(file_path, progress_callback=progress_dialog.update_progress)

                progress_dialog.close()

                # Show results
                self.show_import_results(result)

            except Exception as e:
                self.gui.message_queue.put({'type': 'error', 'text': f'Import failed: {str(e)}'})

        thread = threading.Thread(target=import_worker)
        thread.daemon = True
        thread.start()

    def import_from_excel(self):
        """GUI version of Excel import"""
        import pandas as pd
        file_path = filedialog.askopenfilename(
            title=_t("batch_ops.dialogs.select_excel"),
            filetypes=[(_t("batch_ops.filetypes.excel"), "*.xlsx *.xls"), (_t("batch_ops.filetypes.all"), "*.*")]
        )

        if not file_path:
            return

        # Check for multiple sheets first
        try:
            xl_file = pd.ExcelFile(file_path)
            sheet_name = None

            if len(xl_file.sheet_names) > 1:
                # Show sheet selection dialog
                sheet_name = self.select_excel_sheet(xl_file.sheet_names)
                if not sheet_name:
                    return
            else:
                sheet_name = xl_file.sheet_names[0]

            # Run import in separate thread
            def import_worker():
                try:
                    self.gui.message_queue.put({'type': 'status', 'text': f'Importing from {os.path.basename(file_path)}...'})

                    progress_dialog = GUIProgressDialog(self.gui.root, "Excel Import", f"Importing from sheet: {sheet_name}")

                    result = self.gui.backend.import_from_excel_file(file_path, sheet_name, progress_callback=progress_dialog.update_progress)

                    progress_dialog.close()
                    self.show_import_results(result)

                except Exception as e:
                    self.gui.message_queue.put({'type': 'error', 'text': f'Import failed: {str(e)}'})

            thread = threading.Thread(target=import_worker)
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror(_t("batch_ops.dialogs.error"), _t("batch_ops.errors.excel_read_failed") + f": {str(e)}")

    def select_excel_sheet(self, sheet_names):
        """Show dialog to select Excel sheet"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.dialogs.select_sheet"))
        dialog.geometry("300x200")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        selected_sheet = tk.StringVar()

        ttk.Label(dialog, text=_t("batch_ops.dialogs.select_sheet_prompt"), font=("Arial", 12, "bold")).pack(pady=10)

        # Sheet selection
        for sheet in sheet_names:
            ttk.Radiobutton(dialog, text=sheet, variable=selected_sheet, value=sheet).pack(anchor='w', padx=20)

        # Set default selection
        if sheet_names:
            selected_sheet.set(sheet_names[0])

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        result = [None]

        def on_ok():
            result[0] = selected_sheet.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text=_t("batch_ops.buttons.ok"), command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=on_cancel).pack(side=tk.LEFT)

        # Wait for dialog to close
        dialog.wait_window()
        return result[0]

    def multi_file_import(self):
        """GUI version of multi-file import"""
        directory = filedialog.askdirectory(title=_t("batch_ops.dialogs.select_import_dir"))
        if not directory:
            return

        # Find supported files
        supported_extensions = ['.csv', '.xlsx', '.xls']
        files = []

        for ext in supported_extensions:
            files.extend(Path(directory).glob(f"*{ext}"))

        if not files:
            messagebox.showwarning(_t("batch_ops.dialogs.no_files"), _t("batch_ops.errors.no_supported_files"))
            return

        # Show file selection dialog
        selected_files = self.select_files_for_import(files)
        if not selected_files:
            return

        # Confirm and start import
        if messagebox.askyesno(_t("batch_ops.dialogs.confirm"), _t("batch_ops.dialogs.process_files_confirm").format(count=len(selected_files))):
            def import_worker():
                try:
                    progress_dialog = GUIProgressDialog(self.gui.root, _t("batch_ops.progress.multi_file_import"), _t("batch_ops.progress.processing_files"))
                    progress_dialog.set_total(len(selected_files))

                    total_imported = 0
                    total_errors = 0

                    for i, file_path in enumerate(selected_files):
                        if progress_dialog.cancelled:
                            break

                        progress_dialog.update_progress(i, f"Processing {file_path.name}")

                        try:
                            if file_path.suffix.lower() == '.csv':
                                result = self.gui.backend.import_from_csv_file(str(file_path))
                            else:
                                result = self.gui.backend.import_from_excel_file(str(file_path))

                            total_imported += result.successful_imports
                            total_errors += result.failed_imports

                        except Exception as e:
                            logger.error(f"Error processing {file_path}: {e}")
                            total_errors += 1

                    progress_dialog.close()

                    # Show summary
                    summary = _t("batch_ops.messages.multi_import_complete").format(imported=total_imported, errors=total_errors)
                    messagebox.showinfo(_t("batch_ops.dialogs.import_complete"), summary)

                except Exception as e:
                    self.gui.message_queue.put({'type': 'error', 'text': f'Multi-file import failed: {str(e)}'})

            thread = threading.Thread(target=import_worker)
            thread.daemon = True
            thread.start()

    def select_files_for_import(self, files):
        """Show dialog to select files for multi-file import"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.dialogs.select_files"))
        dialog.geometry("500x400")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        ttk.Label(dialog, text=_t("batch_ops.dialogs.select_files_prompt"), font=("Arial", 12, "bold")).pack(pady=10)

        # File list with checkboxes
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Scrollable listbox
        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        # File checkboxes
        file_vars = {}
        for file_path in files:
            var = tk.BooleanVar(value=True)
            file_vars[file_path] = var
            ttk.Checkbutton(scrollable_frame, text=file_path.name, variable=var).pack(anchor='w', pady=2)

        scrollable_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        # Control buttons
        control_frame = ttk.Frame(dialog)
        control_frame.pack(fill=tk.X, padx=20, pady=10)

        def select_all():
            for var in file_vars.values():
                var.set(True)

        def select_none():
            for var in file_vars.values():
                var.set(False)

        ttk.Button(control_frame, text=_t("batch_ops.buttons.select_all"), command=select_all).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text=_t("batch_ops.buttons.select_none"), command=select_none).pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        result = [None]

        def on_ok():
            selected = [file_path for file_path, var in file_vars.items() if var.get()]
            result[0] = selected
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text=_t("batch_ops.buttons.import_selected"), command=on_ok).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=on_cancel).pack(side=tk.LEFT)

        dialog.wait_window()
        return result[0]

    def import_with_duplicates(self):
        """GUI version of import with duplicate detection"""
        file_path = filedialog.askopenfilename(
            title=_t("batch_ops.dialogs.select_file_duplicate"),
            filetypes=[(_t("batch_ops.filetypes.csv"), "*.csv"), (_t("batch_ops.filetypes.excel"), "*.xlsx *.xls"), (_t("batch_ops.filetypes.all"), "*.*")]
        )

        if not file_path:
            return

        def import_worker():
            try:
                progress_dialog = GUIProgressDialog(self.gui.root, _t("batch_ops.progress.duplicate_detection"), _t("batch_ops.progress.analyzing_duplicates"))

                # Read file and check for duplicates
                if file_path.lower().endswith('.csv'):
                    records = self.gui.backend.read_csv_file(file_path)
                else:
                    records = self.gui.backend.read_excel_file(file_path)

                if not records:
                    progress_dialog.close()
                    messagebox.showerror(_t("batch_ops.dialogs.error"), _t("batch_ops.errors.no_valid_records"))
                    return

                progress_dialog.update_progress(50, "Checking for duplicates...")

                duplicates = self.gui.backend.find_duplicates_in_import(records)
                progress_dialog.close()

                if duplicates:
                    # Show duplicate handling dialog
                    choice = self.show_duplicate_handling_dialog(duplicates)
                    if choice:
                        result = self.gui.backend.handle_duplicates(records, duplicates, choice)
                        self.show_import_results(result)
                else:
                    # No duplicates, proceed with import
                    if messagebox.askyesno(_t("batch_ops.dialogs.no_duplicates"), _t("batch_ops.dialogs.no_duplicates_proceed")):
                        result = self.gui.backend.import_valid_records(records)
                        self.show_import_results(result)

            except Exception as e:
                self.gui.message_queue.put({'type': 'error', 'text': f'Import with duplicate detection failed: {str(e)}'})

        thread = threading.Thread(target=import_worker)
        thread.daemon = True
        thread.start()

    def show_duplicate_handling_dialog(self, duplicates):
        """Show dialog for handling duplicates"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.dialogs.duplicates_found"))
        dialog.geometry("600x500")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 50, self.gui.root.winfo_rooty() + 50))

        # Header
        header = ttk.Label(dialog, text=_t("batch_ops.dialogs.found_duplicates").format(count=len(duplicates)),
                          font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Duplicate list
        list_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.dialogs.duplicate_records"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Scrollable text widget for duplicates
        dup_text = scrolledtext.ScrolledText(list_frame, height=15, width=70)
        dup_text.pack(fill=tk.BOTH, expand=True)

        # Show first 10 duplicates
        for i, dup in enumerate(duplicates[:10], 1):
            import_rec = dup['import_record']
            existing_rec = dup['existing_record']
            confidence = dup['confidence']

            dup_text.insert(tk.END, f"{i}. {import_rec['first_name']} {import_rec['last_name']} "
                                   f"matches existing student {existing_rec[3]} {existing_rec[5]} "
                                   f"(ID: {existing_rec[0]}) - Confidence: {confidence:.0%}\n\n")

        if len(duplicates) > 10:
            dup_text.insert(tk.END, f"... and {len(duplicates) - 10} more duplicates\n")

        dup_text.config(state='disabled')

        # Options
        options_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.dialogs.duplicate_options"), padding="10")
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        choice_var = tk.StringVar(value="1")

        ttk.Radiobutton(options_frame, text=_t("batch_ops.duplicates.skip_all"), variable=choice_var, value="1").pack(anchor='w')
        ttk.Radiobutton(options_frame, text=_t("batch_ops.duplicates.update_existing"), variable=choice_var, value="2").pack(anchor='w')
        ttk.Radiobutton(options_frame, text=_t("batch_ops.duplicates.handle_individually"), variable=choice_var, value="3").pack(anchor='w')
        ttk.Radiobutton(options_frame, text=_t("batch_ops.duplicates.import_anyway"), variable=choice_var, value="4").pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        result = [None]

        def on_proceed():
            result[0] = choice_var.get()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ttk.Button(button_frame, text=_t("batch_ops.buttons.proceed"), command=on_proceed).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=on_cancel).pack(side=tk.LEFT)

        dialog.wait_window()
        return result[0]

    def preview_import(self):
        """GUI version of preview import"""
        file_path = filedialog.askopenfilename(
            title=_t("batch_ops.dialogs.select_file_preview"),
            filetypes=[(_t("batch_ops.filetypes.csv"), "*.csv"), (_t("batch_ops.filetypes.excel"), "*.xlsx *.xls"), (_t("batch_ops.filetypes.all"), "*.*")]
        )

        if not file_path:
            return

        def preview_worker():
            try:
                # Read file
                if file_path.lower().endswith('.csv'):
                    records = self.gui.backend.read_csv_file(file_path)
                else:
                    records = self.gui.backend.read_excel_file(file_path)

                if not records:
                    messagebox.showerror(_t("batch_ops.dialogs.error"), _t("batch_ops.errors.no_valid_records"))
                    return

                # Show preview dialog
                self.show_preview_dialog(records, file_path)

            except Exception as e:
                messagebox.showerror(_t("batch_ops.dialogs.error"), _t("batch_ops.errors.preview_failed") + f": {str(e)}")

        thread = threading.Thread(target=preview_worker)
        thread.daemon = True
        thread.start()

    def show_preview_dialog(self, records, file_path):
        """Show preview dialog"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.dialogs.import_preview"))
        dialog.geometry("800x600")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 50, self.gui.root.winfo_rooty() + 50))

        # Header
        header = ttk.Label(dialog, text=_t("batch_ops.dialogs.preview_records").format(count=len(records), filename=os.path.basename(file_path)),
                          font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Preview content
        content_frame = ttk.Frame(dialog)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Sample records
        sample_frame = ttk.LabelFrame(content_frame, text=_t("batch_ops.dialogs.sample_records"), padding="10")
        sample_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview for sample data
        columns = list(records[0].keys()) if records else []
        preview_tree = ttk.Treeview(sample_frame, columns=columns, show="headings", height=8)

        # Configure columns
        for col in columns:
            preview_tree.heading(col, text=col.replace('_', ' ').title())
            preview_tree.column(col, width=100)

        # Add sample data
        for record in records[:5]:
            values = [str(record.get(col, '')) for col in columns]
            preview_tree.insert('', 'end', values=values)

        preview_tree.pack(fill=tk.BOTH, expand=True)

        # Summary info
        summary_frame = ttk.LabelFrame(content_frame, text=_t("batch_ops.dialogs.import_summary"), padding="10")
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        summary_text = f"""Records to import: {len(records)}
File type: {os.path.splitext(file_path)[1].upper()}
Estimated processing time: {len(records) * 0.1:.1f} seconds

Modules that will be assigned to CS students:
\u2022 {compulsory_module_1['name']} (Compulsory)
\u2022 {compulsory_module_2['name']} (Compulsory)
\u2022 {CS_optional_module_1['name']} (CS Optional)
\u2022 {CS_optional_module_2['name']} (CS Optional)

Modules that will be assigned to DS students:
\u2022 {compulsory_module_1['name']} (Compulsory)
\u2022 {compulsory_module_2['name']} (Compulsory)
\u2022 {DS_optional_module_1['name']} (DS Optional)
\u2022 {DS_optional_module_2['name']} (DS Optional)"""

        summary_label = ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT)
        summary_label.pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

    def resume_import(self):
        """GUI version of resume failed import"""
        # Find resume files
        resume_files = list(Path('.').glob('import_resume_*.json'))

        if not resume_files:
            messagebox.showinfo(_t("batch_ops.msg_titles.no_resumes"), "No failed imports found to resume")
            return

        # Show selection dialog
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.resume_failed"))
        dialog.geometry("400x300")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        ttk.Label(dialog, text="Select import to resume:", font=("Arial", 12, "bold")).pack(pady=10)

        # Resume file list
        selected_file = tk.StringVar()

        for file in resume_files:
            timestamp = file.stem.replace('import_resume_', '')
            ttk.Radiobutton(dialog, text=f"Import from {timestamp}",
                           variable=selected_file, value=str(file)).pack(anchor='w', padx=20)

        if resume_files:
            selected_file.set(str(resume_files[0]))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def resume_selected():
            file_path = selected_file.get()
            if file_path:
                dialog.destroy()
                self.execute_resume_import(file_path)

        ttk.Button(button_frame, text="Resume", command=resume_selected).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def execute_resume_import(self, resume_file_path):
        """Execute the resume import operation"""
        def resume_worker():
            try:
                # Load saved state
                with open(resume_file_path, 'r') as f:
                    saved_state = json.load(f)

                remaining_records = saved_state['remaining_records']
                original_total = saved_state['original_total']
                processed_count = original_total - len(remaining_records)

                if messagebox.askyesno(_t("batch_ops.msg_titles.resume_import"),
                                     f"Resume import: {processed_count}/{original_total} records already processed\n"
                                     f"{len(remaining_records)} records remaining\n\n"
                                     f"Continue with remaining records?"):

                    progress_dialog = GUIProgressDialog(self.gui.root, "Resume Import", "Resuming import")

                    result = self.gui.backend.import_valid_records(remaining_records)

                    progress_dialog.close()

                    # Clean up resume file
                    os.remove(resume_file_path)

                    self.show_import_results(result, "Resumed Import")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=resume_worker)
        thread.daemon = True
        thread.start()

    def show_import_results(self, result, operation_type="Import"):
        """Show import results dialog"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(f"{operation_type} Results")
        dialog.geometry("500x400")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        if result.successful_imports > 0 and result.failed_imports == 0:
            header_text = f"\u2705 {result.successful_imports} student(s) added/updated successfully"
            header_color = "green"
        elif result.successful_imports > 0:
            header_text = f"\u26a0\ufe0f {result.successful_imports} student(s) added/updated, {result.failed_imports} failed"
            header_color = "orange"
        else:
            header_text = f"\u274c No students were added — {result.failed_imports} record(s) failed"
            header_color = "red"

        header = ttk.Label(dialog, text=header_text, font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Results summary
        summary_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.summary"), padding="10")
        summary_frame.pack(fill=tk.X, padx=20, pady=10)

        duration = (result.end_time - result.start_time).total_seconds() if result.end_time and result.start_time else 0

        summary_text = f"""Total Records: {result.total_records}
Successful Imports: {result.successful_imports}
Failed Imports: {result.failed_imports}
Duplicates Found: {result.duplicates_found}
Duplicates Skipped: {result.duplicates_skipped}
Duplicates Updated: {result.duplicates_updated}
Processing Time: {duration:.1f} seconds"""

        summary_label = ttk.Label(summary_frame, text=summary_text, justify=tk.LEFT)
        summary_label.pack(anchor='w')

        # Errors (if any)
        if result.errors:
            error_frame = ttk.LabelFrame(dialog, text=f"Errors ({len(result.errors)})", padding="10")
            error_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            error_text = scrolledtext.ScrolledText(error_frame, height=10)
            error_text.pack(fill=tk.BOTH, expand=True)

            for i, error in enumerate(result.errors[:20], 1):  # Show first 20 errors
                if isinstance(error, dict):
                    row = error.get('row', '?')
                    # Support both 'errors' (list) and 'error' (string) keys
                    err_detail = error.get('errors', error.get('error', 'Unknown error'))
                    if isinstance(err_detail, list):
                        err_detail = '; '.join(str(e) for e in err_detail)
                    error_text.insert(tk.END, f"{i}. Row {row}: {err_detail}\n")
                else:
                    error_text.insert(tk.END, f"{i}. {error}\n")

            if len(result.errors) > 20:
                error_text.insert(tk.END, f"\n... and {len(result.errors) - 20} more errors")

            error_text.config(state='disabled')

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="OK", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

        if result.errors:
            def export_errors():
                error_file = filedialog.asksaveasfilename(
                    title="Save error report",
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                )
                if error_file:
                    try:
                        with open(error_file, 'w') as f:
                            f.write(f"{operation_type} Error Report\n")
                            f.write(f"Generated: {datetime.datetime.now()}\n\n")
                            for i, error in enumerate(result.errors, 1):
                                if isinstance(error, dict):
                                    row = error.get('row', '?')
                                    err_detail = error.get('errors', error.get('error', 'Unknown error'))
                                    if isinstance(err_detail, list):
                                        err_detail = '; '.join(str(e) for e in err_detail)
                                    f.write(f"{i}. Row {row}: {err_detail}\n")
                                else:
                                    f.write(f"{i}. {error}\n")
                        messagebox.showinfo(_t("batch_ops.msg_titles.exported"), f"Error report saved to {error_file}")
                    except Exception as e:
                        messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            ttk.Button(button_frame, text=_t("batch_ops.buttons.export_errors"), command=export_errors).pack(side=tk.LEFT)
