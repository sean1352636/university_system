from education_system.university_system.modules.domain.mobility.services.trip_management import _common
from education_system.university_system.modules.domain.mobility.services.trip_management._common import get_text, logging, CALENDAR_AVAILABLE, log_menu_navigation
from education_system.university_system.modules.domain.mobility.services.trip_management.database import init_trip_db
from education_system.university_system.modules.domain.mobility.services.trip_management.permissions import setup_trip_permissions, setup_report_permissions
from education_system.university_system.modules.domain.mobility.services.trip_management.trips import view_trips, view_trips_with_calendar, create_trip, update_trip, delete_trip
from education_system.university_system.modules.domain.mobility.services.trip_management.registrations import (
    register_for_trip, view_my_trip_registrations, manage_trip_participants,
)
from education_system.university_system.modules.domain.mobility.services.trip_management.reports import generate_trip_report
from education_system.university_system.modules.domain.mobility.services.trip_management.calendar_integration import create_trip_calendar_event, view_trip_events_in_calendar

# Conditional calendar imports
if CALENDAR_AVAILABLE:
    from education_system.university_system.modules.domain.mobility.services.trip_management._common import AcademicCalendarManager, CalendarConfig


@log_menu_navigation(description="Displaying trip management menu")
def display_trip_management_menu():
    """Display the main trip management menu with calendar integration"""
    auth = _common.auth

    if not auth or not auth.current_user:
        print(get_text("mobility.trip_management.auth.must_login_access", "You must be logged in to access trip management."))
        return

    # Initialize calendar system if available
    calendar_manager = None
    if CALENDAR_AVAILABLE:
        try:
            config = CalendarConfig()
            calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)
        except Exception as e:
            logging.warning(f"Could not initialize calendar system: {e}")

    while True:
        print(get_text("mobility.trip_management.menu.title", "\nIntegrated Trip Management & Calendar System"))
        username = auth.current_user.get('username', 'User')
        role = auth.current_user.get('role', 'user')
        print(get_text("mobility.trip_management.menu.logged_in_as", "Logged in as: {username} ({role})").format(username=username, user=username, role=role))
        print("=" * 60)

        # Build menu based on permissions
        options = []
        option_num = 1

        # Trip management options
        print(get_text("mobility.trip_management.menu.trip_management_section", "TRIP MANAGEMENT:"))
        if auth.check_permission('view_trips'):
            print(f"{option_num}. " + get_text("mobility.trip_management.menu.view_all_trips", "View All Trips"))
            options.append(('view_trips', view_trips))
            option_num += 1

            if CALENDAR_AVAILABLE:
                print(f"{option_num}. " + get_text("mobility.trip_management.menu.view_trips_calendar", "View Trips with Calendar Info"))
                options.append(('view_trips_calendar', view_trips_with_calendar))
                option_num += 1

        if auth.check_permission('create_trips'):
            print(f"{option_num}. " + get_text("mobility.trip_management.menu.create_new_trip", "Create New Trip"))
            options.append(('create_trip', create_trip))
            option_num += 1

        if auth.check_permission('manage_trips'):
            print(f"{option_num}. " + get_text("mobility.trip_management.menu.update_trip", "Update Trip"))
            options.append(('update_trip', update_trip))
            option_num += 1

            print(f"{option_num}. " + get_text("mobility.trip_management.menu.delete_trip", "Delete Trip"))
            options.append(('delete_trip', delete_trip))
            option_num += 1

        if auth.check_permission('register_for_trips'):
            print(f"{option_num}. " + get_text("mobility.trip_management.menu.register_for_trip", "Register for Trip"))
            options.append(('register_trip', register_for_trip))
            option_num += 1

        if auth.check_permission('view_own_trip_registrations'):
            print(f"{option_num}. " + get_text("mobility.trip_management.menu.view_my_registrations", "View My Registrations"))
            options.append(('view_registrations', view_my_trip_registrations))
            option_num += 1

        if auth.check_permission('manage_trip_participants'):
            print(f"{option_num}. " + get_text("mobility.trip_management.menu.manage_participants", "Manage Participants"))
            options.append(('manage_participants', manage_trip_participants))
            option_num += 1

        if auth.check_permission('generate_trip_reports'):
            print(f"{option_num}. " + get_text("mobility.trip_management.menu.generate_report", "Generate Trip Report"))
            options.append(('generate_report', generate_trip_report))
            option_num += 1

        # Calendar integration options
        if CALENDAR_AVAILABLE and calendar_manager:
            print("\n" + get_text("mobility.trip_management.menu.calendar_integration_section", "CALENDAR INTEGRATION:"))
            if auth.check_permission('manage_schedules'):
                print(f"{option_num}. " + get_text("mobility.trip_management.menu.create_calendar_event", "Create Calendar Event for Trip"))
                options.append(('create_trip_calendar_event', lambda: create_trip_calendar_event(calendar_manager)))
                option_num += 1

            if auth.check_permission('view_own_timetable'):
                print(f"{option_num}. " + get_text("mobility.trip_management.menu.view_trip_events", "View Trip Events in Calendar"))
                options.append(('view_trip_events', lambda: view_trip_events_in_calendar(calendar_manager)))
                option_num += 1

        print(f"\n{option_num}. " + get_text("mobility.trip_management.menu.return_to_main", "Return to Main Menu"))

        try:
            choice = int(input(get_text("mobility.trip_management.menu.enter_choice", "\nEnter your choice (1-{max}): ").format(max=option_num)))

            if choice == option_num:  # Return to main menu
                break
            elif 1 <= choice <= len(options):
                action_name, action_func = options[choice - 1]
                try:
                    action_func()
                except Exception as e:
                    print(get_text("mobility.trip_management.errors.executing_action", "Error executing {action}: {error}").format(action=action_name, error=e))
                    logging.error(get_text("mobility.trip_management.errors.in_action", "Error in {action}: {error}").format(action=action_name, error=e))

                input(get_text("mobility.trip_management.common.press_enter", "\nPress Enter to continue..."))
            else:
                print(get_text("mobility.trip_management.validation.invalid_choice_try_again", "Invalid choice. Please try again."))

        except ValueError:
            print(get_text("mobility.trip_management.validation.enter_valid_number", "Please enter a valid number."))
        except KeyboardInterrupt:
            print(get_text("mobility.trip_management.common.operation_cancelled", "\nOperation cancelled."))
            break
        except Exception as e:
            print(get_text("mobility.trip_management.errors.unexpected", "Unexpected error: {error_type}: {error}").format(error_type=type(e).__name__, error=e))
            logging.error(get_text("mobility.trip_management.errors.in_trip_menu", "Unexpected error in trip menu: {error}").format(error=e))


