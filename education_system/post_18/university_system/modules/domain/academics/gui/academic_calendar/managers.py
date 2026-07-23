import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.exceptions import ValidationError, DatabaseError
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.validators import validate_date
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.utils import convert_to_user_error

# Import DatabaseManager for type hints and to access database operations.
from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.database import DatabaseManager

gui_logger = logging.getLogger(__name__)

class RecurringEventManager:
    """
    Manages recurring events with flexible recurrence patterns

    Supports:
    - Daily, weekly, monthly, yearly recurrence
    - Custom recurrence intervals
    - End date or occurrence count limits
    - Exception dates (skip specific occurrences)
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize recurring event manager

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        gui_logger.info("RecurringEventManager initialized")

    def create_recurring_event(self, event_data: Dict[str, Any],
                               recurrence_pattern: str,
                               interval: int = 1,
                               end_date: Optional[datetime] = None,
                               occurrences: Optional[int] = None) -> List[int]:
        """
        Create recurring event with specified pattern

        Args:
            event_data: Base event data (title, description, etc.)
            recurrence_pattern: 'daily', 'weekly', 'monthly', 'yearly'
            interval: Recurrence interval (e.g., every 2 weeks)
            end_date: Optional end date for recurrence
            occurrences: Optional number of occurrences to create

        Returns:
            List[int]: List of created event IDs

        Raises:
            ValidationError: If parameters are invalid

        Example:
            event_ids = recurring_mgr.create_recurring_event(
                {
                    'title': 'Weekly Team Meeting',
                    'description': 'Team sync',
                    'start_time': '10:00',
                    'duration': 60
                },
                recurrence_pattern='weekly',
                interval=1,
                occurrences=10
            )
        """
        # Validate recurrence pattern
        valid_patterns = ['daily', 'weekly', 'monthly', 'yearly']
        if recurrence_pattern not in valid_patterns:
            raise ValidationError.invalid_format(
                'recurrence_pattern',
                f"One of: {', '.join(valid_patterns)}",
                recurrence_pattern
            )

        # Validate that either end_date or occurrences is specified
        if end_date is None and occurrences is None:
            raise ValidationError(
                "Either end_date or occurrences must be specified",
                field="recurrence"
            )

        # Generate recurring occurrences
        event_dates = self._generate_recurring_occurrences(
            start_date=event_data.get('date'),
            pattern=recurrence_pattern,
            interval=interval,
            end_date=end_date,
            occurrences=occurrences
        )

        # Create events for each occurrence
        event_ids = []
        try:
            with self.db.transaction() as conn:
                for event_date in event_dates:
                    # Create event with specific date
                    event_copy = event_data.copy()
                    event_copy['date'] = event_date.strftime('%Y-%m-%d')

                    cursor = conn.execute(
                        """INSERT INTO scheduled_events
                           (title, description, date, start_time, end_time, location,
                            event_type, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            event_copy.get('title'),
                            event_copy.get('description'),
                            event_copy['date'],
                            event_copy.get('start_time'),
                            event_copy.get('end_time'),
                            event_copy.get('location'),
                            event_copy.get('event_type', 'recurring'),
                            datetime.now().isoformat()
                        )
                    )
                    event_ids.append(cursor.lastrowid)

            gui_logger.info(
                f"Created {len(event_ids)} recurring events: {recurrence_pattern}, "
                f"interval: {interval}"
            )
            return event_ids

        except Exception as e:
            raise convert_to_user_error(e, {'operation': 'create_recurring_events'})

    def _generate_recurring_occurrences(self, start_date: str, pattern: str,
                                       interval: int, end_date: Optional[datetime],
                                       occurrences: Optional[int]) -> List[datetime]:
        """
        Generate list of dates for recurring event

        Args:
            start_date: Start date string (YYYY-MM-DD)
            pattern: Recurrence pattern
            interval: Recurrence interval
            end_date: Optional end date
            occurrences: Optional number of occurrences

        Returns:
            List[datetime]: List of occurrence dates
        """
        # Parse start date
        is_valid, current_date = validate_date(start_date)
        if not is_valid:
            raise ValidationError.invalid_format('start_date', 'YYYY-MM-DD', start_date)

        occurrence_dates = []
        count = 0

        # Determine delta based on pattern
        delta_map = {
            'daily': lambda i: timedelta(days=i),
            'weekly': lambda i: timedelta(weeks=i),
            'monthly': lambda i: timedelta(days=30 * i),  # Approximate
            'yearly': lambda i: timedelta(days=365 * i)  # Approximate
        }

        delta_func = delta_map[pattern]

        # Generate occurrences
        while True:
            # Check if we've reached the limit
            if occurrences and count >= occurrences:
                break
            if end_date and current_date > end_date:
                break

            occurrence_dates.append(current_date)
            count += 1

            # Move to next occurrence
            current_date = current_date + delta_func(interval)

        return occurrence_dates


