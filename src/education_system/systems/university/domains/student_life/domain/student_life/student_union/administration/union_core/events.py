"""Student Union events: browse, register, create, update, cancel (with registrant e-mails).

Split out of ``student_union_core.py``, which re-exports every name here;
callers keep importing from ``student_union_core``.
"""

from datetime import datetime

from education_system.systems.university.domains.student_life.domain.student_life.student_union.calendar_bridge import mirror as _mirror_to_calendar
from education_system.systems.university.infrastructure.database.db import get_connection

from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.union_core.common import (
    _club_current_student,
    get_current_user,
    logger,
    _send_club_email,
)


EVENT_CANCELLED_TEMPLATE = "student_life/student_union/event_cancelled"
EVENT_UPDATED_TEMPLATE = "student_life/student_union/event_updated"


# ---------------------------------------------------------------------------
# Event helpers
# ---------------------------------------------------------------------------

EVENT_REGISTERED_TEMPLATE = "student_life/student_union/event_registration_confirmation"


def _pick_event(cursor, prompt="Select an event", statuses=("upcoming",)):
    """Show the events and let the operator pick one by number.

    Returns the chosen row, or None. Typing a raw event_id was the source of
    the "FOREIGN KEY constraint failed" on registration: any id that did not
    exist in unified_events failed the foreign key, and the error surfaced
    with no hint that the id was simply wrong.
    """
    if statuses:
        placeholders = ','.join('?' * len(statuses))
        # db-audit: ignore[DBW001] - join of placeholders
        cursor.execute(
            "SELECT event_id, title, start_datetime, location, max_capacity, status"
            " FROM unified_events"
            f" WHERE COALESCE(status, 'upcoming') IN ({placeholders})"
            " ORDER BY start_datetime", tuple(statuses))
    else:
        cursor.execute(
            "SELECT event_id, title, start_datetime, location, max_capacity, status"
            " FROM unified_events ORDER BY start_datetime")
    events = cursor.fetchall()
    if not events:
        print("There are no events to choose from.")
        return None

    print(f"\n{prompt}:")
    for index, (eid, title, start, location, capacity, status) in enumerate(events, 1):
        cursor.execute(
            "SELECT COUNT(*) FROM unified_event_registrations WHERE event_id = ?", (eid,))
        taken = cursor.fetchone()[0]
        places = f"{taken}/{capacity}" if capacity else f"{taken} registered"
        print(f"{index}. {title}")
        print(f"     {start or 'date TBC'} · {location or 'location TBC'} · "
              f"{places} · {status or 'upcoming'}")

    while True:
        raw = input(f"\nSelect an event (1-{len(events)}, blank to cancel): ").strip()
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(events):
            return events[int(raw) - 1]
        print(f"Please enter a number between 1 and {len(events)}.")


def _event_registrants(cursor, event_id, exclude_student=None):
    """Everyone registered for an event, with their contact details."""
    cursor.execute('''
        SELECT r.user_id, s.first_name, s.last_name, s.email_address
        FROM unified_event_registrations r
        LEFT JOIN students s ON r.user_id = s.student_id
        WHERE r.event_id = ?
    ''', (event_id,))
    people = []
    for uid, first, last, email in cursor.fetchall():
        if exclude_student and uid == exclude_student:
            continue
        people.append({
            'student_id': uid,
            'name': f"{first or ''} {last or ''}".strip() or uid,
            'email': email,
        })
    return people


def _notify_registrants(people, template, base_vars, label):
    """Email each registrant, reporting sends, failures and missing addresses."""
    if not people:
        print(f"{label}: nobody is registered, so no email was sent.")
        return
    sent = failed = no_address = 0
    for person in people:
        if not (person['email'] or '').strip():
            no_address += 1
            continue
        template_vars = dict(base_vars)
        template_vars['student_name'] = person['name']
        template_vars['username'] = person['name']
        if _send_club_email(template, person['email'], template_vars):
            sent += 1
        else:
            failed += 1
    summary = f"{label}: {sent} sent"
    if failed:
        summary += f", {failed} failed"
    if no_address:
        summary += f", {no_address} with no address on file"
    print(summary + ".")


