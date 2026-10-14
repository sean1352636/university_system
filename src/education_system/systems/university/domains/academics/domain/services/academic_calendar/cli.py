from education_system.systems.university.infrastructure.database.db import sqlite3
import logging
import os
from datetime import datetime
from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
    display_language_menu_option,
)

from education_system.systems.university.domains.academics.domain.services.academic_calendar.exceptions import CalendarError, ValidationError, DatabaseError, PermissionError
from education_system.systems.university.domains.academics.domain.services.academic_calendar.config import CalendarConfig, ValidationUtils

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
    from education_system.systems.university.infrastructure.auth import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

# The event types offered wherever an event is created. Kept in one place so
# the add-event, recurring-event and bulk-create prompts cannot drift apart.
EVENT_TYPES = ["Academic", "Holiday", "Administrative", "Social", "Sports", "Deadline"]

# How many menu options to print per row.
MENU_COLUMNS = 5


def set_auth(auth_manager):
    """Set the authentication manager for the calendar system"""
    global auth
    auth = auth_manager
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_manager)


def print_menu_grid(entries, columns=MENU_COLUMNS, width=30):
    """Print "N. Label" entries across a grid instead of one per line.

    The calendar menu had grown to ~25 options in a single column, which
    scrolls the header off the screen before the operator reaches the prompt.
    """
    for row_start in range(0, len(entries), columns):
        row = entries[row_start:row_start + columns]
        print("".join(f"{number}. {label}".ljust(width) for number, label in row).rstrip())


def prompt_event_type(prompt="Select event type", default="Academic"):
    """Pick an event type from a numbered list rather than typing it free-hand.

    Returns the chosen type, or None if the operator entered something invalid.
    Pressing Enter accepts *default*.
    """
    print("\nEvent Types:")
    print_menu_grid([(i, get_text(f'calendar.event_types.{et.lower()}', default=et))
                     for i, et in enumerate(EVENT_TYPES, 1)], columns=3, width=22)

    raw = input(f"{prompt} (1-{len(EVENT_TYPES)}, Enter for {default}): ").strip()
    if not raw:
        return default
    if not raw.isdigit() or not (1 <= int(raw) <= len(EVENT_TYPES)):
        print("Invalid event type selected.")
        return None
    return EVENT_TYPES[int(raw) - 1]


def choose_from_db(rows, what, label, allow_blank=False):
    """Let the operator pick one of *rows* by number instead of typing an id.

    *rows* is a list of sqlite rows/tuples whose first column is the id;
    *label* formats a row for display. Returns the chosen id, "" when blank is
    allowed and the operator just pressed Enter, or None when there is nothing
    to choose or the choice was invalid. Typing an id directly still works, but
    it is checked against the list — the prompts these replace accepted any
    text at all and then reported a confusing "not found" from deep in a query.
    """
    if not rows:
        print(f"No {what} found in the database.")
        return None

    print(f"\nAvailable {what}:")
    for i, row in enumerate(rows, 1):
        print(f"{i:>3}. {label(row)}")

    suffix = ", Enter for all" if allow_blank else ""
    raw = input(f"\nSelect {what[:-1] if what.endswith('s') else what} (1-{len(rows)}{suffix}): ").strip()

    if not raw:
        if allow_blank:
            return ""
        print("A selection is required.")
        return None

    if raw.isdigit() and 1 <= int(raw) <= len(rows):
        return rows[int(raw) - 1][0]

    # Typed an id directly — only accept it if it is actually in the list.
    for row in rows:
        if str(row[0]).lower() == raw.lower():
            return row[0]

    print(f"'{raw}' is not one of the {what} listed above.")
    return None


def fetch_rows(query, params=()):
    """Run a read-only lookup against the university database."""
    try:
        conn = get_connection()
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Lookup failed: {e}")
        print(f"Could not read from the database: {e}")
        return []


def open_image(path):
    """Open a generated chart in the desktop image viewer.

    The manager's own safe_open_file() reduces its argument to a bare
    basename, so it only works for files in the current directory; charts are
    written to the exports directory, hence the local opener.
    """
    import platform
    import subprocess

    path = str(path)
    # A generator can report success without drawing anything — the conflict
    # chart returns "No conflicts found in date range" and writes no file.
    if not os.path.exists(path):
        print("Nothing to display — no chart image was produced.")
        return False

    try:
        if platform.system() == "Windows":
            os.startfile(path)  # noqa: F821 - Windows only
        elif platform.system() == "Darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
        print(f"Opened {path}")
        return True
    except Exception as e:
        logger.error(f"Could not open {path}: {e}")
        print(f"Chart saved to {path} (could not open it automatically: {e})")
        return False


