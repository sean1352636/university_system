"""Student dashboard — the single student-facing home screen.

This is the merge (2026-08-22) of what used to be two separate, competing
student dashboards:

* ``shell/gui/main/dashboard/student_dashboard.py`` — the role tab shown by
  ``show_integrated_dashboard`` when the logged-in user's role is ``student``.
  It owned the launcher grid, the enrolled-modules / assignments / office-hours
  tables and the four embedded summary widgets.
* ``domains/academics/interfaces/gui/student_dashboard/`` — ``StudentDashboardPortal``,
  reached from a "Student Dashboard" sidebar button. It owned the welcome
  header, the stat-card row, Today's Schedule, Recent Grades and the mitigating
  circumstances summary.

Neither was complete and the two disagreed about how to resolve the student's
identity, so a student saw different numbers depending on which one they opened.
Everything worth keeping now lives here; the domains package and the sidebar
button are gone. The only way in is the "My Dashboard" tab, which is built for
logged-in students only — see :func:`create_student_dashboard`.

Several queries carried over from the portal were silently broken (they named
columns and tables that do not exist and were swallowed by bare ``except``
blocks, so the panels rendered empty rather than erroring). They are corrected
against the live schema here — see the comments on each fetch helper.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Ported from the retired ``student_dashboard/common_imports.py`` so the stat
# cards keep their colour language now that the domains package is gone.
COLORS = {
    'primary': '#2c3e50',
    'secondary': '#34495e',
    'success': '#27ae60',
    'warning': '#f39c12',
    'danger': '#e74c3c',
    'info': '#3498db',
    'light': '#ecf0f1',
    'dark': '#2c3e50',
    'white': '#ffffff',
}


def _create_stat_card(parent, title, value, color='primary'):
    """A single headline-number card. Ported from the retired portal."""
    card = ttk.Frame(parent, relief='raised', borderwidth=2)
    ttk.Label(card, text=title, font=('Arial', 10)).pack(pady=(10, 5))
    ttk.Label(card, text=str(value), font=('Arial', 18, 'bold'),
              foreground=COLORS.get(color, COLORS['primary'])).pack(pady=(0, 10))
    return card


# ----------------------------------------------------------------------
# Identity
# ----------------------------------------------------------------------

def resolve_student_id(auth):
    """Return the *student number* for the logged-in user, or ``None``.

    The old role tab passed ``current_user['username']`` straight into queries
    that key on ``student_modules.student_id`` etc. That is the student number
    (e.g. ``1280801``), not the login name, and it only appeared to work
    because most seeded student logins happen to use their student number as
    their username. Accounts whose username differs — ``university.student``,
    the documented demo account, among them — got a dashboard of empty tables
    and no explanation.

    ``build_session_user`` already resolves ``student_id`` from the university
    ``users`` table, so prefer that and fall back to the username only as a
    guess. The caller must still confirm the id names a real ``students`` row
    before trusting it — see :func:`student_record_exists`.
    """
    user = getattr(auth, 'current_user', None)
    if not user:
        return None
    if not isinstance(user, dict):
        user = getattr(user, '__dict__', {}) or {}
    student_id = user.get('student_id') or user.get('username') or None
    return str(student_id) if student_id else None


def student_record_exists(student_id):
    """True when *student_id* names a row in ``students``.

    Used to tell "this account has no student record" apart from "this student
    has no data yet" — previously indistinguishable, both rendering as a page
    of empty tables.
    """
    if not student_id:
        return False
    try:
        from education_system.systems.university.infrastructure.database.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ? LIMIT 1",
                (student_id,),
            ).fetchone()
        return row is not None
    except Exception as exc:
        logger.warning("Could not verify student record for %r: %s", student_id, exc)
        # Unknown, not absent — don't accuse the account of being unlinked
        # because the database was unreachable.
        return True


def _display_name(auth):
    """Human name for the welcome line, never the raw login or student number."""
    user = getattr(auth, 'current_user', None) or {}
    if not isinstance(user, dict):
        user = getattr(user, '__dict__', {}) or {}
    name = (user.get('display_name') or user.get('full_name') or user.get('name'))
    if not name:
        first, last = user.get('first_name', ''), user.get('last_name', '')
        name = f"{first} {last}".strip()
    return name or user.get('username') or 'Student'


# ----------------------------------------------------------------------
# Scrolling
# ----------------------------------------------------------------------

def _bind_mousewheel(canvas, inner):
    """Wheel-scroll the dashboard canvas.

    Neither predecessor bound the wheel, so a page several screens tall could
    only be moved by dragging the scrollbar. Bound widget-locally (not
    ``bind_all``) and re-applied to new children on ``<Configure>``, matching
    the navigation panel's approach so the binding dies with the widget instead
    of leaking into the rest of the app.
    """
    def _on_wheel(event):
        try:
            delta = -1 if (getattr(event, 'num', None) == 5
                           or getattr(event, 'delta', 0) < 0) else 1
            canvas.yview_scroll(-delta, "units")
        except tk.TclError:
            pass
        return "break"

    def _bind_recursive(widget):
        try:
            if not getattr(widget, '_dash_wheel_bound', False):
                for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                    widget.bind(seq, _on_wheel, add="+")
                widget._dash_wheel_bound = True
            for child in widget.winfo_children():
                _bind_recursive(child)
        except tk.TclError:
            pass

    for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
        canvas.bind(seq, _on_wheel, add="+")
    canvas._dash_wheel_bound = True
    inner.bind('<Configure>', lambda _e: _bind_recursive(inner), add="+")
    _bind_recursive(inner)


# ----------------------------------------------------------------------
# Feature launchers
# ----------------------------------------------------------------------

def _safe_launch(title, fn):
    """Run a launcher, reporting failures instead of swallowing them.

    The direct ``_launch_*`` helpers had no error handling: a broken import
    raised into the Tk callback, which prints to stderr and leaves the button
    looking simply dead. ``_launch_feature`` already reported its failures;
    this gives the rest the same treatment.
    """
    try:
        fn()
    except Exception as exc:
        logger.exception("Failed to open %s", title)
        messagebox.showerror(
            _t('gui.shell.main.dashboard.student_dashboard.dialogs.error', default="Error"),
            f"Failed to open {title}: {exc}",
        )


def _launch_profile(parent, auth):
    """Launch Student Profile Center."""
    from education_system.systems.university.domains.pastoral.interfaces.gui.student_profile.profile_gui import StudentProfileGUI
    StudentProfileGUI(parent, auth=auth)


def _launch_security(parent, auth):
    """Launch Account Security Dashboard."""
    from education_system.systems.university.domains.pastoral.interfaces.gui.account_security.security_gui import AccountSecurityGUI
    AccountSecurityGUI(parent, auth=auth)


def _launch_notifications(parent, auth):
    """Launch Notification Preferences."""
    from education_system.systems.university.domains.pastoral.interfaces.gui.notification_prefs.notification_prefs_gui import NotificationPrefsGUI
    NotificationPrefsGUI(parent, auth=auth)


def _launch_grades_breakdown(parent, auth):
    """Launch Grades Breakdown by Module."""
    from education_system.systems.university.domains.assessment.interfaces.gui.academic_progress.grades_breakdown_gui import GradesBreakdownGUI
    GradesBreakdownGUI(parent, auth=auth)


def _launch_degree_progress(parent, auth):
    """Launch Degree Progress Tracker."""
    from education_system.systems.university.domains.assessment.interfaces.gui.academic_progress.degree_progress_gui import DegreeProgressGUI
    DegreeProgressGUI(parent, auth=auth)


def _launch_course_catalog(parent, auth):
    """Launch Course Catalog & Registration."""
    from education_system.systems.university.domains.academics.interfaces.gui.course_catalog.course_catalog_gui import CourseCatalogGUI
    CourseCatalogGUI(parent, auth=auth)


def _launch_gpa_calculator(parent, auth):
    """Launch What-If GPA Calculator."""
    from education_system.systems.university.domains.assessment.interfaces.gui.academic_progress.gpa_calculator_gui import GPACalculatorGUI
    GPACalculatorGUI(parent, auth=auth)


def _launch_messaging(parent, auth):
    """Launch the unified Email & Communications GUI."""
    from education_system.systems.university.shell.gui.email.email_gui.email_manager_main import EmailManagerGUI
    EmailManagerGUI(tk.Toplevel(parent), auth=auth)


def _launch_forums(parent, auth):
    """Launch Course Discussion Forums."""
    from education_system.systems.university.domains.academics.interfaces.gui.course_forums.course_forums_gui import CourseForumsGUI
    CourseForumsGUI(parent, auth=auth)


def _launch_finance(parent, auth):
    """Launch the main Finance GUI in a new window."""
    from education_system.systems.university.domains.finance.interfaces.gui.finance.finance_gui import FinanceGUI
    window = tk.Toplevel(parent)
    window.title(_t('gui.shell.main.dashboard.student_dashboard.windows.finance', default="Finance"))
    window.geometry("1280x800")
    window.minsize(1024, 640)
    FinanceGUI(window, auth=auth)


def _launch_roommate_finder(parent, auth):
    """Roommate Finder now lives inside Housing — open the Housing GUI.

    The user clicks "Find a Roommate" on the housing sidebar to reach it.
    """
    from education_system.systems.university.domains.operations.interfaces.gui.campus.housing.housing_accommodation_gui.main_gui import HousingGUI
    HousingGUI(parent=tk.Toplevel(parent), auth_instance=auth)


def _launch_help_center(parent, auth):
    """Launch Student Support (formerly Help Center)."""
    from education_system.systems.university.domains.pastoral.interfaces.gui.student_support import StudentSupportGUI
    StudentSupportGUI(tk.Toplevel(parent), auth_system=auth)


def _launch_documents(parent, auth):
    """Launch Personal Document Center."""
    from education_system.systems.university.domains.pastoral.interfaces.gui.document_center.document_center_gui import DocumentCenterGUI
    DocumentCenterGUI(parent, auth=auth)


def _launch_graduation(parent, auth):
    """Launch the Graduation Ceremony GUI (opens the student self-service tab)."""
    from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.graduation_ceremony_gui import GraduationCeremonyGUI
    GraduationCeremonyGUI(parent, auth=auth)


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
    feature_map = {
        'marketplace': (
            'Marketplace',
            'education_system.systems.university.plugins.campus_commerce.interfaces.gui.marketplace.marketplace_gui',
            'MarketplaceGUI', 'kwarg', True,
        ),
        'lost_found': (
            'Lost & Found',
            'education_system.systems.university.domains.operations.interfaces.gui.campus.lost_found.lost_found_gui',
            'LostFoundGUI', 'kwarg', True,
        ),
        'campus_navigation': (
            'Campus Navigation',
            'education_system.systems.university.domains.operations.interfaces.gui.campus.campus_navigation.navigation_gui',
            'NavigationGUI', 'none', True,
        ),
        'social_matching': (
            'Social Matching',
            'education_system.systems.university.domains.pastoral.interfaces.gui.social_matching.social_matching_gui',
            'SocialMatchingGUI', 'none', True,
        ),
        'mail_post': (
            'Mail & Post',
            'education_system.systems.university.domains.operations.interfaces.gui.communications.mail.mail_post_gui',
            'MailPostGUI', 'positional', True,
        ),
        'printing_services': (
            'Printing Services',
            'education_system.systems.university.domains.operations.interfaces.gui.campus.printing.printing_gui',
            'PrintingServicesGUI', 'none', True,
        ),
        'study_room_booking': (
            'Study Room Booking',
            'education_system.systems.university.domains.operations.interfaces.gui.campus.study_rooms.study_room_gui',
            'StudyRoomBookingGUI', 'none', True,
        ),
        'student_id': (
            'Student ID Card',
            'education_system.systems.university.domains.learners.interfaces.gui.student_id.student_id_gui',
            'StudentIDGUI', 'none', True,
        ),
        'achievement_badges': (
            'Achievement Badges',
            'education_system.systems.university.domains.pastoral.interfaces.gui.achievement_badges.achievement_badge_gui',
            'AchievementBadgeGUI', 'kwarg', True,
        ),
        'wellness_hub': (
            'Wellness Hub',
            'education_system.systems.university.domains.pastoral.interfaces.gui.wellbeing.wellness.wellness_gui',
            'WellnessGUI', 'kwarg', True,
        ),
        'todo_app': (
            'Todo App',
            'education_system.systems.university.shell.gui.tools.todo_app_gui',
            'TodoApp', 'none', False,
        ),
        'my_visa_status': (
            'My Visa Status',
            'education_system.systems.university.domains.governance.interfaces.gui.compliance.international_compliance.my_visa_status_gui',
            'MyVisaStatusGUI', 'none', True,
        ),
        'enrolment_letters': (
            'Status Letters',
            'education_system.systems.university.domains.pastoral.interfaces.gui.student_app.documentation.documentation_gui',
            'DocumentationGUI', 'kwarg', True,
        ),
    }

    if feature_name not in feature_map:
        messagebox.showerror(_t('gui.shell.main.dashboard.student_dashboard.dialogs.error', default="Error"), f"Unknown feature: {feature_name}")
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
        messagebox.showerror(_t('gui.shell.main.dashboard.student_dashboard.dialogs.error', default="Error"), f"Failed to open {title}: {e}")


# Quick actions inherited from the retired portal. These are features the main
# GUI already owns a launcher for, so route through it rather than duplicating
# the import/auth dance. ``main_gui`` is either the UnifiedManagementGUI
# instance or a zero-arg callable returning one (the student portal builds its
# backend GUI lazily — instantiating seven GUI managers — so it must not be
# resolved just to draw a button). Absent, these buttons are not rendered.
_MAIN_GUI_ACTIONS = [
    ("My Grades", 'show_grades'),
    ("My Timetable", 'show_student_timetable_gui'),
    ("Register for Modules", 'show_student_registration_gui'),
    ("My Exams", 'show_exam_scheduler_gui'),
    ("Library", 'show_library_management'),
    ("Financial Aid", 'show_financial_aid'),
    ("Mitigating Circumstances", 'show_mitigating_circumstances_gui'),
]


def _main_gui_action(main_gui, label, method_name):
    """Return a click handler for *method_name*, or ``None`` to skip the button.

    A resolver (``callable``) is never invoked here — the button is rendered
    optimistically and the GUI is built on first click.
    """
    if main_gui is None:
        return None
    if callable(main_gui):
        def _run():
            gui = main_gui()
            method = getattr(gui, method_name, None)
            if not callable(method):
                messagebox.showinfo(
                    _t('gui.shell.main.dashboard.student_dashboard.dialogs.unavailable', default="Unavailable"),
                    f"{label} is not available in this session.")
                return
            method()
        return lambda: _safe_launch(label, _run)
    method = getattr(main_gui, method_name, None)
    if not callable(method):
        return None
    return lambda: _safe_launch(label, method)


# ----------------------------------------------------------------------
# Data fetches ported from the portal (corrected against the live schema)
# ----------------------------------------------------------------------

def _fetch_gpa(conn, student_id):
    """Credit-weighted GPA.

    ``calculate_student_gpa`` unifies module_grades, assignment_submissions and
    grades in priority order, which is why the portal's number was the more
    trustworthy of the two. The old role tab derived GPA from
    ``assignment_submissions`` alone — a table holding two rows, both ungraded
    — so it read "N/A" for every student. This is the portal's source.
    """
    try:
        from education_system.systems.university.domains.assessment.domain.grading.grade_calculation import (
            calculate_student_gpa,
        )
        gpa, _credits, _detail = calculate_student_gpa(conn.cursor(), student_id)
        return f"{gpa:.2f}" if gpa is not None else "N/A"
    except Exception as exc:
        logger.debug("Could not fetch GPA: %s", exc)
        return "N/A"


def _fetch_enrolled_count(conn, student_id):
    """Modules the student is currently enrolled on."""
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM student_modules "
            "WHERE student_id = ? AND LOWER(status) = 'enrolled'",
            (student_id,),
        ).fetchone()
        return str(row[0] if row else 0)
    except Exception as exc:
        logger.debug("Could not fetch enrolled count: %s", exc)
        return "0"


def _fetch_upcoming_exam_count(conn, student_id):
    """Upcoming exams on the student's enrolled modules.

    The portal queried ``exams.exam_date``; the column is ``exams.date``. The
    mistake sat inside a bare ``except`` that fell through to a second broken
    query, so this card showed 0 for everyone regardless of the exam timetable.
    """
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM exams e "
            "JOIN student_modules sm ON e.module_code = sm.module_code "
            "WHERE sm.student_id = ? AND LOWER(sm.status) = 'enrolled' "
            "AND e.date >= date('now')",
            (student_id,),
        ).fetchone()
        return str(row[0] if row else 0)
    except Exception as exc:
        logger.debug("Could not fetch upcoming exams: %s", exc)
        return "0"


def _fetch_outstanding_fines(conn, student_id):
    """Unpaid library fines.

    The portal read a ``library_fines`` table that does not exist. The
    student-keyed fines live on ``library_accounts.fine_amount``.
    """
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(fine_amount), 0) FROM library_accounts "
            "WHERE student_id = ? AND COALESCE(fine_amount, 0) > 0 "
            "AND LOWER(COALESCE(status, '')) != 'paid'",
            (student_id,),
        ).fetchone()
        total = float(row[0]) if row and row[0] else 0.0
        return f"£{total:.2f}"
    except Exception as exc:
        logger.debug("Could not fetch outstanding fines: %s", exc)
        return "£0.00"


def _fetch_todays_schedule(conn, student_id):
    """Today's classes.

    The portal selected ``ms.day`` and ``ms.room`` from ``module_schedule``;
    the columns are ``day_of_week`` and ``room_id``. Every row raised and was
    swallowed, so the panel always read "No classes scheduled for today."
    """
    try:
        today = datetime.now().strftime('%A')
        return conn.execute(
            "SELECT ms.start_time, ms.end_time, ms.module_code, "
            "       COALESCE(m.module_name, ms.module_code) AS module_name, "
            "       ms.room_id, ms.session_type "
            "FROM module_schedule ms "
            "JOIN student_modules sm ON ms.module_code = sm.module_code "
            "LEFT JOIN modules m ON m.module_code = ms.module_code "
            "WHERE sm.student_id = ? AND LOWER(sm.status) = 'enrolled' "
            "AND ms.day_of_week = ? "
            "ORDER BY ms.start_time",
            (student_id, today),
        ).fetchall()
    except Exception as exc:
        logger.debug("Could not fetch today's schedule: %s", exc)
        return []


def _fetch_recent_grades(conn, student_id):
    """The five most recent module results.

    The portal selected ``module_grades.grade`` / ``date_recorded``; the score
    column is ``final_score`` (``final_grade`` holds the letter) and
    ``date_recorded`` is unpopulated, so order by ``completion_date`` and fall
    back to ``date_recorded``.
    """
    try:
        return conn.execute(
            "SELECT mg.module_code, "
            "       COALESCE(m.module_name, mg.module_code) AS module_name, "
            "       mg.final_score, mg.final_grade, "
            "       COALESCE(mg.completion_date, mg.date_recorded) AS recorded "
            "FROM module_grades mg "
            "LEFT JOIN modules m ON m.module_code = mg.module_code "
            "WHERE mg.student_id = ? "
            "ORDER BY recorded DESC LIMIT 5",
            (student_id,),
        ).fetchall()
    except Exception as exc:
        logger.debug("Could not fetch recent grades: %s", exc)
        return []


# ----------------------------------------------------------------------
# Panels ported from the portal
# ----------------------------------------------------------------------

def _build_header(parent, auth, student_id, on_refresh):
    """Welcome banner, identity line and Refresh.

    Replaces the old ``Welcome, {student_id}``, which greeted people as
    ``university.student`` or ``7911243``.
    """
    header = ttk.Frame(parent)
    header.pack(fill=tk.X, padx=15, pady=(15, 5))

    left = ttk.Frame(header)
    left.pack(side=tk.LEFT, fill=tk.X, expand=True)

    ttk.Label(left, text=f"Welcome back, {_display_name(auth)}!",
              font=('Arial', 18, 'bold'),
              foreground=COLORS['primary']).pack(anchor="w")

    subtitle = datetime.now().strftime('%A, %d %B %Y')
    if student_id:
        subtitle = f"{subtitle}   ·   Student ID: {student_id}"
    ttk.Label(left, text=subtitle, font=('Arial', 10),
              foreground=COLORS['secondary']).pack(anchor="w", pady=(2, 0))

    # The dashboard was previously frozen at tab-open: register for a module
    # and the tables kept showing the old list until the app restarted.
    ttk.Button(header,
               text=_t('gui.shell.main.dashboard.student_dashboard.buttons.refresh', default="Refresh"),
               command=on_refresh).pack(side=tk.RIGHT, anchor="ne")


def _build_stat_cards(parent, conn, student_id):
    """Headline numbers: GPA, enrolled modules, upcoming exams, fines."""
    cards = ttk.Frame(parent)
    cards.pack(fill=tk.X, padx=15, pady=5)
    for col in range(4):
        cards.columnconfigure(col, weight=1)

    card_data = [
        (_t('gui.shell.main.dashboard.student_dashboard.labels.current_gpa', default="Current GPA"),
         _fetch_gpa(conn, student_id), 'info'),
        (_t('gui.shell.main.dashboard.student_dashboard.labels.enrolled_modules', default="Enrolled Modules"),
         _fetch_enrolled_count(conn, student_id), 'success'),
        (_t('gui.shell.main.dashboard.student_dashboard.labels.upcoming_exams', default="Upcoming Exams"),
         _fetch_upcoming_exam_count(conn, student_id), 'warning'),
        (_t('gui.shell.main.dashboard.student_dashboard.labels.outstanding_fines', default="Outstanding Fines"),
         _fetch_outstanding_fines(conn, student_id), 'danger'),
    ]
    for idx, (title, value, color) in enumerate(card_data):
        _create_stat_card(cards, title, value, color).grid(
            row=0, column=idx, padx=8, pady=5, sticky="nsew")


def _build_todays_schedule(parent, conn, student_id):
    """Today's classes, in a table rather than the portal's hand-packed rows."""
    frame = ttk.LabelFrame(
        parent,
        text=_t('gui.shell.main.dashboard.student_dashboard.labels.todays_schedule', default="Today's Schedule"),
        padding="10")
    frame.pack(fill=tk.X, padx=15, pady=5)

    rows = _fetch_todays_schedule(conn, student_id)
    if not rows:
        ttk.Label(frame, text=_t('gui.shell.main.dashboard.student_dashboard.labels.no_classes_today', default="No classes scheduled for today.")).pack(anchor="w")
        return

    cols = ('time', 'module', 'room', 'type')
    tree = ttk.Treeview(frame, columns=cols, show='headings', height=min(6, len(rows)))
    tree.heading('time', text=_t('gui.shell.main.dashboard.student_dashboard.headings.time', default='Time'))
    tree.heading('module', text=_t('gui.shell.main.dashboard.student_dashboard.headings.module', default='Module'))
    tree.heading('room', text=_t('gui.shell.main.dashboard.student_dashboard.headings.room', default='Room'))
    tree.heading('type', text=_t('gui.shell.main.dashboard.student_dashboard.headings.type', default='Type'))
    tree.column('time', width=140)
    tree.column('module', width=300)
    tree.column('room', width=120)
    tree.column('type', width=120)
    for r in rows:
        start, end = r['start_time'] or '', r['end_time'] or ''
        tree.insert('', tk.END, values=(
            f"{start} - {end}".strip(' -'),
            f"{r['module_code']} — {r['module_name']}",
            r['room_id'] or '',
            r['session_type'] or '',
        ))
    tree.pack(fill=tk.X)


def _build_recent_grades(parent, conn, student_id):
    """The five most recent module results."""
    frame = ttk.LabelFrame(
        parent,
        text=_t('gui.shell.main.dashboard.student_dashboard.labels.recent_grades', default="Recent Grades"),
        padding="10")
    frame.pack(fill=tk.X, padx=15, pady=5)

    rows = _fetch_recent_grades(conn, student_id)
    if not rows:
        ttk.Label(frame, text=_t('gui.shell.main.dashboard.student_dashboard.labels.no_grades_recorded', default="No grades recorded yet.")).pack(anchor="w")
        return

    cols = ('module', 'score', 'grade', 'date')
    tree = ttk.Treeview(frame, columns=cols, show='headings', height=min(5, len(rows)))
    tree.heading('module', text=_t('gui.shell.main.dashboard.student_dashboard.headings.module', default='Module'))
    tree.heading('score', text=_t('gui.shell.main.dashboard.student_dashboard.headings.score', default='Score'))
    tree.heading('grade', text=_t('gui.shell.main.dashboard.student_dashboard.headings.grade', default='Grade'))
    tree.heading('date', text=_t('gui.shell.main.dashboard.student_dashboard.headings.recorded', default='Recorded'))
    tree.column('module', width=320)
    tree.column('score', width=90)
    tree.column('grade', width=90)
    tree.column('date', width=120)
    for r in rows:
        score = r['final_score']
        tree.insert('', tk.END, values=(
            f"{r['module_code']} — {r['module_name']}",
            f"{score:.1f}" if isinstance(score, (int, float)) else 'N/A',
            r['final_grade'] or 'N/A',
            r['recorded'] or '',
        ))
    tree.pack(fill=tk.X)


def _build_mc_summary(parent, student_id):
    """Mitigating / extenuating circumstances claims, hidden when there are none.

    Ported unchanged in behaviour from the portal — students who never claim
    shouldn't carry an empty panel.
    """
    try:
        from education_system.systems.university.domains.assessment.domain.mitigating_circumstances.integration import (
            claims_for_student,
        )
        claims = claims_for_student(student_id) if student_id else []
    except Exception as exc:
        logger.debug("Could not fetch MC claims: %s", exc)
        return
    if not claims:
        return

    frame = ttk.LabelFrame(
        parent,
        text=_t('gui.shell.main.dashboard.student_dashboard.labels.my_mitigating_circumstances', default="My Mitigating Circumstances"),
        padding="10")
    frame.pack(fill=tk.X, padx=15, pady=5)

    for c in claims[:5]:
        line = (f"#{c['id']}  {c.get('module_code') or '—'}  "
                f"{c.get('assessment_ref') or ''}  · "
                f"{c.get('grounds') or '—'}  → {c['status']}")
        ttk.Label(frame, text=line, font=('Arial', 10)).pack(anchor='w', pady=2)
    if len(claims) > 5:
        ttk.Label(frame,
                  text=f"… and {len(claims) - 5} more (open Mitigating Circumstances for the full list)",
                  font=('Arial', 9, 'italic'),
                  foreground=COLORS['secondary']).pack(anchor='w', pady=(2, 0))


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def create_student_dashboard(parent_frame, auth, service, main_gui=None):
    """Populate *parent_frame* with the student dashboard.

    Args:
        parent_frame: The ttk.Frame to populate.
        auth: Auth manager instance.
        service: DashboardService instance.
        main_gui: Optional UnifiedManagementGUI (or student-portal backend GUI)
            used to route the quick actions inherited from the retired portal.
            Omitted, those buttons are not rendered.

    Access: logged-in students only. Callers already gate on role, but the
    check is repeated here so the dashboard cannot be built for the wrong
    account by a future caller that forgets.
    """
    for child in parent_frame.winfo_children():
        child.destroy()

    user = getattr(auth, 'current_user', None)
    if not user:
        ttk.Label(parent_frame,
                  text=_t('gui.shell.main.dashboard.student_dashboard.labels.login_required', default="Please log in to view your dashboard."),
                  font=('Arial', 12)).pack(padx=20, pady=20)
        return

    role = user.get('role', '') if isinstance(user, dict) else getattr(user, 'role', '')
    if role != 'student':
        ttk.Label(parent_frame,
                  text=_t('gui.shell.main.dashboard.student_dashboard.labels.students_only', default="The student dashboard is only available to student accounts."),
                  font=('Arial', 12)).pack(padx=20, pady=20)
        return

    student_id = resolve_student_id(auth)

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
    _bind_mousewheel(canvas, scrollable)

    root = parent_frame.winfo_toplevel()

    def _refresh():
        create_student_dashboard(parent_frame, auth, service, main_gui=main_gui)

    _build_header(scrollable, auth, student_id, _refresh)

    # One connection for every panel below rather than a fresh one per query:
    # opening student_records.db costs ~100ms of schema parse, and this screen
    # used to pay it six times over before showing anything. Every nested
    # get_connection() — including the ones inside DashboardService,
    # StudentDashboardService and the embedded widgets — shares this one.
    from education_system.systems.university.infrastructure.database.db import (
        get_connection, reuse_connection,
    )

    with reuse_connection():
        # An account with no student record used to render as a page of empty
        # tables, indistinguishable from a student who simply has no data.
        if not student_record_exists(student_id):
            warning = ttk.LabelFrame(scrollable, text="Account not linked", padding="10")
            warning.pack(fill=tk.X, padx=15, pady=5)
            ttk.Label(
                warning,
                text=("No student record is linked to this account"
                      f"{f' (looked up: {student_id})' if student_id else ''}.\n"
                      "Your modules, grades and finances cannot be shown until an "
                      "administrator links your login to a student record."),
                foreground=COLORS['danger'], justify=tk.LEFT,
            ).pack(anchor="w")

        # Announcements posted via the Communications (Email) GUI, filtered to
        # audiences a student can see.
        try:
            from education_system.systems.university.shell.gui.main.dashboard.announcements_widget import (
                create_announcements_panel,
            )
            create_announcements_panel(scrollable, auth, limit=5)
        except Exception as e:
            logger.error(f"Error loading announcements panel: {e}")

        with get_connection() as conn:
            _build_stat_cards(scrollable, conn, student_id)

        try:
            data = service.get_student_dashboard_data(student_id)
        except Exception as e:
            logger.exception("Error fetching student dashboard data")
            data = None

        if data is None:
            ttk.Label(scrollable,
                      text=_t('gui.shell.main.dashboard.student_dashboard.labels.data_unavailable', default="Your dashboard data could not be loaded. Please try Refresh."),
                      foreground=COLORS['danger']).pack(anchor="w", padx=15, pady=5)
            data = {
                'enrolled_courses': [], 'upcoming_assignments': [], 'gpa': None,
                'office_hour_bookings': [], 'ta_assignments': [], 'total_credits': 0,
            }

        # Quick Actions button bar (4-column grid so buttons are never clipped)
        actions_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.student_dashboard.labels.quick_actions', default="Quick Actions"), padding="5")
        actions_frame.pack(fill=tk.X, padx=15, pady=5)

        actions_grid = ttk.Frame(actions_frame)
        actions_grid.pack(fill=tk.X)
        for col in range(4):
            actions_grid.columnconfigure(col, weight=1)

        buttons = []

        # Inherited from the retired portal — routed through the main GUI.
        for label, method_name in _MAIN_GUI_ACTIONS:
            handler = _main_gui_action(main_gui, label, method_name)
            if handler is not None:
                buttons.append((label, handler))

        buttons.extend([
            ("My Profile", lambda: _safe_launch("My Profile", lambda: _launch_profile(root, auth))),
            ("Account Security", lambda: _safe_launch("Account Security", lambda: _launch_security(root, auth))),
            ("Notifications", lambda: _safe_launch("Notifications", lambda: _launch_notifications(root, auth))),
            ("Grades Breakdown", lambda: _safe_launch("Grades Breakdown", lambda: _launch_grades_breakdown(root, auth))),
            ("Degree Progress", lambda: _safe_launch("Degree Progress", lambda: _launch_degree_progress(root, auth))),
            ("Course Catalog", lambda: _safe_launch("Course Catalog", lambda: _launch_course_catalog(root, auth))),
            ("GPA Calculator", lambda: _safe_launch("GPA Calculator", lambda: _launch_gpa_calculator(root, auth))),
            ("Email", lambda: _safe_launch("Email", lambda: _launch_messaging(root, auth))),
            ("Discussion Forums", lambda: _safe_launch("Discussion Forums", lambda: _launch_forums(root, auth))),
            ("Finances", lambda: _safe_launch("Finances", lambda: _launch_finance(root, auth))),
            ("Student Support", lambda: _safe_launch("Student Support", lambda: _launch_help_center(root, auth))),
            ("My Graduation", lambda: _safe_launch("My Graduation", lambda: _launch_graduation(root, auth))),
            ("Documents", lambda: _safe_launch("Documents", lambda: _launch_documents(root, auth))),
            ("Roommate Finder", lambda: _safe_launch("Roommate Finder", lambda: _launch_roommate_finder(root, auth))),
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
            ("My Visa Status", lambda: _launch_feature(root, auth, 'my_visa_status')),
            ("Status Letters", lambda: _launch_feature(root, auth, 'enrolment_letters')),
        ])
        from education_system.systems.university.shell.gui.main.dashboard.evaluation_launchers import (
            EVALUATION_MODULES, launch_evaluation_module,
        )
        for _label, _module in EVALUATION_MODULES:
            buttons.append((_label,
                            lambda m=_module, l=_label: launch_evaluation_module(root, auth, m, l)))
        for i, (label, cmd) in enumerate(buttons):
            ttk.Button(actions_grid, text=label, command=cmd).grid(
                row=i // 4, column=i % 4, padx=3, pady=2, sticky="ew"
            )

        # Today's classes — inherited from the portal.
        with get_connection() as conn:
            _build_todays_schedule(scrollable, conn, student_id)

        # GPA Card
        gpa_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.student_dashboard.labels.academic_summary', default="Academic Summary"), padding="10")
        gpa_frame.pack(fill=tk.X, padx=15, pady=5)

        gpa_text = f"{data['gpa']:.2f}" if data['gpa'] is not None else "N/A"
        ttk.Label(gpa_frame, text=f"Current GPA: {gpa_text}",
                  font=('Arial', 12, 'bold')).pack(anchor="w")
        ttk.Label(gpa_frame, text=f"Total Credits: {data['total_credits']}").pack(anchor="w")
        ttk.Label(gpa_frame, text=f"Enrolled Modules: {len(data['enrolled_courses'])}").pack(anchor="w")

        # Enrolled Modules
        courses_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.student_dashboard.labels.enrolled_modules', default="Enrolled Modules"), padding="10")
        courses_frame.pack(fill=tk.X, padx=15, pady=5)

        if data['enrolled_courses']:
            cols = ('code', 'name', 'type')
            tree = ttk.Treeview(courses_frame, columns=cols, show='headings', height=min(8, len(data['enrolled_courses'])))
            tree.heading('code', text=_t('gui.shell.main.dashboard.student_dashboard.headings.code', default='Code'))
            tree.heading('name', text=_t('gui.shell.main.dashboard.student_dashboard.headings.module_name', default='Module Name'))
            tree.heading('type', text=_t('gui.shell.main.dashboard.student_dashboard.headings.type', default='Type'))
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
            ttk.Label(courses_frame, text=_t('gui.shell.main.dashboard.student_dashboard.labels.no_modules_enrolled', default="No modules enrolled.")).pack(anchor="w")

        # Upcoming Assignments
        assign_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.student_dashboard.labels.upcoming_assignments', default="Upcoming Assignments"), padding="10")
        assign_frame.pack(fill=tk.X, padx=15, pady=5)

        if data['upcoming_assignments']:
            cols = ('title', 'module', 'due_date')
            tree = ttk.Treeview(assign_frame, columns=cols, show='headings',
                                height=min(5, len(data['upcoming_assignments'])))
            tree.heading('title', text=_t('gui.shell.main.dashboard.student_dashboard.headings.title', default='Title'))
            tree.heading('module', text=_t('gui.shell.main.dashboard.student_dashboard.headings.module', default='Module'))
            tree.heading('due_date', text=_t('gui.shell.main.dashboard.student_dashboard.headings.due_date', default='Due Date'))
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
            ttk.Label(assign_frame, text=_t('gui.shell.main.dashboard.student_dashboard.labels.no_upcoming_assignments', default="No upcoming assignments.")).pack(anchor="w")

        # Recent module results — inherited from the portal.
        with get_connection() as conn:
            _build_recent_grades(scrollable, conn, student_id)

        # Office Hour Bookings
        oh_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.student_dashboard.labels.office_hour_bookings', default="Office Hour Bookings"), padding="10")
        oh_frame.pack(fill=tk.X, padx=15, pady=5)

        if data['office_hour_bookings']:
            cols = ('instructor', 'day', 'time', 'location', 'date')
            tree = ttk.Treeview(oh_frame, columns=cols, show='headings',
                                height=min(4, len(data['office_hour_bookings'])))
            tree.heading('instructor', text=_t('gui.shell.main.dashboard.student_dashboard.headings.instructor', default='Instructor'))
            tree.heading('day', text=_t('gui.shell.main.dashboard.student_dashboard.headings.day', default='Day'))
            tree.heading('time', text=_t('gui.shell.main.dashboard.student_dashboard.headings.time', default='Time'))
            tree.heading('location', text=_t('gui.shell.main.dashboard.student_dashboard.headings.location', default='Location'))
            tree.heading('date', text=_t('gui.shell.main.dashboard.student_dashboard.headings.booking_date', default='Booking Date'))
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
            ttk.Label(oh_frame, text=_t('gui.shell.main.dashboard.student_dashboard.labels.no_upcoming_office_hour_bookings', default="No upcoming office hour bookings.")).pack(anchor="w")

        # TA Assignments
        if data['ta_assignments']:
            ta_frame = ttk.LabelFrame(scrollable, text=_t('gui.shell.main.dashboard.student_dashboard.labels.my_ta_assignments', default="My TA Assignments"), padding="10")
            ta_frame.pack(fill=tk.X, padx=15, pady=5)

            cols = ('module', 'role', 'hours')
            tree = ttk.Treeview(ta_frame, columns=cols, show='headings',
                                height=min(3, len(data['ta_assignments'])))
            tree.heading('module', text=_t('gui.shell.main.dashboard.student_dashboard.headings.module', default='Module'))
            tree.heading('role', text=_t('gui.shell.main.dashboard.student_dashboard.headings.role', default='Role'))
            tree.heading('hours', text=_t('gui.shell.main.dashboard.student_dashboard.headings.hours_week', default='Hours/Week'))
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

        # Mitigating circumstances — inherited from the portal.
        _build_mc_summary(scrollable, student_id)

        # --- Embedded Summary Widgets ---
        try:
            from education_system.systems.university.shell.gui.main.dashboard.student_widgets import (
                create_grades_summary_widget,
                create_degree_progress_widget,
                create_gpa_whatif_widget,
                create_payment_alerts_widget,
            )

            create_grades_summary_widget(scrollable, student_id)
            create_degree_progress_widget(scrollable, student_id)
            create_gpa_whatif_widget(
                scrollable, student_id,
                launch_callback=lambda: _safe_launch(
                    "GPA Calculator", lambda: _launch_gpa_calculator(root, auth)),
            )
            create_payment_alerts_widget(scrollable, student_id)
        except Exception as e:
            logger.error(f"Error loading student dashboard widgets: {e}")
