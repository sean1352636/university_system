"""Stable finance facade for legacy GUI consumers.

The finance domain was split into focused modules, but the legacy layout GUI
continued importing every operation from ``financial_core`` in two atomic
imports. One absent export therefore replaced all operations with no-op stubs.
This facade resolves each operation independently from its canonical module.
"""

from __future__ import annotations

from importlib import import_module
from typing import Callable

_ROOT = "education_system.systems.university.domain.finance"

_FUNCTION_MODULES = {
    # Collections and collection agencies
    "assign_to_collection_agency": "reporting.revenue_analytics.collections",
    "track_collection_progress": "reporting.revenue_analytics.collections",
    "update_collection_case_status": "reporting.revenue_analytics.collections",
    "create_collection_case": "reporting.revenue_analytics.collections",
    "send_collection_notice": "reporting.revenue_analytics.collections",
    "view_student_collection_detail": "reporting.revenue_analytics.collections",
    "aging_analysis_report": "reporting.revenue_analytics.collection_reports",
    "collection_case_status_report": "reporting.revenue_analytics.collection_reports",
    "collection_performance_summary": "reporting.revenue_analytics.collection_reports",
    "agency_performance_report": "reporting.revenue_analytics.collection_reports",
    "manage_collection_agencies": "reporting.revenue_analytics.agencies",
    "view_collection_agencies": "reporting.revenue_analytics.agencies",
    "add_collection_agency": "reporting.revenue_analytics.agencies",
    "edit_collection_agency": "reporting.revenue_analytics.agencies",
    "deactivate_collection_agency": "reporting.revenue_analytics.agencies",
    "setup_collection_workflows": "reporting.revenue_analytics.agencies",
    # Payments, credits and communications
    "modify_payment_plan": "billing.payment_plans",
    "create_payment_arrangement": "core.aid",
    "send_arrangement_confirmation": "core.communications",
    "view_student_credits": "core.students",
    "add_student_credit": "core.students",
    "apply_credit_to_fees": "core.students",
    "view_credit_history": "core.students",
    "process_stripe_payment": "core.payments",
    "generate_qr_payment_code": "core.payments",
    "setup_email_config": "core.communications",
    "setup_sms_config": "core.communications",
    "test_email_service": "core.communications",
    "test_sms_service": "core.communications",
    # Budgets
    "create_budget_plan": "reporting.budget_analysis",
    "budget_vs_actual_analysis": "reporting.budget_analysis",
    "manage_budget_categories": "reporting.budget_analysis",
    "view_budget_categories": "reporting.budget_analysis",
    "create_budget_category": "reporting.budget_analysis",
    "edit_budget_category": "reporting.budget_analysis",
    "deactivate_budget_category": "reporting.budget_analysis",
    "budget_performance_trends": "reporting.budget_analysis",
    "update_actual_amounts": "core.analytics",
    "variance_analysis_report": "reporting.revenue_analytics.budget",
    "category_performance_report": "reporting.revenue_analytics.budget",
    # Financial aid
    "manage_financial_aid": "scholarships.scholarship_programs",
    "manage_aid_types": "core.aid",
    "view_aid_types": "core.aid",
    "create_aid_type": "core.aid",
    "edit_aid_type": "core.aid",
    "deactivate_aid_type": "core.aid",
    "review_pending_aid_applications": "core.aid",
    "process_loan_payment": "core.aid",
    "view_aid_application_detail": "core.aid",
    "track_loan_repayments": "core.aid",
    "aid_distribution_summary": "core.aid",
    "aid_by_academic_year": "core.aid",
    "aid_effectiveness_analysis": "core.aid",
    "generate_aid_reports": "reporting.revenue_analytics.scholarships",
    "loan_repayment_status_report": "reporting.revenue_analytics.scholarships",
    # Reporting, security and administration
    "view_overdue_accounts": "core.analytics",
    "recovery_rate_analysis": "core.analytics",
    "monthly_revenue_trend_report": "reporting.revenue_analytics.dashboard",
    "export_forecast_report": "reporting.revenue_analytics.scholarships",
    "generate_audit_report": "reporting.revenue_analytics.reports",
    "enhanced_notification_system": "core.security_automation",
    "detect_payment_fraud": "core.security_automation",
    "create_approval_workflow": "core.security_automation",
    "check_required_packages": "core.finance_db_operations",
    "ensure_database_exists": "core.finance_db_operations",
    "complete_database_fix": "core.finance_db_operations",
    "quick_fix_database": "core.finance_db_operations",
    "initialize_finance": "core.finance_db_operations",
    "verify_fix": "core.finance_db_operations",
}

UNAVAILABLE_FUNCTIONS: dict[str, str] = {}


def _unavailable(name: str, reason: str) -> Callable:
    def unavailable(*_args, **_kwargs):
        raise RuntimeError(f"Finance operation '{name}' is unavailable: {reason}")

    unavailable.__name__ = name
    unavailable.__finance_unavailable__ = True
    return unavailable


def _resolve(name: str, module_suffix: str) -> Callable:
    try:
        function = getattr(import_module(f"{_ROOT}.{module_suffix}"), name)
    except (ImportError, AttributeError) as exc:
        reason = str(exc) or type(exc).__name__
        UNAVAILABLE_FUNCTIONS[name] = reason
        return _unavailable(name, reason)
    return function


globals().update({
    name: _resolve(name, module_suffix)
    for name, module_suffix in _FUNCTION_MODULES.items()
})

__all__ = [*_FUNCTION_MODULES, "UNAVAILABLE_FUNCTIONS"]
