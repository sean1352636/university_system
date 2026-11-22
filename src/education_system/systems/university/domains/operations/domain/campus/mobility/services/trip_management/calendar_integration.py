import uuid

from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, timedelta

# Calendar rows written for trips carry this event_type so the scheduling
# GUIs and ``get_events_by_date_range(..., 'Trip')`` pick them up.
TRIP_EVENT_TYPE = 'Trip'


def _trip_event_fields(trip_name, destination, cost):
    """Shared name/description for a trip's calendar event."""
    name = get_text("mobility.trip_management.calendar.event_name", "Trip: {trip_name}").format(trip_name=trip_name)
    description = get_text(
        "mobility.trip_management.calendar.event_description",
        "Destination: {destination}; Cost: £{cost:.2f}",
    ).format(destination=destination, cost=cost or 0)
    return name[:255], description


def sync_trip_calendar_event(conn, trip_id, *, trip_name, destination,
                             start_date, end_date, cost=None, created_by=None,
                             pending=None):
    """Create or refresh the calendar event for ``trip_id``.

    Runs on the caller's connection so the event is written in the same
    transaction as the trip itself — a trip is never persisted without its
    calendar entry, and never leaves a stray entry behind if the write fails.
    Returns the event id, or ``None`` when the calendar table is unavailable.

    The calendar-changed notification must not go out before the trip
    commits: pass ``pending`` (a list, flushed with
    ``database.run_after_commit`` once committed) and it is queued there.
    Without ``pending`` it is published straight away (older callers).
    """
    name, description = _trip_event_fields(trip_name, destination, cost)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor = conn.cursor()

    try:
        row = cursor.execute(
            "SELECT id FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE trip_id = ? LIMIT 1",
            (trip_id,),
        ).fetchone()

        if row:
            event_id = row[0]
            cursor.execute(
                "UPDATE unified_events "
                "SET title = ?, event_date = ?, start_datetime = ?, end_datetime = ?, "
                "    description = ?, event_type = ?, location = ?, updated_at = ? "
                "WHERE source_type = 'academic_calendar' AND source_event_id = ?",
                (name, start_date, start_date, end_date, description,
                 TRIP_EVENT_TYPE, destination, now, event_id),
            )
            action = 'updated'
        else:
            event_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO unified_events "
                "(source_event_id, title, event_date, start_datetime, end_datetime, description, event_type, location, created_at, updated_at, created_by, trip_id, source_type) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'academic_calendar')",
                (event_id, name, start_date, start_date, end_date, description,
                 TRIP_EVENT_TYPE, destination, now, now, created_by, trip_id),
            )
            action = 'created'
    except sqlite3.Error as e:
        logging.warning(
            "Could not sync calendar event for trip %s: %s", trip_id, e,
        )
        return None

    _notify(pending, event_id, action, start_date)
    return event_id


def remove_trip_calendar_event(conn, trip_id, pending=None):
    """Drop the calendar event(s) for a cancelled or archived trip. Returns rows removed.

    ``pending`` works as for :func:`sync_trip_calendar_event`.
    """
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT id, date_start FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE trip_id = ?",
            (trip_id,),
        ).fetchall()
        if not rows:
            return 0
        cursor.execute(
            "DELETE FROM unified_events WHERE source_type = 'academic_calendar' AND (trip_id = ?)", (trip_id,)
        )
    except sqlite3.Error as e:
        logging.warning(
            "Could not remove calendar event for trip %s: %s", trip_id, e,
        )
        return 0

    for event_id, date_start in rows:
        _notify(pending, event_id, 'deleted', date_start)
    return len(rows)


def _notify(pending, event_id, action, date):
    if pending is None:
        _publish_calendar_changed(event_id, action, date)
    else:
        pending.append(lambda: _publish_calendar_changed(event_id, action, date))


def _publish_calendar_changed(event_id, action, date):
    """Notify calendar subscribers; never fatal to the trip operation."""
    try:
        from education_system.systems.university.infrastructure.event_bus import (
            publish, EVENT_CALENDAR_CHANGED,
        )
        publish(EVENT_CALENDAR_CHANGED, event_id=event_id,
                event_type=TRIP_EVENT_TYPE, action=action, date=date)
    except Exception:
        logging.debug("Failed to publish calendar-changed for event_id=%s",
                      event_id, exc_info=True)


def create_trip_calendar_event(calendar_manager=None):
    """Put a trip that has no calendar event onto the academic calendar.

    Trips are synced automatically when they are created, updated or
    archived; this backfills one that predates that. It writes the event
    with :func:`sync_trip_calendar_event` — the same path as every other trip
    event — rather than the calendar manager's retired ``create_trip_event``.
    ``calendar_manager`` is accepted for older callers and not used.
    """
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import (
        read_connection, write_transaction, run_after_commit,
    )

    auth = _common.get_auth()
    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_view", "You must be logged in to view trips."))
        return False
    if not (auth.check_permission('manage_trips') or auth.check_permission('create_trips')):
        print(get_text("mobility.trip_management.auth.no_permission_update", "You don't have permission to update trips."))
        return False

    with read_connection() as conn:
        available_trips = conn.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status, t.cost
        FROM trips t
        WHERE t.status NOT IN ('cancelled', 'archived')
          AND NOT EXISTS (SELECT 1 FROM unified_events e
                          WHERE e.source_type = 'academic_calendar' AND e.trip_id = t.id)
        ORDER BY t.start_date
        ''').fetchall()

    if not available_trips:
        print(get_text("mobility.trip_management.calendar.no_trips_available", "No trips available for calendar event creation."))
        return False

    print("\n" + get_text("mobility.trip_management.calendar.trips_without_events", "Trips without Calendar Events:"))
    print("-" * 70)
    for trip in available_trips:
        print(f"{trip[0]}: {trip[1]} to {trip[2]} ({trip[3]} - {trip[4]}) - {trip[5].title()}")

    try:
        trip_id = int(input(get_text("mobility.trip_management.calendar.enter_trip_id", "\nEnter Trip ID: ")))
    except ValueError:
        print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
        return False

    selected_trip = next((trip for trip in available_trips if trip[0] == trip_id), None)
    if not selected_trip:
        print(get_text("mobility.trip_management.calendar.invalid_selection", "Invalid trip selection."))
        return False

    pending = []
    with write_transaction() as conn:
        event_id = sync_trip_calendar_event(
            conn, trip_id, trip_name=selected_trip[1], destination=selected_trip[2],
            start_date=selected_trip[3], end_date=selected_trip[4], cost=selected_trip[6],
            created_by=auth.current_user.get('username'), pending=pending,
        )
    run_after_commit(pending)

    if event_id:
        print(get_text("mobility.trip_management.calendar.event_created", "Calendar event created successfully!"))
        print(get_text("mobility.trip_management.calendar.event_id", "Event ID: {event_id}").format(event_id=event_id))
    else:
        print(get_text("mobility.trip_management.calendar.event_failed", "Failed to create calendar event: {message}").format(message="calendar unavailable"))
    return bool(event_id)

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
