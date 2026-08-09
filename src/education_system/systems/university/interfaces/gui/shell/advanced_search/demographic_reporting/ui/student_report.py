"""Public demographic-report GUI coordinator."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *
from .common import StudentUiCommonMixin
from .filter_panel import StudentUiFilterPanelMixin
from .results_table import StudentUiResultsTableMixin
from ..report_builder import StudentReportBuilderMixin
from ..exports.text_export import StudentExportsTextExportMixin
from ..exports.csv_export import StudentExportsCsvExportMixin
from ..notifications.admin_email import StudentNotificationsAdminEmailMixin

class StudentDemographicReportGUI(
    StudentUiCommonMixin,
    StudentUiFilterPanelMixin,
    StudentUiResultsTableMixin,
    StudentReportBuilderMixin,
    StudentExportsTextExportMixin,
    StudentExportsCsvExportMixin,
    StudentNotificationsAdminEmailMixin,
):
    def show_window(self):
        """Display the demographic reports window"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.master)
        self.window.title(_t('gui.shell.advanced_search.demographic_reporting.ui.student_report.windows.student_demographic_reports', default="Student Demographic Reports"))
        self.window.geometry("1350x900")
        self.window.transient(self.master)
        self.window.minsize(1200, 800)

        # Center window on screen
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 1350) // 2
        y = (self.window.winfo_screenheight() - 900) // 2
        self.window.geometry(f"+{x}+{y}")

        self._setup_styles()
        self._create_widgets()
        self._load_filter_options()

    def __init__(self, master, auth=None):
        self.master = master
        self.auth = auth
        self.window = None
        self.report_data = []
        self.filter_vars = {}
