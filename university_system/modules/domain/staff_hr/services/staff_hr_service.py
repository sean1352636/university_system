"""
Staff HR Service - Main Orchestrator

Provides unified access to all HR managers and handles
cross-cutting concerns like initialization and singleton access.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

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

logger = logging.getLogger(__name__)


class StaffHRService:
    """Main service orchestrating all staff HR operations.

    Provides unified access to all HR managers through a single interface.
    Use get_staff_hr_service() to get the singleton instance.

    Example:
        service = get_staff_hr_service()
        profile = service.employee.get_profile('user123')
        balance = service.leave.get_balance('user123')
    """

    def __init__(self):
        """Initialize all managers."""
        self._employee = None
        self._leave = None
        self._time = None
        self._training = None
        self._performance = None
        self._onboarding = None
        self._academic = None
        self._communication = None
        self._recruitment = None
        self._admin = None
        self._assets = None

    @property
    def employee(self) -> EmployeeManager:
        """Get employee manager (lazy initialization)."""
        if self._employee is None:
            self._employee = EmployeeManager()
        return self._employee

    @property
    def leave(self) -> LeaveManager:
        """Get leave manager."""
        if self._leave is None:
            self._leave = LeaveManager()
        return self._leave

    @property
    def time(self) -> TimeManager:
        """Get time manager."""
        if self._time is None:
            self._time = TimeManager()
        return self._time

    @property
    def training(self) -> TrainingManager:
        """Get training manager."""
        if self._training is None:
            self._training = TrainingManager()
        return self._training

    @property
    def performance(self) -> PerformanceManager:
        """Get performance manager."""
        if self._performance is None:
            self._performance = PerformanceManager()
        return self._performance

    @property
    def onboarding(self) -> OnboardingManager:
        """Get onboarding manager."""
        if self._onboarding is None:
            self._onboarding = OnboardingManager()
        return self._onboarding

    @property
    def academic(self) -> AcademicStaffManager:
        """Get academic staff manager."""
        if self._academic is None:
            self._academic = AcademicStaffManager()
        return self._academic

    @property
    def communication(self) -> CommunicationManager:
        """Get communication manager."""
        if self._communication is None:
            self._communication = CommunicationManager()
        return self._communication

    @property
    def recruitment(self) -> RecruitmentManager:
        """Get recruitment manager."""
        if self._recruitment is None:
            self._recruitment = RecruitmentManager()
        return self._recruitment

    @property
    def admin(self) -> AdminToolsManager:
        """Get admin tools manager."""
        if self._admin is None:
            self._admin = AdminToolsManager()
        return self._admin

    @property
    def assets(self) -> AssetManager:
        """Get asset manager."""
        if self._assets is None:
            self._assets = AssetManager()
        return self._assets

    def get_employee_dashboard(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive employee dashboard data.

        Returns a summary of all relevant HR data for an employee.
        """
        dashboard = {
            'profile': None,
            'leave_balance': [],
            'pending_leave_requests': [],
            'current_clock_status': None,
            'pending_training': [],
            'expiring_certifications': [],
            'active_goals': [],
            'pending_onboarding_tasks': [],
            'unread_announcements': 0,
            'assigned_assets': [],
        }

        try:
            # Profile
            dashboard['profile'] = EmployeeManager.get_profile(user_id)

            # Leave
            dashboard['leave_balance'] = LeaveManager.get_balance(user_id)
            dashboard['pending_leave_requests'] = LeaveManager.get_requests(
                user_id, status='pending', limit=5
            )

            # Time
            dashboard['current_clock_status'] = TimeManager.get_current_status(user_id)

            # Training
            dashboard['pending_training'] = TrainingManager.get_mandatory_incomplete(user_id)
            dashboard['expiring_certifications'] = TrainingManager.get_expiring_certs(
                days=30
            )

            # Performance
            active_cycle = PerformanceManager.get_active_cycle()
            if active_cycle:
                dashboard['active_goals'] = PerformanceManager.get_goals(
                    user_id, cycle_id=active_cycle.get('cycle_id')
                )

            # Onboarding
            dashboard['pending_onboarding_tasks'] = OnboardingManager.get_pending_tasks(
                user_id=user_id
            )

            # Communication
            dashboard['unread_announcements'] = CommunicationManager.get_unread_count(
                user_id
            )

            # Assets
            dashboard['assigned_assets'] = AssetManager.get_user_assets(user_id)

        except Exception as e:
            logger.error(f"Error building dashboard for {user_id}: {e}")

        return dashboard

    def get_manager_dashboard(self, manager_id: str) -> Dict[str, Any]:
        """Get manager dashboard with team-related data."""
        dashboard = {
            'pending_leave_approvals': [],
            'pending_timesheet_approvals': [],
            'pending_appraisal_reviews': [],
            'team_members': [],
            'pending_document_approvals': [],
            'open_job_postings': [],
        }

        try:
            # Approvals
            dashboard['pending_leave_approvals'] = LeaveManager.get_pending_approvals(
                manager_id
            )
            dashboard['pending_timesheet_approvals'] = TimeManager.get_pending_approvals(
                manager_id
            )
            dashboard['pending_appraisal_reviews'] = PerformanceManager.get_pending_reviews(
                manager_id
            )
            dashboard['pending_document_approvals'] = AdminToolsManager.get_pending_approvals(
                manager_id
            )

            # Team
            dashboard['team_members'] = EmployeeManager.get_staff_by_manager(manager_id)

            # Recruitment
            dashboard['open_job_postings'] = RecruitmentManager.get_job_postings(
                status='open', limit=10
            )

        except Exception as e:
            logger.error(f"Error building manager dashboard for {manager_id}: {e}")

        return dashboard


# Singleton instance
_service_instance: Optional[StaffHRService] = None


def get_staff_hr_service() -> StaffHRService:
    """Get or create the staff HR service singleton.

    Returns:
        StaffHRService: The singleton service instance.

    Example:
        service = get_staff_hr_service()
        profile = service.employee.get_profile('user123')
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = StaffHRService()
    return _service_instance


def reset_service():
    """Reset the service singleton (useful for testing)."""
    global _service_instance
    _service_instance = None
