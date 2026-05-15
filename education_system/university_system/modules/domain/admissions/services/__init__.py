"""
Admissions & Recruitment CRM Service Module
"""

from education_system.university_system.modules.domain.students.admissions.services.admissions_crm_core import (
    ProspectManager, ApplicationManager, ReviewWorkflowManager,
    CampaignManager, TourManager, YieldPredictionManager
)

__all__ = [
    'ProspectManager', 'ApplicationManager', 'ReviewWorkflowManager',
    'CampaignManager', 'TourManager', 'YieldPredictionManager'
]
