"""Church management application coordinator."""
from . import *
from .services.user_context import get_current_user
from .ui.dialogs.payment_dialog import PaymentDialog
from .services.user_context import ChurchServicesUserContextMixin
from .ui.shell import ChurchUiShellMixin
from .ui.pages.dashboard import ChurchUiPagesDashboardMixin
from .ui.pages.members import ChurchUiPagesMembersMixin
from .ui.dialogs.member_dialog import ChurchUiDialogsMemberDialogMixin
from .ui.pages.donations import ChurchUiPagesDonationsMixin
from .ui.dialogs.donation_dialog import ChurchUiDialogsDonationDialogMixin
from .ui.pages.events import ChurchUiPagesEventsMixin
from .ui.dialogs.event_dialog import ChurchUiDialogsEventDialogMixin
from .ui.pages.prayer_requests import ChurchUiPagesPrayerRequestsMixin
from .ui.dialogs.prayer_dialog import ChurchUiDialogsPrayerDialogMixin
from .ui.pages.sermons import ChurchUiPagesSermonsMixin
from .ui.dialogs.sermon_dialog import ChurchUiDialogsSermonDialogMixin
from .ui.pages.announcements import ChurchUiPagesAnnouncementsMixin
from .ui.dialogs.announcement_dialog import ChurchUiDialogsAnnouncementDialogMixin
from .ui.pages.volunteers import ChurchUiPagesVolunteersMixin
from .ui.dialogs.volunteer_dialog import ChurchUiDialogsVolunteerDialogMixin
from .ui.pages.attendance import ChurchUiPagesAttendanceMixin
from .ui.dialogs.attendance_dialog import ChurchUiDialogsAttendanceDialogMixin
from .ui.pages.small_groups import ChurchUiPagesSmallGroupsMixin
from .ui.dialogs.small_group_dialog import ChurchUiDialogsSmallGroupDialogMixin
from .ui.pages.expenses import ChurchUiPagesExpensesMixin
from .ui.dialogs.expense_dialog import ChurchUiDialogsExpenseDialogMixin
from .ui.pages.reports import ChurchUiPagesReportsMixin
from .services.reports import ChurchServicesReportsMixin
from .state import ChurchStateMixin
from .persistence.members import ChurchPersistenceMembersMixin
from .persistence.donations import ChurchPersistenceDonationsMixin
from .persistence.events import ChurchPersistenceEventsMixin
from .persistence.ministry import ChurchPersistenceMinistryMixin
from .persistence.engagement import ChurchPersistenceEngagementMixin
from .persistence.finance import ChurchPersistenceFinanceMixin

class ChurchManagementSystem(
    ChurchServicesUserContextMixin,
    ChurchUiShellMixin,
    ChurchUiPagesDashboardMixin,
    ChurchUiPagesMembersMixin,
    ChurchUiDialogsMemberDialogMixin,
    ChurchUiPagesDonationsMixin,
    ChurchUiDialogsDonationDialogMixin,
    ChurchUiPagesEventsMixin,
    ChurchUiDialogsEventDialogMixin,
    ChurchUiPagesPrayerRequestsMixin,
    ChurchUiDialogsPrayerDialogMixin,
    ChurchUiPagesSermonsMixin,
    ChurchUiDialogsSermonDialogMixin,
    ChurchUiPagesAnnouncementsMixin,
    ChurchUiDialogsAnnouncementDialogMixin,
    ChurchUiPagesVolunteersMixin,
    ChurchUiDialogsVolunteerDialogMixin,
    ChurchUiPagesAttendanceMixin,
    ChurchUiDialogsAttendanceDialogMixin,
    ChurchUiPagesSmallGroupsMixin,
    ChurchUiDialogsSmallGroupDialogMixin,
    ChurchUiPagesExpensesMixin,
    ChurchUiDialogsExpenseDialogMixin,
    ChurchUiPagesReportsMixin,
    ChurchServicesReportsMixin,
    ChurchStateMixin,
    ChurchPersistenceMembersMixin,
    ChurchPersistenceDonationsMixin,
    ChurchPersistenceEventsMixin,
    ChurchPersistenceMinistryMixin,
    ChurchPersistenceEngagementMixin,
    ChurchPersistenceFinanceMixin,
):
    """Coordinates church-management pages and services."""

    def __init__(self, root, current_user=None):
        self.root = root
        self.root.title(_t("church.window_title"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)
        self.root.configure(bg="#f5f5dc")

        # Get current user - require login
        self.current_user = current_user or get_current_user()

        if not self.current_user:
            messagebox.showerror(_t("church.errors.access_denied"),
                               _t("church.errors.login_required"))
            self.root.destroy()
            return

        # Data storage
        self.members = []
        self.donations = []
        self.events = []
        self.prayer_requests = []
        self.sermons = []
        self.announcements = []
        self.volunteers = []
        self.attendance_records = []
        self.small_groups = []
        self.expenses = []

        # Load existing data
        self.load_data()

        # Create main UI
        self.create_header()
        self.create_navigation()
        self.create_main_content()
        self.create_footer()

        # Show dashboard by default
        self.show_dashboard()

def main():
    """Main entry point for the application."""
    root = tk.Tk()
    app = ChurchManagementSystem(root)
    if hasattr(app, 'root') and app.root.winfo_exists():
        root.mainloop()
