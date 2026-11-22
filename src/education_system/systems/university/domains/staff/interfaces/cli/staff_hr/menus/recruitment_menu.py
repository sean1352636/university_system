"""
Recruitment Menu - Job posting and applicant management CLI.

Options 10-15 take an accepted applicant to their first day
(``staff_hr.hiring``): pre-employment checks, references, offers, the hire
itself, the checks each job type requires, and the HR reminders.
"""

from education_system.systems.university.domains.staff.domain.staff_hr import access, hiring
from education_system.systems.university.domains.staff.domain.staff_hr.services import RecruitmentManager


def _actor(user_id):
    """The signed-in session when it is ``user_id``'s; otherwise just the name."""
    try:
        from education_system.systems.university.infrastructure.shared_context import get_auth
        auth = get_auth()
        if access.username_of(auth) == user_id:
            return auth
    except Exception:
        pass
    # not the session's: the person user_id names, with their university role
    from education_system.systems.university.domains.staff.domain.staff_hr import leave_rules
    return leave_rules.actor_for(user_id) or {'username': user_id}


def display_recruitment_menu(user_id: str = None, actor=None) -> None:
    """Display recruitment management menu."""
    actor = actor or _actor(user_id)
    while True:
        print("\n" + "=" * 60)
        print("RECRUITMENT MANAGEMENT")
        print("=" * 60)

        print("\n--- Job Postings ---")
        print("  1. View Active Postings")
        print("  2. Create Job Posting")
        print("  3. Edit Job Posting")
        print("  4. Close Job Posting")

        print("\n--- Applicants ---")
        print("  5. View All Applicants")
        print("  6. Review Applicant")
        print("  7. Schedule Interview")
        print("  8. Update Applicant Status")

        print("\n--- Reports ---")
        print("  9. Recruitment Statistics")

        print("\n--- Hiring ---")
        print(" 10. Pre-employment Checks")
        print(" 11. References")
        print(" 12. Offers")
        print(" 13. Hire (create staff record)")
        print(" 14. Required Checks by Job Type")
        print(" 15. Send HR Reminders Now")
        print("  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_active_postings(actor)
        elif choice == '2':
            _create_posting(user_id, actor)
        elif choice == '3':
            _edit_posting(actor)
        elif choice == '4':
            _close_posting(actor)
        elif choice == '5':
            _view_applicants(actor)
        elif choice == '6':
            _review_applicant(actor)
        elif choice == '7':
            _schedule_interview(actor)
        elif choice == '8':
            _update_applicant_status(actor)
        elif choice == '9':
            _recruitment_stats(actor)
        elif choice in _HIRING:
            if not hiring.can_hire(actor):
                print("Only recruitment or HR can manage hiring.")
                continue
            try:
                _HIRING[choice](actor)
            except (ValueError, PermissionError) as e:
                print(f"\n{e}")
                input("Press Enter to continue...")
        else:
            print("Invalid choice.")


def _view_active_postings(actor) -> None:
    """View active job postings."""
    print("\n--- Active Job Postings ---")
    try:
        postings = RecruitmentManager.get_active_postings(actor=actor)
        if postings:
            for p in postings:
                print(f"\nID: {p.get('posting_id')}")
                print(f"  Title: {p.get('job_title', 'N/A')}")
                print(f"  Department: {p.get('department', 'N/A')}")
                print(f"  Posted: {p.get('post_date', 'N/A')}")
                print(f"  Applicants: {p.get('applicant_count', 0)}")
        else:
            print("No active job postings.")
    except Exception as e:
        print(f"Error loading postings: {e}")

    input("\nPress Enter to continue...")


def _create_posting(user_id: str, actor=None) -> None:
    """Create a new job posting."""
    print("\n--- Create Job Posting ---")
    try:
        title = input("Job Title: ").strip()
        if not title:
            print("Cancelled.")
            return

        department = input("Department: ").strip()
        job_type = input("Job Type [permanent/fixed_term/part_time/temporary] "
                         "(Enter = permanent): ").strip() or 'permanent'
        description = input("Job Description: ").strip()
        requirements = input("Requirements: ").strip()
        salary_range = input("Salary Range (optional): ").strip()

        posting_id = RecruitmentManager.create_posting(
            posted_by=user_id,
            job_title=title,
            department=department,
            job_type=job_type,
            description=description,
            requirements=requirements,
            salary_range=salary_range or None,
            posted_by_name=user_id, actor=actor
        )
        print(f"\nJob posting created (draft). ID: {posting_id}")
        if input("Publish it now? (y/n): ").strip().lower() == 'y':
            RecruitmentManager.publish_posting(posting_id, actor=actor)
            print("Posting published.")
    except Exception as e:
        print(f"Error creating posting: {e}")

    input("Press Enter to continue...")


def _edit_posting(actor) -> None:
    """Edit an existing job posting."""
    posting_id = input("\nEnter posting ID to edit: ").strip()
    if not posting_id:
        print("Cancelled.")
        return

    try:
        posting = RecruitmentManager.get_posting(int(posting_id), actor=actor)
        if not posting:
            print("Posting not found.")
            return

        print(f"\nCurrent Title: {posting.get('job_title')}")
        new_title = input("New Title (Enter to keep): ").strip()

        print(f"Current Description: {posting.get('description')}")
        new_desc = input("New Description (Enter to keep): ").strip()

        print(f"Current Closing Date: {posting.get('closing_date')}")
        new_close = input("New Closing Date YYYY-MM-DD (Enter to keep): ").strip()

        if RecruitmentManager.update_posting(int(posting_id), job_title=new_title or None,
                                             description=new_desc or None,
                                             closing_date=new_close or None, actor=actor):
            print("Posting updated.")
        else:
            print("Nothing changed.")
    except Exception as e:
        print(f"Error updating posting: {e}")

    input("Press Enter to continue...")


def _close_posting(actor) -> None:
    """Close a job posting."""
    posting_id = input("\nEnter posting ID to close: ").strip()
    if not posting_id:
        print("Cancelled.")
        return

    try:
        RecruitmentManager.close_posting(int(posting_id), actor=actor)
        print("Posting closed.")
    except Exception as e:
        print(f"Error closing posting: {e}")

    input("Press Enter to continue...")


def _view_applicants(actor) -> None:
    """View all applicants."""
    print("\n--- All Applicants ---")
    posting_id = input("Filter by posting ID (Enter for all): ").strip()

    try:
        applicants = RecruitmentManager.get_applications(
            posting_id=int(posting_id) if posting_id else None, limit=500, actor=actor)
        if applicants:
            for a in applicants:
                print(f"\nID: {a.get('application_id')}")
                print(f"  Name: {a.get('applicant_name', 'N/A')}")
                print(f"  Position: {a.get('job_title', 'N/A')}")
                print(f"  Status: {a.get('status', 'N/A')}")
                print(f"  Applied: {a.get('application_date', 'N/A')}")
        else:
            print("No applicants found.")
    except Exception as e:
        print(f"Error loading applicants: {e}")

    input("\nPress Enter to continue...")


def _review_applicant(actor) -> None:
    """Review an applicant's details."""
    applicant_id = input("\nEnter applicant ID: ").strip()
    if not applicant_id:
        print("Cancelled.")
        return

    try:
        applicant = RecruitmentManager.get_application(int(applicant_id), actor=actor)
        if applicant:
            print("\n--- Applicant Details ---")
            print(f"Name: {applicant.get('applicant_name', 'N/A')}")
            print(f"Email: {applicant.get('applicant_email', 'N/A')}")
            print(f"Phone: {applicant.get('applicant_phone', 'N/A')}")
            print(f"Position: {applicant.get('job_title', 'N/A')}")
            print(f"Status: {applicant.get('status', 'N/A')}")
            print(f"Resume: {applicant.get('cv_path', 'N/A')}")
            print(f"Notes: {applicant.get('notes', 'N/A')}")
            interviews = RecruitmentManager.get_interviews(application_id=int(applicant_id), actor=actor)
            for i in interviews:
                print(f"Interview {i.get('interview_date')} {i.get('interview_time')}: "
                      f"{i.get('status')} - {i.get('recommendation') or 'no recommendation yet'}")
        else:
            print("Applicant not found.")
    except Exception as e:
        print(f"Error loading applicant: {e}")

    input("\nPress Enter to continue...")


def _schedule_interview(actor) -> None:
    """Schedule an interview."""
    applicant_id = input("\nEnter applicant ID: ").strip()
    if not applicant_id:
        print("Cancelled.")
        return

    try:
        date = input("Interview Date (YYYY-MM-DD): ").strip()
        time = input("Interview Time (HH:MM): ").strip()
        interviewer = input("Interviewer: ").strip()
        location = input("Location/Link: ").strip()

        RecruitmentManager.schedule_interview(
            application_id=int(applicant_id),
            interview_date=date,
            interview_time=time,
            interviewers=interviewer,
            location=location, actor=actor
        )
        print("Interview scheduled.")
    except Exception as e:
        print(f"Error scheduling interview: {e}")

    input("Press Enter to continue...")


def _update_applicant_status(actor) -> None:
    """Update applicant status."""
    applicant_id = input("\nEnter applicant ID: ").strip()
    if not applicant_id:
        print("Cancelled.")
        return

    print("\nStatus options:")
    print("  1. Under Review")
    print("  2. Interview Scheduled")
    print("  3. Interviewed")
    print("  4. Offer Extended")
    print("  5. Hired")
    print("  6. Rejected")

    status_map = {
        '1': 'under_review',
        '2': 'interview_scheduled',
        '3': 'interviewed',
        '4': 'offer_extended',
        '5': 'hired',
        '6': 'rejected'
    }

    choice = input("Select new status: ").strip()
    if choice not in status_map:
        print("Invalid status.")
        return
    if choice == '4':
        print("Offers are made from 12. Offers (salary, start date, conditions).")
        input("Press Enter to continue...")
        return
    if choice == '5':
        print("Hires are made from 13. Hire, once the offer is accepted and checks clear.")
        input("Press Enter to continue...")
        return

    try:
        RecruitmentManager.update_application_status(int(applicant_id), status_map[choice], actor=actor)
        print("Status updated.")
    except Exception as e:
        print(f"Error updating status: {e}")

    input("Press Enter to continue...")


def _recruitment_stats(actor) -> None:
    """View recruitment statistics."""
    print("\n--- Recruitment Statistics ---")
    try:
        stats = RecruitmentManager.get_statistics(actor=actor)
        if stats:
            print(f"Active Postings: {stats.get('active_postings', 0)}")
            print(f"Total Applicants: {stats.get('total_applicants', 0)}")
            print(f"Pending Reviews: {stats.get('pending_reviews', 0)}")
            print(f"Interviews Scheduled: {stats.get('interviews_scheduled', 0)}")
            print(f"Offers Extended: {stats.get('offers_extended', 0)}")
            print(f"Hired This Month: {stats.get('hired_this_month', 0)}")
        else:
            print("No statistics available.")
    except Exception as e:
        print(f"Error loading statistics: {e}")

    input("\nPress Enter to continue...")


# ── hiring ──────────────────────────────────────────────────────────────


def _ask_id(label: str):
    text = input(f"\n{label}: ").strip()
    if not text:
        print("Cancelled.")
        return None
    if not text.isdigit():
        raise ValueError(f"{label} must be a number")
    return int(text)


def _pick(label: str, options) -> str:
    print(f"{label}: " + ", ".join(f"{n}. {o}" for n, o in enumerate(options, 1)))
    choice = input("Select: ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(options):
        raise ValueError("Invalid choice")
    return options[int(choice) - 1]


def _show_status(actor, application_id: int) -> None:
    state = hiring.check_status(actor, application_id)
    print(f"\nRequired for '{state['job_type'] or 'any job'}': "
          + ", ".join(state['required']))
    for check, status in state['checks'].items():
        print(f"  {check:<15} {status}")
    refs = state['references']
    print(f"  references: {refs['satisfactory']} satisfactory / {refs['requested']} requested"
          f" (need {hiring.REFERENCES_REQUIRED})")
    print("All required checks cleared." if state['cleared']
          else "Outstanding: " + ", ".join(state['outstanding']))


def _checks_menu(actor) -> None:
    """Start and record pre-employment checks."""
    print("\n--- Pre-employment Checks ---")
    application_id = _ask_id("Application ID")
    if application_id is None:
        return
    for row in hiring.list_checks(actor, application_id=application_id):
        extra = (f" follow-up {row['follow_up_date']}" if row.get('follow_up_date') else '') + \
            (f" re-check {row['recheck_date']}" if row.get('recheck_date') else '')
        print(f"  {row['check_type']:<15} {row['status']:<12}{extra}")
    _show_status(actor, application_id)
    print("\n  1. Start the required checks  2. Record a check  0. Back")
    action = input("Select: ").strip()
    if action == '1':
        created = hiring.start_checks(actor, application_id)
        print("Started: " + (", ".join(created) or "nothing new"))
    elif action == '2':
        check = _pick("Check", list(hiring.CHECK_TYPES))
        status = _pick("Status", list(hiring.CHECK_STATUSES))
        fields = {}
        if check == 'right_to_work':
            fields['document_type'] = _pick("Document", list(hiring.RTW_DOCUMENTS))
            if fields['document_type'] == 'share_code':
                fields['share_code'] = input("Share code: ").strip()
            fields['check_date'] = input("Check date YYYY-MM-DD (Enter = today): ").strip()
            fields['follow_up_date'] = input("Follow-up / permission expiry date "
                                             "(Enter if unlimited): ").strip()
        elif check == 'dbs':
            fields['dbs_level'] = _pick("DBS level", list(hiring.DBS_LEVELS))
            fields['certificate_number'] = input("Certificate number: ").strip()
            fields['issue_date'] = input("Issue date YYYY-MM-DD: ").strip()
            fields['update_service'] = input("On the update service? (y/n): ").strip().lower()
            fields['recheck_date'] = input("Re-check date (Enter = default): ").strip()
        else:
            fields['details'] = input("Details: ").strip()
        fields['notes'] = input("Notes: ").strip()
        hiring.record_check(actor, application_id, check, status, **fields)
        print("Check recorded.")
        _show_status(actor, application_id)
    input("\nPress Enter to continue...")


def _references_menu(actor) -> None:
    """Request and record references."""
    print("\n--- References ---")
    application_id = _ask_id("Application ID")
    if application_id is None:
        return
    for r in hiring.list_references(actor, application_id):
        sat = {1: 'satisfactory', 0: 'NOT satisfactory'}.get(r.get('satisfactory'), '')
        print(f"  #{r['reference_id']} {r['referee_name']} <{r.get('referee_email') or ''}> "
              f"{r['status']} {sat}")
    print("\n  1. Request a reference (e-mails the referee)  2. Record a reference  0. Back")
    action = input("Select: ").strip()
    if action == '1':
        ref_id = hiring.request_reference(actor, application_id,
                                          input("Referee name: ").strip(),
                                          input("Referee e-mail: ").strip(),
                                          input("Relationship: ").strip())
        print(f"Reference #{ref_id} requested.")
    elif action == '2':
        ref_id = _ask_id("Reference #")
        if ref_id is None:
            return
        status = _pick("Status", ['received', 'declined'])
        satisfactory = None
        if status == 'received':
            satisfactory = input("Satisfactory? (y/n): ").strip().lower() == 'y'
        hiring.record_reference(actor, ref_id, status=status, satisfactory=satisfactory,
                                content=input("Summary / content: ").strip(),
                                notes=input("Notes: ").strip())
        print("Reference recorded.")
    input("\nPress Enter to continue...")


def _offers_menu(actor) -> None:
    """Make, accept, decline, withdraw offers and confirm start dates."""
    print("\n--- Offers ---")
    for o in hiring.list_offers(actor)[:30]:
        print(f"  #{o['offer_id']} app {o['application_id']} {o.get('applicant_name') or ''}: "
              f"{o['offer_type']} {o['status']} start {o.get('start_date') or '-'}"
              + (" (confirmed)" if o.get('start_confirmed') else ''))
    print("\n  1. Make an offer  2. Accepted  3. Declined  4. Withdraw  "
          "5. Confirm start date  0. Back")
    action = input("Select: ").strip()
    if action == '1':
        application_id = _ask_id("Application ID")
        if application_id is None:
            return
        offer_id = hiring.make_offer(
            actor, application_id,
            offer_type=_pick("Offer type", list(hiring.OFFER_TYPES)),
            salary=input("Full-time annual salary: ").strip(),
            grade=input("Grade (optional): ").strip(),
            start_date=input("Start date YYYY-MM-DD: ").strip(),
            fte=input("FTE (Enter = 1.0): ").strip() or 1.0,
            end_date=input("End date (fixed term only): ").strip(),
            manager_id=input("Line manager username (Enter = hiring manager): ").strip(),
            conditions=input("Conditions (Enter = the required checks): ").strip())
        print(f"Offer #{offer_id} made and e-mailed to the applicant.")
    elif action in ('2', '3', '4', '5'):
        offer_id = _ask_id("Offer #")
        if offer_id is None:
            return
        if action == '2':
            hiring.accept_offer(actor, offer_id, input("Note: ").strip())
            print("Offer accepted.")
        elif action == '3':
            hiring.decline_offer(actor, offer_id, input("Note: ").strip())
            print("Offer declined.")
        elif action == '4':
            hiring.withdraw_offer(actor, offer_id, input("Reason: ").strip())
            print("Offer withdrawn; the applicant has been told.")
        else:
            offer = hiring.confirm_start_date(
                actor, offer_id, input("Start date (Enter = as offered): ").strip())
            print(f"Start date {offer['start_date']} confirmed; the offer is unconditional.")
    input("\nPress Enter to continue...")


def _hire_menu(actor) -> None:
    """Turn an accepted offer into a member of staff."""
    print("\n--- Hire ---")
    offer_id = _ask_id("Accepted offer #")
    if offer_id is None:
        return
    offer = hiring.get_offer(actor, offer_id)
    _show_status(actor, offer['application_id'])
    username = input("Username for the new account (Enter = automatic): ").strip()
    template = input("Onboarding template ID (Enter = automatic): ").strip()
    if input("Create the staff record, contract and onboarding now? (y/n): "
             ).strip().lower() != 'y':
        print("Cancelled.")
        return
    result = hiring.hire(actor, offer_id, username=username or None,
                         onboarding_template_id=template or None)
    print(f"\nHired as {result['username']}"
          + (" (new account)" if result['account_created'] else ''))
    print(f"Contract #{result['contract_id']}; onboarding "
          f"{result.get('onboarding_assignment_id') or 'not assigned'}")
    for w in result['warnings']:
        print(f"  ! {w}")
    input("\nPress Enter to continue...")


def _requirements_menu(actor) -> None:
    """Which checks each job type must clear."""
    print("\n--- Required Checks by Job Type ---")
    for job_type, checks in hiring.list_requirements(actor).items():
        print(f"  {job_type:<12} {', '.join(checks)}")
    job_type = input("\nJob type to change ('*' = every job, Enter = back): ").strip()
    if not job_type:
        return
    print("Checks: " + ", ".join(hiring.REQUIREMENT_TYPES))
    checks = [c.strip() for c in input("Required checks (comma separated, Enter = none): "
                                       ).split(',') if c.strip()]
    print("Now: " + (", ".join(hiring.set_required_checks(actor, job_type, checks)) or 'none'))
    input("\nPress Enter to continue...")


def _reminders_now(actor) -> None:
    """Send the daily HR reminders now (HR only; each is sent once anyway)."""
    if not access.is_hr(actor):
        print("Only HR can send the reminders by hand.")
        return
    from education_system.systems.university.domains.staff.domain.staff_hr import reminders
    result = reminders.run()
    print("\n" + "\n".join(f"  {k}: {v}" for k, v in result.items()))
    input("\nPress Enter to continue...")


_HIRING = {
    '10': _checks_menu,
    '11': _references_menu,
    '12': _offers_menu,
    '13': _hire_menu,
    '14': _requirements_menu,
    '15': _reminders_now,
}
