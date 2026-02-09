"""
Roommate Finder CLI Interface

Command-line interface for roommate matching and communication.
"""

from typing import Optional
from datetime import datetime

from university_system.infrastructure.shared_context import get_auth
from university_system.modules.domain.roommate_finder.services.roommate_service import RoommateService


class RoommateCLI:
    """CLI interface for roommate finder functionality."""

    def __init__(self):
        """Initialize the Roommate Finder CLI."""
        self.service = RoommateService()
        self.auth = get_auth()

    def run(self):
        """Run the CLI (alias for display_menu)."""
        self.display_menu()

    def display_menu(self):
        """Display the main roommate finder menu."""
        if not self.auth.is_logged_in():
            print("\nYou must be logged in to use the Roommate Finder.")
            return

        while True:
            print("\n" + "=" * 60)
            print(" " * 20 + "ROOMMATE FINDER")
            print("=" * 60)
            print("\n[Profile Management]")
            print("1. Create/Update My Profile")
            print("2. View My Profile")
            print("3. Complete Compatibility Questionnaire")
            print("\n[Matching]")
            print("4. Find Roommate Matches")
            print("5. View My Matches")
            print("6. Respond to Match (Accept/Decline)")
            print("\n[Messaging]")
            print("7. Send Message to Match")
            print("8. View Messages")
            print("9. View Unread Messages")
            print("\n[Statistics]")
            print("10. View My Profile Statistics")
            print("\n0. Back to Main Menu")
            print("=" * 60)

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.create_or_update_profile()
            elif choice == '2':
                self.view_profile()
            elif choice == '3':
                self.complete_questionnaire()
            elif choice == '4':
                self.find_matches()
            elif choice == '5':
                self.view_matches()
            elif choice == '6':
                self.respond_to_match()
            elif choice == '7':
                self.send_message()
            elif choice == '8':
                self.view_messages()
            elif choice == '9':
                self.view_unread_messages()
            elif choice == '10':
                self.view_statistics()
            else:
                print("\nInvalid choice. Please try again.")

    def create_or_update_profile(self):
        """Create or update roommate profile."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        existing_profile = self.service.get_profile_by_student(student_id)

        print("\n" + "=" * 60)
        print("CREATE/UPDATE ROOMMATE PROFILE")
        print("=" * 60)

        if existing_profile:
            print("\nExisting profile found. Leave blank to keep current value.")

        display_name = input(f"\nDisplay Name [{existing_profile['display_name'] if existing_profile else ''}]: ").strip()
        if not display_name and not existing_profile:
            print("\nDisplay name is required for new profiles.")
            return

        bio = input(f"Short Bio [{existing_profile['bio'] if existing_profile else ''}]: ").strip()

        budget_min_str = input(f"Minimum Budget ($/month) [{existing_profile['budget_min'] if existing_profile else '0'}]: ").strip()
        budget_min = int(budget_min_str) if budget_min_str else (existing_profile['budget_min'] if existing_profile else 0)

        budget_max_str = input(f"Maximum Budget ($/month) [{existing_profile['budget_max'] if existing_profile else '0'}]: ").strip()
        budget_max = int(budget_max_str) if budget_max_str else (existing_profile['budget_max'] if existing_profile else 0)

        move_in_date = input(f"Preferred Move-in Date (YYYY-MM-DD) [{existing_profile['move_in_date'] if existing_profile else ''}]: ").strip()

        print("\nGender Preference Options:")
        print("1. No preference")
        print("2. Male")
        print("3. Female")
        print("4. Non-binary")
        gender_choice = input("Choice: ").strip()
        gender_map = {'1': 'No preference', '2': 'Male', '3': 'Female', '4': 'Non-binary'}
        preferred_gender = gender_map.get(gender_choice, existing_profile['preferred_gender'] if existing_profile else 'No preference')

        age_str = input(f"Age [{existing_profile['age'] if existing_profile else ''}]: ").strip()
        age = int(age_str) if age_str else (existing_profile['age'] if existing_profile else None)

        major = input(f"Major [{existing_profile['major'] if existing_profile else ''}]: ").strip()
        year_of_study = input(f"Year of Study (Freshman/Sophomore/Junior/Senior) [{existing_profile['year_of_study'] if existing_profile else ''}]: ").strip()

        print("\nSmoking Preference:")
        print("1. No")
        print("2. Yes")
        print("3. Occasionally")
        smoke_choice = input("Choice: ").strip()
        smoke_map = {'1': 'No', '2': 'Yes', '3': 'Occasionally'}
        smoking_preference = smoke_map.get(smoke_choice, existing_profile['smoking_preference'] if existing_profile else 'No')

        print("\nPet Preference:")
        print("1. No pets")
        print("2. Cats only")
        print("3. Dogs only")
        print("4. Any pets welcome")
        pet_choice = input("Choice: ").strip()
        pet_map = {'1': 'No pets', '2': 'Cats only', '3': 'Dogs only', '4': 'Any pets welcome'}
        pet_preference = pet_map.get(pet_choice, existing_profile['pet_preference'] if existing_profile else 'No pets')

        try:
            if existing_profile:
                # Update profile
                updates = {}
                if display_name:
                    updates['display_name'] = display_name
                if bio:
                    updates['bio'] = bio
                if budget_min_str:
                    updates['budget_min'] = budget_min
                if budget_max_str:
                    updates['budget_max'] = budget_max
                if move_in_date:
                    updates['move_in_date'] = move_in_date
                if gender_choice:
                    updates['preferred_gender'] = preferred_gender
                if age_str:
                    updates['age'] = age
                if major:
                    updates['major'] = major
                if year_of_study:
                    updates['year_of_study'] = year_of_study
                if smoke_choice:
                    updates['smoking_preference'] = smoking_preference
                if pet_choice:
                    updates['pet_preference'] = pet_preference

                self.service.update_profile(existing_profile['profile_id'], **updates)
                print("\nProfile updated successfully!")
            else:
                # Create new profile
                profile_id = self.service.create_profile(
                    student_id=student_id,
                    display_name=display_name or user.get('first_name', 'Anonymous'),
                    bio=bio,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    move_in_date=move_in_date or None,
                    preferred_gender=preferred_gender,
                    age=age,
                    major=major,
                    year_of_study=year_of_study,
                    smoking_preference=smoking_preference,
                    pet_preference=pet_preference
                )
                print(f"\nProfile created successfully! Profile ID: {profile_id}")
                print("\nNext step: Complete the compatibility questionnaire to find better matches.")
        except Exception as e:
            print(f"\nError creating/updating profile: {e}")

    def view_profile(self):
        """View current user's profile."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou don't have a roommate profile yet.")
            print("Use option 1 to create a profile.")
            return

        print("\n" + "=" * 60)
        print("MY ROOMMATE PROFILE")
        print("=" * 60)
        print(f"\nDisplay Name: {profile['display_name']}")
        print(f"Bio: {profile['bio'] or 'Not provided'}")
        print(f"Budget: ${profile['budget_min']} - ${profile['budget_max']}/month")
        print(f"Move-in Date: {profile['move_in_date'] or 'Flexible'}")
        print(f"Gender Preference: {profile['preferred_gender']}")
        print(f"Age: {profile['age'] or 'Not provided'}")
        print(f"Major: {profile['major'] or 'Not provided'}")
        print(f"Year: {profile['year_of_study'] or 'Not provided'}")
        print(f"Smoking: {profile['smoking_preference']}")
        print(f"Pets: {profile['pet_preference']}")
        print(f"Status: {'Active' if profile['is_active'] else 'Inactive'}")
        print(f"Created: {profile['created_at']}")
        print(f"Last Updated: {profile['updated_at']}")

    def complete_questionnaire(self):
        """Complete compatibility questionnaire."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        questions = self.service.get_questions()
        if not questions:
            print("\nNo questionnaire available.")
            return

        print("\n" + "=" * 60)
        print("COMPATIBILITY QUESTIONNAIRE")
        print("=" * 60)
        print("\nAnswer the following questions to find compatible roommates.")
        print("For each question, select your answer and importance level.")

        responses = []
        current_category = None

        for question in questions:
            if question['category'] != current_category:
                current_category = question['category']
                print(f"\n{'=' * 60}")
                print(f"{current_category.upper()}")
                print(f"{'=' * 60}")

            print(f"\nQ{question['question_id']}: {question['question_text']}")

            if question['response_type'] == 'scale':
                print(f"Scale: {question['options']}")
                response = input("Your answer: ").strip()
            elif question['response_type'] == 'choice':
                options = question['options'].split('|')
                for i, option in enumerate(options, 1):
                    print(f"  {i}. {option}")
                choice = input("Your choice (number): ").strip()
                try:
                    response = options[int(choice) - 1] if 1 <= int(choice) <= len(options) else options[0]
                except (ValueError, IndexError):
                    response = options[0]
            else:
                response = input("Your answer: ").strip()

            print("\nImportance Level:")
            print("1. Low")
            print("2. Medium")
            print("3. High")
            print("4. Critical")
            imp_choice = input("Choice: ").strip()
            imp_map = {'1': 'Low', '2': 'Medium', '3': 'High', '4': 'Critical'}
            importance = imp_map.get(imp_choice, 'Medium')

            responses.append({
                'question_id': question['question_id'],
                'response_value': response,
                'importance_level': importance
            })

        try:
            self.service.submit_questionnaire(profile['profile_id'], responses)
            print("\n" + "=" * 60)
            print("Questionnaire completed successfully!")
            print("=" * 60)
            print("\nYou can now find compatible roommate matches.")
        except Exception as e:
            print(f"\nError submitting questionnaire: {e}")

    def find_matches(self):
        """Find compatible roommate matches."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        print("\n" + "=" * 60)
        print("FINDING ROOMMATE MATCHES...")
        print("=" * 60)

        min_score_str = input("\nMinimum compatibility score (0-100) [50]: ").strip()
        min_score = float(min_score_str) if min_score_str else 50.0

        limit_str = input("Maximum number of matches [20]: ").strip()
        limit = int(limit_str) if limit_str else 20

        try:
            matches = self.service.find_matches(profile['profile_id'], min_score, limit)

            if not matches:
                print("\nNo matches found with the specified criteria.")
                print("Try lowering the minimum compatibility score or completing the questionnaire.")
                return

            print(f"\nFound {len(matches)} compatible matches:")
            print("=" * 60)

            for i, match in enumerate(matches, 1):
                match_profile = match['profile']
                print(f"\n{i}. {match_profile['display_name']}")
                print(f"   Compatibility Score: {match['compatibility_score']:.1f}%")
                print(f"   Major: {match_profile['major'] or 'Not specified'}")
                print(f"   Year: {match_profile['year_of_study'] or 'Not specified'}")
                print(f"   Budget: ${match_profile['budget_min']}-${match_profile['budget_max']}/month")
                print(f"   Bio: {match_profile['bio'][:100] if match_profile['bio'] else 'No bio'}")
                print(f"   Match Reasons:")
                for reason in match['match_reasons'][:3]:
                    print(f"     - {reason}")

            print("\nUse option 5 to view all matches and send messages.")
        except Exception as e:
            print(f"\nError finding matches: {e}")

    def view_matches(self):
        """View all matches."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        matches = self.service.get_matches(profile['profile_id'])

        if not matches:
            print("\nNo matches found. Use option 4 to find new matches.")
            return

        print("\n" + "=" * 60)
        print("MY ROOMMATE MATCHES")
        print("=" * 60)

        for i, match in enumerate(matches, 1):
            print(f"\n{i}. Match ID: {match['match_id']}")
            print(f"   Name: {match['display_name']}")
            print(f"   Compatibility: {match['compatibility_score']:.1f}%")
            print(f"   Status: {match['status']}")
            print(f"   Major: {match['major'] or 'Not specified'}")
            print(f"   Year: {match['year_of_study'] or 'Not specified'}")

    def respond_to_match(self):
        """Accept or decline a roommate match."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        match_id_str = input("\nEnter Match ID: ").strip()
        if not match_id_str:
            return

        try:
            match_id = int(match_id_str)

            print("\nResponse Options:")
            print("1. Interested")
            print("2. Connected (both agreed)")
            print("3. Decline")
            choice = input("Your choice: ").strip()

            status_map = {'1': 'Interested', '2': 'Connected', '3': 'Declined'}
            status = status_map.get(choice)

            if not status:
                print("\nInvalid choice.")
                return

            self.service.update_match_status(match_id, status)
            print(f"\nMatch status updated to: {status}")
        except Exception as e:
            print(f"\nError updating match: {e}")

    def send_message(self):
        """Send a message to a matched roommate."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        match_id_str = input("\nEnter Match ID: ").strip()
        if not match_id_str:
            return

        try:
            match_id = int(match_id_str)

            print("\nEnter your message (press Enter twice to send):")
            lines = []
            while True:
                line = input()
                if not line and lines:
                    break
                lines.append(line)

            message_text = '\n'.join(lines)

            if not message_text.strip():
                print("\nMessage cannot be empty.")
                return

            message_id = self.service.send_message(match_id, profile['profile_id'], message_text)
            print(f"\nMessage sent successfully! Message ID: {message_id}")
        except Exception as e:
            print(f"\nError sending message: {e}")

    def view_messages(self):
        """View messages for a match."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        match_id_str = input("\nEnter Match ID: ").strip()
        if not match_id_str:
            return

        try:
            match_id = int(match_id_str)
            messages = self.service.get_messages(match_id, profile['profile_id'])

            if not messages:
                print("\nNo messages in this conversation.")
                return

            print("\n" + "=" * 60)
            print(f"CONVERSATION - Match ID: {match_id}")
            print("=" * 60)

            for message in messages:
                sender = "You" if message['direction'] == 'sent' else "Them"
                timestamp = message['sent_at']
                read_status = "[Read]" if message['is_read'] else "[Unread]"

                print(f"\n{sender} - {timestamp} {read_status if message['direction'] == 'sent' else ''}")
                print(f"{message['message_text']}")
                print("-" * 60)

            # Mark messages as read
            self.service.mark_messages_read(match_id, profile['profile_id'])
        except Exception as e:
            print(f"\nError viewing messages: {e}")

    def view_unread_messages(self):
        """View count of unread messages."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        unread_count = self.service.get_unread_count(profile['profile_id'])

        print("\n" + "=" * 60)
        print(f"You have {unread_count} unread message(s)")
        print("=" * 60)

        if unread_count > 0:
            print("\nUse option 8 to view messages for a specific match.")

    def view_statistics(self):
        """View profile statistics."""
        user = self.auth.get_current_user()
        if not user:
            print("\nError: User not found.")
            return

        student_id = user['username']
        profile = self.service.get_profile_by_student(student_id)

        if not profile:
            print("\nYou must create a profile first.")
            return

        stats = self.service.get_profile_stats(profile['profile_id'])

        print("\n" + "=" * 60)
        print("ROOMMATE FINDER STATISTICS")
        print("=" * 60)

        match_stats = stats.get('matches', {})
        message_stats = stats.get('messages', {})

        print("\n[Matching Statistics]")
        print(f"Total Matches: {match_stats.get('total_matches', 0)}")
        print(f"Average Compatibility: {match_stats.get('avg_score', 0):.1f}%")
        print(f"Highest Compatibility: {match_stats.get('max_score', 0):.1f}%")

        print("\n[Messaging Statistics]")
        print(f"Total Messages: {message_stats.get('total_messages', 0)}")
        print(f"Messages Sent: {message_stats.get('sent_count', 0)}")
        print(f"Messages Received: {message_stats.get('received_count', 0)}")


def main():
    """Main entry point for CLI."""
    cli = RoommateCLI()
    cli.display_menu()


if __name__ == '__main__':
    main()


# Alias for compatibility with main CLI
RoommateFinderCLI = RoommateCLI
