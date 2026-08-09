"""
Car Rental System Module

Provides comprehensive car rental management including
vehicles, reservations, returns, and transaction management
with email and finance integration.
"""

from education_system.systems.university.domain.operations.commerce.carrental.services.carrental_core import (
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

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "CarRentalGUI": "education_system.systems.university.interfaces.gui.operations.commerce.carrental.carrental_gui",
    "launch_carrental_gui": "education_system.systems.university.interfaces.gui.operations.commerce.carrental.carrental_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
