"""Tab mixin modules for ParkingManagementGUI."""
from education_system.university_system.modules.domain.mobility.gui.parking_management.tabs.permits import PermitsMixin
from education_system.university_system.modules.domain.mobility.gui.parking_management.tabs.vehicles import VehiclesMixin
from education_system.university_system.modules.domain.mobility.gui.parking_management.tabs.violations import ViolationsMixin
from education_system.university_system.modules.domain.mobility.gui.parking_management.tabs.lots import LotsMixin
from education_system.university_system.modules.domain.mobility.gui.parking_management.tabs.payments import PaymentsMixin
from education_system.university_system.modules.domain.mobility.gui.parking_management.tabs.dashboard import DashboardMixin

__all__ = [
    'PermitsMixin', 'VehiclesMixin', 'ViolationsMixin',
    'LotsMixin', 'PaymentsMixin', 'DashboardMixin',
]
