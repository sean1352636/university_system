"""Public demographic-report GUI coordinator."""

from education_system.systems.university.infrastructure.i18n import get_text as _t
from .. import *
from .common import AdvancedUiCommonMixin
from .tabs.overview import AdvancedUiTabsOverviewMixin
from .tabs.analysis import AdvancedUiTabsAnalysisMixin
from .tabs.crosstab import AdvancedUiTabsCrosstabMixin
from .tabs.full_report import AdvancedUiTabsFullReportMixin
from ..controller import AdvancedControllerMixin
from ..calculations import AdvancedCalculationsMixin
from ..report_builder import AdvancedReportBuilderMixin
from ..exports.text_export import AdvancedExportsTextExportMixin
from ..exports.csv_export import AdvancedExportsCsvExportMixin
from ..notifications.admin_email import AdvancedNotificationsAdminEmailMixin

class AdvancedDemographicReportGUI(
    AdvancedUiCommonMixin,
    AdvancedUiTabsOverviewMixin,
    AdvancedUiTabsAnalysisMixin,
    AdvancedUiTabsCrosstabMixin,
    AdvancedUiTabsFullReportMixin,
    AdvancedControllerMixin,
    AdvancedCalculationsMixin,
    AdvancedReportBuilderMixin,
    AdvancedExportsTextExportMixin,
    AdvancedExportsCsvExportMixin,
    AdvancedNotificationsAdminEmailMixin,
):
    def show_window(self):
        """Display the advanced demographic report window"""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return

        self.window = tk.Toplevel(self.master)
        self.window.title(_t('gui.shell.advanced_search.demographic_reporting.ui.advanced_report.windows.advanced_demographic_report', default="Advanced Demographic Report"))
        self.window.geometry("1450x950")
        self.window.transient(self.master)
        self.window.minsize(1300, 850)

        # Center window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() - 1450) // 2
        y = (self.window.winfo_screenheight() - 950) // 2
        self.window.geometry(f"+{x}+{y}")

        self._setup_styles()
        self._create_widgets()

    def __init__(self, master, auth=None):
        self.master = master
        self.auth = auth
        self.window = None
        self.report_data = {}
        self.raw_data = []
