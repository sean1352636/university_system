"""Self-Assessment CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def self_assessment_menu(auth):
    """Self-Assessment management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.admin.self_assessment.services.self_assessment_service import SelfAssessmentService

    svc = SelfAssessmentService(get_db_path())

    while True:
        print_header("Self-Assessment")
        print_menu([
            ("1", "List records"),
            ("2", "View details"),
            ("3", "Add record"),
            ("4", "Update record"),
            ("5", "Delete record"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_all()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            academic_year = input("  Academic Year: ").strip()
            area = input("  Area: ").strip()
            ofsted_grade = input("  Ofsted Grade: ").strip()
            status = input("  Status: ").strip()
            try:
                svc.create(academic_year=academic_year, area=area, ofsted_grade=ofsted_grade, status=status)
                print("\n  Record created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            academic_year = input("  Academic Year: ").strip()
            area = input("  Area: ").strip()
            ofsted_grade = input("  Ofsted Grade: ").strip()
            status = input("  Status: ").strip()
            try:
                svc.update(int(pk), academic_year=academic_year, area=area, ofsted_grade=ofsted_grade, status=status)
                print("\n  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete(int(pk))
                print("\n  Record deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
