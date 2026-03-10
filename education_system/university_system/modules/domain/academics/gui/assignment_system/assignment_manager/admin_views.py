"""Admin-specific assignment views"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class AdminViewsMixin:
    """Admin assignment views"""

    def show_admin_all_assignments(self):
        """Show all assignments in the system (admin view)"""
        if not self.auth.current_user or self.auth.current_user.get('role') != 'admin':
            messagebox.showerror("Access Denied", "This feature is only available to administrators.")
            return

        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="All Assignments (Admin View)", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Info label
        info_label = ttk.Label(self.gui.layout.content_area,
                              text="As an administrator, you can view all assignments in the system.",
                              foreground='blue')
        info_label.pack(anchor='w', pady=(0, 10))

        # Create assignments table
        assignments_frame = ttk.Frame(self.gui.layout.content_area)
        assignments_frame.pack(fill='both', expand=True)

        # Treeview for assignments with admin-specific columns
        columns = ('ID', 'Title', 'Module', 'Due Date', 'Type', 'Active', 'Created By', 'Created Date', 'Submissions')
        tree = ttk.Treeview(assignments_frame, columns=columns, show='headings')

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Title':
                tree.column(col, width=200)
            elif col in ['Created Date', 'Due Date']:
                tree.column(col, width=150)
            else:
                tree.column(col, width=100)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(assignments_frame, orient='vertical', command=tree.yview)
        h_scrollbar = ttk.Scrollbar(assignments_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Grid layout
        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        assignments_frame.grid_rowconfigure(0, weight=1)
        assignments_frame.grid_columnconfigure(0, weight=1)

        # Load all assignments data
        self.load_admin_assignments_data(tree)

        # Buttons frame
        buttons_frame = ttk.Frame(self.gui.layout.content_area)
        buttons_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(buttons_frame, text="View Assignment Details",
                  command=lambda: self.view_admin_assignment_details(tree)).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="View All Submissions",
                  command=lambda: self.view_all_submissions_for_assignment(tree)).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Refresh",
                  command=lambda: self.load_admin_assignments_data(tree)).pack(side='left')


    def load_admin_assignments_data(self, tree):
        """Load all assignments data for admin view"""
        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.id, a.title, a.module_code, a.due_date, a.assignment_type,
                   a.is_active, u.username as creator, a.created_at,
                   COUNT(s.id) as submission_count
            FROM assignments a
            LEFT JOIN users u ON a.created_by = u.id
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            GROUP BY a.id, a.title, a.module_code, a.due_date, a.assignment_type,
                     a.is_active, u.username, a.created_at
            ORDER BY a.created_at DESC
            ''')

            assignments = cursor.fetchall()

            for assignment in assignments:
                aid, title, module, due_date, atype, is_active, creator, created_at, submission_count = assignment

                # Format display values
                active_status = "Yes" if is_active else "No"
                creator_display = creator if creator else "Unknown"

                # Color code based on active status
                tags = []
                if not is_active:
                    tags = ['inactive']
                elif due_date < datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                    tags = ['overdue']

                values = (aid, title, module, due_date, atype, active_status,
                         creator_display, created_at, submission_count)
                tree.insert('', 'end', values=values, tags=tags)

            # Configure tags
            tree.tag_configure('inactive', background='#ffcccc')
            tree.tag_configure('overdue', background='#fff3cd')

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load admin assignments: {e}")


    def view_admin_assignment_details(self, tree):
        """View detailed information about selected assignment (admin)"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to view details.")
            return

        # Get assignment ID from selected item
        item = tree.item(selection[0])
        assignment_id = item['values'][0]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.*, u.username as creator_name
            FROM assignments a
            LEFT JOIN users u ON a.created_by = u.id
            WHERE a.id = ?
            ''', (assignment_id,))

            assignment = cursor.fetchone()
            if not assignment:
                messagebox.showerror("Error", "Assignment not found.")
                return

            # Create details window
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Assignment Details - {assignment[2]}")  # assignment[2] is title
            details_window.geometry("600x500")

            # Scrollable frame
            canvas = tk.Canvas(details_window)
            scrollbar = ttk.Scrollbar(details_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Assignment details
            ttk.Label(scrollable_frame, text="Assignment Details", font=('TkDefaultFont', 12, 'bold')).pack(pady=10)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignment details: {e}")

    def view_all_submissions_for_assignment(self, tree):
        """View all submissions for selected assignment (admin)"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to view submissions.")
            return

        # Get assignment details
        item = tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT s.id, s.student_id, u.first_name, u.last_name, s.submission_date,
                   s.status, s.grade, s.feedback, s.late_submission, s.late_days
            FROM assignment_submissions s
            JOIN users u ON s.student_id = u.student_id
            WHERE s.assignment_id = ?
            ORDER BY s.submission_date DESC
            ''', (assignment_id,))

            submissions = cursor.fetchall()

            # Create submissions window
            submissions_window = tk.Toplevel(self.root)
            submissions_window.title(f"Submissions for: {assignment_title}")
            submissions_window.geometry("900x600")

            # Submissions table
            columns = ('ID', 'Student ID', 'Name', 'Submission Date', 'Status', 'Grade', 'Late', 'Late Days')
            submissions_tree = ttk.Treeview(submissions_window, columns=columns, show='headings')

            for col in columns:
                submissions_tree.heading(col, text=col)
                if col == 'Name':
                    submissions_tree.column(col, width=150)
                elif col == 'Submission Date':
                    submissions_tree.column(col, width=140)
                else:
                    submissions_tree.column(col, width=100)

            # Add scrollbars
            v_scroll = ttk.Scrollbar(submissions_window, orient='vertical', command=submissions_tree.yview)
            h_scroll = ttk.Scrollbar(submissions_window, orient='horizontal', command=submissions_tree.xview)
            submissions_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

            # Load data
            for submission in submissions:
                sub_id, student_id, first_name, last_name, sub_date, status, grade, feedback, is_late, late_days = submission
                full_name = f"{first_name} {last_name}"
                late_status = "Yes" if is_late else "No"
                late_days_display = late_days if late_days else "0"
                grade_display = grade if grade else "Not Graded"

                submissions_tree.insert('', 'end', values=(
                    sub_id, student_id, full_name, sub_date, status,
                    grade_display, late_status, late_days_display
                ))

            # Pack widgets
            submissions_tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)
            v_scroll.pack(side='right', fill='y', pady=10)

            # Info label
            info_label = ttk.Label(submissions_window,
                                 text=f"Total submissions: {len(submissions)}")
            info_label.pack(pady=5)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")
