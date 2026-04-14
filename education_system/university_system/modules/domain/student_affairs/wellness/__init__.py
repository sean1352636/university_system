"""
Mental Health & Wellness Module

Provides comprehensive wellness tracking including:
- Mental health check-ins
- Mood tracking with pattern recognition
- Sleep and wellness goals
- Crisis resources
- Exercise and hydration tracking
"""

from education_system.university_system.modules.domain.student_affairs.wellness.services.wellness_service import WellnessService
from education_system.university_system.modules.domain.student_affairs.wellness.cli.wellness_cli import WellnessCLI
from education_system.university_system.modules.domain.student_affairs.wellness.gui.wellness_gui import WellnessGUI

__all__ = ['WellnessService', 'WellnessCLI', 'WellnessGUI']
