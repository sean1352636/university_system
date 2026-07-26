"""Office Hours CLI menu.

Provides a command-line interface for managing instructor office hours
and student booking operations. Menu options are dynamically rendered
based on the authenticated user's role.
"""

import logging

from education_system.systems.university.domain.academics.services.office_hours.office_hours_service import (
    OfficeHoursService,
)

logger = logging.getLogger(__name__)


def display_office_hours_menu(auth):
    """Display the office hours management CLI menu."""
    if not auth or not auth.current_user:
        print("\n--- Please log in to access office hours.")
        input("Press Enter to continue...")
        return

    service = OfficeHoursService()
    role = auth.current_user.get('role', '')
    user_id = auth.current_user.get('username', '')
    is_instructor = role in ('admin', 'instructor', 'staff')

    while True:
        print("\n" + "=" * 60)
        print("      OFFICE HOURS MANAGEMENT")
        print("=" * 60)

        option_num = 1
        options = {}

        # View available office hours (all roles)
        print(f"{option_num}. View Available Office Hours")
        options[str(option_num)] = 'view_available'
        option_num += 1

        if is_instructor:
            print(f"{option_num}. Create Office Hours")
            options[str(option_num)] = 'create'
            option_num += 1

            print(f"{option_num}. Edit Office Hours")
            options[str(option_num)] = 'edit'
            option_num += 1

            print(f"{option_num}. Delete Office Hours")
            options[str(option_num)] = 'delete'
            option_num += 1

            print(f"{option_num}. View Bookings for My Hours")
            options[str(option_num)] = 'view_instructor_bookings'
            option_num += 1

        if role in ('student', 'admin'):
            print(f"{option_num}. Book an Appointment")
            options[str(option_num)] = 'book'
            option_num += 1

            print(f"{option_num}. Cancel a Booking")
            options[str(option_num)] = 'cancel'
            option_num += 1

            print(f"{option_num}. View My Bookings")
            options[str(option_num)] = 'view_student_bookings'
            option_num += 1

        print(f"{option_num}. Return to Main Menu")
        options[str(option_num)] = 'return'

        print("=" * 60)
        choice = input("\nEnter your choice: ").strip()

        if choice not in options:
            print("Invalid choice. Please try again.")
            continue

        action = options[choice]

        if action == 'return':
            break
        elif action == 'view_available':
            _view_available_hours(service)
        elif action == 'create':
            _create_office_hours(service, user_id)
        elif action == 'edit':
            _edit_office_hours(service, user_id)
        elif action == 'delete':
            _delete_office_hours(service, user_id)
        elif action == 'view_instructor_bookings':
            _view_instructor_bookings(service, user_id)
        elif action == 'book':
            _book_appointment(service, user_id)
        elif action == 'cancel':
            _cancel_booking(service, user_id)
        elif action == 'view_student_bookings':
            _view_student_bookings(service, user_id)


# ------------------------------------------------------------------ #
#  Helper functions
# ------------------------------------------------------------------ #


def _view_available_hours(service):
    """View available office hours, optionally filtered by instructor."""
    print("\n--- Available Office Hours ---")
    instructor_filter = input(
        "Filter by instructor ID (leave blank for all): "
    ).strip() or None

    try:
        hours = service.get_available_office_hours(instructor_id=instructor_filter)
        if not hours:
            print("\nNo office hours found.")
            input("Press Enter to continue...")
            return

        print(
            f"\n{'ID':<6}{'Instructor':<16}{'Day':<12}{'Start':<10}"
            f"{'End':<10}{'Location':<20}{'Capacity':<10}"
        )
        print("-" * 84)
        for h in hours:
            print(
                f"{h['id']:<6}{h['instructor_id']:<16}{h['day_of_week']:<12}"
                f"{h['start_time']:<10}{h['end_time']:<10}"
                f"{h['location']:<20}{h['capacity']:<10}"
            )
    except Exception as e:
        logger.error("Error viewing office hours: %s", e)
        print(f"\nError retrieving office hours: {e}")

    input("\nPress Enter to continue...")


def _create_office_hours(service, instructor_id):
    """Create a new office hours slot."""
    print("\n--- Create Office Hours ---")

    valid_days = [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
        'Saturday', 'Sunday',
    ]
    print("Days of week: " + ", ".join(valid_days))
    day = input("Day of week: ").strip()
    if day not in valid_days:
        print(f"Invalid day. Must be one of: {', '.join(valid_days)}")
        input("Press Enter to continue...")
        return

    start_time = input("Start time (HH:MM): ").strip()
    end_time = input("End time (HH:MM): ").strip()
    location = input("Location: ").strip()

    capacity_str = input("Capacity (default 5): ").strip()
    try:
        capacity = int(capacity_str) if capacity_str else 5
    except ValueError:
        print("Invalid capacity. Using default of 5.")
        capacity = 5

    notes = input("Notes (optional): ").strip()

    try:
        oh_id = service.create_office_hours(
            instructor_id=instructor_id,
            day_of_week=day,
            start_time=start_time,
            end_time=end_time,
            location=location,
            capacity=capacity,
            notes=notes,
        )
        print(f"\nOffice hours created successfully (ID: {oh_id}).")
    except ValueError as e:
        print(f"\nValidation error: {e}")
    except Exception as e:
        logger.error("Error creating office hours: %s", e)
        print(f"\nError creating office hours: {e}")

    input("Press Enter to continue...")


