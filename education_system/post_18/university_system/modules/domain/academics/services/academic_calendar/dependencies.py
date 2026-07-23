import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.exceptions import CalendarError, ValidationError, PermissionError
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.database import DatabaseManager
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.auth import AuthenticationManager

logger = configure_logging(name=__name__)


class EventDependencyManager:
    """Manages event dependencies, prerequisites, and workflows"""

    def __init__(self, db_manager: DatabaseManager, auth_manager: AuthenticationManager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self._create_dependency_tables()

    def _create_dependency_tables(self):
        """Create tables for event dependencies"""
        try:
            # Event dependencies table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_dependencies (
                id TEXT PRIMARY KEY,
                prerequisite_event_id TEXT NOT NULL,
                dependent_event_id TEXT NOT NULL,
                dependency_type TEXT NOT NULL,
                delay_days INTEGER DEFAULT 0,
                delay_hours INTEGER DEFAULT 0,
                is_mandatory BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL,
                FOREIGN KEY (prerequisite_event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE,
                FOREIGN KEY (dependent_event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE,
                UNIQUE(prerequisite_event_id, dependent_event_id)
            )''')

            # Event workflows table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_workflows (
                id TEXT PRIMARY KEY,
                workflow_name TEXT NOT NULL,
                description TEXT,
                template_data TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_by TEXT,
                created_at TEXT NOT NULL
            )''')

            # Event sequence tracking
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS event_sequences (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                event_id TEXT NOT NULL,
                sequence_order INTEGER NOT NULL,
                completion_status TEXT DEFAULT 'pending',
                completion_date TEXT,
                FOREIGN KEY (workflow_id) REFERENCES event_workflows (id) ON DELETE CASCADE,
                FOREIGN KEY (event_id) REFERENCES academic_calendar_events (id) ON DELETE CASCADE
            )''')

        except Exception as e:
            logger.error(f"Failed to create dependency tables: {e}")

    def add_event_dependency(self, prerequisite_event_id: str, dependent_event_id: str,
                            dependency_type: str = 'blocking', delay_days: int = 0,
                            delay_hours: int = 0, is_mandatory: bool = True) -> Tuple[bool, str]:
        """Add a dependency between two events"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to manage event dependencies")

        try:
            # Validate events exist
            for event_id in [prerequisite_event_id, dependent_event_id]:
                if not event_id or not str(event_id).strip():
                    raise ValidationError(f"Invalid event ID: {event_id}")

                event_exists = self.db_manager.execute_query(
                    "SELECT id FROM academic_calendar_events WHERE id = ?", (event_id,)
                )
                if not event_exists:
                    raise ValidationError(f"Event not found: {event_id}")

            # Check for circular dependencies
            if self._creates_circular_dependency(prerequisite_event_id, dependent_event_id):
                return False, "Cannot create dependency: would create circular dependency"

            dependency_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO event_dependencies
                (id, prerequisite_event_id, dependent_event_id, dependency_type,
                 delay_days, delay_hours, is_mandatory, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (dependency_id, prerequisite_event_id, dependent_event_id,
                     dependency_type, delay_days, delay_hours, is_mandatory,
                     datetime.now().isoformat()))

                # Update dependent event dates if necessary
                self._update_dependent_event_dates(dependent_event_id)

            return True, f"Dependency created successfully: {dependency_id}"

        except Exception as e:
            logger.error(f"Failed to create event dependency: {e}")
            return False, f"Error creating dependency: {str(e)}"

    def _creates_circular_dependency(self, prerequisite_id: str, dependent_id: str) -> bool:
        """Check if adding this dependency would create a circular dependency"""
        def has_path(start_id: str, target_id: str, visited: set) -> bool:
            if start_id == target_id:
                return True
            if start_id in visited:
                return False

            visited.add(start_id)

            # Get all events that depend on start_id
            rows = self.db_manager.execute_query('''
            SELECT dependent_event_id FROM event_dependencies
            WHERE prerequisite_event_id = ?
            ''', (start_id,))

            for row in rows:
                if has_path(row['dependent_event_id'], target_id, visited.copy()):
                    return True

            return False

        return has_path(dependent_id, prerequisite_id, set())

    def _update_dependent_event_dates(self, event_id: str):
        """Update event dates based on dependencies"""
        try:
            # Get all prerequisites for this event
            rows = self.db_manager.execute_query('''
            SELECT ed.prerequisite_event_id, ed.delay_days, ed.delay_hours,
                   e.date, e.date_end
            FROM event_dependencies ed
            JOIN academic_calendar_events e ON ed.prerequisite_event_id = e.id
            WHERE ed.dependent_event_id = ? AND ed.is_mandatory = TRUE
            ''', (event_id,))

            if not rows:
                return

            # Find the latest end date among prerequisites
            latest_end_date = None
            max_delay_days = 0
            max_delay_hours = 0

            for row in rows:
                prereq_end = row['date_end'] or row['date']
                if prereq_end:
                    prereq_date = datetime.strptime(prereq_end, "%Y-%m-%d")
                    if latest_end_date is None or prereq_date > latest_end_date:
                        latest_end_date = prereq_date
                        max_delay_days = row['delay_days']
                        max_delay_hours = row['delay_hours']

            if latest_end_date:
                # Calculate new start date
                new_start_date = latest_end_date + timedelta(
                    days=max_delay_days, hours=max_delay_hours
                )

                # Update the dependent event
                self.db_manager.execute_update('''
                UPDATE academic_calendar_events SET date_start = ?, last_modified = ?
                WHERE id = ? AND date_start < ?
                ''', (new_start_date.strftime("%Y-%m-%d"),
                     datetime.now().isoformat(), event_id,
                     new_start_date.strftime("%Y-%m-%d")))

        except Exception as e:
            logger.error(f"Failed to update dependent event dates: {e}")

    def create_workflow(self, workflow_name: str, description: str = None,
                       event_templates: List[Dict] = None) -> Tuple[bool, str]:
        """Create an event workflow template"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create workflows")

        try:
            workflow_id = str(uuid.uuid4())
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO event_workflows (id, workflow_name, description, template_data,
                                           is_active, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (workflow_id, workflow_name, description,
                     json.dumps(event_templates or []), True, user_id,
                     datetime.now().isoformat()))

            return True, f"Workflow created: {workflow_id}"

        except Exception as e:
            logger.error(f"Failed to create workflow: {e}")
            return False, f"Error creating workflow: {str(e)}"

    def calculate_automatic_deadlines(self, base_event_id: str,
                                    deadline_rules: List[Dict]) -> List[Dict]:
        """Calculate automatic deadlines based on rules"""
        try:
            # Get base event
            rows = self.db_manager.execute_query(
                "SELECT * FROM academic_calendar_events WHERE id = ?", (base_event_id,)
            )
            if not rows:
                return []

            base_event = dict(rows[0])
            base_date_str = base_event['date'] or base_event['date_start']
            if not base_date_str:
                return []

            base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
            calculated_deadlines = []

            for rule in deadline_rules:
                deadline_date = base_date - timedelta(
                    days=rule.get('days_before', 0),
                    hours=rule.get('hours_before', 0)
                )

                calculated_deadlines.append({
                    'name': rule.get('name', 'Deadline'),
                    'date': deadline_date.strftime("%Y-%m-%d"),
                    'description': rule.get('description', ''),
                    'event_type': rule.get('event_type', 'Deadline'),
                    'priority': rule.get('priority', 'medium')
                })

            return calculated_deadlines

        except Exception as e:
            logger.error(f"Failed to calculate deadlines: {e}")
            return []
