"""Split from course_planning_gui.py — provides mixins assembled in
course_planning_gui/__init__.py into the final CoursePlanningGUI class."""
from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.domain.academics.course_planning.services.planning_service import PlanningService
from education_system.systems.university.domain.assessment.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.systems.university.infrastructure.activity_logger import log_activity


class _PlannerMixin:
    """Methods extracted from CoursePlanningGUI.planner responsibility."""

    def _create_planner_tab(self):
        """Create the semester planner tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Semester Planner")

        # Top control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Current Plan:", font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=5)
        self.plan_name_label = ttk.Label(control_frame, text="No plan loaded",
                                         font=('Arial', 11), foreground='gray')
        self.plan_name_label.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Add Course",
                  command=self._add_course_dialog).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Export to PDF",
                  command=self._export_plan_pdf).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Email to Advisor",
                  command=self._email_plan_to_advisor).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Email Report to Admin",
                  command=self._email_report_to_admin).pack(side=tk.RIGHT, padx=5)
        ttk.Button(control_frame, text="Save Changes",
                  command=self._save_plan_changes).pack(side=tk.RIGHT, padx=5)

        # Main planner area with scrollbar
        planner_frame = ttk.Frame(tab)
        planner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Canvas for scrolling
        canvas = tk.Canvas(planner_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(planner_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.planner_content = ttk.Frame(canvas)

        self.planner_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=self.planner_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # 8.117.98: bind the inner frame's width to the canvas so the
        # empty-state placeholder and semester blocks actually fill the
        # visible area instead of collapsing to their natural width.
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_window, width=e.width)
        )

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._display_planner_content()

    def _display_planner_content(self):
        """Display semester planner content."""
        # Clear existing content
        for widget in self.planner_content.winfo_children():
            widget.destroy()

        if not self.current_plan_id or not self.current_plan_data:
            # 8.117.98: actionable empty state. Pre-fix this was a
            # single grey label "No plan loaded. Create or load a plan
            # to begin." parented to a tiny zero-width frame, so the
            # tab looked empty and the user had no way to create a
            # plan without navigating to the Dashboard tab.
            empty = ttk.Frame(self.planner_content, padding=40)
            empty.pack(fill=tk.BOTH, expand=True)
            ttk.Label(empty, text="No plan loaded",
                      font=('Arial', 16, 'bold')).pack(pady=(20, 4))
            ttk.Label(empty,
                      text="Create a new semester plan or pick an existing one below.",
                      font=('Arial', 11), foreground='#555').pack(pady=(0, 20))

            # Inline Create / Auto-Generate buttons.
            btns = ttk.Frame(empty)
            btns.pack(pady=10)
            ttk.Button(btns, text="Create New Plan",
                       command=self._create_new_plan).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text="Auto-Generate Plan",
                       command=self._auto_generate_plan).pack(side=tk.LEFT, padx=5)

            # Existing plans list — double-click to load.
            try:
                existing_plans = self._student_plans()
            except Exception:
                existing_plans = []

            if existing_plans:
                box = ttk.LabelFrame(empty, text="Existing plans (double-click to load)",
                                     padding=10)
                box.pack(fill=tk.X, pady=(20, 0))
                lb = tk.Listbox(box, height=min(8, len(existing_plans)),
                                font=('Arial', 10))
                lb.pack(fill=tk.X)
                self._empty_state_plans = list(existing_plans)
                for p in existing_plans:
                    lb.insert(tk.END,
                              f"#{p['plan_id']} — {p['plan_name']} "
                              f"({p.get('status', 'Active')}) — "
                              f"{p.get('total_semesters', '?')} semesters")

                def _load_picked(_e=None):
                    sel = lb.curselection()
                    if not sel:
                        return
                    plan = self._empty_state_plans[sel[0]]
                    self.current_plan_id = plan['plan_id']
                    self.current_plan_data = self.planning_service.get_semester_plan(
                        self.current_plan_id, conn=self._read_conn())
                    if self.current_plan_data:
                        try:
                            self.plan_name_label.config(
                                text=plan['plan_name'], foreground='#1a73e8')
                        except Exception:
                            pass
                        self._display_planner_content()
                lb.bind('<Double-Button-1>', _load_picked)
            return

        plan = self.current_plan_data['plan']
        semesters = self.current_plan_data['semesters']

        # A freshly created plan has no planned courses yet, so the semester
        # loop below would render nothing and the tab would look blank. Show
        # the plan header plus a prompt to start adding courses.
        if not semesters:
            empty = ttk.Frame(self.planner_content, padding=40)
            empty.pack(fill=tk.BOTH, expand=True)
            ttk.Label(empty, text=plan.get('plan_name', 'Plan'),
                      font=('Arial', 16, 'bold')).pack(pady=(20, 4))
            ttk.Label(empty,
                      text="This plan has no courses yet. Add your first course to get started.",
                      font=('Arial', 11), foreground='#555').pack(pady=(0, 20))
            ttk.Button(empty, text="Add Course",
                       command=self._add_course_dialog).pack(pady=10)
            return

        # Display semester blocks
        for semester_num in sorted(semesters.keys()):
            courses = semesters[semester_num]
            total_credits = sum(c['credits'] for c in courses)

            # Semester frame
            semester_frame = ttk.LabelFrame(
                self.planner_content,
                text=f"Semester {semester_num}: {courses[0]['semester_name'] if courses else 'N/A'} - {total_credits} Credits",
                padding=10
            )
            semester_frame.pack(fill=tk.X, padx=10, pady=10)

            if total_credits > plan['credits_per_semester'] + 3:
                ttk.Label(semester_frame, text="⚠ Credit Overload",
                         style='Conflict.TLabel').pack(anchor=tk.W)

            # Course list
            for course in courses:
                course_frame = ttk.Frame(semester_frame, relief=tk.RIDGE, borderwidth=1, padding=5)
                course_frame.pack(fill=tk.X, pady=2)

                # Course info
                info_text = f"{course['course_id']}: {course['course_name']} ({course['credits']} cr)"
                if course['is_locked']:
                    info_text += " [LOCKED]"

                ttk.Label(course_frame, text=info_text, font=('Arial', 10)).pack(side=tk.LEFT)

                # Action buttons
                btn_frame = ttk.Frame(course_frame)
                btn_frame.pack(side=tk.RIGHT)

                ttk.Button(btn_frame, text="Move", width=8,
                          command=lambda c=course: self._move_course_dialog(c)).pack(side=tk.LEFT, padx=2)
                ttk.Button(btn_frame, text="Remove", width=8,
                          command=lambda c=course: self._remove_course(c)).pack(side=tk.LEFT, padx=2)

                if course['notes']:
                    ttk.Label(course_frame, text=f"Note: {course['notes']}",
                             font=('Arial', 9), foreground='blue').pack(anchor=tk.W)

    def _refresh_plans_list(self):
        """Refresh the plans list."""
        try:
            self.plans_listbox.delete(0, tk.END)
            # Plans changed (or first load) — refetch and refresh the cache.
            plans = self._student_plans(force=True)

            for plan in plans:
                display_text = f"{plan['plan_name']} - {plan['status']} ({plan['start_semester']})"
                self.plans_listbox.insert(tk.END, display_text)
                # Plan ID is retrieved by index when loading (see _load_selected_plan)

            self.status_bar.config(text=f"Loaded {len(plans)} plan(s)")
        except Exception:
            import traceback
            traceback.print_exc()
            raise

    def _on_plan_double_click(self, event):
        """Handle double-click on plan."""
        self._load_selected_plan()

    def _load_selected_plan(self):
        """Load the selected plan."""
        selection = self.plans_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a plan to load.")
            return

        index = selection[0]
        # Reuse the same cached list the listbox was populated from so the
        # index lines up (and no extra connection is opened).
        plans = self._student_plans()

        if index >= len(plans):
            return

        plan = plans[index]
        self.current_plan_id = plan['plan_id']
        self.current_plan_data = self.planning_service.get_semester_plan(
            self.current_plan_id, conn=self._read_conn())

        if self.current_plan_data:
            self.plan_name_label.config(text=plan['plan_name'], foreground='black')
            self._display_planner_content()
            self.notebook.select(1)  # Switch to planner tab
            self.status_bar.config(text=f"Loaded plan: {plan['plan_name']}")
        else:
            messagebox.showerror("Error", "Failed to load plan data.")

    def _activate_plan(self, plan_id, plan_name=None):
        """Make a plan the current one and render it on the Planner tab.

        Shared by the create / auto-generate flows so a freshly made plan is
        immediately visible instead of leaving the user on the empty state.
        """
        self.current_plan_id = plan_id
        self.current_plan_data = self.planning_service.get_semester_plan(
            plan_id, conn=self._read_conn())
        if not self.current_plan_data:
            return

        if plan_name is None:
            plan_name = self.current_plan_data['plan'].get('plan_name', 'Plan')
        try:
            self.plan_name_label.config(text=plan_name, foreground='black')
        except Exception:
            pass

        self._display_planner_content()
        try:
            self.notebook.select(1)  # Switch to planner tab
        except Exception:
            pass
        try:
            self.status_bar.config(text=f"Loaded plan: {plan_name}")
        except Exception:
            pass

    def _create_new_plan(self):
        """Create a new course plan."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Create New Course Plan")
        dialog.geometry("500x400")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text="Create New Course Plan", font=('Arial', 14, 'bold')).pack(pady=10)

        # Form fields
        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Plan name
        ttk.Label(form_frame, text="Plan Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(form_frame, width=30)
        name_entry.grid(row=0, column=1, pady=5, sticky=tk.EW)

        # Get student's major
        with get_connection() as conn:
            student = conn.execute("""
                SELECT course FROM students WHERE student_id = ?
            """, (self.student_id,)).fetchone()

        default_program = student['course'] if student and student['course'] else ""

        # Program code
        ttk.Label(form_frame, text="Program/Major:").grid(row=1, column=0, sticky=tk.W, pady=5)
        program_entry = ttk.Entry(form_frame, width=30)
        program_entry.insert(0, default_program)
        program_entry.grid(row=1, column=1, pady=5, sticky=tk.EW)

        # Start semester
        ttk.Label(form_frame, text="Start Semester:").grid(row=2, column=0, sticky=tk.W, pady=5)
        semester_entry = ttk.Entry(form_frame, width=30)
        semester_entry.insert(0, "Fall 2026")
        semester_entry.grid(row=2, column=1, pady=5, sticky=tk.EW)

        # Total semesters
        ttk.Label(form_frame, text="Total Semesters:").grid(row=3, column=0, sticky=tk.W, pady=5)
        total_sem_entry = ttk.Entry(form_frame, width=30)
        total_sem_entry.insert(0, "8")
        total_sem_entry.grid(row=3, column=1, pady=5, sticky=tk.EW)

        # Credits per semester
        ttk.Label(form_frame, text="Credits/Semester:").grid(row=4, column=0, sticky=tk.W, pady=5)
        credits_entry = ttk.Entry(form_frame, width=30)
        credits_entry.insert(0, "15")
        credits_entry.grid(row=4, column=1, pady=5, sticky=tk.EW)

        # Include summer
        summer_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Include Summer Sessions", variable=summer_var).grid(
            row=5, column=0, columnspan=2, sticky=tk.W, pady=5)

        form_frame.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        def create_plan():
            plan_name = name_entry.get().strip()
            if not plan_name:
                messagebox.showerror("Error", "Plan name is required.")
                return

            # Validate integer fields
            try:
                total_semesters = int(total_sem_entry.get())
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Total semesters must be a number.")
                return
            try:
                credits_per_sem = int(credits_entry.get())
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Credits per semester must be a number.")
                return

            try:
                plan_id = self.planning_service.create_semester_plan(
                    student_id=self.student_id,
                    plan_name=plan_name,
                    program_code=program_entry.get().strip() or None,
                    start_semester=semester_entry.get().strip(),
                    total_semesters=total_semesters,
                    credits_per_semester=credits_per_sem,
                    include_summer=summer_var.get()
                )

                messagebox.showinfo("Success", f"Plan created successfully! (ID: {plan_id})")
                dialog.destroy()
                self._refresh_plans_list()
                # Make the new plan the active one and show it, otherwise the
                # user is left staring at whichever tab they created it from
                # (the "No plan loaded" empty state on the Planner tab) and it
                # looks like nothing happened.
                self._activate_plan(plan_id, plan_name)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to create plan: {e}")

        ttk.Button(button_frame, text="Create", command=create_plan).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _auto_generate_plan(self):
        """Auto-generate a course plan."""
        # Get student's major
        with get_connection() as conn:
            student = conn.execute("""
                SELECT course FROM students WHERE student_id = ?
            """, (self.student_id,)).fetchone()

        if not student or not student['course']:
            messagebox.showerror("Error", "No major found. Please set your major first.")
            return

        program_code = student['course']

        result = messagebox.askyesno(
            "Auto-Generate Plan",
            f"Generate an optimized course plan for {program_code}?\n\n"
            "This will:\n"
            "• Analyze your completed courses\n"
            "• Identify remaining requirements\n"
            "• Order courses by prerequisites\n"
            "• Distribute across semesters"
        )

        if not result:
            return

        try:
            plan_id = self.planning_service.generate_auto_plan(
                student_id=self.student_id,
                program_code=program_code,
                start_semester="Fall 2026"
            )

            messagebox.showinfo("Success", f"Auto-plan generated! (ID: {plan_id})\n\n"
                                          "Review and customize as needed.")
            self._refresh_plans_list()
            self._activate_plan(plan_id)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate plan: {e}")

    def _add_course_dialog(self):
        """Show dialog to add course to plan."""
        if not self.current_plan_id:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        dialog = tk.Toplevel(self.window)
        dialog.title("Add Course to Plan")
        dialog.geometry("500x400")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text="Add Course to Plan", font=('Arial', 14, 'bold')).pack(pady=10)

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Get available modules for this student's course
        available_modules = []
        try:
            with get_connection() as conn:
                # Get student's course/program
                student_info = conn.execute("""
                    SELECT course FROM students WHERE student_id = ?
                """, (self.student_id,)).fetchone()

                # Get all modules (we'll show all since course-to-module mapping may vary)
                modules = conn.execute("""
                    SELECT module_code, module_name FROM modules
                    WHERE module_code LIKE 'CIS%'
                    ORDER BY module_code
                """).fetchall()

                available_modules = [f"{m['module_code']} - {m['module_name']}" for m in modules]
        except Exception:
            pass

        # Module selection dropdown
        ttk.Label(form_frame, text="Select Module:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_combo = ttk.Combobox(form_frame, values=available_modules, width=50, state='readonly')
        course_combo.grid(row=0, column=1, columnspan=2, pady=5, sticky=tk.EW)
        if available_modules:
            course_combo.current(0)

        # Semester number — defaults to 1 so a blank submission doesn't
        # raise "invalid literal for int() with base 10: ''" (8.117.99).
        ttk.Label(form_frame, text="Semester Number:").grid(row=1, column=0, sticky=tk.W, pady=5)
        sem_num_entry = ttk.Entry(form_frame, width=30)
        sem_num_entry.insert(0, "1")
        sem_num_entry.grid(row=1, column=1, pady=5, sticky=tk.EW)

        # Semester name
        ttk.Label(form_frame, text="Semester Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        sem_name_entry = ttk.Entry(form_frame, width=30)
        sem_name_entry.insert(0, "Fall 2026")
        sem_name_entry.grid(row=2, column=1, pady=5, sticky=tk.EW)

        # Priority
        ttk.Label(form_frame, text="Priority (0-10):").grid(row=3, column=0, sticky=tk.W, pady=5)
        priority_entry = ttk.Entry(form_frame, width=30)
        priority_entry.insert(0, "0")
        priority_entry.grid(row=3, column=1, pady=5, sticky=tk.EW)

        # Lock course
        lock_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(form_frame, text="Lock this course in semester", variable=lock_var).grid(
            row=4, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Notes
        ttk.Label(form_frame, text="Notes:").grid(row=5, column=0, sticky=tk.W, pady=5)
        notes_entry = ttk.Entry(form_frame, width=30)
        notes_entry.grid(row=5, column=1, pady=5, sticky=tk.EW)

        form_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        def add_course():
            # Extract module code from combobox selection (format: "CIS0001 - module name")
            selection = course_combo.get()
            if not selection:
                messagebox.showerror("Error", "Please select a module.")
                return

            course_id = selection.split(' - ')[0].strip().upper()

            # Verify course exists - check both courses and modules tables
            with get_connection() as conn:
                course = conn.execute("""
                    SELECT code as course_code, name as course_name, credits FROM courses WHERE code = ?
                """, (course_id,)).fetchone()

                if not course:
                    # Try modules table
                    course = conn.execute("""
                        SELECT module_code as course_code, module_name as course_name, credits FROM modules WHERE module_code = ?
                    """, (course_id,)).fetchone()

            if not course:
                messagebox.showerror("Error", f"Course/Module {course_id} not found in database.\n\nTry codes like: CIS0001, CIS0002, CIS1001, etc.")
                return

            # Check eligibility
            eligibility = self.planning_service.check_prerequisite_eligibility(
                self.student_id, course_id
            )

            if not eligibility['eligible']:
                result = messagebox.askyesnocancel(
                    "Prerequisites Not Met",
                    f"You haven't met all prerequisites for {course_id}.\n\n"
                    f"Missing: {len(eligibility['missing_prerequisites'])} prerequisite(s)\n\n"
                    "Add anyway?"
                )
                if not result:
                    return

            # Validate integer fields
            try:
                semester_number = int(sem_num_entry.get())
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Semester number must be a number.")
                return
            try:
                priority = int(priority_entry.get()) if priority_entry.get().strip() else 0
            except (ValueError, TypeError):
                messagebox.showerror("Error", "Priority must be a number.")
                return

            try:
                self.planning_service.add_course_to_plan(
                    plan_id=self.current_plan_id,
                    course_id=course_id,
                    semester_number=semester_number,
                    semester_name=sem_name_entry.get().strip(),
                    is_locked=lock_var.get(),
                    priority=priority,
                    notes=notes_entry.get().strip() or None
                )

                messagebox.showinfo("Success", f"Course {course_id} added to plan!")

                # Reload plan
                self.current_plan_data = self.planning_service.get_semester_plan(self.current_plan_id)
                self._display_planner_content()
                dialog.destroy()

            except Exception as e:
                # Translate the schema-level UNIQUE constraint error into
                # something a user can act on (8.117.99). The schema has
                # ``UNIQUE(plan_id, course_id)`` so each module can only
                # appear once in a plan; on retry the friendlier text
                # tells the user to use Move/Remove instead.
                msg = str(e)
                if 'UNIQUE constraint failed' in msg \
                        and 'plan_id' in msg and 'course_id' in msg:
                    messagebox.showerror(
                        "Already in plan",
                        f"{course_id} is already in this plan. Each module "
                        "can only appear once — use the Move or Remove "
                        "controls on the existing entry instead.")
                else:
                    messagebox.showerror("Error", f"Failed to add course: {e}")

        ttk.Button(button_frame, text="Add", command=add_course).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _move_course_dialog(self, course: Dict):
        """Show dialog to move course to different semester."""
        dialog = tk.Toplevel(self.window)
        dialog.title("Move Course")
        dialog.geometry("400x250")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Move {course['course_id']}",
                 font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Current: Semester {course['semester_number']}").pack()

        form_frame = ttk.Frame(dialog, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text="New Semester Number:").grid(row=0, column=0, sticky=tk.W, pady=5)
        sem_num_entry = ttk.Entry(form_frame, width=20)
        sem_num_entry.grid(row=0, column=1, pady=5)

        ttk.Label(form_frame, text="New Semester Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        sem_name_entry = ttk.Entry(form_frame, width=20)
        sem_name_entry.grid(row=1, column=1, pady=5)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        def move_course():
            try:
                new_sem_num = sem_num_entry.get().strip()
                if not new_sem_num:
                    messagebox.showerror("Error", "Semester number is required.")
                    return
                try:
                    new_sem_num = int(new_sem_num)
                except (ValueError, TypeError):
                    messagebox.showerror("Error", "Semester number must be a number.")
                    return

                with transaction() as conn:
                    conn.execute("""
                        UPDATE planned_courses
                        SET semester_number = ?, semester_name = ?
                        WHERE planned_course_id = ?
                    """, (new_sem_num, sem_name_entry.get().strip(),
                         course['planned_course_id']))

                messagebox.showinfo("Success", f"Course moved to Semester {sem_num_entry.get()}")
                self.current_plan_data = self.planning_service.get_semester_plan(self.current_plan_id)
                self._display_planner_content()
                dialog.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to move course: {e}")

        ttk.Button(button_frame, text="Move", command=move_course).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def _remove_course(self, course: Dict):
        """Remove course from plan."""
        result = messagebox.askyesno(
            "Confirm Removal",
            f"Remove {course['course_id']} from plan?"
        )

        if not result:
            return

        try:
            with transaction() as conn:
                conn.execute("""
                    DELETE FROM planned_courses
                    WHERE planned_course_id = ?
                """, (course['planned_course_id'],))

            messagebox.showinfo("Success", f"Course {course['course_id']} removed from plan")
            self.current_plan_data = self.planning_service.get_semester_plan(self.current_plan_id)
            self._display_planner_content()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to remove course: {e}")

    def _save_plan_changes(self):
        """Save changes to the plan."""
        if not self.current_plan_id:
            messagebox.showwarning("Warning", "No plan loaded.")
            return

        messagebox.showinfo("Info", "Changes are saved automatically.")
        self.status_bar.config(text="Plan saved")

    def _duplicate_plan(self):
        """Duplicate the selected plan with a new name."""
        selection = self.plans_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a plan to duplicate.")
            return

        index = selection[0]
        plans = self._student_plans()

        if index >= len(plans):
            return

        original_plan = plans[index]

        # Dialog to get new plan name
        new_name = tk.simpledialog.askstring(
            "Duplicate Plan",
            f"Enter name for duplicate of '{original_plan['plan_name']}':",
            initialvalue=f"{original_plan['plan_name']} (Copy)"
        )

        if not new_name:
            return

        try:
            # Get original plan data
            original_data = self.planning_service.get_semester_plan(
                original_plan['plan_id'], conn=self._read_conn())

            if not original_data:
                messagebox.showerror("Error", "Failed to load original plan data.")
                return

            # Create new plan with same settings
            with transaction() as conn:
                # Create new plan
                cursor = conn.execute("""
                    INSERT INTO semester_plans (
                        student_id, plan_name, program_code, start_semester,
                        total_semesters, credits_per_semester, include_summer, status
                    )
                    SELECT student_id, ?, program_code, start_semester,
                           total_semesters, credits_per_semester, include_summer, 'Draft'
                    FROM semester_plans
                    WHERE plan_id = ?
                """, (new_name, original_plan['plan_id']))

                new_plan_id = cursor.lastrowid

                # Copy all planned courses
                conn.execute("""
                    INSERT INTO planned_courses (
                        plan_id, course_id, semester_number, semester_name,
                        is_locked, priority, notes
                    )
                    SELECT ?, course_id, semester_number, semester_name,
                           is_locked, priority, notes
                    FROM planned_courses
                    WHERE plan_id = ?
                """, (new_plan_id, original_plan['plan_id']))

            messagebox.showinfo("Success", f"Plan duplicated successfully!\nNew plan: {new_name}")
            self._refresh_plans_list()

            log_activity('create', 'semester_plan', user_id=self.student_id,
                        details={'action': 'duplicate_plan', 'new_plan_id': new_plan_id,
                                'original_plan_id': original_plan['plan_id']})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate plan: {e}")

    def _delete_plan(self):
        """Delete or archive the selected plan."""
        selection = self.plans_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a plan to delete.")
            return

        index = selection[0]
        plans = self._student_plans()

        if index >= len(plans):
            return

        plan = plans[index]

        # Confirm deletion
        result = messagebox.askyesnocancel(
            "Delete Plan",
            f"Delete plan '{plan['plan_name']}'?\n\n"
            "Yes = Archive (keep data, mark inactive)\n"
            "No = Permanently delete\n"
            "Cancel = Keep plan"
        )

        if result is None:  # Cancel
            return

        try:
            with transaction() as conn:
                if result:  # Archive
                    conn.execute("""
                        UPDATE semester_plans
                        SET status = 'Archived'
                        WHERE plan_id = ?
                    """, (plan['plan_id'],))
                    messagebox.showinfo("Success", f"Plan '{plan['plan_name']}' archived successfully!")
                    action = 'archive_plan'
                else:  # Delete
                    # Delete all planned courses first
                    conn.execute("""
                        DELETE FROM planned_courses
                        WHERE plan_id = ?
                    """, (plan['plan_id'],))

                    # Delete plan
                    conn.execute("""
                        DELETE FROM semester_plans
                        WHERE plan_id = ?
                    """, (plan['plan_id'],))
                    messagebox.showinfo("Success", f"Plan '{plan['plan_name']}' deleted permanently!")
                    action = 'delete_plan'

            # Clear current plan if deleted
            if self.current_plan_id == plan['plan_id']:
                self.current_plan_id = None
                self.current_plan_data = None
                self.plan_name_label.config(text="No plan loaded", foreground='gray')
                self._display_planner_content()

            self._refresh_plans_list()

            log_activity('delete', 'semester_plan', user_id=self.student_id,
                        details={'action': action, 'plan_id': plan['plan_id'],
                                'plan_name': plan['plan_name']})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete/archive plan: {e}")

