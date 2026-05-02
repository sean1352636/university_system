# Auto-generated module for Student Success & Engagement GUIs
import tkinter as tk
from tkinter import ttk, messagebox
import logging

# Import GUI launchers
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    launch_advanced_attendance_gui,
    launch_mental_health_gui,
    launch_early_warning_gui,
    launch_career_services_gui,
    launch_ai_features_gui,
    launch_blockchain_credentials_gui,
    launch_mobile_app_pwa_gui,
    EXTRAS_LAUNCHER_AVAILABLE,
    launch_extras_gui,
)

# Alias for translation function
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = logging.getLogger(__name__)

def show_academic_progress_gui(self):
    """Launch Academic Progress Dashboard GUI"""
    try:
        from education_system.university_system.modules.domain.academics.academic_progress.gui.progress_gui import AcademicProgressGUI
        # AcademicProgressGUI creates its own window
        gui = AcademicProgressGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Academic Progress GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Academic Progress", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Academic Progress GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Academic Progress", error=str(e)))

def show_ai_study_gui(self):
    """Launch AI Study Companion GUI"""
    try:
        from education_system.university_system.modules.domain.academics.ai_study.gui.ai_study_gui import AIStudyGUI
        gui = AIStudyGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import AI Study GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="AI Study", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching AI Study GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="AI Study", error=str(e)))

def show_budget_tracker_gui(self):
    """Launch Budget Tracker GUI"""
    try:
        from education_system.university_system.modules.domain.finance.budget.gui.budget_gui import BudgetTrackerGUI
        from education_system.university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        gui = BudgetTrackerGUI(parent=self.root, auth=auth)
    except ImportError as e:
        logger.error(f"Failed to import Budget Tracker GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Budget Tracker", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Budget Tracker GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Budget Tracker", error=str(e)))

def show_student_jobs_gui(self):
    """Launch Student Job Board GUI"""
    try:
        from education_system.university_system.modules.domain.career.student_jobs.gui.jobs_gui import StudentJobsGUI
        from education_system.university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        gui = StudentJobsGUI(parent=self.root, auth=auth)
    except ImportError as e:
        logger.error(f"Failed to import Student Jobs GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Student Jobs", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Student Jobs GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Student Jobs", error=str(e)))

def show_scholarship_finder_gui(self):
    """Launch Scholarship Finder GUI"""
    try:
        from education_system.university_system.modules.domain.finance.scholarship_finder.gui.scholarship_gui import ScholarshipFinderGUI
        gui = ScholarshipFinderGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Scholarship Finder GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Scholarship Finder", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Scholarship Finder GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Scholarship Finder", error=str(e)))

