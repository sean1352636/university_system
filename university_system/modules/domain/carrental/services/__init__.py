"""Car Rental Core Services Module"""

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
    'VehicleManager',
    'RentalManager',
    'TransactionManager',
    'ReportManager',
    'init_carrental_db',
    'VEHICLE_CATEGORIES',
    'RENTAL_STATUSES',
    'VEHICLE_STATUSES'
]
