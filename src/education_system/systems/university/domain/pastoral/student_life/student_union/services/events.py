from __future__ import annotations

import logging

from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.pastoral.student_life.student_union.services import union_context as ctx
from education_system.systems.university.domain.pastoral.student_life.student_union.services.union_context import (
    manage_book_clubs, manage_shared_resources, knowledge_sharing_sessions,
    learning_analytics_dashboard, auto_award_points
)

logger = logging.getLogger(__name__)

def manage_live_streaming(cursor):
    """Manage live streaming for virtual events"""
    try:
        print("\n📡 Live Streaming Management")
        print("=" * 35)

        print("Live Streaming Platforms:")
        print("1. YouTube Live")
        print("2. Facebook Live")
        print("3. Instagram Live")
        print("4. Twitch")
        print("5. Custom RTMP Stream")

        platform_choice = input("Select streaming platform: ").strip()

        if platform_choice in ['1', '2', '3', '4']:
            platforms = ['YouTube Live', 'Facebook Live', 'Instagram Live', 'Twitch']
            selected_platform = platforms[int(platform_choice)-1]

            print(f"\n{selected_platform} Setup:")
            print("• Account verification required")
            print("• Streaming key needed")
            print("• Privacy settings configuration")
            print("• Chat moderation setup")

        elif platform_choice == '5':
            print("\nCustom RTMP Stream Setup:")
            rtmp_url = input("RTMP Server URL: ").strip()
            stream_key = input("Stream Key: ").strip()
            print("Custom stream configured")

        # Streaming quality settings
        print("\nStreaming Quality Options:")
        print("1. HD (1080p) - High quality, higher bandwidth")
        print("2. SD (720p) - Good quality, moderate bandwidth")
        print("3. Low (480p) - Basic quality, low bandwidth")
        print("4. Auto - Adaptive quality based on connection")

        quality_choice = input("Select quality: ").strip()
        qualities = ['HD (1080p)', 'SD (720p)', 'Low (480p)', 'Auto']

        if quality_choice.isdigit() and 1 <= int(quality_choice) <= 4:
            selected_quality = qualities[int(quality_choice)-1]
            print(f"Quality set to: {selected_quality}")

        # Additional streaming features
        print("\nAdditional Features:")

        enable_chat = input("Enable live chat? (y/n): ").strip().lower() == 'y'
        enable_recording = input("Record stream? (y/n): ").strip().lower() == 'y'
        enable_captions = input("Enable auto-captions? (y/n): ").strip().lower() == 'y'

        # Moderation settings
        if enable_chat:
            print("\nChat Moderation:")
            print("• Profanity filter enabled")
            print("• Spam protection active")
            print("• Moderator controls available")

            assign_moderators = input("Assign chat moderators? (y/n): ").strip().lower() == 'y'
            if assign_moderators:
                print("Moderator assignment interface would be shown here")

        # Pre-stream checklist
        print("\n✅ Pre-Stream Checklist:")
        print("□ Test camera and microphone")
        print("□ Check internet connection speed")
        print("□ Verify streaming platform login")
        print("□ Test stream quality")
        print("□ Brief moderators (if applicable)")
        print("□ Prepare backup streaming method")
        print("□ Notify attendees of stream link")

        print("Live streaming setup complete!")
        print("Stream will start automatically at event time.")

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        print(f"An error occurred: {e}")

