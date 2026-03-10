"""
Enhanced Activity Logger GUI Application
A comprehensive graphical interface for the Enhanced Activity Logger with full backward compatibility.

Features:
- Real-time log monitoring and visualization
- Configuration management
- Analytics and reporting
- Security monitoring
- Plugin management
- Database querying and filtering
- Export functionality
- System health monitoring

Author: Enhanced Activity Logger Team
Version: 2.0.0
"""

from .main_gui import EnhancedActivityLoggerGUI
from .theme import LoggerGUITheme
from .status_bar import StatusBar
from .tabs import (
    LogViewerTab,
    AnalyticsTab,
    ConfigurationTab,
    SecurityTab,
    PluginTab,
    QueryTab,
)
from .entry import (
    main,
    launch_logger_gui,
    create_gui_instance,
    check_dependencies,
    get_gui_version,
    print_startup_banner,
    run_demo_mode,
    check_installation,
)

__all__ = [
    'EnhancedActivityLoggerGUI',
    'LoggerGUITheme',
    'StatusBar',
    'LogViewerTab',
    'AnalyticsTab',
    'ConfigurationTab',
    'SecurityTab',
    'PluginTab',
    'QueryTab',
    'main',
    'launch_logger_gui',
    'create_gui_instance',
    'check_dependencies',
    'get_gui_version',
    'print_startup_banner',
    'run_demo_mode',
    'check_installation',
]
