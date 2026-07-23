"""Study room service — database operations and business logic for study-room bookings."""

import logging
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Table initialisation
# ---------------------------------------------------------------------------

def init_db():
    """Create study-room tables and seed sample rooms if the table is empty."""
    with get_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS study_rooms (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT NOT NULL,
            building TEXT DEFAULT '',
            capacity INTEGER DEFAULT 4,
            room_type TEXT DEFAULT 'study',
            equipment TEXT DEFAULT '',
            has_whiteboard INTEGER DEFAULT 0,
            has_projector INTEGER DEFAULT 0,
            has_power_outlets INTEGER DEFAULT 1,
            status TEXT DEFAULT 'available'
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS study_room_bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            booked_by TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            purpose TEXT DEFAULT 'study',
            group_size INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'confirmed',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (room_id) REFERENCES study_rooms(room_id)
        )""")
        # Seed sample rooms when empty
        count = conn.execute("SELECT COUNT(*) FROM study_rooms").fetchone()[0]
        if count == 0:
            rooms = [
                ("SR-101", "Library", 4, "study", "Quiet study room", 1, 0, 1),
                ("SR-102", "Library", 6, "group_study", "Group study room", 1, 1, 1),
                ("SR-103", "Library", 2, "study", "Individual study pod", 0, 0, 1),
                ("SR-201", "Student Center", 8, "group_study", "Large group room", 1, 1, 1),
                ("SR-202", "Student Center", 4, "study", "Quiet room", 1, 0, 1),
                ("SR-301", "Science Building", 6, "lab_study", "Study room with lab access", 1, 1, 1),
                ("SR-302", "Science Building", 4, "study", "Science study room", 1, 0, 1),
                ("SR-401", "Engineering Block", 8, "group_study", "Engineering project room", 1, 1, 1),
            ]
            for r in rooms:
                conn.execute(
                    "INSERT INTO study_rooms (room_number, building, capacity, room_type, equipment, has_whiteboard, has_projector, has_power_outlets) VALUES (?,?,?,?,?,?,?,?)",
                    r,
                )
            conn.commit()


# ---------------------------------------------------------------------------
# Room queries
# ---------------------------------------------------------------------------

def get_available_rooms(building=None, room_type=None):
    """Return available rooms, optionally filtered by building and/or room type.

    Parameters
    ----------
    building : str or None
        Pass ``None`` or ``"All"`` for no filter.
    room_type : str or None
        Pass ``None`` or ``"All"`` for no filter.

    Returns
    -------
    list[sqlite3.Row]
    """
    with get_connection() as conn:
        query = "SELECT * FROM study_rooms WHERE status = 'available'"
        params = []
        if building and building != "All":
            query += " AND building = ?"
            params.append(building)
        if room_type and room_type != "All":
            query += " AND room_type = ?"
            params.append(room_type)
        query += " ORDER BY building, room_number"
        return conn.execute(query, params).fetchall()


def get_room_list():
    """Return a list of available rooms with id, number, building, and capacity."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT room_id, room_number, building, capacity FROM study_rooms "
            "WHERE status='available' ORDER BY building, room_number"
        ).fetchall()


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

def get_bookings(user_id):
    """Return all bookings for *user_id* with the room number joined in."""
    with get_connection() as conn:
        return conn.execute(
            """SELECT b.*, r.room_number FROM study_room_bookings b
               JOIN study_rooms r ON b.room_id = r.room_id
               WHERE b.booked_by = ? ORDER BY b.booking_date DESC, b.start_time DESC""",
            (user_id,),
        ).fetchall()


def book_room(
    room_id,
    user_id,
    booking_date,
    start_time,
    end_time,
    purpose="study",
    group_size=1,
    notes="",
):
    """Book a study room after checking for time-slot conflicts.

    Raises
    ------
    ValueError
        If validation fails or the room is already booked for the given slot.
    """
    # Validate date
    try:
        datetime.strptime(booking_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD.")

    if start_time >= end_time:
        raise ValueError("End time must be after start time.")

    with get_connection() as conn:
        conflict = conn.execute(
            """SELECT COUNT(*) FROM study_room_bookings
               WHERE room_id = ? AND booking_date = ? AND status = 'confirmed'
               AND start_time < ? AND end_time > ?""",
            (room_id, booking_date, end_time, start_time),
        ).fetchone()[0]
        if conflict > 0:
            raise ValueError("Room is already booked for that time slot.")

        conn.execute(
            """INSERT INTO study_room_bookings
                (room_id, booked_by, booking_date, start_time, end_time, purpose, group_size, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (room_id, user_id, booking_date, start_time, end_time,
             purpose, int(group_size), notes),
        )
        conn.commit()


def cancel_booking(booking_id):
    """Cancel a booking. Returns True if a row was updated, False otherwise."""
    with get_connection() as conn:
        cur = conn.execute(
            "UPDATE study_room_bookings SET status='cancelled' WHERE booking_id=? AND status != 'cancelled'",
            (booking_id,),
        )
        conn.commit()
        return cur.rowcount > 0
