"""
Nail Bar/Salon Module

Provides comprehensive nail bar/salon management including
treatments, appointments, technicians, and transaction management
with email and finance integration.
"""

from education_system.systems.university.domain.operations.commerce.nailbar.services.nailbar_core import (
    TreatmentManager,
    TechnicianManager,
    AppointmentManager,
    TransactionManager,
    ReportManager,
    init_nailbar_db,
    TREATMENT_CATEGORIES,
    APPOINTMENT_STATUSES,
    TIME_SLOTS
)

__all__ = [
    'NailBarGUI',
    'launch_nailbar_gui',
    'TreatmentManager',
    'TechnicianManager',
    'AppointmentManager',
    'TransactionManager',
    'ReportManager',
    'init_nailbar_db',
    'TREATMENT_CATEGORIES',
    'APPOINTMENT_STATUSES',
    'TIME_SLOTS'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "NailBarGUI": "education_system.systems.university.interfaces.gui.operations.commerce.nailbar.nailbar_gui",
    "launch_nailbar_gui": "education_system.systems.university.interfaces.gui.operations.commerce.nailbar.nailbar_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
