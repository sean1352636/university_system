"""Assignment submission handling"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
import json
import csv
import logging
from PIL import Image, ImageTk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import seaborn as sns
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.infrastructure.security.file_upload import (
    get_upload_handler,
    validate_upload,
    secure_filename,
)
from collections import deque

logger = logging.getLogger(__name__)

class SubmissionManager:
    """Assignment submission handling"""

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

    def _calculate_file_hash(self, file_path):
        """Calculate file hash for integrity checking"""
        try:
            import hashlib

            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)

            return hash_md5.hexdigest()
        except Exception as e:
            print(f"Error calculating file hash: {e}")
            return None

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

    def show_submit_assignment(self):
        """Show assignment submission form"""
        self.gui.layout.clear_content_area()

        title = ttk.Label(self.gui.layout.content_area, text="Submit Assignment", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))

        # Create submission form
        form_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Assignment Submission", padding=20)
        form_frame.pack(fill='x', pady=(0, 20))

        current_row = 0

        # Admin: show student selector for testing
        current_user_role = self.auth.current_user.get('role', '') if self.auth.current_user else ''
        self._admin_student_var = None
        self._admin_student_map = {}
        if current_user_role == 'admin':
            ttk.Label(form_frame, text="[ADMIN] Submit as Student:").grid(row=current_row, column=0, sticky='w', pady=5)
            self._admin_student_var = tk.StringVar()
            student_combo = ttk.Combobox(form_frame, textvariable=self._admin_student_var, width=50, state='readonly')
            student_combo.grid(row=current_row, column=1, sticky='ew', pady=5, padx=(10, 0))
            self._load_students_for_admin(student_combo)
            current_row += 1

        # Assignment selection
        ttk.Label(form_frame, text="Select Assignment:").grid(row=current_row, column=0, sticky='w', pady=5)
        self.assignment_var = tk.StringVar()
        assignment_combo = ttk.Combobox(form_frame, textvariable=self.assignment_var, width=50)
        assignment_combo.grid(row=current_row, column=1, sticky='ew', pady=5, padx=(10, 0))
        current_row += 1

        # Load available assignments
        self.load_available_assignments(assignment_combo)

        # File selection
        ttk.Label(form_frame, text="Select File:").grid(row=current_row, column=0, sticky='w', pady=5)
        self.file_var = tk.StringVar()
        file_frame = ttk.Frame(form_frame)
        file_frame.grid(row=current_row, column=1, sticky='ew', pady=5, padx=(10, 0))
        current_row += 1

        file_entry = ttk.Entry(file_frame, textvariable=self.file_var, width=40)
        file_entry.pack(side='left', fill='x', expand=True)

        ttk.Button(file_frame, text="Browse",
                  command=self.browse_file).pack(side='right', padx=(10, 0))

        # Comments
        ttk.Label(form_frame, text="Comments (optional):").grid(row=current_row, column=0, sticky='nw', pady=5)
        self.comments_text = scrolledtext.ScrolledText(form_frame, height=4, width=50)
        self.comments_text.grid(row=current_row, column=1, sticky='ew', pady=5, padx=(10, 0))
        current_row += 1

        # Configure grid weights
        form_frame.grid_columnconfigure(1, weight=1)

        # Submit button
        submit_btn = ttk.Button(form_frame, text="Submit Assignment",
                               command=self.submit_assignment_gui)
        submit_btn.grid(row=current_row, column=1, sticky='e', pady=(20, 0))

        # Status frame for feedback
        self.status_frame = ttk.Frame(self.gui.layout.content_area)
        self.status_frame.pack(fill='x', pady=(10, 0))

    def _load_students_for_admin(self, combo):
        """Load student list for admin testing dropdown"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id, first_name, last_name, course
                FROM students ORDER BY last_name, first_name
            ''')
            students = cursor.fetchall()
            conn.close()

            self._admin_student_map = {}
            display_list = []
            for sid, fname, lname, course in students:
                label = f"{sid} - {fname} {lname} ({course})"
                display_list.append(label)
                self._admin_student_map[label] = sid

            combo['values'] = display_list
            if display_list:
                combo.current(0)
        except Exception as e:
            logger.error(f"Failed to load students for admin: {e}")
    

    def load_available_assignments(self, combo):
        """Load available assignments for submission"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            # Check if user is admin
            current_user_role = self.auth.current_user.get('role', '') if self.auth.current_user else ''
    
            if current_user_role == 'admin':
                # Admin can see all assignments
                cursor.execute('''
                SELECT a.id, a.title, a.module_code, a.due_date, a.created_by
                FROM assignments a
                WHERE a.is_active = 1
                ORDER BY a.due_date
                ''')
    
                assignments = cursor.fetchall()
    
                # Format for display - include creator info for admin
                assignment_list = []
                self.assignment_map = {}
    
                for aid, title, module, due_date, created_by in assignments:
                    # Get creator username
                    cursor.execute('SELECT username FROM users WHERE id = ?', (created_by,))
                    creator_result = cursor.fetchone()
                    creator = creator_result[0] if creator_result else 'Unknown'
    
                    display_text = f"[ADMIN] {title} ({module}) - Due: {due_date} - Created by: {creator}"
                    assignment_list.append(display_text)
                    self.assignment_map[display_text] = aid
    
            else:
                # Regular student logic
                student_id = self.assignment_system._get_student_id()
                if not student_id:
                    combo['values'] = []
                    conn.close()
                    return
    
                cursor.execute('''
                SELECT a.id, a.title, a.module_code, a.due_date
                FROM assignments a
                JOIN student_modules sm ON a.module_code = sm.module_code
                LEFT JOIN assignment_submissions s ON a.id = s.assignment_id AND s.student_id = ?
                WHERE sm.student_id = ? AND a.is_active = 1
                ORDER BY a.due_date
                ''', (student_id, student_id))
    
                assignments = cursor.fetchall()
    
                # Format for display
                assignment_list = []
                self.assignment_map = {}
    
                for aid, title, module, due_date in assignments:
                    display_text = f"{title} ({module}) - Due: {due_date}"
                    assignment_list.append(display_text)
                    self.assignment_map[display_text] = aid
    
            combo['values'] = assignment_list
            conn.close()
    
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load assignments: {e}")
    

    def browse_file(self):
        """Open file browser for assignment submission"""
        filename = filedialog.askopenfilename(
            title="Select Assignment File",
            filetypes=[
                ("All Files", "*.*"),
                ("PDF Files", "*.pdf"),
                ("Word Documents", "*.docx *.doc"),
                ("Text Files", "*.txt"),
                ("Images", "*.jpg *.jpeg *.png *.gif"),
                ("Archives", "*.zip *.rar")
            ]
        )
        if filename:
            self.file_var.set(filename)
    

    def submit_assignment_gui(self):
        """Submit assignment through GUI"""
        # Clear previous status messages
        for widget in self.status_frame.winfo_children():
            widget.destroy()

        # For admin users, validate that a student is selected
        current_user_role = self.auth.current_user.get('role', '') if self.auth.current_user else ''
        if current_user_role == 'admin':
            if not self._admin_student_var or not self._admin_student_var.get():
                self.show_status_message("Please select a student to submit on behalf of", "error")
                return

        # Validate inputs
        if not self.assignment_var.get():
            self.show_status_message("Please select an assignment", "error")
            return

        if not self.file_var.get():
            self.show_status_message("Please select a file", "error")
            return

        if not os.path.exists(self.file_var.get()):
            self.show_status_message("Selected file does not exist", "error")
            return

        # Get assignment ID
        assignment_id = self.assignment_map.get(self.assignment_var.get())
        if not assignment_id:
            self.show_status_message("Invalid assignment selection", "error")
            return

        # Show progress
        self.show_status_message("Submitting assignment...", "info")
        self.root.update()

        # Submit in background thread to prevent GUI freezing
        threading.Thread(target=self.perform_submission,
                        args=(assignment_id, self.file_var.get(), self.comments_text.get(1.0, tk.END).strip()),
                        daemon=True).start()
    

    def _validate_file_submission(self, file_path, allowed_types, max_size_mb):
        """Validate file for assignment submission with comprehensive error handling"""
        try:
            # Check if file path is provided
            if not file_path:
                return False, "No file path provided"
    
            # Check if file exists
            if not os.path.exists(file_path):
                return False, f"File does not exist: {file_path}"
    
            # Check if it's a file (not a directory)
            if not os.path.isfile(file_path):
                return False, f"Path is not a file: {file_path}"
    
            # Check if file is readable
            try:
                with open(file_path, 'rb') as f:
                    f.read(1)
            except PermissionError:
                return False, f"File is not readable (permission denied): {file_path}"
            except Exception as e:
                return False, f"Cannot read file: {str(e)}"
    
            # Get file size in MB
            try:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            except OSError as e:
                return False, f"Cannot determine file size: {str(e)}"
    
            # Check file size
            if max_size_mb:
                try:
                    max_size_mb_float = float(max_size_mb)
                    if file_size_mb > max_size_mb_float:
                        return False, f"File size ({file_size_mb:.1f}MB) exceeds maximum allowed size ({max_size_mb_float}MB)"
                except (ValueError, TypeError):
                    # Log warning but don't fail validation
                    print(f"Warning: Invalid maximum file size value: {max_size_mb}")
    
            # Check file extension
            if allowed_types:
                file_ext = os.path.splitext(file_path)[1].lower()
    
                # Handle both comma-separated and space-separated formats
                if isinstance(allowed_types, str):
                    allowed_exts = [ext.strip().lower() for ext in allowed_types.replace(',', ' ').split() if ext.strip()]
                    # Ensure extensions start with a dot
                    allowed_exts = [ext if ext.startswith('.') else f'.{ext}' for ext in allowed_exts]
                else:
                    allowed_exts = []
    
                if allowed_exts and file_ext not in allowed_exts:
                    return False, f"File type '{file_ext}' not allowed. Allowed types: {', '.join(allowed_exts)}"
    
            return True, "File validation successful"
    
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    

    def _get_student_id_safe(self):
        """Safely get student ID with fallback"""
        try:
            # Try to get from assignment system
            if hasattr(self.assignment_system, '_get_student_id'):
                return self.assignment_system._get_student_id()

            # Fallback to auth system - MUST get student_id, not user id
            if self.auth and self.auth.current_user:
                # First try to get student_id directly
                student_id = self.auth.current_user.get('student_id')

                # If no student_id in current_user, look it up in database
                if not student_id:
                    user_id = self.auth.current_user.get('id')
                    if user_id:
                        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                        cursor = conn.cursor()
                        cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
                        result = cursor.fetchone()
                        conn.close()

                        if result and result[0]:
                            student_id = result[0]

                return student_id

            return None
        except Exception as e:
            print(f"Error getting student ID: {e}")
            return None
    

    def perform_submission(self, assignment_id, file_path, comments):
        """Perform the actual submission (runs in background thread)"""
        try:
            # Validate file path first
            if not file_path or not isinstance(file_path, str) or not file_path.strip():
                self.root.after(0, lambda: self.show_status_message("Please select a file to submit", "error"))
                return

            # Use admin-selected student or look up from auth
            current_user_role = self.auth.current_user.get('role', '') if self.auth.current_user else ''
            if current_user_role == 'admin' and self._admin_student_var:
                student_id = self._admin_student_map.get(self._admin_student_var.get())
            else:
                student_id = self._get_student_id_safe()
            if not student_id:
                self.root.after(0, lambda: self.show_status_message("No student ID found", "error"))
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Validate that student_id exists in students table (foreign key requirement)
            cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
            if not cursor.fetchone():
                self.root.after(0, lambda: self.show_status_message(
                    f"Student ID '{student_id}' not found in students table. Please ensure you are registered as a student.",
                    "error"
                ))
                conn.close()
                return
            
            # Get assignment details
            cursor.execute('''
            SELECT a.*, m.module_name
            FROM assignments a
            JOIN modules m ON a.module_code = m.module_code
            WHERE a.id = ? AND a.is_active = 1
            ''', (assignment_id,))

            assignment = cursor.fetchone()
            if not assignment:
                # Check if assignment exists but is inactive
                cursor.execute('SELECT id FROM assignments WHERE id = ?', (assignment_id,))
                if cursor.fetchone():
                    self.root.after(0, lambda: self.show_status_message("Assignment is no longer active", "error"))
                else:
                    self.root.after(0, lambda: self.show_status_message("Assignment not found", "error"))
                conn.close()
                return
            
            # Validate file
            # Column indexes: 7=file_types_allowed, 8=max_file_size_mb
            valid, message = self._validate_file_submission(
                file_path, assignment[7], assignment[8]
            )

            if not valid:
                self.root.after(0, lambda: self.show_status_message(f"File validation failed: {message}", "error"))
                conn.close()
                return

            # Check for existing submissions
            cursor.execute('''
            SELECT version_number FROM assignment_submissions
            WHERE assignment_id = ? AND student_id = ?
            ORDER BY submission_date DESC LIMIT 1
            ''', (assignment_id, student_id))

            existing = cursor.fetchone()
            version_number = (existing[0] + 1) if existing else 1

            # Check due date
            # Column index: 5=due_date
            due_date = datetime.strptime(assignment[5], '%Y-%m-%d %H:%M:%S')
            submission_time = datetime.now()
            late_submission = submission_time > due_date
            late_days = (submission_time - due_date).days if late_submission else 0

            # Column index: 12=allow_late_submission
            if late_submission and not assignment[12]:  # allow_late_submission
                self.root.after(0, lambda: self.show_status_message("Late submissions are not allowed", "error"))
                conn.close()
                return
            
            # Create submission directory
            import shutil
            from education_system.university_system.modules.shared.constants import paths

            # Use proper path from shared constants with fallback
            assignment_submission_dir = getattr(self.assignment_system, 'submission_dir', None)
            if assignment_submission_dir is None:
                base_dir = paths.SUBMISSIONS_DIR
            else:
                base_dir = Path(assignment_submission_dir)

            submission_dir = os.path.join(
                str(base_dir),
                'submitted', student_id, f"assignment_{assignment_id}"
            )
            os.makedirs(submission_dir, exist_ok=True)

            # Read file content for secure validation
            file_name = os.path.basename(file_path)
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # Validate file using secure upload handler
            validation = validate_upload(file_name, file_content, category='documents')
            if not validation['valid']:
                self.root.after(0, lambda: self.show_status_message(
                    f"File validation failed: {validation['error']}", "error"
                ))
                return

            # Use sanitized filename
            safe_filename = validation['safe_filename']
            timestamp = submission_time.strftime('%Y%m%d_%H%M%S')
            new_file_name = f"v{version_number}_{timestamp}_{safe_filename}"
            new_file_path = os.path.join(submission_dir, new_file_name)

            # Save file with secure copy
            shutil.copy2(file_path, new_file_path)

            # Set restrictive permissions on uploaded file
            try:
                os.chmod(new_file_path, 0o600)
            except OSError:
                pass  # May fail on some systems

            # Use hash and size from validation
            file_hash = self._calculate_file_hash(new_file_path)
            file_size = len(file_content)

            logger.info(f"Assignment submission saved securely: {new_file_name} ({file_size} bytes)")
            
            # Save submission
            submission_date = submission_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Mark previous submissions as not final
            if existing:
                cursor.execute('''
                UPDATE assignment_submissions 
                SET is_final_submission = 0 
                WHERE assignment_id = ? AND student_id = ?
                ''', (assignment_id, student_id))
            
            try:
                cursor.execute('''
                INSERT INTO assignment_submissions
                (assignment_id, student_id, submission_date, file_path,
                 file_name, file_size, file_hash, status, late_submission, late_days,
                 version_number, is_final_submission)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (assignment_id, student_id, submission_date, new_file_path,
                      file_name, file_size, file_hash, 'submitted', late_submission, late_days,
                      version_number, 1))

                conn.commit()
            except sqlite3.IntegrityError as ie:
                conn.close()
                error_msg = str(ie)
                if 'FOREIGN KEY constraint failed' in error_msg:
                    self.root.after(0, lambda: self.show_status_message(
                        f"Database constraint error: Student ID '{student_id}' or Assignment ID '{assignment_id}' is invalid. "
                        "Please ensure you are registered as a student and the assignment exists.",
                        "error"
                    ))
                else:
                    self.root.after(0, lambda: self.show_status_message(
                        f"Database error: {error_msg}",
                        "error"
                    ))
                return

            conn.close()

            # Send email notifications
            try:
                self._send_submission_emails(
                    student_id=student_id,
                    assignment_id=assignment_id,
                    assignment_title=assignment[2],  # title column
                    module_code=assignment[1],  # module_code column
                    module_name=assignment[-1],  # module_name from JOIN
                    version_number=version_number,
                    late_submission=late_submission,
                    late_days=late_days
                )
            except Exception as email_error:
                print(f"Warning: Failed to send submission emails: {email_error}")

            # Update GUI on main thread
            success_msg = f"Assignment submitted successfully! Version: {version_number}"
            if late_submission:
                success_msg += f" (Late submission: {late_days} days)"

            self.root.after(0, lambda: self.show_status_message(success_msg, "success"))
            self.root.after(0, self.clear_submission_form)
            
        except Exception as e:
            error_msg = f"Submission failed: {str(e)}"
            self.root.after(0, lambda: self.show_status_message(error_msg, "error"))
    

    def show_status_message(self, message, msg_type):
        """Show status message in the status frame"""
        for widget in self.status_frame.winfo_children():
            widget.destroy()
        
        if msg_type == "success":
            style = 'Success.TLabel'
        elif msg_type == "error":
            style = 'Error.TLabel'
        else:
            style = 'Warning.TLabel'
        
        status_label = ttk.Label(self.status_frame, text=message, style=style)
        status_label.pack(anchor='w')
    

    def clear_submission_form(self):
        """Clear the submission form after successful submission"""
        self.assignment_var.set('')
        self.file_var.set('')
        self.comments_text.delete(1.0, tk.END)
    

    def show_my_submissions(self):
        """Show student's submissions"""
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="My Submissions", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Create submissions table
        submissions_frame = ttk.Frame(self.gui.layout.content_area)
        submissions_frame.pack(fill='both', expand=True)
        
        # Treeview for submissions
        columns = ('ID', 'Assignment', 'File', 'Submitted', 'Status', 'Grade', 'Feedback')
        tree = ttk.Treeview(submissions_frame, columns=columns, show='headings')
        
        for col in columns:
            tree.heading(col, text=col)
            if col == 'Feedback':
                tree.column(col, width=200)
            else:
                tree.column(col, width=120)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(submissions_frame, orient='vertical', command=tree.yview)
        h_scrollbar = ttk.Scrollbar(submissions_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout
        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        submissions_frame.grid_rowconfigure(0, weight=1)
        submissions_frame.grid_columnconfigure(0, weight=1)
        
        # Load submissions data
        self.load_submissions_data(tree)
        
        # Buttons frame
        buttons_frame = ttk.Frame(self.gui.layout.content_area)
        buttons_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(buttons_frame, text="View File", 
                  command=lambda: self.view_submission_file(tree)).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Download File", 
                  command=lambda: self.download_submission_file(tree)).pack(side='left', padx=(0, 10))
        ttk.Button(buttons_frame, text="Refresh", 
                  command=lambda: self.load_submissions_data(tree)).pack(side='left')
    

    def load_submissions_data(self, tree):
        """Load submissions data into the treeview"""
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
            SELECT s.id, a.title, s.file_name, s.submission_date, s.status,
                   COALESCE(CAST(s.grade AS TEXT), 'Not Graded') as grade,
                   COALESCE(s.feedback, 'No feedback') as feedback
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.student_id = ?
            ORDER BY s.submission_date DESC
            ''', (student_id,))
            
            submissions = cursor.fetchall()
            
            for submission in submissions:
                tree.insert('', 'end', values=submission)
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")
    

    def view_submissions(self):
        """Enhanced view submissions with better filtering and actions"""
        if not self._check_permission('view_own_submissions'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="My Submissions", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Enhanced filter frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Filters & Search", padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))
        
        # Assignment filter
        ttk.Label(filter_frame, text="Assignment:").grid(row=0, column=0, sticky='w', padx=5)
        self.submission_assignment_filter = tk.StringVar()
        assignment_combo = ttk.Combobox(filter_frame, textvariable=self.submission_assignment_filter, width=25)
        assignment_combo.grid(row=0, column=1, padx=5)
        
        # Grade status filter
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, sticky='w', padx=5)
        self.submission_status_filter = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.submission_status_filter,
                                   values=["All", "Graded", "Ungraded", "Late"], width=12)
        status_combo.grid(row=0, column=3, padx=5)
        
        # Date range filter
        ttk.Label(filter_frame, text="From:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.submission_date_from = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.submission_date_from, width=12).grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(filter_frame, text="To:").grid(row=1, column=2, sticky='w', padx=5, pady=5)
        self.submission_date_to = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.submission_date_to, width=12).grid(row=1, column=3, padx=5, pady=5)
        
        ttk.Button(filter_frame, text="Apply Filters", 
                  command=self.apply_my_submission_filters).grid(row=1, column=4, padx=10, pady=5)
        ttk.Button(filter_frame, text="Clear Filters", 
                  command=self.clear_submission_filters).grid(row=1, column=5, padx=5, pady=5)
        
        # Enhanced submissions table
        submissions_frame = ttk.Frame(self.gui.layout.content_area)
        submissions_frame.pack(fill='both', expand=True)
        
        columns = ('ID', 'Assignment', 'Module', 'File', 'Submitted', 'Status', 'Grade', 'Feedback Available')
        self.enhanced_submissions_tree = ttk.Treeview(submissions_frame, columns=columns, show='headings')
        
        for col in columns:
            self.enhanced_submissions_tree.heading(col, text=col)
            if col == 'Feedback Available':
                self.enhanced_submissions_tree.column(col, width=120)
            else:
                self.enhanced_submissions_tree.column(col, width=100)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(submissions_frame, orient='vertical', command=self.enhanced_submissions_tree.yview)
        h_scroll = ttk.Scrollbar(submissions_frame, orient='horizontal', command=self.enhanced_submissions_tree.xview)
        self.enhanced_submissions_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.enhanced_submissions_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        submissions_frame.grid_rowconfigure(0, weight=1)
        submissions_frame.grid_columnconfigure(0, weight=1)
        
        # Load assignments for filter
        self.load_my_assignments_filter(assignment_combo)
        
        # Enhanced action buttons
        actions_frame = ttk.Frame(self.gui.layout.content_area)
        actions_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(actions_frame, text="View Feedback", 
                  command=self.view_detailed_feedback).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text="Download File", 
                  command=self.download_my_submission).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text="Resubmit (if allowed)", 
                  command=self.resubmit_assignment).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text="Export My Grades", 
                  command=self.export_my_grades).pack(side='left', padx=(0, 10))
        ttk.Button(actions_frame, text="Grade Statistics", 
                  command=self.show_my_grade_stats).pack(side='left')
        
        # Load submissions
        self.load_enhanced_submissions()
    

    def apply_my_submission_filters(self):
        """Apply filters for the student's submissions view."""
        self.load_enhanced_submissions()
    

    def clear_submission_filters(self):
        """Clear all submission filters"""
        self.submission_assignment_filter.set("All Assignments")
        self.submission_status_filter.set("All")
        self.submission_date_from.set("")
        self.submission_date_to.set("")
        self.load_enhanced_submissions()
    

    def load_enhanced_submissions(self):
        """Load submissions with enhanced filtering"""
        # Clear existing data
        for item in self.enhanced_submissions_tree.get_children():
            self.enhanced_submissions_tree.delete(item)
        
        try:
            student_id = self.assignment_system._get_student_id()
            if not student_id:
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Build query with filters
            query = '''
            SELECT s.id, a.title, a.module_code, s.file_name, s.submission_date,
                   s.status, 
                   CASE WHEN s.grade IS NULL THEN 'Not Graded' ELSE CAST(s.grade AS TEXT) || '%' END as grade,
                   CASE WHEN s.feedback IS NOT NULL AND s.feedback != '' THEN 'Yes' ELSE 'No' END as has_feedback
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.student_id = ?
            '''
            
            params = [student_id]
            
            # Apply assignment filter
            assignment_filter = self.submission_assignment_filter.get()
            assignment_id = self.submission_assignment_map.get(assignment_filter)
            if assignment_id:
                query += " AND s.assignment_id = ?"
                params.append(assignment_id)
            
            # Apply status filter
            status_filter = self.submission_status_filter.get()
            if status_filter == "Graded":
                query += " AND s.grade IS NOT NULL"
            elif status_filter == "Ungraded":
                query += " AND s.grade IS NULL"
            elif status_filter == "Late":
                query += " AND s.late_submission = 1"
            
            # Apply date filters
            date_from = self.submission_date_from.get().strip()
            if date_from:
                query += " AND date(s.submission_date) >= ?"
                params.append(date_from)
            
            date_to = self.submission_date_to.get().strip()
            if date_to:
                query += " AND date(s.submission_date) <= ?"
                params.append(date_to)
            
            query += " ORDER BY s.submission_date DESC"
            
            cursor.execute(query, params)
            submissions = cursor.fetchall()
            
            for submission in submissions:
                sid, title, module, filename, date, status, grade, feedback = submission
                
                # Color coding
                tags = []
                if grade != 'Not Graded':
                    if float(grade.replace('%', '')) >= 70:
                        tags = ['good_grade']
                    elif float(grade.replace('%', '')) >= 50:
                        tags = ['average_grade']
                    else:
                        tags = ['poor_grade']
                elif status == 'late':
                    tags = ['late']
                
                self.enhanced_submissions_tree.insert('', 'end', 
                                                    values=(sid, title, module, filename, date, status, grade, feedback),
                                                    tags=tags)
            
            # Configure tags
            self.enhanced_submissions_tree.tag_configure('good_grade', background='#e8f5e8')
            self.enhanced_submissions_tree.tag_configure('average_grade', background='#fff3e0')
            self.enhanced_submissions_tree.tag_configure('poor_grade', background='#ffebee')
            self.enhanced_submissions_tree.tag_configure('late', background='#ffcdd2')
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")
    

    def view_detailed_feedback(self):
        """View detailed feedback for selected submission"""
        selection = self.enhanced_submissions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission")
            return
        
        item = self.enhanced_submissions_tree.item(selection[0])
        submission_id = item['values'][0]
        
        # Create feedback window
        feedback_window = tk.Toplevel(self.root)
        feedback_window.title("Detailed Feedback")
        feedback_window.geometry("600x500")
        feedback_window.transient(self.root)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get submission details with feedback
            cursor.execute('''
            SELECT s.*, a.title, a.max_marks, st.first_name, st.last_name
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            WHERE s.id = ?
            ''', (submission_id,))
            
            submission = cursor.fetchone()
            
            if not submission:
                messagebox.showerror("Error", "Submission not found")
                feedback_window.destroy()
                return
            
            # Display feedback
            main_frame = ttk.Frame(feedback_window)
            main_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Header info
            header_label = ttk.Label(main_frame, text=f"Assignment: {submission[11]}")
            header_label.pack(pady=5)

            conn.close()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load feedback: {e}")

    def download_my_submission(self):
        """Download selected submission file"""
        selection = self.enhanced_submissions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission")
            return
        
        item = self.enhanced_submissions_tree.item(selection[0])
        submission_id = item['values'][0]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('SELECT file_path, file_name FROM assignment_submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()
            
            if result and os.path.exists(result[0]):
                save_path = filedialog.asksaveasfilename(
                    defaultextension=os.path.splitext(result[1])[1],
                    initialfile=result[1],
                    filetypes=[("All files", "*.*")]
                )
                
                if save_path:
                    shutil.copy2(result[0], save_path)
                    messagebox.showinfo("Success", f"File saved to: {save_path}")
            else:
                messagebox.showerror("Error", "File not found")
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download file: {e}")
    

    def resubmit_assignment(self):
        """Allow resubmission if permitted"""
        selection = self.enhanced_submissions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission")
            return
        
        item = self.enhanced_submissions_tree.item(selection[0])
        submission_id = item['values'][0]
        assignment_title = item['values'][1]
        
        # Check if resubmission is allowed
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.due_date, a.allow_late_submission, s.assignment_id
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.id = ?
            ''', (submission_id,))
            
            result = cursor.fetchone()
            if not result:
                messagebox.showerror("Error", "Assignment not found")
                return
            
            due_date, allow_late, assignment_id = result
            due_datetime = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
            
            if datetime.now() > due_datetime and not allow_late:
                messagebox.showerror("Error", "Resubmission not allowed after due date")
                return
            
            conn.close()
            
            # Confirm resubmission
            if messagebox.askyesno("Confirm Resubmission", 
                                  f"Are you sure you want to resubmit '{assignment_title}'?\n"
                                  f"This will create a new version."):
                # Switch to submission interface for this assignment
                self.show_submit_assignment()
                # Pre-select the assignment (if possible with current interface)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check resubmission: {e}")
    

    def export_my_grades(self):
        """Export student's grades to file"""
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                initialfile="my_grades.csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not save_path:
                return
            
            student_id = self.assignment_system._get_student_id()
            if not student_id:
                messagebox.showerror("Error", "Student ID not found")
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT a.title, a.module_code, s.submission_date, s.grade, s.late_submission,
                   a.max_marks, s.feedback
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            WHERE s.student_id = ? AND s.grade IS NOT NULL
            ORDER BY s.submission_date
            ''', (student_id,))
            
            data = cursor.fetchall()
            
            import csv
            with open(save_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Assignment', 'Module', 'Submission Date', 'Grade (%)', 'Late', 'Max Marks', 'Feedback'])
                
                for row in data:
                    # Convert grade percentage to actual grade
                    title, module, date, grade_pct, late, max_marks, feedback = row
                    actual_grade = (grade_pct * max_marks) / 100 if grade_pct else 0
                    late_text = 'Yes' if late else 'No'
                    
                    writer.writerow([title, module, date, f"{grade_pct:.1f}", late_text, max_marks, feedback or ''])
            
            conn.close()
            messagebox.showinfo("Success", f"Grades exported to: {save_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export grades: {e}")
    

    def show_my_grade_stats(self):
        """Show grade statistics for student"""
        student_id = self.assignment_system._get_student_id()
        if not student_id:
            messagebox.showerror("Error", "Student ID not found")
            return
        
        # Create statistics window
        stats_window = tk.Toplevel(self.root)
        stats_window.title("My Grade Statistics")
        stats_window.geometry("500x400")
        stats_window.transient(self.root)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            # Get grade statistics
            cursor.execute('''
            SELECT COUNT(*) as total_graded,
                   AVG(grade) as avg_grade,
                   MIN(grade) as min_grade,
                   MAX(grade) as max_grade,
                   COUNT(CASE WHEN late_submission = 1 THEN 1 END) as late_count
            FROM assignment_submissions
            WHERE student_id = ? AND grade IS NOT NULL
            ''', (student_id,))
            
            stats = cursor.fetchone()
            
            if not stats or not stats[0]:
                ttk.Label(stats_window, text="No graded submissions found").pack(pady=20)
                return
            
            total, avg, min_grade, max_grade, late_count = stats
            
            # Display statistics
            stats_frame = ttk.LabelFrame(stats_window, text="Grade Summary", padding=20)
            stats_frame.pack(fill='x', padx=10, pady=10)

            stats_label = ttk.Label(stats_frame, text=f"Total Graded Assignments: {total}")
            stats_label.pack(pady=5)

        except Exception as e:
            messagebox.showerror("Error", f"Operation failed: {e}")

    def view_all_submissions(self):
        """View all submissions (instructor/admin)"""
        if not self._check_permission('view_all_submissions'):
            return
        
        self.gui.layout.clear_content_area()
        
        title = ttk.Label(self.gui.layout.content_area, text="All Submissions", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 20))
        
        # Filter frame
        filter_frame = ttk.LabelFrame(self.gui.layout.content_area, text="Filters", padding=10)
        filter_frame.pack(fill='x', pady=(0, 10))
        
        # Module filter
        ttk.Label(filter_frame, text="Module:").grid(row=0, column=0, sticky='w', padx=5)
        self.module_filter_var = tk.StringVar()
        module_combo = ttk.Combobox(filter_frame, textvariable=self.module_filter_var, width=20)
        module_combo.grid(row=0, column=1, padx=5)
        self.load_modules(module_combo)
        existing_values = list(module_combo['values'])
        module_combo['values'] = ["All Modules"] + existing_values
        module_combo.set("All Modules")
        if hasattr(self, 'module_map'):
            self.module_map["All Modules"] = None
    
        # Status filter
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=2, sticky='w', padx=5)
        self.status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_filter_var, 
                                   values=["All", "Submitted", "Graded", "Late"], width=15)
        status_combo.grid(row=0, column=3, padx=5)
        
        # Apply filter button
        ttk.Button(filter_frame, text="Apply Filters", 
                  command=self.apply_admin_submission_filters).grid(row=0, column=4, padx=10)
        
        # Submissions table
        submissions_frame = ttk.Frame(self.gui.layout.content_area)
        submissions_frame.pack(fill='both', expand=True)
        
        columns = ('ID', 'Student', 'Assignment', 'Module', 'Submitted', 'Status', 'Grade')
        self.all_submissions_tree = ttk.Treeview(submissions_frame, columns=columns, show='headings')
        
        for col in columns:
            self.all_submissions_tree.heading(col, text=col)
            self.all_submissions_tree.column(col, width=100)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(submissions_frame, orient='vertical', command=self.all_submissions_tree.yview)
        h_scroll = ttk.Scrollbar(submissions_frame, orient='horizontal', command=self.all_submissions_tree.xview)
        self.all_submissions_tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.all_submissions_tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        submissions_frame.grid_rowconfigure(0, weight=1)
        submissions_frame.grid_columnconfigure(0, weight=1)
        
        # Load all submissions
        self.load_all_submissions()
        
        # Action buttons
        action_frame = ttk.Frame(self.gui.layout.content_area)
        action_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(action_frame, text="Grade Selected", 
                  command=self.grade_selected_submission).pack(side='left', padx=(0, 10))
        ttk.Button(action_frame, text="Download File", 
                  command=self.download_selected_file).pack(side='left', padx=(0, 10))
        ttk.Button(action_frame, text="Export List", 
                  command=self.export_submissions_list).pack(side='left')
    

    def load_all_submissions(self):
        """Load all submissions into treeview"""
        # Clear existing data
        for item in self.all_submissions_tree.get_children():
            self.all_submissions_tree.delete(item)
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
    
            module_label = getattr(self, 'module_filter_var', tk.StringVar()).get()
            module_code = None
            if module_label:
                module_code = self.module_map.get(module_label)
                if module_code is None and module_label not in ("All Modules", "") and ' - ' not in module_label:
                    module_code = module_label
    
            status_filter = getattr(self, 'status_filter_var', tk.StringVar(value="All")).get()
    
            query = '''
                SELECT s.id, st.first_name, st.last_name, a.title, a.module_code,
                       s.submission_date, s.status,
                       CASE WHEN s.grade IS NULL THEN 'Not Graded' ELSE CAST(s.grade AS TEXT) || '%' END as grade
                FROM assignment_submissions s
                JOIN assignments a ON s.assignment_id = a.id
                JOIN students st ON s.student_id = st.student_id
                WHERE 1=1
            '''
            params = []
    
            if module_code:
                query += " AND a.module_code = ?"
                params.append(module_code)
    
            if status_filter and status_filter != "All":
                if status_filter == "Late":
                    query += " AND s.late_submission = 1"
                else:
                    query += " AND LOWER(s.status) = ?"
                    params.append(status_filter.lower())
    
            query += " ORDER BY s.submission_date DESC"
    
            cursor.execute(query, params)
            submissions = cursor.fetchall()
            
            for submission in submissions:
                sid, fname, lname, title, module, date, status, grade = submission
                student_name = f"{fname} {lname}"
                
                # Color coding
                tags = []
                if status == 'graded':
                    tags = ['graded']
                elif 'late' in status.lower():
                    tags = ['late']
                elif status.lower() == 'archived':
                    tags = ['archived']
                
                self.all_submissions_tree.insert('', 'end', values=(sid, student_name, title, module, date, status, grade), tags=tags)
            
            # Configure tags
            self.all_submissions_tree.tag_configure('graded', background='#e8f5e8')
            self.all_submissions_tree.tag_configure('late', background='#ffebee')
            self.all_submissions_tree.tag_configure('archived', background='#eeeeee')
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load submissions: {e}")
    

    def apply_admin_submission_filters(self):
        """Apply filters for the instructor/admin submissions view."""
        self.load_all_submissions()
    

    def grade_selected_submission(self):
        """Grade the selected submission"""
        selection = self.all_submissions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission to grade")
            return
        
        item = self.all_submissions_tree.item(selection[0])
        submission_id = item['values'][0]

        # Switch to grading interface
        self.gui.grading.show_grading_interface(submission_id)
    

    def download_selected_file(self):
        """Download the selected submission file"""
        selection = self.all_submissions_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission")
            return
        
        item = self.all_submissions_tree.item(selection[0])
        submission_id = item['values'][0]
        
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('SELECT file_path, file_name FROM assignment_submissions WHERE id = ?', (submission_id,))
            result = cursor.fetchone()
            
            if result:
                file_path, file_name = result
                save_path = filedialog.asksaveasfilename(
                    defaultextension=os.path.splitext(file_name)[1],
                    initialfile=file_name,
                    filetypes=[("All Files", "*.*")]
                )
                
                if save_path and os.path.exists(file_path):
                    shutil.copy2(file_path, save_path)
                    messagebox.showinfo("Success", f"File saved to: {save_path}")
                else:
                    messagebox.showerror("Error", "Source file not found")
            
            conn.close()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download file: {e}")
    

    def export_submissions_list(self):
        """Export submissions list to CSV"""
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if not save_path:
                return
            
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            
            cursor.execute('''
            SELECT s.id, st.student_id, st.first_name, st.last_name, 
                   a.title, a.module_code, s.submission_date, s.status, s.grade
            FROM assignment_submissions s
            JOIN assignments a ON s.assignment_id = a.id
            JOIN students st ON s.student_id = st.student_id
            ORDER BY s.submission_date DESC
            ''')
            
            data = cursor.fetchall()
            
            import csv
            with open(save_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['ID', 'Student ID', 'First Name', 'Last Name', 'Assignment', 'Module', 'Submitted', 'Status', 'Grade'])
                writer.writerows(data)
            
            conn.close()
            messagebox.showinfo("Success", f"Submissions exported to: {save_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export submissions: {e}")
    
    # Additional helper method for permission checking in GUI

    def view_submission_file(self, tree):
        """View selected submission file"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission")
            return
        
        submission_id = tree.item(selection[0])['values'][0]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                'SELECT file_path FROM assignment_submissions WHERE id = ?',
                (submission_id,)
            )
            row = cursor.fetchone()
            conn.close()
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to load submission: {exc}")
            return
    
        if not row or not row[0]:
            messagebox.showwarning("Missing File", "No file is associated with this submission.")
            return
    
        file_path = row[0]
        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"The file could not be located:\n{file_path}")
            return
    
        self.open_submission_file(file_path)
    

    def download_submission_file(self, tree):
        """Download selected submission file"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a submission")
            return
        
        submission_id = tree.item(selection[0])['values'][0]
    
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute(
                'SELECT file_path FROM assignment_submissions WHERE id = ?',
                (submission_id,)
            )
            row = cursor.fetchone()
            conn.close()
        except Exception as exc:
            messagebox.showerror("Error", f"Unable to load submission: {exc}")
            return
    
        if not row or not row[0]:
            messagebox.showwarning("Missing File", "No file is associated with this submission.")
            return
    
        file_path = row[0]
        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"The file could not be located:\n{file_path}")
            return
    
        self.download_file(file_path)
    

    def open_submission_file(self, file_path):
        """Open submission file with default application"""
        try:
            import os
            import platform
            import subprocess

            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path], check=False)
            elif platform.system() == 'Windows':  # Windows
                os.startfile(file_path)
            else:  # Linux
                subprocess.run(['xdg-open', file_path], check=False)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")
    

    def download_file(self, file_path):
        """Download file to user's chosen location"""
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=os.path.splitext(file_path)[1],
                filetypes=[("All Files", "*.*")]
            )
            
            if save_path:
                import shutil
                shutil.copy2(file_path, save_path)
                messagebox.showinfo("Success", f"File saved to: {save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to download file: {e}")

    def _send_submission_emails(self, student_id, assignment_id, assignment_title,
                                module_code, module_name, version_number,
                                late_submission, late_days):
        """Send email notifications for assignment submission"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get student info and email
            cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (student_id,))
            student_row = cursor.fetchone()

            if not student_row:
                print(f"Warning: Student {student_id} not found in database")
                conn.close()
                return

            student_first_name, student_last_name, student_email = student_row
            student_name = f"{student_first_name} {student_last_name}"

            # Send confirmation email to student
            if student_email:
                late_text = f" (Late submission - {late_days} days overdue)" if late_submission else ""

                # Use email template
                try:
                    from education_system.university_system.infrastructure.email.template_utils import render_template
                    student_subject, student_body = render_template("assignment_submission_student", {
                        "first_name": student_first_name,
                        "module_code": module_code,
                        "module_name": module_name,
                        "assignment_title": assignment_title,
                        "version_number": str(version_number),
                        "submission_status": 'Late Submission' if late_submission else 'On Time',
                        "late_text": late_text,
                        "submission_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    if not student_subject or not student_body:
                        raise ValueError("Template returned empty subject/body")
                except Exception as template_error:
                    # Fallback to hardcoded email
                    student_subject = f"Assignment Submission Confirmed: {assignment_title}"
                    student_body = f"""Dear {student_first_name},

This email confirms that your assignment has been successfully submitted.

Assignment Details:
- Module: {module_code} - {module_name}
- Assignment: {assignment_title}
- Submission Version: {version_number}
- Status: {'Late Submission' if late_submission else 'On Time'}{late_text}
- Submission Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Your submission is being processed and will be reviewed by your instructor.

You can view your submission details in the Assignment System.

Best regards,
Academic Administration Team
"""

                try:
                    send_email(student_email, student_subject, student_body)
                    print(f"Confirmation email sent to student: {student_email}")
                except Exception as e:
                    print(f"Failed to send student email: {e}")

            # Get instructor/staff email for this module
            # First try to get from assignments table (created_by)
            cursor.execute('''
                SELECT u.email, u.first_name, u.last_name
                FROM assignments a
                JOIN users u ON a.created_by = u.id
                WHERE a.id = ?
            ''', (assignment_id,))

            instructor_row = cursor.fetchone()

            # Also get admin emails as backup
            cursor.execute('''
                SELECT email, first_name FROM users
                WHERE LOWER(role) IN ('admin', 'staff', 'instructor')
                AND email IS NOT NULL AND email != ''
            ''')

            admin_staff_emails = cursor.fetchall()

            # Send notification to instructor/creator
            if instructor_row and instructor_row[0]:
                instructor_email, instructor_first, instructor_last = instructor_row

                # Use email template
                try:
                    from education_system.university_system.infrastructure.email.template_utils import render_template
                    instructor_subject, instructor_body = render_template("assignment_submission_instructor", {
                        "instructor_first_name": instructor_first,
                        "module_code": module_code,
                        "module_name": module_name,
                        "assignment_title": assignment_title,
                        "student_name": student_name,
                        "student_id": student_id,
                        "version_number": str(version_number),
                        "submission_status": 'Late Submission' if late_submission else 'On Time',
                        "late_text": late_text,
                        "submission_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    if not instructor_subject or not instructor_body:
                        raise ValueError("Template returned empty subject/body")
                except Exception as template_error:
                    # Fallback to hardcoded email
                    instructor_subject = f"New Assignment Submission: {assignment_title}"
                    instructor_body = f"""Dear {instructor_first},

A student has submitted an assignment for your review.

Assignment Details:
- Module: {module_code} - {module_name}
- Assignment: {assignment_title}
- Student: {student_name} ({student_id})
- Submission Version: {version_number}
- Status: {'Late Submission' if late_submission else 'On Time'}{late_text}
- Submission Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please review the submission in the Assignment Grading System.

Best regards,
Assignment Management System
"""

                try:
                    send_email(instructor_email, instructor_subject, instructor_body)
                    print(f"Notification email sent to instructor: {instructor_email}")
                except Exception as e:
                    print(f"Failed to send instructor email: {e}")

            # Send to admins if instructor email failed or doesn't exist
            if not instructor_row or not instructor_row[0]:
                for admin_email, admin_first in admin_staff_emails[:3]:  # Limit to first 3
                    if admin_email:
                        # Use email template
                        try:
                            from education_system.university_system.infrastructure.email.template_utils import render_template
                            admin_subject, admin_body = render_template("assignment_submission_admin", {
                                "admin_first_name": admin_first,
                                "module_code": module_code,
                                "module_name": module_name,
                                "assignment_title": assignment_title,
                                "student_name": student_name,
                                "student_id": student_id,
                                "version_number": str(version_number),
                                "submission_status": 'Late Submission' if late_submission else 'On Time',
                                "late_text": late_text
                            })
                            if not admin_subject or not admin_body:
                                raise ValueError("Template returned empty subject/body")
                        except Exception as template_error:
                            # Fallback to hardcoded email
                            admin_subject = f"Assignment Submission Notification: {assignment_title}"
                            admin_body = f"""Dear {admin_first},

A student has submitted an assignment.

Assignment Details:
- Module: {module_code} - {module_name}
- Assignment: {assignment_title}
- Student: {student_name} ({student_id})
- Submission Version: {version_number}
- Status: {'Late Submission' if late_submission else 'On Time'}{late_text}

This notification was sent because no instructor email was found for this assignment.

Best regards,
Assignment Management System
"""

                        try:
                            send_email(admin_email, admin_subject, admin_body)
                            print(f"Notification email sent to admin: {admin_email}")
                        except Exception as e:
                            print(f"Failed to send admin email to {admin_email}: {e}")

            conn.close()

        except Exception as e:
            print(f"Error in _send_submission_emails: {e}")
            import traceback
            traceback.print_exc()

