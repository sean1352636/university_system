"""
Staff HR CLI Menus

Individual menu modules for each Staff HR feature area.
"""

from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.profile_menu import (
    display_profile_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.leave_menu import (
    display_leave_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.time_menu import (
    display_time_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.training_menu import (
    display_training_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.appraisal_menu import (
    display_appraisal_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.asset_menu import (
    display_asset_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.academic_menu import (
    display_academic_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.communication_menu import (
    display_communication_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.admin_menu import (
    display_admin_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.directory_menu import (
    display_directory_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.recruitment_menu import (
    display_recruitment_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.onboarding_menu import (
    display_onboarding_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.reports_menu import (
    display_reports_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.contract_menu import (
    display_contract_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.expense_menu import (
    display_expense_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.grievance_menu import (
    display_grievance_menu,
)
from education_system.university_system.modules.domain.operations.staff_hr.cli.menus.exit_menu import (
    display_exit_menu,
)

__all__ = [
    'display_profile_menu',
    'display_leave_menu',
    'display_time_menu',
    'display_training_menu',
    'display_appraisal_menu',
    'display_asset_menu',
    'display_academic_menu',
    'display_communication_menu',
    'display_admin_menu',
    'display_directory_menu',
    'display_recruitment_menu',
    'display_onboarding_menu',
    'display_reports_menu',
    'display_contract_menu',
    'display_expense_menu',
    'display_grievance_menu',
    'display_exit_menu',
]
