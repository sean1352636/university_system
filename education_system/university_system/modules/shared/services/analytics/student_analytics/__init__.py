"""Student Analytics package - composed from mixin modules."""

from education_system.university_system.modules.shared.services.analytics.student_analytics.config import configure_matplotlib, CONFIG, GUI_AVAILABLE
from education_system.university_system.modules.shared.services.analytics.student_analytics.base import StudentAnalyticsBase
from education_system.university_system.modules.shared.services.analytics.student_analytics.data_access import DataAccessMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.demographics import DemographicsMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.grades import GradesMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.enrollment import EnrollmentMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.risk import RiskMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.modules import ModulesMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.correlations import CorrelationsMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.engagement import EngagementMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.cohorts import CohortsMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.predictive import PredictiveMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.reporting import ReportingMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.cli import CLIMixin
from education_system.university_system.modules.shared.services.analytics.student_analytics.utilities import UtilitiesMixin


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
