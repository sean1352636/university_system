"""Split from course_planning_gui.py — provides mixins assembled in
course_planning_gui/__init__.py into the final CoursePlanningGUI class."""
from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.modules.domain.academics.course_planning.services.planning_service import PlanningService
from education_system.university_system.modules.domain.academics.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.university_system.core.activity_logger import log_activity


class _ToolsMixin:
    """Methods extracted from CoursePlanningGUI.tools responsibility."""

    def _create_tools_tab(self):
        """Create the tools tab with GPA calculator, progress tracker, and plan comparison."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Tools")

        # Create notebook for sub-tools
        tools_notebook = ttk.Notebook(tab)
        tools_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # GPA Calculator/Projector
        self._create_gpa_calculator(tools_notebook)

        # Progress Tracker
        self._create_progress_tracker(tools_notebook)

        # Plan Comparison
        self._create_plan_comparison(tools_notebook)

    def _create_gpa_calculator(self, parent_notebook):
        """Create GPA calculator and projector tool."""
        tab = ttk.Frame(parent_notebook)
        parent_notebook.add(tab, text="GPA Calculator")

        # Create canvas with scrollbar for the entire tab
        canvas = tk.Canvas(tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # Header
        header_frame = ttk.Frame(scrollable_frame)
        header_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(header_frame, text="GPA Calculator & Projector",
                 font=('Arial', 14, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text="Calculate current GPA and project future GPA based on planned courses",
                 font=('Arial', 10)).pack(anchor=tk.W)

        # Current GPA section
        current_frame = ttk.LabelFrame(scrollable_frame, text="Current GPA", padding=15)
        current_frame.pack(fill=tk.X, padx=20, pady=10)

        stats_frame = ttk.Frame(current_frame)
        stats_frame.pack(fill=tk.X)

        self.gpa_current_label = ttk.Label(stats_frame, text="Current GPA: --",
                                           font=('Arial', 18, 'bold'))
        self.gpa_current_label.pack(side=tk.LEFT, padx=20)

        self.gpa_credits_label = ttk.Label(stats_frame, text="Total Credits: --",
                                           font=('Arial', 12))
        self.gpa_credits_label.pack(side=tk.LEFT, padx=20)

        ttk.Button(current_frame, text="Calculate Current GPA",
                  command=self._calculate_current_gpa).pack(pady=10)

        # GPA Projection section
        projection_frame = ttk.LabelFrame(scrollable_frame, text="GPA Projection", padding=15)
        projection_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(projection_frame, text="Project your GPA based on planned courses:",
                 font=('Arial', 11)).pack(anchor=tk.W, pady=5)

        # Select plan
        plan_select_frame = ttk.Frame(projection_frame)
        plan_select_frame.pack(fill=tk.X, pady=10)

        ttk.Label(plan_select_frame, text="Select Plan:").pack(side=tk.LEFT, padx=5)
        self.gpa_plan_combo = ttk.Combobox(plan_select_frame, state='readonly', width=40)
        self.gpa_plan_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(plan_select_frame, text="Load Plans",
                  command=self._load_plans_for_gpa).pack(side=tk.LEFT, padx=5)

        # Projected grade input and button
        grade_frame = ttk.Frame(projection_frame)
        grade_frame.pack(fill=tk.X, pady=10)

        ttk.Label(grade_frame, text="Expected Grade Average:").pack(side=tk.LEFT, padx=5)
        self.gpa_expected_grade = ttk.Combobox(grade_frame, values=['A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'F'],
                                               state='readonly', width=10)
        self.gpa_expected_grade.set('B')
        self.gpa_expected_grade.pack(side=tk.LEFT, padx=5)

        ttk.Button(grade_frame, text="Project GPA",
                  command=self._project_gpa).pack(side=tk.LEFT, padx=15)

        # Results
        results_label_frame = ttk.LabelFrame(projection_frame, text="Projection Results", padding=10)
        results_label_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.gpa_projection_text = scrolledtext.ScrolledText(results_label_frame, wrap=tk.WORD,
                                                             font=('Courier', 10), height=12)
        self.gpa_projection_text.pack(fill=tk.BOTH, expand=True)

    def _create_progress_tracker(self, parent_notebook):
        """Create progress tracker tool."""
        tab = ttk.Frame(parent_notebook)
        parent_notebook.add(tab, text="Progress Tracker")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(header_frame, text="Degree Progress Tracker",
                 font=('Arial', 14, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text="Track completed courses vs remaining requirements",
                 font=('Arial', 10)).pack(anchor=tk.W)

        # Program selection
        program_frame = ttk.Frame(tab)
        program_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(program_frame, text="Program:").pack(side=tk.LEFT, padx=5)
        self.progress_program_var = tk.StringVar()
        self.progress_program_entry = ttk.Combobox(program_frame, textvariable=self.progress_program_var,
                                                    width=30, state='readonly')

        # Load courses from DB and get student's major
        try:
            with get_connection() as conn:
                student = conn.execute(
                    "SELECT course FROM students WHERE student_id = ?",
                    (self.student_id,)
                ).fetchone()

                courses = conn.execute(
                    "SELECT DISTINCT code, name FROM courses ORDER BY code"
                ).fetchall()

            course_list = [f"{c['code']} - {c['name']}" if hasattr(c, '__getitem__') and not isinstance(c, tuple) else f"{c[0]} - {c[1]}" for c in courses]

            # Also add student's enrolled course if not already in the list
            student_course = student['course'] if student and student['course'] else None
            if student_course and not any(student_course in c for c in course_list):
                course_list.insert(0, student_course)

            self.progress_program_entry['values'] = course_list

            # Pre-select student's course
            if student_course:
                for i, c in enumerate(course_list):
                    if c.startswith(student_course) or c == student_course:
                        self.progress_program_entry.current(i)
                        break
                else:
                    self.progress_program_var.set(student_course)
        except Exception:
            pass

        self.progress_program_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(program_frame, text="Analyze Progress",
                  command=self._analyze_progress).pack(side=tk.LEFT, padx=5)

        # Progress display
        display_frame = ttk.LabelFrame(tab, text="Progress Overview", padding=15)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Stats cards
        stats_container = ttk.Frame(display_frame)
        stats_container.pack(fill=tk.X, pady=10)

        self.progress_completed_label = ttk.Label(stats_container, text="Completed: --",
                                                  font=('Arial', 12, 'bold'),
                                                  foreground='green')
        self.progress_completed_label.pack(side=tk.LEFT, padx=20)

        self.progress_remaining_label = ttk.Label(stats_container, text="Remaining: --",
                                                  font=('Arial', 12, 'bold'),
                                                  foreground='orange')
        self.progress_remaining_label.pack(side=tk.LEFT, padx=20)

        self.progress_percent_label = ttk.Label(stats_container, text="Progress: --",
                                                font=('Arial', 12, 'bold'),
                                                foreground='blue')
        self.progress_percent_label.pack(side=tk.LEFT, padx=20)

        # Detailed breakdown
        self.progress_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD,
                                                       font=('Courier', 10), height=20)
        self.progress_text.pack(fill=tk.BOTH, expand=True, pady=10)

    def _create_plan_comparison(self, parent_notebook):
        """Create plan comparison tool."""
        tab = ttk.Frame(parent_notebook)
        parent_notebook.add(tab, text="Plan Comparison")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(header_frame, text="Plan Comparison Tool",
                 font=('Arial', 14, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text="Compare two course plans side-by-side",
                 font=('Arial', 10)).pack(anchor=tk.W)

        # Plan selection
        selection_frame = ttk.Frame(tab)
        selection_frame.pack(fill=tk.X, padx=20, pady=10)

        # Plan 1
        plan1_frame = ttk.LabelFrame(selection_frame, text="Plan 1", padding=10)
        plan1_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.compare_plan1_combo = ttk.Combobox(plan1_frame, state='readonly', width=30)
        self.compare_plan1_combo.pack(fill=tk.X, pady=5)

        # Plan 2
        plan2_frame = ttk.LabelFrame(selection_frame, text="Plan 2", padding=10)
        plan2_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.compare_plan2_combo = ttk.Combobox(plan2_frame, state='readonly', width=30)
        self.compare_plan2_combo.pack(fill=tk.X, pady=5)

        # Buttons
        button_frame = ttk.Frame(tab)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(button_frame, text="Load Plans",
                  command=self._load_plans_for_comparison).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Compare Plans",
                  command=self._compare_plans).pack(side=tk.LEFT, padx=5)

        # Comparison results
        results_frame = ttk.LabelFrame(tab, text="Comparison Results", padding=15)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.comparison_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD,
                                                         font=('Courier', 10), height=20)
        self.comparison_text.pack(fill=tk.BOTH, expand=True)

    # ===== Tools Tab Business Logic =====

    def _calculate_current_gpa(self):
        """Calculate student's current GPA via the canonical calculator."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                gpa, total_credits, details = calculate_student_gpa(cursor, self.student_id)

            if gpa is None or not details:
                messagebox.showinfo("Info", "No graded modules found.")
                return

            total_points = gpa * total_credits

            self.gpa_current_label.config(text=f"Current GPA: {gpa:.2f}")
            self.gpa_credits_label.config(text=f"Total Credits: {total_credits}")

            if hasattr(self, 'gpa_projection_text'):
                self.gpa_projection_text.delete(1.0, tk.END)
                self.gpa_projection_text.insert(tk.END, "=== Current GPA Breakdown ===\n\n")
                self.gpa_projection_text.insert(tk.END, f"Student: {self.student_id}\n")
                self.gpa_projection_text.insert(tk.END, f"Modules graded: {len(details)}\n")
                self.gpa_projection_text.insert(tk.END, f"Total credits: {total_credits}\n")
                self.gpa_projection_text.insert(tk.END, f"GPA: {gpa:.2f}\n\n")
                self.gpa_projection_text.insert(tk.END, "Module Grades:\n")
                self.gpa_projection_text.insert(tk.END, "-" * 60 + "\n")
                for code, name, letter, pts, cr in details:
                    self.gpa_projection_text.insert(
                        tk.END, f"  {code}: {name} - {letter} ({pts:.1f} x {cr} cr)\n"
                    )
                self.gpa_projection_text.insert(tk.END, "-" * 60 + "\n")
                self.gpa_projection_text.insert(
                    tk.END,
                    f"\nWeighted Total: {total_points:.2f} / {total_credits} credits = {gpa:.2f} GPA\n",
                )

            log_activity('view', 'gpa_calculation', user_id=self.student_id,
                        details={'gpa': gpa, 'credits': total_credits})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate GPA: {e}")

    def _load_plans_for_gpa(self):
        """Load student's plans into GPA calculator dropdown."""
        try:
            plans = self.planning_service.get_student_plans(self.student_id)

            if not plans:
                messagebox.showinfo("Info", "No plans found.")
                return

            plan_names = [f"{p['plan_name']} (ID: {p['plan_id']})" for p in plans]
            self.gpa_plan_combo['values'] = plan_names

            if plan_names:
                self.gpa_plan_combo.set(plan_names[0])

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load plans: {e}")

    def _project_gpa(self):
        """Project GPA based on planned courses."""
        if not self.gpa_plan_combo.get():
            messagebox.showwarning("Warning", "Please select a plan first.")
            return

        try:
            # Extract plan ID from combo selection
            plan_text = self.gpa_plan_combo.get()
            plan_id = int(plan_text.split('ID: ')[1].rstrip(')'))

            # Get expected grade
            expected_grade = self.gpa_expected_grade.get()

            # Grade points
            grade_points = {
                'A': 4.0, 'A-': 3.7,
                'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                'C+': 2.3, 'C': 2.0, 'C-': 1.7,
                'D': 1.0, 'F': 0.0
            }

            expected_points = grade_points.get(expected_grade, 3.0)

            # Get current GPA
            with get_connection() as conn:
                current_grades = conn.execute("""
                    SELECT m.credits, mg.final_grade as grade
                    FROM module_grades mg
                    LEFT JOIN modules m ON mg.module_code = m.module_code
                    WHERE mg.student_id = ? AND mg.final_grade IS NOT NULL
                    UNION ALL
                    SELECT c.credits, sg.grade
                    FROM student_grades sg
                    LEFT JOIN courses c ON sg.module_code = c.code
                    WHERE sg.student_id = ? AND sg.grade IS NOT NULL
                    AND sg.assessment_name LIKE '%Final%'
                """, (self.student_id, self.student_id)).fetchall()

            current_points = 0.0
            current_credits = 0

            for grade_row in current_grades:
                credits = grade_row['credits']
                grade = grade_row['grade'].strip().upper()
                if grade in grade_points:
                    current_points += grade_points[grade] * credits
                    current_credits += credits

            current_gpa = current_points / current_credits if current_credits > 0 else 0.0

            # Get planned courses
            plan_data = self.planning_service.get_semester_plan(plan_id)
            if not plan_data:
                messagebox.showerror("Error", "Failed to load plan data.")
                return

            # Calculate projected GPA
            self.gpa_projection_text.delete(1.0, tk.END)
            self.gpa_projection_text.insert(tk.END, "=== GPA Projection ===\n\n")
            self.gpa_projection_text.insert(tk.END, f"Current GPA: {current_gpa:.2f}\n")
            self.gpa_projection_text.insert(tk.END, f"Current Credits: {current_credits}\n\n")
            self.gpa_projection_text.insert(tk.END, f"Expected Grade Average: {expected_grade} ({expected_points:.1f} points)\n\n")
            self.gpa_projection_text.insert(tk.END, "Semester-by-Semester Projection:\n")
            self.gpa_projection_text.insert(tk.END, "="*60 + "\n\n")

            cumulative_points = current_points
            cumulative_credits = current_credits

            for semester_num in sorted(plan_data['semesters'].keys()):
                courses = plan_data['semesters'][semester_num]
                if not courses:
                    continue

                semester_credits = sum(c['credits'] for c in courses)
                semester_points = semester_credits * expected_points

                cumulative_points += semester_points
                cumulative_credits += semester_credits
                projected_gpa = cumulative_points / cumulative_credits if cumulative_credits > 0 else 0.0

                sem_name = courses[0]['semester_name'] if courses else f'Semester {semester_num}'

                self.gpa_projection_text.insert(tk.END,
                    f"After {sem_name} (Semester {semester_num}):\n"
                )
                self.gpa_projection_text.insert(tk.END,
                    f"  Courses: {len(courses)} courses, {semester_credits} credits\n"
                )
                self.gpa_projection_text.insert(tk.END,
                    f"  Cumulative Credits: {cumulative_credits}\n"
                )
                self.gpa_projection_text.insert(tk.END,
                    f"  Projected GPA: {projected_gpa:.2f}\n\n"
                )

            final_gpa = cumulative_points / cumulative_credits if cumulative_credits > 0 else 0.0
            gpa_change = final_gpa - current_gpa

            self.gpa_projection_text.insert(tk.END, "="*60 + "\n")
            self.gpa_projection_text.insert(tk.END, f"FINAL PROJECTED GPA: {final_gpa:.2f}\n")
            self.gpa_projection_text.insert(tk.END, f"Change from Current: {gpa_change:+.2f}\n")
            self.gpa_projection_text.insert(tk.END, "="*60 + "\n")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to project GPA: {e}")

    def _analyze_progress(self):
        """Analyze degree completion progress."""
        raw_value = self.progress_program_entry.get().strip()

        if not raw_value:
            messagebox.showwarning("Warning", "Please select a program.")
            return

        # Extract code from "CS - Computer Science" format
        program_code = raw_value.split(' - ')[0].strip() if ' - ' in raw_value else raw_value

        try:
            # Get program requirements
            with get_connection() as conn:
                # Get required courses for program
                program_courses = conn.execute("""
                    SELECT dp.course_id, c.name, c.credits
                    FROM degree_program_courses dp
                    JOIN courses c ON dp.course_id = c.code
                    WHERE dp.program_code = ?
                """, (program_code,)).fetchall()

                # Get completed modules (from module_grades and assignment_submissions)
                completed = conn.execute("""
                    SELECT mg.module_code as course_id, mg.final_grade as grade,
                           m.module_name as name, m.credits
                    FROM module_grades mg
                    LEFT JOIN modules m ON mg.module_code = m.module_code
                    WHERE mg.student_id = ? AND mg.final_grade IS NOT NULL
                    AND mg.final_grade NOT IN ('F', 'W', 'I')
                    UNION
                    SELECT a.module_code as course_id,
                           CASE
                               WHEN AVG(sub.grade) >= 93 THEN 'A'
                               WHEN AVG(sub.grade) >= 83 THEN 'B'
                               WHEN AVG(sub.grade) >= 73 THEN 'C'
                               WHEN AVG(sub.grade) >= 63 THEN 'D'
                               ELSE 'F'
                           END as grade,
                           m.module_name as name, m.credits
                    FROM assignment_submissions sub
                    JOIN assignments a ON sub.assignment_id = a.id
                    LEFT JOIN modules m ON a.module_code = m.module_code
                    WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                    GROUP BY a.module_code
                    HAVING AVG(sub.grade) >= 63
                """, (self.student_id, self.student_id)).fetchall()

            if not program_courses:
                messagebox.showinfo("Info", f"No course requirements found for program: {program_code}")
                return

            # Track completed vs remaining
            completed_ids = {c['course_id'] for c in completed}
            required_ids = {c['course_id'] for c in program_courses}

            completed_required = completed_ids & required_ids
            remaining_required = required_ids - completed_ids

            completed_credits = sum(c['credits'] for c in program_courses if c['course_id'] in completed_required)
            total_credits = sum(c['credits'] for c in program_courses)
            remaining_credits = total_credits - completed_credits

            progress_percent = (len(completed_required) / len(required_ids) * 100) if required_ids else 0

            # Update labels
            self.progress_completed_label.config(
                text=f"Completed: {len(completed_required)}/{len(required_ids)} courses ({completed_credits} cr)"
            )
            self.progress_remaining_label.config(
                text=f"Remaining: {len(remaining_required)} courses ({remaining_credits} cr)"
            )
            self.progress_percent_label.config(
                text=f"Progress: {progress_percent:.1f}%"
            )

            # Display detailed breakdown
            self.progress_text.delete(1.0, tk.END)
            self.progress_text.insert(tk.END, f"=== Degree Progress: {program_code} ===\n\n")

            self.progress_text.insert(tk.END, f"✓ COMPLETED COURSES ({len(completed_required)}):\n")
            self.progress_text.insert(tk.END, "="*60 + "\n")
            for course in program_courses:
                if course['course_id'] in completed_required:
                    # Find grade
                    grade = next((c['grade'] for c in completed if c['course_id'] == course['course_id']), 'N/A')
                    self.progress_text.insert(tk.END,
                        f"  ✓ {course['course_id']}: {course['name']} ({course['credits']} cr) - Grade: {grade}\n"
                    )

            self.progress_text.insert(tk.END, f"\n\n⚠ REMAINING COURSES ({len(remaining_required)}):\n")
            self.progress_text.insert(tk.END, "="*60 + "\n")
            for course in program_courses:
                if course['course_id'] in remaining_required:
                    self.progress_text.insert(tk.END,
                        f"  ○ {course['course_id']}: {course['name']} ({course['credits']} cr)\n"
                    )

            self.progress_text.insert(tk.END, "\n" + "="*60 + "\n")
            self.progress_text.insert(tk.END, f"Total Credits Required: {total_credits}\n")
            self.progress_text.insert(tk.END, f"Credits Completed: {completed_credits}\n")
            self.progress_text.insert(tk.END, f"Credits Remaining: {remaining_credits}\n")
            self.progress_text.insert(tk.END, f"Completion: {progress_percent:.1f}%\n")

            log_activity('view', 'degree_progress', user_id=self.student_id,
                        details={'program': program_code, 'progress': progress_percent})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze progress: {e}")

    def _load_plans_for_comparison(self):
        """Load student's plans into comparison dropdowns."""
        try:
            plans = self.planning_service.get_student_plans(self.student_id)

            if not plans:
                messagebox.showinfo("Info", "No plans found.")
                return

            plan_names = [f"{p['plan_name']} (ID: {p['plan_id']})" for p in plans]
            self.compare_plan1_combo['values'] = plan_names
            self.compare_plan2_combo['values'] = plan_names

            if len(plan_names) >= 2:
                self.compare_plan1_combo.set(plan_names[0])
                self.compare_plan2_combo.set(plan_names[1])
            elif len(plan_names) == 1:
                self.compare_plan1_combo.set(plan_names[0])

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load plans: {e}")

    def _compare_plans(self):
        """Compare two plans side-by-side."""
        if not self.compare_plan1_combo.get() or not self.compare_plan2_combo.get():
            messagebox.showwarning("Warning", "Please select two plans to compare.")
            return

        try:
            # Extract plan IDs
            plan1_text = self.compare_plan1_combo.get()
            plan2_text = self.compare_plan2_combo.get()

            plan1_id = int(plan1_text.split('ID: ')[1].rstrip(')'))
            plan2_id = int(plan2_text.split('ID: ')[1].rstrip(')'))

            if plan1_id == plan2_id:
                messagebox.showwarning("Warning", "Please select two different plans.")
                return

            # Get plan data
            plan1_data = self.planning_service.get_semester_plan(plan1_id)
            plan2_data = self.planning_service.get_semester_plan(plan2_id)

            if not plan1_data or not plan2_data:
                messagebox.showerror("Error", "Failed to load plan data.")
                return

            plan1 = plan1_data['plan']
            plan2 = plan2_data['plan']
            semesters1 = plan1_data['semesters']
            semesters2 = plan2_data['semesters']

            # Calculate statistics
            total_credits1 = sum(sum(c['credits'] for c in courses) for courses in semesters1.values())
            total_credits2 = sum(sum(c['credits'] for c in courses) for courses in semesters2.values())

            total_courses1 = sum(len(courses) for courses in semesters1.values())
            total_courses2 = sum(len(courses) for courses in semesters2.values())

            # Get all course IDs
            courses1_ids = set()
            for courses in semesters1.values():
                courses1_ids.update(c['course_id'] for c in courses)

            courses2_ids = set()
            for courses in semesters2.values():
                courses2_ids.update(c['course_id'] for c in courses)

            common_courses = courses1_ids & courses2_ids
            unique_to_plan1 = courses1_ids - courses2_ids
            unique_to_plan2 = courses2_ids - courses1_ids

            # Display comparison
            self.comparison_text.delete(1.0, tk.END)
            self.comparison_text.insert(tk.END, "=== PLAN COMPARISON ===\n\n")

            # Summary table
            self.comparison_text.insert(tk.END, f"{'Metric':<30} {'Plan 1':<20} {'Plan 2':<20}\n")
            self.comparison_text.insert(tk.END, "="*70 + "\n")
            self.comparison_text.insert(tk.END, f"{'Plan Name':<30} {plan1['plan_name']:<20} {plan2['plan_name']:<20}\n")
            self.comparison_text.insert(tk.END, f"{'Program':<30} {plan1['program_code'] or 'N/A':<20} {plan2['program_code'] or 'N/A':<20}\n")
            self.comparison_text.insert(tk.END, f"{'Start Semester':<30} {plan1['start_semester']:<20} {plan2['start_semester']:<20}\n")
            self.comparison_text.insert(tk.END, f"{'Total Semesters':<30} {plan1['total_semesters']:<20} {plan2['total_semesters']:<20}\n")
            self.comparison_text.insert(tk.END, f"{'Credits/Semester':<30} {plan1['credits_per_semester']:<20} {plan2['credits_per_semester']:<20}\n")
            self.comparison_text.insert(tk.END, f"{'Total Courses':<30} {total_courses1:<20} {total_courses2:<20}\n")
            self.comparison_text.insert(tk.END, f"{'Total Credits':<30} {total_credits1:<20} {total_credits2:<20}\n")
            self.comparison_text.insert(tk.END, f"{'Status':<30} {plan1['status']:<20} {plan2['status']:<20}\n")

            # Course overlap
            self.comparison_text.insert(tk.END, "\n" + "="*70 + "\n")
            self.comparison_text.insert(tk.END, "COURSE OVERLAP ANALYSIS\n")
            self.comparison_text.insert(tk.END, "="*70 + "\n")
            self.comparison_text.insert(tk.END, f"Common Courses: {len(common_courses)}\n")
            self.comparison_text.insert(tk.END, f"Unique to Plan 1: {len(unique_to_plan1)}\n")
            self.comparison_text.insert(tk.END, f"Unique to Plan 2: {len(unique_to_plan2)}\n")

            if common_courses:
                self.comparison_text.insert(tk.END, f"\nCommon Courses ({len(common_courses)}):\n")
                for course_id in sorted(common_courses):
                    self.comparison_text.insert(tk.END, f"  • {course_id}\n")

            if unique_to_plan1:
                self.comparison_text.insert(tk.END, f"\nUnique to Plan 1 ({len(unique_to_plan1)}):\n")
                for course_id in sorted(unique_to_plan1):
                    self.comparison_text.insert(tk.END, f"  • {course_id}\n")

            if unique_to_plan2:
                self.comparison_text.insert(tk.END, f"\nUnique to Plan 2 ({len(unique_to_plan2)}):\n")
                for course_id in sorted(unique_to_plan2):
                    self.comparison_text.insert(tk.END, f"  • {course_id}\n")

            # Semester-by-semester comparison
            self.comparison_text.insert(tk.END, "\n" + "="*70 + "\n")
            self.comparison_text.insert(tk.END, "SEMESTER-BY-SEMESTER COMPARISON\n")
            self.comparison_text.insert(tk.END, "="*70 + "\n\n")

            all_semesters = sorted(set(semesters1.keys()) | set(semesters2.keys()))

            for sem_num in all_semesters:
                courses1 = semesters1.get(sem_num, [])
                courses2 = semesters2.get(sem_num, [])

                credits1 = sum(c['credits'] for c in courses1)
                credits2 = sum(c['credits'] for c in courses2)

                self.comparison_text.insert(tk.END, f"Semester {sem_num}:\n")
                self.comparison_text.insert(tk.END, f"  Plan 1: {len(courses1)} courses, {credits1} credits\n")
                self.comparison_text.insert(tk.END, f"  Plan 2: {len(courses2)} courses, {credits2} credits\n\n")

            log_activity('compare', 'semester_plans', user_id=self.student_id,
                        details={'plan1_id': plan1_id, 'plan2_id': plan2_id})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to compare plans: {e}")