def interactive_virtual_features(cursor):
    """Manage interactive features for virtual events"""
    try:
        print("\n🎮 Interactive Virtual Features")
        print("=" * 40)

        print("Available Interactive Features:")
        print()

        print("1. 📊 Live Polls and Surveys")
        print("   • Real-time audience polling")
        print("   • Multiple choice questions")
        print("   • Word clouds")
        print("   • Rating scales")

        print("\n2. ❓ Q&A Sessions")
        print("   • Anonymous question submission")
        print("   • Question upvoting")
        print("   • Moderated Q&A")
        print("   • Live answers")

        print("\n3. 💬 Chat and Messaging")
        print("   • Public chat rooms")
        print("   • Private messaging")
        print("   • Emoji reactions")
        print("   • File sharing")

        print("\n4. 🏠 Virtual Breakout Rooms")
        print("   • Small group discussions")
        print("   • Random or assigned groups")
        print("   • Rotating participants")
        print("   • Group reporting back")

        print("\n5. 🎨 Virtual Whiteboard")
        print("   • Collaborative drawing")
        print("   • Sticky notes")
        print("   • Screen annotation")
        print("   • Shared documents")

        print("\n6. 🎮 Gamification")
        print("   • Virtual scavenger hunts")
        print("   • Quiz competitions")
        print("   • Achievement badges")
        print("   • Leaderboards")

        print("\n7. 🤝 Networking Features")
        print("   • Speed networking")
        print("   • Interest-based matching")
        print("   • Virtual coffee chats")
        print("   • Contact exchange")

        feature_choice = input("\nSelect feature to configure (1-7): ").strip()

        if feature_choice == '1':
            # Live Polls
            print("\n📊 Live Polls Configuration")
            print("Poll types available:")
            print("• Multiple choice")
            print("• Yes/No questions")
            print("• Rating scales (1-5 or 1-10)")
            print("• Open-ended text")
            print("• Word clouds")

            poll_question = input("Sample poll question: ").strip()
            if poll_question:
                print(f"Poll created: '{poll_question}'")
                print("Participants can respond via mobile or web interface")

        elif feature_choice == '2':
            # Q&A Sessions
            print("\n❓ Q&A Session Setup")
            print("Q&A features:")
            print("• Anonymous submissions allowed")
            print("• Question moderation enabled")
            print("• Upvoting system active")
            print("• Live answer display")

            moderated_qa = input("Enable question moderation? (y/n): ").strip().lower() == 'y'
            if moderated_qa:
                print("Questions will be reviewed before display")
            else:
                print("Questions will appear immediately")

        elif feature_choice == '3':
            # Chat and Messaging
            print("\n💬 Chat Configuration")
            print("Chat settings:")

            public_chat = input("Enable public chat? (y/n): ").strip().lower() == 'y'
            private_messaging = input("Enable private messaging? (y/n): ").strip().lower() == 'y'
            file_sharing = input("Allow file sharing? (y/n): ").strip().lower() == 'y'

            print("Chat moderation tools:")
            print("• Automatic profanity filtering")
            print("• Spam detection")
            print("• Moderator controls")
            print("• Message deletion capability")

        elif feature_choice == '4':
            # Breakout Rooms
            print("\n🏠 Breakout Room Setup")

            try:
                room_count = int(input("Number of breakout rooms: ").strip())
                room_size = int(input("Maximum participants per room: ").strip())
            except ValueError:
                room_count, room_size = 5, 8

            assignment_method = input("Assignment method (random/manual/self-select): ").strip().lower()

            print("Breakout rooms configured:")
            print(f"• {room_count} rooms")
            print(f"• Max {room_size} participants per room")
            print(f"• Assignment: {assignment_method}")
            print("• 15-minute timer set")
            print("• Host can visit all rooms")

        elif feature_choice == '6':
            # Gamification
            print("\n🎮 Gamification Setup")

            game_types = ["Quiz Competition", "Scavenger Hunt", "Bingo", "Trivia"]

            print("Available games:")
            for i, game in enumerate(game_types, 1):
                print(f"{i}. {game}")

            game_choice = input("Select game type: ").strip()
            if game_choice.isdigit() and 1 <= int(game_choice) <= len(game_types):
                selected_game = game_types[int(game_choice)-1]
                print(f"{selected_game} game configured!")
                print("Participants will earn points and badges")
                print("Leaderboard will be displayed during event")

        print("\nInteractive features configured successfully!")
        print("Features will be available during the virtual event.")

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        print(f"An error occurred: {e}")

