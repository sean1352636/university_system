"""Financial reports package - split from monolithic financial_reports.py.

All public names are re-exported here for backward compatibility.
Existing imports like:
    from education_system.university_system.modules.domain.finance.reporting.financial_reports import FinancialAlertSystem
continue to work unchanged.
"""

from ._common import (
    set_auth,
    auth,
    get_current_academic_year,
    get_auth,
    get_connection,
    HAS_AUTH,
)
from .alerts import FinancialAlertSystem
from .ml import (
    PaymentPredictionML,
    AnomalyDetector,
    _RestrictedModelUnpickler,
    _safe_model_load,
    _BLOCKED_NAMES,
)
from .forecasting import CashFlowForecaster
from .analyzers import StudentLifecycleAnalyzer, ComparativeAnalyzer
from .reports import (
    generate_advanced_financial_forecasting,
    generate_comprehensive_budget_variance_report,
    real_time_financial_dashboard,
    automated_reporting_system,
)
from .scenario_planning import scenario_planning_tools
from .export import advanced_export_system
from .compliance import compliance_audit_system
from .menu import display_enhanced_finance_menu
from .db_setup import initialize_enhanced_database, run_system_health_check
