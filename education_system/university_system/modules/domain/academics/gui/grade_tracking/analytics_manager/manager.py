"""Main AnalyticsManager class assembled from mixins."""

from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.tabs import TabsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.competency import CompetencyMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.risk import RiskMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.performance import PerformanceMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.reports import ReportsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.exports import ExportsMixin
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.predictions import PredictionsMixin


class AnalyticsManager(
    TabsMixin,
    CompetencyMixin,
    RiskMixin,
    PerformanceMixin,
    ReportsMixin,
    ExportsMixin,
    PredictionsMixin,
):
    """Analytics and reporting"""

    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.auth = app.auth
        self.conn = app.conn

    @property
    def content_frame(self):
        """Dynamically get content frame from layout"""
        if hasattr(self.app, 'layout') and hasattr(self.app.layout, 'content_frame'):
            return self.app.layout.content_frame
        return None
