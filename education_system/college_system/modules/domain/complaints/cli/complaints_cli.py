"""Complaints CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.complaints.services.complaints_service import ComplaintService
from education_system.college_system.infrastructure.auth.core import UserAuth


def complaints_menu(auth: UserAuth):
    """Complaints management menu."""
    svc = ComplaintService(auth._db_path)

    while True:
        print_header("Complaints Management")
        options = [
            ("1", "List Complaints"),
            ("2", "Search Complaints"),
            ("3", "View Complaint"),
            ("4", "New Complaint"),
            ("5", "Update Complaint"),
            ("6", "Escalate Complaint"),
            ("7", "Resolve Complaint"),
            ("8", "Delete Complaint"),
            ("9", "View Responses"),
            ("10", "Add Response"),
            ("11", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            status = input("  Status filter (or Enter for all): ").strip() or None
            records = svc.list_complaints(status=status)
            for r in records:
                print(f"  [{r['id']}] {r.get('complaint_date', '')} | "
                      f"{r.get('complainant_name', '')} | "
                      f"{r.get('subject', '')} | "
                      f"Stage: {r.get('stage', '')} | "
                      f"Status: {r.get('status', '')}")
            if not records:
                print("  No complaints found.")

        elif choice == "2":
            term = input("  Search (name/subject/description): ").strip()
            if not term:
                print("  No search term entered.")
                continue
            records = svc.list_complaints(search=term)
            for r in records:
                print(f"  [{r['id']}] {r.get('complainant_name', '')} - "
                      f"{r.get('subject', '')} [{r.get('status', '')}]")
            if not records:
                print("  No results found.")

        elif choice == "3":
            try:
                cid = int(input("  Complaint ID: ").strip())
                rec = svc.get_complaint(cid)
                if not rec:
                    print("  Complaint not found.")
                    continue
                print(f"\n  Subject:         {rec.get('subject', '')}")
                print(f"  Complainant:     {rec.get('complainant_name', '')} "
                      f"({rec.get('complainant_type', '')})")
                print(f"  Email:           {rec.get('complainant_email', '')}")
                print(f"  Phone:           {rec.get('complainant_phone', '')}")
                print(f"  Date:            {rec.get('complaint_date', '')}")
                print(f"  Category:        {rec.get('category', '')}")
                print(f"  Stage:           {rec.get('stage', '')}")
                print(f"  Status:          {rec.get('status', '')}")
                print(f"  Description:     {rec.get('description', '')}")
                print(f"  Investigation:   {rec.get('investigation_notes', '')}")
                print(f"  Outcome:         {rec.get('outcome', '')}")
                print(f"  Resolution:      {rec.get('resolution', '')}")
                print(f"  Resolved Date:   {rec.get('resolved_date', '')}")
                print(f"  Appeal Lodged:   {'Yes' if rec.get('appeal_lodged') else 'No'}")
            except ValueError:
                print("  Invalid ID.")

        elif choice == "4":
            try:
                name = input("  Complainant Name: ").strip()
                subj = input("  Subject: ").strip()
                desc = input("  Description: ").strip()
                if not name or not subj or not desc:
                    print("  Name, subject, and description are required.")
                    continue
                ctype = input("  Type (student/parent/staff/visitor/other) [parent]: ").strip() or "parent"
                cat = input("  Category (general/teaching/facilities/staff_conduct/assessment/other) [general]: ").strip() or "general"
                email = input("  Email: ").strip() or None
                phone = input("  Phone: ").strip() or None
                rec = svc.create_complaint(
                    name, subj, desc,
                    complainant_type=ctype, category=cat,
                    complainant_email=email, complainant_phone=phone)
                print(f"\n  Complaint #{rec['id']} logged.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                cid = int(input("  Complaint ID to update: ").strip())
                rec = svc.get_complaint(cid)
                if not rec:
                    print("  Complaint not found.")
                    continue
                print(f"  Current: {rec.get('subject', '')} [{rec.get('status', '')}]")
                print("  (Press Enter to keep current value)")
                kwargs = {}
                status = input(f"  Status [{rec.get('status', '')}]: ").strip()
                if status:
                    kwargs["status"] = status
                stage = input(f"  Stage [{rec.get('stage', '')}]: ").strip()
                if stage:
                    kwargs["stage"] = stage
                inv = input(f"  Investigation Notes: ").strip()
                if inv:
                    kwargs["investigation_notes"] = inv
                outcome = input(f"  Outcome: ").strip()
                if outcome:
                    kwargs["outcome"] = outcome
                if kwargs:
                    svc.update_complaint(cid, **kwargs)
                    print("  Complaint updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            try:
                cid = int(input("  Complaint ID to escalate: ").strip())
                rec = svc.get_complaint(cid)
                if not rec:
                    print("  Complaint not found.")
                    continue
                print(f"  Current stage: {rec.get('stage', '')}")
                confirm = input("  Escalate? (y/n): ").strip().lower()
                if confirm == "y":
                    updated = svc.escalate(cid)
                    print(f"  Escalated to: {updated.get('stage', '')}")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "7":
            try:
                cid = int(input("  Complaint ID to resolve: ").strip())
                outcome = input("  Outcome: ").strip()
                if not outcome:
                    print("  Outcome is required.")
                    continue
                resolution = input("  Resolution details: ").strip() or None
                svc.resolve(cid, outcome, resolution)
                print("  Complaint resolved.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            try:
                cid = int(input("  Complaint ID to delete: ").strip())
                confirm = input(f"  Delete complaint #{cid} and responses? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_complaint(cid)
                    print("  Complaint deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                cid = int(input("  Complaint ID: ").strip())
                responses = svc.list_responses(cid)
                for r in responses:
                    who = r.get("responder_name") or f"User #{r.get('responder_id', '?')}"
                    print(f"  [{r['id']}] {r.get('response_date', '')} | "
                          f"{who} ({r.get('response_type', '')})")
                    print(f"    {r.get('response_text', '')}")
                if not responses:
                    print("  No responses for this complaint.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            try:
                cid = int(input("  Complaint ID: ").strip())
                text = input("  Response text: ").strip()
                if not text:
                    print("  Response text is required.")
                    continue
                rtype = input("  Type (acknowledgement/investigation/update/outcome/appeal_response) [investigation]: ").strip() or "investigation"
                resp = svc.add_response(cid, text, response_type=rtype)
                print(f"\n  Response #{resp['id']} added.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                stats = svc.get_stats()
                print(f"\n  Total Complaints:  {stats['total']}")
                print(f"  Open:              {stats['open']}")
                print(f"  Investigating:     {stats['investigating']}")
                print(f"  Resolved:          {stats['resolved']}")
                print(f"  Appeals Lodged:    {stats['appealed']}")
                by_cat = stats.get("by_category", {})
                if by_cat:
                    print("\n  By Category:")
                    for k, v in by_cat.items():
                        print(f"    {k}: {v}")
                by_stage = stats.get("by_stage", {})
                if by_stage:
                    print("\n  By Stage:")
                    for k, v in by_stage.items():
                        print(f"    {k}: {v}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
