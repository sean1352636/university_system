import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.exceptions import CalendarError, ValidationError, PermissionError
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.config import ValidationUtils
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.database import DatabaseManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.auth import AuthenticationManager

logger = configure_logging(name=__name__)

try:
    from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
    from dateutil.parser import parse as date_parse
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False


class RecurringEventManager:
    """Manages recurring events with complex patterns"""

    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_recurring_event(self, base_event_data: Dict, recurrence_pattern: Dict) -> Tuple[bool, str]:
        """Create a recurring event with specified pattern"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create recurring events")

        if not DATEUTIL_AVAILABLE:
            raise CalendarError("dateutil library required for recurring events")

        try:
            # Validate recurrence pattern
            required_fields = ['frequency', 'interval']
            for field in required_fields:
                if field not in recurrence_pattern:
                    raise ValidationError(f"Missing required field: {field}")

            frequency_map = {
                'daily': DAILY,
                'weekly': WEEKLY,
                'monthly': MONTHLY,
                'yearly': YEARLY
            }

            if recurrence_pattern['frequency'] not in frequency_map:
                raise ValidationError("Invalid frequency. Must be daily, weekly, monthly, or yearly")

            # Validate base event data
            if not base_event_data.get('name'):
                raise ValidationError("Event name is required")

            base_event_id = str(uuid.uuid4())
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                # Create base event
                self.db_manager.execute_update(
                    """INSERT INTO academic_calendar_events (id, name, date, date_start, date_end, description,
                       event_type, date_added, last_modified, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (base_event_id,
                     ValidationUtils.sanitize_string(base_event_data['name']),
                     base_event_data.get('date'),
                     base_event_data.get('date_start'),
                     base_event_data.get('date_end'),
                     ValidationUtils.sanitize_string(base_event_data.get('description', ''), 1000),
                     ValidationUtils.sanitize_string(base_event_data.get('event_type', 'Academic')),
                     current_time, current_time, user_id)
                )

                # Store recurrence pattern
                recurring_id = str(uuid.uuid4())
                self.db_manager.execute_update(
                    """INSERT INTO recurring_events (id, base_event_id, frequency, interval_count,
                       days_of_week, day_of_month, month_of_year, end_date, occurrence_count,
                       timezone, exceptions, date_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (recurring_id, base_event_id, recurrence_pattern['frequency'],
                     recurrence_pattern.get('interval', 1),
                     json.dumps(recurrence_pattern.get('days_of_week', [])),
                     recurrence_pattern.get('day_of_month'),
                     recurrence_pattern.get('month_of_year'),
                     recurrence_pattern.get('end_date'),
                     recurrence_pattern.get('occurrence_count'),
                     recurrence_pattern.get('timezone', 'UTC'),
                     json.dumps(recurrence_pattern.get('exceptions', [])),
                     current_time)
                )

                # Generate occurrences
                success, message = self._generate_recurring_occurrences(base_event_id, recurrence_pattern, base_event_data)
                if not success:
                    raise CalendarError(f"Failed to generate occurrences: {message}")

            logger.info(f"Recurring event created with base ID: {base_event_id}")
            return True, f"Recurring event created with ID: {base_event_id}"

        except Exception as e:
            logger.error(f"Failed to create recurring event: {e}")
            raise CalendarError(f"Error creating recurring event: {str(e)}")

    def _generate_recurring_occurrences(self, base_event_id: str, pattern: Dict, base_event: Dict) -> Tuple[bool, str]:
        """Generate individual event occurrences from pattern"""
        try:
            # Get base event details
            start_date_str = base_event.get('date') or base_event.get('date_start')
            if not start_date_str:
                return False, "No start date found for base event"

            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")

            # Configure dateutil rrule
            frequency_map = {'daily': DAILY, 'weekly': WEEKLY, 'monthly': MONTHLY, 'yearly': YEARLY}
            freq = frequency_map[pattern['frequency']]

            rrule_kwargs = {
                'freq': freq,
                'interval': pattern.get('interval', 1),
                'dtstart': start_date
            }

            if pattern.get('end_date'):
                rrule_kwargs['until'] = datetime.strptime(pattern['end_date'], "%Y-%m-%d")
            elif pattern.get('occurrence_count'):
                rrule_kwargs['count'] = min(pattern['occurrence_count'], 1000)  # Limit occurrences
            else:
                # Default to 1 year if no end specified
                rrule_kwargs['until'] = start_date + timedelta(days=365)

            if pattern.get('days_of_week'):
                rrule_kwargs['byweekday'] = pattern['days_of_week']

            # Generate occurrences
            rule = rrule(**rrule_kwargs)
            exceptions = set(pattern.get('exceptions', []))

            occurrence_count = 0
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            for occurrence_date in rule:
                if occurrence_date.strftime("%Y-%m-%d") in exceptions:
                    continue

                if occurrence_date != start_date:  # Skip the base event
                    occurrence_id = str(uuid.uuid4())

                    # Calculate end date if it's a date range
                    occurrence_end = None
                    if base_event.get('date_end'):
                        duration_days = (datetime.strptime(base_event['date_end'], "%Y-%m-%d") - start_date).days
                        occurrence_end = (occurrence_date + timedelta(days=duration_days)).strftime("%Y-%m-%d")

                    self.db_manager.execute_update(
                        """INSERT INTO academic_calendar_events (id, name, date, date_start, date_end, description,
                           event_type, date_added, last_modified, created_by)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (occurrence_id,
                         f"{base_event['name']} (Recurring)",
                         occurrence_date.strftime("%Y-%m-%d") if base_event.get('date') else None,
                         occurrence_date.strftime("%Y-%m-%d") if base_event.get('date_start') else None,
                         occurrence_end,
                         base_event.get('description', ''),
                         base_event.get('event_type', 'Academic'),
                         current_time, current_time, user_id)
                    )

                    occurrence_count += 1

            return True, f"Generated {occurrence_count} recurring occurrences"

        except Exception as e:
            logger.error(f"Failed to generate occurrences: {e}")
            return False, f"Error generating occurrences: {str(e)}"
