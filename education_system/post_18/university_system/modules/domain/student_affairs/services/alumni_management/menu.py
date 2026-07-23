from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import auth
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.database import init_alumni_db
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.profiles import register_alumni, view_alumni, update_alumni, setup_alumni_directory
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.events import (
    view_events, register_for_event, create_enhanced_event, event_check_in_system,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.donations import (
    record_donation, view_donations, view_fundraising_campaigns, manage_donor_recognition,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.mentorship import setup_mentorship, view_mentorships, smart_mentorship_matching
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.stories import view_alumni_stories
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.reunions import manage_class_reunions
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.chapters import manage_regional_chapters
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.directory import search_alumni_directory, view_connection_requests, manage_business_directory
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.communications import create_newsletter
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.forum import manage_alumni_forum
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.jobs import view_job_board, post_job_opportunity, schedule_career_counseling
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.gamification import (
    view_engagement_leaderboard, view_my_badges, generate_engagement_recommendations,
)
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.photos import manage_photo_gallery
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.reports import generate_alumni_report


def display_alumni_menu():
    """Display the enhanced alumni system menu with all new features"""
    global auth

    # Initialize the enhanced alumni database if not already done
    init_alumni_db()

    # Check if user is logged in
    if not auth or not auth.current_user:
        print("You must be logged in to access the alumni system.")
        return

    while True:
        print(f"\n🎓 Enhanced Alumni System - Welcome {auth.current_user.get('first_name', 'User')}!")
        print("=" * 70)

        # Display menu options based on permissions
        option_num = 1
        option_map = {}

        # Core Alumni Management
        print("\n📋 ALUMNI MANAGEMENT")
        if auth.check_permission('manage_alumni'):
            print(f"{option_num}. Register New Alumni")
            option_map[str(option_num)] = "register_alumni"
            option_num += 1

        if auth.check_permission('view_alumni') or auth.check_permission('view_own_alumni_profile'):
            print(f"{option_num}. View Alumni Records")
            option_map[str(option_num)] = "view_alumni"
            option_num += 1

        if auth.check_permission('manage_alumni') or auth.check_permission('update_own_alumni_profile'):
            print(f"{option_num}. Update Alumni Record")
            option_map[str(option_num)] = "update_alumni"
            option_num += 1

        # Alumni Directory & Networking
        print("\n🌐 NETWORKING & DIRECTORY")
        if auth.check_permission('access_alumni_directory'):
            print(f"{option_num}. Alumni Directory & Search")
            option_map[str(option_num)] = "alumni_directory"
            option_num += 1

            print(f"{option_num}. Connection Requests")
            option_map[str(option_num)] = "connection_requests"
            option_num += 1

            print(f"{option_num}. Business Directory")
            option_map[str(option_num)] = "business_directory"
            option_num += 1

        # Communication & Social
        print("\n💬 COMMUNICATION & SOCIAL")
        if auth.check_permission('send_newsletters') or auth.check_permission('access_alumni_directory'):
            if auth.check_permission('send_newsletters'):
                print(f"{option_num}. Create Newsletter")
                option_map[str(option_num)] = "create_newsletter"
                option_num += 1

            print(f"{option_num}. Alumni Forum")
            option_map[str(option_num)] = "alumni_forum"
            option_num += 1

            print(f"{option_num}. Alumni Stories")
            option_map[str(option_num)] = "alumni_stories"
            option_num += 1

        # Events
        print("\n🎉 EVENTS")
        if auth.check_permission('manage_events_advanced'):
            print(f"{option_num}. Create Enhanced Event")
            option_map[str(option_num)] = "create_enhanced_event"
            option_num += 1

            print(f"{option_num}. Event Check-In System")
            option_map[str(option_num)] = "event_checkin"
            option_num += 1

        if auth.check_permission('manage_events') or auth.check_permission('view_events'):
            print(f"{option_num}. View Alumni Events")
            option_map[str(option_num)] = "view_events"
            option_num += 1

        if auth.check_permission('manage_events') or auth.check_permission('register_for_events'):
            print(f"{option_num}. Register for Event")
            option_map[str(option_num)] = "register_for_event"
            option_num += 1

        if auth.check_permission('manage_social_features'):
            print(f"{option_num}. Manage Class Reunions")
            option_map[str(option_num)] = "manage_reunions"
            option_num += 1

        # Career Services
        print("\n💼 CAREER SERVICES")
        if auth.check_permission('view_job_board'):
            print(f"{option_num}. Job Board")
            option_map[str(option_num)] = "job_board"
            option_num += 1

        if auth.check_permission('post_jobs'):
            print(f"{option_num}. Post Job Opportunity")
            option_map[str(option_num)] = "post_job"
            option_num += 1

        if auth.check_permission('schedule_career_counseling'):
            print(f"{option_num}. Schedule Career Counseling")
            option_map[str(option_num)] = "career_counseling"
            option_num += 1

        # Donations & Fundraising
        print("\n💰 DONATIONS & FUNDRAISING")
        if auth.check_permission('manage_donations') or auth.check_permission('make_donation'):
            print(f"{option_num}. Record Donation")
            option_map[str(option_num)] = "record_donation"
            option_num += 1

        if auth.check_permission('manage_donations') or auth.check_permission('view_own_donations'):
            print(f"{option_num}. View Donations")
            option_map[str(option_num)] = "view_donations"
            option_num += 1

        if auth.check_permission('manage_campaigns'):
            print(f"{option_num}. Fundraising Campaigns")
            option_map[str(option_num)] = "manage_campaigns"
            option_num += 1

            print(f"{option_num}. Donor Recognition")
            option_map[str(option_num)] = "donor_recognition"
            option_num += 1

        # Mentorship
        print("\n👥 MENTORSHIP")
        if auth.check_permission('manage_mentorships'):
            print(f"{option_num}. Set Up Mentorship")
            option_map[str(option_num)] = "setup_mentorship"
            option_num += 1

        if auth.check_permission('manage_mentorships') or auth.check_permission('view_own_mentorships'):
            print(f"{option_num}. View Mentorships")
            option_map[str(option_num)] = "view_mentorships"
            option_num += 1

        if auth.check_permission('manage_ai_features'):
            print(f"{option_num}. Smart Mentorship Matching")
            option_map[str(option_num)] = "smart_matching"
            option_num += 1

        # Engagement & Gamification
        print("\n🏆 ENGAGEMENT")
        print(f"{option_num}. View Engagement Leaderboard")
        option_map[str(option_num)] = "leaderboard"
        option_num += 1

        print(f"{option_num}. My Badges & Points")
        option_map[str(option_num)] = "my_badges"
        option_num += 1

        print(f"{option_num}. Personalized Recommendations")
        option_map[str(option_num)] = "recommendations"
        option_num += 1

        # Content & Gallery
        print("\n📸 CONTENT")
        print(f"{option_num}. Photo Gallery")
        option_map[str(option_num)] = "photo_gallery"
        option_num += 1

        print(f"{option_num}. Regional Chapters")
        option_map[str(option_num)] = "regional_chapters"
        option_num += 1

        # Settings & Admin
        print("\n⚙️  SETTINGS")
        print(f"{option_num}. Directory Privacy Settings")
        option_map[str(option_num)] = "directory_settings"
        option_num += 1

        if auth.check_permission('generate_reports'):
            print(f"{option_num}. Generate Alumni Reports")
            option_map[str(option_num)] = "generate_reports"
            option_num += 1

        # Return option
        print(f"\n{option_num}. Return to Main Menu")

        print("\n" + "=" * 70)
        choice = input("Enter your choice: ")

        if choice in option_map:
            action = option_map[choice]

            try:
                if action == "register_alumni":
                    register_alumni()
                elif action == "view_alumni":
                    view_alumni()
                elif action == "update_alumni":
                    update_alumni()
                elif action == "alumni_directory":
                    search_alumni_directory()
                elif action == "connection_requests":
                    view_connection_requests()
                elif action == "business_directory":
                    manage_business_directory()
                elif action == "create_newsletter":
                    create_newsletter()
                elif action == "alumni_forum":
                    manage_alumni_forum()
                elif action == "alumni_stories":
                    view_alumni_stories()
                elif action == "create_enhanced_event":
                    create_enhanced_event()
                elif action == "event_checkin":
                    event_check_in_system()
                elif action == "view_events":
                    view_events()
                elif action == "register_for_event":
                    register_for_event()
                elif action == "manage_reunions":
                    manage_class_reunions()
                elif action == "job_board":
                    view_job_board()
                elif action == "post_job":
                    post_job_opportunity()
                elif action == "career_counseling":
                    schedule_career_counseling()
                elif action == "record_donation":
                    record_donation()
                elif action == "view_donations":
                    view_donations()
                elif action == "manage_campaigns":
                    view_fundraising_campaigns()
                elif action == "donor_recognition":
                    manage_donor_recognition()
                elif action == "setup_mentorship":
                    setup_mentorship()
                elif action == "view_mentorships":
                    view_mentorships()
                elif action == "smart_matching":
                    smart_mentorship_matching()
                elif action == "leaderboard":
                    view_engagement_leaderboard()
                elif action == "my_badges":
                    view_my_badges()
                elif action == "recommendations":
                    generate_engagement_recommendations()
                elif action == "photo_gallery":
                    manage_photo_gallery()
                elif action == "regional_chapters":
                    manage_regional_chapters()
                elif action == "directory_settings":
                    setup_alumni_directory()
                elif action == "generate_reports":
                    generate_alumni_report()

            except Exception as e:
                print(f"An error occurred: {e}")
                print("Please try again or contact support.")

        elif choice == str(option_num):
            return
        else:
            print("Invalid choice. Please try again.")


# GUI Launcher using factory pattern
try:
    from education_system.post_18.university_system.modules.shared.feature_gui_factory import create_gui_launcher

    launch_alumni_relations_gui = create_gui_launcher(
        title="Alumni Relations & Engagement",
        description="""Comprehensive alumni management with profiles, donations, events, and engagement tracking.

Features:
* Alumni profiles & directories
* Donation management
* Giving campaigns
* Alumni events & reunions
* Registration & RSVP tracking
* Achievement recognition
* Regional chapters
* Mentorship programs
* Career networking
* Photo galleries
* Communication tools
* Engagement analytics
* Smart recommendations
* Leaderboards & badges
* Event QR codes
* Payment processing
* LinkedIn integration
* SMS notifications""",
        cli_instruction="Use CLI: Alumni Relations & Engagement"
    )
except ImportError:
    # Fallback if factory not available
    def launch_alumni_relations_gui(root, auth):
        """Launch the Alumni Relations & Engagement GUI (same as Alumni Management)"""
        try:
            from education_system.post_18.university_system.modules.domain.student_affairs.gui.alumni import launch_alumni_gui
            launch_alumni_gui(auth)
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Failed to launch Alumni GUI: {str(e)}")


# Alias for consistency with refactored naming
display_alumni_relations_menu = display_alumni_menu
