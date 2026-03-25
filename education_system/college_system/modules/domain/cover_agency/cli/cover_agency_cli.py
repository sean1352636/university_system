"""Supply/Cover Agency Integration CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.cover_agency.services.cover_agency_service import CoverAgencyService
from education_system.college_system.infrastructure.auth.core import UserAuth


def _list_agencies(svc):
    """List all agencies."""
    print_header("List Agencies")
    try:
        show_all = input("  Include inactive? (y/n, default=n): ").strip().lower() == "y"
        agencies = svc.list_agencies(active_only=not show_all)
        if not agencies:
            print("\n  No agencies found.")
        else:
            print(f"\n  {'ID':<5} {'Name':<20} {'Contact':<15} {'Email':<22} "
                  f"{'Phone':<14} {'Rate':>7} {'Rank':>5} {'Active':<7}")
            print("  " + "-" * 100)
            for a in agencies:
                active = "Yes" if a.get('is_active') else "No"
                print(f"  {a['id']:<5} {(a.get('agency_name') or '')[:20]:<20} "
                      f"{(a.get('contact_name') or '')[:15]:<15} "
                      f"{(a.get('contact_email') or '')[:22]:<22} "
                      f"{(a.get('contact_phone') or '')[:14]:<14} "
                      f"{a.get('day_rate', 0):>7.2f} "
                      f"{a.get('preferred_rank', 0):>5} "
                      f"{active:<7}")
            print(f"\n  Total: {len(agencies)} agency/agencies")
    except Exception as e:
        print(f"\n  Error: {e}")


def _add_agency(svc):
    """Add a new agency."""
    print_header("Add Agency")
    try:
        name = input("  Agency name: ").strip()
        if not name:
            print("\n  Error: Agency name is required.")
            return
        contact = input("  Contact name: ").strip()
        email = input("  Email: ").strip()
        phone = input("  Phone: ").strip()
        specialisms = input("  Specialisms (blank=none): ").strip() or None
        rate = float(input("  Day rate: ").strip())
        rank = input("  Preferred rank (0=highest, default=0): ").strip()
        rank = int(rank) if rank else 0
        contract_start = input("  Contract start (YYYY-MM-DD, blank=none): ").strip() or None
        contract_end = input("  Contract end (YYYY-MM-DD, blank=none): ").strip() or None
        result = svc.add_agency(name, contact, email, phone, rate, preferred_rank=rank)
        aid = result if isinstance(result, int) else result.get('id', result)
        # Update specialisms and contract dates if provided
        updates = {}
        if specialisms:
            updates["specialisms"] = specialisms
        if contract_start:
            updates["contract_start"] = contract_start
        if contract_end:
            updates["contract_end"] = contract_end
        if updates:
            svc.update_agency(aid, **updates)
        print(f"\n  Agency #{aid} added.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_agency(svc):
    """Update agency details."""
    print_header("Update Agency")
    try:
        aid = int(input("  Agency ID: ").strip())
        updates = {}
        for field, prompt in [
            ("agency_name", "  New name (Enter to keep): "),
            ("contact_name", "  New contact (Enter to keep): "),
            ("contact_email", "  New email (Enter to keep): "),
            ("contact_phone", "  New phone (Enter to keep): "),
            ("day_rate", "  New day rate (Enter to keep): "),
            ("preferred_rank", "  New rank (Enter to keep): "),
            ("specialisms", "  New specialisms (Enter to keep): "),
        ]:
            val = input(prompt).strip()
            if val:
                if field == "day_rate":
                    val = float(val)
                elif field == "preferred_rank":
                    val = int(val)
                updates[field] = val
        if updates:
            svc.update_agency(aid, **updates)
            print("\n  Agency updated.")
        else:
            print("\n  No changes made.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_request(svc):
    """Create a cover request."""
    print_header("Create Cover Request")
    try:
        aid = int(input("  Agency ID: ").strip())
        date = input("  Date required (YYYY-MM-DD): ").strip()
        subj = input("  Subject area: ").strip()
        start = input("  Start time (HH:MM): ").strip()
        end = input("  End time (HH:MM): ").strip()
        if not date or not subj or not start or not end:
            print("\n  Error: Date, subject, start and end time are required.")
            return
        yg = input("  Year group (blank=none): ").strip() or None
        reqs = input("  Special requirements (blank=none): ").strip() or None
        result = svc.create_cover_request(aid, date, subj, start, end,
                                          year_group=yg, special_requirements=reqs)
        rid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Cover request #{rid} created.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _auto_request(svc):
    """Auto-request cover from best-ranked agency."""
    print_header("Auto-Request Cover")
    try:
        caid = input("  Cover arrangement ID: ").strip()
        caid = int(caid) if caid else None
        subj = input("  Subject area: ").strip()
        if not subj:
            print("\n  Error: Subject area is required.")
            return
        result = svc.auto_request_cover(caid, subj)
        rid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Auto cover request #{rid} created (best-ranked agency).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_requests(svc):
    """List cover requests."""
    print_header("List Cover Requests")
    try:
        aid = input("  Agency ID filter (Enter for all): ").strip()
        aid = int(aid) if aid else None
        status = input("  Status filter (Enter for all): ").strip() or None
        df = input("  Date from (YYYY-MM-DD, Enter for all): ").strip() or None
        dt = input("  Date to (YYYY-MM-DD, Enter for all): ").strip() or None
        requests = svc.list_requests(agency_id=aid, status=status,
                                     date_from=df, date_to=dt)
        if not requests:
            print("\n  No cover requests found.")
        else:
            print(f"\n  {'ID':<5} {'Agency':>7} {'Date':<12} {'Subject':<15} "
                  f"{'Status':<12} {'Teacher':<15} {'Response':<10}")
            print("  " + "-" * 82)
            for r in requests:
                print(f"  {r['id']:<5} {r.get('agency_id', ''):>7} "
                      f"{(r.get('date_required') or '-'):<12} "
                      f"{(r.get('subject_area') or '')[:15]:<15} "
                      f"{(r.get('status') or '-'):<12} "
                      f"{(r.get('teacher_name') or '-')[:15]:<15} "
                      f"{(r.get('agency_response') or '-'):<10}")
            print(f"\n  Total: {len(requests)} request(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_response(svc):
    """Update agency response to a request."""
    print_header("Update Request Response")
    try:
        rid = int(input("  Request ID: ").strip())
        resp = input("  Response (accepted/declined): ").strip()
        teacher = input("  Teacher name (blank=none): ").strip() or None
        rate = input("  Day rate (blank=none): ").strip()
        rate = float(rate) if rate else None
        svc.update_request_response(rid, resp, teacher_name=teacher, day_rate=rate)
        print("\n  Response updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _confirm_teacher(svc):
    """Confirm a supply teacher for a request."""
    print_header("Confirm Teacher")
    try:
        rid = int(input("  Request ID: ").strip())
        teacher = input("  Teacher name: ").strip()
        if not teacher:
            print("\n  Error: Teacher name is required.")
            return
        svc.confirm_teacher(rid, teacher)
        print("\n  Teacher confirmed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _cancel_request(svc):
    """Cancel a cover request."""
    print_header("Cancel Cover Request")
    try:
        rid = int(input("  Request ID: ").strip())
        confirm = input("  Are you sure? (y/n): ").strip().lower()
        if confirm == "y":
            svc.cancel_request(rid)
            print("\n  Request cancelled.")
        else:
            print("\n  Cancelled.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_invoice(svc):
    """Create an agency invoice."""
    print_header("Create Agency Invoice")
    try:
        aid = int(input("  Agency ID: ").strip())
        inv_num = input("  Invoice number: ").strip()
        inv_date = input("  Invoice date (YYYY-MM-DD): ").strip()
        period_start = input("  Period start (YYYY-MM-DD): ").strip()
        period_end = input("  Period end (YYYY-MM-DD): ").strip()
        days = int(input("  Days covered: ").strip())
        total = float(input("  Total amount: ").strip())
        result = svc.create_invoice(aid, inv_num, inv_date, period_start,
                                    period_end, days, total)
        iid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Invoice #{iid} created.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_invoices(svc):
    """List agency invoices."""
    print_header("List Agency Invoices")
    try:
        aid = input("  Agency ID filter (Enter for all): ").strip()
        aid = int(aid) if aid else None
        status = input("  Status filter (Enter for all): ").strip() or None
        invoices = svc.list_invoices(agency_id=aid, status=status)
        if not invoices:
            print("\n  No invoices found.")
        else:
            print(f"\n  {'ID':<5} {'Agency':>7} {'Invoice #':<18} {'Date':<12} "
                  f"{'Days':>5} {'Amount':>10} {'Status':<10}")
            print("  " + "-" * 72)
            for inv in invoices:
                print(f"  {inv['id']:<5} {inv.get('agency_id', ''):>7} "
                      f"{(inv.get('invoice_number') or '-'):<18} "
                      f"{(inv.get('invoice_date') or '-'):<12} "
                      f"{inv.get('days_covered', 0):>5} "
                      f"{inv.get('total_amount', 0):>10.2f} "
                      f"{(inv.get('status') or '-'):<10}")
            print(f"\n  Total: {len(invoices)} invoice(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _approve_invoice(svc):
    """Approve an agency invoice."""
    print_header("Approve Invoice")
    try:
        iid = int(input("  Invoice ID: ").strip())
        approver = input("  Approved by: ").strip()
        if not approver:
            print("\n  Error: Approver name is required.")
            return
        svc.approve_invoice(iid, approver)
        print("\n  Invoice approved.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _agency_stats(svc):
    """Agency statistics."""
    print_header("Agency Statistics")
    try:
        aid = int(input("  Agency ID: ").strip())
        stats = svc.get_agency_stats(aid)
        print(f"\n  {'Metric':<25} {'Value':>12}")
        print("  " + "-" * 40)
        print(f"  {'Total Requests':<25} {stats.get('total_requests', 0):>12}")
        print(f"  {'Accepted':<25} {stats.get('accepted', 0):>12}")
        print(f"  {'Declined':<25} {stats.get('declined', 0):>12}")
        print(f"  {'Acceptance Rate':<25} {stats.get('acceptance_rate', 0):>11.1f}%")
        print(f"  {'Total Spend':<25} {stats.get('total_spend', 0):>12.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _spend_report(svc):
    """Cover spend report."""
    print_header("Cover Spend Report")
    try:
        df = input("  Date from (YYYY-MM-DD): ").strip()
        dt = input("  Date to (YYYY-MM-DD): ").strip()
        if not df or not dt:
            print("\n  Error: Both dates are required.")
            return
        report = svc.get_cover_spend_report(df, dt)
        if not report:
            print("\n  No spend data found for this period.")
        else:
            print(f"\n  {'Agency':<25} {'Requests':>9} {'Total Spend':>12}")
            print("  " + "-" * 50)
            total_spend = 0
            for r in report:
                spend = r.get('total_spend', 0) or 0
                total_spend += spend
                print(f"  {(r.get('agency_name') or '-')[:25]:<25} "
                      f"{r.get('requests', 0):>9} "
                      f"{spend:>12.2f}")
            print("  " + "-" * 50)
            print(f"  {'TOTAL':<25} {'':>9} {total_spend:>12.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def cover_agency_menu(auth: UserAuth):
    """Supply/Cover Agency Integration management menu."""
    svc = CoverAgencyService(auth._db_path)

    while True:
        print_header("Supply/Cover Agency Integration")
        options = [
            ("1", "List Agencies"),
            ("2", "Add Agency"),
            ("3", "Update Agency"),
            ("4", "Create Cover Request"),
            ("5", "Auto-Request Cover"),
            ("6", "List Cover Requests"),
            ("7", "Update Request Response"),
            ("8", "Confirm Teacher"),
            ("9", "Cancel Request"),
            ("10", "Create Invoice"),
            ("11", "List Invoices"),
            ("12", "Approve Invoice"),
            ("13", "Agency Statistics"),
            ("14", "Cover Spend Report"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_agencies(svc)
        elif choice == "2":
            _add_agency(svc)
        elif choice == "3":
            _update_agency(svc)
        elif choice == "4":
            _create_request(svc)
        elif choice == "5":
            _auto_request(svc)
        elif choice == "6":
            _list_requests(svc)
        elif choice == "7":
            _update_response(svc)
        elif choice == "8":
            _confirm_teacher(svc)
        elif choice == "9":
            _cancel_request(svc)
        elif choice == "10":
            _create_invoice(svc)
        elif choice == "11":
            _list_invoices(svc)
        elif choice == "12":
            _approve_invoice(svc)
        elif choice == "13":
            _agency_stats(svc)
        elif choice == "14":
            _spend_report(svc)
        else:
            print("\n  Invalid option.")
