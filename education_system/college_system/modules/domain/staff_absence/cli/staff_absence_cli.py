"""Staff Absence CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.staff_absence.services.staff_absence_service import StaffAbsenceService
from education_system.college_system.infrastructure.auth.core import UserAuth


def staff_absence_menu(auth: UserAuth):
    """Staff Absence management menu."""
    svc = StaffAbsenceService(auth._db_path)

    while True:
        print_header("Staff Absence")
        options = [
            ("1", "List Absences"),
            ("2", "View Absence"),
            ("3", "New Absence"),
            ("4", "Update Absence"),
            ("5", "Close Absence"),
            ("6", "Delete Absence"),
            ("7", "List Triggers"),
            ("8", "New Trigger"),
            ("9", "Update Trigger"),
            ("10", "Delete Trigger"),
            ("11", "Check Triggers (for staff)"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()

        if choice == "0":
            break

        elif choice == "1":
            # List Absences
            staff_id_str = input("  Staff ID (or Enter for all): ").strip()
            status = input("  Status (current/closed or Enter for all): ").strip() or None
            atype = input("  Type (sickness/personal/... or Enter for all): ").strip() or None
            search = input("  Search (or Enter to skip): ").strip() or None
            try:
                absences = svc.list_absences(
                    staff_id=int(staff_id_str) if staff_id_str else None,
                    absence_type=atype,
                    status=status,
                    search=search,
                )
                if not absences:
                    print("\n  No absences found.")
                for a in absences:
                    name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip()
                    print(f"  [{a['id']}] {name or 'Staff #' + str(a.get('staff_id', ''))} | "
                          f"{a.get('absence_type', '')} | {a.get('start_date', '')} - "
                          f"{a.get('end_date', '') or 'ongoing'} | "
                          f"{a.get('days_lost', 0)} days | [{a.get('status', '')}]")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "2":
            # View Absence
            try:
                aid = int(input("  Absence ID: ").strip())
                a = svc.get_absence(aid)
                if not a:
                    print("\n  Absence not found.")
                    continue
                name = f"{a.get('first_name', '')} {a.get('last_name', '')}".strip()
                print(f"\n  ID:            {a['id']}")
                print(f"  Staff:         {name or '#' + str(a.get('staff_id', ''))}")
                print(f"  Type:          {a.get('absence_type', '')}")
                print(f"  Start Date:    {a.get('start_date', '')}")
                print(f"  End Date:      {a.get('end_date', '') or 'ongoing'}")
                print(f"  Days Lost:     {a.get('days_lost', 0)}")
                print(f"  Reason:        {a.get('reason', '') or ''}")
                print(f"  Status:        {a.get('status', '')}")
                print(f"  Self Certified:  {'Yes' if a.get('self_certified') else 'No'}")
                print(f"  Fit Note:        {'Yes' if a.get('fit_note_received') else 'No'}")
                print(f"  Fit Note Expiry: {a.get('fit_note_expiry', '') or ''}")
                print(f"  RTW Done:        {'Yes' if a.get('return_to_work_done') else 'No'}")
                print(f"  RTW Date:        {a.get('rtw_date', '') or ''}")
                print(f"  RTW Notes:       {a.get('rtw_notes', '') or ''}")
                print(f"  OH Referral:     {'Yes' if a.get('occupational_health_referral') else 'No'}")
                print(f"  Trigger Reached: {'Yes' if a.get('trigger_point_reached') else 'No'}")
                print(f"  Notes:         {a.get('notes', '') or ''}")
                print(f"  Created:       {a.get('created_at', '')}")
                print(f"  Updated:       {a.get('updated_at', '')}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "3":
            # New Absence
            try:
                staff_id = int(input("  Staff ID: ").strip())
                start_date = input("  Start Date (YYYY-MM-DD): ").strip()
                if not start_date:
                    print("\n  Start date is required.")
                    continue
                atype = input("  Type (sickness/personal/compassionate/maternity/paternity/unauthorised/other) [sickness]: ").strip() or "sickness"
                end_date = input("  End Date (or Enter if ongoing): ").strip() or None
                days_str = input("  Days Lost [0]: ").strip()
                days_lost = float(days_str) if days_str else 0
                reason = input("  Reason: ").strip() or None
                self_cert = input("  Self Certified? (y/n) [n]: ").strip().lower() == "y"
                fit_note = input("  Fit Note Received? (y/n) [n]: ").strip().lower() == "y"
                notes = input("  Notes: ").strip() or None

                a = svc.create_absence(
                    staff_id, start_date,
                    absence_type=atype,
                    end_date=end_date,
                    days_lost=days_lost,
                    reason=reason,
                    self_certified=1 if self_cert else 0,
                    fit_note_received=1 if fit_note else 0,
                    notes=notes,
                )
                print(f"\n  Absence #{a['id']} created.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            # Update Absence
            try:
                aid = int(input("  Absence ID: ").strip())
                print("  (Press Enter to skip a field)")
                atype = input("  Type: ").strip() or None
                start = input("  Start Date: ").strip() or None
                end = input("  End Date: ").strip() or None
                days_str = input("  Days Lost: ").strip()
                reason = input("  Reason: ").strip() or None
                notes = input("  Notes: ").strip() or None

                kwargs = {}
                if atype:
                    kwargs["absence_type"] = atype
                if start:
                    kwargs["start_date"] = start
                if end:
                    kwargs["end_date"] = end
                if days_str:
                    kwargs["days_lost"] = float(days_str)
                if reason:
                    kwargs["reason"] = reason
                if notes:
                    kwargs["notes"] = notes

                if not kwargs:
                    print("\n  No changes specified.")
                    continue

                svc.update_absence(aid, **kwargs)
                print("  Absence updated.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            # Close Absence
            try:
                aid = int(input("  Absence ID: ").strip())
                end_date = input("  End Date (YYYY-MM-DD): ").strip()
                if not end_date:
                    print("\n  End date is required.")
                    continue
                days_lost = float(input("  Days Lost: ").strip())
                rtw_notes = input("  RTW Notes: ").strip() or None
                svc.close_absence(aid, end_date, days_lost, rtw_notes)
                print("  Absence closed.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            # Delete Absence
            try:
                aid = int(input("  Absence ID: ").strip())
                confirm = input("  Confirm delete? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_absence(aid)
                    print("  Absence deleted.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            # List Triggers
            try:
                status = input("  Status (active/inactive or Enter for all): ").strip() or None
                triggers = svc.list_triggers(status=status)
                if not triggers:
                    print("\n  No triggers found.")
                for t in triggers:
                    print(f"  [{t['id']}] {t.get('trigger_name', '')} | "
                          f"{t.get('trigger_type', '')} >= {t.get('threshold', '')} "
                          f"in {t.get('period_months', 12)} months | "
                          f"Action: {t.get('action_required', '') or 'N/A'} | "
                          f"[{t.get('status', '')}]")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            # New Trigger
            try:
                name = input("  Trigger Name: ").strip()
                if not name:
                    print("\n  Name is required.")
                    continue
                ttype = input("  Type (days/occasions) [days]: ").strip() or "days"
                threshold = int(input("  Threshold: ").strip())
                period_str = input("  Period in months [12]: ").strip()
                period = int(period_str) if period_str else 12
                action = input("  Action Required: ").strip() or None

                t = svc.create_trigger(
                    name, threshold,
                    trigger_type=ttype,
                    period_months=period,
                    action_required=action,
                )
                print(f"\n  Trigger #{t['id']} created.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            # Update Trigger
            try:
                tid = int(input("  Trigger ID: ").strip())
                print("  (Press Enter to skip a field)")
                name = input("  Trigger Name: ").strip() or None
                ttype = input("  Type (days/occasions): ").strip() or None
                thresh_str = input("  Threshold: ").strip()
                period_str = input("  Period (months): ").strip()
                action = input("  Action Required: ").strip() or None
                status = input("  Status (active/inactive): ").strip() or None

                kwargs = {}
                if name:
                    kwargs["trigger_name"] = name
                if ttype:
                    kwargs["trigger_type"] = ttype
                if thresh_str:
                    kwargs["threshold"] = int(thresh_str)
                if period_str:
                    kwargs["period_months"] = int(period_str)
                if action:
                    kwargs["action_required"] = action
                if status:
                    kwargs["status"] = status

                if not kwargs:
                    print("\n  No changes specified.")
                    continue

                svc.update_trigger(tid, **kwargs)
                print("  Trigger updated.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            # Delete Trigger
            try:
                tid = int(input("  Trigger ID: ").strip())
                confirm = input("  Confirm delete? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_trigger(tid)
                    print("  Trigger deleted.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            # Check Triggers for staff
            try:
                staff_id = int(input("  Staff ID: ").strip())
                breached = svc.check_triggers(staff_id)
                if not breached:
                    print("\n  No triggers breached for this staff member.")
                else:
                    print(f"\n  {len(breached)} trigger(s) breached:")
                    for t in breached:
                        print(f"    - {t.get('trigger_name', '')}: "
                              f"{t.get('trigger_type', '')} threshold {t.get('threshold', '')} "
                              f"(actual: {t.get('actual_value', '')}) in "
                              f"{t.get('period_months', 12)} months | "
                              f"Action: {t.get('action_required', '') or 'N/A'}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "12":
            # Statistics
            try:
                stats = svc.get_stats()
                print(f"\n  Total Absences:        {stats.get('total_absences', 0)}")
                print(f"  Current:               {stats.get('current', 0)}")
                print(f"  Closed:                {stats.get('closed', 0)}")
                print(f"  Total Days Lost:       {stats.get('total_days_lost', 0)}")
                print(f"  Staff Currently Absent: {stats.get('staff_on_absence', 0)}")
                print(f"  Active Triggers:       {stats.get('active_triggers', 0)}")
                by_type = stats.get("by_type", [])
                if by_type:
                    print("\n  Breakdown by Type:")
                    print(f"    {'Type':<20} {'Count':>6} {'Days':>10}")
                    print(f"    {'-'*20} {'-'*6} {'-'*10}")
                    for bt in by_type:
                        print(f"    {bt.get('absence_type', ''):<20} "
                              f"{bt.get('cnt', 0):>6} "
                              f"{bt.get('days', 0):>10.1f}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
