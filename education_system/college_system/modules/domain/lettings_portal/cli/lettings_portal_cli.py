"""Lettings Portal & Invoicing CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.lettings_portal.services.lettings_portal_service import LettingsPortalService
from education_system.college_system.infrastructure.auth.core import UserAuth


def _list_hirers(svc):
    """List hirers."""
    print_header("List Hirers")
    try:
        show_all = input("  Include inactive? (y/n, default=n): ").strip().lower() == "y"
        atype = input("  Account type filter (Enter for all): ").strip() or None
        hirers = svc.list_hirers(account_type=atype, active_only=not show_all)
        if not hirers:
            print("\n  No hirers found.")
        else:
            print(f"\n  {'ID':<5} {'Organisation':<22} {'Contact':<15} {'Email':<22} "
                  f"{'Type':<12} {'DBS':<5} {'Ins':<5} {'Active':<7}")
            print("  " + "-" * 98)
            for h in hirers:
                dbs = "Yes" if h.get('dbs_on_file') else "No"
                ins = "Yes" if h.get('insurance_verified') else "No"
                active = "Yes" if h.get('is_active') else "No"
                print(f"  {h['id']:<5} {(h.get('organisation_name') or '')[:22]:<22} "
                      f"{(h.get('contact_name') or '')[:15]:<15} "
                      f"{(h.get('contact_email') or '')[:22]:<22} "
                      f"{(h.get('account_type') or '-'):<12} "
                      f"{dbs:<5} {ins:<5} {active:<7}")
            print(f"\n  Total: {len(hirers)} hirer(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _register_hirer(svc):
    """Register a new hirer."""
    print_header("Register Hirer")
    try:
        org = input("  Organisation name: ").strip()
        if not org:
            print("\n  Error: Organisation name is required.")
            return
        contact = input("  Contact name: ").strip()
        email = input("  Contact email: ").strip()
        phone = input("  Contact phone: ").strip()
        atype = input("  Account type (regular/occasional/community/commercial, default=occasional): ").strip() or "occasional"
        result = svc.register_hirer(org, contact, email, phone, account_type=atype)
        hid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Hirer #{hid} registered.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_hirer(svc):
    """Update hirer details."""
    print_header("Update Hirer")
    try:
        hid = int(input("  Hirer ID: ").strip())
        updates = {}
        for field, prompt in [
            ("organisation_name", "  New organisation (Enter to keep): "),
            ("contact_name", "  New contact (Enter to keep): "),
            ("contact_email", "  New email (Enter to keep): "),
            ("contact_phone", "  New phone (Enter to keep): "),
            ("account_type", "  New account type (Enter to keep): "),
            ("discount_rate", "  Discount rate % (Enter to keep): "),
        ]:
            val = input(prompt).strip()
            if val:
                if field == "discount_rate":
                    val = float(val)
                updates[field] = val
        dbs = input("  DBS on file? (y/n/Enter to keep): ").strip().lower()
        if dbs in ("y", "n"):
            updates["dbs_on_file"] = 1 if dbs == "y" else 0
        ins = input("  Insurance verified? (y/n/Enter to keep): ").strip().lower()
        if ins in ("y", "n"):
            updates["insurance_verified"] = 1 if ins == "y" else 0
        if updates:
            svc.update_hirer(hid, **updates)
            print("\n  Hirer updated.")
        else:
            print("\n  No changes made.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_facilities(svc):
    """List lettable facilities."""
    print_header("List Facilities")
    try:
        ftype = input("  Facility type filter (Enter for all): ").strip() or None
        facilities = svc.list_facilities(facility_type=ftype)
        if not facilities:
            print("\n  No facilities found.")
        else:
            print(f"\n  {'ID':<5} {'Name':<20} {'Type':<15} {'Cap':>5} "
                  f"{'Hourly':>8} {'Half-Day':>9} {'Full-Day':>9} {'Community':>10}")
            print("  " + "-" * 86)
            for f in facilities:
                print(f"  {f['id']:<5} {(f.get('facility_name') or '')[:20]:<20} "
                      f"{(f.get('facility_type') or '-'):<15} "
                      f"{f.get('capacity', 0):>5} "
                      f"{f.get('hourly_rate', 0):>8.2f} "
                      f"{f.get('half_day_rate', 0):>9.2f} "
                      f"{f.get('full_day_rate', 0):>9.2f} "
                      f"{f.get('community_rate', 0):>10.2f}")
            print(f"\n  Total: {len(facilities)} facility/facilities")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_facility(svc):
    """Add a lettable facility."""
    print_header("Add Facility")
    try:
        name = input("  Facility name: ").strip()
        if not name:
            print("\n  Error: Facility name is required.")
            return
        ftype = input("  Type (hall/sports_hall/classroom/field/studio/meeting_room): ").strip()
        cap = int(input("  Capacity: ").strip())
        hourly = float(input("  Hourly rate: ").strip())
        half_day = input("  Half-day rate (default=0): ").strip()
        half_day = float(half_day) if half_day else 0
        full_day = input("  Full-day rate (default=0): ").strip()
        full_day = float(full_day) if full_day else 0
        community = input("  Community rate (default=0): ").strip()
        community = float(community) if community else 0
        result = svc.add_facility(name, ftype, cap, hourly,
                                  half_day_rate=half_day, full_day_rate=full_day,
                                  community_rate=community)
        fid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Facility #{fid} added.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_facility(svc):
    """Update facility details."""
    print_header("Update Facility")
    try:
        fid = int(input("  Facility ID: ").strip())
        updates = {}
        for field, prompt in [
            ("facility_name", "  New name (Enter to keep): "),
            ("facility_type", "  New type (Enter to keep): "),
            ("capacity", "  New capacity (Enter to keep): "),
            ("hourly_rate", "  New hourly rate (Enter to keep): "),
            ("half_day_rate", "  New half-day rate (Enter to keep): "),
            ("full_day_rate", "  New full-day rate (Enter to keep): "),
            ("community_rate", "  New community rate (Enter to keep): "),
            ("available_days", "  Available days (Enter to keep): "),
            ("available_from", "  Available from time (Enter to keep): "),
            ("available_until", "  Available until time (Enter to keep): "),
        ]:
            val = input(prompt).strip()
            if val:
                if field in ("capacity",):
                    val = int(val)
                elif field in ("hourly_rate", "half_day_rate", "full_day_rate", "community_rate"):
                    val = float(val)
                updates[field] = val
        if updates:
            svc.update_facility(fid, **updates)
            print("\n  Facility updated.")
        else:
            print("\n  No changes made.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _check_availability(svc):
    """Check facility availability."""
    print_header("Check Availability")
    try:
        fid = int(input("  Facility ID: ").strip())
        date = input("  Date (YYYY-MM-DD): ").strip()
        start = input("  Start time (HH:MM): ").strip()
        end = input("  End time (HH:MM): ").strip()
        available = svc.check_availability(fid, date, start, end)
        if available:
            print("\n  Facility is AVAILABLE for the requested slot.")
        else:
            print("\n  Facility is NOT AVAILABLE for the requested slot.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _block_availability(svc):
    """Block a facility time slot."""
    print_header("Block Availability")
    try:
        fid = int(input("  Facility ID: ").strip())
        date = input("  Date (YYYY-MM-DD): ").strip()
        start = input("  Start time (HH:MM): ").strip()
        end = input("  End time (HH:MM): ").strip()
        reason = input("  Reason: ").strip()
        result = svc.block_availability(fid, date, start, end, reason)
        bid = result if isinstance(result, int) else result
        print(f"\n  Availability blocked (#{bid}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_booking(svc):
    """Create a booking with invoice."""
    print_header("Create Booking with Invoice")
    try:
        hid = int(input("  Hirer ID: ").strip())
        fid = int(input("  Facility ID: ").strip())
        date = input("  Booking date (YYYY-MM-DD): ").strip()
        start = input("  Start time (HH:MM): ").strip()
        end = input("  End time (HH:MM): ").strip()
        purpose = input("  Purpose: ").strip()
        attendees = input("  Number of attendees (default=0): ").strip()
        attendees = int(attendees) if attendees else 0
        if not date or not start or not end:
            print("\n  Error: Date, start time, and end time are required.")
            return
        result = svc.create_booking_with_invoice(hid, fid, date, start, end,
                                                 purpose, attendee_count=attendees)
        if isinstance(result, dict):
            print(f"\n  Booking created successfully.")
            print(f"  Booking ID:     {result.get('booking_id', '-')}")
            print(f"  Invoice ID:     {result.get('invoice_id', '-')}")
            print(f"  Invoice Number: {result.get('invoice_number', '-')}")
            print(f"  Subtotal:       {result.get('subtotal', 0):.2f}")
            print(f"  Discount:       {result.get('discount_amount', 0):.2f}")
            print(f"  VAT:            {result.get('vat_amount', 0):.2f}")
            print(f"  Total:          {result.get('total_amount', 0):.2f}")
        else:
            print("\n  Booking created with invoice.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _calculate_fee(svc):
    """Calculate a fee estimate."""
    print_header("Calculate Fee Estimate")
    try:
        fid = int(input("  Facility ID: ").strip())
        start = input("  Start time (HH:MM): ").strip()
        end = input("  End time (HH:MM): ").strip()
        atype = input("  Account type (occasional/community/regular/commercial, default=occasional): ").strip() or "occasional"
        fee = svc.calculate_fee(fid, start, end, account_type=atype)
        print(f"\n  Estimated fee: {fee:.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_invoices(svc):
    """List lettings invoices."""
    print_header("List Invoices")
    try:
        hid = input("  Hirer ID filter (Enter for all): ").strip()
        hid = int(hid) if hid else None
        status = input("  Status filter (draft/sent/paid, Enter for all): ").strip() or None
        invoices = svc.list_invoices(hirer_id=hid, status=status)
        if not invoices:
            print("\n  No invoices found.")
        else:
            print(f"\n  {'ID':<5} {'Invoice #':<22} {'Hirer':>6} {'Total':>10} "
                  f"{'Due':<12} {'Status':<8} {'Paid':>10}")
            print("  " + "-" * 78)
            for inv in invoices:
                print(f"  {inv['id']:<5} "
                      f"{(inv.get('invoice_number') or '-'):<22} "
                      f"{inv.get('hirer_id', ''):>6} "
                      f"{inv.get('total_amount', 0):>10.2f} "
                      f"{(inv.get('due_date') or '-'):<12} "
                      f"{(inv.get('status') or '-'):<8} "
                      f"{(inv.get('paid_amount') or 0):>10.2f}")
            print(f"\n  Total: {len(invoices)} invoice(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _record_payment(svc):
    """Record a payment against an invoice."""
    print_header("Record Payment")
    try:
        iid = int(input("  Invoice ID: ").strip())
        amount = float(input("  Payment amount: ").strip())
        pay_date = input("  Payment date (YYYY-MM-DD, Enter for today): ").strip() or None
        svc.record_payment(iid, amount, payment_date=pay_date)
        print("\n  Payment recorded.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _revenue_report(svc):
    """Revenue report for a date range."""
    print_header("Revenue Report")
    try:
        df = input("  Date from (YYYY-MM-DD): ").strip()
        dt = input("  Date to (YYYY-MM-DD): ").strip()
        if not df or not dt:
            print("\n  Error: Both dates are required.")
            return
        report = svc.get_revenue_report(df, dt)
        if not report:
            print("\n  No revenue data found for this period.")
        else:
            print(f"\n  {'Organisation':<25} {'Invoices':>9} {'Invoiced':>12} "
                  f"{'Paid':>12} {'Outstanding':>12}")
            print("  " + "-" * 74)
            total_inv = 0
            total_paid = 0
            for r in report:
                inv = r.get('total_invoiced', 0) or 0
                paid = r.get('total_paid', 0) or 0
                out = r.get('outstanding', 0) or 0
                total_inv += inv
                total_paid += paid
                print(f"  {(r.get('organisation_name') or '-')[:25]:<25} "
                      f"{r.get('num_invoices', 0):>9} "
                      f"{inv:>12.2f} {paid:>12.2f} {out:>12.2f}")
            print("  " + "-" * 74)
            print(f"  {'TOTAL':<25} {'':>9} {total_inv:>12.2f} "
                  f"{total_paid:>12.2f} {total_inv - total_paid:>12.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _utilisation_report(svc):
    """Facility utilisation report."""
    print_header("Utilisation Report")
    try:
        df = input("  Date from (YYYY-MM-DD): ").strip()
        dt = input("  Date to (YYYY-MM-DD): ").strip()
        if not df or not dt:
            print("\n  Error: Both dates are required.")
            return
        report = svc.get_utilisation_report(df, dt)
        if not report:
            print("\n  No utilisation data found for this period.")
        else:
            print(f"\n  {'Facility':<22} {'Type':<15} {'Bookings':>9} {'Hours':>8}")
            print("  " + "-" * 58)
            for r in report:
                print(f"  {(r.get('facility_name') or '-')[:22]:<22} "
                      f"{(r.get('facility_type') or '-'):<15} "
                      f"{r.get('num_bookings', 0):>9} "
                      f"{r.get('total_hours', 0):>8.1f}")
            print(f"\n  Total: {len(report)} facility/facilities")
    except Exception as e:
        print(f"\n  Error: {e}")


def _hirer_statement(svc):
    """Hirer statement."""
    print_header("Hirer Statement")
    try:
        hid = int(input("  Hirer ID: ").strip())
        statement = svc.get_hirer_statement(hid)
        hirer = statement.get('hirer', {})
        print(f"\n  Organisation: {hirer.get('organisation_name', '-')}")
        print(f"  Contact:      {hirer.get('contact_name', '-')}")
        print(f"  Email:        {hirer.get('contact_email', '-')}")
        print(f"  Account Type: {hirer.get('account_type', '-')}")

        invoices = statement.get('invoices', [])
        if invoices:
            print(f"\n  {'Invoice #':<22} {'Date':<12} {'Total':>10} "
                  f"{'Paid':>10} {'Status':<8}")
            print("  " + "-" * 66)
            for inv in invoices:
                print(f"  {(inv.get('invoice_number') or '-'):<22} "
                      f"{(inv.get('invoice_date') or '-'):<12} "
                      f"{(inv.get('total_amount') or 0):>10.2f} "
                      f"{(inv.get('paid_amount') or 0):>10.2f} "
                      f"{(inv.get('status') or '-'):<8}")
        else:
            print("\n  No invoices found.")

        print(f"\n  Total Invoiced: {statement.get('total_invoiced', 0):.2f}")
        print(f"  Total Paid:     {statement.get('total_paid', 0):.2f}")
        print(f"  Balance Due:    {statement.get('balance', 0):.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def lettings_portal_menu(auth: UserAuth):
    """Lettings Portal & Invoicing management menu."""
    svc = LettingsPortalService(auth._db_path)

    while True:
        print_header("Lettings Portal & Invoicing")
        options = [
            ("1", "List Hirers"),
            ("2", "Register Hirer"),
            ("3", "Update Hirer"),
            ("4", "List Facilities"),
            ("5", "Add Facility"),
            ("6", "Update Facility"),
            ("7", "Check Availability"),
            ("8", "Block Availability"),
            ("9", "Create Booking with Invoice"),
            ("10", "Calculate Fee Estimate"),
            ("11", "List Invoices"),
            ("12", "Record Payment"),
            ("13", "Revenue Report"),
            ("14", "Utilisation Report"),
            ("15", "Hirer Statement"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_hirers(svc)
        elif choice == "2":
            _register_hirer(svc)
        elif choice == "3":
            _update_hirer(svc)
        elif choice == "4":
            _list_facilities(svc)
        elif choice == "5":
            _add_facility(svc)
        elif choice == "6":
            _update_facility(svc)
        elif choice == "7":
            _check_availability(svc)
        elif choice == "8":
            _block_availability(svc)
        elif choice == "9":
            _create_booking(svc)
        elif choice == "10":
            _calculate_fee(svc)
        elif choice == "11":
            _list_invoices(svc)
        elif choice == "12":
            _record_payment(svc)
        elif choice == "13":
            _revenue_report(svc)
        elif choice == "14":
            _utilisation_report(svc)
        elif choice == "15":
            _hirer_statement(svc)
        else:
            print("\n  Invalid option.")
