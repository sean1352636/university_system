"""Behaviour CLI for managing conduct records."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.behaviour.services.behaviour_service import BehaviourService


def behaviour_menu(auth: UserAuth):
    svc = BehaviourService(auth._db_path)

    while True:
        print_header("Behaviour & Conduct")
        options = [
            ("1", "Record Incident"),
            ("2", "List Records"),
            ("3", "View Record Details"),
            ("4", "Update Record"),
            ("5", "Student Summary"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            try:
                sid = int(input("  Student ID: ").strip())
                itype = input("  Type (positive/negative/bullying/disruption): ").strip() or "negative"
                desc = input("  Description: ").strip()
                severity = input("  Severity (minor/moderate/major/critical): ").strip() or "minor"
                user_id = auth.current_user["user_id"]
                r = svc.record_incident(sid, user_id, itype, desc, severity=severity)
                print(f"\n  Record #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "2":
            sid = input("  Student ID (or Enter for all): ").strip()
            records = svc.list_records(student_id=int(sid) if sid else None)
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                resolved = "Resolved" if r.get("resolved") else "Open"
                print(f"  [{r['id']}] {name} - {r.get('incident_type', '')} ({r.get('severity', '')}) [{resolved}]")
            if not records:
                print("  No records found.")
        elif choice == "3":
            try:
                rid = int(input("  Record ID: ").strip())
                r = svc.get_record(rid)
                for k, v in r.items():
                    print(f"  {k}: {v}")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                rid = int(input("  Record ID: ").strip())
                action = input("  Action Taken: ").strip() or None
                resolved = input("  Resolved? (y/n): ").strip().lower() == "y"
                kwargs = {"resolved": 1 if resolved else 0}
                if action:
                    kwargs["action_taken"] = action
                svc.update_record(rid, **kwargs)
                print("  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            try:
                sid = int(input("  Student ID: ").strip())
                summary = svc.count_by_type(sid)
                for t, count in summary.items():
                    print(f"  {t}: {count}")
                if not summary:
                    print("  No records for this student.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
