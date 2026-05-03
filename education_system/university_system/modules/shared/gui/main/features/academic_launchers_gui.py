# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
import logging
import sys
import subprocess

from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
    consume_context as _consume_academic_context,
    format_context as _format_academic_context,
    style_guarded as _academic_style_guarded,
)


from education_system.university_system.modules.shared.gui.main._tk_callback_filter import (
    install_clean_close as _install_clean_close,
)


def _apply_academic_context(window, parent_app):
    """Append a context suffix to the window title if a contextual
    right-click brought the user here. Returns the consumed context
    (or None) so the caller can use it for further filtering if able."""
    ctx = _consume_academic_context(parent_app)
    if not ctx:
        return None
    try:
        window.title(window.title() + f"  ◆ {_format_academic_context(ctx)}")
    except Exception:
        pass
    return ctx


def _apply_library_inbound_context(library_gui, ctx):
    """Route inbound academic context to the right Library tab.

    Called ~50ms after LibraryGUI construction (so its base widgets
    have finished laying out). Reading-list-shaped context goes to the
    Reading Lists tab; book-shaped context (from University Shop and
    similar) goes to the All Books tab with the search box pre-filled.
    Mixed context is fine — both branches run independently."""
    if not ctx:
        return
    if ctx.get("reading_list_id") or ctx.get("course_id") or ctx.get("course_code"):
        _open_library_reading_lists(library_gui, ctx)
    if ctx.get("book_title") or ctx.get("isbn") or ctx.get("book_id"):
        _open_library_books_with_search(library_gui, ctx)


def _open_library_books_with_search(library_gui, ctx):
    """Open the All Books tab and run a search on the supplied title /
    ISBN / book_id. Used by the Shop → Library contextual jump."""
    try:
        show = getattr(library_gui, "show_all_books", None)
        if not callable(show):
            logger.debug("LibraryGUI has no show_all_books; skipping books-tab jump")
            return
        show()
    except Exception:
        logger.exception("show_all_books failed during context jump")
        return

    try:
        var = getattr(library_gui, "book_search_var", None)
        if var is None:
            return
        term = (ctx.get("book_title") or ctx.get("isbn")
                or ctx.get("book_id"))
        if not term:
            return
        var.set(str(term))
        do_search = getattr(library_gui, "search_books_table", None)
        if callable(do_search):
            do_search()
    except Exception:
        logger.exception("books-tab search prefill failed")


def _open_library_reading_lists(library_gui, ctx):
    """Navigate a freshly-opened LibraryGUI to its Reading Lists tab and,
    if a reading_list_id was supplied, double-click into that list.

    Used when another module (e.g. Course Management) right-clicks a row
    and asks Library to surface the relevant reading list. Best-effort —
    if the GUI doesn't yet expose ``show_reading_lists`` (e.g. the user
    lacks ``manage_reading_lists`` permission and it short-circuited)
    the helper logs and returns silently."""
    try:
        show = getattr(library_gui, "show_reading_lists", None)
        if not callable(show):
            logger.debug("LibraryGUI has no show_reading_lists; skipping context jump")
            return
        show()
    except Exception:
        logger.exception("show_reading_lists failed during context jump")
        return

    list_id = ctx.get("reading_list_id")
    if not list_id:
        return

    # Try to select the row matching list_id and trigger view-details.
    try:
        tree = getattr(library_gui, "reading_lists_tree", None)
        if tree is None:
            return
        target = str(list_id)
        for iid in tree.get_children():
            try:
                vals = tree.item(iid).get("values") or []
                if vals and str(vals[0]) == target:
                    tree.selection_set(iid)
                    tree.focus(iid)
                    tree.see(iid)
                    view = getattr(library_gui, "view_reading_list_details", None)
                    if callable(view):
                        view()
                    return
            except Exception:
                continue
    except Exception:
        logger.exception("reading_list_id row select failed")

# Import PDF export functionality
try:
    from education_system.university_system.modules.shared.gui.pdf_export_gui import show_pdf_export_gui as _pdf_export_gui_func
    PDF_EXPORT_GUI_AVAILABLE = True
except ImportError:
    _pdf_export_gui_func = None
    PDF_EXPORT_GUI_AVAILABLE = False

# Import GUI availability flags and classes
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    LIBRARY_GUI_AVAILABLE,
    LibraryGUI,
    PARENT_PORTAL_GUI_AVAILABLE,
    ParentPortalGUI,
    VIRTUAL_CLASSROOM_AVAILABLE,
    ACADEMIC_CALENDAR_GUI_AVAILABLE,
    CalendarGUI,
    COURSE_MANAGEMENT_GUI_AVAILABLE,
    CourseManagementGUI,
    MODULE_SCHEDULING_GUI_AVAILABLE,
    ModuleSchedulingGUI,
    launch_module_scheduling_gui,
    ASSIGNMENT_SUBMISSION_GUI_AVAILABLE,
    AssignmentGUI,
    init_calendar_database,
    AttendanceGUI,
    ATTENDANCE_GUI_AVAILABLE,
    AI_DETECTOR_GUI_AVAILABLE,
    AIDetectorGUI,
    OFFICE_HOURS_GUI_AVAILABLE,
    OfficeHoursGUI,
    ADVANCED_SEARCH_GUI_AVAILABLE,
    AdvancedSearchGUI,
    DOCUMENT_MANAGER_GUI_AVAILABLE,
    DocumentManagerGUI,
    start_document_manager_gui,
    display_document_management_menu,
    ENHANCED_REPORTING_GUI_AVAILABLE,
    ReportingSystemGUI,
    start_enhanced_reporting_gui,
    launch_admissions_crm_gui,
    launch_predictive_analytics_gui,
    launch_business_intelligence_gui,
    launch_integration_marketplace_gui,
)

