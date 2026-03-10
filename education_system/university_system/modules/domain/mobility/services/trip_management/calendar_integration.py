from ._common import sqlite3, get_text, logging, datetime, timedelta
from .database import safe_db_operation


def create_trip_calendar_event(calendar_manager):
    """Create a calendar event for a trip"""
    def create_event_operation(conn):
        cursor = conn.cursor()

        # Get trips without calendar events
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
        FROM trips t
        LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
        WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open')
        ORDER BY t.start_date
        ''')

        available_trips = cursor.fetchall()

        if not available_trips:
            print(get_text("mobility.trip_management.calendar.no_trips_available", "No trips available for calendar event creation."))
            return False

        print("\n" + get_text("mobility.trip_management.calendar.trips_without_events", "Trips without Calendar Events:"))
        print("-" * 70)
        for trip in available_trips:
            print(f"{trip[0]}: {trip[1]} to {trip[2]} ({trip[3]} - {trip[4]}) - {trip[5].title()}")

        try:
            trip_id = int(input(get_text("mobility.trip_management.calendar.enter_trip_id", "\nEnter Trip ID: ")))

            # Find selected trip
            selected_trip = None
            for trip in available_trips:
                if trip[0] == trip_id:
                    selected_trip = trip
                    break

            if not selected_trip:
                print(get_text("mobility.trip_management.calendar.invalid_selection", "Invalid trip selection."))
                return False

            # Create calendar event using the calendar manager
            result = calendar_manager.create_trip_event(trip_id)

            if result['success']:
                print(get_text("mobility.trip_management.calendar.event_created", "Calendar event created successfully!"))
                print(get_text("mobility.trip_management.calendar.event_id", "Event ID: {event_id}").format(event_id=result['event_id']))
            else:
                print(get_text("mobility.trip_management.calendar.event_failed", "Failed to create calendar event: {message}").format(message=result['message']))

            return True

        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
            return False

    return safe_db_operation(create_event_operation)

def view_trip_events_in_calendar(calendar_manager):
    """View trip events in the calendar"""
    try:
        # Get current user's trip events
        current_date = datetime.now().strftime('%Y-%m-%d')
        future_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

        events = calendar_manager.get_events_by_date_range(current_date, future_date, 'Trip')

        if not events:
            print(get_text("mobility.trip_management.calendar.no_events_found", "No trip events found in calendar."))
            return

        print("\n" + get_text("mobility.trip_management.calendar.events_title", "Trip Events in Calendar:"))
        print("=" * 80)
        print(f"{get_text('mobility.trip_management.headers.event_name', 'Event Name'):<30} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.end_date', 'End Date'):<12} {get_text('mobility.trip_management.headers.description', 'Description'):<25}")
        print("-" * 80)

        for event in events:
            start_date = event.get('date_start') or event.get('date', get_text("mobility.trip_management.common.tbd", "TBD"))
            end_date = event.get('date_end') or event.get('date', get_text("mobility.trip_management.common.tbd", "TBD"))
            description = (event.get('description') or '')[:24]

            print(f"{event['name'][:29]:<30} {start_date:<12} {end_date:<12} {description:<25}")

        print("=" * 80)

    except Exception as e:
        print(get_text("mobility.trip_management.errors.viewing_events", "Error viewing trip events: {error}").format(error=e))
