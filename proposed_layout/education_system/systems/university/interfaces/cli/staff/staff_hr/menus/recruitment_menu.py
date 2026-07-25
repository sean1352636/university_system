"""
Recruitment Menu - Job posting and applicant management CLI.
"""

from education_system.systems.university.domain.staff.staff_hr.services import RecruitmentManager


def display_recruitment_menu(user_id: str = None) -> None:
    """Display recruitment management menu."""
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
        print("  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _view_active_postings()
        elif choice == '2':
            _create_posting(user_id)
        elif choice == '3':
            _edit_posting()
        elif choice == '4':
            _close_posting()
        elif choice == '5':
            _view_applicants()
        elif choice == '6':
            _review_applicant()
        elif choice == '7':
            _schedule_interview()
        elif choice == '8':
            _update_applicant_status()
        elif choice == '9':
            _recruitment_stats()
        else:
            print("Invalid choice.")


def _view_active_postings() -> None:
    """View active job postings."""
    print("\n--- Active Job Postings ---")
    try:
        postings = RecruitmentManager.get_active_postings()
        if postings:
            for p in postings:
                print(f"\nID: {p.get('id')}")
                print(f"  Title: {p.get('title', 'N/A')}")
                print(f"  Department: {p.get('department', 'N/A')}")
                print(f"  Posted: {p.get('posted_date', 'N/A')}")
                print(f"  Applicants: {p.get('applicant_count', 0)}")
        else:
            print("No active job postings.")
    except Exception as e:
        print(f"Error loading postings: {e}")

    input("\nPress Enter to continue...")


def _create_posting(user_id: str) -> None:
    """Create a new job posting."""
    print("\n--- Create Job Posting ---")
    try:
        title = input("Job Title: ").strip()
        if not title:
            print("Cancelled.")
            return

        department = input("Department: ").strip()
        description = input("Job Description: ").strip()
        requirements = input("Requirements: ").strip()
        salary_range = input("Salary Range (optional): ").strip()

        posting_id = RecruitmentManager.create_posting(
            title=title,
            department=department,
            description=description,
            requirements=requirements,
            salary_range=salary_range or None,
            created_by=user_id
        )
        print(f"\nJob posting created. ID: {posting_id}")
    except Exception as e:
        print(f"Error creating posting: {e}")

    input("Press Enter to continue...")


def _edit_posting() -> None:
    """Edit an existing job posting."""
    posting_id = input("\nEnter posting ID to edit: ").strip()
    if not posting_id:
        print("Cancelled.")
        return

    try:
        posting = RecruitmentManager.get_posting(posting_id)
        if not posting:
            print("Posting not found.")
            return

        print(f"\nCurrent Title: {posting.get('title')}")
        new_title = input("New Title (Enter to keep): ").strip()

        print(f"Current Description: {posting.get('description')}")
        new_desc = input("New Description (Enter to keep): ").strip()

        RecruitmentManager.update_posting(
            posting_id,
            title=new_title or None,
            description=new_desc or None
        )
        print("Posting updated.")
    except Exception as e:
        print(f"Error updating posting: {e}")

    input("Press Enter to continue...")


def _close_posting() -> None:
    """Close a job posting."""
    posting_id = input("\nEnter posting ID to close: ").strip()
    if not posting_id:
        print("Cancelled.")
        return

    try:
        RecruitmentManager.close_posting(posting_id)
        print("Posting closed.")
    except Exception as e:
        print(f"Error closing posting: {e}")

    input("Press Enter to continue...")


def _view_applicants() -> None:
    """View all applicants."""
    print("\n--- All Applicants ---")
    posting_id = input("Filter by posting ID (Enter for all): ").strip()

    try:
        applicants = RecruitmentManager.get_applicants(posting_id or None)
        if applicants:
            for a in applicants:
                print(f"\nID: {a.get('id')}")
                print(f"  Name: {a.get('name', 'N/A')}")
                print(f"  Position: {a.get('position', 'N/A')}")
                print(f"  Status: {a.get('status', 'N/A')}")
                print(f"  Applied: {a.get('applied_date', 'N/A')}")
        else:
            print("No applicants found.")
    except Exception as e:
        print(f"Error loading applicants: {e}")

    input("\nPress Enter to continue...")


def _review_applicant() -> None:
    """Review an applicant's details."""
    applicant_id = input("\nEnter applicant ID: ").strip()
    if not applicant_id:
        print("Cancelled.")
        return

    try:
        applicant = RecruitmentManager.get_applicant(applicant_id)
        if applicant:
            print("\n--- Applicant Details ---")
            print(f"Name: {applicant.get('name', 'N/A')}")
            print(f"Email: {applicant.get('email', 'N/A')}")
            print(f"Phone: {applicant.get('phone', 'N/A')}")
            print(f"Position: {applicant.get('position', 'N/A')}")
            print(f"Status: {applicant.get('status', 'N/A')}")
            print(f"Resume: {applicant.get('resume_path', 'N/A')}")
            print(f"Notes: {applicant.get('notes', 'N/A')}")
        else:
            print("Applicant not found.")
    except Exception as e:
        print(f"Error loading applicant: {e}")

    input("\nPress Enter to continue...")


def _schedule_interview() -> None:
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
            applicant_id=applicant_id,
            interview_date=date,
            interview_time=time,
            interviewer=interviewer,
            location=location
        )
        print("Interview scheduled.")
    except Exception as e:
        print(f"Error scheduling interview: {e}")

    input("Press Enter to continue...")


def _update_applicant_status() -> None:
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

    try:
        RecruitmentManager.update_applicant_status(applicant_id, status_map[choice])
        print("Status updated.")
    except Exception as e:
        print(f"Error updating status: {e}")

    input("Press Enter to continue...")


def _recruitment_stats() -> None:
    """View recruitment statistics."""
    print("\n--- Recruitment Statistics ---")
    try:
        stats = RecruitmentManager.get_statistics()
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
