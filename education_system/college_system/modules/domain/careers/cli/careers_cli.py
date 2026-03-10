"""Careers CLI for managing careers activities, UCAS, and work experience."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.careers.services.careers_service import CareersService


def careers_menu(auth: UserAuth):
    svc = CareersService(auth._db_path)

    while True:
        print_header("Careers & Progression")
        options = [
            ("1", "Careers Activities"),
            ("2", "New Activity"),
            ("3", "UCAS Records"),
            ("4", "New UCAS Record"),
            ("5", "Update UCAS Record"),
            ("6", "Work Experience"),
            ("7", "New Work Experience"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            sid = input("  Student ID (or Enter for all): ").strip()
            activities = svc.list_activities(student_id=int(sid) if sid else None)
            for a in activities:
                name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() or str(a.get("student_id", ""))
                print(f"  [{a['id']}] {name} - {a.get('title', '')} ({a.get('activity_type', '')}) {a.get('activity_date', '')}")
            if not activities:
                print("  No activities found.")
        elif choice == "2":
            try:
                sid = int(input("  Student ID: ").strip())
                title = input("  Title: ").strip()
                atype = input("  Type: ").strip() or "careers_talk"
                a = svc.create_activity(sid, atype, title)
                print(f"\n  Activity #{a['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            records = svc.list_ucas_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} - UCAS: {r.get('ucas_id', '')} PS: {r.get('personal_statement_status', '')} App: {r.get('application_status', '')}")
            if not records:
                print("  No UCAS records found.")
        elif choice == "4":
            try:
                sid = int(input("  Student ID: ").strip())
                ucas_id = input("  UCAS ID: ").strip() or None
                r = svc.create_ucas_record(sid, ucas_id=ucas_id)
                print(f"\n  Record #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            try:
                rid = int(input("  Record ID: ").strip())
                ps = input("  Personal Statement Status: ").strip() or None
                ref = input("  Reference Status: ").strip() or None
                app = input("  Application Status: ").strip() or None
                kwargs = {}
                if ps:
                    kwargs["personal_statement_status"] = ps
                if ref:
                    kwargs["reference_status"] = ref
                if app:
                    kwargs["application_status"] = app
                if kwargs:
                    svc.update_ucas_record(rid, **kwargs)
                    print("  Record updated.")
                else:
                    print("  Nothing to update.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "6":
            sid = input("  Student ID (or Enter for all): ").strip()
            records = svc.list_work_experience(student_id=int(sid) if sid else None)
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} - {r.get('employer', '')} ({r.get('role', '')}) {r.get('start_date', '')} - {r.get('end_date', '')}")
            if not records:
                print("  No work experience records.")
        elif choice == "7":
            try:
                sid = int(input("  Student ID: ").strip())
                employer = input("  Employer: ").strip()
                role = input("  Role: ").strip() or None
                start = input("  Start Date: ").strip() or None
                end = input("  End Date: ").strip() or None
                r = svc.create_work_experience(sid, employer, role=role, start_date=start, end_date=end)
                print(f"\n  Record #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