# Import paths
from education_system.university_system.modules.shared.constants import paths
PROJECT_ROOT = paths.PROJECT_ROOT
DB_PATH = paths.DEFAULT_DB_PATH

# Alias for translation function
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)

def show_library_management(self):
    """Launch the Library Management GUI as a full-screen Toplevel.

    Pre-8.117.34 used ``open_in_workspace`` to render Library as a
    tab inside the main GUI's content notebook (8.117.18 — the
    "right content panel is decorative" fix). User reverted that
    decision specifically for Library: it has its own dense layout
    (notebook of notebooks, ~14 tabs of CRUD treeviews) and felt
    cramped inside the workspace. Now opens as a standalone
    Toplevel that fills the screen — ``LibraryGUI.__init__`` already
    does cross-platform window maximisation
    (``state('zoomed')`` on Windows, ``geometry(screen-50 × screen-100)``
    on Linux/Unix; see ``library/base.py`` 8.117.24), so we just
    hand it a Toplevel and let it size itself.

    The ``open_in_workspace`` mechanism stays available for other
    future migrations — only Library is reverted.
    """
    if not self.auth.current_user:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.login_required_library"))
        return

    if not (self.auth.check_permission('view_books') or
            self.auth.check_permission('manage_books') or
            self.auth.check_permission('manage_loans') or
            self.auth.check_permission('checkout_books')):
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.no_permission_library"))
        return

    if not LIBRARY_GUI_AVAILABLE:
        # Fallback to CLI menu — same as before, no UI host involved.
        messagebox.showinfo(_t("academic_launchers.titles.library_short"),
                            _t("academic_launchers.fallback.library_gui_unavailable",
                               error=LIBRARY_GUI_IMPORT_ERROR))
        try:
            from education_system.university_system.modules.domain.academics.services.library.menu import display_library_menu
            display_library_menu()
        except ImportError:
            messagebox.showerror(_t("academic_launchers.errors.title"),
                                 _t("academic_launchers.errors.library_unavailable"))
        return

    # Consume the inbound academic context up front (so a stale
    # context can't bleed into a later jump) and bake any non-empty
    # tag into the window title so the user knows what scoped them
    # here (e.g. arriving from a "Open reading lists in Library"
    # cross-link).
    try:
        from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
            consume_context as _consume_academic_context,
            format_context as _format_academic_context_fn,
        )
        ctx = _consume_academic_context(self)
    except Exception:
        ctx = None

    title = _t("academic_launchers.titles.library")
    if ctx:
        try:
            tag = _format_academic_context_fn(ctx)
            if tag:
                title = f"{title}  ◆ {tag}"
        except Exception:
            pass

    try:
        library_window = tk.Toplevel(self.root)
        _install_clean_close(library_window)
        library_window.title(title)
        # No explicit geometry — LibraryGUI.__init__ runs its own
        # cross-platform maximisation pass (state('zoomed') with
        # a screen-sized geometry fallback) so the window fills
        # the screen regardless of platform.
        try:
            library_window.transient(self.root)
        except Exception:
            pass

        library_gui = LibraryGUI(library_window)
        if hasattr(library_gui, 'set_auth'):
            library_gui.set_auth(self.auth)
        elif hasattr(library_gui, 'auth'):
            library_gui.auth = self.auth

        if ctx and (ctx.get("reading_list_id") or ctx.get("course_id")
                    or ctx.get("course_code") or ctx.get("book_title")
                    or ctx.get("isbn") or ctx.get("book_id")):
            try:
                library_window.after(
                    50,
                    lambda g=library_gui, c=ctx: _apply_library_inbound_context(g, c),
                )
            except Exception:
                logger.exception("Library context navigation failed")

        print(_t("academic_launchers.success.library_opened"))
    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"),
                             _t("academic_launchers.errors.failed_open_library", error=str(e)))
        print(_t("academic_launchers.errors.library_error_log", error=e))
def show_academic_calendar(self):
    """Launch the Academic Calendar GUI with proper initialization"""
    if not self.auth.current_user:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.login_required_calendar"))
        return

    # Check permissions
    if not (self.auth.check_permission('manage_schedules') or
            self.auth.check_permission('view_own_timetable') or
            self.auth.check_permission('export_data')):
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.no_permission_calendar"))
        return

    try:
        if not ACADEMIC_CALENDAR_GUI_AVAILABLE:
            messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.calendar_gui_unavailable"))
            return

        # Ensure calendar database is initialized
        print(_t("academic_launchers.info.checking_calendar_db"))
        if not init_calendar_database():
            messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.calendar_db_init_failed"))
            return

        # Create calendar GUI with embedded approach
        calendar_window = tk.Toplevel(self.root)
        _install_clean_close(calendar_window)
        calendar_window.title(_t("academic_launchers.titles.calendar"))
        calendar_window.geometry("1400x900")
        calendar_window.minsize(1000, 600)

        # Center the window
        calendar_window.update_idletasks()
        x = (calendar_window.winfo_screenwidth() - calendar_window.winfo_width()) // 2
        y = (calendar_window.winfo_screenheight() - calendar_window.winfo_height()) // 2
        calendar_window.geometry(f"+{x}+{y}")

        try:
            calendar_window.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set calendar_window as transient: {e}")

        # Create the calendar GUI instance
        try:
            # Use the imported CalendarGUI class - correct parameter order
            calendar_gui = CalendarGUI(auth_manager=self.auth, parent_window=calendar_window)

            print(_t("academic_launchers.success.calendar_opened"))

        except Exception as gui_error:
            calendar_window.destroy()
            raise gui_error

    except Exception as e:
        error_msg = _t("academic_launchers.errors.failed_open_calendar", error=str(e))
        messagebox.showerror(_t("academic_launchers.errors.title"), error_msg)
        print(_t("academic_launchers.errors.calendar_error_log", error=e))
        logging.error(_t("academic_launchers.errors.calendar_gui_error_log", error=e))

        # Offer CLI fallback
        if messagebox.askyesno(_t("academic_launchers.fallback.title"), _t("academic_launchers.fallback.try_cli_calendar")):
            try:
                from education_system.university_system.modules.domain.academics.services.academic_calendar.cli import display_academic_calendar_menu
                display_academic_calendar_menu()
            except ImportError:
                messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.calendar_unavailable"))
