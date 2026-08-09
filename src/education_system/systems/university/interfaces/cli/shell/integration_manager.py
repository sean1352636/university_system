"""
Integration manager for CLI system.

Handles external system integrations including calendar, trip management,
and dashboard integration.
"""

from education_system.systems.university.interfaces.cli.shell.imports import (
    logging, sqlite3, datetime, DB_PATH, logger, _t,
    log_activity, get_auth
)

# Import exception types
from education_system.systems.university.infrastructure.exceptions import (
    DatabaseError,
    ValidationError,
)

auth = None

try:
    from education_system.systems.university.domain.academics.services.academic_calendar.cli import display_academic_calendar_menu
except ImportError:
    display_academic_calendar_menu = None

try:
    from education_system.systems.university.domain.operations.campus.mobility.services.trip_management.menu import display_trip_management_menu
except ImportError:
    display_trip_management_menu = None

try:
    from education_system.systems.university.interfaces.cli.shell.services.academic_misconduct_cli import academic_misconduct_menu
    ACADEMIC_MISCONDUCT_AVAILABLE = True
except ImportError:
    academic_misconduct_menu = None
    ACADEMIC_MISCONDUCT_AVAILABLE = False

def set_auth(auth_instance):
    """Set the authentication instance for this module"""
    global auth
    auth = auth_instance

def get_db_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)


def link_attendance_to_calendar_events():
    """Link attendance records to calendar events - ADD THIS TO main.py"""
    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Link existing attendance to calendar events
        cursor.execute('''
        INSERT OR IGNORE INTO attendance_calendar_links
        (attendance_record_id, event_id, module_code, date, created_at)
        SELECT ar.id, e.id, ar.module_code, ar.date, datetime('now')
        FROM attendance_records ar
        JOIN unified_events e ON e.title LIKE '%' || ar.module_code || '%'
        AND e.start_datetime = ar.date
        WHERE NOT EXISTS (
            SELECT 1 FROM attendance_calendar_links acl
            WHERE acl.attendance_record_id = ar.id
        )
        ''')

        linked_count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Linked {linked_count} attendance records to calendar events")
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error linking attendance to calendar: {e}")
        return False


def create_integrated_dashboard_data():
    """Create data for integrated dashboard - ADD THIS TO main.py"""
    try:
        conn = get_db_connection()
        if not conn:
            return None

        cursor = conn.cursor()

        dashboard_data = {
            'upcoming_events': [],
            'attendance_summary': {},
            'recent_activity': []
        }

        # Get upcoming events with attendance status
        cursor.execute('''
        SELECT e.event_id, e.title, e.start_datetime, e.description,
               COUNT(ar.id) as attendance_count
        FROM unified_events e
        LEFT JOIN attendance_records ar ON e.start_datetime = ar.date
        WHERE e.start_datetime >= date('now')
        GROUP BY e.event_id
        ORDER BY e.start_datetime
        LIMIT 10
        ''')

        events = cursor.fetchall()
        for event in events:
            dashboard_data['upcoming_events'].append({
                'id': event[0],
                'name': event[1],
                'date': event[2],
                'type': event[3],
                'attendance_count': event[4]
            })

        # Get attendance summary for current week
        cursor.execute('''
        SELECT module_code, status, COUNT(*) as count
        FROM attendance_records
        WHERE date >= date('now', 'weekday 0', '-7 days')
        AND date < date('now', 'weekday 0')
        GROUP BY module_code, status
        ''')

        attendance_data = cursor.fetchall()
        for record in attendance_data:
            module = record[0]
            if module not in dashboard_data['attendance_summary']:
                dashboard_data['attendance_summary'][module] = {}
            dashboard_data['attendance_summary'][module][record[1]] = record[2]

        conn.close()
        return dashboard_data

    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error creating dashboard data: {e}")
        return None