def integrate_trip_management_with_main():
    """Initialize trip management system for integration with main system"""
    try:
        print(get_text("mobility.trip_management.init.initializing", "Initializing trip management system..."))

        # Initialize database
        if not init_trip_db():
            print(get_text("mobility.trip_management.init.db_failed", "Failed to initialize trip management database."))
            return False

        # Setup permissions
        if not setup_trip_permissions():
            print(get_text("mobility.trip_management.init.permissions_failed", "Failed to setup trip management permissions."))
            return False

        print(get_text("mobility.trip_management.init.success", "Trip management system initialized successfully!"))
        return True

    except Exception as e:
        logging.error(get_text("mobility.trip_management.init.error", "Failed to initialize trip management: {error}").format(error=e))
        print(get_text("mobility.trip_management.init.error", "Error initializing trip management: {error}").format(error=e))
        return False


def test_report_generation():
    """Test the report generation system"""
    from education_system.university_system.modules.domain.mobility.services.trip_management._common import PDF_AVAILABLE
    print(get_text("mobility.trip_management.test.report_testing", "Testing Trip Report Generation System..."))

    try:
        # Test permission setup
        if setup_report_permissions():
            print(get_text("mobility.trip_management.test.report_permissions_success", "Report permissions setup successful"))
        else:
            print(get_text("mobility.trip_management.test.report_permissions_failed", "Report permissions setup failed"))
            return

        print(get_text("mobility.trip_management.test.report_completed", "Report generation system test completed successfully!"))
        print(get_text("mobility.trip_management.test.pdf_available", "PDF Generation Available: {available}").format(available=PDF_AVAILABLE))

    except Exception as e:
        print(get_text("mobility.trip_management.test.failed", "Test failed: {error}").format(error=e))
        logging.error(get_text("mobility.trip_management.test.error", "Report generation test error: {error}").format(error=e))


# Test function
def test_trip_management():
    """Test the trip management system"""
    print(get_text("mobility.trip_management.test.testing", "Testing Trip Management System..."))

    try:
        # Test database initialization
        if init_trip_db():
            print(get_text("mobility.trip_management.test.db_success", "Database initialization successful"))
        else:
            print(get_text("mobility.trip_management.test.db_failed", "Database initialization failed"))
            return

        # Test permission setup
        if setup_trip_permissions():
            print(get_text("mobility.trip_management.test.permissions_success", "Permission setup successful"))
        else:
            print(get_text("mobility.trip_management.test.permissions_failed", "Permission setup failed"))
            return

        print(get_text("mobility.trip_management.test.completed", "Trip management system test completed successfully!"))

    except Exception as e:
        print(get_text("mobility.trip_management.test.failed", "Test failed: {error}").format(error=e))
        logging.error(get_text("mobility.trip_management.test.error", "Trip management test error: {error}").format(error=e))
