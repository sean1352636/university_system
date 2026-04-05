"""Instructor Portal GUI — the landing page for instructor users.

Instead of the full UnifiedManagementGUI (designed for admin/staff), instructors
see a dashboard with a scrollable sidebar listing every module they have
access to, organised by category.  Clicking a sidebar button renders the
feature in the main content area (or opens a Toplevel, depending on the
feature).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)


class InstructorPortalGUI:
    """Instructor-facing portal with sidebar navigation and dashboard home."""

    def __init__(self, auth_manager):
        self.auth = auth_manager
        self.root = tk.Tk()
        self.root.title("Instructor Portal")
        self.root.geometry("1300x800")
        self.root.minsize(1100, 700)

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()

        self.content_frame = None
        self._build_ui()
        self._show_dashboard()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------

    def _configure_styles(self):
        self.style.configure('Sidebar.TButton', padding=(8, 4))
        self.style.configure('SidebarHeading.TLabel', font=('Arial', 10, 'bold'),
                             foreground='#2c3e50')
        self.style.configure('Header.TLabel', font=('Arial', 16, 'bold'),
                             foreground='white', background='#2c3e50')
        self.style.configure('HeaderFrame.TFrame', background='#2c3e50')

    # ------------------------------------------------------------------
    # UI layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Header bar
        header = tk.Frame(self.root, bg='#2c3e50', height=50)
        header.pack(fill='x')
        header.pack_propagate(False)

        username = ''
        if self.auth and self.auth.current_user:
            username = self.auth.current_user.get('display_name') or self.auth.current_user.get('username', '')

        tk.Label(header, text=f"Instructor Portal — {username}",
                 font=('Arial', 15, 'bold'), bg='#2c3e50', fg='white'
                 ).pack(side='left', padx=20, pady=10)

        tk.Button(header, text="Shutdown", bg='#c0392b', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._shutdown).pack(side='right', padx=10, pady=10)

        tk.Button(header, text="Return to Login", bg='#e67e22', fg='white',
                  font=('Arial', 10, 'bold'), bd=0, padx=12, pady=4,
                  command=self._return_to_login).pack(side='right', padx=10, pady=10)

        # Main paned area: sidebar + content
        paned = ttk.PanedWindow(self.root, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # --- Sidebar ---
        sidebar_outer = ttk.Frame(paned, width=240)
        paned.add(sidebar_outer, weight=0)

        canvas = tk.Canvas(sidebar_outer, highlightthickness=0, width=230)
        scrollbar = ttk.Scrollbar(sidebar_outer, orient='vertical', command=canvas.yview)
        self._sidebar = ttk.Frame(canvas)

        self._sidebar.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas_win = canvas.create_window((0, 0), window=self._sidebar, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.itemconfig(canvas_win, width=e.width))

        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Mouse-wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

        def _on_mousewheel_linux(event):
            if event.num == 4:
                canvas.yview_scroll(-1, 'units')
            elif event.num == 5:
                canvas.yview_scroll(1, 'units')

        canvas.bind_all('<MouseWheel>', _on_mousewheel)
        canvas.bind_all('<Button-4>', _on_mousewheel_linux)
        canvas.bind_all('<Button-5>', _on_mousewheel_linux)

        # --- Content area ---
        content_outer = ttk.Frame(paned)
        paned.add(content_outer, weight=1)

        self.content_frame = ttk.Frame(content_outer)
        self.content_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Populate sidebar
        self._build_sidebar()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _add_heading(self, text):
        ttk.Label(self._sidebar, text=text, style='SidebarHeading.TLabel'
                  ).pack(anchor='w', padx=8, pady=(12, 2))
        ttk.Separator(self._sidebar, orient='horizontal').pack(fill='x', padx=8)

    def _add_button(self, text, command):
        ttk.Button(self._sidebar, text=text, command=command,
                   style='Sidebar.TButton').pack(fill='x', padx=6, pady=1)

    def _build_sidebar(self):
        # Dashboard
        self._add_button("Dashboard", self._show_dashboard)

        # Teaching
        self._add_heading("Teaching")
        self._add_button("Course Management", self._launch('show_course_management'))
        self._add_button("Module Management", self._launch('show_module_management'))
        self._add_button("Assignments", self._launch('show_assignments'))
        self._add_button("Grade Tracking", self._launch('show_grade_tracking_gui'))
        self._add_button("AI Auto-Grading", self._launch('show_auto_grading'))
        self._add_button("Virtual Classroom", self._launch('show_virtual_classroom_gui'))
        self._add_button("Office Hours", self._launch('show_office_hours_gui'))
        self._add_button("TA Management", self._launch('show_ta_management_gui'))

        # Students
        self._add_heading("Students")
        self._add_button("Student Records", self._launch('show_student_records'))
        self._add_button("Student Analytics", self._launch('show_student_analytics_gui'))
        self._add_button("Learning Outcomes", self._launch('show_student_outcomes_gui'))
        self._add_button("Student Registration", self._launch('show_student_registration_gui'))
        self._add_button("Early Warning System", self._launch('show_early_warning_gui'))
        self._add_button("Academic Progress", self._launch('show_academic_progress_gui'))

        # Schedule & Attendance
        self._add_heading("Schedule & Attendance")
        self._add_button("Academic Calendar", self._launch('show_academic_calendar'))
        self._add_button("My Timetable", self._launch('show_student_timetable_gui'))
        self._add_button("Scheduling", self._launch('show_module_scheduling'))
        self._add_button("Attendance", self._launch('open_attendance_gui'))
        self._add_button("Exam Scheduler", self._launch('show_exam_scheduler_gui'))

        # Analytics
        self._add_heading("Analytics")
        self._add_button("Analytics", self._launch('show_analytics_dashboard_gui'))
        self._add_button("Predictive Analytics", self._launch('show_predictive_analytics_gui'))
        self._add_button("Enhanced Reports", self._launch('show_enhanced_reporting_gui'))
        self._add_button("Export Data", self._launch('show_export_gui'))

        # Communication
        self._add_heading("Communication")
        self._add_button("Communication Hub", self._launch('show_communication_hub_gui'))
        self._add_button("Cross-System Calendar", self._launch('show_cross_system_calendar_gui'))

        # Resources
        self._add_heading("Resources")
        self._add_button("Library", self._launch('show_library_management'))
        self._add_button("University Shop", self._launch('show_university_shop'))
        self._add_button("Cafe", self._launch('show_cafe_system'))
        self._add_button("Health Portal", self._launch('open_health_portal_gui'))

        # Account
        self._add_heading("Account")
        self._add_button("Change Password", self._launch('show_change_password'))
        self._add_button("MFA Setup", self._launch('show_mfa_setup'))
        self._add_button("Security Questions", self._launch('show_security_questions'))
        self._add_button("Extras & Tools", self._launch('show_extras_launcher_gui'))

    # ------------------------------------------------------------------
    # Launcher helper
    # ------------------------------------------------------------------

    def _launch(self, method_name):
        """Return a callback that calls the named method on the UnifiedManagementGUI.

        We lazily import and instantiate a hidden UnifiedManagementGUI that
        shares our auth and root, purely to reuse its 80+ show_* methods.
        """
        def callback():
            try:
                gui = self._get_backend_gui()
                fn = getattr(gui, method_name, None)
                if fn:
                    fn()
                else:
                    messagebox.showinfo("Coming Soon", f"{method_name} is not yet available.")
            except Exception as e:
                logger.error(f"Error launching {method_name}: {e}")
                messagebox.showerror("Error", f"Failed to open: {e}")
        return callback

    def _get_backend_gui(self):
        """Lazily create a headless UnifiedManagementGUI to reuse its methods."""
        if not hasattr(self, '_backend_gui'):
            from education_system.university_system.modules.shared.gui.main.main_gui import UnifiedManagementGUI
            # We patch __init__ to skip creating a second Tk root
            gui = object.__new__(UnifiedManagementGUI)
            gui.auth = self.auth
            gui.root = self.root
            gui.content_frame = self.content_frame
            gui.style = self.style
            gui.current_user_var = tk.StringVar()
            gui.status_var = tk.StringVar()
            gui.finance_gui = None
            gui.student_union_gui = None
            gui.health_portal_gui = None
            gui.grade_tracking_gui = None
            gui.restaurant_gui = None
            gui.cafe_gui = None
            gui.email_manager_gui = None
            gui.student_tree = None
            gui._session_timer_id = None
            gui.nav_frame = None

            # Bind all the show_* methods from feature modules
            try:
                from education_system.university_system.modules.shared.gui.main import main_gui as _mg
                # The module-level code in main_gui.py already bound all methods
                # to UnifiedManagementGUI class, so they're available on gui
            except Exception:
                pass

            self._backend_gui = gui
        return self._backend_gui

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def _show_dashboard(self):
        """Show the instructor dashboard in the content area."""
        for w in self.content_frame.winfo_children():
            w.destroy()

        try:
            from education_system.university_system.modules.shared.gui.main.dashboard.instructor_dashboard import create_instructor_dashboard
            from education_system.university_system.modules.shared.services.dashboard.dashboard_service import DashboardService
            service = DashboardService()
            create_instructor_dashboard(self.content_frame, self.auth, service)
        except Exception as e:
            logger.error(f"Error loading instructor dashboard: {e}")
            # Fallback: show a simple welcome with instructor-relevant info
            self._show_fallback_dashboard()

    def _show_fallback_dashboard(self):
        """Simple fallback dashboard when the full dashboard fails to load."""
        username = ''
        if self.auth and self.auth.current_user:
            username = self.auth.current_user.get('display_name') or self.auth.current_user.get('username', '')

        ttk.Label(self.content_frame, text=f"Welcome, {username}!",
                  font=('Arial', 14, 'bold')).pack(pady=20)
        ttk.Label(self.content_frame,
                  text="Use the sidebar to navigate to your teaching modules.",
                  font=('Arial', 11)).pack()

        # Attempt to show basic instructor info
        try:
            from education_system.university_system.modules.shared.services.database import connect
            import os
            db_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                                   'data', 'db_files', 'student_records.db')
            db_path = os.path.normpath(db_path)
            conn = connect(db_path)
            try:
                cursor = conn.cursor()
                user_id = self.auth.current_user.get('user_id') or self.auth.current_user.get('id', '')

                # Courses taught
                info_frame = ttk.LabelFrame(self.content_frame, text="Quick Overview", padding=10)
                info_frame.pack(fill='x', padx=20, pady=10)

                try:
                    cursor.execute(
                        "SELECT module_name FROM modules WHERE instructor LIKE ? LIMIT 10",
                        (f"%{username}%",))
                    courses = cursor.fetchall()
                    if courses:
                        ttk.Label(info_frame, text="My Courses:",
                                  font=('Arial', 11, 'bold')).pack(anchor='w')
                        for row in courses:
                            ttk.Label(info_frame, text=f"  - {row[0]}").pack(anchor='w')
                except Exception:
                    pass

                # Upcoming assignments
                try:
                    cursor.execute(
                        "SELECT title, due_date FROM assignments "
                        "WHERE created_by LIKE ? ORDER BY due_date ASC LIMIT 5",
                        (f"%{username}%",))
                    assignments = cursor.fetchall()
                    if assignments:
                        ttk.Label(info_frame, text="\nUpcoming Assignments:",
                                  font=('Arial', 11, 'bold')).pack(anchor='w')
                        for row in assignments:
                            ttk.Label(info_frame, text=f"  - {row[0]} (due {row[1]})").pack(anchor='w')
                except Exception:
                    pass

                # Recent grade submissions
                try:
                    cursor.execute(
                        "SELECT COUNT(*) FROM grades WHERE graded_by LIKE ?",
                        (f"%{username}%",))
                    count = cursor.fetchone()
                    if count and count[0]:
                        ttk.Label(info_frame, text=f"\nGrades Submitted: {count[0]}",
                                  font=('Arial', 11, 'bold')).pack(anchor='w')
                except Exception:
                    pass

                # Office hours summary
                try:
                    cursor.execute(
                        "SELECT day_of_week, start_time, end_time FROM office_hours "
                        "WHERE instructor LIKE ? LIMIT 5",
                        (f"%{username}%",))
                    hours = cursor.fetchall()
                    if hours:
                        ttk.Label(info_frame, text="\nOffice Hours:",
                                  font=('Arial', 11, 'bold')).pack(anchor='w')
                        for row in hours:
                            ttk.Label(info_frame, text=f"  - {row[0]}: {row[1]} - {row[2]}").pack(anchor='w')
                except Exception:
                    pass

            finally:
                conn.close()
        except Exception as e:
            logger.debug(f"Could not load fallback instructor info: {e}")

    # ------------------------------------------------------------------
    # Navigation / close
    # ------------------------------------------------------------------

    def _return_to_login(self):
        """Log out and return to the universal login window."""
        if self.auth:
            try:
                self.auth.logout()
            except Exception:
                pass
        self.root.destroy()
        try:
            from education_system.shared.gui.login_gui import UniversalLoginWindow
            login = UniversalLoginWindow()
            login.mainloop()
            if login.user_info and login.system_key:
                from run import run_university_gui
                run_university_gui(
                    user_info=login.user_info,
                    role=login.system_role,
                    shared_auth=login.auth,
                )
        except Exception as e:
            logger.error(f"Error returning to login: {e}")

    def _shutdown(self):
        """Shut down the application entirely."""
        if self.auth:
            try:
                self.auth.logout()
            except Exception:
                pass
        self.root.destroy()
        raise SystemExit(0)

    def _on_close(self):
        self._shutdown()

    def run(self):
        self.root.mainloop()
