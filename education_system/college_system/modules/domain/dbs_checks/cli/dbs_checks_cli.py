"""DBS Checks CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.dbs_checks.services.dbs_checks_service import DBSCheckService
from education_system.college_system.infrastructure.auth.core import UserAuth


def dbs_checks_menu(auth: UserAuth):
    """DBS Checks management menu."""
    svc = DBSCheckService(auth._db_path)

    while True:
        print_header("DBS Checks")
        options = [
            ("1", "List All Checks"),
            ("2", "View Check"),
            ("3", "New Check"),
            ("4", "Update Check"),
            ("5", "Delete Check"),
            ("6", "Expiring Soon"),
            ("7", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            status = input("  Status filter (valid/expired/pending or Enter): ").strip() or None
            records = svc.list_checks(status=status)
            for r in records:
                person = r.get("volunteer_name") or f"Staff #{r.get('staff_id', '')}" if r.get("staff_id") else f"Governor #{r.get('governor_id', '')}"
                upd = " [Update Svc]" if r.get("update_service") else ""
                print(f"  [{r['id']}] {person} | {r.get('check_type', '')} | "
                      f"Cert: {r.get('certificate_number', '')} | "
                      f"Expiry: {r.get('expiry_date', 'N/A')} | "
                      f"{r.get('status', '')}{upd}")
            if not records:
                print("  No DBS checks found.")

        elif choice == "2":
            try:
                cid = int(input("  Check ID: ").strip())
                rec = svc.get_check(cid)
                if not rec:
                    print("  Check not found.")
                    continue
                print(f"\n  Check Type:         {rec.get('check_type', '')}")
                print(f"  Staff ID:           {rec.get('staff_id', '')}")
                print(f"  Governor ID:        {rec.get('governor_id', '')}")
                print(f"  Volunteer:          {rec.get('volunteer_name', '')}")
                print(f"  Certificate #:      {rec.get('certificate_number', '')}")
                print(f"  Issue Date:         {rec.get('issue_date', '')}")
                print(f"  Expiry Date:        {rec.get('expiry_date', '')}")
                print(f"  Update Service:     {'Yes' if rec.get('update_service') else 'No'}")
                print(f"  Update Service ID:  {rec.get('update_service_id', '')}")
                print(f"  Barred List:        {'Yes' if rec.get('barred_list_checked') else 'No'}")
                print(f"  Children Workforce: {'Yes' if rec.get('children_workforce') else 'No'}")
                print(f"  Status:             {rec.get('status', '')}")
                print(f"  Notes:              {rec.get('notes', '')}")
            except ValueError:
                print("  Invalid ID.")

        elif choice == "3":
            try:
                sid = input("  Staff ID (or Enter): ").strip()
                gid = input("  Governor ID (or Enter): ").strip()
                vname = input("  Volunteer Name (or Enter): ").strip()
                if not sid and not gid and not vname:
                    print("  Must specify staff ID, governor ID, or volunteer name.")
                    continue
                ctype = input("  Check type (enhanced/standard/basic) [enhanced]: ").strip() or "enhanced"
                cert = input("  Certificate Number: ").strip() or None
                issue = input("  Issue Date (YYYY-MM-DD): ").strip() or None
                expiry = input("  Expiry Date (YYYY-MM-DD): ").strip() or None
                upd = input("  On Update Service? (y/n) [n]: ").strip().lower() == "y"
                barred = input("  Barred List Checked? (y/n) [n]: ").strip().lower() == "y"
                rec = svc.create_check(
                    staff_id=int(sid) if sid else None,
                    governor_id=int(gid) if gid else None,
                    volunteer_name=vname or None,
                    check_type=ctype, certificate_number=cert,
                    issue_date=issue, expiry_date=expiry,
                    update_service=1 if upd else 0,
                    barred_list_checked=1 if barred else 0)
                print(f"\n  DBS check #{rec['id']} recorded.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                cid = int(input("  Check ID to update: ").strip())
                rec = svc.get_check(cid)
                if not rec:
                    print("  Check not found.")
                    continue
                print("  (Press Enter to keep current value)")
                kwargs = {}
                status = input(f"  Status [{rec.get('status', '')}]: ").strip()
                if status:
                    kwargs["status"] = status
                cert = input(f"  Certificate # [{rec.get('certificate_number', '')}]: ").strip()
                if cert:
                    kwargs["certificate_number"] = cert
                expiry = input(f"  Expiry Date [{rec.get('expiry_date', '')}]: ").strip()
                if expiry:
                    kwargs["expiry_date"] = expiry
                notes = input(f"  Notes: ").strip()
                if notes:
                    kwargs["notes"] = notes
                if kwargs:
                    svc.update_check(cid, **kwargs)
                    print("  Check updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                cid = int(input("  Check ID to delete: ").strip())
                confirm = input(f"  Delete check #{cid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_check(cid)
                    print("  Check deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            days = input("  Expiring within days [90]: ").strip()
            days = int(days) if days else 90
            records = svc.get_expiring(days)
            for r in records:
                person = r.get("volunteer_name") or f"Staff #{r.get('staff_id', '')}"
                print(f"  [{r['id']}] {person} | Expiry: {r.get('expiry_date', '')} | "
                      f"Cert: {r.get('certificate_number', '')}")
            if not records:
                print(f"  No checks expiring within {days} days.")

        elif choice == "7":
            try:
                stats = svc.get_stats()
                print(f"\n  Total Checks:        {stats['total']}")
                print(f"  Valid:               {stats['valid']}")
                print(f"  Expired:             {stats['expired']}")
                print(f"  Pending:             {stats['pending']}")
                print(f"  On Update Service:   {stats['on_update_service']}")
                print(f"  Expiring (90 days):  {stats['expiring_90_days']}")
                by_type = stats.get("by_type", {})
                if by_type:
                    print("\n  By Type:")
                    for k, v in by_type.items():
                        print(f"    {k}: {v}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
