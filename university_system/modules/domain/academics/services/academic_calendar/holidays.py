import uuid
import logging
from datetime import datetime
from typing import Tuple
from university_system.utils.logging.log_config import configure_logging
from .exceptions import CalendarError, ValidationError, PermissionError
from .config import ValidationUtils

logger = configure_logging(name=__name__)

try:
    import holidays
    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False


class HolidayManager:
    """Manages holidays and regional calendar support"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def import_national_holidays(self, country_code: str, year: int, region: str = None) -> Tuple[bool, str]:
        """Import national holidays for a specific country and year"""
        if not self.auth_manager.check_permission('system_config'):
            raise PermissionError("Insufficient permissions to import holidays")

        if not HOLIDAYS_AVAILABLE:
            return False, "holidays library not available. Install with: pip install holidays"

        try:
            country_code = ValidationUtils.sanitize_string(country_code, 10).upper()
            region = ValidationUtils.sanitize_string(region or "", 50) if region else None

            # Validate year
            current_year = datetime.now().year
            if not (current_year - 10 <= year <= current_year + 10):
                raise ValidationError("Year must be within 10 years of current year")

            # Get holidays using the holidays library
            try:
                if region:
                    holiday_calendar = holidays.country_holidays(country_code, state=region, years=year)
                else:
                    holiday_calendar = holidays.country_holidays(country_code, years=year)
            except Exception as e:
                return False, f"Invalid country code or region: {country_code}, {region}"

            calendar_id = str(uuid.uuid4())
            imported_count = 0
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                # Create holiday calendar entry
                self.db_manager.execute_update(
                    """INSERT INTO holiday_calendars (id, name, country_code, region, is_active, date_added)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (calendar_id,
                     f"{country_code} {region or 'National'} Holidays {year}",
                     country_code, region, True, current_time)
                )

                # Import holidays as events
                for date, name in holiday_calendar.items():
                    event_id = str(uuid.uuid4())

                    # Check if holiday already exists
                    existing = self.db_manager.execute_query(
                        "SELECT id FROM academic_calendar_events WHERE date = ? AND name = ? AND event_type = 'Holiday'",
                        (date.strftime("%Y-%m-%d"), str(name))
                    )

                    if not existing:
                        self.db_manager.execute_update(
                            """INSERT INTO academic_calendar_events (id, name, date, description, event_type,
                               date_added, last_modified, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                            (event_id, str(name)[:255], date.strftime("%Y-%m-%d"),
                             f"National holiday - {country_code}",
                             'Holiday', current_time, current_time, user_id)
                        )
                        imported_count += 1

            logger.info(f"Imported {imported_count} holidays for {country_code} {year}")
            return True, f"Imported {imported_count} holidays for {country_code} {year}"

        except Exception as e:
            logger.error(f"Failed to import holidays: {e}")
            return False, f"Failed to import holidays: {str(e)}"
