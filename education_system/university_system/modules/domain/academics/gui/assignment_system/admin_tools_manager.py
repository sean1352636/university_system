"""Admin tools management - SIS sync, integrity cases, grade audit, accommodations, TA management"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import json
import csv
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class AdminToolsManager:
    """Admin tools for assignment system management"""

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

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sis_sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_type TEXT NOT NULL,
                    records_synced INTEGER DEFAULT 0,
                    records_failed INTEGER DEFAULT 0,
                    synced_by TEXT,
                    synced_at TEXT DEFAULT (datetime('now')),
                    details_json TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS integrity_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    assignment_id INTEGER,
                    case_type TEXT NOT NULL CHECK(case_type IN ('plagiarism','cheating','collusion','other')),
                    description TEXT,
                    evidence_path TEXT,
                    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','investigating','resolved','dismissed')),
                    outcome TEXT,
                    penalty TEXT,
                    created_by TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    resolved_at TEXT
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

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_accommodations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    accommodation_type TEXT NOT NULL CHECK(accommodation_type IN ('extended_time','alt_format','screen_reader','large_text','other')),
                    details TEXT,
                    time_multiplier REAL DEFAULT 1.0,
                    is_active INTEGER DEFAULT 1,
                    approved_by TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    expires_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ta_assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    section_id TEXT,
                    module_code TEXT,
                    role TEXT NOT NULL DEFAULT 'ta' CHECK(role IN ('ta','co_instructor')),
                    can_grade INTEGER DEFAULT 0,
                    can_create_assignments INTEGER DEFAULT 0,
                    can_view_analytics INTEGER DEFAULT 0,
                    assigned_by TEXT,
                    assigned_at TEXT DEFAULT (datetime('now'))
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

    # ─── SIS Sync ────────────────────────────────────────────────────────────

    def show_sis_sync(self):
        """SIS sync dashboard with import/export"""
        if not self._check_permission('manage_sis'):
            messagebox.showerror("Access Denied", "You do not have permission to manage SIS sync.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="SIS Roster Sync", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(btn_frame, text="Import Roster CSV", command=self.import_roster_csv).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Sync Now", command=self.sync_roster).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh Log", command=self.show_sis_sync).pack(side='left', padx=5)

        # Field mapping info
        mapping_frame = ttk.LabelFrame(content, text="CSV Field Mapping", padding=10)
        mapping_frame.pack(fill='x', pady=(0, 15))

        mapping_text = (
            "Expected CSV columns: student_id, first_name, last_name, email, "
            "module_code, section_id, enrollment_status"
        )
        ttk.Label(mapping_frame, text=mapping_text, wraplength=700).pack(anchor='w')

        # Sync log
        log_frame = ttk.LabelFrame(content, text="Sync History", padding=10)
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
            messagebox.showerror("Error", f"Failed to load sync log: {e}")

    def import_roster_csv(self):
        """Import student roster from CSV file"""
        if not self._check_permission('manage_sis'):
            messagebox.showerror("Access Denied", "You do not have permission to import rosters.")
            return

        file_path = filedialog.askopenfilename(
            title="Select Roster CSV",
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
                    messagebox.showerror("Import Error", f"Missing required columns: {', '.join(missing)}")
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

                        # Upsert student record
                        cursor.execute('''
                            INSERT INTO students (student_id, first_name, last_name, email)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(student_id) DO UPDATE SET
                                first_name = excluded.first_name,
                                last_name = excluded.last_name,
                                email = excluded.email
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
                msg += f"\n\nFirst errors:\n" + "\n".join(errors[:10])
            messagebox.showinfo("Import Results", msg)

            # Refresh the sync log view
            self.show_sis_sync()

        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import roster: {e}")

    def sync_roster(self):
        """Trigger manual sync with SIS"""
        if not self._check_permission('manage_sis'):
            messagebox.showerror("Access Denied", "You do not have permission to sync rosters.")
            return

        if not messagebox.askyesno("Confirm Sync", "Trigger a manual SIS roster sync?\n\nThis will re-validate all current enrollments."):
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

            messagebox.showinfo("Sync Complete",
                                f"Sync complete.\nValidated: {records_synced}\nInvalid: {records_failed}")
            self.show_sis_sync()

        except Exception as e:
            messagebox.showerror("Sync Error", f"Failed to sync roster: {e}")

    # ─── Academic Integrity Cases ────────────────────────────────────────────

    def show_integrity_cases(self):
        """Academic integrity case management dashboard"""
        if not self._check_permission('manage_integrity'):
            messagebox.showerror("Access Denied", "You do not have permission to manage integrity cases.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Academic Integrity Cases", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(btn_frame, text="New Case", command=self.create_integrity_case).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.show_integrity_cases).pack(side='left', padx=5)

        # Filter frame
        filter_frame = ttk.LabelFrame(content, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Status:").pack(side='left', padx=(0, 5))
        self.integrity_status_var = tk.StringVar(value='all')
        status_combo = ttk.Combobox(filter_frame, textvariable=self.integrity_status_var,
                                    values=['all', 'open', 'investigating', 'resolved', 'dismissed'],
                                    state='readonly', width=15)
        status_combo.pack(side='left', padx=5)

        ttk.Label(filter_frame, text="Type:").pack(side='left', padx=(15, 5))
        self.integrity_type_var = tk.StringVar(value='all')
        type_combo = ttk.Combobox(filter_frame, textvariable=self.integrity_type_var,
                                  values=['all', 'plagiarism', 'cheating', 'collusion', 'other'],
                                  state='readonly', width=15)
        type_combo.pack(side='left', padx=5)

        ttk.Button(filter_frame, text="Apply", command=self._load_integrity_cases).pack(side='left', padx=15)

        # Cases treeview
        cases_frame = ttk.Frame(content)
        cases_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Student', 'Assignment', 'Type', 'Status', 'Created', 'Outcome')
        self.integrity_tree = ttk.Treeview(cases_frame, columns=columns, show='headings', height=14)
        for col in columns:
            self.integrity_tree.heading(col, text=col)
        self.integrity_tree.column('ID', width=50)
        self.integrity_tree.column('Student', width=100)
        self.integrity_tree.column('Assignment', width=80)
        self.integrity_tree.column('Type', width=100)
        self.integrity_tree.column('Status', width=100)
        self.integrity_tree.column('Created', width=140)
        self.integrity_tree.column('Outcome', width=150)

        scrollbar = ttk.Scrollbar(cases_frame, orient='vertical', command=self.integrity_tree.yview)
        self.integrity_tree.configure(yscrollcommand=scrollbar.set)
        self.integrity_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.integrity_tree.bind('<Double-1>', lambda e: self._on_integrity_case_double_click())

        self._load_integrity_cases()

    def _load_integrity_cases(self):
        """Load integrity cases into treeview with current filters"""
        for item in self.integrity_tree.get_children():
            self.integrity_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, student_id, assignment_id, case_type, status, created_at, outcome
                FROM integrity_cases WHERE 1=1
            '''
            params = []

            status_filter = self.integrity_status_var.get()
            if status_filter != 'all':
                query += ' AND status = ?'
                params.append(status_filter)

            type_filter = self.integrity_type_var.get()
            if type_filter != 'all':
                query += ' AND case_type = ?'
                params.append(type_filter)

            query += ' ORDER BY created_at DESC LIMIT 100'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                self.integrity_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load integrity cases: {e}")

    def _on_integrity_case_double_click(self):
        """Handle double-click on integrity case"""
        selection = self.integrity_tree.selection()
        if selection:
            values = self.integrity_tree.item(selection[0], 'values')
            if values:
                self.review_integrity_case(values[0])

    def create_integrity_case(self):
        """Form to create new integrity case"""
        if not self._check_permission('manage_integrity'):
            messagebox.showerror("Access Denied", "You do not have permission to create integrity cases.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("New Academic Integrity Case")
        dialog.geometry("550x600")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="New Integrity Case", style='Title.TLabel').pack(anchor='w', pady=(0, 15))

        # Student ID
        ttk.Label(main_frame, text="Student ID:").pack(anchor='w', pady=(5, 2))
        student_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=student_var, width=40).pack(anchor='w')

        # Assignment ID
        ttk.Label(main_frame, text="Assignment ID (optional):").pack(anchor='w', pady=(10, 2))
        assignment_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=assignment_var, width=40).pack(anchor='w')

        # Case type
        ttk.Label(main_frame, text="Case Type:").pack(anchor='w', pady=(10, 2))
        type_var = tk.StringVar(value='plagiarism')
        ttk.Combobox(main_frame, textvariable=type_var,
                     values=['plagiarism', 'cheating', 'collusion', 'other'],
                     state='readonly', width=37).pack(anchor='w')

        # Description
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(10, 2))
        desc_text = scrolledtext.ScrolledText(main_frame, width=50, height=8)
        desc_text.pack(anchor='w')

        # Evidence path
        ttk.Label(main_frame, text="Evidence File (optional):").pack(anchor='w', pady=(10, 2))
        evidence_frame = ttk.Frame(main_frame)
        evidence_frame.pack(anchor='w', fill='x')
        evidence_var = tk.StringVar()
        ttk.Entry(evidence_frame, textvariable=evidence_var, width=35).pack(side='left')

        def browse_evidence():
            path = filedialog.askopenfilename(title="Select Evidence File")
            if path:
                evidence_var.set(path)

        ttk.Button(evidence_frame, text="Browse", command=browse_evidence).pack(side='left', padx=5)

        def save_case():
            student_id = student_var.get().strip()
            if not student_id:
                messagebox.showerror("Error", "Student ID is required.", parent=dialog)
                return

            description = desc_text.get('1.0', 'end').strip()
            if not description:
                messagebox.showerror("Error", "Description is required.", parent=dialog)
                return

            assignment_id = assignment_var.get().strip() or None
            if assignment_id:
                try:
                    assignment_id = int(assignment_id)
                except ValueError:
                    messagebox.showerror("Error", "Assignment ID must be a number.", parent=dialog)
                    return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                current_user = getattr(self.auth, 'current_user', {})
                created_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

                cursor.execute('''
                    INSERT INTO integrity_cases
                    (student_id, assignment_id, case_type, description, evidence_path, status, created_by)
                    VALUES (?, ?, ?, ?, ?, 'open', ?)
                ''', (student_id, assignment_id, type_var.get(), description,
                      evidence_var.get().strip() or None, created_by))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Integrity case created.", parent=dialog)
                dialog.destroy()
                self.show_integrity_cases()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create case: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Save Case", command=save_case).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def review_integrity_case(self, case_id):
        """Review/update an integrity case"""
        if not self._check_permission('manage_integrity'):
            messagebox.showerror("Access Denied", "You do not have permission to review integrity cases.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM integrity_cases WHERE id = ?', (case_id,))
            case = cursor.fetchone()
            col_names = [desc[0] for desc in cursor.description]
            conn.close()

            if not case:
                messagebox.showerror("Error", f"Case {case_id} not found.")
                return

            case_data = dict(zip(col_names, case))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load case: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Integrity Case #{case_id}")
        dialog.geometry("550x650")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"Case #{case_id}", style='Title.TLabel').pack(anchor='w', pady=(0, 15))

        # Info display
        info_frame = ttk.LabelFrame(main_frame, text="Case Details", padding=10)
        info_frame.pack(fill='x', pady=(0, 15))

        details = [
            ("Student ID", case_data.get('student_id', '')),
            ("Assignment ID", case_data.get('assignment_id', 'N/A')),
            ("Type", case_data.get('case_type', '')),
            ("Created By", case_data.get('created_by', '')),
            ("Created At", case_data.get('created_at', '')),
        ]
        for label, value in details:
            row = ttk.Frame(info_frame)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=f"{label}:", width=15, anchor='w').pack(side='left')
            ttk.Label(row, text=str(value)).pack(side='left')

        # Description (read-only)
        ttk.Label(main_frame, text="Description:").pack(anchor='w', pady=(5, 2))
        desc_text = scrolledtext.ScrolledText(main_frame, width=55, height=5)
        desc_text.pack(anchor='w')
        desc_text.insert('1.0', case_data.get('description', ''))
        desc_text.configure(state='disabled')

        # Evidence path
        evidence = case_data.get('evidence_path', '')
        if evidence:
            ttk.Label(main_frame, text=f"Evidence: {evidence}").pack(anchor='w', pady=(5, 0))

        # Editable fields
        ttk.Label(main_frame, text="Status:").pack(anchor='w', pady=(15, 2))
        status_var = tk.StringVar(value=case_data.get('status', 'open'))
        ttk.Combobox(main_frame, textvariable=status_var,
                     values=['open', 'investigating', 'resolved', 'dismissed'],
                     state='readonly', width=37).pack(anchor='w')

        ttk.Label(main_frame, text="Outcome:").pack(anchor='w', pady=(10, 2))
        outcome_var = tk.StringVar(value=case_data.get('outcome', '') or '')
        ttk.Entry(main_frame, textvariable=outcome_var, width=40).pack(anchor='w')

        ttk.Label(main_frame, text="Penalty:").pack(anchor='w', pady=(10, 2))
        penalty_var = tk.StringVar(value=case_data.get('penalty', '') or '')
        ttk.Entry(main_frame, textvariable=penalty_var, width=40).pack(anchor='w')

        def update_case():
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                resolved_at = None
                if status_var.get() in ('resolved', 'dismissed') and case_data.get('status') not in ('resolved', 'dismissed'):
                    resolved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                    UPDATE integrity_cases
                    SET status = ?, outcome = ?, penalty = ?, resolved_at = COALESCE(?, resolved_at)
                    WHERE id = ?
                ''', (status_var.get(), outcome_var.get().strip() or None,
                      penalty_var.get().strip() or None, resolved_at, case_id))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Case updated.", parent=dialog)
                dialog.destroy()
                self.show_integrity_cases()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update case: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Update Case", command=update_case).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side='left', padx=5)

    # ─── Grade Audit Log ─────────────────────────────────────────────────────

    def show_grade_audit_log(self):
        """View grade change audit trail with filters"""
        if not self._check_permission('view_audit_log'):
            messagebox.showerror("Access Denied", "You do not have permission to view the audit log.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Grade Change Audit Log", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filters
        filter_frame = ttk.LabelFrame(content, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Student ID:").pack(side='left', padx=(0, 5))
        self.audit_student_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_student_var, width=15).pack(side='left', padx=5)

        ttk.Label(filter_frame, text="Assignment ID:").pack(side='left', padx=(15, 5))
        self.audit_assignment_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_assignment_var, width=10).pack(side='left', padx=5)

        ttk.Label(filter_frame, text="Changed By:").pack(side='left', padx=(15, 5))
        self.audit_changed_by_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.audit_changed_by_var, width=15).pack(side='left', padx=5)

        ttk.Button(filter_frame, text="Search", command=self._load_audit_log).pack(side='left', padx=15)
        ttk.Button(filter_frame, text="Clear", command=self._clear_audit_filters).pack(side='left', padx=5)

        # Audit log treeview
        log_frame = ttk.Frame(content)
        log_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Submission', 'Student', 'Assignment', 'Old Grade', 'New Grade', 'Changed By', 'Reason', 'Date')
        self.audit_tree = ttk.Treeview(log_frame, columns=columns, show='headings', height=16)

        col_widths = {'ID': 40, 'Submission': 80, 'Student': 90, 'Assignment': 80,
                      'Old Grade': 75, 'New Grade': 75, 'Changed By': 100, 'Reason': 160, 'Date': 140}
        for col in columns:
            self.audit_tree.heading(col, text=col)
            self.audit_tree.column(col, width=col_widths.get(col, 100))

        scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=self.audit_tree.yview)
        self.audit_tree.configure(yscrollcommand=scrollbar.set)
        self.audit_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self._load_audit_log()

    def _load_audit_log(self):
        """Load audit log entries with current filters"""
        for item in self.audit_tree.get_children():
            self.audit_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, submission_id, student_id, assignment_id,
                       old_grade, new_grade, changed_by, reason, changed_at
                FROM grade_audit_log WHERE 1=1
            '''
            params = []

            student_filter = self.audit_student_var.get().strip()
            if student_filter:
                query += ' AND student_id = ?'
                params.append(student_filter)

            assignment_filter = self.audit_assignment_var.get().strip()
            if assignment_filter:
                query += ' AND assignment_id = ?'
                params.append(assignment_filter)

            changed_by_filter = self.audit_changed_by_var.get().strip()
            if changed_by_filter:
                query += ' AND changed_by LIKE ?'
                params.append(f'%{changed_by_filter}%')

            query += ' ORDER BY changed_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                self.audit_tree.insert('', 'end', values=row)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load audit log: {e}")

    def _clear_audit_filters(self):
        """Clear audit log filters and reload"""
        self.audit_student_var.set('')
        self.audit_assignment_var.set('')
        self.audit_changed_by_var.set('')
        self._load_audit_log()

    # ─── Accessibility Accommodations ────────────────────────────────────────

    def show_accommodations(self):
        """Manage student accessibility accommodations"""
        if not self._check_permission('manage_accommodations'):
            messagebox.showerror("Access Denied", "You do not have permission to manage accommodations.")
            return

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Student Accommodations", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Action buttons
        btn_frame = ttk.Frame(content)
        btn_frame.pack(fill='x', pady=(0, 15))

        ttk.Button(btn_frame, text="Add Accommodation", command=lambda: self.add_accommodation(None)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self.show_accommodations).pack(side='left', padx=5)

        # Filter
        filter_frame = ttk.LabelFrame(content, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(filter_frame, text="Student ID:").pack(side='left', padx=(0, 5))
        self.accom_student_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.accom_student_var, width=15).pack(side='left', padx=5)

        ttk.Label(filter_frame, text="Active Only:").pack(side='left', padx=(15, 5))
        self.accom_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, variable=self.accom_active_var).pack(side='left', padx=5)

        ttk.Button(filter_frame, text="Search", command=self._load_accommodations).pack(side='left', padx=15)

        # Accommodations treeview
        accom_frame = ttk.Frame(content)
        accom_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Student', 'Type', 'Details', 'Time Mult.', 'Active', 'Approved By', 'Expires')
        self.accom_tree = ttk.Treeview(accom_frame, columns=columns, show='headings', height=14)

        col_widths = {'ID': 40, 'Student': 90, 'Type': 110, 'Details': 180,
                      'Time Mult.': 75, 'Active': 55, 'Approved By': 100, 'Expires': 100}
        for col in columns:
            self.accom_tree.heading(col, text=col)
            self.accom_tree.column(col, width=col_widths.get(col, 100))

        scrollbar = ttk.Scrollbar(accom_frame, orient='vertical', command=self.accom_tree.yview)
        self.accom_tree.configure(yscrollcommand=scrollbar.set)
        self.accom_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Double-click to edit
        self.accom_tree.bind('<Double-1>', lambda e: self._on_accommodation_double_click())

        # Bottom buttons
        bottom_frame = ttk.Frame(content)
        bottom_frame.pack(fill='x', pady=(10, 0))
        ttk.Button(bottom_frame, text="Deactivate Selected", command=self._deactivate_accommodation).pack(side='left', padx=5)

        self._load_accommodations()

    def _load_accommodations(self):
        """Load accommodations into treeview"""
        for item in self.accom_tree.get_children():
            self.accom_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, student_id, accommodation_type, details, time_multiplier,
                       is_active, approved_by, expires_at
                FROM student_accommodations WHERE 1=1
            '''
            params = []

            student_filter = self.accom_student_var.get().strip()
            if student_filter:
                query += ' AND student_id = ?'
                params.append(student_filter)

            if self.accom_active_var.get():
                query += ' AND is_active = 1'

            query += ' ORDER BY created_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                display_row = list(row)
                display_row[5] = 'Yes' if display_row[5] else 'No'
                self.accom_tree.insert('', 'end', values=display_row)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load accommodations: {e}")

    def _on_accommodation_double_click(self):
        """Handle double-click on accommodation row"""
        selection = self.accom_tree.selection()
        if selection:
            values = self.accom_tree.item(selection[0], 'values')
            if values:
                self.add_accommodation(values[1])

    def _deactivate_accommodation(self):
        """Deactivate the selected accommodation"""
        selection = self.accom_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "No accommodation selected.")
            return

        values = self.accom_tree.item(selection[0], 'values')
        accom_id = values[0]

        if not messagebox.askyesno("Confirm", f"Deactivate accommodation #{accom_id}?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('UPDATE student_accommodations SET is_active = 0 WHERE id = ?', (accom_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "Accommodation deactivated.")
            self._load_accommodations()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to deactivate: {e}")

    def add_accommodation(self, student_id):
        """Add accommodation for a student"""
        if not self._check_permission('manage_accommodations'):
            messagebox.showerror("Access Denied", "You do not have permission to manage accommodations.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Add Student Accommodation")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Add Accommodation", style='Title.TLabel').pack(anchor='w', pady=(0, 15))

        # Student ID
        ttk.Label(main_frame, text="Student ID:").pack(anchor='w', pady=(5, 2))
        student_var = tk.StringVar(value=student_id or '')
        ttk.Entry(main_frame, textvariable=student_var, width=40).pack(anchor='w')

        # Accommodation type
        ttk.Label(main_frame, text="Accommodation Type:").pack(anchor='w', pady=(10, 2))
        type_var = tk.StringVar(value='extended_time')
        ttk.Combobox(main_frame, textvariable=type_var,
                     values=['extended_time', 'alt_format', 'screen_reader', 'large_text', 'other'],
                     state='readonly', width=37).pack(anchor='w')

        # Details
        ttk.Label(main_frame, text="Details:").pack(anchor='w', pady=(10, 2))
        details_text = scrolledtext.ScrolledText(main_frame, width=50, height=5)
        details_text.pack(anchor='w')

        # Time multiplier
        ttk.Label(main_frame, text="Time Multiplier (e.g. 1.5 for 50% extra):").pack(anchor='w', pady=(10, 2))
        multiplier_var = tk.StringVar(value='1.0')
        ttk.Entry(main_frame, textvariable=multiplier_var, width=10).pack(anchor='w')

        # Expires at
        ttk.Label(main_frame, text="Expires (YYYY-MM-DD, leave blank for no expiry):").pack(anchor='w', pady=(10, 2))
        expires_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=expires_var, width=20).pack(anchor='w')

        def save_accommodation():
            sid = student_var.get().strip()
            if not sid:
                messagebox.showerror("Error", "Student ID is required.", parent=dialog)
                return

            try:
                time_mult = float(multiplier_var.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Time multiplier must be a number.", parent=dialog)
                return

            expires = expires_var.get().strip() or None
            if expires:
                try:
                    datetime.strptime(expires, '%Y-%m-%d')
                except ValueError:
                    messagebox.showerror("Error", "Expiry date must be YYYY-MM-DD.", parent=dialog)
                    return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                current_user = getattr(self.auth, 'current_user', {})
                approved_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

                cursor.execute('''
                    INSERT INTO student_accommodations
                    (student_id, accommodation_type, details, time_multiplier, is_active, approved_by, expires_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                ''', (sid, type_var.get(), details_text.get('1.0', 'end').strip(),
                      time_mult, approved_by, expires))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Accommodation added.", parent=dialog)
                dialog.destroy()
                self.show_accommodations()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to add accommodation: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=save_accommodation).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    # ─── TA / Co-Instructor Management ───────────────────────────────────────

    def show_ta_management(self):
        """Unified TA/co-instructor management with assignments, permissions, and evaluation"""
        if not self._check_permission('manage_tas'):
            messagebox.showerror("Access Denied", "You do not have permission to manage TA assignments.")
            return

        self._ensure_ta_evaluation_table()

        self.gui.layout.clear_content_area()
        content = self.gui.layout.content_area

        title = ttk.Label(content, text="Teaching Assistant Management", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 10))

        # Tabbed notebook for TA features
        notebook = ttk.Notebook(content)
        notebook.pack(fill='both', expand=True)

        # ── Tab 1: TA Assignments ──
        assign_frame = ttk.Frame(notebook)
        notebook.add(assign_frame, text="TA Assignments")
        self._build_ta_assignments_tab(assign_frame)

        # ── Tab 2: Permissions ──
        perm_frame = ttk.Frame(notebook)
        notebook.add(perm_frame, text="Permissions")
        self._build_ta_permissions_tab(perm_frame)

        # ── Tab 3: Performance Evaluation ──
        eval_frame = ttk.Frame(notebook)
        notebook.add(eval_frame, text="Performance Evaluation")
        self._build_ta_evaluation_tab(eval_frame)

    def _ensure_ta_evaluation_table(self):
        """Ensure ta_evaluations table exists"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ta_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ta_id TEXT NOT NULL,
                    module_code TEXT NOT NULL,
                    evaluation_period TEXT,
                    hours_logged REAL DEFAULT 0,
                    avg_grading_turnaround_days REAL DEFAULT 0,
                    submissions_graded INTEGER DEFAULT 0,
                    feedback_score REAL,
                    evaluator_id TEXT,
                    evaluated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # Tab 1: TA Assignments
    # ──────────────────────────────────────────────────────────────

    def _build_ta_assignments_tab(self, parent):
        """Build the TA assignments management tab"""
        # Action buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(10, 5))

        ttk.Button(btn_frame, text="Assign TA", command=lambda: self.assign_ta(None)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="View Workload", command=self._view_ta_workload).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_ta_assignments).pack(side='right', padx=5)

        # Filter bar
        filter_frame = ttk.Frame(parent)
        filter_frame.pack(fill='x', padx=10, pady=(0, 5))

        ttk.Label(filter_frame, text="Module:").pack(side='left', padx=(0, 5))
        self.ta_module_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.ta_module_var, width=15).pack(side='left', padx=5)

        ttk.Label(filter_frame, text="Role:").pack(side='left', padx=(15, 5))
        self.ta_role_var = tk.StringVar(value='all')
        ttk.Combobox(filter_frame, textvariable=self.ta_role_var,
                     values=['all', 'ta', 'lead_ta', 'grader', 'co_instructor'],
                     state='readonly', width=15).pack(side='left', padx=5)

        ttk.Button(filter_frame, text="Search", command=self._load_ta_assignments).pack(side='left', padx=15)
        ttk.Button(filter_frame, text="Clear", command=self._clear_ta_filter).pack(side='left', padx=5)

        # TA assignments treeview
        ta_frame = ttk.Frame(parent)
        ta_frame.pack(fill='both', expand=True, padx=10)

        columns = ('ID', 'User', 'Section', 'Module', 'Role', 'Hours/Wk',
                   'Grade', 'Create', 'Analytics', 'Assigned By', 'Date')
        self.ta_tree = ttk.Treeview(ta_frame, columns=columns, show='headings', height=12)

        col_widths = {'ID': 35, 'User': 80, 'Section': 70, 'Module': 75, 'Role': 85,
                      'Hours/Wk': 65, 'Grade': 45, 'Create': 50, 'Analytics': 60,
                      'Assigned By': 90, 'Date': 110}
        for col in columns:
            self.ta_tree.heading(col, text=col)
            self.ta_tree.column(col, width=col_widths.get(col, 70))

        scrollbar = ttk.Scrollbar(ta_frame, orient='vertical', command=self.ta_tree.yview)
        self.ta_tree.configure(yscrollcommand=scrollbar.set)
        self.ta_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.ta_tree.bind('<Double-1>', lambda e: self._on_ta_double_click())

        # Bottom buttons
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill='x', padx=10, pady=(5, 10))
        ttk.Button(bottom_frame, text="Edit Permissions", command=self._edit_selected_ta_permissions).pack(side='left', padx=5)
        ttk.Button(bottom_frame, text="Remove Assignment", command=self._remove_ta_assignment).pack(side='left', padx=5)

        self._load_ta_assignments()

    def _clear_ta_filter(self):
        """Clear TA filter and reload"""
        self.ta_module_var.set('')
        self.ta_role_var.set('all')
        self._load_ta_assignments()

    def _load_ta_assignments(self):
        """Load TA assignments into treeview"""
        for item in self.ta_tree.get_children():
            self.ta_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            query = '''
                SELECT id, user_id, section_id, module_code, role,
                       COALESCE(hours_per_week, 0),
                       can_grade, can_create_assignments, can_view_analytics,
                       assigned_by, assigned_at
                FROM ta_assignments WHERE 1=1
            '''
            params = []

            module_filter = self.ta_module_var.get().strip()
            if module_filter:
                query += ' AND module_code LIKE ?'
                params.append(f'%{module_filter}%')

            role_filter = self.ta_role_var.get()
            if role_filter != 'all':
                query += ' AND role = ?'
                params.append(role_filter)

            query += ' ORDER BY assigned_at DESC LIMIT 200'

            cursor.execute(query, params)
            for row in cursor.fetchall():
                display_row = list(row)
                display_row[6] = 'Yes' if display_row[6] else 'No'
                display_row[7] = 'Yes' if display_row[7] else 'No'
                display_row[8] = 'Yes' if display_row[8] else 'No'
                self.ta_tree.insert('', 'end', values=display_row)

            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load TA assignments: {e}")

    def _on_ta_double_click(self):
        """Handle double-click on TA assignment"""
        selection = self.ta_tree.selection()
        if selection:
            values = self.ta_tree.item(selection[0], 'values')
            if values:
                self.configure_ta_permissions(values[0])

    def _edit_selected_ta_permissions(self):
        """Edit permissions for selected TA"""
        selection = self.ta_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "No TA assignment selected.")
            return
        values = self.ta_tree.item(selection[0], 'values')
        if values:
            self.configure_ta_permissions(values[0])

    def _remove_ta_assignment(self):
        """Remove the selected TA assignment with email notification"""
        selection = self.ta_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "No TA assignment selected.")
            return

        values = self.ta_tree.item(selection[0], 'values')
        ta_id = values[0]
        user_id = values[1]
        module_code = values[3]

        if not messagebox.askyesno("Confirm",
                f"Remove TA assignment #{ta_id}?\n\nUser: {user_id}\nModule: {module_code}"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('DELETE FROM ta_assignments WHERE id = ?', (ta_id,))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", "TA assignment removed.")
            self._send_ta_email(user_id, module_code, '', 0, 'removed')
            self._load_ta_assignments()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove assignment: {e}")

    def _view_ta_workload(self):
        """Show workload details for the selected TA"""
        selection = self.ta_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Select a TA to view workload.")
            return

        values = self.ta_tree.item(selection[0], 'values')
        user_id = values[1]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, section_id, module_code, role,
                       COALESCE(hours_per_week, 0) as hours, assigned_at
                FROM ta_assignments WHERE user_id = ?
            ''', (user_id,))
            assignments = cursor.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load workload: {e}")
            return

        total_hours = sum(a[4] for a in assignments)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"TA Workload - {user_id}")
        dialog.geometry("600x400")
        dialog.transient(self.root)

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill='both', expand=True)

        summary_frame = ttk.LabelFrame(main_frame, text="Workload Summary", padding=10)
        summary_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(summary_frame, text=f"User: {user_id}", font=('Arial', 11)).pack(anchor='w')
        ttk.Label(summary_frame, text=f"Active Assignments: {len(assignments)}", font=('Arial', 11)).pack(anchor='w')
        ttk.Label(summary_frame, text=f"Total Hours/Week: {total_hours}", font=('Arial', 11)).pack(anchor='w')

        if total_hours > 20:
            ttk.Label(summary_frame,
                      text="WARNING: Exceeds 20 hours/week across TA assignments.",
                      foreground='red', font=('Arial', 10, 'bold')).pack(anchor='w', pady=(5, 0))

        if assignments:
            detail_frame = ttk.LabelFrame(main_frame, text="Assignment Details", padding=5)
            detail_frame.pack(fill='both', expand=True)

            columns = ('Module', 'Role', 'Hours/Wk', 'Section', 'Assigned')
            detail_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=8)
            for col in columns:
                detail_tree.heading(col, text=col)
                detail_tree.column(col, width=110)

            for a in assignments:
                detail_tree.insert('', 'end', values=(a[2], a[3], a[4], a[1] or 'N/A', a[5] or ''))

            detail_tree.pack(fill='both', expand=True)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(10, 0))

    def assign_ta(self, section_id):
        """Assign TA with student/module dropdowns, roles, hours, and permissions"""
        if not self._check_permission('manage_tas'):
            messagebox.showerror("Access Denied", "You do not have permission to assign TAs.")
            return

        # Fetch students for dropdown
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name")
            students = cursor.fetchall()
            cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
            modules = cursor.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {e}")
            return

        student_map = {}
        student_values = []
        for s in students:
            display = f"{s[0]} - {s[1]} {s[2]}"
            student_values.append(display)
            student_map[display] = s[0]

        module_map = {}
        module_values = []
        for m in modules:
            display = f"{m[0]} - {m[1]}"
            module_values.append(display)
            module_map[display] = m[0]

        dialog = tk.Toplevel(self.root)
        dialog.title("Assign Teaching Assistant")
        dialog.geometry("480x550")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text="Assign TA / Co-Instructor", font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 10))

        # Student dropdown
        ttk.Label(main_frame, text="Student:").pack(anchor='w', pady=(5, 2))
        student_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=student_var, values=student_values,
                     state='readonly', width=45).pack(anchor='w')

        # Module dropdown
        ttk.Label(main_frame, text="Module:").pack(anchor='w', pady=(10, 2))
        module_var = tk.StringVar()
        ttk.Combobox(main_frame, textvariable=module_var, values=module_values,
                     state='readonly', width=45).pack(anchor='w')

        # Section ID
        ttk.Label(main_frame, text="Section ID (optional):").pack(anchor='w', pady=(10, 2))
        section_var = tk.StringVar(value=section_id or '')
        ttk.Entry(main_frame, textvariable=section_var, width=35).pack(anchor='w')

        # Role
        ttk.Label(main_frame, text="Role:").pack(anchor='w', pady=(10, 2))
        role_var = tk.StringVar(value='ta')
        ttk.Combobox(main_frame, textvariable=role_var,
                     values=['ta', 'lead_ta', 'grader', 'co_instructor'],
                     state='readonly', width=25).pack(anchor='w')

        # Hours per week
        ttk.Label(main_frame, text="Hours/Week:").pack(anchor='w', pady=(10, 2))
        hours_var = tk.StringVar(value='10')
        ttk.Entry(main_frame, textvariable=hours_var, width=10).pack(anchor='w')

        # Permissions
        perm_frame = ttk.LabelFrame(main_frame, text="Permissions", padding=10)
        perm_frame.pack(fill='x', pady=(15, 0))

        can_grade_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(perm_frame, text="Can Grade Submissions", variable=can_grade_var).pack(anchor='w', pady=2)
        can_create_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(perm_frame, text="Can Create Assignments", variable=can_create_var).pack(anchor='w', pady=2)
        can_analytics_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(perm_frame, text="Can View Analytics", variable=can_analytics_var).pack(anchor='w', pady=2)

        def save_assignment():
            student_selection = student_var.get().strip()
            module_selection = module_var.get().strip()

            if not student_selection:
                messagebox.showwarning("Validation", "Please select a student.", parent=dialog)
                return
            if not module_selection:
                messagebox.showwarning("Validation", "Please select a module.", parent=dialog)
                return

            uid = student_map.get(student_selection, '')
            mc = module_map.get(module_selection, '')
            sid = section_var.get().strip() or None

            try:
                hours = float(hours_var.get())
                if hours <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Validation", "Hours/Week must be a positive number.", parent=dialog)
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                current_user = getattr(self.auth, 'current_user', {})
                assigned_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

                cursor.execute('''
                    INSERT INTO ta_assignments
                    (user_id, section_id, module_code, role, hours_per_week,
                     can_grade, can_create_assignments, can_view_analytics, assigned_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (uid, sid, mc, role_var.get(), hours,
                      int(can_grade_var.get()), int(can_create_var.get()),
                      int(can_analytics_var.get()), assigned_by))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", f"TA assigned: {uid} to {mc}", parent=dialog)
                dialog.destroy()
                self._send_ta_email(uid, mc, role_var.get(), hours, 'assigned')
                self._load_ta_assignments()

            except sqlite3.IntegrityError:
                messagebox.showerror("Duplicate", f"This student is already a TA for module '{mc}'.", parent=dialog)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create assignment: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Assign", command=save_assignment).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=10)

    def configure_ta_permissions(self, ta_id):
        """Configure TA role and permissions"""
        if not self._check_permission('manage_tas'):
            messagebox.showerror("Access Denied", "You do not have permission to manage TA permissions.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ta_assignments WHERE id = ?', (ta_id,))
            ta = cursor.fetchone()
            col_names = [desc[0] for desc in cursor.description]
            conn.close()

            if not ta:
                messagebox.showerror("Error", f"TA assignment #{ta_id} not found.")
                return

            ta_data = dict(zip(col_names, ta))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load TA assignment: {e}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Configure Permissions - TA #{ta_id}")
        dialog.geometry("480x500")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        ttk.Label(main_frame, text=f"TA Permissions - #{ta_id}", font=('Arial', 14, 'bold')).pack(anchor='w', pady=(0, 15))

        # Info display
        info_frame = ttk.LabelFrame(main_frame, text="Assignment Details", padding=10)
        info_frame.pack(fill='x', pady=(0, 15))

        for label, value in [("User", ta_data.get('user_id', '')),
                             ("Section", ta_data.get('section_id', 'N/A')),
                             ("Module", ta_data.get('module_code', 'N/A'))]:
            row = ttk.Frame(info_frame)
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=f"{label}:", width=12, anchor='w').pack(side='left')
            ttk.Label(row, text=str(value)).pack(side='left')

        # Role
        ttk.Label(main_frame, text="Role:").pack(anchor='w', pady=(10, 2))
        role_var = tk.StringVar(value=ta_data.get('role', 'ta'))
        ttk.Combobox(main_frame, textvariable=role_var,
                     values=['ta', 'lead_ta', 'grader', 'co_instructor'],
                     state='readonly', width=25).pack(anchor='w')

        # Hours
        ttk.Label(main_frame, text="Hours/Week:").pack(anchor='w', pady=(10, 2))
        hours_var = tk.StringVar(value=str(ta_data.get('hours_per_week', 0) or 0))
        ttk.Entry(main_frame, textvariable=hours_var, width=10).pack(anchor='w')

        # Permissions
        perm_frame = ttk.LabelFrame(main_frame, text="Permissions", padding=10)
        perm_frame.pack(fill='x', pady=(15, 0))

        can_grade_var = tk.BooleanVar(value=bool(ta_data.get('can_grade', 0)))
        ttk.Checkbutton(perm_frame, text="Can Grade Submissions", variable=can_grade_var).pack(anchor='w', pady=2)

        can_create_var = tk.BooleanVar(value=bool(ta_data.get('can_create_assignments', 0)))
        ttk.Checkbutton(perm_frame, text="Can Create Assignments", variable=can_create_var).pack(anchor='w', pady=2)

        can_analytics_var = tk.BooleanVar(value=bool(ta_data.get('can_view_analytics', 0)))
        ttk.Checkbutton(perm_frame, text="Can View Analytics", variable=can_analytics_var).pack(anchor='w', pady=2)

        def update_permissions():
            try:
                hours = float(hours_var.get()) if hours_var.get().strip() else 0
            except ValueError:
                messagebox.showwarning("Validation", "Hours must be a number.", parent=dialog)
                return

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE ta_assignments
                    SET role = ?, hours_per_week = ?, can_grade = ?,
                        can_create_assignments = ?, can_view_analytics = ?
                    WHERE id = ?
                ''', (role_var.get(), hours, int(can_grade_var.get()),
                      int(can_create_var.get()), int(can_analytics_var.get()), ta_id))
                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Permissions updated.", parent=dialog)
                dialog.destroy()
                self._load_ta_assignments()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to update permissions: {e}", parent=dialog)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Save", command=update_permissions).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

    def _send_ta_email(self, student_id, module_code, role_type, hours_per_week, action):
        """Email student about TA assignment or removal"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT first_name, last_name, email FROM students WHERE student_id = ?", (student_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT first_name, last_name, email FROM users WHERE username = ?", (student_id,))
                row = cursor.fetchone()
            conn.close()

            if not row or not row[2]:
                return

            name = f"{row[0]} {row[1]}"
            email = row[2]

            if action == 'assigned':
                subject = f"TA Assignment: {module_code}"
                body = (f"Dear {name},\n\nYou have been assigned as a Teaching Assistant:\n\n"
                        f"Module: {module_code}\nRole: {role_type}\nHours per Week: {hours_per_week}\n\n"
                        f"Please contact the module instructor for further details.\n\n"
                        f"Best regards,\nAcademic Administration")
            elif action == 'removed':
                subject = f"TA Assignment Removed: {module_code}"
                body = (f"Dear {name},\n\nYour Teaching Assistant assignment has been removed:\n\n"
                        f"Module: {module_code}\n\nIf you believe this is an error, please contact "
                        f"the module instructor.\n\nBest regards,\nAcademic Administration")
            else:
                return

            send_email(recipient_email=email, subject=subject, body=body)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # Tab 2: Permissions (granular module-level)
    # ──────────────────────────────────────────────────────────────

    PERMISSION_TYPES = [
        ('grade_assignments', 'Grade Assignments'),
        ('take_attendance', 'Take Attendance'),
        ('upload_materials', 'Upload Materials'),
        ('manage_discussions', 'Manage Discussions'),
        ('view_student_info', 'View Student Info'),
    ]

    def _build_ta_permissions_tab(self, parent):
        """Build the granular module-level permissions tab"""
        # Selector
        selector_frame = ttk.LabelFrame(parent, text="Select TA and Module", padding=10)
        selector_frame.pack(fill='x', padx=10, pady=(10, 5))

        row1 = ttk.Frame(selector_frame)
        row1.pack(fill='x', pady=2)
        ttk.Label(row1, text="TA Assignment ID:").pack(side='left', padx=(0, 5))
        self.perm_ta_id_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.perm_ta_id_var, width=15).pack(side='left', padx=(0, 10))
        ttk.Button(row1, text="Load TA", command=self._load_ta_permissions_info).pack(side='left', padx=5)

        # Info display
        self.perm_info_var = tk.StringVar(value="Enter a TA Assignment ID and click 'Load TA'.")
        info_frame = ttk.LabelFrame(parent, text="TA Information", padding=10)
        info_frame.pack(fill='x', padx=10, pady=5)
        ttk.Label(info_frame, textvariable=self.perm_info_var, wraplength=800).pack(anchor='w')

        # Permission checkboxes
        perm_outer = ttk.LabelFrame(parent, text="Module-Level Permissions", padding=10)
        perm_outer.pack(fill='both', expand=True, padx=10, pady=5)

        ttk.Label(perm_outer, text="Select permissions to grant for this TA's module:").pack(anchor='w', pady=(0, 10))

        self._perm_vars = {}
        for perm_key, perm_label in self.PERMISSION_TYPES:
            var = tk.BooleanVar(value=False)
            self._perm_vars[perm_key] = var
            ttk.Checkbutton(perm_outer, text=perm_label, variable=var).pack(anchor='w', padx=20, pady=2)

        # Current permissions display
        current_frame = ttk.LabelFrame(parent, text="Current Permissions", padding=10)
        current_frame.pack(fill='x', padx=10, pady=5)
        self.current_perms_var = tk.StringVar(value="Load a TA to see current permissions.")
        ttk.Label(current_frame, textvariable=self.current_perms_var, wraplength=800).pack(anchor='w')

        # Action buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(5, 10))
        ttk.Button(btn_frame, text="Save Permissions", command=self._save_ta_module_permissions).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Select All", command=lambda: [v.set(True) for v in self._perm_vars.values()]).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Clear All", command=lambda: [v.set(False) for v in self._perm_vars.values()]).pack(side='left', padx=5)

    def _load_ta_permissions_info(self):
        """Load TA details and current module-level permissions"""
        ta_id_str = self.perm_ta_id_var.get().strip()
        if not ta_id_str:
            messagebox.showwarning("Validation", "Please enter a TA Assignment ID.")
            return

        try:
            ta_id = int(ta_id_str)
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ta_assignments WHERE id = ?', (ta_id,))
            ta = cursor.fetchone()
            col_names = [desc[0] for desc in cursor.description]

            if not ta:
                conn.close()
                self.perm_info_var.set(f"No TA assignment found with ID {ta_id}.")
                return

            ta_data = dict(zip(col_names, ta))
            self.perm_info_var.set(
                f"ID: {ta_data['id']}  |  User: {ta_data.get('user_id', '')}  |  "
                f"Module: {ta_data.get('module_code', '')}  |  Role: {ta_data.get('role', '')}")

            # Load existing module-level permissions from ta_permissions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ta_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ta_id INTEGER NOT NULL,
                    module_code TEXT NOT NULL,
                    permission_type TEXT NOT NULL,
                    granted_by TEXT,
                    granted_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

            module_code = ta_data.get('module_code', '')
            cursor.execute("SELECT permission_type FROM ta_permissions WHERE ta_id = ? AND module_code = ?",
                          (ta_id, module_code))
            current_perms = {row[0] for row in cursor.fetchall()}
            conn.close()

            for perm_key, var in self._perm_vars.items():
                var.set(perm_key in current_perms)

            if current_perms:
                labels = [lbl for k, lbl in self.PERMISSION_TYPES if k in current_perms]
                self.current_perms_var.set(f"Current: {', '.join(labels)}")
            else:
                self.current_perms_var.set("No module-level permissions currently set.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load TA: {e}")

    def _save_ta_module_permissions(self):
        """Save granular module-level permissions"""
        ta_id_str = self.perm_ta_id_var.get().strip()
        if not ta_id_str:
            messagebox.showwarning("Validation", "Please enter a TA Assignment ID.")
            return

        try:
            ta_id = int(ta_id_str)
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT module_code FROM ta_assignments WHERE id = ?', (ta_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                messagebox.showwarning("Not Found", f"TA assignment #{ta_id} not found.")
                return

            module_code = row[0]
            selected = [k for k, v in self._perm_vars.items() if v.get()]

            current_user = getattr(self.auth, 'current_user', {})
            granted_by = current_user.get('username', 'unknown') if isinstance(current_user, dict) else 'unknown'

            # Replace all permissions
            cursor.execute("DELETE FROM ta_permissions WHERE ta_id = ? AND module_code = ?", (ta_id, module_code))
            for perm in selected:
                cursor.execute('''
                    INSERT INTO ta_permissions (ta_id, module_code, permission_type, granted_by)
                    VALUES (?, ?, ?, ?)
                ''', (ta_id, module_code, perm, granted_by))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Module-level permissions updated.")
            self._load_ta_permissions_info()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save permissions: {e}")

    # ──────────────────────────────────────────────────────────────
    # Tab 3: Performance Evaluation
    # ──────────────────────────────────────────────────────────────

    def _build_ta_evaluation_tab(self, parent):
        """Build the TA performance evaluation tab"""
        ttk.Label(parent, text="TA Performance Evaluation", font=('Arial', 12, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=5)
        ttk.Button(btn_frame, text="Refresh", command=self._load_ta_evaluations).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Calculate Metrics", command=self._calculate_ta_metrics).pack(side='left', padx=5)

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        cols = ('TA', 'Module', 'Avg Turnaround (d)', 'Hours/Wk', 'Hours Logged', 'Graded', 'Feedback')
        self.eval_tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        for col in cols:
            self.eval_tree.heading(col, text=col)
            self.eval_tree.column(col, width=110)

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.eval_tree.yview)
        self.eval_tree.configure(yscrollcommand=scrollbar.set)
        self.eval_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.eval_status_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self.eval_status_var).pack(anchor='w', padx=10, pady=5)

        self._load_ta_evaluations()

    def _load_ta_evaluations(self):
        """Load TA performance data"""
        self.eval_tree.delete(*self.eval_tree.get_children())
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
                SELECT ta.user_id, ta.module_code, COALESCE(ta.hours_per_week, 0),
                       ev.avg_grading_turnaround_days, ev.hours_logged,
                       ev.submissions_graded, ev.feedback_score
                FROM ta_assignments ta
                LEFT JOIN ta_evaluations ev ON ta.user_id = ev.ta_id AND ta.module_code = ev.module_code
                ORDER BY ta.module_code, ta.user_id
            ''')
            rows = cursor.fetchall()
            conn.close()

            for r in rows:
                self.eval_tree.insert('', 'end', values=(
                    r[0], r[1],
                    f"{r[3]:.1f}" if r[3] is not None else "N/A",
                    r[2],
                    f"{r[4]:.1f}" if r[4] is not None else "N/A",
                    r[5] if r[5] is not None else "N/A",
                    f"{r[6]:.1f}" if r[6] is not None else "N/A",
                ))

            self.eval_status_var.set(f"{len(rows)} TAs loaded.")
        except Exception as e:
            self.eval_status_var.set(f"Error: {e}")

    def _calculate_ta_metrics(self):
        """Calculate grading turnaround and submission counts from DB data"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("SELECT user_id, module_code FROM ta_assignments")
            tas = cursor.fetchall()

            if not tas:
                self.eval_status_var.set("No TAs found.")
                conn.close()
                return

            current_user = getattr(self.auth, 'current_user', {})
            evaluator = current_user.get('username', 'system') if isinstance(current_user, dict) else 'system'
            calculated = 0

            for ta_id, mc in tas:
                cursor.execute('''
                    SELECT COUNT(*) FROM assignment_submissions
                    WHERE graded_by = ? AND assignment_id IN
                    (SELECT id FROM assignments WHERE module_code = ?)
                ''', (ta_id, mc))
                graded_count = cursor.fetchone()[0]

                cursor.execute('''
                    SELECT AVG(julianday(sub.graded_date) - julianday(a.due_date))
                    FROM assignment_submissions sub
                    JOIN assignments a ON sub.assignment_id = a.id
                    WHERE sub.graded_by = ? AND a.module_code = ?
                    AND sub.graded_date IS NOT NULL AND a.due_date IS NOT NULL
                ''', (ta_id, mc))
                avg_turn_row = cursor.fetchone()
                avg_turn = round(avg_turn_row[0], 1) if avg_turn_row and avg_turn_row[0] is not None else 0

                cursor.execute("SELECT id FROM ta_evaluations WHERE ta_id = ? AND module_code = ?", (ta_id, mc))
                existing = cursor.fetchone()

                if existing:
                    cursor.execute('''
                        UPDATE ta_evaluations SET avg_grading_turnaround_days = ?,
                        submissions_graded = ?, evaluator_id = ?, evaluated_at = datetime('now')
                        WHERE ta_id = ? AND module_code = ?
                    ''', (avg_turn, graded_count, evaluator, ta_id, mc))
                else:
                    cursor.execute('''
                        INSERT INTO ta_evaluations (ta_id, module_code, avg_grading_turnaround_days,
                        submissions_graded, evaluator_id) VALUES (?, ?, ?, ?, ?)
                    ''', (ta_id, mc, avg_turn, graded_count, evaluator))
                calculated += 1

            conn.commit()
            conn.close()

            self.eval_status_var.set(f"Metrics calculated for {calculated} TAs.")
            self._load_ta_evaluations()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate metrics: {e}")
