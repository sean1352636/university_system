"""
StudentPortal - Main class composing all mixin functionality.
"""

from ..common_imports import (
    get_auth,
    FinancialAidManager,
    ScholarshipManager,
    get_current_user,
    get_student_id,
)

from .dashboard import DashboardMixin
from .scholarships import ScholarshipsMixin
from .financial_aid import FinancialAidMixin
from .applications import ApplicationsMixin
from .awards import AwardsMixin
from .recommendations import RecommendationsMixin
from .deadlines import DeadlinesMixin
from .documents import DocumentsMixin
from .profile import ProfileMixin


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