def view_events():
    """View all upcoming events"""
    print("\n=== Upcoming Events ===")
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT,
                source_event_id TEXT,
                title TEXT,
                description TEXT,
                event_type TEXT,
                event_category TEXT,
                start_datetime TEXT,
                end_datetime TEXT,
                location TEXT,
                building TEXT,
                room TEXT,
                room_id TEXT,
                organizer_id TEXT,
                organizer_name TEXT,
                organizer_type TEXT,
                max_capacity INTEGER,
                registration_required BOOLEAN,
                registration_deadline TEXT,
                is_public BOOLEAN,
                is_featured BOOLEAN,
                status TEXT,
                tags TEXT,
                image_url TEXT,
                virtual_link TEXT,
                event_fee REAL DEFAULT 0.0,
                payment_required BOOLEAN DEFAULT 0,
                waitlist_enabled BOOLEAN DEFAULT 1,
                qr_code_path TEXT,
                club_id TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT,
                notes TEXT
            )
        ''')

        cursor.execute('''
            SELECT event_id, title, description, start_datetime, location, max_capacity
            FROM unified_events
            WHERE status = 'upcoming'
            ORDER BY start_datetime
        ''')

        events = cursor.fetchall()
        if not events:
            print("No upcoming events.")
            return

        for event_id, name, desc, date, location, capacity in events:
            print(f"\n{event_id}. {name}")
            print(f"   Date: {date}")
            print(f"   Location: {location}")
            if desc:
                print(f"   {desc}")

    except Exception as e:
        print(f"Error viewing events: {e}")
    finally:
        if conn:
            conn.close()

def register_for_event():
    """Register the signed-in student for an event they pick from a list."""
    print("\n=== Register for Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unified_event_registrations (
                registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                user_id TEXT,
                user_type TEXT DEFAULT 'student',
                registration_date TEXT,
                attendance_status TEXT,
                checked_in_at TEXT,
                check_out_time TEXT,
                payment_status TEXT,
                payment_amount REAL DEFAULT 0.0,
                payment_method TEXT,
                is_waitlisted BOOLEAN DEFAULT 0,
                num_guests INTEGER DEFAULT 0,
                feedback_rating REAL,
                feedback_comment TEXT,
                qr_code TEXT,
                cpd_credits REAL DEFAULT 0.0,
                FOREIGN KEY (event_id) REFERENCES unified_events (event_id)
            )
        ''')

        # Identify the student from the session rather than asking them to
        # type an id they may not know — and which let anyone register anyone.
        student_id, student_name, student_email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to register for an event.")
            return
        print(f"Registering as: {student_name} ({student_id})")

        event = _pick_event(cursor, "Events open for registration")
        if not event:
            print("Registration cancelled.")
            return
        event_id, title, start_datetime, location, capacity, _status = event

        # Already registered?
        cursor.execute(
            "SELECT 1 FROM unified_event_registrations"
            " WHERE event_id = ? AND user_id = ? LIMIT 1", (event_id, student_id))
        if cursor.fetchone():
            print(f"You are already registered for {title}.")
            return

        # Respect the capacity rather than overbooking silently.
        if capacity:
            cursor.execute(
                "SELECT COUNT(*) FROM unified_event_registrations WHERE event_id = ?",
                (event_id,))
            if cursor.fetchone()[0] >= capacity:
                print(f"'{title}' is full ({capacity} places). "
                      "Contact the Students' Union about the waiting list.")
                return

        cursor.execute('INSERT INTO unified_event_registrations (event_id, user_id, user_type, registration_date) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
                      (event_id, student_id, 'student'))
        conn.commit()
        print(f"✓ Successfully registered for {title}!")

        event_date, _, event_time = (start_datetime or '').partition(' ')
        if _send_club_email(EVENT_REGISTERED_TEMPLATE, student_email, {
                'username': student_name or 'Student',
                'student_name': student_name or 'Student',
                'event_name': title,
                'event_date': event_date or 'To be confirmed',
                'event_time': event_time or 'To be confirmed',
                'location': location or 'To be confirmed'}):
            print(f"📧 Confirmation emailed to {student_email}.")
        elif student_email:
            print("Note: the confirmation email could not be sent.")
        else:
            print("No email address on file, so no confirmation was sent.")

    except Exception as e:
        print(f"Error registering: {e}")
    finally:
        if conn:
            conn.close()

