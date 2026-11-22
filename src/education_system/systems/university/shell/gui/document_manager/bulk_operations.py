import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
import json

from education_system.systems.university.infrastructure.sql_safety import escape_like
import zipfile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.systems.university.infrastructure.database.db import transaction
except ImportError:
    transaction = None

try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class BulkOperationsManager:
    """Manages all bulk operation dialogs and actions for the document manager GUI."""

    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def bulk_status_update(self):
        """Enhanced bulk status update with GUI"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_status_update', default="Bulk Status Update"))
        dialog.geometry("850x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_status_update', default="Bulk Status Update"), font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Selection criteria
        criteria_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.selection_criteria', default="Selection Criteria"), padding=10)
        criteria_frame.pack(fill='x', pady=(0, 15))

        criteria_var = tk.StringVar(value=_t('gui.shell.document_manager.bulk_operations.values.type', default="type"))
        ttk.Radiobutton(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.by_document_type', default="By Document Type"), variable=criteria_var, value="type").pack(anchor='w')
        ttk.Radiobutton(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.by_current_status', default="By Current Status"), variable=criteria_var, value="status").pack(anchor='w')
        ttk.Radiobutton(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.by_date_range', default="By Date Range"), variable=criteria_var, value="date").pack(anchor='w')

        # Filter input
        filter_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.filter_value', default="Filter Value"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=filter_var, width=40).pack(fill='x')

        # New status selection
        status_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.new_status', default="New Status"), padding=10)
        status_frame.pack(fill='x', pady=(0, 15))

        new_status_var = tk.StringVar(value=_t('gui.shell.document_manager.bulk_operations.values.verified', default="Verified"))
        status_options = ["Verified", "Rejected", "Pending", "Expired"]
        status_combo = ttk.Combobox(status_frame, textvariable=new_status_var, values=status_options)
        status_combo.pack(fill='x')

        # Notes
        ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.notes', default="Notes:")).pack(anchor='w')
        notes_text = tk.Text(main_frame, height=3, width=40)
        notes_text.pack(fill='x', pady=5)

        def perform_bulk_update():
            criteria = criteria_var.get()
            filter_value = filter_var.get()
            new_status = new_status_var.get()
            notes = notes_text.get('1.0', 'end-1c')

            if not filter_value:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_enter_filter_value', default="Please enter filter value"))
                return

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Build query based on criteria
                if criteria == "type":
                    cursor.execute('''
                    SELECT sd.document_id FROM documents sd
                    JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                    WHERE dt.type_name LIKE ? AND sd.is_current_version = 1
                    ''', (f'%{filter_value}%',))
                elif criteria == "status":
                    cursor.execute('''
                    SELECT document_id FROM documents
                    WHERE verification_status = ? AND is_current_version = 1
                    ''', (filter_value,))
                elif criteria == "date":
                    # Expecting date range format: YYYY-MM-DD to YYYY-MM-DD
                    date_parts = filter_value.split(' to ')
                    if len(date_parts) == 2:
                        cursor.execute('''
                        SELECT document_id FROM documents
                        WHERE DATE(upload_date) BETWEEN ? AND ? AND is_current_version = 1
                        ''', (date_parts[0], date_parts[1]))
                    else:
                        messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), _t('gui.shell.document_manager.bulk_operations.dialogs.date_format_should_be_yyyy_mm_dd_to_yyyy_mm_dd', default="Date format should be: YYYY-MM-DD to YYYY-MM-DD"))
                        conn.close()
                        return

                doc_ids = [row[0] for row in cursor.fetchall()]

                if not doc_ids:
                    messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.info', default="Info"), _t('gui.shell.document_manager.bulk_operations.dialogs.no_documents_found_matching_criteria', default="No documents found matching criteria"))
                    conn.close()
                    return

                # Confirm update
                confirm = messagebox.askyesno(_t('gui.shell.document_manager.bulk_operations.dialogs.confirm', default="Confirm"), f"Update {len(doc_ids)} documents to status '{new_status}'?")
                if not confirm:
                    conn.close()
                    return

                # Perform bulk update
                verification_date = datetime.now().strftime('%Y-%m-%d') if new_status != 'Pending' else None

                for doc_id in doc_ids:
                    cursor.execute('''
                    UPDATE documents
                    SET verification_status = ?, verification_date = ?, verification_notes = ?
                    WHERE document_id = ?
                    ''', (new_status, verification_date, f"Bulk update: {notes}" if notes else "Bulk update", doc_id))

                conn.commit()
                conn.close()

                messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.success', default="Success"), f"Successfully updated {len(doc_ids)} documents")
                dialog.destroy()
                self.gui.refresh_documents()

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), f"Bulk update failed: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(15, 0))

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.update', default="Update"), command=perform_bulk_update).pack(side='right', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right')

    def bulk_operations_dialog(self):
        """Show bulk operations dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_operations', default="Bulk Operations"))
        dialog.geometry("700x550")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 50))

        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_operations', default="Bulk Operations"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Operations frame
        operations_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.available_operations', default="Available Operations"), padding=15)
        operations_frame.pack(fill='both', expand=True)

        # Bulk operations list
        operations = [
            ("\U0001f4dd Bulk Status Update", "Update status for multiple documents", self.bulk_status_update),
            ("\U0001f3f7\ufe0f Bulk Tag Assignment", "Assign tags to multiple documents", self.bulk_tag_assignment),
            ("\U0001f4e7 Bulk Notification Send", "Send notifications to multiple students", self.gui.bulk_notification_send),
            ("\U0001f4e5 Bulk Import Documents", "Import documents from CSV/Excel", self.bulk_import_dialog),
            ("\U0001f4e4 Bulk Export Data", "Export multiple datasets", self.bulk_export_dialog),
            ("\U0001f5c2\ufe0f Bulk Document Download", "Download multiple documents", self.bulk_document_download),
        ]

        for i, (title, description, command) in enumerate(operations):
            op_frame = ttk.Frame(operations_frame)
            op_frame.pack(fill='x', pady=5)

            ttk.Button(op_frame, text=title, command=command, width=25).pack(side='left')
            ttk.Label(op_frame, text=description, font=('Arial', 9), foreground='gray').pack(side='left', padx=10)

        # Close button
        ttk.Button(main_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.close', default="Close"), command=dialog.destroy).pack(pady=20)

    def bulk_export_dialog(self):
        """Bulk export dialog for exporting multiple datasets"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_export_data', default="Bulk Export Data"))
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_export_data', default="Bulk Export Data"), font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Export options
        options_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.select_data_to_export', default="Select Data to Export"), padding=15)
        options_frame.pack(fill='x', pady=(0, 15))

        export_students = tk.BooleanVar(value=True)
        export_documents = tk.BooleanVar(value=True)
        export_workflows = tk.BooleanVar(value=False)
        export_compliance = tk.BooleanVar(value=False)

        ttk.Checkbutton(options_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.students_data', default="Students Data"), variable=export_students).pack(anchor='w')
        ttk.Checkbutton(options_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.documents_data', default="Documents Data"), variable=export_documents).pack(anchor='w')
        ttk.Checkbutton(options_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.workflow_data', default="Workflow Data"), variable=export_workflows).pack(anchor='w')
        ttk.Checkbutton(options_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.compliance_report', default="Compliance Report"), variable=export_compliance).pack(anchor='w')

        # Format selection
        format_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.export_format', default="Export Format"), padding=15)
        format_frame.pack(fill='x', pady=(0, 15))

        export_format = tk.StringVar(value=_t('gui.shell.document_manager.bulk_operations.values.csv', default="csv"))
        ttk.Radiobutton(format_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.csv', default="CSV"), variable=export_format, value="csv").pack(anchor='w')
        ttk.Radiobutton(format_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.excel_xlsx', default="Excel (XLSX)"), variable=export_format, value="xlsx").pack(anchor='w')
        ttk.Radiobutton(format_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.json', default="JSON"), variable=export_format, value="json").pack(anchor='w')

        def perform_export():
            # Ask for directory
            export_dir = filedialog.askdirectory(title=_t('gui.shell.document_manager.bulk_operations.dialogs.select_export_directory', default="Select Export Directory"))
            if not export_dir:
                return

            try:
                exported_files = []
                conn = get_connection()
                cursor = conn.cursor()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                fmt = export_format.get()

                if export_students.get():
                    cursor.execute('SELECT * FROM students')
                    data = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    filepath = os.path.join(export_dir, f'students_{timestamp}.{fmt}')
                    self._export_data(filepath, columns, data, fmt)
                    exported_files.append(filepath)

                if export_documents.get():
                    cursor.execute('''
                        SELECT sd.*, dt.type_name
                        FROM documents sd
                        LEFT JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
                    ''')
                    data = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    filepath = os.path.join(export_dir, f'documents_{timestamp}.{fmt}')
                    self._export_data(filepath, columns, data, fmt)
                    exported_files.append(filepath)

                if export_workflows.get():
                    cursor.execute('SELECT * FROM document_workflow')
                    data = cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    filepath = os.path.join(export_dir, f'workflows_{timestamp}.{fmt}')
                    self._export_data(filepath, columns, data, fmt)
                    exported_files.append(filepath)

                if export_compliance.get():
                    cursor.execute('''
                        SELECT s.student_id, s.first_name, s.last_name, s.course,
                               COUNT(DISTINCT dt.type_id) as required_docs,
                               COUNT(DISTINCT sd.document_id) as submitted_docs
                        FROM students s
                        CROSS JOIN document_types dt
                        LEFT JOIN documents sd ON s.student_id = sd.owner_id
                            AND sd.source_type = 'student' AND dt.type_id = CAST(sd.document_type AS INTEGER) AND sd.is_current_version = 1
                        WHERE dt.is_required = 1
                        GROUP BY s.student_id
                    ''')
                    data = cursor.fetchall()
                    columns = ['student_id', 'first_name', 'last_name', 'course', 'required_docs', 'submitted_docs']
                    filepath = os.path.join(export_dir, f'compliance_{timestamp}.{fmt}')
                    self._export_data(filepath, columns, data, fmt)
                    exported_files.append(filepath)

                conn.close()

                messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.export_successful', default="Export Successful"),
                                  f"Exported {len(exported_files)} file(s) to:\n{export_dir}")
                dialog.destroy()

                self.gui.log_event('export', 'bulk_export',
                              details=f'Exported {len(exported_files)} files')

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.export_error', default="Export Error"), f"Failed to export data: {e}")

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.export', default="Export"), command=perform_export).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='right', padx=5)

    def _export_data(self, filepath, columns, data, fmt):
        """Helper method to export data in various formats"""
        if fmt == 'csv':
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(data)
        elif fmt == 'xlsx':
            try:
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.append(columns)
                for row in data:
                    ws.append(row)
                wb.save(filepath)
            except ImportError:
                # Fallback to CSV if openpyxl not available
                filepath = filepath.replace('.xlsx', '.csv')
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)
                    writer.writerows(data)
        elif fmt == 'json':
            json_data = [dict(zip(columns, row)) for row in data]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, default=str)

    def bulk_import_dialog(self):
        """Show bulk import dialog for importing multiple documents"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_document_import', default="Bulk Document Import"))
        dialog.geometry("950x700")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_document_import', default="Bulk Document Import"), font=('Arial', 14, 'bold')).pack(pady=10)

        # File selection
        files_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.select_files', default="Select Files"), padding=10)
        files_frame.pack(fill='both', expand=True, pady=10)

        files_list = tk.Listbox(files_frame, height=10)
        files_list.pack(fill='both', expand=True, pady=5)

        selected_files = []

        def browse_files():
            from tkinter import filedialog
            files = filedialog.askopenfilenames(
                title=_t('gui.shell.document_manager.bulk_operations.dialogs.select_documents_to_import', default="Select Documents to Import"),
                filetypes=[
                    ("All files", "*.*"),
                    ("PDF files", "*.pdf"),
                    ("Image files", "*.png *.jpg *.jpeg"),
                    ("Documents", "*.doc *.docx")
                ]
            )
            if files:
                selected_files.clear()
                selected_files.extend(files)
                files_list.delete(0, tk.END)
                for file in files:
                    files_list.insert(tk.END, os.path.basename(file))

        ttk.Button(files_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.browse_files', default="Browse Files"), command=browse_files).pack(pady=5)

        # Import settings
        settings_frame = ttk.LabelFrame(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.import_settings', default="Import Settings"), padding=10)
        settings_frame.pack(fill='x', pady=10)

        ttk.Label(settings_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.document_type', default="Document Type:")).grid(row=0, column=0, sticky='w', pady=5)
        doc_type_var = tk.StringVar()
        doc_type_combo = ttk.Combobox(settings_frame, textvariable=doc_type_var, state='readonly', width=30)
        doc_type_combo.grid(row=0, column=1, pady=5, padx=10)

        # Load document types
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT type_id, type_name FROM document_types WHERE is_active = 1 ORDER BY type_name')
            type_ids = {name: tid for tid, name in cursor.fetchall()}
            conn.close()
            types = list(type_ids)
            doc_type_combo['values'] = types
            if types:
                doc_type_combo.current(0)
        except Exception as e:
            logger.warning("Could not load document types: %s", e)
            type_ids = {}
            doc_type_combo['values'] = []

        ttk.Label(settings_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.student_id', default="Student ID:")).grid(row=1, column=0, sticky='w', pady=5)
        student_id_var = tk.StringVar()
        ttk.Entry(settings_frame, textvariable=student_id_var, width=30).grid(row=1, column=1, pady=5, padx=10)

        # Import button
        def perform_import():
            if not selected_files:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_select_files_to_import', default="Please select files to import"))
                return

            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_enter_student_id', default="Please enter student ID"),
                                     parent=dialog)
                return

            type_id = type_ids.get(doc_type_var.get())
            if type_id is None:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"),
                                     _t('gui.shell.document_manager.bulk_operations.dialogs.choose_document_type', default="Choose a document type (none are active - add one under Document Types)."),
                                     parent=dialog)
                return

            try:
                with get_connection() as conn:
                    known = conn.execute('SELECT 1 FROM students WHERE student_id = ?', (student_id,)).fetchone()
                if not known:
                    messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"),
                                         f"No student with ID {student_id}.", parent=dialog)
                    return

                imported = 0
                failed = []
                for file_path in selected_files:
                    try:
                        # Same path as Upload Document: validation, secure copy,
                        # hashing, versioning and the student e-mail.
                        if self.gui.upload_document_to_db(student_id, type_id, file_path, None, None, None):
                            imported += 1
                        else:
                            failed.append(os.path.basename(file_path))
                    except Exception as e:
                        failed.append(f"{os.path.basename(file_path)}: {e}")
                        logger.warning("Failed to import %s: %s", file_path, e)

                self.gui.log_event('import', 'bulk_documents', details={
                    'student_id': student_id, 'type_id': type_id,
                    'imported': imported, 'failed': len(failed)})
                result = f"Import completed!\n\nImported: {imported}\nFailed: {len(failed)}"
                if failed:
                    result += "\n\n" + "\n".join(failed[:10])
                messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.import_complete', default="Import Complete"),
                                    result, parent=dialog)
                if hasattr(self.gui, 'refresh_documents'):
                    try:
                        self.gui.refresh_documents()
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), f"Import failed: {e}",
                                     parent=dialog)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        ttk.Button(buttons_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.import', default="Import"), command=perform_import).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.cancel', default="Cancel"), command=dialog.destroy).pack(side='left', padx=5)

    def bulk_tag_assignment(self):
        """Assign tags to multiple documents"""
        try:
            # Get selected documents from main tree
            selected = self.gui.docs_tree.selection()
            if not selected:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_select_documents_to_tag', default="Please select documents to tag"))
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_tag_assignment', default="Bulk Tag Assignment"))
            dialog.geometry("600x450")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Assign tags to {len(selected)} document(s)",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.tags_comma_separated', default="Tags (comma-separated):")).pack(anchor='w')
            tags_entry = tk.Entry(main_frame, width=40)
            tags_entry.pack(fill='x', pady=10)

            def apply_tags():
                tags = tags_entry.get().strip()
                if not tags:
                    messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_enter_at_least_one_tag', default="Please enter at least one tag"))
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    for item in selected:
                        doc_id = self.gui.docs_tree.item(item)['values'][0]
                        cursor.execute('''
                            UPDATE documents
                            SET tags = ?
                            WHERE document_id = ?
                        ''', (tags, doc_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.success', default="Success"), f"Tags applied to {len(selected)} documents")
                    dialog.destroy()
                    self.gui.load_documents()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), f"Failed to apply tags: {e}")

            ttk.Button(main_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.apply_tags', default="Apply Tags"), command=apply_tags).pack(pady=20)
            ttk.Button(main_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.cancel', default="Cancel"), command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), f"Failed to open bulk tag dialog: {e}")

    def bulk_document_download(self):
        """Download multiple documents"""
        try:
            selected = self.gui.docs_tree.selection()
            if not selected:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_select_documents_to_download', default="Please select documents to download"))
                return

            # Ask for download directory
            download_dir = filedialog.askdirectory(title=_t('gui.shell.document_manager.bulk_operations.dialogs.select_download_directory', default="Select Download Directory"))
            if not download_dir:
                return

            # Progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.downloading_documents', default="Downloading Documents"))
            progress_dialog.geometry("600x300")
            progress_dialog.transient(self.root)

            main_frame = ttk.Frame(progress_dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Downloading {len(selected)} document(s)",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            progress = ttk.Progressbar(main_frame, length=500, mode='determinate')
            progress.pack(pady=10)

            status_label = ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.preparing', default="Preparing..."))
            status_label.pack(pady=10)

            # Download documents
            conn = get_connection()
            cursor = conn.cursor()

            success_count = 0
            fail_count = 0

            for i, item in enumerate(selected):
                doc_id = self.gui.docs_tree.item(item)['values'][0]

                cursor.execute('''
                SELECT original_filename, file_path
                FROM documents
                WHERE document_id = ?
                ''', (doc_id,))

                result = cursor.fetchone()
                if result:
                    filename, file_path = result
                    try:
                        import shutil
                        import os

                        if file_path and os.path.exists(file_path):
                            # Contain the destination: a stored filename with
                            # path separators (or "..") must not let the copy
                            # escape the chosen download directory.
                            safe_name = os.path.basename(str(filename)) or "download"
                            dest_path = os.path.join(download_dir, safe_name)
                            shutil.copy2(file_path, dest_path)
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as e:
                        fail_count += 1
                        print(f"Error downloading {filename}: {e}")
                else:
                    fail_count += 1

                progress['value'] = ((i + 1) / len(selected)) * 100
                status_label.config(text=f"Downloaded {i + 1}/{len(selected)}")
                progress_dialog.update()

            conn.close()
            progress_dialog.destroy()

            messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.download_complete', default="Download Complete"),
                              f"Successfully downloaded: {success_count}\nFailed: {fail_count}")

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), f"Failed to download documents: {e}")

    def bulk_expiry_update(self):
        """Update expiry dates for multiple documents"""
        try:
            selected = self.gui.docs_tree.selection()
            if not selected:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.warning', default="Warning"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_select_documents_to_update', default="Please select documents to update"))
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_expiry_update', default="Bulk Expiry Update"))
            dialog.geometry("600x450")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Update Expiry for {len(selected)} document(s)",
                     font=('Arial', 12, 'bold')).pack(pady=(0, 20))

            # Date selection
            ttk.Label(main_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.new_expiry_date', default="New Expiry Date:"), font=('Arial', 10, 'bold')).pack(anchor='w')

            date_frame = ttk.Frame(main_frame)
            date_frame.pack(fill='x', pady=10)

            ttk.Label(date_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.year', default="Year:")).grid(row=0, column=0, padx=5)
            year_var = tk.StringVar(value="2025")
            year_entry = ttk.Spinbox(date_frame, from_=2024, to=2030, textvariable=year_var, width=10)
            year_entry.grid(row=0, column=1, padx=5)

            ttk.Label(date_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.month', default="Month:")).grid(row=0, column=2, padx=5)
            month_var = tk.StringVar(value="12")
            month_entry = ttk.Spinbox(date_frame, from_=1, to=12, textvariable=month_var, width=10)
            month_entry.grid(row=0, column=3, padx=5)

            ttk.Label(date_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.day', default="Day:")).grid(row=0, column=4, padx=5)
            day_var = tk.StringVar(value="31")
            day_entry = ttk.Spinbox(date_frame, from_=1, to=31, textvariable=day_var, width=10)
            day_entry.grid(row=0, column=5, padx=5)

            def apply_expiry_update():
                year = year_var.get()
                month = month_var.get().zfill(2)
                day = day_var.get().zfill(2)
                new_expiry = f"{year}-{month}-{day}"

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    for item in selected:
                        doc_id = self.gui.docs_tree.item(item)['values'][0]
                        cursor.execute('''
                            UPDATE documents
                            SET expiry_date = ?
                            WHERE document_id = ?
                        ''', (new_expiry, doc_id))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.success', default="Success"), f"Expiry date updated for {len(selected)} documents")
                    dialog.destroy()
                    self.gui.load_documents_data()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), f"Failed to update expiry dates: {e}")

            ttk.Button(main_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.apply_update', default="Apply Update"), command=apply_expiry_update).pack(pady=20)
            ttk.Button(main_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.cancel', default="Cancel"), command=dialog.destroy).pack()

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.error', default="Error"), f"Failed to open expiry update dialog: {e}")

    def bulk_import_documents(self):
        """Bulk import documents from a directory"""
        if not self.gui.ensure_login():
            return

        # Create bulk import window
        import_window = tk.Toplevel(self.root)
        import_window.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_import_documents', default="Bulk Import Documents"))
        import_window.geometry("900x700")
        import_window.transient(self.root)
        import_window.grab_set()

        # Title
        ttk.Label(import_window, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_document_import', default="Bulk Document Import"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Instructions
        instructions_frame = ttk.LabelFrame(import_window, text=_t('gui.shell.document_manager.bulk_operations.labels.instructions', default="Instructions"), padding=10)
        instructions_frame.pack(fill='x', padx=10, pady=5)

        instructions = """1. Select a directory containing documents to import
2. Files should be named in format: StudentID_DocumentType_FileName.pdf
3. Example: 12345_Transcript_Fall2024.pdf
4. All documents will be imported with 'Pending' status by default
5. Progress will be shown during import"""

        ttk.Label(instructions_frame, text=instructions, justify='left').pack(anchor='w')

        # Configuration frame
        config_frame = ttk.LabelFrame(import_window, text=_t('gui.shell.document_manager.bulk_operations.labels.import_configuration', default="Import Configuration"), padding=10)
        config_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(config_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.import_directory', default="Import Directory:")).grid(row=0, column=0, sticky='w', pady=5)
        directory_var = tk.StringVar()
        directory_entry = ttk.Entry(config_frame, textvariable=directory_var, width=50, state='readonly')
        directory_entry.grid(row=0, column=1, sticky='ew', pady=5)

        def browse_directory():
            directory = filedialog.askdirectory(title=_t('gui.shell.document_manager.bulk_operations.dialogs.select_import_directory', default="Select Import Directory"))
            if directory:
                directory_var.set(directory)
                scan_directory()

        ttk.Button(config_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.browse', default="Browse..."), command=browse_directory).grid(row=0, column=2, padx=5)

        ttk.Label(config_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.default_document_type', default="Default Document Type:")).grid(row=1, column=0, sticky='w', pady=5)
        default_type_combo = ttk.Combobox(config_frame, width=48, state='readonly')
        default_type_combo['values'] = ['Auto-detect from filename', 'Transcript', 'ID Card',
                                        'Health Form', 'Enrollment Form', 'Financial Document']
        default_type_combo.current(0)
        default_type_combo.grid(row=1, column=1, sticky='ew', pady=5)

        ttk.Label(config_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.default_status', default="Default Status:")).grid(row=2, column=0, sticky='w', pady=5)
        default_status_combo = ttk.Combobox(config_frame, width=48, state='readonly')
        default_status_combo['values'] = ['Pending', 'Approved']
        default_status_combo.current(0)
        default_status_combo.grid(row=2, column=1, sticky='ew', pady=5)

        config_frame.columnconfigure(1, weight=1)

        # Files preview frame
        preview_frame = ttk.LabelFrame(import_window, text=_t('gui.shell.document_manager.bulk_operations.labels.files_to_import', default="Files to Import"), padding=10)
        preview_frame.pack(fill='both', expand=True, padx=10, pady=5)

        files_tree = ttk.Treeview(preview_frame,
                                 columns=('File', 'Student ID', 'Document Type', 'Size'),
                                 show='headings', height=15)
        files_tree.heading('File', text=_t('gui.shell.document_manager.bulk_operations.headings.file_name', default='File Name'))
        files_tree.heading('Student ID', text=_t('gui.shell.document_manager.bulk_operations.headings.detected_student_id', default='Detected Student ID'))
        files_tree.heading('Document Type', text=_t('gui.shell.document_manager.bulk_operations.headings.detected_type', default='Detected Type'))
        files_tree.heading('Size', text=_t('gui.shell.document_manager.bulk_operations.headings.file_size', default='File Size'))

        files_tree.column('File', width=300)
        files_tree.column('Student ID', width=120)
        files_tree.column('Document Type', width=150)
        files_tree.column('Size', width=100)

        scrollbar = ttk.Scrollbar(preview_frame, orient='vertical', command=files_tree.yview)
        files_tree.configure(yscrollcommand=scrollbar.set)

        files_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Status label
        status_label = ttk.Label(import_window, text=_t('gui.shell.document_manager.bulk_operations.labels.no_directory_selected', default="No directory selected"), font=("Arial", 9))
        status_label.pack(pady=5)

        def scan_directory():
            """Scan directory and populate file list"""
            directory = directory_var.get()
            if not directory:
                return

            # Clear existing items
            for item in files_tree.get_children():
                files_tree.delete(item)

            try:
                import os
                files = [f for f in os.listdir(directory) if f.endswith(('.pdf', '.jpg', '.jpeg', '.png'))]

                for file in files:
                    file_path = os.path.join(directory, file)
                    file_size = os.path.getsize(file_path)
                    size_str = f"{file_size / 1024:.1f} KB"

                    # Try to parse filename: StudentID_DocumentType_FileName.pdf
                    parts = file.split('_')
                    student_id = parts[0] if len(parts) > 0 else 'Unknown'
                    doc_type = parts[1] if len(parts) > 1 else 'Unknown'

                    files_tree.insert('', 'end', values=(file, student_id, doc_type, size_str))

                status_label.config(text=f"Found {len(files)} documents to import")

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.scan_error', default="Scan Error"), f"Failed to scan directory: {e}")

        def start_import():
            """Start the bulk import process"""
            directory = directory_var.get()
            if not directory:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.no_directory', default="No Directory"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_select_a_directory_first', default="Please select a directory first"))
                return

            items = files_tree.get_children()
            if not items:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.no_files', default="No Files"), _t('gui.shell.document_manager.bulk_operations.dialogs.no_files_found_to_import', default="No files found to import"))
                return

            if not messagebox.askyesno(_t('gui.shell.document_manager.bulk_operations.dialogs.confirm_import', default="Confirm Import"),
                                      f"Import {len(items)} documents?\n\n"
                                      "This operation cannot be undone."):
                return

            # Progress dialog
            progress_window = tk.Toplevel(import_window)
            progress_window.title(_t('gui.shell.document_manager.bulk_operations.windows.importing', default="Importing..."))
            progress_window.geometry("400x150")
            progress_window.transient(import_window)
            progress_window.grab_set()

            ttk.Label(progress_window, text=_t('gui.shell.document_manager.bulk_operations.labels.importing_documents', default="Importing documents..."),
                     font=("Arial", 11)).pack(pady=10)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_window, variable=progress_var,
                                          maximum=len(items), length=350)
            progress_bar.pack(pady=10)

            progress_label = ttk.Label(progress_window, text="0 / 0")
            progress_label.pack()

            imported_count = 0
            failed_count = 0

            try:
                for idx, item in enumerate(items, 1):
                    values = files_tree.item(item, 'values')
                    file_name, student_id, doc_type, _ = values

                    try:
                        file_path = os.path.join(directory, file_name)
                        file_size = os.path.getsize(file_path)

                        # Insert into database
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO documents (student_id, document_type, file_name,
                                                     file_path, file_size, status, upload_date)
                                VALUES (?, ?, ?, ?, ?, ?, DATE('now'))
                            """, (student_id, doc_type, file_name, file_path, file_size,
                                 default_status_combo.get()))

                        imported_count += 1
                    except Exception as e:
                        failed_count += 1
                        print(f"Failed to import {file_name}: {e}")

                    progress_var.set(idx)
                    progress_label.config(text=f"{idx} / {len(items)}")
                    progress_window.update()

                progress_window.destroy()

                messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.import_complete', default="Import Complete"),
                                  f"Bulk import completed!\n\n"
                                  f"Successfully imported: {imported_count}\n"
                                  f"Failed: {failed_count}")

                # Log activity
                self.gui.log_event('bulk_import', 'documents',
                              details=f'Imported {imported_count} documents, {failed_count} failed')

                import_window.destroy()

            except Exception as e:
                progress_window.destroy()
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.import_error', default="Import Error"), f"Bulk import failed: {e}")

        # Button frame
        button_frame = ttk.Frame(import_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.start_import', default="Start Import"),
                  command=start_import).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.refresh', default="Refresh"),
                  command=scan_directory).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.cancel', default="Cancel"),
                  command=import_window.destroy).pack(side='right', padx=5)

    def bulk_update_from_search(self):
        """Bulk update documents from search results"""
        if not self.gui.ensure_login():
            return

        # Create bulk update window
        update_window = tk.Toplevel(self.root)
        update_window.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_update_from_search', default="Bulk Update from Search"))
        update_window.geometry("1000x750")
        update_window.transient(self.root)
        update_window.grab_set()

        # Title
        ttk.Label(update_window, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_update_from_search_results', default="Bulk Update from Search Results"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Create notebook
        notebook = ttk.Notebook(update_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab 1: Search & Select
        search_frame = ttk.Frame(notebook, padding=10)
        notebook.add(search_frame, text=_t('gui.shell.document_manager.bulk_operations.tabs.search_select', default="Search & Select"))

        # Search criteria
        criteria_frame = ttk.LabelFrame(search_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.search_criteria', default="Search Criteria"), padding=10)
        criteria_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky='w', padx=5)
        student_search = ttk.Entry(criteria_frame, width=20)
        student_search.grid(row=0, column=1, padx=5)

        ttk.Label(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.document_type', default="Document Type:")).grid(row=0, column=2, sticky='w', padx=5)
        type_search = ttk.Combobox(criteria_frame, width=18, state='readonly')
        type_search['values'] = ['All', 'Transcript', 'ID Card', 'Health Form', 'Financial']
        type_search.current(0)
        type_search.grid(row=0, column=3, padx=5)

        ttk.Label(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.current_status', default="Current Status:")).grid(row=0, column=4, sticky='w', padx=5)
        status_search = ttk.Combobox(criteria_frame, width=18, state='readonly')
        status_search['values'] = ['All', 'Pending', 'Approved', 'Rejected']
        status_search.current(0)
        status_search.grid(row=0, column=5, padx=5)

        # Results tree
        results_frame = ttk.Frame(search_frame)
        results_frame.pack(fill='both', expand=True, pady=5)

        results_tree = ttk.Treeview(results_frame,
                                   columns=('Select', 'ID', 'Student', 'Type', 'Status'),
                                   show='headings', height=15)
        results_tree.heading('Select', text='\u2611')
        results_tree.heading('ID', text=_t('gui.shell.document_manager.bulk_operations.headings.doc_id', default='Doc ID'))
        results_tree.heading('Student', text=_t('gui.shell.document_manager.bulk_operations.headings.student_id', default='Student ID'))
        results_tree.heading('Type', text=_t('gui.shell.document_manager.bulk_operations.headings.document_type', default='Document Type'))
        results_tree.heading('Status', text=_t('gui.shell.document_manager.bulk_operations.headings.current_status', default='Current Status'))

        results_tree.column('Select', width=40)
        results_tree.column('ID', width=80)
        results_tree.column('Student', width=100)
        results_tree.column('Type', width=150)
        results_tree.column('Status', width=100)

        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=results_tree.yview)
        results_tree.configure(yscrollcommand=scrollbar.set)

        results_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        selected_items = set()

        def toggle_selection(event):
            """Toggle selection on click"""
            item = results_tree.identify_row(event.y)
            if item:
                if item in selected_items:
                    selected_items.remove(item)
                    results_tree.item(item, values=('\u2610',) + results_tree.item(item, 'values')[1:])
                else:
                    selected_items.add(item)
                    results_tree.item(item, values=('\u2611',) + results_tree.item(item, 'values')[1:])

        results_tree.bind('<Button-1>', toggle_selection)

        def search_documents():
            """Search for documents"""
            for item in results_tree.get_children():
                results_tree.delete(item)
            selected_items.clear()

            student_id = student_search.get()
            doc_type = type_search.get()
            status = status_search.get()

            query = "SELECT id, student_id, document_type, status FROM documents WHERE 1=1"
            params = []

            if student_id:
                query += " AND student_id LIKE ?"
                params.append(f"%{escape_like(student_id)}%")
            if doc_type != 'All':
                query += " AND document_type = ?"
                params.append(doc_type)
            if status != 'All':
                query += " AND status = ?"
                params.append(status)

            query += " LIMIT 200"

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()

            for row in results:
                results_tree.insert('', 'end', values=('\u2610',) + row)

        ttk.Button(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.search', default="Search"),
                  command=search_documents).grid(row=0, column=6, padx=5)

        # Tab 2: Update Actions
        update_frame = ttk.Frame(notebook, padding=10)
        notebook.add(update_frame, text=_t('gui.shell.document_manager.bulk_operations.tabs.update_actions', default="Update Actions"))

        ttk.Label(update_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.select_update_action', default="Select Update Action"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        action_frame = ttk.LabelFrame(update_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_update_options', default="Bulk Update Options"), padding=15)
        action_frame.pack(fill='both', expand=True, pady=5)

        # Status update
        ttk.Label(action_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.update_status_to', default="Update Status To:")).grid(row=0, column=0, sticky='w', pady=10)
        new_status_combo = ttk.Combobox(action_frame, width=30, state='readonly')
        new_status_combo['values'] = ['Pending', 'Approved', 'Rejected', 'Under Review', 'Archived']
        new_status_combo.grid(row=0, column=1, sticky='ew', pady=10, padx=5)

        # Expiry date update
        ttk.Label(action_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.set_expiry_date', default="Set Expiry Date:")).grid(row=1, column=0, sticky='w', pady=10)
        expiry_entry = ttk.Entry(action_frame, width=32)
        expiry_entry.insert(0, "YYYY-MM-DD")
        expiry_entry.grid(row=1, column=1, sticky='ew', pady=10, padx=5)

        # Tags update
        ttk.Label(action_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.add_tags', default="Add Tags:")).grid(row=2, column=0, sticky='w', pady=10)
        tags_entry = ttk.Entry(action_frame, width=32)
        tags_entry.grid(row=2, column=1, sticky='ew', pady=10, padx=5)

        action_frame.columnconfigure(1, weight=1)

        def apply_bulk_update():
            """Apply bulk update to selected items"""
            if not selected_items:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.no_selection', default="No Selection"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_select_documents_to_update', default="Please select documents to update"))
                return

            new_status = new_status_combo.get()
            new_expiry = expiry_entry.get()
            new_tags = tags_entry.get()

            if not new_status and new_expiry == "YYYY-MM-DD" and not new_tags:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.no_changes', default="No Changes"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_specify_at_least_one_update_action', default="Please specify at least one update action"))
                return

            if not messagebox.askyesno(_t('gui.shell.document_manager.bulk_operations.dialogs.confirm_bulk_update', default="Confirm Bulk Update"),
                                      f"Update {len(selected_items)} documents?\n\n"
                                      "This operation cannot be undone."):
                return

            try:
                updated_count = 0
                for item in selected_items:
                    values = results_tree.item(item, 'values')
                    doc_id = values[1]  # Doc ID is second column

                    with transaction() as conn:
                        cursor = conn.cursor()

                        update_parts = []
                        params = []

                        if new_status:
                            update_parts.append("status = ?")
                            params.append(new_status)

                        if new_expiry and new_expiry != "YYYY-MM-DD":
                            update_parts.append("expiry_date = ?")
                            params.append(new_expiry)

                        if new_tags:
                            update_parts.append("tags = ?")
                            params.append(new_tags)

                        if update_parts:
                            update_parts.append("updated_at = CURRENT_TIMESTAMP")
                            params.append(doc_id)
                            query = "UPDATE documents SET " + ", ".join(update_parts) + " WHERE id = ?"
                            cursor.execute(query, params)
                            updated_count += 1

                messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.bulk_update_complete', default="Bulk Update Complete"),
                                  f"Successfully updated {updated_count} documents!")

                # Log activity
                self.gui.log_event('bulk_update', 'documents',
                              details=f'Updated {updated_count} documents')

                # Refresh search
                search_documents()

            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.update_error', default="Update Error"), f"Bulk update failed: {e}")

        ttk.Button(update_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.apply_bulk_update', default="Apply Bulk Update"),
                  command=apply_bulk_update).pack(pady=20)

        # Close button
        ttk.Button(update_window, text=_t('gui.shell.document_manager.bulk_operations.buttons.close', default="Close"),
                  command=update_window.destroy).pack(pady=10)

    def bulk_status_change(self):
        """Bulk change document status"""
        # This is now handled by bulk_update_from_search()
        self.bulk_update_from_search()

    def bulk_delete_documents(self):
        """Bulk delete documents with confirmation"""
        if not self.gui.ensure_login('admin'):
            return

        # Create delete window
        delete_window = tk.Toplevel(self.root)
        delete_window.title(_t('gui.shell.document_manager.bulk_operations.windows.bulk_delete_documents', default="Bulk Delete Documents"))
        delete_window.geometry("900x600")
        delete_window.transient(self.root)
        delete_window.grab_set()

        ttk.Label(delete_window, text=_t('gui.shell.document_manager.bulk_operations.labels.bulk_delete_documents', default="\u26a0\ufe0f Bulk Delete Documents"),
                 font=("Arial", 14, "bold"), foreground="red").pack(pady=10)

        # Warning
        warning_frame = ttk.LabelFrame(delete_window, text=_t('gui.shell.document_manager.bulk_operations.labels.warning', default="\u26a0\ufe0f WARNING"), padding=10)
        warning_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(warning_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.this_operation_is_permanent_and_cannot_be_undone_deleted_documen', default="This operation is PERMANENT and cannot be undone!\n"
                 "Deleted documents cannot be recovered."),
                 foreground="red", font=("Arial", 10, "bold")).pack()

        # Search criteria
        criteria_frame = ttk.LabelFrame(delete_window, text=_t('gui.shell.document_manager.bulk_operations.labels.select_documents_to_delete', default="Select Documents to Delete"), padding=10)
        criteria_frame.pack(fill='x', padx=10, pady=5)

        ttk.Label(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.status', default="Status:")).grid(row=0, column=0, sticky='w', padx=5)
        status_combo = ttk.Combobox(criteria_frame, width=20, state='readonly')
        status_combo['values'] = ['All', 'Pending', 'Rejected', 'Expired', 'Archived']
        status_combo.current(0)
        status_combo.grid(row=0, column=1, padx=5)

        ttk.Label(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.labels.older_than_days', default="Older than (days):")).grid(row=0, column=2, sticky='w', padx=5)
        days_entry = ttk.Entry(criteria_frame, width=10)
        days_entry.insert(0, "90")
        days_entry.grid(row=0, column=3, padx=5)

        # Results tree
        results_frame = ttk.Frame(delete_window)
        results_frame.pack(fill='both', expand=True, padx=10, pady=5)

        tree = ttk.Treeview(results_frame,
                           columns=('Select', 'ID', 'Student', 'Type', 'Status', 'Upload Date'),
                           show='headings', height=15)
        tree.heading('Select', text='\u2611')
        tree.heading('ID', text=_t('gui.shell.document_manager.bulk_operations.headings.doc_id', default='Doc ID'))
        tree.heading('Student', text=_t('gui.shell.document_manager.bulk_operations.headings.student_id', default='Student ID'))
        tree.heading('Type', text=_t('gui.shell.document_manager.bulk_operations.headings.type', default='Type'))
        tree.heading('Status', text=_t('gui.shell.document_manager.bulk_operations.headings.status', default='Status'))
        tree.heading('Upload Date', text=_t('gui.shell.document_manager.bulk_operations.headings.upload_date', default='Upload Date'))

        tree.column('Select', width=40)
        tree.column('ID', width=80)
        tree.column('Student', width=100)
        tree.column('Type', width=150)
        tree.column('Status', width=100)
        tree.column('Upload Date', width=120)

        scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        selected_items = set()

        def toggle_selection(event):
            item = tree.identify_row(event.y)
            if item:
                if item in selected_items:
                    selected_items.remove(item)
                    tree.item(item, values=('\u2610',) + tree.item(item, 'values')[1:])
                else:
                    selected_items.add(item)
                    tree.item(item, values=('\u2611',) + tree.item(item, 'values')[1:])

        tree.bind('<Button-1>', toggle_selection)

        def search_documents():
            for item in tree.get_children():
                tree.delete(item)
            selected_items.clear()

            status = status_combo.get()
            days = days_entry.get()

            query = "SELECT id, student_id, document_type, status, upload_date FROM documents WHERE 1=1"
            params = []

            if status != 'All':
                query += " AND status = ?"
                params.append(status)

            if days:
                query += " AND upload_date < DATE('now', '-' || ? || ' days')"
                params.append(days)

            query += " LIMIT 200"

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()

            for row in results:
                tree.insert('', 'end', values=('\u2610',) + row)

        def delete_selected():
            if not selected_items:
                messagebox.showwarning(_t('gui.shell.document_manager.bulk_operations.dialogs.no_selection', default="No Selection"), _t('gui.shell.document_manager.bulk_operations.dialogs.please_select_documents_to_delete', default="Please select documents to delete"))
                return

            if not messagebox.askyesno(_t('gui.shell.document_manager.bulk_operations.dialogs.confirm_delete', default="\u26a0\ufe0f CONFIRM DELETE"),
                                      f"Are you ABSOLUTELY SURE you want to DELETE {len(selected_items)} documents?\n\n"
                                      "This action is PERMANENT and CANNOT be undone!\n\n"
                                      "Type 'DELETE' in the next dialog to confirm.",
                                      icon='warning'):
                return

            # Extra confirmation
            confirm_dialog = tk.Toplevel(delete_window)
            confirm_dialog.title(_t('gui.shell.document_manager.bulk_operations.windows.confirm_deletion', default="Confirm Deletion"))
            confirm_dialog.geometry("400x150")
            confirm_dialog.transient(delete_window)
            confirm_dialog.grab_set()

            ttk.Label(confirm_dialog, text=_t('gui.shell.document_manager.bulk_operations.labels.type_delete_to_confirm', default="Type 'DELETE' to confirm:"),
                     font=("Arial", 11, "bold")).pack(pady=10)
            confirm_entry = ttk.Entry(confirm_dialog, width=30)
            confirm_entry.pack(pady=5)

            def execute_delete():
                if confirm_entry.get() != 'DELETE':
                    messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.confirmation_failed', default="Confirmation Failed"), _t('gui.shell.document_manager.bulk_operations.dialogs.you_must_type_delete_exactly', default="You must type 'DELETE' exactly"))
                    return

                try:
                    deleted_count = 0
                    for item in selected_items:
                        values = tree.item(item, 'values')
                        doc_id = values[1]

                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                        deleted_count += 1

                    messagebox.showinfo(_t('gui.shell.document_manager.bulk_operations.dialogs.deletion_complete', default="Deletion Complete"),
                                      f"Successfully deleted {deleted_count} documents")

                    self.gui.log_event('bulk_delete', 'documents',
                                  details=f'Deleted {deleted_count} documents')

                    confirm_dialog.destroy()
                    delete_window.destroy()

                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.bulk_operations.dialogs.delete_error', default="Delete Error"), f"Failed to delete documents: {e}")

            ttk.Button(confirm_dialog, text=_t('gui.shell.document_manager.bulk_operations.buttons.execute_delete', default="Execute Delete"),
                      command=execute_delete).pack(pady=10)

        ttk.Button(criteria_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.search', default="Search"), command=search_documents).grid(row=0, column=4, padx=5)

        # Button frame
        button_frame = ttk.Frame(delete_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.delete_selected', default="Delete Selected"),
                  command=delete_selected, style='Danger.TButton').pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.select_all', default="Select All"),
                  command=lambda: [selected_items.add(item) or tree.item(item, values=('\u2611',) + tree.item(item, 'values')[1:])
                                  for item in tree.get_children()]).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.deselect_all', default="Deselect All"),
                  command=lambda: [selected_items.clear() or tree.item(item, values=('\u2610',) + tree.item(item, 'values')[1:])
                                  for item in tree.get_children()]).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.bulk_operations.buttons.cancel', default="Cancel"),
                  command=delete_window.destroy).pack(side='right', padx=5)
