from education_system.university_system.infrastructure.database.db import sqlite3
import logging
from datetime import datetime
from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

from .exceptions import CalendarError, ValidationError, DatabaseError, PermissionError
from .config import CalendarConfig, ValidationUtils

logger = configure_logging(name=__name__)

try:
    from dateutil.rrule import rrule, DAILY, WEEKLY, MONTHLY, YEARLY
    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

try:
    import pytz
    TIMEZONE_AVAILABLE = True
except ImportError:
    TIMEZONE_AVAILABLE = False

try:
    import holidays
    HOLIDAYS_AVAILABLE = True
except ImportError:
    HOLIDAYS_AVAILABLE = False

try:
    from education_system.university_system.modules.domain.mobility.services import trip_management
    TRIP_MANAGEMENT_AVAILABLE = True
except ImportError:
    TRIP_MANAGEMENT_AVAILABLE = False

try:
    from education_system.university_system.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_manager):
    """Set the authentication manager for the calendar system"""
    global auth
    auth = auth_manager
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_manager)

def display_academic_calendar_menu():
    """Display the academic calendar management menu with trip integration"""
    global auth

    if not auth or not auth.current_user:
        print(get_text('calendar.login_required', default='You must be logged in to access the academic calendar.'))
        return

    # Check if user has any calendar-related permissions
    if not (auth.check_permission('manage_schedules') or
            auth.check_permission('view_own_timetable') or
            auth.check_permission('export_data')):
        print(get_text('calendar.no_permission', default="You don't have permission to access the academic calendar."))
        return

    try:
        # Create calendar manager with authentication
        from .calendar_core import AcademicCalendarManager
        config = CalendarConfig()
        calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)

        # Set auth for trip management if available
        if TRIP_MANAGEMENT_AVAILABLE:
            trip_management.set_auth(auth)

        # Create a simple menu interface
        while True:
            print(f"\n{get_text('calendar.title', default='Integrated Academic Calendar & Trip Management')}")
            print("=" * 55)
            print(get_text('calendar.logged_in_as', default='Logged in as: {username} ({role})').format(
                username=auth.current_user['username'], role=auth.current_user['role']))

            options = []
            option_num = 1

            # Calendar options
            print(f"\n\U0001f4c5 {get_text('calendar.sections.calendar_mgmt', default='CALENDAR MANAGEMENT')}:")
            if auth.check_permission('manage_schedules'):
                print(f"{option_num}. {get_text('calendar.menu.add_event', default='Add Event')}")
                options.append(('add_event', lambda: handle_add_event(calendar_manager)))
                option_num += 1

                print(f"{option_num}. {get_text('calendar.menu.update_event', default='Update Event')}")
                options.append(('update_event', lambda: handle_update_event(calendar_manager)))
                option_num += 1

                print(f"{option_num}. {get_text('calendar.menu.delete_event', default='Delete Event')}")
                options.append(('delete_event', lambda: handle_delete_event(calendar_manager)))
                option_num += 1

            print(f"{option_num}. {get_text('calendar.menu.view_calendar', default='View Calendar')}")
            options.append(('view_calendar', lambda: handle_view_calendar(calendar_manager)))
            option_num += 1

            if auth.check_permission('export_data'):
                print(f"{option_num}. {get_text('calendar.menu.export_calendar', default='Export Calendar')}")
                options.append(('export_calendar', lambda: handle_export_calendar(calendar_manager)))
                option_num += 1

            # Trip management options (if available)
            if TRIP_MANAGEMENT_AVAILABLE:
                print(f"\n\U0001f392 {get_text('calendar.sections.trip_mgmt', default='TRIP MANAGEMENT')}:")

                if auth.check_permission('view_trips'):
                    print(f"{option_num}. {get_text('calendar.menu.view_trips', default='View All Trips')}")
                    options.append(('view_trips', trip_management.view_trips))
                    option_num += 1

                if auth.check_permission('create_trips'):
                    print(f"{option_num}. {get_text('calendar.menu.create_trip', default='Create New Trip')}")
                    options.append(('create_trip', trip_management.create_trip))
                    option_num += 1

                if auth.check_permission('register_for_trips'):
                    print(f"{option_num}. {get_text('calendar.menu.register_trip', default='Register for Trip')}")
                    options.append(('register_trip', trip_management.register_for_trip))
                    option_num += 1

                if auth.check_permission('view_own_trip_registrations'):
                    print(f"{option_num}. {get_text('calendar.menu.my_registrations', default='View My Trip Registrations')}")
                    options.append(('view_registrations', trip_management.view_my_trip_registrations))
                    option_num += 1

            # Integration options
            if TRIP_MANAGEMENT_AVAILABLE and auth.check_permission('manage_schedules'):
                print(f"\n\U0001f517 {get_text('calendar.sections.integration', default='INTEGRATION')}:")
                print(f"{option_num}. {get_text('calendar.menu.create_trip_event', default='Create Calendar Event for Trip')}")
                options.append(('create_trip_event', lambda: handle_create_trip_event(calendar_manager)))
                option_num += 1

                print(f"{option_num}. {get_text('calendar.menu.view_links', default='View Trip-Calendar Links')}")
                options.append(('view_links', lambda: handle_view_trip_calendar_links()))
                option_num += 1

            # Language option
            print(f"\n\U0001f310 {get_text('calendar.sections.settings', default='SETTINGS')}:")
            print(f"{option_num}. {get_text('calendar.menu.language', default='Language')}")
            options.append(('language', display_language_menu_option))
            option_num += 1

            print(f"\n{option_num}. {get_text('calendar.menu.return_main', default='Return to Main Menu')}")

            choice = input(f"\n{get_text('calendar.select_option', default='Select option')} (1-{option_num}): ").strip()

            try:
                choice_num = int(choice)

                if choice_num == option_num:  # Return to main menu
                    break
                elif 1 <= choice_num <= len(options):
                    selected_option = options[choice_num - 1]
                    action_name, action_func = selected_option
                    try:
                        action_func()
                    except Exception as e:
                        print(get_text('calendar.error_executing', default='Error executing {action}: {error}').format(
                            action=action_name, error=e))
                        logger.error(f"Error in {action_name}: {e}")
                else:
                    print(get_text('calendar.invalid_choice', default='Invalid choice. Please try again.'))

            except ValueError:
                print(get_text('calendar.enter_valid_number', default='Please enter a valid number.'))
            except KeyboardInterrupt:
                print(f"\n{get_text('calendar.returning', default='Returning to main menu...')}")
                break
            except Exception as e:
                print(get_text('calendar.error_occurred', default='An error occurred: {error}').format(error=e))

            if choice_num != option_num:
                input("Press Enter to continue...")

    except Exception as e:
        print(f"Error initializing calendar system: {e}")
        input("Press Enter to continue...")

