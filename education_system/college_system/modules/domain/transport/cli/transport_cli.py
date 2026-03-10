"""Transport CLI for managing student transport."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.transport.services.transport_service import TransportService


def transport_menu(auth: UserAuth):
    svc = TransportService(auth._db_path)

    while True:
        print_header("Transport")
        options = [
            ("1", "List Records"),
            ("2", "New Record"),
            ("3", "Update Record"),
            ("4", "Delete Record"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            records = svc.list_records()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                funded = "Funded" if r.get("funded") else ""
                print(f"  [{r['id']}] {name} - {r.get('transport_type', '')} Route: {r.get('route', '')} {funded}")
            if not records:
                print("  No records found.")
        elif choice == "2":
            try:
                sid = int(input("  Student ID: ").strip())
                ttype = input("  Type (bus/train/taxi/walking/cycling/car): ").strip()
                route = input("  Route: ").strip() or None
                pickup = input("  Pickup Point: ").strip() or None
                r = svc.create_record(sid, ttype, route=route, pickup_point=pickup)
                print(f"\n  Record #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                rid = int(input("  Record ID: ").strip())
                status = input("  Status (active/suspended/cancelled): ").strip()
                svc.update_record(rid, status=status)
                print("  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                rid = int(input("  Record ID: ").strip())
                confirm = input("  Confirm delete? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_record(rid)
                    print("  Record deleted.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
