
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.sql_safety import escape_like
import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.systems.university.domains.learners.interfaces.gui.alumni._service_imports import (
    init_alumni_db,
    view_events,
    create_enhanced_event,
    event_check_in_system,
    view_connection_requests,
    manage_business_directory,
    manage_alumni_forum,
    post_job_opportunity,
    view_job_board,
    schedule_career_counseling,
    view_engagement_leaderboard,
    view_my_badges,
    manage_photo_gallery,
    manage_class_reunions,
    generate_alumni_report,
    set_auth,
    setup_alumni_permissions,
    generate_engagement_recommendations,
    get_connection,
)



class AlumniCRUDMixin:
        def check_finance_status(self, student_id, alumni_email):
            """Check if alumni owes money to the university"""
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check outstanding balances
                cursor.execute('''
                    SELECT
                        SUM(CASE WHEN status = 'pending' THEN amount ELSE 0 END) as pending_amount,
                        SUM(CASE WHEN status = 'overdue' THEN amount ELSE 0 END) as overdue_amount
                    FROM student_fees
                    WHERE student_id = ?
                ''', (student_id,))

                result = cursor.fetchone()
                conn.close()

                pending_amount = result[0] if result[0] else 0
                overdue_amount = result[1] if result[1] else 0
                total_owed = pending_amount + overdue_amount

                return {
                    'has_debt': total_owed > 0,
                    'pending_amount': pending_amount,
                    'overdue_amount': overdue_amount,
                    'total_owed': total_owed
                }

            except sqlite3.Error as e:
                print(f"Error checking finance status: {e}")
                return {'has_debt': False, 'error': f'Could not check finance status: {e}'}

        def _load_finance_people(self):
            """Return [(label, student_id, email)] for alumni + students that
            exist in the database. Finance status is keyed on student_id, so
            only people with a real DB record are offered (no free-text)."""
            people = []
            seen = set()
            try:
                conn = self._get_db_connection()
                cursor = conn.cursor()
                for sql in (
                    "SELECT student_id, first_name, last_name, email_address FROM alumni "
                    "WHERE student_id IS NOT NULL AND TRIM(student_id) != '' "
                    "ORDER BY last_name, first_name",
                    "SELECT student_id, first_name, last_name, email_address FROM students "
                    "WHERE student_id IS NOT NULL AND TRIM(student_id) != '' "
                    "ORDER BY last_name, first_name",
                ):
                    try:
                        cursor.execute(sql)
                    except sqlite3.Error:
                        continue
                    for sid, fn, ln, email in cursor.fetchall():
                        sid = str(sid)
                        if sid in seen:
                            continue
                        seen.add(sid)
                        name = f"{(fn or '').strip()} {(ln or '').strip()}".strip() or sid
                        people.append((f"{sid} — {name}", sid, email or ""))
                conn.close()
            except sqlite3.Error as e:
                import logging
                logging.warning(f"Failed to load finance people list: {e}")
            return people

        def show_finance_check(self):
            """Show finance status check interface"""
            self.clear_content()
            self.update_status("Finance Status Check")

            # Title
            title_label = ttk.Label(self.content_frame, text=_t('gui.learners.alumni.alumni_crud.labels.finance_status_check', default="Finance Status Check"),
                                   font=('Arial', 16, 'bold'))
            title_label.pack(pady=20)

            # Input frame
            input_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.alumni_crud.labels.check_finance_status', default="Check Finance Status"), padding=20)
            input_frame.pack(fill=tk.X, padx=20, pady=10)

            # Only users that exist in the DB are selectable (no free-text search).
            people = self._load_finance_people()
            label_map = {label: (sid, email) for label, sid, email in people}

            # Person dropdown
            ttk.Label(input_frame, text=_t('gui.learners.alumni.alumni_crud.labels.alumnus_student', default="Alumnus / Student:")).grid(row=0, column=0, sticky='w', pady=5)
            person_var = tk.StringVar()
            person_combo = ttk.Combobox(input_frame, textvariable=person_var, width=45,
                                        state='readonly',
                                        values=[label for label, _s, _e in people])
            person_combo.grid(row=0, column=1, padx=10, pady=5, sticky='w')

            # Student ID (autofilled, read-only)
            ttk.Label(input_frame, text=_t('gui.learners.alumni.alumni_crud.labels.student_id', default="Student ID:")).grid(row=1, column=0, sticky='w', pady=5)
            student_id_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=student_id_var, width=20,
                      state='readonly').grid(row=1, column=1, padx=10, pady=5, sticky='w')

            # Email (autofilled, read-only)
            ttk.Label(input_frame, text=_t('gui.learners.alumni.alumni_crud.labels.email', default="Email:")).grid(row=2, column=0, sticky='w', pady=5)
            email_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=email_var, width=30,
                      state='readonly').grid(row=2, column=1, padx=10, pady=5, sticky='w')

            def on_person_selected(_event=None):
                sid, email = label_map.get(person_var.get(), ("", ""))
                student_id_var.set(sid)
                email_var.set(email or "")
            person_combo.bind("<<ComboboxSelected>>", on_person_selected)

            if not people:
                ttk.Label(input_frame,
                          text=_t('gui.learners.alumni.alumni_crud.labels.no_alumni_or_students_found_in_the_database', default="No alumni or students found in the database."),
                          foreground='#b3261e').grid(row=3, column=0, columnspan=2, pady=10)

            # Check button
            def check_finance():
                student_id = student_id_var.get().strip()
                if not student_id:
                    messagebox.showerror(_t('gui.learners.alumni.alumni_crud.dialogs.selection_required', default="Selection Required"),
                                         _t('gui.learners.alumni.alumni_crud.dialogs.please_select_an_alumnus_or_student_from_the_list', default="Please select an alumnus or student from the list."))
                    return

                finance_status = self.check_finance_status(student_id, email_var.get().strip())

                if 'error' in finance_status:
                    messagebox.showerror(_t('gui.learners.alumni.alumni_crud.dialogs.error', default="Error"), finance_status['error'])
                else:
                    self.show_finance_status_dialog(
                        finance_status, person_var.get() or f"Student {student_id}")

            ttk.Button(input_frame, text=_t('gui.learners.alumni.alumni_crud.buttons.check_finance_status', default="Check Finance Status"),
                      command=check_finance).grid(row=4, column=0, columnspan=2, pady=20)

        def show_finance_status_dialog(self, finance_status, alumni_name):
            """Show dialog with finance status information"""
            dialog = tk.Toplevel(self.root)
            dialog.title(_t('gui.learners.alumni.alumni_crud.windows.finance_status', default="Finance Status"))
            dialog.geometry("400x300")
            dialog.configure(bg='white')
            dialog.grab_set()

            if finance_status['has_debt']:
                # Show debt information
                tk.Label(dialog, text=_t('gui.learners.alumni.alumni_crud.labels.outstanding_balance', default="Outstanding Balance"), font=('Arial', 14, 'bold'),
                        bg='white', fg='#e74c3c').pack(pady=10)

                info_frame = tk.Frame(dialog, bg='white')
                info_frame.pack(fill='x', padx=20, pady=10)

                tk.Label(info_frame, text=f"Pending Amount: £{finance_status['pending_amount']:.2f}",
                        font=('Arial', 11), bg='white', fg='#34495e').pack(anchor='w')
                tk.Label(info_frame, text=f"Overdue Amount: £{finance_status['overdue_amount']:.2f}",
                        font=('Arial', 11), bg='white', fg='#e74c3c').pack(anchor='w')
                tk.Label(info_frame, text=f"Total Owed: £{finance_status['total_owed']:.2f}",
                        font=('Arial', 12, 'bold'), bg='white', fg='#e74c3c').pack(anchor='w', pady=(5, 0))

                tk.Button(dialog, text=_t('gui.learners.alumni.alumni_crud.buttons.open_finance_system', default="Open Finance System"),
                         command=lambda: self.open_finance_gui(),
                         bg='#27ae60', fg='white', font=('Arial', 11),
                         padx=20, pady=8, relief='flat').pack(pady=10)
            else:
                # No debt
                tk.Label(dialog, text=_t('gui.learners.alumni.alumni_crud.labels.finance_status_clear', default="Finance Status: Clear"), font=('Arial', 14, 'bold'),
                        bg='white', fg='#27ae60').pack(pady=20)
                tk.Label(dialog, text=_t('gui.learners.alumni.alumni_crud.labels.no_outstanding_balance_found', default="No outstanding balance found."),
                        font=('Arial', 11), bg='white', fg='#34495e').pack(pady=10)

            tk.Button(dialog, text=_t('gui.learners.alumni.alumni_crud.buttons.close', default="Close"), command=dialog.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10),
                     padx=20, pady=5, relief='flat').pack(pady=10)

        def show_student_validation(self):
            """Show student validation interface"""
            self.clear_content()
            self.update_status("Student Validation")

            # Title
            title_label = ttk.Label(self.content_frame, text=_t('gui.learners.alumni.alumni_crud.labels.student_record_validation', default="Student Record Validation"),
                                   font=('Arial', 16, 'bold'))
            title_label.pack(pady=20)

            # Input frame
            input_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.learners.alumni.alumni_crud.labels.validation_inputs', default="Validation Inputs"), padding=20)
            input_frame.pack(fill=tk.X, padx=20, pady=10)

            # Student ID input
            ttk.Label(input_frame, text=_t('gui.learners.alumni.alumni_crud.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky='w', pady=5)
            student_id_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, padx=10, pady=5)

            # Email input
            ttk.Label(input_frame, text=_t('gui.learners.alumni.alumni_crud.labels.email', default="Email:")).grid(row=1, column=0, sticky='w', pady=5)
            email_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=email_var, width=30).grid(row=1, column=1, padx=10, pady=5)

            # Validate button
            def validate_student():
                student_id = student_id_var.get().strip()
                email = email_var.get().strip()

                if not student_id and not email:
                    messagebox.showerror(_t('gui.learners.alumni.alumni_crud.dialogs.input_required', default="Input Required"), _t('gui.learners.alumni.alumni_crud.dialogs.please_enter_either_student_id_or_email', default="Please enter either Student ID or Email"))
                    return

                result = self.validate_student_record(student_id, email)

                if result['valid']:
                    messagebox.showinfo(_t('gui.learners.alumni.alumni_crud.dialogs.validation_result', default="Validation Result"),
                                      f"Valid Student Found!\n\n"
                                      f"Student ID: {result['student_id']}\n"
                                      f"Name: {result['name']}\n"
                                      f"Email: {result['email']}\n"
                                      f"Graduation Date: {result.get('graduation_date', 'N/A')}")
                else:
                    messagebox.showerror(_t('gui.learners.alumni.alumni_crud.dialogs.validation_result', default="Validation Result"),
                                       f"Validation Failed!\n\n"
                                       f"Error: {result['error']}")

            ttk.Button(input_frame, text=_t('gui.learners.alumni.alumni_crud.buttons.validate_student', default="Validate Student"),
                      command=validate_student).grid(row=2, column=0, columnspan=2, pady=20)

        def validate_student_record(self, student_id, email):
            """Validate if user is a valid student in the database"""
            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Check if student exists in students table
                cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name, s.email_address, NULL
                    FROM students s
                    WHERE s.student_id = ? OR s.email_address = ?
                ''', (student_id, email))

                student_record = cursor.fetchone()
                conn.close()

                if student_record:
                    return {
                        'valid': True,
                        'student_id': student_record[0],
                        'name': f"{student_record[1]} {student_record[2]}",
                        'email': student_record[3],
                        'graduation_date': student_record[4]
                    }
                else:
                    return {'valid': False, 'error': 'Student record not found'}

            except sqlite3.Error as e:
                return {'valid': False, 'error': f'Database error: {e}'}

