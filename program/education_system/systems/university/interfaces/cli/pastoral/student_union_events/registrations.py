"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domain.pastoral.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.interfaces.cli.pastoral.student_union_events.context import auth
from education_system.systems.university.interfaces.cli.pastoral.student_union_events.catalogue import view_events
from education_system.systems.university.interfaces.cli.pastoral.student_union_events.context import auth

def register_for_event():
    """Register for an event"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to register for events.")
        return

    if not auth.check_permission('register_for_events'):
        print("You don't have permission to register for events.")
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

        # Show available events
        view_events()

        event_id = input("\nEnter the ID of the event you want to register for: ").strip()
        if not event_id.isdigit():
            print("Invalid event ID.")
            conn.close()
            return

        # Check if event exists and is upcoming
        cursor.execute('''
        SELECT event_name, max_attendees, current_attendees
        FROM union_events
        WHERE event_id = ? AND status = 'upcoming'
        ''', (event_id,))

        event = cursor.fetchone()

        if not event:
            print("Event not found or not available for registration.")
            conn.close()
            return

        # Check if already registered
        cursor.execute('''
        SELECT COUNT(*) FROM unified_event_registrations
        WHERE event_id = ? AND user_id = ?
        ''', (event_id, student_id))

        if cursor.fetchone()[0] > 0:
            print(f"You are already registered for {event[0]}.")
            conn.close()
            return

        # Check if event is full
        if event[1] > 0 and event[2] >= event[1]:
            print(f"Sorry, {event[0]} is already full.")
            conn.close()
            return

        # Register for the event
        registration_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO unified_event_registrations (event_id, user_id, user_type, registration_date, attendance_status)
        VALUES (?, ?, 'student', ?, ?)
        ''', (event_id, student_id, registration_date, 'registered'))


        # Update attendee count
        cursor.execute('''
        UPDATE union_events SET current_attendees = current_attendees + 1
        WHERE event_id = ?
        ''', (event_id,))

        conn.commit()
        print(f"You have successfully registered for {event[0]}!")

        # Send confirmation email
        send_confirmation_email(student_id, f"Event Registration: {event[0]}",
                               f"You have successfully registered for the {event[0]} event.")

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_my_events():
    """View events I'm registered for"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view your events.")
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

        # Get events the student is registered for
        cursor.execute('''
        SELECT e.event_id, e.event_name, e.event_date, e.start_time, e.location,
               c.club_name, r.registration_date, r.attendance_status
        FROM union_events e
        JOIN student_clubs c ON e.organizer_id = c.club_id
        JOIN unified_event_registrations r ON e.event_id = r.event_id
        WHERE r.user_id = ?
        ORDER BY e.event_date, e.start_time
        ''', (student_id,))

        events = cursor.fetchall()

        if not events:
            print("You are not registered for any events.")
            conn.close()
            return

        print("\nYour Registered Events:")
        print("=======================")

        for event in events:
            print(f"\nID: {event[0]}")
            print(f"Name: {event[1]}")
            print(f"Date: {event[2]} at {event[3]}")
            print(f"Location: {event[4]}")
            print(f"Organized by: {event[5]}")
            print(f"Registration Date: {event[6]}")
            print(f"Status: {event[7]}")
            print("-" * 40)

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
