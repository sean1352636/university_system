"""Extracted AcademicCalendarManager events methods."""
import logging

logger = logging.getLogger(__name__)

from ._shared import *  # noqa: F401,F403


class EventsMixin:
    def add_event(self, name: str, date: Optional[str] = None,
                  date_start: Optional[str] = None, date_end: Optional[str] = None,
                  description: Optional[str] = None, event_type: str = 'Academic') -> Dict[str, Any]:
        """Add a new event to the calendar"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to add events")

        # Validate inputs
        if not name or not name.strip():
            raise ValidationError("Event name is required")

        if not date and not (date_start and date_end):
            raise ValidationError("Either date or date_start and date_end are required")

        if date and not ValidationUtils.validate_date(date):
            raise ValidationError("Invalid date format. Use YYYY-MM-DD")

        if date_start and not ValidationUtils.validate_date(date_start):
            raise ValidationError("Invalid start date format. Use YYYY-MM-DD")

        if date_end and not ValidationUtils.validate_date(date_end):
            raise ValidationError("Invalid end date format. Use YYYY-MM-DD")

        if date_start and date_end and date_start >= date_end:
            raise ValidationError("End date must be after start date")

        event_id = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None

        # Sanitize inputs
        name = ValidationUtils.sanitize_string(name, 255)
        description = ValidationUtils.sanitize_string(description or "", 1000)
        event_type = ValidationUtils.sanitize_string(event_type, 50)

        try:
            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO unified_events (
                    source_event_id, title, event_date, start_datetime, end_datetime, description, event_type, created_at, updated_at, created_by, source_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'academic_calendar')""",
                    (event_id, name, date, date_start, date_end,
                     description, event_type, current_time, current_time, user_id)
                )

                # Log the action
                self.audit_manager.log_change(
                    table_name='events',
                    record_id=event_id,
                    action='CREATE',
                    new_values={'name': name, 'event_type': event_type},
                    user_id=user_id
                )

            logger.info(f"Event '{name}' created with ID {event_id}")

            # Calendar is the canonical writer for academic periods —
            # publish so every scheduler refreshes its term-aware filters.
            # Holidays and exam windows in particular drive validation
            # gates in Module Scheduling, Exam, and Grade.
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(
                    EVENT_CALENDAR_CHANGED,
                    event_id=event_id, name=name, event_type=event_type,
                    date=date, date_start=date_start, date_end=date_end,
                    action="created",
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            return {
                'success': True,
                'message': f"Event '{name}' added successfully",
                'event_id': event_id
            }

        except Exception as e:
            logger.error(f"Failed to add event: {e}")
            raise DatabaseError(f"Failed to add event: {e}")

    def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to update events")

        if not event_id or not str(event_id).strip():
            raise ValidationError("Invalid event ID format")

        # Get existing event
        rows = self.db_manager.execute_query("SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,))
        if not rows:
            raise ValidationError(f"Event with ID {event_id} not found")

        existing_event = dict(rows[0])

        # Validate and sanitize updates
        allowed_fields = {'name', 'date', 'date_start', 'date_end', 'description', 'event_type'}
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            raise ValidationError(f"Invalid fields: {', '.join(invalid_fields)}")

        sanitized_updates = {}
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                if field in ['date', 'date_start', 'date_end']:
                    if not ValidationUtils.validate_date(str(value)):
                        raise ValidationError(f"Invalid {field} format. Use YYYY-MM-DD")
                    sanitized_updates[field] = str(value)
                elif field in ['name', 'event_type']:
                    sanitized_updates[field] = ValidationUtils.sanitize_string(str(value), 255)
                elif field == 'description':
                    sanitized_updates[field] = ValidationUtils.sanitize_string(str(value), 1000)

        if not sanitized_updates:
            return {'success': True, 'message': 'No changes to apply'}

        try:
            with self.db_manager.transaction():
                # Build update query
                set_clauses = []
                params = []

                # Calendar events live in unified_events. This UPDATE used to
                # target the retired academic_calendar_events table, which is
                # empty, so it matched no row and every edit was silently lost
                # while reporting success. Map the calendar's field names onto
                # the unified columns and require that a row actually changed.
                column_for = {
                    'name': 'title', 'date': 'event_date', 'date_start': 'start_datetime',
                    'date_end': 'end_datetime', 'description': 'description',
                    'event_type': 'event_type',
                }
                from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
                for field, value in sanitized_updates.items():
                    safe_field = validate_identifier(column_for[field], "column")
                    set_clauses.append("[" + safe_field + "] = ?")
                    params.append(value)

                set_clauses.append("[updated_at] = ?")
                params.append(datetime.now().isoformat())
                params.append(event_id)

                query = ("UPDATE [unified_events] SET " + ", ".join(set_clauses)
                         + " WHERE source_type = 'academic_calendar' AND source_event_id = ?")
                updated = self.db_manager.execute_update(query, tuple(params))
                if not updated:
                    raise DatabaseError(f"Event {event_id} was not updated")

                # Log the action
                user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                self.audit_manager.log_change(
                    table_name='events',
                    record_id=event_id,
                    action='UPDATE',
                    old_values={k: existing_event.get(k) for k in sanitized_updates.keys()},
                    new_values=sanitized_updates,
                    user_id=user_id
                )

            logger.info(f"Event {event_id} updated successfully")

            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(EVENT_CALENDAR_CHANGED,
                        event_id=event_id, action="updated")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            return {'success': True, 'message': 'Event updated successfully'}

        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            raise DatabaseError(f"Failed to update event: {e}")

    def delete_event(self, event_id: str) -> Dict[str, Any]:
        """Delete an event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to delete events")

        if not event_id or not str(event_id).strip():
            raise ValidationError("Invalid event ID format")

        # Get existing event for audit log
        rows = self.db_manager.execute_query("SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,))
        if not rows:
            raise ValidationError(f"Event with ID {event_id} not found")

        event_data = dict(rows[0])

        try:
            with self.db_manager.transaction():
                # Delete the event (cascade will handle related records)
                rows_affected = self.db_manager.execute_update("DELETE FROM unified_events WHERE source_type = 'academic_calendar' AND (source_event_id = ?)", (event_id,))

                if rows_affected > 0:
                    # Log the action
                    user_id = self.auth_manager.current_user['id'] if self.auth_manager.current_user else None
                    self.audit_manager.log_change(
                        table_name='events',
                        record_id=event_id,
                        action='DELETE',
                        old_values={'name': event_data.get('name'), 'event_type': event_data.get('event_type')},
                        user_id=user_id
                    )

            logger.info(f"Event {event_id} deleted successfully")

            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    publish, EVENT_CALENDAR_CHANGED,
                )
                publish(EVENT_CALENDAR_CHANGED,
                        event_id=event_id, action="deleted")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            return {'success': True, 'message': 'Event deleted successfully'}

        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            raise DatabaseError(f"Failed to delete event: {e}")

    def get_events_by_date_range(self, start_date: str, end_date: str,
                                event_type: Optional[str] = None) -> List[Dict]:
        """Get all events within a date range"""
        if not ValidationUtils.validate_date(start_date):
            raise ValidationError("Invalid start date format")

        if not ValidationUtils.validate_date(end_date):
            raise ValidationError("Invalid end date format")

        if start_date > end_date:
            raise ValidationError("End date must be after start date")

        try:
            query = """
                SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar')
                WHERE ((date BETWEEN ? AND ?)
                OR (date_start <= ? AND date_end >= ?)
                OR (date_start BETWEEN ? AND ?)
                OR (date_end BETWEEN ? AND ?))
            """
            params = [start_date, end_date, end_date, start_date,
                     start_date, end_date, start_date, end_date]

            if event_type:
                event_type = ValidationUtils.sanitize_string(event_type, 50)
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY COALESCE(date, date_start) LIMIT ?"
            params.append(self.config.max_search_results)

            rows = self.db_manager.execute_query(query, tuple(params))
            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get events by date range: {e}")
            raise DatabaseError(f"Failed to retrieve events: {e}")

    def view_calendar(self, academic_year: Optional[str] = None, semester: Optional[str] = None) -> Tuple[bool, List[Dict]]:
        """Retrieve the calendar information for an academic year and/or semester"""
        try:
            query = """
                SELECT s.name AS semester_name, s.start_date AS semester_start, s.end_date AS semester_end,
                       e.name AS event_name, e.date, e.date_start, e.date_end, e.description, e.event_type
                FROM semesters s
                LEFT JOIN (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') e ON (
                    (e.date BETWEEN s.start_date AND s.end_date) OR
                    (e.date_start BETWEEN s.start_date AND s.end_date) OR
                    (e.date_end BETWEEN s.start_date AND s.end_date)
                )
            """
            conditions = []
            params = []

            if academic_year:
                academic_year = ValidationUtils.sanitize_string(academic_year, 20)
                conditions.append("s.academic_year_id = ?")
                params.append(academic_year)

            if semester:
                semester = ValidationUtils.sanitize_string(semester, 50)
                conditions.append("s.name = ?")
                params.append(semester)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY s.start_date, COALESCE(e.date, e.date_start)"

            rows = self.db_manager.execute_query(query, tuple(params))

            if not rows:
                return False, "No calendar data found for the given selection."

            result = [dict(row) for row in rows]
            return True, result

        except Exception as e:
            logger.error(f"Failed to view calendar: {e}")
            return False, f"Database error: {str(e)}"

    def calendar_sync(self, ical_url: str, local_calendar: Optional[str] = None) -> Dict[str, Any]:
        """Sync external iCal feed with security improvements"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to sync calendars")

        if not REQUESTS_AVAILABLE:
            raise CalendarError("Requests library not available. Install with: pip install requests")

        if not ICS_AVAILABLE:
            raise CalendarError("ICS library not available. Install with: pip install ics")

        try:
            # Validate URL
            if not ValidationUtils.validate_url(ical_url):
                raise ValidationError("Invalid URL format")

            # Fetch external calendar with timeout
            response = requests.get(ical_url, timeout=30, headers={'User-Agent': 'Academic Calendar Manager'})
            response.raise_for_status()

            # Check response size
            if len(response.content) > self.config.max_file_size:
                raise ValidationError("Calendar file too large")

            # Parse calendar
            try:
                ext_cal = ICSCalendar(response.text)
            except Exception as e:
                raise ValidationError(f"Invalid iCal format: {e}")

            # Get existing events for conflict detection
            existing_events = self._get_existing_events_index()

            synced = 0
            conflicts = []
            skipped = 0
            current_time = datetime.now().isoformat()
            user_id = self.auth_manager.current_user['id']

            with self.db_manager.transaction():
                for event in ext_cal.events:
                    try:
                        # Skip holidays/breaks
                        event_name = str(event.name) if hasattr(event, 'name') and event.name else ""
                        if any(keyword in event_name.lower() for keyword in ['holiday', 'break']):
                            skipped += 1
                            continue

                        # Extract event details safely
                        if not hasattr(event, 'begin') or not event.begin:
                            skipped += 1
                            continue

                        start_dt = event.begin.datetime if hasattr(event.begin, 'datetime') else None
                        end_dt = event.end.datetime if hasattr(event, 'end') and hasattr(event.end, 'datetime') else None

                        if not start_dt:
                            skipped += 1
                            continue

                        # Convert to local timezone if needed
                        if hasattr(start_dt, 'tzinfo') and start_dt.tzinfo:
                            start_dt = start_dt.replace(tzinfo=None)
                        if end_dt and hasattr(end_dt, 'tzinfo') and end_dt.tzinfo:
                            end_dt = end_dt.replace(tzinfo=None)

                        # Check for conflicts
                        conflict_events = self._check_event_conflicts(start_dt, end_dt, existing_events)
                        if conflict_events:
                            conflicts.extend([{
                                'external': event_name,
                                'conflicts_with': conflict['name'],
                                'when': start_dt.strftime("%Y-%m-%d")
                            } for conflict in conflict_events])

                        # Generate safe event ID
                        event_uid = getattr(event, 'uid', None)
                        if event_uid:
                            event_id = ValidationUtils.sanitize_string(str(event_uid), 36)
                        else:
                            event_id = str(uuid.uuid4())

                        # Check if event already exists
                        if not self._event_exists(event_id):
                            description = ValidationUtils.sanitize_string(
                                str(event.description) if hasattr(event, 'description') and event.description else "",
                                1000
                            )

                            self.db_manager.execute_update(
                                """INSERT INTO unified_events (
                    source_event_id, title, start_datetime, end_datetime, description, event_type, created_at, updated_at, created_by, source_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'academic_calendar')""",
                                (event_id,
                                 ValidationUtils.sanitize_string(event_name, 255),
                                 start_dt.strftime("%Y-%m-%d"),
                                 end_dt.strftime("%Y-%m-%d") if end_dt else start_dt.strftime("%Y-%m-%d"),
                                 description,
                                 'Academic',
                                 current_time, current_time, user_id)
                            )
                            synced += 1

                    except Exception as e:
                        logger.warning(f"Failed to process event: {e}")
                        skipped += 1
                        continue

            # Get upcoming deadlines
            upcoming_deadlines = self._get_upcoming_deadlines()

            result = {
                'success': True,
                'synced': synced,
                'skipped_holidays': skipped,
                'conflicts': conflicts,
                'upcoming_deadlines': upcoming_deadlines
            }

            logger.info(f"Calendar sync completed: {synced} synced, {skipped} skipped")
            return result

        except Exception as e:
            if REQUESTS_AVAILABLE and isinstance(e, requests.RequestException):
                logger.error(f"Failed to fetch remote calendar: {e}")
                raise CalendarError(f"Failed to fetch remote calendar: {e}")
            logger.error(f"Calendar sync failed: {e}")
            raise CalendarError(f"Calendar sync failed: {e}")

    def _get_existing_events_index(self) -> List[Dict]:
        """Get index of existing events for conflict detection"""
        query = "SELECT id, name, date, date_start, date_end, event_type FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar')"
        rows = self.db_manager.execute_query(query)

        events = []
        for row in rows:
            try:
                start_str = row['date'] or row['date_start']
                end_str = row['date'] or row['date_end']

                if start_str:
                    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_str, "%Y-%m-%d") if end_str else start_dt

                    events.append({
                        'id': row['id'],
                        'name': row['name'],
                        'start': start_dt,
                        'end': end_dt,
                        'type': row['event_type']
                    })
            except (ValueError, TypeError):
                continue

        return events

    def _check_event_conflicts(self, start_dt: datetime, end_dt: datetime,
                              existing_events: List[Dict]) -> List[Dict]:
        """Check for scheduling conflicts"""
        conflicts = []

        if not end_dt:
            end_dt = start_dt

        for event in existing_events:
            if event['type'].lower() in ('assignment', 'exam'):
                # Check for overlap
                if not (end_dt <= event['start'] or start_dt >= event['end']):
                    conflicts.append(event)

        return conflicts

    def _event_exists(self, event_id: str) -> bool:
        """Check if event already exists"""
        rows = self.db_manager.execute_query("SELECT 1 FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,))
        return len(rows) > 0

    def _get_upcoming_deadlines(self, days_ahead: int = 7) -> List[Dict]:
        """Get upcoming assignment deadlines"""
        end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        current_date = datetime.now().strftime("%Y-%m-%d")

        query = """
            SELECT name, COALESCE(date, date_start) as due_date
            FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar')
            WHERE event_type = 'Assignment'
            AND COALESCE(date, date_start) BETWEEN ? AND ?
            ORDER BY COALESCE(date, date_start)
        """

        rows = self.db_manager.execute_query(query, (current_date, end_date))
        return [{'name': row['name'], 'due': row['due_date']} for row in rows]

    def _upsert_event(self, event_id: str, name: str,
                      date_start: str, date_end: str,
                      description: str = "", event_type: str = "Academic"):
        """Insert or update one academic_calendar_events row keyed on
        the deterministic *event_id*. Used to mirror academic years and
        semester sub-periods onto the calendar so they show up alongside
        exams, holidays, and ad-hoc events."""
        now = datetime.now().isoformat()
        existing = self.db_manager.execute_query(
            "SELECT id FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?",
            (event_id,),
        )
        if existing:
            self.db_manager.execute_update(
                """UPDATE unified_events SET title = ?, start_datetime = ?, end_datetime = ?,
                       description = ?, event_type = ?, updated_at = ? WHERE source_type = 'academic_calendar' AND (source_event_id = ?)""",
                (name, date_start, date_end, description, event_type, now,
                 event_id),
            )
        else:
            self.db_manager.execute_update(
                """INSERT INTO unified_events (
                    source_event_id, title, start_datetime, end_datetime, description, event_type, created_at, updated_at, source_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'academic_calendar')""",
                (event_id, name, date_start, date_end, description,
                 event_type, now, now),
            )

    def _sync_academic_year_to_calendar(self, year_id: str,
                                         start_date: str,
                                         end_date: str) -> None:
        """Push an academic year onto the calendar as one spanning event."""
        try:
            self._upsert_event(
                event_id=f"AY-{year_id}",
                name=f"Academic Year {year_id}",
                date_start=start_date,
                date_end=end_date,
                description=f"Academic year {year_id}",
                event_type="Academic Year",
            )
        except Exception as exc:
            logger.warning("Failed to sync academic year to calendar: %s", exc)

    def _sync_semester_to_calendar(self, semester_id: int, name: str,
                                    start_date: str, end_date: str,
                                    registration_start: Optional[str] = None,
                                    registration_end: Optional[str] = None,
                                    exams_start: Optional[str] = None,
                                    exams_end: Optional[str] = None) -> None:
        """Push a semester onto the calendar as up to three events:
        the semester period, the registration window, and the final
        exams window. Each gets a deterministic id so re-syncing
        replaces rather than duplicates."""
        try:
            self._upsert_event(
                event_id=f"SEM-{semester_id}-PERIOD",
                name=f"{name} Semester",
                date_start=start_date,
                date_end=end_date,
                description=f"{name} semester period",
                event_type="Semester",
            )
            if registration_start and registration_end:
                self._upsert_event(
                    event_id=f"SEM-{semester_id}-REG",
                    name=f"{name} Registration / Add-Drop",
                    date_start=registration_start,
                    date_end=registration_end,
                    description=(
                        f"Registration and add/drop window for {name} "
                        "semester."
                    ),
                    event_type="Registration",
                )
            if exams_start and exams_end:
                self._upsert_event(
                    event_id=f"SEM-{semester_id}-EXAMS",
                    name=f"{name} Final Exams",
                    date_start=exams_start,
                    date_end=exams_end,
                    description=f"Final exam period for {name} semester.",
                    event_type="Exam Period",
                )
        except Exception as exc:
            logger.warning("Failed to sync semester to calendar: %s", exc)
