"""
Substitute/Cover Arrangements GUI

Provides interface for:
- Cover request management
- Volunteering for cover
- Assignment tracking
- Cover pool administration
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.cover_manager import CoverManager
from education_system.university_system.modules.domain.staff_comms.staff_hr.gui.validators import (
    FormValidator, ValidationError, validate_entry, validate_date_entry,
    validate_combobox, show_validation_error
)


class CoverGUI:
    """GUI for substitute/cover arrangements."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.parent_notebook = parent_notebook
        self.window = None

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Cover Management")
            return

        if parent_notebook:
            self.create_as_tab(parent_notebook)
        else:
            self.create_main_window()

    def _get_user_id(self):
        return self.current_user.get('id') or self.current_user.get('username')

    def create_as_tab(self, notebook: ttk.Notebook):
        self.tab_frame = ttk.Frame(notebook)
        notebook.add(self.tab_frame, text="Cover")
        self._build_interface(self.tab_frame)

    def create_main_window(self):
        self.window = tk.Toplevel(self.root)
        self.window.title("Substitute/Cover Arrangements")
        self.window.geometry("1200x700")
        self.window.minsize(1000, 600)
        bottom_frame = ttk.Frame(self.window)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        self.status_bar = ttk.Label(self.window, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self._build_interface(self.window)

    def _build_interface(self, parent):
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._create_my_requests_tab()
        self._create_find_cover_tab()
        self._create_my_assignments_tab()

        if self.current_user.get('role') in ['admin', 'Admin', 'administrator', 'staff']:
            self._create_cover_pool_tab()
            self._create_reports_tab()

    # ================================================================
    # Tab 1 - My Cover Requests
    # ================================================================

    def _create_my_requests_tab(self):
        """Create the My Cover Requests tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Requests")

        # --- Top section: Create Request form ---
        form_frame = ttk.LabelFrame(tab, text="Create Cover Request", padding=10)
        form_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        # Row 1: Type, Course Code, Course Name
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=tk.X, pady=3)

        ttk.Label(row1, text="Type:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.req_type_combo = ttk.Combobox(
            row1, values=['teaching', 'lab', 'tutorial', 'supervision'],
            width=14, state='readonly'
        )
        self.req_type_combo.set('teaching')
        self.req_type_combo.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row1, text="Course Code:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.req_course_code = ttk.Entry(row1, width=14)
        self.req_course_code.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row1, text="Course Name:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.req_course_name = ttk.Entry(row1, width=20)
        self.req_course_name.pack(side=tk.LEFT)

        # Row 2: Date, Start Time, End Time, Location
        row2 = ttk.Frame(form_frame)
        row2.pack(fill=tk.X, pady=3)

        ttk.Label(row2, text="Date:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.req_date = ttk.Entry(row2, width=14)
        self.req_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.req_date.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row2, text="Start Time:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.req_start_time = ttk.Entry(row2, width=14)
        self.req_start_time.insert(0, "09:00")
        self.req_start_time.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row2, text="End Time:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.req_end_time = ttk.Entry(row2, width=14)
        self.req_end_time.insert(0, "10:00")
        self.req_end_time.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row2, text="Location:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))
        self.req_location = ttk.Entry(row2, width=20)
        self.req_location.pack(side=tk.LEFT)

        # Row 3: Reason + Urgency
        row3 = ttk.Frame(form_frame)
        row3.pack(fill=tk.X, pady=3)

        ttk.Label(row3, text="Reason:", width=12, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5), anchor=tk.N)
        self.req_reason = tk.Text(row3, height=3, width=50)
        self.req_reason.pack(side=tk.LEFT, padx=(0, 15))

        urgency_frame = ttk.Frame(row3)
        urgency_frame.pack(side=tk.LEFT, anchor=tk.N)
        ttk.Label(urgency_frame, text="Urgency:", width=12, anchor=tk.W).pack(anchor=tk.W)
        self.req_urgency_combo = ttk.Combobox(
            urgency_frame, values=['low', 'normal', 'high', 'urgent'],
            width=12, state='readonly'
        )
        self.req_urgency_combo.set('normal')
        self.req_urgency_combo.pack(anchor=tk.W, pady=(3, 0))

        # Row 4: Submit button
        row4 = ttk.Frame(form_frame)
        row4.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(row4, text="Create Request", command=self._create_request).pack(side=tk.RIGHT, padx=5)

        # --- Bottom section: Requests Treeview ---
        tree_header = ttk.Frame(tab)
        tree_header.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(tree_header, text="My Cover Requests", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(tree_header, text="Refresh", command=self._load_my_requests).pack(side=tk.RIGHT, padx=5)
        ttk.Button(tree_header, text="Cancel Selected", command=self._cancel_selected_request).pack(side=tk.RIGHT, padx=5)

        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        columns = ('ID', 'Type', 'Course', 'Date', 'Time', 'Urgency', 'Status')
        self.my_requests_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )
        y_scroll.config(command=self.my_requests_tree.yview)
        x_scroll.config(command=self.my_requests_tree.xview)

        col_widths = {'ID': 50, 'Type': 100, 'Course': 150, 'Date': 100,
                      'Time': 120, 'Urgency': 80, 'Status': 90}
        for col in columns:
            self.my_requests_tree.heading(col, text=col)
            self.my_requests_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.my_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Status colour tags
        self.my_requests_tree.tag_configure('open', background='#fff3cd')
        self.my_requests_tree.tag_configure('assigned', background='#cce5ff')
        self.my_requests_tree.tag_configure('completed', background='#d4edda')
        self.my_requests_tree.tag_configure('cancelled', background='#e2e3e5')

        self._load_my_requests()

    def _create_request(self):
        """Validate form and create a new cover request."""
        try:
            validator = FormValidator()
            validator.add_combobox(self.req_type_combo, "Cover Type", key='request_type')
            validator.add_date(self.req_date, "Date", key='cover_date')
            validator.add_required(self.req_start_time, "Start Time", key='start_time')
            validator.add_required(self.req_end_time, "End Time", key='end_time')

            if not validator.validate():
                return

            vals = validator.get_values()

            course_code = self.req_course_code.get().strip() or None
            course_name = self.req_course_name.get().strip() or None
            location = self.req_location.get().strip() or None
            reason = self.req_reason.get("1.0", "end-1c").strip() or None
            urgency = self.req_urgency_combo.get() or 'normal'

            request_id = CoverManager.create_request(
                requester_id=self._get_user_id(),
                cover_date=vals['cover_date'],
                start_time=vals['start_time'],
                end_time=vals['end_time'],
                request_type=vals['request_type'],
                course_code=course_code,
                course_name=course_name,
                location=location,
                reason=reason,
                urgency=urgency,
            )

            messagebox.showinfo("Success", f"Cover request #{request_id} created successfully.")
            self._clear_request_form()
            self._load_my_requests()

        except ValidationError as e:
            show_validation_error(e)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create request: {e}")

    def _clear_request_form(self):
        """Reset the create-request form to defaults."""
        self.req_type_combo.set('teaching')
        self.req_course_code.delete(0, tk.END)
        self.req_course_name.delete(0, tk.END)
        self.req_date.delete(0, tk.END)
        self.req_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.req_start_time.delete(0, tk.END)
        self.req_start_time.insert(0, "09:00")
        self.req_end_time.delete(0, tk.END)
        self.req_end_time.insert(0, "10:00")
        self.req_location.delete(0, tk.END)
        self.req_reason.delete("1.0", tk.END)
        self.req_urgency_combo.set('normal')

    def _load_my_requests(self):
        """Load current user's cover requests into the treeview."""
        try:
            self.my_requests_tree.delete(*self.my_requests_tree.get_children())

            requests = CoverManager.get_user_requests(self._get_user_id())

            for req in requests:
                time_str = f"{req.get('start_time', '')} - {req.get('end_time', '')}"
                course = req.get('course_code') or req.get('course_name') or ''
                status = req.get('status', 'open')
                values = (
                    req.get('request_id', ''),
                    req.get('request_type', ''),
                    course,
                    req.get('cover_date', ''),
                    time_str,
                    req.get('urgency', 'normal'),
                    status.capitalize(),
                )
                self.my_requests_tree.insert('', 'end', values=values, tags=(status,))

            self._update_status(f"Loaded {len(requests)} request(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load requests: {e}")

    def _cancel_selected_request(self):
        """Cancel the selected cover request."""
        selection = self.my_requests_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a request to cancel.")
            return

        item = self.my_requests_tree.item(selection[0])
        request_id = item['values'][0]
        status = item['values'][6].lower() if len(item['values']) > 6 else ''

        if status not in ('open',):
            messagebox.showwarning("Warning", "Only open requests can be cancelled.")
            return

        if not messagebox.askyesno("Confirm", f"Cancel cover request #{request_id}?"):
            return

        try:
            CoverManager.cancel_request(int(request_id))
            messagebox.showinfo("Success", "Request cancelled successfully.")
            self._load_my_requests()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to cancel request: {e}")

    # ================================================================
    # Tab 2 - Find Cover (volunteer for open requests)
    # ================================================================

    def _create_find_cover_tab(self):
        """Create the Find Cover tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Find Cover")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Open Cover Requests", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_open_requests).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="Volunteer", command=self._volunteer_for_cover).pack(side=tk.RIGHT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        columns = ('ID', 'Requester', 'Type', 'Course', 'Date', 'Time', 'Location', 'Urgency')
        self.open_requests_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )
        y_scroll.config(command=self.open_requests_tree.yview)
        x_scroll.config(command=self.open_requests_tree.xview)

        col_widths = {'ID': 50, 'Requester': 120, 'Type': 90, 'Course': 140,
                      'Date': 100, 'Time': 120, 'Location': 120, 'Urgency': 80}
        for col in columns:
            self.open_requests_tree.heading(col, text=col)
            self.open_requests_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.open_requests_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Urgency colour tags
        self.open_requests_tree.tag_configure('urgent', background='#f8d7da')
        self.open_requests_tree.tag_configure('high', background='#ffe0b2')
        self.open_requests_tree.tag_configure('normal', background='white')
        self.open_requests_tree.tag_configure('low', background='#e2e3e5')

        self._load_open_requests()

    def _load_open_requests(self):
        """Load all open cover requests into the treeview."""
        try:
            self.open_requests_tree.delete(*self.open_requests_tree.get_children())

            requests = CoverManager.get_open_requests()

            for req in requests:
                time_str = f"{req.get('start_time', '')} - {req.get('end_time', '')}"
                course = req.get('course_code') or req.get('course_name') or ''
                urgency = req.get('urgency', 'normal')
                values = (
                    req.get('request_id', ''),
                    req.get('requester_id', ''),
                    req.get('request_type', ''),
                    course,
                    req.get('cover_date', ''),
                    time_str,
                    req.get('location', '') or '',
                    urgency,
                )
                self.open_requests_tree.insert('', 'end', values=values, tags=(urgency,))

            self._update_status(f"Found {len(requests)} open request(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load open requests: {e}")

    def _volunteer_for_cover(self):
        """Volunteer for the selected open cover request."""
        selection = self.open_requests_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a request to volunteer for.")
            return

        item = self.open_requests_tree.item(selection[0])
        request_id = item['values'][0]
        requester = item['values'][1]

        # Prevent self-volunteering
        if str(requester) == str(self._get_user_id()):
            messagebox.showwarning("Warning", "You cannot volunteer for your own request.")
            return

        # Optional message dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Volunteer Message")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=f"Volunteering for request #{request_id}",
            font=('Arial', 11, 'bold')
        ).pack(pady=(0, 10))

        ttk.Label(main_frame, text="Message (optional):").pack(anchor=tk.W)
        message_text = tk.Text(main_frame, height=4, width=45)
        message_text.pack(fill=tk.X, pady=5)

        def submit_volunteer():
            msg = message_text.get("1.0", "end-1c").strip() or None
            try:
                CoverManager.volunteer(
                    request_id=int(request_id),
                    volunteer_id=self._get_user_id(),
                    message=msg,
                )
                messagebox.showinfo("Success", f"You have volunteered for request #{request_id}.")
                dialog.destroy()
                self._load_open_requests()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to volunteer: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Submit", command=submit_volunteer).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    # ================================================================
    # Tab 3 - My Assignments
    # ================================================================

    def _create_my_assignments_tab(self):
        """Create the My Assignments tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="My Assignments")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="My Cover Assignments", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_my_assignments).pack(side=tk.RIGHT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)

        columns = ('ID', 'Course', 'Date', 'Time', 'Location', 'Accepted', 'Completed')
        self.assignments_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings',
            yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set
        )
        y_scroll.config(command=self.assignments_tree.yview)
        x_scroll.config(command=self.assignments_tree.xview)

        col_widths = {'ID': 50, 'Course': 150, 'Date': 100, 'Time': 120,
                      'Location': 120, 'Accepted': 80, 'Completed': 80}
        for col in columns:
            self.assignments_tree.heading(col, text=col)
            self.assignments_tree.column(col, width=col_widths.get(col, 100), anchor=tk.CENTER)

        self.assignments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Action buttons
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Accept", command=self._accept_assignment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Decline", command=self._decline_assignment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Complete", command=self._complete_assignment).pack(side=tk.LEFT, padx=5)

        self._load_my_assignments()

    def _load_my_assignments(self):
        """Load cover assignments for the current user from the database."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection

            self.assignments_tree.delete(*self.assignments_tree.get_children())

            user_id = self._get_user_id()

            with get_connection() as conn:
                rows = conn.execute('''
                    SELECT ca.assignment_id, cr.course_code, cr.course_name,
                           cr.cover_date, cr.start_time, cr.end_time,
                           cr.location, ca.accepted, ca.completed
                    FROM cover_assignments ca
                    JOIN cover_requests cr ON ca.request_id = cr.request_id
                    WHERE ca.assignee_id = ?
                    ORDER BY cr.cover_date DESC
                ''', (user_id,)).fetchall()

            for row in rows:
                course = row['course_code'] or row['course_name'] or ''
                time_str = f"{row['start_time']} - {row['end_time']}"
                accepted = 'Yes' if row['accepted'] else 'No'
                completed = 'Yes' if row['completed'] else 'No'
                values = (
                    row['assignment_id'],
                    course,
                    row['cover_date'],
                    time_str,
                    row['location'] or '',
                    accepted,
                    completed,
                )
                self.assignments_tree.insert('', 'end', values=values)

            self._update_status(f"Loaded {len(rows)} assignment(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")

    def _get_selected_assignment_id(self):
        """Return the assignment_id from the selected treeview row, or None."""
        selection = self.assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment.")
            return None
        item = self.assignments_tree.item(selection[0])
        return item['values'][0]

    def _accept_assignment(self):
        """Accept the selected cover assignment."""
        assignment_id = self._get_selected_assignment_id()
        if assignment_id is None:
            return

        if not messagebox.askyesno("Confirm", f"Accept assignment #{assignment_id}?"):
            return

        try:
            CoverManager.accept_assignment(int(assignment_id))
            messagebox.showinfo("Success", "Assignment accepted.")
            self._load_my_assignments()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to accept assignment: {e}")

    def _decline_assignment(self):
        """Decline the selected cover assignment."""
        assignment_id = self._get_selected_assignment_id()
        if assignment_id is None:
            return

        if not messagebox.askyesno("Confirm", f"Decline assignment #{assignment_id}? This will reopen the request."):
            return

        try:
            CoverManager.decline_assignment(int(assignment_id))
            messagebox.showinfo("Success", "Assignment declined. The request has been reopened.")
            self._load_my_assignments()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to decline assignment: {e}")

    def _complete_assignment(self):
        """Complete the selected cover assignment with optional feedback."""
        assignment_id = self._get_selected_assignment_id()
        if assignment_id is None:
            return

        # Check the assignment is accepted and not already completed
        selection = self.assignments_tree.selection()
        item = self.assignments_tree.item(selection[0])
        accepted = item['values'][5]
        completed = item['values'][6]

        if str(completed) == 'Yes':
            messagebox.showwarning("Warning", "This assignment is already completed.")
            return

        if str(accepted) != 'Yes':
            messagebox.showwarning("Warning", "Please accept the assignment before completing it.")
            return

        # Feedback dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Complete Assignment")
        dialog.geometry("420x280")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=f"Complete Assignment #{assignment_id}",
            font=('Arial', 11, 'bold')
        ).pack(pady=(0, 10))

        ttk.Label(main_frame, text="Feedback (optional):").pack(anchor=tk.W)
        feedback_text = tk.Text(main_frame, height=5, width=45)
        feedback_text.pack(fill=tk.X, pady=5)

        rating_frame = ttk.Frame(main_frame)
        rating_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rating_frame, text="Rating (1-5, optional):").pack(side=tk.LEFT)
        rating_entry = ttk.Entry(rating_frame, width=5)
        rating_entry.pack(side=tk.LEFT, padx=10)

        def submit_completion():
            feedback = feedback_text.get("1.0", "end-1c").strip() or None
            rating_str = rating_entry.get().strip()
            rating = None

            if rating_str:
                try:
                    rating = int(rating_str)
                    if rating < 1 or rating > 5:
                        messagebox.showwarning("Warning", "Rating must be between 1 and 5.")
                        return
                except ValueError:
                    messagebox.showwarning("Warning", "Rating must be a number between 1 and 5.")
                    return

            try:
                CoverManager.complete_assignment(
                    assignment_id=int(assignment_id),
                    feedback=feedback,
                    rating=rating,
                )
                messagebox.showinfo("Success", "Assignment marked as completed.")
                dialog.destroy()
                self._load_my_assignments()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to complete assignment: {e}")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Complete", command=submit_completion).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=10)

    # ================================================================
    # Tab 4 - Cover Pool (admin only)
    # ================================================================

    def _create_cover_pool_tab(self):
        """Create the Cover Pool administration tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Cover Pool")

        # --- Top section: Staff qualifications viewer ---
        qual_frame = ttk.LabelFrame(tab, text="Staff Qualifications", padding=10)
        qual_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        # Search bar
        search_row = ttk.Frame(qual_frame)
        search_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_row, text="User ID:").pack(side=tk.LEFT, padx=(0, 5))
        self.pool_user_id_entry = ttk.Entry(search_row, width=20)
        self.pool_user_id_entry.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(
            search_row, text="View Qualifications",
            command=self._view_staff_qualifications
        ).pack(side=tk.LEFT, padx=5)

        # Qualifications treeview
        qual_tree_frame = ttk.Frame(qual_frame)
        qual_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 5))

        ttk.Label(qual_tree_frame, text="Qualifications:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        qual_inner = ttk.Frame(qual_tree_frame)
        qual_inner.pack(fill=tk.BOTH, expand=True)

        q_scroll = ttk.Scrollbar(qual_inner, orient=tk.VERTICAL)
        qual_cols = ('ID', 'Subject', 'Course Code', 'Level')
        self.quals_tree = ttk.Treeview(
            qual_inner, columns=qual_cols, show='headings', height=5,
            yscrollcommand=q_scroll.set
        )
        q_scroll.config(command=self.quals_tree.yview)

        q_widths = {'ID': 50, 'Subject': 200, 'Course Code': 150, 'Level': 120}
        for col in qual_cols:
            self.quals_tree.heading(col, text=col)
            self.quals_tree.column(col, width=q_widths.get(col, 100), anchor=tk.CENTER)

        self.quals_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        q_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Skills treeview
        skills_tree_frame = ttk.Frame(qual_frame)
        skills_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        ttk.Label(skills_tree_frame, text="Skills:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        skills_inner = ttk.Frame(skills_tree_frame)
        skills_inner.pack(fill=tk.BOTH, expand=True)

        s_scroll = ttk.Scrollbar(skills_inner, orient=tk.VERTICAL)
        skill_cols = ('ID', 'Skill', 'Category', 'Proficiency')
        self.skills_tree = ttk.Treeview(
            skills_inner, columns=skill_cols, show='headings', height=5,
            yscrollcommand=s_scroll.set
        )
        s_scroll.config(command=self.skills_tree.yview)

        s_widths = {'ID': 50, 'Skill': 200, 'Category': 150, 'Proficiency': 120}
        for col in skill_cols:
            self.skills_tree.heading(col, text=col)
            self.skills_tree.column(col, width=s_widths.get(col, 100), anchor=tk.CENTER)

        self.skills_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        s_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Bottom section: Manual assignment ---
        assign_frame = ttk.LabelFrame(tab, text="Manual Assignment", padding=10)
        assign_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        assign_row = ttk.Frame(assign_frame)
        assign_row.pack(fill=tk.X)

        ttk.Label(assign_row, text="Request ID:").pack(side=tk.LEFT, padx=(0, 5))
        self.assign_request_id_entry = ttk.Entry(assign_row, width=10)
        self.assign_request_id_entry.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(assign_row, text="Assignee ID:").pack(side=tk.LEFT, padx=(0, 5))
        self.assign_assignee_id_entry = ttk.Entry(assign_row, width=20)
        self.assign_assignee_id_entry.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Button(assign_row, text="Assign", command=self._manual_assign).pack(side=tk.LEFT, padx=5)

    def _view_staff_qualifications(self):
        """Load qualifications and skills for the entered user ID."""
        user_id = self.pool_user_id_entry.get().strip()
        if not user_id:
            messagebox.showwarning("Warning", "Please enter a User ID.")
            return

        # Clear existing
        self.quals_tree.delete(*self.quals_tree.get_children())
        self.skills_tree.delete(*self.skills_tree.get_children())

        try:
            qualifications = CoverManager.get_qualifications(user_id)
            for q in qualifications:
                values = (
                    q.get('qualification_id', ''),
                    q.get('subject_area', ''),
                    q.get('course_code', '') or '',
                    q.get('qualification_level', ''),
                )
                self.quals_tree.insert('', 'end', values=values)

            skills = CoverManager.get_skills(user_id)
            for s in skills:
                values = (
                    s.get('skill_id', ''),
                    s.get('skill_name', ''),
                    s.get('category', ''),
                    s.get('proficiency', ''),
                )
                self.skills_tree.insert('', 'end', values=values)

            self._update_status(
                f"User {user_id}: {len(qualifications)} qualification(s), {len(skills)} skill(s)"
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load qualifications: {e}")

    def _manual_assign(self):
        """Manually assign a cover request to a staff member."""
        request_id_str = self.assign_request_id_entry.get().strip()
        assignee_id = self.assign_assignee_id_entry.get().strip()

        if not request_id_str:
            messagebox.showwarning("Warning", "Please enter a Request ID.")
            return
        if not assignee_id:
            messagebox.showwarning("Warning", "Please enter an Assignee ID.")
            return

        try:
            request_id = int(request_id_str)
        except ValueError:
            messagebox.showwarning("Warning", "Request ID must be a number.")
            return

        if not messagebox.askyesno(
            "Confirm",
            f"Assign request #{request_id} to user '{assignee_id}'?"
        ):
            return

        try:
            assigned_by = self._get_user_id()
            assignment_id = CoverManager.assign_cover(
                request_id=request_id,
                assignee_id=assignee_id,
                assigned_by=assigned_by,
            )
            messagebox.showinfo(
                "Success",
                f"Assignment #{assignment_id} created. Request #{request_id} assigned to {assignee_id}."
            )
            self.assign_request_id_entry.delete(0, tk.END)
            self.assign_assignee_id_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign cover: {e}")

    # ================================================================
    # Tab 5 - Reports (admin only)
    # ================================================================

    def _create_reports_tab(self):
        """Create the Reports tab with statistics overview."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Reports")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(header_frame, text="Cover Statistics", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self._load_reports).pack(side=tk.RIGHT, padx=5)

        # Summary statistics
        self.stats_frame = ttk.LabelFrame(tab, text="Overview", padding=15)
        self.stats_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        stats_row = ttk.Frame(self.stats_frame)
        stats_row.pack(fill=tk.X)

        self.stat_total_label = ttk.Label(stats_row, text="Total Requests: 0", font=('Arial', 11))
        self.stat_total_label.pack(side=tk.LEFT, padx=20)

        self.stat_open_label = ttk.Label(stats_row, text="Open: 0", font=('Arial', 11))
        self.stat_open_label.pack(side=tk.LEFT, padx=20)

        self.stat_assigned_label = ttk.Label(stats_row, text="Assigned: 0", font=('Arial', 11))
        self.stat_assigned_label.pack(side=tk.LEFT, padx=20)

        self.stat_completed_label = ttk.Label(stats_row, text="Completed: 0", font=('Arial', 11))
        self.stat_completed_label.pack(side=tk.LEFT, padx=20)

        # By urgency breakdown
        urgency_frame = ttk.LabelFrame(tab, text="Requests by Urgency", padding=10)
        urgency_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        urgency_tree_frame = ttk.Frame(urgency_frame)
        urgency_tree_frame.pack(fill=tk.BOTH, expand=True)

        urgency_cols = ('Urgency', 'Count')
        self.urgency_tree = ttk.Treeview(
            urgency_tree_frame, columns=urgency_cols, show='headings', height=6
        )
        for col in urgency_cols:
            self.urgency_tree.heading(col, text=col)
            self.urgency_tree.column(col, width=200, anchor=tk.CENTER)

        self.urgency_tree.pack(fill=tk.BOTH, expand=True)

        # Urgency colour tags for the report treeview
        self.urgency_tree.tag_configure('urgent', background='#f8d7da')
        self.urgency_tree.tag_configure('high', background='#ffe0b2')
        self.urgency_tree.tag_configure('normal', background='white')
        self.urgency_tree.tag_configure('low', background='#e2e3e5')

        self._load_reports()

    def _load_reports(self):
        """Load cover statistics into the reports tab."""
        try:
            stats = CoverManager.get_cover_statistics()

            total = stats.get('total_requests', 0)
            by_status = stats.get('by_status', {})
            by_urgency = stats.get('by_urgency', {})

            self.stat_total_label.config(text=f"Total Requests: {total}")
            self.stat_open_label.config(text=f"Open: {by_status.get('open', 0)}")
            self.stat_assigned_label.config(text=f"Assigned: {by_status.get('assigned', 0)}")
            self.stat_completed_label.config(text=f"Completed: {by_status.get('completed', 0)}")

            # Urgency breakdown
            self.urgency_tree.delete(*self.urgency_tree.get_children())
            for urgency_level in ['urgent', 'high', 'normal', 'low']:
                count = by_urgency.get(urgency_level, 0)
                self.urgency_tree.insert(
                    '', 'end',
                    values=(urgency_level.capitalize(), count),
                    tags=(urgency_level,)
                )

            self._update_status("Reports refreshed")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load statistics: {e}")

    # ================================================================
    # Helpers
    # ================================================================

    def _update_status(self, message: str):
        """Update the status bar if running in standalone window mode."""
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.config(text=message)


def launch_cover_gui(root, auth):
    """Launch Substitute/Cover Arrangements GUI."""
    try:
        return CoverGUI(root, auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Cover Management: {e}")
        return None
