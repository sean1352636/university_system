"""
Smart Timetable Optimizer Service Module

NOTE: This module now redirects to the comprehensive module_scheduling system.
"""

# Import from the comprehensive module scheduling system
from university_system.modules.domain.academics.services.module_scheduling import (
    ModuleScheduler,
    display_enhanced_scheduling_menu,
    display_timetable_optimizer_menu,
    launch_timetable_optimizer_gui,
    DAYS_OF_WEEK,
    TIME_SLOTS,
    SESSION_TYPES,
    ROOM_TYPES,
)

__all__ = [
    'ModuleScheduler',
    'display_enhanced_scheduling_menu',
    'display_timetable_optimizer_menu',
    'launch_timetable_optimizer_gui',
    'DAYS_OF_WEEK',
    'TIME_SLOTS',
    'SESSION_TYPES',
    'ROOM_TYPES',
]
