"""Student role-based dashboard tab."""

import tkinter as tk
from tkinter import ttk
import logging

logger = logging.getLogger(__name__)


def _launch_profile(parent, auth):
    """Launch Student Profile Center."""
    from education_system.university_system.modules.domain.student_affairs.gui.student_profile.profile_gui import StudentProfileGUI
    StudentProfileGUI(parent, auth=auth)


def _launch_security(parent, auth):
    """Launch Account Security Dashboard."""
    from education_system.university_system.modules.domain.student_affairs.gui.account_security.security_gui import AccountSecurityGUI
    AccountSecurityGUI(parent, auth=auth)


def _launch_notifications(parent, auth):
    """Launch Notification Preferences."""
    from education_system.university_system.modules.domain.student_affairs.gui.notification_prefs.notification_prefs_gui import NotificationPrefsGUI
    NotificationPrefsGUI(parent, auth=auth)


def _launch_grades_breakdown(parent, auth):
    """Launch Grades Breakdown by Module."""
    from education_system.university_system.modules.domain.academics.academic_progress.gui.grades_breakdown_gui import GradesBreakdownGUI
    GradesBreakdownGUI(parent, auth=auth)


def _launch_degree_progress(parent, auth):
    """Launch Degree Progress Tracker."""
    from education_system.university_system.modules.domain.academics.academic_progress.gui.degree_progress_gui import DegreeProgressGUI
    DegreeProgressGUI(parent, auth=auth)


def _launch_course_catalog(parent, auth):
    """Launch Course Catalog & Registration."""
    from education_system.university_system.modules.domain.academics.gui.course_catalog.course_catalog_gui import CourseCatalogGUI
    CourseCatalogGUI(parent, auth=auth)


def _launch_gpa_calculator(parent, auth):
    """Launch What-If GPA Calculator."""
    from education_system.university_system.modules.domain.academics.academic_progress.gui.gpa_calculator_gui import GPACalculatorGUI
    GPACalculatorGUI(parent, auth=auth)


def _launch_messaging(parent, auth):
    """Launch Student Messaging Hub."""
    from education_system.university_system.modules.domain.student_affairs.gui.messaging_hub.messaging_hub_gui import MessagingHubGUI
    MessagingHubGUI(parent, auth=auth)


def _launch_forums(parent, auth):
    """Launch Course Discussion Forums."""
    from education_system.university_system.modules.domain.academics.gui.course_forums.course_forums_gui import CourseForumsGUI
    CourseForumsGUI(parent, auth=auth)


def _launch_finance(parent, auth):
    """Launch Student Financial Dashboard."""
    from education_system.university_system.modules.domain.finance.gui.student_finance.student_finance_gui import StudentFinanceGUI
    StudentFinanceGUI(parent, auth=auth)


def _launch_help_center(parent, auth):
    """Launch Integrated Help Center."""
    from education_system.university_system.modules.domain.student_affairs.gui.help_center.help_center_gui import HelpCenterGUI
    HelpCenterGUI(parent, auth=auth)


def _launch_documents(parent, auth):
    """Launch Personal Document Center."""
    from education_system.university_system.modules.domain.student_affairs.gui.document_center.document_center_gui import DocumentCenterGUI
    DocumentCenterGUI(parent, auth=auth)