def show_course_management(self):
    """Launch the Course Management GUI in a new window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.login_required_course"))
        return

    if not (self.auth.check_permission('manage_courses') or self.auth.check_permission('view_courses')):
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.no_permission_course"))
        return

    try:
        if COURSE_MANAGEMENT_GUI_AVAILABLE:
            # Create a new window for the Course Management GUI
            course_window = tk.Toplevel(self.root)
            _install_clean_close(course_window)
            course_window.title(_t("academic_launchers.titles.course"))
            course_window.geometry("1200x800")

            # Center the window
            course_window.update_idletasks()
            x = (course_window.winfo_screenwidth() - course_window.winfo_width()) // 2
            y = (course_window.winfo_screenheight() - course_window.winfo_height()) // 2
            course_window.geometry(f"+{x}+{y}")

            try:
                course_window.transient(self.root)
            except Exception:
                pass  # Continue if transient fails
            _apply_academic_context(course_window, self)

            # Initialize the Course Management GUI in the new window
            # Pass auth_system during construction for proper initialization
            with _academic_style_guarded(self.root, child_window=course_window):
                course_gui = CourseManagementGUI(course_window, auth_system=self.auth)

            print(_t("academic_launchers.success.course_opened"))

        else:
            # Fallback to CLI menu
            messagebox.showinfo(_t("academic_launchers.titles.course_short"),
                              _t("academic_launchers.fallback.course_gui_unavailable"))
            try:
                from education_system.university_system.modules.domain.academics.services.course_management import display_course_management_menu
                display_course_management_menu(self.auth)
            except ImportError:
                messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.course_unavailable"))

    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.failed_open_course", error=str(e)))
        print(_t("academic_launchers.errors.course_error_log", error=e))
def show_module_management(self):
    """Launch the full Module Scheduling GUI in a new window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.login_required_module"))
        return

    if not (self.auth.check_permission('manage_modules') or self.auth.check_permission('view_assigned_modules')):
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.no_permission_module"))
        return

    try:
        if MODULE_SCHEDULING_GUI_AVAILABLE and ModuleSchedulingGUI:
            # Create a new window for the Module Scheduling GUI
            module_window = tk.Toplevel(self.root)
            _install_clean_close(module_window)
            module_window.title(_t("academic_launchers.titles.module"))
            module_window.geometry("1400x900")
            module_window.minsize(1200, 800)

            # Center the window
            module_window.update_idletasks()
            x = (module_window.winfo_screenwidth() - module_window.winfo_width()) // 2
            y = (module_window.winfo_screenheight() - module_window.winfo_height()) // 2
            module_window.geometry(f"+{x}+{y}")

            try:
                module_window.transient(self.root)
            except Exception:
                pass  # Continue if transient fails

            # Initialize the Module Scheduling GUI in the new window
            module_gui = ModuleSchedulingGUI(module_window)

            # Pass the auth context if the ModuleSchedulingGUI supports it
            if hasattr(module_gui, 'set_auth'):
                module_gui.set_auth(self.auth)
            elif hasattr(module_gui, 'auth'):
                module_gui.auth = self.auth

            print(_t("academic_launchers.success.module_opened"))

        else:
            # Fallback to the original CLI menu if GUI not available
            messagebox.showinfo(_t("academic_launchers.titles.module_short"),
                              _t("academic_launchers.fallback.module_gui_unavailable"))
            try:
                # Import and call the CLI version
                from education_system.university_system.modules.domain.academics.services.module_scheduling import display_enhanced_scheduling_menu
                display_enhanced_scheduling_menu()
            except ImportError:
                messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.module_unavailable"))

    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.failed_open_module", error=str(e)))
        print(_t("academic_launchers.errors.module_error_log", error=e))

        # Try CLI fallback on error
        try:
            from education_system.university_system.modules.domain.academics.services.module_scheduling import display_enhanced_scheduling_menu
            display_enhanced_scheduling_menu()
        except ImportError:
            messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.module_both_unavailable"))
