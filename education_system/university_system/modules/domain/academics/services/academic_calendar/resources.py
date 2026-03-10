import uuid
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from education_system.university_system.utils.logging.log_config import configure_logging
from .exceptions import CalendarError, ValidationError, PermissionError
from .config import ValidationUtils

logger = configure_logging(name=__name__)


class ResourceManager:
    """Manages resources like rooms, equipment, etc."""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_resource(self, resource_data: Dict) -> Tuple[bool, str]:
        """Create a new resource"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create resources")

        try:
            required_fields = ['name', 'type']
            for field in required_fields:
                if field not in resource_data or not str(resource_data[field]).strip():
                    raise ValidationError(f"Required field '{field}' is missing or empty")

            resource_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO resources (id, name, type, capacity, location, equipment, status, date_added)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (resource_id,
                     ValidationUtils.sanitize_string(resource_data['name'], 200),
                     ValidationUtils.sanitize_string(resource_data['type'], 50),
                     resource_data.get('capacity'),
                     ValidationUtils.sanitize_string(resource_data.get('location', ''), 200),
                     ValidationUtils.sanitize_string(resource_data.get('equipment', ''), 500),
                     ValidationUtils.sanitize_string(resource_data.get('status', 'available'), 20),
                     datetime.now().isoformat())
                )

            logger.info(f"Resource created with ID: {resource_id}")
            return True, f"Resource created with ID: {resource_id}"

        except Exception as e:
            logger.error(f"Failed to create resource: {e}")
            raise CalendarError(f"Failed to create resource: {str(e)}")

    def book_resource(self, booking_data: Dict) -> Tuple[bool, str]:
        """Book a resource for an event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to book resources")

        try:
            required_fields = ['resource_id', 'event_id', 'start_time', 'end_time']
            for field in required_fields:
                if field not in booking_data:
                    raise ValidationError(f"Required field '{field}' is missing")

            # Validate time format
            start_time = booking_data['start_time']
            end_time = booking_data['end_time']

            if not ValidationUtils.validate_datetime(start_time) or not ValidationUtils.validate_datetime(end_time):
                raise ValidationError("Invalid datetime format. Use YYYY-MM-DD HH:MM:SS")

            # Check for conflicts
            conflicts = self._check_booking_conflicts(
                booking_data['resource_id'],
                start_time,
                end_time,
                booking_data.get('exclude_booking_id')
            )

            if conflicts:
                return False, f"Resource booking conflicts with existing bookings: {', '.join(conflicts)}"

            booking_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO resource_bookings (id, resource_id, event_id, start_time, end_time,
                       status, notes, date_added) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (booking_id,
                     booking_data['resource_id'],
                     booking_data['event_id'],
                     start_time,
                     end_time,
                     ValidationUtils.sanitize_string(booking_data.get('status', 'confirmed'), 20),
                     ValidationUtils.sanitize_string(booking_data.get('notes', ''), 500),
                     datetime.now().isoformat())
                )

            logger.info(f"Resource booked with ID: {booking_id}")
            return True, f"Resource booked with ID: {booking_id}"

        except Exception as e:
            logger.error(f"Failed to book resource: {e}")
            raise CalendarError(f"Failed to book resource: {str(e)}")

    def _check_booking_conflicts(self, resource_id: str, start_time: str, end_time: str,
                                exclude_booking_id: str = None) -> List[str]:
        """Check for booking conflicts"""
        try:
            query = """
                SELECT rb.id, e.name
                FROM resource_bookings rb
                JOIN academic_calendar_events e ON rb.event_id = e.id
                WHERE rb.resource_id = ?
                AND rb.status = 'confirmed'
                AND NOT (rb.end_time <= ? OR rb.start_time >= ?)
            """
            params = [resource_id, start_time, end_time]

            if exclude_booking_id:
                query += " AND rb.id != ?"
                params.append(exclude_booking_id)

            rows = self.db_manager.execute_query(query, tuple(params))
            conflicts = [f"{row['id']} ({row['name']})" for row in rows]

            return conflicts

        except Exception as e:
            logger.error(f"Failed to check booking conflicts: {e}")
            return []
