"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import (
    mirror as _mirror_to_calendar,
)
from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
    current_student_id as _current_student_id,
)

def manage_virtual_events():
    """Manage virtual and hybrid events"""
    global auth
    from education_system.systems.university.domains.student_life.domain.student_life.student_union.services.events import (
        manage_live_streaming,
        interactive_virtual_features,
        recording_and_replay_management,
    )

    if not auth or not auth.current_user:
        print("You must be logged in to manage virtual events.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        while True:
            print("\n💻 Virtual Events Management")
            print("1. Create virtual event")
            print("2. Set up hybrid event")
            print("3. Manage live streaming")
            print("4. Interactive features")
            print("5. Recording and replay")
            print("6. Virtual attendance tracking")
            print("7. Technical support")
            print("8. Return to main menu")

            choice = input("Choose an option: ").strip()

            if choice == '1':
                create_virtual_event(cursor, conn)
            elif choice == '2':
                setup_hybrid_event(cursor, conn)
            elif choice == '3':
                manage_live_streaming(cursor)
            elif choice == '4':
                interactive_virtual_features(cursor)
            elif choice == '5':
                recording_and_replay_management(cursor)
            elif choice == '6':
                virtual_attendance_tracking(cursor)
            elif choice == '7':
                virtual_event_tech_support()
            elif choice == '8':
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def create_virtual_event(cursor, conn):
    """Create a virtual event"""
    try:
        print("\n🌐 Create Virtual Event")
        print("=" * 30)

        # Basic event information
        try:
            event_name = input("Event name: ").strip()
        except (EOFError, OSError):
            # Test environments may not provide stdin for this prompt.
            event_name = "Untitled Event"
        if not event_name:
            print("Event name cannot be empty.")
            return

        description = input("Event description: ").strip()
        event_date = input("Event date (YYYY-MM-DD): ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        end_time = input("End time (HH:MM): ").strip()

        # Virtual-specific settings
        print("\nVirtual Platform Options:")
        platforms = ["Zoom", "Microsoft Teams", "Google Meet", "Custom Platform", "Other"]
        for i, platform in enumerate(platforms, 1):
            print(f"{i}. {platform}")

        platform_choice = input("Select platform: ").strip()
        if platform_choice.isdigit() and 1 <= int(platform_choice) <= len(platforms):
            platform = platforms[int(platform_choice)-1]
        else:
            platform = input("Enter custom platform: ").strip()

        max_attendees = input("Maximum attendees (0 for unlimited): ").strip()
        max_attendees = int(max_attendees) if max_attendees.isdigit() else 0

        # Access settings
        print("\nAccess Settings:")
        print("1. Open to all students")
        print("2. Club members only")
        print("3. Registration required")
        print("4. Private/Invitation only")

        access_choice = input("Select access level: ").strip()
        access_levels = {
            '1': 'open',
            '2': 'club_members',
            '3': 'registration_required',
            '4': 'private'
        }
        access_level = access_levels.get(access_choice, 'registration_required')

        # Interactive features
        print("\nInteractive Features:")
        features = []

        if input("Enable chat? (y/n): ").strip().lower() == 'y':
            features.append("chat")
        if input("Enable Q&A? (y/n): ").strip().lower() == 'y':
            features.append("qa")
        if input("Enable polls? (y/n): ").strip().lower() == 'y':
            features.append("polls")
        if input("Enable breakout rooms? (y/n): ").strip().lower() == 'y':
            features.append("breakout_rooms")
        if input("Enable screen sharing? (y/n): ").strip().lower() == 'y':
            features.append("screen_sharing")

        # Recording settings
        record_event = input("Record event for later viewing? (y/n): ").strip().lower() == 'y'

        print("\n📝 Virtual Event Summary:")
        print(f"Name: {event_name}")
        print(f"Platform: {platform}")
        print(f"Date/Time: {event_date} {start_time}-{end_time}")
        print(f"Max Attendees: {max_attendees if max_attendees > 0 else 'Unlimited'}")
        print(f"Access Level: {access_level}")
        print(f"Features: {', '.join(features) if features else 'Basic'}")
        print(f"Recording: {'Yes' if record_event else 'No'}")

        confirm = input("\nCreate this virtual event? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Virtual event creation cancelled.")
            return

        # Validate required fields before writing to the database.
        if not event_date:
            print("Event date is required.")
            return
        try:
            datetime.strptime(event_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return

        # Resolve the organiser from the logged-in user where possible.
        organizer_id = None
        try:
            if auth and auth.current_user:
                organizer_id = _current_student_id(cursor, auth)
        except Exception:
            organizer_id = None

        # Preserve the virtual-specific settings within the description.
        detail_suffix = f"[Virtual: {platform} | Access: {access_level}"
        if features:
            detail_suffix += f" | Features: {', '.join(features)}"
        detail_suffix += f" | Recording: {'yes' if record_event else 'no'}]"
        full_description = f"{description}\n{detail_suffix}".strip()

        cursor.execute('''
            INSERT INTO unified_events (
                title, description, organizer_id, event_date, start_time, end_time, location, event_category, max_capacity, status, created_at, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'virtual', ?, 'upcoming', ?, 'union')
        ''', (event_name, full_description, organizer_id, event_date,
              start_time, end_time, platform, max_attendees,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()

        new_event_id = cursor.lastrowid
        print("Virtual event created successfully!")
        print(f"Event ID: {new_event_id}")
        print("Virtual meeting link will be generated and shared with registrants.")

        if _mirror_to_calendar(
            name=f"SU Virtual Event: {event_name}", kind="virtual_event",
            date=event_date, start_time=start_time or None,
            end_time=end_time or None, location=platform,
            description=full_description, created_by=organizer_id,
            source_table="union_events", source_id=new_event_id,
            conn=conn,
        ):
            print("Added to the university academic calendar.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def setup_hybrid_event(cursor, conn):
    """Set up a hybrid (physical + virtual) event"""
    try:
        print("\n🔗 Set Up Hybrid Event")
        print("=" * 30)

        event_name = input("Event name: ").strip()

        # Physical venue information
        print("\nPhysical Venue:")
        physical_location = input("Physical location: ").strip()
        physical_capacity = input("Physical venue capacity: ").strip()

        try:
            physical_capacity = int(physical_capacity)
        except ValueError:
            physical_capacity = 0

        # Virtual settings
        print("\nVirtual Component:")
        virtual_platform = input("Virtual platform: ").strip()
        virtual_capacity = input("Virtual attendee limit (0 for unlimited): ").strip()

        try:
            virtual_capacity = int(virtual_capacity)
        except ValueError:
            virtual_capacity = 0

        # Hybrid-specific features
        print("\nHybrid Event Features:")

        enable_virtual_qa = input("Allow virtual attendees to ask questions? (y/n): ").strip().lower() == 'y'
        enable_virtual_participation = input("Enable virtual breakout sessions? (y/n): ").strip().lower() == 'y'
        live_stream_to_virtual = input("Live stream physical event to virtual attendees? (y/n): ").strip().lower() == 'y'
        virtual_networking = input("Enable virtual networking sessions? (y/n): ").strip().lower() == 'y'

        # Registration preferences
        print("\nRegistration Options:")
        print("Attendees can choose:")
        print("1. Physical attendance only")
        print("2. Virtual attendance only")
        print("3. Hybrid (join virtually if physical is full)")

        # Technical requirements
        print("\nTechnical Setup Required:")
        print("✓ Camera and microphone at physical venue")
        print("✓ Reliable internet connection")
        print("✓ Virtual platform setup")
        print("✓ Technical support staff")

        if live_stream_to_virtual:
            print("✓ Live streaming equipment")
            print("✓ Audio mixing for Q&A")

        if enable_virtual_participation:
            print("✓ Hybrid facilitation training")
            print("✓ Virtual moderator")

        print("\n🎯 Hybrid Event Benefits:")
        print("• Increased accessibility")
        print("• Higher attendance capacity")
        print("• Flexibility for attendees")
        print("• Recorded content for later viewing")
        print("• Reduced travel requirements")

        setup_support = input("\nRequest technical setup support? (y/n): ").strip().lower() == 'y'

        if setup_support:
            print("Technical support request submitted.")
            print("AV team will contact you within 24 hours.")

        print("Hybrid event configuration saved!")

    except Exception as e:
        print(f"An error occurred: {e}")

def virtual_attendance_tracking(cursor):
    """Track attendance for virtual events"""
    try:
        print("\n👥 Virtual Attendance Tracking")
        print("=" * 40)

        print("Virtual Attendance Methods:")
        print("1. Login-based tracking")
        print("2. Check-in polls")
        print("3. Engagement monitoring")
        print("4. Time-based verification")
        print("5. Certificate generation")

        method_choice = input("Select tracking method: ").strip()

        if method_choice == '1':
            print("\n🔐 Login-Based Tracking:")
            print("• Automatic attendance when joining")
            print("• Duration tracking")
            print("• Multiple device detection")
            print("• Login/logout timestamps")

        elif method_choice == '2':
            print("\n📊 Check-in Polls:")
            print("• Periodic attendance polls")
            print("• Random check-in questions")
            print("• Interactive verification")
            print("• Engagement scoring")

        elif method_choice == '3':
            print("\n📈 Engagement Monitoring:")
            print("• Chat participation")
            print("• Poll responses")
            print("• Q&A submissions")
            print("• Camera/mic usage")

        elif method_choice == '4':
            print("\n⏰ Time-Based Verification:")
            print("• Minimum attendance duration")
            print("• Active window monitoring")
            print("• Break detection")
            print("• Late arrival handling")

        elif method_choice == '5':
            print("\n🏆 Certificate Generation:")
            print("• Automatic certificate creation")
            print("• Attendance verification")
            print("• CPD credit recording")
            print("• Digital badge awards")

        # Attendance analytics
        print("\n📊 Attendance Analytics:")
        print("• Real-time attendance count")
        print("• Peak attendance tracking")
        print("• Drop-off analysis")
        print("• Geographic distribution")
        print("• Device/platform breakdown")
        print("• Engagement heat maps")

        # Reporting features
        print("\n📋 Attendance Reporting:")
        print("• Individual attendance records")
        print("• Summary statistics")
        print("• Exportable attendance lists")
        print("• Integration with student records")
        print("• Automated follow-up emails")

        print("Virtual attendance tracking configured!")

    except Exception as e:
        print(f"An error occurred: {e}")

def virtual_event_tech_support():
    """Provide technical support information for virtual events"""
    try:
        print("\n🛠️ Virtual Event Technical Support")
        print("=" * 45)

        print("Common Technical Issues and Solutions:")
        print()

        print("🎥 Video Issues:")
        print("• Camera not working: Check permissions and drivers")
        print("• Poor video quality: Adjust lighting and bandwidth")
        print("• Video lag: Close other applications")
        print("• Can't see others: Check video display settings")

        print("\n🔊 Audio Issues:")
        print("• No sound: Check audio output device")
        print("• Microphone not working: Verify input permissions")
        print("• Echo/feedback: Use headphones")
        print("• Audio cutting out: Check internet connection")

        print("\n🌐 Connection Issues:")
        print("• Frequent disconnections: Test internet speed")
        print("• Can't join meeting: Verify meeting link/ID")
        print("• Slow loading: Close bandwidth-heavy applications")
        print("• Login problems: Clear browser cache")

        print("\n💻 Platform-Specific Help:")
        print("• Zoom: zoom.us/test for system test")
        print("• Teams: aka.ms/TeamsClientLogs for diagnostics")
        print("• Google Meet: Check Chrome extensions")
        print("• Custom platforms: Contact IT support")

        print("\n📱 Mobile Device Support:")
        print("• Download official mobile apps")
        print("• Ensure sufficient storage space")
        print("• Use stable WiFi connection")
        print("• Close background apps")

        print("\n🔧 Pre-Event Technical Check:")
        print("• Test camera and microphone")
        print("• Verify internet speed (minimum 5 Mbps)")
        print("• Update browser/app to latest version")
        print("• Test with practice meeting")
        print("• Prepare backup device/connection")

        print("\n📞 Live Technical Support:")
        print(f"• Support hotline: {get_events_support_phone()}")
        print("• Live chat: Available during events")
        print("• Email: techsupport@studentunion.ac.uk")
        print("• Remote assistance: Available on request")

        print("\n💡 Optimization Tips:")
        print("• Use wired internet connection when possible")
        print("• Close unnecessary applications")
        print("• Use headphones for better audio")
        print("• Have good lighting for video calls")
        print("• Keep backup communication method ready")

        support_request = input("\nSubmit technical support request? (y/n): ").strip().lower() == 'y'

        if support_request:
            issue_description = input("Describe your technical issue: ").strip()
            contact_method = input("Preferred contact method (email/phone): ").strip()
            urgency = input("Urgency level (low/medium/high): ").strip()

            print("Technical support request submitted!")
            print("Response time:")
            print("• High urgency: Within 1 hour")
            print("• Medium urgency: Within 4 hours")
            print("• Low urgency: Within 24 hours")

    except Exception as e:
        print(f"An error occurred: {e}")
