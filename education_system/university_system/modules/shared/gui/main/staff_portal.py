"""Staff Portal GUI — the landing page for staff users.

Instead of the full UnifiedManagementGUI (designed for admin), staff
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


class StaffPortalGUI:
    """Staff-facing portal with sidebar navigation and dashboard home."""

    def __init__(self, auth_manager):
        self.auth = auth_manager
        self.root = tk.Tk()
        self.root.title("Staff Portal")
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

        tk.Label(header, text=f"Staff Portal \u2014 {username}",
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

        # Student Management
        self._add_heading("Student Management")
        self._add_button("Student Records", self._launch('show_student_records'))
        self._add_button("Create Student", self._launch('create_student_dialog'))
        self._add_button("Search Students", self._launch('search_students_dialog'))
        self._add_button("Batch Operations", self._launch('show_batch_operations_gui'))

        # Academic
        self._add_heading("Academic")
        self._add_button("Course Management", self._launch('show_course_management'))
        self._add_button("Module Management", self._launch('show_module_management'))
        self._add_button("Assignments", self._open_assignments_portal)
        self._add_button("Grade Tracking", self._open_grade_tracking_portal)
        self._add_button("AI Auto-Grading", self._launch('show_auto_grading'))
        self._add_button("Virtual Classroom", self._launch('show_virtual_classroom_gui'))
        self._add_button("Attendance", self._launch('open_attendance_gui'))


        # Schedule
        self._add_heading("Schedule")
        self._add_button("Academic Calendar", self._open_calendar_portal)
        self._add_button("Scheduling", self._launch('show_module_scheduling'))
        self._add_button("Exam Management", self._launch('show_exam_portal'))

        # HR & Staff
        self._add_heading("HR & Staff")
        self._add_button("Staff HR", self._launch('show_staff_hr_gui'))
        self._add_button("View Staff", self._launch('show_view_staff'))
        self._add_button("Create Staff", self._launch('show_create_staff'))
        self._add_button("Office Hours", self._launch('show_office_hours_gui'))


        # Finance
        self._add_heading("Finance")
        self._add_button("Finance Management", self._launch('show_finance_management'))

        # Health & Facilities
        self._add_heading("Health & Facilities")
        self._add_button("Health Portal", self._open_health_portal)
        self._add_button("Housing", self._launch('show_housing_accommodations'))
        self._add_button("Facilities", self._launch('show_facilities_management_gui'))
        self._add_button("Parking", self._launch('show_parking_management_gui'))

        # Communication
        self._add_heading("Communication")
        self._add_button("Communication Hub", self._launch('show_communication_hub_gui'))
        self._add_button("Email Manager", self._launch('show_email_manager_gui'))

        # Analytics & Reports
        self._add_heading("Analytics & Reports")
        self._add_button("Analytics Dashboard", self._launch('show_analytics_dashboard_gui'))
        self._add_button("Early Warning System", self._launch('show_early_warning_gui'))
        self._add_button("Export Data", self._launch('show_export_gui'))

        # Institutional
        self._add_heading("Institutional")
        self._add_button("Admissions CRM", self._launch('show_admissions_crm_gui'))
        self._add_button("Alumni Management", self._launch('show_alumni_relations_gui'))
        self._add_button("Library", self._open_library_portal)

        # Student Life
        self._add_heading("Student Life")
        self._add_button("Student Union", self._open_student_union_portal)
        self._add_button("Campus Events", self._open_campus_events_portal)
        self._add_button("Clubs & Societies", self._open_clubs_portal)
        self._add_button("Student Jobs", self._open_student_jobs_portal)

        # Services
        self._add_heading("Services")
        self._add_button("University Shop", self._launch('show_university_shop'))
        self._add_button("Charity Shop", self._launch('show_charity_shop'))
        self._add_button("Restaurant", self._launch('show_restaurant_management'))
        self._add_button("Cafe", self._open_cafe_portal)
        self._add_button("Bar", self._open_bar_portal)
        self._add_button("Takeaway", self._open_takeaway_portal)
        self._add_button("Cinema", self._open_cinema_portal)
        self._add_button("Barber", self._open_barber_portal)

        # Cross-System
        self._add_heading("Cross-System")
        self._add_button("Student Journey", self._launch('show_student_journey_gui'))
        self._add_button("Bulk Transfer", self._launch('show_bulk_transfer_gui'))
        self._add_button("Transfer Documents", self._launch('show_transfer_documents_gui'))
        self._add_button("Shared Documents", self._launch('show_shared_documents_gui'))
        self._add_button("GDPR Compliance", self._launch('show_gdpr_compliance_gui'))

        # Account
        self._add_heading("Account")
        self._add_button("Change Password", self._launch('show_change_password'))
        self._add_button("MFA Setup", self._launch('show_mfa_setup'))
        self._add_button("Security Questions", self._launch('show_security_questions'))
        self._add_button("Extras & Tools", self._launch('show_extras_launcher_gui'))

    # ------------------------------------------------------------------
    # Launcher helper
    # ------------------------------------------------------------------

    def _open_grade_tracking_portal(self):
        """Open the instructor/staff Grade Tracking portal directly."""
        try:
            from education_system.university_system.modules.domain.academics.gui.grade_tracking.staff_portal import (
                GradeTrackingStaffPortal,
            )
            GradeTrackingStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening grade tracking staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Grade Tracking: {e}")

    def _open_assignments_portal(self):
        """Open the instructor/staff Assignments portal directly."""
        try:
            from education_system.university_system.modules.domain.academics.gui.assignment_system.staff_portal import (
                AssignmentStaffPortal,
            )
            AssignmentStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening assignments staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Assignments: {e}")

    def _open_library_portal(self):
        """Open the instructor/staff Library portal directly."""
        try:
            from education_system.university_system.modules.domain.academics.gui.library.staff_portal import (
                LibraryStaffPortal,
            )
            LibraryStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening library staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Library: {e}")

    def _open_calendar_portal(self):
        """Open the instructor/staff Academic Calendar portal directly."""
        try:
            from education_system.university_system.modules.domain.academics.gui.academic_calendar.staff_portal import (
                CalendarStaffPortal,
            )
            CalendarStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening calendar staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Academic Calendar: {e}")

    def _open_health_portal(self):
        """Open the instructor/staff Health Portal directly."""
        try:
            from education_system.university_system.modules.domain.health.gui.health_portal.staff_portal import (
                HealthStaffPortal,
            )
            HealthStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening health staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Health Portal: {e}")

    def _open_student_union_portal(self):
        try:
            from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.staff_portal import (
                StudentUnionStaffPortal,
            )
            StudentUnionStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening student union staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Student Union: {e}")

    def _open_campus_events_portal(self):
        try:
            from education_system.university_system.modules.domain.campus.services.campus_events_staff_portal import (
                CampusEventsStaffPortal,
            )
            CampusEventsStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening campus events staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Campus Events: {e}")

    def _open_clubs_portal(self):
        try:
            from education_system.university_system.modules.domain.student_affairs.gui.student_union_gui.clubs.staff_portal import (
                ClubsStaffPortal,
            )
            ClubsStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening clubs staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Clubs & Societies: {e}")

    def _open_student_jobs_portal(self):
        try:
            from education_system.university_system.modules.domain.career.student_jobs.gui.staff_portal import (
                StudentJobsStaffPortal,
            )
            StudentJobsStaffPortal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening student jobs staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Student Jobs: {e}")

    def _open_cafe_portal(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.commerce_portals import (
                launch_cafe_staff_portal,
            )
            launch_cafe_staff_portal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening cafe staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Cafe: {e}")

    def _open_bar_portal(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.commerce_portals import (
                launch_bar_staff_portal,
            )
            launch_bar_staff_portal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening bar staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Bar: {e}")

    def _open_takeaway_portal(self):
        try:
            from education_system.university_system.modules.domain.commerce.services.commerce_portals import (
                launch_takeaway_staff_portal,
            )
            launch_takeaway_staff_portal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening takeaway staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Takeaway: {e}")

    def _open_cinema_portal(self):
        try:
            from education_system.university_system.modules.domain.commerce.cinema.cinema_portals import (
                launch_cinema_staff_portal,
            )
            launch_cinema_staff_portal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening cinema staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Cinema: {e}")

    def _open_barber_portal(self):
        try:
            from education_system.university_system.modules.domain.commerce.barber.barber_portals import (
                launch_barber_staff_portal,
            )
            launch_barber_staff_portal(self.root, self.auth)
        except Exception as e:
            logger.error(f"Error opening barber staff portal: {e}")
            messagebox.showerror("Error", f"Failed to open Barber: {e}")

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
            from education_system.university_system.modules.shared.gui.main.imports.gui_imports import _lazy_import
            for attr, cls_name in [
                ("finance_gui", "FinanceManagementGUI"),
                ("student_union_gui", "StudentUnionManagementGUI"),
                ("health_portal_gui", "HealthPortalManagementGUI"),
                ("grade_tracking_gui", "GradeTrackingManagementGUI"),
                ("restaurant_gui", "RestaurantManagementGUI"),
                ("cafe_gui", "CafeSystemGUI"),
                ("email_manager_gui", "EmailManagerManagementGUI"),
            ]:
                try:
                    cls = _lazy_import(cls_name)
                    setattr(gui, attr, cls(self.root, self.auth) if cls else None)
                except Exception as exc:
                    logger.warning("Could not initialise %s: %s", cls_name, exc)
                    setattr(gui, attr, None)
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
        """Show the staff dashboard in the content area."""
        for w in self.content_frame.winfo_children():
            w.destroy()

        try:
            from education_system.university_system.modules.shared.services.database import connect
            import os

            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))),
                'data', 'db_files', 'student_records.db'
            )

            conn = connect(db_path)
            try:
                cursor = conn.cursor()

                # Total students
                cursor.execute("SELECT COUNT(*) FROM students")
                total_students = cursor.fetchone()[0]

                # Total staff
                try:
                    cursor.execute("SELECT COUNT(*) FROM staff")
                    total_staff = cursor.fetchone()[0]
                except Exception:
                    total_staff = "N/A"

                # Total modules
                try:
                    cursor.execute("SELECT COUNT(*) FROM modules")
                    total_modules = cursor.fetchone()[0]
                except Exception:
                    total_modules = "N/A"

                # Recent registrations
                try:
                    cursor.execute(
                        "SELECT student_id, first_name, last_name, enrollment_date "
                        "FROM students ORDER BY enrollment_date DESC LIMIT 5"
                    )
                    recent = cursor.fetchall()
                except Exception:
                    recent = []
            finally:
                conn.close()

            # --- Render dashboard ---
            ttk.Label(self.content_frame, text="Staff Dashboard",
                      font=('Arial', 18, 'bold')).pack(pady=(10, 20))

            # Quick stats row
            stats_frame = ttk.Frame(self.content_frame)
            stats_frame.pack(fill='x', padx=20, pady=5)

            for label_text, value in [("Total Students", total_students),
                                       ("Total Staff", total_staff),
                                       ("Total Modules", total_modules)]:
                card = ttk.LabelFrame(stats_frame, text=label_text, padding=15)
                card.pack(side='left', expand=True, fill='both', padx=10)
                ttk.Label(card, text=str(value), font=('Arial', 24, 'bold')).pack()

            # Recent registrations
            reg_frame = ttk.LabelFrame(self.content_frame, text="Recent Student Registrations",
                                       padding=10)
            reg_frame.pack(fill='x', padx=30, pady=(20, 10))

            if recent:
                cols = ("ID", "First Name", "Last Name", "Enrolled")
                tree = ttk.Treeview(reg_frame, columns=cols, show='headings', height=5)
                for c in cols:
                    tree.heading(c, text=c)
                    tree.column(c, width=150)
                for row in recent:
                    tree.insert('', 'end', values=row)
                tree.pack(fill='x')
            else:
                ttk.Label(reg_frame, text="No recent registrations found.").pack()

            # System alerts placeholder
            alerts_frame = ttk.LabelFrame(self.content_frame, text="System Alerts", padding=10)
            alerts_frame.pack(fill='x', padx=30, pady=10)
            ttk.Label(alerts_frame, text="No active alerts.",
                      foreground='#27ae60', font=('Arial', 10)).pack(anchor='w')

        except Exception as e:
            logger.error(f"Error loading staff dashboard: {e}")
            ttk.Label(self.content_frame, text="Welcome, staff member!",
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
