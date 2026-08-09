"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_holiday_management_menu(scheduler):
    """Display holiday management menu"""
    while True:
        print("\n📅 Holiday Management:")
        print("1. Add Holiday/Special Event")
        print("2. List All Holidays")
        print("3. Check Date for Conflicts")
        print("4. Remove Holiday")
        print("5. Academic Calendar View")
        print("6. Return to Main Menu")

        choice = input("Enter your choice (1-6): ")

        if choice == '1':
            name = input("Holiday name: ").strip()
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD, leave blank if same as start): ").strip()
            description = input("Description: ").strip()
            recurring = input("Recurring annually? (y/n): ").lower() == 'y'

            if name and start_date:
                scheduler.add_holiday(name, start_date, end_date or start_date, description, recurring)

        elif choice == '2':
            scheduler.list_holidays()

        elif choice == '3':
            date = input("Enter date to check (YYYY-MM-DD): ").strip()
            if date:
                conflicts = scheduler.check_holiday_conflicts(date)
                if conflicts:
                    print(f"\nHolidays on {date}:")
                    for holiday in conflicts:
                        print(f"- {holiday[0]}: {holiday[1]}")
                else:
                    print(f"No holidays found on {date}")

        elif choice == '4':
            scheduler.list_holidays()
            holiday_name = input("\nEnter holiday name to remove: ").strip()
            if holiday_name:
                confirm = input(f"Remove holiday '{holiday_name}'? (y/n): ")
                if confirm.lower() == 'y':
                    conn = get_connection(scheduler.db_path, row_factory=False)
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM holidays WHERE holiday_name = ?', (holiday_name,))
                    if cursor.rowcount > 0:
                        conn.commit()
                        print(f"Holiday '{holiday_name}' removed.")
                    else:
                        print("Holiday not found.")
                    conn.close()

        elif choice == '5':
            # Display academic calendar view
            conn = get_connection(scheduler.db_path, row_factory=False)
            cursor = conn.cursor()

            # Get current month's holidays
            current_month = datetime.now().strftime("%Y-%m")
            cursor.execute('''
            SELECT holiday_name, start_date, end_date, description
            FROM holidays
            WHERE start_date LIKE ?
            ORDER BY start_date
            ''', (f"{current_month}%",))

            holidays = cursor.fetchall()
            conn.close()

            print(f"\nAcademic Calendar - {datetime.now().strftime('%B %Y')}:")
            print("=" * 60)

            if holidays:
                for holiday in holidays:
                    name, start, end, desc = holiday
                    if start == end:
                        print(f"{start}: {name}")
                    else:
                        print(f"{start} to {end}: {name}")
                    if desc:
                        print(f"  {desc}")
                    print()
            else:
                print("No holidays scheduled for this month.")

            print("=" * 60)

        elif choice == '6':
            break

        else:
            print("Invalid choice. Please try again.")