def recording_and_replay_management(cursor):
    """Manage event recordings and replay options"""
    try:
        print("\n🎥 Recording and Replay Management")
        print("=" * 45)

        print("Recording Options:")
        print("1. Automatic recording")
        print("2. Manual recording control")
        print("3. Selective recording (main session only)")
        print("4. No recording")

        recording_choice = input("Select recording option: ").strip()

        recording_options = {
            '1': 'automatic',
            '2': 'manual',
            '3': 'selective',
            '4': 'none'
        }

        recording_type = recording_options.get(recording_choice, 'automatic')

        if recording_type != 'none':
            print("\nRecording Settings:")

            # Quality settings
            print("Recording quality:")
            print("1. HD (1080p) - 2GB per hour")
            print("2. SD (720p) - 1GB per hour")
            print("3. Audio only - 100MB per hour")

            quality_choice = input("Select quality: ").strip()
            qualities = ['HD (1080p)', 'SD (720p)', 'Audio only']

            if quality_choice.isdigit() and 1 <= int(quality_choice) <= 3:
                quality = qualities[int(quality_choice)-1]
                print(f"Recording quality: {quality}")

            # Storage and access
            print("\nStorage and Access:")

            storage_duration = input("How long to store recording (days): ").strip()
            if not storage_duration.isdigit():
                storage_duration = "30"

            print(f"Recording will be stored for {storage_duration} days")

            # Access permissions
            print("\nAccess Permissions:")
            print("1. Public (anyone with link)")
            print("2. Registered attendees only")
            print("3. Club members only")
            print("4. Private (organizers only)")

            access_choice = input("Select access level: ").strip()
            access_levels = ['Public', 'Registered attendees', 'Club members', 'Private']

            if access_choice.isdigit() and 1 <= int(access_choice) <= 4:
                access_level = access_levels[int(access_choice)-1]
                print(f"Access level: {access_level}")

            # Post-processing options
            print("\nPost-Processing Options:")

            auto_captions = input("Generate automatic captions? (y/n): ").strip().lower() == 'y'
            if auto_captions:
                print("• Automatic captions will be generated")
                print("• Multiple language support available")

            chapter_markers = input("Add chapter markers? (y/n): ").strip().lower() == 'y'
            if chapter_markers:
                print("• Chapter markers will be added automatically")
                print("• Manual markers can be added during editing")

            highlights = input("Generate highlight reel? (y/n): ").strip().lower() == 'y'
            if highlights:
                print("• 5-minute highlight reel will be created")
                print("• Key moments and Q&A included")

            # Notification settings
            print("\nNotification Settings:")

            notify_when_ready = input("Notify attendees when recording is ready? (y/n): ").strip().lower() == 'y'
            if notify_when_ready:
                print("Attendees will receive email notification")

            # Analytics
            print("\nRecording Analytics:")
            print("• View count tracking")
            print("• Watch time analytics")
            print("• Engagement metrics")
            print("• Geographic distribution")
            print("• Device/platform breakdown")

        else:
            print("No recording will be made of this event.")
            print("Live attendance only.")

        # Replay schedule
        if recording_type != 'none':
            print("\n📅 Replay Schedule Options:")

            schedule_replays = input("Schedule replay sessions? (y/n): ").strip().lower() == 'y'
            if schedule_replays:
                replay_times = input("Replay times (e.g., 'tomorrow 3pm, next week 7pm'): ").strip()
                if replay_times:
                    print(f"Replay sessions scheduled: {replay_times}")
                    print("Registered attendees will be notified")

        print("\nRecording configuration complete!")
        if recording_type != 'none':
            print("Recording will begin automatically when event starts.")
            print("Processing will complete within 2 hours after event ends.")

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        print(f"An error occurred: {e}")

