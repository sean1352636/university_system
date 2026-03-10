"""Bursary CLI for managing bursary records and free meals."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.bursary.services.bursary_service import BursaryService


def bursary_menu(auth: UserAuth):
    svc = BursaryService(auth._db_path)

    while True:
        print_header("Bursary & Free Meals")
        options = [
            ("1", "List Bursary Records"),
            ("2", "New Bursary"),
            ("3", "Update Bursary"),
            ("4", "Free Meals - Eligible Students"),
            ("5", "Set Meal Eligibility"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            records = svc.list_bursaries()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} - {r.get('bursary_type', '')} £{r.get('amount', 0):.2f} ({r.get('status', '')})")
            if not records:
                print("  No bursary records.")
        elif choice == "2":
            try:
                sid = int(input("  Student ID: ").strip())
                btype = input("  Type (vulnerable/discretionary/free_meals): ").strip()
                amt = input("  Amount: ").strip()
                r = svc.create_bursary(sid, btype, amount=float(amt) if amt else 0.0)
                print(f"\n  Bursary #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                bid = int(input("  Bursary ID: ").strip())
                status = input("  Status (pending/approved/rejected): ").strip()
                svc.update_bursary(bid, status=status)
                print("  Bursary updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            records = svc.list_meal_eligible()
            for r in records:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  {name} - Evidence: {r.get('evidence_type', '')}")
            if not records:
                print("  No eligible students.")
        elif choice == "5":
            try:
                sid = int(input("  Student ID: ").strip())
                eligible = input("  Eligible? (y/n): ").strip().lower() == "y"
                evidence = input("  Evidence Type: ").strip() or None
                user_id = auth.current_user["user_id"]
                svc.set_meal_eligibility(sid, eligible=1 if eligible else 0,
                                          evidence_type=evidence, verified_by=user_id)
                print("  Eligibility updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
