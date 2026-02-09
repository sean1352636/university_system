"""Backwards-compatible shim that re-exports the modular finance helpers."""

from __future__ import annotations

# Re-export all public APIs from finance_misc modules
from university_system.modules.domain.finance.core.students import (
    student_exists,
    get_student_name,
    create_sample_students,
    view_student_credits,
    add_student_credit,
    view_credit_history,
    get_student_email,
    get_student_phone,
    api_get_student_financial_summary,
    apply_credit_to_fees,
)
from university_system.modules.domain.finance.core.payments import (
    manual_rate_update,
    process_stripe_payment,
    generate_qr_payment_code,
)
from university_system.modules.domain.finance.core.menu import (
    display_enhanced_finance_menu,
)
from university_system.modules.domain.finance.core.finance_db_operations import (
    init_enhanced_finance_db,
    init_default_enhanced_data,
    initialize_finance,
    complete_database_fix,
    verify_fix,
    quick_fix_database,
    ensure_database_exists,
    check_required_packages,
)
from university_system.modules.domain.finance.core.communications import (
    send_email_smtp,
    send_email_sendgrid,
    send_email_aws_ses,
    setup_email_config,
    setup_sms_config,
    send_sms_twilio,
    send_sms_aws_sns,
    test_email_service,
    test_sms_service,
    send_arrangement_confirmation,
)
from university_system.modules.domain.finance.core.analytics import (
    calculate_growth_rate,
    calculate_seasonal_factors,
    analyze_fee_structure_impact,
    view_overdue_accounts,
    assign_case_to_agency,
    start_background_scheduler,
    generate_enrollment_projections,
    generate_cash_flow_analysis,
    generate_risk_analysis,
    generate_scenario_planning,
    recovery_rate_analysis,
    update_actual_amounts,
)
from university_system.modules.domain.finance.core.aid import (
    approve_reject_aid_application,
    manage_aid_types,
    view_aid_types,
    create_aid_type,
    edit_aid_type,
    deactivate_aid_type,
    review_pending_aid_applications,
    track_loan_repayments,
    process_loan_payment,
    aid_distribution_summary,
    aid_by_academic_year,
    aid_effectiveness_analysis,
    view_aid_application_detail,
    apply_aid_to_fees,
    create_payment_arrangement,
)

__all__ = [
    # students
    'student_exists',
    'get_student_name',
    'create_sample_students',
    'view_student_credits',
    'add_student_credit',
    'view_credit_history',
    'get_student_email',
    'get_student_phone',
    'api_get_student_financial_summary',
    'apply_credit_to_fees',
    # payments
    'manual_rate_update',
    'process_stripe_payment',
    'generate_qr_payment_code',
    # menu
    'display_enhanced_finance_menu',
    # database
    'init_enhanced_finance_db',
    'init_default_enhanced_data',
    'initialize_finance',
    'complete_database_fix',
    'verify_fix',
    'quick_fix_database',
    'ensure_database_exists',
    'check_required_packages',
    # communications
    'send_email_smtp',
    'send_email_sendgrid',
    'send_email_aws_ses',
    'setup_email_config',
    'setup_sms_config',
    'send_sms_twilio',
    'send_sms_aws_sns',
    'test_email_service',
    'test_sms_service',
    'send_arrangement_confirmation',
    # analytics
    'calculate_growth_rate',
    'calculate_seasonal_factors',
    'analyze_fee_structure_impact',
    'view_overdue_accounts',
    'assign_case_to_agency',
    'start_background_scheduler',
    'generate_enrollment_projections',
    'generate_cash_flow_analysis',
    'generate_risk_analysis',
    'generate_scenario_planning',
    'recovery_rate_analysis',
    'update_actual_amounts',
    # aid
    'approve_reject_aid_application',
    'manage_aid_types',
    'view_aid_types',
    'create_aid_type',
    'edit_aid_type',
    'deactivate_aid_type',
    'review_pending_aid_applications',
    'track_loan_repayments',
    'process_loan_payment',
    'aid_distribution_summary',
    'aid_by_academic_year',
    'aid_effectiveness_analysis',
    'view_aid_application_detail',
    'apply_aid_to_fees',
    'create_payment_arrangement',
]
