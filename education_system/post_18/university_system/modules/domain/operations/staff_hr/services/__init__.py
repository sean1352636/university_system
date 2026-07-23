"""
Staff HR Services

Business logic for Staff HR features.
"""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.staff_hr_service import (
    StaffHRService,
    get_staff_hr_service,
    reset_service,
)

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers import (
    EmployeeManager,
    LeaveManager,
    TimeManager,
    TrainingManager,
    PerformanceManager,
    OnboardingManager,
    AcademicStaffManager,
    CommunicationManager,
    RecruitmentManager,
    AdminToolsManager,
    AssetManager,
)

__all__ = [
    # Main service
    'StaffHRService',
    'get_staff_hr_service',
    'reset_service',
    # Managers
    'EmployeeManager',
    'LeaveManager',
    'TimeManager',
    'TrainingManager',
    'PerformanceManager',
    'OnboardingManager',
    'AcademicStaffManager',
    'CommunicationManager',
    'RecruitmentManager',
    'AdminToolsManager',
    'AssetManager',
]
