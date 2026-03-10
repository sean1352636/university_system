"""
CLI Interface for Interest-Based Social Matching.

Provides command-line interface for:
- Managing interests and personality profile
- Finding and viewing matches
- Buddy requests and messaging
- Team formation and joining
- Club recommendations
- Social activity discovery
"""

from datetime import datetime
from typing import Optional

from education_system.university_system.infrastructure.shared_context import get_auth
from education_system.university_system.modules.domain.social_matching.services.social_matching_service import (
    SocialMatchingService,
    INTEREST_CATEGORIES,
    PERSONALITY_TYPES,
    GROUP_SIZE_PREFERENCES,
    ACTIVITY_LEVELS
)


class SocialMatchingCLI:
    """CLI interface for social matching system."""

    def __init__(self):
        """Initialize the CLI interface."""
        self.service = SocialMatchingService()
        self.auth = get_auth()

    def run(self):
        """Run the main CLI interface."""
        if not self.auth.is_logged_in():
            print("\nYou must be logged in to use Social Matching.")
            return

        while True:
            self.display_main_menu()
            choice = input("\nEnter your choice (1-10, or 0 to exit): ").strip()

            if choice == '0':
                print("\nExiting Social Matching...")
                break
            elif choice == '1':
                self.manage_interests_menu()
            elif choice == '2':
                self.find_matches()
            elif choice == '3':
                self.view_my_matches()
            elif choice == '4':
                self.buddy_requests_menu()
            elif choice == '5':
                self.team_formation_menu()
            elif choice == '6':
                self.view_club_recommendations()
            elif choice == '7':
                self.social_activities_menu()
            elif choice == '8':
                self.manage_personality_profile()
            elif choice == '9':
                self.privacy_settings_menu()
            elif choice == '10':
                self.view_statistics()
            else:
                print("\nInvalid choice. Please try again.")

    def display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 60)
        print("INTEREST-BASED SOCIAL MATCHING".center(60))
        print("=" * 60)
        print("\n1.  Manage My Interests")
        print("2.  Find Interest Matches")
        print("3.  View My Matches")
        print("4.  Buddy Requests")
        print("5.  Team Formation (Sports)")
        print("6.  Club Recommendations")
        print("7.  Social Activities")
        print("8.  Personality Profile")
        print("9.  Privacy Settings")
        print("10. My Statistics")
        print("0.  Exit")

    # ========== Interest Management ==========

    def manage_interests_menu(self):
        """Manage user interests submenu."""
        while True:
            print("\n" + "-" * 50)
            print("MANAGE MY INTERESTS")
            print("-" * 50)
            print("\n1. View My Interests")
            print("2. Add New Interest")
            print("3. Update Interest Level")
            print("4. Remove Interest")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_my_interests()
            elif choice == '2':
                self.add_interest()
            elif choice == '3':
                self.update_interest()
            elif choice == '4':
                self.remove_interest()
            else:
                print("\nInvalid choice.")

    def view_my_interests(self):
        """Display user's current interests."""
        user_id = self.auth.get_current_user()['username']
        interests = self.service.get_user_interests(user_id)

        if not interests:
            print("\nYou haven't added any interests yet.")
            print("Add interests to get matched with like-minded students!")
            return

        print(f"\n{'='*70}")
        print(f"MY INTERESTS ({len(interests)} total)")
        print(f"{'='*70}")

        # Group by category
        by_category = {}
        for interest in interests:
            cat = interest['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(interest)

        for category, items in sorted(by_category.items()):
            print(f"\n{category}:")
            print("-" * 70)
            for item in items:
                level_bar = "█" * item['level'] + "░" * (10 - item['level'])
                visibility = "Public" if item['is_public'] else "Private"
                print(f"  [{item['interest_id']:3d}] {item['name']:30s} "
                      f"Level: {level_bar} ({item['level']}/10)  {visibility}")

    def add_interest(self):
        """Add a new interest to user's profile."""
        print("\n" + "-" * 50)
        print("ADD NEW INTEREST")
        print("-" * 50)

        # Display categories
        print("\nAvailable Categories:")
        for i, cat in enumerate(INTEREST_CATEGORIES, 1):
            print(f"{i}. {cat}")

        cat_choice = input("\nSelect category (1-{}): ".format(len(INTEREST_CATEGORIES))).strip()
        try:
            cat_idx = int(cat_choice) - 1
            if not 0 <= cat_idx < len(INTEREST_CATEGORIES):
                raise ValueError
            category = INTEREST_CATEGORIES[cat_idx]
        except ValueError:
            print("\nInvalid category selection.")
            return

        interest_name = input("\nEnter interest name: ").strip()
        if not interest_name:
            print("\nInterest name cannot be empty.")
            return

        level_input = input("Interest level (1-10, default 5): ").strip()
        try:
            level = int(level_input) if level_input else 5
            if not 1 <= level <= 10:
                raise ValueError
        except ValueError:
            print("\nInvalid level. Using default (5).")
            level = 5

        public_input = input("Make this interest public? (y/n, default y): ").strip().lower()
        is_public = public_input != 'n'

        user_id = self.auth.get_current_user()['username']

        try:
            if self.service.add_user_interest(user_id, category, interest_name, level, is_public):
                print(f"\n✓ Successfully added '{interest_name}' to {category}!")
            else:
                print("\n✗ Failed to add interest (may already exist).")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def update_interest(self):
        """Update the level of an existing interest."""
        self.view_my_interests()

        interest_id = input("\nEnter interest ID to update (or 0 to cancel): ").strip()
        if interest_id == '0':
            return

        try:
            interest_id = int(interest_id)
        except ValueError:
            print("\nInvalid interest ID.")
            return

        new_level = input("Enter new level (1-10): ").strip()
        try:
            new_level = int(new_level)
            if not 1 <= new_level <= 10:
                raise ValueError
        except ValueError:
            print("\nInvalid level. Must be between 1 and 10.")
            return

        user_id = self.auth.get_current_user()['username']

        if self.service.update_interest_level(user_id, interest_id, new_level):
            print(f"\n✓ Interest level updated to {new_level}!")
        else:
            print("\n✗ Failed to update interest.")

    def remove_interest(self):
        """Remove an interest from user's profile."""
        self.view_my_interests()

        interest_id = input("\nEnter interest ID to remove (or 0 to cancel): ").strip()
        if interest_id == '0':
            return

        try:
            interest_id = int(interest_id)
        except ValueError:
            print("\nInvalid interest ID.")
            return

        confirm = input(f"Are you sure you want to remove this interest? (y/n): ").strip().lower()
        if confirm != 'y':
            print("\nCancelled.")
            return

        user_id = self.auth.get_current_user()['username']

        if self.service.remove_user_interest(user_id, interest_id):
            print("\n✓ Interest removed successfully!")
        else:
            print("\n✗ Failed to remove interest.")

    # ========== Matching ==========

    def find_matches(self):
        """Find students with similar interests."""
        print("\n" + "-" * 50)
        print("FIND INTEREST MATCHES")
        print("-" * 50)

        user_id = self.auth.get_current_user()['username']

        min_score = input("\nMinimum compatibility score (0-100, default 30): ").strip()
        try:
            min_score = float(min_score) if min_score else 30.0
        except ValueError:
            min_score = 30.0

        max_results = input("Maximum results (default 20): ").strip()
        try:
            max_results = int(max_results) if max_results else 20
        except ValueError:
            max_results = 20

        print("\nSearching for matches...")
        matches = self.service.find_interest_matches(user_id, min_score, max_results)

        if not matches:
            print("\nNo matches found. Try:")
            print("  - Lowering the minimum score")
            print("  - Adding more interests to your profile")
            print("  - Making your interests public")
            return

        print(f"\n{'='*80}")
        print(f"FOUND {len(matches)} MATCHES")
        print(f"{'='*80}")

        for i, match in enumerate(matches, 1):
            print(f"\n{i}. Student ID: {match['user_id']}")
            print(f"   Compatibility Score: {match['compatibility_score']:.1f}%")
            print(f"   Shared Interests ({match['shared_count']}):")
            for interest in match['shared_interests'][:5]:
                print(f"     • {interest}")
            if len(match['shared_interests']) > 5:
                print(f"     ... and {len(match['shared_interests']) - 5} more")

        # Option to send buddy request
        if matches:
            send_request = input("\nSend buddy request to a match? (enter number or 0 to skip): ").strip()
            if send_request and send_request != '0':
                try:
                    idx = int(send_request) - 1
                    if 0 <= idx < len(matches):
                        receiver_id = matches[idx]['user_id']
                        self.send_buddy_request_to(receiver_id)
                except ValueError:
                    pass

    def view_my_matches(self):
        """View saved matches."""
        user_id = self.auth.get_current_user()['username']
        matches = self.service.get_saved_matches(user_id)

        if not matches:
            print("\nNo saved matches. Use 'Find Interest Matches' to discover connections!")
            return

        print(f"\n{'='*80}")
        print(f"MY SAVED MATCHES ({len(matches)})")
        print(f"{'='*80}")

        for match in matches:
            print(f"\nMatch ID: {match['match_id']}")
            print(f"Student: {match['user_id']}")
            print(f"Compatibility: {match['score']:.1f}%")
            print(f"Shared Interests: {', '.join(match['shared_interests'][:3])}")
            if match['reason']:
                print(f"Reason: {match['reason']}")

    # ========== Buddy Requests ==========

    def buddy_requests_menu(self):
        """Buddy requests submenu."""
        while True:
            print("\n" + "-" * 50)
            print("BUDDY REQUESTS")
            print("-" * 50)
            print("\n1. Send Buddy Request")
            print("2. View Received Requests")
            print("3. View Sent Requests")
            print("4. Find Study Abroad Buddies")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.send_buddy_request()
            elif choice == '2':
                self.view_received_requests()
            elif choice == '3':
                self.view_sent_requests()
            elif choice == '4':
                self.find_study_abroad_buddies()
            else:
                print("\nInvalid choice.")

    def send_buddy_request(self):
        """Send a buddy request to another student."""
        receiver_id = input("\nEnter student ID to send request to: ").strip()
        if not receiver_id:
            return

        self.send_buddy_request_to(receiver_id)

    def send_buddy_request_to(self, receiver_id: str):
        """Helper to send buddy request."""
        print("\nRequest Types:")
        print("1. General Buddy")
        print("2. Study Abroad")
        print("3. Sports/Fitness")
        print("4. Academic/Study")
        print("5. Other")

        type_choice = input("\nSelect type (1-5): ").strip()
        request_types = {
            '1': 'general',
            '2': 'study_abroad',
            '3': 'sports',
            '4': 'academic',
            '5': 'other'
        }
        request_type = request_types.get(type_choice, 'general')

        destination = ""
        if request_type == 'study_abroad':
            destination = input("Study abroad destination: ").strip()

        message = input("Personal message (optional): ").strip()

        user_id = self.auth.get_current_user()['username']

        try:
            request_id = self.service.send_buddy_request(
                user_id, receiver_id, request_type, destination, message
            )
            print(f"\n✓ Buddy request sent successfully! (ID: {request_id})")
        except PermissionError as e:
            print(f"\n✗ {e}")
        except Exception as e:
            print(f"\n✗ Error sending request: {e}")

    def view_received_requests(self):
        """View received buddy requests."""
        user_id = self.auth.get_current_user()['username']
        requests = self.service.get_buddy_requests(user_id, 'pending', 'received')

        if not requests:
            print("\nNo pending buddy requests.")
            return

        print(f"\n{'='*70}")
        print(f"RECEIVED BUDDY REQUESTS ({len(requests)})")
        print(f"{'='*70}")

        for i, req in enumerate(requests, 1):
            print(f"\n{i}. Request ID: {req['request_id']}")
            print(f"   From: {req['sender_id']}")
            print(f"   Type: {req['type']}")
            if req['destination']:
                print(f"   Destination: {req['destination']}")
            if req['message']:
                print(f"   Message: {req['message']}")
            print(f"   Sent: {req['sent_at']}")

        # Respond to request
        respond = input("\nRespond to a request? (enter number or 0 to skip): ").strip()
        if respond and respond != '0':
            try:
                idx = int(respond) - 1
                if 0 <= idx < len(requests):
                    request_id = requests[idx]['request_id']
                    accept = input("Accept this request? (y/n): ").strip().lower()

                    if self.service.respond_to_buddy_request(request_id, user_id, accept == 'y'):
                        status = "accepted" if accept == 'y' else "declined"
                        print(f"\n✓ Request {status}!")
                    else:
                        print("\n✗ Failed to respond to request.")
            except ValueError:
                pass

    def view_sent_requests(self):
        """View sent buddy requests."""
        user_id = self.auth.get_current_user()['username']
        requests = self.service.get_buddy_requests(user_id, 'pending', 'sent')

        if not requests:
            print("\nNo pending sent requests.")
            return

        print(f"\n{'='*70}")
        print(f"SENT BUDDY REQUESTS ({len(requests)})")
        print(f"{'='*70}")

        for req in requests:
            print(f"\nRequest ID: {req['request_id']}")
            print(f"To: {req['receiver_id']}")
            print(f"Type: {req['type']}")
            if req['destination']:
                print(f"Destination: {req['destination']}")
            print(f"Sent: {req['sent_at']}")
            print(f"Status: {req['status']}")

    def find_study_abroad_buddies(self):
        """Find students interested in same study abroad destination."""
        destination = input("\nEnter study abroad destination: ").strip()
        if not destination:
            return

        user_id = self.auth.get_current_user()['username']
        buddies = self.service.find_study_abroad_buddies(user_id, destination)

        if not buddies:
            print(f"\nNo students found interested in {destination}.")
            return

        print(f"\n{'='*70}")
        print(f"STUDY ABROAD BUDDIES FOR {destination.upper()} ({len(buddies)})")
        print(f"{'='*70}")

        for i, buddy in enumerate(buddies, 1):
            print(f"\n{i}. Student: {buddy['user_id']}")
            print(f"   Compatibility: {buddy['compatibility_score']:.1f}%")
            if buddy['shared_interests']:
                print(f"   Shared Interests: {', '.join(buddy['shared_interests'][:3])}")

    # ========== Team Formation ==========

    def team_formation_menu(self):
        """Team formation submenu."""
        while True:
            print("\n" + "-" * 50)
            print("INTRAMURAL TEAM FORMATION")
            print("-" * 50)
            print("\n1. Create New Team")
            print("2. Browse Available Teams")
            print("3. Join a Team")
            print("4. My Teams")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.create_team()
            elif choice == '2':
                self.browse_teams()
            elif choice == '3':
                self.join_team()
            elif choice == '4':
                self.view_my_teams()
            else:
                print("\nInvalid choice.")

    def create_team(self):
        """Create a new intramural team."""
        print("\n" + "-" * 50)
        print("CREATE NEW TEAM")
        print("-" * 50)

        team_name = input("\nTeam name: ").strip()
        if not team_name:
            return

        sport_type = input("Sport type (e.g., Basketball, Soccer): ").strip()
        if not sport_type:
            return

        team_size = input("Team size: ").strip()
        try:
            team_size = int(team_size)
        except ValueError:
            print("\nInvalid team size.")
            return

        print("\nSkill Levels: Beginner, Intermediate, Advanced, Mixed")
        skill_level = input("Skill level: ").strip()

        description = input("Team description (optional): ").strip()

        user_id = self.auth.get_current_user()['username']

        try:
            team_id = self.service.create_team(
                user_id, team_name, sport_type, team_size, skill_level, description
            )
            print(f"\n✓ Team created successfully! (ID: {team_id})")
            print(f"You are the team captain. Start recruiting members!")
        except Exception as e:
            print(f"\n✗ Error creating team: {e}")

    def browse_teams(self):
        """Browse available teams looking for members."""
        sport_filter = input("\nFilter by sport (or press Enter for all): ").strip()
        skill_filter = input("Filter by skill level (or press Enter for all): ").strip()

        teams = self.service.get_available_teams(sport_filter, skill_filter)

        if not teams:
            print("\nNo available teams found.")
            return

        print(f"\n{'='*80}")
        print(f"AVAILABLE TEAMS ({len(teams)})")
        print(f"{'='*80}")

        for i, team in enumerate(teams, 1):
            print(f"\n{i}. {team['team_name']}")
            print(f"   Team ID: {team['team_id']}")
            print(f"   Sport: {team['sport_type']}")
            print(f"   Members: {team['current_members']}/{team['team_size']}")
            print(f"   Skill Level: {team['skill_level']}")
            if team['description']:
                print(f"   Description: {team['description']}")
            print(f"   Created: {team['created_at']}")

    def join_team(self):
        """Join an existing team."""
        self.browse_teams()

        team_id = input("\nEnter team ID to join (or 0 to cancel): ").strip()
        if team_id == '0':
            return

        try:
            team_id = int(team_id)
        except ValueError:
            print("\nInvalid team ID.")
            return

        user_id = self.auth.get_current_user()['username']

        if self.service.join_team(team_id, user_id):
            print("\n✓ Successfully joined the team!")
        else:
            print("\n✗ Failed to join team (may be full or you're already a member).")

    def view_my_teams(self):
        """View teams the user has joined."""
        user_id = self.auth.get_current_user()['username']

        # Get teams where user is a member
        with self.service.service.get_connection() as conn:
            cursor = conn.execute("""
                SELECT t.team_id, t.team_name, t.sport_type, t.current_members,
                       t.team_size, t.skill_level, tm.role
                FROM team_formations t
                JOIN team_members tm ON t.team_id = tm.team_id
                WHERE tm.user_id = ?
            """, (user_id,))

            teams = cursor.fetchall()

        if not teams:
            print("\nYou haven't joined any teams yet.")
            return

        print(f"\n{'='*70}")
        print(f"MY TEAMS ({len(teams)})")
        print(f"{'='*70}")

        for team in teams:
            print(f"\n{team[1]} ({team[2]})")
            print(f"  Role: {team[6]}")
            print(f"  Members: {team[3]}/{team[4]}")
            print(f"  Skill Level: {team[5]}")

    # ========== Club Recommendations ==========

    def view_club_recommendations(self):
        """View personalized club recommendations."""
        print("\n" + "-" * 50)
        print("CLUB RECOMMENDATIONS")
        print("-" * 50)

        user_id = self.auth.get_current_user()['username']

        print("\nGenerating personalized recommendations...")
        recommendations = self.service.generate_club_recommendations(user_id)

        if not recommendations:
            print("\nNo recommendations available.")
            print("Add interests to your profile to get club recommendations!")
            return

        print(f"\n{'='*80}")
        print(f"RECOMMENDED CLUBS ({len(recommendations)})")
        print(f"{'='*80}")

        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec['club_name']}")
            print(f"   Category: {rec['club_category']}")
            print(f"   Match Score: {rec['match_score']}")
            print(f"   Reason: {rec['reason']}")

    # ========== Social Activities ==========

    def social_activities_menu(self):
        """Social activities submenu."""
        while True:
            print("\n" + "-" * 50)
            print("SOCIAL ACTIVITIES")
            print("-" * 50)
            print("\n1. View Suggested Activities")
            print("2. Create New Activity")
            print("3. My Activities")
            print("4. Join an Activity")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_suggested_activities()
            elif choice == '2':
                self.create_activity()
            elif choice == '3':
                self.view_my_activities()
            elif choice == '4':
                self.join_activity()
            else:
                print("\nInvalid choice.")

    def view_suggested_activities(self):
        """View suggested activities based on interests."""
        user_id = self.auth.get_current_user()['username']

        days = input("\nDays ahead to search (default 30): ").strip()
        try:
            days = int(days) if days else 30
        except ValueError:
            days = 30

        activities = self.service.get_suggested_activities(user_id, days)

        if not activities:
            print("\nNo suggested activities found.")
            return

        print(f"\n{'='*80}")
        print(f"SUGGESTED ACTIVITIES ({len(activities)})")
        print(f"{'='*80}")

        for i, activity in enumerate(activities, 1):
            print(f"\n{i}. {activity['activity_name']}")
            print(f"   Activity ID: {activity['activity_id']}")
            print(f"   Type: {activity['activity_type']}")
            print(f"   Date: {activity['activity_date']} at {activity['activity_time']}")
            print(f"   Location: {activity['location']}")
            print(f"   Participants: {activity['current_participants']}/{activity['max_participants']}")
            print(f"   Match Score: {activity['match_score']}")
            if activity['description']:
                print(f"   Description: {activity['description']}")

    def create_activity(self):
        """Create a new social activity."""
        print("\n" + "-" * 50)
        print("CREATE SOCIAL ACTIVITY")
        print("-" * 50)

        activity_name = input("\nActivity name: ").strip()
        if not activity_name:
            return

        activity_type = input("Activity type: ").strip()
        description = input("Description: ").strip()
        location = input("Location: ").strip()

        activity_date = input("Date (YYYY-MM-DD): ").strip()
        activity_time = input("Time (HH:MM): ").strip()

        max_participants = input("Maximum participants: ").strip()
        try:
            max_participants = int(max_participants)
        except ValueError:
            print("\nInvalid number.")
            return

        interests = input("Related interests (comma-separated): ").strip()
        interests_list = [i.strip() for i in interests.split(',') if i.strip()]

        user_id = self.auth.get_current_user()['username']

        try:
            activity_id = self.service.create_social_activity(
                user_id, activity_name, activity_type, description, location,
                activity_date, activity_time, max_participants, interests_list
            )
            print(f"\n✓ Activity created successfully! (ID: {activity_id})")
        except Exception as e:
            print(f"\n✗ Error creating activity: {e}")

    def view_my_activities(self):
        """View activities user has joined."""
        user_id = self.auth.get_current_user()['username']
        activities = self.service.get_my_activities(user_id)

        if not activities:
            print("\nYou haven't joined any activities yet.")
            return

        print(f"\n{'='*70}")
        print(f"MY ACTIVITIES ({len(activities)})")
        print(f"{'='*70}")

        for activity in activities:
            print(f"\n{activity['activity_name']}")
            print(f"  Type: {activity['activity_type']}")
            print(f"  Date: {activity['activity_date']} at {activity['activity_time']}")
            print(f"  Location: {activity['location']}")
            print(f"  RSVP Status: {activity['my_rsvp']}")
            print(f"  Participants: {activity['current_participants']}/{activity['max_participants']}")

    def join_activity(self):
        """Join a social activity."""
        self.view_suggested_activities()

        activity_id = input("\nEnter activity ID to join (or 0 to cancel): ").strip()
        if activity_id == '0':
            return

        try:
            activity_id = int(activity_id)
        except ValueError:
            print("\nInvalid activity ID.")
            return

        print("\nRSVP Status:")
        print("1. Going")
        print("2. Interested")
        print("3. Maybe")

        status_choice = input("\nSelect status (1-3): ").strip()
        status_map = {'1': 'going', '2': 'interested', '3': 'maybe'}
        rsvp_status = status_map.get(status_choice, 'interested')

        user_id = self.auth.get_current_user()['username']

        if self.service.join_activity(activity_id, user_id, rsvp_status):
            print(f"\n✓ Successfully joined activity with status '{rsvp_status}'!")
        else:
            print("\n✗ Failed to join activity (may be full or already joined).")

    # ========== Personality Profile ==========

    def manage_personality_profile(self):
        """Manage personality profile."""
        print("\n" + "-" * 50)
        print("PERSONALITY PROFILE")
        print("-" * 50)

        user_id = self.auth.get_current_user()['username']
        profile = self.service.get_personality_profile(user_id)

        if profile:
            print("\nCurrent Profile:")
            print(f"  Personality Type: {profile['personality_type']}")
            print(f"  Extroversion: {profile['extroversion_score']}/10")
            print(f"  Openness: {profile['openness_score']}/10")
            print(f"  Social Preference: {profile['social_preference']}")
            print(f"  Group Size: {profile['group_size_preference']}")
            print(f"  Activity Level: {profile['activity_level']}")

            update = input("\nUpdate profile? (y/n): ").strip().lower()
            if update != 'y':
                return

        print("\nPersonality Types:")
        for i, pt in enumerate(PERSONALITY_TYPES, 1):
            print(f"{i}. {pt}")

        pt_choice = input("\nSelect type (1-{}): ".format(len(PERSONALITY_TYPES))).strip()
        try:
            pt_idx = int(pt_choice) - 1
            personality_type = PERSONALITY_TYPES[pt_idx]
        except (ValueError, IndexError):
            print("\nInvalid selection.")
            return

        extroversion = input("Extroversion score (1-10): ").strip()
        openness = input("Openness to new experiences (1-10): ").strip()

        try:
            extroversion = int(extroversion)
            openness = int(openness)
        except ValueError:
            print("\nInvalid scores.")
            return

        social_pref = input("Social preference (e.g., 'One-on-one conversations'): ").strip()

        print("\nGroup Size Preferences:")
        for i, gsp in enumerate(GROUP_SIZE_PREFERENCES, 1):
            print(f"{i}. {gsp}")

        gsp_choice = input("\nSelect preference (1-{}): ".format(len(GROUP_SIZE_PREFERENCES))).strip()
        try:
            gsp_idx = int(gsp_choice) - 1
            group_size = GROUP_SIZE_PREFERENCES[gsp_idx]
        except (ValueError, IndexError):
            print("\nInvalid selection.")
            return

        print("\nActivity Levels:")
        for i, al in enumerate(ACTIVITY_LEVELS, 1):
            print(f"{i}. {al}")

        al_choice = input("\nSelect level (1-{}): ".format(len(ACTIVITY_LEVELS))).strip()
        try:
            al_idx = int(al_choice) - 1
            activity_level = ACTIVITY_LEVELS[al_idx]
        except (ValueError, IndexError):
            print("\nInvalid selection.")
            return

        try:
            self.service.set_personality_profile(
                user_id, personality_type, extroversion, openness,
                social_pref, group_size, activity_level
            )
            print("\n✓ Personality profile updated!")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Privacy Settings ==========

    def privacy_settings_menu(self):
        """Manage privacy settings."""
        print("\n" + "-" * 50)
        print("PRIVACY SETTINGS")
        print("-" * 50)

        user_id = self.auth.get_current_user()['username']
        settings = self.service.get_privacy_settings(user_id)

        print("\nCurrent Settings:")
        print(f"  1. Allow Matching: {'Yes' if settings['allow_matching'] else 'No'}")
        print(f"  2. Show Profile: {'Yes' if settings['show_profile'] else 'No'}")
        print(f"  3. Allow Messages: {'Yes' if settings['allow_messages'] else 'No'}")
        print(f"  4. Show Interests: {'Yes' if settings['show_interests'] else 'No'}")
        print(f"  5. Show in Search: {'Yes' if settings['show_in_search'] else 'No'}")
        print(f"  6. Match Same Major: {'Yes' if settings['match_same_major'] else 'No'}")
        print(f"  7. Match Same Year: {'Yes' if settings['match_same_year'] else 'No'}")

        print("\nToggle settings:")
        choice = input("Enter setting number to toggle (or 0 to save): ").strip()

        if choice == '0':
            return

        try:
            choice = int(choice)
            if 1 <= choice <= 7:
                keys = ['allow_matching', 'show_profile', 'allow_messages',
                       'show_interests', 'show_in_search', 'match_same_major',
                       'match_same_year']
                key = keys[choice - 1]
                settings[key] = not settings[key]

                self.service.set_privacy_settings(user_id, **settings)
                print(f"\n✓ Setting updated!")
                self.privacy_settings_menu()  # Refresh display
        except ValueError:
            print("\nInvalid choice.")

    # ========== Statistics ==========

    def view_statistics(self):
        """View user's social matching statistics."""
        user_id = self.auth.get_current_user()['username']
        stats = self.service.get_user_statistics(user_id)

        print("\n" + "=" * 50)
        print("MY SOCIAL MATCHING STATISTICS")
        print("=" * 50)
        print(f"\nTotal Interests: {stats['total_interests']}")
        print(f"Total Matches Found: {stats['total_matches']}")
        print(f"Buddy Requests Sent: {stats['requests_sent']}")
        print(f"Buddy Requests Received: {stats['requests_received']}")
        print(f"Teams Joined: {stats['teams_joined']}")
        print(f"Activities Joined: {stats['activities_joined']}")


def main():
    """Main entry point for CLI."""
    cli = SocialMatchingCLI()
    cli.run()


if __name__ == "__main__":
    main()
