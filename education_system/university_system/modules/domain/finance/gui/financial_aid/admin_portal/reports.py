"""
Report generation mixin for AdminPortal.
"""

from education_system.university_system.modules.domain.finance.gui.financial_aid.admin_portal._imports import (
    tk, ttk, scrolledtext, logging, datetime,
    get_connection,
    clear_frame, create_scrollable_frame,
    format_currency, format_date,
    show_warning,
    get_current_academic_year,
    get_text,
)

logger = logging.getLogger(__name__)


class ReportsMixin:
    """Methods for generating financial aid reports."""

    def show_reports(self):
        """Show reports interface"""
        # Ensure we have a valid parent frame/window
        parent = self._ensure_valid_parent()
        self.parent_frame = parent

        clear_frame(self.parent_frame)

        # Title
        title_frame = ttk.Frame(self.parent_frame)
        title_frame.pack(fill='x', padx=10, pady=10)
        ttk.Label(title_frame, text=get_text("financial_aid.admin_portal.reports.title", "Financial Aid Reports"), style='Title.TLabel').pack(side='left')
        ttk.Button(title_frame, text=get_text("financial_aid.admin_portal.buttons.back_to_dashboard", "Back to Dashboard"), command=self.show_dashboard).pack(side='right')

        # Reports options with scrollbar
        reports_container = ttk.Frame(self.parent_frame)
        reports_container.pack(fill='both', expand=True, padx=10, pady=10)

        # Create scrollable frame
        scrollable_frame, canvas, scrollbar = create_scrollable_frame(reports_container)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        reports_frame = ttk.LabelFrame(scrollable_frame, text=get_text("financial_aid.admin_portal.reports.available_reports", "Available Reports"), padding=20)
        reports_frame.pack(fill='both', expand=True)

        reports = [
            (get_text("financial_aid.admin_portal.reports.aid_distribution", "Aid Distribution Summary"), get_text("financial_aid.admin_portal.reports.aid_distribution_desc", "Summary of aid distributed by type and year")),
            (get_text("financial_aid.admin_portal.reports.scholarship_utilization", "Scholarship Utilization"), get_text("financial_aid.admin_portal.reports.scholarship_utilization_desc", "Analysis of scholarship awards and usage")),
            (get_text("financial_aid.admin_portal.reports.disbursement_schedule", "Disbursement Schedule"), get_text("financial_aid.admin_portal.reports.disbursement_schedule_desc", "Upcoming and completed disbursements")),
            (get_text("financial_aid.admin_portal.reports.compliance_fisap", "Compliance Report (FISAP)"), get_text("financial_aid.admin_portal.reports.compliance_fisap_desc", "Federal compliance reporting")),
            (get_text("financial_aid.admin_portal.reports.sai_report", "Student Aid Index Report"), get_text("financial_aid.admin_portal.reports.sai_report_desc", "SAI/EFC analysis")),
            (get_text("financial_aid.admin_portal.reports.need_analysis", "Need Analysis Report"), get_text("financial_aid.admin_portal.reports.need_analysis_desc", "Unmet financial need by student demographics")),
            (get_text("financial_aid.admin_portal.reports.renewal_tracking", "Renewal Tracking Report"), get_text("financial_aid.admin_portal.reports.renewal_tracking_desc", "Scholarship renewal eligibility and status")),
        ]

        for i, (name, description) in enumerate(reports):
            frame = ttk.Frame(reports_frame)
            frame.pack(fill='x', pady=10)

            ttk.Label(frame, text=name, font=('Arial', 11, 'bold')).pack(anchor='w')
            ttk.Label(frame, text=description, foreground='gray').pack(anchor='w', padx=20)
            ttk.Button(frame, text=get_text("financial_aid.admin_portal.buttons.generate_report", "Generate Report"),
                      command=lambda n=name: self._generate_report(n)).pack(anchor='w', padx=20, pady=5)

    def _generate_report(self, report_name: str):
        """Generate selected report"""
        if report_name == get_text("financial_aid.admin_portal.reports.aid_distribution", "Aid Distribution Summary"):
            self._generate_aid_distribution_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.scholarship_utilization", "Scholarship Utilization"):
            self._generate_scholarship_utilization_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.disbursement_schedule", "Disbursement Schedule"):
            self._generate_disbursement_schedule_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.compliance_fisap", "Compliance Report (FISAP)"):
            self._generate_compliance_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.sai_report", "Student Aid Index Report"):
            self._generate_sai_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.need_analysis", "Need Analysis Report"):
            self._generate_need_analysis_report()
        elif report_name == get_text("financial_aid.admin_portal.reports.renewal_tracking", "Renewal Tracking Report"):
            self._generate_renewal_tracking_report()
        else:
            show_warning(get_text("financial_aid.admin_portal.dialogs.coming_soon", "Coming Soon"), get_text("financial_aid.admin_portal.messages.report_not_implemented", "Report '{name}' not yet implemented").format(name=report_name))

    def _generate_aid_distribution_report(self):
        """Generate Aid Distribution Summary report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.aid_distribution_title", "Aid Distribution Summary Report"))
        report_window.geometry("900x700")

        # Title
        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.aid_distribution", "Aid Distribution Summary"), style='Title.TLabel').pack(pady=10)

        # Create scrolled text for report
        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.report_header.aid_distribution", "FINANCIAL AID DISTRIBUTION SUMMARY"))
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Aid by type
                report.append(get_text("financial_aid.admin_portal.reports.sections.aid_by_type", "AID DISTRIBUTION BY TYPE:"))
                report.append("-" * 80)

                try:
                    aid_by_type = conn.execute("""
                        SELECT fat.aid_name, fat.aid_category,
                               COUNT(sfa.aid_id) as count,
                               SUM(sfa.awarded_amount) as total_awarded,
                               SUM(sfa.disbursed_amount) as total_disbursed,
                               SUM(sfa.remaining_amount) as total_remaining
                        FROM financial_aid_types fat
                        LEFT JOIN student_financial_aid sfa ON fat.aid_type_id = sfa.aid_type_id
                        GROUP BY fat.aid_type_id, fat.aid_name, fat.aid_category
                        ORDER BY total_awarded DESC
                    """).fetchall()

                    for aid in aid_by_type:
                        aid_dict = dict(aid)
                        report.append(f"\n" + get_text("financial_aid.admin_portal.reports.labels.aid_type", "Aid Type: {type}", type=f"{aid_dict['aid_name']} ({aid_dict['aid_category']})"))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.recipients", "  Recipients: {count}", count=aid_dict['count']))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(aid_dict['total_awarded'] or 0)))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.total_disbursed", "  Total Disbursed: {amount}", amount=format_currency(aid_dict['total_disbursed'] or 0)))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.remaining", "  Remaining: {amount}", amount=format_currency(aid_dict['total_remaining'] or 0)))
                except Exception as e:
                    report.append(f"Error loading aid types data: {e}")

                report.append("")
                report.append("=" * 80)
                report.append(get_text("financial_aid.admin_portal.reports.sections.aid_by_year", "AID DISTRIBUTION BY ACADEMIC YEAR:"))
                report.append("-" * 80)

                # Get unique academic years from student_financial_aid
                try:
                    # This query needs the application_date field to extract year
                    report.append("\n" + get_text("financial_aid.admin_portal.reports.notes.academic_year_note", "Note: Academic year breakdown requires application_date field\nin student_financial_aid table for accurate reporting."))
                except Exception as e:
                    report.append(f"Error loading year data: {e}")

                report.append("")
                report.append("=" * 80)
                report.append(get_text("financial_aid.admin_portal.reports.sections.summary_statistics", "SUMMARY STATISTICS:"))
                report.append("-" * 80)

                try:
                    summary = conn.execute("""
                        SELECT
                            COUNT(DISTINCT student_id) as total_students,
                            COUNT(aid_id) as total_awards,
                            SUM(awarded_amount) as total_awarded,
                            SUM(disbursed_amount) as total_disbursed,
                            AVG(awarded_amount) as avg_award
                        FROM student_financial_aid
                        WHERE status IN ('approved', 'disbursed', 'completed')
                    """).fetchone()

                    if summary:
                        s = dict(summary)
                        report.append(f"\n" + get_text("financial_aid.admin_portal.reports.labels.total_students_receiving_aid", "Total Students Receiving Aid: {count}", count=s['total_students'] or 0))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.total_awards", "Total Awards: {count}", count=s['total_awards'] or 0))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.total_amount_awarded", "Total Amount Awarded: {amount}", amount=format_currency(s['total_awarded'] or 0)))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.total_amount_disbursed", "Total Amount Disbursed: {amount}", amount=format_currency(s['total_disbursed'] or 0)))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.average_award_amount", "Average Award Amount: {amount}", amount=format_currency(s['avg_award'] or 0)))
                except Exception as e:
                    report.append(f"Error loading summary statistics: {e}")

            report.append("")
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.end_of_report", "End of Report"))
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating aid distribution report: {e}")
            report_text.insert('1.0', get_text("financial_aid.admin_portal.reports.error_generating", "Error generating report:\n{error}", error=str(e)))
            report_text.config(state='disabled')

        # Export buttons
        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "aid_distribution_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "aid_distribution_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.email_report", "Email Report to Admin"),
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), get_text("financial_aid.admin_portal.reports.aid_distribution", "Aid Distribution Summary"))).pack(side='left', padx=5)

        ttk.Button(report_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=report_window.destroy).pack(pady=5)

    def _generate_scholarship_utilization_report(self):
        """Generate Scholarship Utilization report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.scholarship_utilization_title", "Scholarship Utilization Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.scholarship_utilization", "Scholarship Utilization Report"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.report_header.scholarship_utilization", "SCHOLARSHIP UTILIZATION REPORT"))
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Scholarship awards summary
                report.append(get_text("financial_aid.admin_portal.reports.sections.scholarship_awards_summary", "SCHOLARSHIP AWARDS SUMMARY:"))
                report.append("-" * 80)

                scholarships = conn.execute("""
                    SELECT s.scholarship_name, s.amount as max_amount, s.is_active,
                           COUNT(ss.student_scholarship_id) as awards_count,
                           SUM(ss.amount) as total_awarded,
                           s.academic_year
                    FROM scholarships s
                    LEFT JOIN student_scholarships ss ON s.scholarship_id = ss.scholarship_id
                    GROUP BY s.scholarship_id
                    ORDER BY total_awarded DESC
                """).fetchall()

                for scholarship in scholarships:
                    sch = dict(scholarship)
                    report.append(f"\n" + get_text("financial_aid.admin_portal.reports.labels.scholarship_name", "Scholarship: {name}", name=sch['scholarship_name']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.academic_year_value", "  Academic Year: {year}", year=sch['academic_year'] or 'N/A'))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.status_active", "  Status: Active") if sch['is_active'] else get_text("financial_aid.admin_portal.reports.labels.status_inactive", "  Status: Inactive"))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.maximum_amount", "  Maximum Amount: {amount}", amount=format_currency(sch['max_amount'] or 0)))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.number_of_awards", "  Number of Awards: {count}", count=sch['awards_count']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(sch['total_awarded'] or 0)))

                    if sch['max_amount'] and sch['awards_count'] > 0:
                        utilization = (sch['total_awarded'] or 0) / (sch['max_amount'] * sch['awards_count']) * 100
                        report.append(get_text("financial_aid.admin_portal.reports.labels.utilization_rate", "  Utilization Rate: {rate}%", rate=f"{utilization:.1f}"))

                report.append("")
                report.append("=" * 80)
                report.append(get_text("financial_aid.admin_portal.reports.sections.application_statistics", "APPLICATION STATISTICS:"))
                report.append("-" * 80)

                app_stats = conn.execute("""
                    SELECT
                        COUNT(*) as total_applications,
                        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                        SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied
                    FROM scholarship_applications
                """).fetchone()

                if app_stats:
                    stats = dict(app_stats)
                    report.append(f"\n" + get_text("financial_aid.admin_portal.reports.labels.total_applications", "Total Applications: {count}", count=stats['total_applications']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.pending_applications", "Pending Applications: {count}", count=stats['pending']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.approved_applications", "Approved Applications: {count}", count=stats['approved']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.denied_applications", "Denied Applications: {count}", count=stats['denied']))

                    if stats['total_applications'] > 0:
                        approval_rate = (stats['approved'] / stats['total_applications']) * 100
                        report.append(get_text("financial_aid.admin_portal.reports.labels.approval_rate", "Approval Rate: {rate}%", rate=f"{approval_rate:.1f}"))

            report.append("")
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.end_of_report", "End of Report"))
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating scholarship utilization report: {e}")
            report_text.insert('1.0', get_text("financial_aid.admin_portal.reports.error_generating", "Error generating report:\n{error}", error=str(e)))
            report_text.config(state='disabled')

        # Export buttons
        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "scholarship_utilization_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "scholarship_utilization_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.email_report", "Email Report to Admin"),
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), get_text("financial_aid.admin_portal.reports.scholarship_utilization", "Scholarship Utilization"))).pack(side='left', padx=5)

        ttk.Button(report_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=report_window.destroy).pack(pady=5)

    def _generate_disbursement_schedule_report(self):
        """Generate Disbursement Schedule report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.disbursement_schedule_title", "Disbursement Schedule Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.disbursement_schedule", "Disbursement Schedule Report"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.report_header.disbursement_schedule", "DISBURSEMENT SCHEDULE REPORT"))
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Check if disbursements table exists
                table_check = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='disbursements'
                """).fetchone()

                if not table_check:
                    report.append(get_text("financial_aid.admin_portal.reports.disbursement_not_configured", "DISBURSEMENT TRACKING NOT YET CONFIGURED"))
                    report.append("")
                    report.append(get_text("financial_aid.admin_portal.reports.disbursement_table_missing", "The disbursements table has not been created yet.\nThis feature will be available once the database schema is updated."))
                else:
                    # Pending disbursements
                    report.append(get_text("financial_aid.admin_portal.reports.sections.pending_disbursements", "PENDING DISBURSEMENTS:"))
                    report.append("-" * 80)

                    pending = conn.execute("""
                        SELECT d.*, d.student_id,
                               COALESCE(fat.aid_name, s.scholarship_name, 'General Aid') as aid_name
                        FROM disbursements d
                        LEFT JOIN aid_components ac ON d.component_id = ac.component_id
                        LEFT JOIN aid_packages ap ON ac.package_id = ap.package_id
                        LEFT JOIN student_financial_aid sfa ON d.student_id = sfa.student_id AND ap.academic_year = sfa.notes
                        LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                        LEFT JOIN scholarship_awards sa ON d.award_id = sa.award_id
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE d.status = 'pending'
                        ORDER BY d.scheduled_date ASC
                    """).fetchall()

                    if pending:
                        for disb in pending:
                            d = dict(disb)
                            report.append(f"\n" + get_text("financial_aid.admin_portal.reports.labels.student_id_col", "Student ID") + f": {d['student_id']}")
                            report.append(get_text("financial_aid.admin_portal.reports.labels.aid_type", "Aid Type: {type}", type=d['aid_name']))
                            report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(d['amount'])).replace("Total Awarded", "Amount"))
                            report.append(f"  Scheduled: {format_date(d.get('scheduled_date'))}")
                            report.append(get_text("financial_aid.admin_portal.reports.labels.method", "  Method: {method}", method=d.get('method', get_text("financial_aid.admin_portal.values.direct_deposit", "Direct Deposit"))))
                    else:
                        report.append("\n" + get_text("financial_aid.admin_portal.reports.no_pending_disbursements", "No pending disbursements"))

                    report.append("")
                    report.append("=" * 80)
                    report.append(get_text("financial_aid.admin_portal.reports.sections.completed_disbursements", "COMPLETED DISBURSEMENTS (Last 30 days):"))
                    report.append("-" * 80)

                    completed = conn.execute("""
                        SELECT d.*, d.student_id,
                               COALESCE(fat.aid_name, s.scholarship_name, 'General Aid') as aid_name
                        FROM disbursements d
                        LEFT JOIN aid_components ac ON d.component_id = ac.component_id
                        LEFT JOIN aid_packages ap ON ac.package_id = ap.package_id
                        LEFT JOIN student_financial_aid sfa ON d.student_id = sfa.student_id AND ap.academic_year = sfa.notes
                        LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                        LEFT JOIN scholarship_awards sa ON d.award_id = sa.award_id
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE d.status = 'disbursed'
                        AND d.disbursement_date >= date('now', '-30 days')
                        ORDER BY d.disbursement_date DESC
                    """).fetchall()

                    if completed:
                        for disb in completed:
                            d = dict(disb)
                            report.append(f"\n" + get_text("financial_aid.admin_portal.reports.labels.student_id_col", "Student ID") + f": {d['student_id']}")
                            report.append(get_text("financial_aid.admin_portal.reports.labels.aid_type", "Aid Type: {type}", type=d['aid_name']))
                            report.append(f"  Amount: {format_currency(d['amount'])}")
                            report.append(f"  Disbursed: {format_date(d.get('disbursement_date'))}")
                    else:
                        report.append("\n" + get_text("financial_aid.admin_portal.reports.no_completed_disbursements", "No completed disbursements in last 30 days"))

            report.append("")
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.end_of_report", "End of Report"))
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating disbursement schedule report: {e}")
            report_text.insert('1.0', get_text("financial_aid.admin_portal.reports.error_generating", "Error generating report:\n{error}", error=str(e)))
            report_text.config(state='disabled')

        # Export buttons
        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "disbursement_schedule_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "disbursement_schedule_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.email_report", "Email Report to Admin"),
                  command=lambda: self._email_report(report_text.get('1.0', 'end-1c'), get_text("financial_aid.admin_portal.reports.disbursement_schedule", "Disbursement Schedule"))).pack(side='left', padx=5)

        ttk.Button(report_window, text=get_text("financial_aid.admin_portal.buttons.close", "Close"), command=report_window.destroy).pack(pady=5)

    def _generate_compliance_report(self):
        """Generate Compliance (FISAP) report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.compliance_fisap_title", "Compliance Report (FISAP)"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.fisap_title", "Federal Student Aid Report (FISAP)"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.report_header.fisap", "FISAP COMPLIANCE REPORT"))
            report.append(get_text("financial_aid.admin_portal.reports.report_header.fisap_subtitle", "Fiscal Operations Report and Application to Participate"))
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Section 1: Federal Work-Study (FWS) Expenditures
                report.append(get_text("financial_aid.admin_portal.reports.sections.fws_program", "SECTION 1: FEDERAL WORK-STUDY (FWS) PROGRAM"))
                report.append("-" * 80)

                fws_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        SUM(sfa.remaining_amount) as total_remaining
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_name) LIKE '%work%study%'
                       OR LOWER(fat.aid_name) LIKE '%fws%'
                       OR LOWER(fat.aid_category) = 'work-study'
                """).fetchone()

                if fws_data:
                    fws = dict(fws_data)
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_recipients", "Total Recipients: {count}", count=fws['recipient_count']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(fws['total_awarded'] or 0)).lstrip())
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_disbursed", "  Total Disbursed: {amount}", amount=format_currency(fws['total_disbursed'] or 0)).lstrip())
                    report.append(get_text("financial_aid.admin_portal.reports.labels.remaining_allocation", "Remaining Allocation: {amount}", amount=format_currency(fws['total_remaining'] or 0)))

                    if fws['total_awarded'] and fws['total_awarded'] > 0:
                        utilization = (fws['total_disbursed'] or 0) / fws['total_awarded'] * 100
                        report.append(get_text("financial_aid.admin_portal.reports.labels.utilization_rate", "  Utilization Rate: {rate}%", rate=f"{utilization:.1f}").lstrip())
                else:
                    report.append(get_text("financial_aid.admin_portal.reports.no_fws_awards", "No FWS awards found for this academic year"))

                report.append("")

                # Section 2: Federal Supplemental Educational Opportunity Grant (FSEOG)
                report.append(get_text("financial_aid.admin_portal.reports.sections.seog_program", "SECTION 2: FEDERAL SEOG PROGRAM"))
                report.append("-" * 80)

                fseog_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        SUM(sfa.remaining_amount) as total_remaining
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_name) LIKE '%seog%'
                       OR LOWER(fat.aid_name) LIKE '%supplemental%educational%opportunity%'
                       OR (LOWER(fat.aid_category) = 'grant' AND LOWER(fat.aid_name) LIKE '%federal%')
                """).fetchone()

                if fseog_data:
                    fseog = dict(fseog_data)
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_recipients", "Total Recipients: {count}", count=fseog['recipient_count']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(fseog['total_awarded'] or 0)).lstrip())
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_disbursed", "  Total Disbursed: {amount}", amount=format_currency(fseog['total_disbursed'] or 0)).lstrip())
                    report.append(get_text("financial_aid.admin_portal.reports.labels.remaining_allocation", "Remaining Allocation: {amount}", amount=format_currency(fseog['total_remaining'] or 0)))

                    if fseog['total_awarded'] and fseog['total_awarded'] > 0:
                        utilization = (fseog['total_disbursed'] or 0) / fseog['total_awarded'] * 100
                        report.append(get_text("financial_aid.admin_portal.reports.labels.utilization_rate", "  Utilization Rate: {rate}%", rate=f"{utilization:.1f}").lstrip())
                else:
                    report.append(get_text("financial_aid.admin_portal.reports.no_fseog_awards", "No FSEOG awards found for this academic year"))

                report.append("")

                # Section 3: Federal Perkins Loan
                report.append(get_text("financial_aid.admin_portal.reports.sections.perkins_loan", "SECTION 3: FEDERAL PERKINS LOAN PROGRAM"))
                report.append("-" * 80)

                perkins_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        SUM(sfa.total_repaid) as total_repaid
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_name) LIKE '%perkins%'
                       OR (LOWER(fat.aid_category) = 'loan' AND LOWER(fat.aid_name) LIKE '%federal%')
                """).fetchone()

                if perkins_data:
                    perkins = dict(perkins_data)
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_recipients", "Total Recipients: {count}", count=perkins['recipient_count']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(perkins['total_awarded'] or 0)).lstrip())
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_disbursed", "  Total Disbursed: {amount}", amount=format_currency(perkins['total_disbursed'] or 0)).lstrip())
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_repaid", "Total Repaid: {amount}", amount=format_currency(perkins['total_repaid'] or 0)))

                    if perkins['total_disbursed'] and perkins['total_disbursed'] > 0:
                        outstanding = (perkins['total_disbursed'] or 0) - (perkins['total_repaid'] or 0)
                        report.append(get_text("financial_aid.admin_portal.reports.labels.outstanding_balance", "Outstanding Balance: {amount}", amount=format_currency(outstanding)))
                else:
                    report.append(get_text("financial_aid.admin_portal.reports.no_perkins_awards", "No Perkins Loan awards found"))
                    report.append(get_text("financial_aid.admin_portal.reports.notes.perkins_expired", "Note: The Federal Perkins Loan Program expired on September 30, 2017"))

                report.append("")

                # Section 4: Institutional Matching Contributions
                report.append(get_text("financial_aid.admin_portal.reports.sections.institutional_matching", "SECTION 4: INSTITUTIONAL MATCHING CONTRIBUTIONS"))
                report.append("-" * 80)

                institutional_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as recipient_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE LOWER(fat.aid_category) = 'institutional'
                       OR LOWER(fat.aid_name) LIKE '%institutional%'
                       OR LOWER(fat.aid_name) LIKE '%matching%'
                """).fetchone()

                if institutional_data:
                    inst = dict(institutional_data)
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_recipients", "Total Recipients: {count}", count=inst['recipient_count']))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(inst['total_awarded'] or 0)).lstrip())
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_disbursed", "  Total Disbursed: {amount}", amount=format_currency(inst['total_disbursed'] or 0)).lstrip())

                    # Calculate required matching (typically 25% for FSEOG)
                    if fseog_data:
                        fseog_amt = dict(fseog_data)['total_awarded'] or 0
                        required_match = fseog_amt * 0.25
                        actual_match = inst['total_disbursed'] or 0
                        report.append(get_text("financial_aid.admin_portal.reports.labels.required_match", "Required Match (25% of FSEOG): {amount}", amount=format_currency(required_match)))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.actual_match", "Actual Match Provided: {amount}", amount=format_currency(actual_match)))

                        if required_match > 0:
                            match_percentage = (actual_match / required_match) * 100
                            report.append(get_text("financial_aid.admin_portal.reports.labels.match_compliance", "Match Compliance: {rate}%", rate=f"{match_percentage:.1f}"))
                            if match_percentage >= 100:
                                report.append(get_text("financial_aid.admin_portal.reports.labels.status_compliant", "Status: COMPLIANT") + " \u2713")
                            else:
                                report.append(get_text("financial_aid.admin_portal.reports.labels.status_shortfall", "Status: SHORTFALL - Additional matching required"))
                else:
                    report.append(get_text("financial_aid.admin_portal.reports.no_matching_contributions", "No institutional matching contributions recorded"))

                report.append("")

                # Section 5: Student Enrollment Summary
                report.append(get_text("financial_aid.admin_portal.reports.sections.enrollment_data", "SECTION 5: STUDENT ENROLLMENT DATA"))
                report.append("-" * 80)

                enrollment_data = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as total_aid_recipients,
                        COUNT(DISTINCT CASE WHEN sfa.status = 'awarded' THEN sfa.student_id END) as awarded_count,
                        COUNT(DISTINCT CASE WHEN sfa.status = 'disbursed' THEN sfa.student_id END) as disbursed_count,
                        COUNT(DISTINCT CASE WHEN fat.requires_repayment = 1 THEN sfa.student_id END) as loan_recipients,
                        COUNT(DISTINCT CASE WHEN fat.requires_repayment = 0 THEN sfa.student_id END) as grant_recipients
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                """).fetchone()

                if enrollment_data:
                    enroll = dict(enrollment_data)
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_students_receiving_aid", "Total Students Receiving Aid: {count}", count=enroll['total_aid_recipients']))
                    report.append(f"  - Awards Approved: {enroll['awarded_count']}")
                    report.append(f"  - Funds Disbursed: {enroll['disbursed_count']}")
                    report.append(f"Loan Recipients: {enroll['loan_recipients']}")
                    report.append(f"Grant Recipients: {enroll['grant_recipients']}")

                report.append("")

                # Section 6: Compliance Summary
                report.append(get_text("financial_aid.admin_portal.reports.sections.compliance_summary", "SECTION 6: COMPLIANCE SUMMARY"))
                report.append("-" * 80)

                total_federal = 0
                if fws_data:
                    total_federal += dict(fws_data)['total_disbursed'] or 0
                if fseog_data:
                    total_federal += dict(fseog_data)['total_disbursed'] or 0
                if perkins_data:
                    total_federal += dict(perkins_data)['total_disbursed'] or 0

                report.append(get_text("financial_aid.admin_portal.reports.labels.total_federal_aid", "Total Federal Campus-Based Aid Disbursed: {amount}", amount=format_currency(total_federal)))
                report.append("")
                report.append(get_text("financial_aid.admin_portal.reports.compliance_checklist.heading", "Compliance Checklist:"))
                report.append(get_text("financial_aid.admin_portal.reports.compliance_checklist.fws_reported", "  FWS expenditures reported"))
                report.append(get_text("financial_aid.admin_portal.reports.compliance_checklist.seog_reported", "  FSEOG expenditures reported"))
                report.append("  \u25a1 Institutional matching funds verified")
                report.append("  \u25a1 Enrollment data current")
                report.append("  \u25a1 Award overages reviewed")
                report.append(get_text("financial_aid.admin_portal.reports.compliance_checklist.disbursements_reconciled", "  Disbursements reconciled"))
                report.append("")
                report.append(get_text("financial_aid.admin_portal.reports.notes.review_before_submission", "Note: This report should be reviewed by the Financial Aid Director\nbefore submission to the U.S. Department of Education."))

            report.append("")
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.end_fisap_report", "END OF FISAP COMPLIANCE REPORT"))
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating FISAP report: {e}")
            report_text.insert('1.0', get_text("financial_aid.admin_portal.reports.error_generating_contact_admin", "Error generating report:\n{error}\n\nPlease contact your system administrator.", error=str(e)))
            report_text.config(state='disabled')

        # Export buttons
        button_frame = ttk.Frame(report_window)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_pdf", "Export to PDF"),
                  command=lambda: self._export_report_to_pdf(report_text, "FISAP_Compliance_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_txt", "Export to Text"),
                  command=lambda: self._export_report_to_txt(report_text, "FISAP_Compliance_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=report_window.destroy).pack(side='left', padx=5)

    def _generate_sai_report(self):
        """Generate Student Aid Index (SAI) report"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.sai_report_title", "Student Aid Index (SAI) Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.sai_analysis", "Student Aid Index (SAI) Analysis"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.report_header.sai", "STUDENT AID INDEX (SAI) / EXPECTED FAMILY CONTRIBUTION (EFC) REPORT"))
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")
            report.append(get_text("financial_aid.admin_portal.reports.notes.sai_description", "This report analyzes financial need based on aid awards and costs."))
            report.append(get_text("financial_aid.admin_portal.reports.notes.sai_fafsa_note", "Note: SAI/EFC data typically comes from FAFSA submissions."))
            report.append("")

            with get_connection() as conn:
                # Section 1: Aid Distribution by Need Level
                report.append(get_text("financial_aid.admin_portal.reports.sections.aid_by_award_level", "SECTION 1: AID DISTRIBUTION BY AWARD LEVEL"))
                report.append("-" * 80)

                need_distribution = conn.execute("""
                    SELECT
                        CASE
                            WHEN sfa.awarded_amount < 2000 THEN 'Low Need (< $2,000)'
                            WHEN sfa.awarded_amount < 5000 THEN 'Moderate Need ($2,000-$5,000)'
                            WHEN sfa.awarded_amount < 10000 THEN 'High Need ($5,000-$10,000)'
                            ELSE 'Very High Need (> $10,000)'
                        END as need_category,
                        COUNT(DISTINCT sfa.student_id) as student_count,
                        SUM(sfa.awarded_amount) as total_awarded,
                        AVG(sfa.awarded_amount) as avg_award
                    FROM student_financial_aid sfa
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY need_category
                    ORDER BY MIN(sfa.awarded_amount)
                """).fetchall()

                for category in need_distribution:
                    cat_dict = dict(category)
                    report.append(f"\n{cat_dict['need_category']}")
                    report.append(f"  Students: {cat_dict['student_count']}")
                    report.append(f"  Total Awarded: {format_currency(cat_dict['total_awarded'] or 0)}")
                    report.append(f"  Average Award: {format_currency(cat_dict['avg_award'] or 0)}")

                report.append("")

                # Section 2: Aid Package Analysis
                report.append(get_text("financial_aid.admin_portal.reports.sections.package_composition", "SECTION 2: AID PACKAGE COMPOSITION ANALYSIS"))
                report.append("-" * 80)

                package_analysis = conn.execute("""
                    SELECT
                        fat.aid_category,
                        COUNT(DISTINCT sfa.student_id) as recipients,
                        SUM(sfa.awarded_amount) as total_amount,
                        AVG(sfa.awarded_amount) as avg_amount,
                        MIN(sfa.awarded_amount) as min_amount,
                        MAX(sfa.awarded_amount) as max_amount
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY fat.aid_category
                    ORDER BY total_amount DESC
                """).fetchall()

                for pkg in package_analysis:
                    pkg_dict = dict(pkg)
                    report.append(f"\nAid Category: {(pkg_dict['aid_category'] or 'Other').upper()}")
                    report.append(f"  Recipients: {pkg_dict['recipients']}")
                    report.append(f"  Total Awarded: {format_currency(pkg_dict['total_amount'] or 0)}")
                    report.append(f"  Average Award: {format_currency(pkg_dict['avg_amount'] or 0)}")
                    report.append(f"  Range: {format_currency(pkg_dict['min_amount'] or 0)} - {format_currency(pkg_dict['max_amount'] or 0)}")

                report.append("")

                # Section 3: Grant vs Loan Analysis
                report.append(get_text("financial_aid.admin_portal.reports.sections.grant_vs_loan", "SECTION 3: GRANT vs LOAN DISTRIBUTION"))
                report.append("-" * 80)

                grant_loan_analysis = conn.execute("""
                    SELECT
                        CASE WHEN fat.requires_repayment = 1 THEN 'Loans (Repayable)'
                             ELSE 'Grants/Scholarships (Non-Repayable)'
                        END as aid_type,
                        COUNT(DISTINCT sfa.student_id) as recipients,
                        SUM(sfa.awarded_amount) as total_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed,
                        AVG(sfa.awarded_amount) as avg_award
                    FROM student_financial_aid sfa
                    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY fat.requires_repayment
                    ORDER BY fat.requires_repayment
                """).fetchall()

                total_aid = 0
                for aid_type in grant_loan_analysis:
                    aid_dict = dict(aid_type)
                    total_aid += aid_dict['total_awarded'] or 0
                    report.append(f"\n{aid_dict['aid_type']}")
                    report.append(f"  Recipients: {aid_dict['recipients']}")
                    report.append(f"  Total Awarded: {format_currency(aid_dict['total_awarded'] or 0)}")
                    report.append(f"  Total Disbursed: {format_currency(aid_dict['total_disbursed'] or 0)}")
                    report.append(f"  Average per Student: {format_currency(aid_dict['avg_award'] or 0)}")

                # Calculate grant-to-loan ratio
                if grant_loan_analysis and len(grant_loan_analysis) > 0:
                    grant_total = 0
                    loan_total = 0
                    for aid_type in grant_loan_analysis:
                        aid_dict = dict(aid_type)
                        if 'Grant' in aid_dict['aid_type']:
                            grant_total = aid_dict['total_awarded'] or 0
                        else:
                            loan_total = aid_dict['total_awarded'] or 0

                    report.append("")
                    if total_aid > 0:
                        grant_pct = (grant_total / total_aid) * 100 if total_aid > 0 else 0
                        loan_pct = (loan_total / total_aid) * 100 if total_aid > 0 else 0
                        report.append(get_text("financial_aid.admin_portal.reports.labels.grant_percentage", "Grant Percentage: {rate}%", rate=f"{grant_pct:.1f}"))
                        report.append(get_text("financial_aid.admin_portal.reports.labels.loan_percentage", "Loan Percentage: {rate}%", rate=f"{loan_pct:.1f}"))

                        if grant_pct > 50:
                            report.append(get_text("financial_aid.admin_portal.reports.labels.status_favorable", "Status: FAVORABLE - Majority of aid is gift aid"))
                        else:
                            report.append(get_text("financial_aid.admin_portal.reports.labels.status_caution", "Status: CAUTION - High reliance on loans"))

                report.append("")

                # Section 4: Unmet Need Analysis
                report.append(get_text("financial_aid.admin_portal.reports.sections.coverage_analysis", "SECTION 4: COVERAGE AND NEED ANALYSIS"))
                report.append("-" * 80)

                # Calculate students with different coverage levels
                coverage_analysis = conn.execute("""
                    SELECT
                        student_id,
                        SUM(awarded_amount) as total_aid,
                        COUNT(DISTINCT aid_type_id) as aid_types_count
                    FROM student_financial_aid
                    WHERE status IN ('awarded', 'disbursed')
                    GROUP BY student_id
                """).fetchall()

                if coverage_analysis:
                    total_students = len(coverage_analysis)
                    single_source = sum(1 for s in coverage_analysis if dict(s)['aid_types_count'] == 1)
                    multiple_sources = sum(1 for s in coverage_analysis if dict(s)['aid_types_count'] > 1)

                    aid_amounts = [dict(s)['total_aid'] for s in coverage_analysis]
                    avg_total_aid = sum(aid_amounts) / len(aid_amounts) if aid_amounts else 0
                    median_aid = sorted(aid_amounts)[len(aid_amounts) // 2] if aid_amounts else 0

                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_students_with_aid", "Total Students with Aid: {count}", count=total_students))
                    report.append(f"Students with Single Aid Source: {single_source}")
                    report.append(f"Students with Multiple Aid Sources: {multiple_sources}")
                    report.append(f"Average Total Aid per Student: {format_currency(avg_total_aid)}")
                    report.append(f"Median Total Aid per Student: {format_currency(median_aid)}")

                    # Estimate typical Cost of Attendance (COA)
                    estimated_coa = 30000  # Placeholder - adjust based on institution
                    report.append(f"\n" + get_text("financial_aid.admin_portal.reports.labels.estimated_cost_attendance", "Estimated Cost of Attendance: {amount}", amount=format_currency(estimated_coa)))

                    if avg_total_aid > 0:
                        coverage_pct = (avg_total_aid / estimated_coa) * 100
                        unmet_need = max(0, estimated_coa - avg_total_aid)
                        report.append(f"Average Aid Coverage: {coverage_pct:.1f}%")
                        report.append(f"Average Unmet Need: {format_currency(unmet_need)}")

                        if coverage_pct >= 75:
                            report.append(get_text("financial_aid.admin_portal.reports.labels.status_strong", "Status: STRONG - High financial need being met"))
                        elif coverage_pct >= 50:
                            report.append(get_text("financial_aid.admin_portal.reports.labels.status_adequate", "Status: ADEQUATE - Moderate coverage"))
                        else:
                            report.append(get_text("financial_aid.admin_portal.reports.labels.status_concern", "Status: CONCERN - Significant unmet need"))
                else:
                    report.append(get_text("financial_aid.admin_portal.reports.no_coverage_data", "No coverage analysis data available"))

                report.append("")

                # Section 5: Recommendations
                report.append(get_text("financial_aid.admin_portal.reports.sections.recommendations", "SECTION 5: RECOMMENDATIONS"))
                report.append("-" * 80)

                # Calculate key metrics for recommendations
                if grant_loan_analysis:
                    grant_total = 0
                    loan_total = 0
                    for aid_type in grant_loan_analysis:
                        aid_dict = dict(aid_type)
                        if 'Grant' in aid_dict['aid_type']:
                            grant_total = aid_dict['total_awarded'] or 0
                        else:
                            loan_total = aid_dict['total_awarded'] or 0

                    report.append(get_text("financial_aid.admin_portal.reports.based_on_analysis", "Based on the analysis:"))
                    report.append("")

                    if grant_total < loan_total:
                        report.append("• Consider increasing grant/scholarship funding to reduce")
                        report.append("  student debt burden")

                    if coverage_analysis and avg_total_aid < estimated_coa * 0.5:
                        report.append("• Average aid covers less than 50% of COA - evaluate")
                        report.append("  institutional aid policies")

                    if multiple_sources < single_source:
                        report.append("• Many students rely on single aid source - consider")
                        report.append("  package diversification")

                    report.append("")
                    report.append("• Review SAI/EFC thresholds for Pell Grant eligibility")
                    report.append("• Conduct FAFSA completion campaign to ensure all eligible")
                    report.append("  students apply for federal aid")
                    report.append("• Implement verification process for selected applications")
                    report.append("• Monitor professional judgment requests for special circumstances")

            report.append("")
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.end_sai_report", "END OF SAI/EFC ANALYSIS REPORT"))
            report.append("=" * 80)
            report.append("")
            report.append(get_text("financial_aid.admin_portal.reports.notes.sai_overview_note", "Note: This report provides an overview of financial need and aid distribution.\nFor detailed SAI/EFC values, import FAFSA data via ISIR processing."))

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating SAI report: {e}")
            report_text.insert('1.0', get_text("financial_aid.admin_portal.reports.error_generating_contact_admin", "Error generating report:\n{error}\n\nPlease contact your system administrator.", error=str(e)))
            report_text.config(state='disabled')

        # Export buttons
        button_frame = ttk.Frame(report_window)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_pdf", "Export to PDF"),
                  command=lambda: self._export_report_to_pdf(report_text, "SAI_EFC_Analysis_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.export_txt", "Export to Text"),
                  command=lambda: self._export_report_to_txt(report_text, "SAI_EFC_Analysis_Report")).pack(side='left', padx=5)
        ttk.Button(button_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=lambda: report_window.destroy).pack(side='left', padx=5)

    def _generate_need_analysis_report(self):
        """Generate Need Analysis report showing unmet financial need by demographics"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.need_analysis_title", "Need Analysis Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.need_analysis", "Need Analysis Report"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.report_header.need_analysis", "FINANCIAL NEED ANALYSIS REPORT"))
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Section 1: Overall Need Summary
                report.append(get_text("financial_aid.admin_portal.reports.sections.overall_need_summary", "SECTION 1: OVERALL FINANCIAL NEED SUMMARY"))
                report.append("-" * 80)

                overall = conn.execute("""
                    SELECT
                        COUNT(DISTINCT sfa.student_id) as aided_students,
                        SUM(sfa.awarded_amount) as total_awarded,
                        AVG(sfa.awarded_amount) as avg_awarded,
                        SUM(sfa.disbursed_amount) as total_disbursed
                    FROM student_financial_aid sfa
                    WHERE sfa.status IN ('awarded', 'disbursed')
                """).fetchone()

                if overall:
                    d = dict(overall)
                    report.append(get_text("financial_aid.admin_portal.reports.labels.students_receiving_aid", "Students Receiving Aid: {count}", count=d['aided_students'] or 0))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_amount_awarded", "Total Amount Awarded: {amount}", amount=format_currency(d['total_awarded'] or 0)))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.average_award_amount", "Average Award Amount: {amount}", amount=format_currency(d['avg_awarded'] or 0)))
                    report.append(get_text("financial_aid.admin_portal.reports.labels.total_amount_disbursed", "Total Amount Disbursed: {amount}", amount=format_currency(d['total_disbursed'] or 0)))

                # Total enrolled students
                total_enrolled = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
                aided = dict(overall)['aided_students'] or 0 if overall else 0
                unaided = total_enrolled - aided
                report.append(f"\nTotal Enrolled Students: {total_enrolled}")
                report.append(f"Students Without Aid: {unaided}")
                if total_enrolled > 0:
                    report.append(f"Aid Participation Rate: {aided / total_enrolled * 100:.1f}%")

                report.append("")

                # Section 2: Need by Aid Category
                report.append(get_text("financial_aid.admin_portal.reports.sections.aid_by_category", "SECTION 2: AID DISTRIBUTION BY CATEGORY"))
                report.append("-" * 80)

                by_category = conn.execute("""
                    SELECT
                        COALESCE(fat.aid_category, 'Other') as category,
                        COUNT(DISTINCT sfa.student_id) as recipients,
                        SUM(sfa.awarded_amount) as total,
                        AVG(sfa.awarded_amount) as avg_amount
                    FROM student_financial_aid sfa
                    LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY category
                    ORDER BY total DESC
                """).fetchall()

                for row in by_category:
                    r = dict(row)
                    report.append(f"\n{(r['category'] or 'Other').upper()}")
                    report.append(f"  Recipients: {r['recipients']}")
                    report.append(f"  Total: {format_currency(r['total'] or 0)}")
                    report.append(f"  Average: {format_currency(r['avg_amount'] or 0)}")

                report.append("")

                # Section 3: Students with Highest Unmet Need
                report.append(get_text("financial_aid.admin_portal.reports.sections.highest_total_aid", "SECTION 3: STUDENTS WITH HIGHEST TOTAL AID"))
                report.append("-" * 80)

                top_aid = conn.execute("""
                    SELECT
                        sfa.student_id,
                        SUM(sfa.awarded_amount) as total_aid,
                        COUNT(DISTINCT sfa.aid_type_id) as aid_sources
                    FROM student_financial_aid sfa
                    WHERE sfa.status IN ('awarded', 'disbursed')
                    GROUP BY sfa.student_id
                    ORDER BY total_aid DESC
                    LIMIT 15
                """).fetchall()

                if top_aid:
                    report.append(f"{get_text('financial_aid.admin_portal.reports.labels.student_id_col', 'Student ID'):<15} {get_text('financial_aid.admin_portal.reports.labels.total_aid_col', 'Total Aid'):>15} {get_text('financial_aid.admin_portal.reports.labels.sources_col', 'Sources'):>10}")
                    report.append("-" * 40)
                    for row in top_aid:
                        r = dict(row)
                        report.append(f"{r['student_id']:<15} {format_currency(r['total_aid'] or 0):>15} {r['aid_sources']:>10}")
                else:
                    report.append(get_text("financial_aid.admin_portal.reports.no_aid_data", "No aid data available"))

                report.append("")

                # Section 4: Aid Status Breakdown
                report.append(get_text("financial_aid.admin_portal.reports.sections.aid_status_breakdown", "SECTION 4: AID STATUS BREAKDOWN"))
                report.append("-" * 80)

                status_breakdown = conn.execute("""
                    SELECT status, COUNT(*) as count, SUM(awarded_amount) as total
                    FROM student_financial_aid
                    GROUP BY status
                    ORDER BY count DESC
                """).fetchall()

                for row in status_breakdown:
                    r = dict(row)
                    report.append(f"  {r['status'].title()}: {r['count']} awards, {format_currency(r['total'] or 0)}")

            report.append("")
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.end_need_report", "END OF NEED ANALYSIS REPORT"))
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating need analysis report: {e}")
            report_text.insert('1.0', get_text("financial_aid.admin_portal.reports.error_generating", "Error generating report:\n{error}", error=str(e)))
            report_text.config(state='disabled')

        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "need_analysis_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "need_analysis_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=report_window.destroy).pack(side='left', padx=5)

    def _generate_renewal_tracking_report(self):
        """Generate Renewal Tracking report for scholarships"""
        report_window = tk.Toplevel(self.parent_frame)
        report_window.title(get_text("financial_aid.admin_portal.reports.renewal_tracking_title", "Renewal Tracking Report"))
        report_window.geometry("900x700")

        ttk.Label(report_window, text=get_text("financial_aid.admin_portal.reports.renewal_tracking", "Renewal Tracking Report"), style='Title.TLabel').pack(pady=10)

        report_frame = ttk.Frame(report_window)
        report_frame.pack(fill='both', expand=True, padx=10, pady=10)

        report_text = scrolledtext.ScrolledText(report_frame, width=100, height=35, wrap='word', font=('Courier', 10))
        report_text.pack(fill='both', expand=True)

        try:
            report = []
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.report_header.renewal_tracking", "SCHOLARSHIP RENEWAL TRACKING REPORT"))
            report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"Academic Year: {get_current_academic_year()}")
            report.append("=" * 80)
            report.append("")

            with get_connection() as conn:
                # Check if scholarship_awards table exists
                table_check = conn.execute("""
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name='scholarship_awards'
                """).fetchone()

                if not table_check:
                    report.append(get_text("financial_aid.admin_portal.reports.awards_table_not_configured", "SCHOLARSHIP AWARDS TABLE NOT YET CONFIGURED"))
                    report.append("")
                    report.append(get_text("financial_aid.admin_portal.reports.awards_table_missing", "The scholarship_awards table has not been created yet.\nThis report requires scholarship award tracking to be enabled."))
                else:
                    # Section 1: Renewable Scholarship Summary
                    report.append(get_text("financial_aid.admin_portal.reports.sections.renewable_overview", "SECTION 1: RENEWABLE SCHOLARSHIP OVERVIEW"))
                    report.append("-" * 80)

                    renewable_summary = conn.execute("""
                        SELECT
                            COUNT(*) as total_awards,
                            SUM(CASE WHEN sa.is_renewable = 1 THEN 1 ELSE 0 END) as renewable_count,
                            SUM(CASE WHEN sa.is_renewable = 0 THEN 1 ELSE 0 END) as non_renewable_count,
                            SUM(sa.amount) as total_amount,
                            SUM(CASE WHEN sa.is_renewable = 1 THEN sa.amount ELSE 0 END) as renewable_amount
                        FROM scholarship_awards sa
                        WHERE sa.status = 'active'
                    """).fetchone()

                    if renewable_summary:
                        d = dict(renewable_summary)
                        report.append(f"Total Active Awards: {d['total_awards'] or 0}")
                        report.append(f"Renewable Awards: {d['renewable_count'] or 0}")
                        report.append(f"Non-Renewable Awards: {d['non_renewable_count'] or 0}")
                        report.append(f"Total Award Amount: {format_currency(d['total_amount'] or 0)}")
                        report.append(f"Renewable Amount: {format_currency(d['renewable_amount'] or 0)}")

                    report.append("")

                    # Section 2: Awards by Scholarship
                    report.append(get_text("financial_aid.admin_portal.reports.sections.active_awards_by_scholarship", "SECTION 2: ACTIVE AWARDS BY SCHOLARSHIP"))
                    report.append("-" * 80)

                    awards_by_scholarship = conn.execute("""
                        SELECT
                            COALESCE(s.name, 'Unknown') as scholarship_name,
                            s.renewable as is_renewable_scholarship,
                            COUNT(sa.award_id) as award_count,
                            SUM(sa.amount) as total_awarded,
                            AVG(sa.amount) as avg_award
                        FROM scholarship_awards sa
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE sa.status = 'active'
                        GROUP BY sa.scholarship_id
                        ORDER BY total_awarded DESC
                    """).fetchall()

                    if awards_by_scholarship:
                        for row in awards_by_scholarship:
                            r = dict(row)
                            renewable_tag = get_text("financial_aid.admin_portal.reports.labels.renewable_tag", " [RENEWABLE]") if r['is_renewable_scholarship'] else ""
                            report.append(f"\n{r['scholarship_name']}{renewable_tag}")
                            report.append(f"  Active Awards: {r['award_count']}")
                            report.append(get_text("financial_aid.admin_portal.reports.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(r['total_awarded'] or 0)))
                            report.append(f"  Average Award: {format_currency(r['avg_award'] or 0)}")
                    else:
                        report.append(get_text("financial_aid.admin_portal.reports.no_active_awards", "No active scholarship awards found"))

                    report.append("")

                    # Section 3: Recent Awards
                    report.append(get_text("financial_aid.admin_portal.reports.sections.recent_scholarship_awards", "SECTION 3: RECENT SCHOLARSHIP AWARDS"))
                    report.append("-" * 80)

                    recent_awards = conn.execute("""
                        SELECT
                            sa.student_id,
                            COALESCE(s.name, 'Unknown') as scholarship_name,
                            sa.amount,
                            sa.academic_year,
                            sa.is_renewable,
                            sa.awarded_date
                        FROM scholarship_awards sa
                        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                        WHERE sa.status = 'active'
                        ORDER BY sa.awarded_date DESC
                        LIMIT 20
                    """).fetchall()

                    if recent_awards:
                        report.append(f"{get_text('financial_aid.admin_portal.reports.labels.student_col', 'Student'):<12} {get_text('financial_aid.admin_portal.reports.labels.scholarship_col', 'Scholarship'):<30} {get_text('financial_aid.admin_portal.reports.labels.amount_col', 'Amount'):>12} {get_text('financial_aid.admin_portal.reports.labels.year_col', 'Year'):<12} {get_text('financial_aid.admin_portal.reports.labels.renewable_col', 'Renewable'):<10}")
                        report.append("-" * 76)
                        for row in recent_awards:
                            r = dict(row)
                            renew_str = get_text("financial_aid.admin_portal.values.yes", "Yes") if r['is_renewable'] else get_text("financial_aid.admin_portal.values.no", "No")
                            name = (r['scholarship_name'] or 'Unknown')[:28]
                            report.append(f"{r['student_id']:<12} {name:<30} {format_currency(r['amount'] or 0):>12} {r['academic_year'] or 'N/A':<12} {renew_str:<10}")
                    else:
                        report.append(get_text("financial_aid.admin_portal.reports.no_recent_awards", "No recent awards found"))

            report.append("")
            report.append("=" * 80)
            report.append(get_text("financial_aid.admin_portal.reports.end_renewal_report", "END OF RENEWAL TRACKING REPORT"))
            report.append("=" * 80)

            report_text.insert('1.0', '\n'.join(report))
            report_text.config(state='disabled')

        except Exception as e:
            logger.error(f"Error generating renewal tracking report: {e}")
            report_text.insert('1.0', get_text("financial_aid.admin_portal.reports.error_generating", "Error generating report:\n{error}", error=str(e)))
            report_text.config(state='disabled')

        btn_frame = ttk.Frame(report_window)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_csv", "Export as CSV"),
                  command=lambda: self._export_report_to_csv(report_text.get('1.0', 'end-1c'), "renewal_tracking_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.export_text", "Export as Text"),
                  command=lambda: self._export_report_to_txt(report_text.get('1.0', 'end-1c'), "renewal_tracking_report")).pack(side='left', padx=5)
        ttk.Button(btn_frame, text=get_text("financial_aid.admin_portal.buttons.close", "Close"),
                  command=report_window.destroy).pack(side='left', padx=5)
