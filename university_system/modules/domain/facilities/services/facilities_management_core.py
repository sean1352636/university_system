"""
Facilities & Space Management Core Service

Building management, room bookings, maintenance tracking,
work orders, asset inventory, and space utilization analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection, transaction


class BuildingManager:
    """Manages buildings"""

    @staticmethod
    def register_building(building_name: str, building_code: str,
                         address: str = "", total_floors: int = 0,
                         building_type: str = "") -> int:
        """Register a new building in the system"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO buildings (
                        building_name, building_code, address, total_floors, building_type
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (building_name, building_code, address, total_floors, building_type))
                building_id = cursor.lastrowid
                return building_id
        except Exception as e:
            raise Exception(f"Error registering building: {e}")


class RoomManager:
    """Manages rooms"""

    @staticmethod
    def register_room(building_id: int, room_number: str, room_type: str,
                     capacity: int = 0, floor_number: int = 1) -> int:
        """Register a new room in a building"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO rooms (
                        building_id, room_number, room_type, capacity, floor_number
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (building_id, room_number, room_type, capacity, floor_number))
                room_id = cursor.lastrowid
                return room_id
        except Exception as e:
            raise Exception(f"Error registering room: {e}")

    @staticmethod
    def get_available_rooms(room_type: str = "", min_capacity: int = 0) -> List[Dict[str, Any]]:
        """Get list of available rooms with optional filters"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM rooms WHERE status = 'available'"
                params = []

                if room_type:
                    query += " AND room_type = ?"
                    params.append(room_type)
                if min_capacity > 0:
                    query += " AND capacity >= ?"
                    params.append(min_capacity)

                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error getting available rooms: {e}")


class RoomBookingManager:
    """Manages room bookings"""

    @staticmethod
    def book_room(room_id: int, booked_by: str, booking_type: str,
                 start_datetime: str, end_datetime: str,
                 purpose: str = "", expected_attendees: int = 0) -> int:
        """Book a room for a specific time period with conflict checking"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                # Check for conflicts
                cursor.execute('''
                    SELECT COUNT(*) as conflict_count
                    FROM room_bookings
                    WHERE room_id = ?
                      AND booking_status = 'confirmed'
                      AND ((start_datetime <= ? AND end_datetime > ?)
                        OR (start_datetime < ? AND end_datetime >= ?))
                ''', (room_id, start_datetime, start_datetime, end_datetime, end_datetime))

                if cursor.fetchone()['conflict_count'] > 0:
                    raise Exception("Room is already booked for this time slot")

                cursor.execute('''
                    INSERT INTO room_bookings (
                        room_id, booked_by, booking_type, purpose,
                        start_datetime, end_datetime, expected_attendees
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (room_id, booked_by, booking_type, purpose,
                      start_datetime, end_datetime, expected_attendees))
                booking_id = cursor.lastrowid
                return booking_id
        except Exception as e:
            raise Exception(f"Error booking room: {e}")


class MaintenanceRequestManager:
    """Manages maintenance requests"""

    @staticmethod
    def submit_request(request_type: str, priority: str, description: str,
                      reported_by: str, building_id: int = None,
                      room_id: int = None) -> int:
        """Submit a new maintenance request for a building or room"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                location_type = "room" if room_id else "building"

                cursor.execute('''
                    INSERT INTO maintenance_requests (
                        location_type, building_id, room_id, request_type,
                        priority, description, reported_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (location_type, building_id, room_id, request_type,
                      priority, description, reported_by))
                request_id = cursor.lastrowid
                return request_id
        except Exception as e:
            raise Exception(f"Error submitting maintenance request: {e}")


class WorkOrderManager:
    """Manages work orders"""

    @staticmethod
    def create_work_order(request_id: int, work_order_type: str,
                         description: str, assigned_technician: str = "") -> int:
        """Create a work order from a maintenance request"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO work_orders (
                        request_id, work_order_type, description, assigned_technician
                    ) VALUES (?, ?, ?, ?)
                ''', (request_id, work_order_type, description, assigned_technician))
                work_order_id = cursor.lastrowid
                return work_order_id
        except Exception as e:
            raise Exception(f"Error creating work order: {e}")


class AssetManager:
    """Manages facility assets"""

    @staticmethod
    def register_asset(asset_name: str, asset_type: str, asset_tag: str,
                      building_id: int = None, room_id: int = None,
                      purchase_cost: float = 0) -> int:
        """Register a new facility asset"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO facility_assets (
                        asset_name, asset_type, asset_tag, building_id,
                        room_id, purchase_cost
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (asset_name, asset_type, asset_tag, building_id,
                      room_id, purchase_cost))
                asset_id = cursor.lastrowid
                return asset_id
        except Exception as e:
            raise Exception(f"Error registering asset: {e}")


def display_facilities_management_menu(auth):
    """Display the Facilities & Space Management CLI menu"""
    print("\n" + "="*50)
    print("   FACILITIES & SPACE MANAGEMENT")
    print("="*50)
    print("1. Building Management")
    print("2. Room Bookings")
    print("3. Maintenance Requests")
    print("4. Work Orders")
    print("5. Asset Inventory")
    print("6. Energy Usage Tracking")
    print("7. Space Utilization Reports")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🏢 Feature available via Facilities managers")
                print("Use: from university_system.modules.domain.facilities.services import BuildingManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


def launch_facilities_management_gui(root, auth):
    """Launch the Facilities & Space Management GUI"""
    try:
        from university_system.modules.domain.facilities.gui.facilities_management_gui import (
            launch_facilities_management_gui as launch_gui
        )
        launch_gui(root, auth)
    except ImportError:
        # Fallback to placeholder if GUI module not found
        from university_system.modules.shared.feature_gui_factory import create_gui_launcher
        placeholder = create_gui_launcher(
            title="Facilities & Space Management",
            description="""Manage buildings, rooms, bookings, and maintenance.

Features:
• Building management
• Room bookings
• Maintenance requests
• Work orders
• Asset inventory
• Energy tracking""",
            cli_instruction="Use CLI: Facilities & Space Management"
        )
        placeholder(root, auth)



__all__ = [
    'BuildingManager', 'RoomManager', 'RoomBookingManager',
    'MaintenanceRequestManager', 'WorkOrderManager', 'AssetManager',
    'display_facilities_management_menu',
    'launch_facilities_management_gui',
]
