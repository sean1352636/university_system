"""
Admin Menu - HR Administration CLI.
"""

from university_system.modules.domain.staff_hr.services import (
    AdminToolsManager, RecruitmentManager, OnboardingManager, EmployeeManager
)


def display_admin_menu(user_id: str) -> None:
    """Display HR administration menu."""
    while True:
        print("\n" + "=" * 60)
        print("HR ADMINISTRATION")
        print("=" * 60)

        print("\n--- Recruitment ---")
        print("  1. View Job Postings")
        print("  2. Create Job Posting")
        print("  3. View Applications")
        print("  4. Schedule Interview")

        print("\n--- Onboarding ---")
        print("  5. Active Onboardings")
        print("  6. Start New Onboarding")
        print("  7. Onboarding Templates")

        print("\n--- Admin Tools ---")
        print("  8. Document Approvals")
        print("  9. Access Card Management")
        print("  10. Key Management")
        print("  11. Visitor Management")
        print("  12. Interdepartmental Requests")

        print("\n--- Reports ---")
        print("  13. Staff Reports")
        print("  14. Department KPIs")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_job_postings()
        elif choice == '2':
            _create_job_posting(user_id)
        elif choice == '3':
            _view_applications()
        elif choice == '4':
            _schedule_interview(user_id)
        elif choice == '5':
            _active_onboardings()
        elif choice == '6':
            _start_onboarding(user_id)
        elif choice == '7':
            _onboarding_templates()
        elif choice == '8':
            _document_approvals(user_id)
        elif choice == '9':
            _access_card_management()
        elif choice == '10':
            _key_management()
        elif choice == '11':
            _visitor_management(user_id)
        elif choice == '12':
            _interdepartmental_requests(user_id)
        elif choice == '13':
            _staff_reports()
        elif choice == '14':
            _department_kpis()
        else:
            print("Invalid choice.")


# ==================== RECRUITMENT ====================

