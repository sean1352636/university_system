"""Fixtures for pastoral module tests."""

import pytest


@pytest.fixture
def pastoral_service(db_path):
    from education_system.college_system.modules.domain.pastoral.services.pastoral_service import PastoralService
    return PastoralService(db_path)


@pytest.fixture
def behaviour_service(db_path):
    from education_system.college_system.modules.domain.behaviour.services.behaviour_service import BehaviourService
    return BehaviourService(db_path)


@pytest.fixture
def safeguarding_service(db_path):
    from education_system.college_system.modules.domain.safeguarding.services.safeguarding_service import SafeguardingService
    return SafeguardingService(db_path)


@pytest.fixture
def send_service(db_path):
    from education_system.college_system.modules.domain.send.services.send_service import SENDService
    return SENDService(db_path)


@pytest.fixture
def parent_portal_service(db_path):
    from education_system.college_system.modules.domain.parent_portal.services.parent_service import ParentService
    return ParentService(db_path)


@pytest.fixture
def parents_evening_service(db_path):
    from education_system.college_system.modules.domain.parents_evening.services.parents_evening_service import ParentsEveningService
    return ParentsEveningService(db_path)


@pytest.fixture
def early_warning_service(db_path):
    from education_system.college_system.modules.domain.early_warning.services.early_warning_service import EarlyWarningService
    return EarlyWarningService(db_path)
