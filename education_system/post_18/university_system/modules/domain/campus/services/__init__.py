"""
Campus Events Hub Service Module
"""

from education_system.post_18.university_system.modules.domain.campus.services.campus_events_core import (
    CampusEventManager, EventRegistrationManager, EventSeriesManager,
    EventAnnouncementManager, EventSponsorManager
)

from education_system.post_18.university_system.modules.domain.campus.services.campus_events_gui import launch_campus_events_gui

__all__ = [
    'CampusEventManager', 'EventRegistrationManager', 'EventSeriesManager',
    'EventAnnouncementManager', 'EventSponsorManager',
    'launch_campus_events_gui'
]