def show_study_matching_gui(self):
    """Launch Peer Study Matching GUI with the academic quick-switch bar
    injected at the top of the GUI's internal Toplevel."""
    try:
        from education_system.university_system.modules.domain.academics.study_matching.gui.study_matching_gui import StudyMatchingGUI
        from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
            attach_quickbar, consume_context, format_context, style_guarded,
        )
        with style_guarded(self.root):
            gui = StudyMatchingGUI(parent=self.root, auth=self.auth)
        # Re-bind a Destroy guard once we have the real window handle.
        try:
            _w = getattr(gui, "window", None)
            if _w is not None:
                from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
                    _snapshot_base_styles, _restore_base_styles,
                )
                _t, _s = _snapshot_base_styles()
                _w.bind(
                    "<Destroy>",
                    lambda _e: _restore_base_styles(_t, _s, parent=self.root),
                    add="+",
                )
        except Exception:
            logger.exception("Could not bind style-guard destroy hook for Study Matching")
        # The GUI stores its Toplevel as `gui.window` and packs a notebook
        # as the first child; inject the back-to-hub button above that
        # notebook.
        try:
            window = getattr(gui, "window", None)
            notebook = getattr(gui, "notebook", None)
            if window is not None:
                from education_system.university_system.modules.shared.gui.main.features.academic_launchers_gui import (
                    _attach_back_to_hub_button,
                )
                _attach_back_to_hub_button(window, self, before=notebook)
                ctx = consume_context(self)
                if ctx:
                    try:
                        window.title(window.title()
                                     + f"  ◆ {format_context(ctx)}")
                    except Exception:
                        pass
        except Exception:
            logger.exception("Could not attach quickbar to Study Matching")
    except ImportError as e:
        logger.error(f"Failed to import Study Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Study Matching", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Study Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Study Matching", error=str(e)))

def show_course_planning_gui(self):
    """Launch Course Planning Assistant GUI"""
    try:
        from education_system.university_system.modules.domain.academics.gui.course_management_gui.course_planning_gui import CoursePlanningGUI
        from education_system.university_system.infrastructure.shared_context import get_auth
        auth = get_auth()
        # CoursePlanningGUI creates its own Toplevel window
        gui = CoursePlanningGUI(root=self.root, auth=auth)
    except ImportError as e:
        logger.error(f"Failed to import Course Planning GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Course Planning", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Course Planning GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Course Planning", error=str(e)))

def show_roommate_finder_gui(self):
    """Launch Roommate Finder — now a sub-view inside the Housing GUI."""
    try:
        import tkinter as tk
        from education_system.university_system.modules.domain.housing.gui.housing_accommodation_gui.main_gui import HousingGUI
        HousingGUI(parent=tk.Toplevel(self.root), auth_instance=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Housing GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Roommate Finder", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Housing GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Roommate Finder", error=str(e)))

def show_campus_navigation_gui(self):
    """Launch Campus Navigation GUI"""
    try:
        import tkinter as tk
        from education_system.university_system.modules.domain.campus.campus_navigation.gui.navigation_gui import NavigationGUI
        # Create a new Toplevel window
        window = tk.Toplevel(self.root)
        window.title(_t("student_success.windows.campus_navigation"))
        window.geometry("1200x800")
        gui = NavigationGUI(parent=window)
    except ImportError as e:
        logger.error(f"Failed to import Campus Navigation GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Campus Navigation", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Campus Navigation GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Campus Navigation", error=str(e)))

def show_lost_found_gui(self):
    """Launch Lost & Found GUI"""
    try:
        from education_system.university_system.modules.domain.campus.lost_found.gui.lost_found_gui import LostFoundGUI
        gui = LostFoundGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Lost & Found GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Lost & Found", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Lost & Found GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Lost & Found", error=str(e)))

def show_marketplace_gui(self):
    """Launch Student Marketplace GUI.

    If a contextual right-click brought the user here (e.g. Library →
    "Find on Student Marketplace"), the academic context dict is
    consumed and the marketplace's ``search_var`` is pre-filled with
    the book title / ISBN before ``perform_search`` runs."""
    ctx = _consume_library_book_context(self)
    try:
        from education_system.university_system.modules.domain.commerce.marketplace.gui.marketplace_gui import MarketplaceGUI
        gui = MarketplaceGUI(parent=self.root, auth=self.auth)
        _prefill_marketplace_search(gui, ctx)
    except ImportError as e:
        logger.error(f"Failed to import Student Marketplace GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Student Marketplace", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Student Marketplace GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Student Marketplace", error=str(e)))


def _consume_library_book_context(parent_app):
    """Consume the pending academic context if it carries a book-shaped
    payload (book_title / isbn / book_id). Returns the search term, or
    None. Always clears the parent's pending context so later jumps are
    not contaminated."""
    try:
        from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
            consume_context as _consume,
        )
        ctx = _consume(parent_app) or {}
    except Exception:
        return None
    return (ctx.get("book_title") or ctx.get("isbn")
            or ctx.get("book_id") or None)


def _prefill_marketplace_search(gui, term):
    """If a search term is supplied, drop it into the Marketplace's
    ``search_var`` and trigger ``perform_search``. Best-effort."""
    if not term:
        return
    try:
        var = getattr(gui, "search_var", None)
        if var is None:
            return
        var.set(str(term))
        do_search = getattr(gui, "perform_search", None)
        if callable(do_search):
            do_search()
    except Exception:
        logger.debug("marketplace prefill failed", exc_info=True)

