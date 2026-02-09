"""
Academics GUI Module

GUI interfaces for academic management.
"""

from __future__ import annotations

__all__ = [
    'launch_blockchain_credentials_gui',
    'GradeTrackingManagementGUI',
    'CalendarGUI',
]

# Import main launchers
try:
    from university_system.modules.domain.academics.gui.blockchain_credentials_gui import launch_blockchain_credentials_gui
except ImportError:
    launch_blockchain_credentials_gui = None

try:
    from university_system.modules.domain.academics.gui.grade_tracking_management_gui import GradeTrackingManagementGUI
except ImportError:
    GradeTrackingManagementGUI = None

try:
    from university_system.modules.domain.academics.gui.academic_calendar.main_gui import CalendarGUI
except ImportError:
    CalendarGUI = None
