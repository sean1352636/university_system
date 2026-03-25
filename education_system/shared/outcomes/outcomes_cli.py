"""Student outcome tracking CLI module.

Provides a text-based menu for viewing student outcomes after they leave
each education system.
"""

from education_system.shared.outcomes.outcomes_service import (
    OutcomesService,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
)


def run(db_path=None, auth=None):
    """Run the student outcome tracking CLI menu loop."""
    service = OutcomesService()

    while True:
        print("\n" + "=" * 60)
        print("  Student Outcome Tracking")
        print("=" * 60)
        print("  1) View outcomes by source system")
        print("  2) Progression statistics")
        print("  3) Search student outcome")
        print("  0) Back")
        print("-" * 60)

        choice = input("Select option: ").strip()

        if choice == "1":
            _view_outcomes(service)
        elif choice == "2":
            _progression_stats(service)
        elif choice == "3":
            _search_student(service)
        elif choice == "0":
            break
        else:
            print("Invalid option. Please try again.")


def _select_system():
    """Prompt the user to select a source system."""
    print("\n  Available systems:")
    for i, sys_key in enumerate(SYSTEM_ORDER, 1):
        print(f"    {i}) {SYSTEM_LABELS[sys_key]}")

    try:
        idx = int(input("  Select system (number): ").strip()) - 1
        if 0 <= idx < len(SYSTEM_ORDER):
            return SYSTEM_ORDER[idx]
    except (ValueError, IndexError):
        pass
    print("  Invalid selection.")
    return None


def _view_outcomes(service):
    """View outcomes for students who left a specific system."""
    system = _select_system()
    if not system:
        return

    try:
        outcomes = service.get_outcomes_for_system(system)
    except Exception as exc:
        print(f"  Error: {exc}")
        return

    print(f"\n--- Outcomes for students from {SYSTEM_LABELS[system]} ---")
    if not outcomes:
        print("  No outcome data found.")
        return

    print(f"\n  {'Student Name':<30} {'Destination':<22} {'Status':<15} {'Grade Avg':>10}")
    print("  " + "-" * 80)
    for o in outcomes:
        dest = SYSTEM_LABELS.get(o.get("destination_system", ""),
                                  o.get("destination_system", ""))
        grade = f"{o['grade_average']:.1f}" if o.get("grade_average") is not None else "N/A"
        print(f"  {o.get('student_name', ''):<30} {dest:<22} "
              f"{o.get('destination_status', ''):<15} {grade:>10}")

    print(f"\n  Total: {len(outcomes)} student(s)")


def _progression_stats(service):
    """Show progression statistics for a source system."""
    system = _select_system()
    if not system:
        return

    try:
        stats = service.get_progression_stats(system)
    except Exception as exc:
        print(f"  Error: {exc}")
        return

    print(f"\n--- Progression Statistics: {stats['source_label']} ---")
    print(f"  Total students who left:    {stats['total_left']}")
    print(f"  Successfully progressed:    {stats['progressed_count']}")
    print(f"  Progression rate:           {stats['progression_rate']}%")

    avg = stats.get("avg_grade_at_destination")
    print(f"  Avg grade at destination:   {avg:.1f}" if avg is not None else
          "  Avg grade at destination:   N/A")

    breakdown = stats.get("destination_status_breakdown", {})
    if breakdown:
        print("\n  Status breakdown at destination:")
        for status, count in sorted(breakdown.items()):
            print(f"    {status:<20} {count:>5}")


def _search_student(service):
    """Search for a specific student's outcome."""
    name = input("\n  Enter student name to search: ").strip()
    if not name:
        print("  No name entered.")
        return

    try:
        results = service.search_student_outcome(name)
    except Exception as exc:
        print(f"  Error: {exc}")
        return

    if not results:
        print(f"  No outcomes found for '{name}'.")
        return

    print(f"\n--- Outcomes for '{name}' ---")
    print(f"\n  {'Name':<25} {'Source':<18} {'Destination':<18} {'Status':<15} {'Grade':>8}")
    print("  " + "-" * 88)
    for r in results:
        src = SYSTEM_LABELS.get(r.get("source_system", ""), r.get("source_system", ""))
        dst = SYSTEM_LABELS.get(r.get("destination_system", ""), r.get("destination_system", ""))
        grade = f"{r['grade_average']:.1f}" if r.get("grade_average") is not None else "N/A"
        print(f"  {r.get('student_name', ''):<25} {src:<18} {dst:<18} "
              f"{r.get('destination_status', ''):<15} {grade:>8}")

    print(f"\n  Total: {len(results)} result(s)")


if __name__ == "__main__":
    run()
