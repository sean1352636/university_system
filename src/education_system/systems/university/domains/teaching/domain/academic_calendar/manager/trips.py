"""Extracted AcademicCalendarManager trips methods.

Trip records belong to Trip Management (operations). These methods read
them for the calendar and write through ``services.bus.trip_bus`` — the
cross-domain port onto Trip Management's own writers — so a trip made from
a calendar event gets the same history, status and calendar rules as one
made in Trip Management.
"""

import builtins

from ._shared import *  # noqa: F401,F403

# Trip statuses that can still appear on the calendar (cancelled and
# archived trips are taken off it).
_CALENDAR_TRIP_STATUSES = ('proposed', 'planning', 'approved', 'open', 'full', 'closed',
                           'in_progress')


def _trip_bus():
    from education_system.systems.university.services.bus import trip_bus
    return trip_bus


class TripsMixin:
    def get_trips_for_calendar_integration(self):
        """Get trips that can be integrated with calendar"""
        conn = None
        try:
            # sqlite3 is imported globally from education_system.systems.university.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            # Trips that don't have calendar events yet
            marks = ", ".join("?" * len(_CALENDAR_TRIP_STATUSES))
            cursor.execute(f'''
                SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
                FROM trips t
                WHERE t.status IN ({marks})
                  AND NOT EXISTS (SELECT 1 FROM unified_events e
                                  WHERE e.source_type = 'academic_calendar' AND e.trip_id = t.id)
                ORDER BY t.start_date
            ''', _CALENDAR_TRIP_STATUSES)

            trips = cursor.fetchall()

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
        finally:
            if conn is not None:
                conn.close()

    def get_calendar_events_for_trip(self, trip_id):
        """Get calendar events linked to a specific trip"""
        conn = None
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
        finally:
            if conn is not None:
                conn.close()

    def remove_trip_calendar_link(self, trip_id, event_id):
        """Remove the link between a trip and calendar event"""
        conn = None
        try:
            # sqlite3 is imported globally from education_system.systems.university.infrastructure.database.db
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute('''
                UPDATE unified_events SET trip_id = NULL WHERE source_type = 'academic_calendar' AND (trip_id = ? AND source_event_id = ?)''', (trip_id, event_id))

            conn.commit()
            deleted = cursor.rowcount > 0

            if deleted:
                logger.info(f"Removed link between trip {trip_id} and event {event_id}")
                return {'success': True, 'message': 'Link removed successfully'}
            else:
                return {'success': False, 'message': 'Link not found'}

        except Exception as e:
            if conn is not None:
                conn.rollback()
            logger.error(f"Error removing trip-calendar link: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
        finally:
            if conn is not None:
                conn.close()

    def create_trip_event(self, trip_id, event_details=None):
        """Create (or refresh) the calendar event for a trip.

        Trip Management writes a trip's event itself when the trip is
        created, changed or archived; this is the manual backfill for a trip
        that has none, and uses the same writer
        (``calendar_integration.sync_trip_calendar_event``) so there is one
        shape of trip event. ``event_details`` is accepted for older callers;
        the event's name and description come from the trip.
        """
        if not self.auth_manager or not self.auth_manager.current_user:
            return {'success': False, 'message': 'Authentication required'}

        if not self.auth_manager.check_permission('manage_schedules'):
            return {'success': False, 'message': 'Insufficient permissions'}

        try:
            event_id = _trip_bus().refresh_trip_calendar_event(
                trip_id, changed_by=self.auth_manager.current_user.get('username'))
            if not event_id:
                return {'success': False, 'message': 'The calendar is unavailable'}
            return {'success': True, 'event_id': event_id, 'message': 'Calendar event saved'}

        except ValueError as e:
            return {'success': False, 'message': str(e)}
        except Exception as e:
            logger.error(f"Error creating trip event: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}

    def create_trip_from_event(self, event_id, *, name, start_date, end_date,
                               destination, description=None,
                               max_participants=50, cost=0.0,
                               created_by=None):
        """Create a trip for a calendar event of type "Trip", and link them.

        This is the *forward* direction: the calendar is where a trip can
        start life, so a Trip-typed event registers itself in Trip
        Management. The signed-in user needs ``create_trips`` (or
        ``manage_trips``) — the same right Trip Management asks for. The trip
        starts 'proposed' and the event becomes its calendar entry (one
        transaction: trip, link and event refresh commit together).

        Returns ``{'success': bool, 'trip_id': int|None, 'message': str}``.
        """
        auth = self.auth_manager
        if not auth or not getattr(auth, 'current_user', None):
            return {'success': False, 'trip_id': None, 'message': 'Authentication required'}
        if not (auth.check_permission('create_trips') or auth.check_permission('manage_trips')):
            return {'success': False, 'trip_id': None,
                    'message': 'You do not have permission to create trips.'}

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
            trip = _trip_bus().create_trip_from_calendar_event(
                auth, event_id, trip_name=str(name).strip(), description=description,
                destination=str(destination).strip(), start_date=start_date,
                end_date=end_date, max_participants=int(max_participants or 50),
                cost=float(cost or 0.0))
            logger.info("Created trip %s from calendar event %s", trip['id'], event_id)
            return {'success': True, 'trip_id': trip['id'],
                    'message': f"Trip created and linked (trip #{trip['id']})."}

        except (ValueError, builtins.PermissionError) as e:
            return {'success': False, 'trip_id': None, 'message': str(e)}
        except Exception as e:
            logger.error(f"Error creating trip from event {event_id}: {e}")
            return {'success': False, 'trip_id': None,
                    'message': f'Could not create the trip: {e}'}