def show_module_scheduling(self):
    """Open the Module Scheduling GUI (child window if possible)."""
    try:
        if not MODULE_SCHEDULING_GUI_AVAILABLE:
            messagebox.showinfo(_t("academic_launchers.titles.module_scheduling"), _t("academic_launchers.errors.module_scheduling_unavailable"))
            return
        # Prefer embedding into a Toplevel to avoid creating a second Tk root.
        try:
            top = tk.Toplevel(self.root)
            _install_clean_close(top)
            top.title(_t("academic_launchers.titles.module_scheduling"))
            _apply_academic_context(top, self)
            with _academic_style_guarded(self.root, child_window=top):
                app = ModuleSchedulingGUI(top) if 'ModuleSchedulingGUI' in globals() and ModuleSchedulingGUI else None
            # Pass auth context if supported
            try:
                if app and hasattr(app, 'set_auth'):
                    app.set_auth(self.auth)
            except Exception as e:
                logger.debug(f"Could not set auth on app: {e}")
            try:
                top.transient(self.root)
                top.grab_set()
            except Exception as e:
                logger.debug(f"Could not set window as transient or grab focus: {e}")
        except Exception as inner_e:
            # Fallback to provided launcher (may create its own Tk root)
            try:
                launch_module_scheduling_gui()
            except Exception as e2:
                messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.module_scheduling_launch_failed", error=e2))
    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.failed_open_module_scheduling", error=e))
def show_grades(self):
    """Open the Grade Tracking GUI (child window) or fall back to CLI."""
    if self.grade_tracking_gui:
        self.grade_tracking_gui.show_grades()
    else:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.grade_tracking_unavailable"))
def show_grade_tracking_gui(self):
    """Launch the Grade Tracking GUI in a child window"""
    if self.grade_tracking_gui:
        self.grade_tracking_gui.show_grade_tracking_gui()
    else:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.grade_tracking_unavailable"))
def show_auto_grading(self):
    """Launch the AI Auto-Grading window (staff/admin only)"""
    if self.grade_tracking_gui:
        self.grade_tracking_gui.show_auto_grading()
    else:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.grade_tracking_unavailable"))
def show_assignments(self):
    """Show assignments interface - Launch full AssignmentGUI"""
    try:
        print(f"Debug: ASSIGNMENT_SUBMISSION_GUI_AVAILABLE = {ASSIGNMENT_SUBMISSION_GUI_AVAILABLE}")
        if not ASSIGNMENT_SUBMISSION_GUI_AVAILABLE:
            messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.assignment_gui_unavailable"))
            return

        # Create a new window for the Assignment GUI
        assignment_window = tk.Toplevel(self.root)
        _install_clean_close(assignment_window)
        assignment_window.title(_t("academic_launchers.titles.assignment"))
        assignment_window.geometry("1200x800")

        # Center the window
        assignment_window.update_idletasks()
        x = (assignment_window.winfo_screenwidth() - assignment_window.winfo_width()) // 2
        y = (assignment_window.winfo_screenheight() - assignment_window.winfo_height()) // 2
        assignment_window.geometry(f"+{x}+{y}")

        try:
            assignment_window.transient(self.root)
        except Exception:
            pass  # Continue if transient fails

        # Create a minimal assignment system for the GUI
        # Since AssignmentSubmission is not implemented, create a minimal substitute
        class MinimalAssignmentSystem:
            def __init__(self):
                self.db_path = None  # Will be set by the GUI if needed
                self.submission_dir = None
                self.auth = None

            def set_auth(self, auth):
                self.auth = auth

            def _get_student_id(self):
                """Get student ID from current user"""
                if self.auth and self.auth.current_user:
                    # Check if user is admin - for admin users, return a special ID for testing
                    user_role = self.auth.current_user.get('role', '')
                    if user_role == 'admin':
                        return 'ADMIN_TEST'  # Special ID for admin testing

                    # First try to get student_id from user record
                    student_id = self.auth.current_user.get('student_id')
                    if student_id:
                        return student_id

                    # Query the database to get the student_id from users table
                    user_id = self.auth.current_user.get('id')
                    if user_id:
                        try:
                            from education_system.university_system.infrastructure.database.db import sqlite3
                            from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH

                            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                            try:
                                cursor = conn.cursor()
                                cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
                                result = cursor.fetchone()
                            finally:
                                conn.close()

                            if result and result[0]:
                                return result[0]
                        except Exception as e:
                            print(_t("academic_launchers.errors.student_id_db_error", error=e))

                    # Fallback: use username as student_id if it follows student ID format
                    username = self.auth.current_user.get('username', '')
                    if username.startswith('S') or username.isdigit():
                        return username
                return None

        assignment_system = MinimalAssignmentSystem()
        assignment_system.set_auth(self.auth)

        # Initialize the Assignment GUI with minimal system
        assignment_gui = AssignmentGUI(assignment_system, self.auth, parent=assignment_window)

        print(_t("academic_launchers.success.assignment_opened"))

    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.failed_open_assignment", error=str(e)))
        print(_t("academic_launchers.errors.assignment_error_log", error=e))
def show_plagiarism_checker(self):
    """Show plagiarism checker interface"""
    try:
        # Launch plagiarism checker GUI or show in content area
        from education_system.university_system.modules.domain.academics.gui.plagiarism_main_gui import launch_gui_from_main_system
        launch_gui_from_main_system(self.auth)
    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.plagiarism_unavailable", error=e))
def show_ai_detector(self):
    """Show AI detector interface"""
    try:
        if not AI_DETECTOR_GUI_AVAILABLE:
            messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.ai_detector_gui_unavailable"))
            return

        # Create new window for AI Detector
        ai_window = tk.Toplevel(self.root)
        _install_clean_close(ai_window)
        ai_window.title(_t("academic_launchers.titles.ai_detector"))
        ai_window.geometry("1000x700")

        # Initialize AI Detector GUI
        ai_gui = AIDetectorGUI(ai_window, self.auth)
        print(_t("academic_launchers.success.ai_detector_opened"))

    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.ai_detector_unavailable", error=e))
