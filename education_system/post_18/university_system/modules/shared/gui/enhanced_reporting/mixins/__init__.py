"""Mixin classes for the ReportingSystemGUI.

Each mixin extracts a cohesive group of methods so that ``core.py`` stays
small while every method remains accessible via ``self``.
"""

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.api_handlers_mixin import ApiHandlersMixin
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.templates_mixin import TemplatesMixin
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.reports_mixin import ReportsMixin
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.analytics_mixin import AnalyticsMixin
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.scheduling_mixin import SchedulingMixin
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.dialogs_mixin import DialogsMixin
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.maintenance_mixin import MaintenanceMixin
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.mixins.config_mixin import ConfigMixin

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
