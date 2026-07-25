"""
Mental Health & Wellness Module

Provides comprehensive wellness tracking including:
- Mental health check-ins
- Mood tracking with pattern recognition
- Sleep and wellness goals
- Crisis resources
- Exercise and hydration tracking
"""

from education_system.systems.university.domain.pastoral.wellbeing.wellness.services.wellness_service import WellnessService
from education_system.systems.university.interfaces.cli.pastoral.wellbeing.wellness.wellness_cli import WellnessCLI
from education_system.systems.university.interfaces.gui.pastoral.wellbeing.wellness.wellness_gui import WellnessGUI

__all__ = ['WellnessService', 'WellnessCLI', 'WellnessGUI']
