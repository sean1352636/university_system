"""Single and bulk fee assignment to students"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.i18n import get_text as _
from datetime import datetime

from education_system.university_system.infrastructure.database.db import get_connection


class FeeAssignmentMixin:
    """Fee assignment methods"""

    def assign_fee_to_student(self):
        """Assign fee to student"""
        # Simple fee assignment dialog using built-in dialogs
        student_id = simpledialog.askstring(_("expense_manager.buttons.assign_fee"), _("expense_manager.labels.student_id"))
        if student_id:
            fee_type = simpledialog.askstring(_("expense_manager.buttons.assign_fee"), _("expense_manager.labels.fee_type"))
            if fee_type:
                amount = simpledialog.askfloat(_("expense_manager.buttons.assign_fee"), _("expense_manager.labels.amount_pounds"))
                if amount:
                    due_date = simpledialog.askstring(_("expense_manager.buttons.assign_fee"), _("expense_manager.labels.due_date_format"),
                                                     initialvalue=datetime.now().strftime("%Y-%m-%d"))
                    if due_date:
                        try:
                            # Here you would save the fee assignment to database
                            messagebox.showinfo(_("common.success"), _("expense_manager.messages.fee_assigned", fee_type=fee_type, amount=amount, student_id=student_id))
                            self.refresh_fees()
                        except Exception as e:
                            messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_assign_fee", error=e))

    def gui_assign_fees_to_student(self):
        """GUI wrapper for assign_fees_to_student"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("expense_manager.dialogs.assign_fees_title"))
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        # Student selection
        ttk.Label(dialog, text=_("expense_manager.labels.student_id"), font=('Arial', 12)).pack(pady=10)
        student_id_var = tk.StringVar()
        student_entry = ttk.Entry(dialog, textvariable=student_id_var, font=('Arial', 12))
        student_entry.pack(pady=5)

        # Fee type selection
        ttk.Label(dialog, text=_("expense_manager.labels.fee_type"), font=('Arial', 12)).pack(pady=(20, 10))
        fee_type_var = tk.StringVar()
        fee_type_combo = ttk.Combobox(dialog, textvariable=fee_type_var, state='readonly', font=('Arial', 12))
        fee_type_combo.pack(pady=5)

        # Load fee types
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT fee_name FROM fee_types ORDER BY fee_name')
            fee_types = [row[0] for row in cursor.fetchall()]
            fee_type_combo['values'] = fee_types
        except sqlite3.Error as e:
            messagebox.showerror(_("common.error"), _("expense_manager.errors.database_error", error=e))
            dialog.destroy()
            return
        except Exception as e:
            messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_load_fee_types", error=e))
            dialog.destroy()
            return
        finally:
            if conn:
                conn.close()

        # Amount
        ttk.Label(dialog, text=_("expense_manager.labels.amount_pounds"), font=('Arial', 12)).pack(pady=(20, 10))
        amount_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=amount_var, font=('Arial', 12)).pack(pady=5)

        # Due date
        ttk.Label(dialog, text=_("expense_manager.labels.due_date_format"), font=('Arial', 12)).pack(pady=(20, 10))
        due_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(dialog, textvariable=due_date_var, font=('Arial', 12)).pack(pady=5)

        def assign_fee():
            conn = None
            try:
                # Validate inputs
                if not all([student_id_var.get(), fee_type_var.get(), amount_var.get(), due_date_var.get()]):
                    messagebox.showerror(_("common.error"), _("expense_manager.errors.all_fields_required"))
                    return

                student_id = student_id_var.get().strip()
                fee_type = fee_type_var.get()
                amount = float(amount_var.get())
                due_date = due_date_var.get().strip()

                # Call original function logic
                conn = get_connection()
                cursor = conn.cursor()

                # Check if student exists
                cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
                if cursor.fetchone()[0] == 0:
                    messagebox.showerror(_("common.error"), _("expense_manager.errors.student_not_found", student_id=student_id))
                    return

                # Get fee type ID
                cursor.execute('SELECT fee_type_id FROM fee_types WHERE fee_name = ?', (fee_type,))
                fee_type_result = cursor.fetchone()
                if not fee_type_result:
                    messagebox.showerror(_("common.error"), _("expense_manager.errors.fee_type_not_found"))
                    return

                fee_type_id = fee_type_result[0]

                # Create student fee
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''
                INSERT INTO student_fees
                (student_id, fee_type_id, amount, due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (student_id, fee_type_id, amount, due_date, now, now))

                fee_id = cursor.lastrowid
                conn.commit()

                # Auto-post AR + revenue to GL (no-op if ledger not initialised; never raises)
                try:
                    from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                    notify_ledger('fee_assignment', fee_id, posted_by='gui')
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "ledger hook failed for fee_assignment %s", fee_id,
                    )

                messagebox.showinfo(_("common.success"), _("expense_manager.messages.fee_assigned_success", fee_id=fee_id))
                dialog.destroy()
                self.update_status(_("expense_manager.status.fee_assigned_status", student_id=student_id))

            except ValueError:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.invalid_amount"))
            except sqlite3.Error as e:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.database_error", error=e))
                if conn:
                    conn.rollback()
            except Exception as e:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_assign_fee", error=e))
            finally:
                if conn:
                    conn.close()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text=_("expense_manager.buttons.assign_fee"), command=assign_fee).pack(side='left', padx=10)
        ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side='left', padx=10)

    def bulk_assign_fees(self):
        """Bulk assign fees to students"""
        if messagebox.askyesno(_("expense_manager.dialogs.bulk_assignment_title"), _("expense_manager.dialogs.confirm_bulk_assign")):
            try:
                # Call original function
                self.bulk_assign_fees_to_course()
                self.refresh_fees()
                self.update_status(_("expense_manager.status.bulk_assign_completed"))
            except Exception as e:
                messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_assign_fee", error=str(e)))

    def bulk_assign_fees_to_course(self):
        """Bulk assign fees to course with full functionality"""
        try:
            # Create bulk assignment dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_("expense_manager.dialogs.bulk_assignment_title"))
            dialog.geometry("600x550")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(main_frame, text=_("expense_manager.dialogs.bulk_assignment_header"),
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Form frame
            form_frame = ttk.LabelFrame(main_frame, text=_("expense_manager.labels.assignment_details"), padding=15)
            form_frame.pack(fill=tk.X, pady=(0, 20))

            # Course selection
            ttk.Label(form_frame, text=_("expense_manager.labels.course_code")).grid(row=0, column=0, sticky=tk.W, pady=10)
            course_var = tk.StringVar()

            # Get available courses
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT course_code FROM courses WHERE status = "active" ORDER BY course_code')
            courses = [row[0] for row in cursor.fetchall()]

            if not courses:
                courses = ['CS', 'DS', 'ENG', 'BUS']  # Fallback

            course_combo = ttk.Combobox(form_frame, textvariable=course_var, values=courses, state='readonly')
            course_combo.grid(row=0, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

            # Fee type
            ttk.Label(form_frame, text=_("expense_manager.labels.fee_type")).grid(row=1, column=0, sticky=tk.W, pady=10)
            fee_type_var = tk.StringVar()
            fee_types = ['Tuition', 'Library', 'Laboratory', 'Sports', 'Technology', 'Registration', 'Examination']
            fee_combo = ttk.Combobox(form_frame, textvariable=fee_type_var, values=fee_types, state='readonly')
            fee_combo.grid(row=1, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

            # Amount
            ttk.Label(form_frame, text=_("expense_manager.labels.amount_pounds")).grid(row=2, column=0, sticky=tk.W, pady=10)
            amount_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=amount_var).grid(row=2, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

            # Due date
            ttk.Label(form_frame, text=_("expense_manager.labels.due_date_format")).grid(row=3, column=0, sticky=tk.W, pady=10)
            due_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
            ttk.Entry(form_frame, textvariable=due_date_var).grid(row=3, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

            # Description
            ttk.Label(form_frame, text=_("common.description")).grid(row=4, column=0, sticky=tk.W, pady=10)
            desc_var = tk.StringVar()
            ttk.Entry(form_frame, textvariable=desc_var).grid(row=4, column=1, sticky=tk.EW, pady=10, padx=(10, 0))

            form_frame.columnconfigure(1, weight=1)

            # Preview frame
            preview_frame = ttk.LabelFrame(main_frame, text=_("expense_manager.labels.preview"), padding=10)
            preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

            preview_text = tk.Text(preview_frame, height=6, width=60, wrap=tk.WORD)
            preview_text.pack(fill=tk.BOTH, expand=True)
            preview_text.config(state='disabled')

            def update_preview(*args):
                """Update preview of students affected"""
                try:
                    course = course_var.get()
                    if course:
                        cursor.execute('''
                            SELECT COUNT(*) FROM students WHERE course = ? AND status = "Active"
                        ''', (course,))
                        count = cursor.fetchone()[0]
                        fee_type_display = fee_type_var.get() or _("common.not_selected")
                        preview_text.config(state='normal')
                        preview_text.delete('1.0', tk.END)
                        preview_text.insert('1.0',
                            f"{_('expense_manager.preview.course', course=course)}\n"
                            f"{_('expense_manager.preview.active_students', count=count)}\n"
                            f"{_('expense_manager.preview.fee_type', fee_type=fee_type_display)}\n"
                            f"{_('expense_manager.preview.amount_per_student', amount=amount_var.get() or '0.00')}\n"
                            f"{_('expense_manager.preview.total_fees', total=float(amount_var.get() or 0) * count)}")
                        preview_text.config(state='disabled')
                except Exception as e:
                    # Preview update failed (likely invalid input), silently ignore
                    print(f"Debug: Preview update failed: {e}")

            course_var.trace('w', update_preview)
            fee_type_var.trace('w', update_preview)
            amount_var.trace('w', update_preview)

            def assign_fees():
                """Perform bulk fee assignment"""
                try:
                    course = course_var.get()
                    fee_type = fee_type_var.get()
                    amount = amount_var.get()
                    due_date = due_date_var.get()
                    description = desc_var.get()

                    if not all([course, fee_type, amount, due_date]):
                        messagebox.showwarning(_("expense_manager.errors.missing_data"), _("expense_manager.errors.missing_data"))
                        return

                    amount_float = float(amount)
                    if amount_float <= 0:
                        messagebox.showwarning(_("expense_manager.errors.invalid_amount"), _("expense_manager.errors.amount_must_be_positive"))
                        return

                    # Get students in the course
                    cursor.execute('''
                        SELECT student_id FROM students WHERE course = ? AND status = "Active"
                    ''', (course,))
                    students = cursor.fetchall()

                    if not students:
                        messagebox.showinfo(_("common.info"), _("expense_manager.messages.no_students_in_course", course=course))
                        return

                    # Confirm before proceeding
                    if not messagebox.askyesno(_("common.confirm"),
                        _("expense_manager.dialogs.confirm_bulk_assign") + f"\n\u00a3{amount_float:.2f} {fee_type} \u2192 {len(students)} {_('common.students')} ({course})"):
                        return

                    # Assign fees
                    assigned_count = 0
                    current_date = datetime.now().strftime('%Y-%m-%d')

                    for student in students:
                        student_id = student[0]
                        cursor.execute('''
                            INSERT INTO student_fees (student_id, fee_type, amount, due_date, description, created_date)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (student_id, fee_type, amount_float, due_date, description, current_date))
                        assigned_count += 1

                    conn.commit()
                    conn.close()

                    messagebox.showinfo(_("common.success"),
                        _("expense_manager.messages.bulk_assign_success", amount=amount_float, fee_type=fee_type, count=assigned_count, course=course))

                    print(f"Bulk assigned {assigned_count} fees to course {course}")
                    dialog.destroy()

                except ValueError:
                    messagebox.showerror(_("expense_manager.errors.invalid_amount"), _("expense_manager.errors.invalid_amount"))
                except Exception as e:
                    messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_assign_fee", error=str(e)))
                    print(f"Error in bulk assignment: {e}")

            # Buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)

            ttk.Button(button_frame, text=_("expense_manager.buttons.assign_fees"), command=assign_fees).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text=_("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("expense_manager.errors.failed_open_dialog", error=str(e)))
            print(f"Error in bulk_assign_fees_to_course: {e}")
