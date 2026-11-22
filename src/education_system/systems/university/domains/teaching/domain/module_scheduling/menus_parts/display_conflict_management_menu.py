"""Extracted function implementation."""

from .. import menus_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def display_conflict_management_menu(scheduler):
    """Display conflict management menu"""
    while True:
        print("\n⚠️  Conflict Management Menu:")
        print("1. Detect All Conflicts")
        print("2. View Active Conflicts")
        print("3. View Resolved Conflicts")
        print("4. Resolve Conflict")
        print("5. Return to Main Menu")

        choice = input("Enter your choice (1-5): ")

        if choice == '1':
            print("Detecting conflicts...")
            conflicts = scheduler.detect_all_conflicts()
            print(f"Detection complete. Found {len(conflicts)} conflicts.")

        elif choice == '2':
            conflicts = scheduler._get_all_conflicts()
            active_conflicts = [c for c in conflicts if not c['resolved']]

            if active_conflicts:
                print(f"\nActive Conflicts ({len(active_conflicts)}):")
                print("=" * 100)
                print(f"{'ID':<5} {'Type':<20} {'Description':<70}")
                print("-" * 100)

                for conflict in active_conflicts:
                    print(f"{conflict['id']:<5} {conflict['type']:<20} {conflict['description'][:68]:<70}")

                print("=" * 100)
            else:
                print("No active conflicts found.")

        elif choice == '3':
            conflicts = scheduler._get_all_conflicts()
            resolved_conflicts = [c for c in conflicts if c['resolved']]

            if resolved_conflicts:
                print(f"\nResolved Conflicts ({len(resolved_conflicts)}):")
                print("=" * 100)

                for conflict in resolved_conflicts:
                    print(f"ID {conflict['id']}: {conflict['description']}")
                    if conflict['resolution_notes']:
                        print(f"  Resolution: {conflict['resolution_notes']}")
                    print()
            else:
                print("No resolved conflicts found.")

        elif choice == '4':
            conflicts = scheduler._get_all_conflicts()
            active_conflicts = [c for c in conflicts if not c['resolved']]

            if not active_conflicts:
                print("No active conflicts to resolve.")
                continue

            print("\nActive Conflicts:")
            for conflict in active_conflicts:
                print(f"ID {conflict['id']}: {conflict['description']}")

            try:
                conflict_id = int(input("\nEnter conflict ID to resolve: "))
                resolution_notes = input("Enter resolution notes: ")
                scheduler.resolve_conflict(conflict_id, resolution_notes)
            except ValueError:
                print("Invalid conflict ID.")

        elif choice == '5':
            break

        else:
            print("Invalid choice. Please try again.")
