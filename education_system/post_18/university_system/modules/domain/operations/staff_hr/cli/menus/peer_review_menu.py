"""
Peer Review Menu - Submissions, review assignments and shared resources CLI.

Wired to PeerReviewManager (the same manager the peer review GUI uses).
"""

from datetime import datetime

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.peer_review_manager import (
    PeerReviewManager,
)


def display_peer_review_menu(user_id: str, is_admin: bool = False) -> None:
    """Display the peer review management menu."""
    while True:
        print("\n" + "=" * 60)
        print("PEER REVIEW MANAGEMENT")
        print("=" * 60)

        print("\n--- My Submissions ---")
        print("  1. View My Submissions")
        print("  2. New Submission")
        print("  3. Submit for Review")

        print("\n--- My Reviews ---")
        print("  4. My Review Assignments")
        print("  5. Start Review")
        print("  6. Submit Feedback")
        print("  7. Decline Assignment")

        print("\n--- Library ---")
        print("  8. Review Cycles")
        print("  9. Shared Resources")
        print("  10. Share Resource")
        print("  11. Rate Resource")

        if is_admin:
            print("\n--- Administration ---")
            print("  12. Create Review Cycle")
            print("  13. Activate Cycle")
            print("  14. Assign Reviewer")

        print("\n  0. Return")

        choice = input("\nEnter choice: ").strip()

        if choice == '0':
            break
        elif choice == '1':
            _my_submissions(user_id)
        elif choice == '2':
            _new_submission(user_id)
        elif choice == '3':
            _submit_for_review(user_id)
        elif choice == '4':
            _my_reviews(user_id)
        elif choice == '5':
            _start_review(user_id)
        elif choice == '6':
            _submit_feedback(user_id)
        elif choice == '7':
            _decline_assignment(user_id)
        elif choice == '8':
            _review_cycles()
        elif choice == '9':
            _shared_resources()
        elif choice == '10':
            _share_resource(user_id)
        elif choice == '11':
            _rate_resource(user_id)
        elif choice == '12' and is_admin:
            _create_cycle(user_id)
        elif choice == '13' and is_admin:
            _activate_cycle()
        elif choice == '14' and is_admin:
            _assign_reviewer(user_id)
        else:
            print("Invalid choice.")


