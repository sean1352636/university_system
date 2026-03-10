"""
Tab widgets for the Activity Logger GUI.
"""

from .log_viewer import LogViewerTab
from .analytics import AnalyticsTab
from .configuration import ConfigurationTab
from .security import SecurityTab
from .plugin import PluginTab
from .query import QueryTab

__all__ = [
    'LogViewerTab',
    'AnalyticsTab',
    'ConfigurationTab',
    'SecurityTab',
    'PluginTab',
    'QueryTab',
]
