"""
Office Hours Management Service

Provides CRUD operations for instructor office hours and student booking
management. Supports capacity-limited scheduling, conflict detection, and
full audit logging for compliance.
"""

from __future__ import annotations

import logging
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

class OfficeHoursService:
    """Service for managing instructor office hours and student bookings.

    This service handles the full lifecycle of office hours, including creation,
    modification, deletion, and student booking with capacity enforcement.
    All mutating operations are logged via the centralized activity logger.
    """

    def __init__(self):
        """Initialize the OfficeHoursService and ensure database tables exist."""
        self._init_db()

    def _init_db(self) -> None:
        """Create the office_hours and office_hour_bookings tables if they do not exist."""
        try:
            with transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS office_hours (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        instructor_id TEXT NOT NULL,
                        day_of_week TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        location TEXT NOT NULL,
                        capacity INTEGER DEFAULT 5,
                        notes TEXT DEFAULT '',
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS office_hour_bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        office_hour_id INTEGER NOT NULL,
                        student_id TEXT NOT NULL,
                        booking_date TEXT NOT NULL,
                        notes TEXT DEFAULT '',
                        status TEXT DEFAULT 'confirmed',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (office_hour_id) REFERENCES office_hours(id)
                    )
                ''')
            logger.info("Office hours database tables initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize office hours tables: {e}")
            raise

    # ------------------------------------------------------------------ #
    #  Office Hours CRUD
    # ------------------------------------------------------------------ #

    def create_office_hours(
        self,
        instructor_id: str,
        day_of_week: str,
        start_time: str,
        end_time: str,
        location: str,
        capacity: int = 5,
        notes: str = '',
    ) -> int:
        """Create a new office hours slot for an instructor.

        Args:
            instructor_id: Unique identifier for the instructor.
            day_of_week: Day of the week (e.g. 'Monday', 'Tuesday').
            start_time: Start time in HH:MM format.
            end_time: End time in HH:MM format.
            location: Room or location description.
            capacity: Maximum number of bookings per session (default 5).
            notes: Optional notes about the office hours.

        Returns:
            The ID of the newly created office hours record.

        Raises:
            ValueError: If required fields are missing or invalid.
            sqlite3.Error: On database failure.
        """
        if not instructor_id or not instructor_id.strip():
            raise ValueError("instructor_id is required")
        if not day_of_week or not day_of_week.strip():
            raise ValueError("day_of_week is required")
        if not start_time or not start_time.strip():
            raise ValueError("start_time is required")
        if not end_time or not end_time.strip():
            raise ValueError("end_time is required")
        if not location or not location.strip():
            raise ValueError("location is required")
        if capacity < 1:
            raise ValueError("capacity must be at least 1")

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO office_hours
                        (instructor_id, day_of_week, start_time, end_time,
                         location, capacity, notes, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    ''',
                    (
                        instructor_id.strip(),
                        day_of_week.strip(),
                        start_time.strip(),
                        end_time.strip(),
                        location.strip(),
                        capacity,
                        notes,
                        now,
                        now,
                    ),
                )
                office_hour_id = cursor.lastrowid

            log_activity(
                f'Created office hours {office_hour_id} for instructor {instructor_id}',
                'office_hours',
            )
            logger.info(
                "Created office hours id=%s for instructor=%s on %s %s-%s",
                office_hour_id, instructor_id, day_of_week, start_time, end_time,
            )
            return office_hour_id

        except sqlite3.Error as e:
            logger.error(f"Error creating office hours: {e}")
            raise

    def update_office_hours(self, office_hour_id: int, **kwargs: Any) -> bool:
        """Update an existing office hours record.

        Accepted keyword arguments: day_of_week, start_time, end_time,
        location, capacity, notes, is_active.

        Args:
            office_hour_id: ID of the office hours record to update.
            **kwargs: Fields to update with their new values.

        Returns:
            True if the record was updated, False if not found or nothing changed.

        Raises:
            ValueError: If no valid fields are provided.
            sqlite3.Error: On database failure.
        """
        allowed_fields = {
            'day_of_week', 'start_time', 'end_time', 'location',
            'capacity', 'notes', 'is_active',
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            raise ValueError(
                f"No valid fields to update. Allowed fields: {', '.join(sorted(allowed_fields))}"
            )

        updates['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        set_clause = ', '.join(f'{col} = ?' for col in updates)
        values = list(updates.values()) + [office_hour_id]

        try:
            with transaction() as conn:
                cursor = conn.execute(
                    f'UPDATE office_hours SET {set_clause} WHERE id = ? AND is_active = 1',
                    values,
                )
                updated = cursor.rowcount > 0

            if updated:
                log_activity(
                    f'Updated office hours {office_hour_id}: {list(updates.keys())}',
                    'office_hours',
                )
                logger.info("Updated office hours id=%s fields=%s", office_hour_id, list(updates.keys()))
            else:
                logger.warning("Office hours id=%s not found or inactive", office_hour_id)

            return updated

        except sqlite3.Error as e:
            logger.error(f"Error updating office hours {office_hour_id}: {e}")
            raise

    def delete_office_hours(self, office_hour_id: int) -> bool:
        """Soft-delete an office hours record by setting is_active to 0.

        Args:
            office_hour_id: ID of the office hours record to deactivate.

        Returns:
            True if the record was deactivated, False if not found.

        Raises:
            sqlite3.Error: On database failure.
        """
        try:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with transaction() as conn:
                cursor = conn.execute(
                    'UPDATE office_hours SET is_active = 0, updated_at = ? WHERE id = ? AND is_active = 1',
                    (now, office_hour_id),
                )
                deleted = cursor.rowcount > 0

            if deleted:
                log_activity(
                    f'Deleted office hours {office_hour_id}',
                    'office_hours',
                )
                logger.info("Soft-deleted office hours id=%s", office_hour_id)
            else:
                logger.warning("Office hours id=%s not found or already inactive", office_hour_id)

            return deleted

        except sqlite3.Error as e:
            logger.error(f"Error deleting office hours {office_hour_id}: {e}")
            raise

    def get_office_hours(self, office_hour_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single office hours record by ID.

        Args:
            office_hour_id: ID of the office hours record.

        Returns:
            A dictionary with the office hours data, or None if not found.
        """
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    'SELECT * FROM office_hours WHERE id = ?',
                    (office_hour_id,),
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Error retrieving office hours {office_hour_id}: {e}")
            raise

    def get_available_office_hours(
        self,
        instructor_id: Optional[str] = None,
        department: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve active office hours, optionally filtered by instructor or department.

        Args:
            instructor_id: If provided, filter to this instructor only.
            department: If provided, filter by department (matched against location).

        Returns:
            A list of dictionaries representing matching office hours records.
        """
        try:
            query = 'SELECT * FROM office_hours WHERE is_active = 1'
            params: List[Any] = []

            if instructor_id:
                query += ' AND instructor_id = ?'
                params.append(instructor_id)
            if department:
                query += ' AND location LIKE ?'
                params.append(f'%{department}%')

            query += ' ORDER BY day_of_week, start_time'

            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(query, params).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error retrieving available office hours: {e}")
            raise

    # ------------------------------------------------------------------ #
    #  Bookings
    # ------------------------------------------------------------------ #

    def book_office_hour(
        self,
        office_hour_id: int,
        student_id: str,
        booking_date: str,
        notes: str = '',
    ) -> int:
        """Book a student into an office hours slot for a specific date.

        Enforces capacity limits by counting existing confirmed bookings for the
        given office_hour_id and booking_date combination.

        Args:
            office_hour_id: ID of the office hours slot to book.
            student_id: Unique identifier of the student.
            booking_date: Date of the booking in YYYY-MM-DD format.
            notes: Optional notes from the student.

        Returns:
            The ID of the newly created booking.

        Raises:
            ValueError: If the office hours slot is inactive, at capacity,
                        or the student already has a confirmed booking.
            sqlite3.Error: On database failure.
        """
        if not student_id or not student_id.strip():
            raise ValueError("student_id is required")
        if not booking_date or not booking_date.strip():
            raise ValueError("booking_date is required")

        try:
            with transaction() as conn:
                conn.row_factory = sqlite3.Row

                # Fetch the office hours slot
                oh_row = conn.execute(
                    'SELECT * FROM office_hours WHERE id = ?',
                    (office_hour_id,),
                ).fetchone()

                if not oh_row:
                    raise ValueError(f"Office hours slot {office_hour_id} not found")
                if not oh_row['is_active']:
                    raise ValueError(f"Office hours slot {office_hour_id} is not active")

                capacity = oh_row['capacity']

                # Count existing confirmed bookings for this slot and date
                count_row = conn.execute(
                    '''
                    SELECT COUNT(*) as cnt FROM office_hour_bookings
                    WHERE office_hour_id = ? AND booking_date = ? AND status = 'confirmed'
                    ''',
                    (office_hour_id, booking_date),
                ).fetchone()
                current_count = count_row['cnt'] if count_row else 0

                if current_count >= capacity:
                    raise ValueError(
                        f"Office hours slot {office_hour_id} is at full capacity "
                        f"({current_count}/{capacity}) for {booking_date}"
                    )

                # Check for duplicate booking by the same student
                existing = conn.execute(
                    '''
                    SELECT id FROM office_hour_bookings
                    WHERE office_hour_id = ? AND student_id = ? AND booking_date = ?
                          AND status = 'confirmed'
                    ''',
                    (office_hour_id, student_id.strip(), booking_date),
                ).fetchone()

                if existing:
                    raise ValueError(
                        f"Student {student_id} already has a confirmed booking "
                        f"for office hours {office_hour_id} on {booking_date}"
                    )

                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO office_hour_bookings
                        (office_hour_id, student_id, booking_date, notes, status, created_at)
                    VALUES (?, ?, ?, ?, 'confirmed', ?)
                    ''',
                    (
                        office_hour_id,
                        student_id.strip(),
                        booking_date,
                        notes,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    ),
                )
                booking_id = cursor.lastrowid

            log_activity(
                f'Booked office hour {office_hour_id} for student {student_id} on {booking_date}',
                'office_hour_booking',
            )
            logger.info(
                "Created booking id=%s for student=%s office_hour=%s date=%s",
                booking_id, student_id, office_hour_id, booking_date,
            )
            return booking_id

        except ValueError:
            raise
        except sqlite3.Error as e:
            logger.error(f"Error booking office hour {office_hour_id}: {e}")
            raise

    def cancel_booking(self, booking_id: int, student_id: str) -> bool:
        """Cancel an existing booking.

        Only the student who owns the booking can cancel it. The booking status
        is set to 'cancelled' rather than deleting the record.

        Args:
            booking_id: ID of the booking to cancel.
            student_id: ID of the student requesting cancellation.

        Returns:
            True if the booking was cancelled, False if not found or not owned
            by the specified student.

        Raises:
            sqlite3.Error: On database failure.
        """
        if not student_id or not student_id.strip():
            raise ValueError("student_id is required")

        try:
            with transaction() as conn:
                cursor = conn.execute(
                    '''
                    UPDATE office_hour_bookings
                    SET status = 'cancelled'
                    WHERE id = ? AND student_id = ? AND status = 'confirmed'
                    ''',
                    (booking_id, student_id.strip()),
                )
                cancelled = cursor.rowcount > 0

            if cancelled:
                log_activity(
                    f'Cancelled booking {booking_id} for student {student_id}',
                    'office_hour_booking',
                )
                logger.info("Cancelled booking id=%s by student=%s", booking_id, student_id)
            else:
                logger.warning(
                    "Booking id=%s not found or not owned by student=%s",
                    booking_id, student_id,
                )

            return cancelled

        except sqlite3.Error as e:
            logger.error(f"Error cancelling booking {booking_id}: {e}")
            raise

    def get_student_bookings(self, student_id: str) -> List[Dict[str, Any]]:
        """Retrieve all bookings for a given student.

        Includes joined office hours data for display purposes.

        Args:
            student_id: Unique identifier of the student.

        Returns:
            A list of dictionaries with booking and office hours details.
        """
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    '''
                    SELECT b.*, oh.instructor_id, oh.day_of_week,
                           oh.start_time, oh.end_time, oh.location
                    FROM office_hour_bookings b
                    JOIN office_hours oh ON b.office_hour_id = oh.id
                    WHERE b.student_id = ?
                    ORDER BY b.booking_date DESC, oh.start_time
                    ''',
                    (student_id,),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error retrieving bookings for student {student_id}: {e}")
            raise

    def get_instructor_bookings(self, instructor_id: str) -> List[Dict[str, Any]]:
        """Retrieve all bookings for a given instructor's office hours.

        Includes joined booking data for display purposes.

        Args:
            instructor_id: Unique identifier of the instructor.

        Returns:
            A list of dictionaries with booking and office hours details.
        """
        try:
            with get_connection() as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    '''
                    SELECT b.*, oh.instructor_id, oh.day_of_week,
                           oh.start_time, oh.end_time, oh.location, oh.capacity
                    FROM office_hour_bookings b
                    JOIN office_hours oh ON b.office_hour_id = oh.id
                    WHERE oh.instructor_id = ?
                    ORDER BY b.booking_date DESC, oh.start_time
                    ''',
                    (instructor_id,),
                ).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Error retrieving bookings for instructor {instructor_id}: {e}")
            raise