def open_ai_detector_window(self):
    """Open the AI Detector GUI in a separate full-screen window (new process)."""
    try:
        python = sys.executable
        code = (
            "import sys, os; "
            f"sys.path.insert(0, r'{PROJECT_ROOT}'); "
            "import ai_detector as m; "
            f"det = m.AIDetector(db_path=r'{DB_PATH}'); "
            "app = m.AIDetectorGUI(det); "
            "app.root.attributes('-fullscreen', True); "
            "app.run()"
        )
        subprocess.Popen([python, "-c", code], close_fds=True)
    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.failed_open_ai_detector_window", error=e))
def open_attendance_gui(self):
    try:
        import tkinter as tk
        from tkinter import messagebox
        if AttendanceGUI is None:
            messagebox.showerror(_t("academic_launchers.titles.attendance"), _t("academic_launchers.errors.attendance_gui_unavailable"))
            return
        # Create a child window for the attendance UI
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.transient(self.root)
        _apply_academic_context(win, self)
        try:
            # AttendanceGUI (and its absence-tab dependency) directly
            # mutate base ttk style names — guard the parent so those
            # changes don't bleed back into the main GUI.
            with _academic_style_guarded(self.root, child_window=win):
                AttendanceGUI(win, auth_manager=self.auth)
        except Exception as e:
            win.destroy()
            messagebox.showerror(_t("academic_launchers.titles.attendance"), _t("academic_launchers.errors.failed_open_attendance", error=e))
    except Exception as e:
        try:
            from tkinter import messagebox
            messagebox.showerror(_t("academic_launchers.titles.attendance"), _t("academic_launchers.errors.attendance_unexpected_error", error=e))
        except Exception as ex:
            logger.error(f"Failed to show attendance error dialog: {ex}")
def open_absence_tracker_gui(self):
    """Launch the standalone University Absence Tracker as a separate process.

    Passes the current authenticated user via CLI args — no second login prompt.
    """
    try:
        python = sys.executable
        cmd = [python, "-m",
               "education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.absence_tracker"]
        user = getattr(self.auth, "current_user", None) if getattr(self, "auth", None) else None
        if user:
            if user.get("username"):
                cmd += ["--username", str(user["username"])]
            elif user.get("id") is not None:
                cmd += ["--user-id", str(user["id"])]
            if user.get("role"):
                cmd += ["--role", str(user["role"])]
        else:
            messagebox.showerror("Absence Tracker", "Please log in first.")
            return
        subprocess.Popen(cmd, close_fds=True)
    except Exception as e:
        try:
            messagebox.showerror("Absence Tracker", f"Failed to open Absence Tracker: {e}")
        except Exception as ex:
            logger.error(f"Failed to show absence tracker error dialog: {ex}")
def show_office_hours_gui(self):
    """Launch Office Hours Management inside the main GUI's content
    notebook when a workspace is available, falling back to a
    Toplevel otherwise — same pattern as Student Records (8.117.38)."""
    if not self.auth.current_user:
        messagebox.showerror("Error", "Please log in to access Office Hours.")
        return

    if not OFFICE_HOURS_GUI_AVAILABLE:
        messagebox.showerror("Office Hours", "Office Hours GUI is not available.")
        return

    title = "Office Hours"
    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: OfficeHoursGUI(host, auth=self.auth))
        return

    try:
        win = tk.Toplevel(self.root)
        _install_clean_close(win)
        win.transient(self.root)
        OfficeHoursGUI(win, auth=self.auth)
    except Exception as e:
        try:
            win.destroy()
        except Exception:
            pass
        messagebox.showerror("Office Hours", f"Failed to open Office Hours: {e}")

def show_student_grades_gui(self):
    """Launch the Student Grades & GPA GUI"""
    if not self.auth.current_user:
        messagebox.showerror("Error", "Please log in to access your grades.")
        return

    try:
        from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
            STUDENT_GRADES_GUI_AVAILABLE, StudentGradesPortal
        )
        if not STUDENT_GRADES_GUI_AVAILABLE or StudentGradesPortal is None:
            messagebox.showerror("Grades", "Student Grades GUI is not available.")
            return

        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title("My Grades & GPA")
        window.geometry("1200x800")
        try:
            window.transient(self.root)
        except Exception:
            pass
        StudentGradesPortal(window, auth_instance=self.auth)
        print("Student Grades GUI opened")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Student Grades: {e}")
        logger.error(f"Student Grades GUI error: {e}")

def show_student_outcomes_gui(self):
    """Launch the Learning Outcomes Tracker GUI"""
    if not self.auth.current_user:
        messagebox.showerror("Error", "Please log in to access Learning Outcomes.")
        return

    try:
        from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
            STUDENT_OUTCOMES_GUI_AVAILABLE, StudentOutcomesGUI
        )
        if not STUDENT_OUTCOMES_GUI_AVAILABLE or StudentOutcomesGUI is None:
            messagebox.showerror("Learning Outcomes", "Learning Outcomes GUI is not available.")
            return

        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title("Learning Outcomes")
        window.geometry("1200x800")
        try:
            window.transient(self.root)
        except Exception:
            pass
        StudentOutcomesGUI(window, auth_instance=self.auth)
        print("Learning Outcomes GUI opened")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Learning Outcomes: {e}")
        logger.error(f"Learning Outcomes GUI error: {e}")

