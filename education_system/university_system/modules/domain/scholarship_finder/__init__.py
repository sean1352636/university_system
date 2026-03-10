"""
Scholarship Finder Module

Advanced scholarship discovery and management system with personalized
recommendations, application tracking, and document vault.
"""

from education_system.university_system.modules.domain.scholarship_finder.services.scholarship_service import (
    ScholarshipDatabase,
    StudentProfileManager,
    RecommendationEngine,
    ApplicationManager,
    DocumentVaultManager
)
from education_system.university_system.modules.domain.scholarship_finder.cli.scholarship_cli import ScholarshipFinderCLI

__all__ = [
    'ScholarshipDatabase',
    'StudentProfileManager',
    'RecommendationEngine',
    'ApplicationManager',
    'DocumentVaultManager',
    'ScholarshipFinderCLI'
]
