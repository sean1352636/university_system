"""
Staff HR GUI Components

Provides GUI interfaces for all Staff HR features.
"""

from university_system.modules.domain.staff_hr.gui.staff_hr_gui import StaffHRGUI
from university_system.modules.domain.staff_hr.gui.leave_management_gui import LeaveManagementGUI
from university_system.modules.domain.staff_hr.gui.time_attendance_gui import TimeAttendanceGUI
from university_system.modules.domain.staff_hr.gui.training_gui import TrainingGUI
from university_system.modules.domain.staff_hr.gui.appraisal_gui import AppraisalGUI
from university_system.modules.domain.staff_hr.gui.onboarding_gui import OnboardingGUI
from university_system.modules.domain.staff_hr.gui.contract_gui import ContractGUI
from university_system.modules.domain.staff_hr.gui.expense_gui import ExpenseGUI
from university_system.modules.domain.staff_hr.gui.grievance_gui import GrievanceGUI
from university_system.modules.domain.staff_hr.gui.exit_gui import ExitGUI

__all__ = [
    'StaffHRGUI',
    'LeaveManagementGUI',
    'TimeAttendanceGUI',
    'TrainingGUI',
    'AppraisalGUI',
    'OnboardingGUI',
    'ContractGUI',
    'ExpenseGUI',
    'GrievanceGUI',
    'ExitGUI',
]
