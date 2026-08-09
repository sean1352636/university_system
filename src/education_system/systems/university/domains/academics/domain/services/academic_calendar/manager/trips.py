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
                LEFT JOIN academic_calendar_events tce ON t.id = tce.trip_id
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
                FROM academic_calendar_events e
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
                UPDATE academic_calendar_events SET trip_id = NULL
                WHERE trip_id = ? AND id = ?
            ''', (trip_id, event_id))

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
                # Link trip to the calendar event (single canonical table):
                # tag the just-created academic_calendar_events row with the trip id.
                cursor.execute('''
                    UPDATE academic_calendar_events SET trip_id = ? WHERE id = ?
                ''', (trip_id, result['event_id']))
                conn.commit()

            conn.close()
            return result

        except Exception as e:
            logger.error(f"Error creating trip event: {e}")
            return {'success': False, 'message': f'Error: {str(e)}'}