def show_wellness_hub_gui(self):
    """Launch Wellness Hub GUI"""
    try:
        from education_system.university_system.modules.domain.student_affairs.wellness.gui.wellness_gui import WellnessGUI
        gui = WellnessGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Wellness Hub GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Wellness Hub", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Wellness Hub GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Wellness Hub", error=str(e)))

def show_accessibility_portal_gui(self):
    """Launch Accessibility Portal GUI"""
    try:
        from education_system.university_system.modules.domain.campus.accessibility.gui.accessibility_gui import AccessibilityGUI
        gui = AccessibilityGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Accessibility Portal GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Accessibility Portal", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Accessibility Portal GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Accessibility Portal", error=str(e)))

def show_events_discovery_gui(self):
    """Launch Events Discovery GUI"""
    try:
        import tkinter as tk
        from education_system.university_system.modules.domain.events.gui.events_gui import EventsGUI
        # Create a new Toplevel window
        window = tk.Toplevel(self.root)
        window.title(_t("student_success.windows.event_discovery"))
        window.geometry("1400x800")
        gui = EventsGUI(parent=window)
    except ImportError as e:
        logger.error(f"Failed to import Events Discovery GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Events Discovery", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Events Discovery GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Events Discovery", error=str(e)))

def show_social_matching_gui(self):
    """Launch Social Matching GUI"""
    try:
        from education_system.university_system.modules.domain.student_affairs.social_matching.gui.social_matching_gui import SocialMatchingGUI
        gui = SocialMatchingGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Social Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Social Matching", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Social Matching GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Social Matching", error=str(e)))

def show_portfolio_system_gui(self):
    """Launch Portfolio System GUI"""
    try:
        from education_system.university_system.modules.domain.events.portfolio.gui.portfolio_gui import PortfolioGUI
        gui = PortfolioGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Portfolio System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Portfolio System", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Portfolio System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Portfolio System", error=str(e)))

def show_notifications_hub_gui(self):
    """Launch Email Manager with Notifications tab focused"""
    try:
        # Import email manager GUI
        from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI
        import tkinter as tk

        # Create new window for email manager
        email_window = tk.Toplevel(self.root)
        email_window.title(_t("student_success.windows.communication_center"))
        email_window.geometry("1200x800")

        # Create email manager GUI
        email_gui = EmailManagerGUI(email_window, auth=self.auth)

        # Switch to notifications tab after window is created
        if hasattr(email_gui, 'show_notifications_tab'):
            email_window.after(100, email_gui.show_notifications_tab)

        logger.info("Opened Email Manager with Notifications tab")
    except ImportError as e:
        logger.error(f"Failed to import Email Manager GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Email Manager", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Email Manager: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Email Manager", error=str(e)))

def show_feedback_system_gui(self):
    """Launch Feedback System GUI"""
    try:
        from education_system.university_system.modules.domain.communications.feedback.gui.feedback_gui import FeedbackGUI
        gui = FeedbackGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Feedback System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Feedback System", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Feedback System GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Feedback System", error=str(e)))

def show_advising_portal_gui(self):
    """Launch Academic Advising Portal GUI"""
    try:
        from education_system.university_system.modules.domain.academics.advising.gui.advising_gui import AdvisingPortalGUI
        gui = AdvisingPortalGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Advising Portal GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Advising Portal", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Advising Portal GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Advising Portal", error=str(e)))

def show_student_id_gui(self):
    """Launch Digital Student ID GUI"""
    try:
        from education_system.university_system.modules.domain.student_affairs.student_id.gui.student_id_gui import StudentIDGUI
        gui = StudentIDGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Student ID GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Student ID", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Student ID GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Student ID", error=str(e)))

