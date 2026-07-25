"""
Tab widgets for the Activity Logger GUI.
"""

from education_system.systems.university.interfaces.gui.shell.activity_logger.tabs.log_viewer import LogViewerTab
from education_system.systems.university.interfaces.gui.shell.activity_logger.tabs.analytics import AnalyticsTab
from education_system.systems.university.interfaces.gui.shell.activity_logger.tabs.configuration import ConfigurationTab
from education_system.systems.university.interfaces.gui.shell.activity_logger.tabs.security import SecurityTab
from education_system.systems.university.interfaces.gui.shell.activity_logger.tabs.plugin import PluginTab
from education_system.systems.university.interfaces.gui.shell.activity_logger.tabs.query import QueryTab

__all__ = [
    'LogViewerTab',
    'AnalyticsTab',
    'ConfigurationTab',
    'SecurityTab',
    'PluginTab',
    'QueryTab',
]
