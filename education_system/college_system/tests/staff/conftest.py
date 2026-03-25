"""Fixtures for staff module tests."""

import pytest

from education_system.college_system.modules.domain.cpd.services.cpd_service import CPDService
from education_system.college_system.modules.domain.observations.services.observations_service import ObservationService
from education_system.college_system.modules.domain.appraisals.services.appraisals_service import AppraisalService
from education_system.college_system.modules.domain.staff_wellbeing.services.staff_wellbeing_service import StaffWellbeingService


@pytest.fixture
def staff_hr_service(db_path):
    from education_system.college_system.modules.domain.staff.services.staff_service import StaffService
    return StaffService(db_path)


@pytest.fixture
def cpd_service(db_path):
    return CPDService(db_path)


@pytest.fixture
def observations_service(db_path):
    return ObservationService(db_path)


@pytest.fixture
def appraisals_service(db_path):
    return AppraisalService(db_path)


@pytest.fixture
def staff_wellbeing_service(db_path):
    return StaffWellbeingService(db_path)


@pytest.fixture
def cover_service(db_path):
    from education_system.college_system.modules.domain.cover.services.cover_service import CoverService
    return CoverService(db_path)


@pytest.fixture
def compliance_service(db_path):
    from education_system.college_system.modules.domain.compliance.services.compliance_service import ComplianceService
    return ComplianceService(db_path)
