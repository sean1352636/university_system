
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from education_system.systems.university.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import mixin classes using relative imports to avoid circular dependency
from education_system.systems.university.domains.learners.interfaces.gui.alumni.dashboard import DashboardMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.alumni_crud import AlumniCRUDMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.directory import DirectoryMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.business_directory import BusinessDirectoryMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.events import EventsMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.forum import ForumMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.stories_photos import StoriesPhotosMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.donations import DonationsMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.reports import ReportsMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.chapters import ChaptersMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.mentorship import MentorshipMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.jobs_career import JobsCareerMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.reunions import ReunionsMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.gamification import GamificationMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.notifications import NotificationsMixin
from education_system.systems.university.domains.learners.interfaces.gui.alumni.alumni_office_records import AlumniOfficeRecordsMixin

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Alumni service functions
from education_system.systems.university.domains.learners.interfaces.gui.alumni._service_imports import (
    init_alumni_db,
    view_events,
    create_enhanced_event,
    event_check_in_system,
    view_connection_requests,
    manage_business_directory,
    manage_alumni_forum,
    post_job_opportunity,
    view_job_board,
    schedule_career_counseling,
    view_engagement_leaderboard,
    view_my_badges,
    manage_photo_gallery,
    manage_class_reunions,
    generate_alumni_report,
    set_auth,
    setup_alumni_permissions,
    generate_engagement_recommendations,
    get_connection,
)



