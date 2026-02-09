"""
AI Study Companion Module

Provides AI-powered study assistance including:
- Personalized study plan generation
- Spaced repetition flashcard system
- AI-powered concept explainer
"""

from university_system.modules.domain.ai_study.services.ai_study_service import AIStudyService
from university_system.modules.domain.ai_study.cli.ai_study_cli import AIStudyCLI, display_ai_study_menu

__all__ = [
    'AIStudyService',
    'AIStudyCLI',
    'display_ai_study_menu',
]
