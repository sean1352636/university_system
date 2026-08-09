from education_system.systems.university.domain.academics.services.parent_portal.accounts import AccountsMixin
from education_system.systems.university.domain.academics.services.parent_portal.academics import AcademicsMixin
from education_system.systems.university.domain.academics.services.parent_portal.communication import CommunicationMixin
from education_system.systems.university.domain.academics.services.parent_portal.finance import FinanceMixin
from education_system.systems.university.domain.academics.services.parent_portal.health_and_behavior import HealthAndBehaviorMixin
from education_system.systems.university.domain.academics.services.parent_portal.services import ServicesMixin
from education_system.systems.university.domain.academics.services.parent_portal.academic_support import AcademicSupportMixin
from education_system.systems.university.domain.academics.services.parent_portal.security_and_documents import SecurityAndDocumentsMixin
from education_system.systems.university.domain.academics.services.parent_portal.analytics import AnalyticsMixin
from education_system.systems.university.domain.academics.services.parent_portal.notifications import NotificationsMixin
from education_system.systems.university.domain.academics.services.parent_portal.quick_actions import QuickActionsMixin
from education_system.systems.university.domain.academics.services.parent_portal.database import initialize_parent_portal
from education_system.systems.university.domain.academics.services.parent_portal.menu import display_parent_portal_menu as _display_menu


class ParentPortal(
    AccountsMixin,
    AcademicsMixin,
    CommunicationMixin,
    FinanceMixin,
    HealthAndBehaviorMixin,
    ServicesMixin,
    AcademicSupportMixin,
    SecurityAndDocumentsMixin,
    AnalyticsMixin,
    NotificationsMixin,
    QuickActionsMixin,
):
    def __init__(self, auth):
        self.auth = auth

    @staticmethod
    def initialize_parent_portal():
        return initialize_parent_portal()

    @staticmethod
    def integrate_parent_portal_with_main():
        return initialize_parent_portal()

    @staticmethod
    def display_parent_portal_menu(auth):
        return _display_menu(auth)
