"""Expense Claims CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.expense_claims.services.expense_claims_service import ExpenseClaimService
from education_system.college_system.infrastructure.auth.core import UserAuth


def expense_claims_menu(auth: UserAuth):
    """Expense Claims management menu."""
    svc = ExpenseClaimService(auth._db_path)

    while True:
        print_header("Expense Claims")
        options = [
            ("1", "List Claims"),
            ("2", "View Claim"),
            ("3", "New Claim"),
            ("4", "Update Claim"),
            ("5", "Approve Claim"),
            ("6", "Reject Claim"),
            ("7", "Mark Paid"),
            ("8", "Delete Claim"),
            ("9", "Pending Approvals"),
            ("10", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()

        if choice == "0":
            break

        elif choice == "1":
            # List Claims
            claimant_str = input("  Claimant ID (or Enter for all): ").strip()
            category = input("  Category (travel/subsistence/equipment/stationery/training/other or Enter for all): ").strip() or None
            status = input("  Status (submitted/approved/rejected/paid or Enter for all): ").strip() or None
            search = input("  Search (or Enter to skip): ").strip() or None
            try:
                claims = svc.list_claims(
                    claimant_id=int(claimant_str) if claimant_str else None,
                    category=category,
                    status=status,
                    search=search,
                )
                if not claims:
                    print("\n  No claims found.")
                for c in claims:
                    name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                    print(f"  [{c['id']}] {name or 'Staff #' + str(c.get('claimant_id', ''))} | "
                          f"{c.get('claim_date', '')} | {c.get('category', '')} | "
                          f"{c.get('amount', 0):.2f} | [{c.get('status', '')}]")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "2":
            # View Claim
            try:
                cid = int(input("  Claim ID: ").strip())
                c = svc.get_claim(cid)
                if not c:
                    print("\n  Claim not found.")
                    continue
                name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                print(f"\n  ID:            {c['id']}")
                print(f"  Claimant:      {name or '#' + str(c.get('claimant_id', ''))}")
                print(f"  Claim Date:    {c.get('claim_date', '')}")
                print(f"  Description:   {c.get('description', '')}")
                print(f"  Category:      {c.get('category', '')}")
                print(f"  Amount:        {c.get('amount', 0):.2f}")
                print(f"  Mileage:       {c.get('mileage', '') or ''}")
                print(f"  Mileage Rate:  {c.get('mileage_rate', '') or ''}")
                print(f"  Receipt:       {c.get('receipt_path', '') or ''}")
                print(f"  Status:        {c.get('status', '')}")
                print(f"  Approved By:   {c.get('approved_by', '') or ''}")
                print(f"  Approved Date: {c.get('approved_date', '') or ''}")
                print(f"  Paid:          {'Yes' if c.get('paid') else 'No'}")
                print(f"  Paid Date:     {c.get('paid_date', '') or ''}")
                print(f"  Notes:         {c.get('notes', '') or ''}")
                print(f"  Created:       {c.get('created_at', '')}")
                print(f"  Updated:       {c.get('updated_at', '')}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "3":
            # New Claim
            try:
                claimant_id = int(input("  Claimant ID: ").strip())
                description = input("  Description: ").strip()
                if not description:
                    print("\n  Description is required.")
                    continue
                amount = float(input("  Amount: ").strip())
                category = input("  Category (travel/subsistence/equipment/stationery/training/other) [travel]: ").strip() or "travel"
                claim_date = input("  Claim Date (YYYY-MM-DD, or Enter for today): ").strip() or None
                mileage_str = input("  Mileage (or Enter to skip): ").strip()
                mileage = float(mileage_str) if mileage_str else None
                rate_str = input("  Mileage Rate [0.45]: ").strip()
                mileage_rate = float(rate_str) if rate_str else None
                receipt = input("  Receipt Path (or Enter to skip): ").strip() or None
                notes = input("  Notes: ").strip() or None

                kwargs = {"category": category}
                if claim_date:
                    kwargs["claim_date"] = claim_date
                if mileage is not None:
                    kwargs["mileage"] = mileage
                if mileage_rate is not None:
                    kwargs["mileage_rate"] = mileage_rate
                if receipt:
                    kwargs["receipt_path"] = receipt
                if notes:
                    kwargs["notes"] = notes

                c = svc.create_claim(claimant_id, description, amount, **kwargs)
                print(f"\n  Claim #{c['id']} created.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            # Update Claim
            try:
                cid = int(input("  Claim ID: ").strip())
                print("  (Press Enter to skip a field)")
                description = input("  Description: ").strip() or None
                amount_str = input("  Amount: ").strip()
                category = input("  Category: ").strip() or None
                claim_date = input("  Claim Date: ").strip() or None
                mileage_str = input("  Mileage: ").strip()
                rate_str = input("  Mileage Rate: ").strip()
                receipt = input("  Receipt Path: ").strip() or None
                notes = input("  Notes: ").strip() or None

                kwargs = {}
                if description:
                    kwargs["description"] = description
                if amount_str:
                    kwargs["amount"] = float(amount_str)
                if category:
                    kwargs["category"] = category
                if claim_date:
                    kwargs["claim_date"] = claim_date
                if mileage_str:
                    kwargs["mileage"] = float(mileage_str)
                if rate_str:
                    kwargs["mileage_rate"] = float(rate_str)
                if receipt:
                    kwargs["receipt_path"] = receipt
                if notes:
                    kwargs["notes"] = notes

                if not kwargs:
                    print("\n  No changes specified.")
                    continue

                svc.update_claim(cid, **kwargs)
                print("  Claim updated.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            # Approve Claim
            try:
                cid = int(input("  Claim ID: ").strip())
                approved_by = int(input("  Approver ID: ").strip())
                svc.approve_claim(cid, approved_by)
                print("  Claim approved.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            # Reject Claim
            try:
                cid = int(input("  Claim ID: ").strip())
                notes = input("  Rejection Reason: ").strip() or None
                svc.reject_claim(cid, notes=notes)
                print("  Claim rejected.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            # Mark Paid
            try:
                cid = int(input("  Claim ID: ").strip())
                confirm = input("  Confirm mark as paid? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.mark_paid(cid)
                    print("  Claim marked as paid.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            # Delete Claim
            try:
                cid = int(input("  Claim ID: ").strip())
                confirm = input("  Confirm delete? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_claim(cid)
                    print("  Claim deleted.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            # Pending Approvals
            try:
                claims = svc.list_claims(status="submitted")
                if not claims:
                    print("\n  No pending claims.")
                else:
                    print(f"\n  {len(claims)} pending claim(s):")
                    for c in claims:
                        name = f"{c.get('first_name', '')} {c.get('last_name', '')}".strip()
                        print(f"  [{c['id']}] {name or 'Staff #' + str(c.get('claimant_id', ''))} | "
                              f"{c.get('claim_date', '')} | {c.get('category', '')} | "
                              f"{c.get('description', '')} | {c.get('amount', 0):.2f}")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            # Statistics
            try:
                stats = svc.get_stats()
                print(f"\n  Total Claims:       {stats.get('total_claims', 0)}")
                print(f"  Total Amount:       {stats.get('total_amount', 0):.2f}")
                print(f"  Total Paid:         {stats.get('total_paid', 0):.2f}")
                print(f"  Total Pending:      {stats.get('total_pending', 0):.2f}")
                print(f"  Mileage Claims:     {stats.get('total_mileage_claims', 0)}")

                by_status = stats.get("by_status", {})
                if by_status:
                    print("\n  Breakdown by Status:")
                    print(f"    {'Status':<15} {'Count':>6}")
                    print(f"    {'-'*15} {'-'*6}")
                    for st, cnt in by_status.items():
                        print(f"    {st:<15} {cnt:>6}")

                by_category = stats.get("by_category", [])
                if by_category:
                    print("\n  Breakdown by Category:")
                    print(f"    {'Category':<15} {'Count':>6} {'Amount':>12}")
                    print(f"    {'-'*15} {'-'*6} {'-'*12}")
                    for bc in by_category:
                        print(f"    {bc.get('category', ''):<15} "
                              f"{bc.get('cnt', 0):>6} "
                              f"{bc.get('total_amount', 0):>12.2f}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
