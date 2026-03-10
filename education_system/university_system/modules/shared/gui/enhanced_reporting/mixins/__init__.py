"""Mixin classes for the ReportingSystemGUI.

Each mixin extracts a cohesive group of methods so that ``core.py`` stays
small while every method remains accessible via ``self``.
"""

from .api_handlers_mixin import ApiHandlersMixin
from .templates_mixin import TemplatesMixin
from .reports_mixin import ReportsMixin
from .analytics_mixin import AnalyticsMixin
from .scheduling_mixin import SchedulingMixin
from .dialogs_mixin import DialogsMixin
from .maintenance_mixin import MaintenanceMixin
from .config_mixin import ConfigMixin

__all__ = [
    "ApiHandlersMixin",
    "TemplatesMixin",
    "ReportsMixin",
    "AnalyticsMixin",
    "SchedulingMixin",
    "DialogsMixin",
    "MaintenanceMixin",
    "ConfigMixin",
]
