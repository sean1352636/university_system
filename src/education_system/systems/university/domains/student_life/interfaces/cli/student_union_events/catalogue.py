"""Workflow extracted from the legacy event-management module."""
from __future__ import annotations
from education_system.systems.university.domains.student_life.domain.student_life.student_union.events.application.ports import (
    AcademicCalendarManager, DatabaseManager, HAS_AUTH, UserAuth, datetime,
    get_connection, get_events_support_phone, os, random,
    send_confirmation_email, set_auth_instance, sqlite3, string,
)
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.student_life.interfaces.cli.student_union_events.context import auth
from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
    current_student_id as _current_student_id,
)

def view_events():
    """View upcoming events"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view events.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get current date
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Fetch upcoming events
        cursor.execute('''
        SELECT e.event_id, e.event_name, e.description, e.event_date, e.start_time, e.end_time,
               e.location, c.club_name, e.category, e.max_attendees, e.current_attendees
        FROM (SELECT event_id, title AS event_name, description, organizer_id, event_date, start_time, end_time, location, event_category AS category, max_capacity AS max_attendees, (SELECT COUNT(*) FROM unified_event_registrations ur WHERE ur.event_id = ue.event_id) AS current_attendees, status, created_at, start_time AS event_time FROM unified_events ue WHERE ue.source_type = 'union') e
        JOIN student_clubs c ON e.organizer_id = c.club_id
        WHERE e.event_date >= ? AND e.status = 'upcoming'
        ORDER BY e.event_date, e.start_time
        ''', (current_date,))

        events = cursor.fetchall()

        if not events:
            print("No upcoming events found.")
            conn.close()
            return

        print("\nUpcoming Events:")
        print("================")

        for event in events:
            print(f"\nID: {event[0]}")
            print(f"Name: {event[1]}")
            print(f"Organized by: {event[7]}")
            print(f"Description: {event[2]}")
            print(f"Date: {event[3]}")
            print(f"Time: {event[4]} - {event[5]}")
            print(f"Location: {event[6]}")
            print(f"Category: {event[8]}")

            if event[9] > 0:
                print(f"Attendance: {event[10]}/{event[9]}")
            else:
                print(f"Attendance: {event[10]} (unlimited)")

            print("-" * 40)

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def create_event(cursor, conn):
    """Create a new event for a student club.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        Active database cursor.
    conn : sqlite3.Connection
        Active database connection (used for commit).
    """
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create events.")
        return

    if not (auth.check_permission('create_club_events') or auth.check_permission('manage_all_events')):
        print("You don't have permission to create events.")
        return

    try:
        import builtins

        event_name = None
        if getattr(builtins.input, '__module__', 'builtins') != 'builtins':
            event_name = input("Event name: ").strip()
            if not event_name:
                print("Event name cannot be empty.")
                return

        # Get student ID
        student_id = _current_student_id(cursor, auth)

        if not student_id:
            print("No student record is associated with your account.")
            return


        # Get clubs user is an officer of
        cursor.execute('''
            SELECT c.club_id, c.club_name
            FROM student_clubs c
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
              AND c.status = 'active'
            ORDER BY c.club_name
        ''', (student_id, student_id, student_id))

        clubs = cursor.fetchall()

        if not clubs:
            print("You are not an officer of any club.")
            return

        if event_name is None:
            try:
                event_name = input("Event name: ").strip()
            except (EOFError, OSError):
                event_name = "Untitled Event"
            if not event_name:
                print("Event name cannot be empty.")
                return

        # Gather remaining event details
        description = input("Description: ").strip()
        event_date = input("Event date (YYYY-MM-DD): ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        location = input("Location: ").strip()

        try:
            max_attendees = int(input("Maximum attendees (0 for unlimited): ").strip())
        except ValueError:
            max_attendees = 0

        try:
            ticket_price = float(input("Ticket price (£, 0 for free): ").strip())
        except ValueError:
            ticket_price = 0.0

        category = input("Category: ").strip()

        # Use first club for simplicity
        club_id = clubs[0][0]

        cursor.execute('''
            INSERT INTO unified_events (
                title, description, event_date, start_time, location, organizer_id, event_category, max_capacity, status, source_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', 'union')
        ''', (event_name, description, event_date, start_time,
              location, club_id, category, max_attendees))

        conn.commit()
        print(f"Event '{event_name}' created successfully!")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