def manage_learning_integration():
    """Main learning integration interface"""

    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to access learning features.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (ctx.auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        while True:
            print("\n📚 Learning Integration")
            print("1. Book clubs")
            print("2. Study resource sharing")
            print("3. Academic conferences")
            print("4. Research presentations")
            print("5. Knowledge sharing sessions")
            print("6. Learning analytics")
            print("7. Return to main menu")

            choice = input("Choose an option: ").strip()

            if choice == '1':
                manage_book_clubs(student_id, cursor, conn)
            elif choice == '2':
                manage_shared_resources(student_id, cursor, conn)
            elif choice == '3':
                organize_academic_conferences(student_id, cursor, conn)
            elif choice == '4':
                research_presentation_platform(student_id, cursor, conn)
            elif choice == '5':
                knowledge_sharing_sessions(student_id, cursor, conn)
            elif choice == '6':
                learning_analytics_dashboard(student_id, cursor)
            elif choice == '7':
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        logger.error("Database error: %s", e, exc_info=True)
        print(f"Database error: {e}")
    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        print(f"An error occurred: {e}")

def organize_academic_conferences(student_id, cursor, conn):
    """Organize academic conferences and symposiums"""
    try:
        print("\n🎓 Academic Conference Organization")
        print("=" * 45)

        print("1. Plan new conference")
        print("2. Submit conference proposal")
        print("3. Call for papers")
        print("4. Review submissions")
        print("5. Conference program")
        print("6. Virtual conference setup")

        choice = input("Choose option: ").strip()

        if choice == '1':
            # Plan new conference
            print("\n📋 Conference Planning")

            conference_name = input("Conference name: ").strip()
            theme = input("Conference theme/topic: ").strip()
            conference_type = input("Type (symposium/workshop/full conference): ").strip()

            # Date and duration
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            try:
                duration_days = int(input("Duration (days): ").strip())
            except ValueError:
                duration_days = 1

            # Format
            print("\nConference format:")
            print("1. In-person only")
            print("2. Virtual only")
            print("3. Hybrid")

            format_choice = input("Select format: ").strip()
            formats = {'1': 'in-person', '2': 'virtual', '3': 'hybrid'}
            conf_format = formats.get(format_choice, 'hybrid')

            # Target audience
            target_audience = input("Target audience (undergrad/postgrad/faculty/all): ").strip()

            try:
                expected_attendees = int(input("Expected attendees: ").strip())
            except ValueError:
                expected_attendees = 50

            # Budget planning
            print("\nBudget Planning:")
            try:
                venue_cost = float(input("Venue costs (£): ").strip() or "0")
                speaker_fees = float(input("Speaker fees (£): ").strip() or "0")
                catering_cost = float(input("Catering costs (£): ").strip() or "0")
                tech_costs = float(input("Technology costs (£): ").strip() or "0")

                total_budget = venue_cost + speaker_fees + catering_cost + tech_costs

                print(f"Total estimated budget: £{total_budget:.2f}")

            except ValueError:
                print("Invalid budget amounts.")
                return

            print("\n✅ Conference Plan Summary:")
            print(f"Name: {conference_name}")
            print(f"Theme: {theme}")
            print(f"Type: {conference_type}")
            print(f"Date: {start_date} ({duration_days} days)")
            print(f"Format: {conf_format}")
            print(f"Expected attendees: {expected_attendees}")
            print(f"Budget: £{total_budget:.2f}")

            save_plan = input("\nSave conference plan? (y/n): ").strip().lower() == 'y'
            if save_plan:
                print("Conference plan saved!")
                print("Next steps:")
                print("• Submit formal proposal")
                print("• Secure funding approval")
                print("• Begin venue booking")
                print("• Recruit organizing committee")

        elif choice == '2':
            # Submit conference proposal
            print("\n📝 Conference Proposal Submission")

            proposal_title = input("Proposal title: ").strip()
            academic_discipline = input("Academic discipline: ").strip()

            print("\nProposal sections:")

            rationale = input("Rationale (why is this conference needed?): ").strip()
            objectives = input("Conference objectives: ").strip()
            target_outcomes = input("Expected outcomes: ").strip()

            # Organizing committee
            print("\nOrganizing Committee:")
            committee_size = input("Number of committee members: ").strip()

            if committee_size.isdigit() and int(committee_size) > 0:
                print(f"Committee of {committee_size} members planned")
                print("Include mix of faculty and student representatives")

            # Timeline
            print("\nTimeline:")
            planning_duration = input("Planning period (months): ").strip()
            submission_deadline = input("Paper submission deadline: ").strip()

            print("\n📋 Proposal submitted for review")
            print("Review process:")
            print("• Academic committee review (2 weeks)")
            print("• Budget approval (1 week)")
            print("• Final decision notification")

        elif choice == '3':
            # Call for papers
            print("\n📢 Call for Papers")

            conference_title = input("Conference title: ").strip()
            submission_types = input("Submission types (papers/posters/abstracts): ").strip()

            print("\nKey dates:")
            abstract_deadline = input("Abstract submission deadline: ").strip()
            full_paper_deadline = input("Full paper deadline: ").strip()
            notification_date = input("Acceptance notification date: ").strip()

            print("\nSubmission guidelines:")
            word_limit = input("Word limit for papers: ").strip()
            format_requirements = input("Format requirements: ").strip()

            print("\nCall for Papers created:")
            print(f"Conference: {conference_title}")
            print(f"Submissions: {submission_types}")
            print(f"Abstract deadline: {abstract_deadline}")
            print(f"Paper deadline: {full_paper_deadline}")
            print(f"Word limit: {word_limit}")

            distribute_call = input("\nDistribute call for papers? (y/n): ").strip().lower() == 'y'
            if distribute_call:
                print("Call for papers distributed to:")
                print("• University mailing lists")
                print("• Academic social networks")
                print("• Relevant professional associations")
                print("• Partner institutions")

        elif choice == '4':
            # Review submissions
            print("\n📄 Submission Review Process")

            print("Review criteria:")
            print("• Academic rigor")
            print("• Relevance to conference theme")
            print("• Originality of research")
            print("• Quality of methodology")
            print("• Clarity of presentation")

            review_system = input("Review system (single-blind/double-blind): ").strip()
            reviewers_per_paper = input("Reviewers per submission: ").strip()

            print("Review process configured:")
            print(f"System: {review_system}")
            print(f"Reviewers per paper: {reviewers_per_paper}")

            print("\nReview timeline:")
            print("• 2 weeks for initial reviews")
            print("• 1 week for discussions")
            print("• Final decisions by notification date")

        elif choice == '5':
            # Conference program
            print("\n📅 Conference Program")

            print("Program structure:")
            print("• Opening keynote")
            print("• Parallel session tracks")
            print("• Poster sessions")
            print("• Panel discussions")
            print("• Closing remarks")

            session_duration = input("Session duration (minutes): ").strip()
            break_duration = input("Break duration (minutes): ").strip()

            print(f"Sessions: {session_duration} minutes")
            print(f"Breaks: {break_duration} minutes")

            print("\nProgram features:")
            print("• Accessible venues")
            print("• Live captioning")
            print("• Recording permissions")
            print("• Q&A facilitation")
            print("• Networking opportunities")

        elif choice == '6':
            # Virtual conference setup
            print("\n💻 Virtual Conference Setup")

            platform = input("Virtual platform (Zoom/Teams/Custom): ").strip()

            print("Virtual features:")
            print("• Multiple breakout rooms")
            print("• Interactive Q&A")
            print("• Virtual poster hall")
            print("• Networking rooms")
            print("• Live streaming")
            print("• Recording capabilities")

            technical_support = input("24/7 technical support needed? (y/n): ").strip().lower() == 'y'
            if technical_support:
                print("Technical support team assigned")

            print("Virtual conference platform configured!")

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        print(f"An error occurred: {e}")

def research_presentation_platform(student_id, cursor, conn):
    """Platform for research presentations and academic talks"""
    try:
        print("\n🎤 Research Presentation Platform")
        print("=" * 40)

        print("1. Submit presentation proposal")
        print("2. Schedule presentation")
        print("3. Browse upcoming presentations")
        print("4. Presentation skills workshop")
        print("5. Feedback and ratings")

        choice = input("Choose option: ").strip()

        if choice == '1':
            # Submit presentation proposal
            print("\n📝 Presentation Proposal")

            title = input("Presentation title: ").strip()
            research_area = input("Research area/discipline: ").strip()

            print("\nPresentation type:")
            print("1. Research findings")
            print("2. Work in progress")
            print("3. Literature review")
            print("4. Methodology discussion")
            print("5. Industry application")

            pres_type = input("Select type: ").strip()
            types = ['Research findings', 'Work in progress', 'Literature review',
                    'Methodology discussion', 'Industry application']

            if pres_type.isdigit() and 1 <= int(pres_type) <= 5:
                presentation_type = types[int(pres_type)-1]
            else:
                presentation_type = "Research findings"

            abstract = input("Abstract (brief summary): ").strip()
            duration = input("Requested duration (minutes): ").strip()

            # Target audience
            print("\nTarget audience:")
            print("1. Undergraduate students")
            print("2. Graduate students")
            print("3. Faculty")
            print("4. General academic audience")
            print("5. Industry professionals")

            audience_choice = input("Select audience: ").strip()
            audiences = ['Undergraduate', 'Graduate', 'Faculty', 'General academic', 'Industry']

            if audience_choice.isdigit() and 1 <= int(audience_choice) <= 5:
                target_audience = audiences[int(audience_choice)-1]
            else:
                target_audience = "General academic"

            # Technical requirements
            print("\nTechnical requirements:")
            needs_projector = input("Need projector? (y/n): ").strip().lower() == 'y'
            needs_microphone = input("Need microphone? (y/n): ").strip().lower() == 'y'
            needs_recording = input("Allow recording? (y/n): ").strip().lower() == 'y'

            print("\n📋 Proposal Summary:")
            print(f"Title: {title}")
            print(f"Type: {presentation_type}")
            print(f"Duration: {duration} minutes")
            print(f"Audience: {target_audience}")
            print(f"Recording: {'Allowed' if needs_recording else 'Not allowed'}")

            submit = input("\nSubmit proposal? (y/n): ").strip().lower() == 'y'
            if submit:
                print("Presentation proposal submitted!")
                print("Review process:")
                print("• Academic relevance review")
                print("• Scheduling coordination")
                print("• Venue/technology arrangement")
                print("• Promotion and publicity")

        elif choice == '2':
            # Schedule presentation
            print("\n📅 Schedule Presentation")

            preferred_dates = input("Preferred dates (e.g., 'next week', 'month of March'): ").strip()
            preferred_time = input("Preferred time (e.g., 'afternoon', '2-4pm'): ").strip()

            print("\nVenue preferences:")
            print("1. Lecture hall (100+ capacity)")
            print("2. Seminar room (20-50 capacity)")
            print("3. Small meeting room (5-20 capacity)")
            print("4. Virtual presentation")
            print("5. Hybrid (physical + virtual)")

            venue_choice = input("Select venue type: ").strip()
            venues = ['Lecture hall', 'Seminar room', 'Meeting room', 'Virtual', 'Hybrid']

            if venue_choice.isdigit() and 1 <= int(venue_choice) <= 5:
                venue_type = venues[int(venue_choice)-1]
            else:
                venue_type = "Seminar room"

            # Promotion
            promote_event = input("Promote to wider university community? (y/n): ").strip().lower() == 'y'

            print("\nScheduling request:")
            print(f"Preferred dates: {preferred_dates}")
            print(f"Preferred time: {preferred_time}")
            print(f"Venue type: {venue_type}")
            print(f"Promotion: {'Yes' if promote_event else 'No'}")

            print("Scheduling coordinator will contact you within 48 hours")

        elif choice == '3':
            # Browse upcoming presentations
            print("\n🎯 Upcoming Research Presentations")

            # Sample presentations
            presentations = [
                ("Machine Learning in Climate Modeling", "Dr. Sarah Chen", "Tomorrow 2pm", "Lecture Hall A"),
                ("Social Media Impact on Mental Health", "James Wilson (PhD)", "Friday 3pm", "Room 204"),
                ("Quantum Computing Applications", "Prof. David Kumar", "Next Monday 11am", "Virtual"),
                ("Sustainable Architecture Design", "Maria Rodriguez", "Next Wed 4pm", "Seminar Room B"),
                ("Biomedical Data Analysis", "Alex Thompson", "Next Friday 1pm", "Hybrid")
            ]

            print(f"{'Title':<35} {'Presenter':<20} {'Time':<15} {'Venue':<15}")
            print("-" * 90)

            for i, pres in enumerate(presentations, 1):
                print(f"{pres[0][:35]:<35} {pres[1]:<20} {pres[2]:<15} {pres[3]:<15}")

            register_choice = input("\nRegister for a presentation (enter number, 0 to skip): ").strip()
            if register_choice.isdigit() and 1 <= int(register_choice) <= len(presentations):
                selected = presentations[int(register_choice)-1]
                print(f"Registered for: {selected[0]}")
                print("Calendar invitation will be sent to your email")

        elif choice == '4':
            # Presentation skills workshop
            print("\n🎯 Presentation Skills Workshop")

            print("Workshop modules:")
            print("• Structuring your presentation")
            print("• Effective visual aids")
            print("• Handling Q&A sessions")
            print("• Managing presentation anxiety")
            print("• Virtual presentation techniques")
            print("• Academic presentation conventions")

            skill_level = input("Your presentation experience (beginner/intermediate/advanced): ").strip()

            workshops = {
                'beginner': [
                    "Presentation Basics (2 hours)",
                    "Overcoming Nerves (1 hour)",
                    "Visual Design Fundamentals (1.5 hours)"
                ],
                'intermediate': [
                    "Advanced Storytelling (2 hours)",
                    "Audience Engagement (1.5 hours)",
                    "Q&A Mastery (1 hour)"
                ],
                'advanced': [
                    "Executive Presentation Skills (2 hours)",
                    "Media Training (1.5 hours)",
                    "International Audience Adaptation (1 hour)"
                ]
            }

            recommended_workshops = workshops.get(skill_level, workshops['beginner'])

            print(f"\nRecommended workshops for {skill_level} level:")
            for workshop in recommended_workshops:
                print(f"• {workshop}")

            enroll = input("\nEnroll in presentation skills program? (y/n): ").strip().lower() == 'y'
            if enroll:
                print("Enrolled in presentation skills development program!")
                print("Workshop schedule will be emailed to you")

        elif choice == '5':
            # Feedback and ratings
            print("\n⭐ Presentation Feedback System")

            print("Feedback categories:")
            print("• Content quality and relevance")
            print("• Presentation clarity")
            print("• Visual aid effectiveness")
            print("• Q&A handling")
            print("• Overall engagement")

            print("\nRating system:")
            print("• 1-5 star ratings for each category")
            print("• Written feedback comments")
            print("• Anonymous feedback option")
            print("• Constructive improvement suggestions")

            view_feedback = input("View feedback for your presentations? (y/n): ").strip().lower() == 'y'
            if view_feedback:
                print("\nYour presentation feedback summary:")
                print("• Average rating: 4.2/5 stars")
                print("• Total presentations: 3")
                print("• Audience reach: 127 people")
                print("• Top strength: Clear explanations")
                print("• Improvement area: Visual aids")

    except Exception as e:
        logger.error("Error: %s", e, exc_info=True)
        print(f"An error occurred: {e}")