class AlumniGUIApp(
    AlumniOfficeRecordsMixin,       # first: its screens replace older ones of the same name
    DashboardMixin,
    AlumniCRUDMixin,
    DirectoryMixin,
    BusinessDirectoryMixin,
    EventsMixin,
    ForumMixin,
    StoriesPhotosMixin,
    DonationsMixin,
    ReportsMixin,
    ChaptersMixin,
    MentorshipMixin,
    JobsCareerMixin,
    ReunionsMixin,
    GamificationMixin,
    NotificationsMixin
):
    def __init__(self, root, auth=None, show_return_button=True):
        self.root = root
        # When an alumnus logs in, this app is the primary portal window and
        # there is no parent dashboard to return to (the portal header already
        # offers Return to Login / Shutdown). The launcher passes
        # show_return_button=False in that case. Staff who open the alumni
        # system as a child window (e.g. from the graduation ceremony GUI)
        # keep the button so they can close it and return.
        self.show_return_button = show_return_button
        self.root.title(_t("alumni.window_title", default="Enhanced Alumni Management System"))
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Who is signed in. There is no fallback user: without a sign-in the
        # window only says so (it used to pretend to be an all-powerful admin).
        self.auth = auth
        self.current_user = getattr(auth, "current_user", None) if auth else None
        self.who = None
        if self.current_user:
            # Applies the alumni-office schema once (no tables are created here).
            init_alumni_db()
            from education_system.systems.university.application.alumni import (
                access as alumni_access,
            )
            from education_system.systems.university.infrastructure.ui import record_screens as common
            self.who = common.call(self.root, alumni_access.from_user, self.current_user,
                                   write=True, quiet=True)
        if self.who is None or not (self.who.is_staff_role or self.who.alumni_id or
                                    self.who.is_student):
            message = ("Sign in to use the alumni system." if not self.current_user else
                       "The alumni system is for graduates, current students (mentoring) and "
                       "alumni office staff. Ask the alumni office if you need a role.")
            ttk.Label(self.root, text=message, padding=40, font=("Arial", 12),
                      wraplength=700, justify="center").pack(expand=True)
            self.status_bar = None
            return

        # Set authentication for backend functions
        try:
            from alumni_management import auth as backend_auth
            backend_auth.current_user = self.current_user
        except (ImportError, AttributeError):
            pass

        self.create_widgets()
        self.show_home()
        self._photo_file_paths: list[str] = []
        self._event_lookup: dict[str, int] = {}
        self._photo_storage_dir = Path(paths.UNIVERSITY_DATA_DIR) / "alumni_photos"
        self._photo_storage_dir.mkdir(parents=True, exist_ok=True)

    def _current_user_id(self):
        """Return current user's identifier for auditing."""
        if self.current_user and isinstance(self.current_user, dict):
            return str(self.current_user.get('username') or self.current_user.get('id') or 'gui_user')
        return 'gui_user'

    def _get_db_connection(self):
        """Return a central database connection with row access."""
        conn = db_get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    def clear_content(self):
        """Clear the main content area"""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def create_main_content(self, parent):
        """Create the main content area"""
        self.content_frame = ttk.Frame(parent)
        self.content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    def create_navigation_menu(self, parent):
        """Create the navigation menu with categorized buttons and scrollbar"""
        # Add dashboard button at the top
        home_text = (_t("alumni.dashboard", default="Dashboard") if self.who.is_staff_role
                     else "Home")
        ttk.Button(parent, text=home_text, command=self.show_home).pack(fill=tk.X, pady=(0, 10))

        # "Return to Homescreen" is only meaningful when this app was opened
        # from a parent menu (staff Toplevel). For a logged-in alumnus it would
        # drop them into the main GUI with no way back, so it is hidden.
        if self.show_return_button:
            ttk.Button(parent, text=_t("common.return_to_main_menu", default="Return to Homescreen"), command=self.return_to_main_menu).pack(fill=tk.X, pady=(0, 10))

        # Create container for scrollable navigation
        nav_container = ttk.Frame(parent)
        nav_container.pack(fill=tk.BOTH, expand=True)

        # Create scrollable frame for navigation buttons
        canvas = tk.Canvas(nav_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(nav_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Configure canvas width to match scrollable frame
            canvas.configure(width=scrollable_frame.winfo_reqwidth())

        scrollable_frame.bind("<Configure>", configure_scroll_region)

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        menu_categories = self._menu_for_role()

        # Create category sections with buttons
        for category, items in menu_categories.items():
            # Category header
            category_label = ttk.Label(scrollable_frame, text=category, font=('Arial', 10, 'bold'))
            category_label.pack(fill=tk.X, pady=(10, 5), padx=5)

            # Category separator
            separator = ttk.Separator(scrollable_frame, orient='horizontal')
            separator.pack(fill=tk.X, pady=(0, 5), padx=5)

            # Add category buttons
            for item_name, item_command in items:
                ttk.Button(scrollable_frame, text=item_name, command=item_command).pack(
                    fill=tk.X, pady=2, padx=10)

        # Pack the canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel)

    def create_sidebar(self, parent):
        """Create the navigation sidebar"""
        sidebar_frame = ttk.Frame(parent, width=250)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sidebar_frame.pack_propagate(False)

        # Title
        title_label = ttk.Label(sidebar_frame, text=_t("alumni.sidebar_title", default="Alumni System"), font=('Arial', 16, 'bold'))
        title_label.pack(pady=(0, 20))

        # User info
        user_frame = ttk.LabelFrame(sidebar_frame, text=_t("common.current_user", default="Current User"), padding=10)
        user_frame.pack(fill=tk.X, pady=(0, 20))

        display_name = (self.current_user.get('first_name')
                        or self.current_user.get('display_name')
                        or self.current_user.get('username')
                        or 'User')
        ttk.Label(user_frame, text=_t("common.welcome_user", default="Welcome, {name}!").format(name=display_name),
                 font=('Arial', 10, 'bold')).pack()
        ttk.Label(user_frame, text=_t("common.username_display", default="Username: {username}").format(username=self.current_user.get('username', ''))).pack()

        # Navigation menu
        self.create_navigation_menu(sidebar_frame)

    def create_status_bar(self):
        """Create status bar at the bottom"""
        self.status_bar = ttk.Label(self.root, text=_t('gui.learners.alumni.main.labels.ready', default="Ready"), relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_widgets(self):
        """Create the main GUI structure"""
        # Add return to main menu button at the top — only when there is a
        # menu/dashboard to go back to (i.e. not when an alumnus is logged in
        # and this is the primary portal window).
        if self.show_return_button:
            return_btn = ttk.Button(
                self.root,
                text=_t("common.return_to_main_menu", default="Return to Main Menu"),
                command=self.return_to_main_menu
            )
            return_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=10)

        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create left sidebar
        self.create_sidebar(main_frame)

        # Create main content area
        self.create_main_content(main_frame)

        # Create status bar
        self.create_status_bar()

    # ── what each person can open ──────────────────────────────────────
    def show_home(self):
        """Office staff land on the dashboard, alumni on their profile,
        students on their mentoring."""
        if self.who.is_staff_role:
            self.show_dashboard()
        elif self.who.alumni_id:
            self.show_my_profile()
        else:
            self.show_my_mentoring()

    def _community(self, name):
        """Screens from ``alumni_office_community`` (loaded when first used)."""
        def open_screen():
            try:
                from education_system.systems.university.domains.learners.interfaces.gui.alumni import (  # noqa: E501
                    alumni_office_community as screens,
                )
                getattr(screens, name)(self)
            except (ImportError, AttributeError):
                self.clear_content()
                ttk.Label(self.content_frame, text="This screen is not available yet.",
                          padding=30).pack()
        return open_screen

    def show_my_mentoring(self):
        self._community("show_my_mentoring")()

    def _menu_for_role(self):
        """Menu sections for the signed-in person. Every rule re-checks
        permissions, so this decides what is shown, not what is allowed."""
        who = self.who
        office = who.is_office
        sections = {}

        def add(title, items):
            items = [(label, cmd) for label, cmd, allowed in items if allowed]
            if items:
                sections.setdefault(title, []).extend(items)

        add("👤 My alumni account", [
            ("My profile", self.show_my_profile, who.alumni_id),
            ("Privacy & directory listing", self.show_privacy, who.alumni_id),
            ("Keep in touch", self.show_keep_in_touch, who.alumni_id),
            ("My data", self.show_my_data, who.alumni_id),
            ("My giving", self._community("show_my_giving"), who.alumni_id),
            ("My chapters", self._community("show_my_chapters"), who.alumni_id),
            ("Mentoring", self._community("show_my_mentoring"),
             who.alumni_id or who.is_student),
        ])
        add("📋 Alumni office", [
            ("Alumni records", self.show_alumni_records, office),
            ("Data requests", self.show_data_requests, office),
            ("Newsletters", self.show_newsletters, office),
            ("Roles & audit", self.show_roles_audit, office),
        ])
        add("🌐 Directory & networking", [
            ("Alumni directory", self.show_directory, who.alumni_id or who.is_staff_role),
            ("Connection requests", self.show_connections, who.alumni_id),
            ("Business directory", self.show_business_directory,
             office or (who.alumni_id and self.has_permission('access_alumni_directory'))),
        ])
        add("💰 Giving", [("Gifts, Gift Aid & pledges", self._community("show_giving"),
                          who.is_fundraiser)])
        add("🏘 Chapters", [("Regional chapters", self._community("show_chapters"), office)])
        add("👥 Mentoring", [("Mentors, matches & concerns", self._community("show_mentoring"),
                             who.is_coordinator)])
        add("🛡 Moderation", [("Reports, stories & photos", self._community("show_moderation"),
                              who.is_moderator)])
        self._add_community_features(add, office, bool(who.alumni_id))
        add("⚙️ Reports & integration", [
            ("Generate reports", self.show_generate_reports, office),
            ("System analytics", self.show_analytics, office),
            ("Email manager", self.open_email_manager_gui, office),
            ("Finance system", self.open_finance_gui, office),
            ("Student validation", self.show_student_validation, office),
            ("Finance status check", self.show_finance_check, office),
        ])
        return sections

    def _add_community_features(self, add, office, alumnus):
        """The existing community screens, for alumni (as their permissions
        allow) and the office."""
        member = office or alumnus
        perm = self.has_permission
        add("💬 Community", [
            ("Alumni forum", self.show_forum, member),
            ("Search forum posts", self.show_search_forum_posts, member),
            ("My forum posts", self.show_my_forum_posts, alumnus),
            ("Alumni stories", self.show_stories, member),
            ("Photo gallery", self.show_photo_gallery, member),
        ])
        add("🎉 Events", [
            ("View events", self.show_view_events, member),
            ("Create event", self.show_create_event, office),
            ("Event check-in", self.show_event_checkin, office),
            ("Class reunions", self.show_class_reunions, office or (
                alumnus and perm('manage_social_features'))),
        ])
        add("💼 Careers", [
            ("Job board", self.show_job_board, office or (alumnus and perm('view_job_board'))),
            ("Post a job", self.show_post_job, office or (alumnus and perm('post_jobs'))),
            ("Career counselling", self.show_career_counseling,
             office or (alumnus and perm('schedule_career_counseling'))),
        ])
        add("🏆 Engagement", [
            ("Leaderboard", self.show_leaderboard, member),
            ("My badges", self.show_my_badges, alumnus),
            ("Recommendations", self.show_recommendations, alumnus),
        ])

    def has_permission(self, permission):
        """Check if current user has permission"""
        # An empty/blank permission name is a caller bug, not an all-access
        # pass — treat it as a denial rather than granting everything.
        if not permission:
            return False
        if getattr(self, "who", None) is not None and self.who.is_office:
            return True
        perms = (self.current_user or {}).get('permissions', [])
        return permission in perms or 'admin' in perms

    def open_email_manager_gui(self):
        """Open email manager GUI"""
        try:
            from education_system.systems.university.shell.gui.email.email_gui import EmailManagerGUI
            email_window = tk.Toplevel(self.root)
            email_window.title(_t("alumni.nav.items.email_manager", default="Email Manager"))
            email_window.geometry("800x600")
            email_gui = EmailManagerGUI(email_window, auth=self.auth)
        except ImportError:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("alumni.errors.email_manager_not_available", default="Email Manager GUI not available"))
        except (tk.TclError, RuntimeError) as e:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("alumni.errors.email_manager_error", default="Error opening Email Manager: {error}").format(error=e))

    def open_finance_gui(self):
        """Open finance management GUI"""
        try:
            from education_system.systems.university.domains.finance.interfaces.gui.finance import FinanceGUI
            finance_window = tk.Toplevel(self.root)
            finance_window.title(_t("alumni.nav.items.finance_system", default="Finance Management"))
            finance_window.geometry("1000x700")
            finance_gui = FinanceGUI(finance_window, auth=self.auth)
        except ImportError:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("alumni.errors.finance_gui_not_available", default="Finance GUI not available"))
        except (tk.TclError, RuntimeError) as e:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("alumni.errors.finance_gui_error", default="Error opening Finance GUI: {error}").format(error=e))

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Check if this is a child window (Toplevel) or standalone (Tk)
            root_widget = self.root if hasattr(self, 'root') else self.master
            if isinstance(root_widget, tk.Toplevel):
                # Just close the child window
                root_widget.destroy()
            else:
                # Running standalone, need to create main GUI
                root_widget.destroy()
                from education_system.systems.university.shell.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except (tk.TclError, ImportError, RuntimeError) as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.config(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")

def main(auth=None):
    """Main function to run the Alumni Management GUI application"""
    try:
        # Create the main window
        root = tk.Tk()

        # Set window properties
        root.title(_t("alumni.window_title", default="Enhanced Alumni Management System"))
        root.geometry("1400x900")
        root.minsize(1200, 800)

        # Center the window on screen
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        # Create the application instance with authentication
        app = AlumniGUIApp(root, auth=auth)

        # Configure window close behavior
        def on_closing():
            if messagebox.askokcancel(_t("alumni.dialogs.quit_title", default="Quit"),
                                     _t("alumni.dialogs.quit_message", default="Do you want to quit the Alumni Management System?")):
                root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)

        # Start the GUI event loop
        root.mainloop()

    except (tk.TclError, RuntimeError) as e:
        print(f"Error starting Alumni Management System: {e}")
        messagebox.showerror(_t("alumni.dialogs.startup_error", default="Startup Error"),
                           _t("alumni.dialogs.startup_failed", default="Failed to start the application:\n{error}").format(error=str(e)))


def launch_alumni_gui(auth=None):
    """Launch Alumni GUI for integration with university system"""
    main(auth=auth)


if __name__ == "__main__":
    main()
