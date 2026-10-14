"""Extracted AcademicCalendarManager trips methods."""

from ._shared import *  # noqa: F401,F403


class TripsMixin:
    def get_trips_for_calendar_integration(self):
        """Get trips that can be integrated with calendar"""
        try:
            # sqlite3 is imported globally from education_system.systems.university.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            # Get trips that don't have calendar events yet
            cursor.execute('''
                SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
                FROM trips t
                LEFT JOIN (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') tce ON t.id = tce.trip_id
                WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open', 'confirmed')
                ORDER BY t.start_date
            ''')

            trips = cursor.fetchall()
            conn.close()

            return [
                {
                    'id': trip[0],
                    'name': trip[1],
                    'destination': trip[2],
                    'start_date': trip[3],
                    'end_date': trip[4],
                    'status': trip[5]
                }
                for trip in trips
            ]

        except Exception as e:
            logger.error(f"Error getting trips for calendar integration: {e}")
            return []

    def get_calendar_events_for_trip(self, trip_id):
        """Get calendar events linked to a specific trip"""
        try:
            # sqlite3 is imported globally from education_system.systems.university.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                SELECT e.id, e.name, e.date, e.date_start, e.date_end, e.description, e.event_type
                FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') e
                WHERE e.trip_id = ?
                ORDER BY COALESCE(e.date, e.date_start)
            ''', (trip_id,))

            events = cursor.fetchall()
            conn.close()

            return [
                {
                    'id': event[0],
                    'name': event[1],
                    'date': event[2],
                    'date_start': event[3],
                    'date_end': event[4],
                    'description': event[5],
                    'event_type': event[6]
                }
                for event in events
            ]

        except Exception as e:
            logger.error(f"Error getting calendar events for trip: {e}")
            return []

    def remove_trip_calendar_link(self, trip_id, event_id):
        """Remove the link between a trip and calendar event"""
        try:
            # sqlite3 is imported globally from education_system.systems.university.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE unified_events SET trip_id = NULL WHERE source_type = 'academic_calendar' AND (trip_id = ? AND source_event_id = ?)''', (trip_id, event_id))

            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                logger.info(f"Removed link between trip {trip_id} and event {event_id}")
                return {'success': True, 'message': 'Link removed successfully'}
            else:
                return {'success': False, 'message': 'Link not found'}

        except Exception as e:
            logger.error(f"Error removing trip-calendar link: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def create_trip_event(self, trip_id, event_details=None):
        """Create a calendar event for a trip"""
        if not self.auth_manager or not self.auth_manager.current_user:
            return {'success': False, 'message': 'Authentication required'}

        if not self.auth_manager.check_permission('manage_schedules'):
            return {'success': False, 'message': 'Insufficient permissions'}

        try:
            # Get trip details from trip_management
            # sqlite3 is imported globally from education_system.systems.university.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trips WHERE id = ?', (trip_id,))
            trip = cursor.fetchone()

            if not trip:
                conn.close()
                return {'success': False, 'message': 'Trip not found'}

            # Create event details
            trip_id_val, trip_name, description, destination, start_date, end_date = trip[:6]

            event_name = event_details.get('name', f"Trip: {trip_name}") if event_details else f"Trip: {trip_name}"
            event_description = event_details.get('description', f"Trip to {destination} - {description or 'No description'}") if event_details else f"Trip to {destination}"

            # Create the calendar event
            result = self.add_event(
                name=event_name,
                date_start=start_date,
                date_end=end_date,
                description=event_description,
                event_type='Trip'
            )

            if result['success']:
                # Link trip to the calendar event: tag the just-created
                # calendar event (in unified_events) with the trip id.
                cursor.execute('''
                    UPDATE unified_events SET trip_id = ? WHERE source_type = 'academic_calendar' AND (source_event_id = ?)''', (trip_id, result['event_id']))
                conn.commit()

            conn.close()
            return result

        except Exception as e:
            logger.error(f"Error creating trip event: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def create_trip_from_event(self, event_id, *, name, start_date, end_date,
                               destination, description=None,
                               max_participants=50, cost=0.0,
                               created_by=None):
        """Create a trip for a calendar event of type "Trip", and link them.

        This is the *forward* direction: the calendar is where a trip now
        starts life, so a Trip-typed event registers itself in Trip
        Management rather than being created there and back-filled into the
        calendar. ``create_trip_event`` (the reverse) is retired.

        Returns ``{'success': bool, 'trip_id': int|None, 'message': str}``.
        """
        if not destination or not str(destination).strip():
            return {'success': False, 'trip_id': None,
                    'message': 'A destination is required to create a trip.'}
        # trips.start_date/end_date are NOT NULL; a single-date event is a
        # one-day trip rather than an error.
        start_date = start_date or end_date
        end_date = end_date or start_date
        if not start_date:
            return {'success': False, 'trip_id': None,
                    'message': 'A date is required to create a trip.'}

        try:
            now = datetime.now().isoformat()
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO trips
                   (trip_name, description, destination, start_date, end_date,
                    max_participants, cost, status, created_by,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'planning', ?, ?, ?)''',
                (str(name).strip(), description, str(destination).strip(),
                 start_date, end_date, int(max_participants or 50),
                 float(cost or 0.0), created_by, now, now))
            trip_id = cursor.lastrowid

            # Link the event back to the trip so the two stay associated.
            try:
                # unified_events, not the retired academic_calendar_events
                # table: writing there matched no row, so the trip was created
                # but never linked back to its calendar event.
                cursor.execute(
                    "UPDATE unified_events SET trip_id = ? "
                    "WHERE source_type = 'academic_calendar' AND source_event_id = ?",
                    (trip_id, event_id))
            except Exception:
                logger.warning("Could not link event %s to trip %s",
                               event_id, trip_id, exc_info=True)

            conn.commit()
            conn.close()
            logger.info("Created trip %s from calendar event %s", trip_id, event_id)
            return {'success': True, 'trip_id': trip_id,
                    'message': f'Trip created and linked (trip #{trip_id}).'}

        except Exception as e:
            logger.error(f"Error creating trip from event {event_id}: {e}")
            return {'success': False, 'trip_id': None,
                    'message': f'Could not create the trip: {e}'}
