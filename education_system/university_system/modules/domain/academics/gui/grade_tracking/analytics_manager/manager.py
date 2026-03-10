"""Main AnalyticsManager class assembled from mixins."""

from .tabs import TabsMixin
from .competency import CompetencyMixin
from .risk import RiskMixin
from .performance import PerformanceMixin
from .reports import ReportsMixin
from .exports import ExportsMixin
from .predictions import PredictionsMixin


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
