
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import csv
import json
import logging
from datetime import datetime

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


# ----------------------------------------------------------------------
# Document templates store.  No table held these before, so this module
# owns ``document_templates`` (created on first use, never seeded).  The
# template settings live in the module's existing ``system_settings``
# key/value table under ``document_templates.*`` keys.
# ----------------------------------------------------------------------

_TEMPLATES_DDL = """
CREATE TABLE IF NOT EXISTS document_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL UNIQUE,
    document_type TEXT,
    description TEXT,
    content TEXT NOT NULL,
    times_used INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
)
"""

TEMPLATE_SETTINGS = [
    ("allow_students", "Allow students to use templates", True),
    ("require_admin_approval", "Require admin approval for custom templates", True),
    ("auto_fill_student_info", "Auto-fill student information", True),
    ("versioning", "Enable template versioning", False),
    ("notify_on_use", "Send notification on template usage", True),
]

IMPORT_COLUMNS = ['student_id', 'document_type', 'file_name', 'status',
                  'upload_date', 'expiry_date', 'tags', 'notes']


def ensure_templates_table(conn):
    conn.execute(_TEMPLATES_DDL)


def list_templates():
    with get_connection() as conn:
        ensure_templates_table(conn)
        return [tuple(r) for r in conn.execute(
            "SELECT template_id, template_name, COALESCE(document_type, ''), times_used, "
            "date(created_at), COALESCE(description, ''), content "
            "FROM document_templates ORDER BY template_name").fetchall()]


def save_template_record(name, doc_type, description, content, actor):
    """Insert or update (by name). Returns 'created' or 'updated'."""
    with transaction() as conn:
        ensure_templates_table(conn)
        exists = conn.execute("SELECT 1 FROM document_templates WHERE template_name = ?",
                              (name,)).fetchone()
        if exists:
            conn.execute("UPDATE document_templates SET document_type = ?, description = ?, "
                         "content = ?, updated_at = datetime('now') WHERE template_name = ?",
                         (doc_type, description, content, name))
            return 'updated'
        conn.execute("INSERT INTO document_templates (template_name, document_type, description, "
                     "content, created_by) VALUES (?, ?, ?, ?, ?)",
                     (name, doc_type, description, content, actor))
        return 'created'


def load_template_settings():
    values = {key: default for key, _, default in TEMPLATE_SETTINGS}
    try:
        with get_connection() as conn:
            for key, value in conn.execute(
                    "SELECT key, value FROM system_settings WHERE key LIKE 'document_templates.%'"):
                short = key.split('.', 1)[1]
                if short in values:
                    values[short] = str(value) in ('1', 'true', 'True')
    except Exception as e:
        logger.debug("Template settings not readable: %s", e)
    return values


def save_template_settings(values):
    with transaction() as conn:
        for key, label, _ in TEMPLATE_SETTINGS:
            conn.execute("INSERT INTO system_settings (key, value, description, last_modified) "
                         "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                         "last_modified = CURRENT_TIMESTAMP",
                         (f"document_templates.{key}", '1' if values.get(key) else '0', label))


def active_document_type_names():
    try:
        with get_connection() as conn:
            return [r[0] for r in conn.execute(
                "SELECT type_name FROM document_types WHERE COALESCE(is_active, 1) = 1 "
                "ORDER BY sort_order, type_name")]
    except Exception:
        return []


