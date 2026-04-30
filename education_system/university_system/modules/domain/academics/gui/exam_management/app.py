"""Main application class for the Exam Scheduling System."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.university_system.modules.domain.academics.gui.exam_management.data_manager import DataManager
from education_system.university_system.modules.domain.academics.gui.exam_management.tabs import ScheduleTabMixin, ExamsTabMixin, RoomsTabMixin, CalendarTabMixin, DeferredExamTabMixin, AtRiskTabMixin, ExamEligibilityTabMixin, ResultsTabMixin
from education_system.university_system.modules.domain.academics.gui.exam_management.dialogs import DialogsMixin

# i18n import
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key


class ExamSchedulerApp(ScheduleTabMixin, ExamsTabMixin, RoomsTabMixin,
                       CalendarTabMixin, DeferredExamTabMixin,
                       AtRiskTabMixin, ExamEligibilityTabMixin,
                       ResultsTabMixin, DialogsMixin):
    """Main application class for the Exam Scheduling System."""

    def __init__(self, root):
        self.root = root
        self._is_embedded = not isinstance(root, (tk.Tk, tk.Toplevel))

        if not self._is_embedded:
            self.root.title(_("exam_scheduler.title"))
            self.root.geometry("1200x700")
            self.root.minsize(1000, 600)

        # Initialize data manager
        self.data_manager = DataManager()

        # Configure style
        self.setup_styles()

        # Create main layout
        if not self._is_embedded:
            self.create_menu()
        self.create_main_layout()

        # Load initial data
        self.refresh_exam_list()
        self.refresh_room_list()

        # Live refresh: when sibling GUIs change module schedules or
        # student enrolment, re-pull exam data so this view doesn't
        # show stale rosters or hidden room conflicts.
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                subscribe_tk,
                EVENT_MODULE_SCHEDULE_CHANGED,
                EVENT_ENROLMENT_CHANGED,
                EVENT_ASSESSMENT_CHANGED,
            )

            def _on_external_change(**_payload):
                if hasattr(self, "refresh_exam_list"):
                    self.refresh_exam_list()
                if hasattr(self, "refresh_room_list"):
                    self.refresh_room_list()

            subscribe_tk(EVENT_MODULE_SCHEDULE_CHANGED, self.root, _on_external_change)
            subscribe_tk(EVENT_ENROLMENT_CHANGED, self.root, _on_external_change)
            subscribe_tk(EVENT_ASSESSMENT_CHANGED, self.root, _on_external_change)
        except Exception:
            pass

    def setup_styles(self):
        """Configure ttk styles for the application."""
        style = ttk.Style()
        # ttk.Style is process-global. Only switch themes when this app
        # owns its Tk root; if we're embedded in a parent window inherit
        # its theme so the parent isn't restyled.
        prev_theme = style.theme_use()
        if not self._is_embedded:
            try:
                style.theme_use('clam')
            except tk.TclError:
                pass
            self.root.bind(
                "<Destroy>",
                lambda _e, p=prev_theme, s=style: (
                    s.theme_use(p) if _e.widget is self.root else None
                ),
                add="+",
            )

        # Configure colors
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        style.configure('TNotebook.Tab', padding=[20, 10])
        style.configure('Accent.TButton', font=('Helvetica', 10, 'bold'))

        # Treeview styling
        style.configure('Treeview', rowheight=28, font=('Helvetica', 10))
        style.configure('Treeview.Heading', font=('Helvetica', 10, 'bold'))

    def create_menu(self):
        """Create the application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("exam_scheduler.menu.file"), menu=file_menu)
        file_menu.add_command(label=_("exam_scheduler.menu.export_csv"), command=self.export_schedule)
        file_menu.add_separator()
        file_menu.add_command(label=_("exam_scheduler.menu.exit"), command=self.root.quit)

        # Open — cross-launch sibling academic GUIs in their own Toplevels.
        # Imports lazy via the central _cross_launchers helper so this stays
        # cycle-safe.
        from education_system.university_system.modules.domain.academics.gui._cross_launchers import (
            open_grade_gui, open_module_gui, open_course_gui,
        )
        open_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Open", menu=open_menu)
        open_menu.add_command(
            label="Grade Tracking",
            command=lambda: open_grade_gui(self.root, getattr(self, "auth", None)),
        )
        open_menu.add_command(
            label="Module Scheduling",
            command=lambda: open_module_gui(self.root, getattr(self, "auth", None)),
        )
        open_menu.add_command(
            label="Course Management",
            command=lambda: open_course_gui(self.root, getattr(self, "auth", None)),
        )

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("exam_scheduler.menu.help"), menu=help_menu)
        help_menu.add_command(label=_("exam_scheduler.menu.about"), command=self.show_about)

    def create_main_layout(self):
        """Create the main application layout with tabs."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_("exam_scheduler.title"),
                               style='Title.TLabel')
        title_label.pack(pady=(0, 10))

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_schedule_tab()
        self.create_exams_tab()
        self.create_rooms_tab()
        self.create_calendar_tab()
        self.create_deferred_tab()
        self.create_at_risk_tab()
        self.create_eligibility_tab()
        self.create_results_tab()

    def export_schedule(self):
        """Export the schedule to a CSV file."""
        if not self.data_manager.exams:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.no_exams_to_export"))
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[(_("exam_scheduler.filetypes.csv"), "*.csv"), (_("exam_scheduler.filetypes.all"), "*.*")],
            initialfile="exam_schedule.csv"
        )

        if filepath:
            self.data_manager.export_to_csv(filepath)
            messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.schedule_exported", filepath=filepath))

    def show_about(self):
        """Show the about dialog."""
        about_text = _("exam_scheduler.about.text")

        messagebox.showinfo(_("exam_scheduler.menu.about"), about_text)


def main():
    """Main entry point."""
    root = tk.Tk()
    app = ExamSchedulerApp(root)
    root.mainloop()
