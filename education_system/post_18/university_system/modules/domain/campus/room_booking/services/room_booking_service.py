"""Generic room-booking service.

Lifts the time-clash detection logic from
``modules/domain/campus/study_rooms/services/study_room_service.py`` and
generalises it to the shared ``room_bookings`` table defined in
``infrastructure/database/schemas/facilities_housing_schemas.py``.

Schema columns used (from the existing schema — no DDL added here):

    rooms(room_id, building_id, room_number, room_name, room_type,
          capacity, equipment, status, ...)
    room_bookings(booking_id, room_id, booked_by, booking_type, purpose,
                  start_datetime, end_datetime, equipment_needed,
                  booking_status, ...)

Datetimes are stored as ISO ``YYYY-MM-DD HH:MM`` strings (lex-comparable).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DT_FMT = "%Y-%m-%d %H:%M"


class RoomBookingError(Exception):
    """Raised on validation or clash failures inside :class:`RoomBookingService`."""


def _parse_dt(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoomBookingError(f"{label} is required")
    raw = value.strip()
    # Accept either 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM:SS' — normalise.
    for fmt in (_DT_FMT, "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime(_DT_FMT)
        except ValueError:
            continue
    raise RoomBookingError(f"Invalid {label}: expected 'YYYY-MM-DD HH:MM', got {value!r}")


def _csv_to_set(csv: str) -> set[str]:
    return {item.strip().lower() for item in (csv or "").split(",") if item.strip()}


class RoomBookingService:
    """Clash-aware bookings on the shared ``room_bookings`` table.

    Parameters
    ----------
    db_path : str | None
        SQLite path. If ``None``, falls back to the project's shared connection
        helper (``infrastructure.database.db.get_connection``).
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        if self._db_path:
            conn = sqlite3.connect(self._db_path)
        else:
            from education_system.post_18.university_system.infrastructure.database.db import (
                get_connection,
            )
            conn = get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    def _rooms_has_equipment_column(self, conn: sqlite3.Connection) -> bool:
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(rooms)").fetchall()}
        except sqlite3.Error:
            return False
        return "equipment" in cols

    # ------------------------------------------------------------------
    # Clash detection
    # ------------------------------------------------------------------
    def _check_clash(
        self,
        room_id: int,
        start: str,
        end: str,
        ignore_booking_id: Optional[int] = None,
    ) -> Optional[int]:
        """Return the ID of a clashing booking, or ``None`` if the slot is free.

        Interval-overlap test: ``start1 < end2 AND end1 > start2``.
        Cancelled bookings are excluded.
        """
        sql = (
            "SELECT booking_id FROM room_bookings "
            "WHERE room_id = ? "
            "  AND booking_status != 'cancelled' "
            "  AND start_datetime < ? "
            "  AND end_datetime > ?"
        )
        params: list[Any] = [room_id, end, start]
        if ignore_booking_id is not None:
            sql += " AND booking_id != ?"
            params.append(ignore_booking_id)
        sql += " LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["booking_id"] if row else None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    def create_booking(
        self,
        room_id: int,
        start_datetime: str,
        end_datetime: str,
        booked_by: str,
        purpose: str,
        equipment_needed: str = "",
        booking_type: str = "general",
    ) -> int:
        if not isinstance(room_id, int) or room_id <= 0:
            raise RoomBookingError("room_id must be a positive integer")
        if not booked_by or not str(booked_by).strip():
            raise RoomBookingError("booked_by is required")
        start = _parse_dt(start_datetime, "start_datetime")
        end = _parse_dt(end_datetime, "end_datetime")
        if start >= end:
            raise RoomBookingError("end_datetime must be after start_datetime")

        clash = self._check_clash(room_id, start, end)
        if clash is not None:
            raise RoomBookingError(f"clash with booking #{clash}")

        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO room_bookings "
                "(room_id, booked_by, booking_type, purpose, "
                " start_datetime, end_datetime, equipment_needed, booking_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')",
                (room_id, str(booked_by).strip(), booking_type, purpose,
                 start, end, equipment_needed or ""),
            )
            conn.commit()
            return int(cur.lastrowid)

    def reschedule_booking(self, booking_id: int, new_start: str, new_end: str) -> None:
        if not isinstance(booking_id, int) or booking_id <= 0:
            raise RoomBookingError("booking_id must be a positive integer")
        start = _parse_dt(new_start, "new_start")
        end = _parse_dt(new_end, "new_end")
        if start >= end:
            raise RoomBookingError("new_end must be after new_start")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT room_id, booking_status FROM room_bookings WHERE booking_id = ?",
                (booking_id,),
            ).fetchone()
        if not row:
            raise RoomBookingError(f"booking #{booking_id} not found")
        if row["booking_status"] == "cancelled":
            raise RoomBookingError(f"booking #{booking_id} is cancelled")

        clash = self._check_clash(row["room_id"], start, end, ignore_booking_id=booking_id)
        if clash is not None:
            raise RoomBookingError(f"clash with booking #{clash}")

        with self._connect() as conn:
            conn.execute(
                "UPDATE room_bookings SET start_datetime = ?, end_datetime = ? "
                "WHERE booking_id = ?",
                (start, end, booking_id),
            )
            conn.commit()

    def cancel_booking(self, booking_id: int) -> bool:
        if not isinstance(booking_id, int) or booking_id <= 0:
            raise RoomBookingError("booking_id must be a positive integer")
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE room_bookings SET booking_status = 'cancelled' "
                "WHERE booking_id = ? AND booking_status != 'cancelled'",
                (booking_id,),
            )
            conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def list_bookings(
        self,
        room_id: Optional[int] = None,
        on_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM room_bookings WHERE 1=1"
        params: list[Any] = []
        if room_id is not None:
            sql += " AND room_id = ?"
            params.append(room_id)
        if on_date:
            try:
                datetime.strptime(on_date, "%Y-%m-%d")
            except ValueError as e:
                raise RoomBookingError("on_date must be YYYY-MM-DD") from e
            # Bookings overlapping that day.
            day_start = f"{on_date} 00:00"
            day_end = f"{on_date} 23:59"
            sql += " AND start_datetime <= ? AND end_datetime >= ?"
            params.extend([day_end, day_start])
        sql += " ORDER BY start_datetime"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def find_available_rooms(
        self,
        start_datetime: str,
        end_datetime: str,
        capacity_min: Optional[int] = None,
        equipment_csv: str = "",
    ) -> list[dict[str, Any]]:
        start = _parse_dt(start_datetime, "start_datetime")
        end = _parse_dt(end_datetime, "end_datetime")
        if start >= end:
            raise RoomBookingError("end_datetime must be after start_datetime")

        sql = "SELECT * FROM rooms WHERE 1=1"
        params: list[Any] = []
        # Tolerate absence of a status column on minimal test schemas.
        with self._connect() as conn:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(rooms)").fetchall()}
            if "status" in cols:
                sql += " AND status = 'available'"
            if capacity_min is not None and "capacity" in cols:
                sql += " AND capacity >= ?"
                params.append(int(capacity_min))
            rooms = [dict(r) for r in conn.execute(sql, params).fetchall()]

            wanted = _csv_to_set(equipment_csv)
            has_equipment = "equipment" in cols
            available: list[dict[str, Any]] = []
            for r in rooms:
                # Equipment match (superset).
                if wanted:
                    if not has_equipment:
                        # Schema doesn't expose equipment — fall back to capacity-only filter.
                        pass
                    else:
                        provided = _csv_to_set(r.get("equipment") or "")
                        if not wanted.issubset(provided):
                            continue
                # Clash check.
                clash = conn.execute(
                    "SELECT 1 FROM room_bookings "
                    "WHERE room_id = ? AND booking_status != 'cancelled' "
                    "  AND start_datetime < ? AND end_datetime > ? LIMIT 1",
                    (r["room_id"], end, start),
                ).fetchone()
                if clash is None:
                    available.append(r)
        return available
