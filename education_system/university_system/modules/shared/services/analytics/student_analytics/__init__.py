"""Student Analytics package - composed from mixin modules."""

from .config import configure_matplotlib, CONFIG, GUI_AVAILABLE
from .base import StudentAnalyticsBase
from .data_access import DataAccessMixin
from .demographics import DemographicsMixin
from .grades import GradesMixin
from .enrollment import EnrollmentMixin
from .risk import RiskMixin
from .modules import ModulesMixin
from .correlations import CorrelationsMixin
from .engagement import EngagementMixin
from .cohorts import CohortsMixin
from .predictive import PredictiveMixin
from .reporting import ReportingMixin
from .cli import CLIMixin
from .utilities import UtilitiesMixin


class StudentAnalytics(
    StudentAnalyticsBase,
    DataAccessMixin,
    DemographicsMixin,
    GradesMixin,
    EnrollmentMixin,
    RiskMixin,
    ModulesMixin,
    CorrelationsMixin,
    EngagementMixin,
    CohortsMixin,
    PredictiveMixin,
    ReportingMixin,
    CLIMixin,
    UtilitiesMixin,
):
    """Full StudentAnalytics composed from mixins."""
    pass


# Main execution
if __name__ == "__main__":
    analytics = StudentAnalytics()
    analytics.display_main_menu()
