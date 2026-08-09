"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.pastoral.domain.student_life.student_union.events.infrastructure.qr_codes import generate_qr_code
from education_system.systems.university.domains.pastoral.interfaces.cli.student_union_events.context import auth

def _manage_event_attendance_simple():
    """Manage event attendance for club events."""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage attendance.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        cursor.execute('''
        SELECT c.club_id, c.club_name
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ?
        ''', (student_id,))
        clubs = cursor.fetchall()

        if not clubs:
            print("You are not an officer of any club.")
            conn.close()
            return

        cursor.execute('''
        SELECT e.event_id, e.event_name, e.event_date
        FROM union_events e
        WHERE e.organizer_id IN (
            SELECT club_id FROM club_members WHERE student_id = ?
        )
        ORDER BY e.event_date DESC
        ''', (student_id,))
        events = cursor.fetchall()

        if not events:
            print("No events found for your clubs.")
            conn.close()
            return

        print("\nEvent Attendance Management")
        print("1. Mark attendance")
        print("2. View attendance list")
        print("3. Return")

        choice = input("Choose an option: ").strip()

        if choice not in {'1', '2'}:
            conn.close()
            return

        event_id = input("Enter event ID: ").strip()
        if not event_id.isdigit():
            print("Invalid event ID.")
            conn.close()
            return

        cursor.execute('''
        SELECT COUNT(*) FROM union_events
        WHERE event_id = ? AND organizer_id IN (
            SELECT club_id FROM club_members WHERE student_id = ?
        )
        ''', (event_id, student_id))
        if cursor.fetchone()[0] == 0:
            print("You can only manage attendance for your own club events.")
            conn.close()
            return

        if choice == '1':
            target_student = input("Enter student ID to mark attendance: ").strip()
            cursor.execute('''
            SELECT COUNT(*) FROM unified_event_registrations
            WHERE event_id = ? AND user_id = ?
            ''', (event_id, target_student))
            if cursor.fetchone()[0] == 0:
                print("Student is not registered for this event.")
                conn.close()
                return

            cursor.execute('''
            UPDATE unified_event_registrations
            SET attendance_status = 'checked_in'
            WHERE event_id = ? AND user_id = ?
            ''', (event_id, target_student))
            conn.commit()
            print("Attendance marked.")
        else:
            cursor.execute('''
            SELECT r.user_id, s.first_name, s.last_name, r.attendance_status, r.registration_date
            FROM unified_event_registrations r
            JOIN students s ON r.user_id = s.student_id
            WHERE r.event_id = ?
            ORDER BY r.registration_date ASC
            ''', (event_id,))
            attendees = cursor.fetchall()

            if not attendees:
                print("No registrations found for this event.")
            else:
                print("\nAttendance List:")
                for attendee in attendees:
                    print(f"{attendee[0]} - {attendee[1]} {attendee[2]} ({attendee[3]})")

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def manage_event_attendance():
    """Manage event attendance tracking"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage event attendance.")
        return

    if not (auth.check_permission('create_club_events') or auth.check_permission('manage_all_events')):
        print("You don't have permission to manage event attendance.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()

        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return

        student_id = result[0]

        # Get events user can manage
        if auth.check_permission('manage_all_events'):
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date, e.status
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE e.event_date >= date('now', '-7 days')
            ORDER BY e.event_date DESC
            ''')
        else:
            cursor.execute('''
            SELECT e.event_id, e.event_name, c.club_name, e.event_date, e.status
            FROM union_events e
            JOIN student_clubs c ON e.organizer_id = c.club_id
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND e.event_date >= date('now', '-7 days')
            ORDER BY e.event_date DESC
            ''', (student_id, student_id, student_id))

        events = cursor.fetchall()

        if not events:
            print("No recent events available for attendance management.")
            conn.close()
            return

        print("\nRecent events:")
        for i, event in enumerate(events):
            print(f"{i+1}. {event[1]} ({event[2]}) - {event[3]} [{event[4]}]")

        choice = input("Select an event to manage attendance (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(events):
            print("Invalid selection.")
            conn.close()
            return

        selected_event = events[int(choice)-1]
        event_id = selected_event[0]
        event_name = selected_event[1]

        while True:
            print(f"\nAttendance Management - {event_name}")
            print("1. Generate QR codes for registered attendees")
            print("2. Check in attendee")
            print("3. View attendance report")
            print("4. Mark attendance for multiple students")
            print("5. Award CPD credits")
            print("6. Return to previous menu")

            action = input("Choose an action: ").strip()

            if action == '1':
                # Generate QR codes for registered attendees
                cursor.execute('''
                SELECT r.user_id, s.first_name, s.last_name
                FROM unified_event_registrations r
                JOIN students s ON r.user_id = s.student_id
                WHERE r.event_id = ? AND r.attendance_status = 'registered'
                ''', (event_id,))

                registered = cursor.fetchall()

                if not registered:
                    print("No registered attendees found.")
                    continue

                print(f"\nGenerating QR codes for {len(registered)} registered attendees...")

                for attendee in registered:
                    qr_code = generate_qr_code()

                    # Check if attendance record already exists
                    cursor.execute('''
                    SELECT COUNT(*) FROM unified_event_registrations
                    WHERE event_id = ? AND user_id = ? AND qr_code IS NOT NULL
                    ''', (event_id, attendee[0]))

                    if cursor.fetchone()[0] == 0:
                        cursor.execute('''
                        UPDATE unified_event_registrations
                        SET qr_code = ?
                        WHERE event_id = ? AND user_id = ?
                        ''', (qr_code, event_id, attendee[0]))

                    print(f"{attendee[1]} {attendee[2]} ({attendee[0]}): QR-{qr_code}")

                conn.commit()
                print("QR codes generated successfully!")

            elif action == '2':
                # Check in attendee
                qr_or_id = input("Enter QR code or Student ID: ").strip()

                if qr_or_id.startswith('QR-'):
                    qr_code = qr_or_id[3:]  # Remove 'QR-' prefix
                    cursor.execute('''
                    SELECT a.user_id, s.first_name, s.last_name
                    FROM unified_event_registrations a
                    JOIN students s ON a.user_id = s.student_id
                    WHERE a.event_id = ? AND a.qr_code = ?
                    ''', (event_id, qr_code))
                else:
                    cursor.execute('''
                    SELECT a.user_id, s.first_name, s.last_name
                    FROM unified_event_registrations a
                    JOIN students s ON a.user_id = s.student_id
                    WHERE a.event_id = ? AND a.user_id = ?
                    ''', (event_id, qr_or_id))

                attendee = cursor.fetchone()

                if not attendee:
                    print("Attendee not found or not registered for this event.")
                    continue

                # Check if already checked in
                cursor.execute('''
                SELECT checked_in_at FROM unified_event_registrations
                WHERE event_id = ? AND user_id = ?
                ''', (event_id, attendee[0]))

                check_in_data = cursor.fetchone()

                if check_in_data and check_in_data[0]:
                    print(f"{attendee[1]} {attendee[2]} is already checked in at {check_in_data[0]}.")
                    continue

                # Record check-in
                check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                cursor.execute('''
                UPDATE unified_event_registrations
                SET checked_in_at = ?, attendance_status = 'verified'
                WHERE event_id = ? AND user_id = ?
                ''', (check_in_time, event_id, attendee[0]))

                # Update registration status
                cursor.execute('''
                UPDATE unified_event_registrations
                SET attendance_status = 'attended'
                WHERE event_id = ? AND user_id = ?
                ''', (event_id, attendee[0]))

                conn.commit()
                print(f"✓ {attendee[1]} {attendee[2]} checked in successfully at {check_in_time}")

            elif action == '3':
                # View attendance report
                cursor.execute('''
                SELECT
                    COUNT(*) as total_registered,
                    COUNT(CASE WHEN r.checked_in_at IS NOT NULL THEN 1 END) as attended,
                    COUNT(CASE WHEN r.checked_in_at IS NULL THEN 1 END) as no_show
                FROM unified_event_registrations r
                WHERE r.event_id = ?
                ''', (event_id,))

                stats = cursor.fetchone()

                print(f"\nAttendance Report - {event_name}")
                print("=" * 40)
                print(f"Total Registered: {stats[0]}")
                print(f"Attended: {stats[1]}")
                print(f"No Shows: {stats[2]}")

                if stats[0] > 0:
                    attendance_rate = (stats[1] / stats[0]) * 100
                    print(f"Attendance Rate: {attendance_rate:.1f}%")

                # Show individual attendance
                print("\nIndividual Attendance:")
                print(f"{'Student ID':<12} {'Name':<25} {'Status':<15} {'Check-in Time':<20}")
                print("-" * 75)

                cursor.execute('''
                SELECT r.user_id, s.first_name, s.last_name,
                       COALESCE(r.checked_in_at, 'Not checked in') as check_in,
                       CASE WHEN r.checked_in_at IS NOT NULL THEN 'Attended' ELSE 'No Show' END as status
                FROM unified_event_registrations r
                JOIN students s ON r.user_id = s.student_id
                WHERE r.event_id = ?
                ORDER BY s.last_name, s.first_name
                ''', (event_id,))

                attendees = cursor.fetchall()

                for attendee in attendees:
                    print(f"{attendee[0]:<12} {attendee[1]} {attendee[2]:<25} {attendee[4]:<15} {attendee[3]:<20}")

            elif action == '4':
                # Mark attendance for multiple students
                print("Enter student IDs (one per line, empty line to finish):")
                student_ids = []

                while True:
                    student_id_input = input().strip()
                    if not student_id_input:
                        break
                    student_ids.append(student_id_input)

                if not student_ids:
                    print("No student IDs entered.")
                    continue

                check_in_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                successful_checkins = 0

                for sid in student_ids:
                    try:
                        # Check if student is registered
                        cursor.execute('''
                        SELECT COUNT(*) FROM unified_event_registrations
                        WHERE event_id = ? AND user_id = ?
                        ''', (event_id, sid))

                        if cursor.fetchone()[0] == 0:
                            print(f"Student {sid} is not registered for this event.")
                            continue

                        # Create or update attendance record
                        cursor.execute('''
                        UPDATE unified_event_registrations
                        SET checked_in_at = ?, attendance_status = 'verified'
                        WHERE event_id = ? AND user_id = ?
                        ''', (check_in_time, event_id, sid))

                        # Update registration status
                        cursor.execute('''
                        UPDATE unified_event_registrations
                        SET attendance_status = 'attended'
                        WHERE event_id = ? AND user_id = ?
                        ''', (event_id, sid))

                        successful_checkins += 1

                    except sqlite3.Error as e:
                        print(f"Error checking in student {sid}: {e}")

                conn.commit()
                print(f"Successfully checked in {successful_checkins} students.")

            elif action == '5':
                # Award CPD credits
                try:
                    cpd_credits = float(input("CPD credits to award per attendee: ").strip())
                    if cpd_credits <= 0:
                        print("CPD credits must be positive.")
                        continue
                except ValueError:
                    print("Invalid CPD credits format.")
                    continue

                cursor.execute('''
                UPDATE unified_event_registrations
                SET cpd_credits = ?
                WHERE event_id = ? AND attendance_status = 'verified'
                ''', (cpd_credits, event_id))

                affected_rows = cursor.rowcount
                conn.commit()

                print(f"Awarded {cpd_credits} CPD credits to {affected_rows} attendees.")

            elif action == '6':
                break

            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
