"""
Campus Events Hub Core Service

Event management, registrations, calendar subscriptions,
and event analytics for campus activities.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.feature_gui_factory import create_gui_launcher


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
            raise Exception(f"Error creating event: {e}")

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
                           (SELECT COUNT(*) FROM event_registrations WHERE event_id = ?) as current_count
                    FROM campus_events
                    WHERE event_id = ?
                ''', (event_id, event_id))
                event = cursor.fetchone()

                if event and event['capacity'] > 0 and event['current_count'] >= event['capacity']:
                    raise Exception("Event is at full capacity")

                cursor = conn.execute('''
                    INSERT INTO event_registrations (event_id, user_id, user_type)
                    VALUES (?, ?, ?)
                ''', (event_id, user_id, user_type))
                return cursor.lastrowid
        except Exception as e:
            raise Exception(f"Error registering for event: {e}")

    @staticmethod
    def check_in_attendee(registration_id: int) -> bool:
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE event_registrations
                    SET attendance_status = 'attended',
                        checked_in_at = ?
                    WHERE registration_id = ?
                ''', (datetime.now().isoformat(), registration_id))
                return True
        except Exception as e:
            raise Exception(f"Error checking in attendee: {e}")


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
            raise Exception(f"Error creating event series: {e}")


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
                    raise Exception(f"Event {event_id} not found")

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
            raise Exception(f"Error sending announcement: {e}")

    @staticmethod
    def _send_announcement_emails(conn, event_id: int, event_name: str,
                                 event_date: str, event_time: str,
                                 event_location: str, announcement_text: str,
                                 sent_to: str):
        """Send announcement emails to registered users"""
        try:
            from university_system.infrastructure.email.email_service import queue_email

            recipient_emails = []

            if sent_to == 'all_registrants':
                # Get emails of all registered users for this event
                cursor = conn.execute('''
                    SELECT DISTINCT user_id, user_type
                    FROM event_registrations
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

            # Compose email
            subject = f"Event Announcement: {event_name}"
            body = f"""Dear Participant,

We have an important announcement regarding the upcoming event:

Event: {event_name}
Date: {event_date}
Time: {event_time}
Location: {event_location}

Announcement:
{announcement_text}

If you have any questions, please contact the event organizer.

Best regards,
Campus Events Team
"""

            # Queue emails for all recipients
            for email in recipient_emails:
                queue_email(email, subject, body)

            print(f"✅ Queued announcement emails to {len(recipient_emails)} recipient(s)")

        except Exception as e:
            print(f"⚠️  Warning: Failed to send announcement emails: {e}")

    @staticmethod
    def _get_user_email(conn, user_id: str, user_type: str) -> Optional[str]:
        """Get email address for a user based on their type"""
        try:
            if user_type == 'student':
                result = conn.execute(
                    'SELECT email FROM students WHERE student_id = ?',
                    (user_id,)
                ).fetchone()
            elif user_type == 'staff':
                result = conn.execute(
                    'SELECT email FROM staff WHERE staff_id = ?',
                    (user_id,)
                ).fetchone()
            elif user_type == 'faculty':
                result = conn.execute(
                    'SELECT email FROM faculty WHERE faculty_id = ?',
                    (user_id,)
                ).fetchone()
            else:
                # For guest or other types, user_id might be an email
                if '@' in user_id:
                    return user_id
                return None

            return result['email'] if result else None

        except Exception as e:
            print(f"⚠️  Warning: Could not get email for {user_type} {user_id}: {e}")
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
            raise Exception(f"Error adding sponsor: {e}")


def display_campus_events_menu(auth):
    """Display the Campus Events Hub CLI menu"""
    print("\n" + "="*50)
    print("        CAMPUS EVENTS HUB")
    print("="*50)
    print("1. Browse Events")
    print("2. Create New Event")
    print("3. Event Registration")
    print("4. Recurring Events")
    print("5. Event Announcements")
    print("6. Sponsorship Management")
    print("7. Calendar Subscriptions")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🎉 Feature available via Campus Events managers")
                print("Use: from university_system.modules.domain.campus.services import CampusEventManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# Use factory to create GUI launcher
launch_campus_events_gui = create_gui_launcher(
    title="Campus Events Hub",
    description="""Manage campus events, registrations, and announcements.

Features:
• Event management
• Event registration
• Recurring events
• Event announcements
• Sponsorship tracking
• Calendar subscriptions""",
    cli_instruction="Use CLI: Campus Events Hub"
)



__all__ = [
    'CampusEventManager', 'EventRegistrationManager', 'EventSeriesManager',
    'EventAnnouncementManager', 'EventSponsorManager',
    'display_campus_events_menu',
    'launch_campus_events_gui',
]
