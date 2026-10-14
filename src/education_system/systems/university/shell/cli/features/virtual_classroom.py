"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import (
    AuthenticationError,
    ParticipantManager,
    PermissionDeniedError,
    RecordingManager,
    SessionManager,
    ValidationError,
    VirtualClassroomManager,
    datetime,
    display_language_menu_option,
    get_text,
)

def _vc_schedule_session(auth):
    """Schedule a virtual session sub-menu"""
    print("\n--- Schedule Virtual Session ---")
    print("1. Create new session")
    print("2. View upcoming sessions")
    print("3. List sessions by classroom")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        sm = SessionManager()
        if sub == '1':
            classroom_id = int(input("Enter classroom ID: ").strip())
            start_time_str = input("Enter start time (YYYY-MM-DD HH:MM): ").strip()
            start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
            session_type = input("Session type (lecture/lab/office_hours) [lecture]: ").strip() or "lecture"
            duration = int(input("Duration in minutes [60]: ").strip() or "60")
            notes = input("Notes (optional): ").strip() or None
            session_id = sm.create_session(
                classroom_id=classroom_id, start_time=start_time,
                session_type=session_type, duration_minutes=duration, notes=notes
            )
            if session_id:
                print(f"✅ Session created! Session ID: {session_id}")
            else:
                print("❌ Failed to create session.")
        elif sub == '2':
            classroom_id_str = input("Classroom ID (or Enter for all): ").strip()
            classroom_id = int(classroom_id_str) if classroom_id_str else None
            sessions = sm.get_upcoming_sessions(classroom_id=classroom_id)
            if sessions:
                for s in sessions:
                    print(f"  ID: {s['id']}, Start: {s.get('start_time', 'N/A')}, Type: {s.get('session_type', 'N/A')}, Status: {s.get('status', 'N/A')}")
            else:
                print("No upcoming sessions found.")
        elif sub == '3':
            classroom_id = int(input("Enter classroom ID: ").strip())
            sessions = sm.get_sessions_by_classroom(classroom_id)
            if sessions:
                for s in sessions:
                    print(f"  ID: {s['id']}, Start: {s.get('start_time', 'N/A')}, Type: {s.get('session_type', 'N/A')}, Status: {s.get('status', 'N/A')}")
            else:
                print("No sessions found for this classroom.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")

