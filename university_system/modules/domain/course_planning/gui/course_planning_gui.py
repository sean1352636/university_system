"""
Course Planning Assistant GUI

Main GUI interface for course planning with:
- Semester planner with course scheduling
- Prerequisite visualization tree
- Conflict warnings and alerts
- Course search and recommendations
- Plan export functionality
"""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from typing import Optional, Dict, List

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.auth import UserAuth
from university_system.modules.domain.course_planning.services.planning_service import PlanningService
from university_system.modules.shared.utils.activity_logger import log_activity


class CoursePlanningGUI:
    """Main GUI for Course Planning Assistant."""

    def __init__(self, root, auth: Optional[UserAuth] = None, parent_notebook: Optional[ttk.Notebook] = None):
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth and auth.current_user else None
        self.planning_service = PlanningService()
        self.window = None
        self.parent_notebook = parent_notebook

        if not self.current_user:
            messagebox.showerror("Error", "Login required to access Course Planning")
            return

        self.user_role = self.current_user.get('role', 'student').lower()

        # For admin/staff, let them select a student
        if self.user_role in ['admin', 'staff', 'instructor']:
            try:
                self.student_id = self._select_student_for_planning()
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.student_id = None

            if not self.student_id:
                # Try to get first available student as fallback
                try:
                    with get_connection() as conn:
                        first_student = conn.execute("SELECT student_id FROM students LIMIT 1").fetchone()
                        if first_student:
                            self.student_id = first_student['student_id']
                            messagebox.showwarning("No Student Selected",
                                                  f"Using first available student: {self.student_id}\n\n"
                                                  "You can switch students using the 'Switch Student' button.")
                        else:
                            messagebox.showerror("Error", "No students found in database")
                            return
                except Exception as e2:
                    messagebox.showerror("Error", "Failed to load student data")
                    return

            self.viewing_as_admin = True
        else:
            self.student_id = self.current_user.get('id') or self.current_user.get('username')
            self.viewing_as_admin = False

        # Cache for current plan
        self.current_plan_id = None
        self.current_plan_data = None

        self.create_main_window()

    def create_main_window(self):
        """Create the main Course Planning window."""
        if self.parent_notebook:
            # Embedded mode - add to parent notebook
            self.window = ttk.Frame(self.parent_notebook)
            self.parent_notebook.add(self.window, text="Course Planning")
        else:
            # Standalone mode - create new window
            self.window = tk.Toplevel(self.root)
            self.window.title("Course Planning Assistant")
            self.window.geometry("1400x900")
            self.window.minsize(1200, 800)

        # Configure styles
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 16, 'bold'))
        style.configure('Subheader.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Conflict.TLabel', foreground='red', font=('Arial', 10, 'bold'))
        style.configure('Success.TLabel', foreground='green', font=('Arial', 10, 'bold'))

        # Header frame
        if not self.parent_notebook:
            header_frame = ttk.Frame(self.window)
            header_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(header_frame, text="Course Planning Assistant",
                     style='Header.TLabel').pack(side=tk.LEFT)

            # Show logged-in user and which student is being viewed
            if self.viewing_as_admin:
                # Get student name
                try:
                    with get_connection() as conn:
                        student = conn.execute("""
                            SELECT first_name, last_name FROM students WHERE student_id = ?
                        """, (self.student_id,)).fetchone()

                    student_name = f"{student['first_name']} {student['last_name']}" if student else self.student_id
                except Exception:
                    student_name = self.student_id

                user_info = f"Admin: {self.current_user.get('username', 'Unknown')} | Viewing: {student_name} ({self.student_id})"
            else:
                user_info = f"Student: {self.current_user.get('username', 'Unknown')}"

            ttk.Label(header_frame, text=user_info, style='Subheader.TLabel').pack(side=tk.RIGHT)

        # Status bar (create early so methods can update it)
        self.status_bar = ttk.Label(self.window, text="Ready - Course Planning Assistant v1.0",
                                     relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Bottom frame with buttons
        if not self.parent_notebook:
            bottom_frame = ttk.Frame(self.window)
            bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
            ttk.Button(bottom_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

        # Main notebook with tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        self._create_dashboard_tab()
        self._create_planner_tab()
        self._create_prerequisites_tab()
        self._create_recommendations_tab()
        self._create_conflicts_tab()
        self._create_tools_tab()

        log_activity('view', 'course_planning_gui', user_id=self.student_id,
                    details={'action': 'opened_gui'})

    def _select_student_for_planning(self):
        """Show dialog for admin to select a student."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Student for Course Planning")
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()

        selected_student_id = None

        ttk.Label(dialog, text="Select Student for Course Planning",
                 font=('Arial', 14, 'bold')).pack(pady=10)

        ttk.Label(dialog, text="Search by Student ID or Name:",
                 font=('Arial', 11)).pack(pady=5)

        # Search frame
        search_frame = ttk.Frame(dialog)
        search_frame.pack(fill=tk.X, padx=20, pady=10)

        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Students listbox
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        students_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                      font=('Arial', 10))
        students_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=students_listbox.yview)

        # Load students
        def load_students(search_term=""):
            students_listbox.delete(0, tk.END)

            try:
                with get_connection() as conn:
                    if search_term:
                        students = conn.execute("""
                            SELECT student_id, first_name, last_name, course
                            FROM students
                            WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                            ORDER BY last_name, first_name
                            LIMIT 100
                        """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')).fetchall()
                    else:
                        students = conn.execute("""
                            SELECT student_id, first_name, last_name, course
                            FROM students
                            ORDER BY last_name, first_name
                            LIMIT 100
                        """).fetchall()

                for student in students:
                    display = f"{student['student_id']} - {student['first_name']} {student['last_name']}"
                    if student['course']:
                        display += f" ({student['course']})"
                    students_listbox.insert(tk.END, display)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load students: {e}")

        # Search button
        ttk.Button(search_frame, text="Search",
                  command=lambda: load_students(search_var.get())).pack(side=tk.LEFT, padx=5)

        ttk.Button(search_frame, text="Show All",
                  command=lambda: load_students()).pack(side=tk.LEFT, padx=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        def select_student():
            nonlocal selected_student_id
            selection = students_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a student")
                return

            selected_text = students_listbox.get(selection[0])
            selected_student_id = selected_text.split(' - ')[0]
            dialog.destroy()

        ttk.Button(button_frame, text="Select Student",
                  command=select_student).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Double-click to select
        students_listbox.bind('<Double-Button-1>', lambda e: select_student())

        # Load initial students
        load_students()

        # Wait for dialog to close
        dialog.wait_window()

        return selected_student_id

    def _switch_student(self):
        """Allow admin to switch to viewing a different student."""
        new_student_id = self._select_student_for_planning()

        if new_student_id and new_student_id != self.student_id:
            self.student_id = new_student_id

            # Clear current plan
            self.current_plan_id = None
            self.current_plan_data = None

            # Update header to show new student
            if hasattr(self, 'window'):
                # Recreate the window to update all student-specific info
                messagebox.showinfo("Student Changed",
                                   f"Now viewing plans for student: {new_student_id}\n\n"
                                   "The view has been refreshed.")

                # Refresh all data
                self._refresh_plans_list()
                if hasattr(self, 'planner_content'):
                    self._display_planner_content()

            log_activity('view', 'course_planning_switch_student',
                        details={'admin_user': self.current_user.get('username'),
                                'viewing_student': new_student_id})

    def _create_dashboard_tab(self):
        """Create the dashboard overview tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Dashboard")

        # Welcome section
        welcome_frame = ttk.Frame(tab)
        welcome_frame.pack(fill=tk.X, padx=20, pady=20)

        ttk.Label(welcome_frame, text="Course Planning Dashboard",
                 font=('Arial', 18, 'bold')).pack(anchor=tk.W)
        ttk.Label(welcome_frame, text="Plan your academic journey with intelligent course scheduling",
                 font=('Arial', 11)).pack(anchor=tk.W, pady=5)

        # Quick stats
        stats_frame = ttk.LabelFrame(tab, text="Your Planning Overview", padding=15)
        stats_frame.pack(fill=tk.X, padx=20, pady=10)

        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)

        # Get stats
        try:
            plans = self.planning_service.get_student_plans(self.student_id)
            active_plans = [p for p in plans if p['status'] == 'Active']
        except Exception:
            plans = []
            active_plans = []

        try:
            recommendations_count = len(self.planning_service.get_student_recommendations(self.student_id))
        except Exception:
            recommendations_count = 0

        self._create_stat_card(stats_grid, "Total Plans", len(plans), 0, 0)
        self._create_stat_card(stats_grid, "Active Plans", len(active_plans), 0, 1)
        self._create_stat_card(stats_grid, "Recommendations", recommendations_count, 0, 2)

        # Recent plans
        recent_frame = ttk.LabelFrame(tab, text="Recent Course Plans", padding=15)
        recent_frame.pack(fill=tk.X, padx=20, pady=10)

        # BUTTONS FIRST - at the TOP so they're always visible
        button_frame = ttk.Frame(recent_frame, relief=tk.RAISED, borderwidth=2)
        button_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10), ipady=5)
        ttk.Button(button_frame, text="Create New Plan",
                  command=self._create_new_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Load Plan",
                  command=self._load_selected_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Auto-Generate Plan",
                  command=self._auto_generate_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Duplicate Plan",
                  command=self._duplicate_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Delete Plan",
                  command=self._delete_plan).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(button_frame, text="Refresh",
                  command=self._refresh_plans_list).pack(side=tk.LEFT, padx=5, pady=5)

        # Admin-only button to switch students
        if self.viewing_as_admin:
            ttk.Button(button_frame, text="Switch Student",
                      command=self._switch_student).pack(side=tk.RIGHT, padx=5, pady=5)

        # Force geometry update to ensure buttons are visible
        button_frame.update_idletasks()
        recent_frame.update_idletasks()

        # Plans listbox with scrollbar - AFTER buttons so buttons stay on top
        list_frame = ttk.Frame(recent_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.plans_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                        font=('Arial', 10), height=6)
        self.plans_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.plans_listbox.yview)

        self.plans_listbox.bind('<Double-Button-1>', self._on_plan_double_click)

        try:
            self._refresh_plans_list()
        except Exception as e:
            import traceback
            traceback.print_exc()

    def _create_stat_card(self, parent, title, value, row, col):
        """Create a statistics card."""
        card = ttk.Frame(parent, relief=tk.RIDGE, borderwidth=1, padding=15)
        card.grid(row=row, column=col, padx=10, pady=5, sticky='nsew')
        parent.columnconfigure(col, weight=1)

        ttk.Label(card, text=title, font=('Arial', 10)).pack()
        ttk.Label(card, text=str(value), font=('Arial', 18, 'bold')).pack(pady=5)

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
        ttk.Button(control_frame, text="Save Changes",
                  command=self._save_plan_changes).pack(side=tk.RIGHT, padx=5)

        # Main planner area with scrollbar
        planner_frame = ttk.Frame(tab)
        planner_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Canvas for scrolling
        canvas = tk.Canvas(planner_frame)
        scrollbar = ttk.Scrollbar(planner_frame, orient=tk.VERTICAL, command=canvas.yview)
        self.planner_content = ttk.Frame(canvas)

        self.planner_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.planner_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._display_planner_content()

    def _display_planner_content(self):
        """Display semester planner content."""
        # Clear existing content
        for widget in self.planner_content.winfo_children():
            widget.destroy()

        if not self.current_plan_id or not self.current_plan_data:
            ttk.Label(self.planner_content, text="No plan loaded. Create or load a plan to begin.",
                     font=('Arial', 12), foreground='gray').pack(pady=50)
            return

        plan = self.current_plan_data['plan']
        semesters = self.current_plan_data['semesters']

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

    def _create_prerequisites_tab(self):
        """Create the prerequisites visualization tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Prerequisites")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Course ID:", font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        self.prereq_course_entry = ttk.Entry(control_frame, width=15, font=('Arial', 11))
        self.prereq_course_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Visualize Prerequisites",
                  command=self._visualize_prerequisites).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Check Eligibility",
                  command=self._check_eligibility).pack(side=tk.LEFT, padx=5)

        # Display area
        display_frame = ttk.LabelFrame(tab, text="Prerequisite Visualization", padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.prereq_text = scrolledtext.ScrolledText(display_frame, wrap=tk.WORD,
                                                     font=('Courier', 10), height=30)
        self.prereq_text.pack(fill=tk.BOTH, expand=True)

    def _create_recommendations_tab(self):
        """Create the course recommendations tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Recommendations")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(control_frame, text="Target Semester:", font=('Arial', 11)).pack(side=tk.LEFT, padx=5)
        self.rec_semester_entry = ttk.Entry(control_frame, width=15, font=('Arial', 11))
        self.rec_semester_entry.insert(0, "Fall 2026")
        self.rec_semester_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Get Recommendations",
                  command=self._get_recommendations).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self._get_recommendations).pack(side=tk.LEFT, padx=5)

        # Recommendations display
        rec_frame = ttk.LabelFrame(tab, text="Recommended Courses", padding=10)
        rec_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create treeview for recommendations
        columns = ('Course ID', 'Course Name', 'Credits', 'Score', 'Reason')
        self.rec_tree = ttk.Treeview(rec_frame, columns=columns, show='tree headings', height=20)

        for col in columns:
            self.rec_tree.heading(col, text=col)
            self.rec_tree.column(col, width=150)

        self.rec_tree.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        rec_scrollbar = ttk.Scrollbar(rec_frame, orient=tk.VERTICAL, command=self.rec_tree.yview)
        rec_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.rec_tree.configure(yscrollcommand=rec_scrollbar.set)

        # Button to add to plan
        ttk.Button(rec_frame, text="Add Selected to Plan",
                  command=self._add_recommended_course).pack(pady=10)

    def _create_conflicts_tab(self):
        """Create the conflicts detection tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Conflicts")

        # Control panel
        control_frame = ttk.Frame(tab)
        control_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(control_frame, text="Detect Conflicts",
                  command=self._detect_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Refresh",
                  command=self._detect_conflicts).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Report",
                  command=self._export_conflicts_report).pack(side=tk.LEFT, padx=5)

        # Conflicts display
        conflicts_frame = ttk.LabelFrame(tab, text="Detected Conflicts", padding=10)
        conflicts_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create treeview for conflicts
        columns = ('Severity', 'Type', 'Semester', 'Description')
        self.conflicts_tree = ttk.Treeview(conflicts_frame, columns=columns, show='tree headings', height=20)

        self.conflicts_tree.heading('Severity', text='Severity')
        self.conflicts_tree.heading('Type', text='Type')
        self.conflicts_tree.heading('Semester', text='Semester')
        self.conflicts_tree.heading('Description', text='Description')

        self.conflicts_tree.column('Severity', width=100)
        self.conflicts_tree.column('Type', width=150)
        self.conflicts_tree.column('Semester', width=100)
        self.conflicts_tree.column('Description', width=500)

        self.conflicts_tree.pack(fill=tk.BOTH, expand=True)

        # Scrollbar
        conflicts_scrollbar = ttk.Scrollbar(conflicts_frame, orient=tk.VERTICAL, command=self.conflicts_tree.yview)
        conflicts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.conflicts_tree.configure(yscrollcommand=conflicts_scrollbar.set)

        # Details panel
        details_frame = ttk.LabelFrame(tab, text="Suggestions", padding=10)
        details_frame.pack(fill=tk.X, padx=10, pady=10)

        self.conflict_details_text = scrolledtext.ScrolledText(details_frame, wrap=tk.WORD,
                                                               font=('Arial', 10), height=6)
        self.conflict_details_text.pack(fill=tk.BOTH, expand=True)

        self.conflicts_tree.bind('<<TreeviewSelect>>', self._on_conflict_select)

    # ===== Event Handlers =====

    def _refresh_plans_list(self):
        """Refresh the plans list."""
        try:
            self.plans_listbox.delete(0, tk.END)
            plans = self.planning_service.get_student_plans(self.student_id)

            for plan in plans:
                display_text = f"{plan['plan_name']} - {plan['status']} ({plan['start_semester']})"
                self.plans_listbox.insert(tk.END, display_text)
                # Plan ID is retrieved by index when loading (see _load_selected_plan)

            self.status_bar.config(text=f"Loaded {len(plans)} plan(s)")
        except Exception as e:
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
        plans = self.planning_service.get_student_plans(self.student_id)

        if index >= len(plans):
            return

        plan = plans[index]
        self.current_plan_id = plan['plan_id']
        self.current_plan_data = self.planning_service.get_semester_plan(self.current_plan_id)

        if self.current_plan_data:
            self.plan_name_label.config(text=plan['plan_name'], foreground='black')
            self._display_planner_content()
            self.notebook.select(1)  # Switch to planner tab
            self.status_bar.config(text=f"Loaded plan: {plan['plan_name']}")
        else:
            messagebox.showerror("Error", "Failed to load plan data.")

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

            try:
                plan_id = self.planning_service.create_semester_plan(
                    student_id=self.student_id,
                    plan_name=plan_name,
                    program_code=program_entry.get().strip() or None,
                    start_semester=semester_entry.get().strip(),
                    total_semesters=int(total_sem_entry.get()),
                    credits_per_semester=int(credits_entry.get()),
                    include_summer=summer_var.get()
                )

                messagebox.showinfo("Success", f"Plan created successfully! (ID: {plan_id})")
                self._refresh_plans_list()
                dialog.destroy()

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
        except Exception as e:
            pass

        # Module selection dropdown
        ttk.Label(form_frame, text="Select Module:").grid(row=0, column=0, sticky=tk.W, pady=5)
        course_combo = ttk.Combobox(form_frame, values=available_modules, width=50, state='readonly')
        course_combo.grid(row=0, column=1, columnspan=2, pady=5, sticky=tk.EW)
        if available_modules:
            course_combo.current(0)

        # Semester number
        ttk.Label(form_frame, text="Semester Number:").grid(row=1, column=0, sticky=tk.W, pady=5)
        sem_num_entry = ttk.Entry(form_frame, width=30)
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

            try:
                self.planning_service.add_course_to_plan(
                    plan_id=self.current_plan_id,
                    course_id=course_id,
                    semester_number=int(sem_num_entry.get()),
                    semester_name=sem_name_entry.get().strip(),
                    is_locked=lock_var.get(),
                    priority=int(priority_entry.get()),
                    notes=notes_entry.get().strip() or None
                )

                messagebox.showinfo("Success", f"Course {course_id} added to plan!")

                # Reload plan
                self.current_plan_data = self.planning_service.get_semester_plan(self.current_plan_id)
                self._display_planner_content()
                dialog.destroy()

            except Exception as e:
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
                with transaction() as conn:
                    conn.execute("""
                        UPDATE planned_courses
                        SET semester_number = ?, semester_name = ?
                        WHERE planned_course_id = ?
                    """, (int(sem_num_entry.get()), sem_name_entry.get().strip(),
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

    def _visualize_prerequisites(self):
        """Visualize prerequisite chain."""
        course_id = self.prereq_course_entry.get().strip().upper()
        if not course_id:
            messagebox.showwarning("Warning", "Please enter a course ID.")
            return

        try:
            chain = self.planning_service.visualize_prerequisite_chain(course_id)
            tree = self.planning_service.build_prerequisite_tree(course_id)
            all_prereqs = self.planning_service.get_all_prerequisites(course_id)

            # Clear text
            self.prereq_text.delete(1.0, tk.END)

            # Display visualization
            self.prereq_text.insert(tk.END, f"=== Prerequisite Chain for {course_id} ===\n\n")
            self.prereq_text.insert(tk.END, f"Total Prerequisites: {len(all_prereqs)}\n")
            self.prereq_text.insert(tk.END, f"Prerequisite Depth: {tree.get('total_depth', 0)}\n\n")

            if len(chain) <= 1:
                self.prereq_text.insert(tk.END, "✓ No prerequisites required\n")
            else:
                self.prereq_text.insert(tk.END, "Prerequisite Levels (Foundation → Advanced):\n\n")
                for level, courses in enumerate(chain):
                    if level == len(chain) - 1:
                        self.prereq_text.insert(tk.END, f"Level {level} (Target):\n")
                    else:
                        self.prereq_text.insert(tk.END, f"Level {level}:\n")

                    for course in courses:
                        self.prereq_text.insert(tk.END, f"  • {course}\n")
                    self.prereq_text.insert(tk.END, "\n")

            self.status_bar.config(text=f"Visualized prerequisites for {course_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to visualize prerequisites: {e}")

    def _check_eligibility(self):
        """Check prerequisite eligibility."""
        course_id = self.prereq_course_entry.get().strip().upper()
        if not course_id:
            messagebox.showwarning("Warning", "Please enter a course ID.")
            return

        try:
            eligibility = self.planning_service.check_prerequisite_eligibility(
                self.student_id, course_id
            )

            # Clear text
            self.prereq_text.delete(1.0, tk.END)

            # Display eligibility
            self.prereq_text.insert(tk.END, f"=== Eligibility Check for {course_id} ===\n\n")

            if eligibility['eligible']:
                self.prereq_text.insert(tk.END, "✓ ELIGIBLE - You can take this course!\n\n")
            else:
                self.prereq_text.insert(tk.END, "✗ NOT ELIGIBLE - Prerequisites not met\n\n")

            self.prereq_text.insert(tk.END, f"Total Prerequisites: {eligibility['total_prerequisites']}\n\n")

            if eligibility['met_prerequisites']:
                self.prereq_text.insert(tk.END, f"✓ Met Prerequisites ({len(eligibility['met_prerequisites'])}):\n")
                for prereq in eligibility['met_prerequisites']:
                    self.prereq_text.insert(tk.END,
                        f"  • {prereq['course_id']}: Grade {prereq['grade']} "
                        f"(Required: {prereq['required_grade']})\n")
                self.prereq_text.insert(tk.END, "\n")

            if eligibility['missing_prerequisites']:
                self.prereq_text.insert(tk.END, f"✗ Missing Prerequisites ({len(eligibility['missing_prerequisites'])}):\n")
                for prereq in eligibility['missing_prerequisites']:
                    self.prereq_text.insert(tk.END,
                        f"  • {prereq['course_id']}: {prereq['reason']} ({prereq['status']})\n")

            self.status_bar.config(text=f"Checked eligibility for {course_id}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check eligibility: {e}")

    def _get_recommendations(self):
        """Get course recommendations."""
        semester = self.rec_semester_entry.get().strip() or "Fall 2026"

        try:
            recommendations = self.planning_service.recommend_courses(
                self.student_id, semester, max_recommendations=20
            )

            # Clear tree
            for item in self.rec_tree.get_children():
                self.rec_tree.delete(item)

            if not recommendations:
                self.rec_tree.insert('', tk.END, text="No recommendations available")
                return

            # Populate tree
            for rec in recommendations:
                score_stars = "★" * int(rec['relevance_score']) + "☆" * (5 - int(rec['relevance_score']))
                self.rec_tree.insert('', tk.END, values=(
                    rec['course_id'],
                    rec['course_name'],
                    rec['credits'],
                    f"{score_stars} ({rec['relevance_score']})",
                    rec['reason']
                ))

            self.status_bar.config(text=f"Loaded {len(recommendations)} recommendations")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get recommendations: {e}")

    def _add_recommended_course(self):
        """Add selected recommended course to plan."""
        if not self.current_plan_id:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        selection = self.rec_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a course to add.")
            return

        item = selection[0]
        values = self.rec_tree.item(item, 'values')
        course_id = values[0]

        # Simple dialog for semester
        semester_num = tk.simpledialog.askinteger(
            "Add Course",
            f"Add {course_id} to which semester?",
            minvalue=1, maxvalue=10
        )

        if not semester_num:
            return

        semester_name = tk.simpledialog.askstring(
            "Add Course",
            "Semester name (e.g., Fall 2026):"
        )

        if not semester_name:
            return

        try:
            self.planning_service.add_course_to_plan(
                plan_id=self.current_plan_id,
                course_id=course_id,
                semester_number=semester_num,
                semester_name=semester_name
            )

            messagebox.showinfo("Success", f"Course {course_id} added to Semester {semester_num}!")
            self.current_plan_data = self.planning_service.get_semester_plan(self.current_plan_id)
            self._display_planner_content()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add course: {e}")

    def _detect_conflicts(self):
        """Detect schedule conflicts."""
        if not self.current_plan_id:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        try:
            conflicts = self.planning_service.detect_schedule_conflicts(self.current_plan_id)

            # Clear tree
            for item in self.conflicts_tree.get_children():
                self.conflicts_tree.delete(item)

            if not conflicts:
                self.conflicts_tree.insert('', tk.END, text="✓ No conflicts detected!")
                self.conflict_details_text.delete(1.0, tk.END)
                self.conflict_details_text.insert(tk.END, "Your schedule looks good!")
                return

            # Populate tree with conflicts
            for conflict in conflicts:
                severity_icon = {
                    'High': '🔴',
                    'Medium': '🟡',
                    'Low': '🟢'
                }.get(conflict['severity'], '')

                self.conflicts_tree.insert('', tk.END, values=(
                    f"{severity_icon} {conflict['severity']}",
                    conflict['type'],
                    conflict.get('semester', 'N/A'),
                    conflict['description']
                ), tags=(conflict['severity'],))

            # Configure tags for coloring
            self.conflicts_tree.tag_configure('High', foreground='red')
            self.conflicts_tree.tag_configure('Medium', foreground='orange')
            self.conflicts_tree.tag_configure('Low', foreground='blue')

            self.status_bar.config(text=f"Detected {len(conflicts)} conflict(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to detect conflicts: {e}")

    def _on_conflict_select(self, event):
        """Handle conflict selection to show suggestions."""
        selection = self.conflicts_tree.selection()
        if not selection:
            return

        # Get conflict data (would need to store this)
        # For now, show generic message
        self.conflict_details_text.delete(1.0, tk.END)
        self.conflict_details_text.insert(tk.END, "Suggestions:\n\n")
        self.conflict_details_text.insert(tk.END, "• Review the affected courses\n")
        self.conflict_details_text.insert(tk.END, "• Consider moving courses to different semesters\n")
        self.conflict_details_text.insert(tk.END, "• Check prerequisite requirements\n")

    def _export_conflicts_report(self):
        """Export conflicts report."""
        if not self.current_plan_id:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        try:
            conflicts = self.planning_service.get_plan_conflicts(self.current_plan_id)

            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=f"conflicts_report_plan_{self.current_plan_id}.json"
            )

            if not filename:
                return

            with open(filename, 'w') as f:
                json.dump(conflicts, f, indent=2, default=str)

            messagebox.showinfo("Success", f"Conflicts report exported to:\n{filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")

    def _duplicate_plan(self):
        """Duplicate the selected plan with a new name."""
        selection = self.plans_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a plan to duplicate.")
            return

        index = selection[0]
        plans = self.planning_service.get_student_plans(self.student_id)

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
            original_data = self.planning_service.get_semester_plan(original_plan['plan_id'])

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
        plans = self.planning_service.get_student_plans(self.student_id)

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

    def _export_plan_pdf(self):
        """Export current plan to PDF."""
        if not self.current_plan_id or not self.current_plan_data:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
            from reportlab.lib.enums import TA_CENTER, TA_LEFT
            import datetime

        except ImportError:
            messagebox.showerror(
                "Error",
                "PDF export requires reportlab library.\n\n"
                "Install with: pip install reportlab"
            )
            return

        # Get save location
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"course_plan_{self.current_plan_id}.pdf"
        )

        if not filename:
            return

        try:
            plan = self.current_plan_data['plan']
            semesters = self.current_plan_data['semesters']

            # Create PDF
            doc = SimpleDocTemplate(filename, pagesize=letter)
            story = []
            styles = getSampleStyleSheet()

            # Title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            story.append(Paragraph(f"Course Plan: {plan['plan_name']}", title_style))
            story.append(Spacer(1, 0.3*inch))

            # Plan info
            info_data = [
                ["Student ID:", self.student_id],
                ["Program:", plan['program_code'] or 'N/A'],
                ["Start Semester:", plan['start_semester']],
                ["Total Semesters:", str(plan['total_semesters'])],
                ["Credits/Semester:", str(plan['credits_per_semester'])],
                ["Status:", plan['status']],
                ["Generated:", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")]
            ]

            info_table = Table(info_data, colWidths=[2*inch, 4*inch])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey)
            ]))
            story.append(info_table)
            story.append(Spacer(1, 0.5*inch))

            # Semester breakdown
            for semester_num in sorted(semesters.keys()):
                courses = semesters[semester_num]
                if not courses:
                    continue

                total_credits = sum(c['credits'] for c in courses)

                # Semester header
                sem_header_style = ParagraphStyle(
                    'SemesterHeader',
                    parent=styles['Heading2'],
                    fontSize=14,
                    textColor=colors.HexColor('#3498db'),
                    spaceAfter=10
                )
                sem_name = courses[0]['semester_name'] if courses else f'Semester {semester_num}'
                story.append(Paragraph(
                    f"Semester {semester_num}: {sem_name} ({total_credits} Credits)",
                    sem_header_style
                ))

                # Course table
                course_data = [['Course ID', 'Course Name', 'Credits', 'Notes']]
                for course in courses:
                    notes = course['notes'] or ''
                    if course['is_locked']:
                        notes = '[LOCKED] ' + notes
                    course_data.append([
                        course['course_id'],
                        course['course_name'][:40],  # Truncate long names
                        str(course['credits']),
                        notes[:30]  # Truncate long notes
                    ])

                course_table = Table(course_data, colWidths=[1.2*inch, 2.5*inch, 0.8*inch, 1.5*inch])
                course_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(course_table)
                story.append(Spacer(1, 0.3*inch))

            # Build PDF
            doc.build(story)

            messagebox.showinfo("Success", f"Plan exported to PDF:\n{filename}")

            log_activity('export', 'semester_plan', user_id=self.student_id,
                        details={'action': 'export_pdf', 'plan_id': self.current_plan_id,
                                'filename': filename})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export PDF: {e}")

    def _email_plan_to_advisor(self):
        """Email current plan to academic advisor."""
        if not self.current_plan_id or not self.current_plan_data:
            messagebox.showwarning("Warning", "Please load a plan first.")
            return

        # Create dialog to select advisor
        dialog = tk.Toplevel(self.window)
        dialog.title("Email Plan to Advisor")
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        # Header
        ttk.Label(dialog, text="Select Academic Advisor",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(dialog, text="Choose a staff member or administrator to email your course plan:",
                 font=('Arial', 10)).pack(pady=5)

        # Get staff and admin users
        with get_connection() as conn:
            staff_users = conn.execute("""
                SELECT user_id, username, email, role
                FROM users
                WHERE role IN ('Staff', 'Admin', 'Instructor')
                AND email IS NOT NULL AND email != ''
                ORDER BY role, username
            """).fetchall()

        if not staff_users:
            messagebox.showerror("Error", "No staff/admin users found with email addresses.")
            dialog.destroy()
            return

        # List frame
        list_frame = ttk.LabelFrame(dialog, text="Available Advisors", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Create listbox with scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        advisor_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                     font=('Arial', 10), height=10)
        scrollbar.config(command=advisor_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        advisor_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Populate listbox
        advisor_data = {}
        for user in staff_users:
            display_text = f"{user['username']} ({user['role']}) - {user['email']}"
            advisor_listbox.insert(tk.END, display_text)
            advisor_data[display_text] = user

        selected_advisor = {'user': None}

        def select_and_send():
            selection = advisor_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select an advisor.")
                return

            selected_text = advisor_listbox.get(selection[0])
            selected_advisor['user'] = advisor_data[selected_text]
            dialog.destroy()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(button_frame, text="Send Email", command=select_and_send).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)

        # Wait for dialog to close
        dialog.wait_window()

        # Check if an advisor was selected
        if not selected_advisor['user']:
            return

        advisor_email = selected_advisor['user']['email']
        advisor_name = selected_advisor['user']['username']

        try:
            # Check if email service is available
            try:
                from university_system.infrastructure.email.email_service import queue_email
                EMAIL_AVAILABLE = True
            except ImportError:
                EMAIL_AVAILABLE = False

            if not EMAIL_AVAILABLE:
                messagebox.showerror(
                    "Error",
                    "Email service is not available.\n\n"
                    "Configure email settings in the system."
                )
                return

            plan = self.current_plan_data['plan']
            semesters = self.current_plan_data['semesters']

            # Build email body
            subject = f"Course Plan: {plan['plan_name']} - {self.current_user.get('username', 'Student')}"

            body = f"""Dear {advisor_name},

