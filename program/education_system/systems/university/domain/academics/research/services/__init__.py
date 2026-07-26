"""
Research & Grants Management Service Module
"""

from education_system.systems.university.domain.academics.research.services.research_grants_core import (
    ResearchProjectManager, GrantApplicationManager, PublicationManager,
    MilestoneManager, EquipmentManager, EthicsReviewManager
)

__all__ = [
    'ResearchProjectManager', 'GrantApplicationManager', 'PublicationManager',
    'MilestoneManager', 'EquipmentManager', 'EthicsReviewManager'
]
