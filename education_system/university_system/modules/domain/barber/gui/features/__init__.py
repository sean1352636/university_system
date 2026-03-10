"""Barber Shop GUI - Feature mixins."""

from education_system.university_system.modules.domain.barber.gui.features.appointments import AppointmentsMixin
from education_system.university_system.modules.domain.barber.gui.features.services import ServicesMixin
from education_system.university_system.modules.domain.barber.gui.features.staff import StaffMixin
from education_system.university_system.modules.domain.barber.gui.features.customers import CustomersMixin
from education_system.university_system.modules.domain.barber.gui.features.finance import FinanceMixin
from education_system.university_system.modules.domain.barber.gui.features.analytics import AnalyticsMixin
from education_system.university_system.modules.domain.barber.gui.features.refunds import RefundsMixin

__all__ = [
    'AppointmentsMixin', 'ServicesMixin', 'StaffMixin',
    'CustomersMixin', 'FinanceMixin', 'AnalyticsMixin', 'RefundsMixin',
]
