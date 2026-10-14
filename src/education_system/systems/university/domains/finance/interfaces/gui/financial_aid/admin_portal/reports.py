"""
Report generation mixin for AdminPortal.

The report text itself is built by
``finance.domain.services.financial_aid.reports`` (shared with the financial
aid CLI); this mixin only lists the reports, shows the text and offers the
export buttons.
"""
from education_system.systems.university.shell.gui import report_view as _rv

from education_system.systems.university.domains.finance.interfaces.gui.financial_aid.admin_portal._imports import (
    tk, ttk, scrolledtext, logging, datetime,
    get_connection,
    clear_frame, create_scrollable_frame,
    format_currency, format_date,
    show_warning,
    get_current_academic_year,
    get_text,
)
from education_system.systems.university.domains.finance.domain.services.financial_aid import (
    reports as _reports,
)

logger = logging.getLogger(__name__)

_T = "financial_aid.admin_portal"


class ReportsMixin:
    """Methods for generating financial aid reports."""

    def show_reports(self):
        """Show reports interface"""
        self._prepare_view_parent()

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text(f"{_T}.reports.title", "Financial Aid Reports"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text(f"{_T}.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Reports options with scrollbar
        reports_container = ttk.Frame(self.parent_frame)
        reports_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(reports_container)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        reports_frame = ttk.LabelFrame(scrollable_frame, text=get_text(f"{_T}.reports.available_reports", "Available Reports"), padding=20)
        reports_frame.pack(fill='both', expand=True)

        descriptions = {
            "aid_distribution": "Summary of aid distributed by type and year",
            "scholarship_utilization": "Analysis of scholarship awards and usage",
            "disbursement_schedule": "Upcoming and completed disbursements",
            "compliance_fisap": "Federal compliance reporting",
            "sai_report": "SAI/EFC analysis",
            "need_analysis": "Unmet financial need by student demographics",
            "renewal_tracking": "Scholarship renewal eligibility and status",
        }

        for spec in _reports.REPORTS:
            frame = ttk.Frame(reports_frame)
            frame.pack(fill='x', pady=10)

            ttk.Label(frame, text=spec.title, font=('Arial', 11, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=get_text(f"{_T}.reports.{spec.key}_desc", descriptions[spec.key]),
                      foreground='gray').pack(anchor='w', padx=20)
            ttk.Button(frame, text=get_text(f"{_T}.buttons.generate_report", "Generate Report"),
                      command=lambda n=spec.title: self._generate_report(n)).pack(anchor='w', padx=20, pady=5)

    def _generate_report(self, report_name: str):
        """Generate selected report"""
        for spec in _reports.REPORTS:
            if report_name == spec.title:
                self._open_text_report(spec)
                return
        show_warning(get_text(f"{_T}.dialogs.coming_soon", "Coming Soon"),
                     get_text(f"{_T}.messages.report_not_implemented", "Report '{name}' not yet implemented").format(name=report_name))

    # ------------------------------------------------------------------ #
    # Shared window
    # ------------------------------------------------------------------ #
    _WINDOW_TITLES = {
        "aid_distribution": ("aid_distribution_title", "Aid Distribution Summary Report", "aid_distribution", "Aid Distribution Summary"),
        "scholarship_utilization": ("scholarship_utilization_title", "Scholarship Utilization Report", "scholarship_utilization", "Scholarship Utilization Report"),
        "disbursement_schedule": ("disbursement_schedule_title", "Disbursement Schedule Report", "disbursement_schedule", "Disbursement Schedule Report"),
        "compliance_fisap": ("compliance_fisap_title", "Compliance Report (FISAP)", "fisap_title", "Federal Student Aid Report (FISAP)"),
        "sai_report": ("sai_report_title", "Student Aid Index (SAI) Report", "sai_analysis", "Student Aid Index (SAI) Analysis"),
        "need_analysis": ("need_analysis_title", "Need Analysis Report", "need_analysis", "Need Analysis Report"),
        "renewal_tracking": ("renewal_tracking_title", "Renewal Tracking Report", "renewal_tracking", "Renewal Tracking Report"),
    }
    #: Reports whose window also offers "Email Report to Admin".
    _EMAILABLE = ("aid_distribution", "scholarship_utilization", "disbursement_schedule")

    def _open_text_report(self, spec):
        """Build ``spec`` and show it in a window with its export buttons."""
        title_key, title_default, heading_key, heading_default = self._WINDOW_TITLES[spec.key]
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text(f"{_T}.reports.{title_key}", title_default))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text(f"{_T}.reports.{heading_key}", heading_default),
                  style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = _rv.TextReportView(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            # ``get_connection`` is looked up on this module so tests can patch it.
            text = spec.build(connect=get_connection)
        except Exception as e:
            logger.error(f"Error generating {spec.key} report: {e}")
            text = get_text(f"{_T}.reports.error_generating", "Error generating report:\n{error}", error=str(e))
        report_text.insert('1.0', text)
        report_text.config(state='disabled')

        current = lambda: report_text.get('1.0', 'end-1c')  # noqa: E731
        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)
        if "csv" in spec.formats:
            ttk.Button(btn_frame, text=get_text(f"{_T}.buttons.export_csv", "Export as CSV"),
                       command=lambda: self._export_report_to_csv(current(), spec.filename_base)).pack(side='left', padx=5)
        if "pdf" in spec.formats:
            ttk.Button(btn_frame, text=get_text(f"{_T}.buttons.export_pdf", "Export to PDF"),
                       command=lambda: self._export_report_to_pdf(current(), spec.filename_base)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text(f"{_T}.buttons.export_text", "Export as Text"),
                   command=lambda: self._export_report_to_txt(current(), spec.filename_base)).pack(side='left', padx=5)
        if spec.key in self._EMAILABLE:
            ttk.Button(btn_frame, text=get_text(f"{_T}.buttons.email_report", "Email Report to Admin"),
                       command=lambda: self._email_report(current(), spec.title)).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text(f"{_T}.buttons.close", "Close"),
                   command=report_window.destroy).pack(side='left', padx=5)

    # ------------------------------------------------------------------ #
    # Per-report entry points (kept for callers and tests)
    # ------------------------------------------------------------------ #
    def _generate_aid_distribution_report(self):
        """Generate Aid Distribution Summary report"""
        self._open_text_report(_reports.get_report("aid_distribution"))

    def _generate_scholarship_utilization_report(self):
        """Generate Scholarship Utilization report"""
        self._open_text_report(_reports.get_report("scholarship_utilization"))

    def _generate_disbursement_schedule_report(self):
        """Generate Disbursement Schedule report"""
        self._open_text_report(_reports.get_report("disbursement_schedule"))

    def _generate_compliance_report(self):
        """Generate Compliance (FISAP) report"""
        self._open_text_report(_reports.get_report("compliance_fisap"))

    def _generate_sai_report(self):
        """Generate Student Aid Index (SAI) report"""
        self._open_text_report(_reports.get_report("sai_report"))

    def _generate_need_analysis_report(self):
        """Generate Need Analysis report showing unmet financial need by demographics"""
        self._open_text_report(_reports.get_report("need_analysis"))

    def _generate_renewal_tracking_report(self):
        """Generate Renewal Tracking report for scholarships"""
        self._open_text_report(_reports.get_report("renewal_tracking"))
