"""Tab mixin modules for ParkingManagementGUI."""
from .permits import PermitsMixin
from .vehicles import VehiclesMixin
from .violations import ViolationsMixin
from .lots import LotsMixin
from .payments import PaymentsMixin
from .dashboard import DashboardMixin

__all__ = [
    'PermitsMixin', 'VehiclesMixin', 'ViolationsMixin',
    'LotsMixin', 'PaymentsMixin', 'DashboardMixin',
]