def handle_create_trip_event(calendar_manager):
    """Handle creating a calendar event for a trip"""
    try:
        # Get available trips
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.id, t.trip_name, t.destination, t.start_date, t.end_date, t.status
            FROM trips t
            LEFT JOIN trip_calendar_events tce ON t.id = tce.trip_id
            WHERE tce.trip_id IS NULL AND t.status IN ('planning', 'open')
            ORDER BY t.start_date
        ''')

        available_trips = cursor.fetchall()

        if not available_trips:
            print("No trips available for calendar event creation.")
            conn.close()
            return

        print("\nTrips Available for Calendar Event Creation:")
        print("-" * 70)
        for trip in available_trips:
            print(f"{trip[0]}: {trip[1]} to {trip[2]} ({trip[3]} - {trip[4]}) - {trip[5].title()}")

        trip_id = int(input("\nEnter Trip ID to create calendar event for: "))

        # Find selected trip
        selected_trip = None
        for trip in available_trips:
            if trip[0] == trip_id:
                selected_trip = trip
                break

        if not selected_trip:
            print("Invalid trip selection.")
            conn.close()
            return

        # Get event customization
        print(f"\nCreating calendar event for: {selected_trip[1]}")
        event_name = input(f"Event name (press Enter for default): ").strip()
        event_description = input("Event description (optional): ").strip()

        event_details = {}
        if event_name:
            event_details['name'] = event_name
        if event_description:
            event_details['description'] = event_description

        # Create the event
        result = calendar_manager.create_trip_event(trip_id, event_details)

        if result['success']:
            print(f"\u2713 Calendar event created successfully!")
            print(f"Event ID: {result['event_id']}")
        else:
            print(f"\u2717 Failed to create calendar event: {result['message']}")

        conn.close()

    except ValueError:
        print("Invalid trip ID.")
    except Exception as e:
        print(f"Error: {e}")

def handle_view_trip_calendar_links():
    """View existing trip-calendar links"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT t.trip_name, t.destination, t.start_date, t.end_date,
                   e.name as event_name, e.event_type, tce.created_at
            FROM trip_calendar_events tce
            JOIN trips t ON tce.trip_id = t.id
            JOIN academic_calendar_events e ON tce.event_id = e.id
            ORDER BY t.start_date
        ''')

        links = cursor.fetchall()

        if not links:
            print("No trip-calendar links found.")
        else:
            print("\nTrip-Calendar Event Links:")
            print("=" * 80)
            print(f"{'Trip':<25} {'Destination':<15} {'Dates':<20} {'Calendar Event':<15} {'Created':<12}")
            print("-" * 80)

            for link in links:
                trip_name, destination, start_date, end_date, event_name, event_type, created_at = link
                dates = f"{start_date} to {end_date}"
                created = created_at[:10]  # Just the date part

                print(f"{trip_name[:24]:<25} {destination[:14]:<15} {dates[:19]:<20} {event_name[:14]:<15} {created:<12}")

            print("=" * 80)

        conn.close()

    except Exception as e:
        print(f"Error viewing links: {e}")

