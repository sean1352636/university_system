"""Student Portal GUI — the landing page for student users.

Instead of the full UnifiedManagementGUI (designed for admin/staff), students
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


class StudentPortalGUI:
    """Student-facing portal with sidebar navigation and dashboard home."""

    def __init__(self, auth_manager):
        self.auth = auth_manager
        self.root = tk.Tk()
        self.root.title("Student Portal")
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

        tk.Label(header, text=f"Student Portal — {username}",
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
        # Home
        self._add_button("Dashboard", self._show_dashboard)

        # Academic
        self._add_heading("Academic")
        self._add_button("Assignments", self._launch('show_assignments'))
        self._add_button("Grade Tracking", self._launch('show_grade_tracking_gui'))
        self._add_button("Course Planning", self._launch('show_course_planning_gui'))
        self._add_button("AI Study Tools", self._launch('show_ai_study_gui'))
        self._add_button("Study Matching", self._launch('show_study_matching_gui'))
        self._add_button("Study Recommendations", self._launch('show_study_recommendations_gui'))
        self._add_button("Library", self._launch('show_library_management'))
        self._add_button("Office Hours", self._launch('show_office_hours_gui'))
        self._add_button("LMS", self._launch('show_lms_gui'))
        self._add_button("Student Registration", self._launch('show_student_registration_gui'))

        # Schedule & Attendance
        self._add_heading("Schedule")
        self._add_button("Academic Calendar", self._launch('show_academic_calendar'))
        self._add_button("My Timetable", self._launch('show_student_timetable_gui'))
        self._add_button("Exam Management", self._launch('show_exam_portal'))

        # Finance
        self._add_heading("Finance")
        self._add_button("Financial Aid", self._launch('show_financial_aid_gui'))

        # Health & Wellness
        self._add_heading("Health & Wellness")
        self._add_button("Health Portal", self._launch('open_health_portal_gui'))

        # Student Life
        self._add_heading("Student Life")
        self._add_button("Student Union", self._launch('show_student_union_portal'))
        self._add_button("Campus Events", self._launch('show_campus_events_gui'))
        self._add_button("Clubs & Societies", self._launch('show_clubs_gui'))
        self._add_button("Student Jobs", self._launch('show_student_jobs_gui'))

        # Services & Shops
        self._add_heading("Services")
        self._add_button("University Shop", self._launch('show_university_shop'))
        self._add_button("Cafe", self._launch('show_cafe_system'))
        self._add_button("Takeaway", self._launch('show_takeaway_system'))
        self._add_button("Bar", self._launch('show_bar'))
        self._add_button("Cinema", self._launch('show_cinema_gui'))
        self._add_button("Barber", self._launch('show_barber_gui'))

        # Support
        self._add_heading("Support")
        self._add_button("Helpdesk", self._launch('show_helpdesk_gui'))
        self._add_button("Career Services", self._launch('show_career_services_gui'))
        self._add_button("Internship Portal", self._launch('show_internship_portal_gui'))
        self._add_button("Advising Portal", self._launch('show_advising_portal_gui'))
        self._add_button("Student Support", self._launch('show_student_support_gui'))
        self._add_button("Accessibility", self._launch('show_accessibility_gui'))
        self._add_button("Feedback", self._launch('show_feedback_system_gui'))

        # Portfolio & Achievements
        self._add_heading("Portfolio")
        self._add_button("My Portfolio", self._launch('show_portfolio_system_gui'))
        self._add_button("Digital Transcript", self._launch('show_digital_transcript_gui'))
        self._add_button("Certificates", self._launch('show_certificates_gui'))

        # Communication
        self._add_heading("Communication")
        self._add_button("Cross-System Calendar", self._launch('show_cross_system_calendar_gui'))
        self._add_button("Cross-System Comms", self._launch('show_cross_system_communications_gui'))

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
        """Show the student dashboard in the content area."""
        for w in self.content_frame.winfo_children():
            w.destroy()

        try:
            from education_system.university_system.modules.shared.gui.main.dashboard.student_dashboard import create_student_dashboard
            from education_system.university_system.modules.shared.services.dashboard.dashboard_service import DashboardService
            service = DashboardService()
            create_student_dashboard(self.content_frame, self.auth, service)
        except Exception as e:
            logger.error(f"Error loading student dashboard: {e}")
            ttk.Label(self.content_frame, text=f"Welcome, student!",
                      font=('Arial', 14, 'bold')).pack(pady=20)
            ttk.Label(self.content_frame,
                      text="Use the sidebar to navigate to your modules.",
                      font=('Arial', 11)).pack()

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

        # Re-show the universal login and relaunch the appropriate portal
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
