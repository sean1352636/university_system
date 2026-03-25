"""Predictive alerts CLI module.

Provides a text-based menu for viewing at-risk student alerts based
on cross-system analysis.
"""

from education_system.shared.predictive.predictive_service import (
    PredictiveService,
    SYSTEM_LABELS,
    SYSTEM_ORDER,
)


def run(db_path=None, auth=None):
    """Run the predictive alerts CLI menu loop."""
    service = PredictiveService()

    while True:
        print("\n" + "=" * 60)
        print("  Predictive At-Risk Alerts")
        print("=" * 60)
        print("  1) View all alerts")
        print("  2) Filter by risk level")
        print("  3) View student detail")
        print("  0) Back")
        print("-" * 60)

        choice = input("Select option: ").strip()

        if choice == "1":
            _view_all_alerts(service)
        elif choice == "2":
            _filter_by_level(service)
        elif choice == "3":
            _view_student_detail(service)
        elif choice == "0":
            break
        else:
            print("Invalid option. Please try again.")


def _select_system():
    """Prompt the user to select a system."""
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


def _view_all_alerts(service):
    """Scan and display all at-risk alerts for a system."""
    system = _select_system()
    if not system:
        return

    try:
        alerts = service.get_at_risk_students(system)
    except Exception as exc:
        print(f"  Error: {exc}")
        return

    _display_alerts(alerts, system)


def _filter_by_level(service):
    """Scan and filter alerts by risk level."""
    system = _select_system()
    if not system:
        return

    print("\n  Risk levels:")
    print("    1) High")
    print("    2) Medium")
    print("    3) Low")

    level_choice = input("  Select level: ").strip()
    level_map = {"1": "High", "2": "Medium", "3": "Low"}
    level = level_map.get(level_choice)
    if not level:
        print("  Invalid selection.")
        return

    try:
        alerts = service.get_at_risk_students(system)
    except Exception as exc:
        print(f"  Error: {exc}")
        return

    filtered = [a for a in alerts if a["risk_level"] == level]
    print(f"\n  Showing {level} risk alerts ({len(filtered)} of {len(alerts)} total)")
    _display_alerts(filtered, system)


def _display_alerts(alerts, system):
    """Print alerts in a table format."""
    label = SYSTEM_LABELS.get(system, system)
    print(f"\n--- At-Risk Students in {label} ---")

    if not alerts:
        print("  No at-risk students found.")
        print("  (Students must have a previous_system_id to be analyzed)")
        return

    high = sum(1 for a in alerts if a["risk_level"] == "High")
    med = sum(1 for a in alerts if a["risk_level"] == "Medium")
    low = sum(1 for a in alerts if a["risk_level"] == "Low")
    print(f"  Summary: {high} High, {med} Medium, {low} Low  (Total: {len(alerts)})")

    print(f"\n  {'#':>3}  {'Student Name':<28} {'Risk':>6} {'Score':>5}  {'Key Factors'}")
    print("  " + "-" * 80)

    for i, a in enumerate(alerts, 1):
        factors = "; ".join(a.get("risk_factors", [])[:2])
        if len(a.get("risk_factors", [])) > 2:
            factors += " ..."
        print(f"  {i:>3}  {a.get('student_name', ''):<28} "
              f"{a.get('risk_level', ''):>6} {a.get('risk_score', 0):>5}  {factors}")


def _view_student_detail(service):
    """View detailed risk factors for a specific student."""
    system = _select_system()
    if not system:
        return

    student_id = input("\n  Enter student ID: ").strip()
    if not student_id:
        print("  No student ID entered.")
        return

    try:
        detail = service.get_risk_factors(student_id, system)
    except Exception as exc:
        print(f"  Error: {exc}")
        return

    if detail.get("error"):
        print(f"  Error: {detail['error']}")
        return

    print(f"\n--- Risk Detail: {detail.get('student_name', 'Unknown')} ---")
    print(f"  Student ID:      {detail.get('student_id', '')}")
    print(f"  System:          {SYSTEM_LABELS.get(detail.get('system', ''), detail.get('system', ''))}")
    print(f"  Risk Level:      {detail.get('risk_level', 'Unknown')}")
    print(f"  Risk Score:      {detail.get('risk_score', 0)} / 100")

    print("\n  Risk Factors:")
    for factor in detail.get("risk_factors", []):
        print(f"    - {factor}")
    if not detail.get("risk_factors"):
        print("    (none identified)")

    # Previous system info
    prev = detail.get("previous_system_info", {})
    if prev.get("available"):
        print(f"\n  Previous System: {prev.get('label', '')}")
        print(f"    Student ID:    {prev.get('student_id', '')}")
        print(f"    Status:        {prev.get('status', '')}")
        print(f"    Year Group:    {prev.get('year_group', '')}")

    # Transfer history summary
    transfers = detail.get("transfer_history", [])
    if transfers:
        print(f"\n  Transfer History: {len(transfers)} record(s)")
        for t in transfers[:5]:
            parts = []
            for key in ("source_system", "academic_year", "subject", "grade"):
                if key in t and t[key]:
                    parts.append(f"{key}: {t[key]}")
            print(f"    {' | '.join(parts) if parts else '(record)'}")
        if len(transfers) > 5:
            print(f"    ... and {len(transfers) - 5} more")

    # Attendance history summary
    att_records = detail.get("attendance_history", [])
    if att_records:
        print(f"\n  Attendance Records: {len(att_records)}")

    # Grade history summary
    grade_records = detail.get("grade_history", [])
    if grade_records:
        print(f"  Grade Records: {len(grade_records)}")


if __name__ == "__main__":
    run()
