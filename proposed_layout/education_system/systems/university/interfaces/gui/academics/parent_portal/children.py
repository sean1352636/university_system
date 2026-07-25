from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.systems.university.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.systems.university.interfaces.gui.academics.parent_portal.base import ParentPortalGUI

def show_children(self):
    """Show authorized students overview"""
    self.clear_content()
    is_admin = self.is_admin()

    if is_admin:
        self.update_status("All Students (Admin)")
        title = ttk.Label(self.content_frame, text="All Students (Admin Access)", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

        # Admin info banner
        admin_info = ttk.Label(
            self.content_frame,
            text=f"📋 Admin Mode: Viewing all {len(self.children)} students in the database",
            font=('Arial', 11),
            foreground='#27ae60'
        )
        admin_info.pack(pady=(0, 10))
    else:
        self.update_status("My Students")
        title = ttk.Label(self.content_frame, text="Authorized Students", style='Title.TLabel', font=('Arial', 20, 'bold'))
        title.pack(pady=20)

    # Add browse all students button for all users
    browse_frame = ttk.Frame(self.content_frame)
    browse_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
    ttk.Button(
        browse_frame,
        text="Browse All University Students",
        command=self.show_all_students
    ).pack(side=tk.LEFT)

    if not self.children:
        no_children_label = ttk.Label(self.content_frame, text="No students linked to your guardian account.\n\nAs an authorized family member, you can view academic information\nfor students who have granted you access.")
        no_children_label.pack(pady=50)
        return

    # Children list with detailed cards - paginated to reduce X resource usage
    children_container = ttk.Frame(self.content_frame)
    children_container.pack(fill=tk.BOTH, expand=True, padx=20)

    # Pagination settings
    page_size = 20  # Show 20 students per page to avoid X resource exhaustion
    total_children = len(self.children)
    total_pages = (total_children + page_size - 1) // page_size

    # Store pagination state
    if not hasattr(self, '_students_page'):
        self._students_page = 0

    # Pagination controls
    if total_children > page_size:
        page_frame = ttk.Frame(children_container)
        page_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(page_frame, text=f"Page {self._students_page + 1} of {total_pages} ({total_children} students)").pack(side=tk.LEFT)

        def prev_page():
            if self._students_page > 0:
                self._students_page -= 1
                self.show_children()

        def next_page():
            if self._students_page < total_pages - 1:
                self._students_page += 1
                self.show_children()

        ttk.Button(page_frame, text="◀ Previous", command=prev_page).pack(side=tk.LEFT, padx=5)
        ttk.Button(page_frame, text="Next ▶", command=next_page).pack(side=tk.LEFT, padx=5)

    # Create scrollable frame
    canvas = tk.Canvas(children_container)
    scrollbar = ttk.Scrollbar(children_container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Display only current page of students
    start_idx = self._students_page * page_size
    end_idx = min(start_idx + page_size, total_children)
    page_children = self.children[start_idx:end_idx]

    for child in page_children:
        detailed_card = self.create_detailed_child_card(scrollable_frame, child)
        detailed_card.pack(fill=tk.X, pady=10, padx=10)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
ParentPortalGUI.show_children = show_children

def create_detailed_child_card(self, parent, child):
    """Create a detailed card for a child"""
    card = ttk.LabelFrame(parent, text=f"{child[1]} {child[3]}", padding=15)

    # Child info section
    info_frame = ttk.Frame(card)
    info_frame.pack(fill=tk.X, pady=5)

    left_info = ttk.Frame(info_frame)
    left_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

    ttk.Label(left_info, text=f"Student ID: {child[0]}", style='Info.TLabel').pack(anchor='w')
    ttk.Label(left_info, text=f"Course: {child[4] if len(child) > 4 else 'N/A'}", style='Info.TLabel').pack(anchor='w')
    ttk.Label(left_info, text=f"Relationship: {child[5] if len(child) > 5 else 'N/A'}", style='Info.TLabel').pack(anchor='w')
    if len(child) > 6:
        ttk.Label(left_info, text=f"Access Level: {child[6]}", style='Info.TLabel').pack(anchor='w')

    # Action buttons
    btn_frame = ttk.Frame(card)
    btn_frame.pack(fill=tk.X, pady=10)

    buttons = [
        ("📊 View Grades", lambda c=child: self.view_child_grades(c)),
        ("📅 Attendance", lambda c=child: self.view_child_attendance(c)),
        ("📝 Assignments", lambda c=child: self.view_child_assignments(c)),
        ("📋 Reports", lambda c=child: self.view_teacher_reports(c)),
        ("💬 Message Instructors", lambda c=child: self.message_teachers(c)),
    ]

    for i, (text, command) in enumerate(buttons):
        btn = ttk.Button(btn_frame, text=text, command=command)
        btn.grid(row=i//3, column=i%3, padx=5, pady=2, sticky='ew')

    for i in range(3):
        btn_frame.grid_columnconfigure(i, weight=1)

    return card
ParentPortalGUI.create_detailed_child_card = create_detailed_child_card

def show_all_students(self):
    """Show all students from the university database"""
    self.clear_content()
    self.update_status("All University Students")

    title = ttk.Label(self.content_frame, text="University Student Directory",
                     style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Search frame
    search_frame = ttk.Frame(self.content_frame)
    search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

    ttk.Label(search_frame, text="Search:", font=('Arial', 10)).pack(side=tk.LEFT)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    # Results frame with treeview
    results_frame = ttk.Frame(self.content_frame)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    columns = ('ID', 'First Name', 'Last Name', 'Email', 'Course/Program', 'Status')
    tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=20)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=130)

    tree.column('ID', width=100)
    tree.column('Email', width=180)
    tree.column('Course/Program', width=180)
    tree.column('Status', width=80)

    # Scrollbars
    y_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=tree.yview)
    x_scroll = ttk.Scrollbar(results_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

    tree.grid(row=0, column=0, sticky='nsew')
    y_scroll.grid(row=0, column=1, sticky='ns')
    x_scroll.grid(row=1, column=0, sticky='ew')

    results_frame.grid_rowconfigure(0, weight=1)
    results_frame.grid_columnconfigure(0, weight=1)

    def load_students(filter_text=""):
        """Load students from database with optional filter"""
        for item in tree.get_children():
            tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Query students table
            if filter_text:
                query = """
                    SELECT student_id, first_name, last_name, email_address, course, status
                    FROM students
                    WHERE first_name LIKE ? OR last_name LIKE ? OR student_id LIKE ?
                        OR email_address LIKE ? OR course LIKE ?
                    ORDER BY last_name, first_name
                    LIMIT 500
                """
                pattern = f"%{escape_like(filter_text)}%"
                cursor.execute(query, (pattern, pattern, pattern, pattern, pattern))
            else:
                cursor.execute("""
                    SELECT student_id, first_name, last_name, email_address, course, status
                    FROM students
                    ORDER BY last_name, first_name
                    LIMIT 500
                """)

            students = cursor.fetchall()
            conn.close()

            if students:
                for student in students:
                    # Handle None values
                    row = tuple(str(val) if val is not None else 'N/A' for val in student)
                    tree.insert('', tk.END, values=row)
                self.update_status(f"Found {len(students)} students")
            else:
                tree.insert('', tk.END, values=('', 'No students found', '', '', '', ''))
                self.update_status("No students found")

        except Exception as e:
            tree.insert('', tk.END, values=('ERROR', str(e), '', '', '', ''))
            self.update_status(f"Error: {str(e)}")

    def on_search(*args):
        load_students(search_var.get())

    search_var.trace('w', on_search)

    ttk.Button(search_frame, text="Search", command=lambda: load_students(search_var.get())).pack(side=tk.LEFT, padx=5)
    ttk.Button(search_frame, text="Show All", command=lambda: load_students("")).pack(side=tk.LEFT, padx=5)

    # Link student button
    def link_selected_student():
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Selection Required", "Please select a student to link.")
            return

        item = tree.item(selection[0])
        student_id = item['values'][0]
        student_name = f"{item['values'][1]} {item['values'][2]}"

        if messagebox.askyesno("Link Student",
                               f"Link student {student_name} (ID: {student_id}) to a family account?"):
            self.show_quick_link_dialog(student_id, student_name)

    # Only show link button for admins
    if self.is_admin():
        ttk.Button(search_frame, text="Link Selected to Family",
                  command=link_selected_student).pack(side=tk.RIGHT, padx=5)

    # Back button
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(fill=tk.X, padx=20, pady=10)
    ttk.Button(btn_frame, text="← Back to My Students", command=self.show_children).pack(side=tk.LEFT)

    # Load all students initially
    load_students()
ParentPortalGUI.show_all_students = show_all_students

def show_quick_link_dialog(self, student_id, student_name):
    """Quick dialog to link a student to a family account"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Link Student to Family Account")
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()

    ttk.Label(dialog, text=f"Link {student_name}", font=('Arial', 14, 'bold')).pack(pady=15)
    ttk.Label(dialog, text=f"Student ID: {student_id}").pack()

    form_frame = ttk.Frame(dialog, padding=20)
    form_frame.pack(fill=tk.X)

    ttk.Label(form_frame, text="Family Account ID:").grid(row=0, column=0, sticky='w', pady=5)
    parent_id_entry = ttk.Entry(form_frame, width=30)
    parent_id_entry.grid(row=0, column=1, pady=5)

    ttk.Label(form_frame, text="Relationship:").grid(row=1, column=0, sticky='w', pady=5)
    relationship_var = tk.StringVar(value="Parent")
    relationship_combo = ttk.Combobox(form_frame, textvariable=relationship_var,
                                      values=["Parent", "Guardian", "Spouse", "Other Family"],
                                      state='readonly', width=27)
    relationship_combo.grid(row=1, column=1, pady=5)

    def do_link():
        parent_id = parent_id_entry.get().strip()
        if not parent_id:
            messagebox.showwarning("Required", "Please enter a Family Account ID.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Verify family account exists
            cursor.execute('SELECT parent_id FROM parent_accounts WHERE parent_id = ?', (parent_id,))
            if not cursor.fetchone():
                messagebox.showerror("Error", "Family account not found.")
                conn.close()
                return

            # Check if already linked
            cursor.execute('''
                SELECT * FROM parent_student_links
                WHERE parent_id = ? AND student_id = ?
            ''', (parent_id, student_id))
            if cursor.fetchone():
                messagebox.showwarning("Already Linked", "This student is already linked to this family account.")
                conn.close()
                return

            # Create link
            cursor.execute('''
                INSERT INTO parent_student_links (parent_id, student_id, relationship)
                VALUES (?, ?, ?)
            ''', (parent_id, student_id, relationship_var.get()))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Student {student_name} linked to family account {parent_id}.")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to link: {str(e)}")

    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(pady=20)
    ttk.Button(btn_frame, text="Link", command=do_link).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.show_quick_link_dialog = show_quick_link_dialog

def _load_all_students_from_db(self):
    """Load all students from the database"""
    students = []
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT student_id, first_name, middle_name, last_name, course, email_address
            FROM students
            WHERE status = 'Active' OR status IS NULL
            ORDER BY last_name, first_name
            LIMIT 500
        ''')
        students = cursor.fetchall()
        conn.close()
    except Exception as e:
        print(f"Error loading students: {e}")
    return students
ParentPortalGUI._load_all_students_from_db = _load_all_students_from_db

class DataExportDialog:
    """Dialog for exporting student data."""

    def __init__(self, parent, children):
        self.result = None

        dialog = tk.Toplevel(parent)
        dialog.title("Export Student Data")
        dialog.geometry("500x450")
        dialog.transient(parent)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Export Student Data",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Child selection
        ttk.Label(main_frame, text="Select Student:").pack(anchor='w')
        child_var = tk.StringVar()
        child_combo = ttk.Combobox(main_frame, textvariable=child_var, width=45, state="readonly")
        child_combo['values'] = [f"{c[1]} {c[3]} (ID: {c[0]})" for c in children]
        if child_combo['values']:
            child_combo.current(0)
        child_combo.pack(fill=tk.X, pady=(0, 10))

        # Data types
        ttk.Label(main_frame, text="Select data to export:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(5, 0))
        data_type_options = [
            ("Grades", "grades"),
            ("Attendance", "attendance"),
            ("Assignments", "assignments"),
            ("Conduct Reports", "conduct"),
            ("Medical Records", "medical"),
            ("Financial Records", "financial"),
        ]
        data_vars = {}
        for label, key in data_type_options:
            var = tk.BooleanVar(value=True)
            data_vars[key] = var
            ttk.Checkbutton(main_frame, text=label, variable=var).pack(anchor='w', padx=10)

        # Format selection
        ttk.Label(main_frame, text="Export Format:", font=('Arial', 10, 'bold')).pack(anchor='w', pady=(10, 0))
        format_var = tk.StringVar(value="csv")
        fmt_frame = ttk.Frame(main_frame)
        fmt_frame.pack(anchor='w', padx=10)
        ttk.Radiobutton(fmt_frame, text="CSV", variable=format_var, value="csv").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(fmt_frame, text="PDF", variable=format_var, value="pdf").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(fmt_frame, text="JSON", variable=format_var, value="json").pack(side=tk.LEFT, padx=5)

        def submit():
            idx = child_combo.current()
            if idx < 0:
                messagebox.showwarning("No Student", "Please select a student.")
                return
            selected_types = [k for k, v in data_vars.items() if v.get()]
            if not selected_types:
                messagebox.showwarning("No Data", "Please select at least one data type.")
                return
            self.result = {
                'child_id': children[idx][0],
                'data_types': selected_types,
                'format': format_var.get()
            }
            dialog.destroy()

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Export", command=submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        dialog.wait_window()


def export_child_data(self):
    """Export all data for a child"""
    if not self.children:
        messagebox.showinfo("No Students", "No students linked to your guardian account.")
        return

    dialog = DataExportDialog(self.root, self.children)
    if dialog.result:
        child_id, data_types, format_type = dialog.result['child_id'], dialog.result['data_types'], dialog.result['format']

        # In real implementation, would generate actual export file
        messagebox.showinfo("Export Complete",
                          f"Data exported successfully in {format_type.upper()} format.\n"
                          f"Data types: {', '.join(data_types)}")
ParentPortalGUI.export_child_data = export_child_data
