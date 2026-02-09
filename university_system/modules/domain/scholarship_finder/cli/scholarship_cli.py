"""
CLI Interface for Scholarship Finder.

Provides command-line interface for:
- Searching scholarships with filters
- Personalized scholarship recommendations
- Application tracking and management
- Deadline management and reminders
- Document vault management
- Profile management for better matching
"""

from datetime import datetime, timedelta
from typing import Optional

from university_system.infrastructure.shared_context import get_auth
from university_system.modules.domain.scholarship_finder.services.scholarship_service import (
    ScholarshipDatabase,
    StudentProfileManager,
    RecommendationEngine,
    ApplicationManager,
    DocumentVaultManager
)


class ScholarshipFinderCLI:
    """CLI interface for scholarship finder system."""

    def __init__(self):
        """Initialize the CLI interface."""
        self.auth = get_auth()

    def run(self):
        """Run the main CLI interface."""
        if not self.auth.is_logged_in():
            print("\nYou must be logged in to use Scholarship Finder.")
            return

        while True:
            self.display_main_menu()
            choice = input("\nEnter your choice (1-10, or 0 to exit): ").strip()

            if choice == '0':
                print("\nExiting Scholarship Finder...")
                break
            elif choice == '1':
                self.search_scholarships()
            elif choice == '2':
                self.view_recommendations()
            elif choice == '3':
                self.manage_profile()
            elif choice == '4':
                self.my_applications_menu()
            elif choice == '5':
                self.view_upcoming_deadlines()
            elif choice == '6':
                self.start_new_application()
            elif choice == '7':
                self.document_vault_menu()
            elif choice == '8':
                self.view_scholarship_details()
            elif choice == '9':
                self.view_award_history()
            elif choice == '10':
                self.generate_new_recommendations()
            else:
                print("\nInvalid choice. Please try again.")

    def display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 60)
        print("SCHOLARSHIP FINDER".center(60))
        print("=" * 60)
        print("\n1.  Search Scholarships")
        print("2.  View My Recommendations")
        print("3.  Manage My Profile")
        print("4.  My Applications")
        print("5.  Upcoming Deadlines")
        print("6.  Start New Application")
        print("7.  Document Vault")
        print("8.  View Scholarship Details")
        print("9.  View Award History")
        print("10. Generate New Recommendations")
        print("0.  Exit")

    # ========== Search ==========

    def search_scholarships(self):
        """Search for scholarships with filters."""
        print("\n" + "-" * 60)
        print("SEARCH SCHOLARSHIPS")
        print("-" * 60)

        filters = {}

        # Organization type
        print("\nOrganization Types:")
        print("1. University")
        print("2. Government")
        print("3. Private")
        print("4. Corporate")
        print("5. Foundation")
        print("6. Nonprofit")
        print("7. Community")
        print("8. Any")

        org_choice = input("\nSelect organization type (1-8, or skip): ").strip()
        org_types = ['university', 'government', 'private', 'corporate', 'foundation', 'nonprofit', 'community']
        if org_choice and org_choice != '8':
            try:
                idx = int(org_choice) - 1
                if 0 <= idx < len(org_types):
                    filters['organization_type'] = org_types[idx]
            except ValueError:
                pass

        # Minimum award amount
        min_award = input("\nMinimum award amount (or skip): $").strip()
        if min_award:
            try:
                filters['min_award'] = float(min_award)
            except ValueError:
                pass

        # Academic level
        print("\nAcademic Levels:")
        print("1. Freshman")
        print("2. Sophomore")
        print("3. Junior")
        print("4. Senior")
        print("5. Graduate")
        print("6. Any")

        level_choice = input("\nSelect academic level (1-6, or skip): ").strip()
        levels = ['freshman', 'sophomore', 'junior', 'senior', 'graduate']
        if level_choice and level_choice != '6':
            try:
                idx = int(level_choice) - 1
                if 0 <= idx < len(levels):
                    filters['academic_level'] = levels[idx]
            except ValueError:
                pass

        # Major
        major = input("\nMajor (or skip): ").strip()
        if major:
            filters['major'] = major

        # Merit-based
        merit = input("\nMerit-based only? (y/n, or skip): ").strip().lower()
        if merit == 'y':
            filters['merit_based'] = 1

        # Deadline after
        deadline = input("\nShow scholarships with deadline after date (YYYY-MM-DD, or skip): ").strip()
        if deadline:
            filters['deadline_after'] = deadline

        # Sort by
        print("\nSort By:")
        print("1. Deadline (earliest first)")
        print("2. Award Amount (highest first)")
        print("3. Competition Level (lowest first)")
        print("4. Most Recent")

        sort_choice = input("\nSelect sort order (1-4, default 1): ").strip()
        sort_options = ['deadline', 'amount', 'competition', 'recent']
        sort_by = 'deadline'
        if sort_choice:
            try:
                idx = int(sort_choice) - 1
                if 0 <= idx < len(sort_options):
                    sort_by = sort_options[idx]
            except ValueError:
                pass

        # Search
        print("\nSearching...")
        scholarships = ScholarshipDatabase.search_scholarships(filters, sort_by)

        if not scholarships:
            print("\nNo scholarships found matching your criteria.")
            print("Try adjusting your filters or search without filters.")
            return

        print(f"\n{'=' * 80}")
        print(f"FOUND {len(scholarships)} SCHOLARSHIPS")
        print(f"{'=' * 80}")

        for i, sch in enumerate(scholarships[:20], 1):  # Show first 20
            award_range = f"${sch['award_amount_min']:,.0f}"
            if sch['award_amount_max']:
                award_range += f" - ${sch['award_amount_max']:,.0f}"

            print(f"\n{i}. [{sch['scholarship_id']}] {sch['scholarship_name']}")
            print(f"   Organization: {sch['organization']} ({sch['organization_type']})")
            print(f"   Award: {award_range} ({sch['award_type']})")
            print(f"   Deadline: {sch['application_deadline']}")
            if sch['min_gpa']:
                print(f"   Min GPA: {sch['min_gpa']}")
            if sch['competition_level']:
                print(f"   Competition: {sch['competition_level']}")

        if len(scholarships) > 20:
            print(f"\n... and {len(scholarships) - 20} more scholarships")

        # View details option
        view_more = input("\nView details for a scholarship? (enter ID or 0 to skip): ").strip()
        if view_more and view_more != '0':
            try:
                sch_id = int(view_more)
                self.display_scholarship_details(sch_id)
            except ValueError:
                print("\nInvalid scholarship ID.")

    # ========== Recommendations ==========

    def view_recommendations(self):
        """View personalized scholarship recommendations."""
        print("\n" + "-" * 60)
        print("MY SCHOLARSHIP RECOMMENDATIONS")
        print("-" * 60)

        user_id = self.auth.get_current_user()['username']

        # Try to get cached recommendations first
        recommendations = RecommendationEngine.get_cached_recommendations(user_id)

        if not recommendations:
            print("\nNo recommendations found. Generating recommendations...")
            recommendations = RecommendationEngine.generate_recommendations(user_id)

        if not recommendations:
            print("\nNo recommendations available.")
            print("\nTo get better recommendations:")
            print("  - Complete your scholarship profile (option 3)")
            print("  - Ensure your academic information is up to date")
            return

        print(f"\n{'=' * 90}")
        print(f"PERSONALIZED RECOMMENDATIONS ({len(recommendations)} scholarships)")
        print(f"{'=' * 90}")

        for i, rec in enumerate(recommendations, 1):
            award_range = f"${rec['award_amount_min']:,.0f}"
            if rec['award_amount_max']:
                award_range += f" - ${rec['award_amount_max']:,.0f}"

            # Match score bar
            score = rec['match_score']
            bar_length = int(score / 5)
            score_bar = "█" * bar_length + "░" * (20 - bar_length)

            print(f"\n{i}. {rec['scholarship_name']}")
            print(f"   Organization: {rec['organization']}")
            print(f"   Award: {award_range}")
            print(f"   Deadline: {rec['application_deadline']}")
            print(f"   Match Score: {score_bar} {score:.0f}%")
            print(f"   Priority: {rec['priority_level'].upper()}")
            print(f"   Eligibility: {rec['eligibility_status']}")

            if rec['matching_criteria']:
                print(f"   Why you match: {rec['matching_criteria']}")

            if rec['essay_required']:
                print(f"   Requirements: Essay required")
            if rec['recommendation_letters_required']:
                print(f"                {rec['recommendation_letters_required']} recommendation letters")

        # Apply for a scholarship
        apply = input("\nStart application for a scholarship? (enter number or 0 to skip): ").strip()
        if apply and apply != '0':
            try:
                idx = int(apply) - 1
                if 0 <= idx < len(recommendations):
                    rec = recommendations[idx]
                    self.quick_start_application(rec['scholarship_id'], rec['match_score'])
            except ValueError:
                print("\nInvalid selection.")

    def generate_new_recommendations(self):
        """Generate fresh recommendations."""
        print("\n" + "-" * 60)
        print("GENERATE NEW RECOMMENDATIONS")
        print("-" * 60)

        user_id = self.auth.get_current_user()['username']

        print("\nAnalyzing your profile and finding matching scholarships...")
        recommendations = RecommendationEngine.generate_recommendations(user_id, limit=20)

        if recommendations:
            print(f"\n✓ Generated {len(recommendations)} new recommendations!")
            print("View them in the 'View My Recommendations' menu.")
        else:
            print("\n✗ Could not generate recommendations.")
            print("Please ensure your profile is complete and up to date.")

    # ========== Profile Management ==========

    def manage_profile(self):
        """Manage scholarship profile."""
        while True:
            print("\n" + "-" * 60)
            print("MANAGE MY PROFILE")
            print("-" * 60)

            user_id = self.auth.get_current_user()['username']
            profile = StudentProfileManager.get_student_profile(user_id)

            if profile:
                print(f"\nProfile Completeness: {profile['profile_completeness']:.1f}%")
                bar_length = int(profile['profile_completeness'] / 5)
                completeness_bar = "█" * bar_length + "░" * (20 - bar_length)
                print(f"{completeness_bar}")

            print("\n1. View Current Profile")
            print("2. Update Basic Information")
            print("3. Update Academic & Career Info")
            print("4. Update Activities & Achievements")
            print("5. Update Preferences")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_profile()
            elif choice == '2':
                self.update_basic_info()
            elif choice == '3':
                self.update_academic_info()
            elif choice == '4':
                self.update_activities()
            elif choice == '5':
                self.update_preferences()
            else:
                print("\nInvalid choice.")

    def view_profile(self):
        """View current profile."""
        user_id = self.auth.get_current_user()['username']
        profile = StudentProfileManager.get_student_profile(user_id)

        if not profile:
            print("\nNo profile found. Please create one by updating your information.")
            return

        print(f"\n{'=' * 60}")
        print("MY SCHOLARSHIP PROFILE")
        print(f"{'=' * 60}")

        print("\nBasic Information:")
        print(f"  Citizenship: {profile['citizenship_status'] or 'Not set'}")
        print(f"  State Residency: {profile['state_residency'] or 'Not set'}")
        print(f"  Ethnicity: {profile['ethnicity'] or 'Not set'}")
        print(f"  Gender: {profile['gender'] or 'Not set'}")
        print(f"  First Generation: {'Yes' if profile['first_generation'] else 'No'}")
        print(f"  Military Affiliation: {profile['military_affiliation'] or 'None'}")
        print(f"  Disability Status: {profile['disability_status'] or 'None'}")

        print("\nFinancial & Academic:")
        print(f"  Financial Need Level: {profile['financial_need_level'] or 'Not set'}")
        print(f"  Intended Career Field: {profile['intended_career_field'] or 'Not set'}")

        print("\nActivities & Achievements:")
        print(f"  Community Service Hours: {profile['community_service_hours']}")
        print(f"  Leadership Positions: {profile['leadership_positions'] or 'None listed'}")
        print(f"  Academic Honors: {profile['academic_honors'] or 'None listed'}")
        print(f"  Extracurricular Activities: {profile['extracurricular_activities'] or 'None listed'}")
        print(f"  Special Talents: {profile['special_talents'] or 'None listed'}")
        print(f"  Languages Spoken: {profile['languages_spoken'] or 'Not set'}")

        print("\nInterests & Preferences:")
        print(f"  Study Abroad Interest: {'Yes' if profile['study_abroad_interest'] else 'No'}")
        print(f"  Research Interest: {'Yes' if profile['research_interest'] else 'No'}")
        print(f"  Preferred Scholarship Types: {profile['preferred_scholarship_types'] or 'No preference'}")
        print(f"  Minimum Award Amount: ${profile['minimum_award_amount'] or 0:,.0f}")
        print(f"  Willing to Write Essays: {'Yes' if profile['willing_to_write_essays'] else 'No'}")
        print(f"  Max Recommendation Letters: {profile['max_recommendation_letters']}")

    def update_basic_info(self):
        """Update basic profile information."""
        print("\n" + "-" * 60)
        print("UPDATE BASIC INFORMATION")
        print("-" * 60)

        profile_data = {}

        citizenship = input("\nCitizenship Status (US Citizen, Permanent Resident, International, etc.): ").strip()
        if citizenship:
            profile_data['citizenship_status'] = citizenship

        state = input("State of Residency (2-letter code): ").strip().upper()
        if state:
            profile_data['state_residency'] = state

        ethnicity = input("Ethnicity (optional): ").strip()
        if ethnicity:
            profile_data['ethnicity'] = ethnicity

        gender = input("Gender (optional): ").strip()
        if gender:
            profile_data['gender'] = gender

        first_gen = input("First generation college student? (y/n): ").strip().lower()
        if first_gen:
            profile_data['first_generation'] = 1 if first_gen == 'y' else 0

        military = input("Military Affiliation (Veteran, Active Duty, Dependent, None): ").strip()
        if military:
            profile_data['military_affiliation'] = military

        disability = input("Disability Status (optional): ").strip()
        if disability:
            profile_data['disability_status'] = disability

        if profile_data:
            user_id = self.auth.get_current_user()['username']
            StudentProfileManager.create_or_update_profile(user_id, **profile_data)
            print("\n✓ Basic information updated successfully!")
        else:
            print("\nNo changes made.")

    def update_academic_info(self):
        """Update academic and career information."""
        print("\n" + "-" * 60)
        print("UPDATE ACADEMIC & CAREER INFO")
        print("-" * 60)

        profile_data = {}

        print("\nFinancial Need Level:")
        print("1. None")
        print("2. Low")
        print("3. Moderate")
        print("4. High")
        print("5. Exceptional")

        need_choice = input("\nSelect financial need level (1-5): ").strip()
        needs = ['none', 'low', 'moderate', 'high', 'exceptional']
        if need_choice:
            try:
                idx = int(need_choice) - 1
                if 0 <= idx < len(needs):
                    profile_data['financial_need_level'] = needs[idx]
            except ValueError:
                pass

        career = input("\nIntended Career Field: ").strip()
        if career:
            profile_data['intended_career_field'] = career

        if profile_data:
            user_id = self.auth.get_current_user()['username']
            StudentProfileManager.create_or_update_profile(user_id, **profile_data)
            print("\n✓ Academic information updated successfully!")
        else:
            print("\nNo changes made.")

    def update_activities(self):
        """Update activities and achievements."""
        print("\n" + "-" * 60)
        print("UPDATE ACTIVITIES & ACHIEVEMENTS")
        print("-" * 60)

        profile_data = {}

        service_hours = input("\nCommunity Service Hours: ").strip()
        if service_hours:
            try:
                profile_data['community_service_hours'] = int(service_hours)
            except ValueError:
                pass

        leadership = input("Leadership Positions (comma-separated): ").strip()
        if leadership:
            profile_data['leadership_positions'] = leadership

        honors = input("Academic Honors (comma-separated): ").strip()
        if honors:
            profile_data['academic_honors'] = honors

        activities = input("Extracurricular Activities (comma-separated): ").strip()
        if activities:
            profile_data['extracurricular_activities'] = activities

        talents = input("Special Talents (comma-separated): ").strip()
        if talents:
            profile_data['special_talents'] = talents

        languages = input("Languages Spoken (comma-separated): ").strip()
        if languages:
            profile_data['languages_spoken'] = languages

        study_abroad = input("Interested in Study Abroad? (y/n): ").strip().lower()
        if study_abroad:
            profile_data['study_abroad_interest'] = 1 if study_abroad == 'y' else 0

        research = input("Interested in Research? (y/n): ").strip().lower()
        if research:
            profile_data['research_interest'] = 1 if research == 'y' else 0

        if profile_data:
            user_id = self.auth.get_current_user()['username']
            StudentProfileManager.create_or_update_profile(user_id, **profile_data)
            print("\n✓ Activities updated successfully!")
        else:
            print("\nNo changes made.")

    def update_preferences(self):
        """Update scholarship preferences."""
        print("\n" + "-" * 60)
        print("UPDATE PREFERENCES")
        print("-" * 60)

        profile_data = {}

        types = input("\nPreferred Scholarship Types (merit, need-based, athletic, etc.): ").strip()
        if types:
            profile_data['preferred_scholarship_types'] = types

        min_amount = input("Minimum Award Amount ($): ").strip()
        if min_amount:
            try:
                profile_data['minimum_award_amount'] = float(min_amount)
            except ValueError:
                pass

        essays = input("Willing to Write Essays? (y/n): ").strip().lower()
        if essays:
            profile_data['willing_to_write_essays'] = 1 if essays == 'y' else 0

        max_letters = input("Maximum Recommendation Letters you can obtain: ").strip()
        if max_letters:
            try:
                profile_data['max_recommendation_letters'] = int(max_letters)
            except ValueError:
                pass

        if profile_data:
            user_id = self.auth.get_current_user()['username']
            StudentProfileManager.create_or_update_profile(user_id, **profile_data)
            print("\n✓ Preferences updated successfully!")
        else:
            print("\nNo changes made.")

    # ========== Applications ==========

    def my_applications_menu(self):
        """Manage applications."""
        while True:
            print("\n" + "-" * 60)
            print("MY APPLICATIONS")
            print("-" * 60)
            print("\n1. View All Applications")
            print("2. View In-Progress Applications")
            print("3. View Submitted Applications")
            print("4. Update Application Progress")
            print("5. Submit Application")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_applications()
            elif choice == '2':
                self.view_applications('in-progress')
            elif choice == '3':
                self.view_applications('submitted')
            elif choice == '4':
                self.update_application()
            elif choice == '5':
                self.submit_application()
            else:
                print("\nInvalid choice.")

    def view_applications(self, status: Optional[str] = None):
        """View student applications."""
        user_id = self.auth.get_current_user()['username']
        applications = ApplicationManager.get_student_applications(user_id, status)

        if not applications:
            status_text = f" with status '{status}'" if status else ""
            print(f"\nNo applications found{status_text}.")
            return

        print(f"\n{'=' * 90}")
        print(f"MY APPLICATIONS ({len(applications)})")
        print(f"{'=' * 90}")

        for i, app in enumerate(applications, 1):
            progress = app['application_progress']
            progress_bar_length = int(progress / 5)
            progress_bar = "█" * progress_bar_length + "░" * (20 - progress_bar_length)

            print(f"\n{i}. [{app['application_id']}] {app['scholarship_name']}")
            print(f"   Organization: {app['organization']}")
            print(f"   Status: {app['status'].upper()}")
            print(f"   Deadline: {app['deadline_date']}")
            print(f"   Progress: {progress_bar} {progress:.0f}%")

            # Show completion status
            checks = []
            if app['essay_completed']:
                checks.append("✓ Essay")
            if app['transcript_uploaded']:
                checks.append("✓ Transcript")
            if app['documents_completed']:
                checks.append("✓ Documents")
            if app['recommendations_required'] > 0:
                checks.append(f"✓ Rec Letters ({app['recommendations_obtained']}/{app['recommendations_required']})")

            if checks:
                print(f"   Completed: {', '.join(checks)}")

        # Update application option
        update = input("\nUpdate an application? (enter ID or 0 to skip): ").strip()
        if update and update != '0':
            try:
                app_id = int(update)
                self.update_application_details(app_id)
            except ValueError:
                print("\nInvalid application ID.")

    def start_new_application(self):
        """Start a new scholarship application."""
        print("\n" + "-" * 60)
        print("START NEW APPLICATION")
        print("-" * 60)

        scholarship_id = input("\nEnter Scholarship ID: ").strip()
        if not scholarship_id:
            return

        try:
            scholarship_id = int(scholarship_id)
        except ValueError:
            print("\nInvalid scholarship ID.")
            return

        # Get scholarship details
        scholarship = ScholarshipDatabase.get_scholarship_details(scholarship_id)
        if not scholarship:
            print("\nScholarship not found.")
            return

        print(f"\nScholarship: {scholarship['scholarship_name']}")
        print(f"Organization: {scholarship['organization']}")
        print(f"Deadline: {scholarship['application_deadline']}")

        confirm = input("\nStart application for this scholarship? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\nCancelled.")
            return

        user_id = self.auth.get_current_user()['username']

        try:
            app_id = ApplicationManager.start_application(user_id, scholarship_id)
            print(f"\n✓ Application started! Application ID: {app_id}")
            print("Deadline reminders have been automatically created.")
        except Exception as e:
            print(f"\n✗ Error starting application: {e}")

    def quick_start_application(self, scholarship_id: int, match_score: float):
        """Quick start application from recommendations."""
        user_id = self.auth.get_current_user()['username']

        try:
            app_id = ApplicationManager.start_application(user_id, scholarship_id, match_score)
            print(f"\n✓ Application started! Application ID: {app_id}")
            print("Track your progress in the 'My Applications' menu.")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def update_application(self):
        """Update application progress."""
        app_id = input("\nEnter Application ID: ").strip()
        if not app_id:
            return

        try:
            app_id = int(app_id)
        except ValueError:
            print("\nInvalid application ID.")
            return

        self.update_application_details(app_id)

    def update_application_details(self, app_id: int):
        """Update specific application details."""
        print("\n" + "-" * 60)
        print("UPDATE APPLICATION")
        print("-" * 60)

        updates = {}

        essay = input("\nEssay completed? (y/n/skip): ").strip().lower()
        if essay == 'y':
            updates['essay_completed'] = 1
        elif essay == 'n':
            updates['essay_completed'] = 0

        transcript = input("Transcript uploaded? (y/n/skip): ").strip().lower()
        if transcript == 'y':
            updates['transcript_uploaded'] = 1
        elif transcript == 'n':
            updates['transcript_uploaded'] = 0

        documents = input("All documents completed? (y/n/skip): ").strip().lower()
        if documents == 'y':
            updates['documents_completed'] = 1
        elif documents == 'n':
            updates['documents_completed'] = 0

        rec_count = input("Number of recommendations obtained (or skip): ").strip()
        if rec_count:
            try:
                updates['recommendations_obtained'] = int(rec_count)
            except ValueError:
                pass

        notes = input("Add notes (or skip): ").strip()
        if notes:
            updates['notes'] = notes

        if updates:
            if ApplicationManager.update_application_progress(app_id, **updates):
                print("\n✓ Application updated successfully!")
            else:
                print("\n✗ Failed to update application.")
        else:
            print("\nNo changes made.")

    def submit_application(self):
        """Submit a completed application."""
        app_id = input("\nEnter Application ID to submit: ").strip()
        if not app_id:
            return

        try:
            app_id = int(app_id)
        except ValueError:
            print("\nInvalid application ID.")
            return

        confirm = input("\nAre you sure the application is complete? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\nCancelled.")
            return

        try:
            if ApplicationManager.submit_application(app_id):
                print("\n✓ Application submitted successfully!")
                print("You will be notified when you receive a response.")
            else:
                print("\n✗ Failed to submit application.")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Deadlines ==========

    def view_upcoming_deadlines(self):
        """View applications with upcoming deadlines."""
        print("\n" + "-" * 60)
        print("UPCOMING DEADLINES")
        print("-" * 60)

        days = input("\nShow deadlines within how many days? (default 14): ").strip()
        try:
            days = int(days) if days else 14
        except ValueError:
            days = 14

        user_id = self.auth.get_current_user()['username']
        deadlines = ApplicationManager.get_upcoming_deadlines(user_id, days)

        if not deadlines:
            print(f"\nNo deadlines in the next {days} days.")
            return

        print(f"\n{'=' * 80}")
        print(f"UPCOMING DEADLINES ({len(deadlines)} applications)")
        print(f"{'=' * 80}")

        for i, app in enumerate(deadlines, 1):
            deadline = datetime.strptime(app['deadline_date'], '%Y-%m-%d')
            days_left = (deadline - datetime.now()).days

            urgency = "URGENT!" if days_left <= 3 else "Soon" if days_left <= 7 else "Upcoming"

            print(f"\n{i}. {app['scholarship_name']}")
            print(f"   Deadline: {app['deadline_date']} ({days_left} days) - {urgency}")
            print(f"   Status: {app['status'].upper()}")
            print(f"   Progress: {app['application_progress']:.0f}%")

    # ========== Document Vault ==========

    def document_vault_menu(self):
        """Manage document vault."""
        while True:
            print("\n" + "-" * 60)
            print("DOCUMENT VAULT")
            print("-" * 60)
            print("\n1. View All Documents")
            print("2. View Essays")
            print("3. View Transcripts")
            print("4. View Resumes")
            print("5. View Recommendations")
            print("6. Upload New Document")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_documents()
            elif choice == '2':
                self.view_documents('essay')
            elif choice == '3':
                self.view_documents('transcript')
            elif choice == '4':
                self.view_documents('resume')
            elif choice == '5':
                self.view_documents('recommendation')
            elif choice == '6':
                self.upload_document()
            else:
                print("\nInvalid choice.")

    def view_documents(self, doc_type: Optional[str] = None):
        """View documents in vault."""
        user_id = self.auth.get_current_user()['username']
        documents = DocumentVaultManager.get_student_documents(user_id, doc_type)

        if not documents:
            type_text = f" of type '{doc_type}'" if doc_type else ""
            print(f"\nNo documents found{type_text}.")
            return

        print(f"\n{'=' * 80}")
        print(f"MY DOCUMENTS ({len(documents)})")
        print(f"{'=' * 80}")

        for i, doc in enumerate(documents, 1):
            print(f"\n{i}. [{doc['document_id']}] {doc['document_name']}")
            print(f"   Type: {doc['document_type']}")
            print(f"   Uploaded: {doc['upload_date']}")
            print(f"   File: {doc['file_path']}")
            if doc['description']:
                print(f"   Description: {doc['description']}")
            print(f"   Used {doc['usage_count']} times")

    def upload_document(self):
        """Upload a new document to vault."""
        print("\n" + "-" * 60)
        print("UPLOAD DOCUMENT")
        print("-" * 60)

        print("\nDocument Types:")
        doc_types = ['essay', 'transcript', 'resume', 'recommendation',
                    'financial-document', 'certificate', 'portfolio', 'other']
        for i, dt in enumerate(doc_types, 1):
            print(f"{i}. {dt}")

        type_choice = input("\nSelect document type (1-8): ").strip()
        try:
            idx = int(type_choice) - 1
            if not 0 <= idx < len(doc_types):
                raise ValueError
            document_type = doc_types[idx]
        except ValueError:
            print("\nInvalid document type.")
            return

        document_name = input("Document name: ").strip()
        if not document_name:
            print("\nDocument name is required.")
            return

        file_path = input("File path: ").strip()
        if not file_path:
            print("\nFile path is required.")
            return

        description = input("Description (optional): ").strip()
        tags = input("Tags (comma-separated, optional): ").strip()

        user_id = self.auth.get_current_user()['username']

        try:
            doc_id = DocumentVaultManager.upload_document(
                user_id, document_name, document_type, file_path,
                description=description, tags=tags
            )
            print(f"\n✓ Document uploaded! Document ID: {doc_id}")
        except Exception as e:
            print(f"\n✗ Error uploading document: {e}")

    # ========== Details ==========

    def view_scholarship_details(self):
        """View detailed scholarship information."""
        scholarship_id = input("\nEnter Scholarship ID: ").strip()
        if not scholarship_id:
            return

        try:
            scholarship_id = int(scholarship_id)
        except ValueError:
            print("\nInvalid scholarship ID.")
            return

        self.display_scholarship_details(scholarship_id)

    def display_scholarship_details(self, scholarship_id: int):
        """Display detailed scholarship information."""
        scholarship = ScholarshipDatabase.get_scholarship_details(scholarship_id)

        if not scholarship:
            print("\nScholarship not found.")
            return

        print(f"\n{'=' * 80}")
        print(f"{scholarship['scholarship_name']}")
        print(f"{'=' * 80}")

        print(f"\nOrganization: {scholarship['organization']} ({scholarship['organization_type']})")

        award_range = f"${scholarship['award_amount_min']:,.0f}"
        if scholarship['award_amount_max']:
            award_range += f" - ${scholarship['award_amount_max']:,.0f}"
        print(f"Award Amount: {award_range} ({scholarship['award_type']})")

        print(f"\nDeadline: {scholarship['application_deadline']}")
        if scholarship['notification_date']:
            print(f"Notification Date: {scholarship['notification_date']}")
        if scholarship['award_disbursement_date']:
            print(f"Disbursement Date: {scholarship['award_disbursement_date']}")

        print(f"\n{scholarship['description']}")

        if scholarship['eligibility_criteria']:
            print(f"\nEligibility Criteria:\n{scholarship['eligibility_criteria']}")

        print(f"\nRequirements:")
        if scholarship['min_gpa']:
            print(f"  - Minimum GPA: {scholarship['min_gpa']}")
        if scholarship['academic_level']:
            print(f"  - Academic Level: {scholarship['academic_level']}")
        if scholarship['required_majors']:
            print(f"  - Required Majors: {scholarship['required_majors']}")
        if scholarship['citizenship_requirements']:
            print(f"  - Citizenship: {scholarship['citizenship_requirements']}")
        if scholarship['financial_need_required']:
            print(f"  - Financial need required")
        if scholarship['merit_based']:
            print(f"  - Merit-based")

        print(f"\nApplication Requirements:")
        if scholarship['essay_required']:
            print(f"  - Essay required")
            if scholarship['essay_prompts']:
                print(f"    Prompts: {scholarship['essay_prompts']}")
        if scholarship['recommendation_letters_required']:
            print(f"  - {scholarship['recommendation_letters_required']} recommendation letters")
        if scholarship['transcript_required']:
            print(f"  - Official transcript")
        if scholarship['interview_required']:
            print(f"  - Interview")

        if scholarship['number_of_awards']:
            print(f"\nNumber of Awards: {scholarship['number_of_awards']}")
        if scholarship['competition_level']:
            print(f"Competition Level: {scholarship['competition_level']}")

        if scholarship['application_url']:
            print(f"\nApplication URL: {scholarship['application_url']}")

        if scholarship['contact_email'] or scholarship['contact_phone']:
            print(f"\nContact Information:")
            if scholarship['contact_email']:
                print(f"  Email: {scholarship['contact_email']}")
            if scholarship['contact_phone']:
                print(f"  Phone: {scholarship['contact_phone']}")

        # Application statistics
        if 'application_stats' in scholarship:
            stats = scholarship['application_stats']
            print(f"\nApplication Statistics:")
            print(f"  Total Applications: {stats['total_applications']}")
            if stats['awards_given']:
                print(f"  Awards Given: {stats['awards_given']}")

    def view_award_history(self):
        """View award history (placeholder for future implementation)."""
        print("\n" + "-" * 60)
        print("AWARD HISTORY")
        print("-" * 60)
        print("\nThis feature will show your scholarship award history.")
        print("Coming soon!")


def main():
    """Main entry point for CLI."""
    cli = ScholarshipFinderCLI()
    cli.run()


if __name__ == "__main__":
    main()