def _edit_office_hours(service, instructor_id):
    """Edit an existing office hours slot."""
    print("\n--- Edit Office Hours ---")

    # Show current hours for reference
    try:
        hours = service.get_available_office_hours(instructor_id=instructor_id)
        if not hours:
            print("You have no active office hours to edit.")
            input("Press Enter to continue...")
            return

        print(f"\n{'ID':<6}{'Day':<12}{'Start':<10}{'End':<10}{'Location':<20}{'Capacity':<10}")
        print("-" * 68)
        for h in hours:
            print(
                f"{h['id']:<6}{h['day_of_week']:<12}{h['start_time']:<10}"
                f"{h['end_time']:<10}{h['location']:<20}{h['capacity']:<10}"
            )
    except Exception as e:
        logger.error("Error listing office hours: %s", e)
        print(f"\nError listing office hours: {e}")
        input("Press Enter to continue...")
        return

    oh_id_str = input("\nEnter the ID of the office hours to edit: ").strip()
    try:
        oh_id = int(oh_id_str)
    except ValueError:
        print("Invalid ID.")
        input("Press Enter to continue...")
        return

    print("\nLeave fields blank to keep current values.")

    valid_days = [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday',
        'Saturday', 'Sunday',
    ]

    updates = {}

    day = input("New day of week: ").strip()
    if day:
        if day not in valid_days:
            print(f"Invalid day. Must be one of: {', '.join(valid_days)}")
            input("Press Enter to continue...")
            return
        updates['day_of_week'] = day

    start_time = input("New start time (HH:MM): ").strip()
    if start_time:
        updates['start_time'] = start_time

    end_time = input("New end time (HH:MM): ").strip()
    if end_time:
        updates['end_time'] = end_time

    location = input("New location: ").strip()
    if location:
        updates['location'] = location

    capacity_str = input("New capacity: ").strip()
    if capacity_str:
        try:
            updates['capacity'] = int(capacity_str)
        except ValueError:
            print("Invalid capacity value. Skipping.")

    notes = input("New notes: ").strip()
    if notes:
        updates['notes'] = notes

    if not updates:
        print("No changes specified.")
        input("Press Enter to continue...")
        return

    try:
        success = service.update_office_hours(oh_id, **updates)
        if success:
            print("\nOffice hours updated successfully.")
        else:
            print("\nOffice hours not found or could not be updated.")
    except ValueError as e:
        print(f"\nValidation error: {e}")
    except Exception as e:
        logger.error("Error updating office hours: %s", e)
        print(f"\nError updating office hours: {e}")

    input("Press Enter to continue...")


def _delete_office_hours(service, instructor_id):
    """Delete (deactivate) an office hours slot."""
    print("\n--- Delete Office Hours ---")

    # Show current hours for reference
    try:
        hours = service.get_available_office_hours(instructor_id=instructor_id)
        if not hours:
            print("You have no active office hours to delete.")
            input("Press Enter to continue...")
            return

        print(f"\n{'ID':<6}{'Day':<12}{'Start':<10}{'End':<10}{'Location':<20}")
        print("-" * 58)
        for h in hours:
            print(
                f"{h['id']:<6}{h['day_of_week']:<12}{h['start_time']:<10}"
                f"{h['end_time']:<10}{h['location']:<20}"
            )
    except Exception as e:
        logger.error("Error listing office hours: %s", e)
        print(f"\nError listing office hours: {e}")
        input("Press Enter to continue...")
        return

    oh_id_str = input("\nEnter the ID of the office hours to delete: ").strip()
    try:
        oh_id = int(oh_id_str)
    except ValueError:
        print("Invalid ID.")
        input("Press Enter to continue...")
        return

    confirm = input(f"Are you sure you want to delete office hours {oh_id}? (yes/no): ").strip()
    if confirm.lower() != 'yes':
        print("Deletion cancelled.")
        input("Press Enter to continue...")
        return

    try:
        success = service.delete_office_hours(oh_id)
        if success:
            print("\nOffice hours deleted successfully.")
        else:
            print("\nOffice hours not found or already inactive.")
    except Exception as e:
        logger.error("Error deleting office hours: %s", e)
        print(f"\nError deleting office hours: {e}")

    input("Press Enter to continue...")


def _view_instructor_bookings(service, instructor_id):
    """View all bookings for the instructor's office hours."""
    print("\n--- Bookings for My Office Hours ---")

    try:
        bookings = service.get_instructor_bookings(instructor_id)
        if not bookings:
            print("No bookings found for your office hours.")
            input("Press Enter to continue...")
            return

        print(
            f"\n{'ID':<6}{'Student':<16}{'Date':<14}{'Day':<12}"
            f"{'Time':<14}{'Status':<12}{'Notes':<20}"
        )
        print("-" * 94)
        for b in bookings:
            time_str = f"{b['start_time']}-{b['end_time']}"
            print(
                f"{b['id']:<6}{b['student_id']:<16}{b['booking_date']:<14}"
                f"{b['day_of_week']:<12}{time_str:<14}"
                f"{b['status']:<12}{(b.get('notes', '') or '')[:20]:<20}"
            )
    except Exception as e:
        logger.error("Error viewing instructor bookings: %s", e)
        print(f"\nError retrieving bookings: {e}")

    input("\nPress Enter to continue...")


