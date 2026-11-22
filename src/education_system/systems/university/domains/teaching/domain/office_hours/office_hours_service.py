"""
Office Hours Management Service

Provides CRUD operations for instructor office hours and student booking
management. Supports capacity-limited scheduling, conflict detection, and
full audit logging for compliance.
"""

from __future__ import annotations

import logging
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity

logger = logging.getLogger(__name__)


def _lookup_booking_context(conn, booking_id: int) -> Optional[Dict[str, Any]]:
    """Join office_hour_bookings -> office_hours -> students for email context."""
    row = conn.execute(
        '''
        SELECT b.id AS booking_id, b.office_hour_id, b.booking_date,
               b.status, b.notes,
               oh.instructor_id, oh.day_of_week, oh.start_time, oh.end_time,
               oh.location,
               TRIM(COALESCE(s.first_name,'')||' '
                    ||COALESCE(s.last_name,'')) AS student_name,
               COALESCE(s.email_address,'')    AS student_email,
               b.student_id
          FROM office_hour_bookings b
          JOIN office_hours oh ON oh.id = b.office_hour_id
          LEFT JOIN students   s  ON s.student_id = b.student_id
         WHERE b.id = ?
        ''',
        (booking_id,),
    ).fetchone()
    return dict(row) if row else None


def _lookup_instructor(conn, instructor_id: str) -> Dict[str, str]:
    """Resolve an instructor to ``{'name', 'email'}``.

    ``office_hours.instructor_id`` holds a **username**. The staff table is
    keyed by ``username`` and has ``name``/``email`` columns — there is no
    ``staff_id`` and no ``first_name``/``last_name``, so the previous query
    raised and was swallowed, leaving every email addressed to the raw id
    and no way to reach the instructor at all.
    """
    blank = {'name': instructor_id or "(instructor)", 'email': ''}
    if not instructor_id:
        return blank

    for sql in (
        "SELECT name AS name, email AS email FROM staff WHERE username = ?",
        "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name, "
        "       email AS email FROM users WHERE username = ?",
    ):
        try:
            row = conn.execute(sql, (instructor_id,)).fetchone()
        except sqlite3.Error:
            continue
        if not row:
            continue
        name = (row['name'] or '').strip() or instructor_id
        return {'name': name, 'email': (row['email'] or '').strip()}

    return blank


def _lookup_instructor_name(conn, instructor_id: str) -> str:
    """Best-effort instructor display name. Falls back to the raw ID."""
    return _lookup_instructor(conn, instructor_id)['name']


def _resolve_user_email(conn, user_id: str, fallback: str = '') -> str:
    """Email for whoever is acting, preferring the students row.

    Staff and admins book office hours too, and they have no ``students``
    row — so the booking context's ``student_email`` comes back empty and
    the confirmation went nowhere. Fall back to their account email.
    """
    if fallback:
        return fallback
    if not user_id:
        return ''
    for sql in (
        "SELECT email_address AS email FROM students WHERE student_id = ?",
        "SELECT email AS email FROM users WHERE username = ?",
        "SELECT email AS email FROM staff WHERE username = ?",
    ):
        try:
            row = conn.execute(sql, (user_id,)).fetchone()
        except sqlite3.Error:
            continue
        if row and (row['email'] or '').strip():
            return row['email'].strip()
    return ''


# Where the office-hours templates actually live. The service used to ask
# for "office_hours/<name>", which matches no file, so every render returned
# (None, None) and no office-hours email had ever been sent. A bare name is
# not an option either: "booking_confirmation" also exists under
# finance_commerce/commerce/cinema.
_TEMPLATE_DIR = 'academics/teaching/office_hours'


def _send_office_hours_email(template_name: str, recipient: str,
                             vars_: Dict[str, Any]) -> bool:
    """Render the office-hours template and dispatch best-effort."""
    if not recipient:
        logger.info("no recipient for office_hours/%s; email not sent", template_name)
        return False
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    subject, body = render_template(f"{_TEMPLATE_DIR}/{template_name}", vars_)
    if not subject or not body:
        logger.error("template render failed: %s/%s", _TEMPLATE_DIR, template_name)
        return False
    try:
        send_email(recipient_email=recipient, subject=subject, body=body)
        return True
    except Exception:
        logger.exception("send_email failed office_hours/%s recipient=%s",
                         template_name, recipient)
        return False


