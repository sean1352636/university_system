"""Financial aid analysis reports: FISAP compliance, SAI/EFC and need analysis.

Lifted from the admin portal's reports mixin; see ``reports`` for the registry.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from education_system.systems.university.domains.finance.domain.services.financial_aid.report_common import (
    _LINE,
    _RULE,
    _T,
    _default_connect,
    _ratio_pct,
    _stamp,
    _t,
    format_currency,
    get_current_academic_year,
)


# --------------------------------------------------------------------------- #
# 4. FISAP compliance
# --------------------------------------------------------------------------- #
_FISAP_PROGRAM_SQL = """
    SELECT
        COUNT(DISTINCT sfa.student_id) as recipient_count,
        SUM(sfa.awarded_amount) as total_awarded,
        SUM(sfa.disbursed_amount) as total_disbursed,
        {extra}
    FROM student_financial_aid sfa
    JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
    WHERE {where}
"""
_FWS_WHERE = ("LOWER(fat.aid_name) LIKE '%work%study%' OR LOWER(fat.aid_name) LIKE '%fws%'"
              " OR LOWER(fat.aid_category) = 'work-study'")
_FSEOG_WHERE = ("LOWER(fat.aid_name) LIKE '%seog%'"
                " OR LOWER(fat.aid_name) LIKE '%supplemental%educational%opportunity%'"
                " OR (LOWER(fat.aid_category) = 'grant' AND LOWER(fat.aid_name) LIKE '%federal%')")
_PERKINS_WHERE = ("LOWER(fat.aid_name) LIKE '%perkins%'"
                  " OR (LOWER(fat.aid_category) = 'loan' AND LOWER(fat.aid_name) LIKE '%federal%')")
_INSTITUTIONAL_WHERE = ("LOWER(fat.aid_category) = 'institutional'"
                        " OR LOWER(fat.aid_name) LIKE '%institutional%'"
                        " OR LOWER(fat.aid_name) LIKE '%matching%'")


def _program_row(conn, where: str, extra: str) -> Optional[Dict[str, Any]]:
    row = conn.execute(_FISAP_PROGRAM_SQL.format(extra=extra, where=where)).fetchone()
    return dict(row) if row else None


def _program_lines(data: Dict[str, Any]) -> List[str]:
    lines = [
        _t(f"{_T}.labels.total_recipients", "Total Recipients: {count}", count=data['recipient_count']),
        _t(f"{_T}.labels.total_awarded", "  Total Awarded: {amount}",
                 amount=format_currency(data['total_awarded'])).lstrip(),
        _t(f"{_T}.labels.total_disbursed", "  Total Disbursed: {amount}",
                 amount=format_currency(data['total_disbursed'])).lstrip(),
    ]
    return lines


def _fisap_campus_program(report: List[str], data: Optional[Dict[str, Any]], missing_key: str, missing_default: str) -> None:
    if not data:
        report.append(_t(f"{_T}.{missing_key}", missing_default))
        return
    report += _program_lines(data)
    report.append(_t(f"{_T}.labels.remaining_allocation", "Remaining Allocation: {amount}",
                           amount=format_currency(data['total_remaining'])))
    if data['total_awarded'] and data['total_awarded'] > 0:
        utilization = (data['total_disbursed'] or 0) / data['total_awarded'] * 100
        report.append(_t(f"{_T}.labels.utilization_rate", "  Utilization Rate: {rate}%", rate=f"{utilization:.1f}").lstrip())


def _fisap_perkins(report: List[str], perkins: Optional[Dict[str, Any]]) -> None:
    if not perkins:
        report.append(_t(f"{_T}.no_perkins_awards", "No Perkins Loan awards found"))
        report.append(_t(f"{_T}.notes.perkins_expired", "Note: The Federal Perkins Loan Program expired on September 30, 2017"))
        return
    report += _program_lines(perkins)
    report.append(_t(f"{_T}.labels.total_repaid", "Total Repaid: {amount}", amount=format_currency(perkins['total_repaid'])))
    if perkins['total_disbursed'] and perkins['total_disbursed'] > 0:
        outstanding = (perkins['total_disbursed'] or 0) - (perkins['total_repaid'] or 0)
        report.append(_t(f"{_T}.labels.outstanding_balance", "Outstanding Balance: {amount}", amount=format_currency(outstanding)))


def _fisap_institutional(report: List[str], inst: Optional[Dict[str, Any]], fseog: Optional[Dict[str, Any]]) -> None:
    if not inst:
        report.append(_t(f"{_T}.no_matching_contributions", "No institutional matching contributions recorded"))
        return
    report += _program_lines(inst)
    if not fseog:
        return
    required_match = (fseog['total_awarded'] or 0) * 0.25
    actual_match = inst['total_disbursed'] or 0
    report.append(_t(f"{_T}.labels.required_match", "Required Match (25% of FSEOG): {amount}", amount=format_currency(required_match)))
    report.append(_t(f"{_T}.labels.actual_match", "Actual Match Provided: {amount}", amount=format_currency(actual_match)))
    if required_match > 0:
        match_percentage = (actual_match / required_match) * 100
        report.append(_t(f"{_T}.labels.match_compliance", "Match Compliance: {rate}%", rate=f"{match_percentage:.1f}"))
        if match_percentage >= 100:
            report.append(_t(f"{_T}.labels.status_compliant", "Status: COMPLIANT") + " ✓")
        else:
            report.append(_t(f"{_T}.labels.status_shortfall", "Status: SHORTFALL - Additional matching required"))


def _fisap_enrollment(report: List[str], conn) -> None:
    row = conn.execute("""
        SELECT
            COUNT(DISTINCT sfa.student_id) as total_aid_recipients,
            COUNT(DISTINCT CASE WHEN sfa.status = 'awarded' THEN sfa.student_id END) as awarded_count,
            COUNT(DISTINCT CASE WHEN sfa.status = 'disbursed' THEN sfa.student_id END) as disbursed_count,
            COUNT(DISTINCT CASE WHEN fat.requires_repayment = 1 THEN sfa.student_id END) as loan_recipients,
            COUNT(DISTINCT CASE WHEN fat.requires_repayment = 0 THEN sfa.student_id END) as grant_recipients
        FROM student_financial_aid sfa
        JOIN financial_aid_types fat ON sfa.aid_type_id = fat.aid_type_id
    """).fetchone()
    if not row:
        return
    enroll = dict(row)
    report.append(_t(f"{_T}.labels.total_students_receiving_aid", "Total Students Receiving Aid: {count}",
                           count=enroll['total_aid_recipients']))
    report.append(f"  - Awards Approved: {enroll['awarded_count']}")
    report.append(f"  - Funds Disbursed: {enroll['disbursed_count']}")
    report.append(f"Loan Recipients: {enroll['loan_recipients']}")
    report.append(f"Grant Recipients: {enroll['grant_recipients']}")


def _fisap_summary(report: List[str], programs: List[Optional[Dict[str, Any]]]) -> None:
    total_federal = sum((p['total_disbursed'] or 0) for p in programs if p)
    report.append(_t(f"{_T}.labels.total_federal_aid", "Total Federal Campus-Based Aid Disbursed: {amount}",
                           amount=format_currency(total_federal)))
    report.append("")
    report.append(_t(f"{_T}.compliance_checklist.heading", "Compliance Checklist:"))
    report.append(_t(f"{_T}.compliance_checklist.fws_reported", "  FWS expenditures reported"))
    report.append(_t(f"{_T}.compliance_checklist.seog_reported", "  FSEOG expenditures reported"))
    report.append("  □ Institutional matching funds verified")
    report.append("  □ Enrollment data current")
    report.append("  □ Award overages reviewed")
    report.append(_t(f"{_T}.compliance_checklist.disbursements_reconciled", "  Disbursements reconciled"))
    report.append("")
    report.append(_t(f"{_T}.notes.review_before_submission",
                           "Note: This report should be reviewed by the Financial Aid Director\n"
                           "before submission to the U.S. Department of Education."))


def build_compliance_report(connect: Optional[Callable] = None) -> str:
    connect = connect or _default_connect
    report = [
        _RULE,
        _t(f"{_T}.report_header.fisap", "FISAP COMPLIANCE REPORT"),
        _t(f"{_T}.report_header.fisap_subtitle", "Fiscal Operations Report and Application to Participate"),
        _stamp(),
        f"Academic Year: {get_current_academic_year()}",
        _RULE, "",
    ]
    with connect() as conn:
        report += [_t(f"{_T}.sections.fws_program", "SECTION 1: FEDERAL WORK-STUDY (FWS) PROGRAM"), _LINE]
        fws = _program_row(conn, _FWS_WHERE, "SUM(sfa.remaining_amount) as total_remaining")
        _fisap_campus_program(report, fws, "no_fws_awards", "No FWS awards found for this academic year")
        report.append("")

        report += [_t(f"{_T}.sections.seog_program", "SECTION 2: FEDERAL SEOG PROGRAM"), _LINE]
        fseog = _program_row(conn, _FSEOG_WHERE, "SUM(sfa.remaining_amount) as total_remaining")
        _fisap_campus_program(report, fseog, "no_fseog_awards", "No FSEOG awards found for this academic year")
        report.append("")

        report += [_t(f"{_T}.sections.perkins_loan", "SECTION 3: FEDERAL PERKINS LOAN PROGRAM"), _LINE]
        perkins = _program_row(conn, _PERKINS_WHERE, "SUM(sfa.total_repaid) as total_repaid")
        _fisap_perkins(report, perkins)
        report.append("")

        report += [_t(f"{_T}.sections.institutional_matching", "SECTION 4: INSTITUTIONAL MATCHING CONTRIBUTIONS"), _LINE]
        inst = _program_row(conn, _INSTITUTIONAL_WHERE, "0 as total_remaining")
        _fisap_institutional(report, inst, fseog)
        report.append("")

        report += [_t(f"{_T}.sections.enrollment_data", "SECTION 5: STUDENT ENROLLMENT DATA"), _LINE]
        _fisap_enrollment(report, conn)
        report.append("")

        report += [_t(f"{_T}.sections.compliance_summary", "SECTION 6: COMPLIANCE SUMMARY"), _LINE]
        _fisap_summary(report, [fws, fseog, perkins])

    report += ["", _RULE, _t(f"{_T}.end_fisap_report", "END OF FISAP COMPLIANCE REPORT"), _RULE]
    return "\n".join(report)


# --------------------------------------------------------------------------- #
# 5. Student Aid Index (SAI / EFC)
# --------------------------------------------------------------------------- #
_ESTIMATED_COA = 30000  # placeholder cost of attendance; adjust per institution


def _sai_need_levels(report: List[str], conn) -> None:
    rows = conn.execute("""
        SELECT
            CASE
                WHEN sfa.awarded_amount < 2000 THEN 'Low Need (< £2,000)'
                WHEN sfa.awarded_amount < 5000 THEN 'Moderate Need (£2,000-£5,000)'
                WHEN sfa.awarded_amount < 10000 THEN 'High Need (£5,000-£10,000)'
                ELSE 'Very High Need (> £10,000)'
            END as need_category,
            COUNT(DISTINCT sfa.student_id) as student_count,
            SUM(sfa.awarded_amount) as total_awarded,
            AVG(sfa.awarded_amount) as avg_award
        FROM student_financial_aid sfa
        WHERE sfa.status IN ('awarded', 'disbursed')
        GROUP BY need_category
        ORDER BY MIN(sfa.awarded_amount)
    """).fetchall()
    for category in rows:
        c = dict(category)
        report.append(f"\n{c['need_category']}")
        report.append(f"  Students: {c['student_count']}")
        report.append(f"  Total Awarded: {format_currency(c['total_awarded'])}")
        report.append(f"  Average Award: {format_currency(c['avg_award'])}")


def _sai_package_composition(report: List[str], conn) -> None:
    rows = conn.execute("""
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
    for pkg in rows:
        p = dict(pkg)
        report.append(f"\nAid Category: {(p['aid_category'] or 'Other').upper()}")
        report.append(f"  Recipients: {p['recipients']}")
        report.append(f"  Total Awarded: {format_currency(p['total_amount'])}")
        report.append(f"  Average Award: {format_currency(p['avg_amount'])}")
        report.append(f"  Range: {format_currency(p['min_amount'])} - {format_currency(p['max_amount'])}")