def show_study_room_booking_gui(self):
    """Launch Study Room Booking GUI.

    Consumes (and discards) any pending academic context so a stale
    book/student id from a Library → "Book a study room" right-click
    can't bleed into the next jump. The Study Room GUI's filters
    (date / building / type) don't currently take a student or book
    pre-filter, so no prefill happens — the user lands on today's
    availability."""
    try:
        from education_system.university_system.modules.shared.gui.main.features.academic_link_bar import (
            consume_context as _consume,
        )
        _consume(self)
    except Exception:
        pass

    try:
        from education_system.university_system.modules.domain.campus.study_rooms.gui.study_room_gui import StudyRoomBookingGUI
        gui = StudyRoomBookingGUI(parent=self.root)
    except ImportError as e:
        logger.error(f"Failed to import Study Room Booking GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Study Room Booking", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Study Room Booking GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Study Room Booking", error=str(e)))

def show_printing_services_gui(self):
    """Launch Printing Services GUI.

    If a contextual right-click brought the user here (e.g. Library →
    "Photocopy this book"), the academic context's book title is
    consumed and dropped into the Submit Print Job tab's file-name
    entry so the print form is half-filled out on arrival."""
    term = _consume_library_book_context(self)
    try:
        from education_system.university_system.modules.domain.campus.printing.gui.printing_gui import PrintingServicesGUI
        gui = PrintingServicesGUI(parent=self.root)
        _prefill_printing_job(gui, term)
    except ImportError as e:
        logger.error(f"Failed to import Printing Services GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Printing Services", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Printing Services GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Printing Services", error=str(e)))


def _prefill_printing_job(gui, term):
    """Select the Submit Print Job tab (index 1) and pre-populate
    ``file_entry`` with the supplied title. Best-effort — the GUI
    layout could change; on any error the user just sees a vanilla
    Quota tab."""
    if not term:
        return
    try:
        nb = getattr(gui, "notebook", None)
        if nb is not None:
            try:
                nb.select(1)
            except Exception:
                pass
        entry = getattr(gui, "file_entry", None)
        if entry is None:
            return
        try:
            entry.delete(0, "end")
            entry.insert(0, str(term))
        except Exception:
            return
    except Exception:
        logger.debug("printing services prefill failed", exc_info=True)

def show_textbook_store_gui(self):
    """Launch Textbook & Course Materials GUI.

    If a contextual right-click brought the user here, the search box
    is pre-filled with the book title / ISBN and ``_search_textbooks``
    is triggered so the matching exchange listings surface
    immediately."""
    term = _consume_library_book_context(self)
    try:
        from education_system.university_system.modules.domain.commerce.textbooks.gui.textbook_gui import TextbookStoreGUI
        gui = TextbookStoreGUI(parent=self.root)
        _prefill_textbook_search(gui, term)
    except ImportError as e:
        logger.error(f"Failed to import Textbook Store GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.gui_not_available", feature="Textbook Store", error=str(e)))
    except Exception as e:
        logger.error(f"Error launching Textbook Store GUI: {e}")
        messagebox.showerror(_t("common.error"), _t("student_success.errors.failed_to_launch", feature="Textbook Store", error=str(e)))


def _prefill_textbook_search(gui, term):
    """Drop the search term into the textbook store's search Entry
    (which is a plain ``ttk.Entry``, not backed by a StringVar) and
    trigger ``_search_textbooks``."""
    if not term:
        return
    try:
        entry = getattr(gui, "search_entry", None)
        if entry is None:
            return
        try:
            entry.delete(0, "end")
            entry.insert(0, str(term))
        except Exception:
            return
        do_search = getattr(gui, "_search_textbooks", None)
        if callable(do_search):
            do_search()
    except Exception:
        logger.debug("textbook store prefill failed", exc_info=True)

def show_ai_features_gui(self):
    """Launch the Ai Features GUI"""
    launch_ai_features_gui(self.root, self.auth)
def show_blockchain_credentials_gui(self):
    """Launch the Blockchain Credentials & Digital Badges GUI"""
    launch_blockchain_credentials_gui(auth=self.auth)
def show_mobile_app_pwa_gui(self):
    """Launch the Mobile App (PWA) Infrastructure GUI"""
    launch_mobile_app_pwa_gui(auth=self.auth)
def show_extras_launcher(self):
    """Launch the Extras & Tools Launcher (games, utilities, mini-projects)"""
    if not EXTRAS_LAUNCHER_AVAILABLE:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.extras_launcher_not_available"))
        return

    try:
        launch_extras_gui(self.root)
        print(_t("extras_gui.messages.extras_launcher_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.extras_launcher_failed").format(error=str(e)))
        print(_t("extras_gui.messages.extras_launcher_error").format(error=e))
def show_todo_app_gui(self):
    """Launch the To-Do List GUI"""
    try:
        from education_system.university_system.modules.shared.gui.tools.todo_app_gui import TodoApp
        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.todo_list"))
        window.geometry("500x600")
        try:
            window.transient(self.root)
        except Exception:
            pass
        TodoApp(window)
        print(_t("extras_gui.messages.todo_list_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.todo_list_failed").format(error=str(e)))
        print(_t("extras_gui.messages.todo_list_error").format(error=e))
def show_accessibility_tools_gui(self):
    """Launch the Accessibility & Accommodation Tools GUI"""
    try:
        from education_system.university_system.modules.domain.student_affairs.gui.accessibility_tools_gui import (
            launch_accessibility_tools_gui
        )
        launch_accessibility_tools_gui(self.root, self.auth)
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.accessibility_tools_failed").format(error=str(e)))
        print(_t("extras_gui.messages.accessibility_tools_error").format(error=e))
def _show_feature_gui(self, title, description, cli_instruction):
    """Generic method to show feature GUI window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_feature").format(title=title))
        return

    try:
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("900x600")
        window.minsize(800, 500)

        main_frame = ttk.Frame(window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=title, font=('Arial', 16, 'bold')).pack(pady=10)
        ttk.Label(main_frame, text=description, justify=tk.LEFT, wraplength=800).pack(pady=10)

        info_frame = ttk.LabelFrame(main_frame, text=_t("extras_gui.labels.how_to_access"), padding="15")
        info_frame.pack(fill=tk.X, pady=20)
        ttk.Label(info_frame, text=cli_instruction, font=('Arial', 11)).pack()

        ttk.Button(main_frame, text=_t("extras_gui.buttons.close"), command=window.destroy).pack(pady=10)

        print(_t("extras_gui.messages.feature_opened").format(title=title))

    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.feature_failed").format(title=title, error=str(e)))
        print(_t("extras_gui.messages.feature_error").format(title=title, error=e))

def show_student_app_gui(self):
    """Launch Student App / Portal GUI"""
    try:
        from education_system.university_system.modules.domain.student_affairs.student_app.gui.student_app_gui import StudentAppGUI
        gui = StudentAppGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Student App GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Student App GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching Student App GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Student App: {e}")


def show_achievement_badge_gui(self):
    """Launch Achievement Badge GUI"""
    try:
        from education_system.university_system.modules.domain.student_affairs.achievement_badges.gui.achievement_badge_gui import AchievementBadgeGUI
        gui = AchievementBadgeGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Achievement Badge GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Achievement Badge GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching Achievement Badge GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Achievement Badges: {e}")


def show_study_recommendations_gui(self):
    """Launch Study Recommendations GUI"""
    try:
        from education_system.university_system.modules.domain.academics.study_recommendations.gui.study_recommendation_gui import StudyRecommendationGUI
        gui = StudyRecommendationGUI(parent=self.root, auth=self.auth)
    except ImportError as e:
        logger.error(f"Failed to import Study Recommendations GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Study Recommendations GUI not available: {e}")
    except Exception as e:
        logger.error(f"Error launching Study Recommendations GUI: {e}")
        messagebox.showerror(_t("common.error"), f"Failed to launch Study Recommendations: {e}")
