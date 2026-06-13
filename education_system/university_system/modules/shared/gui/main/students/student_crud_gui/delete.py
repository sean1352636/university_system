# Auto-generated module (split from student_crud_gui.py)
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging
import random
import secrets
import json
import csv
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from education_system.university_system.modules.shared.gui.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.university_system.core.i18n import get_text as _t
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction, foreign_keys_off
from education_system.university_system.core.sql_safety import (
    validate_table_name,
    validate_column_name,
    SQLIdentifierError,
)

logger = logging.getLogger("education_system.university_system.modules.shared.gui.main.students.student_crud_gui")

try:
    from education_system.university_system.core.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False

from .widgets import _safe_set_combobox, _safe_entry_insert
from .sync.auth import _purge_user_from_all_chat_rooms
from education_system.university_system.modules.domain.academics.services.admissions_selection import (
    purge_user_chat_on_cursor,
)

def delete_student_dialog(self, student_id=None):
    """Comprehensive delete student dialog with safety checks"""
    if not student_id:
        # Show selection dialog first
        student_id = self.select_student_for_deletion()
        if not student_id:
            return

    dialog = tk.Toplevel(self.root)
    _install_clean_close(dialog)
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

                deletion_log = []

                # Delete the student + all related rows with FK checks off; the
                # context manager restores enforcement even if the body raises.
                with foreign_keys_off(conn):
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
                        ('parent_student_relationships', 'student_id'),
                        # Tier-4 / Student Route sponsor-compliance tables —
                        # leaving these orphaned is a UKVI data-protection
                        # issue, not just clutter.
                        ('visa_records', 'student_id'),
                        ('cas_records', 'student_id'),
                        ('visa_engagement_checks', 'student_id'),
                        ('visa_change_of_circumstance', 'student_id'),
                        ('right_to_study_checks', 'student_id'),
                        ('atas_clearances', 'student_id'),
                        ('visa_expiry_alert_log', 'student_id'),
                        # Attendance pipeline's UKVI mirror — see 8.117.132.
                        ('ukvi_engagement_events', 'student_id'),
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

                conn.commit()
                conn.close()
                conn = None

                # Purge chat-room memberships and any messages this user
                # sent, BEFORE the user row goes away. Done on a fresh
                # connection to keep this independent of the main delete tx.
                if user_id is not None:
                    try:
                        _purge_user_from_all_chat_rooms(user_id)
                        deletion_log.append("Removed user from all chat rooms (and deleted their messages)")
                    except Exception as e:
                        deletion_log.append(f"Warning: chat-room purge failed: {e}")

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
                # FK enforcement is restored by the foreign_keys_off context
                # manager above, so no manual PRAGMA reset is needed here.
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
            conn = None
            try:
                status_label.config(
                    text=f"Deactivating student {student_id} …",
                    foreground="blue")
                dialog.update()
                conn = get_db_connection()
                if not conn:
                    raise sqlite3.OperationalError(
                        "Database connection failed during deactivation")
                cur = conn.cursor()
                cur.execute(
                    "UPDATE students SET is_active = 0, "
                    "status = 'Withdrawn' WHERE student_id = ?",
                    (student_id,),
                )
                if cur.rowcount == 0:
                    raise Exception(
                        f"No student with id {student_id} — already removed?")
                # Also flip the auth-side row so the student can no
                # longer sign in. Best-effort.
                try:
                    cur.execute(
                        "UPDATE users SET is_active = 0 "
                        "WHERE username = ?",
                        (str(student_id),),
                    )
                except Exception as e:
                    logger.debug("Auth deactivate skipped: %s", e)
                # Drop the withdrawn student out of their module chat rooms so
                # they no longer appear in active class chats. Keep their
                # messages (chat history) since deactivation is reversible.
                try:
                    urow = cur.execute(
                        "SELECT id FROM users WHERE username = ?",
                        (str(student_id),)).fetchone()
                    if urow:
                        removed, _ = purge_user_chat_on_cursor(
                            cur, urow[0], delete_messages=False)
                        if removed:
                            logger.info(
                                "Removed withdrawn student %s from %d chat "
                                "room(s)", student_id, removed)
                except Exception as e:
                    logger.debug(
                        "Chat membership removal on deactivate skipped: %s", e)
                conn.commit()
                if ACTIVITY_LOGGER_AVAILABLE:
                    try:
                        log_activity(
                            'deactivate', 'student',
                            user_id=getattr(getattr(self, 'auth', None),
                                              'current_user', {}).get('user_id'),
                            details={'student_id': student_id})
                    except Exception:
                        pass
                messagebox.showinfo(
                    "Student deactivated",
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
                    pass
                try:
                    if dialog.winfo_exists():
                        dialog.destroy()
                except tk.TclError:
                    pass
            except Exception as e:
                logger.exception("Deactivate failed for %s", student_id)
                messagebox.showerror(
                    "Deactivation failed", str(e))
                try:
                    status_label.config(
                        text="Deactivation failed.",
                        foreground="red")
                except tk.TclError:
                    pass
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Buttons. Deactivate (soft-delete) is the default and
        # safest action — keeps history, reversible. Permanent
        # delete is still available but framed clearly as the
        # destructive option.
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame,
                    text="Deactivate (recommended)",
                    command=perform_deactivation,
                    style="Accent.TButton").pack(side=tk.LEFT,
                                                    padx=(0, 10))
        ttk.Button(button_frame,
                    text="Delete permanently",
                    command=perform_deletion).pack(
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
