"""Barber Shop GUI - Tab creation mixins."""

from education_system.university_system.modules.domain.commerce.barber.gui.tabs.appointments_tab import AppointmentsTabMixin
from education_system.university_system.modules.domain.commerce.barber.gui.tabs.services_tab import ServicesTabMixin
from education_system.university_system.modules.domain.commerce.barber.gui.tabs.staff_tab import StaffTabMixin
from education_system.university_system.modules.domain.commerce.barber.gui.tabs.customers_tab import CustomersTabMixin
from education_system.university_system.modules.domain.commerce.barber.gui.tabs.finance_tab import FinanceTabMixin
from education_system.university_system.modules.domain.commerce.barber.gui.tabs.analytics_tab import AnalyticsTabMixin
from education_system.university_system.modules.domain.commerce.barber.gui.tabs.reports_tab import ReportsTabMixin
from education_system.university_system.modules.domain.commerce.barber.gui.tabs.refunds_tab import RefundsTabMixin

__all__ = [
    'AppointmentsTabMixin', 'ServicesTabMixin', 'StaffTabMixin',
    'CustomersTabMixin', 'FinanceTabMixin', 'AnalyticsTabMixin',
    'ReportsTabMixin', 'RefundsTabMixin',
]
