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
from education_system.systems.university.infrastructure.database.db import get_db_connection, get_connection, transaction, foreign_keys_off
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

from .widgets import _safe_set_combobox, _safe_entry_insert
from .authorization import require_student_permission
from .sync.auth import _purge_user_from_all_chat_rooms
from education_system.systems.university.domains.admissions.domain.services.admissions_selection import (
    purge_user_chat_on_cursor,
)

def delete_student_dialog(self, student_id=None):
    """Comprehensive delete student dialog with safety checks"""
    if not require_student_permission(self, "delete_any_student", "delete"):
        return
    if not student_id:
        # Show selection dialog first
        student_id = self.select_student_for_deletion()
        if not student_id:
            return

    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
    dialog.title(_t("student.delete_student_title").replace("{student_id}", str(student_id)))
    _fit_window(dialog, "900x900", minsize=(640, 480))
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

        warning_label = ttk.Label(warning_frame, text="Withdraw this student",
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
Withdrawing keeps all of these and switches off the student's sign-in.
It can be undone (Registration status > Reinstate).
Permanent erasure is a separate, dual-control request."""

        ttk.Label(related_frame, text=related_info, font=('Courier', 10), foreground="dark red").pack(anchor=tk.W)

        # Confirmation section
        confirm_frame = ttk.LabelFrame(main_frame, text=_t("student.confirmation_required"), padding=15)
        confirm_frame.pack(fill=tk.X, pady=(0, 20))


        ttk.Label(confirm_frame, text=_t("student.type_to_confirm").replace("{student_id}", str(student_id))).pack(anchor=tk.W)
        confirm_entry = ttk.Entry(confirm_frame, width=30, font=('Arial', 11))
        confirm_entry.pack(pady=(5, 10), fill=tk.X)

        ttk.Label(confirm_frame, text="Reason for withdrawal *").pack(anchor=tk.W)
        reason_entry = ttk.Entry(confirm_frame, width=50)
        reason_entry.pack(pady=(2, 6), fill=tk.X)

        status_label = ttk.Label(confirm_frame, text="", foreground="red")
        status_label.pack(pady=(10, 0))

        # Close the initial read-only connection before performing destructive work
        if conn:
            conn.close()

        def perform_deactivation():
            """Soft-delete: flip the student to inactive + Withdrawn.

            Reversible — keeps every related record (grades,
            modules, attendance, chat history, user account)
            untouched, except that the student is dropped out of
            their module chat-room memberships so they no longer
            appear in active class chats (their messages are kept).
            Only the typed-id check is required; the checkbox /
            final-confirm gate is reserved for the permanent path.
            """
            entered_id = confirm_entry.get().strip()
            if entered_id != str(student_id).strip():
                status_label.config(text=_t("student.id_mismatch"))
                return
            try:
                status_label.config(
                    text=f"Deactivating student {student_id} …",
                    foreground="blue")
                dialog.update()
                if not require_student_permission(self, "delete_any_student", "delete"):
                    return
                from education_system.systems.university.application.students.lifecycle import StudentLifecycleService
                actor = str((getattr(self.auth, 'current_user', {}) or {}).get('id', 'unknown'))
                reason = reason_entry.get().strip()
                if not reason:
                    status_label.config(text="Give the reason for the withdrawal.",
                                        foreground="red")
                    return
                StudentLifecycleService().deactivate(
                    str(student_id), actor_id=actor, reason=reason,
                    idempotency_key=f"gui:student:{student_id}:deactivate:{secrets.token_urlsafe(12)}",
                )
                if ACTIVITY_LOGGER_AVAILABLE:
                    try:
                        log_activity(
                            'deactivate', 'student',
                            user_id=getattr(getattr(self, 'auth', None),
                                              'current_user', {}).get('user_id'),
                            details={'student_id': student_id})
                    except Exception:
                        logger.debug("Suppressed exception", exc_info=True)
                messagebox.showinfo(
                    _t('gui.learners.students.student_crud_gui.delete.dialogs.student_deactivated', default="Student deactivated"),
                    f"Student {student_id} has been marked Withdrawn "
                    "and their login disabled. Their academic records "
                    "(grades, modules, attendance, etc.) are preserved "
                    "and the action can be reversed by reactivating "
                    "the record.",
                )
                try:
                    if hasattr(self, 'view_students'):
                        self.view_students()
                    self.refresh_advanced_search()
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
                try:
                    if dialog.winfo_exists():
                        dialog.destroy()
                except tk.TclError:
                    pass
            except Exception as e:
                logger.exception("Deactivate failed for %s", student_id)
                messagebox.showerror(
                    _t('gui.learners.students.student_crud_gui.delete.dialogs.deactivation_failed', default="Deactivation failed"), str(e))
                try:
                    status_label.config(
                        text=_t('gui.learners.students.student_crud_gui.delete.text.deactivation_failed', default="Deactivation failed."),
                        foreground="red")
                except tk.TclError:
                    pass

        def explain_controlled_purge():
            from .erasure import request_erasure_dialog
            request_erasure_dialog(self, dialog, student_id)

        # Buttons. Deactivate (soft-delete) is the default and
        # safest action — keeps history, reversible. Permanent
        # delete is still available but framed clearly as the
        # destructive option.
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame,
                    text=_t('gui.learners.students.student_crud_gui.delete.buttons.deactivate_recommended', default="Deactivate (recommended)"),
                    command=perform_deactivation,
                    style="Accent.TButton").pack(side=tk.LEFT,
                                                    padx=(0, 10))
        ttk.Button(button_frame,
                    text="Request permanent erasure…",
                    command=explain_controlled_purge).pack(
            side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text=_t("common.cancel"),
                    command=dialog.destroy).pack(side=tk.LEFT)

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
    _install_clean_close(selection_dialog)
    selection_dialog.title(_t("student.select_student_delete"))
    _fit_window(selection_dialog, "1000x700", minsize=(640, 480))
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