def _book_appointment(service, student_id):
    """Book an appointment with an instructor's office hours."""
    print("\n--- Book an Appointment ---")

    # Show available hours
    try:
        hours = service.get_available_office_hours()
        if not hours:
            print("No office hours are currently available.")
            input("Press Enter to continue...")
            return

        print(
            f"\n{'ID':<6}{'Instructor':<16}{'Day':<12}{'Start':<10}"
            f"{'End':<10}{'Location':<20}{'Capacity':<10}"
        )
        print("-" * 84)
        for h in hours:
            print(
                f"{h['id']:<6}{h['instructor_id']:<16}{h['day_of_week']:<12}"
                f"{h['start_time']:<10}{h['end_time']:<10}"
                f"{h['location']:<20}{h['capacity']:<10}"
            )
    except Exception as e:
        logger.error("Error listing available hours: %s", e)
        print(f"\nError retrieving office hours: {e}")
        input("Press Enter to continue...")
        return

    oh_id_str = input("\nEnter the office hours ID to book: ").strip()
    try:
        oh_id = int(oh_id_str)
    except ValueError:
        print("Invalid ID.")
        input("Press Enter to continue...")
        return

    booking_date = input("Enter booking date (YYYY-MM-DD): ").strip()
    if not booking_date:
        print("Booking date is required.")
        input("Press Enter to continue...")
        return

    notes = input("Notes (optional): ").strip()

    try:
        booking_id = service.book_office_hour(
            office_hour_id=oh_id,
            student_id=student_id,
            booking_date=booking_date,
            notes=notes,
        )
        print(f"\nAppointment booked successfully (Booking ID: {booking_id}).")
    except ValueError as e:
        print(f"\nBooking error: {e}")
    except Exception as e:
        logger.error("Error booking appointment: %s", e)
        print(f"\nError booking appointment: {e}")

    input("Press Enter to continue...")


def _cancel_booking(service, student_id):
    """Cancel an existing booking."""
    print("\n--- Cancel a Booking ---")

    # Show student's current bookings
    try:
        bookings = service.get_student_bookings(student_id)
        confirmed = [b for b in bookings if b['status'] == 'confirmed']

        if not confirmed:
            print("You have no confirmed bookings to cancel.")
            input("Press Enter to continue...")
            return

        print(
            f"\n{'ID':<6}{'Instructor':<16}{'Day':<12}"
            f"{'Time':<14}{'Date':<14}{'Location':<20}"
        )
        print("-" * 82)
        for b in confirmed:
            time_str = f"{b['start_time']}-{b['end_time']}"
            print(
                f"{b['id']:<6}{b['instructor_id']:<16}{b['day_of_week']:<12}"
                f"{time_str:<14}{b['booking_date']:<14}{b['location']:<20}"
            )
    except Exception as e:
        logger.error("Error listing bookings: %s", e)
        print(f"\nError retrieving bookings: {e}")
        input("Press Enter to continue...")
        return

    booking_id_str = input("\nEnter the booking ID to cancel: ").strip()
    try:
        booking_id = int(booking_id_str)
    except ValueError:
        print("Invalid ID.")
        input("Press Enter to continue...")
        return

    confirm = input(f"Are you sure you want to cancel booking {booking_id}? (yes/no): ").strip()
    if confirm.lower() != 'yes':
        print("Cancellation aborted.")
        input("Press Enter to continue...")
        return

    try:
        success = service.cancel_booking(booking_id, student_id)
        if success:
            print("\nBooking cancelled successfully.")
        else:
            print("\nBooking not found or could not be cancelled.")
    except Exception as e:
        logger.error("Error cancelling booking: %s", e)
        print(f"\nError cancelling booking: {e}")

    input("Press Enter to continue...")


def _view_student_bookings(service, student_id):
    """View all bookings for the current student."""
    print("\n--- My Bookings ---")

    try:
        bookings = service.get_student_bookings(student_id)
        if not bookings:
            print("You have no bookings.")
            input("Press Enter to continue...")
            return

        print(
            f"\n{'ID':<6}{'Instructor':<16}{'Day':<12}"
            f"{'Time':<14}{'Date':<14}{'Status':<12}{'Location':<20}"
        )
        print("-" * 94)
        for b in bookings:
            time_str = f"{b['start_time']}-{b['end_time']}"
            print(
                f"{b['id']:<6}{b['instructor_id']:<16}{b['day_of_week']:<12}"
                f"{time_str:<14}{b['booking_date']:<14}"
                f"{b['status']:<12}{b['location']:<20}"
            )
    except Exception as e:
        logger.error("Error viewing student bookings: %s", e)
        print(f"\nError retrieving bookings: {e}")

    input("\nPress Enter to continue...")