Please review my course plan for the upcoming semesters.

PLAN DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Student: {self.current_user.get('username', 'N/A')} ({self.student_id})
Plan Name: {plan['plan_name']}
Program: {plan['program_code'] or 'N/A'}
Start Semester: {plan['start_semester']}
Total Semesters: {plan['total_semesters']}
Target Credits/Semester: {plan['credits_per_semester']}
Status: {plan['status']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SEMESTER BREAKDOWN
"""

            # Add semester details
            for semester_num in sorted(semesters.keys()):
                courses = semesters[semester_num]
                if not courses:
                    continue

                total_credits = sum(c['credits'] for c in courses)
                sem_name = courses[0]['semester_name'] if courses else f'Semester {semester_num}'

                body += f"\n\n{'='*60}\n"
                body += f"Semester {semester_num}: {sem_name} ({total_credits} Credits)\n"
                body += f"{'='*60}\n"

                for course in courses:
                    locked_flag = " [LOCKED]" if course['is_locked'] else ""
                    notes_text = f"\n    Notes: {course['notes']}" if course['notes'] else ""
                    body += f"  • {course['course_id']}: {course['course_name']} ({course['credits']} cr){locked_flag}{notes_text}\n"

            body += f"\n\n{'='*60}\n"
            body += f"Total Credits Planned: {sum(sum(c['credits'] for c in courses) for courses in semesters.values())}\n"
            body += f"{'='*60}\n\n"
            body += "Please let me know if you have any suggestions or concerns about this plan.\n\n"
            body += "Best regards,\n"
            body += f"{self.current_user.get('username', 'Student')}"

            # Send email
            success = queue_email(advisor_email, subject, body)

            if success:
                messagebox.showinfo(
                    "Success",
                    f"Course plan emailed to:\n{advisor_email}\n\n"
                    "Your advisor will receive the plan details shortly."
                )

                log_activity('email', 'semester_plan', user_id=self.student_id,
                            details={'action': 'email_to_advisor', 'plan_id': self.current_plan_id,
                                    'advisor_email': advisor_email})
            else:
                messagebox.showerror("Error", "Failed to queue email. Please try again.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to email plan: {e}")

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
        self.progress_program_entry = ttk.Entry(program_frame, width=30)

        # Get student's major
        with get_connection() as conn:
            student = conn.execute("""
                SELECT course FROM students WHERE student_id = ?
            """, (self.student_id,)).fetchone()

        if student and student['course']:
            self.progress_program_entry.insert(0, student['course'])

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
        """Calculate student's current GPA from completed courses."""
        try:
            with get_connection() as conn:
                # Get all graded courses from module_grades (final course grades)
                grades = conn.execute("""
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

            if not grades:
                messagebox.showinfo("Info", "No graded courses found.")
                return

            # GPA scale
            grade_points = {
                'A': 4.0, 'A-': 3.7,
                'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                'C+': 2.3, 'C': 2.0, 'C-': 1.7,
                'D+': 1.3, 'D': 1.0, 'D-': 0.7,
                'F': 0.0
            }

            total_points = 0.0
            total_credits = 0

            for grade_row in grades:
                credits = grade_row['credits']
                grade = grade_row['grade'].strip().upper()

                if grade in grade_points:
                    total_points += grade_points[grade] * credits
                    total_credits += credits

            if total_credits == 0:
                messagebox.showinfo("Info", "No valid graded courses for GPA calculation.")
                return

            gpa = total_points / total_credits

            # Update labels
            self.gpa_current_label.config(text=f"Current GPA: {gpa:.2f}")
            self.gpa_credits_label.config(text=f"Total Credits: {total_credits}")

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
        program_code = self.progress_program_entry.get().strip()

        if not program_code:
            messagebox.showwarning("Warning", "Please enter a program code.")
            return

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

                # Get completed courses
                completed = conn.execute("""
                    SELECT mg.module_code as course_id, mg.final_grade as grade,
                           m.module_name as name, m.credits
                    FROM module_grades mg
                    LEFT JOIN modules m ON mg.module_code = m.module_code
                    WHERE mg.student_id = ? AND mg.final_grade IS NOT NULL
                    AND mg.final_grade NOT IN ('F', 'W', 'I')
                    UNION
                    SELECT sg.module_code as course_id, sg.grade,
                           c.name, c.credits
                    FROM student_grades sg
                    LEFT JOIN courses c ON sg.module_code = c.code
                    WHERE sg.student_id = ? AND sg.grade IS NOT NULL
                    AND sg.grade NOT IN ('F', 'W', 'I')
                    AND sg.assessment_name LIKE '%Final%'
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


# Standalone launcher for testing
def launch_course_planning_gui():
    """Launch the Course Planning GUI standalone."""
    root = tk.Tk()
    root.withdraw()

    # Mock auth for testing
    class MockAuth:
        current_user = {
            'id': 'TEST001',
            'username': 'test_student',
            'role': 'student'
        }

    app = CoursePlanningGUI(root, MockAuth())
    root.mainloop()


if __name__ == "__main__":
    launch_course_planning_gui()