def handle_add_event(calendar_manager):
    """Handle adding a new event"""
    print(f"\n{get_text('calendar.add_event.title', default='Add New Event')}")
    print("-" * 30)

    name = input(f"{get_text('calendar.add_event.name', default='Event Name')}: ").strip()
    if not name:
        print(get_text('calendar.add_event.name_required', default='Event name is required.'))
        return

    print(f"\n{get_text('calendar.add_event.date_type', default='Event Type')}:")
    print(f"1. {get_text('calendar.add_event.single_date', default='Single Date')}")
    print(f"2. {get_text('calendar.add_event.date_range', default='Date Range')}")

    date_type = input(f"{get_text('calendar.add_event.select_type', default='Select type')} (1-2): ").strip()

    date = None
    date_start = None
    date_end = None

    if date_type == '1':
        date = input(f"{get_text('calendar.add_event.event_date', default='Event Date')} (YYYY-MM-DD): ").strip()
    elif date_type == '2':
        date_start = input(f"{get_text('calendar.add_event.start_date', default='Start Date')} (YYYY-MM-DD): ").strip()
        date_end = input(f"{get_text('calendar.add_event.end_date', default='End Date')} (YYYY-MM-DD): ").strip()
    else:
        print(get_text('calendar.add_event.invalid_selection', default='Invalid selection.'))
        return

    description = input(f"{get_text('calendar.add_event.description', default='Description')} ({get_text('common.optional', default='optional')}): ").strip()

    print(f"\n{get_text('calendar.add_event.event_types', default='Event Types')}:")
    event_types = ["Academic", "Holiday", "Administrative", "Social", "Sports", "Deadline"]
    for i, et in enumerate(event_types, 1):
        print(f"{i}. {get_text(f'calendar.event_types.{et.lower()}', default=et)}")

    try:
        type_choice = int(input(f"{get_text('calendar.add_event.select_event_type', default='Select event type')} (1-6): "))
        if 1 <= type_choice <= len(event_types):
            event_type = event_types[type_choice - 1]
        else:
            print(get_text('calendar.add_event.invalid_type', default='Invalid event type selected.'))
            return
    except ValueError:
        print(get_text('calendar.invalid_choice', default='Invalid choice.'))
        return

    try:
        result = calendar_manager.add_event(name, date, date_start, date_end, description, event_type)
        print(f"\n{result['message']}")
        if result['success']:
            print(get_text('calendar.add_event.event_id', default='Event ID: {id}').format(id=result['event_id']))
    except Exception as e:
        print(get_text('calendar.add_event.error', default='Error creating event: {error}').format(error=e))

    input(f"\n{get_text('common.press_enter', default='Press Enter to continue...')}")

def handle_update_event(calendar_manager):
    """Handle updating an event"""
    print("\nUpdate Event")
    print("-" * 30)

    event_id = input("Event ID: ").strip()
    if not event_id:
        print("Event ID is required.")
        return

    # Get current event details
    try:
        rows = calendar_manager.db_manager.execute_query("SELECT * FROM academic_calendar_events WHERE id = ?", (event_id,))
        if not rows:
            print("Event not found.")
            return

        current_event = dict(rows[0])
        print(f"\nCurrent Event: {current_event['name']}")
        print(f"Type: {current_event['event_type']}")

        # Build the date string separately
        if current_event['date']:
            date_display = current_event['date']
        else:
            date_display = f"{current_event['date_start']} to {current_event['date_end']}"
        print(f"Date: {date_display}")
        print(f"Description: {current_event['description'] or 'None'}")

        updates = {}

        new_name = input(f"\nNew name (current: {current_event['name']}, press Enter to keep): ").strip()
        if new_name:
            updates['name'] = new_name

        new_description = input(f"New description (current: {current_event['description'] or 'None'}, press Enter to keep): ").strip()
        if new_description:
            updates['description'] = new_description

        if updates:
            result = calendar_manager.update_event(event_id, updates)
            print(f"\n{result['message']}")
        else:
            print("No updates provided.")

    except Exception as e:
        print(f"Error updating event: {e}")

    input("\nPress Enter to continue...")

def handle_delete_event(calendar_manager):
    """Handle deleting an event"""
    print("\nDelete Event")
    print("-" * 30)

    event_id = input("Event ID: ").strip()
    if not event_id:
        print("Event ID is required.")
        return

    try:
        # Get event details for confirmation
        rows = calendar_manager.db_manager.execute_query("SELECT name FROM academic_calendar_events WHERE id = ?", (event_id,))
        if not rows:
            print("Event not found.")
            return

        event_name = rows[0]['name']
        confirm = input(f"Are you sure you want to delete '{event_name}'? (yes/no): ").lower()

        if confirm == 'yes':
            result = calendar_manager.delete_event(event_id)
            print(f"\n{result['message']}")
        else:
            print("Deletion cancelled.")

    except Exception as e:
        print(f"Error deleting event: {e}")

    input("\nPress Enter to continue...")

