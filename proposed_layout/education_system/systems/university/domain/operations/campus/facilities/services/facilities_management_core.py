"""
Facilities & Space Management Core Service

Building management, room bookings, maintenance tracking,
work orders, asset inventory, and space utilization analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
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

    @staticmethod
    def list_buildings(active_only: bool = True) -> List[Dict[str, Any]]:
        """Return all buildings (optionally only active ones)."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM buildings"
                if active_only:
                    query += " WHERE COALESCE(is_active, 1) = 1"
                query += " ORDER BY building_code"
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing buildings: {e}")

    @staticmethod
    def get_building(building_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single building by id, or None."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM buildings WHERE building_id = ?",
                    (building_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            raise Exception(f"Error getting building: {e}")


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

    @staticmethod
    def list_rooms(building_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List rooms, optionally filtered to a single building."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                if building_id:
                    cursor.execute(
                        "SELECT * FROM rooms WHERE building_id = ? "
                        "AND COALESCE(is_active, 1) = 1 "
                        "ORDER BY COALESCE(floor_number, 0), room_number",
                        (building_id,))
                else:
                    cursor.execute(
                        "SELECT * FROM rooms WHERE COALESCE(is_active, 1) = 1 "
                        "ORDER BY COALESCE(floor_number, 0), room_number")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing rooms: {e}")


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

    @staticmethod
    def list_bookings(room_id: Optional[int] = None,
                      status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List bookings with room/building context, newest first."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = (
                    "SELECT bk.*, r.room_number, r.building "
                    "FROM room_bookings bk "
                    "LEFT JOIN rooms r ON r.id = bk.room_id "
                    "WHERE 1=1")
                params: List[Any] = []
                if room_id:
                    query += " AND bk.room_id = ?"
                    params.append(room_id)
                if status:
                    query += " AND bk.booking_status = ?"
                    params.append(status)
                query += " ORDER BY bk.start_datetime DESC"
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing bookings: {e}")

    @staticmethod
    def cancel_booking(booking_id: int) -> bool:
        """Mark a booking as cancelled. Returns True if a row changed."""
        try:
            with transaction() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE room_bookings SET booking_status = 'cancelled' "
                    "WHERE booking_id = ?", (booking_id,))
                return cur.rowcount > 0
        except Exception as e:
            raise Exception(f"Error cancelling booking: {e}")


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

    @staticmethod
    def list_requests(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List maintenance requests, optionally filtered by status."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM maintenance_requests"
                params: List[Any] = []
                if status:
                    query += " WHERE status = ?"
                    params.append(status)
                query += " ORDER BY reported_date DESC"
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing maintenance requests: {e}")

    @staticmethod
    def update_status(request_id: int, status: str,
                      assigned_to: Optional[str] = None) -> bool:
        """Update a request's status (and optionally assignee)."""
        try:
            with transaction() as conn:
                cur = conn.cursor()
                if assigned_to is not None:
                    cur.execute(
                        "UPDATE maintenance_requests "
                        "SET status = ?, assigned_to = ?, assigned_date = ? "
                        "WHERE request_id = ?",
                        (status, assigned_to, datetime.now().isoformat(),
                         request_id))
                else:
                    cur.execute(
                        "UPDATE maintenance_requests SET status = ? "
                        "WHERE request_id = ?", (status, request_id))
                return cur.rowcount > 0
        except Exception as e:
            raise Exception(f"Error updating maintenance request: {e}")


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

    @staticmethod
    def list_work_orders(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List work orders, optionally filtered by status."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM work_orders"
                params: List[Any] = []
                if status:
                    query += " WHERE status = ?"
                    params.append(status)
                query += " ORDER BY work_order_id DESC"
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing work orders: {e}")

    @staticmethod
    def update_status(work_order_id: int, status: str) -> bool:
        """Update a work order's status; stamps completion_date when completed."""
        try:
            with transaction() as conn:
                cur = conn.cursor()
                if status == 'completed':
                    cur.execute(
                        "UPDATE work_orders SET status = ?, completion_date = ? "
                        "WHERE work_order_id = ?",
                        (status, datetime.now().isoformat(), work_order_id))
                else:
                    cur.execute(
                        "UPDATE work_orders SET status = ? "
                        "WHERE work_order_id = ?", (status, work_order_id))
                return cur.rowcount > 0
        except Exception as e:
            raise Exception(f"Error updating work order: {e}")


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

    @staticmethod
    def list_assets(building_id: Optional[int] = None,
                    status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List facility assets, optionally filtered by building and/or status."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM facility_assets WHERE 1=1"
                params: List[Any] = []
                if building_id:
                    query += " AND building_id = ?"
                    params.append(building_id)
                if status:
                    query += " AND status = ?"
                    params.append(status)
                query += " ORDER BY asset_name"
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing assets: {e}")

    @staticmethod
    def update_asset(asset_id: int, *, status: Optional[str] = None,
                     condition: Optional[str] = None) -> bool:
        """Update an asset's status and/or condition."""
        try:
            fields: List[str] = []
            params: List[Any] = []
            if status is not None:
                fields.append("status = ?")
                params.append(status)
            if condition is not None:
                fields.append("condition = ?")
                params.append(condition)
            if not fields:
                return False
            params.append(asset_id)
            with transaction() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE facility_assets SET {', '.join(fields)} "
                    "WHERE asset_id = ?", params)
                return cur.rowcount > 0
        except Exception as e:
            raise Exception(f"Error updating asset: {e}")


class EnergyUsageManager:
    """Records and reports building energy usage (``energy_usage`` table)."""

    @staticmethod
    def record_reading(building_id: int, usage_type: str, reading_date: str,
                       meter_reading: float, consumption: Optional[float] = None,
                       cost: Optional[float] = None) -> int:
        """Record a meter reading for a building."""
        try:
            with transaction() as conn:
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO energy_usage (
                        building_id, usage_type, reading_date, meter_reading,
                        consumption, cost
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (building_id, usage_type, reading_date, meter_reading,
                      consumption, cost))
                return cur.lastrowid
        except Exception as e:
            raise Exception(f"Error recording energy usage: {e}")

    @staticmethod
    def list_recent(limit: int = 20) -> List[Dict[str, Any]]:
        """Most recent energy readings with building code."""
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute('''
                    SELECT u.*, b.building_code
                    FROM energy_usage u
                    LEFT JOIN buildings b ON b.building_id = u.building_id
                    ORDER BY u.reading_date DESC LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing energy usage: {e}")

    @staticmethod
    def summary_by_building() -> List[Dict[str, Any]]:
        """Total consumption and cost per building."""
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute('''
                    SELECT b.building_code, b.building_name,
                           SUM(u.consumption) AS total_consumption,
                           SUM(u.cost) AS total_cost,
                           COUNT(*) AS readings
                    FROM energy_usage u
                    LEFT JOIN buildings b ON b.building_id = u.building_id
                    GROUP BY u.building_id
                    ORDER BY total_cost DESC
                ''')
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            raise Exception(f"Error summarising energy usage: {e}")


class AccessCardManager:
    """Manages building access / key cards (``access_cards`` table).

    Mirrors the AccessCards tab in ``building_management_app.py``:
    ``buildings_access`` is a comma-separated list of building codes.
    """

    @staticmethod
    def issue_card(card_number: str, user_id: str = "", user_name: str = "",
                   card_type: str = "staff", access_level: str = "standard",
                   buildings_access: str = "", issue_date: Optional[str] = None,
                   expiry_date: Optional[str] = None, issued_by: str = "",
                   notes: str = "") -> int:
        """Issue a new access card. Returns the new card_id."""
        try:
            issue_date = issue_date or datetime.now().strftime("%Y-%m-%d")
            with transaction() as conn:
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO access_cards (
                        card_number, user_id, user_name, card_type,
                        access_level, buildings_access, issue_date,
                        expiry_date, status, issued_by, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                ''', (card_number, user_id, user_name, card_type, access_level,
                      buildings_access, issue_date, expiry_date, issued_by,
                      notes))
                return cur.lastrowid
        except Exception as e:
            raise Exception(f"Error issuing access card: {e}")

    @staticmethod
    def list_cards(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List access cards, optionally filtered by status."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM access_cards"
                params: List[Any] = []
                if status:
                    query += " WHERE status = ?"
                    params.append(status)
                query += " ORDER BY status, expiry_date"
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing access cards: {e}")

    @staticmethod
    def update_status(card_id: int, status: str) -> bool:
        """Update a card's status (active/suspended/lost/expired/revoked)."""
        try:
            with transaction() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE access_cards SET status = ? WHERE card_id = ?",
                    (status, card_id))
                return cur.rowcount > 0
        except Exception as e:
            raise Exception(f"Error updating access card: {e}")


class InspectionManager:
    """Manages facility inspections (``housing_inspections`` table).

    ``inspection_id`` is TEXT (``INS-YYYYMMDDHHMMSS-<n>``). ``room_id`` is a
    ``housing_rooms.room_id`` (TEXT) — that is what the table's foreign key
    requires. Use :meth:`list_inspectable_rooms` to find valid ids. (The
    Facilities GUI's Inspections tab stored a ``rooms.id`` here instead, which
    never satisfies the FK — this CLI references the correct room instead.)
    """

    @staticmethod
    def _gen_inspection_id() -> str:
        import random
        return "INS-{}-{:04d}".format(
            datetime.now().strftime("%Y%m%d%H%M%S"),
            random.randint(0, 9999))

    @staticmethod
    def list_inspectable_rooms(limit: int = 50) -> List[Dict[str, Any]]:
        """Rooms that satisfy the inspection FK (``housing_rooms``)."""
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute('''
                    SELECT room_id, building_id, room_number, floor_number,
                           room_type, status
                    FROM housing_rooms
                    ORDER BY building_id, floor_number, room_number
                    LIMIT ?
                ''', (limit,))
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing inspectable rooms: {e}")

    @staticmethod
    def schedule_inspection(room_id: str, inspector: str, inspection_type: str,
                            inspection_date: Optional[str] = None,
                            status: str = "scheduled", findings: str = "",
                            action_required: str = "",
                            follow_up_date: Optional[str] = None) -> str:
        """Record/schedule an inspection. Returns the generated inspection_id."""
        try:
            inspection_date = inspection_date or datetime.now().strftime("%Y-%m-%d")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            inspection_id = InspectionManager._gen_inspection_id()
            with transaction() as conn:
                cur = conn.cursor()
                cur.execute('''
                    INSERT INTO housing_inspections (
                        inspection_id, room_id, inspector, inspection_date,
                        inspection_type, status, findings, action_required,
                        follow_up_date, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (inspection_id, str(room_id), inspector, inspection_date,
                      inspection_type, status, findings, action_required,
                      follow_up_date, now, now))
                return inspection_id
        except Exception as e:
            raise Exception(f"Error scheduling inspection: {e}")

    @staticmethod
    def list_inspections(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List inspections (newest first) with a friendly room label."""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = (
                    "SELECT i.*, "
                    "COALESCE('F' || COALESCE(hr.floor_number, 0) || '-' || "
                    "hr.room_number, i.room_id) AS room_label "
                    "FROM housing_inspections i "
                    "LEFT JOIN housing_rooms hr ON hr.room_id = i.room_id "
                    "WHERE 1=1")
                params: List[Any] = []
                if status:
                    query += " AND i.status = ?"
                    params.append(status)
                query += " ORDER BY i.inspection_date DESC LIMIT 500"
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error listing inspections: {e}")

    @staticmethod
    def update_status(inspection_id: str, status: str,
                      findings: Optional[str] = None,
                      action_required: Optional[str] = None,
                      follow_up_date: Optional[str] = None) -> bool:
        """Update an inspection's status (and optionally findings/follow-up)."""
        try:
            fields = ["status = ?"]
            params: List[Any] = [status]
            if findings is not None:
                fields.append("findings = ?")
                params.append(findings)
            if action_required is not None:
                fields.append("action_required = ?")
                params.append(action_required)
            if follow_up_date is not None:
                fields.append("follow_up_date = ?")
                params.append(follow_up_date)
            fields.append("updated_at = ?")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            params.append(inspection_id)
            with transaction() as conn:
                cur = conn.cursor()
                cur.execute(
                    f"UPDATE housing_inspections SET {', '.join(fields)} "
                    "WHERE inspection_id = ?", params)
                return cur.rowcount > 0
        except Exception as e:
            raise Exception(f"Error updating inspection: {e}")


def display_facilities_management_menu(auth):
    """Display the Facilities & Space Management CLI menu.

    Delegates to the interactive CLI in ``facilities.cli.facilities_cli``,
    which is wired to the managers above (same ``student_records.db`` the
    Facilities GUI uses). Imported lazily to avoid an import cycle.
    """
    from education_system.systems.university.interfaces.cli.operations.campus.facilities.facilities_cli import (
        run_facilities_menu,
    )
    run_facilities_menu(auth)


def launch_facilities_management_gui(root, auth):
    """Launch the unified Facilities GUI.

    Single window with tabs for Buildings, Rooms, Bookings, Utilities,
    Cleaning, Maintenance, Work Orders, Occupancy, Access Cards, Inspections,
    Assets and Reports. Replaces three previously-separate GUIs (Facilities,
    Building Management, Room Booking) with one consolidated app.
    """
    try:
        from education_system.systems.university.interfaces.gui.operations.campus.facilities.building_management_app import (
            launch_in_window,
        )
        return launch_in_window(root, auth=auth)
    except Exception as exc:
        from education_system.systems.university.services.feature_gui_factory import create_gui_launcher
        placeholder = create_gui_launcher(
            title="Facilities Management",
            description=f"Failed to open the unified Facilities app: {exc}",
            cli_instruction="Check logs and re-launch from the main menu."
        )
        placeholder(root, auth)



# The richer booking service lives in the room_booking package; re-export it
# here so callers can import everything from facilities.services.
try:
    from education_system.systems.university.domain.operations.campus.room_booking.services.room_booking_service import (  # noqa: F401
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
    'EnergyUsageManager', 'AccessCardManager', 'InspectionManager',
    'RoomBookingService', 'RoomBookingError',
    'display_facilities_management_menu',
    'launch_facilities_management_gui',
]
