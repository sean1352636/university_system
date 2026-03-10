"""Attendance CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def attendance_menu(auth):
    """Attendance management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService

    svc = AttendanceService(get_db_path())

    while True:
        print_header("Attendance")
        print_menu([
            ("1", "List attendance_records"),
            ("2", "View details"),
            ("3", "Add Attendance"),
            ("4", "Update Attendance"),
            ("5", "Delete Attendance"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_attendance_records()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_attendance(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pupil_id = input("  Pupil Id: ").strip()
            date = input("  Date: ").strip()
            status = input("  Status: ").strip()
            try:
                svc.create_attendance(pupil_id=pupil_id, date=date, status=status)
                print("\n  Attendance created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            pupil_id = input("  Pupil Id: ").strip()
            date = input("  Date: ").strip()
            status = input("  Status: ").strip()
            try:
                svc.update_attendance(int(pk), pupil_id=pupil_id, date=date, status=status)
                print("\n  Attendance updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_attendance(int(pk))
                print("\n  Attendance deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
