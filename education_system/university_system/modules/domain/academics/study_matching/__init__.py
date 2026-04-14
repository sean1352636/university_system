"""
Peer Study Matching Module

Intelligent peer matching system that connects students for collaborative learning.

Features:
- Study profile with learning preferences
- AI-powered compatibility matching
- Study group formation and management
- Virtual study rooms with Pomodoro timer
- Anonymous Q&A board
- Comprehensive analytics

Components:
- Service Layer: StudyMatchingService
- CLI Interface: StudyMatchingCLI
- GUI Interface: StudyMatchingGUI
"""

from education_system.university_system.modules.domain.academics.study_matching.services.study_matching_service import StudyMatchingService
from education_system.university_system.modules.domain.academics.study_matching.cli.study_matching_cli import StudyMatchingCLI
from education_system.university_system.modules.domain.academics.study_matching.gui.study_matching_gui import StudyMatchingGUI

__all__ = [
    'StudyMatchingService',
    'StudyMatchingCLI',
    'StudyMatchingGUI'
]

__version__ = '1.0.0'
