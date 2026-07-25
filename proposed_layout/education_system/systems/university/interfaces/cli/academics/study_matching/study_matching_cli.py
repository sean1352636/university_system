"""
CLI Interface for Peer Study Matching.

Provides command-line interface for:
- Managing study profile and preferences
- Finding compatible study partners
- Creating and joining study groups
- Virtual study rooms with Pomodoro timer
- Anonymous Q&A board
- Study session analytics
"""

from datetime import datetime
from typing import Optional

from education_system.systems.university.infrastructure.shared_context import get_auth
from education_system.systems.university.domain.academics.study_matching.services.study_matching_service import StudyMatchingService


# Constants for study preferences
STUDY_STYLES = ["Visual", "Auditory", "Kinesthetic", "Reading/Writing"]
PREFERRED_TIMES = ["Morning", "Afternoon", "Evening", "Night"]
GROUP_SIZES = ["Solo", "Small (2-4)", "Medium (5-8)", "Large (9+)"]
COMMUNICATION_STYLES = ["Collaborative", "Independent", "Mixed"]
NOISE_PREFERENCES = ["Quiet", "Moderate", "Lively"]
QA_CATEGORIES = ["General", "Concepts", "Problem Solving", "Projects", "Exam Prep"]
DIFFICULTY_LEVELS = ["Easy", "Medium", "Hard"]


