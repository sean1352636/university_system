# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.post_18.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.post_18.university_system.core.i18n import get_text as _t
from education_system.post_18.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.post_18.university_system.core.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.post_18.university_system.modules.shared.gui.main.students.student_crud_gui")

try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _DOBPicker, _safe_set_combobox, _safe_entry_insert
from .importers import _open_sixth_form_import_dialog, _open_bulk_csv_import_dialog
from .sync.visa import _create_visa_record_for_new_student
from .sync.atas import _resync_atas_after_module_change
from .sync.auth import _ensure_shared_auth_user, _purge_user_from_all_chat_rooms
from .sync.chat_rooms import _auto_join_module_chat_rooms, _resolve_module_name, _sync_module_chat_rooms
from education_system.post_18.university_system.modules.shared.services.student_provisioning import (
    compute_age as _compute_age,
)

def update_student_dialog(self, student_id):
    """Comprehensive update student dialog with full editing capabilities and random course assignment"""
    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
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
                    age = _compute_age(dob)
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
                        new_age = _compute_age(dob_date)
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

                # Handle course change — drop the old curriculum and enrol the
                # student in the new course's full 18-module curriculum
                # (6/year x 3), the same set the single-create and CLI paths
                # use (rather than a hand-picked 6).
                if course_changed:
                    from education_system.post_18.university_system.modules.domain.academics.services.admissions_selection import (
                        enrol_student_in_curriculum,
                    )

                    # Capture the modules being dropped so we can cancel unpaid
                    # enrolment fees, release holds, and sync chat rooms below.
                    dropped_modules = [
                        r[0] for r in update_cursor.execute(
                            'SELECT module_code FROM student_modules '
                            'WHERE student_id = ?', (student_id,)
                        ).fetchall()
                    ]

                    # Remove the old modules, then enrol the full new
                    # curriculum on the same cursor (atomic with the update).
                    update_cursor.execute(
                        'DELETE FROM student_modules WHERE student_id = ?',
                        (student_id,))
                    curriculum = enrol_student_in_curriculum(
                        update_cursor, student_id, new_course, new_course)
                    selected_modules = [m['module_code'] for m in curriculum]

                # Commit the module insert/delete BEFORE running the
                # cross-domain bus calls below — same fix as 8.117.39
                # in the create flow. SQLite serialises writers, so
                # bus calls (which open their own connections) deadlock
                # waiting for this transaction to commit while we wait
                # for them to return.
                update_conn.commit()

                # ── Bus side effects, on fresh connections ──────────
                # Only relevant when the course actually changed (which
                # is when ``selected_modules`` and ``dropped_modules``
                # are defined). Best-effort: a failure here can't roll
                # back the module update — that's already committed.
                if course_changed:
                    try:
                        from education_system.post_18.university_system.modules.domain.finance.services.enrolment_fees import (
                            cancel_module_enrolment_fee,
                            assess_module_enrolment_fee,
                        )
                        for code in dropped_modules:
                            if code not in selected_modules:
                                cancel_module_enrolment_fee(student_id, code)
                        for code in selected_modules:
                            assess_module_enrolment_fee(student_id, code)
                    except Exception as exc:
                        print(f"Note: could not sync enrolment fees: {exc}")

                    try:
                        from education_system.post_18.university_system.modules.domain.commerce.textbooks.services.library_holds import (
                            place_holds_for_enrolment,
                            release_holds_for_drop,
                        )
                        for code in dropped_modules:
                            if code not in selected_modules:
                                release_holds_for_drop(student_id, code)
                        for code in selected_modules:
                            place_holds_for_enrolment(student_id, code)
                    except Exception as exc:
                        print(f"Note: could not sync library holds: {exc}")

                    try:
                        from education_system.post_18.university_system.modules.domain.academics.services.course_management.timetable_sync import (
                            sync_for_student_enrolment,
                            clear_for_student_drop,
                        )
                        for code in dropped_modules:
                            if code not in selected_modules:
                                clear_for_student_drop(student_id, code)
                        for code in selected_modules:
                            sync_for_student_enrolment(student_id, code)
                    except Exception as exc:
                        print(f"Note: could not sync timetables: {exc}")

                    # Sync module chat-room membership to the new curriculum:
                    # leave the dropped modules' rooms and join (creating if
                    # needed) the new ones. Emails the student a summary.
                    try:
                        removed = [c for c in dropped_modules
                                   if c not in selected_modules]
                        added = [c for c in selected_modules
                                 if c not in dropped_modules]
                        _sync_module_chat_rooms(student_id, removed, added)
                    except Exception as exc:
                        print(f"Note: could not sync module chat rooms: {exc}")

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
                            from education_system.post_18.university_system.infrastructure.email.email_service import send_update_confirmation
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