def display_integrated_system_dashboard():
    """Display integrated system dashboard - ADD THIS TO main.py"""
    global auth

    if not auth or not auth.current_user:
        print(_t("cli.dashboard.login_required"))
        return

    print("\n" + "="*60)
    print(_t("cli.dashboard.title"))
    print("="*60)
    print(_t("cli.dashboard.user_info").format(user=auth.current_user['username'], role=auth.current_user['role']))
    print(_t("cli.dashboard.date_info").format(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Get dashboard data
    data = create_integrated_dashboard_data()
    if not data:
        print(_t("cli.dashboard.unable_to_load"))
        return

    # Display upcoming events
    print(f"\n📅 UPCOMING EVENTS ({len(data['upcoming_events'])})")
    if data['upcoming_events']:
        for event in data['upcoming_events'][:5]:
            attendance_info = f" (📊 {event['attendance_count']} attendance records)" if event['attendance_count'] > 0 else ""
            print(f"   • {event['date']}: {event['name']} [{event['type']}]{attendance_info}")
    else:
        print("   No upcoming events")

    # Display attendance summary
    print("\n📊 WEEKLY ATTENDANCE SUMMARY")
    if data['attendance_summary']:
        for module, statuses in data['attendance_summary'].items():
            total = sum(statuses.values())
            present = statuses.get('Present', 0) + statuses.get('Late', 0)
            percentage = (present / total * 100) if total > 0 else 0
            print(f"   • {module}: {percentage:.1f}% attendance ({present}/{total})")
    else:
        print("   No attendance data for this week")

    print("="*60)
    input("\nPress Enter to continue...")


def ensure_communication_integration_on_startup():
    """
    Ensure all users are properly integrated with the communication system on startup.
    This function checks for any missing integrations and fixes them automatically.
    """
    try:
        logger.info("Checking communication system integration...")

        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Check if users table exists, if not create it
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            logger.info("Users table not found. Creating...")
            cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL,
                student_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )
            ''')

        # Get all students and check if they have user accounts
        cursor.execute('''
        SELECT s.student_id, s.email_address, s.first_name, s.last_name, s.registration_datetime
        FROM students s
        LEFT JOIN users u ON s.student_id = u.student_id
        WHERE u.id IS NULL
        ''')

        missing_students = cursor.fetchall()

        if missing_students:
            logger.info(f"Found {len(missing_students)} students not integrated with communication system. Integrating...")

            for student in missing_students:
                student_id, email, first_name, last_name, reg_time = student

                try:
                    cursor.execute('''
                    INSERT INTO users (username, first_name, last_name, email, role, student_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        student_id,
                        first_name,
                        last_name,
                        email,
                        'student',
                        student_id,
                        reg_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    logger.info(f"Integrated student {student_id} ({first_name} {last_name})")

                except sqlite3.IntegrityError as e:
                    logger.warning(f"Could not integrate student {student_id}: {e}")

        # Check for any orphaned user accounts (users without student records for students)
        cursor.execute('''
        SELECT u.username, u.first_name, u.last_name, u.role
        FROM users u
        LEFT JOIN students s ON u.student_id = s.student_id
        WHERE u.role = 'student' AND s.student_id IS NULL
        ''')

        orphaned_users = cursor.fetchall()
        if orphaned_users:
            logger.warning(f"Found {len(orphaned_users)} orphaned user accounts")
            for user in orphaned_users:
                logger.warning(f"Orphaned account: {user[0]} ({user[1]} {user[2]}) - {user[3]}")

        conn.commit()
        conn.close()

        logger.info("Communication system integration check complete")
        return True

    except (sqlite3.Error, DatabaseError) as e:
        logging.error(f"Error during communication integration check: {e}")
        return False


def add_communication_dashboard_to_main_menu(auth):
    """Add the communication dashboard to the main menu"""
    # This function can be called from main.py
    try:
        from education_system.systems.university.infrastructure.email.admin.menus import display_communication_dashboard
        display_communication_dashboard(auth)
        return True
    except ImportError:
        logging.warning("CommunicationDashboard not available")
        return False
    except Exception as e:
        logging.error(f"Error displaying communication dashboard: {e}")
        return False


def create_trip_calendar_event(trip_id, event_details=None):
    """Create a calendar event for a trip"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create trip events.")
        return False

    if not auth.check_permission('manage_schedules'):
        print("You don't have permission to create calendar events.")
        return False

    try:
        # Get trip details
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM trips WHERE id = ?', (trip_id,))
        trip = cursor.fetchone()

        if not trip:
            print("Trip not found.")
            conn.close()
            return False

        # Create calendar event using the academic calendar system
        from education_system.systems.university.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
        from education_system.systems.university.domain.academics.services.academic_calendar.config import CalendarConfig

        config = CalendarConfig()
        calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)

        # Create event details
        event_name = event_details.get('name', f"Trip: {trip[1]}") if event_details else f"Trip: {trip[1]}"
        event_description = event_details.get('description', f"Trip to {trip[3]} - {trip[2] or 'No description'}") if event_details else f"Trip to {trip[3]}"

        # Create the calendar event
        result = calendar_manager.add_event(
            name=event_name,
            date_start=trip[4],  # start_date
            date_end=trip[5],    # end_date
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

            print("✅ Calendar event created successfully!")
            print(f"Event ID: {result['event_id']}")
            return True
        else:
            print(f"✗ Failed to create calendar event: {result.get('message', 'Unknown error')}")
            conn.close()
            return False

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error creating trip calendar event: {e}")
        logging.error(f"Error creating trip calendar event: {e}")
        return False


def view_integrated_dashboard():
    """View integrated dashboard showing both calendar and trip data"""
    global auth

    # Add this import at the start of the function
    from datetime import datetime, timedelta

    if not auth or not auth.current_user:
        print("You must be logged in to view the dashboard.")
        return

    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        print("\n" + "="*60)
        print("INTEGRATED ACADEMIC DASHBOARD")
        print("="*60)
        print(f"User: {auth.current_user['username']} ({auth.current_user['role']})")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Get upcoming calendar events
        try:
            from education_system.systems.university.domain.academics.services.academic_calendar.calendar_core import AcademicCalendarManager
            from education_system.systems.university.domain.academics.services.academic_calendar.config import CalendarConfig
            config = CalendarConfig()
            calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)

            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

            upcoming_events = calendar_manager.get_events_by_date_range(start_date, end_date)

            print(f"\n📅 UPCOMING EVENTS (next 30 days): {len(upcoming_events)}")
            if upcoming_events:
                for event in upcoming_events[:5]:  # Show first 5
                    event_date = event.get('date') or event.get('date_start', 'TBD')
                    print(f"   • {event_date}: {event['name']} ({event['event_type']})")
                if len(upcoming_events) > 5:
                    print(f"   ... and {len(upcoming_events) - 5} more events")
            else:
                print("   No upcoming events")

        except (ValueError, TypeError, ValidationError) as e:
            print(f"\n📅 CALENDAR: Error loading calendar data - {e}")

        # Get upcoming trips
        cursor.execute('''
        SELECT t.*, COUNT(tp.id) as participant_count
        FROM trips t
        LEFT JOIN trip_participants tp ON t.id = tp.trip_id AND tp.status = 'registered'
        WHERE t.start_date >= date('now')
        GROUP BY t.id
        ORDER BY t.start_date
        LIMIT 10
        ''')

        upcoming_trips = cursor.fetchall()

        print(f"\n🎒 UPCOMING TRIPS: {len(upcoming_trips)}")
        if upcoming_trips:
            for trip in upcoming_trips[:5]:  # Show first 5
                print(f"   • {trip[4]}: {trip[1]} to {trip[3]}")
                print(f"     Participants: {trip[-1]}/{trip[6]} - Status: {trip[8].title()}")
            if len(upcoming_trips) > 5:
                print(f"   ... and {len(upcoming_trips) - 5} more trips")
        else:
            print("   No upcoming trips")

        # Get integration statistics
        cursor.execute('SELECT COUNT(*) FROM academic_calendar_events WHERE trip_id IS NOT NULL')
        linked_events = cursor.fetchone()[0]

        print("\n🔗 INTEGRATION STATUS:")
        print(f"   Trip-Calendar links: {linked_events}")

        print("="*60)
        conn.close()

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Error loading dashboard: {e}")
        logging.error(f"Error loading integrated dashboard: {e}")


def sync_trips_with_calendar():
    """Sync all trips with calendar events"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to sync trips.")
        return False

    if not auth.check_permission('manage_schedules'):
        print("You don't have permission to sync calendar events.")
        return False

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Get trips without calendar events
        cursor.execute('''
        SELECT t.* FROM trips t
        LEFT JOIN academic_calendar_events tce ON t.id = tce.trip_id
        WHERE tce.trip_id IS NULL AND t.status IN ('open', 'planning')
        ''')

        trips_to_sync = cursor.fetchall()

        if not trips_to_sync:
            print("No trips found that need calendar events.")
            conn.close()
            return True

        print(f"Found {len(trips_to_sync)} trips to sync with calendar...")

        synced_count = 0

        for trip in trips_to_sync:
            event_details = {
                'name': f"Trip: {trip[1]}",
                'description': f"Trip to {trip[3]} - {trip[2] or 'No description'}"
            }

            if create_trip_calendar_event(trip[0], event_details):
                synced_count += 1
                print(f"  ✅ Synced: {trip[1]}")
            else:
                print(f"  ✗ Failed: {trip[1]}")

        conn.close()
        print(f"\nSync completed: {synced_count}/{len(trips_to_sync)} trips synced successfully")
        return True

    except (ValueError, TypeError, ValidationError) as e:
        print(f"Error syncing trips: {e}")
        logging.error(f"Error syncing trips with calendar: {e}")
        return False


def link_trip_to_event_manually():
    """Manually link a trip to a calendar event"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to link trips.")
        return False

    if not auth.check_permission('manage_schedules'):
        print("You don't have permission to create calendar events.")
        return False

    try:
        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor()

        # Get trips without calendar events
        cursor.execute('''
        SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date
        FROM trips t
        LEFT JOIN academic_calendar_events tce ON t.id = tce.trip_id
        WHERE tce.trip_id IS NULL
        ORDER BY t.start_date
        ''')

        available_trips = cursor.fetchall()

        if not available_trips:
            print("No trips available for linking (all may already be linked)")
            conn.close()
            return False

        print("\nAvailable Trips for Calendar Event Creation:")
        print("-" * 70)
        for trip in available_trips:
            print(f"{trip[0]}: {trip[1]} to {trip[2]} ({trip[3]} - {trip[4]})")

        trip_id = input("\nEnter Trip ID to create calendar event for: ").strip()

        try:
            trip_id = int(trip_id)
        except ValueError:
            print("Invalid trip ID.")
            conn.close()
            return False

        # Verify trip selection
        selected_trip = None
        for trip in available_trips:
            if trip[0] == trip_id:
                selected_trip = trip
                break

        if not selected_trip:
            print("Invalid trip selection.")
            conn.close()
            return False

        # Get event details
        print(f"\nCreating calendar event for: {selected_trip[1]}")
        event_name = input("Event name (press Enter for default): ").strip()
        description = input("Event description (optional): ").strip()

        event_details = {}
        if event_name:
            event_details['name'] = event_name
        if description:
            event_details['description'] = description

        conn.close()
        return create_trip_calendar_event(trip_id, event_details)

    except (ValueError, TypeError, ValidationError) as e:
        print(f"Error linking trip: {e}")
        logging.error(f"Error linking trip to event: {e}")
        return False


def view_trip_calendar_links():
    """View existing trip-calendar links"""
    try:
        conn = get_db_connection()
        if not conn:
            return

        cursor = conn.cursor()

        cursor.execute('''
        SELECT t.trip_name, t.destination, t.start_date, t.end_date,
               e.name as event_name, e.description, e.date_added as created_at
        FROM academic_calendar_events e
        JOIN trips t ON e.trip_id = t.id
        WHERE e.trip_id IS NOT NULL
        ORDER BY t.start_date
        ''')

        links = cursor.fetchall()

        if not links:
            print("No trip-calendar links found.")
        else:
            print("\nTrip-Calendar Event Links:")
            print("=" * 90)
            print(f"{'Trip':<25} {'Destination':<15} {'Dates':<20} {'Calendar Event':<20} {'Created':<12}")
            print("-" * 90)

            for link in links:
                trip_name, destination, start_date, end_date, event_name, event_type, created_at = link
                dates = f"{start_date} to {end_date}"
                created = created_at[:10]  # Just the date part

                print(f"{trip_name[:24]:<25} {destination[:14]:<15} {dates[:19]:<20} {event_name[:19]:<20} {created:<12}")

            print("=" * 90)

        conn.close()

    except (ValueError, TypeError, ValidationError) as e:
        print(f"Error viewing links: {e}")
        logging.error(f"Error viewing trip-calendar links: {e}")


def display_integrated_academic_menu():
    """Display the integrated academic management menu"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to access the integrated academic system.")
        return

    # Check if user has access to either system
    calendar_access = (auth.check_permission('manage_schedules') or
                      auth.check_permission('view_own_timetable') or
                      auth.check_permission('export_data'))

    trips_access = (auth.check_permission('view_trips') or
                   auth.check_permission('create_trips') or
                   auth.check_permission('manage_trips') or
                   auth.check_permission('register_for_trips'))

    if not (calendar_access or trips_access):
        print("You don't have permission to access academic management systems.")
        return

    while True:
        print("\nIntegrated Academic Management System")
        print(f"Logged in as: {auth.current_user['username']} ({auth.current_user['role']})")
        print("=" * 60)

        options = []
        option_num = 1

        # Dashboard (available to all users with either system access)
        if calendar_access or trips_access:
            print(f"{option_num}. View Integrated Dashboard")
            options.append(('dashboard', view_integrated_dashboard))
            option_num += 1

        # Calendar System
        if calendar_access and display_academic_calendar_menu:
            print(f"{option_num}. Academic Calendar Management")
            options.append(('calendar', display_academic_calendar_menu))
            option_num += 1

        # Trip System
        if trips_access and display_trip_management_menu:
            print(f"{option_num}. Trip Management")
            options.append(('trips', display_trip_management_menu))
            option_num += 1

        # Academic Misconduct System (admin, staff, instructor only)
        misconduct_access = auth.current_user['role'].lower() in ['admin', 'staff', 'instructor', 'administrator']
        if misconduct_access and ACADEMIC_MISCONDUCT_AVAILABLE:
            print(f"{option_num}. Academic Misconduct Management")
            options.append(('misconduct', academic_misconduct_menu))
            option_num += 1

        # Integration Features (only for users with manage permissions)
        if auth.check_permission('manage_schedules') and trips_access:
            print(f"{option_num}. Create Calendar Event for Trip")
            options.append(('link', link_trip_to_event_manually))
            option_num += 1

            print(f"{option_num}. Sync All Trips with Calendar")
            options.append(('sync', sync_trips_with_calendar))
            option_num += 1

            print(f"{option_num}. View Trip-Calendar Links")
            options.append(('view_links', view_trip_calendar_links))
            option_num += 1

        print(f"{option_num}. Return to Main Menu")

        try:
            choice = int(input(f"\nEnter your choice (1-{option_num}): "))

            if choice == option_num:  # Return to main menu
                break
            elif 1 <= choice <= len(options):
                action_name, action_func = options[choice - 1]
                try:
                    if action_name in ['sync', 'link']:
                        success = action_func()
                        if success:
                            print("Operation completed successfully!")
                        else:
                            print("Operation failed or was cancelled.")
                    else:
                        action_func()
                except (ValueError, TypeError, ValidationError) as e:
                    print(f"Error executing {action_name}: {e}")
                    logging.error(f"Error in {action_name}: {e}")

                if action_name not in ['calendar', 'trips']:
                    input("\nPress Enter to continue...")
            else:
                print("Invalid choice. Please try again.")

        except ValueError:
            print("Please enter a valid number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled.")
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(f"Unexpected error: {e}")
            logging.error(f"Unexpected error in integrated menu: {e}")


__all__ = [
    'link_attendance_to_calendar_events',
    'create_integrated_dashboard_data',
    'display_integrated_system_dashboard',
    'ensure_communication_integration_on_startup',
    'add_communication_dashboard_to_main_menu',
    'create_trip_calendar_event',
    'view_integrated_dashboard',
    'sync_trips_with_calendar',
    'link_trip_to_event_manually',
    'view_trip_calendar_links',
    'display_integrated_academic_menu',
]
