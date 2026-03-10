"""Safeguarding CLI for managing concerns."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.safeguarding.services.safeguarding_service import SafeguardingService


def safeguarding_menu(auth: UserAuth):
    svc = SafeguardingService(auth._db_path)

    while True:
        print_header("Safeguarding")
        options = [
            ("1", "Report Concern"),
            ("2", "List Concerns"),
            ("3", "View Concern Details"),
            ("4", "Update Concern"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            try:
                sid = int(input("  Student ID: ").strip())
                category = input("  Category: ").strip()
                desc = input("  Description: ").strip()
                severity = input("  Severity (low/medium/high/critical): ").strip() or "low"
                user_id = auth.current_user["user_id"]
                c = svc.report_concern(sid, user_id, category, desc, severity=severity)
                print(f"\n  Concern #{c['id']} reported.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "2":
            status = input("  Filter by status (or Enter for all): ").strip() or None
            concerns = svc.list_concerns(status=status)
            for c in concerns:
                name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or str(c.get("student_id", ""))
                print(f"  [{c['id']}] {name} - {c.get('category', '')} ({c.get('severity', '')}) [{c.get('status', '')}]")
            if not concerns:
                print("  No concerns found.")
        elif choice == "3":
            try:
                cid = int(input("  Concern ID: ").strip())
                c = svc.get_concern(cid)
                for k, v in c.items():
                    print(f"  {k}: {v}")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                cid = int(input("  Concern ID: ").strip())
                status = input("  New Status: ").strip()
                outcome = input("  Outcome: ").strip() or None
                kwargs = {"status": status}
                if outcome:
                    kwargs["outcome"] = outcome
                svc.update_concern(cid, **kwargs)
                print("  Concern updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
