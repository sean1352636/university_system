"""SEND/ALS CLI for managing special educational needs and interventions."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.send.services.send_service import SENDService


def send_menu(auth: UserAuth):
    svc = SENDService(auth._db_path)

    while True:
        print_header("SEND / ALS")
        options = [
            ("1", "List SEND Records"),
            ("2", "New SEND Record"),
            ("3", "View Record Details"),
            ("4", "Update Record"),
            ("5", "List Interventions"),
            ("6", "New Intervention"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            records = svc.list_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                ehcp = "EHCP" if r.get("ehcp") else ""
                print(f"  [{r['id']}] {name} - {r.get('need_type', '')} ({r.get('status', '')}) {ehcp}")
            if not records:
                print("  No SEND records found.")
        elif choice == "2":
            try:
                sid = int(input("  Student ID: ").strip())
                need = input("  Need Type: ").strip()
                desc = input("  Description: ").strip()
                ehcp = input("  EHCP in place? (y/n): ").strip().lower() == "y"
                r = svc.create_record(sid, need, desc, ehcp=1 if ehcp else 0)
                print(f"\n  Record #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
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
                status = input("  Status (active/review/closed): ").strip()
                svc.update_record(rid, status=status)
                print("  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            sid = input("  Student ID (or Enter for all): ").strip()
            interventions = svc.list_interventions(student_id=int(sid) if sid else None)
            for iv in interventions:
                name = f"{iv.get('first_name', '')} {iv.get('last_name', '')}".strip() or str(iv.get("student_id", ""))
                print(f"  [{iv['id']}] {name} - {iv.get('intervention_type', '')} ({iv.get('status', '')})")
            if not interventions:
                print("  No interventions found.")
        elif choice == "6":
            try:
                sid = int(input("  Student ID: ").strip())
                itype = input("  Type: ").strip()
                desc = input("  Description: ").strip()
                iv = svc.create_intervention(sid, itype, desc)
                print(f"\n  Intervention #{iv['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
