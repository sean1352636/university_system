"""
Gym/Fitness Center Module

Provides comprehensive gym management including memberships,
class bookings, equipment tracking, and personal training with
email and finance integration.
"""

from education_system.systems.university.domain.operations.commerce.gym.services.gym_core import (
    MembershipManager,
    ClassManager,
    PTSessionManager,
    EquipmentManager,
    TransactionManager,
    ReportManager,
    init_gym_db,
    MEMBERSHIP_TYPES,
    CLASS_TYPES
)

__all__ = [
    'GymGUI',
    'launch_gym_gui',
    'MembershipManager',
    'ClassManager',
    'PTSessionManager',
    'EquipmentManager',
    'TransactionManager',
    'ReportManager',
    'init_gym_db',
    'MEMBERSHIP_TYPES',
    'CLASS_TYPES'
]

# The GUI classes live in the interfaces layer, which imports back into this
# domain package, so an eager re-export here is a circular import. PEP 562
# lazy lookup keeps these names on the package's public surface without the
# cycle: the interfaces module is only imported on first attribute access.
_LAZY_GUI_EXPORTS = {
    "GymGUI": "education_system.systems.university.interfaces.gui.operations.commerce.gym.gym_gui",
    "launch_gym_gui": "education_system.systems.university.interfaces.gui.operations.commerce.gym.gym_gui",
}


def __getattr__(name: str):
    module_path = _LAZY_GUI_EXPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(module_path), name)
    globals()[name] = value  # cache so subsequent access skips __getattr__
    return value
