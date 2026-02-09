import tkinter as tk
from tkinter import ttk, messagebox

# Import internationalization support
from university_system.modules.shared.utils.i18n import get_text as _, init_i18n
init_i18n()

# Import main database connection
try:
    from university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    MAIN_DB_AVAILABLE = False

ORIGINAL_FUNCTIONS_AVAILABLE = MAIN_DB_AVAILABLE


def show_student_management_redirect(self):
        """Redirect to centralized student management"""
        messagebox.showinfo(
            _("attendance.messages.student_management_redirect"),
            _("attendance.messages.student_management_redirect_message")
        )

def delete_student(self):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

def filter_students(self, event=None):
        """Filter students based on search text"""
        search_text = self.search_var.get().lower()

        # Clear and reload with filter
        for item in self.students_tree.get_children():
            self.students_tree.delete(item)

        try:
            if MAIN_DB_AVAILABLE:
                # Use main database connection - same schema as main_gui.py
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    if search_text:
                        cursor.execute('''
                        SELECT student_id, first_name, last_name, email_address, course,
                               COALESCE(enrollment_date, registration_datetime, 'Unknown') as enrollment_date
                        FROM students
                        WHERE LOWER(student_id) LIKE ? OR LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
                        ORDER BY last_name, first_name
                        ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                    else:
                        cursor.execute('''
                        SELECT student_id, first_name, last_name, email_address, course,
                               COALESCE(enrollment_date, registration_datetime, 'Unknown') as enrollment_date
                        FROM students
                        ORDER BY last_name, first_name
                        ''')

                    students = cursor.fetchall()

                    for student in students:
                        student_data = (student[0], student[1], student[2], student[3], student[4], student[5])
                        self.students_tree.insert('', 'end', values=student_data)

                    conn.close()
                    return

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                if search_text:
                    cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address,
                           course, COALESCE(registration_datetime, 'Unknown') as enrollment_date
                    FROM students
                    WHERE LOWER(student_id) LIKE ? OR LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
                    ORDER BY student_id
                    ''', (f'%{search_text}%', f'%{search_text}%', f'%{search_text}%'))
                else:
                    cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address,
                           course, COALESCE(registration_datetime, 'Unknown') as enrollment_date
                    FROM students
                    ORDER BY student_id
                    ''')

                students = cursor.fetchall()

                for student in students:
                    self.students_tree.insert('', 'end', values=student)

                conn.close()

        except Exception as e:
            print(f"Error filtering students: {e}")

def add_student(self):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

def refresh_students_data(self):
        """Refresh students data in management tab"""
        try:
            # Clear existing items
            for item in self.students_tree.get_children():
                self.students_tree.delete(item)

            if MAIN_DB_AVAILABLE:
                # Use main database connection - same schema as main_gui.py
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    # Get students using same schema as main_gui.py
                    cursor.execute('''
                    SELECT student_id, first_name, last_name, email_address, course,
                           COALESCE(enrollment_date, registration_datetime, 'Unknown') as enrollment_date
                    FROM students
                    ORDER BY last_name, first_name
                    ''')
                    students = cursor.fetchall()

                    for student in students:
                        # Use the 6 columns we need for the TreeView
                        student_data = (student[0], student[1], student[2], student[3], student[4], student[5])
                        self.students_tree.insert('', 'end', values=student_data)

                    conn.close()
                    return

            if ORIGINAL_FUNCTIONS_AVAILABLE:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute('''
                SELECT student_id, first_name, last_name, email_address,
                       course, COALESCE(registration_datetime, 'Unknown') as enrollment_date
                FROM students
                ORDER BY student_id
                ''')

                students = cursor.fetchall()

                for student in students:
                    self.students_tree.insert('', 'end', values=student)

                conn.close()
            else:
                # Sample data fallback
                sample_students = [
                    ("S001", "John", "Doe", "john.doe@email.com", "Computer Science", "2024-09-01"),
                    ("S002", "Jane", "Smith", "jane.smith@email.com", "Computer Science", "2024-09-01"),
                ]

                for student in sample_students:
                    self.students_tree.insert('', 'end', values=student)

        except Exception as e:
            print(f"Error refreshing students data: {e}")

def create_students_tab(self):
        """Create students management tab"""
        students_frame = ttk.Frame(self.notebook)
        self.notebook.add(students_frame, text=_("attendance.tabs.students"))

        # Toolbar
        toolbar = ttk.Frame(students_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # Note: Student management (add/edit/delete) should be done through the main Student Management module
        # These buttons have been removed to avoid duplicate functionality and maintain data consistency

        # Search frame
        search_frame = ttk.Frame(toolbar)
        search_frame.pack(side=tk.RIGHT)

        ttk.Label(search_frame, text=_("common.search")).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.LEFT)
        search_entry.bind('<KeyRelease>', self.filter_students)

        # Students treeview
        student_mgmt_columns = (_("attendance.columns.id"), _("attendance.columns.first_name"), _("attendance.columns.last_name"), _("attendance.columns.email"), _("attendance.columns.course"), _("attendance.columns.enrollment_date"))
        self.students_tree = ttk.Treeview(students_frame, columns=student_mgmt_columns, show="headings")

        for col in student_mgmt_columns:
            self.students_tree.heading(col, text=col)
            self.students_tree.column(col, width=120)

        students_scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=students_scrollbar.set)

        self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        students_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

def edit_student(self, event=None):
        """Redirect to centralized student management"""
        self.show_student_management_redirect()

