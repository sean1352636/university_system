"""Assessment CLI menu."""

from education_system.primary_school.infrastructure.database.db import get_db_path


def assessment_menu(auth):
    """Assessment management menu."""
    from education_system.primary_school.cli.cli_main import print_header, print_menu, get_choice
    from education_system.primary_school.modules.domain.academics.assessment.services.assessment_service import AssessmentService

    svc = AssessmentService(get_db_path())

    while True:
        print_header("Assessment")
        print_menu([
            ("1", "List assessments"),
            ("2", "View details"),
            ("3", "Add Assessment"),
            ("4", "Update Assessment"),
            ("5", "Delete Assessment"),
            ("0", "Back"),
        ])

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            items = svc.list_assessments()
            if not items:
                print("\n  No records found.")
            else:
                for item in items:
                    print(f"  {dict(item) if hasattr(item, 'keys') else item}")
        elif choice == "2":
            pk = input("  Enter ID: ").strip()
            try:
                item = svc.get_assessment(int(pk))
                if item:
                    for k, v in (dict(item) if hasattr(item, "keys") else {}).items():
                        print(f"  {k}: {v}")
                else:
                    print("\n  Not found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            pupil_id = input("  Pupil Id: ").strip()
            subject_code = input("  Subject Code: ").strip()
            level = input("  Level: ").strip()
            term = input("  Term: ").strip()
            try:
                svc.create_assessment(pupil_id=pupil_id, subject_code=subject_code, level=level, term=term)
                print("\n  Assessment created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            pk = input("  Enter ID to update: ").strip()
            pupil_id = input("  Pupil Id: ").strip()
            subject_code = input("  Subject Code: ").strip()
            level = input("  Level: ").strip()
            term = input("  Term: ").strip()
            try:
                svc.update_assessment(int(pk), pupil_id=pupil_id, subject_code=subject_code, level=level, term=term)
                print("\n  Assessment updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            pk = input("  Enter ID to delete: ").strip()
            try:
                svc.delete_assessment(int(pk))
                print("\n  Assessment deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        else:
            print("\n  Invalid option.")
