"""
Staff HR Managers

Manager classes for Staff HR business logic.
Each manager handles a specific domain area.
"""

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.employee_manager import (
    EmployeeManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.leave_manager import (
    LeaveManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.time_manager import (
    TimeManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.training_manager import (
    TrainingManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.performance_manager import (
    PerformanceManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.onboarding_manager import (
    OnboardingManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.academic_staff_manager import (
    AcademicStaffManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.communication_manager import (
    CommunicationManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.recruitment_manager import (
    RecruitmentManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.admin_tools_manager import (
    AdminToolsManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.asset_manager import (
    AssetManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.contract_manager import (
    ContractManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager import (
    ExpenseManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.grievance_manager import (
    GrievanceManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.exit_manager import (
    ExitManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.payroll_manager import (
    PayrollManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.faculty_schedule_manager import (
    FacultyScheduleManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.curriculum_manager import (
    CurriculumManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.travel_manager import (
    TravelManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.sabbatical_manager import (
    SabbaticalManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.committee_manager import (
    CommitteeManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.ip_manager import (
    IPManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.equipment_manager import (
    EquipmentManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.cover_manager import (
    CoverManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.workload_manager import (
    WorkloadManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.directory_manager import (
    DirectoryManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.mentoring_manager import (
    MentoringManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.grant_budget_manager import (
    GrantBudgetManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.peer_review_manager import (
    PeerReviewManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.comm_hub_manager import (
    CommHubManager,
)
from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.teaching_load_manager import (
    TeachingLoadManager,
)

__all__ = [
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
    'ContractManager',
    'ExpenseManager',
    'GrievanceManager',
    'ExitManager',
    'PayrollManager',
    'FacultyScheduleManager',
    'CurriculumManager',
    'TravelManager',
    'SabbaticalManager',
    'CommitteeManager',
    'IPManager',
    'EquipmentManager',
    'CoverManager',
    'WorkloadManager',
    'DirectoryManager',
    'MentoringManager',
    'GrantBudgetManager',
    'PeerReviewManager',
    'CommHubManager',
    'TeachingLoadManager',
]
