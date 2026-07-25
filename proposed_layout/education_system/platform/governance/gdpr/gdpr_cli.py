"""GDPR Data Subject Request CLI.

Text-based menu interface for GDPR compliance operations:
searching students across systems, generating SAR reports,
exporting data, anonymising records, and checking data retention.
"""

from education_system.platform.governance.gdpr.gdpr_service import GDPRService, SYSTEM_LABELS

SYSTEM_KEYS = ["primary", "secondary", "sixth_form", "university"]


def _print_header(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def _search_student(svc):
    _print_header("Search Student Across Systems")
    name = input("  Name (or blank): ").strip() or None
    email = input("  Email (or blank): ").strip() or None
    dob = input("  DOB [YYYY-MM-DD] (or blank): ").strip() or None

    if not name and not email and not dob:
        print("\n  Please provide at least one search criterion.")
        return

    results = svc.search_all_systems(name=name, email=email, dob=dob)
    if not results:
        print("\n  No matching records found.")
    else:
        print(f"\n  Found {len(results)} record(s):\n")
        print(f"  {'System':20s} {'ID':12s} {'Name':25s} {'Email':25s} {'DOB':12s} {'Status':10s}")
        print("  " + "-" * 104)
        for r in results:
            print(f"  {r['system_label']:20s} {r['student_id']:12s} "
                  f"{r['name']:25s} {r['email']:25s} {r['dob']:12s} {r['status']:10s}")
    print()


def _generate_sar(svc):
    _print_header("Generate SAR Report")
    name = input("  Student name: ").strip()
    if not name:
        print("\n  Name is required.")
        return

    report = svc.generate_sar_report(name)
    print()
    print(report)

    save = input("\n  Save to file? (y/n): ").strip().lower()
    if save == "y":
        filepath = input("  File path [sar_report.txt]: ").strip() or "sar_report.txt"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"  Report saved to: {filepath}")
        except Exception as e:
            print(f"  Error saving: {e}")
    print()


def _export_data(svc):
    _print_header("Export Student Data")
    name = input("  Student name: ").strip()
    if not name:
        print("\n  Name is required.")
        return

    data = svc.get_full_data_export(name)
    if not data:
        print(f"\n  No data found for '{name}'.")
        return

    for system, sys_data in data.items():
        label = SYSTEM_LABELS.get(system, system.capitalize())
        print(f"\n  --- {label} ---")
        pi = sys_data.get("personal_info", {})
        if pi:
            print("  Personal info:")
            for k, v in pi.items():
                if v is not None and v != "":
                    print(f"    {k}: {v}")

        grades = sys_data.get("grades", [])
        if grades:
            print(f"  Grades: {len(grades)} record(s)")

        att = sys_data.get("attendance", [])
        if att:
            print(f"  Attendance: {len(att)} record(s)")
    print()


def _anonymise_student(svc):
    _print_header("Anonymise Student Data")
    print("\n  WARNING: This operation is IRREVERSIBLE.")
    print("  All PII will be permanently replaced with 'REDACTED'.\n")

    name = input("  Student name: ").strip()
    if not name:
        print("\n  Name is required.")
        return

    print("\n  Select system:")
    for i, key in enumerate(SYSTEM_KEYS, 1):
        print(f"    {i}) {SYSTEM_LABELS.get(key, key)}")
    choice = input("  System: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(SYSTEM_KEYS)):
        print("\n  Invalid choice.")
        return
    system = SYSTEM_KEYS[int(choice) - 1]

    # Strong confirmation
    confirm = input(
        f"\n  Type '{name}' to confirm anonymisation in "
        f"{SYSTEM_LABELS.get(system, system)}: "
    ).strip()

    if confirm != name:
        print("\n  Confirmation failed. Anonymisation cancelled.")
        return

    try:
        count = svc.anonymise_student(name, system)
        print(f"\n  Successfully anonymised {count} record(s) for '{name}' "
              f"in {SYSTEM_LABELS.get(system, system)}.")
    except Exception as e:
        print(f"\n  Error: {e}")
    print()


def _retention_report(svc):
    _print_header("Data Retention Report")
    years_str = input("  Retention period in years [6]: ").strip() or "6"
    try:
        years = int(years_str)
    except ValueError:
        years = 6

    records = svc.get_data_retention_report(retention_years=years)
    if not records:
        print(f"\n  No records older than {years} years found.")
    else:
        print(f"\n  {len(records)} record(s) older than {years} years:\n")
        print(f"  {'System':20s} {'ID':12s} {'Name':25s} {'Oldest Date':12s} {'Age (yrs)':10s}")
        print("  " + "-" * 79)
        for r in records:
            print(f"  {r['system_label']:20s} {r['student_id']:12s} "
                  f"{r['name']:25s} {r['oldest_date']:12s} {str(r['age_years']):10s}")
    print()


def run(db_path=None, auth=None):
    """Run the GDPR Compliance CLI menu loop."""
    svc = GDPRService()
    _print_header("GDPR Compliance")

    while True:
        print("\n  1) Search student across systems")
        print("  2) Generate SAR report")
        print("  3) Export student data")
        print("  4) Anonymise student")
        print("  5) Data retention report")
        print("  0) Back")

        choice = input("\n  Select option: ").strip()

        if choice == "1":
            _search_student(svc)
        elif choice == "2":
            _generate_sar(svc)
        elif choice == "3":
            _export_data(svc)
        elif choice == "4":
            _anonymise_student(svc)
        elif choice == "5":
            _retention_report(svc)
        elif choice == "0":
            print("\n  Returning...\n")
            break
        else:
            print("\n  Invalid option. Please try again.")
