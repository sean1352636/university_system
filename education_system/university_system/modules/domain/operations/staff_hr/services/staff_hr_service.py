"""
Staff HR Service - Main Orchestrator

Provides unified access to all HR managers and handles
cross-cutting concerns like initialization and singleton access.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from education_system.university_system.modules.domain.operations.staff_hr.services.managers.employee_manager import (
    EmployeeManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.leave_manager import (
    LeaveManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.time_manager import (
    TimeManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.training_manager import (
    TrainingManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.performance_manager import (
    PerformanceManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.onboarding_manager import (
    OnboardingManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.academic_staff_manager import (
    AcademicStaffManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.communication_manager import (
    CommunicationManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.recruitment_manager import (
    RecruitmentManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.admin_tools_manager import (
    AdminToolsManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.asset_manager import (
    AssetManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.payroll_manager import (
    PayrollManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.faculty_schedule_manager import (
    FacultyScheduleManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.curriculum_manager import (
    CurriculumManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.travel_manager import (
    TravelManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.sabbatical_manager import (
    SabbaticalManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.committee_manager import (
    CommitteeManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.ip_manager import (
    IPManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.equipment_manager import (
    EquipmentManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.cover_manager import (
    CoverManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.workload_manager import (
    WorkloadManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.directory_manager import (
    DirectoryManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.mentoring_manager import (
    MentoringManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.grant_budget_manager import (
    GrantBudgetManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.peer_review_manager import (
    PeerReviewManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.comm_hub_manager import (
    CommHubManager,
)
from education_system.university_system.modules.domain.operations.staff_hr.services.managers.teaching_load_manager import (
    TeachingLoadManager,
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
        self._payroll = None
        self._faculty_schedule = None
        self._curriculum = None
        self._travel = None
        self._sabbatical = None
        self._committee = None
        self._ip = None
        self._equipment = None
        self._cover = None
        self._workload = None
        self._directory = None
        self._mentoring = None
        self._grant_budget = None
        self._peer_review = None
        self._comm_hub = None
        self._teaching_load = None

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

    @property
    def payroll(self) -> PayrollManager:
        """Get payroll manager."""
        if self._payroll is None:
            self._payroll = PayrollManager()
        return self._payroll

    @property
    def faculty_schedule(self) -> FacultyScheduleManager:
        """Get faculty schedule manager."""
        if self._faculty_schedule is None:
            self._faculty_schedule = FacultyScheduleManager()
        return self._faculty_schedule

    @property
    def curriculum(self) -> CurriculumManager:
        """Get curriculum manager."""
        if self._curriculum is None:
            self._curriculum = CurriculumManager()
        return self._curriculum

    @property
    def travel(self) -> TravelManager:
        """Get travel manager."""
        if self._travel is None:
            self._travel = TravelManager()
        return self._travel

    @property
    def sabbatical(self) -> SabbaticalManager:
        """Get sabbatical manager."""
        if self._sabbatical is None:
            self._sabbatical = SabbaticalManager()
        return self._sabbatical

    @property
    def committee(self) -> CommitteeManager:
        """Get committee manager."""
        if self._committee is None:
            self._committee = CommitteeManager()
        return self._committee

    @property
    def ip(self) -> IPManager:
        """Get intellectual property manager."""
        if self._ip is None:
            self._ip = IPManager()
        return self._ip

    @property
    def equipment(self) -> EquipmentManager:
        """Get equipment booking manager."""
        if self._equipment is None:
            self._equipment = EquipmentManager()
        return self._equipment

    @property
    def cover(self) -> CoverManager:
        """Get cover arrangements manager."""
        if self._cover is None:
            self._cover = CoverManager()
        return self._cover

    @property
    def workload(self) -> WorkloadManager:
        """Get workload manager."""
        if self._workload is None:
            self._workload = WorkloadManager()
        return self._workload

    @property
    def directory(self) -> DirectoryManager:
        """Get directory manager."""
        if self._directory is None:
            self._directory = DirectoryManager()
        return self._directory

    @property
    def mentoring(self) -> MentoringManager:
        """Get mentoring manager."""
        if self._mentoring is None:
            self._mentoring = MentoringManager()
        return self._mentoring

    @property
    def grant_budget(self) -> GrantBudgetManager:
        """Get grant budget manager."""
        if self._grant_budget is None:
            self._grant_budget = GrantBudgetManager()
        return self._grant_budget

    @property
    def peer_review(self) -> PeerReviewManager:
        """Get peer review manager."""
        if self._peer_review is None:
            self._peer_review = PeerReviewManager()
        return self._peer_review

    @property
    def comm_hub(self) -> CommHubManager:
        """Get communication hub manager."""
        if self._comm_hub is None:
            self._comm_hub = CommHubManager()
        return self._comm_hub

    @property
    def teaching_load(self) -> TeachingLoadManager:
        """Get teaching load manager."""
        if self._teaching_load is None:
            self._teaching_load = TeachingLoadManager()
        return self._teaching_load

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
