"""Transfer Documents CLI module.

Provides a text-based menu for searching students, generating transition
reports, and saving them to file.
"""

from education_system.shared.transfer_docs.transfer_docs_service import (
    TransferDocsService,
    SYSTEM_LABELS,
)


def run(db_path=None, auth=None):
    """Entry point for the Transfer Documents CLI menu."""
    service = TransferDocsService()
    search_results = []
    current_report = ""

    while True:
        print("\n=== Transfer Documents ===")
        print("1) Search student")
        print("2) Generate report")
        print("3) Save report to file")
        print("0) Back")

        try:
            choice = input("\nChoice: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "0":
            break

        elif choice == "1":
            try:
                query = input("Student name: ").strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if not query:
                print("No name entered.")
                continue

            try:
                search_results = service.search_students(query)
            except Exception as exc:
                print(f"Error: {exc}")
                search_results = []
                continue

            if not search_results:
                print("No students found.")
                continue

            print(f"\n{'#':<4} {'System':<18} {'ID':<15} {'Name':<30} {'Year':<10} {'Status':<10}")
            print("-" * 87)
            for i, r in enumerate(search_results, 1):
                sys_label = SYSTEM_LABELS.get(r["system"], r["system"])
                print(
                    f"{i:<4} {sys_label:<18} {r.get('student_id', ''):<15} "
                    f"{r.get('name', ''):<30} {r.get('year_group', ''):<10} "
                    f"{r.get('status', ''):<10}"
                )
            print(f"\nTotal: {len(search_results)} result(s)")

        elif choice == "2":
            if not search_results:
                print("Search for a student first (option 1).")
                continue

            try:
                num = input(f"Select student number (1-{len(search_results)}): ").strip()
                idx = int(num) - 1
            except (ValueError, EOFError, KeyboardInterrupt):
                print("Invalid selection.")
                continue

            if idx < 0 or idx >= len(search_results):
                print("Invalid selection.")
                continue

            student = search_results[idx]
            print(f"\nGenerating report for {student.get('name', '?')} "
                  f"({SYSTEM_LABELS.get(student['system'], student['system'])})...")

            try:
                current_report = service.generate_report(
                    student_name=student.get("name", ""),
                    source_system=student["system"],
                    student_id=student.get("student_id", ""),
                )
            except Exception as exc:
                print(f"Error: {exc}")
                current_report = ""
                continue

            print("\n" + current_report)

        elif choice == "3":
            if not current_report:
                print("Generate a report first (option 2).")
                continue

            try:
                filepath = input("Save to file path: ").strip()
            except (EOFError, KeyboardInterrupt):
                continue
            if not filepath:
                print("No path entered.")
                continue

            try:
                saved = service.save_report(current_report, filepath)
                print(f"Report saved to: {saved}")
            except Exception as exc:
                print(f"Error saving: {exc}")

        else:
            print("Invalid choice.")
