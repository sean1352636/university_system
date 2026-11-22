from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import _common
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, log_create, log_read
from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import safe_db_operation


def _trips():
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import trips
    return trips


# ---------------------------------------------------------------------------
# Domain API (same contract as trips.py)
# ---------------------------------------------------------------------------

_ITINERARY_FIELDS = ('day_number', 'activity', 'location', 'start_time', 'end_time', 'notes')


def _clean_item(trip, fields, *, partial=False):
    out = {}
    for name, value in fields.items():
        if name not in _ITINERARY_FIELDS:
            raise ValueError(f"unknown itinerary field {name!r}")
        out[name] = value.strip() if isinstance(value, str) else value
    days = (datetime.strptime(trip['end_date'], '%Y-%m-%d')
            - datetime.strptime(trip['start_date'], '%Y-%m-%d')).days + 1
    if 'day_number' in out or not partial:
        try:
            out['day_number'] = int(out.get('day_number'))
        except (TypeError, ValueError):
            raise ValueError(get_text("mobility.trip_management.validation.enter_valid_day_number",
                                      "Please enter a valid day number.")) from None
        if not 1 <= out['day_number'] <= days:
            raise ValueError(get_text("mobility.trip_management.itinerary.day_number_range",
                                      "Day number must be between 1 and {max}.").format(max=days))
    if 'activity' in out or not partial:
        if not out.get('activity'):
            raise ValueError(get_text("mobility.trip_management.itinerary.activity_required",
                                      "Activity description is required."))
    for name in ('start_time', 'end_time'):
        if out.get(name):
            try:
                datetime.strptime(out[name], '%H:%M')
            except ValueError:
                raise ValueError(f"{name}: use HH:MM") from None
        elif name in out:
            out[name] = None
    return out


def _require_trip_manager(auth, trip_id, c, who):
    trip = _trips().get_trip(trip_id, conn=c)
    if not trip:
        raise ValueError(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
    if not (auth.check_permission('manage_trips') or auth.check_permission('create_trips')) \
            or not _trips().can_manage_trip(auth, trip, conn=c, who=who):
        raise PermissionError(get_text("mobility.trip_management.auth.no_permission_itinerary",
                                       "You don't have permission to manage trip itineraries."))
    return trip


def list_itinerary(trip_id, conn=None):
    """A trip's itinerary items in order (dicts with ``id``)."""
    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management import database
    with database.read_connection(conn) as c:
        cur = c.execute(
            "SELECT id, trip_id, day_number, activity, location, start_time, end_time, notes "
            "FROM trip_itinerary WHERE trip_id = ? "
            "ORDER BY day_number, COALESCE(start_time, ''), id", (trip_id,))
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def add_itinerary_item(auth, trip_id, day_number, activity, location=None, start_time=None,
                       end_time=None, notes=None, *, conn=None, pending=None):
    """Add one itinerary item. Raises ValueError on a clash (same day and start time)."""
    trips = _trips()
    who = trips.actor(auth)

    def work(c, p):
        trip = _require_trip_manager(auth, trip_id, c, who)
        item = _clean_item(trip, {'day_number': day_number, 'activity': activity,
                                  'location': location or None, 'start_time': start_time,
                                  'end_time': end_time, 'notes': notes or None})
        try:
            item_id = c.execute(
                "INSERT INTO trip_itinerary (trip_id, day_number, activity, location, start_time, "
                "end_time, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (trip_id, item['day_number'], item['activity'], item['location'],
                 item['start_time'], item['end_time'], item['notes'])).lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(get_text("mobility.trip_management.itinerary.conflict_error",
                                      "Error: Conflicting itinerary item (same day and time). Please try different time.")) from None
        trips._publish_after(p, "trip.updated", trip_id=trip_id, fields=['itinerary'])
        return item_id
    return trips._in_transaction(conn, pending, work)


