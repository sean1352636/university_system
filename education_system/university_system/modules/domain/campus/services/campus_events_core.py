"""
Campus Events Hub Core Service

Event management, registrations, calendar subscriptions,
and event analytics for campus activities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.modules.shared.utils.i18n import get_text


class CampusEventManager:
    """Manages campus events"""

    @staticmethod
    def create_event(event_name: str, event_type: str, event_category: str,
                    organizer_id: str, organizer_type: str, event_date: str,
                    start_time: str, end_time: str, location: str = "",
                    capacity: int = 0, registration_required: bool = False,
                    is_public: bool = True, description: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO campus_events (
                        event_name, event_type, event_category, organizer_id,
                        organizer_type, event_date, start_time, end_time,
                        location, capacity, registration_required, is_public, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (event_name, event_type, event_category, organizer_id,
                      organizer_type, event_date, start_time, end_time,
                      location, capacity, registration_required, is_public, description))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(get_text("campus.events.errors.create_event", "Error creating event: {error}").format(error=e))

    @staticmethod
    def get_upcoming_events(days_ahead: int = 30, event_category: str = "") -> List[Dict[str, Any]]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if event_category:
                cursor.execute('''
                    SELECT * FROM campus_events
                    WHERE event_date >= DATE('now')
                      AND event_date <= DATE('now', '+' || ? || ' days')
                      AND event_category = ?
                      AND status = 'scheduled'
                    ORDER BY event_date, start_time
                ''', (days_ahead, event_category))
            else:
                cursor.execute('''
                    SELECT * FROM campus_events
                    WHERE event_date >= DATE('now')
                      AND event_date <= DATE('now', '+' || ? || ' days')
                      AND status = 'scheduled'
                    ORDER BY event_date, start_time
                ''', (days_ahead,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


class EventRegistrationManager:
    """Manages event registrations"""

    @staticmethod
    def register_for_event(event_id: int, user_id: str, user_type: str) -> int:
        try:
            with transaction() as conn:
                # Check capacity
                cursor = conn.execute('''
                    SELECT capacity,
                           (SELECT COUNT(*) FROM campus_event_registrations WHERE event_id = ?) as current_count
                    FROM campus_events
                    WHERE event_id = ?
                ''', (event_id, event_id))
                event = cursor.fetchone()

                if event and event['capacity'] > 0 and event['current_count'] >= event['capacity']:
                    raise Exception(get_text("campus.events.errors.full_capacity", "Event is at full capacity"))

                cursor = conn.execute('''
                    INSERT INTO campus_event_registrations (event_id, user_id, user_type)
                    VALUES (?, ?, ?)
                ''', (event_id, user_id, user_type))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(get_text("campus.events.errors.register_event", "Error registering for event: {error}").format(error=e))

    @staticmethod
    def check_in_attendee(registration_id: int) -> bool:
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE campus_event_registrations
                    SET attendance_status = 'attended',
                        checked_in_at = ?
                    WHERE registration_id = ?
                ''', (datetime.now().isoformat(), registration_id))
                return True
        except Exception as e:
            raise Exception(get_text("campus.events.errors.check_in_attendee", "Error checking in attendee: {error}").format(error=e))


class EventSeriesManager:
    """Manages recurring event series"""

    @staticmethod
    def create_series(series_name: str, organizer_id: str,
                     recurrence_pattern: str, start_date: str,
                     end_date: str = "", description: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO event_series (
                        series_name, organizer_id, recurrence_pattern,
                        start_date, end_date, series_description
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (series_name, organizer_id, recurrence_pattern,
                      start_date, end_date, description))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(get_text("campus.events.errors.create_series", "Error creating event series: {error}").format(error=e))


class EventAnnouncementManager:
    """Manages event announcements"""

    @staticmethod
    def send_announcement(event_id: int, announcement_text: str,
                         sent_to: str, sent_by: str = "") -> int:
        try:
            with transaction() as conn:
                # Insert announcement record
                cursor = conn.execute('''
                    INSERT INTO event_announcements (
                        event_id, announcement_text, sent_to, sent_by
                    ) VALUES (?, ?, ?, ?)
                ''', (event_id, announcement_text, sent_to, sent_by))
                announcement_id = cursor.lastrowid

                # Get event details
                event = conn.execute('''
                    SELECT event_name, event_date, start_time, location
                    FROM campus_events
                    WHERE event_id = ?
                ''', (event_id,)).fetchone()

                if not event:
                    raise Exception(get_text("campus.events.errors.event_not_found", "Event {event_id} not found").format(event_id=event_id))

                event_name = event['event_name']
                event_date = event['event_date']
                event_time = event['start_time']
                event_location = event['location'] or 'TBA'

                # Send emails to recipients
                EventAnnouncementManager._send_announcement_emails(
                    conn, event_id, event_name, event_date, event_time,
                    event_location, announcement_text, sent_to
                )

                return announcement_id
        except Exception as e:
            raise Exception(get_text("campus.events.errors.send_announcement", "Error sending announcement: {error}").format(error=e))

    @staticmethod
    def _send_announcement_emails(conn, event_id: int, event_name: str,
                                 event_date: str, event_time: str,
                                 event_location: str, announcement_text: str,
                                 sent_to: str):
        """Send announcement emails to registered users"""
        try:
            from education_system.university_system.infrastructure.email.email_service import queue_email

            recipient_emails = []
            failed_lookups = []

            if sent_to == 'all_registrants':
                # Get emails of all registered users for this event
                cursor = conn.execute('''
                    SELECT DISTINCT user_id, user_type
                    FROM campus_event_registrations
                    WHERE event_id = ?
                ''', (event_id,))
                registrants = cursor.fetchall()

                # Get email addresses based on user type
                for reg in registrants:
                    user_id = reg['user_id']
                    user_type = reg['user_type']

                    email = EventAnnouncementManager._get_user_email(conn, user_id, user_type)
                    if email:
                        recipient_emails.append(email)
                        print(f"✓ Found email for {user_type} {user_id}: {email}")
                    else:
                        failed_lookups.append(f"{user_type} {user_id}")
                        print(f"✗ Could not find email for {user_type} {user_id}")

            # Compose email using template
            subject, body = render_template('campus_event_announcement', {
                'event_name': event_name,
                'event_date': event_date,
                'event_time': event_time,
                'event_location': event_location,
                'announcement_text': announcement_text
            })

            # Send emails immediately to all recipients
            successful_sends = 0
            failed_sends = []

            for email in recipient_emails:
                try:
                    result = queue_email(email, subject, body)
                    if result:
                        successful_sends += 1
                        print(f"✓ Email sent to inbox: {email}")
                    else:
                        failed_sends.append(email)
                        print(f"✗ Failed to send to: {email}")
                except Exception as e:
                    failed_sends.append(email)
                    print(f"✗ Error sending to {email}: {e}")

            # Print summary
            print(f"\n📧 Email Summary:")
            print(f"   ✓ Sent to {successful_sends} inbox(es)")
            if failed_sends:
                print(f"   ✗ Failed: {len(failed_sends)} ({', '.join(failed_sends)})")
            if failed_lookups:
                print(f"   ⚠ Email lookup failed: {len(failed_lookups)} ({', '.join(failed_lookups)})")

        except Exception as e:
            print(get_text("campus.events.warnings.announcement_emails_failed", "Warning: Failed to send announcement emails: {error}").format(error=e))

    @staticmethod
    def _get_user_email(conn, user_id: str, user_type: str) -> Optional[str]:
        """Get email address for a user based on their type"""
        try:
            # First try to get email from the users table (most reliable)
            result = conn.execute(
                'SELECT email FROM users WHERE username = ? OR student_id = ?',
                (user_id, user_id)
            ).fetchone()

            if result and result['email']:
                return result['email']

            # Fallback to type-specific tables
            if user_type == 'student':
                result = conn.execute(
                    'SELECT email_address FROM students WHERE student_id = ?',
                    (user_id,)
                ).fetchone()
                return result['email_address'] if result else None
            elif user_type == 'staff':
                result = conn.execute(
                    'SELECT email FROM staff WHERE staff_id = ?',
                    (user_id,)
                ).fetchone()
                return result['email'] if result else None
            elif user_type == 'faculty':
                result = conn.execute(
                    'SELECT email FROM faculty WHERE faculty_id = ?',
                    (user_id,)
                ).fetchone()
                return result['email'] if result else None
            else:
                # For guest or other types, user_id might be an email
                if '@' in user_id:
                    return user_id
                return None

        except Exception as e:
            print(get_text("campus.events.warnings.get_email_failed", "Warning: Could not get email for {user_type} {user_id}: {error}").format(user_type=user_type, user_id=user_id, error=e))
            return None


class EventSponsorManager:
    """Manages event sponsorships"""

    @staticmethod
    def add_sponsor(event_id: int, sponsor_name: str,
                   sponsor_type: str = "", contribution_amount: float = 0,
                   logo_url: str = "", website_url: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO event_sponsors (
                        event_id, sponsor_name, sponsor_type,
                        contribution_amount, logo_url, website_url
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (event_id, sponsor_name, sponsor_type,
                      contribution_amount, logo_url, website_url))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(get_text("campus.events.errors.add_sponsor", "Error adding sponsor: {error}").format(error=e))


def display_campus_events_menu(auth):
    """Display the Campus Events Hub CLI menu"""
    print("\n" + "="*50)
    print("        " + get_text("campus.events.menu.title", "CAMPUS EVENTS HUB"))
    print("="*50)
    print("1. " + get_text("campus.events.menu.browse_events", "Browse Events"))
    print("2. " + get_text("campus.events.menu.create_event", "Create New Event"))
    print("3. " + get_text("campus.events.menu.registration", "Event Registration"))
    print("4. " + get_text("campus.events.menu.recurring_events", "Recurring Events"))
    print("5. " + get_text("campus.events.menu.announcements", "Event Announcements"))
    print("6. " + get_text("campus.events.menu.sponsorship", "Sponsorship Management"))
    print("7. " + get_text("campus.events.menu.calendar", "Calendar Subscriptions"))
    print("8. " + get_text("campus.events.menu.return", "Return to Main Menu"))
    print("="*50)

    while True:
        try:
            choice = input("\n" + get_text("campus.events.menu.prompt", "Enter your choice (1-8): ")).strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print("\n" + get_text("campus.events.menu.feature_available", "Feature available via Campus Events managers"))
                print(get_text("campus.events.menu.use_instruction", "Use: from education_system.university_system.modules.domain.campus.services import CampusEventManager"))
            elif choice == '8':
                break
            else:
                print(get_text("campus.events.menu.invalid_choice", "Invalid choice."))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(get_text("campus.events.menu.error", "Error: {error}").format(error=e))


# Use factory to create GUI launcher
launch_campus_events_gui = create_gui_launcher(
    title=get_text("campus.events.gui.title", "Campus Events Hub"),
    description=get_text("campus.events.gui.description", """Manage campus events, registrations, and announcements.

Features:
- Event management
- Event registration
- Recurring events
- Event announcements
- Sponsorship tracking
- Calendar subscriptions"""),
    cli_instruction=get_text("campus.events.gui.cli_instruction", "Use CLI: Campus Events Hub")
)



__all__ = [
    'CampusEventManager', 'EventRegistrationManager', 'EventSeriesManager',
    'EventAnnouncementManager', 'EventSponsorManager',
    'display_campus_events_menu',
    'launch_campus_events_gui',
]