def _vc_manage_participants(auth):
    """Manage participants sub-menu"""
    print("\n--- Manage Participants ---")
    print("1. Join a session")
    print("2. View session participants")
    print("3. View attendance history")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        pm = ParticipantManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            user_id = auth.current_user['user_id']
            user_type = auth.current_user.get('role', 'student')
            device = input("Device type (desktop/mobile/tablet) [desktop]: ").strip() or "desktop"
            pid = pm.add_participant(
                session_id=session_id, user_id=user_id,
                user_type=user_type, device_type=device
            )
            if pid:
                print(f"✅ Joined session! Participant ID: {pid}")
            else:
                print("❌ Failed to join session.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            participants = pm.get_session_participants(session_id)
            if participants:
                for p in participants:
                    print(f"  User ID: {p.get('user_id')}, Type: {p.get('user_type')}, Status: {p.get('attendance_status', 'N/A')}")
            else:
                print("No participants found.")
        elif sub == '3':
            user_id_str = input("Enter user ID (or Enter for yourself): ").strip()
            user_id = int(user_id_str) if user_id_str else auth.current_user['user_id']
            history = pm.get_user_attendance_history(user_id)
            if history:
                for h in history:
                    print(f"  Session: {h.get('session_id')}, Status: {h.get('attendance_status', 'N/A')}, Joined: {h.get('join_time', 'N/A')}")
            else:
                print("No attendance history found.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")

def _vc_view_recordings(auth):
    """View recordings sub-menu"""
    print("\n--- View Recordings ---")
    print("1. List recordings by classroom")
    print("2. View recording details")
    print("3. View storage usage")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        rm = RecordingManager()
        if sub == '1':
            classroom_id = int(input("Enter classroom ID: ").strip())
            recordings = rm.get_recordings_by_classroom(classroom_id)
            if recordings:
                for r in recordings:
                    print(f"  ID: {r['id']}, File: {r.get('file_name', 'N/A')}, Duration: {r.get('duration', 'N/A')}s, Views: {r.get('view_count', 0)}")
            else:
                print("No recordings found.")
        elif sub == '2':
            recording_id = int(input("Enter recording ID: ").strip())
            rec = rm.get_recording(recording_id)
            if rec:
                for k, v in rec.items():
                    print(f"  {k}: {v}")
            else:
                print("Recording not found.")
        elif sub == '3':
            classroom_id_str = input("Classroom ID (or Enter for all): ").strip()
            classroom_id = int(classroom_id_str) if classroom_id_str else None
            usage = rm.get_storage_usage(classroom_id=classroom_id)
            for k, v in usage.items():
                print(f"  {k}: {v}")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")




def _vc_session_analytics(auth):
    """Session analytics sub-menu"""
    print("\n--- Session Analytics ---")
    print("1. View session statistics")
    print("2. Classroom overview")
    print("3. Return")
    sub = input("Choice: ").strip()
    try:
        if sub == '1':
            sm = SessionManager()
            session_id = int(input("Enter session ID: ").strip())
            stats = sm.get_session_statistics(session_id)
            if stats:
                for k, v in stats.items():
                    print(f"  {k}: {v}")
            else:
                print("No statistics available for this session.")
        elif sub == '2':
            vcm = VirtualClassroomManager()
            classroom_id = int(input("Enter classroom ID: ").strip())
            classroom = vcm.get_classroom(classroom_id)
            if classroom:
                for k, v in classroom.items():
                    print(f"  {k}: {v}")
            else:
                print("Classroom not found.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")

def display_virtual_classroom_menu(auth):
    """Display the virtual classroom management CLI menu"""
    print("\n" + "="*50)
    print(f"      {get_text('virtual.title', default='VIRTUAL CLASSROOM MANAGEMENT')}")
    print("="*50)
    print(f"1. {get_text('virtual.menu.create_classroom', default='Create Virtual Classroom')}")
    print(f"2. {get_text('virtual.menu.schedule_session', default='Schedule Virtual Session')}")
    print(f"3. {get_text('virtual.menu.manage_participants', default='Manage Participants')}")
    print(f"4. {get_text('virtual.menu.view_recordings', default='View Recordings')}")
    print(f"5. {get_text('virtual.menu.analytics', default='Session Analytics')}")
    print(f"6. {get_text('virtual.menu.language', default='Language')}")
    print(f"7. {get_text('virtual.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('virtual.prompt.choice', default='Enter your choice (1-7)')}: ").strip()

            if choice == '1':
                # Create Virtual Classroom
                try:
                    session_name = input(get_text('virtual.prompt.session_name', default='Enter session name: ')).strip()
                    platform = input(get_text('virtual.prompt.platform', default='Enter platform (zoom/teams/meet/webrtc): ')).strip()
                    meeting_link = input(get_text('virtual.prompt.meeting_link', default='Enter meeting link: ')).strip()

                    classroom_mgr = VirtualClassroomManager()
                    classroom_id = classroom_mgr.create_classroom(
                        session_name=session_name,
                        instructor_id=auth.current_user['user_id'],
                        platform=platform,
                        meeting_link=meeting_link
                    )
                    print(get_text('virtual.success.created', default='Virtual classroom created successfully! Classroom ID: {id}').format(id=classroom_id))
                except (AuthenticationError, PermissionDeniedError) as e:
                    print(get_text('virtual.error.creating', default='Error creating classroom: {error}').format(error=e))
            elif choice == '2':
                _vc_schedule_session(auth)
            elif choice == '3':
                _vc_manage_participants(auth)
            elif choice == '4':
                _vc_view_recordings(auth)
            elif choice == '5':
                _vc_session_analytics(auth)
            elif choice == '6':
                display_language_menu_option()
            elif choice == '7':
                print(get_text('virtual.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('virtual.invalid_choice', default='Invalid choice. Please enter a number between 1 and 7.'))

        except KeyboardInterrupt:
            print(get_text('virtual.exiting', default='\n\nExiting virtual classroom menu...'))
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(get_text('virtual.error', default='Error: {error}').format(error=e))
