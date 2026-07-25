"""Barber Shop GUI - Feature mixins."""

from education_system.systems.university.interfaces.gui.operations.commerce.barber.features.appointments import AppointmentsMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.features.services import ServicesMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.features.staff import StaffMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.features.customers import CustomersMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.features.finance import FinanceMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.features.analytics import AnalyticsMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.features.refunds import RefundsMixin

__all__ = [
    'AppointmentsMixin', 'ServicesMixin', 'StaffMixin',
    'CustomersMixin', 'FinanceMixin', 'AnalyticsMixin', 'RefundsMixin',
]
