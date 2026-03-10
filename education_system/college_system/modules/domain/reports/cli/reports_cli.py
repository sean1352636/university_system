"""Reports CLI for managing progress reports."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.reports.services.reports_service import ReportsService


def reports_menu(auth: UserAuth):
    svc = ReportsService(auth._db_path)

    while True:
        print_header("Progress Reports")
        options = [
            ("1", "List Reports"),
            ("2", "Create Report"),
            ("3", "View Report Entries"),
            ("4", "Add Report Entry"),
            ("5", "Update Report Status"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            reports = svc.list_reports()
            for r in reports:
                print(f"  [{r['id']}] {r.get('title', '')} ({r.get('report_type', '')}) [{r.get('status', '')}] Due: {r.get('due_date', '')}")
            if not reports:
                print("  No reports found.")
        elif choice == "2":
            try:
                title = input("  Title: ").strip()
                rtype = input("  Type (interim/full/final): ").strip() or "interim"
                year = input("  Academic Year: ").strip() or None
                term = input("  Term: ").strip() or None
                due = input("  Due Date: ").strip() or None
                user_id = auth.current_user["user_id"]
                r = svc.create_report(title, report_type=rtype, academic_year=year, term=term, due_date=due, created_by=user_id)
                print(f"\n  Report #{r['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                rid = int(input("  Report ID: ").strip())
                entries = svc.list_entries(rid)
                for e in entries:
                    name = f"{e.get('first_name', '')} {e.get('last_name', '')}".strip() or str(e.get("student_id", ""))
                    print(f"  [{e['id']}] {name} - {e.get('course_name', '')} Current: {e.get('current_grade', '')} Target: {e.get('target_grade', '')} Effort: {e.get('effort_grade', '')}")
                if not entries:
                    print("  No entries found.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            try:
                rid = int(input("  Report ID: ").strip())
                sid = int(input("  Student ID: ").strip())
                cid = int(input("  Course ID: ").strip())
                current = input("  Current Grade: ").strip() or None
                target = input("  Target Grade: ").strip() or None
                effort = input("  Effort Grade: ").strip() or None
                comment = input("  Comment: ").strip() or None
                user_id = auth.current_user["user_id"]
                e = svc.add_entry(rid, sid, cid, user_id, current_grade=current, target_grade=target, effort_grade=effort, comment=comment)
                print(f"\n  Entry #{e['id']} added.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "5":
            try:
                rid = int(input("  Report ID: ").strip())
                status = input("  Status (draft/open/closed): ").strip()
                svc.update_report_status(rid, status)
                print("  Status updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