def _view_job_postings() -> None:
    """View job postings."""
    postings = RecruitmentManager.get_job_postings()
    print("\n" + "-" * 60)
    print("JOB POSTINGS")
    print("-" * 60)

    if postings:
        for p in postings:
            status = p.get('status', 'open').upper()
            print(f"\n  [{status}] {p.get('title')}")
            print(f"    Department: {p.get('department', 'N/A')}")
            print(f"    Type: {p.get('employment_type', 'N/A')}")
            print(f"    Posted: {p.get('posted_date', 'N/A')[:10]}")
            print(f"    Deadline: {p.get('closing_date', 'N/A')}")
            print(f"    Applications: {p.get('application_count', 0)}")
    else:
        print("No job postings found.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _create_job_posting(user_id: str) -> None:
    """Create a new job posting."""
    print("\n--- Create Job Posting ---")
    title = input("Job Title: ").strip()
    department = input("Department: ").strip()
    employment_type = input("Type (full_time/part_time/contract/temporary): ").strip()
    description = input("Description:\n").strip()
    requirements = input("Requirements:\n").strip()
    salary_range = input("Salary Range: ").strip()
    closing_date = input("Closing Date (YYYY-MM-DD): ").strip()

    if title and department:
        try:
            posting_id = RecruitmentManager.create_job_posting(
                title=title,
                department=department,
                employment_type=employment_type,
                description=description,
                requirements=requirements,
                salary_range=salary_range,
                closing_date=closing_date,
                created_by=user_id
            )
            print(f"\nJob posting created. ID: {posting_id}")
        except Exception as e:
            print(f"\nError: {e}")
    else:
        print("\nTitle and department are required.")

    input("Press Enter to continue...")


def _view_applications() -> None:
    """View job applications."""
    postings = RecruitmentManager.get_job_postings(status='open')
    if not postings:
        print("\nNo open job postings.")
        input("Press Enter to continue...")
        return

    print("\nSelect Job Posting:")
    for i, p in enumerate(postings, 1):
        print(f"  {i}. {p.get('title')} ({p.get('application_count', 0)} applications)")

    try:
        choice = int(input("\nSelect (0 for all): ").strip())
        posting_id = None
        if 1 <= choice <= len(postings):
            posting_id = postings[choice - 1]['posting_id']

        applications = RecruitmentManager.get_applications(posting_id=posting_id)

        print("\n" + "-" * 60)
        print("APPLICATIONS")
        print("-" * 60)

        if applications:
            for a in applications:
                status = a.get('status', 'received').upper()
                print(f"\n  [{status}] {a.get('applicant_name', 'N/A')}")
                print(f"    Position: {a.get('job_title', 'N/A')}")
                print(f"    Applied: {a.get('applied_date', 'N/A')[:10]}")
                print(f"    Email: {a.get('email', 'N/A')}")
        else:
            print("No applications found.")

        print("-" * 60)
    except ValueError:
        print("Invalid input.")

    input("\nPress Enter to continue...")


def _schedule_interview(user_id: str) -> None:
    """Schedule an interview."""
    applications = RecruitmentManager.get_applications(status='shortlisted')
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

            interview_date = input("Interview Date (YYYY-MM-DD HH:MM): ").strip()
            interview_type = input("Type (in_person/video/phone): ").strip() or 'in_person'
            location = input("Location/Link: ").strip()
            panel = input("Panel Members (comma-separated user IDs): ").strip()

            interview_id = RecruitmentManager.schedule_interview(
                application['application_id'],
                interview_date=interview_date,
                interview_type=interview_type,
                location=location,
                panel_members=panel.split(',') if panel else None,
                scheduled_by=user_id
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
    onboardings = OnboardingManager.get_active_onboardings()
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
            created_by=user_id
        )
        print(f"\nOnboarding started. ID: {onboarding_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _onboarding_templates() -> None:
    """View onboarding templates."""
    templates = OnboardingManager.get_templates()
    print("\n" + "-" * 60)
    print("ONBOARDING TEMPLATES")
    print("-" * 60)

    if templates:
        for t in templates:
            print(f"\n  {t.get('name')}")
            print(f"    Type: {t.get('employee_type', 'all')}")
            print(f"    Tasks: {t.get('task_count', 0)}")
            print(f"    Duration: {t.get('duration_days', 'N/A')} days")
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
                    employee_type=emp_type or 'all',
                    duration_days=int(duration) if duration else 30
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
        print(f"     Type: {d.get('document_type')} | Submitted: {d.get('submitted_date', 'N/A')[:10]}")
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


def _access_card_management() -> None:
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
            print(f"  [{status}] {c.get('card_number')} - {c.get('holder_name', 'N/A')}")
        print("-" * 50)

    elif choice == '2':
        user_id = input("User ID: ").strip()
        card_number = input("Card Number: ").strip()
        access_level = input("Access Level (basic/standard/full): ").strip()

        if user_id and card_number:
            try:
                card_id = AdminToolsManager.issue_access_card(
                    user_id, card_number, access_level=access_level
                )
                print(f"\nCard issued. ID: {card_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '3':
        card_number = input("Card Number to deactivate: ").strip()
        reason = input("Reason: ").strip()
        AdminToolsManager.deactivate_access_card(card_number, reason)
        print("\nCard deactivated.")

    elif choice == '4':
        card_number = input("Lost Card Number: ").strip()
        AdminToolsManager.report_lost_card(card_number)
        print("\nCard reported as lost and deactivated.")

    input("Press Enter to continue...")


def _key_management() -> None:
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
            print(f"    Issued: {k.get('issued_date', 'N/A')[:10]}")
        print("-" * 50)

    elif choice == '2':
        user_id = input("User ID: ").strip()
        key_number = input("Key Number: ").strip()
        location = input("Location/Room: ").strip()

        if user_id and key_number:
            try:
                key_id = AdminToolsManager.issue_key(user_id, key_number, location)
                print(f"\nKey issued. ID: {key_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '3':
        key_number = input("Key Number to return: ").strip()
        AdminToolsManager.return_key(key_number)
        print("\nKey returned.")

    elif choice == '4':
        key_number = input("Lost Key Number: ").strip()
        AdminToolsManager.report_lost_key(key_number)
        print("\nKey reported as lost.")

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
            status = 'IN' if v.get('checked_in') and not v.get('checked_out') else 'OUT'
            print(f"  [{status}] {v.get('visitor_name')}")
            print(f"    Visiting: {v.get('host_name', 'N/A')}")
            print(f"    Purpose: {v.get('purpose', 'N/A')}")
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
                    name, host_id,
                    company=company,
                    purpose=purpose,
                    expected_date=expected_date,
                    registered_by=user_id
                )
                print(f"\nVisitor registered. ID: {visitor_id}")
            except Exception as e:
                print(f"\nError: {e}")

    elif choice == '3':
        visitor_id = input("Visitor ID or Name: ").strip()
        badge_number = input("Badge Number: ").strip()
        AdminToolsManager.check_in_visitor(visitor_id, badge_number)
        print("\nVisitor checked in.")

    elif choice == '4':
        visitor_id = input("Visitor ID or Name: ").strip()
        AdminToolsManager.check_out_visitor(visitor_id)
        print("\nVisitor checked out.")

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
            print(f"    Submitted: {r.get('submitted_date', 'N/A')[:10]}")
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
                        AdminToolsManager.approve_request(req['request_id'], user_id)
                        print("\nRequest approved.")
                    elif action == 'R':
                        reason = input("Rejection reason: ").strip()
                        AdminToolsManager.reject_request(req['request_id'], user_id, reason)
                        print("\nRequest rejected.")
            except ValueError:
                pass
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
        report = EmployeeManager.get_headcount_report()
        print("\n" + "-" * 50)
        print("HEADCOUNT BY DEPARTMENT")
        print("-" * 50)
        if report:
            for dept, count in report.items():
                print(f"  {dept}: {count}")
        print("-" * 50)

    elif choice == '2':
        from university_system.modules.domain.staff_hr.services import LeaveManager
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
        from university_system.modules.domain.staff_hr.services import TrainingManager
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
        from university_system.modules.domain.staff_hr.services import AssetManager
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
        from university_system.modules.domain.staff_hr.services import TimeManager
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
    """View department KPIs."""
    kpis = RecruitmentManager.get_department_kpis()
    print("\n" + "-" * 60)
    print("DEPARTMENT KPIs")
    print("-" * 60)

    if kpis:
        for dept, metrics in kpis.items():
            print(f"\n[{dept}]")
            print(f"  Headcount: {metrics.get('headcount', 0)}")
            print(f"  Vacancies: {metrics.get('vacancies', 0)}")
            print(f"  Turnover Rate: {metrics.get('turnover_rate', 0):.1f}%")
            print(f"  Avg Tenure: {metrics.get('avg_tenure', 0):.1f} years")
            print(f"  Training Completion: {metrics.get('training_completion', 0):.1f}%")
    else:
        print("No KPI data available.")

    print("-" * 60)
    input("\nPress Enter to continue...")
