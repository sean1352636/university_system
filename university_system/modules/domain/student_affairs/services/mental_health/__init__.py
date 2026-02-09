"""
Mental Health & Wellness Portal Service Module

This module provides comprehensive mental health support including counseling,
wellness resources, check-ins, peer support, and mindfulness resources.
"""

from .mental_health_core import (
    CounselorManager,
    AppointmentManager,
    ResourceManager,
    WellnessCheckInManager,
    PeerSupportManager,
    MeditationManager,
)

__all__ = [
    'CounselorManager',
    'AppointmentManager',
    'ResourceManager',
    'WellnessCheckInManager',
    'PeerSupportManager',
    'MeditationManager',
]
