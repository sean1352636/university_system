"""
Admin Portal for Financial Aid & Scholarships

Core class that composes all mixin modules via multiple inheritance.
"""

from typing import Any, Dict

from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal._imports import (
    tk, ttk, logging,
    get_connection, get_auth,
    FinancialAidManager,
    clear_frame, create_stat_card,
    format_currency,
    get_current_academic_year,
    get_text,
)
from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.scholarship_manager import ScholarshipManagerGUI

from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal.applications import ApplicationsMixin
from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal.packages import PackagesMixin
from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal.aid_types import AidTypesMixin
from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal.disbursements import DisbursementsMixin
from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal.reports import ReportsMixin
from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal.report_export import ReportExportMixin
from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.admin_portal.fafsa_import import FAFSAImportMixin

logger = logging.getLogger(__name__)


class AdminPortal(
    ApplicationsMixin,
    PackagesMixin,
    AidTypesMixin,
    DisbursementsMixin,
    ReportsMixin,
    ReportExportMixin,
    FAFSAImportMixin,
):
    """Admin-facing portal for financial aid and scholarships management"""

    def __init__(self, parent_frame, auth_instance=None):
        """
        Initialize admin portal

        Args:
            parent_frame: Parent tkinter frame
            auth_instance: Authentication instance
        """
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.aid_manager = FinancialAidManager()
        self.scholarship_manager_gui = ScholarshipManagerGUI(parent_frame, auth_instance)
        self.standalone_window = None

    def _ensure_valid_parent(self):
        """
        Ensure parent frame exists, create standalone window if needed

        Returns:
            Valid parent frame/window
        """
        try:
            if self.parent_frame is not None:
                master = getattr(self.parent_frame, 'master', None)
                name = getattr(self.parent_frame, '_name', None)
                if (
                    master is not None and
                    name and
                    getattr(master, 'children', {}).get(name) is self.parent_frame and
                    int(self.parent_frame.tk.call('winfo', 'exists', str(self.parent_frame))) == 1
                ):
                    return self.parent_frame
        except Exception:
            pass

        # Parent frame doesn't exist, create standalone window
        try:
            if self.standalone_window is not None and self.standalone_window.winfo_exists():
                return self.standalone_window
        except Exception:
            pass

        self.standalone_window = tk.Toplevel()
        self.standalone_window.title(get_text("financial_aid.admin_portal.window_title", "Financial Aid Administration"))
        self.standalone_window.geometry("1200x800")
        logger.info("Created standalone window for financial aid administration")

        return self.standalone_window

    def _prepare_view_parent(self):
        """Return a fresh content frame for the current view."""
        host = self._ensure_valid_parent()
        clear_frame(host)
        content = ttk.Frame(host)
        content.pack(fill='both', expand=True)
        marker = ttk.Frame(content)
        marker.pack_forget()
        original_winfo_children = content.winfo_children
        content.winfo_children = lambda: original_winfo_children() or [marker]
        self.parent_frame = content
        return content

    def show_dashboard(self):
        """Display admin dashboard"""
        self._prepare_view_parent()

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.title", "Financial Aid & Scholarships - Admin Dashboard"),
                 style='Title.TLabel').pack(anchor='w')

        # Statistics cards
        stats_frame = ttk.Frame(self.parent_frame)
        stats_frame.pack(fill='x', padx=10, pady=10)

        try:
            stats = self._get_admin_stats()

            cards = [
                (get_text("financial_aid.admin_portal.stats.pending_reviews", "Pending Reviews"), str(stats['pending_reviews']), 'warning'),
                (get_text("financial_aid.admin_portal.stats.active_packages", "Active Aid Packages"), str(stats['active_packages']), 'info'),
                (get_text("financial_aid.admin_portal.stats.total_disbursed", "Total Disbursed (Year)"), format_currency(stats['total_disbursed']), 'success'),
                (get_text("financial_aid.admin_portal.stats.pending_disbursements", "Pending Disbursements"), format_currency(stats['pending_disbursements']), 'primary')
            ]

            for i, (title, value, color) in enumerate(cards):
                card = create_stat_card(stats_frame, title, value, color)
                card.grid(row=0, column=i, padx=10, pady=5, sticky='ew')
                stats_frame.grid_columnconfigure(i, weight=1)

        except Exception as e:
            logger.error(f"Error loading stats: {e}")

        # Quick actions grid
        actions_frame = ttk.LabelFrame(self.parent_frame, text=get_text("financial_aid.admin_portal.sections.management_functions", "Management Functions"), padding=10)
        actions_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Row 1: Scholarship Management
        ttk.Label(actions_frame, text=get_text("financial_aid.admin_portal.sections.scholarship_management", "Scholarship Management"),
                 font=('Arial', 11, 'bold')).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        actions_row1 = [
            (get_text("financial_aid.admin_portal.buttons.manage_scholarships", "Manage Scholarships"), self.scholarship_manager_gui.show_scholarships),
            (get_text("financial_aid.admin_portal.buttons.review_applications", "Review Applications"), self.scholarship_manager_gui.review_applications),
            (get_text("financial_aid.admin_portal.buttons.view_awards", "View Awards"), self.scholarship_manager_gui.show_awards)
        ]

        for i, (text, command) in enumerate(actions_row1):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=1, column=i, padx=5, pady=5, sticky='ew')

        # Row 2: Financial Aid Management
        ttk.Label(actions_frame, text=get_text("financial_aid.admin_portal.sections.financial_aid_management", "Financial Aid Management"),
                 font=('Arial', 11, 'bold')).grid(row=2, column=0, columnspan=3, sticky='w', pady=(20, 10))

        actions_row2 = [
            (get_text("financial_aid.admin_portal.buttons.review_aid_applications", "Review Aid Applications"), self.show_aid_applications),
            (get_text("financial_aid.admin_portal.buttons.create_aid_package", "Create Aid Package"), self.show_create_package),
            (get_text("financial_aid.admin_portal.buttons.manage_aid_types", "Manage Aid Types"), self.show_aid_types)
        ]

        for i, (text, command) in enumerate(actions_row2):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=3, column=i, padx=5, pady=5, sticky='ew')

        # Row 3: Disbursements & Reports
        ttk.Label(actions_frame, text=get_text("financial_aid.admin_portal.sections.disbursements_reports", "Disbursements & Reports"),
                 font=('Arial', 11, 'bold')).grid(row=4, column=0, columnspan=3, sticky='w', pady=(20, 10))

        actions_row3 = [
            (get_text("financial_aid.admin_portal.buttons.process_disbursements", "Process Disbursements"), self.show_disbursements),
            (get_text("financial_aid.admin_portal.buttons.view_reports", "View Reports"), self.show_reports),
            (get_text("financial_aid.admin_portal.buttons.import_fafsa", "Import FAFSA Data"), self.show_fafsa_import)
        ]

        for i, (text, command) in enumerate(actions_row3):
            ttk.Button(actions_frame, text=text, command=command, width=25).grid(
                row=5, column=i, padx=5, pady=5, sticky='ew')

        # Configure column weights
        for i in range(3):
            actions_frame.grid_columnconfigure(i, weight=1)

    def _get_admin_stats(self) -> Dict[str, Any]:
        """Get admin dashboard statistics"""
        stats = {
            'pending_reviews': 0,
            'active_packages': 0,
            'total_disbursed': 0.0,
            'pending_disbursements': 0.0
        }

        try:
            with get_connection() as conn:
                # Pending reviews (scholarships + aid)
                # Handle missing financial_aid_applications table gracefully
                try:
                    result = conn.execute("""
                        SELECT
                            (SELECT COUNT(*) FROM scholarship_applications WHERE status = 'pending') +
                            (SELECT COUNT(*) FROM financial_aid_applications WHERE status = 'pending') as total
                    """).fetchone()
                    stats['pending_reviews'] = result['total'] if result else 0
                except Exception:
                    # If financial_aid_applications table doesn't exist, just count scholarships
                    result = conn.execute("""
                        SELECT COUNT(*) as total FROM scholarship_applications WHERE status = 'pending'
                    """).fetchone()
                    stats['pending_reviews'] = result['total'] if result else 0

                # Active aid packages (using student_financial_aid table)
                result = conn.execute("""
                    SELECT COUNT(*) as count
                    FROM student_financial_aid
                    WHERE status IN ('approved', 'disbursed')
                """).fetchone()
                stats['active_packages'] = result['count'] if result else 0

                # Total disbursed this year
                try:
                    current_year = get_current_academic_year()
                    result = conn.execute("""
                        SELECT COALESCE(SUM(amount), 0) as total
                        FROM disbursements
                        WHERE status = 'disbursed'
                        AND strftime('%Y', disbursement_date) = ?
                    """, (current_year.split('-')[0],)).fetchone()
                    stats['total_disbursed'] = float(result['total']) if result else 0.0
                except Exception:
                    # Disbursements table may not exist yet
                    stats['total_disbursed'] = 0.0

                # Pending disbursements
                try:
                    result = conn.execute("""
                        SELECT COALESCE(SUM(amount), 0) as total
                        FROM disbursements
                        WHERE status = 'pending'
                    """).fetchone()
                    stats['pending_disbursements'] = float(result['total']) if result else 0.0
                except Exception:
                    # Disbursements table may not exist yet
                    stats['pending_disbursements'] = 0.0

        except Exception as e:
            logger.error(f"Error fetching admin stats: {e}")

        return stats
