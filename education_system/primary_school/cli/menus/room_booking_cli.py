"""Room Booking CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def room_booking_menu(auth):
    """Room Booking management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.facilities.room_booking.services.room_booking_service import RoomBookingService

    svc = RoomBookingService(get_db_path())

    while True:
        print_header("Room Booking")
        print_menu([
            ("1", "List bookings"),
            ("2", "View details"),
            ("3", "Add Booking"),
            ("4", "Update Booking"),
            ("5", "Delete Booking"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_bookings()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_booking(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            room_name = input("  Room Name: ").strip()
            date = input("  Date: ").strip()
            start_time = input("  Start Time: ").strip()
            end_time = input("  End Time: ").strip()
            booked_by = input("  Booked By: ").strip()
            try:
                svc.create_booking(room_name=room_name, date=date, start_time=start_time, end_time=end_time, booked_by=booked_by)
                print("\n  Booking created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            room_name = input("  Room Name: ").strip()
            date = input("  Date: ").strip()
            start_time = input("  Start Time: ").strip()
            end_time = input("  End Time: ").strip()
            booked_by = input("  Booked By: ").strip()
            try:
                svc.update_booking(int(pk), room_name=room_name, date=date, start_time=start_time, end_time=end_time, booked_by=booked_by)
                print("\n  Booking updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_booking(int(pk))
                print("\n  Booking deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
