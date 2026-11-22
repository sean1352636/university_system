"""
Admin Menu - HR Administration CLI.
"""

from datetime import datetime

from education_system.systems.university.domains.staff.interfaces.cli.staff_hr.menus import _access as _hr
from education_system.systems.university.domains.staff.domain.staff_hr.services import (
    AdminToolsManager, RecruitmentManager, OnboardingManager, EmployeeManager
)


def display_admin_menu(user_id: str) -> None:
    """Display HR administration menu (each section shown to whoever may use it)."""
    can = {cap: _hr.can(cap) for cap in
           ('recruitment', 'hr', 'operations', 'reports', 'hr_admin')}
    sections = (
        ('recruitment', "Recruitment", (
            ('1', "View Job Postings", _view_job_postings),
            ('2', "Create Job Posting", lambda: _create_job_posting(user_id)),
            ('3', "View Applications", _view_applications),
            ('4', "Schedule Interview", lambda: _schedule_interview(user_id)))),
        ('hr', "Onboarding", (
            ('5', "Active Onboardings", _active_onboardings),
            ('6', "Start New Onboarding", lambda: _start_onboarding(user_id)),
            ('7', "Onboarding Templates", lambda: _onboarding_templates(user_id)))),
        ('operations', "Admin Tools", (
            ('8', "Document Approvals", lambda: _document_approvals(user_id)),
            ('9', "Access Card Management", lambda: _access_card_management(user_id)),
            ('10', "Key Management", lambda: _key_management(user_id)),
            ('11', "Visitor Management", lambda: _visitor_management(user_id)),
            ('12', "Interdepartmental Requests", lambda: _interdepartmental_requests(user_id)))),
        ('reports', "Reports", (
            ('13', "Staff Reports", _staff_reports),
            ('14', "Department KPIs", _department_kpis))),
        ('hr_admin', "HR Roles", (
            ('15', "Who Holds HR Roles", _hr_role_holders),
            ('16', "Grant / Revoke an HR Role", _hr_grant_revoke),
            ('17', "HR Audit Trail", _hr_audit_trail))),
    )
    while True:
        print("\n" + "=" * 60)
        print("HR ADMINISTRATION")
        print("=" * 60)

        actions = {}
        for cap, title, items in sections:
            if not can[cap]:
                continue
            print(f"\n--- {title} ---")
            for key, label, handler in items:
                print(f"  {key}. {label}")
                actions[key] = handler
        if not actions:
            print("\n  You have no HR administration access.")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice in actions:
            actions[choice]()
        else:
            print("Invalid choice.")


# ==================== HR ROLES ====================

def _hr_role_holders() -> None:
    """Who holds each HR role (administrators hold all of them implicitly)."""
    from education_system.systems.university.domains.staff.domain.staff_hr import access
    try:
        rows = access.list_role_holders(_hr.actor())
    except PermissionError as e:
        print(f"\n{e}")
        return
    print("\n--- HR Role Holders ---")
    if not rows:
        print("No HR roles granted (system administrators hold every role).")
    for r in rows:
        print(f"  {access.ROLE_LABELS.get(r['role'], r['role']):<18} {r['username']:<16} "
              f"{access.display_name(r['username']):<24} by {r.get('granted_by') or '-'} "
              f"on {(r.get('granted_at') or '')[:16]}")
    input("\nPress Enter to continue...")