def _launch_feature(root, auth, feature_name):
    """Launch a student feature GUI.

    Each feature_map entry is (title, module_path, class_name, auth_style,
    creates_window):
      - `auth_style` — how the class accepts auth:
        'kwarg'      : cls(parent, auth=auth)
        'positional' : cls(parent, auth)   — required positional auth
        'none'       : cls(parent)         — class calls get_auth() itself
      - `creates_window` — True if the class builds its own Toplevel/Tk
        internally (pass `root` as parent, don't wrap in a Toplevel).
        False if the class expects to be handed a pre-made container
        window to populate (wrap in a Toplevel ourselves).

    Module paths reflect the 8.77.0 domain reorganisation (there is no
    `modules.domain.student_services` — those modules live under
    `student_affairs/`, `campus/`, `commerce/`, or `communications/`).
    """
    import tkinter as tk
    from tkinter import messagebox

    feature_map = {
        'roommate_finder': (
            'Roommate Finder',
            'education_system.university_system.modules.domain.student_affairs.roommate_finder.gui.roommate_gui',
            'RoommateFinderGUI', 'kwarg', True,
        ),
        'marketplace': (
            'Marketplace',
            'education_system.university_system.modules.domain.commerce.marketplace.gui.marketplace_gui',
            'MarketplaceGUI', 'kwarg', True,
        ),
        'lost_found': (
            'Lost & Found',
            'education_system.university_system.modules.domain.campus.lost_found.gui.lost_found_gui',
            'LostFoundGUI', 'kwarg', True,
        ),
        'campus_navigation': (
            'Campus Navigation',
            'education_system.university_system.modules.domain.campus.campus_navigation.gui.navigation_gui',
            'NavigationGUI', 'none', True,
        ),
        'social_matching': (
            'Social Matching',
            'education_system.university_system.modules.domain.student_affairs.social_matching.gui.social_matching_gui',
            'SocialMatchingGUI', 'none', True,
        ),
        'mail_post': (
            'Mail & Post',
            'education_system.university_system.modules.domain.communications.mail.gui.mail_post_gui',
            'MailPostGUI', 'positional', True,
        ),
        'printing_services': (
            'Printing Services',
            'education_system.university_system.modules.domain.campus.printing.gui.printing_gui',
            'PrintingServicesGUI', 'none', True,
        ),
        'study_room_booking': (
            'Study Room Booking',
            'education_system.university_system.modules.domain.campus.study_rooms.gui.study_room_gui',
            'StudyRoomBookingGUI', 'none', True,
        ),
        'student_id': (
            'Student ID Card',
            'education_system.university_system.modules.domain.student_affairs.student_id.gui.student_id_gui',
            'StudentIDGUI', 'none', True,
        ),
        'achievement_badges': (
            'Achievement Badges',
            'education_system.university_system.modules.domain.student_affairs.achievement_badges.gui.achievement_badge_gui',
            'AchievementBadgeGUI', 'kwarg', True,
        ),
        'wellness_hub': (
            'Wellness Hub',
            'education_system.university_system.modules.domain.student_affairs.wellness.gui.wellness_gui',
            'WellnessGUI', 'kwarg', True,
        ),
        'todo_app': (
            'Todo App',
            'education_system.university_system.modules.shared.gui.tools.todo_app_gui',
            'TodoApp', 'none', False,
        ),
    }

    if feature_name not in feature_map:
        messagebox.showerror("Error", f"Unknown feature: {feature_name}")
        return

    title, module_path, class_name, auth_style, creates_window = feature_map[feature_name]
    try:
        module = __import__(module_path, fromlist=[class_name])
        gui_class = getattr(module, class_name)

        if creates_window:
            # Class builds its own Toplevel/Tk from the parent — pass root
            # directly so we don't end up with an extra empty window.
            target = root
        else:
            # Class expects a pre-made container window to populate.
            target = tk.Toplevel(root)
            target.title(title)
            target.geometry("1000x700")

        if auth_style == 'kwarg':
            gui_class(target, auth=auth)
        elif auth_style == 'positional':
            gui_class(target, auth)
        else:
            gui_class(target)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open {title}: {e}")


