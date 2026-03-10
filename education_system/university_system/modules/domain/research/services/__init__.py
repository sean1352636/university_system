"""
Research & Grants Management Service Module
"""

from .research_grants_core import (
    ResearchProjectManager, GrantApplicationManager, PublicationManager,
    MilestoneManager, EquipmentManager, EthicsReviewManager
)

__all__ = [
    'ResearchProjectManager', 'GrantApplicationManager', 'PublicationManager',
    'MilestoneManager', 'EquipmentManager', 'EthicsReviewManager'
]
