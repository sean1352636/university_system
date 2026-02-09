"""
Staff HR Managers

Manager classes for Staff HR business logic.
Each manager handles a specific domain area.
"""

from university_system.modules.domain.staff_hr.services.managers.employee_manager import (
    EmployeeManager,
)
from university_system.modules.domain.staff_hr.services.managers.leave_manager import (
    LeaveManager,
)
from university_system.modules.domain.staff_hr.services.managers.time_manager import (
    TimeManager,
)
from university_system.modules.domain.staff_hr.services.managers.training_manager import (
    TrainingManager,
)
from university_system.modules.domain.staff_hr.services.managers.performance_manager import (
    PerformanceManager,
)
from university_system.modules.domain.staff_hr.services.managers.onboarding_manager import (
    OnboardingManager,
)
from university_system.modules.domain.staff_hr.services.managers.academic_staff_manager import (
    AcademicStaffManager,
)
from university_system.modules.domain.staff_hr.services.managers.communication_manager import (
    CommunicationManager,
)
from university_system.modules.domain.staff_hr.services.managers.recruitment_manager import (
    RecruitmentManager,
)
from university_system.modules.domain.staff_hr.services.managers.admin_tools_manager import (
    AdminToolsManager,
)
from university_system.modules.domain.staff_hr.services.managers.asset_manager import (
    AssetManager,
)
from university_system.modules.domain.staff_hr.services.managers.contract_manager import (
    ContractManager,
)
from university_system.modules.domain.staff_hr.services.managers.expense_manager import (
    ExpenseManager,
)
from university_system.modules.domain.staff_hr.services.managers.grievance_manager import (
    GrievanceManager,
)
from university_system.modules.domain.staff_hr.services.managers.exit_manager import (
    ExitManager,
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
]