class StudyMatchingCLI:
    """CLI interface for peer study matching system."""

    def __init__(self):
        """Initialize the CLI interface."""
        self.service = StudyMatchingService()
        self.auth = get_auth()

    def run(self):
        """Run the main CLI interface."""
        if not self.auth.is_logged_in():
            print("\nYou must be logged in to use Peer Study Matching.")
            return

        while True:
            self.display_main_menu()
            choice = input("\nEnter your choice (1-8, or 0 to exit): ").strip()

            if choice == '0':
                print("\nExiting Peer Study Matching...")
                break
            elif choice == '1':
                self.study_profile_menu()
            elif choice == '2':
                self.find_study_partners()
            elif choice == '3':
                self.study_groups_menu()
            elif choice == '4':
                self.virtual_study_rooms_menu()
            elif choice == '5':
                self.qa_board_menu()
            elif choice == '6':
                self.pomodoro_menu()
            elif choice == '7':
                self.view_analytics()
            elif choice == '8':
                self.quick_start_guide()
            else:
                print("\nInvalid choice. Please try again.")

    def display_main_menu(self):
        """Display the main menu."""
        print("\n" + "=" * 70)
        print("PEER STUDY MATCHING & COLLABORATION".center(70))
        print("=" * 70)
        print("\n1.  My Study Profile")
        print("2.  Find Study Partners")
        print("3.  Study Groups")
        print("4.  Virtual Study Rooms")
        print("5.  Q&A Board")
        print("6.  Pomodoro Timer")
        print("7.  My Analytics")
        print("8.  Quick Start Guide")
        print("0.  Exit")

    # ========== Study Profile Management ==========

    def study_profile_menu(self):
        """Study profile submenu."""
        while True:
            print("\n" + "-" * 60)
            print("MY STUDY PROFILE")
            print("-" * 60)
            print("\n1. View My Profile")
            print("2. Create/Update Profile")
            print("3. View Compatibility Factors")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_my_profile()
            elif choice == '2':
                self.create_update_profile()
            elif choice == '3':
                self.explain_compatibility()
            else:
                print("\nInvalid choice.")

    def view_my_profile(self):
        """Display user's study profile."""
        user_id = self.auth.get_current_user()['username']
        profile = self.service.get_study_profile(user_id)

        if not profile:
            print("\nYou haven't created a study profile yet.")
            print("Create a profile to find compatible study partners!")
            return

        print(f"\n{'='*70}")
        print("MY STUDY PROFILE")
        print(f"{'='*70}")
        print(f"\nStudent ID: {profile['student_id']}")
        print(f"Study Style: {profile['study_style']}")
        print(f"Preferred Time: {profile['preferred_time']}")
        print(f"Group Size Preference: {profile['group_size_preference']}")
        print(f"Communication Style: {profile['communication_style']}")
        print(f"Noise Preference: {profile['noise_preference']}")

        if profile['availability']:
            print(f"\nAvailability: {', '.join(profile['availability'])}")

        if profile['interests']:
            print(f"\nAcademic Interests: {', '.join(profile['interests'])}")

        print(f"\nCreated: {profile['created_at']}")
        print(f"Last Updated: {profile['updated_at']}")

    def create_update_profile(self):
        """Create or update study profile."""
        print("\n" + "-" * 60)
        print("CREATE/UPDATE STUDY PROFILE")
        print("-" * 60)

        # Study Style
        print("\nStudy Style:")
        for i, style in enumerate(STUDY_STYLES, 1):
            print(f"{i}. {style}")
        style_choice = input(f"\nSelect your learning style (1-{len(STUDY_STYLES)}): ").strip()
        try:
            study_style = STUDY_STYLES[int(style_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid selection. Using 'Visual'.")
            study_style = "Visual"

        # Preferred Time
        print("\nPreferred Study Time:")
        for i, time in enumerate(PREFERRED_TIMES, 1):
            print(f"{i}. {time}")
        time_choice = input(f"\nSelect your preferred time (1-{len(PREFERRED_TIMES)}): ").strip()
        try:
            preferred_time = PREFERRED_TIMES[int(time_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid selection. Using 'Evening'.")
            preferred_time = "Evening"

        # Group Size
        print("\nGroup Size Preference:")
        for i, size in enumerate(GROUP_SIZES, 1):
            print(f"{i}. {size}")
        size_choice = input(f"\nSelect your preference (1-{len(GROUP_SIZES)}): ").strip()
        try:
            group_size = GROUP_SIZES[int(size_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid selection. Using 'Small (2-4)'.")
            group_size = "Small (2-4)"

        # Communication Style
        print("\nCommunication Style:")
        for i, style in enumerate(COMMUNICATION_STYLES, 1):
            print(f"{i}. {style}")
        comm_choice = input(f"\nSelect your style (1-{len(COMMUNICATION_STYLES)}): ").strip()
        try:
            communication_style = COMMUNICATION_STYLES[int(comm_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid selection. Using 'Collaborative'.")
            communication_style = "Collaborative"

        # Noise Preference
        print("\nNoise Preference:")
        for i, noise in enumerate(NOISE_PREFERENCES, 1):
            print(f"{i}. {noise}")
        noise_choice = input(f"\nSelect your preference (1-{len(NOISE_PREFERENCES)}): ").strip()
        try:
            noise_preference = NOISE_PREFERENCES[int(noise_choice) - 1]
        except (ValueError, IndexError):
            print("\nInvalid selection. Using 'Quiet'.")
            noise_preference = "Quiet"

        # Availability
        print("\nAvailability (comma-separated, e.g., 'Monday Evening, Wednesday Morning'):")
        availability_input = input("Enter your available times (or press Enter to skip): ").strip()
        availability = [a.strip() for a in availability_input.split(',')] if availability_input else []

        # Interests
        print("\nAcademic Interests (comma-separated, e.g., 'Mathematics, Physics, Programming'):")
        interests_input = input("Enter your interests (or press Enter to skip): ").strip()
        interests = [i.strip() for i in interests_input.split(',')] if interests_input else []

        user_id = self.auth.get_current_user()['username']

        try:
            profile_id = self.service.create_study_profile(
                student_id=user_id,
                study_style=study_style,
                preferred_time=preferred_time,
                group_size_preference=group_size,
                communication_style=communication_style,
                noise_preference=noise_preference,
                availability=availability,
                interests=interests
            )
            print(f"\n✓ Study profile saved successfully! (ID: {profile_id})")
            print("You can now find compatible study partners.")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def explain_compatibility(self):
        """Explain compatibility scoring factors."""
        print("\n" + "=" * 70)
        print("COMPATIBILITY FACTORS")
        print("=" * 70)
        print("\nYour compatibility score with other students is calculated based on:")
        print("\n1. Study Style Match (25% weight)")
        print("   - Visual, Auditory, Kinesthetic, or Reading/Writing learners")
        print("\n2. Preferred Time Match (20% weight)")
        print("   - Morning, Afternoon, Evening, or Night study preferences")
        print("\n3. Group Size Preference (15% weight)")
        print("   - Solo, Small, Medium, or Large group preferences")
        print("\n4. Communication Style (20% weight)")
        print("   - Collaborative, Independent, or Mixed approaches")
        print("\n5. Noise Preference (10% weight)")
        print("   - Quiet, Moderate, or Lively study environments")
        print("\n6. Interest Overlap (10% weight)")
        print("   - Shared academic interests and subjects")
        print("\nMinimum compatibility threshold: 30%")
        print("Scores above 70% indicate highly compatible study partners!")

    # ========== Find Study Partners ==========

    def find_study_partners(self):
        """Find compatible study partners."""
        user_id = self.auth.get_current_user()['username']

        # Check if profile exists
        profile = self.service.get_study_profile(user_id)
        if not profile:
            print("\nYou need to create a study profile first!")
            create = input("Would you like to create one now? (y/n): ").strip().lower()
            if create == 'y':
                self.create_update_profile()
            return

        print("\n" + "-" * 60)
        print("FIND STUDY PARTNERS")
        print("-" * 60)

        # Optional course filter
        course_id = input("\nFilter by course ID (or press Enter for all courses): ").strip()
        course_id = course_id if course_id else None

        limit_input = input("Number of matches to show (default 10): ").strip()
        try:
            limit = int(limit_input) if limit_input else 10
        except ValueError:
            limit = 10

        print("\nSearching for compatible study partners...")

        try:
            matches = self.service.find_study_matches(user_id, course_id, limit)

            if not matches:
                print("\nNo compatible study partners found.")
                print("Try updating your profile or removing course filter.")
                return

            print(f"\n{'='*80}")
            print(f"FOUND {len(matches)} COMPATIBLE STUDY PARTNERS")
            print(f"{'='*80}")

            for i, match in enumerate(matches, 1):
                compatibility = match['compatibility_score']
                bars = int(compatibility / 10)
                bar_display = "█" * bars + "░" * (10 - bars)

                print(f"\n{i}. {match['name']} (ID: {match['student_id']})")
                print(f"   Compatibility: {bar_display} {compatibility}%")
                print(f"   Study Style: {match['study_style']}")
                print(f"   Preferred Time: {match['preferred_time']}")
                print(f"   Match Reason: {match['match_reason']}")

            # Option to send match suggestion
            send = input("\nWould you like to send a match suggestion to someone? (y/n): ").strip().lower()
            if send == 'y':
                match_num = input("Enter match number: ").strip()
                try:
                    match_idx = int(match_num) - 1
                    if 0 <= match_idx < len(matches):
                        suggested_id = matches[match_idx]['student_id']
                        suggestion_id = self.service.create_match_suggestion(user_id, suggested_id, course_id)
                        print(f"\n✓ Match suggestion sent! (Suggestion ID: {suggestion_id})")
                    else:
                        print("\nInvalid match number.")
                except ValueError:
                    print("\nInvalid input.")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Study Groups ==========

    def study_groups_menu(self):
        """Study groups submenu."""
        while True:
            print("\n" + "-" * 60)
            print("STUDY GROUPS")
            print("-" * 60)
            print("\n1. My Study Groups")
            print("2. Create New Group")
            print("3. Browse Available Groups")
            print("4. Join a Group")
            print("5. View Group Details")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.view_my_study_groups()
            elif choice == '2':
                self.create_study_group()
            elif choice == '3':
                self.browse_study_groups()
            elif choice == '4':
                self.join_study_group()
            elif choice == '5':
                self.view_group_details()
            else:
                print("\nInvalid choice.")

    def view_my_study_groups(self):
        """View student's study groups."""
        user_id = self.auth.get_current_user()['username']
        groups = self.service.get_student_study_groups(user_id)

        if not groups:
            print("\nYou're not a member of any study groups yet.")
            return

        print(f"\n{'='*80}")
        print(f"MY STUDY GROUPS ({len(groups)} groups)")
        print(f"{'='*80}")

        for i, group in enumerate(groups, 1):
            print(f"\n{i}. {group['group_name']} (ID: {group['group_id']})")
            print(f"   Course: {group['course_id']}")
            print(f"   Role: {group['role']}")
            print(f"   Members: {group['current_members']}/{group['max_members']}")
            print(f"   Type: {'Virtual' if group['is_virtual'] else 'In-Person'}")
            print(f"   Status: {group['status']}")
            if group['meeting_schedule']:
                print(f"   Schedule: {group['meeting_schedule']}")
            print(f"   Joined: {group['joined_at']}")

    def create_study_group(self):
        """Create a new study group."""
        print("\n" + "-" * 60)
        print("CREATE STUDY GROUP")
        print("-" * 60)

        course_id = input("\nCourse ID: ").strip()
        if not course_id:
            print("\nCourse ID is required.")
            return

        group_name = input("Group name: ").strip()
        if not group_name:
            print("\nGroup name is required.")
            return

        max_members_input = input("Maximum members (default 6): ").strip()
        try:
            max_members = int(max_members_input) if max_members_input else 6
        except ValueError:
            max_members = 6

        meeting_schedule = input("Meeting schedule (optional): ").strip()
        meeting_schedule = meeting_schedule if meeting_schedule else None

        is_virtual_input = input("Virtual group? (y/n, default y): ").strip().lower()
        is_virtual = is_virtual_input != 'n'

        location = None
        if is_virtual:
            location = input("Virtual platform (e.g., Zoom, Discord): ").strip()
        else:
            location = input("Meeting location: ").strip()

        user_id = self.auth.get_current_user()['username']

        try:
            group_id = self.service.create_study_group(
                course_id=course_id,
                group_name=group_name,
                creator_id=user_id,
                max_members=max_members,
                meeting_schedule=meeting_schedule,
                location=location,
                is_virtual=is_virtual
            )
            print(f"\n✓ Study group created successfully! (ID: {group_id})")
            print("You are the group admin. Share the group ID with others to invite them.")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def browse_study_groups(self):
        """Browse available study groups."""
        course_id = input("\nEnter course ID to browse groups: ").strip()
        if not course_id:
            print("\nCourse ID is required.")
            return

        try:
            groups = self.service.get_available_study_groups(course_id)

            if not groups:
                print(f"\nNo available study groups found for course {course_id}.")
                return

            print(f"\n{'='*80}")
            print(f"AVAILABLE STUDY GROUPS FOR {course_id}")
            print(f"{'='*80}")

            for i, group in enumerate(groups, 1):
                print(f"\n{i}. {group['group_name']} (ID: {group['group_id']})")
                print(f"   Members: {group['current_members']}/{group['max_members']}")
                print(f"   Type: {'Virtual' if group['is_virtual'] else 'In-Person'}")
                if group['location']:
                    print(f"   Location: {group['location']}")
                if group['meeting_schedule']:
                    print(f"   Schedule: {group['meeting_schedule']}")
                print(f"   Created: {group['created_at']}")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    def join_study_group(self):
        """Join an existing study group."""
        group_id_input = input("\nEnter group ID to join: ").strip()
        try:
            group_id = int(group_id_input)
        except ValueError:
            print("\nInvalid group ID.")
            return

        user_id = self.auth.get_current_user()['username']

        try:
            if self.service.join_study_group(group_id, user_id):
                print(f"\n✓ Successfully joined study group {group_id}!")
            else:
                print("\n✗ Could not join group (already a member).")
        except ValueError as e:
            print(f"\n✗ Error: {e}")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def view_group_details(self):
        """View detailed group information."""
        group_id_input = input("\nEnter group ID: ").strip()
        try:
            group_id = int(group_id_input)
        except ValueError:
            print("\nInvalid group ID.")
            return

        try:
            group_data = self.service.get_study_group(group_id)

            if not group_data:
                print("\nGroup not found.")
                return

            group = group_data['group']
            members = group_data['members']

            print(f"\n{'='*80}")
            print("STUDY GROUP DETAILS")
            print(f"{'='*80}")
            print(f"\nGroup Name: {group['group_name']}")
            print(f"Course: {group['course_id']}")
            print(f"Type: {'Virtual' if group['is_virtual'] else 'In-Person'}")
            print(f"Members: {group['current_members']}/{group['max_members']}")
            print(f"Status: {group['status']}")

            if group['location']:
                print(f"Location: {group['location']}")
            if group['meeting_schedule']:
                print(f"Schedule: {group['meeting_schedule']}")

            print(f"\nCreated: {group['created_at']}")

            print(f"\n{'='*80}")
            print(f"MEMBERS ({len(members)})")
            print(f"{'='*80}")

            for i, member in enumerate(members, 1):
                print(f"\n{i}. {member['first_name']} {member['last_name']} (ID: {member['student_id']})")
                print(f"   Role: {member['role']}")
                print(f"   Joined: {member['joined_at']}")
                print(f"   Attendance: {member['attendance_count']} sessions")
                print(f"   Contribution Score: {member['contribution_score']}")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Virtual Study Rooms ==========

    def virtual_study_rooms_menu(self):
        """Virtual study rooms submenu."""
        while True:
            print("\n" + "-" * 60)
            print("VIRTUAL STUDY ROOMS")
            print("-" * 60)
            print("\n1. Create Study Room")
            print("2. Join Room (by code)")
            print("3. Browse Active Rooms")
            print("4. Leave Current Room")
            print("5. My Room Statistics")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.create_virtual_study_room()
            elif choice == '2':
                self.join_virtual_study_room()
            elif choice == '3':
                self.browse_active_rooms()
            elif choice == '4':
                self.leave_study_room()
            elif choice == '5':
                self.view_room_statistics()
            else:
                print("\nInvalid choice.")

    def create_virtual_study_room(self):
        """Create a virtual study room."""
        print("\n" + "-" * 60)
        print("CREATE VIRTUAL STUDY ROOM")
        print("-" * 60)

        room_name = input("\nRoom name: ").strip()
        if not room_name:
            print("\nRoom name is required.")
            return

        course_id = input("Course ID (optional): ").strip()
        course_id = course_id if course_id else None

        max_participants_input = input("Maximum participants (default 8): ").strip()
        try:
            max_participants = int(max_participants_input) if max_participants_input else 8
        except ValueError:
            max_participants = 8

        pomodoro_input = input("Enable Pomodoro timer? (y/n, default y): ").strip().lower()
        pomodoro_enabled = pomodoro_input != 'n'

        work_duration = 25
        break_duration = 5

        if pomodoro_enabled:
            work_input = input("Work duration in minutes (default 25): ").strip()
            try:
                work_duration = int(work_input) if work_input else 25
            except ValueError:
                work_duration = 25

            break_input = input("Break duration in minutes (default 5): ").strip()
            try:
                break_duration = int(break_input) if break_input else 5
            except ValueError:
                break_duration = 5

        user_id = self.auth.get_current_user()['username']

        try:
            room = self.service.create_virtual_study_room(
                host_id=user_id,
                room_name=room_name,
                course_id=course_id,
                max_participants=max_participants,
                pomodoro_enabled=pomodoro_enabled,
                work_duration=work_duration,
                break_duration=break_duration
            )

            print("\n✓ Virtual study room created successfully!")
            print(f"\nRoom ID: {room['room_id']}")
            print(f"Room Code: {room['room_code']}")
            print(f"Room Name: {room['room_name']}")
            print(f"Pomodoro: {'Enabled' if room['pomodoro_enabled'] else 'Disabled'}")
            print("\nShare the room code with others to invite them!")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    def join_virtual_study_room(self):
        """Join a virtual study room."""
        room_code = input("\nEnter room code: ").strip().upper()
        if not room_code:
            print("\nRoom code is required.")
            return

        user_id = self.auth.get_current_user()['username']

        try:
            room = self.service.join_virtual_study_room(room_code, user_id)
            print("\n✓ Successfully joined study room!")
            print(f"\nRoom: {room['room_name']}")
            print(f"Host: {room['host_id']}")
            print(f"Participants: {room['current_participants']}/{room['max_participants']}")
            if room['pomodoro_enabled']:
                print(f"Pomodoro: {room['work_duration']}min work / {room['break_duration']}min break")

        except ValueError as e:
            print(f"\n✗ {e}")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def browse_active_rooms(self):
        """Browse active virtual study rooms."""
        course_id = input("\nFilter by course ID (or press Enter for all): ").strip()
        course_id = course_id if course_id else None

        try:
            rooms = self.service.get_active_study_rooms(course_id)

            if not rooms:
                print("\nNo active study rooms found.")
                return

            print(f"\n{'='*80}")
            print(f"ACTIVE VIRTUAL STUDY ROOMS ({len(rooms)} rooms)")
            print(f"{'='*80}")

            for i, room in enumerate(rooms, 1):
                print(f"\n{i}. {room['room_name']} (Code: {room['room_code']})")
                print(f"   Host: {room['first_name']} {room['last_name']}")
                print(f"   Participants: {room['current_participants']}/{room['max_participants']}")
                if room['course_id']:
                    print(f"   Course: {room['course_id']}")
                if room['pomodoro_enabled']:
                    print(f"   Pomodoro: {room['work_duration']}min work / {room['break_duration']}min break")
                print(f"   Sessions Completed: {room['session_count']}")
                print(f"   Created: {room['created_at']}")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    def leave_study_room(self):
        """Leave a virtual study room."""
        room_id_input = input("\nEnter room ID to leave: ").strip()
        try:
            room_id = int(room_id_input)
        except ValueError:
            print("\nInvalid room ID.")
            return

        user_id = self.auth.get_current_user()['username']

        try:
            if self.service.leave_virtual_study_room(room_id, user_id):
                print("\n✓ Left study room successfully.")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def view_room_statistics(self):
        """View personal room statistics."""
        user_id = self.auth.get_current_user()['username']

        try:
            stats = self.service.get_student_pomodoro_stats(user_id)

            if not stats or stats.get('total_sessions', 0) == 0:
                print("\nNo study room activity yet.")
                return

            print(f"\n{'='*70}")
            print("MY VIRTUAL STUDY ROOM STATISTICS")
            print(f"{'='*70}")
            print(f"\nTotal Sessions: {stats['total_sessions']}")
            print(f"Completed Sessions: {stats['completed_sessions']}")
            print(f"Total Study Time: {stats['total_minutes']} minutes ({stats['total_minutes'] / 60:.1f} hours)")
            print(f"Average Session Duration: {stats['avg_session_duration']:.1f} minutes")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Pomodoro Timer ==========

    def pomodoro_menu(self):
        """Pomodoro timer submenu."""
        while True:
            print("\n" + "-" * 60)
            print("POMODORO TIMER")
            print("-" * 60)
            print("\n1. Start Work Session")
            print("2. Start Break Session")
            print("3. Complete Current Session")
            print("4. My Pomodoro Statistics")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.start_pomodoro_session('work')
            elif choice == '2':
                self.start_pomodoro_session('break')
            elif choice == '3':
                self.complete_pomodoro_session()
            elif choice == '4':
                self.view_pomodoro_statistics()
            else:
                print("\nInvalid choice.")

    def start_pomodoro_session(self, session_type: str):
        """Start a Pomodoro session."""
        room_id_input = input("\nEnter room ID: ").strip()
        try:
            room_id = int(room_id_input)
        except ValueError:
            print("\nInvalid room ID.")
            return

        user_id = self.auth.get_current_user()['username']

        try:
            session_id = self.service.start_pomodoro_session(room_id, user_id, session_type)
            print(f"\n✓ {session_type.capitalize()} session started! (Session ID: {session_id})")
            print("Focus on your studies. Mark as complete when done.")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def complete_pomodoro_session(self):
        """Complete a Pomodoro session."""
        session_id_input = input("\nEnter session ID to complete: ").strip()
        try:
            session_id = int(session_id_input)
        except ValueError:
            print("\nInvalid session ID.")
            return

        try:
            if self.service.complete_pomodoro_session(session_id):
                print("\n✓ Session completed! Well done!")
            else:
                print("\n✗ Session not found or already completed.")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def view_pomodoro_statistics(self):
        """View Pomodoro statistics."""
        user_id = self.auth.get_current_user()['username']

        try:
            stats = self.service.get_student_pomodoro_stats(user_id)

            if not stats or stats.get('total_sessions', 0) == 0:
                print("\nNo Pomodoro sessions recorded yet.")
                return

            print(f"\n{'='*70}")
            print("MY POMODORO STATISTICS")
            print(f"{'='*70}")
            print(f"\nTotal Work Sessions: {stats['total_sessions']}")
            print(f"Completed Sessions: {stats['completed_sessions']}")
            completion_rate = (stats['completed_sessions'] / stats['total_sessions'] * 100) if stats['total_sessions'] > 0 else 0
            print(f"Completion Rate: {completion_rate:.1f}%")
            print(f"\nTotal Focus Time: {stats['total_minutes']} minutes ({stats['total_minutes'] / 60:.1f} hours)")
            print(f"Average Session: {stats['avg_session_duration']:.1f} minutes")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Q&A Board ==========

    def qa_board_menu(self):
        """Q&A board submenu."""
        while True:
            print("\n" + "-" * 60)
            print("ANONYMOUS Q&A BOARD")
            print("-" * 60)
            print("\n1. Browse Questions")
            print("2. Ask Question")
            print("3. Answer Question")
            print("4. View Question Details")
            print("5. Vote on Content")
            print("6. My Q&A Activity")
            print("0. Back to Main Menu")

            choice = input("\nEnter your choice: ").strip()

            if choice == '0':
                break
            elif choice == '1':
                self.browse_questions()
            elif choice == '2':
                self.ask_question()
            elif choice == '3':
                self.answer_question()
            elif choice == '4':
                self.view_question_details()
            elif choice == '5':
                self.vote_on_content()
            elif choice == '6':
                self.view_qa_activity()
            else:
                print("\nInvalid choice.")

    def browse_questions(self):
        """Browse questions on Q&A board."""
        course_id = input("\nEnter course ID: ").strip()
        if not course_id:
            print("\nCourse ID is required.")
            return

        print("\nSort by:")
        print("1. Recent")
        print("2. Popular")
        print("3. Unanswered")
        sort_choice = input("\nEnter choice (default 1): ").strip()
        sort_map = {'1': 'recent', '2': 'popular', '3': 'unanswered'}
        sort_by = sort_map.get(sort_choice, 'recent')

        try:
            questions = self.service.get_course_questions(course_id, sort_by=sort_by)

            if not questions:
                print(f"\nNo questions found for course {course_id}.")
                return

            print(f"\n{'='*80}")
            print(f"Q&A BOARD - {course_id} ({len(questions)} questions)")
            print(f"{'='*80}")

            for i, q in enumerate(questions, 1):
                status = "✓" if q['is_resolved'] else ("Answered" if q['is_answered'] else "Unanswered")
                votes = q['upvotes'] - q['downvotes']
                vote_display = f"+{votes}" if votes >= 0 else str(votes)

                print(f"\n{i}. [{q['question_id']}] {q['question_title']}")
                print(f"   By: {q['anonymous_id']} | Category: {q['category']} | Difficulty: {q['difficulty_level']}")
                print(f"   Votes: {vote_display} | Answers: {q['answer_count']} | Views: {q['view_count']} | Status: {status}")
                print(f"   Posted: {q['created_at']}")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    def ask_question(self):
        """Post a question to Q&A board."""
        print("\n" + "-" * 60)
        print("ASK QUESTION (ANONYMOUS)")
        print("-" * 60)

        course_id = input("\nCourse ID: ").strip()
        if not course_id:
            print("\nCourse ID is required.")
            return

        question_title = input("Question title: ").strip()
        if not question_title:
            print("\nQuestion title is required.")
            return

        print("\nQuestion text (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and lines:
                break
            lines.append(line)
        question_text = '\n'.join(lines)

        if not question_text:
            print("\nQuestion text is required.")
            return

        print("\nCategory:")
        for i, cat in enumerate(QA_CATEGORIES, 1):
            print(f"{i}. {cat}")
        cat_choice = input(f"\nSelect category (1-{len(QA_CATEGORIES)}, default 1): ").strip()
        try:
            category = QA_CATEGORIES[int(cat_choice) - 1] if cat_choice else QA_CATEGORIES[0]
        except (ValueError, IndexError):
            category = QA_CATEGORIES[0]

        print("\nDifficulty Level:")
        for i, level in enumerate(DIFFICULTY_LEVELS, 1):
            print(f"{i}. {level}")
        level_choice = input(f"\nSelect difficulty (1-{len(DIFFICULTY_LEVELS)}, default 2): ").strip()
        try:
            difficulty = DIFFICULTY_LEVELS[int(level_choice) - 1] if level_choice else DIFFICULTY_LEVELS[1]
        except (ValueError, IndexError):
            difficulty = DIFFICULTY_LEVELS[1]

        user_id = self.auth.get_current_user()['username']

        try:
            result = self.service.post_question(
                course_id=course_id,
                student_id=user_id,
                question_title=question_title,
                question_text=question_text,
                category=category,
                difficulty_level=difficulty
            )

            print("\n✓ Question posted successfully!")
            print(f"Question ID: {result['question_id']}")
            print(f"Your anonymous ID for this course: {result['anonymous_id']}")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    def answer_question(self):
        """Answer a question on Q&A board."""
        question_id_input = input("\nEnter question ID to answer: ").strip()
        try:
            question_id = int(question_id_input)
        except ValueError:
            print("\nInvalid question ID.")
            return

        print("\nYour answer (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and lines:
                break
            lines.append(line)
        answer_text = '\n'.join(lines)

        if not answer_text:
            print("\nAnswer text is required.")
            return

        user_id = self.auth.get_current_user()['username']

        try:
            answer_id = self.service.post_answer(
                question_id=question_id,
                student_id=user_id,
                answer_text=answer_text
            )

            print(f"\n✓ Answer posted successfully! (Answer ID: {answer_id})")

        except ValueError as e:
            print(f"\n✗ {e}")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def view_question_details(self):
        """View question with all answers."""
        question_id_input = input("\nEnter question ID: ").strip()
        try:
            question_id = int(question_id_input)
        except ValueError:
            print("\nInvalid question ID.")
            return

        try:
            data = self.service.get_question_with_answers(question_id)

            if not data:
                print("\nQuestion not found.")
                return

            question = data['question']
            answers = data['answers']

            print(f"\n{'='*80}")
            print(f"QUESTION #{question['question_id']}")
            print(f"{'='*80}")
            print(f"\nTitle: {question['question_title']}")
            print(f"By: {question['anonymous_id']}")
            print(f"Category: {question['category']} | Difficulty: {question['difficulty_level']}")
            print(f"Posted: {question['created_at']}")

            votes = question['upvotes'] - question['downvotes']
            print(f"\nVotes: {votes} (↑{question['upvotes']} ↓{question['downvotes']})")
            print(f"Views: {question['view_count']}")
            print(f"Status: {'Resolved' if question['is_resolved'] else ('Answered' if question['is_answered'] else 'Unanswered')}")

            print(f"\n{'-'*80}")
            print("QUESTION:")
            print(f"{'-'*80}")
            print(question['question_text'])

            if answers:
                print(f"\n{'='*80}")
                print(f"ANSWERS ({len(answers)})")
                print(f"{'='*80}")

                for i, ans in enumerate(answers, 1):
                    ans_votes = ans['upvotes'] - ans['downvotes']
                    accepted = "✓ ACCEPTED" if ans['is_accepted'] else ""
                    instructor = "[INSTRUCTOR]" if ans['is_instructor_answer'] else ""

                    print(f"\n{i}. Answer #{ans['answer_id']} {accepted} {instructor}")
                    print(f"   By: {ans['anonymous_id']}")
                    print(f"   Votes: {ans_votes} (↑{ans['upvotes']} ↓{ans['downvotes']})")
                    print(f"   Posted: {ans['created_at']}")
                    print(f"\n   {ans['answer_text']}")
            else:
                print("\n\nNo answers yet. Be the first to answer!")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    def vote_on_content(self):
        """Vote on a question or answer."""
        print("\n1. Vote on Question")
        print("2. Vote on Answer")
        choice = input("\nEnter choice: ").strip()

        target_type = 'question' if choice == '1' else 'answer' if choice == '2' else None
        if not target_type:
            print("\nInvalid choice.")
            return

        target_id_input = input(f"\nEnter {target_type} ID: ").strip()
        try:
            target_id = int(target_id_input)
        except ValueError:
            print(f"\nInvalid {target_type} ID.")
            return

        print("\n1. Upvote")
        print("2. Downvote")
        vote_choice = input("\nEnter choice: ").strip()
        vote_type = 'upvote' if vote_choice == '1' else 'downvote' if vote_choice == '2' else None

        if not vote_type:
            print("\nInvalid choice.")
            return

        user_id = self.auth.get_current_user()['username']

        try:
            if self.service.vote_on_content(user_id, target_type, target_id, vote_type):
                print("\n✓ Vote recorded!")
        except Exception as e:
            print(f"\n✗ Error: {e}")

    def view_qa_activity(self):
        """View personal Q&A activity."""
        user_id = self.auth.get_current_user()['username']

        try:
            analytics = self.service.get_study_matching_analytics(user_id)
            qa_stats = analytics.get('qa_participation', {})

            if not qa_stats:
                print("\nNo Q&A activity yet.")
                return

            print(f"\n{'='*70}")
            print("MY Q&A ACTIVITY")
            print(f"{'='*70}")
            print(f"\nQuestions Asked: {qa_stats.get('questions_asked', 0)}")
            print(f"Answers Given: {qa_stats.get('answers_given', 0)}")
            print(f"Question Upvotes: {qa_stats.get('question_upvotes', 0)}")
            print(f"Answer Upvotes: {qa_stats.get('answer_upvotes', 0)}")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Analytics ==========

    def view_analytics(self):
        """View comprehensive analytics."""
        user_id = self.auth.get_current_user()['username']

        try:
            analytics = self.service.get_study_matching_analytics(user_id)

            print(f"\n{'='*80}")
            print("MY STUDY MATCHING ANALYTICS")
            print(f"{'='*80}")

            # Group stats
            group_stats = analytics.get('groups', {})
            if group_stats:
                print("\n--- STUDY GROUPS ---")
                print(f"Total Groups: {group_stats.get('total_groups', 0)}")
                print(f"Active Groups: {group_stats.get('active_groups', 0)}")
                avg_contrib = group_stats.get('avg_contribution', 0)
                print(f"Average Contribution Score: {avg_contrib if avg_contrib else 0:.1f}")
                print(f"Total Attendance: {group_stats.get('total_attendance', 0)} sessions")

            # Virtual room stats
            room_stats = analytics.get('virtual_rooms', {})
            if room_stats:
                print("\n--- VIRTUAL STUDY ROOMS ---")
                print(f"Rooms Joined: {room_stats.get('rooms_joined', 0)}")
                total_time = room_stats.get('total_study_time', 0)
                print(f"Total Study Time: {total_time if total_time else 0} minutes ({total_time / 60:.1f} hours)")
                print(f"Pomodoro Sessions: {room_stats.get('total_pomodoros', 0)}")

            # Q&A stats
            qa_stats = analytics.get('qa_participation', {})
            if qa_stats:
                print("\n--- Q&A PARTICIPATION ---")
                print(f"Questions Asked: {qa_stats.get('questions_asked', 0)}")
                print(f"Answers Given: {qa_stats.get('answers_given', 0)}")
                print(f"Question Upvotes: {qa_stats.get('question_upvotes', 0)}")
                print(f"Answer Upvotes: {qa_stats.get('answer_upvotes', 0)}")

        except Exception as e:
            print(f"\n✗ Error: {e}")

    # ========== Quick Start Guide ==========

    def quick_start_guide(self):
        """Display quick start guide."""
        print("\n" + "=" * 80)
        print("PEER STUDY MATCHING - QUICK START GUIDE")
        print("=" * 80)

        print("\n1. CREATE YOUR STUDY PROFILE")
        print("   - Define your learning style and preferences")
        print("   - Set your availability and interests")
        print("   - This helps us find compatible study partners")

        print("\n2. FIND STUDY PARTNERS")
        print("   - View compatibility scores with other students")
        print("   - See match reasons based on shared preferences")
        print("   - Send match suggestions to connect")

        print("\n3. JOIN OR CREATE STUDY GROUPS")
        print("   - Form organized study groups for your courses")
        print("   - Set meeting schedules and locations")
        print("   - Track attendance and contributions")

        print("\n4. USE VIRTUAL STUDY ROOMS")
        print("   - Create instant study sessions")
        print("   - Share room codes to invite others")
        print("   - Use Pomodoro timer for focused study")

        print("\n5. ASK & ANSWER QUESTIONS")
        print("   - Post questions anonymously")
        print("   - Help others by answering")
        print("   - Vote on helpful content")

        print("\n6. TRACK YOUR PROGRESS")
        print("   - View study time and Pomodoro stats")
        print("   - Monitor group participation")
        print("   - Check Q&A contribution")

        print("\n" + "=" * 80)
        print("TIP: Start by creating your study profile to unlock all features!")
        print("=" * 80)


def main():
    """Main entry point for CLI."""
    cli = StudyMatchingCLI()
    cli.run()


if __name__ == "__main__":
    main()
