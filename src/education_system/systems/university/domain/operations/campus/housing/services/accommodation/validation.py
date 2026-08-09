import logging
from datetime import datetime, timedelta

from education_system.systems.university.domain.operations.campus.housing.services.accommodation._common import (
    sqlite3, DB_PATH, get_text,
)
from education_system.systems.university.domain.operations.campus.housing.services.accommodation.db import init_accommodation_db


def validate_date(date_str):
    """Validate date format and return tuple (is_valid, error_message)."""
    if not date_str:  # Empty date is allowed (means indefinite or not set)
        return True, None

    try:
        # Validate format and attempts to parse the date
        date_obj = datetime.fromisoformat(date_str)

        # Check if date is not too far in the past or future (optional)
        now = datetime.now()
        max_future = now + timedelta(days=3650)  # ~10 years
        min_past = now - timedelta(days=3650)  # ~10 years

        if date_obj > max_future:
            return False, get_text("housing.accommodation.validation.date_too_far_future", "Date is too far in the future (maximum 10 years ahead)")
        if date_obj < min_past:
            return False, get_text("housing.accommodation.validation.date_too_far_past", "Date is too far in the past (maximum 10 years ago)")

        return True, None
    except ValueError:
        return False, get_text("housing.accommodation.validation.invalid_date_format", "Invalid date format. Please use YYYY-MM-DD format.")
    except Exception as e:
        return False, get_text("housing.accommodation.validation.date_validation_error", "Date validation error: {error}").format(error=str(e))


def check_conflict(student_id, accommodation_type, start_date, end_date, excluded_id=None):
    """Return True if new dates overlap existing for same student and type, with improved error handling."""
    init_accommodation_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Exclude the current record if we're updating
            exclude_clause = " AND id != ?" if excluded_id else ""
            params = [student_id, accommodation_type]
            if excluded_id:
                params.append(excluded_id)

            cursor.execute(
                "SELECT id, start_date, end_date FROM accommodations"
                " WHERE student_id=? AND accommodation_type=? AND status='active' " + exclude_clause,
                params)

            rows = cursor.fetchall()
            if not rows:
                return False

            for aid, sd, ed in rows:
                if not sd and not ed:  # Indefinite accommodation already exists
                    return True

                if not start_date and not end_date:  # New indefinite accommodation
                    return True

                # Convert to date objects for comparison
                existing_start = datetime.fromisoformat(sd) if sd else datetime.min
                existing_end = datetime.fromisoformat(ed) if ed else datetime.max
                new_start = datetime.fromisoformat(start_date) if start_date else datetime.min
                new_end = datetime.fromisoformat(end_date) if end_date else datetime.max

                # Check for overlap
                if not (new_end < existing_start or new_start > existing_end):
                    return True

        return False
    except Exception as e:
        logging.error(f"Error checking accommodation conflicts: {e}")
        print(get_text("housing.accommodation.conflict.error_checking", "Error checking for accommodation conflicts: {error}").format(error=e))
        # Since we couldn't check for conflicts, fail safe and return True
        return True


def get_accommodation_types():
    """Retrieve list of available accommodation types from the database."""
    init_accommodation_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT type_name FROM accommodation_types ORDER BY type_name')
            types = [row[0] for row in cursor.fetchall()]
            return types if types else ["Extended Time", "Alternate Format", "Note-Taking", "Assistive Technology"]
    except Exception as e:
        logging.error(f"Error retrieving accommodation types: {e}")
        # Return default list if database query fails
        return ["Extended Time", "Alternate Format", "Note-Taking", "Assistive Technology"]


def validate_student_id(student_id):
    """Validate if student exists in the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM students WHERE student_id = ?', (student_id,))
            return cursor.fetchone()[0] > 0
    except Exception as e:
        logging.error(f"Error validating student ID: {e}")
        return False
