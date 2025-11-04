"""
Degree Audit & Academic Advising GUI

Full-featured GUI for managing degree progress, prerequisites, what-if scenarios,
advising appointments, and graduation audits.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime
from typing import Optional

from university_system.infrastructure.auth.user_authentication import UserAuth
from university_system.modules.domain.academics.services.degree_audit.degree_audit_core import (
    DegreeProgramManager,
    DegreeProgressManager,
    WhatIfScenarioManager,
    AdvisingAppointmentManager,
    GraduationAuditManager
)
from university_system.modules.domain.academics.services.degree_audit.db_schema import initialize_degree_audit_database
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.activity_logger import log_activity


class DegreeAuditGUI:
    """Main GUI for Degree Audit & Academic Advising System"""

    def __init__(self, parent, auth: UserAuth):
        self.root = tk.Toplevel(parent)
        self.root.title("Degree Audit & Academic Advising System")
        self.root.geometry("1200x700")
        self.auth = auth

        # Initialize database
        try:
            initialize_degree_audit_database()
        except Exception as e:
            print(f"Database initialization warning: {e}")

        self.create_widgets()
        self.load_programs()
        self.load_student_progress()

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(main_frame, text="Degree Audit & Academic Advising System",
                         font=('Arial', 16, 'bold'))
        title.pack(pady=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_progress_tab()
        self.create_prerequisites_tab()
        self.create_whatif_tab()
        self.create_advising_tab()
        self.create_graduation_tab()

    def create_progress_tab(self):
        """Create Degree Progress tracking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Degree Progress")

        # Top frame for student selection
        select_frame = ttk.LabelFrame(tab, text="Student Selection", padding="10")
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.progress_student_entry = ttk.Entry(select_frame, width=30)
        self.progress_student_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Button(select_frame, text="Load Progress",
                  command=self.load_student_progress).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(select_frame, text="Update Progress",
                  command=self.update_progress).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(select_frame, text="Initialize Progress",
                  command=self.initialize_progress).grid(row=0, column=4, padx=5, pady=5)

        # Progress summary frame
        summary_frame = ttk.LabelFrame(tab, text="Progress Summary", padding="10")
        summary_frame.pack(fill=tk.X, pady=5)

        self.progress_labels = {}
        labels = ['Program', 'Credits Earned', 'Credits Required', 'Current GPA',
                 'Completion %', 'Enrollment Year', 'Expected Graduation']

        for i, label in enumerate(labels):
            ttk.Label(summary_frame, text=f"{label}:", font=('Arial', 10, 'bold')).grid(
                row=i//2, column=(i%2)*2, sticky=tk.W, padx=10, pady=5)
            self.progress_labels[label] = ttk.Label(summary_frame, text="N/A")
            self.progress_labels[label].grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, padx=10, pady=5)

        # Detailed progress treeview
        list_frame = ttk.LabelFrame(tab, text="Requirement Details", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('Requirement Type', 'Name', 'Credits Required', 'Status', 'Grade Required')
        self.progress_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.progress_tree.heading(col, text=col)
            width = 200 if col == 'Name' else 120
            self.progress_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.progress_tree.yview)
        self.progress_tree.configure(yscrollcommand=scrollbar.set)

        self.progress_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_prerequisites_tab(self):
        """Create Prerequisites checking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Prerequisites")

        ttk.Label(tab, text="Check Course Prerequisites",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Check prerequisite frame
        check_frame = ttk.LabelFrame(tab, text="Check Prerequisites", padding="10")
        check_frame.pack(fill=tk.X, pady=5)

        ttk.Label(check_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_student_entry = ttk.Entry(check_frame, width=30)
        self.prereq_student_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(check_frame, text="Module Code:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_module_entry = ttk.Entry(check_frame, width=30)
        self.prereq_module_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Button(check_frame, text="Check Prerequisites",
                  command=self.check_prerequisites).grid(row=0, column=2, rowspan=2, padx=10, pady=5)

        # Results display
        results_frame = ttk.LabelFrame(tab, text="Prerequisite Check Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.prereq_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                             width=80, height=12)
        self.prereq_results_text.pack(fill=tk.BOTH, expand=True)

        # Add prerequisite frame
        add_frame = ttk.LabelFrame(tab, text="Add New Prerequisite", padding="10")
        add_frame.pack(fill=tk.X, pady=5)

        ttk.Label(add_frame, text="Course:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_course_entry = ttk.Entry(add_frame, width=25)
        self.prereq_course_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(add_frame, text="Prerequisite:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.prereq_prereq_entry = ttk.Entry(add_frame, width=25)
        self.prereq_prereq_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(add_frame, text="Min Grade:").grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.prereq_grade_entry = ttk.Entry(add_frame, width=10)
        self.prereq_grade_entry.grid(row=0, column=5, padx=5, pady=5)

        ttk.Button(add_frame, text="Add Prerequisite",
                  command=self.add_prerequisite).grid(row=0, column=6, padx=10, pady=5)

    def create_whatif_tab(self):
        """Create What-If Scenarios tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="What-If Scenarios")

        ttk.Label(tab, text="Analyze Program Change Scenarios",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Create scenario frame
        create_frame = ttk.LabelFrame(tab, text="Create What-If Scenario", padding="10")
        create_frame.pack(fill=tk.X, pady=5)

        ttk.Label(create_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_student_entry = ttk.Entry(create_frame, width=30)
        self.whatif_student_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(create_frame, text="Scenario Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_name_entry = ttk.Entry(create_frame, width=30)
        self.whatif_name_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(create_frame, text="Target Program:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_program_combo = ttk.Combobox(create_frame, width=28, state='readonly')
        self.whatif_program_combo.grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(create_frame, text="Notes:").grid(row=3, column=0, sticky=tk.NW, padx=5, pady=5)
        self.whatif_notes_text = tk.Text(create_frame, width=40, height=4)
        self.whatif_notes_text.grid(row=3, column=1, padx=5, pady=5)

        button_frame = ttk.Frame(create_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Create Scenario",
                  command=self.create_whatif_scenario).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Analyze",
                  command=self.analyze_whatif).pack(side=tk.LEFT, padx=5)

        # Analysis results
        results_frame = ttk.LabelFrame(tab, text="Scenario Analysis Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.whatif_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                             width=80, height=15)
        self.whatif_results_text.pack(fill=tk.BOTH, expand=True)

    def create_advising_tab(self):
        """Create Academic Advising Appointments tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Advising Appointments")

        ttk.Label(tab, text="Academic Advising Appointments",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Schedule appointment frame
        schedule_frame = ttk.LabelFrame(tab, text="Schedule Appointment", padding="10")
        schedule_frame.pack(fill=tk.X, pady=5)

        fields = {}

        ttk.Label(schedule_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        fields['student'] = ttk.Entry(schedule_frame, width=25)
        fields['student'].grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(schedule_frame, text="Advisor ID:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        fields['advisor'] = ttk.Entry(schedule_frame, width=25)
        fields['advisor'].grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(schedule_frame, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        fields['date'] = ttk.Entry(schedule_frame, width=25)
        fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        fields['date'].grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(schedule_frame, text="Time (HH:MM):").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        fields['time'] = ttk.Entry(schedule_frame, width=25)
        fields['time'].insert(0, "10:00")
        fields['time'].grid(row=1, column=3, padx=5, pady=5)

        ttk.Label(schedule_frame, text="Type:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        fields['type'] = ttk.Combobox(schedule_frame, values=[
            'Academic Planning', 'Course Selection', 'Degree Progress',
            'Career Advising', 'General', 'Other'
        ], width=23, state='readonly')
        fields['type'].current(0)
        fields['type'].grid(row=2, column=1, padx=5, pady=5)

        ttk.Label(schedule_frame, text="Duration (min):").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)
        fields['duration'] = ttk.Entry(schedule_frame, width=25)
        fields['duration'].insert(0, "30")
        fields['duration'].grid(row=2, column=3, padx=5, pady=5)

        ttk.Label(schedule_frame, text="Topic:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        fields['topic'] = ttk.Entry(schedule_frame, width=58)
        fields['topic'].grid(row=3, column=1, columnspan=3, padx=5, pady=5)

        ttk.Label(schedule_frame, text="Notes:").grid(row=4, column=0, sticky=tk.NW, padx=5, pady=5)
        fields['notes'] = tk.Text(schedule_frame, width=58, height=4)
        fields['notes'].grid(row=4, column=1, columnspan=3, padx=5, pady=5)

        self.appointment_fields = fields

        ttk.Button(schedule_frame, text="Schedule Appointment",
                  command=self.schedule_appointment).grid(row=5, column=0, columnspan=4, pady=10)

        # Appointments list
        list_frame = ttk.LabelFrame(tab, text="Scheduled Appointments", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Load appointments button
        ttk.Button(list_frame, text="Load My Appointments",
                  command=self.load_appointments).pack(anchor=tk.W, pady=5)

        columns = ('ID', 'Student', 'Advisor', 'Date', 'Time', 'Type', 'Topic', 'Status')
        self.appointments_tree = ttk.Treeview(list_frame, columns=columns,
                                             show='headings', height=8)

        for col in columns:
            self.appointments_tree.heading(col, text=col)
            width = 150 if col == 'Topic' else 100
            self.appointments_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.appointments_tree.yview)
        self.appointments_tree.configure(yscrollcommand=scrollbar.set)

        self.appointments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_graduation_tab(self):
        """Create Graduation Audit tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Graduation Audit")

        ttk.Label(tab, text="Graduation Readiness Audit",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Audit controls frame
        control_frame = ttk.LabelFrame(tab, text="Run Graduation Audit", padding="10")
        control_frame.pack(fill=tk.X, pady=5)

        ttk.Label(control_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.grad_student_entry = ttk.Entry(control_frame, width=30)
        self.grad_student_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(control_frame, text="Program:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.grad_program_combo = ttk.Combobox(control_frame, width=28, state='readonly')
        self.grad_program_combo.grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(control_frame, text="Run Audit",
                  command=self.run_graduation_audit).grid(row=0, column=4, padx=10, pady=5)

        # Checklist frame
        checklist_frame = ttk.LabelFrame(tab, text="Graduation Checklist", padding="10")
        checklist_frame.pack(fill=tk.X, pady=5)

        self.checklist_vars = {}
        checklist_items = [
            ('all_requirements', 'All Course Requirements Met'),
            ('gpa_requirement', 'GPA Requirement Met'),
            ('credit_requirement', 'Credit Requirement Met'),
            ('residency', 'Residency Requirement Met'),
            ('financial', 'Financial Clearance')
        ]

        for i, (key, label) in enumerate(checklist_items):
            var = tk.BooleanVar()
            self.checklist_vars[key] = var
            ttk.Checkbutton(checklist_frame, text=label, variable=var,
                           state='disabled').grid(row=i//2, column=(i%2)*2,
                                                 columnspan=2, sticky=tk.W, padx=20, pady=5)

        # Audit results display
        results_frame = ttk.LabelFrame(tab, text="Audit Results", padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.grad_results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                           width=80, height=12)
        self.grad_results_text.pack(fill=tk.BOTH, expand=True)

        # Approval frame
        approval_frame = ttk.Frame(tab)
        approval_frame.pack(fill=tk.X, pady=10)

        ttk.Label(approval_frame, text="Graduation Date:").pack(side=tk.LEFT, padx=5)
        self.grad_date_entry = ttk.Entry(approval_frame, width=20)
        self.grad_date_entry.insert(0, datetime.now().strftime('%Y-%m-%d'))
        self.grad_date_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(approval_frame, text="Approve for Graduation",
                  command=self.approve_graduation).pack(side=tk.LEFT, padx=20)

    # ======================== Helper Methods ========================

    def load_programs(self):
        """Load all degree programs into combo boxes"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT program_id, program_code, program_name
                    FROM degree_programs
                    WHERE is_active = 1
                    ORDER BY program_name
                ''')

                programs = cursor.fetchall()
                program_list = [f"{row[0]}: {row[1]} - {row[2]}" for row in programs]

                # Update all combo boxes that need programs
                self.whatif_program_combo['values'] = program_list
                self.grad_program_combo['values'] = program_list

        except Exception as e:
            print(f"Failed to load programs: {e}")

    def load_student_progress(self):
        """Load and display student degree progress"""
        try:
            student_id = self.progress_student_entry.get().strip()
            if not student_id:
                # Use current user if no student ID provided
                student_id = self.auth.current_user.get('username') if self.auth.current_user else None

            if not student_id:
                return

            progress = DegreeProgressManager.get_student_progress(student_id)

            if progress:
                self.progress_labels['Program'].config(text=progress.get('program_name', 'N/A'))
                self.progress_labels['Credits Earned'].config(
                    text=str(progress.get('total_credits_earned', 0)))
                self.progress_labels['Credits Required'].config(
                    text=str(progress.get('total_credits_required', 0)))
                self.progress_labels['Current GPA'].config(
                    text=f"{progress.get('current_gpa', 0.0):.2f}")
                self.progress_labels['Completion %'].config(
                    text=f"{progress.get('completion_percentage', 0.0):.1f}%")
                self.progress_labels['Enrollment Year'].config(
                    text=str(progress.get('enrollment_year', 'N/A')))
                self.progress_labels['Expected Graduation'].config(
                    text=progress.get('expected_graduation_date', 'N/A'))

                # Load requirements
                self.load_requirements(progress.get('program_id'))
            else:
                messagebox.showinfo("Info", "No progress found for this student")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load progress: {e}")

    def load_requirements(self, program_id):
        """Load program requirements into treeview"""
        try:
            self.progress_tree.delete(*self.progress_tree.get_children())

            requirements = DegreeProgramManager.get_program_requirements(program_id)

            for req in requirements:
                status = "Completed" if req.get('is_mandatory') else "Optional"
                self.progress_tree.insert('', tk.END, values=(
                    req.get('requirement_type', ''),
                    req.get('requirement_name', ''),
                    req.get('credits_required', 0),
                    status,
                    req.get('min_grade', 'N/A')
                ))

        except Exception as e:
            print(f"Failed to load requirements: {e}")

    def update_progress(self):
        """Update student's degree progress"""
        try:
            student_id = self.progress_student_entry.get().strip()
            if not student_id:
                messagebox.showwarning("Warning", "Please enter a student ID")
                return

            # Get student's program
            progress = DegreeProgressManager.get_student_progress(student_id)
            if not progress:
                messagebox.showwarning("Warning", "No progress record found. Please initialize first.")
                return

            program_id = progress.get('program_id')
            DegreeProgressManager.update_progress(student_id, program_id)

            log_activity('update', 'degree_progress', student_id,
                       {'program_id': program_id})

            messagebox.showinfo("Success", "Degree progress updated successfully!")
            self.load_student_progress()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update progress: {e}")

    def initialize_progress(self):
        """Initialize degree progress for a student"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Initialize Degree Progress")
        dialog.geometry("400x250")

        ttk.Label(dialog, text="Student ID:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=10)
        student_entry = ttk.Entry(dialog, width=30)
        student_entry.grid(row=0, column=1, padx=10, pady=10)

        ttk.Label(dialog, text="Program:").grid(row=1, column=0, sticky=tk.W, padx=10, pady=10)
        program_combo = ttk.Combobox(dialog, width=28, state='readonly')
        program_combo.grid(row=1, column=1, padx=10, pady=10)

        # Load programs
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT program_id, program_code, program_name FROM degree_programs WHERE is_active = 1')
                programs = cursor.fetchall()
                program_combo['values'] = [f"{row[0]}: {row[1]} - {row[2]}" for row in programs]
        except Exception as e:
            print(f"Failed to load programs: {e}")

        ttk.Label(dialog, text="Enrollment Year:").grid(row=2, column=0, sticky=tk.W, padx=10, pady=10)
        year_entry = ttk.Entry(dialog, width=30)
        year_entry.insert(0, str(datetime.now().year))
        year_entry.grid(row=2, column=1, padx=10, pady=10)

        def save_init():
            try:
                student_id = student_entry.get().strip()
                program_selection = program_combo.get()
                enrollment_year = int(year_entry.get())

                if not student_id or not program_selection:
                    messagebox.showerror("Error", "All fields are required")
                    return

                program_id = int(program_selection.split(':')[0])

                progress_id = DegreeProgressManager.initialize_student_progress(
                    student_id, program_id, enrollment_year
                )

                log_activity('create', 'degree_progress', student_id,
                           {'program_id': program_id, 'year': enrollment_year})

                messagebox.showinfo("Success",
                                  f"Progress initialized successfully! ID: {progress_id}")
                dialog.destroy()
                self.load_student_progress()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to initialize progress: {e}")

        ttk.Button(dialog, text="Initialize",
                  command=save_init).grid(row=3, column=0, columnspan=2, pady=20)

    def check_prerequisites(self):
        """Check if student met prerequisites for a course"""
        try:
            student_id = self.prereq_student_entry.get().strip()
            module_code = self.prereq_module_entry.get().strip()

            if not student_id or not module_code:
                messagebox.showwarning("Warning", "Please enter both Student ID and Module Code")
                return

            can_enroll, missing = DegreeProgressManager.check_prerequisite_completion(
                student_id, module_code
            )

            self.prereq_results_text.delete('1.0', tk.END)
            self.prereq_results_text.insert(tk.END,
                f"PREREQUISITE CHECK - {module_code}\n")
            self.prereq_results_text.insert(tk.END, "=" * 60 + "\n\n")
            self.prereq_results_text.insert(tk.END,
                f"Student ID: {student_id}\n")
            self.prereq_results_text.insert(tk.END,
                f"Module Code: {module_code}\n\n")

            if can_enroll:
                self.prereq_results_text.insert(tk.END,
                    "STATUS: ELIGIBLE\n\n"
                    "All prerequisites have been met. Student can enroll in this course.\n")
            else:
                self.prereq_results_text.insert(tk.END,
                    "STATUS: NOT ELIGIBLE\n\n"
                    "Missing Prerequisites:\n")
                for prereq in missing:
                    self.prereq_results_text.insert(tk.END, f"  - {prereq}\n")

            log_activity('check', 'prerequisite', module_code,
                       {'student_id': student_id, 'can_enroll': can_enroll})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check prerequisites: {e}")

    def add_prerequisite(self):
        """Add a new prerequisite relationship"""
        try:
            module_code = self.prereq_course_entry.get().strip()
            prerequisite = self.prereq_prereq_entry.get().strip()
            min_grade = self.prereq_grade_entry.get().strip()

            if not module_code or not prerequisite:
                messagebox.showwarning("Warning", "Course and Prerequisite are required")
                return

            prereq_id = DegreeProgramManager.add_prerequisite(
                module_code=module_code,
                prerequisite_module_code=prerequisite,
                min_grade=min_grade if min_grade else None
            )

            log_activity('create', 'prerequisite', str(prereq_id),
                       {'course': module_code, 'prerequisite': prerequisite})

            messagebox.showinfo("Success",
                              f"Prerequisite added successfully! ID: {prereq_id}")

            # Clear fields
            self.prereq_course_entry.delete(0, tk.END)
            self.prereq_prereq_entry.delete(0, tk.END)
            self.prereq_grade_entry.delete(0, tk.END)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add prerequisite: {e}")

    def create_whatif_scenario(self):
        """Create and analyze what-if scenario"""
        try:
            student_id = self.whatif_student_entry.get().strip()
            scenario_name = self.whatif_name_entry.get().strip()
            program_selection = self.whatif_program_combo.get()
            notes = self.whatif_notes_text.get('1.0', tk.END).strip()

            if not student_id or not scenario_name or not program_selection:
                messagebox.showwarning("Warning", "All fields are required")
                return

            target_program_id = int(program_selection.split(':')[0])

            scenario_id = WhatIfScenarioManager.create_scenario(
                student_id=student_id,
                scenario_name=scenario_name,
                target_program_id=target_program_id,
                notes=notes
            )

            log_activity('create', 'whatif_scenario', str(scenario_id),
                       {'student_id': student_id, 'program_id': target_program_id})

            messagebox.showinfo("Success",
                              f"Scenario created successfully! ID: {scenario_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create scenario: {e}")

    def analyze_whatif(self):
        """Analyze what-if scenario"""
        try:
            student_id = self.whatif_student_entry.get().strip()
            program_selection = self.whatif_program_combo.get()

            if not student_id or not program_selection:
                messagebox.showwarning("Warning", "Student ID and Program are required")
                return

            target_program_id = int(program_selection.split(':')[0])

            analysis = WhatIfScenarioManager.analyze_scenario(student_id, target_program_id)

            self.whatif_results_text.delete('1.0', tk.END)
            self.whatif_results_text.insert(tk.END,
                f"WHAT-IF SCENARIO ANALYSIS\n")
            self.whatif_results_text.insert(tk.END, "=" * 60 + "\n\n")
            self.whatif_results_text.insert(tk.END,
                f"Student ID: {student_id}\n")
            self.whatif_results_text.insert(tk.END,
                f"Target Program ID: {target_program_id}\n\n")
            self.whatif_results_text.insert(tk.END,
                f"Total Requirements: {analysis['total_requirements']}\n")
            self.whatif_results_text.insert(tk.END,
                f"Requirements Already Met: {analysis['requirements_met']}\n")
            self.whatif_results_text.insert(tk.END,
                f"Completion Percentage: {analysis['completion_percentage']:.1f}%\n")
            self.whatif_results_text.insert(tk.END,
                f"Completed Courses Count: {analysis['completed_courses_count']}\n\n")

            remaining = analysis['total_requirements'] - analysis['requirements_met']
            self.whatif_results_text.insert(tk.END,
                f"Remaining Requirements: {remaining}\n\n")

            if analysis['completion_percentage'] >= 50:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Feasible program change\n"
                    "More than half of the requirements are already met.")
            else:
                self.whatif_results_text.insert(tk.END,
                    "RECOMMENDATION: Consider carefully\n"
                    "Significant coursework will be required to complete this program.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze scenario: {e}")

    def schedule_appointment(self):
        """Schedule an advising appointment"""
        try:
            fields = self.appointment_fields

            student_id = fields['student'].get().strip()
            advisor_id = fields['advisor'].get().strip()
            date = fields['date'].get().strip()
            time = fields['time'].get().strip()
            appt_type = fields['type'].get()
            duration = int(fields['duration'].get())
            topic = fields['topic'].get().strip()
            notes = fields['notes'].get('1.0', tk.END).strip()

            if not all([student_id, advisor_id, date, time]):
                messagebox.showwarning("Warning",
                                     "Student ID, Advisor ID, Date, and Time are required")
                return

            appointment_id = AdvisingAppointmentManager.schedule_appointment(
                student_id=student_id,
                advisor_id=advisor_id,
                appointment_date=date,
                appointment_time=time,
                appointment_type=appt_type,
                duration_minutes=duration,
                topic=topic,
                notes=notes
            )

            log_activity('create', 'advising_appointment', str(appointment_id),
                       {'student_id': student_id, 'date': date})

            messagebox.showinfo("Success",
                              f"Appointment scheduled successfully! ID: {appointment_id}")

            # Clear fields
            fields['student'].delete(0, tk.END)
            fields['advisor'].delete(0, tk.END)
            fields['topic'].delete(0, tk.END)
            fields['notes'].delete('1.0', tk.END)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule appointment: {e}")

    def load_appointments(self):
        """Load advising appointments for current user"""
        try:
            student_id = self.auth.current_user.get('username') if self.auth.current_user else None
            if not student_id:
                messagebox.showwarning("Warning", "No user logged in")
                return

            self.appointments_tree.delete(*self.appointments_tree.get_children())

            appointments = AdvisingAppointmentManager.get_student_appointments(student_id)

            for appt in appointments:
                self.appointments_tree.insert('', tk.END, values=(
                    appt.get('appointment_id', ''),
                    appt.get('student_id', ''),
                    appt.get('advisor_id', ''),
                    appt.get('appointment_date', ''),
                    appt.get('appointment_time', ''),
                    appt.get('appointment_type', ''),
                    appt.get('topic', ''),
                    appt.get('status', '')
                ))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load appointments: {e}")

    def run_graduation_audit(self):
        """Run comprehensive graduation audit"""
        try:
            student_id = self.grad_student_entry.get().strip()
            program_selection = self.grad_program_combo.get()

            if not student_id or not program_selection:
                messagebox.showwarning("Warning", "Student ID and Program are required")
                return

            program_id = int(program_selection.split(':')[0])

            results = GraduationAuditManager.run_graduation_audit(student_id, program_id)

            # Update checklist
            self.checklist_vars['all_requirements'].set(results['all_requirements_met'])
            self.checklist_vars['gpa_requirement'].set(results['gpa_requirement_met'])
            self.checklist_vars['credit_requirement'].set(results['credit_requirement_met'])

            # Display results
            self.grad_results_text.delete('1.0', tk.END)
            self.grad_results_text.insert(tk.END,
                f"GRADUATION AUDIT RESULTS\n")
            self.grad_results_text.insert(tk.END, "=" * 60 + "\n\n")
            self.grad_results_text.insert(tk.END,
                f"Student ID: {student_id}\n")
            self.grad_results_text.insert(tk.END,
                f"Program ID: {program_id}\n\n")
            self.grad_results_text.insert(tk.END,
                f"Total Requirements: {results['total_requirements']}\n")
            self.grad_results_text.insert(tk.END,
                f"Completed Requirements: {results['completed_requirements']}\n\n")

            self.grad_results_text.insert(tk.END, "Requirement Status:\n")
            self.grad_results_text.insert(tk.END,
                f"  All Requirements: {'✓ PASS' if results['all_requirements_met'] else '✗ FAIL'}\n")
            self.grad_results_text.insert(tk.END,
                f"  GPA Requirement: {'✓ PASS' if results['gpa_requirement_met'] else '✗ FAIL'}\n")
            self.grad_results_text.insert(tk.END,
                f"  Credit Requirement: {'✓ PASS' if results['credit_requirement_met'] else '✗ FAIL'}\n\n")

            if results['can_graduate']:
                self.grad_results_text.insert(tk.END,
                    "GRADUATION STATUS: ELIGIBLE\n\n"
                    "Student meets all requirements for graduation.\n")
            else:
                self.grad_results_text.insert(tk.END,
                    "GRADUATION STATUS: NOT ELIGIBLE\n\n"
                    "Student does not meet all requirements. Review checklist above.\n")

            log_activity('run', 'graduation_audit', student_id,
                       {'program_id': program_id, 'can_graduate': results['can_graduate']})

            messagebox.showinfo("Success", "Graduation audit completed!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to run graduation audit: {e}")

    def approve_graduation(self):
        """Approve student for graduation"""
        try:
            student_id = self.grad_student_entry.get().strip()
            program_selection = self.grad_program_combo.get()
            grad_date = self.grad_date_entry.get().strip()

            if not student_id or not program_selection or not grad_date:
                messagebox.showwarning("Warning", "All fields are required")
                return

            program_id = int(program_selection.split(':')[0])

            # Confirm approval
            confirm = messagebox.askyesno("Confirm Graduation Approval",
                f"Approve {student_id} for graduation on {grad_date}?\n\n"
                "This action should only be performed after verifying all requirements.")

            if not confirm:
                return

            success = GraduationAuditManager.approve_graduation(
                student_id, program_id, grad_date
            )

            if success:
                log_activity('approve', 'graduation', student_id,
                           {'program_id': program_id, 'date': grad_date})

                messagebox.showinfo("Success",
                    f"Student {student_id} approved for graduation on {grad_date}!")
            else:
                messagebox.showerror("Error", "Graduation approval failed")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to approve graduation: {e}")

    def view_requirements(self):
        """Show program requirements"""
        messagebox.showinfo("View Requirements",
                          "Use the Degree Progress tab to view detailed requirements")


def launch_degree_audit_gui(root, auth):
    """Launch the Degree Audit & Academic Advising GUI"""
    try:
        if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
            messagebox.showerror("Error",
                               "You must be logged in to access Degree Audit System.")
            return

        DegreeAuditGUI(root, auth)

    except Exception as e:
        messagebox.showerror("Error",
                           f"Failed to launch Degree Audit System: {e}")


__all__ = ['DegreeAuditGUI', 'launch_degree_audit_gui']
