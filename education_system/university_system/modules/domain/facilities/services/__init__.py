"""
Facilities & Space Management Service Module
"""

from .facilities_management_core import (
    BuildingManager, RoomManager, RoomBookingManager,
    MaintenanceRequestManager, WorkOrderManager, AssetManager
)

__all__ = [
    'BuildingManager', 'RoomManager', 'RoomBookingManager',
    'MaintenanceRequestManager', 'WorkOrderManager', 'AssetManager'
]
