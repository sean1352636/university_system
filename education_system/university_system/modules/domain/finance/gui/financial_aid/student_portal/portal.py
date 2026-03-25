"""
StudentPortal - Main class composing all mixin functionality.
"""

from education_system.university_system.modules.domain.finance.gui.financial_aid.common_imports import (
    get_auth,
    FinancialAidManager,
    ScholarshipManager,
    get_current_user,
    get_student_id,
)

from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.dashboard import DashboardMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.scholarships import ScholarshipsMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.financial_aid import FinancialAidMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.applications import ApplicationsMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.awards import AwardsMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.recommendations import RecommendationsMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.deadlines import DeadlinesMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.documents import DocumentsMixin
from education_system.university_system.modules.domain.finance.gui.financial_aid.student_portal.profile import ProfileMixin


class StudentPortal(
    DashboardMixin,
    ScholarshipsMixin,
    FinancialAidMixin,
    ApplicationsMixin,
    AwardsMixin,
    RecommendationsMixin,
    DeadlinesMixin,
    DocumentsMixin,
    ProfileMixin,
):
    """Student-facing portal for financial aid and scholarships"""

    def __init__(self, parent_frame, auth_instance=None):
        """
        Initialize student portal

        Args:
            parent_frame: Parent tkinter frame
            auth_instance: Authentication instance
        """
        self.parent_frame = parent_frame
        self.auth = auth_instance or get_auth()
        self.aid_manager = FinancialAidManager()
        self.scholarship_manager = ScholarshipManager()

        # Current user info
        self.student_id = get_student_id()
        self.current_user = get_current_user()
