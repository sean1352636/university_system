from ..context import *  # noqa: F401,F403

def reservations_cli() -> None:
    """Reservations management submenu."""
    while True:
        print("\n--- Reservations ---")
        print("1. Create Reservation")
        print("2. View Today's Reservations")
        print("3. View Upcoming Reservations")
        print("4. View All Reservations")
        print("5. View Reservation Details")
        print("6. Update Reservation")
        print("7. Cancel Reservation")
        print("8. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            print("\n--- Create New Reservation ---")
            customer_name = input("Customer name: ").strip()
            if not customer_name:
                print("Customer name is required.")
                continue
            student_id = input("Student ID (optional, press Enter to skip): ").strip()

            res_date = input("Reservation date (YYYY-MM-DD): ").strip()
            try:
                parsed_date = datetime.strptime(res_date, "%Y-%m-%d").date()
                if parsed_date < datetime.now().date():
                    print("Date cannot be in the past.")
                    continue
            except ValueError:
                print("Invalid date format. Use YYYY-MM-DD.")
                continue

            res_time = input("Reservation time (HH:MM, 24-hour): ").strip()
            try:
                datetime.strptime(res_time, "%H:%M")
            except ValueError:
                print("Invalid time format. Use HH:MM.")
                continue

            try:
                party_size = int(input("Party size: "))
                if party_size < 1:
                    print("Party size must be at least 1.")
                    continue
            except ValueError:
                print("Invalid party size.")
                continue

            notes = input("Notes (optional): ").strip()

            reservation_id = create_reservation(customer_name, student_id, res_date, res_time, party_size, notes)
            if reservation_id:
                print(f"\n Reservation #{reservation_id} created!")
                print(f"  {customer_name} | {res_date} at {res_time} | Party of {party_size}")
            else:
                print("\n Failed to create reservation.")

        elif choice in ('2', '3', '4'):
            filter_map = {'2': 'today', '3': 'upcoming', '4': 'all'}
            label_map = {'2': "Today's", '3': 'Upcoming', '4': 'All'}
            reservations = get_all_reservations(filter_map[choice])
            if not reservations:
                print(f"\nNo {label_map[choice].lower()} reservations found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 100}")
            print(f"{'ID':<6} {'Customer':<20} {'Date':<12} {'Time':<8} {'Party':<7} {'Status':<12} {'Notes':<20}")
            print(f"{'=' * 100}")
            for res in reservations:
                rid, cname, sid, rdate, rtime, psize, status, rnotes = res
                print(f"{rid:<6} {cname[:19]:<20} {rdate:<12} {rtime:<8} {psize:<7} {status:<12} {(rnotes or '')[:19]:<20}")
            print(f"\nTotal: {len(reservations)} reservations")
            input("\nPress Enter to continue...")

        elif choice == '5':
            try:
                reservation_id = int(input("Enter Reservation ID: "))
            except ValueError:
                print("Invalid ID.")
                continue

            res = get_reservation(reservation_id)
            if not res:
                print("Reservation not found.")
                continue

            rid, cname, sid, rdate, rtime, psize, status, rnotes = res
            print(f"\n{'=' * 50}")
            print(f"RESERVATION #{rid}")
            print(f"{'=' * 50}")
            print(f"Customer:   {cname}")
            print(f"Student ID: {sid or 'N/A'}")
            print(f"Date:       {rdate}")
            print(f"Time:       {rtime}")
            print(f"Party Size: {psize}")
            print(f"Status:     {status}")
            print(f"Notes:      {rnotes or 'N/A'}")
            input("\nPress Enter to continue...")

        elif choice == '6':
            try:
                reservation_id = int(input("Enter Reservation ID to update: "))
            except ValueError:
                print("Invalid ID.")
                continue

            res = get_reservation(reservation_id)
            if not res:
                print("Reservation not found.")
                continue

            if res[6] == 'cancelled':
                print("Cannot update a cancelled reservation.")
                continue

            rid, cname, sid, rdate, rtime, psize, status, rnotes = res
            print(f"\nUpdating Reservation #{rid}")
            print("(Press Enter to keep current value)")

            new_name = input(f"Customer [{cname}]: ").strip() or cname

            new_date = input(f"Date [{rdate}] (YYYY-MM-DD): ").strip()
            if new_date:
                try:
                    datetime.strptime(new_date, "%Y-%m-%d")
                except ValueError:
                    print("Invalid date. Keeping current.")
                    new_date = rdate
            else:
                new_date = rdate

            new_time = input(f"Time [{rtime}] (HH:MM): ").strip()
            if new_time:
                try:
                    datetime.strptime(new_time, "%H:%M")
                except ValueError:
                    print("Invalid time. Keeping current.")
                    new_time = rtime
            else:
                new_time = rtime

            size_input = input(f"Party size [{psize}]: ").strip()
            try:
                new_size = int(size_input) if size_input else psize
            except ValueError:
                new_size = psize

            new_notes = input(f"Notes [{rnotes or ''}]: ").strip()
            if not new_notes:
                new_notes = rnotes or ""

            if update_reservation_details(reservation_id, new_name, new_date, new_time, new_size, new_notes):
                print(f"\n Reservation #{reservation_id} updated!")
            else:
                print("\n Failed to update reservation.")

        elif choice == '7':
            try:
                reservation_id = int(input("Enter Reservation ID to cancel: "))
            except ValueError:
                print("Invalid ID.")
                continue

            res = get_reservation(reservation_id)
            if not res:
                print("Reservation not found.")
                continue

            if res[6] == 'cancelled':
                print("Reservation is already cancelled.")
                continue

            confirm = input(f"Cancel reservation #{reservation_id} for '{res[1]}'? (y/n): ").strip().lower()
            if confirm == 'y':
                if cancel_reservation(reservation_id):
                    print(f"\n Reservation #{reservation_id} cancelled.")
                else:
                    print("\n Failed to cancel reservation.")

        elif choice == '8':
            break