def _duration_minutes(start_time: str, end_time: str) -> int:
    """HH:MM-HH:MM string pair → integer minutes. Returns 0 on parse error."""
    try:
        fmt = "%H:%M"
        s = datetime.strptime(start_time, fmt)
        e = datetime.strptime(end_time, fmt)
        return max(0, int((e - s).total_seconds() // 60))
    except Exception:
        return 0

def _rules(fn, *args, **kwargs):
    """Run an ``application/teaching/office_hours`` rule in one transaction and send
    the emails it returns. Booking, cancelling, rescheduling and retiring all
    follow those shared rules (dates, slots, notice, limits, waitlist)."""
    from education_system.systems.university.application.teaching import (
        occurrences as timetable_occurrences,
    )
    with transaction() as conn:
        result = fn(conn, *args, **kwargs)
    emails = result.get("emails") if isinstance(result, dict) else None
    if emails:
        timetable_occurrences.send_emails(emails)
    return result


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
            from education_system.systems.university.application.teaching import (
                office_hours as rules,
            )
            _rules(rules.sync_directory, office_hour_id)
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
        # Iterate over a literal column tuple so user-supplied keys never
        # flow into the SQL identifier positions (py/sql-injection).
        set_parts: list[str] = []
        values: list = []
        updates: dict = {}
        for col in (
            'day_of_week', 'start_time', 'end_time', 'location',
            'capacity', 'notes', 'is_active',
        ):
            if col in kwargs:
                set_parts.append(f"{col} = ?")
                values.append(kwargs[col])
                updates[col] = kwargs[col]
        if not set_parts:
            raise ValueError(
                "No valid fields to update. Allowed fields: "
                "capacity, day_of_week, end_time, is_active, location, notes, start_time"
            )

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        set_parts.append("updated_at = ?")
        values.append(now)
        updates['updated_at'] = now
        set_clause = ', '.join(set_parts)
        values.append(office_hour_id)

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

            if updated:
                from education_system.systems.university.application.teaching import (
                    office_hours as rules,
                )
                _rules(rules.sync_directory, office_hour_id)
            return updated

        except sqlite3.Error as e:
            logger.error(f"Error updating office hours {office_hour_id}: {e}")
            raise

    def delete_office_hours(self, office_hour_id: int) -> bool:
        """Retire a block (``is_active = 0``). Future bookings are cancelled and
        the students told; the staff directory entry is removed."""
        from education_system.systems.university.application.teaching import office_hours as rules
        current = self.get_office_hours(office_hour_id)
        if not current or not current.get("is_active"):
            return False
        _rules(rules.retire_block, office_hour_id)
        log_activity(f'Deleted office hours {office_hour_id}', 'office_hours')
        return True

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
        slot_start: Optional[str] = None,
        module_code: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> int:
        """Book a student in under the shared rules: the date must be a real,
        future date of the block (in term, not a holiday or cancelled), with
        enough notice, within the weekly limit, in a free slot or place.

        Raises ValueError with the reason (``office_hours.FullError`` when
        full, so callers can offer the waitlist)."""
        from education_system.systems.university.application.teaching import office_hours as rules
        result = _rules(rules.book, office_hour_id, student_id, booking_date,
                        slot_start=slot_start, module_code=module_code, notes=notes, mode=mode)
        log_activity(f'Booked office hour {office_hour_id} for student {student_id} on '
                     f'{booking_date}', 'office_hour_booking')
        return result["booking_id"]

    def cancel_booking(self, booking_id: int, student_id: str, *, staff: bool = False) -> bool:
        """Cancel a booking (the student's own, outside the cut-off; staff any).
        Returns False when there is no such active booking."""
        from education_system.systems.university.application.teaching import office_hours as rules
        if not student_id or not student_id.strip():
            raise ValueError("student_id is required")
        try:
            _rules(rules.cancel, booking_id, student_id.strip(), staff=staff)
        except ValueError as exc:
            if "not active" in str(exc) or "No such booking" in str(exc):
                return False
            if "your own" in str(exc):
                return False
            raise
        log_activity(f'Cancelled booking {booking_id}', 'office_hour_booking')
        return True

    def reschedule_booking(
        self,
        booking_id: int,
        student_id: str,
        new_booking_date: str,
        new_office_hour_id: Optional[int] = None,
        reason: str = "",
        slot_start: Optional[str] = None,
    ) -> bool:
        """Move a booking to another date (and slot) of the same block.

        Moving to a different block is a cancel and a new booking; it is
        refused here so the student sees the rules of the new block."""
        from education_system.systems.university.application.teaching import office_hours as rules
        if not student_id or not student_id.strip():
            raise ValueError("student_id is required")
        current = rules.booking
        with transaction() as conn:
            existing = current(conn, booking_id)
        if new_office_hour_id and int(new_office_hour_id) != existing["office_hour_id"]:
            raise ValueError("Cancel and book the other office hours instead")
        _rules(rules.reschedule, booking_id, student_id.strip(), new_booking_date,
               slot_start=slot_start)
        log_activity(f'Rescheduled booking {booking_id} to {new_booking_date}: {reason}',
                     'office_hour_booking')
        return True

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