def chart_path(stem):
    """Absolute path for a generated chart, timestamped so runs do not clash."""
    from education_system import paths

    directory = paths.UNIVERSITY_EXPORTS_REPORTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return directory / f"{stem}_{stamp}.png"

def display_academic_calendar_menu():
    """Display the academic calendar management menu"""
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
        from education_system.systems.university.domains.academics.domain.services.academic_calendar.calendar_core import AcademicCalendarManager
        config = CalendarConfig()
        calendar_manager = AcademicCalendarManager(config=config, auth_manager=auth)

        # Create a simple menu interface
        while True:
            print(f"\n{get_text('calendar.title', default='Academic Calendar')}")
            print("=" * 55)
            print(get_text('calendar.logged_in_as', default='Logged in as: {username} ({role})').format(
                username=auth.current_user['username'], role=auth.current_user['role']))

            options = []

            def section(title, icon):
                """Start a section; options added after it print under it."""
                print(f"\n{icon} {title}:")

            def add(label, action):
                """Register an option and return its "N. Label" grid entry."""
                options.append((label, action))
                return (len(options), label)

            # Calendar options
            section(get_text('calendar.sections.calendar_mgmt', default='CALENDAR MANAGEMENT'), "\U0001f4c5")
            row = []
            if auth.check_permission('manage_schedules'):
                row.append(add(get_text('calendar.menu.add_event', default='Add Event'),
                               lambda: handle_add_event(calendar_manager)))
                row.append(add(get_text('calendar.menu.update_event', default='Update Event'),
                               lambda: handle_update_event(calendar_manager)))
                row.append(add(get_text('calendar.menu.delete_event', default='Delete Event'),
                               lambda: handle_delete_event(calendar_manager)))
            row.append(add(get_text('calendar.menu.view_calendar', default='View Calendar'),
                           lambda: handle_view_calendar(calendar_manager)))
            row.append(add(get_text('calendar.menu.search_events', default='Search Events'),
                           lambda: handle_search_events(calendar_manager)))
            if auth.check_permission('export_data'):
                row.append(add(get_text('calendar.menu.export_calendar', default='Export Calendar'),
                               lambda: handle_export_calendar(calendar_manager)))
            if auth.check_permission('manage_schedules'):
                row.append(add(get_text('calendar.menu.import_calendar', default='Import Calendar'),
                               lambda: handle_import_calendar(calendar_manager)))
            print_menu_grid(row)

            # Academic structure
            if auth.check_permission('manage_schedules'):
                section(get_text('calendar.sections.academic_structure', default='ACADEMIC STRUCTURE'), "\U0001f4da")
                row = [
                    add(get_text('calendar.menu.add_academic_year', default='Add Academic Year'),
                        lambda: handle_add_academic_year(calendar_manager)),
                    add(get_text('calendar.menu.add_semester', default='Add Semester'),
                        lambda: handle_add_semester(calendar_manager)),
                    add(get_text('calendar.menu.recurring_event', default='Recurring Events'),
                        lambda: handle_recurring_events(calendar_manager)),
                    add(get_text('calendar.menu.event_dependencies', default='Event Dependencies'),
                        lambda: handle_event_dependencies(calendar_manager)),
                    add(get_text('calendar.menu.project_milestones', default='Project Milestones'),
                        lambda: handle_project_milestones(calendar_manager)),
                    add(get_text('calendar.menu.bulk_operations', default='Bulk Operations'),
                        lambda: handle_bulk_operations(calendar_manager)),
                ]
                print_menu_grid(row)

            # Reporting & Visualizations
            if auth.check_permission('export_data') or auth.check_permission('view_reports'):
                section(get_text('calendar.sections.reporting', default='REPORTING & VISUALIZATIONS'), "\U0001f4ca")
                print_menu_grid([
                    add(get_text('calendar.menu.advanced_reports', default='Advanced Reports'),
                        lambda: handle_advanced_reports(calendar_manager)),
                    add(get_text('calendar.menu.visualizations', default='Data Visualizations'),
                        lambda: handle_visualizations(calendar_manager)),
                ])

            # System management
            if auth.check_permission('system_config') or auth.check_permission('manage_schedules'):
                section(get_text('calendar.sections.system', default='SYSTEM MANAGEMENT'), "\U0001f6e0")
                print_menu_grid([
                    add(get_text('calendar.menu.system_management', default='System Management'),
                        lambda: handle_system_management(calendar_manager)),
                    add(get_text('calendar.menu.restore_database', default='Restore Database'),
                        lambda: handle_restore_database(calendar_manager)),
                ])

            # Language option
            section(get_text('calendar.sections.settings', default='SETTINGS'), "\U0001f310")
            print_menu_grid([add(get_text('calendar.menu.language', default='Language'),
                                 display_language_menu_option)])

            return_option = len(options) + 1
            print(f"\n{return_option}. {get_text('calendar.menu.return_main', default='Return to Main Menu')}")

            choice = input(f"\n{get_text('calendar.select_option', default='Select option')} (1-{return_option}): ").strip()

            try:
                choice_num = int(choice)

                if choice_num == return_option:  # Return to main menu
                    break
                elif 1 <= choice_num <= len(options):
                    action_name, action_func = options[choice_num - 1]
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
                choice_num = None
            except KeyboardInterrupt:
                print(f"\n{get_text('calendar.returning', default='Returning to main menu...')}")
                break
            except Exception as e:
                print(get_text('calendar.error_occurred', default='An error occurred: {error}').format(error=e))
                choice_num = None

            # The single pause in the whole menu. Handlers used to prompt as
            # well, so every action asked twice; and an action that returned
            # early (missing name, bad date) scrolled past with no pause at all.
            if choice_num != return_option:
                input("\nPress Enter to continue...")

    except Exception as e:
        print(f"Error initializing calendar system: {e}")
        input("\nPress Enter to continue...")

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
        rows = calendar_manager.db_manager.execute_query("SELECT * FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,))
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
        rows = calendar_manager.db_manager.execute_query("SELECT name FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE id = ?", (event_id,))
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

            filename = input("Filename (without extension): ").strip()
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


def handle_import_calendar(calendar_manager):
    """Handle importing calendar from file"""
    print("\nImport Calendar")
    print("-" * 30)

    print("Supported formats:")
    formats = [
        ("JSON", "json"),
        ("CSV", "csv"),
        ("iCal", "ics"),
    ]

    for i, (name, ext) in enumerate(formats, 1):
        print(f"{i}. {name} (.{ext})")

    try:
        format_choice = int(input(f"Select format (1-{len(formats)}): "))

        if 1 <= format_choice <= len(formats):
            format_name, format_ext = formats[format_choice - 1]

            file_path = input(f"File path to import (.{format_ext}): ").strip()
            if not file_path:
                print("File path is required.")
                return

            import os
            if not os.path.exists(file_path):
                print(f"File not found: {file_path}")
                return

            result = calendar_manager.import_calendar(file_path, format_ext)
            if result.get('success'):
                print(f"\nImported {result.get('imported_count', 0)} events successfully.")
                if result.get('skipped_count', 0) > 0:
                    print(f"Skipped {result['skipped_count']} events (duplicates or errors).")
            else:
                print(f"\nImport failed: {result.get('message', 'Unknown error')}")
        else:
            print("Invalid choice.")

    except ValueError:
        print("Invalid choice.")
    except Exception as e:
        print(f"Import error: {e}")


def handle_restore_database(calendar_manager):
    """Handle restoring database from backup"""
    print("\nRestore Database")
    print("-" * 30)

    file_path = input("Backup file path: ").strip()
    if not file_path:
        print("File path is required.")
        return

    import os
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    confirm = input("WARNING: This will overwrite the current database. Continue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        print("Restore cancelled.")
        return

    try:
        result = calendar_manager.restore_backup(file_path)
        if result.get('success'):
            print(f"\nDatabase restored successfully: {result.get('message', '')}")
        else:
            print(f"\nRestore failed: {result.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"Restore error: {e}")


def handle_recurring_events(calendar_manager):
    """Recurring events: create, view, update and delete a series."""
    print("\nRECURRING EVENTS")
    print("-" * 30)
    print_menu_grid([(1, "Create recurring event"), (2, "View recurring events"),
                     (3, "Update recurring event"), (4, "Delete recurring event"),
                     (5, "Return to calendar menu")], columns=3, width=28)

    choice = input("\nSelect option (1-5): ").strip()

    if choice == '1':
        handle_create_recurring_event(calendar_manager)
    elif choice == '2':
        handle_view_recurring_events(calendar_manager)
    elif choice == '3':
        handle_update_recurring_event(calendar_manager)
    elif choice == '4':
        handle_delete_recurring_event(calendar_manager)
    elif choice != '5':
        print("Invalid choice.")


def list_recurring_series(calendar_manager, header="RECURRING EVENTS"):
    """Print every recurring series and return them, newest first."""
    try:
        series_list = calendar_manager.recurring_events.list_recurring_events()
    except Exception as e:
        print(f"Error loading recurring events: {e}")
        return []

    if not series_list:
        print("\nNo recurring events have been created yet.")
        return []

    print(f"\n{header} ({len(series_list)}):")
    print("=" * 100)
    print(f"{'#':<4}{'Name':<28}{'Start':<12}{'Type':<16}{'Pattern':<22}{'Occurrences':<12}")
    print("-" * 100)

    for i, series in enumerate(series_list, 1):
        interval = series['interval_count'] or 1
        pattern = f"every {interval} {series['frequency']}" if interval != 1 else str(series['frequency'])
        if series['end_date']:
            pattern += f" until {series['end_date']}"
        elif series['occurrence_count']:
            pattern += f" x{series['occurrence_count']}"

        print(f"{i:<4}{(series['name'] or '')[:27]:<28}"
              f"{(series['date'] or series['date_start'] or '-'):<12}"
              f"{(series['event_type'] or '-')[:15]:<16}{pattern[:21]:<22}{series['generated_count']:<12}")

    print("=" * 100)
    return series_list


def select_recurring_series(calendar_manager, action):
    """Show the series and let the operator pick one by number."""
    series_list = list_recurring_series(calendar_manager)
    if not series_list:
        return None

    raw = input(f"\nSelect a recurring event to {action} (1-{len(series_list)}): ").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(series_list)):
        print("Invalid selection.")
        return None
    return series_list[int(raw) - 1]


def handle_view_recurring_events(calendar_manager):
    """Show all recurring series, with the option to expand one."""
    series_list = list_recurring_series(calendar_manager)
    if not series_list:
        return

    raw = input("\nEnter a number for full details (or Enter to go back): ").strip()
    if not raw:
        return
    if not raw.isdigit() or not (1 <= int(raw) <= len(series_list)):
        print("Invalid selection.")
        return

    series = series_list[int(raw) - 1]
    print("\n" + "=" * 60)
    print(f"Name:         {series['name']}")
    print(f"Recurring ID: {series['id']}")
    print(f"Base event:   {series['base_event_id']}")
    print(f"Start date:   {series['date'] or series['date_start'] or '-'}")
    print(f"Type:         {series['event_type'] or '-'}")
    print(f"Description:  {series['description'] or '-'}")
    print(f"Frequency:    every {series['interval_count'] or 1} {series['frequency']}")
    print(f"Ends:         {series['end_date'] or (str(series['occurrence_count']) + ' occurrences' if series['occurrence_count'] else 'no end set')}")
    print(f"Occurrences:  {series['generated_count']} generated")
    print(f"Created:      {series['date_added']}")
    print("=" * 60)


def handle_update_recurring_event(calendar_manager):
    """Update a recurring series' name, description or type."""
    series = select_recurring_series(calendar_manager, "update")
    if not series:
        return

    print(f"\nUpdating '{series['name']}' (press Enter to keep a value)")
    print("Note: the recurrence pattern itself cannot be changed — its occurrences")
    print("      already exist as individual events. Delete and recreate to change it.")

    updates = {}

    new_name = input(f"Name [{series['name']}]: ").strip()
    if new_name:
        updates['name'] = new_name

    new_description = input(f"Description [{series['description'] or 'none'}]: ").strip()
    if new_description:
        updates['description'] = new_description

    change_type = input(f"Change event type from '{series['event_type']}'? (y/N): ").strip().lower()
    if change_type == 'y':
        event_type = prompt_event_type(default=series['event_type'] or "Academic")
        if event_type is None:
            return
        updates['event_type'] = event_type

    if not updates:
        print("Nothing to update.")
        return

    try:
        success, message = calendar_manager.recurring_events.update_recurring_event(series['id'], updates)
        print(message)
    except Exception as e:
        print(f"Error updating recurring event: {e}")


def handle_delete_recurring_event(calendar_manager):
    """Delete a recurring series and, optionally, its generated occurrences."""
    series = select_recurring_series(calendar_manager, "delete")
    if not series:
        return

    print(f"\n'{series['name']}' has {series['generated_count']} generated occurrences.")
    keep = input("Keep the generated occurrences as standalone events? (y/N): ").strip().lower()

    confirm = input(f"Delete recurring event '{series['name']}'? (yes/no): ").strip().lower()
    if confirm not in ('yes', 'y'):
        print("Deletion cancelled.")
        return

    try:
        success, message = calendar_manager.recurring_events.delete_recurring_event(
            series['id'], delete_occurrences=(keep != 'y')
        )
        print(message)
    except Exception as e:
        print(f"Error deleting recurring event: {e}")


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

    event_type = prompt_event_type()
    if event_type is None:
        return

    # Get recurrence pattern
    print("\nRecurrence Pattern:")
    print_menu_grid([(1, "Daily"), (2, "Weekly"), (3, "Monthly"), (4, "Yearly")], columns=4, width=14)

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
        print_menu_grid([(1, "End date"), (2, "Number of occurrences")], columns=2, width=26)

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
        # Pick from the students actually on file. The free-text prompt this
        # replaces accepted any string and then reported a bare "not found".
        students = fetch_rows(
            """SELECT student_id, first_name, last_name, course, status
               FROM students ORDER BY last_name, first_name"""
        )
        student_id = choose_from_db(
            students, "students",
            lambda r: f"{str(r[0]):<10} {f'{r[1]} {r[2]}':<26} {(r[3] or '-'):<24}"
                      + (f"[{r[4]}]" if r[4] else "")
        )
        if not student_id:
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


def handle_bulk_operations(calendar_manager):
    """Handle bulk operations menu"""
    print("\nBULK OPERATIONS")
    print("-" * 30)
    print_menu_grid([(1, "Bulk create events"), (2, "Bulk update events"),
                     (3, "Bulk view events"), (4, "Bulk delete events"),
                     (5, "Create event template"), (6, "Return to calendar menu")],
                    columns=3, width=26)

    choice = input("\nSelect option (1-6): ").strip()

    if choice == '1':
        print("\nBulk Create Events")
        print("Enter events one by one (press Enter with empty name to finish):")

        events_data = []
        while True:
            name = input(f"\nEvent {len(events_data) + 1} name (or Enter to finish): ").strip()
            if not name:
                break

            date = input("Date (YYYY-MM-DD): ").strip()
            if not ValidationUtils.validate_date(date):
                print("Invalid date format - event skipped.")
                continue

            event_type = prompt_event_type()
            if event_type is None:
                continue

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
                print(f"\nCreated {result['created_count']} events successfully")
                if result['failed_count'] > 0:
                    print(f"Failed to create {result['failed_count']} events")
            except Exception as e:
                print(f"Error: {e}")

    elif choice == '2':
        events = select_events_for_bulk("update")
        if not events:
            return

        update_data = {}

        change_type = input("Change the event type? (y/N): ").strip().lower()
        if change_type == 'y':
            new_type = prompt_event_type()
            if new_type is None:
                return
            update_data['event_type'] = new_type

        new_description = input("New description (Enter to keep): ").strip()
        if new_description:
            update_data['description'] = new_description

        if not update_data:
            print("Nothing to update.")
            return

        try:
            result = calendar_manager.batch_operations.bulk_update_events(
                [event['id'] for event in events], update_data
            )
            print(f"Updated {result['updated_count']} events successfully")
            if result['failed_count'] > 0:
                print(f"Failed to update {result['failed_count']} events")
        except Exception as e:
            print(f"Error: {e}")

    elif choice == '3':
        handle_bulk_view_events()

    elif choice == '4':
        handle_bulk_delete_events(calendar_manager)

    elif choice == '5':
        template_name = input("Template Name: ").strip()
        if not template_name:
            print("Template name is required.")
            return

        event_type = prompt_event_type("Default event type")
        if event_type is None:
            return

        template_data = {
            'event_type': event_type,
            'description': input("Default Description: ").strip()
        }

        try:
            success, message = calendar_manager.batch_operations.create_event_template(
                template_name, template_data
            )
            print(message)
        except Exception as e:
            print(f"Error: {e}")

    elif choice != '6':
        print("Invalid choice.")


def fetch_events(event_type=None, search=None, limit=50):
    """Recent calendar events, most recent first, for the bulk pickers."""
    query = """SELECT id, name, COALESCE(date, date_start) AS when_, event_type, description
               FROM (SELECT source_event_id AS id, title AS name, event_date AS date, start_datetime AS date_start, end_datetime AS date_end, description, event_type, created_at AS date_added, updated_at AS last_modified, created_by, start_time, end_time, location, audience, assignment_id, trip_id, organizer_name AS organizer, participants, status, country_code, region, is_active FROM unified_events uev WHERE uev.source_type = 'academic_calendar') WHERE 1=1"""
    params = []
    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)
    if search:
        query += " AND name LIKE ?"
        params.append(f"%{search}%")
    query += " ORDER BY COALESCE(date, date_start) DESC LIMIT ?"
    params.append(limit)
    return fetch_rows(query, tuple(params))


def print_events_table(rows):
    """Print numbered events for the bulk view/update/delete pickers."""
    print(f"\n{len(rows)} EVENTS:")
    print("=" * 105)
    print(f"{'#':<5}{'Date':<19}{'Event Name':<36}{'Type':<16}{'ID':<28}")
    print("-" * 105)
    for i, row in enumerate(rows, 1):
        # Dates may carry a time ("2026-07-22 09:00"), so every field is
        # truncated to its column rather than trusted to fit.
        print(f"{i:<5}{str(row[2] or '-')[:18]:<19}{(row[1] or '')[:35]:<36}"
              f"{(row[3] or '-')[:15]:<16}{str(row[0])[:27]:<28}")
    print("=" * 105)


def filter_events_prompt():
    """Shared filter prompt for the bulk event pickers."""
    search = input("Filter by name (Enter for all): ").strip() or None

    event_type = None
    if input("Filter by event type? (y/N): ").strip().lower() == 'y':
        event_type = prompt_event_type("Filter to type", default=None)
        if event_type is None:
            return None, None, False
    return search, event_type, True


def handle_bulk_view_events():
    """List calendar events, optionally filtered by name or type."""
    print("\nBULK VIEW EVENTS")
    print("-" * 30)

    search, event_type, ok = filter_events_prompt()
    if not ok:
        return

    rows = fetch_events(event_type=event_type, search=search)
    if not rows:
        print("No events matched.")
        return

    print_events_table(rows)


def select_events_for_bulk(action):
    """Pick several events by number for a bulk action.

    Returns a list of {'id', 'name'} dicts, or None if nothing was selected.
    """
    search, event_type, ok = filter_events_prompt()
    if not ok:
        return None

    rows = fetch_events(event_type=event_type, search=search)
    if not rows:
        print("No events matched.")
        return None

    print_events_table(rows)

    raw = input(f"\nNumbers to {action} (comma-separated, or 'all'): ").strip()
    if not raw:
        print("Nothing selected.")
        return None

    if raw.lower() == 'all':
        chosen = rows
    else:
        chosen = []
        for part in raw.split(','):
            part = part.strip()
            if not part.isdigit() or not (1 <= int(part) <= len(rows)):
                print(f"'{part}' is not one of the numbers listed.")
                return None
            chosen.append(rows[int(part) - 1])

    return [{'id': row[0], 'name': row[1]} for row in chosen]


def handle_bulk_delete_events(calendar_manager):
    """Delete several calendar events at once."""
    print("\nBULK DELETE EVENTS")
    print("-" * 30)

    events = select_events_for_bulk("delete")
    if not events:
        return

    print(f"\nAbout to delete {len(events)} event(s):")
    for event in events[:10]:
        print(f"  - {event['name']}")
    if len(events) > 10:
        print(f"  ... and {len(events) - 10} more")

    confirm = input(f"\nDelete these {len(events)} event(s)? (yes/no): ").strip().lower()
    if confirm not in ('yes', 'y'):
        print("Deletion cancelled.")
        return

    deleted = 0
    failed = []
    for event in events:
        try:
            result = calendar_manager.delete_event(event['id'])
            if isinstance(result, dict) and not result.get('success', True):
                failed.append(f"{event['name']}: {result.get('message', 'failed')}")
            else:
                deleted += 1
        except Exception as e:
            failed.append(f"{event['name']}: {e}")

    print(f"\nDeleted {deleted} event(s).")
    for failure in failed:
        print(f"  Failed - {failure}")


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
            # Pick from the courses on file rather than typing an id that is
            # silently accepted and then matches nothing.
            courses = fetch_rows(
                """SELECT id, COALESCE(code, course_code) AS code,
                          COALESCE(name, course_name) AS name, department
                   FROM courses ORDER BY COALESCE(code, course_code)"""
            )
            course_id = choose_from_db(
                courses, "courses",
                lambda r: f"{(r[1] or '-'):<12} {(r[2] or '-'):<40} {r[3] or ''}",
                allow_blank=True,
            )
            if course_id is None:
                return
            course_id = course_id or None  # blank means every course

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


def handle_visualizations(calendar_manager):
    """Handle data visualizations menu.

    Every option renders a PNG into the reports export directory and opens it
    in the desktop image viewer. The heatmap and distribution chart used to
    return an interactive HTML document when no output path was given, which
    the CLI then printed — a screenful of markup rather than a chart.
    """
    print("\nDATA VISUALIZATIONS")
    print("-" * 30)
    print_menu_grid([(1, "Calendar heatmap"), (2, "Event distribution"),
                     (3, "Timeline"), (4, "Conflicts"),
                     (5, "Return to calendar menu")], columns=3, width=24)

    choice = input("\nSelect option (1-5): ").strip()

    try:
        if choice == '1':
            year_raw = input(f"Year (Enter for {datetime.now().year}): ").strip()
            year = int(year_raw) if year_raw else datetime.now().year

            path = chart_path(f"calendar_heatmap_{year}")
            print("\nGenerating heatmap...")
            success, message = calendar_manager.visualizations.create_calendar_heatmap_image(year, str(path))
            print(message)
            if success:
                open_image(path)

        elif choice == '2':
            print("\nTimeframe:")
            print_menu_grid([(1, "This month"), (2, "This semester"), (3, "This year")],
                            columns=3, width=18)
            timeframe_choice = input("Select timeframe (1-3, Enter for month): ").strip() or "1"
            timeframes = {'1': 'month', '2': 'semester', '3': 'year'}
            if timeframe_choice not in timeframes:
                print("Invalid choice.")
                return
            timeframe = timeframes[timeframe_choice]

            path = chart_path(f"event_distribution_{timeframe}")
            print("\nGenerating distribution chart...")
            success, message = calendar_manager.visualizations.create_event_distribution_image(
                timeframe, str(path)
            )
            print(message)
            if success:
                open_image(path)

        elif choice == '3':
            # academic_years has no "year" column — its id is the label.
            years = fetch_rows("SELECT id, start_date, end_date FROM academic_years ORDER BY start_date DESC")
            academic_year = choose_from_db(
                years, "academic years",
                lambda r: f"{str(r[0]):<14} {r[1] or '?'} to {r[2] or '?'}"
            )
            if not academic_year:
                return

            path = chart_path("calendar_timeline")
            print("\nGenerating timeline...")
            success, message = calendar_manager.enhanced_visualizations.create_timeline_visualization(
                academic_year, str(path)
            )
            print(message)
            if success:
                open_image(path)

        elif choice == '4':
            start_date = input("Start Date (YYYY-MM-DD): ").strip()
            end_date = input("End Date (YYYY-MM-DD): ").strip()
            if not (ValidationUtils.validate_date(start_date) and ValidationUtils.validate_date(end_date)):
                print("Invalid date format.")
                return

            path = chart_path("calendar_conflicts")
            print("\nGenerating conflict chart...")
            success, message = calendar_manager.enhanced_visualizations.create_conflict_visualization(
                (start_date, end_date), str(path)
            )
            print(message)
            if success:
                open_image(path)

        elif choice != '5':
            print("Invalid choice.")

    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error: {e}")

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
    from education_system.systems.university.infrastructure.auth import UserAuth
    from education_system.systems.university.infrastructure.shared_context import get_auth

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
        try:
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
        finally:
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

        from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608
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
                        SELECT 1  -- academic_calendar_events is retired: calendar events are
                    -- rows in unified_events, tagged with the academic_calendar source
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
        logger.debug("Database fix completed successfully!")

    except Exception as e:
        print(f"Database fix failed: {e}")

# Run this once
fix_calendar_database()
