"""Fixtures for communication module tests."""

import pytest

from education_system.college_system.modules.domain.announcements.services.announcements_service import AnnouncementService
from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService
from education_system.college_system.modules.domain.sms_email.services.sms_email_service import SmsEmailService
from education_system.college_system.modules.domain.feedback.services.feedback_service import FeedbackService
from education_system.college_system.modules.domain.multi_language.services.multi_language_service import MultiLanguageService


@pytest.fixture
def announcements_service(db_path):
    return AnnouncementService(db_path)


@pytest.fixture
def notification_service(db_path):
    return NotificationService(db_path)


@pytest.fixture
def sms_email_service(db_path):
    return SmsEmailService(db_path)


@pytest.fixture
def feedback_service(db_path):
    return FeedbackService(db_path)


@pytest.fixture
def multi_language_service(db_path):
    return MultiLanguageService(db_path)


@pytest.fixture
def messaging_service(db_path):
    from education_system.college_system.modules.domain.messaging.services.messaging_service import MessagingService
    return MessagingService(db_path)


@pytest.fixture
def calendar_service(db_path):
    from education_system.college_system.modules.domain.calendar.services.calendar_service import CalendarService
    return CalendarService(db_path)
