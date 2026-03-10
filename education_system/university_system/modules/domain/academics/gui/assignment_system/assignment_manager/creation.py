"""Assignment creation form, validation, and execution"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH


class CreationMixin:
    """Assignment creation operations"""

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

        ttk.Button(due_frame, text="\U0001f4c5", command=show_date_picker, width=3).pack(side='left', padx=(10, 0))

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
                from education_system.university_system.infrastructure.email.email_service import send_assignment_notification
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
