"""Fixtures for finance module tests."""

import pytest

from education_system.college_system.modules.domain.finance.services.finance_service import FinanceService
from education_system.college_system.modules.domain.funding.services.funding_service import FundingService
from education_system.college_system.modules.domain.student_support.services.student_support_service import StudentSupportService
from education_system.college_system.modules.domain.departments.services.department_service import DepartmentService, GroupService


@pytest.fixture
def finance_service(db_path):
    return FinanceService(db_path)


@pytest.fixture
def funding_service(db_path):
    return FundingService(db_path)


@pytest.fixture
def bursary_service(db_path):
    from education_system.college_system.modules.domain.bursary.services.bursary_service import BursaryService
    return BursaryService(db_path)


@pytest.fixture
def student_support_service(db_path):
    return StudentSupportService(db_path)


@pytest.fixture
def department_service(db_path):
    return DepartmentService(db_path)


@pytest.fixture
def group_service(db_path):
    return GroupService(db_path)