def view_my_events():
    """View the signed-in student's event registrations."""
    print("\n=== My Events ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        student_id, student_name, _email = _club_current_student(conn)
        if not student_id:
            print("You must be signed in as a student to view your registrations.")
            return
        print(f"Registrations for {student_name} ({student_id}):")

        cursor.execute('''
            SELECT e.title, e.start_datetime, e.location
            FROM unified_event_registrations r
            JOIN unified_events e ON r.event_id = e.event_id
            WHERE r.user_id = ? AND r.user_type = 'student'
            ORDER BY e.start_datetime
        ''', (student_id,))

        events = cursor.fetchall()
        if not events:
            print("No registered events.")
            return

        for name, date, location in events:
            print(f"\n• {name}")
            print(f"  Date: {date} | Location: {location}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

def create_event():
    """Create a new Students' Union event."""
    print("\n=== Create Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        title = input("Event title (blank to cancel): ").strip()
        if not title:
            print("Event creation cancelled.")
            return

        cursor.execute(
            "SELECT 1 FROM unified_events WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))"
            " AND COALESCE(status,'upcoming') = 'upcoming' LIMIT 1", (title,))
        if cursor.fetchone():
            if input(f"An upcoming event called '{title}' already exists. "
                     "Create another with the same name? (y/n): ").strip().lower() != 'y':
                print("Event creation cancelled.")
                return

        description = input("Description: ").strip()

        start_datetime = None
        while start_datetime is None:
            raw = input("Start (YYYY-MM-DD HH:MM, blank to cancel): ").strip()
            if not raw:
                print("Event creation cancelled.")
                return
            try:
                datetime.strptime(raw, '%Y-%m-%d %H:%M')
                start_datetime = raw
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        end_datetime = None
        while end_datetime is None:
            raw = input("End (YYYY-MM-DD HH:MM, blank for none): ").strip()
            if not raw:
                break
            try:
                if datetime.strptime(raw, '%Y-%m-%d %H:%M') <= datetime.strptime(
                        start_datetime, '%Y-%m-%d %H:%M'):
                    print("The end must be after the start.")
                    continue
                end_datetime = raw
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        location = input("Location: ").strip()

        capacity = None
        while True:
            raw = input("Maximum capacity (blank for unlimited): ").strip()
            if not raw:
                break
            if raw.isdigit() and int(raw) > 0:
                capacity = int(raw)
                break
            print("Please enter a whole number greater than 0, or leave blank.")

        organizer = "Students' Union"
        try:
            user = get_current_user()
            if user:
                organizer = user.get('username', organizer)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO unified_events
            (source_type, title, description, start_datetime, end_datetime,
             location, max_capacity, organizer_name, registration_required,
             is_public, status, created_by, created_at, updated_at)
            VALUES ('student_union', ?, ?, ?, ?, ?, ?, ?, 1, 1, 'upcoming', ?, ?, ?)
        ''', (title, description or None, start_datetime, end_datetime,
              location or None, capacity, organizer, organizer, now, now))
        conn.commit()
        event_row_id = cursor.lastrowid
        print(f"\n✓ Event '{title}' created (ID {event_row_id}).")

        if _mirror_to_calendar(
            name=f"SU Event: {title}", kind="event",
            date_start=start_datetime, date_end=end_datetime,
            description=description or None, location=location or None,
            organizer=organizer, created_by=organizer,
            source_table="unified_events", source_id=event_row_id,
            conn=conn,
        ):
            print("  Added to the university academic calendar.")

    except Exception as e:
        print(f"Error creating event: {e}")
    finally:
        if conn:
            conn.close()


def update_event():
    """Update an event and tell everyone registered what changed."""
    print("\n=== Update Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_event(cursor, "Select the event to update", statuses=None)
        if not chosen:
            print("Update cancelled.")
            return
        event_id = chosen[0]

        cursor.execute('''
            SELECT title, description, start_datetime, end_datetime, location,
                   max_capacity, status, organizer_name
            FROM unified_events WHERE event_id = ?
        ''', (event_id,))
        row = cursor.fetchone()
        if not row:
            print("Event not found.")
            return
        (title, description, start_datetime, end_datetime, location,
         capacity, status, organizer) = row

        print("\nLeave a field blank to keep its current value.")
        new_title = input(f"Title [{title}]: ").strip() or title
        new_description = input(f"Description [{description or 'none'}]: ").strip() or description

        new_start = start_datetime
        while True:
            raw = input(f"Start YYYY-MM-DD HH:MM [{start_datetime or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d %H:%M')
                new_start = raw
                break
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        new_end = end_datetime
        while True:
            raw = input(f"End YYYY-MM-DD HH:MM [{end_datetime or 'not set'}]: ").strip()
            if not raw:
                break
            try:
                datetime.strptime(raw, '%Y-%m-%d %H:%M')
                new_end = raw
                break
            except ValueError:
                print("Invalid format. Please use YYYY-MM-DD HH:MM.")

        new_location = input(f"Location [{location or 'none'}]: ").strip() or location

        new_capacity = capacity
        while True:
            raw = input(f"Capacity [{capacity if capacity else 'unlimited'}]: ").strip()
            if not raw:
                break
            if raw.isdigit() and int(raw) > 0:
                new_capacity = int(raw)
                break
            print("Please enter a whole number greater than 0, or leave blank.")

        new_status = input(f"Status [{status or 'upcoming'}]: ").strip() or status

        changes = [(label, old, new) for label, old, new in (
            ("Title", title, new_title),
            ("Description", description, new_description),
            ("Start", start_datetime, new_start),
            ("End", end_datetime, new_end),
            ("Location", location, new_location),
            ("Capacity", capacity, new_capacity),
            ("Status", status, new_status),
        ) if (old if old is not None else '') != (new if new is not None else '')]

        if not changes:
            print("\nNothing was changed.")
            return

        registrants = _event_registrants(cursor, event_id)
        print("\nAbout to apply these changes:")
        for label, old, new in changes:
            print(f"  - {label}: '{old if old not in (None, '') else 'not set'}' "
                  f"-> '{new if new not in (None, '') else 'not set'}'")
        print(f"\n{len(registrants)} person(s) registered will be emailed this list.")

        if input("\nApply these changes? (y/n): ").strip().lower() != 'y':
            print("Update cancelled. Nothing has been changed.")
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE unified_events
            SET title = ?, description = ?, start_datetime = ?, end_datetime = ?,
                location = ?, max_capacity = ?, status = ?, updated_at = ?
            WHERE event_id = ?
        ''', (new_title, new_description, new_start, new_end, new_location,
              new_capacity, new_status, now, event_id))
        conn.commit()
        print(f"\n✓ Event {event_id} updated ({len(changes)} change(s)).")

        updated_by = "the Students' Union"
        try:
            user = get_current_user()
            if user:
                updated_by = user.get('username', updated_by)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        change_list = "\n".join(
            f"  - {label}: '{old if old not in (None, '') else 'not set'}' "
            f"-> '{new if new not in (None, '') else 'not set'}'"
            for label, old, new in changes)

        _notify_registrants(registrants, EVENT_UPDATED_TEMPLATE, {
            'event_name': new_title,
            'change_list': change_list,
            'start_datetime': new_start or 'Not specified',
            'end_datetime': new_end or 'Not specified',
            'location': new_location or 'To be confirmed',
            'organizer_name': organizer or "Students' Union",
            'status': new_status or 'upcoming',
            'description': new_description or 'No description provided.',
            'updated_at': now,
            'updated_by': updated_by,
        }, "Change notices")

    except Exception as e:
        print(f"Error updating event: {e}")
    finally:
        if conn:
            conn.close()


def delete_event():
    """Cancel an event, telling everyone registered."""
    print("\n=== Delete Event ===")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        chosen = _pick_event(cursor, "Select the event to delete", statuses=None)
        if not chosen:
            print("Deletion cancelled.")
            return
        event_id, title, start_datetime, location, _capacity, _status = chosen

        cursor.execute("SELECT organizer_name FROM unified_events WHERE event_id = ?",
                       (event_id,))
        row = cursor.fetchone()
        organizer = row[0] if row else "Students' Union"

        registrants = _event_registrants(cursor, event_id)
        print(f"\nAbout to delete '{title}' ({start_datetime or 'date TBC'}).")
        if registrants:
            reachable = sum(1 for r in registrants if (r['email'] or '').strip())
            print(f"{len(registrants)} person(s) registered; {reachable} can be emailed.")
            for person in registrants[:10]:
                mark = '' if (person['email'] or '').strip() else '  (no email on file)'
                print(f"  • {person['name']} ({person['student_id']}){mark}")
            if len(registrants) > 10:
                print(f"  … and {len(registrants) - 10} more")
        else:
            print("Nobody is registered.")

        if input("\nDelete this event? (yes/no): ").strip().lower() != 'yes':
            print("Deletion cancelled. Nothing has been changed.")
            return

        reason = input("Reason for cancelling (shown to attendees, optional): ").strip()

        cancelled_by = "the Students' Union"
        try:
            user = get_current_user()
            if user:
                cancelled_by = user.get('username', cancelled_by)
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        cursor.execute("DELETE FROM unified_event_registrations WHERE event_id = ?",
                       (event_id,))
        cursor.execute("DELETE FROM unified_events WHERE event_id = ?", (event_id,))
        conn.commit()
        print(f"\n✓ Event '{title}' deleted.")

        _notify_registrants(registrants, EVENT_CANCELLED_TEMPLATE, {
            'event_name': title,
            'start_datetime': start_datetime or 'Not specified',
            'location': location or 'Not specified',
            'organizer_name': organizer or "Students' Union",
            'cancelled_date': datetime.now().strftime('%Y-%m-%d'),
            'cancelled_by': cancelled_by,
            'reason': reason or 'No reason was recorded.',
        }, "Cancellation notices")

    except Exception as e:
        print(f"Error deleting event: {e}")
    finally:
        if conn:
            conn.close()
