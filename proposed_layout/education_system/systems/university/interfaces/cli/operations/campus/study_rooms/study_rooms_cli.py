"""CLI for the study-room booking system."""

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.operations.campus.study_rooms.services import study_room_service


def main():
    """Run the study rooms CLI menu loop."""
    study_room_service.init_db()

    while True:
        print("\n===== Study Room Booking System =====")
        print("1. View Available Rooms")
        print("2. Book a Room")
        print("3. View My Bookings")
        print("4. Cancel Booking")
        print("0. Back / Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            view_available_rooms()
        elif choice == "2":
            book_room()
        elif choice == "3":
            view_bookings()
        elif choice == "4":
            cancel_booking()
        elif choice == "0":
            print("Returning to main menu.")
            break
        else:
            print("Invalid option. Please try again.")


def view_available_rooms():
    """Display available study rooms with optional filters."""
    try:
        building = input("Filter by building (leave blank for all): ").strip() or None
        room_type = input("Filter by type (study/group_study/lab_study, leave blank for all): ").strip() or None

        rooms = study_room_service.get_available_rooms(building=building, room_type=room_type)
        if not rooms:
            print("No available rooms found.")
            return
        print(
            f"\n{'ID':<6} {'Room':<10} {'Building':<20} {'Capacity':<10} "
            f"{'Type':<15} {'Whiteboard':<12} {'Projector':<10}"
        )
        print("-" * 83)
        for r in rooms:
            wb = "Yes" if r["has_whiteboard"] else "No"
            proj = "Yes" if r["has_projector"] else "No"
            print(
                f"{r['room_id']:<6} {r['room_number']:<10} {r['building']:<20} "
                f"{r['capacity']:<10} {r['room_type']:<15} {wb:<12} {proj:<10}"
            )
    except Exception as e:
        print(f"Error: {e}")


def book_room():
    """Book a study room."""
    try:
        # Show available rooms first
        rooms = study_room_service.get_room_list()
        if not rooms:
            print("No rooms available to book.")
            return
        print("\nAvailable rooms:")
        for r in rooms:
            print(f"  ID {r['room_id']}: {r['room_number']} ({r['building']}, capacity {r['capacity']})")

        room_id = input("\nRoom ID: ").strip()
        user_id = input("Your user/student ID: ").strip()
        booking_date = input("Date (YYYY-MM-DD): ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        end_time = input("End time (HH:MM): ").strip()
        purpose = input("Purpose (study/group_study/meeting) [study]: ").strip() or "study"
        group_size = input("Group size [1]: ").strip() or "1"
        notes = input("Notes: ").strip()

        study_room_service.book_room(
            room_id=int(room_id),
            user_id=user_id,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            purpose=purpose,
            group_size=int(group_size),
            notes=notes,
        )
        print("Room booked successfully.")
    except Exception as e:
        print(f"Error: {e}")


def view_bookings():
    """View bookings for a user."""
    try:
        user_id = input("Your user/student ID: ").strip()
        bookings = study_room_service.get_bookings(user_id)
        if not bookings:
            print("No bookings found.")
            return
        print(
            f"\n{'ID':<6} {'Room':<10} {'Date':<12} {'Start':<8} "
            f"{'End':<8} {'Purpose':<15} {'Status':<12}"
        )
        print("-" * 71)
        for b in bookings:
            print(
                f"{b['booking_id']:<6} {b['room_number']:<10} {b['booking_date']:<12} "
                f"{b['start_time']:<8} {b['end_time']:<8} {b['purpose']:<15} {b['status']:<12}"
            )
    except Exception as e:
        print(f"Error: {e}")


def cancel_booking():
    """Cancel an existing booking."""
    try:
        booking_id = input("Booking ID to cancel: ").strip()
        if study_room_service.cancel_booking(int(booking_id)):
            print("Booking cancelled successfully.")
        else:
            print("Booking not found or already cancelled.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