def handle_add_academic_year(calendar_manager):
    """Handle adding an academic year"""
    print("\nAdd Academic Year")
    print("-" * 30)

    year = input("Academic Year (e.g., 2024-2025): ").strip()
    start_date = input("Start Date (YYYY-MM-DD): ").strip()
    end_date = input("End Date (YYYY-MM-DD): ").strip()

    try:
        success, message = calendar_manager.add_academic_year(year, start_date, end_date)
        print(f"\n{message}")
    except Exception as e:
        print(f"Error: {e}")

    input("\nPress Enter to continue...")

def handle_add_semester(calendar_manager):
    """Handle adding a semester"""
    print("\nAdd Semester")
    print("-" * 30)

    academic_year = input("Academic Year (e.g., 2024-2025): ").strip()
    semester_name = input("Semester Name (e.g., Fall, Spring): ").strip()
    start_date = input("Start Date (YYYY-MM-DD): ").strip()
    end_date = input("End Date (YYYY-MM-DD): ").strip()

    try:
        success, message = calendar_manager.add_semester(academic_year, semester_name, start_date, end_date)
        print(f"\n{message}")
    except Exception as e:
        print(f"Error: {e}")

    input("\nPress Enter to continue...")

def handle_view_calendar(calendar_manager):
    """Handle viewing calendar"""
    print(f"\n{get_text('calendar.view.title', default='View Calendar')}")
    print("-" * 30)

    academic_year = input(f"{get_text('calendar.view.academic_year', default='Academic Year')} ({get_text('calendar.view.leave_blank_current', default='leave blank for current')}): ").strip()
    semester = input(f"{get_text('calendar.view.semester', default='Semester')} ({get_text('calendar.view.leave_blank_all', default='leave blank for all')}): ").strip()

    academic_year = academic_year if academic_year else None
    semester = semester if semester else None

    try:
        success, result = calendar_manager.view_calendar(academic_year, semester)
        if success:
            display_calendar_data(result)
        else:
            print(get_text('calendar.error', default='Error: {error}').format(error=result))
    except Exception as e:
        print(get_text('calendar.view.error', default='Error viewing calendar: {error}').format(error=e))

    input(f"\n{get_text('common.press_enter', default='Press Enter to continue...')}")

def handle_search_events(calendar_manager):
    """Handle searching events"""
    print("\nSearch Events")
    print("-" * 30)

    print("1. Search by date range")
    print("2. Advanced search")

    try:
        search_choice = int(input("Select search type (1-2): "))

        if search_choice == 1:
            start_date = input("Start Date (YYYY-MM-DD): ").strip()
            end_date = input("End Date (YYYY-MM-DD): ").strip()
            event_type = input("Event Type (optional): ").strip()

            events = calendar_manager.get_events_by_date_range(start_date, end_date, event_type or None)
            display_events_list(events)

        elif search_choice == 2:
            criteria = {}

            text = input("Search text (optional): ").strip()
            if text:
                criteria['text'] = text

            start_date = input("Start date (YYYY-MM-DD, optional): ").strip()
            if start_date and ValidationUtils.validate_date(start_date):
                criteria['start_date'] = start_date

            end_date = input("End date (YYYY-MM-DD, optional): ").strip()
            if end_date and ValidationUtils.validate_date(end_date):
                criteria['end_date'] = end_date

            event_type = input("Event type (optional): ").strip()
            if event_type:
                criteria['event_type'] = event_type

            success, results = calendar_manager.search.advanced_search(criteria)
            if success:
                display_events_list(results)
            else:
                print(f"Search failed: {results}")
        else:
            print("Invalid choice.")

    except ValueError:
        print("Invalid choice.")
    except Exception as e:
        print(f"Search error: {e}")

    input("\nPress Enter to continue...")

def handle_export_calendar(calendar_manager):
    """Handle exporting calendar"""
    print("\nExport Calendar")
    print("-" * 30)

    print("Available formats:")
    formats = [
        ("JSON", "json"),
        ("CSV", "csv"),
        ("Excel", "xlsx"),
        ("PDF", "pdf"),
        ("iCal", "ics"),
        ("Text", "txt")
    ]

    for i, (name, ext) in enumerate(formats, 1):
        print(f"{i}. {name} (.{ext})")

    try:
        format_choice = int(input(f"Select format (1-{len(formats)}): "))

        if 1 <= format_choice <= len(formats):
            format_name, format_ext = formats[format_choice - 1]

            filename = input(f"Filename (without extension): ").strip()
            if not filename:
                filename = f"calendar_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            file_path = f"{filename}.{format_ext}"

            academic_year = input("Academic Year (leave blank for all): ").strip()
            academic_year = academic_year if academic_year else None

            result = calendar_manager.export_calendar(file_path, format_ext, academic_year)
            print(f"\n{result['message']}")

            if result['success']:
                open_file = input("Open the exported file? (y/n): ").lower().strip()
                if open_file == 'y':
                    try:
                        calendar_manager.safe_open_file(result['file_path'])
                    except Exception as e:
                        print(f"Could not open file: {e}")
        else:
            print("Invalid choice.")

    except ValueError:
        print("Invalid choice.")
    except Exception as e:
        print(f"Export error: {e}")

    input("\nPress Enter to continue...")