def update_itinerary_item(auth, trip_id, item_id, *, conn=None, pending=None, **fields):
    """Change an itinerary item that belongs to ``trip_id``."""
    trips = _trips()
    who = trips.actor(auth)

    def work(c, p):
        trip = _require_trip_manager(auth, trip_id, c, who)
        changes = _clean_item(trip, fields, partial=True)
        if not changes:
            return False
        try:
            cur = c.execute(f"UPDATE trip_itinerary SET {', '.join(k + ' = ?' for k in changes)} "
                            "WHERE id = ? AND trip_id = ?", [*changes.values(), item_id, trip_id])
        except sqlite3.IntegrityError:
            raise ValueError(get_text("mobility.trip_management.itinerary.conflict_error",
                                      "Error: Conflicting itinerary item (same day and time). Please try different time.")) from None
        if cur.rowcount == 0:
            raise ValueError("itinerary item not found")
        trips._publish_after(p, "trip.updated", trip_id=trip_id, fields=['itinerary'])
        return True
    return trips._in_transaction(conn, pending, work)


def remove_itinerary_item(auth, trip_id, item_id, *, conn=None, pending=None):
    """Delete an itinerary item that belongs to ``trip_id``."""
    trips = _trips()
    who = trips.actor(auth)

    def work(c, p):
        _require_trip_manager(auth, trip_id, c, who)
        cur = c.execute("DELETE FROM trip_itinerary WHERE id = ? AND trip_id = ?", (item_id, trip_id))
        if cur.rowcount == 0:
            raise ValueError("itinerary item not found")
        trips._publish_after(p, "trip.updated", trip_id=trip_id, fields=['itinerary'])
        return True
    return trips._in_transaction(conn, pending, work)


