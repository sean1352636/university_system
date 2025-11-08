"""Assignment CRUD operations and management"""

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
from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.shared.constants import paths
from collections import deque



class AssignmentManager:
    """Assignment CRUD operations and management"""

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
        except:
            return self.auth.user_role in ['Admin', 'Faculty']

    def load_modules_for_filter(self, combo):
        """Load modules for filtering"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()

            module_list = ["All Modules"] + [f"{code} - {name}" for code, name in modules]
            combo['values'] = module_list
            combo.set("All Modules")

            conn.close()

        except Exception as e:
            print(f"Error loading modules: {e}")

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
                   s.status, s.grade, s.feedback, s.is_late, s.late_days
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
    

    def show_manage_assignments(self):
        """Show assignment management interface"""
        if not self._check_permission('manage_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Manage Assignments", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Filter and search frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Filters & Search", padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))
        
        # Module filter
        ttk.Label(filter_frame, text="Module:").grid(row=0, column=0, sticky='w', padx=5)
        self.manage_module_filter_var = tk.StringVar()
        module_combo = ttk.Combobox(filter_frame, textvariable=self.manage_module_filter_var, width=20)
        module_combo.grid(row=0, column=1, padx=5)
        self.load_modules_for_filter(module_combo)
        
        # Status filter
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, sticky='w', padx=5)
        self.manage_status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.manage_status_filter_var,
                                   values=["All", "Active", "Inactive", "Upcoming", "Overdue"], width=15)
        status_combo.grid(row=0, column=3, padx=5)
        
        # Search
        ttk.Label(filter_frame, text="Search:").grid(row=0, column=4, sticky='w', padx=5)
        self.manage_search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=self.manage_search_var, width=20)
        search_entry.grid(row=0, column=5, padx=5)
        
        # Apply filter button
        ttk.Button(filter_frame, text="Apply Filters", 
                  command=self.load_managed_assignments).grid(row=0, column=6, padx=10)
        
        # Assignments table
        assignments_frame = ttk.Frame(self.gui.layout.content_area)
        assignments_frame.pack(fill='both', expand=True)
        
        columns = ('ID', 'Title', 'Module', 'Type', 'Due Date', 'Submissions', 'Status')
        self.manage_assignments_tree = ttk.Treeview(assignments_frame, columns=columns, show='headings')
        
        for col in columns:
            self.manage_assignments_tree.heading(col, text=col)
            self.manage_assignments_tree.column(col, width=100)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(assignments_frame, orient='vertical', command=self.manage_assignments_tree.yview)
        h_scroll = ttk.Scrollbar(assignments_frame, orient='horizontal', command=self.manage_assignments_tree.xview)
        self.manage_assignments_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.manage_assignments_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        assignments_frame.grid_rowconfigure(0, weight=1)
        assignments_frame.grid_columnconfigure(0, weight=1)
        
        # Action buttons - Row 1
        action_frame = ttk.Frame(self.gui.layout.content_area)
        action_frame.pack(fill='x', pady=(10, 0))
    
        ttk.Label(action_frame, text="Single Assignment Actions:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))
    
        ttk.Button(action_frame, text="Edit Assignment",
                  command=self.edit_selected_assignment).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Clone",
                  command=self.duplicate_selected_assignment).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Toggle Status",
                  command=self.toggle_assignment_status).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="View Submissions",
                  command=self.view_assignment_submissions).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Export Data",
                  command=self.export_assignment_data).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Download All",
                  command=self.download_all_submissions).pack(side='left', padx=(0, 5))
    
        # Action buttons - Row 2: Bulk Operations
        bulk_frame = ttk.Frame(self.gui.layout.content_area)
        bulk_frame.pack(fill='x', pady=(5, 0))
    
        ttk.Label(bulk_frame, text="Bulk Actions:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))
    
        ttk.Button(bulk_frame, text="Archive Selected",
                  command=self.bulk_archive_assignments).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text="Delete Selected",
                  command=self.bulk_delete_assignments).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text="Change Due Dates",
                  command=self.bulk_change_due_dates).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text="Export Selected",
                  command=self.bulk_export_assignments).pack(side='left', padx=(0, 5))
        ttk.Button(bulk_frame, text="Send Reminders",
                  command=self.bulk_send_reminders).pack(side='left', padx=(0, 5))
    
        # Statistics button
        ttk.Button(bulk_frame, text="View Statistics",
                  command=self.show_assignment_statistics).pack(side='right', padx=(0, 5))
        
        # Assignment details frame
        self.assignment_details_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Assignment Details", padding=10)
        self.assignment_details_frame.pack(fill='x', pady=(10, 0))
        
        # Load assignments
        self.load_managed_assignments()
    

    def load_managed_assignments(self):
        """Load assignments for management"""
        # Clear existing data
        for item in self.manage_assignments_tree.get_children():
            self.manage_assignments_tree.delete(item)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Build query based on filters
            query = '''
            SELECT a.id, a.title, a.module_code, a.assignment_type, a.due_date,
                   COUNT(s.id) as submission_count,
                   CASE 
                       WHEN a.is_active = 0 THEN 'Inactive'
                       WHEN a.due_date < datetime('now') THEN 'Overdue'
                       WHEN a.due_date > datetime('now', '+7 days') THEN 'Upcoming'
                       ELSE 'Active'
                   END as status
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            '''
            
            conditions = []
            params = []
            
            # Apply filters
            module_filter = self.manage_module_filter_var.get()
            if module_filter and module_filter != "All Modules":
                module_code = module_filter.split(' - ')[0]
                conditions.append("a.module_code = ?")
                params.append(module_code)
            
            status_filter = self.manage_status_filter_var.get()
            if status_filter != "All":
                if status_filter == "Active":
                    conditions.append("a.is_active = 1 AND a.due_date >= datetime('now')")
                elif status_filter == "Inactive":
                    conditions.append("a.is_active = 0")
                elif status_filter == "Upcoming":
                    conditions.append("a.due_date > datetime('now', '+7 days')")
                elif status_filter == "Overdue":
                    conditions.append("a.due_date < datetime('now') AND a.is_active = 1")
            
            search_term = self.manage_search_var.get().strip()
            if search_term:
                conditions.append("(a.title LIKE ? OR a.description LIKE ?)")
                params.extend([f"%{search_term}%", f"%{search_term}%"])
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " GROUP BY a.id ORDER BY a.due_date DESC"
            
            cursor.execute(query, params)
            assignments = cursor.fetchall()
            
            for assignment in assignments:
                aid, title, module, atype, due_date, submissions, status = assignment
                
                # Color coding
                tags = []
                if status == 'Inactive':
                    tags = ['inactive']
                elif status == 'Overdue':
                    tags = ['overdue']
                elif status == 'Upcoming':
                    tags = ['upcoming']
                
                self.manage_assignments_tree.insert('', 'end', 
                                                   values=(aid, title, module, atype, due_date, submissions, status),
                                                   tags=tags)
            
            # Configure tags
            self.manage_assignments_tree.tag_configure('inactive', background='#f5f5f5', foreground='#666666')
            self.manage_assignments_tree.tag_configure('overdue', background='#ffebee')
            self.manage_assignments_tree.tag_configure('upcoming', background='#e3f2fd')
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")
    

    def on_manage_assignment_select(self, event):
        """Handle assignment selection in management view"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            return
        
        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        
        self.show_assignment_management_details(assignment_id)
    

    def show_assignment_management_details(self, assignment_id):
        """Show detailed assignment information for management"""
        # Clear existing details
        for widget in self.assignment_details_frame.winfo_children():
            widget.destroy()
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.*, m.module_name,
                   COUNT(s.id) as total_submissions,
                   COUNT(CASE WHEN s.grade IS NOT NULL THEN 1 END) as graded_submissions,
                   COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) as late_submissions,
                   AVG(s.grade) as avg_grade
            FROM assignments a
            JOIN modules m ON a.module_code = m.module_code
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE a.id = ?
            GROUP BY a.id
            ''', (assignment_id,))
            
            assignment = cursor.fetchone()
            if not assignment:
                return
            
            # Create details display
            details_notebook = ttk.Notebook(self.assignment_details_frame)
            details_notebook.pack(fill='both', expand=True)
            
            # Basic info tab
            basic_frame = ttk.Frame(details_notebook)
            details_notebook.add(basic_frame, text="Basic Info")

            # Display basic info
            ttk.Label(basic_frame, text=f"Title: {assignment[2]}").pack(pady=5)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignment details: {e}")

    def edit_selected_assignment(self):
        """Edit the selected assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to edit")
            return

        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]

        try:
            # Fetch assignment data
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            assignment = cursor.fetchone()
            conn.close()

            if not assignment:
                messagebox.showerror("Error", "Assignment not found")
                return

            # Create edit window
            edit_window = tk.Toplevel(self.root)
            edit_window.title(f"Edit Assignment - {assignment['title']}")
            edit_window.geometry("700x700")
            edit_window.transient(self.root)
            edit_window.grab_set()

            # Scrollable frame
            canvas = tk.Canvas(edit_window)
            scrollbar = ttk.Scrollbar(edit_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Form fields
            form_frame = ttk.LabelFrame(scrollable_frame, text="Assignment Details", padding=20)
            form_frame.pack(fill='x', padx=10, pady=10)

            # Title
            ttk.Label(form_frame, text="Title:").grid(row=0, column=0, sticky='w', pady=5)
            title_var = tk.StringVar(value=assignment['title'])
            ttk.Entry(form_frame, textvariable=title_var, width=50).grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

            # Module
            ttk.Label(form_frame, text="Module:").grid(row=1, column=0, sticky='w', pady=5)
            module_var = tk.StringVar(value=assignment['module_code'])
            ttk.Label(form_frame, text=assignment['module_code']).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))

            # Due Date
            ttk.Label(form_frame, text="Due Date (YYYY-MM-DD HH:MM):").grid(row=2, column=0, sticky='w', pady=5)
            due_var = tk.StringVar(value=assignment['due_date'])
            ttk.Entry(form_frame, textvariable=due_var, width=30).grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))

            # Max Marks
            ttk.Label(form_frame, text="Max Marks:").grid(row=3, column=0, sticky='w', pady=5)
            marks_var = tk.StringVar(value=str(assignment['max_marks']))
            ttk.Entry(form_frame, textvariable=marks_var, width=10).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))

            # Description
            ttk.Label(form_frame, text="Description:").grid(row=4, column=0, sticky='nw', pady=5)
            desc_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
            desc_text.grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 0))
            desc_text.insert('1.0', assignment['description'] or '')

            # Instructions
            ttk.Label(form_frame, text="Instructions:").grid(row=5, column=0, sticky='nw', pady=5)
            instr_text = scrolledtext.ScrolledText(form_frame, height=5, width=50)
            instr_text.grid(row=5, column=1, sticky='ew', pady=5, padx=(10, 0))
            instr_text.insert('1.0', assignment.get('instructions', ''))

            # Assignment Type
            ttk.Label(form_frame, text="Type:").grid(row=6, column=0, sticky='w', pady=5)
            type_var = tk.StringVar(value=assignment.get('assignment_type', 'individual'))
            type_combo = ttk.Combobox(form_frame, textvariable=type_var,
                                     values=['individual', 'group'], state='readonly', width=15)
            type_combo.grid(row=6, column=1, sticky='w', pady=5, padx=(10, 0))

            form_frame.grid_columnconfigure(1, weight=1)

            def save_changes():
                try:
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    cursor.execute('''
                    UPDATE assignments
                    SET title = ?, due_date = ?, max_marks = ?, description = ?,
                        instructions = ?, assignment_type = ?, updated_at = datetime('now')
                    WHERE id = ?
                    ''', (
                        title_var.get().strip(),
                        due_var.get().strip(),
                        int(marks_var.get()),
                        desc_text.get('1.0', tk.END).strip(),
                        instr_text.get('1.0', tk.END).strip(),
                        type_var.get(),
                        assignment_id
                    ))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", "Assignment updated successfully")
                    edit_window.destroy()
                    self.load_managed_assignments()

                except ValueError:
                    messagebox.showerror("Error", "Max marks must be a valid number")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update assignment: {e}")

            # Buttons
            button_frame = ttk.Frame(scrollable_frame)
            button_frame.pack(fill='x', padx=10, pady=10)
            ttk.Button(button_frame, text="Save Changes", command=save_changes,
                      style='Accent.TButton').pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=edit_window.destroy).pack(side='right', padx=5)

            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open edit window: {e}")


    def duplicate_selected_assignment(self):
        """Duplicate the selected assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to duplicate")
            return
        
        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")

            # Get original assignment with named columns
            cursor.execute('SELECT * FROM assignments WHERE id = ?', (assignment_id,))
            original = cursor.fetchone()

            if not original:
                messagebox.showerror("Error", "Assignment not found")
                conn.close()
                return

            # Create duplicate
            new_title = f"{original['title']} (Copy)"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO assignments
            (module_code, title, description, instructions, due_date, max_marks,
             file_types_allowed, max_file_size_mb, assignment_type,
             group_size_min, group_size_max, allow_late_submission,
             late_penalty_per_day, auto_release_grades, peer_review_enabled,
             rubric_id, is_active, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                original['module_code'], new_title, original['description'],
                original.get('instructions', ''), original['due_date'],
                original['max_marks'], original.get('file_types_allowed', ''),
                original.get('max_file_size_mb', 10), original.get('assignment_type', 'individual'),
                original.get('group_size_min', 1), original.get('group_size_max', 1),
                original.get('allow_late_submission', 1), original.get('late_penalty_per_day', 0),
                original.get('auto_release_grades', 0), original.get('peer_review_enabled', 0),
                original.get('rubric_id'), 1, self.auth.current_user['id'],
                timestamp, timestamp
            ))

            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON")
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", f"Assignment duplicated as '{new_title}'")
            self.load_managed_assignments()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate assignment: {e}")
    

    def toggle_assignment_status(self):
        """Toggle assignment active/inactive status"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment")
            return
        
        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get current status
            cursor.execute('SELECT is_active FROM assignments WHERE id = ?', (assignment_id,))
            current_status = cursor.fetchone()[0]
            
            new_status = 0 if current_status else 1
            action = "activate" if new_status else "deactivate"
            
            if messagebox.askyesno("Confirm", f"Are you sure you want to {action} '{assignment_title}'?"):
                cursor.execute('UPDATE assignments SET is_active = ? WHERE id = ?', (new_status, assignment_id))
                conn.commit()
                
                messagebox.showinfo("Success", f"Assignment {action}d successfully")
                self.load_managed_assignments()
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle status: {e}")
    

    def view_assignment_submissions(self):
        """View submissions for selected assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment")
            return
        
        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        
        # Switch to submissions view with filter
        self.show_assignment_specific_submissions(assignment_id)
    

    def show_assignment_specific_submissions(self, assignment_id):
        """Show submissions for a specific assignment"""
        self.gui.layout.clear_content_area()
        
        # Get assignment title
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT title FROM assignments WHERE id = ?', (assignment_id,))
            assignment_title = cursor.fetchone()[0]
            conn.close()
        except:
            assignment_title = "Unknown Assignment"
        
        title = ttk.Label(self.gui.layout.content_area, text=f"Submissions: {assignment_title}", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Submissions table
        submissions_frame = ttk.Frame(self.gui.layout.content_area)
        submissions_frame.pack(fill='both', expand=True)
        
        columns = ('ID', 'Student', 'Submitted', 'Status', 'Grade', 'Late')
        submissions_tree = ttk.Treeview(submissions_frame, columns=columns, show='headings')
        
        for col in columns:
            submissions_tree.heading(col, text=col)
            submissions_tree.column(col, width=120)
        
        submissions_tree.pack(fill='both', expand=True)
        
        # Load submissions for this assignment
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT s.id, st.first_name, st.last_name, s.submission_date, s.status,
                   CASE WHEN s.grade IS NULL THEN 'Not Graded' ELSE CAST(s.grade AS TEXT) || '%' END,
                   CASE WHEN s.late_submission = 1 THEN 'Yes' ELSE 'No' END
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.student_id
            WHERE s.assignment_id = ?
            ORDER BY s.submission_date DESC
            ''', (assignment_id,))
            
            submissions = cursor.fetchall()
            
            for submission in submissions:
                sid, fname, lname, date, status, grade, late = submission
                student_name = f"{fname} {lname}"
                
                tags = []
                if late == 'Yes':
                    tags = ['late']
                elif grade != 'Not Graded':
                    tags = ['graded']
                
                submissions_tree.insert('', 'end', values=(sid, student_name, date, status, grade, late), tags=tags)
            
            submissions_tree.tag_configure('late', background='#ffebee')
            submissions_tree.tag_configure('graded', background='#e8f5e8')
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")
        
        # Back button
        ttk.Button(self.gui.layout.content_area, text="Back to Manage Assignments", 
                  command=self.show_manage_assignments).pack(pady=(10, 0))
    

    def export_assignment_data(self):
        """Export assignment data"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to export")
            return
        
        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]
        
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile=f"{assignment_title.replace(' ', '_')}_data.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not save_path:
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT st.student_id, st.first_name, st.last_name, s.submission_date,
                   s.status, s.grade, s.late_submission, s.late_days, s.feedback
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.student_id
            WHERE s.assignment_id = ?
            ORDER BY st.last_name, st.first_name
            ''', (assignment_id,))
            
            data = cursor.fetchall()
            
            import csv
            with open(save_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Student ID', 'First Name', 'Last Name', 'Submission Date', 
                               'Status', 'Grade', 'Late Submission', 'Late Days', 'Feedback'])
                writer.writerows(data)
            
            conn.close()
            messagebox.showinfo("Success", f"Assignment data exported to: {save_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data: {e}")
    

    def send_assignment_email_reminders(self):
        """Send email reminders for assignment"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment to send reminders for")
            return
    
        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]
        assignment_due_date = item['values'][3]
    
        # Create email reminder dialog
        email_window = tk.Toplevel(self.root)
        email_window.title(f"Email Reminders - {assignment_title}")
        email_window.geometry("600x500")
        email_window.transient(self.root)
        email_window.grab_set()
    
        # Email options frame
        options_frame = ttk.LabelFrame(email_window, text="Email Options", padding=10)
        options_frame.pack(fill='x', padx=10, pady=10)
    
        # Email type selection
        email_type_var = tk.StringVar(value="upcoming")
        ttk.Label(options_frame, text="Email Type:").grid(row=0, column=0, sticky='w', padx=(0, 10))
    
        email_types = [
            ("upcoming", "Upcoming Assignment Reminder"),
            ("overdue", "Overdue Assignment Notice"),
            ("new", "New Assignment Notification"),
            ("custom", "Custom Message")
        ]
    
        for i, (value, text) in enumerate(email_types):
            ttk.Radiobutton(options_frame, text=text, variable=email_type_var,
                           value=value).grid(row=i+1, column=0, sticky='w', padx=(20, 0))
    
        # Recipient selection
        recipient_frame = ttk.LabelFrame(email_window, text="Recipients", padding=10)
        recipient_frame.pack(fill='x', padx=10, pady=10)
    
        recipient_var = tk.StringVar(value="enrolled")
        recipient_options = [
            ("enrolled", "All Enrolled Students"),
            ("not_submitted", "Students Who Haven't Submitted"),
            ("late_submissions", "Students with Late Submissions"),
            ("custom", "Custom Recipients")
        ]
    
        for i, (value, text) in enumerate(recipient_options):
            ttk.Radiobutton(recipient_frame, text=text, variable=recipient_var,
                           value=value).grid(row=i, column=0, sticky='w')
    
        # Message frame
        message_frame = ttk.LabelFrame(email_window, text="Message", padding=10)
        message_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        # Subject line
        ttk.Label(message_frame, text="Subject:").pack(anchor='w')
        subject_var = tk.StringVar(value=f"Reminder: {assignment_title}")
        subject_entry = ttk.Entry(message_frame, textvariable=subject_var, width=70)
        subject_entry.pack(fill='x', pady=(0, 10))
    
        # Message body
        ttk.Label(message_frame, text="Message:").pack(anchor='w')
        message_text = scrolledtext.ScrolledText(message_frame, height=10, width=70)
        message_text.pack(fill='both', expand=True)
    
        # Default message based on type
        def update_default_message(*args):
            email_type = email_type_var.get()
            template_map = {
                "upcoming": "assignment_reminder_upcoming",
                "overdue": "assignment_reminder_overdue",
                "new": "assignment_new"
            }
    
            if email_type in template_map:
                try:
                    from university_system.infrastructure.email.template_utils import render_template
                    _, default_message = render_template(template_map[email_type], {
                        "assignment_title": assignment_title,
                        "assignment_due_date": assignment_due_date
                    })
                except:
                    default_message = ""
            else:
                default_message = f"Dear Student,\n\nRegarding assignment: {assignment_title}\nDue Date: {assignment_due_date}\n\n[Enter your custom message here]\n\nBest regards,\nAcademic Team"
    
            message_text.delete('1.0', tk.END)
            message_text.insert('1.0', default_message)
    
        email_type_var.trace('w', update_default_message)
        update_default_message()  # Set initial message
    
        # Buttons frame
        buttons_frame = ttk.Frame(email_window)
        buttons_frame.pack(fill='x', padx=10, pady=10)
    
        def send_emails():
            """Send the email reminders"""
            try:
                email_type = email_type_var.get()
                recipient_type = recipient_var.get()
                subject = subject_var.get().strip()
                message = message_text.get('1.0', tk.END).strip()
    
                if not subject or not message:
                    messagebox.showwarning("Warning", "Please enter both subject and message")
                    return
    
                # Get recipient list based on selection
                recipients = self._get_assignment_email_recipients(assignment_id, recipient_type)
    
                if not recipients:
                    messagebox.showinfo("Info", "No recipients found for the selected criteria")
                    return
    
                # Try to open email GUI if available
                success = self._send_assignment_emails_via_gui(recipients, subject, message, assignment_title)
    
                if success:
                    email_window.destroy()
                    messagebox.showinfo("Success", f"Email reminders sent to {len(recipients)} recipients")
                else:
                    # Fallback: show email details for manual sending
                    self._show_email_fallback_dialog(recipients, subject, message)
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send emails: {e}")
    
        def preview_recipients():
            """Preview the list of recipients"""
            try:
                recipient_type = recipient_var.get()
                recipients = self._get_assignment_email_recipients(assignment_id, recipient_type)
    
                preview_window = tk.Toplevel(email_window)
                preview_window.title("Email Recipients Preview")
                preview_window.geometry("500x400")
                preview_window.transient(email_window)
    
                ttk.Label(preview_window, text=f"Recipients ({len(recipients)}):").pack(anchor='w', padx=10, pady=10)
    
                recipients_list = tk.Listbox(preview_window, height=20)
                recipients_list.pack(fill='both', expand=True, padx=10, pady=(0, 10))
    
                for recipient in recipients:
                    recipients_list.insert(tk.END, f"{recipient['name']} ({recipient['email']})")
    
                ttk.Button(preview_window, text="Close",
                          command=preview_window.destroy).pack(pady=10)
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to preview recipients: {e}")
    
        ttk.Button(buttons_frame, text="Preview Recipients",
                  command=preview_recipients).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Send Emails",
                  command=send_emails).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Cancel",
                  command=email_window.destroy).pack(side='right')
    

    def _get_assignment_email_recipients(self, assignment_id, recipient_type):
        """Get email recipients based on criteria"""
        recipients = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            if recipient_type == "enrolled":
                # All students enrolled in the module
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN student_enrollments se ON s.student_id = se.student_id
                JOIN assignments a ON se.module_code = a.module_code
                WHERE a.id = ? AND s.email IS NOT NULL AND s.email != ''
                ''', (assignment_id,))
    
            elif recipient_type == "not_submitted":
                # Students who haven't submitted
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN student_enrollments se ON s.student_id = se.student_id
                JOIN assignments a ON se.module_code = a.module_code
                LEFT JOIN assignment_submissions sub ON s.student_id = sub.student_id AND a.id = sub.assignment_id
                WHERE a.id = ? AND sub.id IS NULL AND s.email IS NOT NULL AND s.email != ''
                ''', (assignment_id,))
    
            elif recipient_type == "late_submissions":
                # Students with late submissions
                cursor.execute('''
                SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email
                FROM students s
                JOIN assignment_submissions sub ON s.student_id = sub.student_id
                WHERE sub.assignment_id = ? AND sub.late_submission = 1 AND s.email IS NOT NULL AND s.email != ''
                ''', (assignment_id,))
    
            for row in cursor.fetchall():
                recipients.append({
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}",
                    'email': row[3]
                })
    
            conn.close()
    
        except Exception as e:
            print(f"Error getting recipients: {e}")
    
        return recipients
    

    def _send_assignment_emails_via_gui(self, recipients, subject, message, assignment_title):
        """Try to send emails via email GUI"""
        try:
            # Try to import and use email GUI
            from university_system.infrastructure.email.gui.email_manager_gui import EmailGUI
    
            # Create email GUI instance
            email_gui = EmailGUI(self.root, self.auth)
    
            # Prepare recipient list
            recipient_emails = [r['email'] for r in recipients]
    
            # Send emails through email GUI
            for recipient in recipients:
                personalized_message = message.replace("[Student Name]", recipient['name'])
                email_gui.send_email(
                    to_email=recipient['email'],
                    subject=subject,
                    message=personalized_message
                )
    
            return True
    
        except ImportError:
            return False
        except Exception as e:
            print(f"Error sending emails via GUI: {e}")
            return False
    

    def _show_email_fallback_dialog(self, recipients, subject, message):
        """Show fallback dialog with email details for manual sending"""
        fallback_window = tk.Toplevel(self.root)
        fallback_window.title("Email Details - Manual Send")
        fallback_window.geometry("700x500")
        fallback_window.transient(self.root)
    
        ttk.Label(fallback_window, text="Email GUI not available. Please send manually:",
                 font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=10)
    
        # Email details
        details_frame = ttk.LabelFrame(fallback_window, text="Email Details", padding=10)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        details_text = scrolledtext.ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)
    
        email_details = f"Subject: {subject}\n\n"
        email_details += f"Recipients ({len(recipients)}):\n"
        for recipient in recipients:
            email_details += f"  - {recipient['name']} ({recipient['email']})\n"
        email_details += f"\nMessage:\n{message}"
    
        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')
    
        ttk.Button(fallback_window, text="Close",
                  command=fallback_window.destroy).pack(pady=10)
    
    # Bulk Operations Methods

    def download_all_submissions(self):
        """Download all submissions for selected assignment as ZIP"""
        selection = self.manage_assignments_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select an assignment")
            return
    
        item = self.manage_assignments_tree.item(selection[0])
        assignment_id = item['values'][0]
        assignment_title = item['values'][1]
    
        try:
            # Ask for save location
            save_path = filedialog.asksaveasfilename(
                defaultextension=".zip",
                initialfile=f"{assignment_title.replace(' ', '_')}_submissions.zip",
                filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
            )
    
            if not save_path:
                return
    
            import zipfile
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT s.id, st.student_id, st.first_name, st.last_name, s.file_path
            FROM assignment_submissions s
            JOIN students st ON s.student_id = st.student_id
            WHERE s.assignment_id = ? AND s.file_path IS NOT NULL
            ''', (assignment_id,))
    
            submissions = cursor.fetchall()
            conn.close()
    
            if not submissions:
                messagebox.showinfo("No Submissions", "No submissions with files found for this assignment")
                return
    
            # Create ZIP file
            with zipfile.ZipFile(save_path, 'w') as zipf:
                for submission in submissions:
                    sub_id, student_id, fname, lname, file_path = submission
                    if file_path and os.path.exists(file_path):
                        # Create friendly filename
                        filename = f"{lname}_{fname}_{student_id}_{os.path.basename(file_path)}"
                        zipf.write(file_path, filename)
    
            messagebox.showinfo("Success", f"Downloaded {len(submissions)} submissions to:\n{save_path}")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download submissions: {e}")
    

    def bulk_archive_assignments(self):
        """Archive multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to archive")
            return
    
        if not messagebox.askyesno("Confirm", f"Archive {len(selections)} assignment(s)?"):
            return
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Ensure archived column exists
            cursor.execute("PRAGMA table_info(assignments)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'archived' not in columns:
                cursor.execute("ALTER TABLE assignments ADD COLUMN archived INTEGER DEFAULT 0")
    
            for selection in selections:
                item = self.manage_assignments_tree.item(selection)
                assignment_id = item['values'][0]
                cursor.execute("UPDATE assignments SET archived = 1, is_active = 0 WHERE id = ?",
                             (assignment_id,))
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", f"Archived {len(selections)} assignment(s)")
            self.load_managed_assignments()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to archive assignments: {e}")
    

    def bulk_delete_assignments(self):
        """Delete multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to delete")
            return
    
        if not messagebox.askyesno("Confirm Delete",
                                   f"Permanently delete {len(selections)} assignment(s)?\n\nThis will also delete all submissions!"):
            return
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            for selection in selections:
                item = self.manage_assignments_tree.item(selection)
                assignment_id = item['values'][0]
    
                # Delete submissions first
                cursor.execute("DELETE FROM assignment_submissions WHERE assignment_id = ?", (assignment_id,))
                # Delete assignment
                cursor.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", f"Deleted {len(selections)} assignment(s)")
            self.load_managed_assignments()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete assignments: {e}")
    

    def bulk_change_due_dates(self):
        """Change due dates for multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to change due dates")
            return
    
        # Create dialog for date change
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Due Dates")
        dialog.geometry("400x300")
        dialog.transient(self.root)
    
        ttk.Label(dialog, text=f"Change due dates for {len(selections)} assignment(s)",
                 font=('TkDefaultFont', 11, 'bold')).pack(pady=10)
    
        # Method selection
        method_frame = ttk.LabelFrame(dialog, text="Change Method", padding=10)
        method_frame.pack(fill='x', padx=10, pady=10)
    
        method_var = tk.StringVar(value="extend")
        ttk.Radiobutton(method_frame, text="Extend by days", variable=method_var,
                       value="extend").pack(anchor='w')
        ttk.Radiobutton(method_frame, text="Set specific date", variable=method_var,
                       value="specific").pack(anchor='w')
    
        # Days to extend
        extend_frame = ttk.Frame(method_frame)
        extend_frame.pack(fill='x', pady=5)
        ttk.Label(extend_frame, text="Days to extend:").pack(side='left')
        days_var = tk.StringVar(value="7")
        ttk.Entry(extend_frame, textvariable=days_var, width=10).pack(side='left', padx=(10, 0))
    
        # Specific date
        specific_frame = ttk.Frame(method_frame)
        specific_frame.pack(fill='x', pady=5)
        ttk.Label(specific_frame, text="New date (YYYY-MM-DD):").pack(side='left')
        date_var = tk.StringVar()
        ttk.Entry(specific_frame, textvariable=date_var, width=15).pack(side='left', padx=(10, 0))
    
        def apply_changes():
            try:
                method = method_var.get()
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
    
                for selection in selections:
                    item = self.manage_assignments_tree.item(selection)
                    assignment_id = item['values'][0]
    
                    if method == "extend":
                        days = int(days_var.get())
                        cursor.execute('''
                        UPDATE assignments
                        SET due_date = datetime(due_date, '+' || ? || ' days')
                        WHERE id = ?
                        ''', (days, assignment_id))
                    else:
                        new_date = date_var.get()
                        # Validate date format
                        datetime.strptime(new_date, "%Y-%m-%d")
                        cursor.execute("UPDATE assignments SET due_date = ? WHERE id = ?",
                                     (new_date, assignment_id))
    
                conn.commit()
                conn.close()
    
                dialog.destroy()
                messagebox.showinfo("Success", "Due dates updated successfully")
                self.load_managed_assignments()
    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to change due dates: {e}")
    
        ttk.Button(dialog, text="Apply Changes", command=apply_changes).pack(pady=10)
        ttk.Button(dialog, text="Cancel", command=dialog.destroy).pack()
    

    def bulk_export_assignments(self):
        """Export data for multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to export")
            return
    
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile="bulk_assignments_export.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
    
            if not save_path:
                return
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            all_data = []
            for selection in selections:
                item = self.manage_assignments_tree.item(selection)
                assignment_id = item['values'][0]
    
                cursor.execute('''
                SELECT a.title, a.module_code, st.student_id, st.first_name, st.last_name,
                       s.submission_date, s.status, s.grade, s.late_submission
                FROM assignments a
                LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
                LEFT JOIN students st ON s.student_id = st.student_id
                WHERE a.id = ?
                ORDER BY a.title, st.last_name, st.first_name
                ''', (assignment_id,))
    
                all_data.extend(cursor.fetchall())
    
            conn.close()
    
            # Write to CSV
            with open(save_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Assignment', 'Module', 'Student ID', 'First Name', 'Last Name',
                               'Submission Date', 'Status', 'Grade', 'Late'])
                writer.writerows(all_data)
    
            messagebox.showinfo("Success", f"Exported {len(all_data)} records to:\n{save_path}")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export assignments: {e}")
    

    def bulk_send_reminders(self):
        """Send reminders for multiple selected assignments"""
        selections = self.manage_assignments_tree.selection()
        if not selections:
            messagebox.showwarning("Warning", "Please select assignments to send reminders")
            return
    
        messagebox.showinfo("Bulk Reminders",
                           f"Sending reminders for {len(selections)} assignment(s)...\n\n"
                           "This feature would integrate with email system to send batch reminders.")
    

    def show_assignment_statistics(self):
        """Show statistics for all assignments"""
        try:
            stats_window = tk.Toplevel(self.root)
            stats_window.title("Assignment Statistics")
            stats_window.geometry("900x600")
            stats_window.transient(self.root)
    
            ttk.Label(stats_window, text="Assignment Statistics Dashboard",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)
    
            # Summary statistics
            summary_frame = ttk.LabelFrame(stats_window, text="Summary", padding=10)
            summary_frame.pack(fill='x', padx=10, pady=10)
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Total assignments
            cursor.execute("SELECT COUNT(*) FROM assignments")
            total_assignments = cursor.fetchone()[0]
    
            # Active assignments
            cursor.execute("SELECT COUNT(*) FROM assignments WHERE is_active = 1")
            active_assignments = cursor.fetchone()[0]
    
            # Total submissions
            cursor.execute("SELECT COUNT(*) FROM assignment_submissions")
            total_submissions = cursor.fetchone()[0]
    
            # Average grade
            cursor.execute("SELECT AVG(grade) FROM assignment_submissions WHERE grade IS NOT NULL")
            avg_grade = cursor.fetchone()[0] or 0
    
            conn.close()
    
            summary_text = f"""
            Total Assignments: {total_assignments}
            Active Assignments: {active_assignments}
            Total Submissions: {total_submissions}
            Average Grade: {avg_grade:.2f}%
            """
    
            ttk.Label(summary_frame, text=summary_text, font=('TkDefaultFont', 10)).pack()
    
            # Detailed statistics table
            details_frame = ttk.LabelFrame(stats_window, text="Assignment Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
            columns = ('Assignment', 'Module', 'Submissions', 'Avg Grade', 'Late %')
            stats_tree = ttk.Treeview(details_frame, columns=columns, show='headings', height=15)
    
            for col in columns:
                stats_tree.heading(col, text=col)
                stats_tree.column(col, width=150)
    
            stats_tree.pack(fill='both', expand=True)
    
            # Load detailed statistics
            self.load_assignment_statistics(stats_tree)
    
            ttk.Button(stats_window, text="Close", command=stats_window.destroy).pack(pady=10)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to show statistics: {e}")
    

    def load_assignment_statistics(self, tree):
        """Load detailed assignment statistics"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT a.title, a.module_code,
                   COUNT(s.id) as submission_count,
                   AVG(s.grade) as avg_grade,
                   (COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) * 100.0 / COUNT(s.id)) as late_percentage
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            GROUP BY a.id
            ORDER BY a.title
            ''')
    
            stats = cursor.fetchall()
            conn.close()
    
            for stat in stats:
                title, module, subs, avg, late = stat
                avg_grade = f"{avg:.1f}%" if avg else "N/A"
                late_pct = f"{late:.1f}%" if late else "0%"
                tree.insert('', 'end', values=(title, module, subs, avg_grade, late_pct))
    
        except Exception as e:
            print(f"Error loading statistics: {e}")
    

    def show_create_assignment(self):
        """Show assignment creation form - FIXED DATE PICKER"""
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Create Assignment", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create scrollable frame for the form (increased size for better display)
        canvas = tk.Canvas(self.gui.layout.content_area, height=600)
        scrollbar = ttk.Scrollbar(self.gui.layout.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Assignment creation form
        form_frame = ttk.LabelFrame(scrollable_frame, text="Assignment Details", padding=20)
        form_frame.pack(fill='x', padx=10, pady=10)
        
        # Module selection
        ttk.Label(form_frame, text="Module:").grid(row=0, column=0, sticky='w', pady=5)
        self.module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=self.module_var, width=30)
        module_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self.load_modules(module_combo)
        
        # Title
        ttk.Label(form_frame, text="Title:").grid(row=1, column=0, sticky='w', pady=5)
        self.title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.title_var, width=50).grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Description
        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.description_text = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.description_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Instructions
        ttk.Label(form_frame, text="Instructions:").grid(row=3, column=0, sticky='nw', pady=5)
        self.instructions_text = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.instructions_text.grid(row=3, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # FIXED: Due date without tkcalendar
        ttk.Label(form_frame, text="Due Date:").grid(row=4, column=0, sticky='w', pady=5)
        due_frame = ttk.Frame(form_frame)
        due_frame.grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))
        
        # Date entry with validation
        self.due_date_var = tk.StringVar()
        self.due_time_var = tk.StringVar(value="23:59")
        
        # Create date entry with helper text
        date_entry_frame = ttk.Frame(due_frame)
        date_entry_frame.pack(side='left')
        
        ttk.Label(date_entry_frame, text="Date (YYYY-MM-DD):").pack(side='left')
        date_entry = ttk.Entry(date_entry_frame, textvariable=self.due_date_var, width=12)
        date_entry.pack(side='left', padx=(5, 0))
        
        # Add calendar button for date picker
        def show_date_picker():
            """Simple date picker dialog"""
            date_window = tk.Toplevel(self.root)
            date_window.title("Select Date")
            date_window.geometry("300x200")
            date_window.transient(self.root)
            
            # Simple date selection interface
            ttk.Label(date_window, text="Enter date (YYYY-MM-DD):").pack(pady=10)
            
            date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
            date_entry_popup = ttk.Entry(date_window, textvariable=date_var, width=15)
            date_entry_popup.pack(pady=5)
            
            # Quick date buttons
            quick_frame = ttk.Frame(date_window)
            quick_frame.pack(pady=10)
            
            def set_date(days_from_now):
                target_date = datetime.now() + timedelta(days=days_from_now)
                date_var.set(target_date.strftime("%Y-%m-%d"))
            
            ttk.Button(quick_frame, text="Today", command=lambda: set_date(0)).pack(side='left', padx=2)
            ttk.Button(quick_frame, text="Tomorrow", command=lambda: set_date(1)).pack(side='left', padx=2)
            ttk.Button(quick_frame, text="1 Week", command=lambda: set_date(7)).pack(side='left', padx=2)
            ttk.Button(quick_frame, text="2 Weeks", command=lambda: set_date(14)).pack(side='left', padx=2)
            
            def confirm_date():
                try:
                    # Validate date format
                    selected_date = datetime.strptime(date_var.get(), "%Y-%m-%d")
                    self.due_date_var.set(date_var.get())
                    date_window.destroy()
                except ValueError:
                    messagebox.showerror("Invalid Date", "Please enter date in YYYY-MM-DD format")
            
            button_frame = ttk.Frame(date_window)
            button_frame.pack(pady=10)
            
            ttk.Button(button_frame, text="OK", command=confirm_date).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=date_window.destroy).pack(side='left', padx=5)
        
        ttk.Button(due_frame, text="📅", command=show_date_picker, width=3).pack(side='left', padx=(10, 0))
        
        # Time selection
        ttk.Label(due_frame, text="Time:").pack(side='left', padx=(10, 5))
        time_combo = ttk.Combobox(due_frame, textvariable=self.due_time_var, width=8, values=[
            "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", 
            "16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:59"
        ])
        time_combo.pack(side='left')
        
        # Set default date to one week from now
        default_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        self.due_date_var.set(default_date)
        
        # Max marks
        ttk.Label(form_frame, text="Max Marks:").grid(row=5, column=0, sticky='w', pady=5)
        self.max_marks_var = tk.StringVar(value="100")
        ttk.Entry(form_frame, textvariable=self.max_marks_var, width=10).grid(row=5, column=1, sticky='w', pady=5, padx=(10, 0))
        
        # File settings frame
        file_frame = ttk.LabelFrame(scrollable_frame, text="File Settings", padding=20)
        file_frame.pack(fill='x', padx=10, pady=10)
        
        # Allowed file types
        ttk.Label(file_frame, text="Allowed File Types:").grid(row=0, column=0, sticky='w', pady=5)
        self.file_types_var = tk.StringVar(value=".pdf,.docx,.txt")
        ttk.Entry(file_frame, textvariable=self.file_types_var, width=30).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(file_frame, text="(comma-separated, e.g., .pdf,.docx,.txt)").grid(row=0, column=2, sticky='w', pady=5, padx=(5, 0))
        
        # Max file size
        ttk.Label(file_frame, text="Max File Size (MB):").grid(row=1, column=0, sticky='w', pady=5)
        self.max_size_var = tk.StringVar(value="10")
        ttk.Entry(file_frame, textvariable=self.max_size_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        
        # Assignment type frame
        type_frame = ttk.LabelFrame(scrollable_frame, text="Assignment Type & Category", padding=20)
        type_frame.pack(fill='x', padx=10, pady=10)
    
        # Assessment Type Selection
        ttk.Label(type_frame, text="Assessment Type:").grid(row=0, column=0, sticky='w', pady=5)
        self.assessment_type_var = tk.StringVar(value="essay")
        assessment_combo = ttk.Combobox(type_frame, textvariable=self.assessment_type_var, width=20,
                                       values=["essay", "quiz", "project", "presentation", "lab_report",
                                              "case_study", "exam", "homework", "discussion", "other"])
        assessment_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
    
        # Grading Method Selection
        ttk.Label(type_frame, text="Grading Method:").grid(row=1, column=0, sticky='w', pady=5)
        self.grading_method_var = tk.StringVar(value="points")
        grading_combo = ttk.Combobox(type_frame, textvariable=self.grading_method_var, width=20,
                                     values=["points", "percentage", "letter_grade", "pass_fail", "rubric"])
        grading_combo.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
    
        # Visibility Options
        ttk.Label(type_frame, text="Visibility:").grid(row=2, column=0, sticky='w', pady=5)
        self.visibility_var = tk.StringVar(value="draft")
        visibility_combo = ttk.Combobox(type_frame, textvariable=self.visibility_var, width=20,
                                       values=["draft", "published", "hidden", "scheduled"])
        visibility_combo.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(type_frame, text="(Draft = not visible to students)").grid(row=2, column=2, sticky='w', pady=5, padx=(5, 0))
    
        self.assignment_type_var = tk.StringVar(value="individual")
        ttk.Radiobutton(type_frame, text="Individual", variable=self.assignment_type_var,
                       value="individual").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Radiobutton(type_frame, text="Group", variable=self.assignment_type_var,
                       value="group").grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
    
        # Group size (enabled when group is selected)
        ttk.Label(type_frame, text="Group Size (min-max):").grid(row=4, column=0, sticky='w', pady=5)
        group_size_frame = ttk.Frame(type_frame)
        group_size_frame.grid(row=4, column=1, sticky='w', pady=5, padx=(10, 0))
    
        self.group_min_var = tk.StringVar(value="2")
        self.group_max_var = tk.StringVar(value="4")
        ttk.Entry(group_size_frame, textvariable=self.group_min_var, width=5).pack(side='left')
        ttk.Label(group_size_frame, text=" to ").pack(side='left')
        ttk.Entry(group_size_frame, textvariable=self.group_max_var, width=5).pack(side='left')
    
        # Group assignment options
        ttk.Label(type_frame, text="Group Assignment:").grid(row=5, column=0, sticky='w', pady=5)
        self.auto_assign_groups_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(type_frame, text="Auto-assign students to groups",
                       variable=self.auto_assign_groups_var).grid(row=5, column=1, sticky='w', pady=5)
    
        ttk.Label(type_frame, text="Group Submission:").grid(row=6, column=0, sticky='w', pady=5)
        self.group_submission_type_var = tk.StringVar(value="one_per_group")
        group_sub_frame = ttk.Frame(type_frame)
        group_sub_frame.grid(row=6, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Radiobutton(group_sub_frame, text="One per group", variable=self.group_submission_type_var,
                       value="one_per_group").pack(side='left')
        ttk.Radiobutton(group_sub_frame, text="Individual within group", variable=self.group_submission_type_var,
                       value="individual").pack(side='left', padx=(10, 0))
    
        self.peer_eval_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(type_frame, text="Enable peer evaluation within groups",
                       variable=self.peer_eval_var).grid(row=7, column=1, sticky='w', pady=5)
    
        ttk.Button(type_frame, text="Configure Groups & Students",
                  command=self.gui.groups.show_group_configuration).grid(row=8, column=1, sticky='w', pady=10)
        
        # Additional settings frame
        settings_frame = ttk.LabelFrame(scrollable_frame, text="Submission & Grading Settings", padding=20)
        settings_frame.pack(fill='x', padx=10, pady=10)
    
        # Late submission settings
        self.allow_late_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings_frame, text="Allow Late Submissions",
                       variable=self.allow_late_var).grid(row=0, column=0, sticky='w', pady=5)
    
        ttk.Label(settings_frame, text="Late Penalty (% per day):").grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self.late_penalty_var = tk.StringVar(value="0")
        ttk.Entry(settings_frame, textvariable=self.late_penalty_var, width=10).grid(row=0, column=2, sticky='w', pady=5, padx=(10, 0))
    
        # Maximum late days allowed
        ttk.Label(settings_frame, text="Max Late Days:").grid(row=1, column=0, sticky='w', pady=5)
        self.max_late_days_var = tk.StringVar(value="7")
        ttk.Entry(settings_frame, textvariable=self.max_late_days_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(settings_frame, text="(0 = unlimited)").grid(row=1, column=2, sticky='w', pady=5, padx=(5, 0))
    
        # Resubmission settings
        self.allow_resubmit_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Allow Resubmissions",
                       variable=self.allow_resubmit_var).grid(row=2, column=0, sticky='w', pady=5)
    
        ttk.Label(settings_frame, text="Max Attempts:").grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        self.max_attempts_var = tk.StringVar(value="1")
        ttk.Entry(settings_frame, textvariable=self.max_attempts_var, width=10).grid(row=2, column=2, sticky='w', pady=5, padx=(10, 0))
    
        # Other settings
        self.auto_release_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Auto-release Grades",
                       variable=self.auto_release_var).grid(row=3, column=0, sticky='w', pady=5)
    
        self.peer_review_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Enable Peer Review",
                       variable=self.peer_review_var).grid(row=3, column=1, sticky='w', pady=5)
    
        self.plagiarism_check_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(settings_frame, text="Enable Plagiarism Check",
                       variable=self.plagiarism_check_var).grid(row=3, column=2, sticky='w', pady=5)
    
        # Advanced settings collapsible section
        advanced_frame = ttk.LabelFrame(scrollable_frame, text="Advanced Settings (Optional)", padding=20)
        advanced_frame.pack(fill='x', padx=10, pady=10)
    
        # Rubric selection
        ttk.Label(advanced_frame, text="Rubric Template:").grid(row=0, column=0, sticky='w', pady=5)
        self.rubric_var = tk.StringVar(value="None")
        rubric_combo = ttk.Combobox(advanced_frame, textvariable=self.rubric_var, width=30,
                                    values=["None", "Standard Essay Rubric", "Project Rubric", "Presentation Rubric", "Custom"])
        rubric_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Button(advanced_frame, text="Create/Edit Rubric",
                  command=self.gui.rubrics.show_rubric_editor).grid(row=0, column=2, padx=(10, 0))
    
        # Submission notifications
        ttk.Label(advanced_frame, text="Notifications:").grid(row=1, column=0, sticky='w', pady=5)
        self.notify_on_submit_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(advanced_frame, text="Email on submission",
                       variable=self.notify_on_submit_var).grid(row=1, column=1, sticky='w', pady=5)
    
        # Reminder settings
        ttk.Label(advanced_frame, text="Reminder Before Due:").grid(row=2, column=0, sticky='w', pady=5)
        self.reminder_days_var = tk.StringVar(value="2")
        reminder_frame = ttk.Frame(advanced_frame)
        reminder_frame.grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Entry(reminder_frame, textvariable=self.reminder_days_var, width=5).pack(side='left')
        ttk.Label(reminder_frame, text=" days").pack(side='left', padx=(5, 0))
    
        # Weight/Points distribution
        ttk.Label(advanced_frame, text="Course Weight (%):").grid(row=3, column=0, sticky='w', pady=5)
        self.course_weight_var = tk.StringVar(value="0")
        ttk.Entry(advanced_frame, textvariable=self.course_weight_var, width=10).grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        ttk.Label(advanced_frame, text="(0 = not weighted)").grid(row=3, column=2, sticky='w', pady=5, padx=(5, 0))
        
        # Configure grid weights
        form_frame.grid_columnconfigure(1, weight=1)
        file_frame.grid_columnconfigure(1, weight=1)
        
        # Buttons frame
        buttons_frame = ttk.Frame(scrollable_frame)
        buttons_frame.pack(fill='x', padx=10, pady=20)
    
        ttk.Button(buttons_frame, text="Create Assignment",
                  command=self.create_assignment_gui, style='Accent.TButton').pack(side='right', padx=(10, 0))
        ttk.Button(buttons_frame, text="Save as Draft",
                  command=self.save_assignment_draft).pack(side='right', padx=(10, 0))
        ttk.Button(buttons_frame, text="Load Template",
                  command=self.load_assignment_template).pack(side='left')
        ttk.Button(buttons_frame, text="Save as Template",
                  command=self.save_assignment_template).pack(side='left', padx=(10, 0))
        ttk.Button(buttons_frame, text="Clear Form",
                  command=self.clear_assignment_form).pack(side='right', padx=(10, 0))
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Status frame
        self.assignment_status_frame = ttk.Frame(self.gui.layout.content_area)
        self.assignment_status_frame.pack(fill='x', pady=(10, 0))
    
    # ASSESSMENT SYSTEM METHODS

    def validate_assignment_form(self):
        """Validate the assignment creation form"""
        if not self.module_var.get():
            self.show_assignment_status("Please select a module", "error")
            return False
        
        if not self.title_var.get().strip():
            self.show_assignment_status("Please enter a title", "error")
            return False
        
        if not self.due_date_var.get().strip():
            self.show_assignment_status("Please enter a due date", "error")
            return False
        
        try:
            # Validate date format
            due_date_str = f"{self.due_date_var.get()} {self.due_time_var.get()}"
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
            if due_date <= datetime.now():
                self.show_assignment_status("Due date must be in the future", "error")
                return False
        except ValueError:
            self.show_assignment_status("Invalid date format. Use YYYY-MM-DD", "error")
            return False
        
        try:
            max_marks = int(self.max_marks_var.get())
            if max_marks <= 0:
                self.show_assignment_status("Max marks must be positive", "error")
                return False
        except ValueError:
            self.show_assignment_status("Max marks must be a number", "error")
            return False
        
        return True
    

    def load_modules(self, combo):
        """Load available modules"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('SELECT module_code, module_name FROM modules ORDER BY module_code')
            modules = cursor.fetchall()
            
            module_list = [f"{code} - {name}" for code, name in modules]
            combo['values'] = module_list
            
            # Create mapping for easy lookup
            self.module_map = {f"{code} - {name}": code for code, name in modules}
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load modules: {e}")
    

    def create_assignment_gui(self):
        """Create assignment through GUI"""
        # Clear previous status
        for widget in self.assignment_status_frame.winfo_children():
            widget.destroy()
        
        # Validate form
        if not self.validate_assignment_form():
            return
        
        # Show progress
        self.show_assignment_status("Creating assignment...", "info")
        self.root.update()
        
        # Create assignment in background thread
        threading.Thread(target=self.perform_assignment_creation, daemon=True).start()
    

    def perform_assignment_creation(self):
        """Perform the actual assignment creation"""
        try:
            # Get module code
            module_code = self.module_map.get(self.module_var.get())
    
            # Prepare assignment data
            due_date_str = f"{self.due_date_var.get()} {self.due_time_var.get()}"
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")
    
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO assignments 
            (module_code, title, description, instructions, due_date, max_marks, 
             file_types_allowed, max_file_size_mb, assignment_type, group_size_min, group_size_max,
             allow_late_submission, late_penalty_per_day, auto_release_grades, peer_review_enabled,
             created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                module_code,
                self.title_var.get().strip(),
                self.description_text.get(1.0, tk.END).strip(),
                self.instructions_text.get(1.0, tk.END).strip(),
                due_date.strftime('%Y-%m-%d %H:%M:%S'),
                int(self.max_marks_var.get()),
                self.file_types_var.get().strip(),
                int(self.max_size_var.get()),
                self.assignment_type_var.get(),
                int(self.group_min_var.get()) if self.assignment_type_var.get() == 'group' else 1,
                int(self.group_max_var.get()) if self.assignment_type_var.get() == 'group' else 1,
                self.allow_late_var.get(),
                float(self.late_penalty_var.get()) if self.late_penalty_var.get() else 0,
                self.auto_release_var.get(),
                self.peer_review_var.get(),
                self.auth.current_user['id'],
                timestamp,
                timestamp
            ))
            
            assignment_id = cursor.lastrowid
    
            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON")
    
            conn.commit()
            conn.close()

            # Send assignment notification to students
            try:
                from university_system.infrastructure.email.email_service import send_assignment_notification
                import logging
                send_assignment_notification(
                    assignment_id,
                    self.title_var.get().strip(),
                    module_code,
                    due_date.strftime('%Y-%m-%d %H:%M:%S'),
                    self.description_text.get(1.0, tk.END).strip()
                )
            except Exception as e:
                import logging
                logging.warning(f"Failed to send assignment notification emails: {e}")

            # Update GUI on main thread
            self.root.after(0, lambda: self.show_assignment_status(
                f"Assignment '{self.title_var.get()}' created successfully! ID: {assignment_id}", "success"))
            self.root.after(0, self.clear_assignment_form)
            
        except Exception as e:
            error_msg = f"Failed to create assignment: {str(e)}"
            self.root.after(0, lambda: self.show_assignment_status(error_msg, "error"))
    

    def show_assignment_status(self, message, msg_type):
        """Show status message in assignment status frame"""
        for widget in self.assignment_status_frame.winfo_children():
            widget.destroy()
        
        if msg_type == "success":
            style = 'Success.TLabel'
        elif msg_type == "error":
            style = 'Error.TLabel'
        else:
            style = 'Warning.TLabel'
        
        status_label = ttk.Label(self.assignment_status_frame, text=message, style=style)
        status_label.pack(anchor='w')
    

    def clear_assignment_form(self):
        """Clear the assignment creation form"""
        self.module_var.set('')
        self.title_var.set('')
        self.description_text.delete(1.0, tk.END)
        self.instructions_text.delete(1.0, tk.END)
        self.due_date_var.set('')
        self.due_time_var.set('23:59')
        self.max_marks_var.set('100')
        self.file_types_var.set('.pdf,.docx,.txt')
        self.max_size_var.set('10')
        self.assignment_type_var.set('individual')
        self.group_min_var.set('2')
        self.group_max_var.set('4')
        self.allow_late_var.set(True)
        self.late_penalty_var.set('0')
        self.auto_release_var.set(False)
        self.peer_review_var.set(False)
    
        # Clear new fields if they exist
        if hasattr(self, 'assessment_type_var'):
            self.assessment_type_var.set('essay')
        if hasattr(self, 'grading_method_var'):
            self.grading_method_var.set('points')
        if hasattr(self, 'visibility_var'):
            self.visibility_var.set('draft')
        if hasattr(self, 'max_late_days_var'):
            self.max_late_days_var.set('7')
        if hasattr(self, 'allow_resubmit_var'):
            self.allow_resubmit_var.set(False)
        if hasattr(self, 'max_attempts_var'):
            self.max_attempts_var.set('1')
        if hasattr(self, 'plagiarism_check_var'):
            self.plagiarism_check_var.set(False)
        if hasattr(self, 'rubric_var'):
            self.rubric_var.set('None')
        if hasattr(self, 'notify_on_submit_var'):
            self.notify_on_submit_var.set(True)
        if hasattr(self, 'reminder_days_var'):
            self.reminder_days_var.set('2')
        if hasattr(self, 'course_weight_var'):
            self.course_weight_var.set('0')
    

    def save_assignment_draft(self):
        """Save current assignment as draft"""
        try:
            # Validate basic fields
            if not self.title_var.get().strip():
                messagebox.showerror("Error", "Please enter a title before saving draft")
                return
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Create assignment_drafts table if not exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                draft_name TEXT NOT NULL,
                draft_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
    
            # Collect form data
            draft_data = {
                'module': self.module_var.get(),
                'title': self.title_var.get(),
                'description': self.description_text.get(1.0, tk.END).strip(),
                'instructions': self.instructions_text.get(1.0, tk.END).strip(),
                'due_date': self.due_date_var.get(),
                'due_time': self.due_time_var.get(),
                'max_marks': self.max_marks_var.get(),
                'file_types': self.file_types_var.get(),
                'max_size': self.max_size_var.get(),
                'assignment_type': self.assignment_type_var.get(),
                'group_min': self.group_min_var.get(),
                'group_max': self.group_max_var.get(),
                'allow_late': self.allow_late_var.get(),
                'late_penalty': self.late_penalty_var.get(),
                'auto_release': self.auto_release_var.get(),
                'peer_review': self.peer_review_var.get(),
            }
    
            # Add new fields if they exist
            if hasattr(self, 'assessment_type_var'):
                draft_data['assessment_type'] = self.assessment_type_var.get()
            if hasattr(self, 'grading_method_var'):
                draft_data['grading_method'] = self.grading_method_var.get()
            if hasattr(self, 'visibility_var'):
                draft_data['visibility'] = self.visibility_var.get()
    
            draft_name = f"Draft - {self.title_var.get()[:30]} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
            cursor.execute('''
            INSERT INTO assignment_drafts (user_id, draft_name, draft_data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (self.auth.current_user['id'], draft_name, json.dumps(draft_data)))
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", f"Draft saved successfully as:\n{draft_name}")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save draft: {e}")
    

    def load_assignment_template(self):
        """Load an assignment template or draft"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get templates and drafts
            cursor.execute('''
            SELECT id, draft_name, draft_data, created_at
            FROM assignment_drafts
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 20
            ''', (self.auth.current_user['id'],))
    
            templates = cursor.fetchall()
            conn.close()
    
            if not templates:
                messagebox.showinfo("No Templates", "No saved templates or drafts found")
                return
    
            # Create selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Load Template/Draft")
            dialog.geometry("600x400")
            dialog.transient(self.root)
    
            ttk.Label(dialog, text="Select a template or draft to load:",
                     font=('TkDefaultFont', 12, 'bold')).pack(pady=10)
    
            # Templates listbox
            list_frame = ttk.Frame(dialog)
            list_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side='right', fill='y')
    
            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=15)
            listbox.pack(fill='both', expand=True)
            scrollbar.config(command=listbox.yview)
    
            template_map = {}
            for template in templates:
                tid, name, data, created = template
                listbox.insert(tk.END, name)
                template_map[name] = (tid, data)
    
            def load_selected():
                selection = listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a template")
                    return
    
                selected_name = listbox.get(selection[0])
                tid, data_json = template_map[selected_name]
    
                try:
                    data = json.loads(data_json)
    
                    # Load data into form
                    self.module_var.set(data.get('module', ''))
                    self.title_var.set(data.get('title', ''))
                    self.description_text.delete(1.0, tk.END)
                    self.description_text.insert(1.0, data.get('description', ''))
                    self.instructions_text.delete(1.0, tk.END)
                    self.instructions_text.insert(1.0, data.get('instructions', ''))
                    self.due_date_var.set(data.get('due_date', ''))
                    self.due_time_var.set(data.get('due_time', '23:59'))
                    self.max_marks_var.set(data.get('max_marks', '100'))
                    self.file_types_var.set(data.get('file_types', '.pdf,.docx,.txt'))
                    self.max_size_var.set(data.get('max_size', '10'))
                    self.assignment_type_var.set(data.get('assignment_type', 'individual'))
                    self.group_min_var.set(data.get('group_min', '2'))
                    self.group_max_var.set(data.get('group_max', '4'))
                    self.allow_late_var.set(data.get('allow_late', True))
                    self.late_penalty_var.set(data.get('late_penalty', '0'))
                    self.auto_release_var.set(data.get('auto_release', False))
                    self.peer_review_var.set(data.get('peer_review', False))
    
                    # Load new fields if they exist
                    if hasattr(self, 'assessment_type_var'):
                        self.assessment_type_var.set(data.get('assessment_type', 'essay'))
                    if hasattr(self, 'grading_method_var'):
                        self.grading_method_var.set(data.get('grading_method', 'points'))
                    if hasattr(self, 'visibility_var'):
                        self.visibility_var.set(data.get('visibility', 'draft'))
    
                    dialog.destroy()
                    messagebox.showinfo("Success", "Template loaded successfully")
    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load template: {e}")
    
            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)
    
            ttk.Button(button_frame, text="Load", command=load_selected).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {e}")
    

    def save_assignment_template(self):
        """Save current form as a reusable template"""
        try:
            if not self.title_var.get().strip():
                messagebox.showerror("Error", "Please enter a title before saving template")
                return
    
            # Ask for template name
            template_name = tk.simpledialog.askstring("Template Name",
                                                      "Enter a name for this template:",
                                                      initialfile=f"Template - {self.title_var.get()[:30]}")
            if not template_name:
                return
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                draft_name TEXT NOT NULL,
                draft_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
    
            draft_data = {
                'module': self.module_var.get(),
                'title': self.title_var.get(),
                'description': self.description_text.get(1.0, tk.END).strip(),
                'instructions': self.instructions_text.get(1.0, tk.END).strip(),
                'max_marks': self.max_marks_var.get(),
                'file_types': self.file_types_var.get(),
                'max_size': self.max_size_var.get(),
                'assignment_type': self.assignment_type_var.get(),
                'group_min': self.group_min_var.get(),
                'group_max': self.group_max_var.get(),
                'allow_late': self.allow_late_var.get(),
                'late_penalty': self.late_penalty_var.get(),
                'auto_release': self.auto_release_var.get(),
                'peer_review': self.peer_review_var.get(),
            }
    
            if hasattr(self, 'assessment_type_var'):
                draft_data['assessment_type'] = self.assessment_type_var.get()
            if hasattr(self, 'grading_method_var'):
                draft_data['grading_method'] = self.grading_method_var.get()
    
            cursor.execute('''
            INSERT INTO assignment_drafts (user_id, draft_name, draft_data, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (self.auth.current_user['id'], template_name, json.dumps(draft_data)))
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", f"Template '{template_name}' saved successfully")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")
    

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

    def load_assignments_for_group_filter(self, combo):
        """Load assignments that have groups"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT DISTINCT a.id, a.title
            FROM assignments a
            WHERE a.assignment_type = 'group'
            ORDER BY a.title
            ''')
    
            assignments = cursor.fetchall()
            conn.close()
    
            combo_values = ["All Assignments"] + [f"{aid} - {title}" for aid, title in assignments]
            combo['values'] = combo_values
            if combo_values:
                combo.current(0)
    
        except Exception as e:
            print(f"Error loading assignments: {e}")
    

    def load_assignments_for_message(self, combo):
        """Load assignments for message reference"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, title, module_code FROM assignments WHERE is_active = 1 ORDER BY due_date DESC')
            assignments = cursor.fetchall()
            
            assignment_list = ["None"] + [f"{title} ({module})" for aid, title, module in assignments]
            combo['values'] = assignment_list
            combo.set("None")
            
            # Create mapping for assignment IDs
            self.message_assignment_map = {"None": None}
            for aid, title, module in assignments:
                self.message_assignment_map[f"{title} ({module})"] = aid
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading assignments: {e}")
    

    def load_my_assignments_filter(self, combo):
        """Load assignments for submission filter"""
        try:
            student_id = self.assignment_system._get_student_id()
            if not student_id:
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT DISTINCT a.id, a.title, a.module_code
            FROM assignments a
            JOIN student_modules sm ON a.module_code = sm.module_code
            WHERE sm.student_id = ?
            ORDER BY a.due_date DESC
            ''', (student_id,))
            
            assignments = cursor.fetchall()
            
            assignment_list = ["All Assignments"] + [f"{title} ({module})" for aid, title, module in assignments]
            combo['values'] = assignment_list
            combo.set("All Assignments")
            
            # Create mapping
            self.submission_assignment_map = {"All Assignments": None}
            for aid, title, module in assignments:
                self.submission_assignment_map[f"{title} ({module})"] = aid
            
            conn.close()
            
        except Exception as e:
            print(f"Error loading assignments: {e}")
    

    def load_extension_assignments(self, combo):
        """Load assignments available for extension request"""
        try:
            student_id = self._get_student_id_safe()
            # Show all assignments if no student ID (for admin/instructor)
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
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
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")
    

    def _load_assignments_for_compose(self, assignment_combo):
        """Load assignments for message compose"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
                SELECT id, title, module_code
                FROM assignments
                WHERE is_active = 1
                ORDER BY due_date DESC
                LIMIT 50
            ''')
    
            assignments = cursor.fetchall()
            conn.close()
    
            values = ["(No Assignment)"] + [f"{a[0]}: {a[1]} ({a[2]})" for a in assignments]
            assignment_combo['values'] = values
            assignment_combo.current(0)
    
        except Exception as e:
            print(f"Error loading assignments: {e}")
    
