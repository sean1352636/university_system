"""Methods __init__ through show_integrity_cases."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from tkinter import ttk
from tkinter import filedialog
import json
import csv
from education_system.systems.university.domains.assessment.interfaces.gui.assignment_system._dialogs import messagebox
from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH

from .. import admin_tools_manager_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class AdminToolsManager:
    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure all admin tools tables exist"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Must match the canonical definition in db_manager.py
            # (synced_by is FK to users.id which is INTEGER).
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sis_sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type TEXT,
                    records_synced INTEGER DEFAULT 0,
                    records_failed INTEGER DEFAULT 0,
                    synced_by INTEGER,
                    synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    details_json TEXT,
                    FOREIGN KEY (synced_by) REFERENCES users (id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS grade_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    submission_id INTEGER,
                    student_id TEXT,
                    assignment_id INTEGER,
                    old_grade REAL,
                    new_grade REAL,
                    changed_by TEXT,
                    reason TEXT,
                    changed_at TEXT DEFAULT (datetime('now'))
                )
            ''')

            # Must match the canonical definitions in db_manager.py.
            # approved_by / assigned_by / user_id are FKs to users.id
            # which is INTEGER (not TEXT), and the role enum has all
            # four values from the canonical schema.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_accommodations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    accommodation_type TEXT DEFAULT 'other' CHECK (accommodation_type IN ('extended_time', 'alt_format', 'screen_reader', 'large_text', 'other')),
                    details TEXT,
                    time_multiplier REAL DEFAULT 1.0,
                    is_active INTEGER DEFAULT 1,
                    approved_by INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    FOREIGN KEY (student_id) REFERENCES students (student_id),
                    FOREIGN KEY (approved_by) REFERENCES users (id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ta_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    section_id TEXT,
                    module_code TEXT,
                    role TEXT DEFAULT 'ta' CHECK (role IN ('ta', 'lead_ta', 'grader', 'co_instructor')),
                    hours_per_week REAL DEFAULT 0,
                    can_grade INTEGER DEFAULT 1,
                    can_create_assignments INTEGER DEFAULT 0,
                    can_view_analytics INTEGER DEFAULT 1,
                    assigned_by INTEGER,
                    assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (module_code) REFERENCES modules (module_code),
                    FOREIGN KEY (assigned_by) REFERENCES users (id)
                )
            ''')

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error ensuring admin tools tables: {e}")

    def _check_permission(self, permission):
        """Check if user has permission, with role-based fallback for admin/faculty"""
        try:
            if self.auth.check_permission(permission):
                return True
        except (AttributeError, Exception):
            pass
        # Fallback: admin and faculty roles always have access
        try:
            role = getattr(self.auth, 'user_role', None)
            if role is None and hasattr(self.auth, 'current_user') and self.auth.current_user:
                role = self.auth.current_user.get('role', '')
            return str(role).lower() in ['admin', 'faculty', 'instructor', 'staff']
        except (AttributeError, Exception):
            return False

    def show_sis_sync(self):
        """SIS sync dashboard with import/export"""
        if not self._check_permission('manage_integrations'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.you_do_not_have_permission_to_manage_sis_sync', default="You do not have permission to manage SIS sync."))
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.labels.sis_roster_sync', default="SIS Roster Sync"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.buttons.import_roster_csv', default="Import Roster CSV"), command=self.import_roster_csv).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.buttons.sync_now', default="Sync Now"), command=self.sync_roster).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.buttons.refresh_log', default="Refresh Log"), command=self.show_sis_sync).pack(side='left', padx=5)

        # Field mapping info
        mapping_frame = ttk.LabelFrame(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.labels.csv_field_mapping', default="CSV Field Mapping"), padding=10)
        mapping_frame.pack(fill='x', pady=(0, 15))

        mapping_text = (
            "Expected CSV columns: student_id, first_name, last_name, email, "
            "module_code, section_id, enrollment_status"
        )
        ttk.Label(mapping_frame, text=mapping_text, wraplength=700).pack(anchor='w')

        # Sync log
        log_frame = ttk.LabelFrame(content, text=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.labels.sync_history', default="Sync History"), padding=10)
        log_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Type', 'Synced', 'Failed', 'By', 'Date')
        self.sync_tree = ttk.Treeview(log_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.sync_tree.heading(col, text=col)
        self.sync_tree.column('ID', width=50)
        self.sync_tree.column('Type', width=100)
        self.sync_tree.column('Synced', width=80)
        self.sync_tree.column('Failed', width=80)
        self.sync_tree.column('By', width=120)
        self.sync_tree.column('Date', width=160)

        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.sync_tree.yview)
        self.sync_tree.configure(yscrollcommand=scrollbar.set)
        self.sync_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Load sync history
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, sync_type, records_synced, records_failed, synced_by, synced_at
                FROM sis_sync_log ORDER BY synced_at DESC LIMIT 50
            ''')
            for row in cursor.fetchall():
                self.sync_tree.insert('', 'end', values=row)
            conn.close()
        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.error', default="Error"), f"Failed to load sync log: {e}")

    def import_roster_csv(self):
        """Import student roster from CSV file"""
        if not self._check_permission('manage_integrations'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.you_do_not_have_permission_to_import_rosters', default="You do not have permission to import rosters."))
            return

        file_path = filedialog.askopenfilename(
            title=_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.select_roster_csv', default="Select Roster CSV"),
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not file_path:
            return

        records_synced = 0
        records_failed = 0
        errors = []

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                required_fields = {'student_id', 'first_name', 'last_name', 'email'}
                if not required_fields.issubset(set(reader.fieldnames or [])):
                    missing = required_fields - set(reader.fieldnames or [])
                    messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.import_error', default="Import Error"), f"Missing required columns: {', '.join(missing)}")
                    conn.close()
                    return

                for row_num, row in enumerate(reader, start=2):
                    try:
                        student_id = row['student_id'].strip()
                        first_name = row['first_name'].strip()
                        last_name = row['last_name'].strip()
                        email = row['email'].strip()
                        module_code = row.get('module_code', '').strip()
                        section_id = row.get('section_id', '').strip()
                        enrollment_status = row.get('enrollment_status', 'active').strip()

                        if not student_id or not first_name or not last_name:
                            records_failed += 1
                            errors.append(f"Row {row_num}: Missing required fields")
                            continue

                        # Upsert student record. The CSV column is "email";
                        # the table column is email_address.
                        cursor.execute('''
                            INSERT INTO students (student_id, first_name, last_name, email_address)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(student_id) DO UPDATE SET
                                first_name = excluded.first_name,
                                last_name = excluded.last_name,
                                email_address = excluded.email_address
                        ''', (student_id, first_name, last_name, email))

                        # Enroll in module if provided
                        if module_code:
                            cursor.execute('''
                                INSERT OR IGNORE INTO student_modules (student_id, module_code, section_id, status)
                                VALUES (?, ?, ?, ?)
                            ''', (student_id, module_code, section_id, enrollment_status))

                        records_synced += 1
                    except Exception as row_err:
                        records_failed += 1
                        errors.append(f"Row {row_num}: {row_err}")

            # Log the sync
            current_user = getattr(self.auth, 'current_user', {})
            synced_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

            details = json.dumps({
                'file': file_path,
                'errors': errors[:50]
            })

            cursor.execute('''
                INSERT INTO sis_sync_log (sync_type, records_synced, records_failed, synced_by, details_json)
                VALUES (?, ?, ?, ?, ?)
            ''', ('csv_import', records_synced, records_failed, synced_by, details))

            conn.commit()
            conn.close()

            msg = f"Import complete.\nRecords synced: {records_synced}\nRecords failed: {records_failed}"
            if errors:
                msg += "\n\nFirst errors:\n" + "\n".join(errors[:10])
            messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.import_results', default="Import Results"), msg)

            # Refresh the sync log view
            self.show_sis_sync()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.import_error', default="Import Error"), f"Failed to import roster: {e}")

    def sync_roster(self):
        """Trigger manual sync with SIS"""
        if not self._check_permission('manage_integrations'):
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.access_denied', default="Access Denied"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.you_do_not_have_permission_to_sync_rosters', default="You do not have permission to sync rosters."))
            return

        if not messagebox.askyesno(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.confirm_sync', default="Confirm Sync"), _t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.trigger_a_manual_sis_roster_sync_this_will_re_validate_all_curre', default="Trigger a manual SIS roster sync?\n\nThis will re-validate all current enrollments.")):
            return

        records_synced = 0
        records_failed = 0

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Validate existing student-module enrollments
            cursor.execute('''
                SELECT sm.student_id, sm.module_code, sm.section_id
                FROM student_modules sm
                LEFT JOIN students s ON sm.student_id = s.student_id
            ''')
            enrollments = cursor.fetchall()

            for student_id, module_code, section_id in enrollments:
                try:
                    cursor.execute('SELECT 1 FROM students WHERE student_id = ?', (student_id,))
                    if cursor.fetchone():
                        records_synced += 1
                    else:
                        records_failed += 1
                except Exception:
                    records_failed += 1

            current_user = getattr(self.auth, 'current_user', {})
            synced_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

            details = json.dumps({
                'total_enrollments': len(enrollments),
                'validated': records_synced,
                'invalid': records_failed
            })

            cursor.execute('''
                INSERT INTO sis_sync_log (sync_type, records_synced, records_failed, synced_by, details_json)
                VALUES (?, ?, ?, ?, ?)
            ''', ('manual_sync', records_synced, records_failed, synced_by, details))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.sync_complete', default="Sync Complete"),
                                f"Sync complete.\nValidated: {records_synced}\nInvalid: {records_failed}")
            self.show_sis_sync()

        except Exception as e:
            messagebox.showerror(_t('gui.academics.assignment_system.admin_tools_manager_parts.admintoolsmanager_init.dialogs.sync_error', default="Sync Error"), f"Failed to sync roster: {e}")

    def show_integrity_cases(self):
        """Academic integrity cases (the Academic Integrity rules: officers
        see and decide every case; other staff see the cases they opened)."""
        from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.cases_panel import (
            build_cases_panel,
        )
        self.gui.layout.clear_content_area()
        build_cases_panel(self.gui.layout.content_area, self.auth)
