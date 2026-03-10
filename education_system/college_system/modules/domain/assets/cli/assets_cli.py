"""Assets CLI for managing equipment loans."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.assets.services.assets_service import AssetsService


def assets_menu(auth: UserAuth):
    svc = AssetsService(auth._db_path)

    while True:
        print_header("Asset Loans")
        options = [
            ("1", "List Loans"),
            ("2", "New Loan"),
            ("3", "Return Asset"),
            ("4", "View Student Loans"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            status = input("  Status filter (on_loan/returned or Enter for all): ").strip() or None
            loans = svc.list_loans(status=status)
            for l in loans:
                name = f"{l.get('first_name', '')} {l.get('last_name', '')}".strip() or str(l.get("loaned_to", ""))
                print(f"  [{l['id']}] {l.get('asset_name', '')} ({l.get('asset_tag', '')}) -> {name} [{l.get('status', '')}]")
            if not loans:
                print("  No loans found.")
        elif choice == "2":
            try:
                asset_name = input("  Asset Name: ").strip()
                asset_tag = input("  Asset Tag: ").strip()
                loaned_to = int(input("  Student ID: ").strip())
                atype = input("  Type (laptop/tablet/camera/other): ").strip() or "laptop"
                user_id = auth.current_user["user_id"]
                l = svc.create_loan(asset_name, asset_tag, loaned_to, asset_type=atype, issued_by=user_id)
                print(f"\n  Loan #{l['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                lid = int(input("  Loan ID: ").strip())
                condition = input("  Condition (good/fair/poor/damaged): ").strip() or "good"
                svc.return_asset(lid, condition_in=condition)
                print("  Asset returned.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                sid = int(input("  Student ID: ").strip())
                loans = svc.get_student_loans(sid)
                for l in loans:
                    print(f"  [{l['id']}] {l.get('asset_name', '')} ({l.get('asset_tag', '')}) [{l.get('status', '')}]")
                if not loans:
                    print("  No loans for this student.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
