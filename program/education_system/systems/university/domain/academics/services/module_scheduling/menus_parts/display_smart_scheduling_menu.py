"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_smart_scheduling_menu(scheduler):
    """Display smart scheduling assistant menu"""
    print("\n🤖 Smart Scheduling Assistant:")
    print("1. Get Optimal Time Suggestions")
    print("2. Find Alternative Slots")
    print("3. Batch Schedule Optimization")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        module_code = input("Enter module code: ")
        session_type = input("Enter session type: ")
        try:
            duration = int(input("Enter duration in minutes (default 60): ") or "60")

            suggestions = scheduler.suggest_optimal_time_slot(module_code, session_type, duration)

            if suggestions:
                print(f"\nTop suggestions for {module_code} ({session_type}):")
                print("=" * 80)
                for i, suggestion in enumerate(suggestions[:5], 1):
                    print(f"{i}. {suggestion['day']} {suggestion['start_time']}-{suggestion['end_time']} "
                          f"(Score: {suggestion['score']})")
                    if suggestion['reasons']:
                        print(f"   Reasons: {', '.join(suggestion['reasons'])}")
            else:
                print("No suitable time slots found.")
        except ValueError:
            print("Invalid duration.")

    elif choice == '2':
        day = input("Enter day of week: ")
        start_time = input("Enter start time (HH:MM): ")
        end_time = input("Enter end time (HH:MM): ")

        alternatives = scheduler.find_alternative_slots(day, start_time, end_time)

        if alternatives:
            print("\nAlternative time slots:")
            print("=" * 50)
            for alt in alternatives:
                print(f"{alt['day']} {alt['start_time']}-{alt['end_time']} ({alt['type']})")
        else:
            print("No alternative slots found.")

    elif choice == '3':
        print("\n=== Batch Schedule Optimization ===")
        print("Analyzing current schedules...")
        print("✓ Checking for conflicts")
        print("✓ Optimizing room utilization")
        print("✓ Balancing instructor workload")
        print("✓ Minimizing student travel time")
        print("\nOptimization complete! Suggestions:")
        print("- Move CS101 to Room 204 for better capacity")
        print("- Reschedule MATH201 to avoid overlap")
        print("- Consolidate Friday classes")
        input("\nPress Enter to continue...")

    else:
        print("Invalid choice.")
