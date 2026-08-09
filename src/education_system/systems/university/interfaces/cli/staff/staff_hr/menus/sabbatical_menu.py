"""
Sabbatical Menu - Sabbatical / study leave applications CLI.

Wired to SabbaticalManager (the same manager the sabbatical GUI uses).
"""

from datetime import datetime

from education_system.systems.university.domain.staff.staff_hr.services.managers.sabbatical_manager import (
    SabbaticalManager,
)


def display_sabbatical_menu(user_id: str, is_admin: bool = False) -> None:
    """Display the sabbatical management menu."""
    while True:
        print("\n" + "=" * 60)
        print("SABBATICAL / STUDY LEAVE")
        print("=" * 60)

        print("\n  1. My Applications")
        print("  2. Check Eligibility")
        print("  3. Apply for Sabbatical")
        print("  4. View Progress Reports")
        print("  5. Submit Progress Report")

        if is_admin:
            print("\n--- Administration ---")
            print("  6. Pending Approvals")
            print("  7. Approve / Reject Application")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _my_applications(user_id)
        elif choice == '2':
            _check_eligibility(user_id)
        elif choice == '3':
            _apply(user_id)
        elif choice == '4':
            _view_progress_reports(user_id)
        elif choice == '5':
            _submit_progress_report(user_id)
        elif choice == '6' and is_admin:
            _pending_approvals()
        elif choice == '7' and is_admin:
            _decide_application(user_id)
        else:
            print("Invalid choice.")


