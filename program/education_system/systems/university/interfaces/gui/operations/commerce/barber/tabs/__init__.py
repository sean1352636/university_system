"""Barber Shop GUI - Tab creation mixins."""

from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.appointments_tab import AppointmentsTabMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.services_tab import ServicesTabMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.staff_tab import StaffTabMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.customers_tab import CustomersTabMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.finance_tab import FinanceTabMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.analytics_tab import AnalyticsTabMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.reports_tab import ReportsTabMixin
from education_system.systems.university.interfaces.gui.operations.commerce.barber.tabs.refunds_tab import RefundsTabMixin

__all__ = [
    'AppointmentsTabMixin', 'ServicesTabMixin', 'StaffTabMixin',
    'CustomersTabMixin', 'FinanceTabMixin', 'AnalyticsTabMixin',
    'ReportsTabMixin', 'RefundsTabMixin',
]
