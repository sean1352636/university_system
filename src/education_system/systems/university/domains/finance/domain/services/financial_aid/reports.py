"""Financial aid report builders.

Each builder returns the full report as plain text. They were lifted from the
admin portal's reports mixin so the GUI window, the CLI and the file exporters
all render exactly the same report.

``connect`` is a zero-argument callable returning a connection usable as a
context manager with ``sqlite3.Row`` rows (the university ``get_connection``
by default); callers may pass their own for tests or a scratch database.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from education_system.systems.university.domains.finance.domain.services.financial_aid.report_common import (
    _LINE,
    _RULE,
    _T,
    _default_connect,
    _stamp,
    _t,
    _table_exists,
    format_currency,
    format_date,
    get_current_academic_year,
)
from education_system.systems.university.domains.finance.domain.services.financial_aid.reports_analysis import (
    build_compliance_report,
    build_need_analysis_report,
    build_sai_report,
)


# --------------------------------------------------------------------------- #
# 1. Aid distribution summary
# --------------------------------------------------------------------------- #
def build_aid_distribution_report(connect: Optional[Callable] = None) -> str:
    connect = connect or _default_connect
    report = [_RULE, _t(f"{_T}.report_header.aid_distribution", "FINANCIAL AID DISTRIBUTION SUMMARY"),
              _stamp(), _RULE, ""]
    with connect() as conn:
        report += [_t(f"{_T}.sections.aid_by_type", "AID DISTRIBUTION BY TYPE:"), _LINE]
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
                a = dict(aid)
                report.append("\n" + _t(f"{_T}.labels.aid_type", "Aid Type: {type}",
                                              type=f"{a['aid_name']} ({a['aid_category']})"))
                report.append(_t(f"{_T}.labels.recipients", "  Recipients: {count}", count=a['count']))
                report.append(_t(f"{_T}.labels.total_awarded", "  Total Awarded: {amount}",
                                       amount=format_currency(a['total_awarded'])))
                report.append(_t(f"{_T}.labels.total_disbursed", "  Total Disbursed: {amount}",
                                       amount=format_currency(a['total_disbursed'])))
                report.append(_t(f"{_T}.labels.remaining", "  Remaining: {amount}",
                                       amount=format_currency(a['total_remaining'])))
        except Exception as exc:
            report.append(f"Error loading aid types data: {exc}")

        report += ["", _RULE, _t(f"{_T}.sections.aid_by_year", "AID DISTRIBUTION BY ACADEMIC YEAR:"), _LINE]
        report.append("\n" + _t(
            f"{_T}.notes.academic_year_note",
            "Note: Academic year breakdown requires application_date field\n"
            "in student_financial_aid table for accurate reporting."))

        report += ["", _RULE, _t(f"{_T}.sections.summary_statistics", "SUMMARY STATISTICS:"), _LINE]
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
                report.append("\n" + _t(f"{_T}.labels.total_students_receiving_aid",
                                              "Total Students Receiving Aid: {count}", count=s['total_students'] or 0))
                report.append(_t(f"{_T}.labels.total_awards", "Total Awards: {count}", count=s['total_awards'] or 0))
                report.append(_t(f"{_T}.labels.total_amount_awarded", "Total Amount Awarded: {amount}",
                                       amount=format_currency(s['total_awarded'])))
                report.append(_t(f"{_T}.labels.total_amount_disbursed", "Total Amount Disbursed: {amount}",
                                       amount=format_currency(s['total_disbursed'])))
                report.append(_t(f"{_T}.labels.average_award_amount", "Average Award Amount: {amount}",
                                       amount=format_currency(s['avg_award'])))
        except Exception as exc:
            report.append(f"Error loading summary statistics: {exc}")

    report += ["", _RULE, _t(f"{_T}.end_of_report", "End of Report"), _RULE]
    return "\n".join(report)


# --------------------------------------------------------------------------- #
# 2. Scholarship utilization
# --------------------------------------------------------------------------- #
def build_scholarship_utilization_report(connect: Optional[Callable] = None) -> str:
    connect = connect or _default_connect
    report = [_RULE, _t(f"{_T}.report_header.scholarship_utilization", "SCHOLARSHIP UTILIZATION REPORT"),
              _stamp(), _RULE, ""]
    with connect() as conn:
        report += [_t(f"{_T}.sections.scholarship_awards_summary", "SCHOLARSHIP AWARDS SUMMARY:"), _LINE]
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
            report.append("\n" + _t(f"{_T}.labels.scholarship_name", "Scholarship: {name}", name=sch['scholarship_name']))
            report.append(_t(f"{_T}.labels.academic_year_value", "  Academic Year: {year}", year=sch['academic_year'] or 'N/A'))
            report.append(_t(f"{_T}.labels.status_active", "  Status: Active") if sch['is_active']
                          else _t(f"{_T}.labels.status_inactive", "  Status: Inactive"))
            report.append(_t(f"{_T}.labels.maximum_amount", "  Maximum Amount: {amount}",
                                   amount=format_currency(sch['max_amount'])))
            report.append(_t(f"{_T}.labels.number_of_awards", "  Number of Awards: {count}", count=sch['awards_count']))
            report.append(_t(f"{_T}.labels.total_awarded", "  Total Awarded: {amount}",
                                   amount=format_currency(sch['total_awarded'])))
            if sch['max_amount'] and sch['awards_count'] > 0:
                utilization = (sch['total_awarded'] or 0) / (sch['max_amount'] * sch['awards_count']) * 100
                report.append(_t(f"{_T}.labels.utilization_rate", "  Utilization Rate: {rate}%", rate=f"{utilization:.1f}"))

        report += ["", _RULE, _t(f"{_T}.sections.application_statistics", "APPLICATION STATISTICS:"), _LINE]
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
            report.append("\n" + _t(f"{_T}.labels.total_applications", "Total Applications: {count}", count=stats['total_applications']))
            report.append(_t(f"{_T}.labels.pending_applications", "Pending Applications: {count}", count=stats['pending']))
            report.append(_t(f"{_T}.labels.approved_applications", "Approved Applications: {count}", count=stats['approved']))
            report.append(_t(f"{_T}.labels.denied_applications", "Denied Applications: {count}", count=stats['denied']))
            if stats['total_applications']:
                approval_rate = (stats['approved'] or 0) / stats['total_applications'] * 100
                report.append(_t(f"{_T}.labels.approval_rate", "Approval Rate: {rate}%", rate=f"{approval_rate:.1f}"))

    report += ["", _RULE, _t(f"{_T}.end_of_report", "End of Report"), _RULE]
    return "\n".join(report)


# --------------------------------------------------------------------------- #
# 3. Disbursement schedule
# --------------------------------------------------------------------------- #
_DISBURSEMENT_SQL = """
    SELECT d.*, d.student_id,
           COALESCE(fat.aid_name, s.scholarship_name, 'General Aid') as aid_name
    FROM disbursements d
    LEFT JOIN aid_components ac ON d.component_id = ac.component_id
    LEFT JOIN aid_packages ap ON ac.package_id = ap.package_id
    LEFT JOIN student_financial_aid sfa ON d.student_id = sfa.student_id AND ap.academic_year = sfa.notes
    LEFT JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
    LEFT JOIN scholarship_awards sa ON d.award_id = sa.award_id
    LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