def import_document_rows(rows, uploaded_by):
    """Import metadata rows (dicts keyed by IMPORT_COLUMNS).

    Each row must name an existing student and an active document type; it
    is written in both the upload shape (source_type/owner_id/type_id/
    verification_status) and the legacy columns other screens read.
    Returns (imported, errors) where errors is a list of "row N: reason".
    """
    imported, errors = 0, []
    with get_connection() as conn:
        students = {str(r[0]) for r in conn.execute("SELECT student_id FROM students")}
        types = {str(name).lower(): (tid, name) for tid, name in conn.execute(
            "SELECT type_id, type_name FROM document_types WHERE COALESCE(is_active, 1) = 1")}
    for n, row in enumerate(rows, start=2):
        row = {str(k).strip().lower(): ('' if v is None else str(v).strip()) for k, v in row.items() if k}
        student_id = row.get('student_id', '')
        type_key = row.get('document_type', '').lower()
        file_name = row.get('file_name', '')
        if not student_id or not type_key or not file_name:
            errors.append(f"row {n}: student_id, document_type and file_name are required")
            continue
        if student_id not in students:
            errors.append(f"row {n}: no student {student_id}")
            continue
        if type_key not in types:
            errors.append(f"row {n}: unknown document type '{row.get('document_type')}'")
            continue
        type_id, type_name = types[type_key]
        status = row.get('status') or 'Pending'
        upload_date = row.get('upload_date') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO documents (source_type, owner_id, owner_type, student_id,
                                           type_id, document_type, file_name, original_filename,
                                           status, verification_status, upload_date, expiry_date,
                                           tags, notes, uploaded_by, version_number,
                                           is_current_version, workflow_status)
                    VALUES ('student', ?, 'student', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 'submitted')
                """, (student_id, student_id, type_id, type_name, file_name, file_name,
                      status, status, upload_date, row.get('expiry_date') or None,
                      row.get('tags') or None, row.get('notes') or None, uploaded_by))
            imported += 1
        except Exception as e:
            errors.append(f"row {n}: {e}")
    return imported, errors


def _import_result_text(imported, errors):
    text = f"Successfully imported: {imported}\nFailed: {len(errors)}"
    if errors:
        text += "\n\n" + "\n".join(errors[:15])
        if len(errors) > 15:
            text += f"\n... and {len(errors) - 15} more"
    return text


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

        templates_cache = {}

        def refresh_templates():
            tree.delete(*tree.get_children())
            templates_cache.clear()
            try:
                rows = list_templates()
            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"),
                                     f"Could not load templates: {e}", parent=templates_window)
                return
            if not rows:
                tree.insert('', 'end', values=('', _t('gui.shell.document_manager.imports.labels.no_templates_yet',
                                                      default="No templates yet - create one in Template Builder"),
                                               '', '', ''))
                return
            for tid, name, dtype, used, created, desc, content in rows:
                templates_cache[str(tid)] = (name, dtype, desc, content)
                tree.insert('', 'end', iid=str(tid), values=(tid, name, dtype, used, created))

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
        type_combo['values'] = active_document_type_names() + ['Other']
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
            name = name_entry.get().strip()
            content = content_text.get('1.0', 'end-1c').strip()
            if not name or not content:
                messagebox.showwarning(_t('gui.shell.document_manager.imports.dialogs.save_template', default="Save Template"),
                                       _t('gui.shell.document_manager.imports.dialogs.name_and_content_required',
                                          default="Template name and content are required."),
                                       parent=templates_window)
                return
            actor = (self.gui.current_user or {}).get('username', 'unknown')
            try:
                outcome = save_template_record(name, type_combo.get().strip() or None,
                                               desc_text.get('1.0', 'end-1c').strip() or None,
                                               content, actor)
            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"),
                                     f"Could not save template: {e}", parent=templates_window)
                return
            self.gui.log_event('create' if outcome == 'created' else 'update', 'document_template',
                          details=f'{outcome.title()} template: {name}')
            refresh_templates()
            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.save_template', default="Save Template"),
                                f"Template '{name}' {outcome}.", parent=templates_window)

        def load_into_builder(_event=None):
            selected = tree.selection()
            if not selected or selected[0] not in templates_cache:
                return
            name, dtype, desc, content = templates_cache[selected[0]]
            name_entry.delete(0, 'end')
            name_entry.insert(0, name)
            type_combo.set(dtype or '')
            desc_text.delete('1.0', 'end')
            desc_text.insert('1.0', desc or '')
            content_text.delete('1.0', 'end')
            content_text.insert('1.0', content or '')
            notebook.select(builder_frame)

        tree.bind('<Double-1>', load_into_builder)

        ttk.Button(builder_frame, text=_t('gui.shell.document_manager.imports.buttons.save_template', default="Save Template"),
                  command=save_template).pack(pady=10)

        # Tab 3: Settings
        settings_frame = ttk.Frame(notebook, padding=10)
        notebook.add(settings_frame, text=_t('gui.shell.document_manager.imports.tabs.settings', default="Settings"))

        ttk.Label(settings_frame, text=_t('gui.shell.document_manager.imports.labels.template_settings', default="Template Settings"),
                 font=("Arial", 12, "bold")).pack(pady=5)

        current_settings = load_template_settings()
        setting_vars = {}
        for key, setting_text, _default in TEMPLATE_SETTINGS:
            var = tk.BooleanVar(value=current_settings.get(key, _default))
            setting_vars[key] = var
            ttk.Checkbutton(settings_frame, text=setting_text,
                           variable=var).pack(anchor='w', pady=5)

        def save_settings():
            try:
                save_template_settings({k: v.get() for k, v in setting_vars.items()})
            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"),
                                     f"Could not save settings: {e}", parent=templates_window)
                return
            self.gui.log_event('update', 'document_template_settings',
                               details={k: v.get() for k, v in setting_vars.items()})
            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.settings', default="Settings"),
                                _t('gui.shell.document_manager.imports.dialogs.settings_saved_successfully', default="Settings saved successfully!"),
                                parent=templates_window)

        ttk.Button(settings_frame, text=_t('gui.shell.document_manager.imports.buttons.save_settings', default="Save Settings"),
                  command=save_settings).pack(pady=20)

        # Button frame
        button_frame = ttk.Frame(templates_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        def export_templates():
            rows = list_templates()
            if not rows:
                messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.export', default="Export"),
                                    _t('gui.shell.document_manager.imports.dialogs.no_templates_to_export', default="There are no templates to export."),
                                    parent=templates_window)
                return
            path = filedialog.asksaveasfilename(parent=templates_window, defaultextension='.json',
                                                filetypes=[("JSON Files", "*.json")],
                                                initialfile="document_templates.json")
            if not path:
                return
            data = [{'template_name': name, 'document_type': dtype, 'description': desc,
                     'content': content} for _tid, name, dtype, _u, _c, desc, content in rows]
            try:
                with open(path, 'w', encoding='utf-8') as fh:
                    json.dump({'document_templates': data}, fh, indent=2)
            except OSError as e:
                messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"),
                                     f"Could not write file: {e}", parent=templates_window)
                return
            self.gui.log_event('export', 'document_templates', details=f'Exported {len(data)} templates')
            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.export', default="Export"),
                                f"Exported {len(data)} template(s) to:\n{path}", parent=templates_window)

        def import_templates():
            path = filedialog.askopenfilename(parent=templates_window,
                                              filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
            if not path:
                return
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    payload = json.load(fh)
                items = payload.get('document_templates', []) if isinstance(payload, dict) else payload
                if not isinstance(items, list):
                    raise ValueError("expected a list of templates")
            except (OSError, ValueError) as e:
                messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"),
                                     f"Could not read templates: {e}", parent=templates_window)
                return
            actor = (self.gui.current_user or {}).get('username', 'unknown')
            created = updated = skipped = 0
            for item in items:
                if not isinstance(item, dict) or not str(item.get('template_name') or '').strip() \
                        or not str(item.get('content') or '').strip():
                    skipped += 1
                    continue
                outcome = save_template_record(str(item['template_name']).strip(),
                                               item.get('document_type') or None,
                                               item.get('description') or None,
                                               str(item['content']), actor)
                if outcome == 'created':
                    created += 1
                else:
                    updated += 1
            refresh_templates()
            self.gui.log_event('import', 'document_templates',
                               details={'created': created, 'updated': updated, 'skipped': skipped})
            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.import', default="Import"),
                                f"Created: {created}\nUpdated: {updated}\nSkipped (invalid): {skipped}",
                                parent=templates_window)

        ttk.Button(button_frame, text=_t('gui.shell.document_manager.imports.buttons.export_templates', default="Export Templates"),
                  command=export_templates).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.imports.buttons.import_templates', default="Import Templates"),
                  command=import_templates).pack(side='left', padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.document_manager.imports.buttons.close', default="Close"),
                  command=templates_window.destroy).pack(side='right', padx=5)

        refresh_templates()

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
            with open(file_path, 'r', newline='', encoding='utf-8-sig') as f:
                rows = list(csv.DictReader(f))
            imported_count, errors = import_document_rows(
                rows, (self.gui.current_user or {}).get('username', 'unknown'))

            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.import_complete', default="Import Complete"),
                              "CSV import completed!\n\n" + _import_result_text(imported_count, errors),
                              parent=self.root)

            self.gui.log_event('import', 'csv_documents',
                          details=f'Imported {imported_count} documents from CSV ({len(errors)} failed)')

        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.import_error', default="Import Error"), f"Failed to import CSV: {e}",
                                 parent=self.root)

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

        try:
            from education_system.systems.university.infrastructure.utils.document_manager.import_export import (
                _read_excel_rows,
            )
            rows = _read_excel_rows(file_path)
        except ImportError:
            messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.excel_import', default="Excel Import"),
                                 _t('gui.shell.document_manager.imports.dialogs.openpyxl_missing',
                                    default="Excel import needs the 'openpyxl' library. Save the sheet as CSV and use CSV import."),
                                 parent=self.root)
            return
        except Exception as e:
            messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.import_error', default="Import Error"),
                                 f"Could not read {os.path.basename(file_path)} (.xlsx expected): {e}",
                                 parent=self.root)
            return

        imported_count, errors = import_document_rows(
            rows, (self.gui.current_user or {}).get('username', 'unknown'))
        messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.import_complete', default="Import Complete"),
                            f"Excel import of {os.path.basename(file_path)} completed!\n\n"
                            + _import_result_text(imported_count, errors), parent=self.root)

        self.gui.log_event('import', 'excel_documents',
                      details=f'Imported {imported_count} documents from {os.path.basename(file_path)} ({len(errors)} failed)')

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
                        csv.writer(f).writerow(IMPORT_COLUMNS)

                    messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.template_created', default="Template Created"),
                                      f"CSV template created successfully:\n{file_path}\n\n"
                                      + self._template_instructions(), parent=self.root)
                except Exception as e:
                    messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"), f"Failed to create template: {e}",
                                         parent=self.root)
                    return
            else:
                return
        else:
            file_path = filedialog.asksaveasfilename(
                parent=self.root,
                defaultextension=".xlsx",
                filetypes=[("Excel Files", "*.xlsx")],
                initialfile="document_import_template.xlsx"
            )
            if not file_path:
                return
            try:
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.title = "Documents"
                ws.append(IMPORT_COLUMNS)
                types_ws = wb.create_sheet("Document types")
                types_ws.append(["document_type (use one of these)"])
                for name in active_document_type_names():
                    types_ws.append([name])
                wb.save(file_path)
            except ImportError:
                messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.excel_template', default="Excel Template"),
                                     _t('gui.shell.document_manager.imports.dialogs.excel_template_generation_requires_openpyxl_library_please_use_t', default="Excel template generation requires 'openpyxl' library.\n\n"
                                     "Please use the CSV template as a reference."), parent=self.root)
                return
            except Exception as e:
                messagebox.showerror(_t('gui.shell.document_manager.imports.dialogs.error', default="Error"), f"Failed to create template: {e}",
                                     parent=self.root)
                return
            messagebox.showinfo(_t('gui.shell.document_manager.imports.dialogs.template_created', default="Template Created"),
                                f"Excel template created successfully:\n{file_path}\n\n"
                                + self._template_instructions(), parent=self.root)

        self.gui.log_event('download', 'import_template',
                      details='Downloaded import template')

    @staticmethod
    def _template_instructions():
        types = ", ".join(active_document_type_names()) or "(no active document types)"
        return ("Columns:\n"
                "- student_id: an existing student ID (required)\n"
                f"- document_type: one of {types} (required)\n"
                "- file_name: the document's file name (required)\n"
                "- status: Pending / Verified / Rejected (default Pending)\n"
                "- upload_date, expiry_date: YYYY-MM-DD\n"
                "- tags: comma-separated; notes: free text")
