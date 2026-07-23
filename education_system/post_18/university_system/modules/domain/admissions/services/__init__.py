"""
Admissions & Recruitment CRM Service Module
"""

from education_system.post_18.university_system.modules.domain.admissions.services.admissions_crm_core import (
    ProspectManager, ApplicationManager, ReviewWorkflowManager,
    CampaignManager, TourManager, YieldPredictionManager
)

__all__ = [
    'ProspectManager', 'ApplicationManager', 'ReviewWorkflowManager',
    'CampaignManager', 'TourManager', 'YieldPredictionManager'
]
