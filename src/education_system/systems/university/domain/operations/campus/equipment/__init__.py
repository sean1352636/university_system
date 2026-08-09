"""
Equipment Rental System Module

Provides comprehensive equipment rental management including
inventory, reservations, checkouts, returns, and transaction management
with email and finance integration.
"""

from education_system.systems.university.domain.operations.campus.equipment.services.equipment_core import (
    EquipmentManager,
    RentalManager,
    TransactionManager,
    ReportManager,
    init_equipment_db,
    EQUIPMENT_CATEGORIES,
    RENTAL_STATUSES,
    EQUIPMENT_CONDITIONS
)

__all__ = [
    'EquipmentRentalGUI',
    'launch_equipment_gui',
    'EquipmentManager',
    'RentalManager',
    'TransactionManager',
    'ReportManager',
    'init_equipment_db',
    'EQUIPMENT_CATEGORIES',
    'RENTAL_STATUSES',
    'EQUIPMENT_CONDITIONS'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "EquipmentRentalGUI": "education_system.systems.university.interfaces.gui.operations.campus.equipment.equipment_gui",
    "launch_equipment_gui": "education_system.systems.university.interfaces.gui.operations.campus.equipment.equipment_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
