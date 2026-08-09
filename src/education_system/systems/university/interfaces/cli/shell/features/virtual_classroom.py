"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import (
    AuthenticationError,
    BreakoutRoomManager,
    ChatManager,
    ParticipantManager,
    PermissionDeniedError,
    PollManager,
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

def _vc_create_polls(auth):
    """Create polls/quizzes sub-menu"""
    print("\n--- Polls & Quizzes ---")
    print("1. Create a poll")
    print("2. View session polls")
    print("3. View poll results")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        plm = PollManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            question = input("Enter poll question: ").strip()
            poll_type = input("Poll type (multiple_choice/true_false/open_ended) [multiple_choice]: ").strip() or "multiple_choice"
            options = None
            if poll_type in ('multiple_choice', 'true_false'):
                options_str = input("Enter options (comma-separated): ").strip()
                options = [o.strip() for o in options_str.split(',') if o.strip()]
            correct_answer = input("Correct answer (optional): ").strip() or None
            time_limit_str = input("Time limit in seconds (optional): ").strip()
            time_limit = int(time_limit_str) if time_limit_str else None
            poll_id = plm.create_poll(
                session_id=session_id, question=question,
                created_by=auth.current_user['user_id'],
                poll_type=poll_type, options=options,
                correct_answer=correct_answer, time_limit=time_limit
            )
            if poll_id:
                print(f"✅ Poll created! Poll ID: {poll_id}")
            else:
                print("❌ Failed to create poll.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            polls = plm.get_session_polls(session_id)
            if polls:
                for p in polls:
                    print(f"  ID: {p['id']}, Question: {p.get('question', 'N/A')}, Type: {p.get('poll_type', 'N/A')}, Status: {p.get('status', 'N/A')}")
            else:
                print("No polls found for this session.")
        elif sub == '3':
            poll_id = int(input("Enter poll ID: ").strip())
            results = plm.get_poll_results(poll_id)
            for k, v in results.items():
                print(f"  {k}: {v}")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")

def _vc_manage_breakout_rooms(auth):
    """Manage breakout rooms sub-menu"""
    print("\n--- Breakout Rooms ---")
    print("1. Create breakout room")
    print("2. View session rooms")
    print("3. Start a room")
    print("4. End a room")
    print("5. Return")
    sub = input("Choice: ").strip()
    try:
        brm = BreakoutRoomManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            room_name = input("Enter room name: ").strip()
            room_number = int(input("Enter room number: ").strip())
            participants_str = input("Enter participant user IDs (comma-separated): ").strip()
            participants = [int(p.strip()) for p in participants_str.split(',') if p.strip()]
            topic = input("Topic (optional): ").strip() or None
            duration = int(input("Duration in minutes [15]: ").strip() or "15")
            room_id = brm.create_breakout_room(
                session_id=session_id, room_name=room_name,
                room_number=room_number, participants=participants,
                topic=topic, duration_minutes=duration
            )
            if room_id:
                print(f"✅ Breakout room created! Room ID: {room_id}")
            else:
                print("❌ Failed to create breakout room.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            rooms = brm.get_session_breakout_rooms(session_id)
            if rooms:
                for r in rooms:
                    print(f"  ID: {r['id']}, Name: {r.get('room_name', 'N/A')}, Status: {r.get('status', 'N/A')}, Topic: {r.get('topic', 'N/A')}")
            else:
                print("No breakout rooms found.")
        elif sub == '3':
            room_id = int(input("Enter room ID to start: ").strip())
            if brm.start_breakout_room(room_id):
                print("✅ Breakout room started!")
            else:
                print("❌ Failed to start breakout room.")
        elif sub == '4':
            room_id = int(input("Enter room ID to end: ").strip())
            if brm.end_breakout_room(room_id):
                print("✅ Breakout room ended!")
            else:
                print("❌ Failed to end breakout room.")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error: {e}")

def _vc_view_chat(auth):
    """View chat messages sub-menu"""
    print("\n--- Chat Messages ---")
    print("1. View session messages")
    print("2. Search messages")
    print("3. Chat statistics")
    print("4. Return")
    sub = input("Choice: ").strip()
    try:
        cm = ChatManager()
        if sub == '1':
            session_id = int(input("Enter session ID: ").strip())
            limit = int(input("Number of messages to show [50]: ").strip() or "50")
            messages = cm.get_session_messages(session_id, limit=limit)
            if messages:
                for m in messages:
                    print(f"  [{m.get('timestamp', '')}] {m.get('user_name', 'Unknown')}: {m.get('message_text', '')}")
            else:
                print("No messages found.")
        elif sub == '2':
            session_id = int(input("Enter session ID: ").strip())
            search_term = input("Search term: ").strip()
            results = cm.search_messages(session_id, search_term)
            if results:
                for m in results:
                    print(f"  [{m.get('timestamp', '')}] {m.get('user_name', 'Unknown')}: {m.get('message_text', '')}")
            else:
                print("No matching messages found.")
        elif sub == '3':
            session_id = int(input("Enter session ID: ").strip())
            stats = cm.get_chat_statistics(session_id)
            for k, v in stats.items():
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
    print(f"5. {get_text('virtual.menu.create_polls', default='Create Polls/Quizzes')}")
    print(f"6. {get_text('virtual.menu.breakout_rooms', default='Manage Breakout Rooms')}")
    print(f"7. {get_text('virtual.menu.view_chat', default='View Chat Messages')}")
    print(f"8. {get_text('virtual.menu.analytics', default='Session Analytics')}")
    print(f"9. {get_text('virtual.menu.language', default='Language')}")
    print(f"10. {get_text('virtual.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('virtual.prompt.choice', default='Enter your choice (1-10)')}: ").strip()

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
                _vc_create_polls(auth)
            elif choice == '6':
                _vc_manage_breakout_rooms(auth)
            elif choice == '7':
                _vc_view_chat(auth)
            elif choice == '8':
                _vc_session_analytics(auth)
            elif choice == '9':
                display_language_menu_option()
            elif choice == '10':
                print(get_text('virtual.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('virtual.invalid_choice', default='Invalid choice. Please enter a number between 1 and 10.'))

        except KeyboardInterrupt:
            print(get_text('virtual.exiting', default='\n\nExiting virtual classroom menu...'))
            break
        except (ValueError, TypeError, ValidationError) as e:
            print(get_text('virtual.error', default='Error: {error}').format(error=e))