def _hr_grant_revoke() -> None:
    """Grant or revoke one HR role."""
    from education_system.systems.university.domains.staff.domain.staff_hr import access
    username = input("Username: ").strip()
    if not username:
        return
    print("Roles:")
    for i, role in enumerate(access.HR_ROLES, 1):
        print(f"  {i}. {access.ROLE_LABELS.get(role, role)}")
    try:
        role = access.HR_ROLES[int(input("Role number: ").strip()) - 1]
    except (ValueError, IndexError):
        print("Invalid role.")
        return
    action = input("[G]rant or [R]evoke? ").strip().upper()
    try:
        if action == 'G':
            added = access.grant_role(_hr.actor(), username, role)
            print(f"\n{username} {'now holds' if added else 'already holds'} "
                  f"{access.ROLE_LABELS[role]}.")
        elif action == 'R':
            if input(f"Revoke {access.ROLE_LABELS[role]} from {username}? (y/n): "
                     ).strip().lower() != 'y':
                return
            removed = access.revoke_role(_hr.actor(), username, role)
            print(f"\nRevoked {access.ROLE_LABELS[role]} from {username}." if removed
                  else f"\n{username} did not hold {access.ROLE_LABELS[role]}.")
        else:
            print("No action taken.")
    except (ValueError, PermissionError) as e:
        print(f"\nError: {e}")


def _hr_audit_trail() -> None:
    """The HR audit trail, optionally for one person."""
    from education_system.systems.university.domains.staff.domain.staff_hr import access
    subject = input("Person's username (blank for everyone): ").strip() or None
    if subject:
        subject = access.staff_key(subject) or subject
    try:
        rows = access.audit_trail(_hr.actor(), subject=subject, limit=200)
    except PermissionError as e:
        print(f"\n{e}")
        return
    print(f"\n--- HR Audit Trail ({len(rows)} most recent) ---")
    for r in rows:
        print(f"  {(r.get('at') or '')[:19]}  {r.get('actor') or '-':<14} "
              f"{r.get('action') or '':<24} {r.get('subject_username') or '':<14} "
              f"{r.get('entity') or ''} {r.get('entity_id') or ''}")
    if not rows:
        print("  Nothing recorded.")
    input("\nPress Enter to continue...")


# ==================== RECRUITMENT ====================