def show_student_timetable_gui(self):
    """Launch the Student Timetable inside the main GUI's content
    notebook when a workspace is available, falling back to a
    Toplevel otherwise — same pattern as Student Records (8.117.38)."""
    if not self.auth.current_user:
        messagebox.showerror("Error", "Please log in to access your timetable.")
        return

    try:
        from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
            STUDENT_TIMETABLE_GUI_AVAILABLE, StudentTimetableGUI
        )
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Timetable: {e}")
        logger.error(f"Student Timetable GUI error: {e}")
        return

    if not STUDENT_TIMETABLE_GUI_AVAILABLE or StudentTimetableGUI is None:
        messagebox.showerror("Timetable", "Student Timetable GUI is not available.")
        return

    title = "My Timetable"
    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: StudentTimetableGUI(host, auth_instance=self.auth))
        print("Student Timetable GUI opened")
        return

    try:
        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title(title)
        window.geometry("1200x800")
        try:
            window.transient(self.root)
        except Exception:
            pass
        _apply_academic_context(window, self)
        with _academic_style_guarded(self.root, child_window=window):
            StudentTimetableGUI(window, auth_instance=self.auth)
        print("Student Timetable GUI opened")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Timetable: {e}")
        logger.error(f"Student Timetable GUI error: {e}")

def show_student_registration_gui(self):
    """Launch the Student Registration (Module Enrollment) GUI"""
    if not self.auth.current_user:
        messagebox.showerror("Error", "Please log in to access Module Registration.")
        return

    try:
        from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
            STUDENT_REGISTRATION_GUI_AVAILABLE, StudentRegistrationPortal
        )
        if not STUDENT_REGISTRATION_GUI_AVAILABLE or StudentRegistrationPortal is None:
            messagebox.showerror("Registration", "Module Registration GUI is not available.")
            return

        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title("Module Registration")
        window.geometry("1200x800")
        try:
            window.transient(self.root)
        except Exception:
            pass
        StudentRegistrationPortal(window, auth_instance=self.auth)
        print("Module Registration GUI opened")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Module Registration: {e}")
        logger.error(f"Student Registration GUI error: {e}")

def show_student_dashboard_gui(self):
    """Launch the Student Self-Service Dashboard GUI"""
    if not self.auth.current_user:
        messagebox.showerror("Error", "Please log in to access the Student Dashboard.")
        return

    try:
        from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
            STUDENT_DASHBOARD_GUI_AVAILABLE, StudentDashboardPortal
        )
        if not STUDENT_DASHBOARD_GUI_AVAILABLE or StudentDashboardPortal is None:
            messagebox.showerror("Dashboard", "Student Dashboard GUI is not available.")
            return

        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title("Student Dashboard")
        window.geometry("1300x900")
        try:
            window.transient(self.root)
        except Exception:
            pass
        StudentDashboardPortal(window, auth_instance=self.auth, main_gui=self)
        print("Student Dashboard GUI opened")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Student Dashboard: {e}")
        logger.error(f"Student Dashboard GUI error: {e}")

def show_virtual_classroom_gui(self):
    """Launch the Virtual Classroom Management GUI inside the main
    GUI's content notebook when a workspace is available, falling
    back to a Toplevel otherwise — same pattern as Student Records
    (8.117.38)."""
    if not self.auth.current_user:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.login_required_virtual_classroom"))
        return

    if not VIRTUAL_CLASSROOM_AVAILABLE:
        messagebox.showerror(_t("academic_launchers.titles.virtual_classroom"), _t("academic_launchers.errors.virtual_classroom_unavailable"))
        return

    try:
        from education_system.university_system.modules.domain.academics.gui.virtual_classroom_gui import VirtualClassroomGUI
    except ImportError as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.virtual_classroom_import_error", error=str(e)))
        print(_t("academic_launchers.errors.virtual_classroom_import_log", error=e))
        return

    title = _t("academic_launchers.titles.virtual_classroom")

    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: VirtualClassroomGUI(host, auth=self.auth))
        print(_t("academic_launchers.success.virtual_classroom_opened"))
        return

    try:
        classroom_window = tk.Toplevel(self.root)
        _install_clean_close(classroom_window)
        VirtualClassroomGUI(classroom_window, auth=self.auth)
        print(_t("academic_launchers.success.virtual_classroom_opened"))
    except Exception as e:
        messagebox.showerror(_t("academic_launchers.errors.title"), _t("academic_launchers.errors.failed_open_virtual_classroom", error=str(e)))
        print(_t("academic_launchers.errors.virtual_classroom_error_log", error=e))


def show_lms_gui(self):
    """Open the shared Learning Management System GUI."""
    try:
        from education_system.shared.lms.lms_gui import LMSFrame
        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title("Learning Management System")
        window.geometry("1100x700")
        try:
            window.transient(self.root)
        except Exception:
            pass
        auth = self.auth
        frame = LMSFrame(window, db_path=DB_PATH, auth=auth)
        frame.pack(fill="both", expand=True)
        print("LMS GUI opened successfully")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open LMS: {e}")
        print(f"LMS GUI error: {e}")

