"""Reverse Lookup CLI module.

Provides a text-based menu for tracking where transferred students ended up
in destination education systems.
"""

from education_system.shared.reverse_lookup.reverse_lookup_service import (
    ReverseLookupService,
    SYSTEM_LABELS,
)

SOURCE_SYSTEMS = ["primary", "secondary", "college"]


def _choose_source():
    """Prompt the user to select a source system."""
    print("\nSource systems:")
    for i, key in enumerate(SOURCE_SYSTEMS, 1):
        print(f"  {i}) {SYSTEM_LABELS[key]}")
    try:
        choice = int(input("Select source (number): ").strip())
        if 1 <= choice <= len(SOURCE_SYSTEMS):
            return SOURCE_SYSTEMS[choice - 1]
    except (ValueError, EOFError):
        pass
    print("Invalid selection.")
    return None


def run(db_path=None, auth=None):
    """Entry point for the Reverse Lookup CLI menu."""
    service = ReverseLookupService()
    current_source = None
    transferred = []

    while True:
        print("\n=== Reverse Lookup - Transfer Tracking ===")
        print("1) View all transferred students")
        print("2) Look up specific student")
        print("3) Destination summary")
        print("0) Back")

        try:
            choice = input("\nChoice: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "0":
            break

        elif choice == "1":
            current_source = _choose_source()
            if not current_source:
                continue

            print(f"\nTransferred students from {SYSTEM_LABELS.get(current_source, current_source)}:")
            print("-" * 65)

            try:
                transferred = service.find_transferred_students(current_source)
            except Exception as exc:
                print(f"Error: {exc}")
                transferred = []
                continue

            if not transferred:
                print("No transferred students found.")
                continue

            print(f"{'#':<4} {'ID':<15} {'Name':<30} {'Year':<10} {'Status':<10}")
            print("-" * 65)
            for i, stu in enumerate(transferred, 1):
                print(
                    f"{i:<4} {stu.get('student_id', ''):<15} "
                    f"{stu.get('name', ''):<30} "
                    f"{stu.get('year_group', ''):<10} "
                    f"{stu.get('status', ''):<10}"
                )
            print(f"\nTotal: {len(transferred)} transferred student(s)")

        elif choice == "2":
            if not transferred:
                # Quick source selection if not done yet
                if not current_source:
                    current_source = _choose_source()
                    if not current_source:
                        continue
                    try:
                        transferred = service.find_transferred_students(current_source)
                    except Exception as exc:
                        print(f"Error: {exc}")
                        continue

                if not transferred:
                    print("No transferred students available. Use option 1 first.")
                    continue

            try:
                num = input(f"Select student number (1-{len(transferred)}): ").strip()
                idx = int(num) - 1
            except (ValueError, EOFError, KeyboardInterrupt):
                print("Invalid selection.")
                continue

            if idx < 0 or idx >= len(transferred):
                print("Invalid selection.")
                continue

            student = transferred[idx]
            print(f"\nLooking up: {student.get('name', '?')}...")

            try:
                dest = service.find_destination(student["name"], current_source)
            except Exception as exc:
                print(f"Error: {exc}")
                continue

            if not dest:
                print(f"\n  Student: {student.get('name', '?')}")
                print(f"  Source:  {SYSTEM_LABELS.get(current_source, current_source)}")
                print(f"  Destination: NOT FOUND")
                print(f"  This student was not found in any destination system.")
                continue

            print(f"\n  Student: {student.get('name', '?')}")
            print(f"  Source: {SYSTEM_LABELS.get(current_source, current_source)} "
                  f"(ID: {student.get('student_id', '?')})")
            print(f"\n  --- Destination ---")
            print(f"  System:     {SYSTEM_LABELS.get(dest['dest_system'], dest['dest_system'])}")
            print(f"  Student ID: {dest.get('student_id', 'N/A')}")
            print(f"  Name:       {dest.get('name', 'N/A')}")
            print(f"  Status:     {dest.get('status', 'N/A')}")
            print(f"  Year/Group: {dest.get('year_group', 'N/A')}")

            if dest.get("previous_system_id"):
                print(f"  Prev ID:    {dest['previous_system_id']}")

            grades = dest.get("grades_summary", [])
            if grades:
                print(f"\n  --- Recent Grades ({len(grades)} record(s)) ---")
                for g in grades:
                    print(f"    {g}")

        elif choice == "3":
            src = _choose_source()
            if not src:
                continue

            print(f"\nComputing destination summary for {SYSTEM_LABELS.get(src, src)}...")
            print("(This may take a moment as each student is looked up.)\n")

            try:
                summary = service.get_destination_summary(src)
            except Exception as exc:
                print(f"Error: {exc}")
                continue

            total = summary.pop("_total_transferred", 0)
            print(f"Total Transferred: {total}")
            print(f"\n{'Destination':<30} {'Count':>6}")
            print("-" * 38)
            for label, count in sorted(summary.items()):
                print(f"{label:<30} {count:>6}")

        else:
            print("Invalid choice.")
