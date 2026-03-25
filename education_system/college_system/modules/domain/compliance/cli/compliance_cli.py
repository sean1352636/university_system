"""Compliance CLI for managing funding, resits, and destinations."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.compliance.services.compliance_service import ComplianceService


def compliance_menu(auth: UserAuth):
    svc = ComplianceService(auth._db_path)

    while True:
        print_header("Compliance & Funding")
        options = [
            ("1", "Funding Records"),
            ("2", "New Funding Record"),
            ("3", "Resit Tracking"),
            ("4", "New Resit"),
            ("5", "Destination Records"),
            ("6", "New Destination"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            records = svc.list_funding_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} - {r.get('learning_aim', '')} / {r.get('funding_model', '')} ({r.get('completion_status', '')})")
            if not records:
                print("  No funding records.")
        elif choice == "2":
            try:
                sid = int(input("  Student ID: ").strip())
                aim = input("  Learning Aim: ").strip()
                model = input("  Funding Model: ").strip()
                r = svc.create_funding_record(sid, aim, model)
                print(f"\n  Record #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            resits = svc.list_resits()
            for r in resits:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} - {r.get('subject', '')} {r.get('gcse_grade_on_entry', '')} -> {r.get('target_grade', '')} ({r.get('status', '')})")
            if not resits:
                print("  No resits found.")
        elif choice == "4":
            try:
                sid = int(input("  Student ID: ").strip())
                subject = input("  Subject: ").strip()
                gcse = input("  GCSE Grade on Entry: ").strip() or None
                target = input("  Target Grade: ").strip() or None
                r = svc.create_resit(sid, subject, gcse_grade_on_entry=gcse, target_grade=target)
                print(f"\n  Resit #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            dests = svc.list_destinations()
            for d in dests:
                name = f"{d.get('first_name', '')} {d.get('last_name', '')}".strip() or str(d.get("student_id", ""))
                contacted = "Contacted" if d.get("contact_made") else "Not contacted"
                print(f"  [{d['id']}] {name} - {d.get('destination_type', '')}: {d.get('institution_name', '')} [{contacted}]")
            if not dests:
                print("  No destinations found.")
        elif choice == "6":
            try:
                sid = int(input("  Student ID: ").strip())
                dtype = input("  Type (university/apprenticeship/employment/gap_year): ").strip()
                inst = input("  Institution Name: ").strip() or None
                course = input("  Course Title: ").strip() or None
                d = svc.create_destination(sid, dtype, institution_name=inst, course_title=course)
                print(f"\n  Destination #{d['id']} recorded.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
