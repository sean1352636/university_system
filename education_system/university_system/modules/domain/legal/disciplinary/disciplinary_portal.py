"""
University Disciplinary Actions Portal
A GUI application for managing student disciplinary records and actions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
from datetime import datetime
import csv
import os


# ============================================================
# DATABASE MANAGER
# ============================================================
class DatabaseManager:
    """Handles all database operations for the portal."""

    def __init__(self, db_name="disciplinary_portal.db"):
        self.db_name = db_name
        self.init_database()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_database(self):
        """Create tables if they don't exist."""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT,
                department TEXT,
                year_of_study INTEGER,
                enrollment_date TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                incident_date TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT,
                reported_by TEXT,
                location TEXT,
                status TEXT DEFAULT 'Open',
                created_at TEXT,
                FOREIGN KEY (student_id) REFERENCES students(student_id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                action_date TEXT NOT NULL,
                duration TEXT,
                issued_by TEXT,
                notes TEXT,
                FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
            )
        """)

        # Insert sample data if tables are empty
        cursor.execute("SELECT COUNT(*) FROM students")
        if cursor.fetchone()[0] == 0:
            self._insert_sample_data(cursor)

        conn.commit()
        conn.close()

    def _insert_sample_data(self, cursor):
        """Insert sample students for demonstration."""
        sample_students = [
            ("S1001", "John", "Smith", "j.smith@uni.edu", "Computer Science", 2, "2023-09-01"),
            ("S1002", "Emily", "Johnson", "e.johnson@uni.edu", "Mathematics", 3, "2022-09-01"),
            ("S1003", "Michael", "Brown", "m.brown@uni.edu", "Engineering", 1, "2024-09-01"),
            ("S1004", "Sarah", "Davis", "s.davis@uni.edu", "Biology", 4, "2021-09-01"),
            ("S1005", "James", "Wilson", "j.wilson@uni.edu", "Physics", 2, "2023-09-01"),
        ]
        cursor.executemany(
            "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?)",
            sample_students
        )

    # --- Student operations ---
    def add_student(self, data):
        conn = self.get_connection()
        try:
            conn.execute(
                "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?, ?)",
                data
            )
            conn.commit()
            return True, "Student added successfully"
        except sqlite3.IntegrityError:
            return False, "Student ID already exists"
        finally:
            conn.close()

    def get_all_students(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students ORDER BY last_name, first_name")
        results = cursor.fetchall()
        conn.close()
        return results

    def search_students(self, query):
        conn = self.get_connection()
        cursor = conn.cursor()
        q = f"%{query}%"
        cursor.execute("""
            SELECT * FROM students 
            WHERE student_id LIKE ? OR first_name LIKE ? 
            OR last_name LIKE ? OR department LIKE ?
            ORDER BY last_name
        """, (q, q, q, q))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_student(self, student_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    # --- Incident operations ---
    def add_incident(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO incidents 
            (student_id, incident_date, incident_type, severity, description, 
             reported_by, location, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        incident_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return incident_id

    def get_all_incidents(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT i.incident_id, i.student_id, s.first_name || ' ' || s.last_name,
                   i.incident_date, i.incident_type, i.severity, i.status
            FROM incidents i
            LEFT JOIN students s ON i.student_id = s.student_id
            ORDER BY i.incident_date DESC
        """)
        results = cursor.fetchall()
        conn.close()
        return results

    def get_incidents_by_student(self, student_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM incidents WHERE student_id = ?
            ORDER BY incident_date DESC
        """, (student_id,))
        results = cursor.fetchall()
        conn.close()
        return results

    def get_incident(self, incident_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM incidents WHERE incident_id = ?", (incident_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def update_incident_status(self, incident_id, status):
        conn = self.get_connection()
        conn.execute(
            "UPDATE incidents SET status = ? WHERE incident_id = ?",
            (status, incident_id)
        )
        conn.commit()
        conn.close()

    # --- Action operations ---
    def add_action(self, data):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO actions 
            (incident_id, action_type, action_date, duration, issued_by, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, data)
        conn.commit()
        conn.close()

    def get_actions_by_incident(self, incident_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM actions WHERE incident_id = ? ORDER BY action_date DESC",
            (incident_id,)
        )
        results = cursor.fetchall()
        conn.close()
        return results

    # --- Statistics ---
    def get_statistics(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        stats = {}

        cursor.execute("SELECT COUNT(*) FROM students")
        stats['total_students'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM incidents")
        stats['total_incidents'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM incidents WHERE status = 'Open'")
        stats['open_incidents'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM incidents WHERE status = 'Resolved'")
        stats['resolved_incidents'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM actions")
        stats['total_actions'] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT severity, COUNT(*) FROM incidents 
            GROUP BY severity
        """)
        stats['by_severity'] = dict(cursor.fetchall())

        cursor.execute("""
            SELECT incident_type, COUNT(*) FROM incidents 
            GROUP BY incident_type 
            ORDER BY COUNT(*) DESC LIMIT 5
        """)
        stats['top_types'] = cursor.fetchall()

        conn.close()
        return stats


