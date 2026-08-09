"""
Scholarship Finder Module

Advanced scholarship discovery and management system with personalized
recommendations, application tracking, and document vault.
"""

from education_system.systems.university.domains.finance.domain.scholarship_finder.services.scholarship_service import (
    ScholarshipDatabase,
    StudentProfileManager,
    RecommendationEngine,
    ApplicationManager,
    DocumentVaultManager
)
from education_system.systems.university.domains.finance.interfaces.cli.scholarship_finder.scholarship_cli import ScholarshipFinderCLI

__all__ = [
    'ScholarshipDatabase',
    'StudentProfileManager',
    'RecommendationEngine',
    'ApplicationManager',
    'DocumentVaultManager',
    'ScholarshipFinderCLI'
]
