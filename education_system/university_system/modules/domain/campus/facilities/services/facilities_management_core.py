"""
Facilities & Space Management Core Service

Building management, room bookings, maintenance tracking,
work orders, asset inventory, and space utilization analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)


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
                     capacity: int = 0, floor_number: int = 1, building_name: str = "") -> int:
        """Register a new room in a building

        Args:
            building_id: ID of the building (for facilities management schema)
            room_number: Room number/identifier
            room_type: Type of room (Lecture, Lab, etc.)
            capacity: Room capacity
            floor_number: Floor number
            building_name: Building name (for module scheduling compatibility)
        """
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Check if we need to populate building name for module scheduling compatibility
                if not building_name and building_id:
                    try:
                        cursor.execute('SELECT building_name FROM buildings WHERE building_id = ?', (building_id,))
                        result = cursor.fetchone()
                        if result:
                            building_name = result[0]
                    except Exception:
                        pass

                # Insert with both building_id and building for cross-compatibility
                cursor.execute('''
                    INSERT INTO rooms (
                        building_id, building, room_number, room_type, capacity,
                        floor_number, status, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, 'available', 1)
                ''', (building_id, building_name, room_number, room_type, capacity, floor_number))
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
                # Support both status='available' and is_active=1 for compatibility
                query = "SELECT * FROM rooms WHERE (status = 'available' OR is_active = 1 OR status IS NULL)"
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


class CleaningScheduleManager:
    """Manages cleaning schedules per building/room.

    Owns ``bm_cleaning_schedules``. Idempotent table init runs on first call.
    Folded in from the (now-shimmed) building_management module so cleaning
    lives alongside the rest of facilities.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS bm_cleaning_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            room_id INTEGER,
            frequency TEXT NOT NULL,
            last_cleaned TEXT,
            next_due TEXT,
            assigned_to TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """

    @staticmethod
    def _ensure_table():
        with transaction() as conn:
            conn.execute(CleaningScheduleManager._SCHEMA)

    @staticmethod
    def schedule(building_id: int, frequency: str, *, room_id: Optional[int] = None,
                 last_cleaned: Optional[str] = None, next_due: Optional[str] = None,
                 assigned_to: str = "", status: str = "scheduled") -> int:
        CleaningScheduleManager._ensure_table()
        with transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO bm_cleaning_schedules
                   (building_id, room_id, frequency, last_cleaned, next_due,
                    assigned_to, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (building_id, room_id, frequency, last_cleaned, next_due,
                 assigned_to, status),
            )
            return cur.lastrowid

    @staticmethod
    def list_due(before: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return schedules whose next_due is on or before `before` (default: today)."""
        CleaningScheduleManager._ensure_table()
        if before is None:
            before = datetime.now().strftime('%Y-%m-%d')
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT * FROM bm_cleaning_schedules
                   WHERE next_due IS NOT NULL AND next_due <= ?
                     AND status != 'complete'
                   ORDER BY next_due""", (before,))
            return [dict(r) for r in cur.fetchall()]


class OccupancyManager:
    """Records and analyses building/room occupancy.

    Owns ``bm_occupancy_records``. ``record()`` derives `utilization_pct`
    from `occupant_count / capacity` so callers don't have to.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS bm_occupancy_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            building_id INTEGER NOT NULL,
            room_id INTEGER,
            timestamp TEXT NOT NULL,
            occupant_count INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            utilization_pct REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """

    @staticmethod
    def _ensure_table():
        with transaction() as conn:
            conn.execute(OccupancyManager._SCHEMA)

    @staticmethod
    def record(building_id: int, occupant_count: int, capacity: int, *,
               room_id: Optional[int] = None, timestamp: Optional[str] = None) -> int:
        if occupant_count < 0 or capacity < 0:
            raise ValueError("Counts must be non-negative.")
        OccupancyManager._ensure_table()
        ts = timestamp or datetime.now().isoformat(timespec='minutes')
        util = (occupant_count / capacity * 100.0) if capacity > 0 else 0.0
        with transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO bm_occupancy_records
                   (building_id, room_id, timestamp, occupant_count, capacity,
                    utilization_pct)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (building_id, room_id, ts, occupant_count, capacity, util),
            )
            return cur.lastrowid

    @staticmethod
    def utilisation_summary() -> List[Dict[str, Any]]:
        """Per-building avg + peak utilisation."""
        OccupancyManager._ensure_table()
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT b.building_code, b.building_name,
                          AVG(o.utilization_pct) AS avg_pct,
                          MAX(o.utilization_pct) AS peak_pct,
                          COUNT(*) AS sample_count
                   FROM bm_occupancy_records o
                   LEFT JOIN buildings b ON b.building_id = o.building_id
                   GROUP BY o.building_id
                   ORDER BY avg_pct DESC""")
            return [dict(r) for r in cur.fetchall()]


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
    print(f"   {get_text('facilities.title', default='FACILITIES & SPACE MANAGEMENT')}")
    print("="*50)
    print(f"1. {get_text('facilities.menu.building', default='Building Management')}")
    print(f"2. {get_text('facilities.menu.room_bookings', default='Room Bookings')}")
    print(f"3. {get_text('facilities.menu.maintenance', default='Maintenance Requests')}")
    print(f"4. {get_text('facilities.menu.work_orders', default='Work Orders')}")
    print(f"5. {get_text('facilities.menu.assets', default='Asset Inventory')}")
    print(f"6. {get_text('facilities.menu.energy', default='Energy Usage Tracking')}")
    print(f"7. {get_text('facilities.menu.space_reports', default='Space Utilization Reports')}")
    print(f"8. {get_text('facilities.menu.language', default='Language')}")
    print(f"9. {get_text('facilities.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('facilities.prompt.choice', default='Enter your choice (1-9)')}: ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🏢 {get_text('facilities.feature_available', default='Feature available via Facilities managers')}")
                print("Use: from education_system.university_system.modules.domain.campus.facilities.services import BuildingManager")
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
                print(get_text('facilities.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('facilities.invalid_choice', default='Invalid choice.'))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(get_text('facilities.error', default='Error: {error}').format(error=e))


def launch_facilities_management_gui(root, auth):
    """Launch the unified Facilities GUI.

    Single window with tabs for Buildings, Rooms, Bookings, Utilities,
    Cleaning, Maintenance, Work Orders, Occupancy, Access Cards, Inspections,
    Assets and Reports. Replaces three previously-separate GUIs (Facilities,
    Building Management, Room Booking) with one consolidated app.
    """
    try:
        from education_system.university_system.modules.domain.campus.facilities.gui.building_management_app import (
            launch_in_window,
        )
        return launch_in_window(root, auth=auth)
    except Exception as exc:
        from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher
        placeholder = create_gui_launcher(
            title="Facilities Management",
            description=f"Failed to open the unified Facilities app: {exc}",
            cli_instruction="Check logs and re-launch from the main menu."
        )
        placeholder(root, auth)



# The richer booking service lives in the room_booking package; re-export it
# here so callers can import everything from facilities.services.
try:
    from education_system.university_system.modules.domain.campus.room_booking.services.room_booking_service import (  # noqa: F401
        RoomBookingService,
        RoomBookingError,
    )
except Exception:  # pragma: no cover — keep import safe if module relocates
    RoomBookingService = None  # type: ignore[assignment]
    RoomBookingError = Exception  # type: ignore[assignment]


__all__ = [
    'BuildingManager', 'RoomManager', 'RoomBookingManager',
    'CleaningScheduleManager', 'OccupancyManager',
    'MaintenanceRequestManager', 'WorkOrderManager', 'AssetManager',
    'RoomBookingService', 'RoomBookingError',
    'display_facilities_management_menu',
    'launch_facilities_management_gui',
]
