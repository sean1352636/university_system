"""TA Assignment management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


class AssignmentManager:
    """Manages TA assignment UI including viewing, assigning, and removing TAs."""

    def __init__(self, parent, service, auth):
        self.parent = parent
        self.service = service
        self.auth = auth
        self._setup_ui()
        self._refresh_tas()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the assignment management panel."""
        # Top button bar
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        role = ''
        if self.auth and self.auth.current_user:
            role = self.auth.current_user.get('role', '')
        is_manager = role in ('admin', 'instructor')

        if is_manager:
            ttk.Button(btn_frame, text="Assign TA", command=self._assign_ta).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Remove TA", command=self._remove_ta).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="View Workload", command=self._view_workload).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh_tas).pack(side=tk.RIGHT, padx=5)

        # Filter bar
        filter_frame = ttk.Frame(self.parent)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        ttk.Label(filter_frame, text="Filter by Module:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=20)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(filter_frame, text="Filter", command=self._apply_filter).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text="Clear", command=self._clear_filter).pack(side=tk.LEFT, padx=5)

        # Treeview for TA list
        tree_frame = ttk.Frame(self.parent)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('id', 'student_id', 'module_code', 'role_type', 'hours_per_week', 'status')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', selectmode='browse')

        col_config = {
            'id': ('ID', 50),
            'student_id': ('Student ID', 130),
            'module_code': ('Module', 130),
            'role_type': ('Role', 100),
            'hours_per_week': ('Hours/Week', 100),
            'status': ('Status', 90),
        }
        for col, (heading, width) in col_config.items():
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, minwidth=50)

        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')

        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.parent, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, padx=10, pady=(0, 10))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _refresh_tas(self, module_filter=None):
        """Reload TA list from the service."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            if module_filter:
                tas = self.service.get_tas_for_module(module_filter)
            else:
                tas = self.service.get_all_tas(status='active')

            for ta in tas:
                self.tree.insert('', tk.END, values=(
                    ta.get('id', ''),
                    ta.get('student_id', ''),
                    ta.get('module_code', ''),
                    ta.get('role_type', ''),
                    ta.get('hours_per_week', ''),
                    ta.get('status', ''),
                ))

            count = len(tas)
            suffix = f" for module '{module_filter}'" if module_filter else ""
            self.status_var.set(f"Loaded {count} TA assignment(s){suffix}")
        except Exception as e:
            logger.error(f"Error refreshing TA list: {e}")
            self.status_var.set(f"Error loading TAs: {e}")
            messagebox.showerror("Error", f"Failed to load TA assignments:\n{e}")

    def _apply_filter(self):
        """Apply the module filter."""
        module_code = self.filter_var.get().strip()
        if module_code:
            self._refresh_tas(module_filter=module_code)
        else:
            self._refresh_tas()

    def _clear_filter(self):
        """Clear the module filter and reload all TAs."""
        self.filter_var.set('')
        self._refresh_tas()

    def _assign_ta(self):
        """Open a dialog to assign a new TA."""
        # Fetch students for dropdown
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT student_id, first_name, last_name FROM students "
                "ORDER BY last_name, first_name"
            )
            students = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.error("Error fetching students: %s", e)
            students = []

        if not students:
            messagebox.showwarning("No Students", "No students found in the database.")
            return

        student_map = {}
        student_values = []
        for s in students:
            display = f"{s['student_id']} - {s['first_name']} {s['last_name']}"
            student_values.append(display)
            student_map[display] = s['student_id']

        # Fetch modules for dropdown
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT module_code, module_name FROM modules ORDER BY module_code"
            )
            modules = cursor.fetchall()
            conn.close()
        except Exception as e:
            logger.error("Error fetching modules: %s", e)
            modules = []

        if not modules:
            messagebox.showwarning("No Modules", "No modules found in the database.")
            return

        module_map = {}
        module_values = []
        for m in modules:
            display = f"{m['module_code']} - {m['module_name']}"
            module_values.append(display)
            module_map[display] = m['module_code']

        dialog = tk.Toplevel(self.parent)
        dialog.title("Assign Teaching Assistant")
        dialog.geometry("420x320")
        dialog.transient(self.parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Student
        ttk.Label(main_frame, text="Student:").grid(row=0, column=0, sticky=tk.W, pady=5)
        student_var = tk.StringVar()
        ttk.Combobox(
            main_frame, textvariable=student_var, values=student_values,
            state='readonly', width=35,
        ).grid(row=0, column=1, pady=5, padx=(10, 0))

        # Module
        ttk.Label(main_frame, text="Module:").grid(row=1, column=0, sticky=tk.W, pady=5)
        module_var = tk.StringVar()
        ttk.Combobox(
            main_frame, textvariable=module_var, values=module_values,
            state='readonly', width=35,
        ).grid(row=1, column=1, pady=5, padx=(10, 0))

        # Role Type
        ttk.Label(main_frame, text="Role Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        role_var = tk.StringVar(value='ta')
        role_combo = ttk.Combobox(
            main_frame, textvariable=role_var, values=['ta', 'lead_ta', 'grader'],
            state='readonly', width=27,
        )
        role_combo.grid(row=2, column=1, pady=5, padx=(10, 0))

        # Hours per Week
        ttk.Label(main_frame, text="Hours/Week:").grid(row=3, column=0, sticky=tk.W, pady=5)
        hours_var = tk.StringVar(value='10')
        ttk.Entry(main_frame, textvariable=hours_var, width=30).grid(row=3, column=1, pady=5, padx=(10, 0))

        def _do_assign():
            student_selection = student_var.get().strip()
            module_selection = module_var.get().strip()
            role_type = role_var.get().strip()
            hours_str = hours_var.get().strip()

            if not student_selection:
                messagebox.showwarning("Validation", "Please select a student.", parent=dialog)
                return
            if not module_selection:
                messagebox.showwarning("Validation", "Please select a module.", parent=dialog)
                return

            student_id = student_map.get(student_selection, '')
            module_code = module_map.get(module_selection, '')

            try:
                hours_per_week = float(hours_str)
                if hours_per_week <= 0:
                    raise ValueError("Hours must be positive")
            except ValueError:
                messagebox.showwarning("Validation", "Hours/Week must be a positive number.", parent=dialog)
                return

            instructor_id = ''
            if self.auth and self.auth.current_user:
                instructor_id = self.auth.current_user.get('username', '')

            try:
                ta_id = self.service.assign_ta(
                    student_id=student_id,
                    instructor_id=instructor_id,
                    module_code=module_code,
                    role_type=role_type,
                    hours_per_week=hours_per_week,
                )
                messagebox.showinfo("Success", f"TA assigned successfully.\nAssignment ID: {ta_id}", parent=dialog)
                dialog.destroy()
                self._refresh_tas()

                # Email student about TA assignment
                self._send_ta_email(student_id, module_code, role_type, hours_per_week, 'assigned')
            except ValueError as e:
                messagebox.showerror("Validation Error", str(e), parent=dialog)
            except Exception as e:
                logger.error(f"Error assigning TA: {e}")
                if "UNIQUE constraint" in str(e):
                    messagebox.showerror(
                        "Duplicate",
                        f"Student '{student_id}' is already a TA for module '{module_code}'.",
                        parent=dialog,
                    )
                else:
                    messagebox.showerror("Error", f"Failed to assign TA:\n{e}", parent=dialog)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(20, 0))

        ttk.Button(btn_frame, text="Assign", command=_do_assign).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    def _remove_ta(self):
        """Remove the selected TA assignment after confirmation."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a TA assignment to remove.")
            return

        values = self.tree.item(selection[0], 'values')
        ta_id = values[0]
        student_id = values[1]
        module_code = values[2]

        confirm = messagebox.askyesno(
            "Confirm Removal",
            f"Are you sure you want to remove TA assignment?\n\n"
            f"  ID:         {ta_id}\n"
            f"  Student:    {student_id}\n"
            f"  Module:     {module_code}\n\n"
            f"This will deactivate the assignment.",
        )
        if not confirm:
            return

        try:
            success = self.service.remove_ta(int(ta_id))
            if success:
                messagebox.showinfo("Success", f"TA assignment {ta_id} has been deactivated.")
                self._refresh_tas()

                # Email student about TA removal
                self._send_ta_email(student_id, module_code, '', 0, 'removed')
            else:
                messagebox.showwarning(
                    "Not Found",
                    f"TA assignment {ta_id} was not found or is already inactive.",
                )
        except Exception as e:
            logger.error(f"Error removing TA: {e}")
            messagebox.showerror("Error", f"Failed to remove TA:\n{e}")

    def _view_workload(self):
        """Show workload details for the selected TA's student."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a TA to view their workload.")
            return

        values = self.tree.item(selection[0], 'values')
        student_id = values[1]

        try:
            workload = self.service.get_ta_workload(student_id)
        except Exception as e:
            logger.error(f"Error fetching workload: {e}")
            messagebox.showerror("Error", f"Failed to load workload:\n{e}")
            return

        total_hours = workload.get('total_hours', 0)
        count = workload.get('assignment_count', 0)
        assignments = workload.get('assignments', [])

        dialog = tk.Toplevel(self.parent)
        dialog.title(f"TA Workload - {student_id}")
        dialog.geometry("600x400")
        dialog.transient(self.parent)

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Summary
        summary_frame = ttk.LabelFrame(main_frame, text="Workload Summary", padding=10)
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(summary_frame, text=f"Student ID: {student_id}", font=('Arial', 11)).pack(anchor=tk.W)
        ttk.Label(summary_frame, text=f"Active Assignments: {count}", font=('Arial', 11)).pack(anchor=tk.W)

        hours_text = f"Total Hours/Week: {total_hours}"
        hours_label = ttk.Label(summary_frame, text=hours_text, font=('Arial', 11))
        hours_label.pack(anchor=tk.W)

        if total_hours > 20:
            warning = ttk.Label(
                summary_frame,
                text="WARNING: Student exceeds 20 hours/week across TA assignments.",
                foreground='red',
                font=('Arial', 10, 'bold'),
            )
            warning.pack(anchor=tk.W, pady=(5, 0))

        # Detail table
        if assignments:
            detail_frame = ttk.LabelFrame(main_frame, text="Assignment Details", padding=5)
            detail_frame.pack(fill=tk.BOTH, expand=True)

            columns = ('module_code', 'role_type', 'hours_per_week', 'start_date')
            detail_tree = ttk.Treeview(detail_frame, columns=columns, show='headings', height=8)

            detail_tree.heading('module_code', text='Module')
            detail_tree.heading('role_type', text='Role')
            detail_tree.heading('hours_per_week', text='Hours/Week')
            detail_tree.heading('start_date', text='Start Date')

            detail_tree.column('module_code', width=120)
            detail_tree.column('role_type', width=100)
            detail_tree.column('hours_per_week', width=100)
            detail_tree.column('start_date', width=160)

            for a in assignments:
                detail_tree.insert('', tk.END, values=(
                    a.get('module_code', ''),
                    a.get('role_type', ''),
                    a.get('hours_per_week', ''),
                    a.get('start_date', ''),
                ))

            scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=detail_tree.yview)
            detail_tree.configure(yscrollcommand=scrollbar.set)

            detail_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=(10, 0))

    def _send_ta_email(self, student_id, module_code, role_type, hours_per_week, action):
        """Email student about TA assignment or removal."""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            conn = get_connection()
            cursor = conn.cursor()

            # Get student email
            cursor.execute(
                "SELECT first_name, last_name, email_address FROM students WHERE student_id = ?",
                (student_id,)
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    "SELECT first_name, last_name, email FROM users WHERE username = ? OR id = ?",
                    (student_id, student_id)
                )
                row = cursor.fetchone()
            conn.close()

            if not row or not row[2]:
                return

            name = f"{row[0]} {row[1]}"
            email = row[2]

            if action == 'assigned':
                subject = f"TA Assignment: {module_code}"
                body = (
                    f"Dear {name},\n\n"
                    f"You have been assigned as a Teaching Assistant:\n\n"
                    f"Module: {module_code}\n"
                    f"Role: {role_type}\n"
                    f"Hours per Week: {hours_per_week}\n\n"
                    f"Please contact the module instructor for further details "
                    f"about your responsibilities and schedule.\n\n"
                    f"Best regards,\nAcademic Administration"
                )
            elif action == 'removed':
                subject = f"TA Assignment Removed: {module_code}"
                body = (
                    f"Dear {name},\n\n"
                    f"Your Teaching Assistant assignment has been removed:\n\n"
                    f"Module: {module_code}\n\n"
                    f"If you believe this is an error, please contact the "
                    f"module instructor or academic administration.\n\n"
                    f"Best regards,\nAcademic Administration"
                )
            else:
                return

            send_email(recipient_email=email, subject=subject, body=body)

        except Exception as e:
            logger.warning(f"Failed to send TA email: {e}")
