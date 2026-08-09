"""
AI Study Companion CLI Module

Exports the CLI interface for AI-powered study features.
"""

from education_system.systems.university.interfaces.cli.academics.ai_study.ai_study_cli import (
    AIStudyCLI,
    display_ai_study_menu,
    init_ai_study,
    set_auth,
)

__all__ = [
    'AIStudyCLI',
    'display_ai_study_menu',
    'init_ai_study',
    'set_auth',
]
