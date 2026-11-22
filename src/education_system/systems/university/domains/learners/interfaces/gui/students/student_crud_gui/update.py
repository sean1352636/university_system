# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.platform.delivery.gui.tk_callback_filter import install_clean_close as _install_clean_close
from education_system.platform.delivery.gui.window_sizing import fit as _fit_window

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.systems.university.infrastructure.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui")

try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _DOBPicker, _safe_set_combobox, _safe_entry_insert
from .authorization import require_student_permission
from .importers import _open_sixth_form_import_dialog, _open_bulk_csv_import_dialog
from .sync.visa import _create_visa_record_for_new_student
from .sync.atas import _resync_atas_after_module_change
from .sync.auth import _ensure_shared_auth_user, _purge_user_from_all_chat_rooms
from .sync.chat_rooms import _auto_join_module_chat_rooms, _resolve_module_name, _sync_module_chat_rooms
from education_system.systems.university.services.student_provisioning import (
    compute_age as _compute_age,
)

def update_student_dialog(self, student_id):
    """Comprehensive update student dialog with full editing capabilities and random course assignment"""
    if not require_student_permission(self, "update_any_student", "update"):
        return
    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
    dialog.title(_t("student.update_student_title", student_id=student_id))
    _fit_window(dialog, "800x900", minsize=(640, 480))
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
        # SELECT * + positional indices is fragile (a column inserted mid-table
        # shifts every index below it). Resolve new fields by name.
        _col_index = {d[0]: i for i, d in enumerate(cursor.description or ())}

        def _sval(column, default=''):
            i = _col_index.get(column)
            if i is None or student is None or i >= len(student):
                return default
            return student[i] if student[i] is not None else default

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
        from education_system.systems.university.application.students.lifecycle import (
            GENDER_OPTIONS, gender_label,
        )
        gender_options = list(GENDER_OPTIONS)
        gender_value = gender_label((student[6] or '').strip())
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

        # Pronouns — free text, not a fixed list: the point is that the
        # student says what they use.
        ttk.Label(personal_frame,
                  text=_t("student.pronouns_label", default="Pronouns:")).grid(
            row=6, column=0, sticky=tk.W, pady=5)
        fields['pronouns'] = ttk.Entry(personal_frame, width=30)
        fields['pronouns'].grid(row=6, column=1, pady=5, padx=(10, 0))
        _safe_entry_insert(fields['pronouns'], _sval('pronouns'))

        # Emergency contact
        ttk.Label(personal_frame,
                  text=_t("student.emergency_contact_label",
                          default="Emergency contact:")).grid(
            row=7, column=0, sticky=tk.W, pady=5)
        fields['emergency_contact'] = ttk.Entry(personal_frame, width=30)
        fields['emergency_contact'].grid(row=7, column=1, pady=5, padx=(10, 0))
        _safe_entry_insert(fields['emergency_contact'], _sval('emergency_contact'))
        ttk.Label(personal_frame,
                  text=_t("student.emergency_contact_hint",
                          default="Name and how to reach them"),
                  foreground="gray").grid(row=8, column=1, sticky=tk.W,
                                          padx=(10, 0))

        # Contact and study details (validated by the lifecycle service).
        from education_system.systems.university.application.students import (
            record_rules as _record_rules,
        )
        # Address lines: split from the one address for records made
        # before the lines were held separately.
        _lines = tuple(_sval(k) or '' for k in _record_rules.ADDRESS_LINE_FIELDS)
        if not any(_lines) and _sval('address'):
            _lines = tuple(p or '' for p in _record_rules.split_address(_sval('address')))
        _line_values = dict(zip(_record_rules.ADDRESS_LINE_FIELDS, _lines))
        for row, (key, label) in enumerate((("phone", "Phone"), ("personal_email", "Personal email"),
                                            ("address_line1", "Address line 1"),
                                            ("address_line2", "Address line 2"),
                                            ("town", "Town"),
                                            ("postcode", "Postcode"),
                                            ("nationality", "Nationality"),
                                            ("preferred_name", "Preferred name"),
                                            ("notes", "Notes")), 9):
            ttk.Label(personal_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
            fields[key] = ttk.Entry(personal_frame, width=30)
            fields[key].grid(row=row, column=1, pady=5, padx=(10, 0))
            _safe_entry_insert(fields[key], _line_values.get(key, _sval(key)))
        for row, (key, label, values) in enumerate((
                ("mode_of_study", "Mode of study", _record_rules.MODES),
                ("fee_status", "Fee status", _record_rules.FEE_STATUSES)), 18):
            ttk.Label(personal_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=5)
            fields[key] = ttk.Combobox(personal_frame, values=list(values), state='readonly',
                                       width=27)
            fields[key].grid(row=row, column=1, pady=5, padx=(10, 0), sticky=tk.W)
            _safe_set_combobox(fields[key], str(_sval(key) or '').lower())
        ttk.Label(personal_frame, text="Reason for these changes *").grid(
            row=20, column=0, sticky=tk.W, pady=(12, 5))
        fields['reason'] = ttk.Entry(personal_frame, width=30)
        fields['reason'].grid(row=20, column=1, pady=(12, 5), padx=(10, 0))

        # Academic Information
        academic_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.academic_info"), padding=15)
        academic_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Course selection comes from the same live catalogue as create/CLI.
        ttk.Label(academic_frame, text=_t("student.course_label")).grid(row=0, column=0, sticky=tk.W, pady=5)
        course_frame = ttk.Frame(academic_frame)
        course_frame.grid(row=0, column=1, pady=5, padx=(10, 0), sticky=tk.W)

        from education_system.systems.university.domains.admissions.domain.services.admissions_selection import list_active_courses
        course_choices = [row['code'] for row in list_active_courses()]
        if student[9] and student[9] not in course_choices:
            course_choices.insert(0, student[9])
        # A course change is a transfer: old modules are kept as
        # 'Transferred' (with their marks) and the new curriculum is added.
        ttk.Label(course_frame, text=student[9] or '—', width=12).pack(side=tk.LEFT)
        ttk.Button(course_frame, text="Transfer to another course…",
                   command=lambda: _transfer_course_dialog(
                       self, dialog, student_id, student[9], course_choices)).pack(
            side=tk.LEFT, padx=(8, 0))

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
                  command=lambda: self.reassign_modules(student_id, 'optional', parent=dialog)).pack(side=tk.LEFT, padx=5)

        # Validation feedback
        validation_label = ttk.Label(scrollable_frame, text="", foreground="red")
        validation_label.grid(row=5, column=0, columnspan=2, pady=10)

        # Password update section
        password_frame = ttk.LabelFrame(scrollable_frame, text=_t("student.password_management"), padding=15)
        password_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        password_var = tk.BooleanVar()
        ttk.Checkbutton(password_frame, text="Send a single-use password setup link",
                       variable=password_var).pack(anchor=tk.W)

        ttk.Label(password_frame,
                 text="The link is emailed to the student and expires after 30 minutes.",
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
            """Save the edits through the lifecycle service, with a reason;
            only fields that actually changed are sent (and recorded)."""
            if not require_student_permission(self, "update_any_student", "update"):
                return
            errors = validate_update_form()
            if not fields['reason'].get().strip():
                errors.append("Give a reason for the changes")
            if errors:
                validation_label.config(text="; ".join(errors))
                return
            validation_label.config(text="")
            from education_system.systems.university.application.students.lifecycle import (
                StudentLifecycleService,
                StudentValidationError,
            )
            keys = ('title', 'first_name', 'middle_name', 'last_name', 'gender', 'dob',
                    'pronouns', 'emergency_contact', 'phone', 'personal_email',
                    'nationality', 'mode_of_study', 'fee_status', 'preferred_name',
                    'postcode', 'notes', 'address_line1', 'address_line2', 'town')
            changes = {}
            for key in keys:
                value = fields[key].get().strip() if hasattr(fields[key].get(), 'strip') \
                    else fields[key].get()
                if key == 'gender':
                    value = value.lower()
                if (value or None) != (str(_sval(key)).strip() or None):
                    changes[key] = value or None
            if not changes and not password_var.get():
                validation_label.config(text="Nothing has changed.")
                return
            actor = str((getattr(self.auth, 'current_user', {}) or {}).get('id', 'unknown'))
            try:
                if changes:
                    StudentLifecycleService().update(
                        str(student_id), changes, actor_id=actor,
                        reason=fields['reason'].get().strip(),
                        idempotency_key=f"gui:update:{student_id}:{secrets.token_urlsafe(18)}",
                    )
                if password_var.get():
                    from education_system.systems.university.services.student_provisioning import send_student_activation
                    send_student_activation(student[1])
            except StudentValidationError as exc:
                validation_label.config(text="; ".join(f"{k}: {v}" for k, v in exc.errors.items()))
                return
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("student.failed_update_student", error=str(e)))
                return
            messagebox.showinfo(
                _t("common.success"),
                _t("student.student_updated_success", student_id=student_id),
                parent=dialog,
            )
            if hasattr(self, 'view_students'):
                self.view_students()
            self.refresh_advanced_search()
            dialog.destroy()

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
        # Scope wheel handling to this canvas; global bindings leak into other
        # dialogs and break predictable keyboard/pointer navigation.
        canvas.bind("<Enter>", lambda _event: canvas.bind("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _event: canvas.unbind("<MouseWheel>"))

    except Exception as e:
        logging.exception("Failed to load student data for student_id=%s", student_id)
        messagebox.showerror(_t("common.error"), _t("student.failed_load_student_data", error=str(e)))
        dialog.destroy()


def _transfer_course_dialog(self, parent, student_id, current, choices):
    """Ask for the new course and a reason, then transfer through the
    lifecycle service (old modules kept as 'Transferred', marks untouched)."""
    win = tk.Toplevel(parent)
    _install_clean_close(win)
    win.title(f"Transfer {student_id}")
    win.transient(parent)
    body = ttk.Frame(win, padding=12)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(body, text=f"Current course: {current or '—'}").grid(row=0, column=0, columnspan=2,
                                                                  sticky=tk.W)
    ttk.Label(body, text="New course").grid(row=1, column=0, sticky=tk.W, pady=4)
    course = ttk.Combobox(body, values=[c for c in choices if c != current], state='readonly',
                          width=20)
    course.grid(row=1, column=1, sticky=tk.W, pady=4)
    ttk.Label(body, text="Reason *").grid(row=2, column=0, sticky=tk.W, pady=4)
    reason = ttk.Entry(body, width=40)
    reason.grid(row=2, column=1, sticky=tk.W, pady=4)

    def go():
        from education_system.systems.university.application.students.lifecycle import (
            StudentLifecycleService,
            StudentValidationError,
        )
        actor = str((getattr(self.auth, 'current_user', {}) or {}).get('id', 'unknown'))
        try:
            StudentLifecycleService().transfer_course(
                str(student_id), course.get(), actor_id=actor, reason=reason.get().strip(),
                idempotency_key=f"gui:transfer:{student_id}:{secrets.token_urlsafe(18)}")
        except StudentValidationError as exc:
            messagebox.showerror("Transfer", "; ".join(f"{k}: {v}" for k, v in exc.errors.items()),
                                 parent=win)
            return
        messagebox.showinfo("Transfer", f"{student_id} moved to {course.get()}.", parent=win)
        win.destroy()
        parent.destroy()
        if hasattr(self, 'view_students'):
            self.view_students()
    ttk.Button(body, text="Transfer", command=go).grid(row=3, column=1, sticky=tk.W, pady=8)

