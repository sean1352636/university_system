"""Main application class for the Exam Scheduling System."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.university_system.modules.domain.academics.gui.exam_scheduler.data_manager import DataManager
from education_system.university_system.modules.domain.academics.gui.exam_scheduler.tabs import ScheduleTabMixin, ExamsTabMixin, RoomsTabMixin, CalendarTabMixin
from education_system.university_system.modules.domain.academics.gui.exam_scheduler.dialogs import DialogsMixin

# i18n import
try:
    from education_system.university_system.modules.shared.utils.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key


class ExamSchedulerApp(ScheduleTabMixin, ExamsTabMixin, RoomsTabMixin, CalendarTabMixin, DialogsMixin):
    """Main application class for the Exam Scheduling System."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(_("exam_scheduler.title"))
        self.root.geometry("1200x700")
        self.root.minsize(1000, 600)

        # Initialize data manager
        self.data_manager = DataManager()

        # Configure style
        self.setup_styles()

        # Create main layout
        self.create_menu()
        self.create_main_layout()

        # Load initial data
        self.refresh_exam_list()
        self.refresh_room_list()

    def setup_styles(self):
        """Configure ttk styles for the application."""
        style = ttk.Style()
        style.theme_use('clam')

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
