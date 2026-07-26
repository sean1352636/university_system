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


class _LifecycleMixin:
    """Methods extracted from CoursePlanningGUI.lifecycle responsibility."""

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
            except Exception:
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
                except Exception:
                    messagebox.showerror("Error", "Failed to load student data")
                    return

            self.viewing_as_admin = True
        else:
            self.student_id = self.current_user.get('id') or self.current_user.get('username')
            self.viewing_as_admin = False

        # Cache for current plan
        self.current_plan_id = None
        self.current_plan_data = None

        # One reusable read connection for this window (see _read_conn) and a
        # memoized plan list, so opening the GUI doesn't reopen a fresh SQLite
        # connection (~100ms schema-parse + WAL checkpoint each) for every
        # dashboard/planner query.
        self._cached_read_conn = None
        self._plans_cache = None

        self.create_main_window()

    def _read_conn(self):
        """Return a single SQLite connection reused for all of this window's
        read queries.

        Opening a fresh connection on this database costs ~100ms (schema
        parse on first access) plus a WAL checkpoint on close, so the GUI
        keeps one warm connection for the window's lifetime instead of
        paying that per query. Only SELECTs run on it (writes still go
        through transaction()), so it never holds a lock between calls.
        Closed in _close_read_conn when the window is destroyed.
        """
        conn = getattr(self, "_cached_read_conn", None)
        if conn is None:
            conn = get_connection()
            self._cached_read_conn = conn
        return conn

    def _close_read_conn(self):
        """Close the cached read connection, if any."""
        conn = getattr(self, "_cached_read_conn", None)
        self._cached_read_conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _student_plans(self, force: bool = False):
        """Memoized list of the current student's plans for this screen.

        The dashboard, planner empty-state, load/duplicate/delete flows and
        the plans listbox all need the same list; without memoization each
        opened a separate connection. The cache is busted (force=True) by
        _refresh_plans_list whenever plans change.
        """
        if force or getattr(self, "_plans_cache", None) is None:
            self._plans_cache = self.planning_service.get_student_plans(
                self.student_id, conn=self._read_conn())
        return self._plans_cache

    def _on_window_destroy(self, event):
        """Release the cached read connection when the window goes away."""
        if event.widget is self.window:
            self._close_read_conn()

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

        # Release the cached read connection when this window/frame is torn down.
        self.window.bind("<Destroy>", self._on_window_destroy, add="+")

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
            ttk.Button(bottom_frame, text="Switch to CLI", command=self._switch_to_cli).pack(side=tk.LEFT, padx=5)

        # Main notebook with tabs
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dashboard + Planner are built eagerly (Dashboard is the landing
        # view; the Planner is the target of programmatic notebook.select(1)
        # after creating/loading a plan). The remaining tabs are added as
        # empty frames and their content is built the first time the user
        # opens them — see _register_lazy_tab / _on_tab_changed. This keeps
        # each of those tabs' build-time DB queries off the open path.
        self._lazy_tabs = {}
        self._create_dashboard_tab()
        self._create_planner_tab()
        self._create_prerequisites_tab()
        self._create_recommendations_tab()
        self._create_conflicts_tab()
        self._create_tools_tab()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed, add="+")

        log_activity('view', 'course_planning_gui', user_id=self.student_id,
                    details={'action': 'opened_gui'})

    def _register_lazy_tab(self, frame, populate_fn):
        """Register a tab whose content is built on first view.

        The frame has already been added to the notebook (empty); populate_fn
        is called with it the first time the tab is selected.
        """
        if not hasattr(self, "_lazy_tabs"):
            self._lazy_tabs = {}
        self._lazy_tabs[str(frame)] = (frame, populate_fn)

    def _on_tab_changed(self, event=None):
        """Build a lazily-registered tab's content the first time it's shown."""
        try:
            selected = self.notebook.select()  # widget path of the current tab
        except Exception:
            return
        entry = getattr(self, "_lazy_tabs", {}).pop(selected, None)
        if entry is None:
            return
        frame, populate_fn = entry
        try:
            populate_fn(frame)
        except Exception:
            import traceback
            traceback.print_exc()

    def _show_programme_curriculum_map(self):
        """Open a dialog showing the curriculum-spec module list for a
        programme — the canonical structure that course plans should
        track."""
        from tkinter import simpledialog
        try:
            from education_system.systems.university.domain.academics.curriculum_specification.services.curriculum_specification_service import (
                CurriculumSpecificationService,
            )
            curr = CurriculumSpecificationService()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error",
                                 f"Curriculum Specification unavailable: {e}")
            return

        programmes = curr.list_programmes()
        if not programmes:
            from tkinter import messagebox
            messagebox.showinfo("No data",
                                "No programme specifications have been defined yet.")
            return

        choices = "\n".join(f"  [{p['id']}] {p['code']} v{p['version']} — {p['title']}"
                            for p in programmes)
        prog_id = simpledialog.askinteger(
            "Programme",
            f"Select a programme ID:\n\n{choices}",
            parent=self.window if self.window else self.root,
        )
        if not prog_id:
            return
        summary = curr.programme_summary(prog_id)
        if not summary:
            return
        modules = curr.list_module_descriptors(prog_id)

        dlg = tk.Toplevel(self.window if self.window else self.root)
        prog = summary["programme"]
        dlg.title(f"Curriculum Map — {prog['code']} v{prog['version']}")
        dlg.geometry("900x500")

        ttk.Label(dlg,
                  text=f"{prog['title']}  —  {summary['module_count']} modules, "
                       f"{summary['total_credits']} credits",
                  font=("", 11, "bold")).pack(padx=10, pady=8)

        cols = ("code", "version", "title", "credits", "level", "core")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=18)
        widths = {"code": 100, "version": 60, "title": 360, "credits": 70,
                  "level": 60, "core": 70}
        for c in cols:
            tree.heading(c, text=c.title())
            tree.column(c, width=widths[c], anchor=tk.W)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        for m in modules:
            tree.insert("", tk.END, values=(
                m["module_code"], m["version"], m["title"],
                m.get("credits") or "", m.get("level") or "",
                "Y" if m.get("is_core") else "N",
            ))

    def _switch_to_cli(self):
        """Switch from GUI to Course Planning CLI."""
        try:
            from education_system.systems.university.interfaces.gui.academics.course_management_gui.cli.course_planning_cli import display_course_planning_menu

            # Hide GUI temporarily
            target = self.window if self.window else self.root
            target.withdraw()

            import threading
            def run_cli():
                try:
                    display_course_planning_menu()
                except Exception as e:
                    logging.error(f"CLI mode error: {e}")
                finally:
                    target.after(0, target.deiconify)

            cli_thread = threading.Thread(target=run_cli, daemon=True)
            cli_thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch CLI: {e}")

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

