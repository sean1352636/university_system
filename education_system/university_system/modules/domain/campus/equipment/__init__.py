"""
Equipment Rental System Module

Provides comprehensive equipment rental management including
inventory, reservations, checkouts, returns, and transaction management
with email and finance integration.
"""

from education_system.university_system.modules.domain.campus.equipment.gui.equipment_gui import (
    EquipmentRentalGUI,
    launch_equipment_gui
)
from education_system.university_system.modules.domain.campus.equipment.services.equipment_core import (
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
