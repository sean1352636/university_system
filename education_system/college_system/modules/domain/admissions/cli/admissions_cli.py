"""Admissions CLI for managing applications, inductions, and withdrawals."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.modules.domain.admissions.services.admissions_service import AdmissionsService


def admissions_menu(auth: UserAuth):
    svc = AdmissionsService(auth._db_path)

    while True:
        print_header("Admissions")
        options = [
            ("1", "List Applications"),
            ("2", "New Application"),
            ("3", "Update Application Status"),
            ("4", "List Inductions"),
            ("5", "Schedule Induction"),
            ("6", "List Withdrawals"),
            ("7", "Record Withdrawal"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            status = input("  Filter by status (or Enter for all): ").strip() or None
            apps = svc.list_applications(status=status)
            for a in apps:
                print(f"  [{a['id']}] {a.get('applicant_name', '')} - {a.get('course_applied', '')} ({a.get('status', '')})")
            if not apps:
                print("  No applications found.")
        elif choice == "2":
            try:
                name = input("  Applicant Name: ").strip()
                dob = input("  Date of Birth (YYYY-MM-DD): ").strip()
                email = input("  Email: ").strip() or None
                course = input("  Course Applied: ").strip() or None
                school = input("  Previous School: ").strip() or None
                app = svc.create_application(name, dob, email=email, course_applied=course, previous_school=school)
                print(f"\n  Application #{app['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "3":
            try:
                app_id = int(input("  Application ID: ").strip())
                status = input("  New Status: ").strip()
                svc.update_application_status(app_id, status)
                print("  Status updated.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "4":
            inductions = svc.list_inductions()
            for ind in inductions:
                attended = "Yes" if ind.get("attended") else "No"
                print(f"  [{ind['id']}] Student {ind.get('student_id', '')} - {ind.get('induction_date', '')} ({ind.get('status', '')}) Attended: {attended}")
            if not inductions:
                print("  No inductions found.")
        elif choice == "5":
            try:
                sid = int(input("  Student ID: ").strip())
                date = input("  Date (YYYY-MM-DD): ").strip()
                session = input("  Session Type (full_day): ").strip() or "full_day"
                ind = svc.create_induction(sid, date, session_type=session)
                print(f"\n  Induction #{ind['id']} scheduled.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "6":
            wds = svc.list_withdrawals()
            for w in wds:
                print(f"  [{w['id']}] Student {w.get('student_id', '')} - {w.get('reason', '')} ({w.get('withdrawal_date', '')})")
            if not wds:
                print("  No withdrawals found.")
        elif choice == "7":
            try:
                sid = int(input("  Student ID: ").strip())
                reason = input("  Reason: ").strip()
                dest = input("  Destination: ").strip() or None
                w = svc.create_withdrawal(sid, reason, destination=dest)
                print(f"\n  Withdrawal #{w['id']} recorded.")
            except Exception as e:
                print(f"\n  Error: {e}")
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")