@log_create(module="trips", description="Adding trip itinerary")
def add_trip_itinerary():
    """Add itinerary items to a trip (each item is saved as soon as it is entered)."""
    auth = _common.get_auth()

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_itinerary", "You must be logged in to manage trip itineraries."))
        return False

    if not (auth.check_permission('manage_trips') or auth.check_permission('create_trips')):
        print(get_text("mobility.trip_management.auth.no_permission_itinerary", "You don't have permission to manage trip itineraries."))
        return False

    trips = [t for t in _trips()._editable_trips(auth) if t[5] not in ('cancelled', 'completed')]
    if not trips:
        print(get_text("mobility.trip_management.itinerary.no_trips_available", "No trips available for itinerary management."))
        return False

    print("\n" + get_text("mobility.trip_management.itinerary.trips_available", "Trips Available for Itinerary Management:"))
    print("=" * 80)
    print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.status', 'Status'):<10}")
    print("-" * 80)
    for trip in trips:
        print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[5].title():<10}")
    print("=" * 80)

    try:
        trip_id = int(input(get_text("mobility.trip_management.itinerary.enter_trip_id", "\nEnter Trip ID to add itinerary: ")))
    except ValueError:
        print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
        return False

    selected_trip = next((t for t in trips if t[0] == trip_id), None)
    if not selected_trip:
        print(get_text("mobility.trip_management.itinerary.invalid_selection", "Invalid trip selection."))
        return False

    trip_name = selected_trip[1]
    trip_days = (datetime.strptime(selected_trip[4], '%Y-%m-%d')
                 - datetime.strptime(selected_trip[3], '%Y-%m-%d')).days + 1

    print(get_text("mobility.trip_management.itinerary.adding_for", "\nAdding itinerary for: {trip_name}").format(trip_name=trip_name))
    print(get_text("mobility.trip_management.itinerary.trip_duration", "Trip duration: {days} days").format(days=trip_days))

    from education_system.systems.university.domains.operations.domain.campus.mobility.services.trip_management.database import read_connection
    with read_connection() as conn:
        existing_items = conn.execute('''
        SELECT day_number, activity, location, start_time, end_time
        FROM trip_itinerary
        WHERE trip_id = ?
        ORDER BY day_number, start_time
        ''', (trip_id,)).fetchall()

    if existing_items:
        print(get_text("mobility.trip_management.itinerary.existing_items", "\nExisting Itinerary Items:"))
        print("-" * 60)
        for day, activity, location, start_time, end_time in existing_items:
            time_info = f"{start_time}-{end_time}" if start_time and end_time else get_text("mobility.trip_management.itinerary.all_day", "All day")
            location_info = get_text("mobility.trip_management.itinerary.at_location", " at {location}").format(location=location) if location else ""
            print(get_text("mobility.trip_management.itinerary.day_item", "Day {day}: {activity}{location} ({time})").format(day=day, activity=activity, location=location_info, time=time_info))

    while True:
        print(get_text("mobility.trip_management.itinerary.add_new_item", "\nAdd New Itinerary Item:"))

        while True:
            try:
                day_number = int(input(get_text("mobility.trip_management.itinerary.day_number_prompt", "Day number (1-{max}): ").format(max=trip_days)))
                if 1 <= day_number <= trip_days:
                    break
                print(get_text("mobility.trip_management.itinerary.day_number_range", "Day number must be between 1 and {max}.").format(max=trip_days))
            except ValueError:
                print(get_text("mobility.trip_management.validation.enter_valid_day_number", "Please enter a valid day number."))

        activity = input(get_text("mobility.trip_management.itinerary.activity_prompt", "Activity description: ")).strip()
        if not activity:
            print(get_text("mobility.trip_management.itinerary.activity_required", "Activity description is required."))
            continue

        location = input(get_text("mobility.trip_management.itinerary.location_prompt", "Location (optional): ")).strip()
        start_time = input(get_text("mobility.trip_management.itinerary.start_time_prompt", "Start time (HH:MM format, optional): ")).strip()
        end_time = input(get_text("mobility.trip_management.itinerary.end_time_prompt", "End time (HH:MM format, optional): ")).strip()
        notes = input(get_text("mobility.trip_management.itinerary.notes_prompt", "Notes (optional): ")).strip()

        if start_time:
            try:
                datetime.strptime(start_time, '%H:%M')
            except ValueError:
                print(get_text("mobility.trip_management.itinerary.invalid_start_time", "Invalid start time format. Saving without time."))
                start_time = None
        if end_time:
            try:
                datetime.strptime(end_time, '%H:%M')
            except ValueError:
                print(get_text("mobility.trip_management.itinerary.invalid_end_time", "Invalid end time format. Saving without time."))
                end_time = None

        try:
            add_itinerary_item(auth, trip_id, day_number, activity, location, start_time or None,
                               end_time or None, notes)
            print(get_text("mobility.trip_management.itinerary.item_added", "Itinerary item added for Day {day}: {activity}").format(day=day_number, activity=activity))
        except (ValueError, PermissionError) as e:
            print(str(e))
            continue
        except sqlite3.Error as e:
            print(get_text("mobility.trip_management.errors.managing_itinerary", "Error managing itinerary: {error}").format(error=e))
            logging.error(get_text("mobility.trip_management.errors.in_add_itinerary", "Error in add_trip_itinerary: {error}").format(error=e))
            return False

        add_more = input(get_text("mobility.trip_management.itinerary.add_more", "\nAdd another itinerary item? (y/n): ")).lower()
        if add_more != 'y':
            break

    print(get_text("mobility.trip_management.itinerary.completed", "\nItinerary management completed for '{trip_name}'.").format(trip_name=trip_name))
    return True

