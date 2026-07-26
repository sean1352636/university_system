"""Financial reports package - split from monolithic financial_reports.py.

All public names are re-exported here for backward compatibility.
Existing imports like:
    from education_system.systems.university.domain.finance.reporting.financial_reports import FinancialAlertSystem
continue to work unchanged.
"""

from education_system.systems.university.domain.finance.reporting.financial_reports._common import (
    set_auth,
    auth,
    get_current_academic_year,
    get_auth,
    get_connection,
    HAS_AUTH,
)
from education_system.systems.university.domain.finance.reporting.financial_reports.alerts import FinancialAlertSystem
from education_system.systems.university.domain.finance.reporting.financial_reports.ml import (
    PaymentPredictionML,
    AnomalyDetector,
    _RestrictedModelUnpickler,
    _safe_model_load,
    _BLOCKED_NAMES,
)
from education_system.systems.university.domain.finance.reporting.financial_reports.forecasting import CashFlowForecaster
from education_system.systems.university.domain.finance.reporting.financial_reports.analyzers import StudentLifecycleAnalyzer, ComparativeAnalyzer
from education_system.systems.university.domain.finance.reporting.financial_reports.reports import (
    generate_advanced_financial_forecasting,
    generate_comprehensive_budget_variance_report,
    real_time_financial_dashboard,
    automated_reporting_system,
)
from education_system.systems.university.domain.finance.reporting.financial_reports.scenario_planning import scenario_planning_tools
from education_system.systems.university.domain.finance.reporting.financial_reports.export import advanced_export_system
from education_system.systems.university.domain.finance.reporting.financial_reports.compliance import compliance_audit_system
from education_system.systems.university.domain.finance.reporting.financial_reports.menu import display_enhanced_finance_menu
from education_system.systems.university.domain.finance.reporting.financial_reports.db_setup import initialize_enhanced_database, run_system_health_check