def show_document_manager(self):
    """Open the Document Management GUI (with fallbacks).

    If a contextual right-click brought the user here (e.g. Library
    Reading Lists → "Open document attachments"), the academic context
    dict is consumed and surfaced as a title-bar suffix. The Document
    Manager itself doesn't currently take a structured filter for
    reading_list_id — that would need a schema-level link between
    reading_list_items and the document_attachments table — so for now
    the user sees what scoped them here and can search manually."""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_document_manager"))
        return

    user = self.auth.current_user
    perms = user.get('permissions', [])
    role = user.get('role', '')

    # Be generous but safe: admin/staff or explicit perms
    allowed = (
        role in ('admin', 'staff') or
        any(p in perms for p in ['manage_documents', 'system_config', 'view_documents'])
    )
    if not allowed:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.no_permission_document_manager"))
        return

    ctx = None
    try:
        from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
            consume_context as _consume,
        )
        ctx = _consume(self)
    except Exception:
        logger.debug("document manager: could not consume academic context", exc_info=True)

    try:
        if DOCUMENT_MANAGER_GUI_AVAILABLE and DocumentManagerGUI:
            win = tk.Toplevel(self.root)
            _install_clean_close(win)
            win.title(_t("extras_gui.titles.document_manager"))
            if ctx:
                tag = ctx.get("list_name") or ctx.get("reading_list_id") \
                    or ctx.get("course_code") or ctx.get("course_id")
                if tag:
                    try:
                        win.title(win.title() + f"  ◆ {tag}")
                    except Exception:
                        pass
            win.geometry("1400x900")
            try:
                win.transient(self.root)
                win.grab_set()
            except Exception as e:
                logger.debug(f"Could not set window as transient or grab focus: {e}")

            # Embed the full GUI with auth
            DocumentManagerGUI(win, auth=self.auth)
            print(_t("extras_gui.messages.document_manager_opened"))
            return

        # If import flag says unavailable, try the standalone launcher first
        if start_document_manager_gui:
            start_document_manager_gui()
            return

        raise RuntimeError(_t("extras_gui.errors.document_manager_not_available"))

    except Exception as e:
        # Final fallback: original CLI menu you already ship
        try:
            display_document_management_menu()
        except Exception as cli_err:
            messagebox.showerror(
                _t("extras_gui.titles.document_manager_short"),
                _t("extras_gui.errors.document_manager_failed").format(error=e, cli_error=cli_err)
            )
def show_pdf_export_gui(self):
    """Launch the PDF Database Export GUI"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_export"))
        return

    if not (self.auth.check_permission('export_data') or
            self.auth.check_permission('backup_restore') or
            self.auth.current_user.get('role') == 'admin'):
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.no_permission_export"))
        return

    try:
        if PDF_EXPORT_GUI_AVAILABLE and _pdf_export_gui_func is not None:
            _pdf_export_gui_func(self.root, self.auth)
            print(_t("extras_gui.messages.pdf_export_opened"))
        else:
            messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.pdf_export_not_available"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.pdf_export_failed").format(error=str(e)))
        logger.error(f"PDF Export GUI error: {e}")
def show_enhanced_reporting_dashboard(self):
    """Open the Enhanced Reporting GUI as a child window, with safe fallbacks."""
    try:
        if not ENHANCED_REPORTING_GUI_AVAILABLE or ReportingSystemGUI is None:
            messagebox.showerror(
                _t("extras_gui.titles.enhanced_reporting"),
                _t("extras_gui.errors.enhanced_reporting_not_available")
            )
            return

        # Prefer embedding into a Toplevel to avoid creating a second Tk root
        try:
            top = tk.Toplevel(self.root)
            _install_clean_close(top)
            top.title(_t("extras_gui.titles.enhanced_reporting_dashboard"))
            top.geometry("1200x800")
            try:
                top.transient(self.root)
                top.grab_set()
            except Exception as e:
                logger.debug(f"Could not set window as transient or grab focus: {e}")

            # Instantiate the GUI into the Toplevel container
            app = ReportingSystemGUI(top)

            # If the reporting GUI supports auth injection, pass it
            try:
                if hasattr(app, "set_auth"):
                    app.set_auth(self.auth)
            except Exception as e:
                logger.debug(f"Could not set auth on app: {e}")

            print(_t("extras_gui.messages.enhanced_reporting_opened"))

        except Exception as embed_err:
            # Fallback to its own launcher (may create its own Tk root)
            try:
                if start_enhanced_reporting_gui:
                    start_enhanced_reporting_gui()
                else:
                    raise RuntimeError(_t("extras_gui.errors.enhanced_reporting_launcher_not_available"))
            except Exception as launch_err:
                messagebox.showerror(
                    _t("extras_gui.titles.enhanced_reporting"),
                    _t("extras_gui.errors.enhanced_reporting_launch_failed").format(error=launch_err)
                )
                print(_t("extras_gui.messages.enhanced_reporting_error").format(launch_err=launch_err, embed_err=embed_err))

    except Exception as e:
        messagebox.showerror(_t("extras_gui.titles.enhanced_reporting"), _t("extras_gui.errors.unexpected_error").format(error=e))
        print(_t("extras_gui.messages.unexpected_enhanced_reporting_error").format(error=e))
def show_student_analytics_gui(self):
    """Launch the Student Analytics GUI"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), "Please log in to access Student Analytics.")
        return

    try:
        from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
            STUDENT_ANALYTICS_GUI_AVAILABLE, GUIStudentAnalytics
        )
        if not STUDENT_ANALYTICS_GUI_AVAILABLE or GUIStudentAnalytics is None:
            messagebox.showerror("Student Analytics", "Student Analytics GUI is not available.")
            return

        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title("Student Analytics")
        window.geometry("1400x900")
        try:
            window.transient(self.root)
        except Exception:
            pass
        GUIStudentAnalytics(root=window, auth_manager=self.auth)
        print("Student Analytics GUI opened")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Student Analytics: {e}")
        logger.error(f"Student Analytics GUI error: {e}")
def show_predictive_analytics_gui(self):
    """Launch the Predictive Analytics GUI"""
    launch_predictive_analytics_gui(self.root, self.auth)
def show_business_intelligence_gui(self):
    """Launch the Business Intelligence GUI"""
    launch_business_intelligence_gui(self.root, self.auth)
