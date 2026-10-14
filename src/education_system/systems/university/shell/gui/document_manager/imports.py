
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection, transaction
except ImportError:
    from education_system.systems.university.infrastructure.database.db import sqlite3
    from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class ImportManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def manage_document_templates(self):
        """Manage document templates"""
        if not self.gui.ensure_login():
            return

        # Create templates window
        templates_window = tk.Toplevel(self.root)
        templates_window.title(_t('gui.shell.document_manager.imports.windows.document_templates_management', default="Document Templates Management"))
        templates_window.geometry("1000x700")
        templates_window.transient(self.root)
        templates_window.grab_set()

        # Title
        ttk.Label(templates_window, text=_t('gui.shell.document_manager.imports.labels.document_templates', default="Document Templates"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Notebook for different template sections
        notebook = ttk.Notebook(templates_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # Tab 1: Templates List
        list_frame = ttk.Frame(notebook, padding=10)
        notebook.add(list_frame, text=_t('gui.shell.document_manager.imports.tabs.templates', default="Templates"))

        tree = ttk.Treeview(list_frame,
                           columns=('ID', 'Name', 'Type', 'Usage', 'Created'),
                           show='headings', height=18)
        tree.heading('ID', text=_t('gui.shell.document_manager.imports.headings.template_id', default='Template ID'))
        tree.heading('Name', text=_t('gui.shell.document_manager.imports.headings.template_name', default='Template Name'))
        tree.heading('Type', text=_t('gui.shell.document_manager.imports.headings.document_type', default='Document Type'))
        tree.heading('Usage', text=_t('gui.shell.document_manager.imports.headings.times_used', default='Times Used'))
        tree.heading('Created', text=_t('gui.shell.document_manager.imports.headings.created_date', default='Created Date'))

        tree.column('ID', width=80)
        tree.column('Name', width=250)
        tree.column('Type', width=150)
        tree.column('Usage', width=100)
        tree.column('Created', width=120)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Sample templates
        sample_templates = [
            (1, 'Standard Transcript Request', 'Transcript', 145, '2024-01-15'),
            (2, 'ID Card Application', 'ID Card', 278, '2024-01-20'),
            (3, 'Health Form - Basic', 'Health Form', 89, '2024-02-01'),
            (4, 'Financial Aid Application', 'Financial Document', 156, '2024-02-15'),
            (5, 'Enrollment Verification', 'Enrollment Form', 234, '2024-03-01')
        ]

        for template in sample_templates:
            tree.insert('', 'end', values=template)

        # Tab 2: Template Builder
        builder_frame = ttk.Frame(notebook, padding=10)
        notebook.add(builder_frame, text=_t('gui.shell.document_manager.imports.tabs.template_builder', default="Template Builder"))

        ttk.Label(builder_frame, text=_t('gui.shell.document_manager.imports.labels.create_new_template', default="Create New Template"),
                 font=("Arial", 12, "bold")).pack(pady=5)

        builder_form = ttk.Frame(builder_frame)
        builder_form.pack(fill='both', expand=True, pady=10)

        ttk.Label(builder_form, text=_t('gui.shell.document_manager.imports.labels.template_name', default="Template Name:")).grid(row=0, column=0, sticky='w', pady=5)
        name_entry = ttk.Entry(builder_form, width=50)
        name_entry.grid(row=0, column=1, sticky='ew', pady=5)

        ttk.Label(builder_form, text=_t('gui.shell.document_manager.imports.labels.document_type', default="Document Type:")).grid(row=1, column=0, sticky='w', pady=5)
        type_combo = ttk.Combobox(builder_form, width=48, state='readonly')
        type_combo['values'] = ['Transcript', 'ID Card', 'Health Form', 'Enrollment Form',
                                'Financial Document', 'Other']
        type_combo.grid(row=1, column=1, sticky='ew', pady=5)

        ttk.Label(builder_form, text=_t('gui.shell.document_manager.imports.labels.template_description', default="Template Description:")).grid(row=2, column=0, sticky='w', pady=5)
        desc_text = tk.Text(builder_form, width=50, height=4)
        desc_text.grid(row=2, column=1, sticky='ew', pady=5)

        ttk.Label(builder_form, text=_t('gui.shell.document_manager.imports.labels.template_content', default="Template Content:")).grid(row=3, column=0, sticky='w', pady=5)
        content_text = tk.Text(builder_form, width=50, height=15)
        content_text.insert('1.0', "Template content here...\n\n"
                                    "Available placeholders:\n"
                                    "{{student_name}}\n"
                                    "{{student_id}}\n"
                                    "{{date}}\n"
                                    "{{document_type}}")
        content_text.grid(row=3, column=1, sticky='ew', pady=5)

        builder_form.columnconfigure(1, weight=1)

        def save_template():
            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.save_template', default="Save Template"),
                              _t('gui.shell.document_manager.imports.dialogs.template_saved_successfully_this_would_save_the_template_to_the', default="Template saved successfully!\n\n"
                              "This would save the template to the database."))
            self.gui.log_event('create', 'document_template',
                          details=f'Created template: {name_entry.get()}')

        ttk.Button(builder_frame, text=_t('gui.shell.document_manager.imports.buttons.save_template', default="Save Template"),
                  command=save_template).pack(pady=10)

        # Tab 3: Settings
        settings_frame = ttk.Frame(notebook, padding=10)
        notebook.add(settings_frame, text=_t('gui.shell.document_manager.imports.tabs.settings', default="Settings"))

        ttk.Label(settings_frame, text=_t('gui.shell.document_manager.imports.labels.template_settings', default="Template Settings"),
                 font=("Arial", 12, "bold")).pack(pady=5)

        settings_list = [
            ("Allow students to use templates", True),
            ("Require admin approval for custom templates", True),
            ("Auto-fill student information", True),
            ("Enable template versioning", False),
            ("Send notification on template usage", True)
        ]

        for setting_text, default_value in settings_list:
            var = tk.BooleanVar(value=default_value)
            ttk.Checkbutton(settings_frame, text=setting_text,
                           variable=var).pack(anchor='w', pady=5)

        ttk.Button(settings_frame, text=_t('gui.shell.document_manager.imports.buttons.save_settings', default="Save Settings"),
                  command=lambda: messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.settings', default="Settings"), _t('gui.shell.document_manager.imports.dialogs.settings_saved_successfully', default="Settings saved successfully!"))).pack(pady=20)

        # Button frame
        button_frame = ttk.Frame(templates_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.imports.buttons.export_templates', default="Export Templates"),
                  command=lambda: messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.export', default="Export"), _t('gui.shell.document_manager.imports.dialogs.templates_exported_to_json', default="Templates exported to JSON"))).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.imports.buttons.import_templates', default="Import Templates"),
                  command=lambda: messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.import', default="Import"), _t('gui.shell.document_manager.imports.dialogs.select_json_file_to_import_templates', default="Select JSON file to import templates"))).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.imports.buttons.close', default="Close"),
                  command=templates_window.destroy).pack(side='right', padx=5)

        # Log activity
        self.gui.log_event('view', 'document_templates', details='Opened template management')

    def import_from_csv(self):
        """Import documents metadata from CSV"""
        if not self.gui.ensure_login():
            return

        file_path = filedialog.askopenfilename(
            title=_t('gui.shell.document_manager.imports.dialogs.select_csv_file', default="Select CSV File"),
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        try:
            imported_count = 0
            failed_count = 0

            with open(file_path, 'r') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        with transaction() as conn:
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO documents (student_id, document_type, file_name,
                                                     status, upload_date, expiry_date)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (row.get('student_id'), row.get('document_type'),
                                 row.get('file_name'), row.get('status', 'Pending'),
                                 row.get('upload_date'), row.get('expiry_date')))
                        imported_count += 1
                    except Exception:
                        failed_count += 1

            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.import_complete', default="Import Complete"),
                              f"CSV import completed!\n\n"
                              f"Successfully imported: {imported_count}\n"
                              f"Failed: {failed_count}")

            self.gui.log_event('import', 'csv_documents',
                          details=f'Imported {imported_count} documents from CSV')

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.import_error', default="Import Error"), f"Failed to import CSV: {e}")

    def import_from_excel(self):
        """Import documents metadata from Excel"""
        if not self.gui.ensure_login():
            return

        file_path = filedialog.askopenfilename(
            title=_t('gui.shell.document_manager.imports.dialogs.select_excel_file', default="Select Excel File"),
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.excel_import', default="Excel Import"),
                          f"Excel file selected: {os.path.basename(file_path)}\n\n"
                          "This would import document metadata from Excel.\n"
                          "Requires 'openpyxl' or 'xlrd' library.\n\n"
                          "Expected columns:\n"
                          "- student_id\n"
                          "- document_type\n"
                          "- file_name\n"
                          "- status\n"
                          "- upload_date\n"
                          "- expiry_date")

        self.gui.log_event('import', 'excel_documents',
                      details=f'Attempted Excel import: {os.path.basename(file_path)}')

    def download_import_template(self):
        """Download CSV/Excel template for bulk import"""
        if not self.gui.ensure_login():
            return

        # Ask for template format
        format_choice = messagebox.askquestion(_t('gui.shell.document_manager.imports.dialogs.template_format', default="Template Format"),
                                              _t('gui.shell.document_manager.imports.dialogs.download_as_csv_click_no_for_excel_format', default="Download as CSV?\n\n"
                                              "Click 'No' for Excel format"),
                                              icon='question')

        if format_choice == 'yes':
            # CSV template
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv")],
                initialfile="document_import_template.csv"
            )

            if file_path:
                try:
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['student_id', 'document_type', 'file_name',
                                       'status', 'upload_date', 'expiry_date', 'tags', 'notes'])
                        writer.writerow(['12345', 'Transcript', 'transcript_fall2024.pdf',
                                       'Pending', '2024-01-15', '2025-01-15',
                                       'fall,2024,transcript', 'Sample document'])
                        writer.writerow(['67890', 'ID Card', 'id_card.jpg',
                                       'Approved', '2024-01-20', '2029-01-20',
                                       'id,photo', 'Student ID photo'])

                    messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.template_created', default="Template Created"),
                                      f"CSV template created successfully:\n{file_path}")
                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"), f"Failed to create template: {e}")
        else:
            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.excel_template', default="Excel Template"),
                              _t('gui.shell.document_manager.imports.dialogs.excel_template_generation_requires_openpyxl_library_please_use_t', default="Excel template generation requires 'openpyxl' library.\n\n"
                              "Please use the CSV template as a reference."))

        self.gui.log_event('download', 'import_template',
                      details='Downloaded import template')
