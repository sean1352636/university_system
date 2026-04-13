"""
Research & Grants Module

Provides research project and grant management including proposals,
funding tracking, publications, milestones, and ethics reviews.
"""

from education_system.university_system.modules.domain.research.services import (
    ResearchProjectManager,
    GrantApplicationManager,
    PublicationManager,
)
from education_system.university_system.modules.domain.research.gui import (
    ResearchGrantsGUI,
    launch_research_grants_gui,
)

__all__ = [
    'ResearchProjectManager',
    'GrantApplicationManager',
    'PublicationManager',
    'ResearchGrantsGUI',
    'launch_research_grants_gui',
]
