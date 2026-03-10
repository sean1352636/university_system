"""Facility Lettings CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.lettings.services.lettings_service import LettingsService
from education_system.college_system.infrastructure.auth.core import UserAuth


def lettings_menu(auth: UserAuth):
    """Facility Lettings management menu."""
    svc = LettingsService(auth._db_path)

    while True:
        print_header("Facility Lettings")
        options = [
            ("1", "List Bookings"),
            ("2", "View Booking"),
            ("3", "New Booking"),
            ("4", "Update Booking"),
            ("5", "Confirm Booking"),
            ("6", "Cancel Booking"),
            ("7", "Delete Booking"),
            ("8", "List Contracts"),
            ("9", "New Contract"),
            ("10", "Update Contract"),
            ("11", "Sign Contract"),
            ("12", "Delete Contract"),
            ("13", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            facility = input("  Facility filter (or Enter for all): ").strip() or None
            status = input("  Status filter (pending/confirmed/cancelled or Enter): ").strip() or None
            payment = input("  Payment filter (unpaid/paid/invoiced or Enter): ").strip() or None
            search = input("  Search term (or Enter): ").strip() or None
            try:
                bookings = svc.list_bookings(facility=facility, status=status,
                                             payment_status=payment, search=search)
                if not bookings:
                    print("\n  No bookings found.")
                else:
                    print(f"\n  {'ID':<5} {'Hirer':<20} {'Facility':<15} {'Date':<12} "
                          f"{'Time':<13} {'Fee':>8} {'Payment':<10} {'Status':<10}")
                    print("  " + "-" * 95)
                    for b in bookings:
                        time_str = f"{b.get('start_time', '')}-{b.get('end_time', '')}"
                        fee = f"{b.get('fee', 0):.2f}"
                        print(f"  {b['id']:<5} {b.get('hirer_name', ''):<20} "
                              f"{b.get('facility', ''):<15} {b.get('booking_date', ''):<12} "
                              f"{time_str:<13} {fee:>8} {b.get('payment_status', ''):<10} "
                              f"{b.get('status', ''):<10}")
                    print(f"\n  Total: {len(bookings)} booking(s)")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "2":
            try:
                bid = int(input("  Booking ID: ").strip())
                b = svc.get_booking(bid)
                print()
                for key in ["id", "hirer_name", "organisation", "contact_email",
                            "contact_phone", "facility", "booking_date", "start_time",
                            "end_time", "recurrence", "purpose", "attendee_count",
                            "dbs_required", "dbs_verified", "insurance_verified",
                            "risk_assessment_done", "fee", "payment_status",
                            "invoice_number", "status", "notes", "created_at", "updated_at"]:
                    print(f"  {key:<22}: {b.get(key, '')}")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "3":
            try:
                hirer = input("  Hirer Name: ").strip()
                facility = input("  Facility: ").strip()
                bdate = input("  Date (YYYY-MM-DD): ").strip()
                stime = input("  Start Time (HH:MM): ").strip()
                etime = input("  End Time (HH:MM): ").strip()
                if not hirer or not facility or not bdate or not stime or not etime:
                    print("\n  Error: Hirer, facility, date and times are required.")
                    continue
                org = input("  Organisation (optional): ").strip() or None
                email = input("  Contact Email (optional): ").strip() or None
                phone = input("  Contact Phone (optional): ").strip() or None
                purpose = input("  Purpose (optional): ").strip() or None
                attendees = input("  Attendee Count (0): ").strip()
                attendees = int(attendees) if attendees else 0
                fee = input("  Fee (0.00): ").strip()
                fee = float(fee) if fee else 0.0
                recurrence = input("  Recurrence (one-off/weekly/fortnightly/monthly): ").strip() or "one-off"
                b = svc.create_booking(
                    hirer_name=hirer, facility=facility,
                    booking_date=bdate, start_time=stime, end_time=etime,
                    organisation=org, contact_email=email, contact_phone=phone,
                    purpose=purpose, attendee_count=attendees, fee=fee,
                    recurrence=recurrence,
                )
                print(f"\n  Booking #{b['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                bid = int(input("  Booking ID: ").strip())
                b = svc.get_booking(bid)
                print(f"  Current hirer: {b.get('hirer_name', '')}")
                updates = {}
                for field, prompt in [
                    ("hirer_name", "  New Hirer Name (Enter to keep): "),
                    ("facility", "  New Facility (Enter to keep): "),
                    ("booking_date", "  New Date (Enter to keep): "),
                    ("start_time", "  New Start Time (Enter to keep): "),
                    ("end_time", "  New End Time (Enter to keep): "),
                    ("fee", "  New Fee (Enter to keep): "),
                    ("payment_status", "  Payment Status (unpaid/paid/invoiced/waived, Enter to keep): "),
                    ("notes", "  Notes (Enter to keep): "),
                ]:
                    val = input(prompt).strip()
                    if val:
                        if field == "fee":
                            val = float(val)
                        updates[field] = val
                if updates:
                    svc.update_booking(bid, **updates)
                    print("\n  Booking updated.")
                else:
                    print("\n  No changes made.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                bid = int(input("  Booking ID to confirm: ").strip())
                svc.confirm_booking(bid)
                print("\n  Booking confirmed.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            try:
                bid = int(input("  Booking ID to cancel: ").strip())
                svc.cancel_booking(bid)
                print("\n  Booking cancelled.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            try:
                bid = int(input("  Booking ID to delete: ").strip())
                confirm = input("  Are you sure? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_booking(bid)
                    print("\n  Booking deleted.")
                else:
                    print("\n  Cancelled.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            status = input("  Status filter (draft/signed/expired/cancelled or Enter): ").strip() or None
            search = input("  Search term (or Enter): ").strip() or None
            try:
                contracts = svc.list_contracts(status=status, search=search)
                if not contracts:
                    print("\n  No contracts found.")
                else:
                    print(f"\n  {'ID':<5} {'Hirer':<20} {'Organisation':<18} "
                          f"{'Start':<12} {'End':<12} {'Fee':>10} {'Signed':<12} {'Status':<10}")
                    print("  " + "-" * 100)
                    for c in contracts:
                        fee = f"{c.get('agreed_fee', 0):.2f}"
                        print(f"  {c['id']:<5} {c.get('hirer_name', ''):<20} "
                              f"{(c.get('organisation', '') or ''):<18} "
                              f"{(c.get('contract_start', '') or ''):<12} "
                              f"{(c.get('contract_end', '') or ''):<12} "
                              f"{fee:>10} {(c.get('signed_date', '') or ''):<12} "
                              f"{c.get('status', ''):<10}")
                    print(f"\n  Total: {len(contracts)} contract(s)")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                hirer = input("  Hirer Name: ").strip()
                if not hirer:
                    print("\n  Error: Hirer name is required.")
                    continue
                org = input("  Organisation (optional): ").strip() or None
                cstart = input("  Contract Start (YYYY-MM-DD): ").strip() or None
                cend = input("  Contract End (YYYY-MM-DD): ").strip() or None
                fee = input("  Agreed Fee (0.00): ").strip()
                fee = float(fee) if fee else 0.0
                terms = input("  Terms (optional): ").strip() or None
                c = svc.create_contract(
                    hirer_name=hirer, organisation=org,
                    contract_start=cstart, contract_end=cend,
                    agreed_fee=fee, terms=terms,
                )
                print(f"\n  Contract #{c['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            try:
                cid = int(input("  Contract ID: ").strip())
                svc.get_contract(cid)
                updates = {}
                for field, prompt in [
                    ("hirer_name", "  New Hirer Name (Enter to keep): "),
                    ("organisation", "  New Organisation (Enter to keep): "),
                    ("contract_start", "  New Start Date (Enter to keep): "),
                    ("contract_end", "  New End Date (Enter to keep): "),
                    ("agreed_fee", "  New Fee (Enter to keep): "),
                    ("terms", "  New Terms (Enter to keep): "),
                    ("status", "  Status (draft/signed/expired/cancelled, Enter to keep): "),
                ]:
                    val = input(prompt).strip()
                    if val:
                        if field == "agreed_fee":
                            val = float(val)
                        updates[field] = val
                if updates:
                    svc.update_contract(cid, **updates)
                    print("\n  Contract updated.")
                else:
                    print("\n  No changes made.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                cid = int(input("  Contract ID to sign: ").strip())
                signed = input("  Signed Date (YYYY-MM-DD, Enter for today): ").strip()
                if not signed:
                    from datetime import date
                    signed = str(date.today())
                svc.sign_contract(cid, signed_date=signed)
                print("\n  Contract signed.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "12":
            try:
                cid = int(input("  Contract ID to delete: ").strip())
                confirm = input("  Are you sure? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_contract(cid)
                    print("\n  Contract deleted.")
                else:
                    print("\n  Cancelled.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "13":
            try:
                stats = svc.get_stats()
                print("\n  " + "=" * 45)
                print("    FACILITY LETTINGS STATISTICS")
                print("  " + "=" * 45)
                print(f"\n  Total Bookings:       {stats.get('total_bookings', 0)}")
                print("\n  Bookings by Status:")
                for st, cnt in stats.get("by_status", {}).items():
                    print(f"    {st:<18} {cnt}")
                print(f"\n  Total Revenue:        {stats.get('total_revenue', 0):,.2f}")
                print(f"  Pending Payments:     {stats.get('pending_payments', 0)}")
                print(f"\n  Total Contracts:      {stats.get('total_contracts', 0)}")
                print(f"  Active Contracts:     {stats.get('active_contracts', 0)}")
                print(f"  Total Contract Value: {stats.get('total_contract_value', 0):,.2f}")
                print("\n  " + "=" * 45)
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
