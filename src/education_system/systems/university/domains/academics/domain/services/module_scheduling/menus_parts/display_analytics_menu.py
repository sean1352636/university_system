"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_analytics_menu(scheduler):
    """Display analytics submenu"""
    while True:
        print("\n📊 Analytics & Reporting Menu:")
        print("1. Room Utilization Report (Display)")
        print("2. Room Utilization Report (PDF)")
        print("3. Room Utilization Report (CSV)")
        print("4. Instructor Workload Report (Display)")
        print("5. Instructor Workload Report (PDF)")
        print("6. Instructor Workload Report (CSV)")
        print("7. Peak Usage Analysis")
        print("8. Module Distribution Statistics")
        print("9. Return to Main Menu")

        choice = input("Enter your choice (1-9): ")

        if choice == '1':
            scheduler.generate_room_utilization_report('display')
        elif choice == '2':
            scheduler.generate_room_utilization_report('pdf')
        elif choice == '3':
            scheduler.generate_room_utilization_report('csv')
        elif choice == '4':
            scheduler.generate_instructor_workload_report('display')
        elif choice == '5':
            scheduler.generate_instructor_workload_report('pdf')
        elif choice == '6':
            scheduler.generate_instructor_workload_report('csv')
        elif choice == '7':
            peak_times = scheduler._analyze_peak_usage()
            print("\nPeak Usage Times by Day:")
            for day, times in peak_times.items():
                print(f"{day}: {', '.join(times) if times else 'No data'}")
        elif choice == '8':
            stats = scheduler._analyze_module_distribution()
            print("\nModule Distribution Statistics:")
            print(f"Total Modules: {stats['total']}")
            print(f"Most Common Session Type: {stats['most_common_type']}")
            print(f"Average Sessions per Module: {stats['avg_sessions']:.2f}")
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")
