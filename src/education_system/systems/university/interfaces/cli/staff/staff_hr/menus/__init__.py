"""
Staff HR CLI Menus

Individual menu modules for each Staff HR feature area.
"""

from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.profile_menu import (
    display_profile_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.leave_menu import (
    display_leave_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.time_menu import (
    display_time_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.training_menu import (
    display_training_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.appraisal_menu import (
    display_appraisal_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.asset_menu import (
    display_asset_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.academic_menu import (
    display_academic_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.communication_menu import (
    display_communication_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.admin_menu import (
    display_admin_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.directory_menu import (
    display_directory_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.recruitment_menu import (
    display_recruitment_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.onboarding_menu import (
    display_onboarding_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.reports_menu import (
    display_reports_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.contract_menu import (
    display_contract_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.expense_menu import (
    display_expense_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.grievance_menu import (
    display_grievance_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.exit_menu import (
    display_exit_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.grant_budget_menu import (
    display_grant_budget_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.travel_menu import (
    display_travel_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.cover_menu import (
    display_cover_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.curriculum_menu import (
    display_curriculum_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.faculty_schedule_menu import (
    display_faculty_schedule_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.payroll_menu import (
    display_payroll_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.mentoring_menu import (
    display_mentoring_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.sabbatical_menu import (
    display_sabbatical_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.peer_review_menu import (
    display_peer_review_menu,
)
from education_system.systems.university.interfaces.cli.staff.staff_hr.menus.ip_menu import (
    display_ip_menu,
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
    'display_grant_budget_menu',
    'display_travel_menu',
    'display_cover_menu',
    'display_curriculum_menu',
    'display_faculty_schedule_menu',
    'display_payroll_menu',
    'display_mentoring_menu',
    'display_sabbatical_menu',
    'display_peer_review_menu',
    'display_ip_menu',
]
