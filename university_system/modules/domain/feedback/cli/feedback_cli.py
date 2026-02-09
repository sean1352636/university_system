"""
Feedback & Suggestion Box CLI Interface

Provides command-line interface for:
- Submitting feedback and suggestions
- Browsing and voting on suggestions
- Tracking submission status
- Viewing responses
"""

from typing import Optional
from datetime import datetime
from university_system.modules.domain.feedback.services.feedback_service import FeedbackService
from university_system.infrastructure.shared_context import get_auth


class FeedbackCLI:
    """CLI interface for feedback and suggestion system"""

    def __init__(self):
        """Initialize the CLI"""
        self.service = FeedbackService()
        self.auth = get_auth()

    def run(self):
        """Main CLI menu"""
        while True:
            self._display_header()
            choice = self._get_main_menu_choice()

            if choice == '1':
                self._submit_feedback()
            elif choice == '2':
                self._submit_suggestion()
            elif choice == '3':
                self._browse_suggestions()
            elif choice == '4':
                self._view_trending_suggestions()
            elif choice == '5':
                self._view_my_submissions()
            elif choice == '6':
                self._view_implemented_suggestions()
            elif choice == '7':
                self._search_submissions()
            elif choice == '8':
                self._view_statistics()
            elif choice == '9':
                self._admin_menu()
            elif choice == '0':
                print("\nThank you for using the Feedback & Suggestion Box!")
                break
            else:
                print("\nInvalid choice. Please try again.")

            input("\nPress Enter to continue...")

    def _display_header(self):
        """Display CLI header"""
        print("\n" + "=" * 70)
        print(" " * 15 + "FEEDBACK & SUGGESTION BOX")
        print("=" * 70)

        if self.auth.is_logged_in():
            user = self.auth.get_current_user()
            print(f"Logged in as: {user.get('username', 'Unknown')}")
        else:
            print("Not logged in - some features may be limited")
        print("=" * 70)

    def _get_main_menu_choice(self) -> str:
        """Display main menu and get choice"""
        print("\n--- Main Menu ---")
        print("1. Submit Feedback")
        print("2. Submit Suggestion")
        print("3. Browse Suggestions")
        print("4. View Trending Suggestions")
        print("5. View My Submissions")
        print("6. View Implemented Suggestions")
        print("7. Search Submissions")
        print("8. View Statistics")
        print("9. Admin Menu (Admin Only)")
        print("0. Exit")
        return input("\nEnter your choice: ").strip()

    def _submit_feedback(self):
        """Submit new feedback"""
        print("\n--- Submit Feedback ---")

        if not self.auth.is_logged_in():
            print("You must be logged in to submit feedback.")
            return

        user = self.auth.get_current_user()
        user_id = user.get('user_id')

        # Get category
        categories = self.service.get_categories()
        print("\nCategories:")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat['icon']} {cat['name']} - {cat['description']}")

        try:
            cat_choice = int(input("\nSelect category (number): ")) - 1
            if cat_choice < 0 or cat_choice >= len(categories):
                print("Invalid category selection.")
                return
            category = categories[cat_choice]['name']
        except (ValueError, IndexError):
            print("Invalid input.")
            return

        # Get title
        title = input("\nEnter a brief title: ").strip()
        if not title:
            print("Title cannot be empty.")
            return

        # Get description
        print("\nEnter detailed description (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        description = "\n".join(lines).strip()

        if not description:
            print("Description cannot be empty.")
            return

        # Anonymous option
        is_anonymous = input("\nSubmit anonymously? (y/n): ").strip().lower() == 'y'

        # Submit
        try:
            submission_id = self.service.submit_feedback(
                user_id=user_id,
                category=category,
                title=title,
                description=description,
                is_anonymous=is_anonymous,
                feedback_type='feedback'
            )
            print(f"\nFeedback submitted successfully! (ID: {submission_id})")
            print("Administrators will review your feedback and respond if needed.")
        except Exception as e:
            print(f"\nError submitting feedback: {e}")

    def _submit_suggestion(self):
        """Submit new suggestion"""
        print("\n--- Submit Suggestion ---")

        if not self.auth.is_logged_in():
            print("You must be logged in to submit suggestions.")
            return

        user = self.auth.get_current_user()
        user_id = user.get('user_id')

        # Get category
        categories = self.service.get_categories()
        print("\nCategories:")
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat['icon']} {cat['name']} - {cat['description']}")

        try:
            cat_choice = int(input("\nSelect category (number): ")) - 1
            if cat_choice < 0 or cat_choice >= len(categories):
                print("Invalid category selection.")
                return
            category = categories[cat_choice]['name']
        except (ValueError, IndexError):
            print("Invalid input.")
            return

        # Get title
        title = input("\nEnter suggestion title: ").strip()
        if not title:
            print("Title cannot be empty.")
            return

        # Get description
        print("\nDescribe your suggestion in detail (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        description = "\n".join(lines).strip()

        if not description:
            print("Description cannot be empty.")
            return

        # Anonymous option
        is_anonymous = input("\nSubmit anonymously? (y/n): ").strip().lower() == 'y'

        # Submit
        try:
            submission_id = self.service.submit_suggestion(
                user_id=user_id,
                category=category,
                title=title,
                description=description,
                is_anonymous=is_anonymous
            )
            print(f"\nSuggestion submitted successfully! (ID: {submission_id})")
            print("Your suggestion is now visible on the public board.")
            print("Other students can upvote your idea!")
        except Exception as e:
            print(f"\nError submitting suggestion: {e}")

    def _browse_suggestions(self):
        """Browse all suggestions with filters"""
        print("\n--- Browse Suggestions ---")

        # Filter options
        print("\nFilter by:")
        print("1. All suggestions")
        print("2. By category")
        print("3. By status")

        filter_choice = input("\nEnter choice (1-3): ").strip()

        category = None
        status = None

        if filter_choice == '2':
            categories = self.service.get_categories()
            print("\nCategories:")
            for i, cat in enumerate(categories, 1):
                print(f"{i}. {cat['icon']} {cat['name']}")
            try:
                cat_choice = int(input("\nSelect category: ")) - 1
                if 0 <= cat_choice < len(categories):
                    category = categories[cat_choice]['name']
            except (ValueError, IndexError):
                pass

        elif filter_choice == '3':
            statuses = [
                FeedbackService.STATUS_SUBMITTED,
                FeedbackService.STATUS_UNDER_REVIEW,
                FeedbackService.STATUS_PLANNED,
                FeedbackService.STATUS_IN_PROGRESS,
                FeedbackService.STATUS_IMPLEMENTED,
                FeedbackService.STATUS_DECLINED
            ]
            print("\nStatus:")
            for i, s in enumerate(statuses, 1):
                print(f"{i}. {s}")
            try:
                status_choice = int(input("\nSelect status: ")) - 1
                if 0 <= status_choice < len(statuses):
                    status = statuses[status_choice]
            except (ValueError, IndexError):
                pass

        # Sort options
        print("\nSort by:")
        print("1. Most votes")
        print("2. Most recent")
        print("3. Recently updated")

        sort_choice = input("\nEnter choice (1-3): ").strip()
        sort_by = "votes"
        if sort_choice == '2':
            sort_by = "date"
        elif sort_choice == '3':
            sort_by = "updated"

        # Get submissions
        submissions = self.service.get_submissions(
            submission_type='suggestion',
            category=category,
            status=status,
            sort_by=sort_by,
            limit=50
        )

        if not submissions:
            print("\nNo suggestions found.")
            return

        # Display results
        print(f"\n{'=' * 70}")
        print(f"Found {len(submissions)} suggestion(s)")
        print(f"{'=' * 70}\n")

        for i, sub in enumerate(submissions, 1):
            self._display_submission_summary(sub, i)

        # View details option
        if submissions:
            choice = input("\nView details? Enter number (or Enter to skip): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(submissions):
                    self._view_submission_details(submissions[idx]['id'])

    def _display_submission_summary(self, submission: dict, number: int):
        """Display a brief summary of a submission"""
        print(f"{number}. [{submission['category_icon']}] {submission['title']}")
        print(f"   Category: {submission['category']} | Status: {submission['status']}")
        print(f"   Votes: {submission['votes']} | By: {submission.get('display_user', 'Anonymous')}")
        print(f"   Created: {submission['created_at']}")
        print()

    def _view_submission_details(self, submission_id: int):
        """View detailed information about a submission"""
        details = self.service.get_submission_details(submission_id)

        if not details:
            print("\nSubmission not found.")
            return

        print(f"\n{'=' * 70}")
        print(f"[{details['category_icon']}] {details['title']}")
        print(f"{'=' * 70}")
        print(f"Category: {details['category']}")
        print(f"Status: {details['status']}")
        print(f"Type: {details['type'].title()}")
        print(f"Votes: {details['votes']}")
        print(f"Submitted: {details['created_at']}")
        print(f"Updated: {details['updated_at']}")

        if not details['is_anonymous']:
            print(f"Submitted by: {details.get('user_id', 'Unknown')}")
        else:
            print("Submitted by: Anonymous")

        print(f"\n{'-' * 70}")
        print("Description:")
        print(details['description'])
        print(f"{'-' * 70}")

        # Responses
        if details['responses']:
            print(f"\n--- Responses ({len(details['responses'])}) ---")
            for resp in details['responses']:
                print(f"\nFrom: {resp['responder_name']} ({resp['created_at']})")
                print(resp['response_text'])
                print("-" * 50)

        # Status history
        if details['status_history']:
            print(f"\n--- Status History ---")
            for hist in details['status_history']:
                print(f"{hist['created_at']}: {hist['old_status']} -> {hist['new_status']}")
                if hist['notes']:
                    print(f"  Note: {hist['notes']}")

        # Impact data
        if details.get('impact'):
            impact = details['impact']
            print(f"\n--- Impact Data ---")
            print(f"Implementation Date: {impact['implementation_date']}")
            print(f"Users Affected: {impact['users_affected']}")
            if impact['satisfaction_increase']:
                print(f"Satisfaction Increase: {impact['satisfaction_increase']}%")
            if impact['cost_savings']:
                print(f"Cost Savings: ${impact['cost_savings']:.2f}")
            print(f"Description: {impact['description']}")

        # Vote option
        if self.auth.is_logged_in() and details['type'] == 'suggestion':
            user = self.auth.get_current_user()
            user_id = user.get('user_id')
            has_voted = self.service.has_user_voted(submission_id, user_id)

            if has_voted:
                remove = input("\nYou have voted for this. Remove vote? (y/n): ").strip().lower()
                if remove == 'y':
                    if self.service.remove_vote(submission_id, user_id):
                        print("Vote removed.")
                    else:
                        print("Failed to remove vote.")
            else:
                vote = input("\nUpvote this suggestion? (y/n): ").strip().lower()
                if vote == 'y':
                    if self.service.upvote_submission(submission_id, user_id):
                        print("Vote added!")
                    else:
                        print("Failed to add vote.")

    def _view_trending_suggestions(self):
        """View trending suggestions"""
        print("\n--- Trending Suggestions ---")
        print("Most popular suggestions with recent activity\n")

        trending = self.service.get_trending_suggestions(limit=15)

        if not trending:
            print("No trending suggestions at this time.")
            return

        for i, sub in enumerate(trending, 1):
            print(f"{i}. {sub['title']}")
            print(f"   {sub['category_icon']} {sub['category']} | "
                  f"{sub['votes']} votes | Status: {sub['status']}")
            print(f"   {sub['response_count']} responses | Updated: {sub['updated_at']}")
            print()

        # View details
        choice = input("\nView details? Enter number (or Enter to skip): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(trending):
                self._view_submission_details(trending[idx]['id'])

    def _view_my_submissions(self):
        """View user's own submissions"""
        print("\n--- My Submissions ---")

        if not self.auth.is_logged_in():
            print("You must be logged in to view your submissions.")
            return

        user = self.auth.get_current_user()
        user_id = user.get('user_id')

        submissions = self.service.get_user_submissions(user_id)

        if not submissions:
            print("\nYou haven't submitted anything yet.")
            return

        print(f"\nYou have {len(submissions)} submission(s):\n")

        for i, sub in enumerate(submissions, 1):
            self._display_submission_summary(sub, i)

        # View details
        choice = input("\nView details? Enter number (or Enter to skip): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(submissions):
                self._view_submission_details(submissions[idx]['id'])

    def _view_implemented_suggestions(self):
        """View implemented suggestions with impact data"""
        print("\n--- Implemented Suggestions ---")
        print("See what ideas have been brought to life!\n")

        implemented = self.service.get_implemented_suggestions(limit=20)

        if not implemented:
            print("No implemented suggestions yet.")
            return

        for i, sub in enumerate(implemented, 1):
            print(f"{i}. {sub['title']}")
            print(f"   {sub['category_icon']} {sub['category']} | {sub['votes']} votes")

            if sub['implementation_date']:
                print(f"   Implemented: {sub['implementation_date']}")

            if sub['users_affected']:
                print(f"   Users Affected: {sub['users_affected']}")

            if sub['satisfaction_increase']:
                print(f"   Satisfaction Increase: {sub['satisfaction_increase']}%")

            if sub['impact_description']:
                print(f"   Impact: {sub['impact_description']}")

            print()

        # View details
        choice = input("\nView details? Enter number (or Enter to skip): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(implemented):
                self._view_submission_details(implemented[idx]['id'])

    def _search_submissions(self):
        """Search for submissions"""
        print("\n--- Search Submissions ---")

        search_term = input("\nEnter search term: ").strip()

        if not search_term:
            print("Search term cannot be empty.")
            return

        results = self.service.search_submissions(search_term, limit=50)

        if not results:
            print(f"\nNo submissions found matching '{search_term}'.")
            return

        print(f"\nFound {len(results)} result(s):\n")

        for i, sub in enumerate(results, 1):
            self._display_submission_summary(sub, i)

        # View details
        choice = input("\nView details? Enter number (or Enter to skip): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(results):
                self._view_submission_details(results[idx]['id'])

    def _view_statistics(self):
        """View system statistics"""
        print("\n--- Feedback System Statistics ---")

        stats = self.service.get_statistics()

        print(f"\nTotal Submissions: {stats['total_submissions']}")
        print(f"  - Feedback: {stats['total_feedback']}")
        print(f"  - Suggestions: {stats['total_suggestions']}")
        print(f"\nTotal Votes: {stats['total_votes']}")
        print(f"Average Votes per Submission: {stats['average_votes']}")
        print(f"Total Responses: {stats['total_responses']}")

        print("\n--- By Status ---")
        for status, count in stats['by_status'].items():
            print(f"  {status}: {count}")

        print("\n--- By Category ---")
        for category, count in stats['by_category'].items():
            print(f"  {category}: {count}")

        print(f"\nImplemented Suggestions: {stats['implemented_count']}")

    def _admin_menu(self):
        """Administrative menu"""
        print("\n--- Admin Menu ---")

        if not self.auth.is_logged_in():
            print("You must be logged in to access admin features.")
            return

        user = self.auth.get_current_user()
        role = user.get('role', '').lower()

        if role not in ['admin', 'administrator']:
            print("Access denied. Admin privileges required.")
            return

        print("1. Respond to Submission")
        print("2. Update Submission Status")
        print("3. Add Impact Data (for implemented suggestions)")
        print("0. Back to Main Menu")

        choice = input("\nEnter choice: ").strip()

        if choice == '1':
            self._admin_respond()
        elif choice == '2':
            self._admin_update_status()
        elif choice == '3':
            self._admin_add_impact()

    def _admin_respond(self):
        """Admin: Respond to a submission"""
        print("\n--- Respond to Submission ---")

        submission_id = input("Enter submission ID: ").strip()
        if not submission_id.isdigit():
            print("Invalid ID.")
            return

        submission_id = int(submission_id)

        # Show submission
        details = self.service.get_submission_details(submission_id)
        if not details:
            print("Submission not found.")
            return

        print(f"\nSubmission: {details['title']}")
        print(f"Description: {details['description']}")

        # Get response
        print("\nEnter your response (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        response_text = "\n".join(lines).strip()

        if not response_text:
            print("Response cannot be empty.")
            return

        user = self.auth.get_current_user()
        responder_id = user.get('user_id')
        responder_name = user.get('username', 'Administrator')

        try:
            response_id = self.service.add_response(
                submission_id, responder_id, responder_name, response_text
            )
            print(f"\nResponse added successfully! (ID: {response_id})")
        except Exception as e:
            print(f"\nError adding response: {e}")

    def _admin_update_status(self):
        """Admin: Update submission status"""
        print("\n--- Update Submission Status ---")

        submission_id = input("Enter submission ID: ").strip()
        if not submission_id.isdigit():
            print("Invalid ID.")
            return

        submission_id = int(submission_id)

        # Show current status
        details = self.service.get_submission_details(submission_id)
        if not details:
            print("Submission not found.")
            return

        print(f"\nSubmission: {details['title']}")
        print(f"Current Status: {details['status']}")

        # Select new status
        statuses = [
            FeedbackService.STATUS_SUBMITTED,
            FeedbackService.STATUS_UNDER_REVIEW,
            FeedbackService.STATUS_PLANNED,
            FeedbackService.STATUS_IN_PROGRESS,
            FeedbackService.STATUS_IMPLEMENTED,
            FeedbackService.STATUS_DECLINED
        ]

        print("\nNew Status:")
        for i, s in enumerate(statuses, 1):
            print(f"{i}. {s}")

        try:
            status_choice = int(input("\nSelect status: ")) - 1
            if status_choice < 0 or status_choice >= len(statuses):
                print("Invalid selection.")
                return
            new_status = statuses[status_choice]
        except ValueError:
            print("Invalid input.")
            return

        # Get notes
        notes = input("\nNotes (optional): ").strip()

        user = self.auth.get_current_user()
        updated_by = user.get('username', 'Administrator')

        try:
            success = self.service.update_status(
                submission_id, new_status, updated_by, notes if notes else None
            )
            if success:
                print("\nStatus updated successfully!")
            else:
                print("\nFailed to update status.")
        except Exception as e:
            print(f"\nError updating status: {e}")

    def _admin_add_impact(self):
        """Admin: Add impact data for implemented suggestion"""
        print("\n--- Add Impact Data ---")

        submission_id = input("Enter submission ID: ").strip()
        if not submission_id.isdigit():
            print("Invalid ID.")
            return

        submission_id = int(submission_id)

        # Verify it's implemented
        details = self.service.get_submission_details(submission_id)
        if not details:
            print("Submission not found.")
            return

        if details['status'] != FeedbackService.STATUS_IMPLEMENTED:
            print(f"Warning: Submission status is '{details['status']}', not 'Implemented'.")
            cont = input("Continue anyway? (y/n): ").strip().lower()
            if cont != 'y':
                return

        print(f"\nSubmission: {details['title']}")

        # Get impact data
        impl_date = input("\nImplementation date (YYYY-MM-DD): ").strip()
        if not impl_date:
            impl_date = datetime.now().strftime('%Y-%m-%d')

        try:
            users_affected = int(input("Number of users affected: ").strip() or "0")
        except ValueError:
            users_affected = 0

        try:
            satisfaction = float(input("Satisfaction increase (%) [0-100]: ").strip() or "0")
        except ValueError:
            satisfaction = 0.0

        try:
            cost_savings = float(input("Cost savings ($): ").strip() or "0")
        except ValueError:
            cost_savings = 0.0

        description = input("Impact description: ").strip()

        try:
            impact_id = self.service.add_impact_data(
                submission_id, impl_date, users_affected,
                satisfaction, cost_savings, description
            )
            print(f"\nImpact data added successfully! (ID: {impact_id})")
        except Exception as e:
            print(f"\nError adding impact data: {e}")


def main():
    """Main entry point"""
    cli = FeedbackCLI()
    cli.run()


if __name__ == '__main__':
    main()