def _my_submissions(user_id: str) -> None:
    """List the user's submissions."""
    subs = PeerReviewManager.get_submissions(submitter_id=user_id)
    print("\n" + "-" * 60)
    print("MY SUBMISSIONS")
    print("-" * 60)

    if subs:
        for s in subs:
            print(f"\n  #{s.get('submission_id')}  {s.get('title', '')}")
            print(f"    Cycle: {s.get('cycle_id', '')}  |  Version: {s.get('version', 1)}  |  "
                  f"Status: {(s.get('status') or '').replace('_', ' ').title()}")
    else:
        print("\n  No submissions.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _new_submission(user_id: str) -> None:
    """Create a new submission against an active cycle."""
    cycles = PeerReviewManager.get_cycles(status='active')
    if not cycles:
        print("\nNo active review cycles available.")
        input("Press Enter to continue...")
        return

    print("\nActive cycles:")
    for i, c in enumerate(cycles, 1):
        print(f"  {i}. #{c.get('cycle_id')}  {c.get('name', '')}")

    try:
        idx = int(input("\nSelect cycle (0 to abort): ").strip())
        if idx == 0 or not (1 <= idx <= len(cycles)):
            return
        cycle_id = cycles[idx - 1].get('cycle_id')

        title = input("Title: ").strip()
        description = input("Description: ").strip()
        material_type = input(
            "Material type (lecture_notes/assessment/syllabus/lab_manual/presentation/other) [lecture_notes]: "
        ).strip() or 'lecture_notes'
        course_code = input("Course code: ").strip()
        file_path = input("File path: ").strip()
        if not (title and description and course_code and file_path):
            print("\nTitle, description, course code and file path are required.")
            input("Press Enter to continue...")
            return
        file_name = file_path.replace('\\', '/').split('/')[-1]

        submission_id = PeerReviewManager.create_submission(
            cycle_id=cycle_id, submitter_id=user_id, title=title,
            description=description, material_type=material_type,
            course_code=course_code, file_path=file_path, file_name=file_name,
        )
        print(f"\nSubmission created. ID: {submission_id}")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _submit_for_review(user_id: str) -> None:
    """Submit a draft submission for review."""
    subs = PeerReviewManager.get_submissions(submitter_id=user_id)
    drafts = [s for s in subs if s.get('status', '').lower() == 'draft']
    if not drafts:
        print("\nNo draft submissions to submit.")
        input("Press Enter to continue...")
        return

    for i, s in enumerate(drafts, 1):
        print(f"  {i}. #{s.get('submission_id')}  {s.get('title', '')}")

    try:
        idx = int(input("\nSelect submission (0 to abort): ").strip())
        if 1 <= idx <= len(drafts):
            PeerReviewManager.submit_for_review(drafts[idx - 1]['submission_id'])
            print("\nSubmission sent for review.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _my_reviews(user_id: str) -> None:
    """List the user's review assignments."""
    assignments = PeerReviewManager.get_assignments(reviewer_id=user_id)
    print("\n" + "-" * 60)
    print("MY REVIEW ASSIGNMENTS")
    print("-" * 60)

    if assignments:
        for a in assignments:
            print(f"\n  Assignment #{a.get('assignment_id')}  Submission: {a.get('submission_id')}")
            print(f"    Due: {a.get('due_date', '')}  |  "
                  f"Status: {(a.get('status') or '').replace('_', ' ').title()}")
    else:
        print("\n  No review assignments.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _pick_assignment(user_id: str, statuses=None):
    """Prompt to select one of the user's assignments. Returns the assignment dict or None."""
    assignments = PeerReviewManager.get_assignments(reviewer_id=user_id)
    if statuses:
        assignments = [a for a in assignments if a.get('status', '').lower() in statuses]
    if not assignments:
        print("\nNo matching assignments.")
        return None

    for i, a in enumerate(assignments, 1):
        print(f"  {i}. Assignment #{a.get('assignment_id')}  Submission {a.get('submission_id')} "
              f"[{a.get('status', '')}]")

    try:
        idx = int(input("\nSelect assignment (0 to abort): ").strip())
        if 1 <= idx <= len(assignments):
            return assignments[idx - 1]
    except ValueError:
        pass
    return None


def _start_review(user_id: str) -> None:
    """Start a review assignment."""
    assignment = _pick_assignment(user_id, statuses={'assigned'})
    if not assignment:
        input("\nPress Enter to continue...")
        return
    try:
        PeerReviewManager.start_review(assignment['assignment_id'])
        print("\nReview started.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _submit_feedback(user_id: str) -> None:
    """Submit structured feedback for an assignment."""
    assignment = _pick_assignment(user_id, statuses={'assigned', 'in_progress'})
    if not assignment:
        input("\nPress Enter to continue...")
        return

    print("\n--- Submit Feedback (ratings 1-5) ---")
    try:
        overall = int(input("Overall rating: ").strip())
        content_quality = int(input("Content quality: ").strip())
        clarity = int(input("Clarity: ").strip())
        alignment = int(input("Alignment with outcomes: ").strip())
        engagement = int(input("Engagement potential: ").strip())
        for val in (overall, content_quality, clarity, alignment, engagement):
            if not 1 <= val <= 5:
                raise ValueError("Ratings must be between 1 and 5")

        strengths = input("Strengths: ").strip()
        improvements = input("Improvements: ").strip()
        comments = input("Detailed comments: ").strip()
        recommendation = input(
            "Recommendation (approve/minor_revisions/major_revisions/reject) [approve]: "
        ).strip() or 'approve'

        feedback_id = PeerReviewManager.submit_feedback(
            assignment_id=assignment['assignment_id'],
            submission_id=assignment['submission_id'],
            reviewer_id=user_id, overall_rating=overall,
            content_quality=content_quality, clarity=clarity,
            alignment_with_outcomes=alignment, engagement_potential=engagement,
            strengths=strengths, improvements=improvements,
            detailed_comments=comments, recommendation=recommendation,
        )
        print(f"\nFeedback submitted. ID: {feedback_id}")
    except ValueError as e:
        print(f"\nInvalid input: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _decline_assignment(user_id: str) -> None:
    """Decline a review assignment."""
    assignment = _pick_assignment(user_id, statuses={'assigned', 'in_progress'})
    if not assignment:
        input("\nPress Enter to continue...")
        return
    try:
        PeerReviewManager.decline_assignment(assignment['assignment_id'])
        print("\nAssignment declined.")
    except Exception as e:
        print(f"\nError: {e}")
    input("Press Enter to continue...")


def _review_cycles() -> None:
    """List all review cycles."""
    cycles = PeerReviewManager.get_cycles()
    print("\n" + "-" * 60)
    print("REVIEW CYCLES")
    print("-" * 60)

    if cycles:
        for c in cycles:
            print(f"\n  #{c.get('cycle_id')}  {c.get('name', '')}  "
                  f"({(c.get('cycle_type') or '').replace('_', ' ').title()})")
            print(f"    Dept: {c.get('department', '')}  |  "
                  f"{c.get('start_date', '')} to {c.get('end_date', '')}  |  "
                  f"Status: {(c.get('status') or '').replace('_', ' ').title()}")
    else:
        print("\n  No review cycles.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _shared_resources() -> None:
    """List shared resources."""
    resources = PeerReviewManager.get_resources()
    print("\n" + "-" * 60)
    print("SHARED RESOURCES")
    print("-" * 60)

    if resources:
        for r in resources:
            count = r.get('rating_count', 0) or 0
            avg = f"{(r.get('rating_sum', 0) or 0) / count:.1f}" if count else 'N/A'
            print(f"\n  #{r.get('resource_id')}  {r.get('title', '')}  "
                  f"({(r.get('resource_type') or '').replace('_', ' ').title()})")
            print(f"    Subject: {r.get('subject_area', '')}  |  Rating: {avg}  |  "
                  f"Downloads: {r.get('download_count', 0)}  |  "
                  f"Approved: {'Yes' if r.get('is_approved') else 'No'}")
    else:
        print("\n  No shared resources.")

    print("-" * 60)
    input("\nPress Enter to continue...")


def _share_resource(user_id: str) -> None:
    """Share a new resource."""
    print("\n--- Share Resource ---")
    title = input("Title: ").strip()
    description = input("Description: ").strip()
    resource_type = input(
        "Type (template/rubric/example/lecture_notes/other) [template]: "
    ).strip() or 'template'
    subject_area = input("Subject area: ").strip()
    course_code = input("Course code: ").strip()
    file_path = input("File path: ").strip()

    if not (title and description and subject_area and course_code and file_path):
        print("\nAll fields are required.")
        input("Press Enter to continue...")
        return
    file_name = file_path.replace('\\', '/').split('/')[-1]

    try:
        resource_id = PeerReviewManager.share_resource(
            title=title, description=description, resource_type=resource_type,
            subject_area=subject_area, course_code=course_code,
            file_path=file_path, file_name=file_name, shared_by=user_id,
        )
        print(f"\nResource shared. ID: {resource_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _rate_resource(user_id: str) -> None:
    """Rate a shared resource."""
    resources = PeerReviewManager.get_resources()
    if not resources:
        print("\nNo resources to rate.")
        input("Press Enter to continue...")
        return

    for i, r in enumerate(resources, 1):
        print(f"  {i}. #{r.get('resource_id')}  {r.get('title', '')}")

    try:
        idx = int(input("\nSelect resource (0 to abort): ").strip())
        if idx == 0 or not (1 <= idx <= len(resources)):
            return
        resource = resources[idx - 1]
        rating = int(input("Rating (1-5): ").strip())
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        comment = input("Comment (optional): ").strip() or None

        PeerReviewManager.rate_resource(
            resource_id=resource['resource_id'], user_id=user_id,
            rating=rating, comment=comment,
        )
        print("\nRating submitted.")
    except ValueError as e:
        print(f"\nInvalid input: {e}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _create_cycle(user_id: str) -> None:
    """Create a review cycle (admin)."""
    print("\n--- Create Review Cycle ---")
    name = input("Name: ").strip()
    if not name:
        print("\nName is required.")
        input("Press Enter to continue...")
        return
    description = input("Description: ").strip()
    cycle_type = input("Type (annual/mid_term/ad_hoc) [annual]: ").strip() or 'annual'
    department = input("Department: ").strip()
    start_date = input(f"Start date (YYYY-MM-DD) [{datetime.now().strftime('%Y-%m-%d')}]: ").strip() \
        or datetime.now().strftime('%Y-%m-%d')
    end_date = input("End date (YYYY-MM-DD): ").strip()

    try:
        cycle_id = PeerReviewManager.create_cycle(
            name=name, description=description, cycle_type=cycle_type,
            department=department, start_date=start_date, end_date=end_date,
            created_by=user_id,
        )
        print(f"\nReview cycle created. ID: {cycle_id}")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _activate_cycle() -> None:
    """Activate a draft review cycle (admin)."""
    cycles = PeerReviewManager.get_cycles()
    draft = [c for c in cycles if c.get('status', '').lower() == 'draft']
    if not draft:
        print("\nNo draft cycles to activate.")
        input("Press Enter to continue...")
        return

    for i, c in enumerate(draft, 1):
        print(f"  {i}. #{c.get('cycle_id')}  {c.get('name', '')}")

    try:
        idx = int(input("\nSelect cycle (0 to abort): ").strip())
        if 1 <= idx <= len(draft):
            PeerReviewManager.activate_cycle(draft[idx - 1]['cycle_id'])
            print("\nCycle activated.")
    except ValueError:
        print("\nInvalid input.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")


def _assign_reviewer(user_id: str) -> None:
    """Assign a reviewer to a submission (admin)."""
    submission_id = input("Submission ID: ").strip()
    reviewer_id = input("Reviewer user ID: ").strip()
    due_date = input("Due date (YYYY-MM-DD): ").strip()

    if not (submission_id and reviewer_id and due_date):
        print("\nSubmission ID, reviewer ID and due date are required.")
        input("Press Enter to continue...")
        return

    try:
        assignment_id = PeerReviewManager.assign_reviewer(
            submission_id=int(submission_id), reviewer_id=reviewer_id,
            assigned_by=user_id, due_date=due_date,
        )
        print(f"\nReviewer assigned. Assignment ID: {assignment_id}")
    except ValueError:
        print("\nInvalid submission ID.")
    except Exception as e:
        print(f"\nError: {e}")

    input("Press Enter to continue...")