def _sai_grant_vs_loan(report: List[str], conn) -> Dict[str, float]:
    rows = conn.execute("""
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
    totals = {"grant": 0.0, "loan": 0.0, "total": 0.0, "rows": len(rows)}
    for aid_type in rows:
        a = dict(aid_type)
        awarded = a['total_awarded'] or 0
        totals["total"] += awarded
        totals["grant" if 'Grant' in a['aid_type'] else "loan"] = awarded
        report.append(f"\n{a['aid_type']}")
        report.append(f"  Recipients: {a['recipients']}")
        report.append(f"  Total Awarded: {format_currency(awarded)}")
        report.append(f"  Total Disbursed: {format_currency(a['total_disbursed'])}")
        report.append(f"  Average per Student: {format_currency(a['avg_award'])}")
    if rows and totals["total"] > 0:
        report.append("")
        grant_pct = _ratio_pct(totals["grant"], totals["total"])
        loan_pct = _ratio_pct(totals["loan"], totals["total"])
        report.append(_t(f"{_T}.labels.grant_percentage", "Grant Percentage: {rate}%", rate=f"{grant_pct:.1f}"))
        report.append(_t(f"{_T}.labels.loan_percentage", "Loan Percentage: {rate}%", rate=f"{loan_pct:.1f}"))
        if grant_pct > 50:
            report.append(_t(f"{_T}.labels.status_favorable", "Status: FAVORABLE - Majority of aid is gift aid"))
        else:
            report.append(_t(f"{_T}.labels.status_caution", "Status: CAUTION - High reliance on loans"))
    elif rows:
        report.append("")
    return totals


def _sai_coverage(report: List[str], conn) -> Dict[str, float]:
    rows = conn.execute("""
        SELECT student_id, SUM(awarded_amount) as total_aid, COUNT(DISTINCT aid_type_id) as aid_types_count
        FROM student_financial_aid
        WHERE status IN ('awarded', 'disbursed')
        GROUP BY student_id
    """).fetchall()
    coverage = {"students": len(rows), "single": 0, "multiple": 0, "avg": 0.0}
    if not rows:
        report.append(_t(f"{_T}.no_coverage_data", "No coverage analysis data available"))
        return coverage
    amounts = [dict(r)['total_aid'] or 0 for r in rows]
    coverage["single"] = sum(1 for r in rows if dict(r)['aid_types_count'] == 1)
    coverage["multiple"] = sum(1 for r in rows if dict(r)['aid_types_count'] > 1)
    coverage["avg"] = sum(amounts) / len(amounts)
    median_aid = sorted(amounts)[len(amounts) // 2]
    report.append(_t(f"{_T}.labels.total_students_with_aid", "Total Students with Aid: {count}", count=len(rows)))
    report.append(f"Students with Single Aid Source: {coverage['single']}")
    report.append(f"Students with Multiple Aid Sources: {coverage['multiple']}")
    report.append(f"Average Total Aid per Student: {format_currency(coverage['avg'])}")
    report.append(f"Median Total Aid per Student: {format_currency(median_aid)}")
    report.append("\n" + _t(f"{_T}.labels.estimated_cost_attendance", "Estimated Cost of Attendance: {amount}",
                                  amount=format_currency(_ESTIMATED_COA)))
    if coverage["avg"] > 0:
        coverage_pct = _ratio_pct(coverage["avg"], _ESTIMATED_COA)
        report.append(f"Average Aid Coverage: {coverage_pct:.1f}%")
        report.append(f"Average Unmet Need: {format_currency(max(0, _ESTIMATED_COA - coverage['avg']))}")
        if coverage_pct >= 75:
            report.append(_t(f"{_T}.labels.status_strong", "Status: STRONG - High financial need being met"))
        elif coverage_pct >= 50:
            report.append(_t(f"{_T}.labels.status_adequate", "Status: ADEQUATE - Moderate coverage"))
        else:
            report.append(_t(f"{_T}.labels.status_concern", "Status: CONCERN - Significant unmet need"))
    return coverage


def _sai_recommendations(report: List[str], totals: Dict[str, float], coverage: Dict[str, float]) -> None:
    if not totals["rows"]:
        return
    report.append(_t(f"{_T}.based_on_analysis", "Based on the analysis:"))
    report.append("")
    if totals["grant"] < totals["loan"]:
        report.append("• Consider increasing grant/scholarship funding to reduce")
        report.append("  student debt burden")
    if coverage["students"] and coverage["avg"] < _ESTIMATED_COA * 0.5:
        report.append("• Average aid covers less than 50% of COA - evaluate")
        report.append("  institutional aid policies")
    if coverage["multiple"] < coverage["single"]:
        report.append("• Many students rely on single aid source - consider")
        report.append("  package diversification")
    report.append("")
    report.append("• Review SAI/EFC thresholds for Pell Grant eligibility")
    report.append("• Conduct FAFSA completion campaign to ensure all eligible")
    report.append("  students apply for federal aid")
    report.append("• Implement verification process for selected applications")
    report.append("• Monitor professional judgment requests for special circumstances")


def build_sai_report(connect: Optional[Callable] = None) -> str:
    connect = connect or _default_connect
    report = [
        _RULE,
        _t(f"{_T}.report_header.sai", "STUDENT AID INDEX (SAI) / EXPECTED FAMILY CONTRIBUTION (EFC) REPORT"),
        _stamp(),
        f"Academic Year: {get_current_academic_year()}",
        _RULE, "",
        _t(f"{_T}.notes.sai_description", "This report analyzes financial need based on aid awards and costs."),
        _t(f"{_T}.notes.sai_fafsa_note", "Note: SAI/EFC data typically comes from FAFSA submissions."),
        "",
    ]
    with connect() as conn:
        report += [_t(f"{_T}.sections.aid_by_award_level", "SECTION 1: AID DISTRIBUTION BY AWARD LEVEL"), _LINE]
        _sai_need_levels(report, conn)
        report.append("")
        report += [_t(f"{_T}.sections.package_composition", "SECTION 2: AID PACKAGE COMPOSITION ANALYSIS"), _LINE]
        _sai_package_composition(report, conn)
        report.append("")
        report += [_t(f"{_T}.sections.grant_vs_loan", "SECTION 3: GRANT vs LOAN DISTRIBUTION"), _LINE]
        totals = _sai_grant_vs_loan(report, conn)
        report.append("")
        report += [_t(f"{_T}.sections.coverage_analysis", "SECTION 4: COVERAGE AND NEED ANALYSIS"), _LINE]
        coverage = _sai_coverage(report, conn)
        report.append("")
        report += [_t(f"{_T}.sections.recommendations", "SECTION 5: RECOMMENDATIONS"), _LINE]
        _sai_recommendations(report, totals, coverage)

    report += ["", _RULE, _t(f"{_T}.end_sai_report", "END OF SAI/EFC ANALYSIS REPORT"), _RULE, ""]
    report.append(_t(f"{_T}.notes.sai_overview_note",
                           "Note: This report provides an overview of financial need and aid distribution.\n"
                           "For detailed SAI/EFC values, import FAFSA data via ISIR processing."))
    return "\n".join(report)


# --------------------------------------------------------------------------- #
# 6. Need analysis
# --------------------------------------------------------------------------- #
def _need_overall(report: List[str], conn) -> None:
    overall = conn.execute("""
        SELECT
            COUNT(DISTINCT sfa.student_id) as aided_students,
            SUM(sfa.awarded_amount) as total_awarded,
            AVG(sfa.awarded_amount) as avg_awarded,
            SUM(sfa.disbursed_amount) as total_disbursed
        FROM student_financial_aid sfa
        WHERE sfa.status IN ('awarded', 'disbursed')
    """).fetchone()
    aided = 0
    if overall:
        d = dict(overall)
        aided = d['aided_students'] or 0
        report.append(_t(f"{_T}.labels.students_receiving_aid", "Students Receiving Aid: {count}", count=aided))
        report.append(_t(f"{_T}.labels.total_amount_awarded", "Total Amount Awarded: {amount}", amount=format_currency(d['total_awarded'])))
        report.append(_t(f"{_T}.labels.average_award_amount", "Average Award Amount: {amount}", amount=format_currency(d['avg_awarded'])))
        report.append(_t(f"{_T}.labels.total_amount_disbursed", "Total Amount Disbursed: {amount}", amount=format_currency(d['total_disbursed'])))
    total_enrolled = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    report.append(f"\nTotal Enrolled Students: {total_enrolled}")
    report.append(f"Students Without Aid: {total_enrolled - aided}")
    if total_enrolled > 0:
        report.append(f"Aid Participation Rate: {aided / total_enrolled * 100:.1f}%")


def _need_by_category(report: List[str], conn) -> None:
    rows = conn.execute("""
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
    for row in rows:
        r = dict(row)
        report.append(f"\n{(r['category'] or 'Other').upper()}")
        report.append(f"  Recipients: {r['recipients']}")
        report.append(f"  Total: {format_currency(r['total'])}")
        report.append(f"  Average: {format_currency(r['avg_amount'])}")


def _need_top_aid(report: List[str], conn) -> None:
    rows = conn.execute("""
        SELECT sfa.student_id, SUM(sfa.awarded_amount) as total_aid, COUNT(DISTINCT sfa.aid_type_id) as aid_sources
        FROM student_financial_aid sfa
        WHERE sfa.status IN ('awarded', 'disbursed')
        GROUP BY sfa.student_id
        ORDER BY total_aid DESC
        LIMIT 15
    """).fetchall()
    if not rows:
        report.append(_t(f"{_T}.no_aid_data", "No aid data available"))
        return
    report.append(f"{_t(f'{_T}.labels.student_id_col', 'Student ID'):<15} "
                  f"{_t(f'{_T}.labels.total_aid_col', 'Total Aid'):>15} "
                  f"{_t(f'{_T}.labels.sources_col', 'Sources'):>10}")
    report.append("-" * 40)
    for row in rows:
        r = dict(row)
        report.append(f"{str(r['student_id']):<15} {format_currency(r['total_aid']):>15} {r['aid_sources']:>10}")


def _need_status_breakdown(report: List[str], conn) -> None:
    rows = conn.execute("""
        SELECT status, COUNT(*) as count, SUM(awarded_amount) as total
        FROM student_financial_aid
        GROUP BY status
        ORDER BY count DESC
    """).fetchall()
    for row in rows:
        r = dict(row)
        report.append(f"  {(r['status'] or '').title()}: {r['count']} awards, {format_currency(r['total'])}")


def build_need_analysis_report(connect: Optional[Callable] = None) -> str:
    connect = connect or _default_connect
    report = [
        _RULE,
        _t(f"{_T}.report_header.need_analysis", "FINANCIAL NEED ANALYSIS REPORT"),
        _stamp(),
        f"Academic Year: {get_current_academic_year()}",
        _RULE, "",
    ]
    with connect() as conn:
        report += [_t(f"{_T}.sections.overall_need_summary", "SECTION 1: OVERALL FINANCIAL NEED SUMMARY"), _LINE]
        _need_overall(report, conn)
        report.append("")
        report += [_t(f"{_T}.sections.aid_by_category", "SECTION 2: AID DISTRIBUTION BY CATEGORY"), _LINE]
        _need_by_category(report, conn)
        report.append("")
        report += [_t(f"{_T}.sections.highest_total_aid", "SECTION 3: STUDENTS WITH HIGHEST TOTAL AID"), _LINE]
        _need_top_aid(report, conn)
        report.append("")
        report += [_t(f"{_T}.sections.aid_status_breakdown", "SECTION 4: AID STATUS BREAKDOWN"), _LINE]
        _need_status_breakdown(report, conn)

    report += ["", _RULE, _t(f"{_T}.end_need_report", "END OF NEED ANALYSIS REPORT"), _RULE]
    return "\n".join(report)



__all__ = ["build_compliance_report", "build_need_analysis_report", "build_sai_report"]
