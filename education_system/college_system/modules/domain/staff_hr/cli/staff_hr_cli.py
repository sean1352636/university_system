"""Staff HR CLI for managing HR records."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.staff_hr.services.staff_hr_service import StaffHRService


def staff_hr_menu(auth: UserAuth):
    svc = StaffHRService(auth._db_path)

    while True:
        print_header("Staff HR")
        options = [
            ("1", "List Staff Records"),
            ("2", "New HR Record"),
            ("3", "View Record Details"),
            ("4", "Update Record"),
            ("5", "List Departments"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            dept = input("  Department (or Enter for all): ").strip() or None
            records = svc.list_records(department=dept)
            for r in records:
                print(f"  [{r['id']}] {r.get('username', '')} - {r.get('department', '')} / {r.get('role_title', '')} ({r.get('status', '')})")
            if not records:
                print("  No records found.")
        elif choice == "2":
            try:
                uid = int(input("  User ID: ").strip())
                dept = input("  Department: ").strip() or None
                role = input("  Role Title: ").strip() or None
                contract = input("  Contract (permanent/fixed_term/part_time): ").strip() or "permanent"
                r = svc.create_record(uid, department=dept, role_title=role, contract_type=contract)
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
                status = input("  Status (active/on_leave/suspended/terminated): ").strip()
                svc.update_record(rid, status=status)
                print("  Record updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            depts = svc.list_departments()
            for d in depts:
                print(f"  - {d}")
            if not depts:
                print("  No departments found.")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
