from education_system.university_system.modules.domain.mobility.services.trip_management import _common
from education_system.university_system.modules.domain.mobility.services.trip_management._common import sqlite3, get_text, logging, datetime, log_create, log_read
from education_system.university_system.modules.domain.mobility.services.trip_management.database import safe_db_operation


@log_create(module="trips", description="Adding trip itinerary")
def add_trip_itinerary():
    """Add itinerary items to a trip"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_itinerary", "You must be logged in to manage trip itineraries."))
        return False

    if not (auth.check_permission('manage_trips') or auth.check_permission('create_trips')):
        print(get_text("mobility.trip_management.auth.no_permission_itinerary", "You don't have permission to manage trip itineraries."))
        return False

    def add_itinerary_operation(conn):
        cursor = conn.cursor()

        # Get trips that user can manage
        if auth.check_permission('manage_trips'):
            cursor.execute('''
            SELECT id, trip_name, destination, start_date, end_date, status
            FROM trips
            WHERE status IN ('planning', 'open')
            ORDER BY start_date ASC
            ''')
        else:
            cursor.execute('''
            SELECT id, trip_name, destination, start_date, end_date, status
            FROM trips
            WHERE created_by = ? AND status IN ('planning', 'open')
            ORDER BY start_date ASC
            ''', (auth.current_user['id'],))

        trips = cursor.fetchall()

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

            # Verify trip exists and user can manage it
            selected_trip = None
            for trip in trips:
                if trip[0] == trip_id:
                    selected_trip = trip
                    break

            if not selected_trip:
                print(get_text("mobility.trip_management.itinerary.invalid_selection", "Invalid trip selection."))
                return False

            trip_name = selected_trip[1]
            start_date = datetime.strptime(selected_trip[3], '%Y-%m-%d')
            end_date = datetime.strptime(selected_trip[4], '%Y-%m-%d')
            trip_days = (end_date - start_date).days + 1

            print(get_text("mobility.trip_management.itinerary.adding_for", "\nAdding itinerary for: {trip_name}").format(trip_name=trip_name))
            print(get_text("mobility.trip_management.itinerary.trip_duration", "Trip duration: {days} days").format(days=trip_days))

            # Get existing itinerary
            cursor.execute('''
            SELECT day_number, activity, location, start_time, end_time
            FROM trip_itinerary
            WHERE trip_id = ?
            ORDER BY day_number, start_time
            ''', (trip_id,))

            existing_items = cursor.fetchall()

            if existing_items:
                print(get_text("mobility.trip_management.itinerary.existing_items", "\nExisting Itinerary Items:"))
                print("-" * 60)
                for item in existing_items:
                    day, activity, location, start_time, end_time = item
                    time_info = f"{start_time}-{end_time}" if start_time and end_time else get_text("mobility.trip_management.itinerary.all_day", "All day")
                    location_info = get_text("mobility.trip_management.itinerary.at_location", " at {location}").format(location=location) if location else ""
                    print(get_text("mobility.trip_management.itinerary.day_item", "Day {day}: {activity}{location} ({time})").format(day=day, activity=activity, location=location_info, time=time_info))

            # Add new itinerary items
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

                # Validate time format if provided
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

                # Insert itinerary item
                try:
                    cursor.execute('''
                    INSERT INTO trip_itinerary (
                        trip_id, day_number, activity, location,
                        start_time, end_time, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        trip_id, day_number, activity, location,
                        start_time, end_time, notes
                    ))

                    print(get_text("mobility.trip_management.itinerary.item_added", "Itinerary item added for Day {day}: {activity}").format(day=day_number, activity=activity))

                except sqlite3.IntegrityError:
                    print(get_text("mobility.trip_management.itinerary.conflict_error", "Error: Conflicting itinerary item (same day and time). Please try different time."))
                    continue

                # Ask if user wants to add more items
                add_more = input(get_text("mobility.trip_management.itinerary.add_more", "\nAdd another itinerary item? (y/n): ")).lower()
                if add_more != 'y':
                    break

            print(get_text("mobility.trip_management.itinerary.completed", "\nItinerary management completed for '{trip_name}'.").format(trip_name=trip_name))
            return True

        except ValueError:
            print(get_text("mobility.trip_management.validation.invalid_trip_id", "Invalid trip ID."))
            return False
        except Exception as e:
            print(get_text("mobility.trip_management.errors.managing_itinerary", "Error managing itinerary: {error}").format(error=e))
            logging.error(get_text("mobility.trip_management.errors.in_add_itinerary", "Error in add_trip_itinerary: {error}").format(error=e))
            return False

    return safe_db_operation(add_itinerary_operation)

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
                    time_info = f"({start_time} - {end_time})"
                elif start_time:
                    time_info = get_text("mobility.trip_management.itinerary.from_time", "(from {time})").format(time=start_time)
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
