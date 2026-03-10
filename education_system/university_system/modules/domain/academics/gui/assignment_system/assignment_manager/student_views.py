"""Student-facing assignment views"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class StudentViewsMixin:
    """Student assignment views"""

    def show_my_assignments(self):
        """Show student's assignments"""
        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="My Assignments", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create assignments table
        assignments_frame = ttk.Frame(self.gui.layout.content_area)
        assignments_frame.pack(fill='both', expand=True)

        # Treeview for assignments
        columns = ('ID', 'Title', 'Module', 'Due Date', 'Status', 'Grade')
        tree = ttk.Treeview(assignments_frame, columns=columns, show='headings')

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)

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

        # Load assignments data
        self.load_assignments_data(tree)

        # Buttons frame
        buttons_frame = ttk.Frame(self.gui.layout.content_area)
        buttons_frame.pack(fill='x', pady=(10, 0))

        ttk.Button(buttons_frame, text="Submit Assignment",
                  command=self.gui.submissions.show_submit_assignment).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="View Details",
                  command=lambda: self.view_assignment_details(tree)).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Refresh",
                  command=lambda: self.load_assignments_data(tree)).pack(side='left')


    def load_assignments_data(self, tree):
        """Load assignments data into the treeview"""
        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)

        try:
            student_id = self.assignment_system._get_student_id()
            if not student_id:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.id, a.title, a.module_code, a.due_date,
                   CASE
                       WHEN s.id IS NOT NULL THEN 'Submitted'
                       WHEN a.due_date < datetime('now') THEN 'Overdue'
                       ELSE 'Pending'
                   END as status,
                   COALESCE(s.grade, 'Not Graded') as grade
            FROM assignments a
            JOIN student_modules sm ON a.module_code = sm.module_code
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.student_id = ?
            WHERE sm.student_id = ? AND a.is_active = 1
            ORDER BY a.due_date
            ''', (student_id, student_id))

            assignments = cursor.fetchall()

            for assignment in assignments:
                # Color code based on status
                tags = []
                if assignment[4] == 'Overdue':
                    tags = ['overdue']
                elif assignment[4] == 'Submitted':
                    tags = ['submitted']

                tree.insert('', 'end', values=assignment, tags=tags)

            # Configure tags
            tree.tag_configure('overdue', background='#ffebee')
            tree.tag_configure('submitted', background='#e8f5e8')

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")


    def view_assignment_details(self, tree):
        """View selected assignment details"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment")
            return

        item = tree.item(selection[0])
        assignment_id = item['values'][0]

        # Create details window
        details_window = tk.Toplevel(self.root)
        details_window.title("Assignment Details")
        details_window.geometry("600x400")

        # Load and display assignment details
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT a.*, m.module_name
            FROM assignments a
            JOIN modules m ON a.module_code = m.module_code
            WHERE a.id = ?
            ''', (assignment_id,))

            assignment = cursor.fetchone()

            if assignment:
                details_text = scrolledtext.ScrolledText(details_window, wrap=tk.WORD)
                details_text.pack(fill='both', expand=True, padx=10, pady=10)

                # Display assignment details
                details_text.insert('1.0', f"Assignment: {assignment}")

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignment details: {e}")
