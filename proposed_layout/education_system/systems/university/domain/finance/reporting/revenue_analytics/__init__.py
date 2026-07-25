"""Revenue analytics package - split from monolithic revenue_analytics.py.

All public functions are re-exported here for backward compatibility.
Existing imports like:
    from education_system.systems.university.domain.finance.reporting.revenue_analytics import manage_collections
continue to work unchanged.
"""

from education_system.systems.university.domain.finance.reporting.revenue_analytics.app import (
    auth, app, cipher_suite, logger,
    ENCRYPTION_KEY, SUPPORTED_CURRENCIES, PAYMENT_GATEWAYS, EXCHANGE_API_KEY,
)

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

from education_system.systems.university.domain.finance.reporting.revenue_analytics.reports import (
    generate_financial_reports,
    revenue_summary_report,
    generate_budget_variance_report,
    generate_outstanding_fees_report,
    generate_payment_collection_report,
    generate_audit_report,
)

from education_system.systems.university.domain.finance.reporting.revenue_analytics.dashboard import (
    generate_financial_dashboard,
    student_account_summary_report,
    fee_type_analysis_report,
    payment_method_analysis_report,
    monthly_revenue_trend_report,
)

from education_system.systems.university.domain.finance.reporting.revenue_analytics.forecasting import (
    generate_predictive_analytics,
    generate_revenue_forecast,
    generate_forecast_values,
    generate_enrollment_based_forecast,
    create_revenue_forecast_chart,
    save_forecast_to_database,
    generate_financial_forecasting,
    generate_budget_variance_forecast,
    generate_comprehensive_forecast_report,
)

from education_system.systems.university.domain.finance.reporting.revenue_analytics.budget import (
    generate_budget_reports,
    budget_summary_report,
    variance_analysis_report,
    category_performance_report,
)

from education_system.systems.university.domain.finance.reporting.revenue_analytics.collections import (
    manage_collections,
    create_collection_case,
    send_collection_notice,
    assign_to_collection_agency,
    track_collection_progress,
    update_collection_case_status,
    view_student_collection_detail,
)

from education_system.systems.university.domain.finance.reporting.revenue_analytics.agencies import (
    manage_collection_agencies,
    view_collection_agencies,
    add_collection_agency,
    edit_collection_agency,
    deactivate_collection_agency,
    setup_collection_workflows,
)

from education_system.systems.university.domain.finance.reporting.revenue_analytics.collection_reports import (
    generate_collection_reports,
    collection_performance_summary,
    agency_performance_report,
    aging_analysis_report,
    collection_case_status_report,
)

from education_system.systems.university.domain.finance.reporting.revenue_analytics.scholarships import (
    scholarship_reports,
    student_scholarship_report,
    generate_aid_reports,
    loan_repayment_status_report,
    export_forecast_report,
)
