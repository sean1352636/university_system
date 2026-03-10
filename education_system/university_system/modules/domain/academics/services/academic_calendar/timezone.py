import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from education_system.university_system.utils.logging.log_config import configure_logging

logger = configure_logging(name=__name__)

try:
    import pytz
    TIMEZONE_AVAILABLE = True
except ImportError:
    TIMEZONE_AVAILABLE = False


class EnhancedTimeZoneManager:
    """Comprehensive timezone and DST handling"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self._create_timezone_tables()

    def _create_timezone_tables(self):
        """Create timezone configuration tables"""
        try:
            # User timezone preferences
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS user_timezone_preferences (
                user_id TEXT PRIMARY KEY,
                timezone_name TEXT NOT NULL,
                auto_dst BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )''')

            # Event timezone data
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_timezones (
                event_id TEXT PRIMARY KEY,
                timezone_name TEXT NOT NULL,
                utc_offset_hours INTEGER NOT NULL,
                is_dst_active BOOLEAN DEFAULT FALSE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE
            )''')

        except Exception as e:
            logger.error(f"Failed to create timezone tables: {e}")

    def set_user_timezone(self, user_id: str, timezone_name: str,
                         auto_dst: bool = True) -> Tuple[bool, str]:
        """Set timezone preference for a user"""
        try:
            # Validate timezone
            if not self._validate_timezone(timezone_name):
                return False, "Invalid timezone name"

            current_time = datetime.now().isoformat()

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT OR REPLACE INTO user_timezone_preferences
                (user_id, timezone_name, auto_dst, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (user_id, timezone_name, auto_dst, current_time, current_time))

            return True, f"Timezone set to {timezone_name}"

        except Exception as e:
            logger.error(f"Failed to set user timezone: {e}")
            return False, f"Error setting timezone: {str(e)}"

    def _validate_timezone(self, timezone_name: str) -> bool:
        """Validate timezone name"""
        try:
            if not TIMEZONE_AVAILABLE:
                return timezone_name in ['UTC', 'EST', 'PST', 'CST', 'MST']

            pytz.timezone(timezone_name)
            return True
        except Exception:
            return False

    def convert_event_time(self, event_id: str, target_timezone: str) -> Dict[str, Any]:
        """Convert event time to different timezone"""
        if not TIMEZONE_AVAILABLE:
            return {'error': 'Timezone conversion not available without pytz'}

        try:
            # Get event details
            event_rows = self.db_manager.execute_query(
                "SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,)
            )
            if not event_rows:
                return {'error': 'Event not found'}

            event = dict(event_rows[0])

            # Get event timezone
            tz_rows = self.db_manager.execute_query(
                "SELECT timezone_name FROM event_timezones WHERE event_id = ?",
                (event_id,)
            )

            source_tz_name = tz_rows[0]['timezone_name'] if tz_rows else 'UTC'

            # Convert times
            source_tz = pytz.timezone(source_tz_name)
            target_tz = pytz.timezone(target_timezone)

            converted_event = event.copy()

            for date_field in ['date', 'date_start', 'date_end']:
                if event.get(date_field):
                    # Parse date
                    dt = datetime.strptime(event[date_field], "%Y-%m-%d")

                    # Localize to source timezone
                    dt_localized = source_tz.localize(dt)

                    # Convert to target timezone
                    dt_converted = dt_localized.astimezone(target_tz)

                    converted_event[date_field] = dt_converted.strftime("%Y-%m-%d %H:%M:%S %Z")

            return {
                'success': True,
                'original_timezone': source_tz_name,
                'target_timezone': target_timezone,
                'converted_event': converted_event
            }

        except Exception as e:
            logger.error(f"Failed to convert event time: {e}")
            return {'error': str(e)}

    def get_dst_transitions(self, timezone_name: str, year: int) -> List[Dict]:
        """Get DST transition dates for a timezone and year"""
        if not TIMEZONE_AVAILABLE:
            return []

        try:
            tz = pytz.timezone(timezone_name)

            # Get transitions for the year
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)

            transitions = []

            # Sample dates throughout the year to find transitions
            current_date = start_date
            prev_offset = None

            while current_date < end_date:
                dt_localized = tz.localize(current_date.replace(hour=12))
                current_offset = dt_localized.utcoffset()

                if prev_offset is not None and current_offset != prev_offset:
                    # Found a transition
                    transitions.append({
                        'date': current_date.strftime("%Y-%m-%d"),
                        'from_offset': str(prev_offset),
                        'to_offset': str(current_offset),
                        'type': 'spring_forward' if current_offset > prev_offset else 'fall_back'
                    })

                prev_offset = current_offset
                current_date += timedelta(days=1)

            return transitions

        except Exception as e:
            logger.error(f"Failed to get DST transitions: {e}")
            return []