def _view_job_postings() -> None:
    """View job postings (recruitment and HR also see drafts and closed ones)."""
    try:
        postings = RecruitmentManager.get_staff_recruitment_postings(actor=_hr.actor())
    except PermissionError as e:
        print(f"\n{e}")
        input("Press Enter to continue...")
        return
    print("\n" + "-" * 60)
    print("JOB POSTINGS")
    print("-" * 60)

    if postings:
        for p in postings:
            status = (p.get('status') or 'open').upper()
            print(f"\n  [{status}] #{p.get('posting_id')} {p.get('job_title')}")
            print(f"    Department: {p.get('department') or 'N/A'}")
            print(f"    Type: {p.get('job_type') or 'N/A'}")
            print(f"    Posted: {(p.get('post_date') or 'N/A')[:10]}")
            print(f"    Deadline: {p.get('closing_date') or 'N/A'}")
            print(f"    Applications: {p.get('applications_count') or 0}")
    else:
        print("No job postings found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_job_posting(user_id: str) -> None:
    """Create a new job posting (as a draft; publish it from Recruitment)."""
    print("\n--- Create Job Posting ---")
    title = input("Job Title: ").strip()
    department = input("Department: ").strip()
    job_type = input("Type (permanent/fixed_term/part_time/contract): ").strip() or 'permanent'
    description = input("Description:\n").strip()
    requirements = input("Requirements:\n").strip()
    salary_range = input("Salary Range: ").strip()
    closing_date = input("Closing Date (YYYY-MM-DD): ").strip()

    if title and department:
        try:
            posting_id = RecruitmentManager.create_posting(
                user_id, title, department,
                actor=_hr.actor(),
                job_type=job_type,
                description=description or None,
                requirements=requirements or None,
                salary_range=salary_range or None,
                closing_date=closing_date or None,
            )
            print(f"\nJob posting created as a draft. ID: {posting_id}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        print("\nTitle and department are required.")

    input("Press Enter to continue...")


def _view_applications() -> None:
    """View job applications (recruitment and HR)."""
    actor = _hr.actor()
    try:
        postings = RecruitmentManager.get_active_postings(actor=actor)
        if not postings:
            print("\nNo open job postings.")
            input("Press Enter to continue...")
            return

        print("\nSelect Job Posting:")
        for i, p in enumerate(postings, 1):
            print(f"  {i}. {p.get('job_title')} ({p.get('applicant_count', 0)} applications)")

        choice = int(input("\nSelect (0 for all): ").strip())
        posting_id = None
        if 1 <= choice <= len(postings):
            posting_id = postings[choice - 1]['posting_id']

        applications = RecruitmentManager.get_applications(posting_id=posting_id, actor=actor)

        print("\n" + "-" * 60)
        print("APPLICATIONS")
        print("-" * 60)

        if applications:
            for a in applications:
                status = (a.get('status') or 'received').upper()
                print(f"\n  [{status}] #{a.get('application_id')} {a.get('applicant_name') or 'N/A'}")
                print(f"    Position: {a.get('job_title') or 'N/A'}")
                print(f"    Applied: {(a.get('application_date') or 'N/A')[:10]}")
                print(f"    Email: {a.get('applicant_email') or 'N/A'}")
        else:
            print("No applications found.")

        print("-" * 60)
    except ValueError:
        print("Invalid input.")
    except PermissionError as e:
        print(f"\n{e}")

    input("\nPress Enter to continue...")


def _schedule_interview(user_id: str) -> None:
    """Schedule an interview for a shortlisted candidate (recruitment and HR)."""
    actor = _hr.actor()
    try:
        applications = RecruitmentManager.get_applications(status='shortlisted', actor=actor)
    except PermissionError as e:
        print(f"\n{e}")
        input("Press Enter to continue...")
        return
    if not applications:
        print("\nNo shortlisted applications.")
        input("Press Enter to continue...")
        return

    print("\nShortlisted Candidates:")
    for i, a in enumerate(applications, 1):
        print(f"  {i}. {a.get('applicant_name')} - {a.get('job_title')}")

    try:
        choice = int(input("\nSelect candidate (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(applications):
            application = applications[choice - 1]

            interview_date = input("Interview Date (YYYY-MM-DD): ").strip()
            interview_time = input("Interview Time (HH:MM): ").strip()
            interview_type = input("Type (in-person/video/phone): ").strip() or 'in-person'
            location = input("Location/Link: ").strip()
            panel = input("Panel members (comma-separated usernames): ").strip()

            interview_id = RecruitmentManager.schedule_interview(
                application['application_id'], interview_date, interview_time,
                actor=actor,
                interview_type=interview_type,
                location=location or None,
                interviewers=panel or None,
            )
            print(f"\nInterview scheduled. ID: {interview_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


# ==================== ONBOARDING ====================

def _active_onboardings() -> None:
    """View active onboardings."""
    onboardings = OnboardingManager.get_active_onboardings(actor=_hr.actor())
    print("\n" + "-" * 60)
    print("ACTIVE ONBOARDINGS")
    print("-" * 60)

    if onboardings:
        for o in onboardings:
            progress = o.get('progress', 0)
            bar = '█' * (progress // 10) + '░' * (10 - progress // 10)
            name = f"{o.get('first_name', '')} {o.get('last_name', '')}"
            print(f"\n  {name.strip()}")
            print(f"    [{bar}] {progress}%")
            print(f"    Start Date: {o.get('start_date', 'N/A')}")
            print(f"    Department: {o.get('department', 'N/A')}")
            print(f"    Buddy: {o.get('buddy_name', 'Not assigned')}")
    else:
        print("No active onboardings.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _start_onboarding(user_id: str) -> None:
    """Start new onboarding."""
    print("\n--- Start New Onboarding ---")
    employee_id = input("New Employee User ID: ").strip()
    start_date = input("Start Date (YYYY-MM-DD): ").strip()

    templates = OnboardingManager.get_templates()
    print("\nOnboarding Templates:")
    for i, t in enumerate(templates, 1):
        print(f"  {i}. {t.get('name')} ({t.get('task_count', 0)} tasks)")

    try:
        template_choice = int(input("\nSelect template: ").strip()) - 1
        if template_choice < 0 or template_choice >= len(templates):
            print("Invalid template.")
            input("Press Enter to continue...")
            return

        template = templates[template_choice]
        buddy_id = input("Assign Buddy (user ID, or blank): ").strip()

        onboarding_id = OnboardingManager.start_onboarding(
            employee_id,
            template_id=template['template_id'],
            start_date=start_date,
            buddy_id=buddy_id if buddy_id else None,
            created_by=user_id,
            actor=_hr.actor()
        )
        print(f"\nOnboarding started. ID: {onboarding_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _onboarding_templates(user_id: str = None) -> None:
    """View onboarding templates."""
    templates = OnboardingManager.get_templates()
    print("\n" + "-" * 60)
    print("ONBOARDING TEMPLATES")
    print("-" * 60)

    if templates:
        for t in templates:
            print(f"\n  {t.get('name')}")
            print(f"    Type: {t.get('role') or 'all'}")
            print(f"    Tasks: {t.get('task_count', 0)}")
            print(f"    Duration: {t.get('estimated_days', 'N/A')} days")
    else:
        print("No templates found.")

    print("-" * 60)

    create = input("\nCreate new template? (y/n): ").strip().lower()
    if create == 'y':
        name = input("Template Name: ").strip()
        emp_type = input("Employee Type (academic/administrative/all): ").strip()
        duration = input("Duration (days): ").strip()

        if name:
            try:
                template_id = OnboardingManager.create_template(
                    name,
                    created_by=user_id,
                    role=emp_type if emp_type and emp_type != 'all' else None,
                    estimated_days=int(duration) if duration else 30
                )
                print(f"\nTemplate created. ID: {template_id}")
            except Exception as e:
                print(f"\nError: {e}")

    input("Press Enter to continue...")


# ==================== ADMIN TOOLS ====================

def _document_approvals(user_id: str) -> None:
    """Handle document approvals."""
    pending = AdminToolsManager.get_pending_document_approvals(user_id)
    print("\n" + "-" * 60)
    print("PENDING DOCUMENT APPROVALS")
    print("-" * 60)

    if not pending:
        print("No pending document approvals.")
        input("\nPress Enter to continue...")
        return

    for i, d in enumerate(pending, 1):
        print(f"\n  {i}. {d.get('document_name')}")
        print(f"     Type: {d.get('document_type')} | Submitted: {(d.get('submitted_date') or 'N/A')[:10]}")
        print(f"     Submitted by: {d.get('submitter_name', 'N/A')}")

    print("-" * 60)

    try:
        choice = int(input("\nSelect document (0 to abort): ").strip())
        if choice == 0:
            return
        if 1 <= choice <= len(pending):
            document = pending[choice - 1]
            action = input("(A)pprove or (R)eject? ").strip().upper()

            if action == 'A':
                AdminToolsManager.approve_document(document['approval_id'], user_id)
                print("\nDocument approved.")
            elif action == 'R':
                reason = input("Rejection reason: ").strip()
                AdminToolsManager.reject_document(document['approval_id'], user_id, reason)
                print("\nDocument rejected.")
    except ValueError:
        print("\nInvalid input.")

    input("Press Enter to continue...")


def _access_card_management(admin_id: str = None) -> None:
    """Manage access cards."""
    print("\n--- Access Card Management ---")
    print("  1. View All Cards")
    print("  2. Issue New Card")
    print("  3. Deactivate Card")
    print("  4. Report Lost Card")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        cards = AdminToolsManager.get_access_cards()
        print("\n" + "-" * 50)
        print("ACCESS CARDS")
        print("-" * 50)
        for c in cards[:20]:
            status = c.get('status', 'active').upper()
            print(f"  [{status}] {c.get('card_number')} - {c.get('user_name') or c.get('user_id') or 'N/A'}")
        print("-" * 50)

    elif choice == '2':
        user_id = input("User ID: ").strip()
        card_number = input("Card Number: ").strip()
        access_level = input("Access Level (basic/standard/full): ").strip()

        if user_id and card_number:
            try:
                card_id = AdminToolsManager.issue_access_card(
                    card_number, user_id, admin_id, access_level=access_level
                )
                print(f"\nCard issued. ID: {card_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '3':
        card_number = input("Card Number to deactivate: ").strip()
        reason = input("Reason: ").strip()
        if AdminToolsManager.deactivate_card_by_number(card_number, reason):
            print("\nCard deactivated.")
        else:
            print("\nNo card with that number.")

    elif choice == '4':
        card_number = input("Lost Card Number: ").strip()
        if AdminToolsManager.report_lost_card(card_number, admin_id):
            print("\nCard reported as lost and deactivated.")
        else:
            print("\nNo such card, or it is already reported lost.")

    input("Press Enter to continue...")


def _key_management(admin_id: str = None) -> None:
    """Manage keys."""
    print("\n--- Key Management ---")
    print("  1. View Issued Keys")
    print("  2. Issue Key")
    print("  3. Return Key")
    print("  4. Report Lost Key")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        keys = AdminToolsManager.get_issued_keys()
        print("\n" + "-" * 50)
        print("ISSUED KEYS")
        print("-" * 50)
        for k in keys[:20]:
            print(f"  {k.get('key_number')} - {k.get('location', 'N/A')}")
            print(f"    Holder: {k.get('holder_name', 'N/A')}")
            print(f"    Issued: {(k.get('issued_date') or 'N/A')[:10]}")
        print("-" * 50)

    elif choice == '2':
        user_id = input("User ID: ").strip()
        key_number = input("Key Number: ").strip()
        location = input("Location/Room: ").strip()

        if user_id and key_number:
            try:
                key_id = AdminToolsManager.issue_key(user_id, key_number, location, issued_by=admin_id)
                print(f"\nKey issued. ID: {key_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '3':
        key_number = input("Key Number to return: ").strip()
        if AdminToolsManager.return_key_by_number(key_number):
            print("\nKey returned.")
        else:
            print("\nThat key is not out with anyone.")

    elif choice == '4':
        key_number = input("Lost Key Number: ").strip()
        if AdminToolsManager.report_lost_key(key_number, admin_id):
            print("\nKey reported as lost.")
        else:
            print("\nThat key is not out with anyone.")

    input("Press Enter to continue...")


def _visitor_management(user_id: str) -> None:
    """Manage visitors."""
    print("\n--- Visitor Management ---")
    print("  1. Today's Visitors")
    print("  2. Register Visitor")
    print("  3. Check In Visitor")
    print("  4. Check Out Visitor")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        visitors = AdminToolsManager.get_todays_visitors()
        print("\n" + "-" * 50)
        print("TODAY'S VISITORS")
        print("-" * 50)
        for v in visitors:
            status = 'IN' if v.get('status') == 'checked_in' else 'OUT'
            print(f"  [{status}] {v.get('visitor_name')} (ID {v.get('visitor_id')})")
            print(f"    Visiting: {v.get('host_name') or v.get('host_id') or 'N/A'}")
            print(f"    Purpose: {v.get('visit_purpose') or 'N/A'}")
            if v.get('check_in_time'):
                print(f"    Checked In: {v.get('check_in_time')}")
        print("-" * 50)

    elif choice == '2':
        name = input("Visitor Name: ").strip()
        company = input("Company/Organization: ").strip()
        host_id = input("Host User ID: ").strip()
        purpose = input("Purpose of Visit: ").strip()
        expected_date = input("Expected Date (YYYY-MM-DD): ").strip()

        if name and host_id:
            try:
                visitor_id = AdminToolsManager.register_visitor(
                    host_id, name,
                    expected_date or datetime.now().strftime('%Y-%m-%d'),
                    visitor_company=company or None,
                    visit_purpose=purpose or None,
                    notes=f"Registered by {user_id}"
                )
                print(f"\nVisitor registered. ID: {visitor_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '3':
        reference = input("Visitor ID or Name: ").strip()
        badge_number = input("Badge Number: ").strip()
        try:
            visitor_id = AdminToolsManager.find_visitor(reference)
            if visitor_id is None:
                print("\nNo such visitor.")
            else:
                AdminToolsManager.check_in_visitor(visitor_id, badge_number or None)
                print("\nVisitor checked in.")
        except ValueError as e:
            print(f"\n{e}")

    elif choice == '4':
        reference = input("Visitor ID or Name: ").strip()
        try:
            visitor_id = AdminToolsManager.find_visitor(reference)
            if visitor_id is None:
                print("\nNo such visitor.")
            else:
                AdminToolsManager.check_out_visitor(visitor_id)
                print("\nVisitor checked out.")
        except ValueError as e:
            print(f"\n{e}")

    input("Press Enter to continue...")


def _interdepartmental_requests(user_id: str) -> None:
    """Handle interdepartmental requests."""
    print("\n--- Interdepartmental Requests ---")
    print("  1. View My Requests")
    print("  2. Submit Request")
    print("  3. Pending Approvals")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        requests = AdminToolsManager.get_user_requests(user_id)
        print("\n" + "-" * 50)
        print("MY REQUESTS")
        print("-" * 50)
        for r in requests:
            status = r.get('status', 'pending').upper()
            print(f"\n  [{status}] {r.get('request_type')}")
            print(f"    To: {r.get('target_department', 'N/A')}")
            print(f"    Submitted: {(r.get('submitted_date') or 'N/A')[:10]}")
        print("-" * 50)

    elif choice == '2':
        request_type = input("Request Type: ").strip()
        target_dept = input("Target Department: ").strip()
        description = input("Description:\n").strip()
        priority = input("Priority (low/medium/high): ").strip() or 'medium'

        if request_type and target_dept:
            try:
                request_id = AdminToolsManager.submit_request(
                    user_id, request_type,
                    target_department=target_dept,
                    description=description,
                    priority=priority
                )
                print(f"\nRequest submitted. ID: {request_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '3':
        pending = AdminToolsManager.get_pending_requests(user_id)
        print("\n" + "-" * 50)
        print("PENDING FOR MY APPROVAL")
        print("-" * 50)
        if pending:
            for i, r in enumerate(pending, 1):
                print(f"\n  {i}. {r.get('request_type')}")
                print(f"     From: {r.get('requester_name', 'N/A')}")
                print(f"     Priority: {r.get('priority', 'medium')}")

            try:
                idx = int(input("\nSelect to process (0 to skip): ").strip())
                if 1 <= idx <= len(pending):
                    req = pending[idx - 1]
                    action = input("(A)pprove or (R)eject? ").strip().upper()
                    if action == 'A':
                        if AdminToolsManager.approve_request(req['request_id'], user_id):
                            print("\nRequest approved.")
                        else:
                            print("\nThat request is no longer pending.")
                    elif action == 'R':
                        reason = input("Rejection reason: ").strip()
                        if AdminToolsManager.reject_request(req['request_id'], user_id, reason):
                            print("\nRequest rejected.")
                        else:
                            print("\nThat request is no longer pending.")
            except ValueError:
                pass
            except PermissionError as e:
                print(f"\n{e}")
        else:
            print("No pending requests.")
        print("-" * 50)

    input("Press Enter to continue...")


# ==================== REPORTS ====================

def _staff_reports() -> None:
    """Generate staff reports."""
    print("\n--- Staff Reports ---")
    print("  1. Headcount by Department")
    print("  2. Leave Summary")
    print("  3. Training Compliance")
    print("  4. Asset Utilization")
    print("  5. Attendance Summary")
    print("  0. Return")

    choice = input("\nChoice: ").strip()

    if choice == '1':
        report = EmployeeManager.get_department_breakdown()
        print("\n" + "-" * 50)
        print("HEADCOUNT BY DEPARTMENT")
        print("-" * 50)
        if report:
            for dept, count in report.items():
                print(f"  {dept}: {count}")
        print("-" * 50)

    elif choice == '2':
        from education_system.systems.university.domains.staff.domain.staff_hr.services import LeaveManager
        report = LeaveManager.get_leave_summary_report()
        print("\n" + "-" * 50)
        print("LEAVE SUMMARY")
        print("-" * 50)
        if report:
            print(f"  Total Requests: {report.get('total_requests', 0)}")
            print(f"  Approved: {report.get('approved', 0)}")
            print(f"  Pending: {report.get('pending', 0)}")
            print(f"  Rejected: {report.get('rejected', 0)}")
        print("-" * 50)

    elif choice == '3':
        from education_system.systems.university.domains.staff.domain.staff_hr.services import TrainingManager
        report = TrainingManager.get_compliance_report()
        print("\n" + "-" * 50)
        print("TRAINING COMPLIANCE")
        print("-" * 50)
        if report:
            print(f"  Total Staff: {report.get('total_staff', 0)}")
            print(f"  Fully Compliant: {report.get('compliant', 0)}")
            print(f"  Non-Compliant: {report.get('non_compliant', 0)}")
            print(f"  Compliance Rate: {report.get('compliance_rate', 0):.1f}%")
        print("-" * 50)

    elif choice == '4':
        from education_system.systems.university.domains.staff.domain.staff_hr.services import AssetManager
        report = AssetManager.get_utilization_report()
        print("\n" + "-" * 50)
        print("ASSET UTILIZATION")
        print("-" * 50)
        if report:
            print(f"  Total Assets: {report.get('total_assets', 0)}")
            print(f"  In Use: {report.get('assigned', 0)}")
            print(f"  Available: {report.get('available', 0)}")
            print(f"  Under Repair: {report.get('under_repair', 0)}")
            print(f"  Utilization Rate: {report.get('utilization_rate', 0):.1f}%")
        print("-" * 50)

    elif choice == '5':
        from education_system.systems.university.domains.staff.domain.staff_hr.services import TimeManager
        report = TimeManager.get_attendance_summary()
        print("\n" + "-" * 50)
        print("ATTENDANCE SUMMARY (This Month)")
        print("-" * 50)
        if report:
            print(f"  Total Clock-ins: {report.get('total_clockins', 0)}")
            print(f"  Avg Hours/Day: {report.get('avg_hours', 0):.1f}")
            print(f"  Overtime Hours: {report.get('overtime_hours', 0):.1f}")
        print("-" * 50)

    input("Press Enter to continue...")


def _department_kpis() -> None:
    """View one department's KPIs against their targets."""
    department = input("Department: ").strip()
    if not department:
        print("A department is required.")
        input("Press Enter to continue...")
        return
    year = input("Academic year (blank for all): ").strip() or None
    kpis = RecruitmentManager.get_department_kpis(department, year)
    print("\n" + "-" * 60)
    print(f"DEPARTMENT KPIs - {department}")
    print("-" * 60)

    if kpis:
        for k in kpis:
            unit = k.get('unit') or ''
            print(f"\n  [{(k.get('status') or 'on_track').upper()}] {k.get('kpi_name')}"
                  f" ({k.get('kpi_category') or 'general'})")
            print(f"    Target: {k.get('target_value')}{unit}   Current: {k.get('current_value')}{unit}")
            if k.get('owner_name') or k.get('owner_id'):
                print(f"    Owner: {k.get('owner_name') or k.get('owner_id')}")
    else:
        print("No KPIs recorded for this department.")

    print("-" * 60)
    input("\nPress Enter to continue...")