@log_read(module="trips", description="Viewing trip itinerary")
def view_trip_itinerary():
    """View itinerary for a specific trip"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_view_itinerary", "You must be logged in to view trip itineraries."))
        return False

    if not auth.check_permission('view_trips'):
        print(get_text("mobility.trip_management.auth.no_permission_view_itinerary", "You don't have permission to view trip itineraries."))
        return False

    def view_itinerary_operation(conn):
        cursor = conn.cursor()

        # Get trips with itineraries
        cursor.execute('''
        SELECT DISTINCT t.id, t.trip_name, t.destination, t.start_date, t.end_date
        FROM trips t
        JOIN trip_itinerary ti ON t.id = ti.trip_id
        ORDER BY t.start_date ASC
        ''')

        trips = cursor.fetchall()

        if not trips:
            print(get_text("mobility.trip_management.itinerary.no_trips_with_itineraries", "No trips with itineraries found."))
            return True

        print("\n" + get_text("mobility.trip_management.itinerary.trips_with_itineraries", "Trips with Itineraries:"))
        print("=" * 80)
        print(f"{get_text('mobility.trip_management.headers.id', 'ID'):<5} {get_text('mobility.trip_management.headers.name', 'Name'):<25} {get_text('mobility.trip_management.headers.destination', 'Destination'):<20} {get_text('mobility.trip_management.headers.start_date', 'Start Date'):<12} {get_text('mobility.trip_management.headers.end_date', 'End Date'):<12}")
        print("-" * 80)

        for trip in trips:
            print(f"{trip[0]:<5} {trip[1][:24]:<25} {trip[2][:19]:<20} {trip[3]:<12} {trip[4]:<12}")

        print("=" * 80)

        try:
            trip_id = int(input(get_text("mobility.trip_management.itinerary.enter_trip_id_view", "\nEnter Trip ID to view itinerary: ")))

            # Get trip details
            cursor.execute('SELECT trip_name, destination, start_date, end_date FROM trips WHERE id = ?', (trip_id,))
            trip_info = cursor.fetchone()

            if not trip_info:
                print(get_text("mobility.trip_management.trips.trip_not_found", "Trip not found."))
                return False

            trip_name, destination, start_date, end_date = trip_info

            # Get itinerary items
            cursor.execute('''
            SELECT day_number, activity, location, start_time, end_time, notes
            FROM trip_itinerary
            WHERE trip_id = ?
            ORDER BY day_number, start_time
            ''', (trip_id,))

            itinerary_items = cursor.fetchall()

            if not itinerary_items:
                print(get_text("mobility.trip_management.itinerary.no_itinerary_for_trip", "No itinerary found for '{trip_name}'.").format(trip_name=trip_name))
                return True

            print(get_text("mobility.trip_management.itinerary.itinerary_for", "\nItinerary for: {trip_name}").format(trip_name=trip_name))
            print(get_text("mobility.trip_management.itinerary.destination_display", "Destination: {destination}").format(destination=destination))
            print(get_text("mobility.trip_management.itinerary.dates_display", "Dates: {start_date} to {end_date}").format(start_date=start_date, end_date=end_date))
            print("=" * 80)

            current_day = None
            for item in itinerary_items:
                day_number, activity, location, start_time, end_time, notes = item

                if current_day != day_number:
                    print(get_text("mobility.trip_management.itinerary.day_header", "\nDAY {day}:").format(day=day_number))
                    print("-" * 20)
                    current_day = day_number

                # Format time information
                if start_time and end_time:
                    # The translated string spans both ends ("from {start} to {end}"),
                    # so it belongs on this branch, not the start-only one below.
                    time_info = "(" + get_text("mobility.trip_management.itinerary.from_time", "from {start} to {end}").format(start=start_time, end=end_time) + ")"
                elif start_time:
                    time_info = get_text("mobility.trip_management.itinerary.from_time_only", "(from {start})").format(start=start_time)
                else:
                    time_info = ""

                # Format location information
                location_info = get_text("mobility.trip_management.itinerary.at_location", " at {location}").format(location=location) if location else ""

                print(f"- {activity}{location_info} {time_info}")

                if notes:
                    print(get_text("mobility.trip_management.itinerary.notes_display", "  Notes: {notes}").format(notes=notes))

            print("=" * 80)
            return True

        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
            return False
        except Exception as e:
            print(get_text("mobility.trip_management.errors.viewing_itinerary", "Error viewing itinerary: {error}").format(error=e))
            logging.error(get_text("mobility.trip_management.errors.in_view_itinerary", "Error in view_trip_itinerary: {error}").format(error=e))
            return False

    return safe_db_operation(view_itinerary_operation)
