"""
Barber Shop Module

Provides comprehensive barber shop management including
appointments, services, staff, and transaction management
with email and finance integration.
"""

from education_system.systems.university.domain.operations.commerce.barber.services.barber_core import (
    ServiceManager,
    StaffManager,
    AppointmentManager,
    TransactionManager,
    ReportManager,
    init_barber_db,
    SERVICE_TYPES,
    APPOINTMENT_STATUSES,
    TIME_SLOTS
)

__all__ = [
    'BarberGUI',
    'launch_barber_gui',
    'ServiceManager',
    'StaffManager',
    'AppointmentManager',
    'TransactionManager',
    'ReportManager',
    'init_barber_db',
    'SERVICE_TYPES',
    'APPOINTMENT_STATUSES',
    'TIME_SLOTS'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "BarberGUI": "education_system.systems.university.interfaces.gui.operations.commerce.barber.barber_gui",
    "launch_barber_gui": "education_system.systems.university.interfaces.gui.operations.commerce.barber.barber_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
