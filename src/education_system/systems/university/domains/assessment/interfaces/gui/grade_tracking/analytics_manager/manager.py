"""Main AnalyticsManager class assembled from mixins."""

from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.tabs import TabsMixin
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.competency import CompetencyMixin
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.risk import RiskMixin
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.performance import PerformanceMixin
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.reports import ReportsMixin
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.exports import ExportsMixin
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.predictions import PredictionsMixin
from education_system.platform.delivery.gui.report_presentation import SectionReportMixin
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.utils import widget_alive


class AnalyticsManager(
    SectionReportMixin,
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

    def _widget_exists(self, widget):
        """Return True if widget exists and is not destroyed.

        The competency/risk refreshes call this before touching a cached
        tree; without it they raised AttributeError on the live widget.
        """
        return widget_alive(widget)
