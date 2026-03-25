"""Fixtures for facilities module tests."""

import pytest

from education_system.college_system.modules.domain.resource_booking.services.resource_booking_service import ResourceBookingService
from education_system.college_system.modules.domain.visitors.services.visitors_service import VisitorService
from education_system.college_system.modules.domain.meal_ordering.services.meal_ordering_service import MealOrderingService
from education_system.college_system.modules.domain.print_credits.services.print_credits_service import PrintCreditService
from education_system.college_system.modules.domain.emergency.services.emergency_service import EmergencyService


@pytest.fixture
def resource_booking_service(db_path):
    return ResourceBookingService(db_path)


@pytest.fixture
def assets_service(db_path):
    from education_system.college_system.modules.domain.assets.services.assets_service import AssetService
    return AssetService(db_path)


@pytest.fixture
def visitors_service(db_path):
    return VisitorService(db_path)


@pytest.fixture
def meal_ordering_service(db_path):
    return MealOrderingService(db_path)


@pytest.fixture
def print_credits_service(db_path):
    return PrintCreditService(db_path)


@pytest.fixture
def emergency_service(db_path):
    return EmergencyService(db_path)


@pytest.fixture
def library_service(db_path):
    from education_system.college_system.modules.domain.library.services.library_service import LibraryService
    return LibraryService(db_path)


@pytest.fixture
def helpdesk_service(db_path):
    from education_system.college_system.modules.domain.helpdesk.services.helpdesk_service import HelpdeskService
    return HelpdeskService(db_path)


@pytest.fixture
def first_aid_service(db_path):
    from education_system.college_system.modules.domain.first_aid.services.first_aid_service import FirstAidService
    return FirstAidService(db_path)


@pytest.fixture
def transport_service(db_path):
    from education_system.college_system.modules.domain.transport.services.transport_service import TransportService
    return TransportService(db_path)