def handle_create_recurring_event(calendar_manager):
    """Handle create recurring event option"""
    print("\nCREATE RECURRING EVENT")
    print("-" * 30)

    if not DATEUTIL_AVAILABLE:
        print("dateutil library is required for recurring events.")
        return

    # Get base event information
    name = input("Event Name: ").strip()
    if not name:
        print("Event name is required.")
        return

    date = input("Start Date (YYYY-MM-DD): ").strip()
    if not ValidationUtils.validate_date(date):
        print("Invalid date format.")
        return

    description = input("Description: ").strip()
    event_type = input("Event Type (Academic/Holiday/Administrative): ").strip() or "Academic"

    # Get recurrence pattern
    print("\nRecurrence Pattern:")
    print("1. Daily")
    print("2. Weekly")
    print("3. Monthly")
    print("4. Yearly")

    try:
        freq_choice = int(input("Select frequency (1-4): "))
        frequencies = {1: 'daily', 2: 'weekly', 3: 'monthly', 4: 'yearly'}

        if freq_choice not in frequencies:
            print("Invalid choice.")
            return

        frequency = frequencies[freq_choice]
        interval = int(input("Interval (every X periods): ") or "1")

        pattern = {
            'frequency': frequency,
            'interval': interval
        }

        # End condition
        print("\nEnd Condition:")
        print("1. End date")
        print("2. Number of occurrences")

        end_choice = int(input("Select end condition (1-2): "))

        if end_choice == 1:
            end_date = input("End Date (YYYY-MM-DD): ").strip()
            if ValidationUtils.validate_date(end_date):
                pattern['end_date'] = end_date
            else:
                print("Invalid end date.")
                return
        elif end_choice == 2:
            count = int(input("Number of occurrences: "))
            if count > 0:
                pattern['occurrence_count'] = min(count, 100)  # Limit for safety
            else:
                print("Invalid count.")
                return
        else:
            print("Invalid choice.")
            return

        base_event = {
            'name': name,
            'date': date,
            'description': description,
            'event_type': event_type
        }

        success, message = calendar_manager.recurring_events.create_recurring_event(base_event, pattern)
        print(message)

    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error creating recurring event: {e}")

    input("\nPress Enter to continue...")

