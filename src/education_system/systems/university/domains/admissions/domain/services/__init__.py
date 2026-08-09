"""
Admissions & Recruitment CRM Service Module
"""

from education_system.systems.university.domains.admissions.domain.services.admissions_crm_core import (
    ProspectManager, ApplicationManager, ReviewWorkflowManager,
    CampaignManager, TourManager, YieldPredictionManager
)

__all__ = [
    'ProspectManager', 'ApplicationManager', 'ReviewWorkflowManager',
    'CampaignManager', 'TourManager', 'YieldPredictionManager'
]