# ============================================================
# MAIN APPLICATION
# ============================================================
class DisciplinaryPortal:
    """Main application class for the Disciplinary Actions Portal."""

    # Color scheme
    COLORS = {
        'primary': '#1e3a5f',
        'secondary': '#2c5282',
        'accent': '#c9a961',
        'bg': '#f5f7fa',
        'card': '#ffffff',
        'text': '#2d3748',
        'text_light': '#718096',
        'success': '#38a169',
        'warning': '#d69e2e',
        'danger': '#e53e3e',
        'border': '#e2e8f0',
    }

    INCIDENT_TYPES = [
        "Academic Misconduct", "Plagiarism", "Cheating", "Disruptive Behavior",
        "Harassment", "Property Damage", "Substance Abuse", "Violence",
        "Attendance Violation", "Code of Conduct Violation", "Other"
    ]

    SEVERITY_LEVELS = ["Minor", "Moderate", "Serious", "Severe"]

    ACTION_TYPES = [
        "Verbal Warning", "Written Warning", "Probation", "Community Service",
        "Fine", "Suspension", "Expulsion", "Mandatory Counseling",
        "Course Failure", "Educational Sanction", "No Action"
    ]

    STATUS_OPTIONS = ["Open", "Under Review", "Resolved", "Appealed", "Closed"]

    def __init__(self, root):
        self.root = root
        self.root.title("University Disciplinary Actions Portal")
        self.root.geometry("1200x750")
        self.root.configure(bg=self.COLORS['bg'])

        self.db = DatabaseManager()
        self.current_user = "Admin"

        self.setup_styles()
        self.create_header()
        self.create_main_layout()
        self.show_dashboard()

    def setup_styles(self):
        """Configure ttk widget styles."""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Treeview',
                        background=self.COLORS['card'],
                        foreground=self.COLORS['text'],
                        rowheight=28,
                        fieldbackground=self.COLORS['card'],
                        borderwidth=0,
                        font=('Segoe UI', 10))
        style.configure('Treeview.Heading',
                        background=self.COLORS['primary'],
                        foreground='white',
                        font=('Segoe UI', 10, 'bold'),
                        borderwidth=0)
        style.map('Treeview',
                  background=[('selected', self.COLORS['secondary'])],
                  foreground=[('selected', 'white')])
        style.map('Treeview.Heading',
                  background=[('active', self.COLORS['secondary'])])

        style.configure('TCombobox',
                        fieldbackground='white',
                        background='white')
        style.configure('TNotebook',
                        background=self.COLORS['bg'],
                        borderwidth=0)
        style.configure('TNotebook.Tab',
                        padding=[20, 10],
                        font=('Segoe UI', 10))

    def create_header(self):
        """Create the top header bar."""
        header = tk.Frame(self.root, bg=self.COLORS['primary'], height=70)
        header.pack(fill='x', side='top')
        header.pack_propagate(False)

        title_frame = tk.Frame(header, bg=self.COLORS['primary'])
        title_frame.pack(side='left', padx=25, pady=10)

        tk.Label(title_frame, text="🎓 Disciplinary Actions Portal",
                 font=('Segoe UI', 18, 'bold'),
                 bg=self.COLORS['primary'], fg='white').pack(anchor='w')
        tk.Label(title_frame, text="University Administration System",
                 font=('Segoe UI', 10),
                 bg=self.COLORS['primary'], fg='#a0c4e8').pack(anchor='w')

        user_frame = tk.Frame(header, bg=self.COLORS['primary'])
        user_frame.pack(side='right', padx=25, pady=10)

        tk.Label(user_frame, text=f"👤 {self.current_user}",
                 font=('Segoe UI', 11),
                 bg=self.COLORS['primary'], fg='white').pack(anchor='e')
        tk.Label(user_frame, text=datetime.now().strftime("%B %d, %Y"),
                 font=('Segoe UI', 9),
                 bg=self.COLORS['primary'], fg='#a0c4e8').pack(anchor='e')

    def create_main_layout(self):
        """Create the sidebar and main content area."""
        container = tk.Frame(self.root, bg=self.COLORS['bg'])
        container.pack(fill='both', expand=True)

        # Sidebar
        self.sidebar = tk.Frame(container, bg=self.COLORS['secondary'], width=220)
        self.sidebar.pack(side='left', fill='y')
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="MENU",
                 font=('Segoe UI', 9, 'bold'),
                 bg=self.COLORS['secondary'], fg='#a0c4e8').pack(pady=(20, 10), anchor='w', padx=25)

        self.nav_buttons = {}
        nav_items = [
            ("📊 Dashboard", self.show_dashboard),
            ("👥 Students", self.show_students),
            ("⚠️ Incidents", self.show_incidents),
            ("📝 New Report", self.show_new_incident),
            ("📈 Reports", self.show_reports),
        ]

        for text, command in nav_items:
            btn = tk.Button(self.sidebar, text=text, command=command,
                            font=('Segoe UI', 11),
                            bg=self.COLORS['secondary'], fg='white',
                            activebackground=self.COLORS['primary'],
                            activeforeground='white',
                            bd=0, anchor='w', padx=25, pady=12,
                            cursor='hand2')
            btn.pack(fill='x')
            self.nav_buttons[text] = btn

        # Footer in sidebar
        tk.Frame(self.sidebar, bg=self.COLORS['secondary']).pack(expand=True)
        tk.Label(self.sidebar, text="v1.0.0",
                 font=('Segoe UI', 8),
                 bg=self.COLORS['secondary'], fg='#a0c4e8').pack(pady=15)

        # Main content area
        self.content = tk.Frame(container, bg=self.COLORS['bg'])
        self.content.pack(side='right', fill='both', expand=True)

    def clear_content(self):
        """Clear the main content area."""
        for widget in self.content.winfo_children():
            widget.destroy()

    def create_page_header(self, title, subtitle=""):
        """Create a consistent page header."""
        header = tk.Frame(self.content, bg=self.COLORS['bg'])
        header.pack(fill='x', padx=30, pady=(25, 15))

        tk.Label(header, text=title,
                 font=('Segoe UI', 22, 'bold'),
                 bg=self.COLORS['bg'], fg=self.COLORS['text']).pack(anchor='w')

        if subtitle:
            tk.Label(header, text=subtitle,
                     font=('Segoe UI', 10),
                     bg=self.COLORS['bg'], fg=self.COLORS['text_light']).pack(anchor='w')

    # ============================================================
    # DASHBOARD
    # ============================================================
    def show_dashboard(self):
        self.clear_content()
        self.create_page_header("Dashboard", "Overview of disciplinary activities")

        stats = self.db.get_statistics()

        # Stat cards
        cards_frame = tk.Frame(self.content, bg=self.COLORS['bg'])
        cards_frame.pack(fill='x', padx=30, pady=10)

        card_data = [
            ("Total Students", stats['total_students'], "👥", self.COLORS['primary']),
            ("Total Incidents", stats['total_incidents'], "⚠️", self.COLORS['warning']),
            ("Open Cases", stats['open_incidents'], "📋", self.COLORS['danger']),
            ("Resolved Cases", stats['resolved_incidents'], "✅", self.COLORS['success']),
        ]

        for i, (label, value, icon, color) in enumerate(card_data):
            card = tk.Frame(cards_frame, bg=self.COLORS['card'],
                            highlightbackground=self.COLORS['border'],
                            highlightthickness=1)
            card.grid(row=0, column=i, padx=8, pady=5, sticky='ew', ipadx=15, ipady=15)
            cards_frame.columnconfigure(i, weight=1)

            tk.Label(card, text=icon, font=('Segoe UI', 24),
                     bg=self.COLORS['card']).pack(anchor='w', padx=15, pady=(10, 0))
            tk.Label(card, text=str(value),
                     font=('Segoe UI', 28, 'bold'),
                     bg=self.COLORS['card'], fg=color).pack(anchor='w', padx=15)
            tk.Label(card, text=label,
                     font=('Segoe UI', 10),
                     bg=self.COLORS['card'], fg=self.COLORS['text_light']).pack(anchor='w', padx=15, pady=(0, 10))

        # Charts section
        charts_frame = tk.Frame(self.content, bg=self.COLORS['bg'])
        charts_frame.pack(fill='both', expand=True, padx=30, pady=15)

        # Severity breakdown
        severity_card = tk.Frame(charts_frame, bg=self.COLORS['card'],
                                 highlightbackground=self.COLORS['border'],
                                 highlightthickness=1)
        severity_card.pack(side='left', fill='both', expand=True, padx=(0, 10), ipadx=15, ipady=15)

        tk.Label(severity_card, text="Incidents by Severity",
                 font=('Segoe UI', 13, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w', padx=15, pady=(10, 15))

        severity_colors = {
            'Minor': '#48bb78',
            'Moderate': '#ecc94b',
            'Serious': '#ed8936',
            'Severe': '#e53e3e',
        }

        max_count = max(stats['by_severity'].values()) if stats['by_severity'] else 1

        for severity in self.SEVERITY_LEVELS:
            count = stats['by_severity'].get(severity, 0)
            row = tk.Frame(severity_card, bg=self.COLORS['card'])
            row.pack(fill='x', padx=15, pady=4)

            tk.Label(row, text=severity, width=10, anchor='w',
                     font=('Segoe UI', 10),
                     bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side='left')

            bar_frame = tk.Frame(row, bg='#edf2f7', height=22)
            bar_frame.pack(side='left', fill='x', expand=True, padx=10)
            bar_frame.pack_propagate(False)

            if count > 0:
                bar_width = int((count / max_count) * 100)
                bar = tk.Frame(bar_frame, bg=severity_colors[severity], height=22)
                bar.place(relx=0, rely=0, relwidth=bar_width/100, relheight=1)

            tk.Label(row, text=str(count), width=4, anchor='e',
                     font=('Segoe UI', 10, 'bold'),
                     bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side='right')

        # Top incident types
        types_card = tk.Frame(charts_frame, bg=self.COLORS['card'],
                              highlightbackground=self.COLORS['border'],
                              highlightthickness=1)
        types_card.pack(side='right', fill='both', expand=True, padx=(10, 0), ipadx=15, ipady=15)

        tk.Label(types_card, text="Top Incident Types",
                 font=('Segoe UI', 13, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w', padx=15, pady=(10, 15))

        if stats['top_types']:
            for incident_type, count in stats['top_types']:
                row = tk.Frame(types_card, bg=self.COLORS['card'])
                row.pack(fill='x', padx=15, pady=5)

                tk.Label(row, text=f"• {incident_type}",
                         font=('Segoe UI', 10),
                         bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side='left')
                tk.Label(row, text=str(count),
                         font=('Segoe UI', 10, 'bold'),
                         bg=self.COLORS['card'], fg=self.COLORS['primary']).pack(side='right')
        else:
            tk.Label(types_card, text="No incidents recorded yet",
                     font=('Segoe UI', 10, 'italic'),
                     bg=self.COLORS['card'], fg=self.COLORS['text_light']).pack(padx=15, pady=10)

    # ============================================================
    # STUDENTS VIEW
    # ============================================================
    def show_students(self):
        self.clear_content()
        self.create_page_header("Students", "Manage student records")

        # Action bar
        action_bar = tk.Frame(self.content, bg=self.COLORS['bg'])
        action_bar.pack(fill='x', padx=30, pady=(0, 10))

        search_frame = tk.Frame(action_bar, bg=self.COLORS['bg'])
        search_frame.pack(side='left')

        tk.Label(search_frame, text="🔍", font=('Segoe UI', 12),
                 bg=self.COLORS['bg']).pack(side='left', padx=(0, 5))

        self.student_search = tk.Entry(search_frame, font=('Segoe UI', 10),
                                       width=35, relief='solid', bd=1)
        self.student_search.pack(side='left', ipady=5)
        self.student_search.bind('<KeyRelease>', lambda e: self.refresh_students())

        tk.Button(action_bar, text="+ Add Student",
                  command=self.show_add_student,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['primary'], fg='white',
                  bd=0, padx=20, pady=8, cursor='hand2').pack(side='right', padx=5)

        tk.Button(action_bar, text="📋 View Details",
                  command=self.view_student_details,
                  font=('Segoe UI', 10),
                  bg=self.COLORS['secondary'], fg='white',
                  bd=0, padx=20, pady=8, cursor='hand2').pack(side='right', padx=5)

        # Treeview
        tree_frame = tk.Frame(self.content, bg=self.COLORS['card'])
        tree_frame.pack(fill='both', expand=True, padx=30, pady=10)

        columns = ('ID', 'First Name', 'Last Name', 'Email', 'Department', 'Year')
        self.students_tree = ttk.Treeview(tree_frame, columns=columns,
                                          show='headings', height=15)

        widths = [80, 120, 120, 200, 150, 60]
        for col, w in zip(columns, widths):
            self.students_tree.heading(col, text=col)
            self.students_tree.column(col, width=w, anchor='w')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                  command=self.students_tree.yview)
        self.students_tree.configure(yscrollcommand=scrollbar.set)

        self.students_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.students_tree.bind('<Double-1>', lambda e: self.view_student_details())

        self.refresh_students()

    def refresh_students(self):
        for item in self.students_tree.get_children():
            self.students_tree.delete(item)

        query = self.student_search.get().strip()
        students = self.db.search_students(query) if query else self.db.get_all_students()

        for i, student in enumerate(students):
            tag = 'even' if i % 2 == 0 else 'odd'
            self.students_tree.insert('', 'end', values=student[:6], tags=(tag,))

        self.students_tree.tag_configure('odd', background='#f7fafc')
        self.students_tree.tag_configure('even', background='white')

    def show_add_student(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Student")
        dialog.geometry("450x520")
        dialog.configure(bg=self.COLORS['bg'])
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Add New Student",
                 font=('Segoe UI', 16, 'bold'),
                 bg=self.COLORS['bg'], fg=self.COLORS['text']).pack(pady=20)

        form = tk.Frame(dialog, bg=self.COLORS['bg'])
        form.pack(padx=30, fill='x')

        fields = {}
        labels = [
            ('Student ID*', 'student_id'),
            ('First Name*', 'first_name'),
            ('Last Name*', 'last_name'),
            ('Email', 'email'),
            ('Department', 'department'),
            ('Year of Study', 'year'),
        ]

        for label, key in labels:
            tk.Label(form, text=label, font=('Segoe UI', 10),
                     bg=self.COLORS['bg'], fg=self.COLORS['text']).pack(anchor='w', pady=(8, 2))
            entry = tk.Entry(form, font=('Segoe UI', 10),
                             relief='solid', bd=1)
            entry.pack(fill='x', ipady=6)
            fields[key] = entry

        def save():
            try:
                data = (
                    fields['student_id'].get().strip(),
                    fields['first_name'].get().strip(),
                    fields['last_name'].get().strip(),
                    fields['email'].get().strip(),
                    fields['department'].get().strip(),
                    int(fields['year'].get()) if fields['year'].get().strip() else None,
                    datetime.now().strftime("%Y-%m-%d"),
                )

                if not data[0] or not data[1] or not data[2]:
                    messagebox.showerror("Error", "ID, First Name, and Last Name are required")
                    return

                success, msg = self.db.add_student(data)
                if success:
                    messagebox.showinfo("Success", msg)
                    dialog.destroy()
                    self.refresh_students()
                else:
                    messagebox.showerror("Error", msg)
            except ValueError:
                messagebox.showerror("Error", "Year of Study must be a number")

        btn_frame = tk.Frame(dialog, bg=self.COLORS['bg'])
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=('Segoe UI', 10),
                  bg='#cbd5e0', fg=self.COLORS['text'],
                  bd=0, padx=25, pady=8, cursor='hand2').pack(side='left', padx=5)
        tk.Button(btn_frame, text="Save Student", command=save,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['primary'], fg='white',
                  bd=0, padx=25, pady=8, cursor='hand2').pack(side='left', padx=5)

    def view_student_details(self):
        selection = self.students_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a student")
            return

        student_id = self.students_tree.item(selection[0])['values'][0]
        student = self.db.get_student(student_id)
        incidents = self.db.get_incidents_by_student(student_id)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Student Details - {student_id}")
        dialog.geometry("700x600")
        dialog.configure(bg=self.COLORS['bg'])
        dialog.transient(self.root)

        # Student info
        info_frame = tk.Frame(dialog, bg=self.COLORS['card'],
                              highlightbackground=self.COLORS['border'],
                              highlightthickness=1)
        info_frame.pack(fill='x', padx=20, pady=20, ipady=15, ipadx=15)

        tk.Label(info_frame, text=f"{student[1]} {student[2]}",
                 font=('Segoe UI', 18, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w')
        tk.Label(info_frame, text=f"ID: {student[0]}",
                 font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text_light']).pack(anchor='w')

        details_grid = tk.Frame(info_frame, bg=self.COLORS['card'])
        details_grid.pack(fill='x', pady=(15, 0))

        info_items = [
            ("Email:", student[3] or "Not provided"),
            ("Department:", student[4] or "Not provided"),
            ("Year of Study:", str(student[5]) if student[5] else "Not provided"),
            ("Enrolled:", student[6] or "Not provided"),
        ]

        for i, (label, value) in enumerate(info_items):
            tk.Label(details_grid, text=label,
                     font=('Segoe UI', 10, 'bold'),
                     bg=self.COLORS['card'], fg=self.COLORS['text']).grid(
                row=i//2, column=(i%2)*2, sticky='w', padx=(0, 10), pady=3)
            tk.Label(details_grid, text=value,
                     font=('Segoe UI', 10),
                     bg=self.COLORS['card'], fg=self.COLORS['text_light']).grid(
                row=i//2, column=(i%2)*2+1, sticky='w', padx=(0, 30), pady=3)

        # Incident history
        tk.Label(dialog, text=f"Disciplinary History ({len(incidents)} incidents)",
                 font=('Segoe UI', 13, 'bold'),
                 bg=self.COLORS['bg'], fg=self.COLORS['text']).pack(anchor='w', padx=20, pady=(10, 5))

        tree_frame = tk.Frame(dialog, bg=self.COLORS['card'])
        tree_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        columns = ('Date', 'Type', 'Severity', 'Status')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        for incident in incidents:
            tree.insert('', 'end', values=(incident[2], incident[3], incident[4], incident[8]))

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

    # ============================================================
    # INCIDENTS VIEW
    # ============================================================
    def show_incidents(self):
        self.clear_content()
        self.create_page_header("Incidents", "All disciplinary incidents")

        action_bar = tk.Frame(self.content, bg=self.COLORS['bg'])
        action_bar.pack(fill='x', padx=30, pady=(0, 10))

        tk.Button(action_bar, text="+ New Incident",
                  command=self.show_new_incident,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['primary'], fg='white',
                  bd=0, padx=20, pady=8, cursor='hand2').pack(side='right', padx=5)

        tk.Button(action_bar, text="📋 View Details",
                  command=self.view_incident_details,
                  font=('Segoe UI', 10),
                  bg=self.COLORS['secondary'], fg='white',
                  bd=0, padx=20, pady=8, cursor='hand2').pack(side='right', padx=5)

        tk.Button(action_bar, text="📥 Export CSV",
                  command=self.export_incidents,
                  font=('Segoe UI', 10),
                  bg=self.COLORS['accent'], fg='white',
                  bd=0, padx=20, pady=8, cursor='hand2').pack(side='right', padx=5)

        tree_frame = tk.Frame(self.content, bg=self.COLORS['card'])
        tree_frame.pack(fill='both', expand=True, padx=30, pady=10)

        columns = ('ID', 'Student ID', 'Student Name', 'Date', 'Type', 'Severity', 'Status')
        self.incidents_tree = ttk.Treeview(tree_frame, columns=columns,
                                           show='headings', height=15)

        widths = [50, 90, 160, 100, 170, 90, 100]
        for col, w in zip(columns, widths):
            self.incidents_tree.heading(col, text=col)
            self.incidents_tree.column(col, width=w, anchor='w')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical',
                                  command=self.incidents_tree.yview)
        self.incidents_tree.configure(yscrollcommand=scrollbar.set)

        self.incidents_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        self.incidents_tree.bind('<Double-1>', lambda e: self.view_incident_details())

        self.refresh_incidents()

    def refresh_incidents(self):
        for item in self.incidents_tree.get_children():
            self.incidents_tree.delete(item)

        incidents = self.db.get_all_incidents()
        for i, incident in enumerate(incidents):
            tag = 'even' if i % 2 == 0 else 'odd'
            # Add severity-based styling
            severity = incident[5]
            if severity == 'Severe':
                tag = 'severe'
            elif severity == 'Serious':
                tag = 'serious'
            self.incidents_tree.insert('', 'end', values=incident, tags=(tag,))

        self.incidents_tree.tag_configure('odd', background='#f7fafc')
        self.incidents_tree.tag_configure('even', background='white')
        self.incidents_tree.tag_configure('severe', background='#fed7d7')
        self.incidents_tree.tag_configure('serious', background='#feebc8')

    def view_incident_details(self):
        selection = self.incidents_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an incident")
            return

        incident_id = self.incidents_tree.item(selection[0])['values'][0]
        incident = self.db.get_incident(incident_id)
        actions = self.db.get_actions_by_incident(incident_id)
        student = self.db.get_student(incident[1])

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Incident #{incident_id}")
        dialog.geometry("750x700")
        dialog.configure(bg=self.COLORS['bg'])
        dialog.transient(self.root)

        # Header
        hdr = tk.Frame(dialog, bg=self.COLORS['primary'], height=80)
        hdr.pack(fill='x')
        hdr.pack_propagate(False)

        tk.Label(hdr, text=f"Incident #{incident_id}",
                 font=('Segoe UI', 18, 'bold'),
                 bg=self.COLORS['primary'], fg='white').pack(side='left', padx=25, pady=15)

        severity_color = {
            'Minor': '#48bb78', 'Moderate': '#ecc94b',
            'Serious': '#ed8936', 'Severe': '#e53e3e'
        }.get(incident[4], '#718096')

        severity_badge = tk.Label(hdr, text=f"  {incident[4]}  ",
                                   font=('Segoe UI', 10, 'bold'),
                                   bg=severity_color, fg='white')
        severity_badge.pack(side='right', padx=25, pady=25)

        # Scrollable content
        canvas = tk.Canvas(dialog, bg=self.COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient='vertical', command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=self.COLORS['bg'])

        scrollable.bind('<Configure>',
                        lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scrollable, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Info card
        info_card = tk.Frame(scrollable, bg=self.COLORS['card'],
                             highlightbackground=self.COLORS['border'],
                             highlightthickness=1)
        info_card.pack(fill='x', padx=20, pady=15, ipadx=15, ipady=15)

        student_name = f"{student[1]} {student[2]}" if student else "Unknown"
        info_items = [
            ("Student:", f"{student_name} ({incident[1]})"),
            ("Date:", incident[2]),
            ("Type:", incident[3]),
            ("Severity:", incident[4]),
            ("Location:", incident[7] or "Not specified"),
            ("Reported by:", incident[6] or "Not specified"),
            ("Status:", incident[8]),
        ]

        for i, (label, value) in enumerate(info_items):
            row = tk.Frame(info_card, bg=self.COLORS['card'])
            row.pack(fill='x', pady=3)
            tk.Label(row, text=label, width=15, anchor='w',
                     font=('Segoe UI', 10, 'bold'),
                     bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side='left')
            tk.Label(row, text=value, anchor='w',
                     font=('Segoe UI', 10),
                     bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side='left')

        # Description
        desc_card = tk.Frame(scrollable, bg=self.COLORS['card'],
                             highlightbackground=self.COLORS['border'],
                             highlightthickness=1)
        desc_card.pack(fill='x', padx=20, pady=5, ipadx=15, ipady=15)

        tk.Label(desc_card, text="Description",
                 font=('Segoe UI', 11, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w')
        tk.Label(desc_card, text=incident[5] or "No description provided",
                 font=('Segoe UI', 10), wraplength=650, justify='left',
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w', pady=(8, 0))

        # Actions section
        actions_card = tk.Frame(scrollable, bg=self.COLORS['card'],
                                highlightbackground=self.COLORS['border'],
                                highlightthickness=1)
        actions_card.pack(fill='x', padx=20, pady=5, ipadx=15, ipady=15)

        action_header = tk.Frame(actions_card, bg=self.COLORS['card'])
        action_header.pack(fill='x')

        tk.Label(action_header, text=f"Disciplinary Actions ({len(actions)})",
                 font=('Segoe UI', 11, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(side='left')

        tk.Button(action_header, text="+ Add Action",
                  command=lambda: self.show_add_action(incident_id, dialog),
                  font=('Segoe UI', 9, 'bold'),
                  bg=self.COLORS['primary'], fg='white',
                  bd=0, padx=15, pady=5, cursor='hand2').pack(side='right')

        if actions:
            for action in actions:
                a_frame = tk.Frame(actions_card, bg='#f7fafc')
                a_frame.pack(fill='x', pady=5, padx=2)

                header_row = tk.Frame(a_frame, bg='#f7fafc')
                header_row.pack(fill='x', padx=10, pady=(8, 2))

                tk.Label(header_row, text=action[2],
                         font=('Segoe UI', 10, 'bold'),
                         bg='#f7fafc', fg=self.COLORS['primary']).pack(side='left')
                tk.Label(header_row, text=action[3],
                         font=('Segoe UI', 9),
                         bg='#f7fafc', fg=self.COLORS['text_light']).pack(side='right')

                if action[4]:
                    tk.Label(a_frame, text=f"Duration: {action[4]}",
                             font=('Segoe UI', 9),
                             bg='#f7fafc', fg=self.COLORS['text']).pack(anchor='w', padx=10)
                if action[5]:
                    tk.Label(a_frame, text=f"Issued by: {action[5]}",
                             font=('Segoe UI', 9),
                             bg='#f7fafc', fg=self.COLORS['text']).pack(anchor='w', padx=10)
                if action[6]:
                    tk.Label(a_frame, text=action[6],
                             font=('Segoe UI', 9), wraplength=600, justify='left',
                             bg='#f7fafc', fg=self.COLORS['text']).pack(anchor='w', padx=10, pady=(2, 8))
        else:
            tk.Label(actions_card, text="No actions recorded yet",
                     font=('Segoe UI', 10, 'italic'),
                     bg=self.COLORS['card'], fg=self.COLORS['text_light']).pack(pady=10)

        # Status update
        status_card = tk.Frame(scrollable, bg=self.COLORS['card'],
                               highlightbackground=self.COLORS['border'],
                               highlightthickness=1)
        status_card.pack(fill='x', padx=20, pady=5, ipadx=15, ipady=15)

        tk.Label(status_card, text="Update Status",
                 font=('Segoe UI', 11, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w')

        status_row = tk.Frame(status_card, bg=self.COLORS['card'])
        status_row.pack(fill='x', pady=(8, 0))

        status_var = tk.StringVar(value=incident[8])
        status_combo = ttk.Combobox(status_row, textvariable=status_var,
                                     values=self.STATUS_OPTIONS, state='readonly',
                                     font=('Segoe UI', 10), width=20)
        status_combo.pack(side='left', padx=(0, 10))

        def update_status():
            self.db.update_incident_status(incident_id, status_var.get())
            messagebox.showinfo("Success", "Status updated")
            dialog.destroy()
            self.refresh_incidents()

        tk.Button(status_row, text="Update", command=update_status,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['success'], fg='white',
                  bd=0, padx=20, pady=6, cursor='hand2').pack(side='left')

    def show_add_action(self, incident_id, parent_dialog):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Disciplinary Action")
        dialog.geometry("450x480")
        dialog.configure(bg=self.COLORS['bg'])
        dialog.transient(parent_dialog)
        dialog.grab_set()

        tk.Label(dialog, text="Add Disciplinary Action",
                 font=('Segoe UI', 15, 'bold'),
                 bg=self.COLORS['bg'], fg=self.COLORS['text']).pack(pady=15)

        form = tk.Frame(dialog, bg=self.COLORS['bg'])
        form.pack(padx=30, fill='x')

        tk.Label(form, text="Action Type*", font=('Segoe UI', 10),
                 bg=self.COLORS['bg']).pack(anchor='w', pady=(5, 2))
        action_type = ttk.Combobox(form, values=self.ACTION_TYPES,
                                    state='readonly', font=('Segoe UI', 10))
        action_type.pack(fill='x', ipady=3)

        tk.Label(form, text="Action Date*", font=('Segoe UI', 10),
                 bg=self.COLORS['bg']).pack(anchor='w', pady=(10, 2))
        action_date = tk.Entry(form, font=('Segoe UI', 10),
                               relief='solid', bd=1)
        action_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        action_date.pack(fill='x', ipady=6)

        tk.Label(form, text="Duration (e.g., '2 weeks', '30 days')", font=('Segoe UI', 10),
                 bg=self.COLORS['bg']).pack(anchor='w', pady=(10, 2))
        duration = tk.Entry(form, font=('Segoe UI', 10),
                            relief='solid', bd=1)
        duration.pack(fill='x', ipady=6)

        tk.Label(form, text="Issued By", font=('Segoe UI', 10),
                 bg=self.COLORS['bg']).pack(anchor='w', pady=(10, 2))
        issued_by = tk.Entry(form, font=('Segoe UI', 10),
                             relief='solid', bd=1)
        issued_by.insert(0, self.current_user)
        issued_by.pack(fill='x', ipady=6)

        tk.Label(form, text="Notes", font=('Segoe UI', 10),
                 bg=self.COLORS['bg']).pack(anchor='w', pady=(10, 2))
        notes = tk.Text(form, font=('Segoe UI', 10), height=4,
                        relief='solid', bd=1)
        notes.pack(fill='x')

        def save():
            if not action_type.get() or not action_date.get():
                messagebox.showerror("Error", "Action Type and Date are required")
                return

            data = (incident_id, action_type.get(), action_date.get(),
                    duration.get(), issued_by.get(), notes.get('1.0', 'end').strip())
            self.db.add_action(data)
            messagebox.showinfo("Success", "Action added successfully")
            dialog.destroy()
            parent_dialog.destroy()
            self.refresh_incidents()

        btn_frame = tk.Frame(dialog, bg=self.COLORS['bg'])
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="Cancel", command=dialog.destroy,
                  font=('Segoe UI', 10),
                  bg='#cbd5e0', fg=self.COLORS['text'],
                  bd=0, padx=25, pady=8, cursor='hand2').pack(side='left', padx=5)
        tk.Button(btn_frame, text="Save Action", command=save,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['primary'], fg='white',
                  bd=0, padx=25, pady=8, cursor='hand2').pack(side='left', padx=5)

    # ============================================================
    # NEW INCIDENT REPORT
    # ============================================================
    def show_new_incident(self):
        self.clear_content()
        self.create_page_header("New Incident Report", "File a new disciplinary incident")

        form_container = tk.Frame(self.content, bg=self.COLORS['card'],
                                  highlightbackground=self.COLORS['border'],
                                  highlightthickness=1)
        form_container.pack(fill='both', expand=True, padx=30, pady=10, ipadx=20, ipady=20)

        # Two-column layout
        left = tk.Frame(form_container, bg=self.COLORS['card'])
        left.pack(side='left', fill='both', expand=True, padx=(0, 15))

        right = tk.Frame(form_container, bg=self.COLORS['card'])
        right.pack(side='right', fill='both', expand=True, padx=(15, 0))

        # Student selection
        tk.Label(left, text="Student ID*", font=('Segoe UI', 10, 'bold'),
                 bg=self.COLORS['card']).pack(anchor='w', pady=(5, 2))

        students = self.db.get_all_students()
        student_values = [f"{s[0]} - {s[1]} {s[2]}" for s in students]

        student_combo = ttk.Combobox(left, values=student_values,
                                      font=('Segoe UI', 10))
        student_combo.pack(fill='x', ipady=3)

        tk.Label(left, text="Incident Date*", font=('Segoe UI', 10, 'bold'),
                 bg=self.COLORS['card']).pack(anchor='w', pady=(12, 2))
        date_entry = tk.Entry(left, font=('Segoe UI', 10),
                              relief='solid', bd=1)
        date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        date_entry.pack(fill='x', ipady=6)

        tk.Label(left, text="Incident Type*", font=('Segoe UI', 10, 'bold'),
                 bg=self.COLORS['card']).pack(anchor='w', pady=(12, 2))
        type_combo = ttk.Combobox(left, values=self.INCIDENT_TYPES,
                                   state='readonly', font=('Segoe UI', 10))
        type_combo.pack(fill='x', ipady=3)

        tk.Label(left, text="Severity*", font=('Segoe UI', 10, 'bold'),
                 bg=self.COLORS['card']).pack(anchor='w', pady=(12, 2))
        severity_combo = ttk.Combobox(left, values=self.SEVERITY_LEVELS,
                                       state='readonly', font=('Segoe UI', 10))
        severity_combo.pack(fill='x', ipady=3)

        tk.Label(right, text="Location", font=('Segoe UI', 10, 'bold'),
                 bg=self.COLORS['card']).pack(anchor='w', pady=(5, 2))
        location_entry = tk.Entry(right, font=('Segoe UI', 10),
                                   relief='solid', bd=1)
        location_entry.pack(fill='x', ipady=6)

        tk.Label(right, text="Reported By", font=('Segoe UI', 10, 'bold'),
                 bg=self.COLORS['card']).pack(anchor='w', pady=(12, 2))
        reporter_entry = tk.Entry(right, font=('Segoe UI', 10),
                                   relief='solid', bd=1)
        reporter_entry.insert(0, self.current_user)
        reporter_entry.pack(fill='x', ipady=6)

        tk.Label(right, text="Description", font=('Segoe UI', 10, 'bold'),
                 bg=self.COLORS['card']).pack(anchor='w', pady=(12, 2))
        desc_text = tk.Text(right, font=('Segoe UI', 10), height=10,
                            relief='solid', bd=1)
        desc_text.pack(fill='both', expand=True)

        def submit():
            if not student_combo.get() or not type_combo.get() or not severity_combo.get():
                messagebox.showerror("Error", "Please fill all required fields (*)")
                return

            student_id = student_combo.get().split(' - ')[0]

            data = (
                student_id,
                date_entry.get(),
                type_combo.get(),
                severity_combo.get(),
                desc_text.get('1.0', 'end').strip(),
                reporter_entry.get(),
                location_entry.get(),
                'Open',
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )

            incident_id = self.db.add_incident(data)
            messagebox.showinfo("Success",
                                f"Incident #{incident_id} reported successfully")
            self.show_incidents()

        # Submit buttons
        btn_frame = tk.Frame(self.content, bg=self.COLORS['bg'])
        btn_frame.pack(fill='x', padx=30, pady=(0, 20))

        tk.Button(btn_frame, text="Cancel", command=self.show_dashboard,
                  font=('Segoe UI', 11),
                  bg='#cbd5e0', fg=self.COLORS['text'],
                  bd=0, padx=30, pady=10, cursor='hand2').pack(side='right', padx=5)
        tk.Button(btn_frame, text="Submit Report", command=submit,
                  font=('Segoe UI', 11, 'bold'),
                  bg=self.COLORS['primary'], fg='white',
                  bd=0, padx=30, pady=10, cursor='hand2').pack(side='right', padx=5)

    # ============================================================
    # REPORTS / EXPORT
    # ============================================================
    def show_reports(self):
        self.clear_content()
        self.create_page_header("Reports", "Generate and export disciplinary reports")

        stats = self.db.get_statistics()

        # Summary card
        summary = tk.Frame(self.content, bg=self.COLORS['card'],
                           highlightbackground=self.COLORS['border'],
                           highlightthickness=1)
        summary.pack(fill='x', padx=30, pady=10, ipadx=20, ipady=20)

        tk.Label(summary, text="Summary Statistics",
                 font=('Segoe UI', 14, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w')

        summary_text = f"""
📊 Total Registered Students: {stats['total_students']}
⚠️  Total Incidents Filed: {stats['total_incidents']}
📋 Active/Open Cases: {stats['open_incidents']}
✅ Resolved Cases: {stats['resolved_incidents']}
🔨 Total Actions Issued: {stats['total_actions']}

Resolution Rate: {(stats['resolved_incidents']/stats['total_incidents']*100) if stats['total_incidents'] > 0 else 0:.1f}%
        """

        tk.Label(summary, text=summary_text.strip(),
                 font=('Segoe UI', 11), justify='left',
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w', pady=10)

        # Export options
        export_card = tk.Frame(self.content, bg=self.COLORS['card'],
                               highlightbackground=self.COLORS['border'],
                               highlightthickness=1)
        export_card.pack(fill='x', padx=30, pady=10, ipadx=20, ipady=20)

        tk.Label(export_card, text="Export Data",
                 font=('Segoe UI', 14, 'bold'),
                 bg=self.COLORS['card'], fg=self.COLORS['text']).pack(anchor='w', pady=(0, 10))

        tk.Label(export_card, text="Export data as CSV files for external analysis",
                 font=('Segoe UI', 10),
                 bg=self.COLORS['card'], fg=self.COLORS['text_light']).pack(anchor='w', pady=(0, 15))

        btn_row = tk.Frame(export_card, bg=self.COLORS['card'])
        btn_row.pack(anchor='w')

        tk.Button(btn_row, text="📥 Export Students",
                  command=self.export_students,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['primary'], fg='white',
                  bd=0, padx=20, pady=10, cursor='hand2').pack(side='left', padx=5)

        tk.Button(btn_row, text="📥 Export Incidents",
                  command=self.export_incidents,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['secondary'], fg='white',
                  bd=0, padx=20, pady=10, cursor='hand2').pack(side='left', padx=5)

        tk.Button(btn_row, text="📥 Full Report",
                  command=self.export_full_report,
                  font=('Segoe UI', 10, 'bold'),
                  bg=self.COLORS['accent'], fg='white',
                  bd=0, padx=20, pady=10, cursor='hand2').pack(side='left', padx=5)

    def export_students(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv')],
            initialfile='students_export.csv'
        )
        if not filepath:
            return

        students = self.db.get_all_students()
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Student ID', 'First Name', 'Last Name', 'Email',
                             'Department', 'Year', 'Enrollment Date'])
            writer.writerows(students)

        messagebox.showinfo("Export Complete",
                            f"Exported {len(students)} students to {filepath}")

    def export_incidents(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv')],
            initialfile='incidents_export.csv'
        )
        if not filepath:
            return

        incidents = self.db.get_all_incidents()
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Incident ID', 'Student ID', 'Student Name',
                             'Date', 'Type', 'Severity', 'Status'])
            writer.writerows(incidents)

        messagebox.showinfo("Export Complete",
                            f"Exported {len(incidents)} incidents to {filepath}")

    def export_full_report(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension='.txt',
            filetypes=[('Text files', '*.txt')],
            initialfile='disciplinary_report.txt'
        )
        if not filepath:
            return

        stats = self.db.get_statistics()
        incidents = self.db.get_all_incidents()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("UNIVERSITY DISCIPLINARY ACTIONS REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 70 + "\n\n")

            f.write("SUMMARY STATISTICS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total Students: {stats['total_students']}\n")
            f.write(f"Total Incidents: {stats['total_incidents']}\n")
            f.write(f"Open Cases: {stats['open_incidents']}\n")
            f.write(f"Resolved Cases: {stats['resolved_incidents']}\n")
            f.write(f"Total Actions Issued: {stats['total_actions']}\n\n")

            f.write("INCIDENTS BY SEVERITY\n")
            f.write("-" * 70 + "\n")
            for severity, count in stats['by_severity'].items():
                f.write(f"  {severity}: {count}\n")
            f.write("\n")

            f.write("TOP INCIDENT TYPES\n")
            f.write("-" * 70 + "\n")
            for itype, count in stats['top_types']:
                f.write(f"  {itype}: {count}\n")
            f.write("\n")

            f.write("ALL INCIDENTS\n")
            f.write("-" * 70 + "\n")
            for inc in incidents:
                f.write(f"#{inc[0]} | {inc[3]} | {inc[2]} | {inc[4]} "
                        f"[{inc[5]}] | Status: {inc[6]}\n")

        messagebox.showinfo("Export Complete", f"Full report saved to {filepath}")


# ============================================================
# RUN APPLICATION
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = DisciplinaryPortal(root)
    root.mainloop()