def handle_project_milestones(calendar_manager):
    """Handle project milestones menu"""
    print("\nPROJECT MILESTONES")
    print("-" * 30)
    print("1. Create milestone")
    print("2. Update milestone progress")
    print("3. View graduation requirements")
    print("4. Return to main menu")

    choice = input("Select option (1-4): ")

    if choice == '1':
        project_name = input("Project Name: ").strip()
        if not project_name:
            print("Project name is required.")
            return

        milestone_name = input("Milestone Name: ").strip()
        if not milestone_name:
            print("Milestone name is required.")
            return

        due_date = input("Due Date (YYYY-MM-DD): ").strip()
        if not ValidationUtils.validate_date(due_date):
            print("Invalid date format.")
            return

        description = input("Description: ").strip()

        try:
            success, message = calendar_manager.academic_deadlines.create_project_milestone(
                project_name, milestone_name, due_date, description=description
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")

    elif choice == '2':
        milestone_id = input("Milestone ID: ").strip()
        if not milestone_id:
            print("Milestone ID is required.")
            return

        try:
            progress = float(input("Completion percentage (0-100): "))
            success, message = calendar_manager.academic_deadlines.update_milestone_progress(
                milestone_id, progress
            )
            print(message)
        except (ValueError, Exception) as e:
            print(f"Error: {e}")

    elif choice == '3':
        student_id = input("Student ID: ").strip()
        if not student_id:
            print("Student ID is required.")
            return

        try:
            result = calendar_manager.academic_deadlines.track_graduation_requirements(student_id)
            if 'error' in result:
                print(f"Error: {result['error']}")
            else:
                print(f"Student: {result['student_id']}")
                print(f"Total Requirements: {result['total_requirements']}")
                print(f"Completed: {result['completed_requirements']}")
                print(f"Overall Progress: {result['overall_completion_percentage']}%")
                print(f"Graduation Eligible: {result['graduation_eligible']}")
        except Exception as e:
            print(f"Error: {e}")

    input("\nPress Enter to continue...")

def handle_event_dependencies(calendar_manager):
    """Handle event dependencies menu"""
    print("\nEVENT DEPENDENCIES")
    print("-" * 30)
    print("1. Add dependency")
    print("2. Create workflow")
    print("3. Calculate automatic deadlines")
    print("4. Return to main menu")

    choice = input("Select option (1-4): ")

    if choice == '1':
        prerequisite_id = input("Prerequisite Event ID: ").strip()
        dependent_id = input("Dependent Event ID: ").strip()
        dependency_type = input("Dependency Type (blocking/informational): ").strip() or "blocking"
        delay_days = int(input("Delay Days (default 0): ") or "0")

        try:
            success, message = calendar_manager.event_dependencies.add_event_dependency(
                prerequisite_id, dependent_id, dependency_type, delay_days
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")

    elif choice == '2':
        workflow_name = input("Workflow Name: ").strip()
        description = input("Description: ").strip()

        try:
            success, message = calendar_manager.event_dependencies.create_workflow(
                workflow_name, description
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")

    elif choice == '3':
        base_event_id = input("Base Event ID: ").strip()
        deadline_rules = [
            {'name': 'Assignment Due', 'days_before': 7, 'event_type': 'Deadline'},
            {'name': 'Study Reminder', 'days_before': 3, 'event_type': 'Reminder'}
        ]

        try:
            deadlines = calendar_manager.event_dependencies.calculate_automatic_deadlines(
                base_event_id, deadline_rules
            )
            print(f"Generated {len(deadlines)} automatic deadlines:")
            for deadline in deadlines:
                print(f"- {deadline['name']}: {deadline['date']}")
        except Exception as e:
            print(f"Error: {e}")

    input("\nPress Enter to continue...")

def handle_bulk_operations(calendar_manager):
    """Handle bulk operations menu"""
    print("\nBULK OPERATIONS")
    print("-" * 30)
    print("1. Bulk create events")
    print("2. Bulk update events")
    print("3. Create event template")
    print("4. Return to main menu")

    choice = input("Select option (1-4): ")

    if choice == '1':
        print("\nBulk Create Events")
        print("Enter events one by one (press Enter with empty name to finish):")

        events_data = []
        while True:
            name = input(f"Event {len(events_data) + 1} name (or Enter to finish): ").strip()
            if not name:
                break

            date = input("Date (YYYY-MM-DD): ").strip()
            event_type = input("Event type (Academic/Holiday/Administrative): ").strip() or "Academic"
            description = input("Description: ").strip()

            events_data.append({
                'name': name,
                'date': date,
                'event_type': event_type,
                'description': description
            })

        if events_data:
            try:
                result = calendar_manager.batch_operations.bulk_create_events(events_data)
                print(f"Created {result['created_count']} events successfully")
                if result['failed_count'] > 0:
                    print(f"Failed to create {result['failed_count']} events")
            except Exception as e:
                print(f"Error: {e}")

    elif choice == '2':
        event_ids = input("Event IDs (comma-separated): ").strip().split(',')
        event_ids = [eid.strip() for eid in event_ids if eid.strip()]

        if not event_ids:
            print("No event IDs provided.")
            return

        update_data = {}
        new_type = input("New event type (optional): ").strip()
        if new_type:
            update_data['event_type'] = new_type

        new_description = input("New description (optional): ").strip()
        if new_description:
            update_data['description'] = new_description

        if update_data:
            try:
                result = calendar_manager.batch_operations.bulk_update_events(event_ids, update_data)
                print(f"Updated {result['updated_count']} events successfully")
                if result['failed_count'] > 0:
                    print(f"Failed to update {result['failed_count']} events")
            except Exception as e:
                print(f"Error: {e}")

    elif choice == '3':
        template_name = input("Template Name: ").strip()
        if not template_name:
            print("Template name is required.")
            return

        template_data = {
            'event_type': input("Default Event Type: ").strip() or "Academic",
            'description': input("Default Description: ").strip()
        }

        try:
            success, message = calendar_manager.batch_operations.create_event_template(
                template_name, template_data
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")

    input("\nPress Enter to continue...")

def handle_advanced_reports(calendar_manager):
    """Handle advanced reporting menu"""
    print("\nADVANCED REPORTS")
    print("-" * 30)
    print("1. Attendance report")
    print("2. Resource utilization report")
    print("3. Academic year summary")
    print("4. Return to main menu")

    choice = input("Select option (1-4): ")

    try:
        if choice == '1':
            course_id = input("Course ID (optional): ").strip() or None
            report = calendar_manager.advanced_reporting.generate_attendance_report(course_id)
            if report['success']:
                print(f"Total Events: {report['total_events']}")
                print(f"Average Attendance: {report['average_attendance']}")
            else:
                print(f"Error: {report['error']}")

        elif choice == '2':
            resource_type = input("Resource type (optional): ").strip() or None
            report = calendar_manager.advanced_reporting.generate_utilization_report(resource_type)
            if report['success']:
                print(f"Total Resources: {report['total_resources']}")
                for resource in report['resources'][:5]:  # Show first 5
                    print(f"- {resource['resource_name']}: {resource['utilization_percentage']:.1f}% utilized")
            else:
                print(f"Error: {report['error']}")

        elif choice == '3':
            academic_year = input("Academic Year ID: ").strip()
            if academic_year:
                report = calendar_manager.advanced_reporting.generate_academic_year_summary(academic_year)
                if report['success']:
                    print(f"Academic Year: {academic_year}")
                    print(f"Total Events: {report['total_events']}")
                    print("Event Types:")
                    for event_type, count in report['event_statistics'].items():
                        print(f"  {event_type}: {count}")
                else:
                    print(f"Error: {report['error']}")
    except Exception as e:
        print(f"Error generating report: {e}")

    input("\nPress Enter to continue...")

def handle_visualizations(calendar_manager):
    """Handle data visualizations menu"""
    print("\nDATA VISUALIZATIONS")
    print("-" * 30)
    print("1. Calendar heatmap")
    print("2. Event distribution chart")
    print("3. Timeline visualization")
    print("4. Conflict visualization")
    print("5. Return to main menu")

    choice = input("Select option (1-5): ")

    try:
        if choice == '1':
            year = int(input("Year: "))
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.visualizations.create_calendar_heatmap(year, output_path)
            print(message)

        elif choice == '2':
            timeframe = input("Timeframe (month/semester/year): ").strip() or "month"
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.visualizations.create_event_distribution_chart(timeframe, output_path)
            print(message)

        elif choice == '3':
            academic_year = input("Academic Year ID: ").strip()
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.enhanced_visualizations.create_timeline_visualization(academic_year, output_path)
            print(message)

        elif choice == '4':
            start_date = input("Start Date (YYYY-MM-DD): ").strip()
            end_date = input("End Date (YYYY-MM-DD): ").strip()
            output_path = input("Output file path (optional): ").strip() or None
            success, message = calendar_manager.enhanced_visualizations.create_conflict_visualization(
                (start_date, end_date), output_path
            )
            print(message)

    except (ValueError, Exception) as e:
        print(f"Error: {e}")

    input("\nPress Enter to continue...")

def handle_system_management(calendar_manager):
    """Handle system management menu"""
    print("\nSYSTEM MANAGEMENT")
    print("-" * 30)
    print("1. Create backup")
    print("2. Import holidays")
    print("3. Calendar sync")
    print("4. User timezone settings")
    print("5. Return to main menu")

    choice = input("Select option (1-5): ")

    try:
        if choice == '1':
            backup_path = input("Backup file path (leave blank for auto): ").strip()
            backup_path = backup_path if backup_path else None
            result = calendar_manager.create_backup(backup_path)
            print(result['message'])

        elif choice == '2':
            if not HOLIDAYS_AVAILABLE:
                print("holidays library is required for this feature.")
                return

            country_code = input("Country code (e.g., US, UK, CA): ").upper().strip()
            year_str = input("Year: ").strip()
            region = input("Region/State (optional): ").strip()

            year = int(year_str)
            region = region if region else None

            success, message = calendar_manager.holidays.import_national_holidays(country_code, year, region)
            print(message)

        elif choice == '3':
            ical_url = input("iCal URL: ").strip()
            if ical_url:
                result = calendar_manager.calendar_sync(ical_url)
                print(f"Synced: {result['synced']} events")
                print(f"Skipped: {result['skipped_holidays']} holidays")
                if result['conflicts']:
                    print(f"Conflicts: {len(result['conflicts'])}")

        elif choice == '4':
            if not TIMEZONE_AVAILABLE:
                print("pytz library is required for timezone features.")
                return

            user_id = calendar_manager.auth_manager.current_user['id']
            timezone_name = input("Timezone (e.g., US/Eastern, Europe/London): ").strip()

            if timezone_name:
                success, message = calendar_manager.timezone_manager.set_user_timezone(user_id, timezone_name)
                print(message)

    except (ValueError, Exception) as e:
        print(f"Error: {e}")

    input("\nPress Enter to continue...")

def display_calendar_data(calendar_data):
    """Display calendar data in a formatted way"""
    if not calendar_data:
        print("No calendar data to display.")
        return

    print("\nCALENDAR DISPLAY:")
    print("=" * 80)

    current_semester = None
    for item in calendar_data:
        if current_semester != item['semester_name']:
            current_semester = item['semester_name']
            print(f"\n{current_semester} SEMESTER")
            print(f"Period: {item['semester_start']} to {item['semester_end']}")
            print("-" * 60)

        if item['event_name']:
            if item['date']:
                event_date = item['date']
            else:
                event_date = f"{item['date_start']} to {item['date_end']}"

            print(f"{event_date:<20} {item['event_name']:<30} ({item['event_type']})")
            if item['description']:
                print(f"{'':20} {item['description']}")

    print("=" * 80)

def display_events_list(events):
    """Display a list of events"""
    if not events:
        print("No events found.")
        return

    print(f"\nFOUND {len(events)} EVENTS:")
    print("=" * 100)
    print(f"{'ID':<8} {'Date':<20} {'Event Name':<30} {'Type':<15} {'Description':<25}")
    print("-" * 100)

    for event in events:
        event_id = event['id'][:8] + "..." if len(event['id']) > 8 else event['id']

        # Build the date string separately
        if event['date']:
            event_date = event['date']
        else:
            event_date = f"{event['date_start']} to {event['date_end']}"

        description = (event['description'] or '')[:25]
        if len(event['description'] or '') > 25:
            description += "..."

        print(f"{event_id:<8} {event_date:<20} {event['name']:<30} {event['event_type']:<15} {description:<25}")

    print("=" * 100)

def ensure_calendar_permissions(auth=None):
    """Ensure calendar permissions exist in the main auth system"""
    from education_system.university_system.infrastructure.auth import UserAuth
    from education_system.university_system.infrastructure.shared_context import get_auth

    calendar_permissions = [
        ('manage_schedules', 'Manage Academic Schedules'),
        ('view_own_timetable', 'View Own Academic Timetable'),
        ('manage_academic_calendar', 'Manage Academic Calendar'),
        ('view_academic_calendar', 'View Academic Calendar'),
        ('create_academic_events', 'Create Academic Events'),
        ('update_academic_events', 'Update Academic Events'),
        ('delete_academic_events', 'Delete Academic Events'),
        ('export_calendar_data', 'Export Calendar Data')
    ]

    try:
        # Try to get centralized auth first if not provided
        if auth is None:
            auth = get_auth()
        if auth is None:
            auth = UserAuth()
        conn = sqlite3.connect(auth.db_path)
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for perm_name, perm_desc in calendar_permissions:
            # Check if permission exists
            cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm_name,))
            if not cursor.fetchone():
                cursor.execute(
                    'INSERT INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
                    (perm_name, perm_desc, timestamp)
                )

        conn.commit()
        conn.close()

        # Reinitialize the auth system to pick up new permissions
        auth._init_db()

    except Exception as e:
        logger.warning(f"Could not ensure calendar permissions: {e}")

def _verify_required_tables(self):
    """Verify that required tables exist, create missing ones"""
    try:
        required_tables = [
            'academic_years',
            'semesters',
            'events',
            'event_categories'
        ]

        from education_system.university_system.core.sql_safety import validate_identifier
        for table in required_tables:
            try:
                # Test if table exists by querying it
                safe_table = validate_identifier(table, "table")
                self.db_manager.execute_query("SELECT COUNT(*) FROM [" + safe_table + "] LIMIT 1")
                logging.debug(f"Table {table} exists")
            except Exception:
                # Table doesn't exist, create it
                logging.info(f"Creating missing table: {table}")

                if table == 'academic_years':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS academic_years (
                            id TEXT PRIMARY KEY,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            date_added TEXT NOT NULL,
                            CONSTRAINT valid_dates CHECK (start_date < end_date)
                        )
                    ''')

                elif table == 'semesters':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS semesters (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            academic_year_id TEXT NOT NULL,
                            name TEXT NOT NULL,
                            start_date TEXT NOT NULL,
                            end_date TEXT NOT NULL,
                            registration_start TEXT,
                            registration_end TEXT,
                            final_exams_start TEXT,
                            final_exams_end TEXT,
                            date_added TEXT NOT NULL,
                            FOREIGN KEY (academic_year_id) REFERENCES academic_years (id) ON DELETE CASCADE,
                            UNIQUE(academic_year_id, name),
                            CONSTRAINT valid_semester_dates CHECK (start_date < end_date)
                        )
                    ''')

                elif table == 'events':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS academic_calendar_events (
                            id TEXT PRIMARY KEY,
                            name TEXT NOT NULL,
                            date TEXT,
                            date_start TEXT,
                            date_end TEXT,
                            description TEXT,
                            event_type TEXT DEFAULT 'Academic',
                            date_added TEXT NOT NULL,
                            last_modified TEXT,
                            created_by TEXT,
                            CONSTRAINT valid_event_dates CHECK (
                                (date IS NOT NULL AND date_start IS NULL AND date_end IS NULL) OR
                                (date IS NULL AND date_start IS NOT NULL AND date_end IS NOT NULL AND date_start <= date_end)
                            )
                        )
                    ''')

                elif table == 'event_categories':
                    self.db_manager.execute_update('''
                        CREATE TABLE IF NOT EXISTS event_categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT UNIQUE NOT NULL,
                            color_code TEXT,
                            description TEXT,
                            date_added TEXT NOT NULL
                        )
                    ''')

                logging.info(f"Successfully created table: {table}")

        logger.info("Required tables verified/created successfully")
        return True

    except Exception as e:
        logger.error(f"Table verification failed: {e}")
        raise DatabaseError(f"Table verification failed: {e}")

def fix_calendar_database():
    """Quick fix for calendar database issues"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if there's a conflicting role_permissions table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='role_permissions'")
        if cursor.fetchone():
            # Check the schema
            cursor.execute("PRAGMA table_info(role_permissions)")
            columns = [col[1] for col in cursor.fetchall()]

            if 'role' in columns and 'permission' in columns:
                # This is the problematic table from academic calendar
                print("Found conflicting role_permissions table. Renaming it...")
                cursor.execute("ALTER TABLE role_permissions RENAME TO old_role_permissions")
                print("Conflicting table renamed to old_role_permissions")

        conn.commit()
        conn.close()
        print("Database fix completed successfully!")

    except Exception as e:
        print(f"Database fix failed: {e}")

# Run this once
fix_calendar_database()