class EventDependencyManager:
    """
    Manages event dependencies and workflows

    Features:
    - Event dependencies (prerequisite events)
    - Circular dependency detection
    - Automatic deadline calculation
    - Workflow creation
    - Dependency-based date updates
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize event dependency manager

        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self._create_dependency_tables()
        gui_logger.info("EventDependencyManager initialized")

    def _create_dependency_tables(self):
        """Create tables for event dependencies if they don't exist"""
        try:
            with self.db.transaction() as conn:
                # Event dependencies table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS event_dependencies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        depends_on_event_id INTEGER NOT NULL,
                        dependency_type TEXT DEFAULT 'finish_to_start',
                        lag_days INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (event_id) REFERENCES scheduled_events(id) ON DELETE CASCADE,
                        FOREIGN KEY (depends_on_event_id) REFERENCES scheduled_events(id) ON DELETE CASCADE,
                        UNIQUE(event_id, depends_on_event_id)
                    )
                """)

                # Event workflows table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS event_workflows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workflow_name TEXT NOT NULL,
                        description TEXT,
                        created_at TEXT NOT NULL
                    )
                """)

                # Workflow events table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS workflow_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        workflow_id INTEGER NOT NULL,
                        event_id INTEGER NOT NULL,
                        sequence_order INTEGER NOT NULL,
                        FOREIGN KEY (workflow_id) REFERENCES event_workflows(id) ON DELETE CASCADE,
                        FOREIGN KEY (event_id) REFERENCES scheduled_events(id) ON DELETE CASCADE
                    )
                """)

        except Exception as e:
            gui_logger.error(f"Failed to create dependency tables: {e}")

    def add_event_dependency(self, event_id: int, depends_on_event_id: int,
                            dependency_type: str = 'finish_to_start',
                            lag_days: int = 0) -> int:
        """
        Add dependency between two events

        Args:
            event_id: ID of dependent event
            depends_on_event_id: ID of prerequisite event
            dependency_type: Type of dependency ('finish_to_start', 'start_to_start')
            lag_days: Number of days lag between events

        Returns:
            int: Dependency ID

        Raises:
            ValidationError: If circular dependency detected

        Example:
            # Exam depends on lecture finishing
            dep_mgr.add_event_dependency(
                event_id=exam_id,
                depends_on_event_id=lecture_id,
                dependency_type='finish_to_start',
                lag_days=1
            )
        """
        # Check for circular dependencies
        if self._creates_circular_dependency(event_id, depends_on_event_id):
            raise ValidationError(
                f"Circular dependency detected: Event {event_id} cannot depend on {depends_on_event_id}",
                field="dependency"
            )

        try:
            with self.db.transaction() as conn:
                cursor = conn.execute(
                    """INSERT INTO event_dependencies
                       (event_id, depends_on_event_id, dependency_type, lag_days, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        event_id,
                        depends_on_event_id,
                        dependency_type,
                        lag_days,
                        datetime.now().isoformat()
                    )
                )
                dependency_id = cursor.lastrowid

            # Update dependent event dates if needed
            self._update_dependent_event_dates(event_id)

            gui_logger.info(
                f"Event dependency added: {event_id} depends on {depends_on_event_id}"
            )
            return dependency_id

        except Exception as e:
            raise convert_to_user_error(e, {'table': 'event_dependencies'})

    def _creates_circular_dependency(self, event_id: int, depends_on_event_id: int) -> bool:
        """
        Check if adding dependency would create circular reference

        Args:
            event_id: ID of dependent event
            depends_on_event_id: ID of prerequisite event

        Returns:
            bool: True if circular dependency would be created
        """
        # BFS to detect cycles
        visited = set()
        queue = [depends_on_event_id]

        while queue:
            current_id = queue.pop(0)

            if current_id == event_id:
                return True

            if current_id in visited:
                continue

            visited.add(current_id)

            # Get dependencies of current event
            try:
                dependencies = self.db.execute_query(
                    "SELECT depends_on_event_id FROM event_dependencies WHERE event_id = ?",
                    (current_id,)
                )
                queue.extend([dep['depends_on_event_id'] for dep in dependencies])
            except Exception as e:
                gui_logger.debug(f"Failed to retrieve event dependencies: {e}")

        return False

    def _update_dependent_event_dates(self, event_id: int):
        """
        Update dates of dependent events based on dependencies

        Args:
            event_id: ID of event that was updated
        """
        try:
            # Get all events that depend on this event
            dependents = self.db.execute_query(
                """SELECT ed.event_id, ed.dependency_type, ed.lag_days,
                          e.date as dependent_date,
                          pe.date as prerequisite_date
                   FROM event_dependencies ed
                   JOIN scheduled_events e ON ed.event_id = e.id
                   JOIN scheduled_events pe ON ed.depends_on_event_id = pe.id
                   WHERE ed.depends_on_event_id = ?""",
                (event_id,)
            )

            for dep in dependents:
                # Calculate new date based on dependency type
                prereq_date = datetime.strptime(dep['prerequisite_date'], '%Y-%m-%d')
                new_date = prereq_date + timedelta(days=dep['lag_days'])

                if dep['dependency_type'] == 'finish_to_start':
                    new_date += timedelta(days=1)  # Start day after finish

                # Update dependent event date
                self.db.execute_update(
                    "UPDATE scheduled_events SET date = ? WHERE id = ?",
                    (new_date.strftime('%Y-%m-%d'), dep['event_id'])
                )

        except Exception as e:
            gui_logger.warning(f"Failed to update dependent event dates: {e}")

    def create_workflow(self, workflow_name: str, description: str,
                       event_ids: List[int]) -> int:
        """
        Create event workflow with ordered events

        Args:
            workflow_name: Name of workflow
            description: Workflow description
            event_ids: List of event IDs in sequence order

        Returns:
            int: Workflow ID

        Example:
            workflow_id = dep_mgr.create_workflow(
                "Course Semester Flow",
                "Complete semester timeline",
                [orientation_id, lecture1_id, midterm_id, lecture2_id, final_id]
            )
        """
        try:
            with self.db.transaction() as conn:
                # Create workflow
                cursor = conn.execute(
                    """INSERT INTO event_workflows
                       (workflow_name, description, created_at)
                       VALUES (?, ?, ?)""",
                    (workflow_name, description, datetime.now().isoformat())
                )
                workflow_id = cursor.lastrowid

                # Add events to workflow
                for sequence_order, event_id in enumerate(event_ids):
                    conn.execute(
                        """INSERT INTO workflow_events
                           (workflow_id, event_id, sequence_order)
                           VALUES (?, ?, ?)""",
                        (workflow_id, event_id, sequence_order)
                    )

            gui_logger.info(f"Workflow created: {workflow_name} with {len(event_ids)} events")
            return workflow_id

        except Exception as e:
            raise convert_to_user_error(e, {'table': 'event_workflows'})

    def calculate_automatic_deadlines(self, workflow_id: int, start_date: datetime,
                                     event_durations: Dict[int, int]):
        """
        Calculate and set automatic deadlines for workflow events

        Args:
            workflow_id: Workflow ID
            start_date: Start date for workflow
            event_durations: Dict mapping event_id to duration in days

        Example:
            dep_mgr.calculate_automatic_deadlines(
                workflow_id=1,
                start_date=datetime(2025, 9, 1),
                event_durations={
                    orientation_id: 1,
                    lecture1_id: 14,
                    midterm_id: 1,
                    lecture2_id: 14,
                    final_id: 1
                }
            )
        """
        try:
            # Get workflow events in order
            events = self.db.execute_query(
                """SELECT event_id
                   FROM workflow_events
                   WHERE workflow_id = ?
                   ORDER BY sequence_order""",
                (workflow_id,)
            )

            current_date = start_date

            with self.db.transaction() as conn:
                for event in events:
                    event_id = event['event_id']
                    duration = event_durations.get(event_id, 1)

                    # Update event date
                    conn.execute(
                        "UPDATE scheduled_events SET date = ? WHERE id = ?",
                        (current_date.strftime('%Y-%m-%d'), event_id)
                    )

                    # Move to next event start date
                    current_date += timedelta(days=duration)

            gui_logger.info(f"Automatic deadlines calculated for workflow {workflow_id}")

        except Exception as e:
            gui_logger.error(f"Failed to calculate automatic deadlines: {e}")