def create_student_dashboard(parent_frame, auth, service):
    """Create the student-specific dashboard content.

    Args:
        parent_frame: The ttk.Frame to populate.
        auth: Auth manager instance.
        service: DashboardService instance.
    """
    student_id = auth.current_user.get('username', '') if auth.current_user else ''
    data = service.get_student_dashboard_data(student_id)

    canvas = tk.Canvas(parent_frame)
    scrollbar = ttk.Scrollbar(parent_frame, orient=tk.VERTICAL, command=canvas.yview)
    scrollable = ttk.Frame(canvas)

    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Bind canvas resize to stretch scrollable frame to full width
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Welcome
    ttk.Label(scrollable, text=f"Welcome, {student_id}",
              font=('Arial', 14, 'bold')).pack(anchor="w", padx=15, pady=(15, 5))

    # Quick Actions button bar (4-column grid so buttons are never clipped)
    actions_frame = ttk.LabelFrame(scrollable, text="Quick Actions", padding="5")
    actions_frame.pack(fill=tk.X, padx=15, pady=5)

    root = parent_frame.winfo_toplevel()

    actions_grid = ttk.Frame(actions_frame)
    actions_grid.pack(fill=tk.X)
    for col in range(4):
        actions_grid.columnconfigure(col, weight=1)

    buttons = [
        ("My Profile", lambda: _launch_profile(root, auth)),
        ("Account Security", lambda: _launch_security(root, auth)),
        ("Notifications", lambda: _launch_notifications(root, auth)),
        ("Grades Breakdown", lambda: _launch_grades_breakdown(root, auth)),
        ("Degree Progress", lambda: _launch_degree_progress(root, auth)),
        ("Course Catalog", lambda: _launch_course_catalog(root, auth)),
        ("GPA Calculator", lambda: _launch_gpa_calculator(root, auth)),
        ("Messages", lambda: _launch_messaging(root, auth)),
        ("Discussion Forums", lambda: _launch_forums(root, auth)),
        ("Finances", lambda: _launch_finance(root, auth)),
        ("Help Center", lambda: _launch_help_center(root, auth)),
        ("Documents", lambda: _launch_documents(root, auth)),
        ("Roommate Finder", lambda: _launch_feature(root, auth, 'roommate_finder')),
        ("Marketplace", lambda: _launch_feature(root, auth, 'marketplace')),
        ("Lost & Found", lambda: _launch_feature(root, auth, 'lost_found')),
        ("Campus Navigation", lambda: _launch_feature(root, auth, 'campus_navigation')),
        ("Social Matching", lambda: _launch_feature(root, auth, 'social_matching')),
        ("Mail & Post", lambda: _launch_feature(root, auth, 'mail_post')),
        ("Printing Services", lambda: _launch_feature(root, auth, 'printing_services')),
        ("Study Room Booking", lambda: _launch_feature(root, auth, 'study_room_booking')),
        ("Student ID Card", lambda: _launch_feature(root, auth, 'student_id')),
        ("Achievement Badges", lambda: _launch_feature(root, auth, 'achievement_badges')),
        ("Wellness Hub", lambda: _launch_feature(root, auth, 'wellness_hub')),
        ("Todo App", lambda: _launch_feature(root, auth, 'todo_app')),
    ]
    for i, (label, cmd) in enumerate(buttons):
        ttk.Button(actions_grid, text=label, command=cmd).grid(
            row=i // 4, column=i % 4, padx=3, pady=2, sticky="ew"
        )

    # GPA Card
    gpa_frame = ttk.LabelFrame(scrollable, text="Academic Summary", padding="10")
    gpa_frame.pack(fill=tk.X, padx=15, pady=5)

    gpa_text = f"{data['gpa']:.2f}" if data['gpa'] is not None else "N/A"
    ttk.Label(gpa_frame, text=f"Current GPA: {gpa_text}",
              font=('Arial', 12, 'bold')).pack(anchor="w")
    ttk.Label(gpa_frame, text=f"Total Credits: {data['total_credits']}").pack(anchor="w")
    ttk.Label(gpa_frame, text=f"Enrolled Modules: {len(data['enrolled_courses'])}").pack(anchor="w")

    # Enrolled Modules
    courses_frame = ttk.LabelFrame(scrollable, text="Enrolled Modules", padding="10")
    courses_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['enrolled_courses']:
        cols = ('code', 'name', 'type')
        tree = ttk.Treeview(courses_frame, columns=cols, show='headings', height=min(8, len(data['enrolled_courses'])))
        tree.heading('code', text='Code')
        tree.heading('name', text='Module Name')
        tree.heading('type', text='Type')
        tree.column('code', width=120)
        tree.column('name', width=300)
        tree.column('type', width=100)
        for c in data['enrolled_courses']:
            tree.insert('', tk.END, values=(
                c.get('module_code', ''),
                c.get('module_name', ''),
                (c.get('module_type', '') or '').upper()
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(courses_frame, text="No modules enrolled.").pack(anchor="w")

    # Upcoming Assignments
    assign_frame = ttk.LabelFrame(scrollable, text="Upcoming Assignments", padding="10")
    assign_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['upcoming_assignments']:
        cols = ('title', 'module', 'due_date')
        tree = ttk.Treeview(assign_frame, columns=cols, show='headings',
                            height=min(5, len(data['upcoming_assignments'])))
        tree.heading('title', text='Title')
        tree.heading('module', text='Module')
        tree.heading('due_date', text='Due Date')
        tree.column('title', width=250)
        tree.column('module', width=120)
        tree.column('due_date', width=120)
        for a in data['upcoming_assignments']:
            tree.insert('', tk.END, values=(
                a.get('title', ''),
                a.get('module_code', ''),
                a.get('due_date', '')
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(assign_frame, text="No upcoming assignments.").pack(anchor="w")

    # Office Hour Bookings
    oh_frame = ttk.LabelFrame(scrollable, text="Office Hour Bookings", padding="10")
    oh_frame.pack(fill=tk.X, padx=15, pady=5)

    if data['office_hour_bookings']:
        cols = ('instructor', 'day', 'time', 'location', 'date')
        tree = ttk.Treeview(oh_frame, columns=cols, show='headings',
                            height=min(4, len(data['office_hour_bookings'])))
        tree.heading('instructor', text='Instructor')
        tree.heading('day', text='Day')
        tree.heading('time', text='Time')
        tree.heading('location', text='Location')
        tree.heading('date', text='Booking Date')
        tree.column('instructor', width=120)
        tree.column('day', width=80)
        tree.column('time', width=120)
        tree.column('location', width=120)
        tree.column('date', width=100)
        for b in data['office_hour_bookings']:
            tree.insert('', tk.END, values=(
                b.get('instructor_id', ''),
                b.get('day_of_week', ''),
                f"{b.get('start_time', '')} - {b.get('end_time', '')}",
                b.get('location', ''),
                b.get('booking_date', '')
            ))
        tree.pack(fill=tk.X)
    else:
        ttk.Label(oh_frame, text="No upcoming office hour bookings.").pack(anchor="w")

    # TA Assignments
    if data['ta_assignments']:
        ta_frame = ttk.LabelFrame(scrollable, text="My TA Assignments", padding="10")
        ta_frame.pack(fill=tk.X, padx=15, pady=5)

        cols = ('module', 'role', 'hours')
        tree = ttk.Treeview(ta_frame, columns=cols, show='headings',
                            height=min(3, len(data['ta_assignments'])))
        tree.heading('module', text='Module')
        tree.heading('role', text='Role')
        tree.heading('hours', text='Hours/Week')
        tree.column('module', width=150)
        tree.column('role', width=100)
        tree.column('hours', width=100)
        for t in data['ta_assignments']:
            tree.insert('', tk.END, values=(
                t.get('module_code', ''),
                t.get('role_type', ''),
                t.get('hours_per_week', '')
            ))
        tree.pack(fill=tk.X)

    # --- Embedded Summary Widgets ---
    try:
        from education_system.university_system.modules.shared.gui.main.dashboard.student_widgets import (
            create_grades_summary_widget,
            create_degree_progress_widget,
            create_gpa_whatif_widget,
            create_payment_alerts_widget,
        )

        create_grades_summary_widget(scrollable, student_id)
        create_degree_progress_widget(scrollable, student_id)
        create_gpa_whatif_widget(
            scrollable, student_id,
            launch_callback=lambda: _launch_gpa_calculator(root, auth),
        )
        create_payment_alerts_widget(scrollable, student_id)
    except Exception as e:
        logger.error(f"Error loading student dashboard widgets: {e}")
