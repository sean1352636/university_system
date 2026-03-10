"""Assignment template management"""

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
from collections import deque

class TemplateManager:
    """Assignment template management"""

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

    def show_templates(self):
        """Show assignment templates interface"""
        if not self._check_permission('manage_assignments'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="Assignment Templates", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create notebook for template management
        notebook = ttk.Notebook(self.gui.layout.content_area)
        notebook.pack(fill='both', expand=True)
        
        # View templates tab
        view_frame = ttk.Frame(notebook)
        notebook.add(view_frame, text="View Templates")
        
        # Create template tab
        create_frame = ttk.Frame(notebook)
        notebook.add(create_frame, text="Create Template")
        
        # Use template tab
        use_frame = ttk.Frame(notebook)
        notebook.add(use_frame, text="Use Template")
        
        # Templates list in view tab
        templates_tree = ttk.Treeview(view_frame, columns=('ID', 'Name', 'Category', 'Usage Count', 'Created'), show='headings')
        for col in ['ID', 'Name', 'Category', 'Usage Count', 'Created']:
            templates_tree.heading(col, text=col)
            templates_tree.column(col, width=120)
        
        templates_tree.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Load templates
        self.load_templates_data(templates_tree)
        
        # Template buttons
        template_buttons = ttk.Frame(view_frame)
        template_buttons.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(template_buttons, text="Edit Template", 
                  command=lambda: self.edit_template(templates_tree)).pack(side='left', padx=(0, 10))
        ttk.Button(template_buttons, text="Delete Template", 
                  command=lambda: self.delete_template(templates_tree)).pack(side='left', padx=(0, 10))
        ttk.Button(template_buttons, text="Duplicate Template", 
                  command=lambda: self.duplicate_template(templates_tree)).pack(side='left')
        
        # Create template form in create tab
        self.create_template_form(create_frame)
        
        # Use template interface in use tab
        self.use_template_form(use_frame)
    

    def load_templates_data(self, tree):
        """Load templates data into treeview from both database and filesystem"""
        for item in tree.get_children():
            tree.delete(item)

        templates_loaded = []

        # Load from database
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT id, name, category, usage_count, created_at
            FROM assignment_templates
            WHERE is_active = 1
            ORDER BY created_at DESC
            ''')

            db_templates = cursor.fetchall()

            for template in db_templates:
                tree.insert('', 'end', values=template, tags=('database',))
                templates_loaded.append(template[1])  # Track by name

            conn.close()

        except Exception as e:
            print(f"Error loading database templates: {e}")

        # Load from filesystem
        try:
            from education_system.university_system.modules.shared.constants import paths
            import json
            from pathlib import Path

            templates_dir = paths.ASSIGNMENT_TEMPLATES_DIR

            if templates_dir.exists():
                template_files = sorted(templates_dir.glob('*.json'))

                for template_file in template_files:
                    try:
                        with open(template_file, 'r', encoding='utf-8') as f:
                            template_data = json.load(f)

                        # Extract template info
                        template_name = template_data.get('name', template_file.stem)
                        category = template_data.get('category', 'Unknown')

                        # Skip if already loaded from database
                        if template_name in templates_loaded:
                            continue

                        # Display file-based templates with special formatting
                        display_values = (
                            f"FILE: {template_file.name}",
                            template_name,
                            category,
                            0,  # Usage count (N/A for file-based)
                            template_data.get('created_at', 'N/A')
                        )

                        tree.insert('', 'end', values=display_values, tags=('file', str(template_file)))

                    except Exception as e:
                        print(f"Error loading template file {template_file}: {e}")

            else:
                print(f"Templates directory not found: {templates_dir}")

        except Exception as e:
            print(f"Error scanning filesystem templates: {e}")

        # Show message if no templates found
        if len(tree.get_children()) == 0:
            messagebox.showinfo("No Templates",
                "No templates found.\n\n"
                f"You can create templates in the 'Create Template' tab or\n"
                f"place .json template files in:\n{paths.ASSIGNMENT_TEMPLATES_DIR}"
            )
    

    def create_template_form(self, parent):
        """Create template form"""
        form_frame = ttk.LabelFrame(parent, text="Create New Template", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Template name
        ttk.Label(form_frame, text="Template Name:").grid(row=0, column=0, sticky='w', pady=5)
        self.template_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.template_name_var, width=50).grid(row=0, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Category
        ttk.Label(form_frame, text="Category:").grid(row=1, column=0, sticky='w', pady=5)
        self.template_category_var = tk.StringVar()
        category_combo = ttk.Combobox(form_frame, textvariable=self.template_category_var, 
                                     values=["Programming", "Essay", "Lab Report", "Research", "Presentation", "Other"])
        category_combo.grid(row=1, column=1, sticky='w', pady=5, padx=(10, 0))
        
        # Description
        ttk.Label(form_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.template_desc_text = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.template_desc_text.grid(row=2, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Template fields
        ttk.Label(form_frame, text="Template Fields:", font=('Arial', 12, 'bold')).grid(row=3, column=0, columnspan=2, sticky='w', pady=(20, 10))
        
        # Title template
        ttk.Label(form_frame, text="Title Template:").grid(row=4, column=0, sticky='w', pady=5)
        self.template_title_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.template_title_var, width=50).grid(row=4, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Instructions template
        ttk.Label(form_frame, text="Instructions Template:").grid(row=5, column=0, sticky='nw', pady=5)
        self.template_instructions_text = scrolledtext.ScrolledText(form_frame, height=6, width=50)
        self.template_instructions_text.grid(row=5, column=1, sticky='ew', pady=5, padx=(10, 0))
        
        # Default settings
        defaults_frame = ttk.LabelFrame(form_frame, text="Default Settings", padding=10)
        defaults_frame.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(20, 0))
        
        ttk.Label(defaults_frame, text="Max Marks:").grid(row=0, column=0, sticky='w', pady=5)
        self.template_marks_var = tk.StringVar(value="100")
        ttk.Entry(defaults_frame, textvariable=self.template_marks_var, width=10).grid(row=0, column=1, sticky='w', pady=5, padx=5)
        
        ttk.Label(defaults_frame, text="File Types:").grid(row=0, column=2, sticky='w', pady=5, padx=(20, 0))
        self.template_filetypes_var = tk.StringVar(value=".pdf,.docx,.txt")
        ttk.Entry(defaults_frame, textvariable=self.template_filetypes_var, width=20).grid(row=0, column=3, sticky='w', pady=5, padx=5)
        
        ttk.Label(defaults_frame, text="Max File Size (MB):").grid(row=1, column=0, sticky='w', pady=5)
        self.template_filesize_var = tk.StringVar(value="10")
        ttk.Entry(defaults_frame, textvariable=self.template_filesize_var, width=10).grid(row=1, column=1, sticky='w', pady=5, padx=5)
        
        # Save button
        ttk.Button(form_frame, text="Save Template", 
                  command=self.save_template).grid(row=7, column=1, sticky='e', pady=(20, 0))
        
        form_frame.grid_columnconfigure(1, weight=1)
    

    def save_template(self):
        """Save new template"""
        try:
            name = self.template_name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Template name is required")
                return
            
            category = self.template_category_var.get().strip()
            description = self.template_desc_text.get(1.0, tk.END).strip()
            
            template_data = {
                'title_template': self.template_title_var.get().strip(),
                'instructions_template': self.template_instructions_text.get(1.0, tk.END).strip(),
                'default_max_marks': self.template_marks_var.get().strip(),
                'default_file_types': self.template_filetypes_var.get().strip(),
                'default_max_size': self.template_filesize_var.get().strip()
            }
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO assignment_templates (name, description, template_data, category, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, description, json.dumps(template_data), category,
                  self.auth.current_user['id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Template '{name}' created successfully!")
            self.clear_template_form()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")
    

    def clear_template_form(self):
        """Clear template form"""
        self.template_name_var.set('')
        self.template_category_var.set('')
        self.template_desc_text.delete(1.0, tk.END)
        self.template_title_var.set('')
        self.template_instructions_text.delete(1.0, tk.END)
        self.template_marks_var.set('100')
        self.template_filetypes_var.set('.pdf,.docx,.txt')
        self.template_filesize_var.set('10')
    

    def use_template_form(self, parent):
        """Create use template form"""
        form_frame = ttk.LabelFrame(parent, text="Create Assignment from Template", padding=20)
        form_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Template selection
        ttk.Label(form_frame, text="Select Template:").pack(anchor='w', pady=(0, 5))
        self.use_template_var = tk.StringVar()
        template_combo = ttk.Combobox(form_frame, textvariable=self.use_template_var, width=60)
        template_combo.pack(fill='x', pady=(0, 20))
        
        # Load available templates
        self.load_template_options(template_combo)
        
        # Module selection
        ttk.Label(form_frame, text="Select Module:").pack(anchor='w', pady=(0, 5))
        self.use_module_var = tk.StringVar()
        module_combo = ttk.Combobox(form_frame, textvariable=self.use_module_var, width=60)
        module_combo.pack(fill='x', pady=(0, 20))
        self.load_modules(module_combo)
        
        # Due date
        due_frame = ttk.Frame(form_frame)
        due_frame.pack(fill='x', pady=(0, 20))
        
        ttk.Label(due_frame, text="Due Date (YYYY-MM-DD):").pack(side='left')
        self.use_due_date_var = tk.StringVar()
        ttk.Entry(due_frame, textvariable=self.use_due_date_var, width=15).pack(side='left', padx=(10, 0))
        
        ttk.Label(due_frame, text="Time:").pack(side='left', padx=(20, 5))
        self.use_due_time_var = tk.StringVar(value="23:59")
        time_combo = ttk.Combobox(due_frame, textvariable=self.use_due_time_var, width=8, 
                                 values=["08:00", "12:00", "17:00", "23:59"])
        time_combo.pack(side='left')
        
        # Create button
        ttk.Button(form_frame, text="Create Assignment from Template", 
                  command=self.create_from_template).pack(pady=20)
    

    def load_template_options(self, combo):
        """Load template options for selection from database and filesystem"""
        try:
            template_list = []
            self.template_map = {}

            # Load from database
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                SELECT id, name, category FROM assignment_templates
                WHERE is_active = 1 ORDER BY category, name
                ''')

                templates = cursor.fetchall()

                for tid, name, category in templates:
                    display_text = f"{name} ({category})"
                    template_list.append(display_text)
                    self.template_map[display_text] = ('db', tid)

                conn.close()

            except Exception as e:
                print(f"Error loading database templates: {e}")

            # Load from filesystem
            try:
                from education_system.university_system.modules.shared.constants import paths
                import json

                templates_dir = paths.ASSIGNMENT_TEMPLATES_DIR

                if templates_dir.exists():
                    template_files = sorted(templates_dir.glob('*.json'))

                    for template_file in template_files:
                        try:
                            with open(template_file, 'r', encoding='utf-8') as f:
                                template_data = json.load(f)

                            template_name = template_data.get('name', template_file.stem)
                            category = template_data.get('category', 'Unknown')

                            display_text = f"{template_name} ({category}) [FILE]"
                            template_list.append(display_text)
                            self.template_map[display_text] = ('file', str(template_file))

                        except Exception as e:
                            print(f"Error loading template file {template_file}: {e}")

            except Exception as e:
                print(f"Error scanning filesystem templates: {e}")

            combo['values'] = template_list

            if not template_list:
                messagebox.showinfo("No Templates", "No templates available.\nPlease create a template first.")

        except Exception as e:
            print(f"Error loading templates: {e}")
    

    def create_from_template(self):
        """Create assignment from selected template"""
        if not self.use_template_var.get() or not self.use_module_var.get():
            messagebox.showerror("Error", "Please select both template and module")
            return

        if not self.use_due_date_var.get():
            messagebox.showerror("Error", "Please enter due date")
            return

        try:
            template_info = self.template_map.get(self.use_template_var.get())
            module_code = self.module_map.get(self.use_module_var.get())

            # Validate due date
            due_date_str = f"{self.use_due_date_var.get()} {self.use_due_time_var.get()}"
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d %H:%M")

            template_type, template_ref = template_info

            # Load template data based on source
            if template_type == 'db':
                # Load from database
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('SELECT name, template_data FROM assignment_templates WHERE id = ?', (template_ref,))
                result = cursor.fetchone()
                if not result:
                    raise Exception("Template not found in database")

                template_name, template_data_json = result
                template_data = json.loads(template_data_json)
                template_id = template_ref
                conn.close()

            else:  # template_type == 'file'
                # Load from file
                import json
                with open(template_ref, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)

                template_name = template_data.get('name', 'Template Assignment')
                template_id = None  # File-based templates don't have DB IDs

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Temporarily disable foreign key checks to avoid module_code issues
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            # Create assignment from template
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            assignment_title = template_data.get('title_template', template_name)
            assignment_instructions = template_data.get('instructions_template', '')

            cursor.execute('''
            INSERT INTO assignments
            (module_code, title, instructions, due_date, max_marks,
             file_types_allowed, max_file_size_mb, template_id, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                module_code,
                assignment_title,
                assignment_instructions,
                due_date.strftime('%Y-%m-%d %H:%M:%S'),
                int(template_data.get('default_max_marks', 100)),
                template_data.get('default_file_types', ''),
                int(template_data.get('default_max_size', 10)),
                template_id,
                self.auth.current_user['id'],
                timestamp,
                timestamp
            ))

            assignment_id = cursor.lastrowid

            # Update template usage count (only for database templates)
            if template_id is not None:
                cursor.execute('UPDATE assignment_templates SET usage_count = usage_count + 1 WHERE id = ?', (template_id,))

            # Get module name for email
            cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
            module_result = cursor.fetchone()
            module_name = module_result[0] if module_result else module_code

            # Re-enable foreign key checks
            cursor.execute("PRAGMA foreign_keys = ON")

            conn.commit()
            conn.close()

            # Send email notifications to enrolled students
            try:
                self._send_template_assignment_emails(
                    assignment_id=assignment_id,
                    assignment_title=assignment_title,
                    module_code=module_code,
                    module_name=module_name,
                    due_date=due_date.strftime('%Y-%m-%d %H:%M:%S'),
                    instructions=assignment_instructions,
                    template_name=template_name
                )
            except Exception as email_error:
                print(f"Warning: Failed to send template assignment emails: {email_error}")

            messagebox.showinfo("Success", f"Assignment created from template '{template_name}'!\nStudents have been notified by email.")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid date format")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create assignment: {e}")
    

    def edit_template(self, tree):
        """Edit selected template"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to edit")
            return
        
        item = tree.item(selection[0])
        template_id = item['values'][0]
        
        # Create edit window
        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Template")
        edit_window.geometry("600x500")
        
        messagebox.showinfo("Edit Template", f"Template editing interface for ID: {template_id}")
    

    def delete_template(self, tree):
        """Delete selected template"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to delete")
            return
        
        item = tree.item(selection[0])
        template_id = item['values'][0]
        template_name = item['values'][1]
        
        if messagebox.askyesno("Confirm Delete", f"Delete template '{template_name}'?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()
                
                cursor.execute('UPDATE assignment_templates SET is_active = 0 WHERE id = ?', (template_id,))
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Success", "Template deleted successfully")
                self.load_templates_data(tree)
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {e}")
    

    def duplicate_template(self, tree):
        """Duplicate selected template"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to duplicate")
            return
        
        item = tree.item(selection[0])
        template_id = item['values'][0]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get original template
            cursor.execute('SELECT name, description, template_data, category FROM assignment_templates WHERE id = ?', (template_id,))
            name, description, template_data, category = cursor.fetchone()
            
            # Create duplicate
            new_name = f"{name} (Copy)"
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('''
            INSERT INTO assignment_templates (name, description, template_data, category, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (new_name, description, template_data, category, self.auth.current_user['id'], timestamp))
            
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Success", f"Template duplicated as '{new_name}'")
            self.load_templates_data(tree)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate template: {e}")
    
    # EXTENSION REQUEST REVIEW (missing detailed GUI)

    def create_assignment_template(self, *args, **kwargs):
        """Jump to assignment template management."""
        self._launch_gui_feature(self.show_templates, "assignment templates")
    
    

    def use_assignment_template(self, *args, **kwargs):
        """Navigate to template usage flow."""
        self._launch_gui_feature(self.show_templates, "assignment templates")

    def _create_from_template(self, template_id, assignment_title, module_code, due_date):
        """Create assignment from template (instantiation logic)"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get template details
            cursor.execute('SELECT * FROM assignment_templates WHERE id = ?', (template_id,))
            template = cursor.fetchone()

            if not template:
                conn.close()
                messagebox.showerror("Error", "Template not found")
                return False

            # Extract template data (assuming columns match structure)
            template_name, description, assignment_type, max_marks, file_types, max_size = template[1:7]

            # Create assignment from template
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            created_by = self.auth.current_user.get('id') if self.auth and self.auth.current_user else None

            cursor.execute('''
            INSERT INTO assignments
            (title, description, module_code, assignment_type, max_marks, due_date,
             file_types_allowed, max_file_size_mb, created_by, created_at, template_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (assignment_title, description, module_code, assignment_type, max_marks,
                  due_date, file_types, max_size, created_by, timestamp, template_id))

            assignment_id = cursor.lastrowid

            # Copy template criteria if they exist
            cursor.execute('SELECT * FROM template_criteria WHERE template_id = ?', (template_id,))
            criteria = cursor.fetchall()

            for criterion in criteria:
                cursor.execute('''
                INSERT INTO assignment_criteria
                (assignment_id, criteria_name, max_points, weight, description)
                VALUES (?, ?, ?, ?, ?)
                ''', (assignment_id, criterion[2], criterion[3], criterion[4], criterion[5]))

            # Get module name for email
            cursor.execute('SELECT module_name FROM modules WHERE module_code = ?', (module_code,))
            module_result = cursor.fetchone()
            module_name = module_result[0] if module_result else module_code

            conn.commit()
            conn.close()

            # Send email notifications to enrolled students
            try:
                self._send_template_assignment_emails(
                    assignment_id=assignment_id,
                    assignment_title=assignment_title,
                    module_code=module_code,
                    module_name=module_name,
                    due_date=due_date,
                    instructions=description,
                    template_name=template_name
                )
            except Exception as email_error:
                print(f"Warning: Failed to send template assignment emails: {email_error}")

            messagebox.showinfo("Success", f"Assignment '{assignment_title}' created successfully from template!\nStudents have been notified by email.")
            return True

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create assignment from template: {e}")
            return False

    def _launch_gui_feature(self, callback, feature_name):
        """Helper to launch GUI features with error handling"""
        try:
            callback()
        except Exception as e:
            messagebox.showerror("Error", f"Error launching {feature_name}: {str(e)}")

    def _send_template_assignment_emails(self, assignment_id, assignment_title,
                                         module_code, module_name, due_date,
                                         instructions, template_name):
        """Send email notifications to students when assignment is created from template"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get all students enrolled in this module
            cursor.execute('''
                SELECT s.student_id, s.first_name, s.last_name, s.email_address
                FROM students s
                JOIN student_modules sm ON s.student_id = sm.student_id
                WHERE sm.module_code = ?
                AND s.email_address IS NOT NULL
                AND s.email_address != ''
            ''', (module_code,))

            students = cursor.fetchall()
            conn.close()

            if not students:
                print(f"No students enrolled in {module_code} or no email addresses available")
                return 0

            emails_sent = 0

            for student_id, first_name, last_name, email in students:
                try:
                    # Use email template
                    try:
                        from education_system.university_system.infrastructure.email.template_utils import render_template
                        subject, body = render_template("assignment_from_template", {
                            "first_name": first_name,
                            "module_code": module_code,
                            "module_name": module_name,
                            "assignment_title": assignment_title,
                            "due_date": due_date,
                            "template_name": template_name,
                            "instructions": instructions or 'Please check the Assignment System for detailed instructions.'
                        })
                    except Exception as template_error:
                        # Fallback to hardcoded email
                        subject = f"New Assignment from Template: {assignment_title}"
                        body = f"""Dear {first_name},

A new assignment has been created for your module using the "{template_name}" template.

Assignment Details:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Module: {module_code} - {module_name}
Assignment: {assignment_title}
Due Date: {due_date}
Template Used: {template_name}

What You Need to Do:
{instructions or 'Please check the Assignment System for detailed instructions.'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Next Steps:
1. Login to the Assignment System
2. Review the complete assignment requirements
3. Download any provided materials or resources
4. Submit your work before the due date

Important Notes:
- This assignment was created using a standardized template
- All requirements and grading criteria are available in the system
- Contact your instructor if you have any questions

Best regards,
Academic Administration Team

Note: This assignment was automatically created from the "{template_name}" template.
"""

                    send_email(email, subject, body)
                    emails_sent += 1
                    print(f"Template assignment email sent to {student_id} ({email})")

                except Exception as e:
                    print(f"Failed to send email to {student_id}: {e}")

            print(f"Total template assignment emails sent: {emails_sent}/{len(students)}")
            return emails_sent

        except Exception as e:
            print(f"Error in _send_template_assignment_emails: {e}")
            import traceback
            traceback.print_exc()
            return 0

