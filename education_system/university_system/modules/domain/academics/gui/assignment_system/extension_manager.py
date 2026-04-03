"""Extension request management"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.i18n import get_text as _
from collections import deque



class ExtensionManager:
    """Extension request management"""

    def __init__(self, gui):
        """Initialize manager with reference to main GUI"""
        self.gui = gui
        self.root = gui.root
        self.auth = gui.auth
        self.assignment_system = gui.assignment_system
        self.style = gui.style

    def _check_permission(self, permission):
        """Check if user has permission"""
        try:
            return self.auth.check_permission(permission)
        except (AttributeError, Exception):
            return self.auth.user_role in ['Admin', 'Faculty']

    def _get_student_id_safe(self):
        """Safely get student ID with fallback"""
        try:
            # Try to get from assignment system
            if hasattr(self.assignment_system, '_get_student_id'):
                return self.assignment_system._get_student_id()

            # Fallback to auth system
            if self.auth and self.auth.current_user:
                return self.auth.current_user.get('id') or self.auth.current_user.get('student_id')

            return None
        except Exception as e:
            print(f"Error getting student ID: {e}")
            return None

    def load_extension_assignments(self, combo):
        """Load assignments available for extension request"""
        try:
            student_id = self._get_student_id_safe()
            # Show all assignments if no student ID (for admin/instructor)

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                if student_id:
                    cursor.execute('''
                    SELECT a.id, a.title, a.module_code, a.due_date
                    FROM assignments a
                    JOIN student_modules sm ON a.module_code = sm.module_code
                    WHERE sm.student_id = ? AND a.is_active = 1
                    AND a.due_date > datetime('now', '-7 days')
                    ORDER BY a.due_date
                    ''', (student_id,))
                else:
                    # Show all active assignments if no student ID
                    cursor.execute('''
                    SELECT a.id, a.title, a.module_code, a.due_date
                    FROM assignments a
                    WHERE a.is_active = 1
                    AND a.due_date > datetime('now', '-7 days')
                    ORDER BY a.due_date
                    ''')

                assignments = cursor.fetchall()

                assignment_list = []
                self.ext_assignment_map = {}

                for aid, title, module, due_date in assignments:
                    display_text = f"{title} ({module}) - Due: {due_date}"
                    assignment_list.append(display_text)
                    self.ext_assignment_map[display_text] = aid

                combo['values'] = assignment_list
            finally:
                conn.close()

        except Exception as e:
            messagebox.showerror(_("common.error"), _("submission.failed_load_assignments", error=str(e)))

    def show_review_extensions(self):
        """Show extension request review interface"""
        if not self._check_permission('manage_assignments'):
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text=_("extension.title"), style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Filter frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text=_("extension.filters"), padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))

        # Status filter
        ttk.Label(filter_frame, text=_("extension.status")).grid(row=0, column=0, sticky='w', padx=5)
        self.ext_status_filter_var = tk.StringVar(value="pending")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.ext_status_filter_var,
                                   values=["All", "pending", "approved", "denied"], width=15)
        status_combo.grid(row=0, column=1, padx=5)

        ttk.Button(filter_frame, text=_("assignment_gui.buttons.apply_filter"),
                  command=self.load_extension_requests).grid(row=0, column=2, padx=10)

        # Requests table
        requests_frame = ttk.Frame(self.gui.layout.content_area)
        requests_frame.pack(fill='both', expand=True)

        columns = ('ID', 'Student', 'Assignment', 'Requested Date', 'New Due Date', 'Status', 'Days')
        self.extensions_tree = ttk.Treeview(requests_frame, columns=columns, show='headings')

        for col in columns:
            self.extensions_tree.heading(col, text=col)
            self.extensions_tree.column(col, width=100)

        # Scrollbars
        v_scroll = ttk.Scrollbar(requests_frame, orient='vertical', command=self.extensions_tree.yview)
        self.extensions_tree.configure(yscrollcommand=v_scroll.set)

        self.extensions_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')

        requests_frame.grid_rowconfigure(0, weight=1)
        requests_frame.grid_columnconfigure(0, weight=1)

        # Bind selection event
        self.extensions_tree.bind('<<TreeviewSelect>>', self.on_extension_select)

        # Details frame
        self.extension_details_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Request Details", padding=10)
        self.extension_details_frame.pack(fill='x', pady=(10, 0))

        # Load extension requests
        self.load_extension_requests()


    def load_extension_requests(self):
        """Load extension requests into treeview"""
        # Clear existing data
        for item in self.extensions_tree.get_children():
            self.extensions_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            status_filter = self.ext_status_filter_var.get()

            if status_filter == "All":
                cursor.execute('''
                SELECT er.id, st.first_name, st.last_name, a.title,
                       er.requested_date, er.new_due_date, er.status,
                       JULIANDAY(er.new_due_date) - JULIANDAY(a.due_date) as extension_days
                FROM extension_requests er
                JOIN assignments a ON er.assignment_id = a.id
                JOIN students st ON er.student_id = st.student_id
                ORDER BY er.requested_date DESC
                ''')
            else:
                cursor.execute('''
                SELECT er.id, st.first_name, st.last_name, a.title,
                       er.requested_date, er.new_due_date, er.status,
                       JULIANDAY(er.new_due_date) - JULIANDAY(a.due_date) as extension_days
                FROM extension_requests er
                JOIN assignments a ON er.assignment_id = a.id
                JOIN students st ON er.student_id = st.student_id
                WHERE er.status = ?
                ORDER BY er.requested_date DESC
                ''', (status_filter,))

            requests = cursor.fetchall()

            for request in requests:
                req_id, fname, lname, title, req_date, new_due, status, days = request
                student_name = f"{fname} {lname}"
                days_text = f"{int(days) if days else 0} days"

                # Color coding
                tags = []
                if status == 'approved':
                    tags = ['approved']
                elif status == 'denied':
                    tags = ['denied']
                elif status == 'pending':
                    tags = ['pending']

                self.extensions_tree.insert('', 'end',
                                           values=(req_id, student_name, title, req_date, new_due, status, days_text),
                                           tags=tags)

            # Configure tags
            self.extensions_tree.tag_configure('approved', background='#e8f5e8')
            self.extensions_tree.tag_configure('denied', background='#ffebee')
            self.extensions_tree.tag_configure('pending', background='#fff3cd')

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load extension requests: {e}")


    def on_extension_select(self, event):
        """Handle extension request selection"""
        selection = self.extensions_tree.selection()
        if not selection:
            return

        item = self.extensions_tree.item(selection[0])
        request_id = item['values'][0]

        self.show_extension_details(request_id)


    def show_extension_details(self, request_id):
        """Show extension request details"""
        # Clear existing details
        for widget in self.extension_details_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT er.*, st.first_name, st.last_name, a.title, a.due_date
            FROM extension_requests er
            JOIN students st ON er.student_id = st.student_id
            JOIN assignments a ON er.assignment_id = a.id
            WHERE er.id = ?
            ''', (request_id,))

            request = cursor.fetchone()
            if not request:
                return

            # Display request details
            details_label = ttk.Label(details_frame, text=f"Student: {request[11]} {request[12]}")
            details_label.pack(pady=5)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load extension details: {e}")

    def process_extension_decision(self, request_id, decision):
        """Process extension request decision"""
        try:
            comments = ""
            if hasattr(self, 'review_comments_text'):
                comments = self.review_comments_text.get(1.0, tk.END).strip()

            if not comments and decision == 'denied':
                if not messagebox.askyesno("No Comments", "Are you sure you want to deny without comments?"):
                    return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Calculate extension days if approved
                extension_days = 0
                if decision == 'approved':
                    cursor.execute('''
                    SELECT JULIANDAY(er.new_due_date) - JULIANDAY(a.due_date)
                    FROM extension_requests er
                    JOIN assignments a ON er.assignment_id = a.id
                    WHERE er.id = ?
                    ''', (request_id,))

                    extension_days = int(cursor.fetchone()[0])

                # Update request
                cursor.execute('''
                UPDATE extension_requests
                SET status = ?, reviewed_by = ?, reviewed_date = ?,
                    reviewer_comments = ?, approved_extension_days = ?
                WHERE id = ?
                ''', (decision, self.auth.current_user['id'],
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      comments, extension_days, request_id))

                conn.commit()

                # Send extension notification email if approved
                if decision == 'approved':
                    try:
                        # Get student email and assignment details
                        cursor.execute('''
                        SELECT s.email_address, a.title, a.module_code, er.new_due_date
                        FROM extension_requests er
                        JOIN students s ON er.student_id = s.student_id
                        JOIN assignments a ON er.assignment_id = a.id
                        WHERE er.id = ?
                        ''', (request_id,))
                        result = cursor.fetchone()

                        if result:
                            student_email, assignment_title, module_code, new_due_date = result
                            from education_system.university_system.infrastructure.email.email_service import send_extension_notification
                            import logging
                            send_extension_notification(
                                student_email,
                                assignment_title,
                                module_code,
                                new_due_date,
                                str(extension_days)
                            )
                    except Exception as e:
                        import logging
                        logging.warning(f"Failed to send extension notification email: {e}")

            finally:
                conn.close()

            messagebox.showinfo("Success", f"Extension request {decision}!")

            # Refresh the list
            self.load_extension_requests()

            # Clear details
            for widget in self.extension_details_frame.winfo_children():
                widget.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process decision: {e}")

    # MESSAGING SYSTEM (missing from GUI)

    def show_extension_request(self):
        """Show extension request form"""
        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="Request Extension", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Extension request form
        form_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Extension Request", padding=20)
        form_frame.pack(fill='x', pady=(0, 20))

        # Assignment selection
        ttk.Label(form_frame, text="Assignment:").grid(row=0, column=0, sticky='w', pady=5)
        self.ext_assignment_var = tk.StringVar()
        ext_combo = ttk.Combobox(form_frame, textvariable=self.ext_assignment_var, width=50)
        ext_combo.grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

        # Load available assignments for extension
        self.load_extension_assignments(ext_combo)

        # New due date
        ttk.Label(form_frame, text="Requested Due Date:").grid(row=1, column=0, sticky='w', pady=5)
        self.ext_date_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.ext_date_var, width=20).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

        # Reason
        ttk.Label(form_frame, text="Reason:").grid(row=2, column=0, sticky='nw', pady=5)
        self.ext_reason_text = scrolledtext.ScrolledText(form_frame, height=6, width=50)
        self.ext_reason_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))

        form_frame.grid_columnconfigure(1, weight=1)

        # Submit button
        submit_btn = ttk.Button(form_frame, text="Submit Request", command=self.submit_extension_request)
        submit_btn.grid(row=3, column=1, sticky='e', pady=(20, 0))

        # Status frame
        self.ext_status_frame = ttk.Frame(self.gui.layout.content_area)
        self.ext_status_frame.pack(fill='x', pady=(10, 0))


    def submit_extension_request(self):
        """Submit extension request"""
        # Validate form
        if not self.ext_assignment_var.get():
            self.show_ext_status("Please select an assignment", "error")
            return

        if not self.ext_date_var.get():
            self.show_ext_status("Please enter a new due date", "error")
            return

        if not self.ext_reason_text.get(1.0, tk.END).strip():
            self.show_ext_status("Please provide a reason", "error")
            return

        try:
            # Validate date format
            new_due_date = datetime.strptime(self.ext_date_var.get(), "%Y-%m-%d %H:%M")
            if new_due_date <= datetime.now():
                self.show_ext_status("New due date must be in the future", "error")
                return
        except ValueError:
            self.show_ext_status("Invalid date format. Use YYYY-MM-DD HH:MM", "error")
            return

        # Submit request
        try:
            assignment_id = self.ext_assignment_map.get(self.ext_assignment_var.get())
            student_id = self.assignment_system._get_student_id()

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                cursor.execute('''
                INSERT INTO extension_requests
                (assignment_id, student_id, requested_date, new_due_date, reason)
                VALUES (?, ?, ?, ?, ?)
                ''', (assignment_id, student_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                      new_due_date.strftime('%Y-%m-%d %H:%M:%S'), self.ext_reason_text.get(1.0, tk.END).strip()))

                conn.commit()
            finally:
                conn.close()

            self.show_ext_status("Extension request submitted successfully!", "success")
            self.clear_extension_form()

        except Exception as e:
            self.show_ext_status(f"Failed to submit request: {e}", "error")


    def show_ext_status(self, message, msg_type):
        """Show status message for extension request"""
        for widget in self.ext_status_frame.winfo_children():
            widget.destroy()

        if msg_type == "success":
            style = 'Success.TLabel'
        elif msg_type == "error":
            style = 'Error.TLabel'
        else:
            style = 'Warning.TLabel'

        status_label = ttk.Label(self.ext_status_frame, text=message, style=style)
        status_label.pack(anchor='w')


    def clear_extension_form(self):
        """Clear extension request form"""
        self.ext_assignment_var.set('')
        self.ext_date_var.set('')
        self.ext_reason_text.delete(1.0, tk.END)

    # Additional feature entry points

    def request_extension(self, *args, **kwargs):
        """Open the student extension request form."""
        self._launch_gui_feature(self.show_extension_request, "extension request")



    def review_extension_requests(self, *args, **kwargs):
        """Navigate to instructor extension review tools."""
        self._launch_gui_feature(self.show_review_extensions, "extension review")


    def _submit_extension_request(self, assignment_id, reason, requested_date):
        """Submit extension request to database (helper function)"""
        try:
            student_id = self._get_student_id_safe()
            if not student_id:
                messagebox.showerror("Error", "Could not identify student")
                return False

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                INSERT INTO extension_requests
                (assignment_id, student_id, reason, requested_due_date, status, request_date)
                VALUES (?, ?, ?, ?, 'pending', ?)
                ''', (assignment_id, student_id, reason, requested_date, timestamp))

                conn.commit()
            finally:
                conn.close()

            return True

        except Exception as e:
            print(f"Error submitting extension request: {e}")
            return False


    def _process_extension_request(self, request_id, decision, instructor_notes=""):
        """Process single extension request (approve/deny logic)"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get request details
            cursor.execute('''
            SELECT assignment_id, student_id, requested_due_date
            FROM extension_requests WHERE id = ?
            ''', (request_id,))

            request = cursor.fetchone()
            if not request:
                conn.close()
                return False

            assignment_id, student_id, new_due_date = request

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            instructor_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None

            # Update request status
            cursor.execute('''
            UPDATE extension_requests
            SET status = ?, reviewed_by = ?, review_date = ?, instructor_notes = ?
            WHERE id = ?
            ''', (decision, instructor_id, timestamp, instructor_notes, request_id))

            # If approved, update assignment due date for this student
            if decision == 'approved':
                cursor.execute('''
                INSERT OR REPLACE INTO assignment_extensions
                (assignment_id, student_id, original_due_date, extended_due_date, approved_by, approved_date)
                VALUES (?, ?, (SELECT due_date FROM assignments WHERE id = ?), ?, ?, ?)
                ''', (assignment_id, student_id, assignment_id, new_due_date, instructor_id, timestamp))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error processing extension request: {e}")
            return False


    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")


