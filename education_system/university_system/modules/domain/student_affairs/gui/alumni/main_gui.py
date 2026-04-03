import tkinter as tk
from education_system.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import mixin classes using relative imports to avoid circular dependency
from education_system.university_system.modules.domain.student_affairs.gui.alumni.dashboard import DashboardMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.alumni_crud import AlumniCRUDMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.directory import DirectoryMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.business_directory import BusinessDirectoryMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.events import EventsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.forum import ForumMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.stories_photos import StoriesPhotosMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.donations import DonationsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.reports import ReportsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.chapters import ChaptersMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.mentorship import MentorshipMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.jobs_career import JobsCareerMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.reunions import ReunionsMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.gamification import GamificationMixin
from education_system.university_system.modules.domain.student_affairs.gui.alumni.notifications import NotificationsMixin

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import the original functions - backward compatibility
try:
    from education_system.university_system.modules.domain.student_affairs.services.alumni_management import (
        init_alumni_db, register_alumni, view_alumni, update_alumni,
        view_events, create_enhanced_event, event_check_in_system,
        record_donation, view_donations, setup_mentorship, view_mentorships,
        search_alumni_directory, view_connection_requests, manage_business_directory,
        create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
        schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
        view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
        manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
        generate_alumni_report, set_auth, setup_alumni_permissions,
        smart_mentorship_matching, generate_engagement_recommendations,
        create_alumni_story, view_alumni_stories, get_connection
    )
except ImportError as e:
    import_error_details = str(e)
    print(f"Warning: Could not import some functions: {e}")
    # Define fallback functions
    def placeholder_function(*args, **kwargs):
        func_name = kwargs.get('_func_name', 'Unknown function')
        messagebox.showerror(
            "Module Import Error",
            f"The alumni management module could not be loaded.\n\n"
            f"Function: {func_name}\n"
            f"Error: {import_error_details}\n\n"
            f"Please ensure all required dependencies are installed:\n"
            f"• university_system.alumni module\n"
            f"• All database schema requirements\n\n"
            f"Contact your system administrator for assistance."
        )

    # Assign placeholder to missing functions
    register_alumni = placeholder_function
    view_alumni = placeholder_function



