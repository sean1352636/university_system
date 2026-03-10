"""Disciplinary & Appeals CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.disciplinary.services.disciplinary_service import DisciplinaryService
from education_system.college_system.infrastructure.auth.core import UserAuth


def disciplinary_menu(auth: UserAuth):
    """Disciplinary & Appeals management menu."""
    svc = DisciplinaryService(auth._db_path)

    while True:
        print_header("Disciplinary & Appeals")
        options = [
            ("1", "List Cases"),
            ("2", "View Case"),
            ("3", "New Case"),
            ("4", "Update Case"),
            ("5", "Schedule Hearing"),
            ("6", "Record Outcome"),
            ("7", "Delete Case"),
            ("8", "List Evidence"),
            ("9", "Add Evidence"),
            ("10", "List Appeals"),
            ("11", "Lodge Appeal"),
            ("12", "Schedule Appeal Hearing"),
            ("13", "Record Appeal Outcome"),
            ("14", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            status = input("  Status filter (or Enter for all): ").strip() or None
            person_type = input("  Person type filter (student/staff or Enter for all): ").strip() or None
            records = svc.list_cases(status=status, person_type=person_type)
            for r in records:
                print(f"  [{r['id']}] Ref: {r.get('case_reference', '-')} | "
                      f"{r.get('person_type', '')} #{r.get('person_id', '')} | "
                      f"Type: {r.get('case_type', '')} | "
                      f"Status: {r.get('status', '')}")
                print(f"         Allegation: {(r.get('allegation', '') or '')[:80]}")
            if not records:
                print("  No cases found.")

        elif choice == "2":
            try:
                cid = int(input("  Case ID: ").strip())
                rec = svc.get_case(cid)
                if not rec:
                    print("  Case not found.")
                    continue
                print(f"\n  ID:                   {rec.get('id')}")
                print(f"  Case Reference:       {rec.get('case_reference', '')}")
                print(f"  Person Type:          {rec.get('person_type', '')}")
                print(f"  Person ID:            {rec.get('person_id', '')}")
                print(f"  Case Type:            {rec.get('case_type', '')}")
                print(f"  Allegation:           {rec.get('allegation', '')}")
                print(f"  Reported By:          {rec.get('reported_by', '')}")
                print(f"  Reported Date:        {rec.get('reported_date', '')}")
                print(f"  Investigating Officer:{rec.get('investigating_officer', '')}")
                print(f"  Hearing Date:         {rec.get('hearing_date', '')}")
                print(f"  Hearing Panel:        {rec.get('hearing_panel', '')}")
                print(f"  Hearing Outcome:      {rec.get('hearing_outcome', '')}")
                print(f"  Sanction:             {rec.get('sanction', '')}")
                print(f"  Sanction Start:       {rec.get('sanction_start_date', '')}")
                print(f"  Sanction End:         {rec.get('sanction_end_date', '')}")
                print(f"  Appeal Deadline:      {rec.get('appeal_deadline', '')}")
                print(f"  Status:               {rec.get('status', '')}")
                print(f"  Notes:                {rec.get('notes', '')}")
                print(f"  Created:              {rec.get('created_at', '')}")
                print(f"  Updated:              {rec.get('updated_at', '')}")
            except ValueError:
                print("  Invalid ID.")

        elif choice == "3":
            try:
                ptype = input("  Person type (student/staff) [student]: ").strip() or "student"
                pid = int(input("  Person ID: ").strip())
                allegation = input("  Allegation: ").strip()
                if not allegation:
                    print("  Allegation is required.")
                    continue
                ctype = input("  Case type (misconduct/gross_misconduct/academic_misconduct/behavioural) [misconduct]: ").strip() or "misconduct"
                ref = input("  Case reference (or Enter to skip): ").strip() or None
                reported_by = input("  Reported by (user ID, or Enter to skip): ").strip()
                reported_date = input("  Reported date (YYYY-MM-DD, or Enter to skip): ").strip() or None
                inv_officer = input("  Investigating officer (user ID, or Enter to skip): ").strip()
                notes = input("  Notes (or Enter to skip): ").strip() or None
                kwargs = {"case_type": ctype}
                if ref:
                    kwargs["case_reference"] = ref
                if reported_by:
                    kwargs["reported_by"] = int(reported_by)
                if reported_date:
                    kwargs["reported_date"] = reported_date
                if inv_officer:
                    kwargs["investigating_officer"] = int(inv_officer)
                if notes:
                    kwargs["notes"] = notes
                rec = svc.create_case(ptype, pid, allegation, **kwargs)
                print(f"\n  Case #{rec['id']} created.")
            except ValueError:
                print("  Invalid numeric input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                cid = int(input("  Case ID to update: ").strip())
                rec = svc.get_case(cid)
                if not rec:
                    print("  Case not found.")
                    continue
                print(f"  Current: {rec.get('case_type', '')} | "
                      f"Status: {rec.get('status', '')}")
                print("  (Press Enter to keep current value)")
                kwargs = {}
                status = input(f"  Status [{rec.get('status', '')}]: ").strip()
                if status:
                    kwargs["status"] = status
                ctype = input(f"  Case type [{rec.get('case_type', '')}]: ").strip()
                if ctype:
                    kwargs["case_type"] = ctype
                allegation = input("  Allegation (or Enter to keep): ").strip()
                if allegation:
                    kwargs["allegation"] = allegation
                notes = input("  Notes (or Enter to keep): ").strip()
                if notes:
                    kwargs["notes"] = notes
                inv_officer = input("  Investigating officer ID (or Enter to keep): ").strip()
                if inv_officer:
                    kwargs["investigating_officer"] = int(inv_officer)
                if kwargs:
                    svc.update_case(cid, **kwargs)
                    print("  Case updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                cid = int(input("  Case ID: ").strip())
                hdate = input("  Hearing date (YYYY-MM-DD): ").strip()
                if not hdate:
                    print("  Hearing date is required.")
                    continue
                panel = input("  Panel members (or Enter to skip): ").strip() or None
                svc.schedule_hearing(cid, hdate, panel)
                print("  Hearing scheduled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            try:
                cid = int(input("  Case ID: ").strip())
                outcome = input("  Hearing outcome: ").strip()
                if not outcome:
                    print("  Outcome is required.")
                    continue
                sanction = input("  Sanction (or Enter to skip): ").strip() or None
                sanction_start = input("  Sanction start date (YYYY-MM-DD, or Enter): ").strip() or None
                sanction_end = input("  Sanction end date (YYYY-MM-DD, or Enter): ").strip() or None
                appeal_deadline = input("  Appeal deadline (YYYY-MM-DD, or Enter): ").strip() or None
                svc.record_outcome(
                    cid, outcome,
                    sanction=sanction,
                    sanction_start=sanction_start,
                    sanction_end=sanction_end,
                    appeal_deadline=appeal_deadline)
                print("  Outcome recorded.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            try:
                cid = int(input("  Case ID to delete: ").strip())
                confirm = input(f"  Delete case #{cid} and all evidence/appeals? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_case(cid)
                    print("  Case deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            try:
                cid = int(input("  Case ID: ").strip())
                records = svc.list_evidence(cid)
                for r in records:
                    print(f"  [{r['id']}] Type: {r.get('evidence_type', '')} | "
                          f"By: {r.get('submitted_by', '-')} | "
                          f"Date: {r.get('submitted_date', '')}")
                    print(f"         {r.get('description', '')}")
                    if r.get("file_path"):
                        print(f"         File: {r['file_path']}")
                if not records:
                    print("  No evidence for this case.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                cid = int(input("  Case ID: ").strip())
                etype = input("  Evidence type (document/witness_statement/cctv/digital/physical/other) [document]: ").strip() or "document"
                description = input("  Description: ").strip()
                if not description:
                    print("  Description is required.")
                    continue
                submitted_by = input("  Submitted by (user ID, or Enter): ").strip()
                file_path = input("  File path (or Enter): ").strip() or None
                kwargs = {}
                if submitted_by:
                    kwargs["submitted_by"] = int(submitted_by)
                if file_path:
                    kwargs["file_path"] = file_path
                rec = svc.add_evidence(cid, etype, description, **kwargs)
                print(f"\n  Evidence #{rec['id']} added.")
            except ValueError:
                print("  Invalid numeric input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            try:
                case_filter = input("  Case ID filter (or Enter for all): ").strip()
                status = input("  Status filter (or Enter for all): ").strip() or None
                kwargs = {}
                if case_filter:
                    kwargs["case_id"] = int(case_filter)
                if status:
                    kwargs["status"] = status
                records = svc.list_appeals(**kwargs)
                for r in records:
                    print(f"  [{r['id']}] Case #{r.get('case_id', '')} | "
                          f"Appellant: {r.get('appellant_id', '-')} | "
                          f"Date: {r.get('appeal_date', '')} | "
                          f"Status: {r.get('status', '')}")
                    print(f"         Grounds: {(r.get('grounds', '') or '')[:80]}")
                    if r.get("outcome"):
                        print(f"         Outcome: {r['outcome']}")
                if not records:
                    print("  No appeals found.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                cid = int(input("  Case ID: ").strip())
                appellant_id = int(input("  Appellant ID: ").strip())
                appeal_date = input("  Appeal date (YYYY-MM-DD): ").strip()
                if not appeal_date:
                    print("  Appeal date is required.")
                    continue
                grounds = input("  Grounds for appeal: ").strip()
                if not grounds:
                    print("  Grounds are required.")
                    continue
                rec = svc.lodge_appeal(cid, appellant_id, appeal_date, grounds)
                print(f"\n  Appeal #{rec['id']} lodged.")
            except ValueError:
                print("  Invalid numeric input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "12":
            try:
                aid = int(input("  Appeal ID: ").strip())
                hdate = input("  Hearing date (YYYY-MM-DD): ").strip()
                if not hdate:
                    print("  Hearing date is required.")
                    continue
                panel = input("  Panel members (or Enter to skip): ").strip() or None
                svc.schedule_appeal_hearing(aid, hdate, panel)
                print("  Appeal hearing scheduled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "13":
            try:
                aid = int(input("  Appeal ID: ").strip())
                outcome = input("  Outcome (e.g. upheld/rejected/modified): ").strip()
                if not outcome:
                    print("  Outcome is required.")
                    continue
                rec = svc.record_appeal_outcome(aid, outcome)
                print(f"  Appeal outcome recorded. Status: {rec.get('status', '')}")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "14":
            try:
                stats = svc.get_stats()
                print(f"\n  Total Cases:       {stats['total_cases']}")
                print(f"  Active Cases:      {stats['active_cases']}")
                print(f"  Total Appeals:     {stats['total_appeals']}")
                print(f"  Pending Appeals:   {stats['pending_appeals']}")
                print(f"  Total Evidence:    {stats['total_evidence']}")
                by_status = stats.get("by_status", {})
                if by_status:
                    print("\n  By Status:")
                    for k, v in by_status.items():
                        print(f"    {k}: {v}")
                by_type = stats.get("by_type", {})
                if by_type:
                    print("\n  By Type:")
                    for k, v in by_type.items():
                        print(f"    {k}: {v}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