"""


def _disbursement_sections(conn, report: List[str]) -> None:
    report += [_t(f"{_T}.sections.pending_disbursements", "PENDING DISBURSEMENTS:"), _LINE]
    pending = conn.execute(
        _DISBURSEMENT_SQL + " WHERE d.status = 'pending' ORDER BY d.scheduled_date ASC"
    ).fetchall()
    if pending:
        for disb in pending:
            d = dict(disb)
            report.append("\n" + _t(f"{_T}.labels.student_id_col", "Student ID") + f": {d['student_id']}")
            report.append(_t(f"{_T}.labels.aid_type", "Aid Type: {type}", type=d['aid_name']))
            report.append(_t(f"{_T}.labels.total_awarded", "  Total Awarded: {amount}",
                                   amount=format_currency(d['amount'])).replace("Total Awarded", "Amount"))
            report.append(f"  Scheduled: {format_date(d.get('scheduled_date'))}")
            report.append(_t(f"{_T}.labels.method", "  Method: {method}",
                                   method=d.get('method', _t("financial_aid.admin_portal.values.direct_deposit", "Direct Deposit"))))
    else:
        report.append("\n" + _t(f"{_T}.no_pending_disbursements", "No pending disbursements"))

    report += ["", _RULE, _t(f"{_T}.sections.completed_disbursements", "COMPLETED DISBURSEMENTS (Last 30 days):"), _LINE]
    completed = conn.execute(
        _DISBURSEMENT_SQL
        + " WHERE d.status = 'disbursed' AND d.disbursement_date >= date('now', '-30 days')"
        + " ORDER BY d.disbursement_date DESC"
    ).fetchall()
    if completed:
        for disb in completed:
            d = dict(disb)
            report.append("\n" + _t(f"{_T}.labels.student_id_col", "Student ID") + f": {d['student_id']}")
            report.append(_t(f"{_T}.labels.aid_type", "Aid Type: {type}", type=d['aid_name']))
            report.append(f"  Amount: {format_currency(d['amount'])}")
            report.append(f"  Disbursed: {format_date(d.get('disbursement_date'))}")
    else:
        report.append("\n" + _t(f"{_T}.no_completed_disbursements", "No completed disbursements in last 30 days"))


def build_disbursement_schedule_report(connect: Optional[Callable] = None) -> str:
    connect = connect or _default_connect
    report = [_RULE, _t(f"{_T}.report_header.disbursement_schedule", "DISBURSEMENT SCHEDULE REPORT"),
              _stamp(), _RULE, ""]
    with connect() as conn:
        if not _table_exists(conn, "disbursements"):
            report.append(_t(f"{_T}.disbursement_not_configured", "DISBURSEMENT TRACKING NOT YET CONFIGURED"))
            report.append("")
            report.append(_t(f"{_T}.disbursement_table_missing",
                                   "The disbursements table has not been created yet.\n"
                                   "This feature will be available once the database schema is updated."))
        else:
            _disbursement_sections(conn, report)
    report += ["", _RULE, _t(f"{_T}.end_of_report", "End of Report"), _RULE]
    return "\n".join(report)


# --------------------------------------------------------------------------- #
# 7. Renewal tracking
# --------------------------------------------------------------------------- #
def _renewal_overview(report: List[str], conn) -> None:
    row = conn.execute("""
        SELECT
            COUNT(*) as total_awards,
            SUM(CASE WHEN sa.is_renewable = 1 THEN 1 ELSE 0 END) as renewable_count,
            SUM(CASE WHEN sa.is_renewable = 0 THEN 1 ELSE 0 END) as non_renewable_count,
            SUM(sa.amount) as total_amount,
            SUM(CASE WHEN sa.is_renewable = 1 THEN sa.amount ELSE 0 END) as renewable_amount
        FROM scholarship_awards sa
        WHERE sa.status = 'active'
    """).fetchone()
    if not row:
        return
    d = dict(row)
    report.append(f"Total Active Awards: {d['total_awards'] or 0}")
    report.append(f"Renewable Awards: {d['renewable_count'] or 0}")
    report.append(f"Non-Renewable Awards: {d['non_renewable_count'] or 0}")
    report.append(f"Total Award Amount: {format_currency(d['total_amount'])}")
    report.append(f"Renewable Amount: {format_currency(d['renewable_amount'])}")


def _renewal_by_scholarship(report: List[str], conn) -> None:
    rows = conn.execute("""
        SELECT
            COALESCE(s.scholarship_name, 'Unknown') as scholarship_name,
            MAX(sa.is_renewable) as is_renewable_scholarship,
            COUNT(sa.award_id) as award_count,
            SUM(sa.amount) as total_awarded,
            AVG(sa.amount) as avg_award
        FROM scholarship_awards sa
        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
        WHERE sa.status = 'active'
        GROUP BY sa.scholarship_id
        ORDER BY total_awarded DESC
    """).fetchall()
    if not rows:
        report.append(_t(f"{_T}.no_active_awards", "No active scholarship awards found"))
        return
    for row in rows:
        r = dict(row)
        tag = _t(f"{_T}.labels.renewable_tag", " [RENEWABLE]") if r['is_renewable_scholarship'] else ""
        report.append(f"\n{r['scholarship_name']}{tag}")
        report.append(f"  Active Awards: {r['award_count']}")
        report.append(_t(f"{_T}.labels.total_awarded", "  Total Awarded: {amount}", amount=format_currency(r['total_awarded'])))
        report.append(f"  Average Award: {format_currency(r['avg_award'])}")


def _renewal_recent_awards(report: List[str], conn) -> None:
    rows = conn.execute("""
        SELECT sa.student_id, COALESCE(s.scholarship_name, 'Unknown') as scholarship_name, sa.amount,
               sa.academic_year, sa.is_renewable, sa.award_date
        FROM scholarship_awards sa
        LEFT JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
        WHERE sa.status = 'active'
        ORDER BY sa.award_date DESC
        LIMIT 20
    """).fetchall()
    if not rows:
        report.append(_t(f"{_T}.no_recent_awards", "No recent awards found"))
        return
    report.append(f"{_t(f'{_T}.labels.student_col', 'Student'):<12} "
                  f"{_t(f'{_T}.labels.scholarship_col', 'Scholarship'):<30} "
                  f"{_t(f'{_T}.labels.amount_col', 'Amount'):>12} "
                  f"{_t(f'{_T}.labels.year_col', 'Year'):<12} "
                  f"{_t(f'{_T}.labels.renewable_col', 'Renewable'):<10}")
    report.append("-" * 76)
    yes = _t("financial_aid.admin_portal.values.yes", "Yes")
    no = _t("financial_aid.admin_portal.values.no", "No")
    for row in rows:
        r = dict(row)
        name = (r['scholarship_name'] or 'Unknown')[:28]
        report.append(f"{str(r['student_id']):<12} {name:<30} {format_currency(r['amount']):>12} "
                      f"{r['academic_year'] or 'N/A':<12} {(yes if r['is_renewable'] else no):<10}")


def build_renewal_tracking_report(connect: Optional[Callable] = None) -> str:
    connect = connect or _default_connect
    report = [
        _RULE,
        _t(f"{_T}.report_header.renewal_tracking", "SCHOLARSHIP RENEWAL TRACKING REPORT"),
        _stamp(),
        f"Academic Year: {get_current_academic_year()}",
        _RULE, "",
    ]
    with connect() as conn:
        if not _table_exists(conn, "scholarship_awards"):
            report.append(_t(f"{_T}.awards_table_not_configured", "SCHOLARSHIP AWARDS TABLE NOT YET CONFIGURED"))
            report.append("")
            report.append(_t(f"{_T}.awards_table_missing",
                                   "The scholarship_awards table has not been created yet.\n"
                                   "This report requires scholarship award tracking to be enabled."))
        else:
            report += [_t(f"{_T}.sections.renewable_overview", "SECTION 1: RENEWABLE SCHOLARSHIP OVERVIEW"), _LINE]
            _renewal_overview(report, conn)
            report.append("")
            report += [_t(f"{_T}.sections.active_awards_by_scholarship", "SECTION 2: ACTIVE AWARDS BY SCHOLARSHIP"), _LINE]
            _renewal_by_scholarship(report, conn)
            report.append("")
            report += [_t(f"{_T}.sections.recent_scholarship_awards", "SECTION 3: RECENT SCHOLARSHIP AWARDS"), _LINE]
            _renewal_recent_awards(report, conn)

    report += ["", _RULE, _t(f"{_T}.end_renewal_report", "END OF RENEWAL TRACKING REPORT"), _RULE]
    return "\n".join(report)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
class ReportSpec:
    """One report the admin portal and the CLI can generate and export."""

    __slots__ = ("key", "label_key", "label", "filename_base", "builder", "formats")

    def __init__(self, key: str, label_key: str, label: str, filename_base: str,
                 builder: Callable[..., str], formats: tuple[str, ...]):
        self.key = key
        self.label_key = label_key
        self.label = label
        self.filename_base = filename_base
        self.builder = builder
        self.formats = formats

    @property
    def title(self) -> str:
        return _t(f"{_T}.{self.label_key}", self.label)

    def build(self, connect: Optional[Callable] = None) -> str:
        return self.builder(connect=connect)


REPORTS: tuple[ReportSpec, ...] = (
    ReportSpec("aid_distribution", "aid_distribution", "Aid Distribution Summary",
               "aid_distribution_report", build_aid_distribution_report, ("csv", "txt")),
    ReportSpec("scholarship_utilization", "scholarship_utilization", "Scholarship Utilization",
               "scholarship_utilization_report", build_scholarship_utilization_report, ("csv", "txt")),
    ReportSpec("disbursement_schedule", "disbursement_schedule", "Disbursement Schedule",
               "disbursement_schedule_report", build_disbursement_schedule_report, ("csv", "txt")),
    ReportSpec("compliance_fisap", "compliance_fisap", "Compliance Report (FISAP)",
               "FISAP_Compliance_Report", build_compliance_report, ("pdf", "txt")),
    ReportSpec("sai_report", "sai_report", "Student Aid Index Report",
               "SAI_EFC_Analysis_Report", build_sai_report, ("pdf", "txt")),
    ReportSpec("need_analysis", "need_analysis", "Need Analysis Report",
               "need_analysis_report", build_need_analysis_report, ("csv", "txt")),
    ReportSpec("renewal_tracking", "renewal_tracking", "Renewal Tracking Report",
               "renewal_tracking_report", build_renewal_tracking_report, ("csv", "txt")),
)


def get_report(key: str) -> ReportSpec:
    for spec in REPORTS:
        if spec.key == key:
            return spec
    raise KeyError(f"Unknown financial aid report {key!r}")


def build_report(key: str, connect: Optional[Callable] = None) -> str:
    """Render the report registered under ``key`` as text."""
    return get_report(key).build(connect)


__all__ = [
    "REPORTS",
    "ReportSpec",
    "build_aid_distribution_report",
    "build_compliance_report",
    "build_disbursement_schedule_report",
    "build_need_analysis_report",
    "build_renewal_tracking_report",
    "build_report",
    "build_sai_report",
    "build_scholarship_utilization_report",
    "format_currency",
    "format_date",
    "get_current_academic_year",
    "get_report",
]
