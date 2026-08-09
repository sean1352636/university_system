from ..context import *  # noqa: F401,F403

def staff_scheduling_cli() -> None:
    """Staff scheduling submenu."""
    DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    POSITIONS = ["Barista", "Server", "Kitchen", "Supervisor", "Manager"]
    TEMPLATE_SCHEDULES = [
        ("Monday-Friday: 9AM-5PM", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "09:00", "17:00"),
        ("Monday-Friday: 8AM-4PM", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "08:00", "16:00"),
        ("Monday-Friday: 12PM-8PM", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], "12:00", "20:00"),
        ("Weekends Only: 10AM-6PM", ["Saturday", "Sunday"], "10:00", "18:00"),
        ("Monday/Wednesday/Friday: 9AM-5PM", ["Monday", "Wednesday", "Friday"], "09:00", "17:00"),
    ]

    while True:
        print("\n--- Staff Scheduling ---")
        print("1. View All Schedules")
        print("2. View Staff Member Schedule")
        print("3. Add Shift")
        print("4. Add Shift from Template")
        print("5. Update Shift")
        print("6. Delete Shift")
        print("7. Back")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            schedules = get_all_staff_schedules()
            if not schedules:
                print("\nNo schedules found.")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{'=' * 90}")
            print(f"{'ID':<5} {'Staff':<20} {'Position':<12} {'Day':<12} {'Start':<8} {'End':<8} {'Notes':<20}")
            print(f"{'=' * 90}")
            current_day = None
            for sched in schedules:
                sid, sname, pos, day, start, end, notes = sched
                if day != current_day:
                    current_day = day
                    print(f"\n--- {day} ---")
                print(f"{sid:<5} {sname[:19]:<20} {pos:<12} {day:<12} {start:<8} {end:<8} {(notes or '')[:19]:<20}")
            print(f"\nTotal: {len(schedules)} shifts")
            input("\nPress Enter to continue...")

        elif choice == '2':
            staff_name = input("Enter staff name (or part of name): ").strip()
            if not staff_name:
                print("Name is required.")
                continue

            schedules = get_staff_schedule_by_name(staff_name)
            if not schedules:
                print(f"No schedules found for '{staff_name}'.")
                input("\nPress Enter to continue...")
                continue

            staff_display = schedules[0][1]
            print(f"\n{'=' * 60}")
            print(f"SCHEDULE FOR: {staff_display}")
            print(f"{'=' * 60}")
            print(f"{'ID':<5} {'Day':<12} {'Start':<8} {'End':<8} {'Notes':<20}")
            print("-" * 55)
            for sched in schedules:
                sid, sname, pos, day, start, end, notes = sched
                print(f"{sid:<5} {day:<12} {start:<8} {end:<8} {(notes or '')[:19]:<20}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            print("\n--- Add New Shift ---")
            staff_name = input("Staff name: ").strip()
            if not staff_name:
                print("Staff name is required.")
                continue

            print("\nPositions: " + ", ".join(f"{i+1}. {p}" for i, p in enumerate(POSITIONS)))
            try:
                pos_choice = int(input("Select position: "))
                position = POSITIONS[pos_choice - 1] if 1 <= pos_choice <= len(POSITIONS) else "Barista"
            except (ValueError, IndexError):
                position = "Barista"

            print("\nDays: " + ", ".join(f"{i+1}. {d}" for i, d in enumerate(DAYS_OF_WEEK)))
            try:
                day_choice = int(input("Select day: "))
                day = DAYS_OF_WEEK[day_choice - 1] if 1 <= day_choice <= len(DAYS_OF_WEEK) else None
            except (ValueError, IndexError):
                day = None

            if not day:
                print("Invalid day selection.")
                continue

            start_time = input("Start time (HH:MM, 24-hour): ").strip()
            try:
                datetime.strptime(start_time, "%H:%M")
            except ValueError:
                print("Invalid time format.")
                continue

            end_time = input("End time (HH:MM, 24-hour): ").strip()
            try:
                datetime.strptime(end_time, "%H:%M")
            except ValueError:
                print("Invalid time format.")
                continue

            notes = input("Notes (optional): ").strip()

            if add_staff_schedule(staff_name, position, day, start_time, end_time, notes):
                print(f"\n Shift added: {staff_name} - {day} {start_time}-{end_time}")
            else:
                print("\n Failed to add shift.")

        elif choice == '4':
            print("\n--- Add Shift from Template ---")
            staff_name = input("Staff name: ").strip()
            if not staff_name:
                print("Staff name is required.")
                continue

            print("\nPositions: " + ", ".join(f"{i+1}. {p}" for i, p in enumerate(POSITIONS)))
            try:
                pos_choice = int(input("Select position: "))
                position = POSITIONS[pos_choice - 1] if 1 <= pos_choice <= len(POSITIONS) else "Barista"
            except (ValueError, IndexError):
                position = "Barista"

            print("\nTemplate Schedules:")
            for i, (desc, days, start, end) in enumerate(TEMPLATE_SCHEDULES, 1):
                print(f"  {i}. {desc}")

            try:
                tmpl_choice = int(input("Select template: "))
                if 1 <= tmpl_choice <= len(TEMPLATE_SCHEDULES):
                    desc, days, start, end = TEMPLATE_SCHEDULES[tmpl_choice - 1]
                    added = 0
                    for day in days:
                        if add_staff_schedule(staff_name, position, day, start, end):
                            added += 1
                    print(f"\n {added} shifts added for {staff_name} using template '{desc}'")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")

        elif choice == '5':
            try:
                schedule_id = int(input("Enter Shift ID to update: "))
            except ValueError:
                print("Invalid ID.")
                continue

            # Look up current details
            schedules = get_all_staff_schedules()
            current = None
            for s in schedules:
                if s[0] == schedule_id:
                    current = s
                    break

            if not current:
                print("Shift not found.")
                continue

            sid, sname, pos, day, start, end, notes = current
            print(f"\nUpdating shift for {sname}: {day} {start}-{end}")
            print("(Press Enter to keep current value)")

            print("\nDays: " + ", ".join(f"{i+1}. {d}" for i, d in enumerate(DAYS_OF_WEEK)))
            day_input = input(f"Day [{day}]: ").strip()
            try:
                new_day = DAYS_OF_WEEK[int(day_input) - 1] if day_input else day
            except (ValueError, IndexError):
                new_day = day

            new_start = input(f"Start time [{start}] (HH:MM): ").strip() or start
            new_end = input(f"End time [{end}] (HH:MM): ").strip() or end
            new_notes = input(f"Notes [{notes or ''}]: ").strip()
            if not new_notes:
                new_notes = notes or ""

            if update_staff_schedule_entry(schedule_id, new_day, new_start, new_end, new_notes):
                print(f"\n Shift #{schedule_id} updated!")
            else:
                print("\n Failed to update shift.")

        elif choice == '6':
            try:
                schedule_id = int(input("Enter Shift ID to delete: "))
            except ValueError:
                print("Invalid ID.")
                continue

            confirm = input(f"Delete shift #{schedule_id}? (y/n): ").strip().lower()
            if confirm == 'y':
                if delete_staff_schedule_entry(schedule_id):
                    print(f"\n Shift #{schedule_id} deleted!")
                else:
                    print("\n Failed to delete shift.")

        elif choice == '7':
            break

