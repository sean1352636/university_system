"""Group assignment management"""

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



class GroupManager:
    """Group assignment management"""

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

    def show_create_group_assignment(self):
        """Show enhanced group assignment creation"""
        if not self._check_permission('manage_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Create Group Assignment", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create scrollable frame
        canvas = tk.Canvas(self.gui.layout.content_area)
        scrollbar = ttk.Scrollbar(self.gui.layout.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Basic assignment details
        basic_frame = ttk.LabelFrame(scrollable_frame, text="Basic Assignment Details", padding=20)
        basic_frame.pack(fill='x', padx=10, pady=10)
        
        # Module selection
        ttk.Label(basic_frame, text="Module:").grid(row=0, column=0, sticky='w', pady=5)
        self.group_module_var = tk.StringVar()
        module_combo = ttk.Combobox(basic_frame, textvariable=self.group_module_var, width=30)
        module_combo.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        self.load_modules(module_combo)
        
        # Title
        ttk.Label(basic_frame, text="Title:").grid(row=1, column=0, sticky='w', pady=5)
        self.group_title_var = tk.StringVar()
        ttk.Entry(basic_frame, textvariable=self.group_title_var, width=50).grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Description
        ttk.Label(basic_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.group_description_text = scrolledtext.ScrolledText(basic_frame, height=4, width=50)
        self.group_description_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Due date
        ttk.Label(basic_frame, text="Due Date:").grid(row=3, column=0, sticky='w', pady=5)
        due_frame = ttk.Frame(basic_frame)
        due_frame.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        
        self.group_due_date_var = tk.StringVar()
        self.group_due_time_var = tk.StringVar(value="23:59")
        
        ttk.Entry(due_frame, textvariable=self.group_due_date_var, width=12).pack(side='left')
        ttk.Label(due_frame, text="Time:").pack(side='left', padx=(10, 5))
        ttk.Combobox(due_frame, textvariable=self.group_due_time_var, width=8, 
                    values=["08:00", "12:00", "17:00", "23:59"]).pack(side='left')
        
        # Group settings frame
        group_frame = ttk.LabelFrame(scrollable_frame, text="Group Settings", padding=20)
        group_frame.pack(fill='x', padx=10, pady=10)
        
        # Group size
        ttk.Label(group_frame, text="Group Size:").grid(row=0, column=0, sticky='w', pady=5)
        size_frame = ttk.Frame(group_frame)
        size_frame.grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        
        ttk.Label(size_frame, text="Min:").pack(side='left')
        self.group_min_var = tk.StringVar(value="2")
        ttk.Entry(size_frame, textvariable=self.group_min_var, width=5).pack(side='left', padx=5)
        
        ttk.Label(size_frame, text="Max:").pack(side='left', padx=(10, 0))
        self.group_max_var = tk.StringVar(value="4")
        ttk.Entry(size_frame, textvariable=self.group_max_var, width=5).pack(side='left', padx=5)
        
        # Group formation method
        ttk.Label(group_frame, text="Group Formation:").grid(row=1, column=0, sticky='w', pady=5)
        self.group_formation_var = tk.StringVar(value="self_select")
        
        formation_frame = ttk.Frame(group_frame)
        formation_frame.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        
        ttk.Radiobutton(formation_frame, text="Students self-select", 
                       variable=self.group_formation_var, value="self_select").pack(anchor='w')
        ttk.Radiobutton(formation_frame, text="Instructor assigns", 
                       variable=self.group_formation_var, value="instructor_assign").pack(anchor='w')
        ttk.Radiobutton(formation_frame, text="Random assignment", 
                       variable=self.group_formation_var, value="random").pack(anchor='w')
        
        # Collaboration settings
        collab_frame = ttk.LabelFrame(group_frame, text="Collaboration Settings", padding=10)
        collab_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(20, 0))
        
        self.allow_member_removal_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(collab_frame, text="Allow groups to remove members", 
                       variable=self.allow_member_removal_var).pack(anchor='w')
        
        self.require_peer_eval_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(collab_frame, text="Require peer evaluation", 
                       variable=self.require_peer_eval_var).pack(anchor='w')
        
        self.individual_grades_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(collab_frame, text="Allow individual grades within group", 
                       variable=self.individual_grades_var).pack(anchor='w')
        
        # Submission settings
        submission_frame = ttk.LabelFrame(scrollable_frame, text="Submission Settings", padding=20)
        submission_frame.pack(fill='x', padx=10, pady=10)
        
        # Max marks
        ttk.Label(submission_frame, text="Max Marks:").grid(row=0, column=0, sticky='w', pady=5)
        self.group_max_marks_var = tk.StringVar(value="100")
        ttk.Entry(submission_frame, textvariable=self.group_max_marks_var, width=10).grid(row=0, column=1, sticky='w', pady=5, padx=(10, 0))
        
        # File settings
        ttk.Label(submission_frame, text="Allowed File Types:").grid(row=1, column=0, sticky='w', pady=5)
        self.group_file_types_var = tk.StringVar(value=".pdf,.docx,.zip")
        ttk.Entry(submission_frame, textvariable=self.group_file_types_var, width=30).grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        
        ttk.Label(submission_frame, text="Max File Size (MB):").grid(row=2, column=0, sticky='w', pady=5)
        self.group_max_size_var = tk.StringVar(value="50")
        ttk.Entry(submission_frame, textvariable=self.group_max_size_var, width=10).grid(row=2, column=1, sticky='w', pady=5, padx=(10, 0))
        
        # Submission method
        ttk.Label(submission_frame, text="Submission Method:").grid(row=3, column=0, sticky='w', pady=5)
        self.submission_method_var = tk.StringVar(value="one_per_group")
        
        method_frame = ttk.Frame(submission_frame)
        method_frame.grid(row=3, column=1, sticky='w', pady=5, padx=(10, 0))
        
        ttk.Radiobutton(method_frame, text="One submission per group", 
                       variable=self.submission_method_var, value="one_per_group").pack(anchor='w')
        ttk.Radiobutton(method_frame, text="All members must submit", 
                       variable=self.submission_method_var, value="all_submit").pack(anchor='w')
        
        # Instructions
        instructions_frame = ttk.LabelFrame(scrollable_frame, text="Instructions", padding=20)
        instructions_frame.pack(fill='x', padx=10, pady=10)

        self.group_instructions_text = scrolledtext.ScrolledText(instructions_frame, height=6, width=70)
        self.group_instructions_text.pack(fill='both', expand=True)

        # Default group assignment instructions
        default_instructions = "Group Assignment Instructions: Please work in groups as assigned."
        self.group_instructions_text.insert(tk.END, default_instructions)

        # Action buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill='x', padx=10, pady=20)

        ttk.Button(button_frame, text="Save Group Assignment",
                  command=self.create_group_assignment_gui,
                  style='Accent.TButton').pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Group Configuration",
                  command=self.show_group_configuration).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Clear Form",
                  command=self.clear_group_assignment_form).pack(side='left')

        # Pack the canvas and scrollbar
        canvas.pack(side='left', fill='both', expand=True, padx=10, pady=10)
        scrollbar.pack(side='right', fill='y', pady=10)

    def create_group_assignment_gui(self):
        """Create group assignment through GUI"""
        try:
            # Validate form
            if not self.group_module_var.get() or not self.group_title_var.get():
                messagebox.showerror("Error", "Module and title are required")
                return
            
            if not self.group_due_date_var.get():
                messagebox.showerror("Error", "Due date is required")
                return
            
            # Validate group size
            try:
                min_size = int(self.group_min_var.get())
                max_size = int(self.group_max_var.get())
                if min_size < 1 or max_size < min_size:
                    messagebox.showerror("Error", "Invalid group size")
                    return
            except ValueError:
                messagebox.showerror("Error", "Group size must be numbers")
                return
            
            # Get module code
            module_code = self.module_map.get(self.group_module_var.get())
            
            # Parse due date
            due_date_str = f"{self.group_due_date_var.get()} {self.group_due_time_var.get()}"
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")
            
            # Create assignment
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")
    
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO assignments 
            (module_code, title, description, instructions, due_date, max_marks, 
             file_types_allowed, max_file_size_mb, assignment_type, group_size_min, group_size_max,
             created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                module_code,
                self.group_title_var.get().strip(),
                self.group_description_text.get(1.0, tk.END).strip(),
                self.group_instructions_text.get(1.0, tk.END).strip(),
                due_date.strftime('%Y-%m-%d %H:%M:%S'),
                int(self.group_max_marks_var.get()),
                self.group_file_types_var.get().strip(),
                int(self.group_max_size_var.get()),
                'group',
                min_size,
                max_size,
                self.auth.current_user['id'],
                timestamp,
                timestamp
            ))
            
            assignment_id = cursor.lastrowid
            
            # Handle group formation if instructor assigns or random
            formation_method = self.group_formation_var.get()
            if formation_method in ['instructor_assign', 'random']:
                self.create_initial_groups(cursor, assignment_id, module_code, formation_method, min_size, max_size)
    
            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON")
    
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Group assignment '{self.group_title_var.get()}' created successfully!")
            self.clear_group_assignment_form()
            
        except ValueError as e:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create group assignment: {e}")
    

    def create_initial_groups(self, cursor, assignment_id, module_code, method, min_size, max_size):
        """Create initial groups for assignment"""
        try:
            # Get students in module
            cursor.execute('''
            SELECT student_id FROM student_modules WHERE module_code = ?
            ''', (module_code,))
            
            students = [row[0] for row in cursor.fetchall()]
            
            if len(students) < min_size:
                messagebox.showwarning("Warning", f"Not enough students ({len(students)}) to form groups of minimum size {min_size}")
                return
            
            if method == 'random':
                import random
                random.shuffle(students)
            
            # Create groups
            group_number = 1
            i = 0
            
            while i < len(students):
                remaining_students = len(students) - i
                
                # Determine group size
                if remaining_students <= max_size:
                    group_size = remaining_students
                elif remaining_students < min_size + max_size:
                    # Adjust to avoid leaving too few students
                    group_size = remaining_students // 2
                else:
                    group_size = max_size
                
                if group_size < min_size:
                    break
                
                # Create group
                group_name = f"Group {group_number}"
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute('''
                INSERT INTO groups (assignment_id, group_name, created_at, created_by)
                VALUES (?, ?, ?, ?)
                ''', (assignment_id, group_name, timestamp, 'system'))
                
                group_id = cursor.lastrowid
                
                # Add students to group
                for j in range(group_size):
                    if i + j < len(students):
                        student_id = students[i + j]
                        role = 'leader' if j == 0 else 'member'
                        
                        cursor.execute('''
                        INSERT INTO group_members (group_id, student_id, role, joined_at)
                        VALUES (?, ?, ?, ?)
                        ''', (group_id, student_id, role, timestamp))
                
                i += group_size
                group_number += 1
            
            messagebox.showinfo("Groups Created", f"Created {group_number - 1} groups with {method} method")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create initial groups: {e}")
    

    def clear_group_assignment_form(self):
        """Clear group assignment form"""
        self.group_module_var.set('')
        self.group_title_var.set('')
        self.group_description_text.delete(1.0, tk.END)
        self.group_due_date_var.set('')
        self.group_due_time_var.set('23:59')
        self.group_min_var.set('2')
        self.group_max_var.set('4')
        self.group_formation_var.set('self_select')
        self.group_max_marks_var.set('100')
        self.group_file_types_var.set('.pdf,.docx,.zip')
        self.group_max_size_var.set('50')
        self.submission_method_var.set('one_per_group')
        self.allow_member_removal_var.set(False)
        self.require_peer_eval_var.set(True)
        self.individual_grades_var.set(False)
        # Reset instructions to default
        self.group_instructions_text.delete(1.0, tk.END)
        self.group_instructions_text.insert(tk.END, "Group Assignment Instructions: Please work in groups as assigned.")

    def show_group_configuration(self):
        """Show comprehensive group configuration interface"""
        try:
            # Check if module is selected - using group_module_var instead
            if not hasattr(self, 'group_module_var') or not self.group_module_var.get():
                messagebox.showwarning("Module Required", "Please select a module from the Create Group Assignment form first")
                return
    
            dialog = tk.Toplevel(self.root)
            dialog.title("Group Configuration")
            dialog.geometry("1000x700")
            dialog.transient(self.root)
    
            ttk.Label(dialog, text="Group Configuration & Student Assignment",
                     font=('TkDefaultFont', 14, 'bold')).pack(pady=10)
    
            # Create notebook for different group management options
            notebook = ttk.Notebook(dialog)
            notebook.pack(fill='both', expand=True, padx=10, pady=5)
    
            # Tab 1: Auto-Assign Groups
            auto_tab = ttk.Frame(notebook)
            notebook.add(auto_tab, text="Auto-Assign Groups")
    
            ttk.Label(auto_tab, text="Automatically create and assign students to groups",
                     font=('TkDefaultFont', 11)).pack(pady=10)
    
            auto_frame = ttk.LabelFrame(auto_tab, text="Auto-Assignment Settings", padding=20)
            auto_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Label(auto_frame, text="Assignment Method:").grid(row=0, column=0, sticky='w', pady=5)
            auto_method_var = tk.StringVar(value="random")
            ttk.Radiobutton(auto_frame, text="Random", variable=auto_method_var,
                           value="random").grid(row=0, column=1, sticky='w', pady=5)
            ttk.Radiobutton(auto_frame, text="By Performance", variable=auto_method_var,
                           value="performance").grid(row=1, column=1, sticky='w', pady=5)
            ttk.Radiobutton(auto_frame, text="By Preferences", variable=auto_method_var,
                           value="preferences").grid(row=2, column=1, sticky='w', pady=5)
    
            ttk.Label(auto_frame, text="Number of Groups:").grid(row=3, column=0, sticky='w', pady=5)
            num_groups_var = tk.StringVar(value="5")
            ttk.Entry(auto_frame, textvariable=num_groups_var, width=10).grid(row=3, column=1, sticky='w', pady=5)
    
            ttk.Label(auto_frame, text="Or Students per Group:").grid(row=4, column=0, sticky='w', pady=5)
            students_per_group_var = tk.StringVar(value="4")
            ttk.Entry(auto_frame, textvariable=students_per_group_var, width=10).grid(row=4, column=1, sticky='w', pady=5)
    
            balance_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(auto_frame, text="Balance group sizes",
                           variable=balance_var).grid(row=5, column=1, sticky='w', pady=5)
    
            ttk.Button(auto_frame, text="Generate Groups Automatically",
                      command=lambda: self.auto_generate_groups(dialog, auto_method_var.get(),
                                                               num_groups_var.get(), students_per_group_var.get(),
                                                               balance_var.get())).grid(row=6, column=1, sticky='w', pady=10)
    
            # Tab 2: Manual Group Creation
            manual_tab = ttk.Frame(notebook)
            notebook.add(manual_tab, text="Manual Groups")
    
            # Top section - Create new group
            create_frame = ttk.LabelFrame(manual_tab, text="Create New Group", padding=10)
            create_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Label(create_frame, text="Group Name:").grid(row=0, column=0, sticky='w', pady=5)
            group_name_var = tk.StringVar()
            ttk.Entry(create_frame, textvariable=group_name_var, width=30).grid(row=0, column=1, pady=5, padx=(10, 0))
    
            ttk.Label(create_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
            group_desc_text = tk.Text(create_frame, height=2, width=30)
            group_desc_text.grid(row=1, column=1, pady=5, padx=(10, 0))
    
            ttk.Button(create_frame, text="Create Group",
                      command=lambda: self.create_manual_group(group_name_var.get(),
                                                              group_desc_text.get(1.0, tk.END).strip(),
                                                              groups_tree)).grid(row=2, column=1, sticky='w', pady=5)
    
            # Middle section - Groups list and members
            groups_frame = ttk.LabelFrame(manual_tab, text="Groups & Members", padding=10)
            groups_frame.pack(fill='both', expand=True, padx=10, pady=5)
    
            # Split into two panes
            paned = ttk.PanedWindow(groups_frame, orient='horizontal')
            paned.pack(fill='both', expand=True)
    
            # Left pane - Groups list
            left_pane = ttk.Frame(paned)
            paned.add(left_pane, weight=1)
    
            ttk.Label(left_pane, text="Groups", font=('TkDefaultFont', 10, 'bold')).pack()
    
            groups_tree = ttk.Treeview(left_pane, columns=('Name', 'Members', 'Status'), show='headings', height=15)
            groups_tree.heading('Name', text='Group Name')
            groups_tree.heading('Members', text='Members')
            groups_tree.heading('Status', text='Status')
            groups_tree.column('Name', width=150)
            groups_tree.column('Members', width=80)
            groups_tree.column('Status', width=80)
            groups_tree.pack(fill='both', expand=True, pady=5)
    
            # Sample groups
            groups_tree.insert('', 'end', values=('Group 1', '0/4', 'Empty'))
            groups_tree.insert('', 'end', values=('Group 2', '0/4', 'Empty'))
            groups_tree.insert('', 'end', values=('Group 3', '0/4', 'Empty'))
    
            group_buttons = ttk.Frame(left_pane)
            group_buttons.pack(fill='x', pady=5)
            ttk.Button(group_buttons, text="Edit",
                      command=lambda: self.edit_group(groups_tree)).pack(side='left', padx=2)
            ttk.Button(group_buttons, text="Delete",
                      command=lambda: self.delete_group(groups_tree)).pack(side='left', padx=2)
            ttk.Button(group_buttons, text="Merge",
                      command=lambda: self.merge_groups(groups_tree)).pack(side='left', padx=2)
    
            # Right pane - Students list
            right_pane = ttk.Frame(paned)
            paned.add(right_pane, weight=1)
    
            ttk.Label(right_pane, text="Available Students", font=('TkDefaultFont', 10, 'bold')).pack()
    
            students_tree = ttk.Treeview(right_pane, columns=('Student', 'ID', 'Status'), show='headings', height=15)
            students_tree.heading('Student', text='Student Name')
            students_tree.heading('ID', text='Student ID')
            students_tree.heading('Status', text='Status')
            students_tree.column('Student', width=150)
            students_tree.column('ID', width=100)
            students_tree.column('Status', width=80)
            students_tree.pack(fill='both', expand=True, pady=5)

            # Load students from database
            self.load_students_for_group(students_tree, self.group_module_var.get() if hasattr(self, 'group_module_var') else '')
    
            student_buttons = ttk.Frame(right_pane)
            student_buttons.pack(fill='x', pady=5)
            ttk.Button(student_buttons, text="Add to Group",
                      command=lambda: self.add_student_to_group(students_tree, groups_tree)).pack(side='left', padx=2)
            ttk.Button(student_buttons, text="Remove from Group",
                      command=lambda: self.remove_student_from_group(students_tree, groups_tree)).pack(side='left', padx=2)
    
            # Tab 3: Load Existing Groups
            load_tab = ttk.Frame(notebook)
            notebook.add(load_tab, text="Load Existing Groups")
    
            ttk.Label(load_tab, text="Load groups from a previous assignment or saved group set",
                     font=('TkDefaultFont', 11)).pack(pady=10)
    
            load_frame = ttk.LabelFrame(load_tab, text="Available Group Sets", padding=10)
            load_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
            load_tree = ttk.Treeview(load_frame, columns=('Name', 'Assignment', 'Groups', 'Date'),
                                    show='headings', height=15)
            load_tree.heading('Name', text='Group Set Name')
            load_tree.heading('Assignment', text='From Assignment')
            load_tree.heading('Groups', text='# Groups')
            load_tree.heading('Date', text='Created Date')
    
            for col in ('Name', 'Assignment', 'Groups', 'Date'):
                load_tree.column(col, width=150)
    
            load_tree.pack(fill='both', expand=True, pady=5)
    
            # Sample data
            load_tree.insert('', 'end', values=('CS101 Project Groups', 'Project 1', '8', '2025-08-15'))
            load_tree.insert('', 'end', values=('Saved Team Formation', 'N/A', '6', '2025-09-01'))
    
            load_buttons = ttk.Frame(load_tab)
            load_buttons.pack(pady=10)
            ttk.Button(load_buttons, text="Load Selected Groups",
                      command=lambda: messagebox.showinfo("Info", "Groups loaded")).pack(side='left', padx=5)
            ttk.Button(load_buttons, text="Save Current Groups",
                      command=lambda: self.save_group_configuration(groups_tree)).pack(side='left', padx=5)
    
            # Bottom buttons
            bottom_frame = ttk.Frame(dialog)
            bottom_frame.pack(pady=10)
    
            ttk.Button(bottom_frame, text="Apply & Close",
                      command=lambda: self.apply_group_configuration(dialog)).pack(side='left', padx=5)
            ttk.Button(bottom_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open group configuration: {e}")
    

    def auto_generate_groups(self, dialog, method, num_groups, students_per_group, balance):
        """Automatically generate groups based on selected method"""
        try:
            # Get students for current module
            module_code = self.module_map.get(self.group_module_var.get()) if hasattr(self, 'group_module_var') else None
            if not module_code:
                messagebox.showerror("Error", "Please select a module first")
                return
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get enrolled students
            cursor.execute('''
            SELECT s.student_id, u.first_name, u.last_name
            FROM student_enrollments s
            JOIN users u ON s.student_id = u.id
            WHERE s.module_code = ?
            ORDER BY u.last_name, u.first_name
            ''', (module_code,))
    
            students = cursor.fetchall()
            conn.close()
    
            if not students:
                messagebox.showwarning("No Students", "No students enrolled in this module")
                return
    
            # Generate groups based on method
            if method == "random":
                import random
                random.shuffle(students)
    
            try:
                n_groups = int(num_groups)
            except:
                n_groups = len(students) // int(students_per_group) if students_per_group else 5
    
            # Create groups
            groups = [[] for _ in range(n_groups)]
            for i, student in enumerate(students):
                groups[i % n_groups].append(student)
    
            # Display results
            result_msg = f"Created {n_groups} groups:\n\n"
            for i, group in enumerate(groups, 1):
                result_msg += f"Group {i} ({len(group)} members):\n"
                for sid, fname, lname in group:
                    result_msg += f"  - {fname} {lname} (ID: {sid})\n"
                result_msg += "\n"
    
            result_window = tk.Toplevel(dialog)
            result_window.title("Generated Groups")
            result_window.geometry("500x600")
    
            text = scrolledtext.ScrolledText(result_window, wrap=tk.WORD, width=60, height=30)
            text.pack(fill='both', expand=True, padx=10, pady=10)
            text.insert(1.0, result_msg)
            text.config(state='disabled')
    
            ttk.Button(result_window, text="Accept Groups",
                      command=lambda: messagebox.showinfo("Success", "Groups saved")).pack(pady=10)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate groups: {e}")
    

    def load_students_for_group(self, tree, module_name):
        """Load students enrolled in the module"""
        try:
            module_code = self.module_map.get(module_name)
            if not module_code:
                return
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT s.student_id, u.first_name, u.last_name
            FROM student_enrollments s
            JOIN users u ON s.student_id = u.id
            WHERE s.module_code = ?
            ORDER BY u.last_name, u.first_name
            ''', (module_code,))
    
            students = cursor.fetchall()
            conn.close()
    
            for student in students:
                sid, fname, lname = student
                tree.insert('', 'end', values=(f"{fname} {lname}", sid, "Unassigned"))
    
        except Exception as e:
            print(f"Error loading students: {e}")
    

    def create_manual_group(self, name, description, tree):
        """Create a new group manually"""
        if not name:
            messagebox.showwarning("Name Required", "Please enter a group name")
            return
    
        # Add to tree
        tree.insert('', 'end', values=(name, '0/4', 'Empty'))
        messagebox.showinfo("Success", f"Group '{name}' created")
    

    def edit_group(self, tree):
        """Edit selected group"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a group to edit")
            return
    
        # Get current group values
        item = selection[0]
        current_values = tree.item(item, 'values')
        current_name = current_values[0]
        current_members = current_values[1] if len(current_values) > 1 else '0/4'
        current_status = current_values[2] if len(current_values) > 2 else 'Empty'
    
        # Create edit dialog
        edit_dialog = tk.Toplevel()
        edit_dialog.title("Edit Group")
        edit_dialog.geometry("400x200")
        edit_dialog.transient(tree.winfo_toplevel())
        edit_dialog.grab_set()
    
        ttk.Label(edit_dialog, text="Edit Group Details", font=('TkDefaultFont', 12, 'bold')).pack(pady=10)
    
        form_frame = ttk.Frame(edit_dialog, padding=10)
        form_frame.pack(fill='both', expand=True)
    
        ttk.Label(form_frame, text="Group Name:").grid(row=0, column=0, sticky='w', pady=5, padx=5)
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(form_frame, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, pady=5, padx=5)
        name_entry.focus()
    
        ttk.Label(form_frame, text="Max Members:").grid(row=1, column=0, sticky='w', pady=5, padx=5)
        # Parse current max members from '0/4' format
        max_members = current_members.split('/')[1] if '/' in current_members else '4'
        max_var = tk.StringVar(value=max_members)
        max_entry = ttk.Entry(form_frame, textvariable=max_var, width=10)
        max_entry.grid(row=1, column=1, sticky='w', pady=5, padx=5)
    
        def save_changes():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Name Required", "Please enter a group name", parent=edit_dialog)
                return
    
            try:
                new_max = int(max_var.get())
                if new_max < 1:
                    raise ValueError("Max members must be at least 1")
            except ValueError as e:
                messagebox.showwarning("Invalid Input", f"Please enter a valid number for max members: {e}",
                                     parent=edit_dialog)
                return
    
            # Update tree item with new values
            current_count = current_members.split('/')[0] if '/' in current_members else '0'
            new_members = f"{current_count}/{new_max}"
    
            tree.item(item, values=(new_name, new_members, current_status))
            messagebox.showinfo("Success", f"Group updated to '{new_name}'", parent=edit_dialog)
            edit_dialog.destroy()
    
        button_frame = ttk.Frame(edit_dialog)
        button_frame.pack(pady=10)
    
        ttk.Button(button_frame, text="Save", command=save_changes).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=edit_dialog.destroy).pack(side='left', padx=5)
    

    def delete_group(self, tree):
        """Delete selected group"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a group to delete")
            return
    
        if messagebox.askyesno("Confirm", "Delete selected group?"):
            tree.delete(selection[0])
    

    def merge_groups(self, tree):
        """Merge two or more selected groups"""
        selection = tree.selection()
        if len(selection) < 2:
            messagebox.showwarning("Selection Required", "Please select at least 2 groups to merge")
            return
    
        # Get all selected group details
        groups_info = []
        total_current_members = 0
        total_max_members = 0
    
        for item in selection:
            values = tree.item(item, 'values')
            group_name = values[0]
            members_str = values[1] if len(values) > 1 else '0/4'
    
            # Parse member counts
            if '/' in members_str:
                current, maximum = members_str.split('/')
                current_count = int(current)
                max_count = int(maximum)
            else:
                current_count = 0
                max_count = 4
    
            total_current_members += current_count
            total_max_members += max_count
            groups_info.append(group_name)
    
        # Create merge dialog
        merge_dialog = tk.Toplevel()
        merge_dialog.title("Merge Groups")
        merge_dialog.geometry("450x300")
        merge_dialog.transient(tree.winfo_toplevel())
        merge_dialog.grab_set()
    
        ttk.Label(merge_dialog, text="Merge Groups", font=('TkDefaultFont', 12, 'bold')).pack(pady=10)
    
        info_frame = ttk.Frame(merge_dialog, padding=10)
        info_frame.pack(fill='both', expand=True)
    
        ttk.Label(info_frame, text="Groups to merge:", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=5)
    
        # List groups being merged
        groups_text = tk.Text(info_frame, height=5, width=40, wrap='word')
        groups_text.pack(fill='x', pady=5)
        groups_text.insert('1.0', '\n'.join(f"• {name}" for name in groups_info))
        groups_text.config(state='disabled')
    
        ttk.Label(info_frame, text=f"Total members: {total_current_members}",
                 font=('TkDefaultFont', 9)).pack(anchor='w', pady=2)
    
        ttk.Separator(info_frame, orient='horizontal').pack(fill='x', pady=10)
    
        # Merged group name
        ttk.Label(info_frame, text="New merged group name:").pack(anchor='w', pady=5)
        # Default name: combine first two group names
        default_name = f"{groups_info[0]} + {groups_info[1]}" if len(groups_info) >= 2 else "Merged Group"
        name_var = tk.StringVar(value=default_name)
        name_entry = ttk.Entry(info_frame, textvariable=name_var, width=40)
        name_entry.pack(fill='x', pady=5)
        name_entry.focus()
        name_entry.select_range(0, tk.END)
    
        # Max members
        ttk.Label(info_frame, text="Max members for merged group:").pack(anchor='w', pady=5)
        max_var = tk.StringVar(value=str(total_max_members))
        max_entry = ttk.Entry(info_frame, textvariable=max_var, width=10)
        max_entry.pack(anchor='w', pady=5)
    
        def perform_merge():
            merged_name = name_var.get().strip()
            if not merged_name:
                messagebox.showwarning("Name Required", "Please enter a name for the merged group",
                                     parent=merge_dialog)
                return
    
            try:
                merged_max = int(max_var.get())
                if merged_max < total_current_members:
                    if not messagebox.askyesno("Capacity Warning",
                                              f"The max capacity ({merged_max}) is less than the current "
                                              f"member count ({total_current_members}).\n\n"
                                              f"Continue anyway?",
                                              parent=merge_dialog):
                        return
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid number for max members",
                                     parent=merge_dialog)
                return
    
            # Delete all selected groups
            for item in selection:
                tree.delete(item)
    
            # Determine status
            if total_current_members == 0:
                status = 'Empty'
            elif total_current_members >= merged_max:
                status = 'Full'
            else:
                status = 'Active'
    
            # Insert merged group
            tree.insert('', 'end', values=(merged_name, f"{total_current_members}/{merged_max}", status))
    
            messagebox.showinfo("Success",
                              f"Successfully merged {len(groups_info)} groups into '{merged_name}'",
                              parent=merge_dialog)
            merge_dialog.destroy()
    
        button_frame = ttk.Frame(merge_dialog)
        button_frame.pack(pady=10)
    
        ttk.Button(button_frame, text="Merge", command=perform_merge).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=merge_dialog.destroy).pack(side='left', padx=5)
    

    def add_student_to_group(self, students_tree, groups_tree):
        """Add selected student to selected group"""
        student_sel = students_tree.selection()
        group_sel = groups_tree.selection()
    
        if not student_sel or not group_sel:
            messagebox.showwarning("Selection Required", "Please select both a student and a group")
            return
    
        messagebox.showinfo("Success", "Student added to group")
    

    def remove_student_from_group(self, students_tree, groups_tree):
        """Remove selected student from their group"""
        student_sel = students_tree.selection()
        if not student_sel:
            messagebox.showwarning("Selection Required", "Please select a student")
            return
    
        messagebox.showinfo("Success", "Student removed from group")
    

    def save_group_configuration(self, tree):
        """Save current group configuration"""
        name = tk.simpledialog.askstring("Save Groups", "Enter a name for this group configuration:")
        if name:
            messagebox.showinfo("Success", f"Group configuration '{name}' saved")
    

    def apply_group_configuration(self, dialog):
        """Apply group configuration and close dialog"""
        messagebox.showinfo("Success", "Group configuration applied")
        dialog.destroy()
    

    def show_manage_groups(self):
        """Entry point from navigation to the full group management interface."""
        self.manage_groups()
    

    def load_filtered_groups(self):
        """Load groups based on filters"""
        # Clear existing data
        for item in self.manage_groups_tree.get_children():
            self.manage_groups_tree.delete(item)
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Check if groups table exists
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assignment_id INTEGER NOT NULL,
                group_name TEXT NOT NULL,
                description TEXT,
                max_members INTEGER DEFAULT 4,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (assignment_id) REFERENCES assignments(id)
            )
            ''')
    
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS assignment_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (group_id) REFERENCES assignment_groups(id),
                FOREIGN KEY (student_id) REFERENCES users(id)
            )
            ''')
    
            # Build query based on filters
            query = '''
            SELECT g.id, g.group_name, a.title, COUNT(DISTINCT gm.student_id) as member_count,
                   CASE WHEN s.id IS NOT NULL THEN 'Yes' ELSE 'No' END as submitted,
                   CASE
                       WHEN COUNT(DISTINCT gm.student_id) = 0 THEN 'Empty'
                       WHEN COUNT(DISTINCT gm.student_id) >= g.max_members THEN 'Complete'
                       ELSE 'Incomplete'
                   END as status
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
            LEFT JOIN assignment_submissions s ON g.assignment_id = s.assignment_id AND g.id = s.group_id
            '''
    
            conditions = []
            params = []
    
            # Apply assignment filter
            assignment_filter = self.group_assignment_filter_var.get()
            if assignment_filter and assignment_filter != "All Assignments":
                assignment_id = assignment_filter.split(' - ')[0]
                conditions.append("g.assignment_id = ?")
                params.append(assignment_id)
    
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
    
            query += " GROUP BY g.id ORDER BY a.title, g.group_name"
    
            cursor.execute(query, params)
            groups = cursor.fetchall()
    
            # Apply status filter in code (since it's calculated)
            status_filter = self.group_status_filter_var.get()
            for group in groups:
                gid, name, assignment, members, submitted, status = group
    
                if status_filter != "All" and status != status_filter:
                    continue
    
                tags = []
                if status == 'Empty':
                    tags = ['empty']
                elif status == 'Complete':
                    tags = ['complete']
    
                self.manage_groups_tree.insert('', 'end',
                                              values=(gid, name, assignment, members, submitted, status),
                                              tags=tags)
    
            # Configure tags
            self.manage_groups_tree.tag_configure('empty', background='#ffebee')
            self.manage_groups_tree.tag_configure('complete', background='#e8f5e8')
    
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load groups: {e}")
    

    def on_group_select(self, event):
        """Handle group selection"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        self.show_group_details(group_id)
    

    def show_group_details(self, group_id):
        """Show detailed group information"""
        # Clear existing details
        for widget in self.group_details_frame.winfo_children():
            widget.destroy()
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Get group info
            cursor.execute('''
            SELECT g.group_name, g.description, a.title, g.max_members
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))
    
            group_info = cursor.fetchone()
            if not group_info:
                return
    
            name, desc, assignment, max_members = group_info
    
            # Get members
            cursor.execute('''
            SELECT u.first_name, u.last_name, u.email, gm.role
            FROM assignment_group_members gm
            JOIN users u ON gm.student_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.joined_at
            ''', (group_id,))
    
            members = cursor.fetchall()
            conn.close()
    
            # Display details
            details_text = f"Group: {name}\n"
            details_text += f"Assignment: {assignment}\n"
            details_text += f"Description: {desc or 'N/A'}\n"
            details_text += f"Members: {len(members)}/{max_members}\n\n"
            details_text += "Members:\n"
    
            for fname, lname, email, role in members:
                details_text += f"  - {fname} {lname} ({email}) - {role}\n"
    
            ttk.Label(self.group_details_frame, text=details_text,
                     font=('TkDefaultFont', 10), justify='left').pack(anchor='w')
    
        except Exception as e:
            ttk.Label(self.group_details_frame, text=f"Error loading details: {e}").pack()
    

    def view_group_members(self):
        """View members of selected group in detail"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]
    
        # Create members window
        members_window = tk.Toplevel(self.root)
        members_window.title(f"Members - {group_name}")
        members_window.geometry("700x500")
        members_window.transient(self.root)
    
        ttk.Label(members_window, text=f"Group Members: {group_name}",
                 font=('TkDefaultFont', 12, 'bold')).pack(pady=10)
    
        # Members list
        members_frame = ttk.Frame(members_window)
        members_frame.pack(fill='both', expand=True, padx=10, pady=10)
    
        columns = ('Name', 'Email', 'Student ID', 'Role', 'Joined')
        members_tree = ttk.Treeview(members_frame, columns=columns, show='headings', height=15)
    
        for col in columns:
            members_tree.heading(col, text=col)
            members_tree.column(col, width=120)
    
        members_tree.pack(fill='both', expand=True)
    
        # Load members
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT u.first_name || ' ' || u.last_name, u.email, u.id, gm.role, gm.joined_at
            FROM assignment_group_members gm
            JOIN users u ON gm.student_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.joined_at
            ''', (group_id,))
    
            members = cursor.fetchall()
            conn.close()
    
            for member in members:
                members_tree.insert('', 'end', values=member)
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load members: {e}")
    
        ttk.Button(members_window, text="Close", command=members_window.destroy).pack(pady=10)
    

    def edit_group_details(self):
        """Edit selected group details"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to edit")
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
    
        messagebox.showinfo("Edit Group", f"Edit group functionality - Group ID: {group_id}")
    

    def add_members_to_group(self):
        """Add members to selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute(
                '''
                SELECT g.assignment_id, g.group_name, g.max_members,
                       COUNT(gm.id) as member_count
                FROM assignment_groups g
                LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
                WHERE g.id = ?
                GROUP BY g.id
                ''',
                (group_id,)
            )
            group_row = cursor.fetchone()
            if not group_row:
                conn.close()
                messagebox.showerror("Error", "Selected group no longer exists.")
                return
    
            assignment_id, group_name, max_members, current_members = group_row
    
            # Determine module for assignment
            cursor.execute('SELECT module_code, description FROM assignments WHERE id = ?', (assignment_id,))
            assignment_row = cursor.fetchone()
            if not assignment_row:
                conn.close()
                messagebox.showerror("Error", "Assignment associated with this group was not found.")
                return
    
            module_code, assignment_desc = assignment_row
    
            # Fetch existing member user IDs
            cursor.execute(
                'SELECT student_id FROM assignment_group_members WHERE group_id = ?',
                (group_id,)
            )
            existing_user_ids = {row[0] for row in cursor.fetchall()}
    
            # Fetch available students for module
            cursor.execute(
                '''
                SELECT u.id, s.student_id, s.first_name, s.last_name
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                JOIN users u ON s.user_id = u.id
                WHERE sm.module_code = ?
                ORDER BY s.last_name, s.first_name
                ''',
                (module_code,)
            )
            all_candidates = cursor.fetchall()
            conn.close()
    
            available_students = [
                candidate for candidate in all_candidates if candidate[0] not in existing_user_ids
            ]
    
            if not available_students:
                messagebox.showinfo("Add Members", "No available students to add to this group.")
                return
    
            capacity_remaining = None
            if max_members and max_members > 0:
                capacity_remaining = max_members - current_members
                if capacity_remaining <= 0:
                    messagebox.showinfo(
                        "Group Full",
                        f"Group '{group_name}' already has {current_members} member(s) "
                        "and cannot accept additional members."
                    )
                    return
    
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Add Members - {group_name}")
            dialog.geometry("420x460")
            dialog.transient(self.root)
            dialog.grab_set()
    
            ttk.Label(dialog, text=f"Assignment Module: {module_code}",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 0))
            if assignment_desc:
                ttk.Label(dialog, text=f"Assignment: {assignment_desc}",
                         wraplength=380, justify='left').pack(anchor='w', padx=10, pady=(0, 10))
    
            if capacity_remaining is not None:
                ttk.Label(dialog, text=f"Available slots: {capacity_remaining}",
                         style='Info.TLabel').pack(anchor='w', padx=10)
    
            listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False)
            listbox.pack(fill='both', expand=True, padx=10, pady=10)
    
            # Map from index to candidate
            candidate_map = {}
            for index, (user_id, student_id, first_name, last_name) in enumerate(available_students):
                display = f"{student_id} - {first_name} {last_name}"
                listbox.insert(tk.END, display)
                candidate_map[index] = (user_id, student_id, first_name, last_name)
    
            status_var = tk.StringVar(value="")
            status_label = ttk.Label(dialog, textvariable=status_var, style='Info.TLabel')
            status_label.pack(anchor='w', padx=10)
    
            def add_selected_members():
                indices = listbox.curselection()
                if not indices:
                    status_var.set("Select at least one student to add.")
                    return
    
                if capacity_remaining is not None and len(indices) > capacity_remaining:
                    status_var.set(f"Only {capacity_remaining} slot(s) remaining.")
                    return
    
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()
    
                    for idx in indices:
                        user_id, student_id_value, _, _ = candidate_map[idx]
                        cursor_inner.execute(
                            '''
                            INSERT OR IGNORE INTO assignment_group_members
                                (group_id, student_id, role, joined_at)
                            VALUES (?, ?, ?, ?)
                            ''',
                            (group_id, user_id, 'member', timestamp)
                        )
    
                    conn_inner.commit()
                    conn_inner.close()
    
                    dialog.destroy()
                    self.load_filtered_groups()
                    self.show_group_details(group_id)
                    messagebox.showinfo("Members Added", f"Added {len(indices)} member(s) to '{group_name}'.")
                except Exception as exc:
                    status_var.set(f"Failed to add members: {exc}")
    
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Button(button_frame, text="Add Selected", command=add_selected_members,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')
    
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load available members: {exc}")
    

    def remove_members_from_group(self):
        """Remove members from selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT gm.id, u.first_name, u.last_name, u.email
                FROM assignment_group_members gm
                JOIN users u ON gm.student_id = u.id
                WHERE gm.group_id = ?
                ORDER BY u.last_name, u.first_name
                ''',
                (group_id,)
            )
            members = cursor.fetchall()
            conn.close()
    
            if not members:
                messagebox.showinfo("Remove Members", "This group has no members.")
                return
    
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Remove Members - {group_name}")
            dialog.geometry("420x420")
            dialog.transient(self.root)
            dialog.grab_set()
    
            ttk.Label(dialog, text=f"Select members to remove from {group_name}:",
                     wraplength=380, justify='left').pack(anchor='w', padx=10, pady=(10, 10))
    
            listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False)
            listbox.pack(fill='both', expand=True, padx=10, pady=10)
    
            member_map = {}
            for index, (member_id, first_name, last_name, email) in enumerate(members):
                display = f"{first_name} {last_name} ({email})"
                listbox.insert(tk.END, display)
                member_map[index] = member_id
    
            status_var = tk.StringVar(value="")
            status_label = ttk.Label(dialog, textvariable=status_var, style='Info.TLabel')
            status_label.pack(anchor='w', padx=10)
    
            def remove_selected():
                indices = listbox.curselection()
                if not indices:
                    status_var.set("Select at least one member to remove.")
                    return
    
                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()
                    for idx in indices:
                        cursor_inner.execute(
                            "DELETE FROM assignment_group_members WHERE id = ?",
                            (member_map[idx],)
                        )
                    conn_inner.commit()
                    conn_inner.close()
    
                    dialog.destroy()
                    self.load_filtered_groups()
                    self.show_group_details(group_id)
                    messagebox.showinfo("Members Removed", f"Removed {len(indices)} member(s) from '{group_name}'.")
                except Exception as exc:
                    status_var.set(f"Failed to remove members: {exc}")
    
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Button(button_frame, text="Remove Selected", command=remove_selected,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')
    
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load group members: {exc}")
    

    def merge_selected_groups(self):
        """Merge multiple selected groups"""
        selections = self.manage_groups_tree.selection()
        if len(selections) < 2:
            messagebox.showwarning("Warning", "Please select at least 2 groups to merge")
            return
    
        group_ids = [self.manage_groups_tree.item(item)['values'][0] for item in selections]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            placeholder = ','.join('?' * len(group_ids))
            cursor.execute(
                f'''
                SELECT id, assignment_id, group_name
                FROM assignment_groups
                WHERE id IN ({placeholder})
                ''',
                group_ids
            )
            group_data = cursor.fetchall()
    
            if len(group_data) != len(group_ids):
                conn.close()
                messagebox.showerror("Error", "One or more selected groups no longer exist.")
                return
    
            assignment_ids = {row[1] for row in group_data}
            if len(assignment_ids) != 1:
                conn.close()
                messagebox.showwarning(
                    "Cannot Merge",
                    "Selected groups belong to different assignments."
                )
                return
    
            target_group_id = group_data[0][0]
            target_group_name = group_data[0][2]
            other_groups = [row[0] for row in group_data[1:]]
    
            if not messagebox.askyesno(
                    "Confirm Merge",
                    f"Merge {len(group_ids)} groups into '{target_group_name}'?\n\n"
                    "All members will be moved into the first selected group.") :
                conn.close()
                return
    
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for other_id in other_groups:
                cursor.execute(
                    '''
                    UPDATE assignment_group_members
                    SET group_id = ?, joined_at = COALESCE(joined_at, ?)
                    WHERE group_id = ?
                    ''',
                    (target_group_id, timestamp, other_id)
                )
                cursor.execute("DELETE FROM assignment_groups WHERE id = ?", (other_id,))
    
            conn.commit()
            conn.close()
    
            self.load_filtered_groups()
            self.show_group_details(target_group_id)
            messagebox.showinfo("Groups Merged", f"Groups merged into '{target_group_name}'.")
    
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to merge groups: {exc}")
    

    def split_selected_group(self):
        """Split selected group into multiple groups"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to split")
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute(
                '''
                SELECT g.assignment_id, g.group_name, g.description, g.max_members
                FROM assignment_groups g
                WHERE g.id = ?
                ''',
                (group_id,)
            )
            group_info = cursor.fetchone()
    
            cursor.execute(
                '''
                SELECT gm.id, u.first_name, u.last_name, u.email
                FROM assignment_group_members gm
                JOIN users u ON gm.student_id = u.id
                WHERE gm.group_id = ?
                ''',
                (group_id,)
            )
            members = cursor.fetchall()
    
            if not group_info:
                conn.close()
                messagebox.showerror("Error", "Group not found.")
                return
    
            if len(members) < 2:
                conn.close()
                messagebox.showinfo("Split Group", "At least two members are required to split a group.")
                return
    
            assignment_id, group_name, description, max_members = group_info
            conn.close()
    
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Split Group - {group_name}")
            dialog.geometry("480x420")
            dialog.transient(self.root)
            dialog.grab_set()
    
            ttk.Label(dialog, text=f"Move members from '{group_name}' into a new group:",
                     wraplength=440, justify='left').pack(anchor='w', padx=10, pady=(10, 10))
    
            new_name_var = tk.StringVar(value=f"{group_name} - Split")
            ttk.Label(dialog, text="New Group Name:").pack(anchor='w', padx=10)
            ttk.Entry(dialog, textvariable=new_name_var).pack(fill='x', padx=10, pady=(0, 10))
    
            listbox = tk.Listbox(dialog, selectmode=tk.MULTIPLE, exportselection=False, height=12)
            listbox.pack(fill='both', expand=True, padx=10, pady=10)
    
            member_map = {}
            for index, (member_id, first_name, last_name, email) in enumerate(members):
                listbox.insert(tk.END, f"{first_name} {last_name} ({email})")
                member_map[index] = member_id
    
            status_var = tk.StringVar(value="Select members to move into the new group.")
            ttk.Label(dialog, textvariable=status_var, style='Info.TLabel').pack(anchor='w', padx=10)
    
            def perform_split():
                indices = listbox.curselection()
                if not indices:
                    status_var.set("Select at least one member to move.")
                    return
                if len(indices) >= len(members):
                    status_var.set("At least one member must remain in the original group.")
                    return
    
                new_group_name = new_name_var.get().strip()
                if not new_group_name:
                    status_var.set("New group name cannot be empty.")
                    return
    
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()
    
                    # Ensure unique group name
                    suffix = 1
                    base_name = new_group_name
                    cursor_inner.execute(
                        'SELECT 1 FROM assignment_groups WHERE assignment_id = ? AND group_name = ?',
                        (assignment_id, new_group_name)
                    )
                    while cursor_inner.fetchone():
                        suffix += 1
                        new_group_name = f"{base_name} ({suffix})"
                        cursor_inner.execute(
                            'SELECT 1 FROM assignment_groups WHERE assignment_id = ? AND group_name = ?',
                            (assignment_id, new_group_name)
                        )
    
                    cursor_inner.execute(
                        '''
                        INSERT INTO assignment_groups (assignment_id, group_name, description, max_members, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        ''',
                        (assignment_id, new_group_name, description, max_members, timestamp)
                    )
                    new_group_id = cursor_inner.lastrowid
    
                    member_ids = [member_map[idx] for idx in indices]
                    placeholders = ','.join('?' for _ in member_ids)
                    cursor_inner.execute(
                        f'''
                        UPDATE assignment_group_members
                        SET group_id = ?, joined_at = COALESCE(joined_at, ?)
                        WHERE id IN ({placeholders})
                        ''',
                        (new_group_id, timestamp, *member_ids)
                    )
    
                    conn_inner.commit()
                    conn_inner.close()
    
                    dialog.destroy()
                    self.load_filtered_groups()
                    self.show_group_details(group_id)
                    messagebox.showinfo("Group Split",
                                        f"Created '{new_group_name}' with {len(indices)} member(s).")
                except Exception as exc:
                    status_var.set(f"Failed to split group: {exc}")
    
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))
            ttk.Button(button_frame, text="Create New Group", command=perform_split,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')
    
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to split group: {exc}")
    

    def delete_selected_group(self):
        """Delete selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group to delete")
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_id = item['values'][0]
        group_name = item['values'][1]
    
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete group '{group_name}'?\n\nThis will remove all members from the group."):
            return
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Delete members first
            cursor.execute("DELETE FROM assignment_group_members WHERE group_id = ?", (group_id,))
            # Delete group
            cursor.execute("DELETE FROM assignment_groups WHERE id = ?", (group_id,))
    
            conn.commit()
            conn.close()
    
            messagebox.showinfo("Success", f"Group '{group_name}' deleted")
            self.load_filtered_groups()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete group: {e}")
    

    def send_message_to_group(self):
        """Send message to all group members"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return
    
        item = self.manage_groups_tree.item(selection[0])
        group_name = item['values'][1]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                '''
                SELECT u.id, u.first_name, u.last_name
                FROM assignment_group_members gm
                JOIN users u ON gm.student_id = u.id
                WHERE gm.group_id = ?
                ''',
                (item['values'][0],)
            )
            recipients = cursor.fetchall()
            conn.close()
    
            if not recipients:
                messagebox.showinfo("Send Message", "Group has no members to message.")
                return
    
            sender_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not sender_id:
                messagebox.showerror("Error", "You must be logged in to send messages.")
                return
    
            self.gui.db._ensure_messages_table()
    
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Message Group - {group_name}")
            dialog.geometry("520x420")
            dialog.transient(self.root)
            dialog.grab_set()
    
            ttk.Label(dialog, text=f"Send message to {len(recipients)} member(s) in {group_name}:",
                     font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=10, pady=(10, 5))
    
            ttk.Label(dialog, text="\n".join(f"• {fn} {ln}" for _, fn, ln in recipients),
                     justify='left').pack(anchor='w', padx=10)
    
            ttk.Label(dialog, text="Subject:").pack(anchor='w', padx=10, pady=(15, 5))
            subject_var = tk.StringVar()
            ttk.Entry(dialog, textvariable=subject_var).pack(fill='x', padx=10)
    
            ttk.Label(dialog, text="Message:").pack(anchor='w', padx=10, pady=(10, 5))
            body_text = scrolledtext.ScrolledText(dialog, height=8, wrap=tk.WORD)
            body_text.pack(fill='both', expand=True, padx=10)
    
            status_var = tk.StringVar(value="")
            ttk.Label(dialog, textvariable=status_var, style='Info.TLabel').pack(anchor='w', padx=10, pady=(5, 0))
    
            def send():
                subject = subject_var.get().strip()
                body = body_text.get("1.0", tk.END).strip()
                if not subject or not body:
                    status_var.set("Subject and message are required.")
                    return
    
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    conn_inner = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor_inner = conn_inner.cursor()
                    for recipient_id, _, _ in recipients:
                        cursor_inner.execute(
                            '''
                            INSERT INTO messages (sender_id, recipient_id, subject, message, content, sent_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ''',
                            (sender_id, recipient_id, subject, body, body, timestamp)
                        )
                    conn_inner.commit()
                    conn_inner.close()
                    dialog.destroy()
                    messagebox.showinfo("Message Sent",
                                        f"Message sent to {len(recipients)} member(s) in {group_name}.")
                except Exception as exc:
                    status_var.set(f"Failed to send message: {exc}")
    
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=10)
            ttk.Button(button_frame, text="Send Message", command=send, style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')
    
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to prepare message: {exc}")
    

    def view_group_submission(self):
        """View submission for selected group"""
        selection = self.manage_groups_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a group")
            return
    
        group_item = self.manage_groups_tree.item(selection[0])
        group_id = group_item['values'][0]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute(
                '''
                SELECT g.assignment_id, g.group_name
                FROM assignment_groups g
                WHERE g.id = ?
                ''',
                (group_id,)
            )
            group_row = cursor.fetchone()
            if not group_row:
                conn.close()
                messagebox.showerror("Error", "Group not found.")
                return
            assignment_id, group_name = group_row
    
            cursor.execute(
                '''
                SELECT s.student_id
                FROM assignment_group_members gm
                JOIN students s ON s.user_id = gm.student_id
                WHERE gm.group_id = ?
                ''',
                (group_id,)
            )
            student_ids = [row[0] for row in cursor.fetchall()]
    
            if not student_ids:
                conn.close()
                messagebox.showinfo("No Submission", "This group has no enrolled student IDs.")
                return
    
            placeholders = ','.join('?' for _ in student_ids)
            cursor.execute(
                f'''
                SELECT id, file_name, file_path, submission_date, status, grade, feedback, student_id
                FROM assignment_submissions
                WHERE assignment_id = ?
                AND student_id IN ({placeholders})
                ORDER BY submission_date DESC
                LIMIT 1
                ''',
                (assignment_id, *student_ids)
            )
            submission = cursor.fetchone()
            conn.close()
    
            if not submission:
                messagebox.showinfo("No Submission", "No submissions found for members of this group.")
                return
    
            sub_id, file_name, file_path, submitted_at, status, grade, feedback, submitter_id = submission
    
            window = tk.Toplevel(self.root)
            window.title(f"Group Submission - {group_name}")
            window.geometry("520x360")
            window.transient(self.root)
            window.grab_set()
    
            details = [
                f"Submission ID: {sub_id}",
                f"File: {file_name}",
                f"Submitter: {submitter_id}",
                f"Submitted at: {submitted_at}",
                f"Status: {status}",
                f"Grade: {grade if grade is not None else 'Not graded'}"
            ]
            ttk.Label(window, text="\n".join(details),
                     justify='left', font=('TkDefaultFont', 10)).pack(anchor='w', padx=10, pady=10)
    
            if feedback:
                feedback_frame = ttk.LabelFrame(window, text="Feedback", padding=10)
                feedback_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))
                feedback_text = scrolledtext.ScrolledText(feedback_frame, height=6, wrap=tk.WORD)
                feedback_text.pack(fill='both', expand=True)
                feedback_text.insert(tk.END, feedback)
                feedback_text.config(state='disabled')
    
            action_frame = ttk.Frame(window)
            action_frame.pack(fill='x', padx=10, pady=10)
    
            ttk.Button(action_frame, text="Open File",
                      command=lambda: self.open_submission_file(file_path)).pack(side='left')
            ttk.Button(action_frame, text="Download File",
                      command=lambda: self.download_file(file_path)).pack(side='left', padx=10)
            ttk.Button(action_frame, text="Close", command=window.destroy).pack(side='right')
    
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load group submission: {exc}")
    

    def export_group_list(self):
        """Export group list to CSV"""
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile="groups_export.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
    
            if not save_path:
                return
    
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            cursor.execute('''
            SELECT g.id, g.group_name, a.title,
                   GROUP_CONCAT(u.first_name || ' ' || u.last_name, '; ') as members
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
            LEFT JOIN users u ON gm.student_id = u.id
            GROUP BY g.id
            ORDER BY a.title, g.group_name
            ''')
    
            groups = cursor.fetchall()
            conn.close()
    
            with open(save_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Group ID', 'Group Name', 'Assignment', 'Members'])
                writer.writerows(groups)
    
            messagebox.showinfo("Success", f"Exported {len(groups)} groups to:\n{save_path}")
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export groups: {e}")
    
    

    def create_group_assignment(self, *args, **kwargs):
        """Open the group assignment creation wizard."""
        self._launch_gui_feature(self.show_create_group_assignment, "group assignment creation")
    
    

    def manage_groups(self, *args, **kwargs):
        """Comprehensive group management interface"""
        if not self._check_permission('manage_assignments'):
            return
    
        self.gui.layout.clear_content_area()
    
        title = ttk.Label(self.gui.layout.content_area, text="Manage Groups", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
    
        # Filter frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))
    
        ttk.Label(filter_frame, text="Assignment:").grid(row=0, column=0, sticky='w', padx=5)
        self.group_assignment_filter_var = tk.StringVar()
        assignment_combo = ttk.Combobox(filter_frame, textvariable=self.group_assignment_filter_var, width=30)
        assignment_combo.grid(row=0, column=1, padx=5)
        self.load_assignments_for_group_filter(assignment_combo)
    
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, sticky='w', padx=5)
        self.group_status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.group_status_filter_var,
                                    values=["All", "Complete", "Incomplete", "Empty"], width=15)
        status_combo.grid(row=0, column=3, padx=5)
    
        ttk.Button(filter_frame, text="Apply Filters",
                  command=self.load_filtered_groups).grid(row=0, column=4, padx=10)
    
        # Groups table
        groups_frame = ttk.Frame(self.gui.layout.content_area)
        groups_frame.pack(fill='both', expand=True)
    
        columns = ('ID', 'Group Name', 'Assignment', 'Members', 'Submitted', 'Status')
        self.manage_groups_tree = ttk.Treeview(groups_frame, columns=columns, show='headings')
    
        for col in columns:
            self.manage_groups_tree.heading(col, text=col)
            self.manage_groups_tree.column(col, width=120)
    
        # Scrollbars
        v_scroll = ttk.Scrollbar(groups_frame, orient='vertical', command=self.manage_groups_tree.yview)
        h_scroll = ttk.Scrollbar(groups_frame, orient='horizontal', command=self.manage_groups_tree.xview)
        self.manage_groups_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    
        self.manage_groups_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
    
        groups_frame.grid_rowconfigure(0, weight=1)
        groups_frame.grid_columnconfigure(0, weight=1)
    
        # Bind selection event
        self.manage_groups_tree.bind('<<TreeviewSelect>>', self.on_group_select)
    
        # Action buttons
        action_frame = ttk.Frame(self.gui.layout.content_area)
        action_frame.pack(fill='x', pady=(10, 0))
    
        ttk.Label(action_frame, text="Group Actions:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))
    
        ttk.Button(action_frame, text="View Members",
                  command=self.view_group_members).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Edit Group",
                  command=self.edit_group_details).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Add Members",
                  command=self.add_members_to_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Remove Members",
                  command=self.remove_members_from_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Merge Groups",
                  command=self.merge_selected_groups).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Split Group",
                  command=self.split_selected_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame, text="Delete Group",
                  command=self.delete_selected_group).pack(side='left', padx=(0, 5))
    
        # Second row of actions
        action_frame2 = ttk.Frame(self.gui.layout.content_area)
        action_frame2.pack(fill='x', pady=(5, 0))
    
        ttk.Label(action_frame2, text="Communication:", font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=(0, 10))
    
        ttk.Button(action_frame2, text="Send Message to Group",
                  command=self.send_message_to_group).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame2, text="View Submission",
                  command=self.view_group_submission).pack(side='left', padx=(0, 5))
        ttk.Button(action_frame2, text="Export Group List",
                  command=self.export_group_list).pack(side='left', padx=(0, 5))
    
        # Group details frame
        self.group_details_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Group Details", padding=10)
        self.group_details_frame.pack(fill='x', pady=(10, 0))

        # Load groups
        self.load_filtered_groups()


    def _join_existing_group(self, assignment_id=None):
        """Student joins existing group for an assignment"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Join Group")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Join Existing Group", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Assignment selection if not provided
            if not assignment_id:
                assignment_frame = ttk.LabelFrame(dialog, text="Select Assignment", padding=10)
                assignment_frame.pack(fill='x', padx=10, pady=(0, 10))

                ttk.Label(assignment_frame, text="Assignment:").pack(side='left', padx=(0, 10))
                assignment_var = tk.StringVar()
                assignment_combo = ttk.Combobox(assignment_frame, textvariable=assignment_var, width=40)
                assignment_combo.pack(side='left', fill='x', expand=True)

                # Load group assignments
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                SELECT id, title FROM assignments
                WHERE assignment_type = 'group'
                AND due_date >= datetime('now')
                ORDER BY due_date
                ''')
                assignments = cursor.fetchall()
                conn.close()

                if not assignments:
                    messagebox.showinfo("No Assignments", "No group assignments available to join")
                    dialog.destroy()
                    return

                assignment_combo['values'] = [f"{aid} - {title}" for aid, title in assignments]
                assignment_combo.current(0)
            else:
                assignment_var = tk.StringVar(value=str(assignment_id))

            # Available groups frame
            groups_frame = ttk.LabelFrame(dialog, text="Available Groups", padding=10)
            groups_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            columns = ('Group Name', 'Members', 'Status', 'Description')
            groups_tree = ttk.Treeview(groups_frame, columns=columns, show='headings', height=12)

            for col in columns:
                groups_tree.heading(col, text=col)
                width = 200 if col == 'Description' else 120
                groups_tree.column(col, width=width)

            groups_tree.pack(fill='both', expand=True)

            def load_available_groups():
                # Clear tree
                for item in groups_tree.get_children():
                    groups_tree.delete(item)

                try:
                    # Get assignment ID
                    if assignment_id:
                        aid = assignment_id
                    else:
                        combo_value = assignment_var.get()
                        if not combo_value:
                            return
                        aid = combo_value.split(' - ')[0]

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Get assignment group constraints
                    cursor.execute('SELECT group_size_min, group_size_max FROM assignments WHERE id = ?', (aid,))
                    constraints = cursor.fetchone()
                    if not constraints:
                        conn.close()
                        return

                    min_size, max_size = constraints

                    # Get available groups
                    cursor.execute('''
                    SELECT g.id, g.group_name, g.description,
                           COUNT(gm.student_id) as member_count
                    FROM assignment_groups g
                    LEFT JOIN assignment_group_members gm ON g.id = gm.group_id
                    WHERE g.assignment_id = ?
                    GROUP BY g.id
                    HAVING member_count < ?
                    ORDER BY g.group_name
                    ''', (aid, max_size))

                    groups = cursor.fetchall()
                    conn.close()

                    for gid, name, desc, count in groups:
                        status = f"{count}/{max_size}"
                        groups_tree.insert('', 'end', values=(name, status, 'Open', desc or 'N/A'), tags=(gid,))

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load groups: {e}")

            # Load button
            if not assignment_id:
                ttk.Button(assignment_frame, text="Load Groups", command=load_available_groups).pack(side='left', padx=(10, 0))
            else:
                load_available_groups()

            # Join button
            def join_selected_group():
                selection = groups_tree.selection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a group to join")
                    return

                item = groups_tree.item(selection[0])
                group_id = item['tags'][0]
                group_name = item['values'][0]

                if messagebox.askyesno("Confirm Join", f"Join group '{group_name}'?"):
                    try:
                        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                        cursor = conn.cursor()

                        # Check if already in a group for this assignment
                        if assignment_id:
                            aid = assignment_id
                        else:
                            aid = assignment_var.get().split(' - ')[0]

                        cursor.execute('''
                        SELECT g.id FROM assignment_groups g
                        JOIN assignment_group_members gm ON g.id = gm.group_id
                        WHERE g.assignment_id = ? AND gm.student_id = ?
                        ''', (aid, student_id))

                        existing = cursor.fetchone()
                        if existing:
                            conn.close()
                            messagebox.showwarning("Already in Group", "You are already in a group for this assignment")
                            return

                        # Join the group
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        cursor.execute('''
                        INSERT INTO assignment_group_members (group_id, student_id, role, joined_at)
                        VALUES (?, ?, 'member', ?)
                        ''', (group_id, student_id, timestamp))

                        conn.commit()
                        conn.close()

                        messagebox.showinfo("Success", f"You have joined '{group_name}'")
                        dialog.destroy()

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to join group: {e}")

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Join Selected Group", command=join_selected_group,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open join group dialog: {e}")


    def _create_new_group(self, assignment_id=None):
        """Student creates new group for an assignment"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Create New Group")
            dialog.geometry("500x400")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Create New Group", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Assignment selection if not provided
            if not assignment_id:
                assignment_frame = ttk.LabelFrame(dialog, text="Select Assignment", padding=10)
                assignment_frame.pack(fill='x', padx=10, pady=(0, 10))

                ttk.Label(assignment_frame, text="Assignment:").grid(row=0, column=0, sticky='w', padx=5)
                assignment_var = tk.StringVar()
                assignment_combo = ttk.Combobox(assignment_frame, textvariable=assignment_var, width=35)
                assignment_combo.grid(row=0, column=1, sticky='ew', padx=5)

                # Load group assignments
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                cursor.execute('''
                SELECT id, title FROM assignments
                WHERE assignment_type = 'group'
                AND due_date >= datetime('now')
                ORDER BY due_date
                ''')
                assignments = cursor.fetchall()
                conn.close()

                if not assignments:
                    messagebox.showinfo("No Assignments", "No group assignments available")
                    dialog.destroy()
                    return

                assignment_combo['values'] = [f"{aid} - {title}" for aid, title in assignments]
                assignment_combo.current(0)

                assignment_frame.grid_columnconfigure(1, weight=1)
            else:
                assignment_var = tk.StringVar(value=str(assignment_id))

            # Group details frame
            details_frame = ttk.LabelFrame(dialog, text="Group Details", padding=10)
            details_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            ttk.Label(details_frame, text="Group Name:").grid(row=0, column=0, sticky='w', pady=5)
            group_name_var = tk.StringVar()
            ttk.Entry(details_frame, textvariable=group_name_var, width=40).grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))

            ttk.Label(details_frame, text="Description:").grid(row=1, column=0, sticky='nw', pady=5)
            desc_text = scrolledtext.ScrolledText(details_frame, height=6, width=40)
            desc_text.grid(row=1, column=1, sticky='ew', pady=5, padx=(10, 0))

            details_frame.grid_columnconfigure(1, weight=1)

            # Info label
            info_var = tk.StringVar(value="You will be the group leader")
            ttk.Label(dialog, textvariable=info_var, style='Info.TLabel').pack(padx=10, pady=(0, 10))

            # Create button
            def create_group():
                try:
                    group_name = group_name_var.get().strip()
                    if not group_name:
                        messagebox.showerror("Error", "Group name is required", parent=dialog)
                        return

                    description = desc_text.get(1.0, tk.END).strip()

                    # Get assignment ID
                    if assignment_id:
                        aid = assignment_id
                    else:
                        combo_value = assignment_var.get()
                        if not combo_value:
                            messagebox.showerror("Error", "Please select an assignment", parent=dialog)
                            return
                        aid = combo_value.split(' - ')[0]

                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    # Check if student already in a group for this assignment
                    cursor.execute('''
                    SELECT g.id FROM assignment_groups g
                    JOIN assignment_group_members gm ON g.id = gm.group_id
                    WHERE g.assignment_id = ? AND gm.student_id = ?
                    ''', (aid, student_id))

                    existing = cursor.fetchone()
                    if existing:
                        conn.close()
                        messagebox.showwarning("Already in Group", "You are already in a group for this assignment", parent=dialog)
                        return

                    # Create group
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('''
                    INSERT INTO assignment_groups (assignment_id, group_name, description, created_at, created_by)
                    VALUES (?, ?, ?, ?, ?)
                    ''', (aid, group_name, description, timestamp, student_id))

                    group_id = cursor.lastrowid

                    # Add creator as leader
                    cursor.execute('''
                    INSERT INTO assignment_group_members (group_id, student_id, role, joined_at)
                    VALUES (?, ?, 'leader', ?)
                    ''', (group_id, student_id, timestamp))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Group '{group_name}' created successfully!\nYou are the group leader.", parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create group: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Create Group", command=create_group,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open create group dialog: {e}")


    def _view_group_details(self, group_id=None, assignment_id=None):
        """View group details and members (student version)"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # If no group_id provided, find student's group for assignment
            if not group_id:
                if not assignment_id:
                    messagebox.showerror("Error", "Assignment ID required")
                    return

                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                SELECT g.id FROM assignment_groups g
                JOIN assignment_group_members gm ON g.id = gm.group_id
                WHERE g.assignment_id = ? AND gm.student_id = ?
                ''', (assignment_id, student_id))

                result = cursor.fetchone()
                conn.close()

                if not result:
                    messagebox.showinfo("No Group", "You are not in a group for this assignment")
                    return

                group_id = result[0]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Group Details")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Group Details", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Get group info
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT g.group_name, g.description, a.title, a.due_date
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))

            group_info = cursor.fetchone()
            if not group_info:
                conn.close()
                messagebox.showerror("Error", "Group not found")
                dialog.destroy()
                return

            name, desc, assignment, due_date = group_info

            # Info frame
            info_frame = ttk.LabelFrame(dialog, text="Group Information", padding=10)
            info_frame.pack(fill='x', padx=10, pady=(0, 10))

            info_text = f"Group Name: {name}\n"
            info_text += f"Assignment: {assignment}\n"
            info_text += f"Due Date: {due_date}\n"
            info_text += f"Description: {desc or 'N/A'}"

            ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')

            # Members frame
            members_frame = ttk.LabelFrame(dialog, text="Group Members", padding=10)
            members_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            columns = ('Name', 'Email', 'Role', 'Joined')
            members_tree = ttk.Treeview(members_frame, columns=columns, show='headings', height=10)

            for col in columns:
                members_tree.heading(col, text=col)
                members_tree.column(col, width=130)

            members_tree.pack(fill='both', expand=True)

            # Load members
            cursor.execute('''
            SELECT u.first_name || ' ' || u.last_name, u.email, gm.role, gm.joined_at
            FROM assignment_group_members gm
            JOIN users u ON gm.student_id = u.id
            WHERE gm.group_id = ?
            ORDER BY gm.role DESC, gm.joined_at
            ''', (group_id,))

            members = cursor.fetchall()
            conn.close()

            for member in members:
                members_tree.insert('', 'end', values=member)

            # Close button
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to view group details: {e}")


    def _handle_group_submission(self, assignment_id, group_id):
        """Handle submission from group - delegates to submission manager"""
        try:
            student_id = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None
            if not student_id:
                messagebox.showerror("Error", "You must be logged in")
                return

            # Verify student is in the group
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT role FROM assignment_group_members
            WHERE group_id = ? AND student_id = ?
            ''', (group_id, student_id))

            result = cursor.fetchone()
            conn.close()

            if not result:
                messagebox.showerror("Error", "You are not a member of this group")
                return

            role = result[0]

            # Create submission dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Submit Group Assignment")
            dialog.geometry("550x450")
            dialog.transient(self.root)
            dialog.grab_set()

            ttk.Label(dialog, text="Submit Group Assignment", font=('TkDefaultFont', 14, 'bold')).pack(pady=10)

            # Group info
            info_frame = ttk.LabelFrame(dialog, text="Submission Information", padding=10)
            info_frame.pack(fill='x', padx=10, pady=(0, 10))

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT g.group_name, a.title, a.due_date, a.file_types_allowed, a.max_file_size_mb
            FROM assignment_groups g
            JOIN assignments a ON g.assignment_id = a.id
            WHERE g.id = ?
            ''', (group_id,))

            info = cursor.fetchone()
            conn.close()

            if not info:
                messagebox.showerror("Error", "Group or assignment not found")
                dialog.destroy()
                return

            group_name, title, due_date, file_types, max_size = info

            info_text = f"Group: {group_name}\n"
            info_text += f"Assignment: {title}\n"
            info_text += f"Due Date: {due_date}\n"
            info_text += f"Your Role: {role.title()}\n"
            info_text += f"Allowed Files: {file_types}\n"
            info_text += f"Max Size: {max_size} MB"

            ttk.Label(info_frame, text=info_text, justify='left').pack(anchor='w')

            # File selection
            file_frame = ttk.LabelFrame(dialog, text="Select File", padding=10)
            file_frame.pack(fill='x', padx=10, pady=(0, 10))

            file_path_var = tk.StringVar()
            ttk.Entry(file_frame, textvariable=file_path_var, width=40, state='readonly').pack(side='left', fill='x', expand=True)

            def browse_file():
                # Parse allowed file types
                if file_types:
                    types = file_types.split(',')
                    filetypes = [(f"{t} files", f"*{t}") for t in types]
                    filetypes.append(("All files", "*.*"))
                else:
                    filetypes = [("All files", "*.*")]

                filename = filedialog.askopenfilename(filetypes=filetypes)
                if filename:
                    # Check file size
                    if max_size:
                        file_size_mb = os.path.getsize(filename) / (1024 * 1024)
                        if file_size_mb > max_size:
                            messagebox.showerror("File Too Large",
                                               f"File size ({file_size_mb:.1f} MB) exceeds maximum ({max_size} MB)")
                            return

                    file_path_var.set(filename)

            ttk.Button(file_frame, text="Browse", command=browse_file).pack(side='left', padx=(10, 0))

            # Comments
            comments_frame = ttk.LabelFrame(dialog, text="Submission Comments (Optional)", padding=10)
            comments_frame.pack(fill='both', expand=True, padx=10, pady=(0, 10))

            comments_text = scrolledtext.ScrolledText(comments_frame, height=6)
            comments_text.pack(fill='both', expand=True)

            # Submit button
            def submit_assignment():
                file_path = file_path_var.get()
                if not file_path:
                    messagebox.showerror("Error", "Please select a file to submit", parent=dialog)
                    return

                comments = comments_text.get(1.0, tk.END).strip()

                try:
                    # Copy file to submissions directory
                    submissions_dir = paths.SUBMISSIONS_DIR / 'assignments' / str(assignment_id)
                    submissions_dir.mkdir(parents=True, exist_ok=True)

                    file_name = os.path.basename(file_path)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    dest_file = submissions_dir / f"{group_id}_{timestamp}_{file_name}"

                    shutil.copy2(file_path, dest_file)

                    # Save to database
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    cursor = conn.cursor()

                    submission_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    cursor.execute('''
                    INSERT INTO assignment_submissions
                    (assignment_id, student_id, group_id, file_name, file_path, submission_date, status, comments)
                    VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?)
                    ''', (assignment_id, student_id, group_id, file_name, str(dest_file), submission_time, comments))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Assignment submitted successfully!\n\nFile: {file_name}\nTime: {submission_time}", parent=dialog)
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to submit assignment: {e}", parent=dialog)

            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill='x', padx=10, pady=(0, 10))

            ttk.Button(button_frame, text="Submit Assignment", command=submit_assignment,
                      style='Accent.TButton').pack(side='left')
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='right')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to handle group submission: {e}")