class AlumniGUIApp(
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
    def __init__(self, root, auth=None):
        self.root = root
        self.root.title(_t("alumni.window_title", default="Enhanced Alumni Management System"))
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')

        # Set authentication
        self.auth = auth
        if self.auth and hasattr(self.auth, 'current_user'):
            self.current_user = self.auth.current_user
        else:
            # Fallback to mock authentication for demo
            self.current_user = {
                'id': 1,
                'username': 'admin',
                'first_name': 'Administrator',
                'permissions': ['manage_alumni', 'view_alumni', 'manage_events', 'send_newsletters', 'admin']
            }

        # Initialize database and permissions
        try:
            init_alumni_db()
            setup_alumni_permissions()
        except sqlite3.Error as e:
            messagebox.showerror(_t("alumni.errors.database_error", default="Database Error"),
                               _t("alumni.errors.database_init_failed", default="Failed to initialize database: {error}").format(error=e))

        # Set authentication for backend functions
        try:
            from alumni_management import auth as backend_auth
            backend_auth.current_user = self.current_user
        except (ImportError, AttributeError):
            pass

        self.create_widgets()
        self.show_dashboard()
        self._photo_file_paths: list[str] = []
        self._event_lookup: dict[str, int] = {}
        self._photo_storage_dir = Path(paths.DATA_DIR) / "alumni_photos"
        self._photo_storage_dir.mkdir(parents=True, exist_ok=True)

    def _current_user_id(self):
        """Return current user's identifier for auditing."""
        if self.current_user and isinstance(self.current_user, dict):
            return str(self.current_user.get('username') or self.current_user.get('id') or 'gui_user')
        return 'gui_user'

    def _format_alumni_row(self, row):
        """Format alumni row tuple for treeview display."""
        if not isinstance(row, dict):
            row = dict(row)
        full_name = " ".join(filter(None, [row.get('first_name'), row.get('middle_name'), row.get('last_name')])).strip()
        if not full_name:
            full_name = row.get('full_name') or row.get('alumni_id', '')
        status = 'Active' if row.get('privacy_level', 1) else 'Hidden'
        return (
            row.get('alumni_id') or row.get('student_id'),
            full_name,
            row.get('graduation_year') or '',
            row.get('degree_earned') or row.get('course') or '',
            row.get('current_employer') or '',
            row.get('email_address') or row.get('email') or '',
            status
        )

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
        dashboard_btn = ttk.Button(parent, text=_t("alumni.dashboard", default="Dashboard"), command=self.show_dashboard)
        dashboard_btn.pack(fill=tk.X, pady=(0, 10))

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

        # Menu categories with their functions
        menu_categories = {
            "📋 " + _t("alumni.nav.categories.alumni_management", default="Alumni Management"): [
                (_t("alumni.nav.items.register_new_alumni", default="Register New Alumni"), self.show_register_alumni, 'manage_alumni'),
                (_t("alumni.nav.items.view_alumni_records", default="View Alumni Records"), self.show_view_alumni, 'view_alumni'),
                (_t("alumni.nav.items.update_alumni_record", default="Update Alumni Record"), self.show_update_alumni, 'manage_alumni'),
                (_t("alumni.nav.items.alumni_directory", default="Alumni Directory"), self.show_alumni_directory, 'access_alumni_directory')
            ],
            "🌐 " + _t("alumni.nav.categories.networking", default="Networking"): [
                (_t("alumni.nav.items.directory_search", default="Alumni Directory Search"), self.show_directory_search, 'access_alumni_directory'),
                (_t("alumni.nav.items.connection_requests", default="Connection Requests"), self.show_connections, 'access_alumni_directory'),
                (_t("alumni.nav.items.business_directory", default="Business Directory"), self.show_business_directory, 'access_alumni_directory'),
                (_t("alumni.nav.items.regional_chapters", default="Regional Chapters"), self.show_regional_chapters, None)
            ],
            "💬 " + _t("alumni.nav.categories.communication", default="Communication"): [
                (_t("alumni.nav.items.create_newsletter", default="Create Newsletter"), self.show_create_newsletter, 'send_newsletters'),
                (_t("alumni.nav.items.alumni_forum", default="Alumni Forum"), self.show_forum, 'access_alumni_directory'),
                (_t("alumni.nav.items.create_story", default="Create Story"), self.show_create_story, None),
                (_t("alumni.nav.items.alumni_stories", default="Alumni Stories"), self.show_stories, None),
                (_t("alumni.nav.items.search_forum_posts", default="Search Forum Posts"), self.show_search_forum_posts, None),
                (_t("alumni.nav.items.my_forum_posts", default="My Forum Posts"), self.show_my_forum_posts, None),
                (_t("alumni.nav.items.moderate_forum", default="Moderate Forum"), self.show_moderate_forum_posts, 'moderate_forum'),
                (_t("alumni.nav.items.photo_gallery", default="Photo Gallery"), self.show_photo_gallery, None)
            ],
            "🎉 " + _t("alumni.nav.categories.events", default="Events"): [
                (_t("alumni.nav.items.create_event", default="Create Event"), self.show_create_event, 'manage_events_advanced'),
                (_t("alumni.nav.items.view_events", default="View Events"), self.show_view_events, 'view_events'),
                (_t("alumni.nav.items.event_checkin", default="Event Check-in"), self.show_event_checkin, 'manage_events_advanced'),
                (_t("alumni.nav.items.class_reunions", default="Class Reunions"), self.show_class_reunions, 'manage_social_features')
            ],
            "💼 " + _t("alumni.nav.categories.career_services", default="Career Services"): [
                (_t("alumni.nav.items.job_board", default="Job Board"), self.show_job_board, 'view_job_board'),
                (_t("alumni.nav.items.post_job", default="Post Job"), self.show_post_job, 'post_jobs'),
                (_t("alumni.nav.items.career_counseling", default="Career Counseling"), self.show_career_counseling, 'schedule_career_counseling')
            ],
            "💰 " + _t("alumni.nav.categories.fundraising", default="Fundraising"): [
                (_t("alumni.nav.items.record_donation", default="Record Donation"), self.show_record_donation, 'make_donation'),
                (_t("alumni.nav.items.view_donations", default="View Donations"), self.show_view_donations, 'view_donations'),
                (_t("alumni.nav.items.donor_recognition", default="Donor Recognition"), self.show_donor_recognition, 'manage_campaigns'),
                (_t("alumni.nav.items.fundraising_campaigns", default="Fundraising Campaigns"), self.show_campaigns, 'manage_campaigns')
            ],
            "👥 " + _t("alumni.nav.categories.mentorship", default="Mentorship"): [
                (_t("alumni.nav.items.setup_mentorship", default="Setup Mentorship"), self.show_setup_mentorship, 'manage_mentorships'),
                (_t("alumni.nav.items.view_mentorships", default="View Mentorships"), self.show_view_mentorships, 'view_mentorships'),
                (_t("alumni.nav.items.smart_matching", default="Smart Matching"), self.show_smart_matching, 'manage_ai_features')
            ],
            "🏆 " + _t("alumni.nav.categories.engagement", default="Engagement"): [
                (_t("alumni.nav.items.leaderboard", default="Leaderboard"), self.show_leaderboard, None),
                (_t("alumni.nav.items.my_badges", default="My Badges"), self.show_my_badges, None),
                (_t("alumni.nav.items.recommendations", default="Recommendations"), self.show_recommendations, None)
            ],
            "⚙️ " + _t("alumni.nav.categories.settings_reports", default="Settings & Reports"): [
                (_t("alumni.nav.items.directory_settings", default="Directory Settings"), self.show_directory_settings, None),
                (_t("alumni.nav.items.generate_reports", default="Generate Reports"), self.show_generate_reports, 'generate_reports'),
                (_t("alumni.nav.items.system_analytics", default="System Analytics"), self.show_analytics, 'view_analytics')
            ],
            "🔗 " + _t("alumni.nav.categories.integration_services", default="Integration Services"): [
                (_t("alumni.nav.items.email_manager", default="Email Manager"), self.open_email_manager_gui, None),
                (_t("alumni.nav.items.finance_system", default="Finance System"), self.open_finance_gui, None),
                (_t("alumni.nav.items.student_validation", default="Student Validation"), self.show_student_validation, None),
                (_t("alumni.nav.items.finance_status_check", default="Finance Status Check"), self.show_finance_check, None)
            ]
        }

        # Create category sections with buttons
        for category, items in menu_categories.items():
            # Category header
            category_label = ttk.Label(scrollable_frame, text=category, font=('Arial', 10, 'bold'))
            category_label.pack(fill=tk.X, pady=(10, 5), padx=5)

            # Category separator
            separator = ttk.Separator(scrollable_frame, orient='horizontal')
            separator.pack(fill=tk.X, pady=(0, 5), padx=5)

            # Add category buttons
            for item_name, item_command, permission in items:
                if permission is None or self.has_permission(permission):
                    btn = ttk.Button(scrollable_frame, text=item_name, command=item_command)
                    btn.pack(fill=tk.X, pady=2, padx=10)

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

        ttk.Label(user_frame, text=_t("common.welcome_user", default="Welcome, {name}!").format(name=self.current_user['first_name']),
                 font=('Arial', 10, 'bold')).pack()
        ttk.Label(user_frame, text=_t("common.username_display", default="Username: {username}").format(username=self.current_user['username'])).pack()

        # Navigation menu
        self.create_navigation_menu(sidebar_frame)

    def create_status_bar(self):
        """Create status bar at the bottom"""
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_widgets(self):
        """Create the main GUI structure"""
        # Add return to main menu button at the top
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

    def has_permission(self, permission):
        """Check if current user has permission"""
        if not permission:
            return True
        return permission in self.current_user.get('permissions', []) or 'admin' in self.current_user.get('permissions', [])

    def open_email_manager_gui(self):
        """Open email manager GUI"""
        try:
            from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
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
            from education_system.university_system.modules.domain.finance.gui.finance import FinanceGUI
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
                from education_system.university_system.modules.shared.gui.main import UnifiedManagementGUI
                app = UnifiedManagementGUI(self.auth)
                app.run()
        except (tk.TclError, ImportError, RuntimeError) as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.config(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")

def placeholder_function(*args, **kwargs):
    func_name = kwargs.get('_func_name', 'Unknown function')
    messagebox.showerror(
    "Module Import Error",
    f"The alumni management module could not be loaded.\n\n"
    f"Function: {func_name}\n"
    f"Error: {import_error_details}\n\n"
    f"Please ensure all required dependencies are installed:\n"
    f"• university_system.alumni module\n"
    f"• All database schema requirements\n\n"
    f"Contact your system administrator for assistance."
    )

# Assign placeholder to missing functions
register_alumni = placeholder_function
view_alumni = placeholder_function
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

