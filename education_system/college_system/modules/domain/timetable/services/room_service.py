"""Room and resource management service."""

from education_system.college_system.core.exceptions import RoomError
from education_system.college_system.infrastructure.database.db import connect

import logging

logger = logging.getLogger(__name__)


class RoomService:
    """Service for managing rooms, resources, and availability."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def create_room(self, room_code: str, building: str | None = None,
                    floor: str | None = None, room_type: str = "classroom",
                    capacity: int = 30, has_projector: bool = False,
                    has_whiteboard: bool = True, has_computers: bool = False,
                    wheelchair_accessible: bool = False) -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO rooms
                   (room_code, building, floor, room_type, capacity,
                    has_projector, has_whiteboard, has_computers, wheelchair_accessible)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (room_code, building, floor, room_type, capacity,
                 1 if has_projector else 0, 1 if has_whiteboard else 0,
                 1 if has_computers else 0, 1 if wheelchair_accessible else 0),
            )
            conn.commit()
            logger.info("Room created: code=%s type=%s", room_code, room_type)
            row = conn.execute("SELECT * FROM rooms WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise RoomError(f"Failed to create room: {e}") from e
        finally:
            conn.close()

    def list_rooms(self, room_type: str | None = None,
                   status: str | None = None) -> list[dict]:
        conn = self._conn()
        try:
            sql = "SELECT * FROM rooms WHERE 1=1"
            params: list = []
            if room_type:
                sql += " AND room_type = ?"
                params.append(room_type)
            if status:
                sql += " AND status = ?"
                params.append(status)
            sql += " ORDER BY room_code"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_room(self, room_id: int) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_room(self, room_id: int, **updates) -> dict:
        allowed = {"room_code", "building", "floor", "room_type", "capacity",
                    "has_projector", "has_whiteboard", "has_computers",
                    "wheelchair_accessible", "status"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise RoomError("No valid fields to update.")
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM rooms WHERE id = ?", (room_id,)).fetchone()
            if not existing:
                raise RoomError("Room not found.")
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE rooms SET {set_parts}, updated_at = datetime('now') WHERE id = ?",
                (*updates.values(), room_id),
            )
            conn.commit()
            logger.info("Room updated: id=%d", room_id)
            row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
            return dict(row)
        except RoomError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RoomError(f"Failed to update room: {e}") from e
        finally:
            conn.close()

    def set_room_status(self, room_id: int, status: str) -> dict:
        valid = ("active", "maintenance", "decommissioned")
        if status not in valid:
            raise RoomError(f"Invalid status. Must be one of: {', '.join(valid)}")
        return self.update_room(room_id, status=status)

    def add_resource(self, room_id: int, resource_name: str,
                     resource_type: str = "equipment", quantity: int = 1,
                     condition: str = "good") -> dict:
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO room_resources
                   (room_id, resource_name, resource_type, quantity, condition)
                   VALUES (?, ?, ?, ?, ?)""",
                (room_id, resource_name, resource_type, quantity, condition),
            )
            conn.commit()
            logger.info("Resource added: room=%d name=%s", room_id, resource_name)
            row = conn.execute("SELECT * FROM room_resources WHERE id = last_insert_rowid()").fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise RoomError(f"Failed to add resource: {e}") from e
        finally:
            conn.close()

    def list_resources(self, room_id: int) -> list[dict]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM room_resources WHERE room_id = ? ORDER BY resource_name",
                (room_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_resource(self, resource_id: int, **updates) -> dict:
        allowed = {"resource_name", "resource_type", "quantity", "condition"}
        updates = {k: v for k, v in updates.items() if k in allowed and v is not None}
        if not updates:
            raise RoomError("No valid fields to update.")
        conn = self._conn()
        try:
            set_parts = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(f"UPDATE room_resources SET {set_parts} WHERE id = ?",  # nosec B608
                         (*updates.values(), resource_id))
            conn.commit()
            row = conn.execute("SELECT * FROM room_resources WHERE id = ?", (resource_id,)).fetchone()
            return dict(row)
        except Exception as e:
            conn.rollback()
            raise RoomError(f"Failed to update resource: {e}") from e
        finally:
            conn.close()

    def remove_resource(self, resource_id: int) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute("SELECT id FROM room_resources WHERE id = ?", (resource_id,)).fetchone()
            if not existing:
                raise RoomError("Resource not found.")
            conn.execute("DELETE FROM room_resources WHERE id = ?", (resource_id,))
            conn.commit()
            logger.info("Resource removed: id=%d", resource_id)
            return True
        except RoomError:
            conn.rollback()
            raise
        except Exception as e:
            conn.rollback()
            raise RoomError(f"Failed to remove resource: {e}") from e
        finally:
            conn.close()

    def find_available_rooms(self, day: str, start_time: str, end_time: str,
                             min_capacity: int | None = None,
                             room_type: str | None = None) -> list[dict]:
        """Find rooms not booked during the specified time slot."""
        conn = self._conn()
        try:
            sql = """SELECT r.* FROM rooms r
                     WHERE r.status = 'active'
                     AND r.id NOT IN (
                         SELECT DISTINCT rm.id FROM rooms rm
                         JOIN timetable_slots ts ON ts.room = rm.room_code
                         WHERE ts.day_of_week = ?
                         AND ts.start_time < ? AND ts.end_time > ?
                     )"""
            params: list = [day, end_time, start_time]
            if min_capacity:
                sql += " AND r.capacity >= ?"
                params.append(min_capacity)
            if room_type:
                sql += " AND r.room_type = ?"
                params.append(room_type)
            sql += " ORDER BY r.room_code"
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_room_utilization(self) -> list[dict]:
        """Get utilization stats for each room."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT r.id, r.room_code, r.building, r.capacity, r.room_type,
                          COUNT(ts.id) as slots_booked
                   FROM rooms r
                   LEFT JOIN timetable_slots ts ON ts.room = r.room_code
                   WHERE r.status = 'active'
                   GROUP BY r.id
                   ORDER BY slots_booked DESC"""
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                max_slots = 25  # 5 periods * 5 days
                d["utilization_pct"] = round((d["slots_booked"] / max_slots) * 100, 1) if max_slots > 0 else 0
                result.append(d)
            return result
        finally:
            conn.close()
