import uuid
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any
from university_system.utils.logging.log_config import configure_logging
from .exceptions import CalendarError, ValidationError, PermissionError
from .config import ValidationUtils

logger = configure_logging(name=__name__)


class BatchOperationsManager:
    """User-friendly bulk operations interface"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def bulk_create_events(self, events_data: List[Dict],
                          template_id: str = None) -> Dict[str, Any]:
        """Bulk create events from data or template"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions for bulk operations")

        try:
            created_events = []
            failed_events = []
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                for event_data in events_data:
                    try:
                        # Validate event data
                        if not event_data.get('name'):
                            failed_events.append({
                                'data': event_data,
                                'error': 'Missing event name'
                            })
                            continue

                        event_id = str(uuid.uuid4())

                        self.db_manager.execute_update('''
                        INSERT INTO academic_calendar_events (id, name, date, date_start, date_end,
                                          description, event_type, date_added,
                                          last_modified, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            event_id,
                            ValidationUtils.sanitize_string(event_data['name'], 255),
                            event_data.get('date'),
                            event_data.get('date_start'),
                            event_data.get('date_end'),
                            ValidationUtils.sanitize_string(event_data.get('description', ''), 1000),
                            ValidationUtils.sanitize_string(event_data.get('event_type', 'Academic'), 50),
                            current_time,
                            current_time,
                            user_id
                        ))

                        created_events.append({
                            'event_id': event_id,
                            'name': event_data['name']
                        })

                    except Exception as e:
                        failed_events.append({
                            'data': event_data,
                            'error': str(e)
                        })

            return {
                'success': True,
                'created_count': len(created_events),
                'failed_count': len(failed_events),
                'created_events': created_events,
                'failed_events': failed_events
            }

        except Exception as e:
            logger.error(f"Bulk create events failed: {e}")
            return {'success': False, 'error': str(e)}

    def bulk_update_events(self, event_ids: List[str],
                          update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk update multiple events"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions for bulk operations")

        try:
            updated_events = []
            failed_events = []

            # Validate update data
            allowed_fields = {'name', 'description', 'event_type', 'date', 'date_start', 'date_end'}
            invalid_fields = set(update_data.keys()) - allowed_fields
            if invalid_fields:
                return {'success': False, 'error': f'Invalid fields: {invalid_fields}'}

            with self.db_manager.transaction():
                for event_id in event_ids:
                    try:
                        if not event_id or not str(event_id).strip():
                            failed_events.append({
                                'event_id': event_id,
                                'error': 'Invalid event ID format'
                            })
                            continue

                        # Build update query
                        set_clauses = []
                        params = []

                        for field, value in update_data.items():
                            if field in allowed_fields and value is not None:
                                set_clauses.append(f"{field} = ?")
                                if field in ['name', 'description', 'event_type']:
                                    params.append(ValidationUtils.sanitize_string(str(value), 255 if field == 'name' else 1000))
                                else:
                                    params.append(str(value))

                        if set_clauses:
                            set_clauses.append("last_modified = ?")
                            params.append(datetime.now().isoformat())
                            params.append(event_id)

                            query = f"UPDATE academic_calendar_events SET {', '.join(set_clauses)} WHERE id = ?"
                            rows_affected = self.db_manager.execute_update(query, tuple(params))

                            if rows_affected > 0:
                                updated_events.append(event_id)
                            else:
                                failed_events.append({
                                    'event_id': event_id,
                                    'error': 'Event not found'
                                })

                    except Exception as e:
                        failed_events.append({
                            'event_id': event_id,
                            'error': str(e)
                        })

            return {
                'success': True,
                'updated_count': len(updated_events),
                'failed_count': len(failed_events),
                'updated_events': updated_events,
                'failed_events': failed_events
            }

        except Exception as e:
            logger.error(f"Bulk update events failed: {e}")
            return {'success': False, 'error': str(e)}

    def create_event_template(self, template_name: str,
                             template_data: Dict[str, Any]) -> Tuple[bool, str]:
        """Create reusable event template"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create templates")

        try:
            template_id = str(uuid.uuid4())
            user_id = self.auth_manager.current_user['id']

            # Ensure templates table exists
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_templates (
                id TEXT PRIMARY KEY,
                template_name TEXT NOT NULL,
                template_data TEXT NOT NULL,
                created_by TEXT,
                created_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )''')

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO event_templates (id, template_name, template_data,
                                           created_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                ''', (template_id, template_name, json.dumps(template_data),
                     user_id, datetime.now().isoformat()))

            return True, f"Template created: {template_id}"

        except Exception as e:
            logger.error(f"Failed to create event template: {e}")
            return False, f"Error creating template: {str(e)}"
