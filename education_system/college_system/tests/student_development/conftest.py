"""Fixtures for student development module tests."""

import pytest

from education_system.college_system.modules.domain.enrichment.services.enrichment_service import EnrichmentService
from education_system.college_system.modules.domain.peer_mentoring.services.peer_mentoring_service import PeerMentoringService
from education_system.college_system.modules.domain.skills_passport.services.skills_passport_service import SkillsPassportService
from education_system.college_system.modules.domain.portfolio.services.portfolio_service import PortfolioService
from education_system.college_system.modules.domain.work_journal.services.work_journal_service import WorkJournalService
from education_system.college_system.modules.domain.study_planner.services.study_planner_service import StudyPlannerService
from education_system.college_system.modules.domain.progress_dashboard.services.progress_dashboard_service import ProgressDashboardService
from education_system.college_system.modules.domain.intervention_tracking.services.intervention_tracking_service import InterventionService
from education_system.college_system.modules.domain.destinations.services.destination_service import DestinationService
from education_system.college_system.modules.domain.surveys.services.surveys_service import SurveyService
from education_system.college_system.modules.domain.absence_requests.services.absence_requests_service import AbsenceRequestService
from education_system.college_system.modules.domain.alumni.services.alumni_service import AlumniService


@pytest.fixture
def enrichment_service(db_path):
    return EnrichmentService(db_path)


@pytest.fixture
def peer_mentoring_service(db_path):
    return PeerMentoringService(db_path)


@pytest.fixture
def skills_passport_service(db_path):
    return SkillsPassportService(db_path)


@pytest.fixture
def portfolio_service(db_path):
    return PortfolioService(db_path)


@pytest.fixture
def work_journal_service(db_path):
    return WorkJournalService(db_path)


@pytest.fixture
def study_planner_service(db_path):
    return StudyPlannerService(db_path)


@pytest.fixture
def progress_dashboard_service(db_path):
    return ProgressDashboardService(db_path)


@pytest.fixture
def intervention_tracking_service(db_path):
    return InterventionService(db_path)


@pytest.fixture
def destination_service(db_path):
    return DestinationService(db_path)


@pytest.fixture
def surveys_service(db_path):
    return SurveyService(db_path)


@pytest.fixture
def absence_requests_service(db_path):
    return AbsenceRequestService(db_path)


@pytest.fixture
def alumni_service(db_path):
    return AlumniService(db_path)