def _my_applications(user_id: str) -> None:
    """List the user's sabbatical applications."""
    apps = SabbaticalManager.get_user_applications(user_id)
    print("\n" + "-" * 60)
    print("MY SABBATICAL APPLICATIONS")
    print("-" * 60)

    if apps:
        for a in apps:
            print(f"\n  #{a.get('application_id')}  {a.get('title', '')}")
            print(f"    Type: {(a.get('sabbatical_type') or '').replace('_', ' ').title()}  |  "
                  f"{a.get('start_date', '')} to {a.get('end_date', '')}")
            print(f"    Pay: {a.get('pay_percentage', 100)}%  |  "
                  f"Status: {(a.get('status') or '').replace('_', ' ').title()}")
    else:
        print("\n  No applications.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _check_eligibility(user_id: str) -> None:
    """Display the user's sabbatical eligibility."""
    print("\n" + "-" * 60)
    print("SABBATICAL ELIGIBILITY")
    print("-" * 60)
    try:
        elig = SabbaticalManager.check_eligibility(user_id)
        print(f"\n  Years of Service: {elig.get('years_of_service', 0):.1f}")
        print(f"  Last Sabbatical: {elig.get('last_sabbatical_end') or 'None'}")
        if elig.get('is_eligible'):
            print("  Status: Eligible")
        else:
            print(f"  Status: Not Eligible - {elig.get('reason', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _apply(user_id: str) -> None:
    """Create a sabbatical application, optionally submitting it."""
    print("\n--- Apply for Sabbatical ---")
    title = input("Title: ").strip()
    if not title:
        print("\nTitle is required.")
        input("Press Enter to continue...")
        return

    sab_type = input("Type (research/teaching_development/industry/study) [research]: ").strip() or 'research'
    start_date = input("Start date (YYYY-MM-DD): ").strip()
    end_date = input("End date (YYYY-MM-DD): ").strip()
    proposal = input("Research proposal (optional): ").strip() or None
    institution = input("Host institution (optional): ").strip() or None

    try:
        pay_pct = int(input("Pay percentage (100/80/60/50/0) [100]: ").strip() or '100')

        app_id = SabbaticalManager.create_application(
            user_id, title=title, sabbatical_type=sab_type,
            research_proposal=proposal, host_institution=institution,
            start_date=start_date, end_date=end_date, pay_percentage=pay_pct,
        )
        print(f"\nApplication created (draft). ID: {app_id}")

        submit = input("Submit for approval now? (y/n): ").strip().lower()
        if submit == 'y':
            SabbaticalManager.submit_application(app_id, user_id)
            print("Application submitted for approval.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _pick_active_application(user_id: str):
    """Prompt to select an approved/active application. Returns application_id or None."""
    apps = SabbaticalManager.get_user_applications(user_id)
    active = [a for a in apps if a.get('status') in ('approved', 'active')]
    if not active:
        print("\nNo approved/active applications.")
        return None

    print("\nApplications:")
    for i, a in enumerate(active, 1):
        print(f"  {i}. #{a.get('application_id')}  {a.get('title', '')} [{a.get('status', '')}]")

    try:
        idx = int(input("\nSelect application (0 to abort): ").strip())
        if 1 <= idx <= len(active):
            return active[idx - 1]['application_id']
    except ValueError:
        pass
    return None


def _view_progress_reports(user_id: str) -> None:
    """List progress reports for a selected application."""
    app_id = _pick_active_application(user_id)
    if not app_id:
        input("\nPress Enter to continue...")
        return

    reports = SabbaticalManager.get_progress_reports(app_id)
    print("\n" + "-" * 60)
    print(f"PROGRESS REPORTS - Application #{app_id}")
    print("-" * 60)

    if reports:
        for r in reports:
            print(f"\n  #{r.get('report_id')}  {(r.get('report_type') or '').title()}  {r.get('report_date', '')}")
            print(f"    Status: {(r.get('status') or '').title()}")
            if r.get('review_comments'):
                print(f"    Reviewer: {r.get('review_comments')}")
    else:
        print("\n  No progress reports.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _submit_progress_report(user_id: str) -> None:
    """Submit a progress report for a selected application."""
    app_id = _pick_active_application(user_id)
    if not app_id:
        input("\nPress Enter to continue...")
        return

    print("\n--- Submit Progress Report ---")
    report_type = input("Report type (interim/final) [interim]: ").strip() or 'interim'
    content = input("Content: ").strip()
    if not content:
        print("\nContent is required.")
        input("Press Enter to continue...")
        return
    achievements = input("Achievements (optional): ").strip() or None
    challenges = input("Challenges (optional): ").strip() or None

    try:
        report_id = SabbaticalManager.submit_progress_report(
            application_id=app_id, report_type=report_type, content=content,
            achievements=achievements, challenges=challenges,
        )
        print(f"\nProgress report submitted. ID: {report_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _pending_approvals() -> None:
    """List pending sabbatical approvals."""
    approvals = SabbaticalManager.get_pending_approvals()
    print("\n" + "-" * 60)
    print("PENDING SABBATICAL APPROVALS")
    print("-" * 60)

    if approvals:
        for a in approvals:
            print(f"\n  Approval #{a.get('approval_id')}  Applicant: {a.get('user_id', '')}")
            print(f"    {a.get('title', '')}  |  Level: {(a.get('approval_level') or '').title()}  |  "
                  f"Status: {(a.get('status') or '').title()}")
    else:
        print("\n  No pending approvals.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _decide_application(approver_id: str) -> None:
    """Approve or reject a pending sabbatical application."""
    approvals = SabbaticalManager.get_pending_approvals()
    if not approvals:
        print("\nNo pending approvals.")
        input("Press Enter to continue...")
        return

    for i, a in enumerate(approvals, 1):
        print(f"  {i}. Approval #{a.get('approval_id')}  {a.get('user_id', '')}  {a.get('title', '')}")

    try:
        idx = int(input("\nSelect approval (0 to abort): ").strip())
        if idx == 0 or not (1 <= idx <= len(approvals)):
            return
        approval = approvals[idx - 1]
        action = input("Approve or Reject? (a/r): ").strip().lower()
        if action == 'a':
            comments = input("Approval comments (optional): ").strip()
            SabbaticalManager.approve_application(approval['approval_id'], approver_id, comments)
            print("\nApplication approved at this level.")
        elif action == 'r':
            comments = input("Rejection reason: ").strip()
            if not comments:
                print("\nRejection reason is required.")
                input("Press Enter to continue...")
                return
            SabbaticalManager.reject_application(approval['approval_id'], approver_id, comments)
            print("\nApplication rejected.")
        else:
            print("\nNo action taken.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")
