"""Bulk Transfer CLI module.

Provides a text-based menu for performing batch student transfers between
education systems.
"""

from education_system.shared.bulk_transfer.bulk_transfer_service import (
    BulkTransferService,
    DESTINATION_MAP,
)

SYSTEM_LABELS = {
    "primary": "Primary School",
    "secondary": "Secondary School",
    "college": "Sixth Form College",
    "university": "University",
}

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
    """Entry point for the Bulk Transfer CLI menu."""
    service = BulkTransferService()
    current_source = None
    eligible = []
    selected_ids = []

    while True:
        print("\n=== Bulk Student Transfer ===")
        print("1) List eligible students")
        print("2) Select students for transfer (comma-separated IDs)")
        print("3) Execute transfer")
        print("4) View last transfer results")
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
            dest = DESTINATION_MAP.get(current_source, "N/A")
            print(f"\nSource: {SYSTEM_LABELS.get(current_source, current_source)}")
            print(f"Destination: {SYSTEM_LABELS.get(dest, dest)}")
            print("-" * 60)

            try:
                eligible = service.get_eligible_students(current_source)
            except Exception as exc:
                print(f"Error: {exc}")
                eligible = []
                continue

            if not eligible:
                print("No eligible students found.")
                continue

            print(f"{'ID':<15} {'Name':<30} {'Year':<10} {'Status':<12}")
            print("-" * 60)
            for stu in eligible:
                print(
                    f"{stu.get('student_id', '?'):<15} "
                    f"{stu.get('name', ''):<30} "
                    f"{stu.get('year_group', ''):<10} "
                    f"{stu.get('status', ''):<12}"
                )
            print(f"\nTotal: {len(eligible)} student(s)")
            selected_ids = []

        elif choice == "2":
            if not eligible:
                print("Load eligible students first (option 1).")
                continue
            try:
                raw = input("Enter student IDs (comma-separated): ").strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if not raw:
                print("No IDs entered.")
                continue
            entered = [s.strip() for s in raw.split(",") if s.strip()]
            valid_ids = {stu["student_id"] for stu in eligible}
            selected_ids = [sid for sid in entered if sid in valid_ids]
            invalid = [sid for sid in entered if sid not in valid_ids]
            print(f"\nSelected: {len(selected_ids)} student(s)")
            if invalid:
                print(f"Invalid/not eligible IDs ignored: {', '.join(invalid)}")
            for sid in selected_ids:
                stu = next((s for s in eligible if s["student_id"] == sid), {})
                print(f"  {sid} - {stu.get('name', '?')}")

        elif choice == "3":
            if not selected_ids:
                print("Select students first (option 2).")
                continue
            if not current_source:
                print("Choose a source system first (option 1).")
                continue
            dest = DESTINATION_MAP.get(current_source)
            if not dest:
                print("No valid destination for this source system.")
                continue

            print(f"\nAbout to transfer {len(selected_ids)} student(s)")
            print(f"  From: {SYSTEM_LABELS.get(current_source, current_source)}")
            print(f"  To:   {SYSTEM_LABELS.get(dest, dest)}")
            try:
                confirm = input("Proceed? (y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                continue
            if confirm != "y":
                print("Cancelled.")
                continue

            print("Transferring...")
            try:
                results = service.transfer_batch(current_source, dest, selected_ids)
            except Exception as exc:
                print(f"Error: {exc}")
                continue

            print(f"\nTransferred: {results.get('transferred', 0)}")
            print(f"Failed:      {results.get('failed', 0)}")
            for d in results.get("details", []):
                sid = d.get("student_id", "?")
                name = d.get("name", "")
                if d.get("success"):
                    print(f"  OK   {sid}  {name}")
                else:
                    print(f"  FAIL {sid}  {name}  ({d.get('error', 'unknown')})")

            eligible = []
            selected_ids = []

        elif choice == "4":
            results = service.get_last_results()
            if not results:
                print("No transfer results available yet.")
                continue

            print(f"\nLast transfer: {results.get('source_system', '?')} -> {results.get('dest_system', '?')}")
            print(f"Timestamp:     {results.get('timestamp', '')}")
            print(f"Transferred:   {results.get('transferred', 0)}")
            print(f"Failed:        {results.get('failed', 0)}")
            for d in results.get("details", []):
                sid = d.get("student_id", "?")
                name = d.get("name", "")
                if d.get("success"):
                    print(f"  OK   {sid}  {name}")
                else:
                    print(f"  FAIL {sid}  {name}  ({d.get('error', 'unknown')})")

        else:
            print("Invalid choice.")
