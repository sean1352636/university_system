"""
Car Rental System Module

Provides comprehensive car rental management including
vehicles, reservations, returns, and transaction management
with email and finance integration.
"""

from university_system.modules.domain.carrental.gui.carrental_gui import (
    CarRentalGUI,
    launch_carrental_gui
)
from university_system.modules.domain.carrental.services.carrental_core import (
    VehicleManager,
    RentalManager,
    TransactionManager,
    ReportManager,
    init_carrental_db,
    VEHICLE_CATEGORIES,
    RENTAL_STATUSES,
    VEHICLE_STATUSES
)

__all__ = [
    'CarRentalGUI',
    'launch_carrental_gui',
    'VehicleManager',
    'RentalManager',
    'TransactionManager',
    'ReportManager',
    'init_carrental_db',
    'VEHICLE_CATEGORIES',
    'RENTAL_STATUSES',
    'VEHICLE_STATUSES'
]