def show_advanced_search_gui(self):
    """Open Advanced Search GUI in a new window"""
    if not ADVANCED_SEARCH_GUI_AVAILABLE:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.advanced_search_not_available"))
        return

    try:
        # Create a new window for the Advanced Search GUI
        search_window = tk.Toplevel(self.root)
        _install_clean_close(search_window)
        search_window.title(_t("extras_gui.titles.advanced_search"))
        search_window.geometry("1200x800")
        search_window.transient(self.root)

        # Center the window
        search_window.update_idletasks()
        x = (search_window.winfo_screenwidth() - search_window.winfo_width()) // 2
        y = (search_window.winfo_screenheight() - search_window.winfo_height()) // 2
        search_window.geometry(f"+{x}+{y}")

        # Initialize the Advanced Search GUI in the new window
        self.advanced_search_gui = AdvancedSearchGUI(search_window, auth=self.auth)

        # Store reference for data refresh
        self.advanced_search_refresh_callback = self.advanced_search_gui.refresh_data

        print(_t("extras_gui.messages.advanced_search_opened"))

    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.advanced_search_failed").format(error=str(e)))
        print(_t("extras_gui.messages.advanced_search_error").format(error=e))
def refresh_advanced_search(self):
    """Refresh the Advanced Search GUI if it's open"""
    if hasattr(self, 'advanced_search_refresh_callback') and self.advanced_search_refresh_callback:
        try:
            # Check if the Advanced Search window still exists before refreshing
            if (hasattr(self, 'advanced_search_gui') and
                    hasattr(self.advanced_search_gui, 'master') and
                    self.advanced_search_gui.master.winfo_exists()):
                self.advanced_search_refresh_callback()
                print(_t("extras_gui.messages.advanced_search_refreshed"))
            else:
                # Window was closed, clear the stale callback
                self.advanced_search_refresh_callback = None
        except tk.TclError:
            # Window was destroyed, clear the callback
            self.advanced_search_refresh_callback = None
        except Exception as e:
            print(_t("extras_gui.messages.advanced_search_refresh_warning").format(error=e))
def show_integration_marketplace_gui(self):
    """Launch the Integration Marketplace GUI"""
    launch_integration_marketplace_gui(auth=self.auth, parent=self.root)
def show_exam_scheduler_gui(self):
    """Launch the Exam Scheduler GUI - student gets read-only viewer, staff/admin gets full app"""
    try:
        # Determine user role
        role = None
        if self.auth and self.auth.current_user:
            role = self.auth.current_user.get('role')

        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title(_t("extras_gui.titles.exam_scheduler"))
        window.geometry("1100x700")
        try:
            window.transient(self.root)
        except Exception:
            pass

        if role == 'student':
            # Students get read-only exam viewer
            from education_system.university_system.modules.domain.academics.gui.exam_management import StudentExamViewer
            StudentExamViewer(window, auth=self.auth)
        else:
            # Staff/admin get full exam scheduler
            from education_system.university_system.modules.domain.academics.gui.exam_management import ExamSchedulerApp
            ExamSchedulerApp(window)

        print(_t("extras_gui.messages.exam_scheduler_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.exam_scheduler_failed").format(error=str(e)))
        print(_t("extras_gui.messages.exam_scheduler_error").format(error=e))

def show_exam_portal(self):
    """Launch the unified Exam Management GUI (portal + scheduler) in a Toplevel window"""
    try:
        from education_system.university_system.modules.domain.academics.gui.exam_management import ExamPortalGUI
        window = tk.Toplevel(self.root)
        _install_clean_close(window)
        window.title("Exam Management")
        # Match Finance Management's sizing — WM clips to the work area
        # which reads as "fills the screen" on a typical desktop.
        window.geometry("1400x900")
        window.minsize(1200, 800)
        try:
            window.transient(self.root)
        except Exception:
            pass
        ExamPortalGUI(parent=window, auth=self.auth)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Exam Management: {e}")

def show_hesa_export_gui(self):
    """Launch HESA Data Export inside the main GUI's content notebook
    when a workspace is available, falling back to a Toplevel
    otherwise — same pattern as Student Records (8.117.38)."""
    try:
        from education_system.university_system.modules.domain.admissions.hesa_export.gui.hesa_export_gui import HESAExportGUI
    except ImportError as e:
        logger.error(f"Failed to import HESA Export GUI: {e}")
        messagebox.showerror(_t("common.error"), f"HESA Export GUI not available: {e}")
        return

    title = "HESA Export"
    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: HESAExportGUI(parent=host))
        return

    try:
        HESAExportGUI(parent=self.root)
    except Exception as e:
        logger.error(f"Error launching HESA Export GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch HESA Export: {e}")


def show_clearing_adjustment_gui(self):
    """Launch Clearing & Adjustment inside the main GUI's content
    notebook when a workspace is available, falling back to a
    Toplevel otherwise — same pattern as Student Records (8.117.38)."""
    try:
        from education_system.university_system.modules.domain.academics.clearing_adjustment.gui.clearing_adjustment_gui import ClearingAdjustmentGUI
    except ImportError as e:
        logger.error(f"Failed to import Clearing & Adjustment GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Clearing & Adjustment GUI not available: {e}")
        return

    title = "Clearing & Adjustment"
    opener = getattr(self, "open_in_workspace", None)
    if callable(opener):
        opener(title, lambda host: ClearingAdjustmentGUI(parent=host))
        return

    try:
        ClearingAdjustmentGUI(parent=self.root)
    except Exception as e:
        logger.error(f"Error launching Clearing & Adjustment GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Clearing & Adjustment: {e}")
