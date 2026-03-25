"""
Facilities & Space Management Service Module
"""

from education_system.university_system.modules.domain.facilities.services.facilities_management_core import (
    BuildingManager, RoomManager, RoomBookingManager,
    MaintenanceRequestManager, WorkOrderManager, AssetManager
)

__all__ = [
    'BuildingManager', 'RoomManager', 'RoomBookingManager',
    'MaintenanceRequestManager', 'WorkOrderManager', 'AssetManager'
]
