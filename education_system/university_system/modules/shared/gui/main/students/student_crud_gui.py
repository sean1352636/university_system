# Auto-generated module
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.college_system.core.paths import DB_FILE as COLLEGE_DB_FILE
from education_system.shared.transfer.academic_history import extract_college_history
from datetime import datetime

# Import utility functions
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    _safe_entry_insert,
    _safe_set_combobox,
)

# Import i18n
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import database connection
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction

# Import SQL safety utilities
from education_system.university_system.modules.shared.utils.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError
)

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = None

# Helper functions for safely setting widget values
def _safe_set_combobox(combobox, value):
    """Safely set combobox value"""
    try:
        if value and value in combobox['values']:
            combobox.set(value)
        else:
            combobox.set('')
    except Exception:
        combobox.set('')

def _safe_entry_insert(entry, value):
    """Safely insert value into entry widget"""
    try:
        entry.delete(0, tk.END)
        if value:
            entry.insert(0, str(value))
    except Exception:
        pass

def create_student_dialog(self):
    """Create comprehensive dialog for adding new student with full form validation"""
    dialog = self.create_themed_toplevel(_t("student.create_new_student"), "700x800")

    # Make dialog visible before grabbing
    dialog.update_idletasks()
    dialog.deiconify()

    try:
        dialog.grab_set()
    except tk.TclError:
        print("Warning: Could not grab dialog focus")

    # Main scrollable frame
    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    # Create canvas and scrollbar
    canvas = tk.Canvas(main_frame)
    scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Title
    title_label = ttk.Label(scrollable_frame, text=_t("student.create_new_student"),
                           font=('Arial', 16, 'bold'))
    title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

    # Form fields
    fields = {}

    # Personal Information Section
    personal_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.personal_info"), padding=15)
    personal_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    # Import from College button
    def _import_from_college():
        """Show dialog to select a student from the college system and autofill fields."""
        try:
            import sqlite3 as _sqlite3
            if not COLLEGE_DB_FILE.exists():
                messagebox.showinfo("Import", _t("student.college_db_not_found",
                    "College database not found. No college data available for import."))
                return
            conn = _sqlite3.connect(str(COLLEGE_DB_FILE))
            conn.row_factory = _sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, student_id, first_name, last_name, date_of_birth, phone, address "
                "FROM students WHERE status = 'active' ORDER BY last_name, first_name"
            )
            college_students = cursor.fetchall()
            conn.close()
        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Could not load college students:\n{e}")
            return
        if not college_students:
            messagebox.showinfo("Import", "No active students found in the college system.")
            return
        sel_dlg = tk.Toplevel(dialog)
        sel_dlg.title("Select College Student")
        sel_dlg.geometry("550x400")
        sel_dlg.transient(dialog)
        sel_dlg.grab_set()
        tk.Label(sel_dlg, text="Select a student from the College System:",
                 font=('Arial', 11, 'bold')).pack(padx=10, pady=(10, 5))
        srch_frame = tk.Frame(sel_dlg)
        srch_frame.pack(fill="x", padx=10)
        tk.Label(srch_frame, text="Search:").pack(side="left")
        srch_var = tk.StringVar()
        ttk.Entry(srch_frame, textvariable=srch_var, width=30).pack(side="left", padx=5)
        lf = tk.Frame(sel_dlg)
        lf.pack(fill="both", expand=True, padx=10, pady=5)
        lb_scroll = tk.Scrollbar(lf)
        lb_scroll.pack(side="right", fill="y")
        lb = tk.Listbox(lf, yscrollcommand=lb_scroll.set, font=('Courier', 10))
        lb.pack(fill="both", expand=True)
        lb_scroll.config(command=lb.yview)
        _stu_map = {}
        def _populate(ft=""):
            lb.delete(0, tk.END)
            _stu_map.clear()
            for s in college_students:
                name = f"{s['first_name']} {s['last_name']}"
                if ft and ft.lower() not in name.lower() and ft.lower() not in (s['student_id'] or '').lower():
                    continue
                pos = lb.size()
                lb.insert(tk.END, f"{s['student_id']}  {s['first_name']:15s} {s['last_name']:15s}  DOB: {s['date_of_birth'] or 'N/A'}")
                _stu_map[pos] = s
        _populate()
        srch_var.trace_add("write", lambda *_: _populate(srch_var.get()))
        def _on_pick():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Selection", "Please select a student.", parent=sel_dlg)
                return
            s = _stu_map[sel[0]]
            _safe_entry_insert(fields['first_name'], s['first_name'])
            _safe_entry_insert(fields['last_name'], s['last_name'])
            if s['date_of_birth']:
                _safe_entry_insert(fields['dob'], s['date_of_birth'])
            dialog._imported_college_student = dict(s)
            sel_dlg.destroy()
        bf = tk.Frame(sel_dlg)
        bf.pack(pady=10)
        ttk.Button(bf, text="Select & Import", command=_on_pick).pack(side="left", padx=5)
        ttk.Button(bf, text="Cancel", command=sel_dlg.destroy).pack(side="left", padx=5)

    ttk.Button(personal_frame, text="Import from College System",
               command=_import_from_college).grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

    # Title/Prefix
    ttk.Label(personal_frame, text=_t("student.title_label")).grid(row=1, column=0, sticky=tk.W, pady=5)
    fields['title'] = ttk.Combobox(personal_frame, values=['Mr', 'Ms', 'Mrs', 'Dr', 'Prof'],
                                  state='readonly', width=27)
    fields['title'].grid(row=1, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # First Name
    ttk.Label(personal_frame, text=_t("student.first_name_required")).grid(row=2, column=0, sticky=tk.W, pady=5)
    fields['first_name'] = ttk.Entry(personal_frame, width=30)
    fields['first_name'].grid(row=2, column=1, pady=5, padx=(10, 0))

    # Middle Name
    ttk.Label(personal_frame, text=_t("student.middle_name_label")).grid(row=3, column=0, sticky=tk.W, pady=5)
    fields['middle_name'] = ttk.Entry(personal_frame, width=30)
    fields['middle_name'].grid(row=3, column=1, pady=5, padx=(10, 0))

    # Last Name
    ttk.Label(personal_frame, text=_t("student.last_name_required")).grid(row=4, column=0, sticky=tk.W, pady=5)
    fields['last_name'] = ttk.Entry(personal_frame, width=30)
    fields['last_name'].grid(row=4, column=1, pady=5, padx=(10, 0))

    # Gender
    ttk.Label(personal_frame, text=_t("student.gender_required")).grid(row=5, column=0, sticky=tk.W, pady=5)
    fields['gender'] = ttk.Combobox(personal_frame, values=['male', 'female', 'other'],
                                   state='readonly', width=27)
    fields['gender'].grid(row=5, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # Date of Birth
    ttk.Label(personal_frame, text=_t("student.dob_required")).grid(row=6, column=0, sticky=tk.W, pady=5)
    fields['dob'] = ttk.Entry(personal_frame, width=30)
    fields['dob'].grid(row=6, column=1, pady=5, padx=(10, 0))

    # Academic Information Section
    academic_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.academic_info"), padding=15)
    academic_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

    # Course - Show as read-only with random assignment info
    ttk.Label(academic_frame, text=_t("student.course_label")).grid(row=0, column=0, sticky=tk.W, pady=5)
    course_label = ttk.Label(academic_frame, text=_t("student.course_random"),
                            foreground="blue")
    course_label.grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)

    # Status information
    status_label = ttk.Label(scrollable_frame,
                            text=_t("student.auto_generated_note"),
                            foreground="blue")
    status_label.grid(row=3, column=0, columnspan=2, pady=10)

    # Validation feedback
    validation_label = ttk.Label(scrollable_frame, text="", foreground="red")
    validation_label.grid(row=4, column=0, columnspan=2, pady=5)

    def validate_form():
        """Validate form inputs"""
        errors = []

        if not fields['first_name'].get().strip():
            errors.append(_t("student.validation_first_name"))

        if not fields['last_name'].get().strip():
            errors.append(_t("student.validation_last_name"))

        if not fields['gender'].get():
            errors.append(_t("student.validation_gender"))

        dob_text = fields['dob'].get().strip()
        if not dob_text:
            errors.append(_t("student.validation_dob"))
        else:
            try:
                dob = datetime.strptime(dob_text, "%Y-%m-%d")
                age = datetime.now().year - dob.year
                if age < 16 or age > 80:
                    errors.append(_t("student.validation_age"))
            except ValueError:
                errors.append(_t("student.validation_date_format"))

        return errors

    def create_student():
        """Create student with comprehensive data processing and random course assignment"""
        try:
            # Validate form
            errors = validate_form()
            if errors:
                validation_label.config(text="; ".join(errors))
                return

            validation_label.config(text="")

            # Get form data
            first_name = fields['first_name'].get().strip()
            middle_name = fields['middle_name'].get().strip()
            last_name = fields['last_name'].get().strip()
            gender = fields['gender'].get()
            dob_text = fields['dob'].get().strip()

            # RANDOMLY ASSIGN COURSE - Hard-coded to CS or DS only (like CLI)
            course = random.choice(['CS', 'DS'])

            title = fields['title'].get() or ('Mr' if gender == 'male' else 'Ms')

            # Parse date and calculate age
            dob = datetime.strptime(dob_text, "%Y-%m-%d")
            now_dt = datetime.now()
            age = now_dt.year - dob.year - ((now_dt.month, now_dt.day) < (dob.month, dob.day))

            # Generate student ID and email
            student_id = str(secrets.randbelow(9000000) + 1000000).zfill(7)
            email_address = f"C{student_id}@tees.ac.uk"
            registration_time = now_dt.strftime('%Y-%m-%d %H:%M:%S')

            # Create student record in database
            conn = get_db_connection()
            if not conn:
                raise Exception("Database connection failed")

            cursor = conn.cursor()

            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")

            # Insert student record
            cursor.execute('''
                INSERT INTO students (student_id, email_address, title, first_name, middle_name,
                    last_name, gender, dob, age, course, registration_datetime, status, enrollment_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id, email_address, title, first_name, middle_name,
                last_name, gender, dob.strftime('%Y-%m-%d'), age, course, registration_time, 'Active', registration_time
            ))

            # Add modules: 2 compulsory, 2 optional, 2 course-specific
            from education_system.university_system.modules.domain.academics.services.modules import (
                compulsory_module_1, compulsory_module_2,
                optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
            )

            # 2 compulsory modules
            selected_modules = [compulsory_module_1['code'], compulsory_module_2['code']]

            # 2 random optional modules
            optional_pool = [optional_module_1, optional_module_2, optional_module_3, optional_module_4]
            opt_picks = random.sample(optional_pool, 2)
            selected_modules.extend([m['code'] for m in opt_picks])

            # 2 random course-specific modules
            course_pool = {
                'CS': [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4],
                'DS': [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4],
            }.get(course, [])
            if len(course_pool) >= 2:
                course_picks = random.sample(course_pool, 2)
                selected_modules.extend([m['code'] for m in course_picks])

            # Ensure rows exist in `modules` so the academic-data JOIN
            # (modules.module_code = student_modules.module_code) returns
            # the freshly enrolled modules. Without this seeding the
            # student detail view shows "No modules enrolled".
            module_catalog = (
                [compulsory_module_1, compulsory_module_2,
                 optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                 CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                 DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4]
            )
            cursor.executemany(
                'INSERT OR IGNORE INTO modules (module_code, module_name, module_type) VALUES (?, ?, ?)',
                [(m['code'], m['name'], 'Standard') for m in module_catalog]
            )

            # Insert modules. student_modules.module_id is a legacy NOT NULL
            # column kept alongside module_code; populate both from the same value.
            module_data = [
                (student_id, module_code, module_code)
                for module_code in selected_modules
            ]
            cursor.executemany(
                'INSERT INTO student_modules (student_id, module_id, module_code) VALUES (?, ?, ?)',
                module_data
            )

            print(f"Assigned {len(selected_modules)} modules to student {student_id} for course {course}: {selected_modules}")

            # Update course enrollment count
            cursor.execute('''
                UPDATE courses
                SET current_enrollment = current_enrollment + 1
                WHERE course_code = ? AND status = 'active'
            ''', (course,))

            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON")

            conn.commit()
            conn.close()

            # Send registration confirmation email
            try:
                from education_system.university_system.infrastructure.email.email_service import send_registration_confirmation
                send_registration_confirmation(student_id)
            except Exception as e:
                logging.warning(f"Failed to send registration confirmation email: {e}")

            # Create user account
            temp_password = f"{first_name.lower()}123456"
            try:
                self.auth.create_user(
                    username=student_id,
                    password=temp_password,
                    email=email_address,
                    first_name=first_name,
                    last_name=last_name,
                    role='student',
                    student_id=student_id
                )
            except Exception as e:
                logging.warning(f"User account creation failed: {e}")

            # Success message with details
            modules_text = ""
            if selected_modules:
                modules_text = "\n\n    Modules assigned:\n"
                for mod_code in selected_modules:
                    modules_text += f"    - {mod_code}\n"

            success_msg = f"""Student created successfully!

Student Details:
- Student ID: {student_id}
- Name: {title} {first_name} {middle_name} {last_name}
- Email: {email_address}
- Course: {course} (randomly assigned)
- Age: {age}
- Login Password: {temp_password}{modules_text}"""

            messagebox.showinfo(_t("common.success"), success_msg)

            # Transfer academic history from college if imported
            if hasattr(dialog, '_imported_college_student') and dialog._imported_college_student:
                _imp_college = dialog._imported_college_student
                try:
                    _history = extract_college_history(str(COLLEGE_DB_FILE), _imp_college['id'])
                    if _history:
                        import sqlite3 as _hist_sqlite3
                        _hist_conn = _hist_sqlite3.connect(str(self.db_path))
                        _hist_conn.execute(
                            "INSERT INTO academic_transfer_history (student_id, source_system, data_json, transferred_at) "
                            "VALUES (?, ?, ?, datetime('now'))",
                            (student_id, 'college', json.dumps(_history))
                        )
                        _hist_conn.commit()
                        _hist_conn.close()
                except Exception:
                    pass  # Don't fail the import if history extraction fails

                # Set previous_system fields on the new student record
                try:
                    import sqlite3 as _ps_sqlite3
                    _ps_conn = _ps_sqlite3.connect(str(self.db_path))
                    _ps_conn.execute(
                        "UPDATE students SET previous_system = ?, previous_system_id = ? WHERE student_id = ?",
                        ('college', _imp_college.get('student_id', ''), student_id)
                    )
                    _ps_conn.commit()
                    _ps_conn.close()
                except Exception:
                    pass  # Don't fail the import if previous_system update fails

            # Remove imported student from college system if applicable
            if hasattr(dialog, '_imported_college_student') and dialog._imported_college_student:
                _imp = dialog._imported_college_student
                _imp_name = f"{_imp.get('first_name', '')} {_imp.get('last_name', '')}"
                if messagebox.askyesno(
                    "Transfer Student",
                    f"Mark {_imp_name} as transferred in the College System?",
                ):
                    try:
                        import sqlite3 as _sqlite3
                        _conn = _sqlite3.connect(str(COLLEGE_DB_FILE))
                        _conn.execute(
                            "UPDATE students SET status = 'transferred' WHERE id = ?",
                            (_imp['id'],),
                        )
                        _conn.commit()
                        _conn.close()
                        logger.info(
                            "Student %s (%s) transferred from college to university as %s",
                            _imp.get('student_id', ''), _imp_name, student_id,
                        )
                        # Notify college admin(s) of the transfer via cross-system notifications
                        # AND college-local notifications so it appears in their inbox
                        _transfer_title = f"Student Transfer: {_imp_name} moved to University"
                        _transfer_msg = (
                            f"Student {_imp.get('student_id', '')} ({_imp_name}) "
                            f"has been transferred from the College System "
                            f"to the University System.\n\n"
                            f"New University Student ID: {student_id}\n"
                            f"Transferred by: {first_name} {last_name} creation process\n\n"
                            f"The student's college record has been marked as 'transferred'."
                        )
                        try:
                            # 1) Cross-system notification (visible in Cross-System Notifications)
                            from education_system.shared.notifications.service import CrossSystemNotificationService
                            _sender_id = getattr(self.auth, 'current_user', {}).get('user_id') if self.auth else None
                            _xn_svc = CrossSystemNotificationService()
                            _xn_svc.send_to_role(
                                sender_user_id=_sender_id or 0,
                                sender_system='university',
                                target_system='college',
                                target_role='admin',
                                title=_transfer_title,
                                message=_transfer_msg,
                                priority='high',
                            )
                        except Exception:
                            pass
                        try:
                            # 2) College-local notification + email message
                            #    Look up admin users by username in shared auth, then find
                            #    matching local user_id in the college DB.
                            import sqlite3 as _sq3
                            from education_system.shared.auth.db import AUTH_DB_FILE
                            _auth_conn = _sq3.connect(str(AUTH_DB_FILE))
                            _auth_conn.row_factory = _sq3.Row
                            _admins = _auth_conn.execute(
                                "SELECT u.username FROM users u "
                                "JOIN user_systems us ON u.id = us.user_id "
                                "WHERE us.system_key = 'college' AND us.role = 'admin' "
                                "AND u.is_active = 1"
                            ).fetchall()
                            _auth_conn.close()
                            _col_conn = _sqlite3.connect(str(COLLEGE_DB_FILE))
                            _col_conn.row_factory = _sq3.Row
                            _admin_ids = []
                            for _admin in _admins:
                                _local = _col_conn.execute(
                                    "SELECT id FROM users WHERE username = ?",
                                    (_admin['username'],),
                                ).fetchone()
                                if _local:
                                    _admin_ids.append(_local['id'])
                                    _col_conn.execute(
                                        "INSERT INTO notifications (user_id, title, message, type) "
                                        "VALUES (?, ?, ?, ?)",
                                        (_local['id'], _transfer_title, _transfer_msg, 'alert'),
                                    )
                            # Also insert into messages table so it appears in email inbox
                            # Use first admin as sender (system message)
                            _msg_sender = _admin_ids[0] if _admin_ids else 1
                            for _aid in _admin_ids:
                                _col_conn.execute(
                                    "INSERT INTO messages (sender_id, recipient_id, subject, body) "
                                    "VALUES (?, ?, ?, ?)",
                                    (_msg_sender, _aid, _transfer_title, _transfer_msg),
                                )
                            _col_conn.commit()
                            _col_conn.close()
                        except Exception:
                            pass
                    except Exception as _e:
                        logging.warning(f"Failed to mark college student as transferred: {_e}")

            # Send welcome email to new student
            self._send_welcome_email_to_student(
                student_id=student_id,
                first_name=first_name,
                last_name=last_name,
                email_address=email_address,
                temp_password=temp_password,
                course=course
            )

            # Refresh student list and close dialog
            if hasattr(self, 'view_students'):
                self.view_students()
            self.refresh_advanced_search()  # ADD THIS LINE

            dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("student.failed_create_student").replace("{error}", str(e)))

    # Buttons
    button_frame = ttk.Frame(scrollable_frame)
    button_frame.grid(row=5, column=0, columnspan=2, pady=20)

    ttk.Button(button_frame, text=_t("student.create_student"), command=create_student,
              style="Accent.TButton").pack(side=tk.LEFT, padx=10)
    ttk.Button(button_frame, text=_t("student.clear_form"),
              command=lambda: [field.delete(0, tk.END) if hasattr(field, 'delete')
                              else field.set('') for field in fields.values()]).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    # Pack canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Set focus
    fields['first_name'].focus()

    # Bind mousewheel to canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
def update_student_dialog(self, student_id):
    """Comprehensive update student dialog with full editing capabilities and random course assignment"""
    dialog = tk.Toplevel(self.root)
    dialog.title(_t("student.update_student_title", student_id=student_id))
    dialog.geometry("800x900")
    dialog.transient(self.root)

    # Make dialog visible before grabbing
    dialog.update_idletasks()
    dialog.deiconify()

    try:
        dialog.grab_set()
    except tk.TclError:
        print("Warning: Could not grab dialog focus")

    try:
        # Get current student data
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            dialog.destroy()
            return

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            messagebox.showerror(_t("common.error"), _t("student.student_not_found"))
            dialog.destroy()
            return

        # Main scrollable frame
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Title
        title_label = ttk.Label(scrollable_frame, text=_t("student.update_student_label", student_id=student_id),
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # Current info display
        current_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.current_information"), padding=10)
        current_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        current_text = tk.Text(current_frame, height=4, width=70, wrap=tk.WORD)
        current_text.pack(fill=tk.X)
        current_info = f"Name: {student[2]} {student[3]} {student[4]} {student[5]} | Gender: {student[6]} | Course: {student[9]} | Age: {student[8]}"
        current_text.insert(tk.END, current_info)
        current_text.config(state=tk.DISABLED)

        # Form fields with current values
        fields = {}

        # Personal Information Section
        personal_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.personal_info"), padding=15)
        personal_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Title
        ttk.Label(personal_frame, text=_t("student.title_label")).grid(row=0, column=0, sticky=tk.W, pady=5)
        title_options = ['Mr', 'Ms', 'Mrs', 'Dr', 'Prof']
        title_value = (student[2] or '').strip()
        if title_value not in title_options:
            title_value = ''
        fields['title'] = ttk.Combobox(personal_frame, values=title_options,
                                      state='readonly', width=27)
        fields['title'].grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        _safe_set_combobox(fields['title'], title_value)

        # First Name
        ttk.Label(personal_frame, text=_t("student.first_name_label")).grid(row=1, column=0, sticky=tk.W, pady=5)
        fields['first_name'] = ttk.Entry(personal_frame, width=30)
        fields['first_name'].grid(row=1, column=1, pady=5, padx=(10, 0))
        _safe_entry_insert(fields['first_name'], student[3])

        # Middle Name
        ttk.Label(personal_frame, text=_t("student.middle_name_label")).grid(row=2, column=0, sticky=tk.W, pady=5)
        fields['middle_name'] = ttk.Entry(personal_frame, width=30)
        fields['middle_name'].grid(row=2, column=1, pady=5, padx=(10, 0))
        _safe_entry_insert(fields['middle_name'], student[4])

        # Last Name
        ttk.Label(personal_frame, text=_t("student.last_name_label")).grid(row=3, column=0, sticky=tk.W, pady=5)
        fields['last_name'] = ttk.Entry(personal_frame, width=30)
        fields['last_name'].grid(row=3, column=1, pady=5, padx=(10, 0))
        _safe_entry_insert(fields['last_name'], student[5])

        # Gender
        ttk.Label(personal_frame, text=_t("student.gender_label")).grid(row=4, column=0, sticky=tk.W, pady=5)
        gender_options = ['male', 'female', 'other']
        gender_value = (student[6] or '').strip().lower()
        if gender_value not in gender_options:
            gender_value = ''
        fields['gender'] = ttk.Combobox(personal_frame, values=gender_options,
                                       state='readonly', width=27)
        fields['gender'].grid(row=4, column=1, pady=5, padx=(10, 0), sticky=tk.W)
        _safe_set_combobox(fields['gender'], gender_value)

        # Date of Birth
        ttk.Label(personal_frame, text=_t("student.dob_label")).grid(row=5, column=0, sticky=tk.W, pady=5)
        fields['dob'] = ttk.Entry(personal_frame, width=30)
        fields['dob'].grid(row=5, column=1, pady=5, padx=(10, 0))
        _safe_entry_insert(fields['dob'], student[7])

        # Academic Information
        academic_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.academic_info"), padding=15)
        academic_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Course - Add random assignment option
        ttk.Label(academic_frame, text=_t("student.course_label")).grid(row=0, column=0, sticky=tk.W, pady=5)
        course_frame = ttk.Frame(academic_frame)
        course_frame.grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)

        current_course_label = ttk.Label(course_frame, text=_t("student.current_course", course=student[9]), foreground="blue")
        current_course_label.pack(side=tk.LEFT)

        # Random course reassignment option
        reassign_course_var = tk.BooleanVar()
        ttk.Checkbutton(course_frame, text=_t("student.reassign_course_modules"),
                       variable=reassign_course_var).pack(side=tk.LEFT, padx=(20, 0))

        # Email (read-only display)
        ttk.Label(academic_frame, text=_t("student.email_label")).grid(row=1, column=0, sticky=tk.W, pady=5)
        email_label = ttk.Label(academic_frame, text=student[1], foreground="blue")
        email_label.grid(row=1, column=1, pady=5, padx=(10, 0), sticky=tk.W)

        # Module Management Section
        modules_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.module_management"), padding=15)
        modules_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Get current modules
        cursor.execute('''
            SELECT m.module_type, sm.module_code, m.module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
        ''', (student_id,))
        current_modules = cursor.fetchall()

        modules_text = scrolledtext.ScrolledText(modules_frame, height=6, width=70)
        modules_text.pack(fill=tk.X)

        modules_info = _t("student.current_modules") + ":\n" + "-"*40 + "\n"
        for module in current_modules:
            modules_info += f"{module[0]}: {module[1]} - {module[2]}\n"
        modules_text.insert(tk.END, modules_info)
        modules_text.config(state=tk.DISABLED)

        # Buttons for module actions
        module_buttons_frame = ttk.Frame(modules_frame)
        module_buttons_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(module_buttons_frame, text=_t("student.reassign_optional_modules"),
                  command=lambda: self.reassign_modules(student_id, 'optional')).pack(side=tk.LEFT, padx=5)

        # Validation feedback
        validation_label = ttk.Label(scrollable_frame, text="", foreground="red")
        validation_label.grid(row=5, column=0, columnspan=2, pady=10)

        # Password update section
        password_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.password_management"), padding=15)
        password_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        password_var = tk.BooleanVar()
        ttk.Checkbutton(password_frame, text=_t("student.update_password_auto"),
                       variable=password_var).pack(anchor=tk.W)

        ttk.Label(password_frame, text=_t("student.password_note"),
                 foreground="gray").pack(anchor=tk.W, pady=(5, 0))

        def validate_update_form():
            """Validate update form inputs"""
            errors = []

            if not fields['first_name'].get().strip():
                errors.append(_t("student.validation_first_name"))

            if not fields['last_name'].get().strip():
                errors.append(_t("student.validation_last_name"))

            dob_text = fields['dob'].get().strip()
            if dob_text:
                try:
                    dob = datetime.strptime(dob_text, "%Y-%m-%d")
                    age = datetime.now().year - dob.year
                    if age < 16 or age > 80:
                        errors.append(_t("student.validation_age"))
                except ValueError:
                    errors.append(_t("student.validation_date_format"))

            return errors

        def update_student():
            """Update student with form data and random course assignment if selected"""
            update_conn = None
            try:
                # Validate form
                errors = validate_update_form()
                if errors:
                    validation_label.config(text="; ".join(errors))
                    return

                validation_label.config(text="")

                # Get updated data
                new_title = fields['title'].get()
                new_first_name = fields['first_name'].get().strip()
                new_middle_name = fields['middle_name'].get().strip()
                new_last_name = fields['last_name'].get().strip()
                new_gender = fields['gender'].get()
                new_dob = fields['dob'].get().strip()
                if not new_dob:
                    new_dob = None

                # Determine new course
                current_course = student[9]
                if reassign_course_var.get():
                    new_course = 'DS' if current_course == 'CS' else 'CS'
                    course_changed = True
                else:
                    new_course = current_course
                    course_changed = False

                # Calculate new age if DOB changed
                if new_dob:
                    if student[7] != new_dob:
                        dob_date = datetime.strptime(new_dob, "%Y-%m-%d")
                        new_age = datetime.now().year - dob_date.year - (
                            (datetime.now().month, datetime.now().day) < (dob_date.month, dob_date.day)
                        )
                    else:
                        new_age = student[8]
                else:
                    new_age = None

                # Create new database connection for update
                update_conn = get_db_connection()
                update_cursor = update_conn.cursor()

                # Update database
                update_cursor.execute('''
                    UPDATE students
                    SET title = ?, first_name = ?, middle_name = ?, last_name = ?,
                        gender = ?, dob = ?, age = ?, course = ?
                    WHERE student_id = ?
                ''', (new_title, new_first_name, new_middle_name, new_last_name,
                      new_gender, new_dob, new_age, new_course, student_id))

                # Update user profile if exists
                update_cursor.execute('SELECT id FROM users WHERE student_id = ?', (student_id,))
                user_record = update_cursor.fetchone()

                if user_record:
                    user_id = user_record[0]
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    update_cursor.execute('''
                        UPDATE users
                        SET first_name = ?, last_name = ?, updated_at = ?
                        WHERE id = ?
                    ''', (new_first_name, new_last_name, timestamp, user_id))

                    # Update password if requested
                    if password_var.get():
                        new_password = f"{new_first_name.lower()}123456"

                        # Update password in user_accounts table
                        import hashlib
                        import secrets
                        salt = secrets.token_hex(16)
                        key = hashlib.pbkdf2_hmac('sha256', new_password.encode(), salt.encode(), 100000, dklen=64)
                        password_hash = key.hex()

                        update_cursor.execute('''
                            UPDATE user_accounts
                            SET password_hash = ?, salt = ?, updated_at = ?
                            WHERE user_id = ?
                        ''', (password_hash, salt, timestamp, user_id))

                # Handle course change - reassign all modules (2 compulsory, 2 optional, 2 course-specific)
                if course_changed:
                    from education_system.university_system.modules.domain.academics.services.modules import (
                        compulsory_module_1, compulsory_module_2,
                        optional_module_1, optional_module_2, optional_module_3, optional_module_4,
                        CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
                        DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4,
                    )

                    # Remove all existing modules for this student
                    update_cursor.execute('DELETE FROM student_modules WHERE student_id = ?', (student_id,))

                    # 2 compulsory modules
                    selected_modules = [compulsory_module_1['code'], compulsory_module_2['code']]

                    # 2 random optional modules
                    optional_pool = [optional_module_1, optional_module_2, optional_module_3, optional_module_4]
                    opt_picks = random.sample(optional_pool, 2)
                    selected_modules.extend([m['code'] for m in opt_picks])

                    # 2 random course-specific modules
                    course_pool = {
                        'CS': [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4],
                        'DS': [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4],
                    }.get(new_course, [])
                    if len(course_pool) >= 2:
                        course_picks = random.sample(course_pool, 2)
                        selected_modules.extend([m['code'] for m in course_picks])

                    current_date = datetime.now().strftime('%Y-%m-%d')
                    for module_code in selected_modules:
                        update_cursor.execute('''
                            INSERT INTO student_modules (student_id, module_code, enrollment_date, status)
                            VALUES (?, ?, ?, ?)
                        ''', (student_id, module_code, current_date, 'enrolled'))

                update_conn.commit()

                # Send update confirmation email via email_service
                try:
                    # Get student email
                    update_cursor.execute('SELECT email_address FROM students WHERE student_id = ?', (student_id,))
                    email_result = update_cursor.fetchone()

                    if email_result:
                        student_email = email_result[0]
                        # Determine what fields were updated
                        updated_fields = []
                        if new_title != student[2]:
                            updated_fields.append('title')
                        if new_first_name != student[3]:
                            updated_fields.append('first name')
                        if new_middle_name != student[4]:
                            updated_fields.append('middle name')
                        if new_last_name != student[5]:
                            updated_fields.append('last name')
                        if new_gender != student[6]:
                            updated_fields.append('gender')
                        if new_dob and new_dob != student[7]:
                            updated_fields.append('date of birth')
                        if course_changed:
                            updated_fields.append('course')
                        if password_var.get():
                            updated_fields.append('password')

                        if updated_fields:
                            from education_system.university_system.infrastructure.email.email_service import send_update_confirmation
                            send_update_confirmation(student_email, updated_fields)
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to send update confirmation email: {e}")

                success_msg = _t("student.student_updated_success", student_id=student_id)
                if course_changed:
                    success_msg += "\n" + _t("student.course_changed", old_course=student[9], new_course=new_course)
                if password_var.get():
                    success_msg += "\n" + _t("student.new_password", password=f"{new_first_name.lower()}123456")

                messagebox.showinfo(_t("common.success"), success_msg)

                # Send email notification about changes
                self._send_student_update_email(
                    student_id=student_id,
                    old_data=student,
                    new_data={
                        'title': new_title,
                        'first_name': new_first_name,
                        'middle_name': new_middle_name,
                        'last_name': new_last_name,
                        'gender': new_gender,
                        'dob': new_dob,
                        'age': new_age,
                        'course': new_course
                    },
                    course_changed=course_changed,
                    password_reset=password_var.get()
                )

                # Refresh views and close dialog
                if hasattr(self, 'view_students'):
                    self.view_students()
                self.refresh_advanced_search()

                dialog.destroy()

            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("student.failed_update_student", error=str(e)))
            finally:
                # Close the update connection
                if update_conn:
                    update_conn.close()

        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("student.update_student_button"), command=update_student,
                  style="Accent.TButton").pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("student.reset_form"),
                  command=lambda: dialog.destroy() and self.update_student_dialog(student_id)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        conn.close()

        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

    except Exception as e:
        logging.exception("Failed to load student data for student_id=%s", student_id)
        messagebox.showerror(_t("common.error"), _t("student.failed_load_student_data", error=str(e)))
        dialog.destroy()
def delete_student_dialog(self, student_id=None):
    """Comprehensive delete student dialog with safety checks"""
    if not student_id:
        # Show selection dialog first
        student_id = self.select_student_for_deletion()
        if not student_id:
            return

    dialog = tk.Toplevel(self.root)
    dialog.title(_t("student.delete_student_title").replace("{student_id}", str(student_id)))
    dialog.geometry("900x900")  # Made bigger
    dialog.transient(self.root)

    # CRITICAL FIX: Make dialog visible BEFORE grabbing
    dialog.update_idletasks()  # Force geometry calculation
    dialog.deiconify()         # Ensure window is visible

    # Center the dialog on parent
    dialog.geometry("+%d+%d" % (
        self.root.winfo_rootx() + 50,
        self.root.winfo_rooty() + 50
    ))

    # Now it's safe to grab focus
    try:
        dialog.grab_set()
    except tk.TclError:
        # If grab still fails, continue without it
        print("Warning: Could not grab dialog focus")

    # Make dialog modal and non-resizable
    dialog.resizable(False, False)

    try:
        # Get student data for confirmation
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            dialog.destroy()
            return

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            messagebox.showerror(_t("common.error"), _t("student.student_not_found"))
            dialog.destroy()
            return

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Warning header
        warning_frame = ttk.Frame(main_frame)
        warning_frame.pack(fill=tk.X, pady=(0, 20))

        warning_label = ttk.Label(warning_frame, text="⚠️ " + _t("student.delete_warning"),
                                 font=('Arial', 16, 'bold'), foreground="red")
        warning_label.pack()

        # Student information display
        info_frame = ttk.LabelFrame(main_frame, text=_t("student.student_information"), padding=15)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        student_info = f"""Student ID: {student[0]}
Name: {student[2]} {student[3]} {student[4]} {student[5]}
Email: {student[1]}
Course: {student[9]}
Registration Date: {student[10]}"""

        ttk.Label(info_frame, text=student_info, font=('Courier', 10)).pack(anchor=tk.W)

        # Get related records count
        cursor.execute('SELECT COUNT(*) FROM student_modules WHERE student_id = ?', (student_id,))
        modules_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM student_grades WHERE student_id = ?', (student_id,))
        grades_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM attendance WHERE student_id = ?', (student_id,))
        attendance_count = cursor.fetchone()[0]

        # Related records information
        related_frame = ttk.LabelFrame(main_frame, text=_t("student.related_records"), padding=15)
        related_frame.pack(fill=tk.X, pady=(0, 20))

        related_info = f"""{_t("student.module_enrollments")}: {modules_count}
{_t("student.grade_records")}: {grades_count}
{_t("student.attendance_records")}: {attendance_count}
{_t("student.user_account")}: {_t("student.will_be_removed")}
{_t("student.all_data_deleted")}"""

        ttk.Label(related_frame, text=related_info, font=('Courier', 10), foreground="dark red").pack(anchor=tk.W)

        # Confirmation section
        confirm_frame = ttk.LabelFrame(main_frame, text=_t("student.confirmation_required"), padding=15)
        confirm_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(confirm_frame, text=_t("student.cannot_be_undone"),
                 font=('Arial', 12, 'bold'), foreground="red").pack(pady=(0, 10))

        ttk.Label(confirm_frame, text=_t("student.type_to_confirm").replace("{student_id}", str(student_id))).pack(anchor=tk.W)
        confirm_entry = ttk.Entry(confirm_frame, width=30, font=('Arial', 11))
        confirm_entry.pack(pady=(5, 10), fill=tk.X)

        # Additional confirmation checkbox
        additional_confirm = tk.BooleanVar()
        ttk.Checkbutton(confirm_frame, text=_t("student.understand_delete"),
                       variable=additional_confirm).pack(anchor=tk.W)

        # Status label
        status_label = ttk.Label(confirm_frame, text="", foreground="red")
        status_label.pack(pady=(10, 0))

        # Close the initial read-only connection before performing destructive work
        if conn:
            conn.close()

        def perform_deletion():
            """Perform the actual deletion with comprehensive cleanup"""
            # Validate confirmations
            entered_id = confirm_entry.get().strip()
            expected_id = str(student_id).strip()
            if entered_id != expected_id:
                status_label.config(text=_t("student.id_mismatch"))
                return

            if not additional_confirm.get():
                status_label.config(text=_t("student.check_checkbox"))
                return

            # Final confirmation dialog
            if not messagebox.askyesno(_t("student.final_confirm_title"),
                                     _t("student.final_confirm_msg").replace("{student_id}", str(student_id)),
                                     icon='warning'):
                return

            conn = None
            cursor = None
            try:
                # Start deletion process
                status_label.config(text=_t("student.deleting_record"), foreground="blue")
                dialog.update()

                conn = get_db_connection()
                if not conn:
                    raise sqlite3.OperationalError("Database connection failed during deletion")

                cursor = conn.cursor()

                # Disable foreign key constraints temporarily
                cursor.execute("PRAGMA foreign_keys = OFF")

                deletion_log = []

                # Get list of tables that actually exist in the database
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                existing_tables = {row[0] if isinstance(row, tuple) else row['name'] for row in cursor.fetchall()}

                # Delete from related tables first
                tables_to_clean = [
                    ('student_grades', 'student_id'),
                    ('attendance', 'student_id'),
                    ('student_modules', 'student_id'),
                    ('assignment_submissions', 'student_id'),
                    ('accommodation_requests', 'student_id'),
                    ('housing_requests', 'student_id'),
                    ('health_records', 'student_id'),
                    ('internship_applications', 'student_id'),
                    ('trip_participants', 'student_id'),
                    ('loans', 'borrower_id'),
                    ('student_fees', 'student_id'),
                    ('support_tickets', 'student_id'),
                    ('parent_student_relationships', 'student_id')
                ]

                for table_name, column_name in tables_to_clean:
                    if table_name not in existing_tables:
                        logger.debug(f"Skipping non-existent table: {table_name}")
                        continue
                    try:
                        # Validate table and column names to prevent SQL injection
                        validated_table = validate_table_name(table_name, conn=conn)
                        validated_column = validate_column_name(column_name, table_name=validated_table, conn=conn)
                        cursor.execute('DELETE FROM [' + validated_table + '] WHERE [' + validated_column + '] = ?', (student_id,))
                        deleted_count = cursor.rowcount
                        if deleted_count > 0:
                            deletion_log.append(f"Deleted {deleted_count} records from {table_name}")
                    except SQLIdentifierError as e:
                        logger.warning(f"Invalid table/column name: {e}")
                    except sqlite3.OperationalError as e:
                        # Table might not exist
                        logger.debug(f"Table {table_name} might not exist: {e}")

                # Fetch user record info before closing connection
                cursor.execute('SELECT id, username FROM users WHERE student_id = ?', (student_id,))
                user_record = cursor.fetchone()
                user_id = user_record[0] if user_record else None
                username = user_record[1] if user_record else None

                # Update course enrollment count before deleting student
                cursor.execute('SELECT course FROM students WHERE student_id = ?', (student_id,))
                student_course = cursor.fetchone()
                if student_course and student_course[0]:
                    course_code = student_course[0]
                    cursor.execute('''
                        UPDATE courses
                        SET current_enrollment = current_enrollment - 1
                        WHERE course_code = ? AND current_enrollment > 0
                    ''', (course_code,))
                    if cursor.rowcount > 0:
                        deletion_log.append(f"Updated course enrollment count for {course_code}")

                # Finally delete the main student record
                cursor.execute('DELETE FROM students WHERE student_id = ?', (student_id,))
                if cursor.rowcount > 0:
                    deletion_log.append("Deleted main student record")

                # Re-enable foreign key constraints
                cursor.execute("PRAGMA foreign_keys = ON")

                conn.commit()
                conn.close()
                conn = None

                # Delete user account AFTER closing the connection to avoid DB lock
                if user_id is not None:
                    if self.auth:
                        if self.auth.delete_user(user_id):
                            deletion_log.append(f"Deleted user account via auth system (username: {username})")
                            if ACTIVITY_LOGGER_AVAILABLE:
                                log_activity('delete', 'user', user_id=user_id, details={'username': username, 'student_id': student_id, 'reason': 'Student deletion'})
                        else:
                            deletion_log.append(f"Warning: Failed to delete user via auth system for {username}")
                    else:
                        # Fallback to direct deletion if auth not available
                        fallback_conn = get_db_connection()
                        if fallback_conn:
                            try:
                                fb_cursor = fallback_conn.cursor()
                                fb_cursor.execute('DELETE FROM user_accounts WHERE user_id = ?', (user_id,))
                                if fb_cursor.rowcount > 0:
                                    deletion_log.append("Deleted user account")
                                fb_cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
                                if fb_cursor.rowcount > 0:
                                    deletion_log.append("Deleted user profile")
                                    if ACTIVITY_LOGGER_AVAILABLE:
                                        log_activity('delete', 'user', user_id=user_id, details={'username': username, 'student_id': student_id, 'reason': 'Student deletion (fallback)'})
                                fallback_conn.commit()
                            finally:
                                fallback_conn.close()

                # Show deletion summary
                summary = _t("student.deletion_summary").replace("{student_id}", str(student_id)) + "\n".join(deletion_log)
                messagebox.showinfo(_t("student.deletion_complete"), summary)

                # Refresh student list and close dialog
                try:
                    if hasattr(self, 'view_students'):
                        self.view_students()
                    self.refresh_advanced_search()
                except Exception:
                    pass

                try:
                    if dialog.winfo_exists():
                        dialog.destroy()
                except tk.TclError:
                    pass

            except Exception as e:
                if cursor:
                    try:
                        cursor.execute("PRAGMA foreign_keys = ON")
                    except Exception:
                        logger.debug("Connection might already be closed during cleanup")
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                messagebox.showerror(_t("student.deletion_failed"), _t("student.failed_delete_student").replace("{error}", str(e)))
                try:
                    status_label.config(text=_t("student.deletion_failed"), foreground="red")
                except tk.TclError:
                    pass  # Dialog may already be destroyed
            finally:
                if conn:
                    conn.close()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_t("student.delete_button"), command=perform_deletion,
                  style="Accent.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

        # Focus on confirmation entry
        confirm_entry.focus()

        # Handle dialog close event
        def on_dialog_close():
            try:
                dialog.grab_release()
            except Exception as e:
                logger.debug(f"Could not release grab on dialog: {e}")
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_prepare_deletion").replace("{error}", str(e)))
        dialog.destroy()
def select_student_for_deletion(self):
    """Show dialog to select student for deletion"""
    selection_dialog = tk.Toplevel(self.root)
    selection_dialog.title(_t("student.select_student_delete"))
    selection_dialog.geometry("1000x700")  # Made bigger
    selection_dialog.transient(self.root)
    selection_dialog.grab_set()

    selected_student = None

    main_frame = ttk.Frame(selection_dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=_t("student.select_student_delete"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Search frame
    search_frame = ttk.Frame(main_frame)
    search_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(search_frame, text=_t("common.search")).pack(side=tk.LEFT)
    search_entry = ttk.Entry(search_frame, width=30)
    search_entry.pack(side=tk.LEFT, padx=(10, 0))

    # Student list
    list_frame = ttk.Frame(main_frame)
    list_frame.pack(fill=tk.BOTH, expand=True)

    columns = ('ID', 'Name', 'Email', 'Course')
    column_labels = (_t("student.column_id"), _t("student.column_name"), _t("student.column_email"), _t("student.column_course"))
    tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

    for col, label in zip(columns, column_labels):
        tree.heading(col, text=label)
        tree.column(col, width=150)

    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Load students
    def load_students(filter_text=""):
        tree.delete(*tree.get_children())

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if filter_text:
                cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address, course
                    FROM students
                    WHERE LOWER(first_name) LIKE LOWER(?)
                       OR LOWER(last_name) LIKE LOWER(?)
                       OR LOWER(student_id) LIKE LOWER(?)
                    ORDER BY last_name, first_name
                ''', (f'%{filter_text}%', f'%{filter_text}%', f'%{filter_text}%'))
            else:
                cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address, course
                    FROM students
                    ORDER BY last_name, first_name
                ''')

            students = cursor.fetchall()

            for student in students:
                student_id, first_name, last_name, email, course = student
                full_name = f"{first_name} {last_name}"
                tree.insert('', tk.END, values=(student_id, full_name, email, course))

            conn.close()
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("student.failed_load_students", error=str(e)))

    def search_students():
        filter_text = search_entry.get().strip()
        load_students(filter_text)

    def on_select():
        nonlocal selected_student
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            selected_student = item['values'][0]
            selection_dialog.destroy()

    # Search button
    ttk.Button(search_frame, text=_t("common.search_button"), command=search_students).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(search_frame, text=_t("common.show_all"), command=lambda: load_students()).pack(side=tk.LEFT, padx=(5, 0))

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(20, 0))

    ttk.Button(button_frame, text=_t("student.select_for_deletion"), command=on_select).pack(side=tk.LEFT)
    ttk.Button(button_frame, text=_t("common.cancel"), command=selection_dialog.destroy).pack(side=tk.LEFT, padx=(10, 0))

    # Bind double-click
    tree.bind('<Double-1>', lambda e: on_select())

    # Bind search entry
    search_entry.bind('<Return>', lambda e: search_students())

    # Load initial data
    load_students()

    # Wait for dialog to close
    selection_dialog.wait_window()

    return selected_student
def manage_student_grades(self, student_id, first_name, last_name):
    """Display and manage student grades with assignments/assessments table"""
    try:
        grades_window = tk.Toplevel(self.root)
        grades_window.title(f"Manage Grades - {first_name} {last_name} ({student_id})")
        grades_window.geometry("1000x600")
        grades_window.transient(self.root)

        main_frame = ttk.Frame(grades_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Grades for {first_name} {last_name}",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview for grades
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Type", "Module", "Assignment", "Submitted", "Grade", "Max Grade", "Status")
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Fetch grades from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            grades_window.destroy()
            return

        cursor = conn.cursor()

        # Get assignments and grades
        cursor.execute("""
            SELECT 'Assignment' as type, a.module_code, a.title,
                   CASE WHEN s.submission_date IS NOT NULL THEN 'Yes' ELSE 'No' END as submitted,
                   COALESCE(s.grade, 'Not Graded') as grade,
                   COALESCE(a.max_marks, 100) as max_marks,
                   CASE
                       WHEN s.grade IS NOT NULL THEN 'Graded'
                       WHEN s.submission_date IS NOT NULL THEN 'Submitted'
                       ELSE 'Not Submitted'
                   END as status
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.student_id = ?
            ORDER BY a.module_code, a.due_date DESC
        """, (student_id,))

        assignments = cursor.fetchall()

        # Convert Row objects to tuples and insert into tree
        for assignment in assignments:
            tree.insert('', tk.END, values=tuple(assignment))

        # Get assessments if table exists
        assessments = []
        try:
            cursor.execute("""
                SELECT 'Assessment' as type, a.module_code, a.assessment_name,
                       'N/A' as submitted,
                       COALESCE(g.score, 'Not Graded') as score,
                       COALESCE(a.max_points, 100) as max_points,
                       CASE WHEN g.score IS NOT NULL THEN 'Graded' ELSE 'Pending' END as status
                FROM assessments a
                LEFT JOIN grades g ON a.assessment_id = g.assessment_id AND g.student_id = ?
                WHERE a.module_code IN (SELECT module_code FROM student_modules WHERE student_id = ?)
                ORDER BY a.module_code
            """, (student_id, student_id))

            assessments = cursor.fetchall()
            for assessment in assessments:
                tree.insert('', tk.END, values=tuple(assessment))
        except Exception as e:
            print(f"Could not load assessments: {e}")  # For debugging

        conn.close()

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text=_t("student.summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        # Calculate totals from both assignments and assessments
        all_items = list(assignments) + list(assessments)
        total_items = len(all_items)
        submitted = sum(1 for item in all_items if len(item) > 3 and item[3] == 'Yes')
        graded = sum(1 for item in all_items if len(item) > 6 and 'Graded' in str(item[6]))

        ttk.Label(summary_frame, text=f"Total Assignments: {total_items}").grid(row=0, column=0, padx=10)
        ttk.Label(summary_frame, text=f"Submitted: {submitted}").grid(row=0, column=1, padx=10)
        ttk.Label(summary_frame, text=f"Graded: {graded}").grid(row=0, column=2, padx=10)

        # Close button
        ttk.Button(main_frame, text=_t("common.close"), command=grades_window.destroy).pack(pady=(10, 0))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_grades", error=str(e)))
        if 'grades_window' in locals():
            grades_window.destroy()
def view_student_attendance(self, student_id, email, first_name, last_name):
    """Display student attendance table and send email if below 90%"""
    try:
        attendance_window = tk.Toplevel(self.root)
        attendance_window.title(f"Attendance - {first_name} {last_name} ({student_id})")
        attendance_window.geometry("900x600")
        attendance_window.transient(self.root)

        main_frame = ttk.Frame(attendance_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"Attendance for {first_name} {last_name}",
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=(0, 10))

        # Create treeview for attendance
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("Date", "Module", "Session Type", "Status", "Reason")
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col)
        tree.column("Date", width=120)
        tree.column("Module", width=120)
        tree.column("Session Type", width=120)
        tree.column("Status", width=100)
        tree.column("Reason", width=200)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Fetch attendance from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            attendance_window.destroy()
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_date, s.module_code, r.status, r.notes
            FROM attendance_records r
            JOIN attendance_sessions s ON r.session_id = s.session_id
            WHERE r.student_id = ?
            ORDER BY s.session_date DESC
        """, (student_id,))

        attendance_records = cursor.fetchall()
        conn.close()

        present_count = 0
        total_count = len(attendance_records)

        for record in attendance_records:
            # Convert Row object to tuple
            record_tuple = tuple(record)
            date, module, status, reason = record_tuple
            # Default session type to 'Lecture' since it's not in the database
            tree.insert('', tk.END, values=(date, module, 'Lecture', status, reason or ''))
            if status and status.lower() == 'present':
                present_count += 1

        # Calculate attendance percentage
        attendance_percentage = (present_count / total_count * 100) if total_count > 0 else 0

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text=_t("student.attendance_summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(summary_frame, text=f"Total Sessions: {total_count}").grid(row=0, column=0, padx=10)
        ttk.Label(summary_frame, text=f"Present: {present_count}").grid(row=0, column=1, padx=10)

        # Attendance percentage label with color coding
        percentage_label = ttk.Label(summary_frame,
                                    text=f"Attendance: {attendance_percentage:.1f}%",
                                    font=('TkDefaultFont', 10, 'bold'))
        percentage_label.grid(row=0, column=2, padx=10)

        # Send email if attendance below 90%
        if attendance_percentage < 90 and email:
            # Send email alert
            email_sent = False
            try:
                import json
                from education_system.university_system.infrastructure.email.email_service import send_email
                from education_system.university_system.modules.shared.constants.paths import TEMPLATES_DIR

                # Load email template
                template_path = os.path.join(TEMPLATES_DIR, 'email', 'academics', 'low_attendance_alert.json')
                with open(template_path, 'r') as f:
                    template = json.load(f)

                # Build attendance summary
                attendance_summary = (
                    f"- Total Sessions: {total_count}\n"
                    f"- Sessions Attended: {present_count}\n"
                    f"- Sessions Missed: {total_count - present_count}"
                )

                # Replace placeholders in template
                student_name = f"{first_name} {last_name}"
                subject = template['subject'].replace('$student_name', student_name)
                message = template['body'].replace('$student_name', student_name)
                message = message.replace('$module_name', 'All Modules')
                message = message.replace('$attendance_percentage', f"{attendance_percentage:.1f}")
                message = message.replace('$attendance_summary', attendance_summary)
                message = message.replace('$signature', 'University Administration')

                email_sent = send_email(email, subject, message)

            except Exception as e:
                print(f"Failed to send attendance alert email: {e}")

            # Show status label based on whether email was sent
            if email_sent:
                ttk.Label(summary_frame,
                         text="⚠ Low Attendance Alert Sent",
                         foreground='red').grid(row=1, column=0, columnspan=3, pady=5)
            else:
                ttk.Label(summary_frame,
                         text="⚠ Low Attendance - Email notification failed",
                         foreground='orange').grid(row=1, column=0, columnspan=3, pady=5)

        # Close button
        ttk.Button(main_frame, text=_t("common.close"), command=attendance_window.destroy).pack(pady=(10, 0))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_attendance", error=str(e)))
        if 'attendance_window' in locals():
            attendance_window.destroy()

def view_student_timetable(self, student_id, first_name, last_name):
    """Display student's weekly timetable in grid format matching module scheduling GUI"""
    try:
        timetable_window = tk.Toplevel(self.root)
        timetable_window.title(f"Timetable - {first_name} {last_name} ({student_id})")
        timetable_window.geometry("1400x800")
        timetable_window.transient(self.root)

        main_frame = ttk.Frame(timetable_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = tk.Label(main_frame, text=f"Weekly Timetable for {first_name} {last_name} ({student_id})",
                              font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Fetch timetable from database
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student.db_connection_failed"))
            timetable_window.destroy()
            return

        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                ms.day_of_week,
                ms.start_time,
                ms.end_time,
                ms.module_code,
                m.module_name,
                ms.session_type,
                ms.room_id
            FROM student_modules sm
            JOIN module_schedule ms ON sm.module_code = ms.module_code
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY
                CASE ms.day_of_week
                    WHEN 'Monday' THEN 1
                    WHEN 'Tuesday' THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday' THEN 4
                    WHEN 'Friday' THEN 5
                    WHEN 'Saturday' THEN 6
                    WHEN 'Sunday' THEN 7
                END,
                ms.start_time
        """, (student_id,))

        timetable_data = cursor.fetchall()
        conn.close()

        if not timetable_data:
            tk.Label(main_frame, text=_t("student.no_timetable_entries"),
                    font=('Arial', 12)).pack(pady=20)
            ttk.Button(main_frame, text=_t("common.close"),
                      command=timetable_window.destroy).pack()
            return

        # Create canvas with scrollbars for grid view
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)

        grid_container = ttk.Frame(canvas)
        grid_container.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=grid_container, anchor="nw")
        canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Define time slots and days
        DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']

        # Create grid data structure
        grid_data = {}
        for day in DAYS_OF_WEEK:
            grid_data[day] = {}
            for time_slot in TIME_SLOTS:
                grid_data[day][time_slot] = []

        # Populate grid with timetable data
        for entry in timetable_data:
            day, start_time, end_time, module_code, module_name, session_type, room_id = entry

            if not day or not start_time:
                continue

            # Find the closest time slot
            try:
                closest_slot = min(TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
            except (ValueError, TypeError, IndexError):
                continue

            session_info = {
                'module': module_code or 'N/A',
                'name': module_name or 'Unknown Module',
                'type': session_type or 'Session',
                'room': f"Room {room_id}" if room_id else 'TBA',
                'time': f"{start_time}-{end_time}"
            }

            if day in grid_data and closest_slot in grid_data[day]:
                grid_data[day][closest_slot].append(session_info)

        # Create grid frame
        grid_frame = tk.Frame(grid_container)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header row - Time column
        time_header = tk.Label(grid_frame, text=_t("student.timetable_time"), font=('Arial', 10, 'bold'),
                              relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                              width=10, height=2)
        time_header.grid(row=0, column=0, padx=1, pady=1, sticky="nsew")

        # Day headers
        for col, day in enumerate(DAYS_OF_WEEK, 1):
            day_header = tk.Label(grid_frame, text=day, font=('Arial', 10, 'bold'),
                                 relief=tk.SOLID, borderwidth=2, bg='#4a90e2', fg='white',
                                 width=18, height=2)
            day_header.grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

        # Create time slots and schedule cells
        for row, time_slot in enumerate(TIME_SLOTS, 1):
            # Time label
            time_label = tk.Label(grid_frame, text=time_slot, font=('Arial', 9, 'bold'),
                                 relief=tk.SOLID, borderwidth=2, bg='#e8f4f8',
                                 width=10, height=4)
            time_label.grid(row=row, column=0, padx=1, pady=1, sticky="nsew")

            # Schedule cells for each day
            for col, day in enumerate(DAYS_OF_WEEK, 1):
                entries = grid_data[day][time_slot]

                # Create cell frame
                cell_frame = tk.Frame(grid_frame, relief=tk.SOLID, borderwidth=2,
                                     bg='#d4edda' if entries else 'white',
                                     width=160, height=80)
                cell_frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                cell_frame.grid_propagate(False)

                if entries:
                    # Inner container
                    inner_frame = tk.Frame(cell_frame, bg='#d4edda')
                    inner_frame.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

                    # Display entries
                    for i, entry in enumerate(entries):
                        if i < 2:  # Limit to 2 entries per cell
                            session_box = tk.Frame(inner_frame, relief=tk.RAISED, borderwidth=1,
                                                  bg='#c3e6cb', padx=2, pady=2)
                            session_box.pack(fill=tk.X, pady=1)

                            # Module code
                            module_label = tk.Label(session_box, text=entry['module'],
                                                   font=('Arial', 8, 'bold'),
                                                   bg='#c3e6cb', fg='#155724')
                            module_label.pack(anchor='w')

                            # Session type
                            type_label = tk.Label(session_box, text=entry['type'],
                                                 font=('Arial', 7),
                                                 bg='#c3e6cb', fg='#155724')
                            type_label.pack(anchor='w')

                            # Room
                            room_label = tk.Label(session_box, text=entry['room'],
                                                 font=('Arial', 6),
                                                 bg='#c3e6cb', fg='#155724')
                            room_label.pack(anchor='w')

                    if len(entries) > 2:
                        more_label = tk.Label(inner_frame, text=f"+ {len(entries)-2} more...",
                                             font=('Arial', 7, 'italic'),
                                             bg='#d4edda', fg='#155724')
                        more_label.pack(anchor='w', pady=2)

        # Summary frame
        summary_frame = ttk.LabelFrame(main_frame, text=_t("student.summary"), padding=10)
        summary_frame.pack(fill=tk.X, pady=(10, 0))

        # Calculate statistics
        total_sessions = len(timetable_data)
        unique_modules = len(set(entry[3] for entry in timetable_data))
        days_with_classes = len(set(entry[0] for entry in timetable_data))

        ttk.Label(summary_frame, text=f"Total Sessions: {total_sessions}").grid(row=0, column=0, padx=10)
        ttk.Label(summary_frame, text=f"Unique Modules: {unique_modules}").grid(row=0, column=1, padx=10)
        ttk.Label(summary_frame, text=f"Days with Classes: {days_with_classes}").grid(row=0, column=2, padx=10)

        # Close button
        ttk.Button(main_frame, text=_t("common.close"),
                  command=timetable_window.destroy).pack(pady=(10, 0))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_timetable", error=str(e)))
        if 'timetable_window' in locals():
            timetable_window.destroy()

def reassign_modules(self, student_id, module_type, cursor=None):
    """Reassign modules for a student"""
    should_close_conn = cursor is None

    try:
        if cursor is None:
            conn = get_db_connection()
            cursor = conn.cursor()

        # Import modules
        from education_system.university_system.modules.domain.academics.services.modules import (
            optional_module_1, optional_module_2, optional_module_3, optional_module_4,
            CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4,
            DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4
        )

        # Map module_type to the actual DB module_type value
        db_type_map = {'optional': 'optional', 'CS': 'CS_optional', 'DS': 'DS_optional'}
        db_module_type = db_type_map.get(module_type, module_type)

        # Delete existing modules of this type
        cursor.execute('''
            DELETE FROM student_modules
            WHERE student_id = ? AND module_code IN (
                SELECT module_code FROM modules WHERE module_type = ?
            )
        ''', (student_id, db_module_type))

        # Select new modules
        if module_type == 'optional':
            available_modules = [optional_module_1, optional_module_2, optional_module_3, optional_module_4]
        elif module_type == 'CS':
            available_modules = [CS_optional_module_1, CS_optional_module_2, CS_optional_module_3, CS_optional_module_4]
        elif module_type == 'DS':
            available_modules = [DS_optional_module_1, DS_optional_module_2, DS_optional_module_3, DS_optional_module_4]
        else:
            return

        selected_modules = random.sample(available_modules, 2)

        # Insert new modules
        for module in selected_modules:
            cursor.execute('''
                INSERT INTO student_modules (student_id, module_code, enrollment_date, status)
                VALUES (?, ?, ?, ?)
            ''', (student_id, module['code'], datetime.now().strftime('%Y-%m-%d'), 'enrolled'))

        if should_close_conn:
            conn.commit()
            conn.close()

        messagebox.showinfo(_t("common.success"), _t("student.reassign_modules_success", module_type=module_type))

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_reassign_modules", error=str(e)))
