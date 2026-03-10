"""
Admissions & Recruitment CRM Service Module
"""

from .admissions_crm_core import (
    ProspectManager, ApplicationManager, ReviewWorkflowManager,
    CampaignManager, TourManager, YieldPredictionManager
)

__all__ = [
    'ProspectManager', 'ApplicationManager', 'ReviewWorkflowManager',
    'CampaignManager', 'TourManager', 'YieldPredictionManager'
]
