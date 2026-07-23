"""
Event Discovery Engine Service Layer

Provides comprehensive event management with personalized recommendations,
RSVP system, attendance tracking, calendar integration, and social features.

Uses the unified_events table (source_type='campus') shared with Campus Events Hub.

Features:
- Personalized event recommendations based on interests and attendance history
- Friends' event attendance tracking (opt-in social feature)
- Calendar integration with one-click RSVP
- Event reminders and location details
- Event check-in for attendance tracking
- Event photos and recaps
- Multi-category support (Academic, Social, Athletic, Cultural, Career, Community Service)
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.core.sql_safety import escape_like
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import logging

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core import paths
from education_system.post_18.university_system.core.activity_logger import log_activity

logger = logging.getLogger(__name__)

class EventsService:
    """Service for managing university events, RSVPs, and recommendations.

    Uses the unified_events table (source_type='campus'). The discovery_event_* supporting
    tables (rsvps, attendance, interests, photos, ratings, social_settings)
    are created here for the student-facing discovery features.
    """

    # Event categories
    CATEGORIES = [
        'Academic',
        'Social',
        'Athletic',
        'Cultural',
        'Career',
        'Community Service',
        'Other'
    ]

    # RSVP statuses
    RSVP_STATUS = ['Going', 'Interested', 'Not Going']

    def __init__(self):
        """Initialize the events service and create supporting database tables"""
        self.initialize_database()

    def initialize_database(self):
        """Create supporting tables for event discovery features.

        The main unified_events table is created by campus_events_schemas.py.
        This method only creates the discovery-specific supporting tables.
        """
        try:
            with transaction() as conn:
                # RSVPs table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_event_rsvps (
                        rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        rsvp_status TEXT NOT NULL,
                        rsvp_date TEXT DEFAULT CURRENT_TIMESTAMP,
                        added_to_calendar INTEGER DEFAULT 0,
                        reminder_sent INTEGER DEFAULT 0,
                        FOREIGN KEY (event_id) REFERENCES unified_events(event_id),
                        UNIQUE(event_id, user_id)
                    )
                """)

                # Attendance tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_event_attendance (
                        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        check_in_time TEXT NOT NULL,
                        check_out_time TEXT,
                        FOREIGN KEY (event_id) REFERENCES unified_events(event_id),
                        UNIQUE(event_id, user_id)
                    )
                """)

                # User interests/preferences
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_event_interests (
                        interest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        category TEXT NOT NULL,
                        interest_level INTEGER DEFAULT 5,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, category)
                    )
                """)

                # Event photos
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_event_photos (
                        photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        photo_url TEXT NOT NULL,
                        caption TEXT,
                        uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (event_id) REFERENCES unified_events(event_id)
                    )
                """)

                # Event ratings and reviews
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_event_ratings (
                        rating_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                        review TEXT,
                        rated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (event_id) REFERENCES unified_events(event_id),
                        UNIQUE(event_id, user_id)
                    )
                """)

                # Social features - friends who are attending
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_event_social_settings (
                        user_id TEXT PRIMARY KEY,
                        show_attendance_to_friends INTEGER DEFAULT 1,
                        receive_friend_notifications INTEGER DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes for performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_unified_events_date
                    ON unified_events(start_datetime)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_unified_events_category
                    ON unified_events(event_category)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rsvps_user
                    ON discovery_event_rsvps(user_id)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rsvps_event
                    ON discovery_event_rsvps(event_id)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_attendance_user
                    ON discovery_event_attendance(user_id)
                """)

            logger.info("Event Discovery Engine database initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing events database: {e}")
            raise

    # ==================== Helper ====================

    def _make_datetime(self, date_str, time_str):
        """Combine date and time strings into a datetime string."""
        if not date_str:
            return ''
        if not time_str:
            return date_str
        return f"{date_str} {time_str}"

    def _add_to_academic_calendar(self, event_name, event_date, description, event_type, created_by=None):
        """Add an event to the academic calendar automatically on creation."""
        import uuid
        try:
            with transaction() as conn:
                conn.execute('''
                    INSERT INTO academic_calendar_events (
                        id, name, description, event_type,
                        date, created_by, date_added, last_modified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(uuid.uuid4()), event_name, description or '',
                    event_type, event_date, created_by or 'System',
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
        except Exception:
            # Non-critical — don't block event creation if calendar insert fails.
            logger.debug(
                "Calendar mirror insert failed for event '%s'; continuing",
                event_name, exc_info=True)

    def _lookup_user_email(self, user_id):
        """Resolve *user_id* (numeric id, username, or student_id) to ``(name, email)``."""
        try:
            with get_connection() as conn:
                for sql in (
                    "SELECT username, email FROM users WHERE id = ?",
                    "SELECT username, email FROM users WHERE username = ?",
                ):
                    row = conn.execute(sql, (user_id,)).fetchone()
                    if row and row[1]:
                        return (row[0] or str(user_id), row[1])
                row = conn.execute(
                    "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name,"
                    "       COALESCE(email_address,'') AS email"
                    "  FROM students WHERE student_id = ?",
                    (user_id,),
                ).fetchone()
                if row and row[1]:
                    return ((row[0] or '').strip() or str(user_id), row[1])
        except Exception:
            logger.exception("user email lookup failed user_id=%s", user_id)
        return (str(user_id), '')

    def _send_rsvp_confirmation_email(self, user_id, status, event_name,
                                       event_date, start_time, end_time, location,
                                       event_id=None, num_guests=0):
        """Send RSVP confirmation email to user via the events/rsvp_confirmation template."""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service.core import send_email
            from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
            name, email = self._lookup_user_email(user_id)
            if not email:
                logger.info(f"No email found for user {user_id}, skipping RSVP confirmation")
                return
            status_norm = (status or '').lower().replace(' ', '_')
            display_map = {
                'going': "Going",
                'interested': "Interested",
                'not_going': "Not Going",
                'attending': "Going",
                'declined': "Not Going",
            }
            status_message_map = {
                'going':       "You're confirmed for the event. Add it to your calendar so you don't forget.",
                'interested':  "Thanks — we'll keep your seat warm. Flip to 'Going' once you're sure, especially if catering depends on it.",
                'not_going':   "No problem — your seat has been released. Hope to see you at a future event.",
            }
            subject, body = render_template('events/rsvp_confirmation', {
                'recipient_name':       name,
                'event_name':           event_name,
                'event_date':           event_date,
                'start_time':           start_time or 'TBA',
                'end_time':             end_time or 'TBA',
                'location':             location or 'TBA',
                'rsvp_status_display':  display_map.get(status_norm, status or 'Recorded'),
                'num_guests':           num_guests,
                'rsvp_recorded_on':     datetime.now().strftime('%Y-%m-%d %H:%M'),
                'event_id':             event_id if event_id is not None else '(see portal)',
                'status_specific_message': status_message_map.get(status_norm, "Your RSVP has been recorded."),
            })
            if not subject or not body:
                # Defensive fallback so the user still hears back if the template is missing.
                subject = f"RSVP Confirmation: {event_name}"
                body = (f"Dear {name},\n\nYour RSVP ({status}) has been recorded for {event_name} on "
                        f"{event_date} at {location or 'TBA'}.\n\nUniversity Events Team")
            send_email(email, subject, body)
            logger.info(f"RSVP confirmation email sent to {email} for event '{event_name}'")
        except Exception as e:
            logger.warning(f"Could not send RSVP confirmation email: {e}")

    def send_event_invitation(self, event_id: int,
                              recipients: List[Dict[str, str]],
                              dress_code: str = "Smart casual",
                              cost: str = "Free",
                              rsvp_url: str = "(see Events portal)",
                              plus_ones_policy: str = "not permitted unless specified") -> int:
        """Send an invitation email per ``{'name','email'}`` in *recipients*.
        Returns number of emails dispatched."""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service.core import send_email
            from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
        except Exception:
            logger.exception("email infrastructure unavailable")
            return 0
        event = self.get_event(event_id) or {}
        sent = 0
        for r in recipients or []:
            email = (r.get('email') or '').strip()
            if not email:
                continue
            subject, body = render_template('events/event_invitation', {
                'recipient_name':    r.get('name') or 'Guest',
                'event_id':          event_id,
                'event_name':        event.get('event_name') or event.get('title') or 'University Event',
                'event_type':        event.get('event_type', 'Event'),
                'event_date':        event.get('event_date') or event.get('start_datetime', ''),
                'start_time':        event.get('start_time') or '(see portal)',
                'end_time':          event.get('end_time') or '(see portal)',
                'location':          event.get('location') or 'TBA',
                'host_name':         event.get('host_name') or 'University Events Team',
                'dress_code':        dress_code,
                'cost':              cost,
                'capacity':          event.get('max_capacity') or '(open)',
                'rsvp_by':           event.get('rsvp_by') or '(see Events portal)',
                'rsvp_url':          rsvp_url,
                'event_description': event.get('description') or '(no description provided)',
                'plus_ones_policy':  plus_ones_policy,
            })
            if subject and body:
                try:
                    send_email(email, subject, body)
                    sent += 1
                except Exception:
                    logger.exception("event invitation send failed email=%s", email)
        return sent

    def send_event_reminder(self, event_id: int,
                            recipients: List[Dict[str, Any]],
                            when_phrase: str = "tomorrow",
                            travel_note: str = "see the campus travel page",
                            programme_summary: str = "(see Events portal)") -> int:
        """Send an event reminder. Each recipient may include ``rsvp_status`` and
        ``num_guests`` so the reminder reflects their RSVP state."""
        try:
            from education_system.post_18.university_system.infrastructure.email.email_service.core import send_email
            from education_system.post_18.university_system.infrastructure.email.template_utils import render_template
        except Exception:
            logger.exception("email infrastructure unavailable")
            return 0
        event = self.get_event(event_id) or {}
        sent = 0
        for r in recipients or []:
            email = (r.get('email') or '').strip()
            if not email:
                continue
            subject, body = render_template('events/event_reminder', {
                'recipient_name':       r.get('name') or 'Guest',
                'event_id':             event_id,
                'event_name':           event.get('event_name') or event.get('title') or 'University Event',
                'event_date':           event.get('event_date') or event.get('start_datetime', ''),
                'start_time':           event.get('start_time') or '(see portal)',
                'end_time':             event.get('end_time') or '(see portal)',
                'location':             event.get('location') or 'TBA',
                'host_name':            event.get('host_name') or 'University Events Team',
                'rsvp_status_display':  r.get('rsvp_status') or 'Going',
                'num_guests':           r.get('num_guests', 0),
                'when_phrase':          when_phrase,
                'travel_note':          travel_note,
                'programme_summary':    programme_summary,
            })
            if subject and body:
                try:
                    send_email(email, subject, body)
                    sent += 1
                except Exception:
                    logger.exception("event reminder send failed email=%s", email)
        return sent

    def _row_to_event(self, columns, row):
        """Convert a unified_events row to an event dict with discovery-compatible keys."""
        event = dict(zip(columns, row))
        # Add compatibility aliases used by the discovery GUI
        event['event_name'] = event.get('title', '')
        event['category'] = event.get('event_category', '')
        # Derive event_date, start_time, end_time from start_datetime / end_datetime
        sd = event.get('start_datetime', '')
        ed = event.get('end_datetime', '')
        if sd and ' ' in str(sd):
            event['event_date'] = str(sd).split(' ', 1)[0]
            event['start_time'] = str(sd).split(' ', 1)[1]
        else:
            event['event_date'] = str(sd) if sd else ''
            event['start_time'] = ''
        if ed and ' ' in str(ed):
            event['end_time'] = str(ed).split(' ', 1)[1]
        else:
            event['end_time'] = ''
        event['capacity'] = event.get('max_capacity', 0)
        event['event_image_url'] = event.get('image_url', '')
        event['room'] = event.get('room_id', '')
        event['cancelled'] = 1 if event.get('status') == 'cancelled' else 0
        # Parse tags
        if event.get('tags'):
            try:
                event['tags'] = json.loads(event['tags'])
            except (json.JSONDecodeError, TypeError):
                event['tags'] = []
        else:
            event['tags'] = []
        return event

    # ==================== Event Management ====================

    def create_event(self, event_data: Dict[str, Any], user_id: str) -> int:
        """
        Create a new event in the unified_events table (source_type='campus').

        Args:
            event_data: Dictionary containing event details
            user_id: ID of the user creating the event

        Returns:
            event_id of the created event
        """
        try:
            # Parse start/end datetime into date + time if provided as single values
            start_dt = event_data.get('start_datetime', '')
            end_dt = event_data.get('end_datetime', '')

            # Build start_datetime and end_datetime from whatever input we have
            if start_dt and ' ' in start_dt:
                event_date, start_time = start_dt.split(' ', 1)
            else:
                event_date = event_data.get('event_date', start_dt)
                start_time = event_data.get('start_time', '')

            if end_dt and ' ' in end_dt:
                _, end_time = end_dt.split(' ', 1)
            else:
                end_time = event_data.get('end_time', '')

            # Compose full datetime strings for the schema columns
            full_start_dt = f"{event_date} {start_time}".strip() if event_date else start_dt
            full_end_dt = f"{event_date} {end_time}".strip() if event_date and end_time else end_dt

            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO unified_events (
                        title, event_type, event_category, description,
                        organizer_id, organizer_name, organizer_type,
                        start_datetime, end_datetime,
                        location, building, room_id,
                        max_capacity, registration_required,
                        registration_deadline, image_url, tags,
                        source_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'campus')
                """, (
                    event_data.get('title', event_data.get('event_name', '')),
                    event_data.get('event_type', event_data.get('category', 'Other')),
                    event_data.get('category', event_data.get('event_category', 'Other')),
                    event_data.get('description', ''),
                    user_id,
                    event_data.get('organizer_name', ''),
                    event_data.get('organizer_type', 'Student'),
                    full_start_dt,
                    full_end_dt,
                    event_data.get('location', ''),
                    event_data.get('building', ''),
                    event_data.get('room', event_data.get('room_id', None)),
                    event_data.get('max_capacity', event_data.get('capacity', 0)),
                    event_data.get('registration_required', 0),
                    event_data.get('registration_deadline', ''),
                    event_data.get('event_image_url', event_data.get('image_url', '')),
                    json.dumps(event_data.get('tags', []))
                ))

                event_id = cursor.lastrowid

                log_activity(
                    'create', 'event', user_id=user_id,
                    details={'event_id': event_id, 'title': event_data.get('title', event_data.get('event_name', ''))}
                )

            # Also add to academic calendar
            self._add_to_academic_calendar(
                event_data.get('title', event_data.get('event_name', '')),
                event_date,
                event_data.get('description', ''),
                event_data.get('category', event_data.get('event_category', 'Other')),
                user_id
            )

            return event_id

        except Exception as e:
            logger.error(f"Error creating event: {e}")
            raise

    def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific event"""
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM unified_events WHERE event_id = ? AND source_type = 'campus'
                """, (event_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                columns = [description[0] for description in cursor.description]
                event = self._row_to_event(columns, row)

                # Get RSVP count
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_rsvps
                    WHERE event_id = ? AND rsvp_status = 'Going'
                """, (event_id,))
                event['rsvp_count'] = cursor.fetchone()[0]

                # Get average rating
                cursor = conn.execute("""
                    SELECT AVG(rating), COUNT(*) FROM discovery_event_ratings
                    WHERE event_id = ?
                """, (event_id,))
                avg_rating, rating_count = cursor.fetchone()
                event['average_rating'] = round(avg_rating, 1) if avg_rating else None
                event['rating_count'] = rating_count

                return event

        except Exception as e:
            logger.error(f"Error getting event {event_id}: {e}")
            raise

    def update_event(self, event_id: int, event_data: Dict[str, Any], user_id: str) -> bool:
        """Update event details"""
        try:
            # Map discovery field names to unified_events column names
            field_map = {
                'event_name': 'title',
                'category': 'event_category',
                'capacity': 'max_capacity',
                'event_image_url': 'image_url',
                'room': 'room_id',
            }

            with transaction() as conn:
                update_fields = []
                values = []

                for field in ['title', 'event_name', 'description', 'category',
                             'event_category', 'event_type', 'location', 'building',
                             'room', 'room_id', 'max_capacity', 'capacity',
                             'registration_required', 'registration_deadline',
                             'event_image_url', 'image_url']:
                    if field in event_data:
                        col = field_map.get(field, field)
                        update_fields.append(f"{col} = ?")
                        values.append(event_data[field])

                # Handle start_datetime / end_datetime
                if 'start_datetime' in event_data:
                    update_fields.append("start_datetime = ?")
                    values.append(event_data['start_datetime'])
                elif 'event_date' in event_data or 'start_time' in event_data:
                    ed = event_data.get('event_date', '')
                    st = event_data.get('start_time', '')
                    if ed or st:
                        update_fields.append("start_datetime = ?")
                        values.append(f"{ed} {st}".strip())

                if 'end_datetime' in event_data:
                    update_fields.append("end_datetime = ?")
                    values.append(event_data['end_datetime'])
                elif 'end_time' in event_data:
                    ed = event_data.get('event_date', '')
                    et = event_data.get('end_time', '')
                    if ed or et:
                        update_fields.append("end_datetime = ?")
                        values.append(f"{ed} {et}".strip())

                if 'tags' in event_data:
                    update_fields.append("tags = ?")
                    values.append(json.dumps(event_data['tags']))

                if not update_fields:
                    return False

                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(event_id)

                query = f"UPDATE unified_events SET {', '.join(update_fields)} WHERE event_id = ? AND source_type = 'campus'"
                conn.execute(query, values)

                log_activity(
                    'update', 'event', user_id=user_id,
                    details={'event_id': event_id, 'updated_fields': list(event_data.keys())}
                )

                return True

        except Exception as e:
            logger.error(f"Error updating event {event_id}: {e}")
            raise

    def cancel_event(self, event_id: int, user_id: str) -> bool:
        """Cancel an event"""
        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE unified_events SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE event_id = ? AND source_type = 'campus'
                """, (event_id,))

                log_activity(
                    'cancel', 'event',
                    user_id=user_id,
                    details={'event_id': event_id}
                )

                return True

        except Exception as e:
            logger.error(f"Error cancelling event {event_id}: {e}")
            raise

    def search_events(self,
                     category: Optional[str] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None,
                     keyword: Optional[str] = None,
                     upcoming_only: bool = True) -> List[Dict[str, Any]]:
        """
        Search events with various filters

        Args:
            category: Filter by category
            start_date: Filter events starting from this date
            end_date: Filter events ending before this date
            keyword: Search in title, description, tags
            upcoming_only: Only show future events

        Returns:
            List of events matching the criteria
        """
        try:
            with get_connection() as conn:
                query = "SELECT * FROM unified_events WHERE source_type = 'campus' AND status != 'cancelled'"
                params = []

                if upcoming_only:
                    query += " AND date(start_datetime) >= date('now')"

                if category:
                    query += " AND event_category = ?"
                    params.append(category)

                if start_date:
                    query += " AND date(start_datetime) >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND date(start_datetime) <= ?"
                    params.append(end_date)

                if keyword:
                    query += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)"
                    keyword_pattern = f"%{escape_like(keyword)}%"
                    params.extend([keyword_pattern, keyword_pattern, keyword_pattern])

                query += " ORDER BY start_datetime ASC"

                cursor = conn.execute(query, params)
                columns = [description[0] for description in cursor.description]
                events = [self._row_to_event(columns, row) for row in cursor.fetchall()]

                # Enrich with RSVP count
                for event in events:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM discovery_event_rsvps
                        WHERE event_id = ? AND rsvp_status = 'Going'
                    """, (event['event_id'],))
                    event['rsvp_count'] = cursor.fetchone()[0]

                return events

        except Exception as e:
            logger.error(f"Error searching events: {e}")
            raise

    def get_upcoming_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get upcoming events sorted by date"""
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM unified_events
                    WHERE source_type = 'campus' AND status != 'cancelled' AND date(start_datetime) >= date('now')
                    ORDER BY start_datetime ASC
                    LIMIT ?
                """, (limit,))

                columns = [description[0] for description in cursor.description]
                events = [self._row_to_event(columns, row) for row in cursor.fetchall()]

                # Enrich with RSVP count
                for event in events:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM discovery_event_rsvps
                        WHERE event_id = ? AND rsvp_status = 'Going'
                    """, (event['event_id'],))
                    event['rsvp_count'] = cursor.fetchone()[0]

                return events

        except Exception as e:
            logger.error(f"Error getting upcoming events: {e}")
            raise

    # ==================== RSVP Management ====================

    def rsvp_to_event(self, event_id: int, user_id: str, status: str,
                     add_to_calendar: bool = False) -> bool:
        """
        RSVP to an event

        Args:
            event_id: ID of the event
            user_id: ID of the user
            status: RSVP status ('Going', 'Interested', 'Not Going')
            add_to_calendar: Whether to add to calendar

        Returns:
            True if successful
        """
        try:
            if status not in self.RSVP_STATUS:
                raise ValueError(f"Invalid RSVP status: {status}")

            with transaction() as conn:
                # Check capacity if registration required
                cursor = conn.execute("""
                    SELECT max_capacity, registration_required FROM unified_events
                    WHERE event_id = ? AND source_type = 'campus'
                """, (event_id,))

                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Event {event_id} not found")

                max_capacity, registration_required = row

                if registration_required and max_capacity and max_capacity > 0:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM discovery_event_rsvps
                        WHERE event_id = ? AND rsvp_status = 'Going'
                    """, (event_id,))

                    current_count = cursor.fetchone()[0]
                    if current_count >= max_capacity and status == 'Going':
                        raise ValueError("Event is at full capacity")

                # Get event details for email before leaving transaction
                cursor = conn.execute("""
                    SELECT title, start_datetime, end_datetime, location
                    FROM unified_events WHERE event_id = ? AND source_type = 'campus'
                """, (event_id,))
                event_details = cursor.fetchone()

                # Insert or update RSVP
                conn.execute("""
                    INSERT INTO discovery_event_rsvps (event_id, user_id, rsvp_status, added_to_calendar)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(event_id, user_id) DO UPDATE SET
                        rsvp_status = excluded.rsvp_status,
                        added_to_calendar = excluded.added_to_calendar,
                        rsvp_date = CURRENT_TIMESTAMP
                """, (event_id, user_id, status, 1 if add_to_calendar else 0))

                log_activity(
                    'rsvp', 'event', user_id=user_id,
                    details={'event_id': event_id, 'status': status, 'add_to_calendar': add_to_calendar}
                )

            # Send RSVP confirmation email (outside transaction, non-blocking)
            if event_details:
                # event_details: (title, start_datetime, end_datetime, location)
                sd = str(event_details[1] or '')
                ed = str(event_details[2] or '')
                event_date = sd.split(' ', 1)[0] if ' ' in sd else sd
                start_time = sd.split(' ', 1)[1] if ' ' in sd else ''
                end_time = ed.split(' ', 1)[1] if ' ' in ed else ''
                self._send_rsvp_confirmation_email(
                    user_id, status, event_details[0], event_date,
                    start_time, end_time, event_details[3]
                )

            return True

        except Exception as e:
            logger.error(f"Error RSVPing to event {event_id}: {e}")
            raise

    def get_user_rsvps(self, user_id: str, upcoming_only: bool = True) -> List[Dict[str, Any]]:
        """Get all events a user has RSVP'd to"""
        try:
            with get_connection() as conn:
                query = """
                    SELECT e.*, r.rsvp_status, r.rsvp_date, r.added_to_calendar
                    FROM unified_events e
                    JOIN discovery_event_rsvps r ON e.event_id = r.event_id
                    WHERE r.user_id = ? AND e.source_type = 'campus' AND e.status != 'cancelled'
                """

                params = [user_id]

                if upcoming_only:
                    query += " AND date(e.start_datetime) >= date('now')"

                query += " ORDER BY e.start_datetime ASC"

                cursor = conn.execute(query, params)
                columns = [description[0] for description in cursor.description]
                events = [self._row_to_event(columns, row) for row in cursor.fetchall()]

                # Enrich with RSVP count
                for event in events:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM discovery_event_rsvps
                        WHERE event_id = ? AND rsvp_status = 'Going'
                    """, (event['event_id'],))
                    event['rsvp_count'] = cursor.fetchone()[0]

                return events

        except Exception as e:
            logger.error(f"Error getting RSVPs for user {user_id}: {e}")
            raise

    def cancel_rsvp(self, event_id: int, user_id: str) -> bool:
        """Cancel an RSVP to an event"""
        try:
            with transaction() as conn:
                conn.execute("""
                    DELETE FROM discovery_event_rsvps
                    WHERE event_id = ? AND user_id = ?
                """, (event_id, user_id))

                log_activity(
                    'cancel_rsvp', 'event',
                    user_id=user_id,
                    details={'event_id': event_id}
                )

                return True

        except Exception as e:
            logger.error(f"Error cancelling RSVP: {e}")
            raise

    # ==================== Attendance Tracking ====================

    def check_in_to_event(self, event_id: int, user_id: str) -> bool:
        """Check in to an event"""
        try:
            with transaction() as conn:
                # Verify event exists
                cursor = conn.execute("""
                    SELECT start_datetime, end_datetime FROM unified_events
                    WHERE event_id = ? AND source_type = 'campus'
                """, (event_id,))

                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Event {event_id} not found")

                start_datetime_str, end_datetime_str = row
                now = datetime.now()

                # Allow check-in 30 minutes before and until event end
                try:
                    start_dt = datetime.fromisoformat(start_datetime_str)
                    end_dt = datetime.fromisoformat(end_datetime_str)
                    start_check = start_dt - timedelta(minutes=30)

                    if now < start_check or now > end_dt:
                        raise ValueError("Event is not currently happening")
                except (ValueError, TypeError):
                    pass  # Allow check-in if datetime parsing fails

                # Record check-in
                conn.execute("""
                    INSERT INTO discovery_event_attendance (event_id, user_id, check_in_time)
                    VALUES (?, ?, ?)
                    ON CONFLICT(event_id, user_id) DO UPDATE SET
                        check_in_time = excluded.check_in_time
                """, (event_id, user_id, now.isoformat()))

                log_activity(
                    'check_in', 'event',
                    user_id=user_id,
                    details={'event_id': event_id}
                )

                event_name_row = conn.execute(
                    "SELECT event_name FROM unified_events WHERE event_id = ?",
                    (event_id,),
                ).fetchone()

            try:
                from education_system.post_18.university_system.modules.services.integration_bus import (
                    publish_event_attendance,
                )
                publish_event_attendance(
                    event_id, user_id=str(user_id),
                    event_name=event_name_row[0] if event_name_row else None,
                )
            except Exception:
                pass
            return True

        except Exception as e:
            logger.error(f"Error checking in to event {event_id}: {e}")
            raise

    def check_out_from_event(self, event_id: int, user_id: str) -> bool:
        """Check out from an event"""
        try:
            with transaction() as conn:
                conn.execute("""
                    UPDATE discovery_event_attendance
                    SET check_out_time = ?
                    WHERE event_id = ? AND user_id = ?
                """, (datetime.now().isoformat(), event_id, user_id))

                log_activity(
                    'check_out', 'event',
                    user_id=user_id,
                    details={'event_id': event_id}
                )

                return True

        except Exception as e:
            logger.error(f"Error checking out from event {event_id}: {e}")
            raise

    def get_event_attendance(self, event_id: int) -> List[Dict[str, Any]]:
        """Get attendance records for an event"""
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM discovery_event_attendance
                    WHERE event_id = ?
                    ORDER BY check_in_time DESC
                """, (event_id,))

                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting attendance for event {event_id}: {e}")
            raise

    def get_user_attendance_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all events a user has attended"""
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT e.*, a.check_in_time, a.check_out_time
                    FROM unified_events e
                    JOIN discovery_event_attendance a ON e.event_id = a.event_id
                    WHERE a.user_id = ? AND e.source_type = 'campus'
                    ORDER BY a.check_in_time DESC
                """, (user_id,))

                columns = [description[0] for description in cursor.description]
                events = [self._row_to_event(columns, row) for row in cursor.fetchall()]

                return events

        except Exception as e:
            logger.error(f"Error getting attendance history for user {user_id}: {e}")
            raise

    # ==================== Interest Preferences ====================

    def set_interest_preference(self, user_id: str, category: str,
                               interest_level: int) -> bool:
        """
        Set interest level for a category (1-10 scale)

        Args:
            user_id: ID of the user
            category: Event category
            interest_level: Interest level (1-10)

        Returns:
            True if successful
        """
        try:
            if category not in self.CATEGORIES:
                raise ValueError(f"Invalid category: {category}")

            if not 1 <= interest_level <= 10:
                raise ValueError("Interest level must be between 1 and 10")

            with transaction() as conn:
                conn.execute("""
                    INSERT INTO discovery_event_interests (user_id, category, interest_level)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, category) DO UPDATE SET
                        interest_level = excluded.interest_level
                """, (user_id, category, interest_level))

                log_activity(
                    'set_interest', 'event_preference',
                    user_id=user_id,
                    details={'category': category, 'level': interest_level}
                )

                return True

        except Exception as e:
            logger.error(f"Error setting interest preference: {e}")
            raise

    def get_user_interests(self, user_id: str) -> Dict[str, int]:
        """Get user's interest preferences"""
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT category, interest_level FROM discovery_event_interests
                    WHERE user_id = ?
                """, (user_id,))

                return {row[0]: row[1] for row in cursor.fetchall()}

        except Exception as e:
            logger.error(f"Error getting interests for user {user_id}: {e}")
            raise

    # ==================== Recommendations Engine ====================

    def get_personalized_recommendations(self, user_id: str,
                                        limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get personalized event recommendations based on:
        - User's interest preferences
        - Past attendance history
        - Events friends are attending
        - Popular events in preferred categories

        Args:
            user_id: ID of the user
            limit: Maximum number of recommendations

        Returns:
            List of recommended events with relevance scores
        """
        try:
            with get_connection() as conn:
                # Get user interests
                cursor = conn.execute("""
                    SELECT category, interest_level FROM discovery_event_interests
                    WHERE user_id = ?
                """, (user_id,))

                interests = {row[0]: row[1] for row in cursor.fetchall()}

                # Get attended event categories
                cursor = conn.execute("""
                    SELECT e.event_category, COUNT(*) as count
                    FROM discovery_event_attendance a
                    JOIN unified_events e ON a.event_id = e.event_id
                    WHERE a.user_id = ? AND e.source_type = 'campus'
                    GROUP BY e.event_category
                """, (user_id,))

                attendance_history = {row[0]: row[1] for row in cursor.fetchall()}

                # Get upcoming events not already RSVP'd to
                cursor = conn.execute("""
                    SELECT e.* FROM unified_events e
                    WHERE e.source_type = 'campus' AND e.status != 'cancelled'
                    AND date(e.start_datetime) >= date('now')
                    AND e.event_id NOT IN (
                        SELECT event_id FROM discovery_event_rsvps WHERE user_id = ?
                    )
                    ORDER BY e.start_datetime ASC
                """, (user_id,))

                columns = [description[0] for description in cursor.description]
                events = [self._row_to_event(columns, row) for row in cursor.fetchall()]

                # Score each event
                scored_events = []
                for event in events:
                    score = 0
                    category = event['category']

                    # Interest preference score (0-40 points)
                    if category in interests:
                        score += interests[category] * 4

                    # Attendance history score (0-20 points)
                    if category in attendance_history:
                        score += min(attendance_history[category] * 5, 20)

                    # Popularity score (0-20 points)
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM discovery_event_rsvps
                        WHERE event_id = ? AND rsvp_status = 'Going'
                    """, (event['event_id'],))
                    rsvp_count = cursor.fetchone()[0]
                    score += min(rsvp_count * 2, 20)

                    event['recommendation_score'] = score
                    event['rsvp_count'] = rsvp_count

                    scored_events.append(event)

                # Sort by score and return top recommendations
                scored_events.sort(key=lambda x: x['recommendation_score'], reverse=True)
                return scored_events[:limit]

        except Exception as e:
            logger.error(f"Error getting recommendations for user {user_id}: {e}")
            raise

    # ==================== Ratings and Reviews ====================

    def rate_event(self, event_id: int, user_id: str, rating: int,
                   review: Optional[str] = None) -> bool:
        """
        Rate and review an event

        Args:
            event_id: ID of the event
            user_id: ID of the user
            rating: Rating (1-5 stars)
            review: Optional text review

        Returns:
            True if successful
        """
        try:
            if not 1 <= rating <= 5:
                raise ValueError("Rating must be between 1 and 5")

            # Verify user attended the event
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_attendance
                    WHERE event_id = ? AND user_id = ?
                """, (event_id, user_id))

                if cursor.fetchone()[0] == 0:
                    raise ValueError("Can only rate events you attended")

            with transaction() as conn:
                conn.execute("""
                    INSERT INTO discovery_event_ratings (event_id, user_id, rating, review)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(event_id, user_id) DO UPDATE SET
                        rating = excluded.rating,
                        review = excluded.review,
                        rated_at = CURRENT_TIMESTAMP
                """, (event_id, user_id, rating, review))

                log_activity(
                    'rate', 'event', user_id=user_id,
                    details={'event_id': event_id, 'rating': rating}
                )

                return True

        except Exception as e:
            logger.error(f"Error rating event {event_id}: {e}")
            raise

    def get_event_reviews(self, event_id: int) -> List[Dict[str, Any]]:
        """Get all reviews for an event"""
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM discovery_event_ratings
                    WHERE event_id = ?
                    ORDER BY rated_at DESC
                """, (event_id,))

                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting reviews for event {event_id}: {e}")
            raise

    # ==================== Event Photos ====================

    def upload_event_photo(self, event_id: int, user_id: str,
                          photo_url: str, caption: Optional[str] = None) -> int:
        """Upload a photo to an event"""
        try:
            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO discovery_event_photos (event_id, user_id, photo_url, caption)
                    VALUES (?, ?, ?, ?)
                """, (event_id, user_id, photo_url, caption))

                photo_id = cursor.lastrowid

                log_activity(
                    'upload_photo', 'event', user_id=user_id,
                    details={'event_id': event_id, 'photo_id': photo_id}
                )

                return photo_id

        except Exception as e:
            logger.error(f"Error uploading photo to event {event_id}: {e}")
            raise

    def get_event_photos(self, event_id: int) -> List[Dict[str, Any]]:
        """Get all photos for an event"""
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM discovery_event_photos
                    WHERE event_id = ?
                    ORDER BY uploaded_at DESC
                """, (event_id,))

                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting photos for event {event_id}: {e}")
            raise

    # ==================== Social Features ====================

    def set_social_settings(self, user_id: str,
                           show_attendance: bool = True,
                           receive_notifications: bool = True) -> bool:
        """Set social feature preferences"""
        try:
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO discovery_event_social_settings
                    (user_id, show_attendance_to_friends, receive_friend_notifications)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        show_attendance_to_friends = excluded.show_attendance_to_friends,
                        receive_friend_notifications = excluded.receive_friend_notifications
                """, (user_id, 1 if show_attendance else 0, 1 if receive_notifications else 0))

                return True

        except Exception as e:
            logger.error(f"Error setting social settings for user {user_id}: {e}")
            raise

    def get_friends_attending(self, event_id: int, user_id: str) -> List[str]:
        """
        Get visible attendees for an event.

        This currently returns attendees who opted into visibility. If a
        friends/connections table is added later, filter this query to the
        current user's confirmed network.
        """
        try:
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT r.user_id FROM discovery_event_rsvps r
                    JOIN discovery_event_social_settings s ON r.user_id = s.user_id
                    WHERE r.event_id = ?
                    AND r.rsvp_status = 'Going'
                    AND s.show_attendance_to_friends = 1
                    AND r.user_id != ?
                """, (event_id, user_id))

                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting friends attending event {event_id}: {e}")
            raise

    # ==================== Analytics and Statistics ====================

    def get_event_statistics(self, event_id: int) -> Dict[str, Any]:
        """Get comprehensive statistics for an event"""
        try:
            with get_connection() as conn:
                stats = {}

                # Basic event info
                event = self.get_event(event_id)
                if not event:
                    raise ValueError(f"Event {event_id} not found")

                stats['event'] = event

                # RSVP breakdown
                cursor = conn.execute("""
                    SELECT rsvp_status, COUNT(*) as count
                    FROM discovery_event_rsvps
                    WHERE event_id = ?
                    GROUP BY rsvp_status
                """, (event_id,))

                stats['rsvp_breakdown'] = {row[0]: row[1] for row in cursor.fetchall()}

                # Attendance count
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_attendance WHERE event_id = ?
                """, (event_id,))
                stats['attendance_count'] = cursor.fetchone()[0]

                # Rating statistics
                cursor = conn.execute("""
                    SELECT
                        AVG(rating) as avg_rating,
                        COUNT(*) as review_count,
                        COUNT(CASE WHEN review IS NOT NULL AND review != '' THEN 1 END) as text_review_count
                    FROM discovery_event_ratings
                    WHERE event_id = ?
                """, (event_id,))

                row = cursor.fetchone()
                stats['average_rating'] = round(row[0], 2) if row[0] else None
                stats['review_count'] = row[1]
                stats['text_review_count'] = row[2]

                # Photo count
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_photos WHERE event_id = ?
                """, (event_id,))
                stats['photo_count'] = cursor.fetchone()[0]

                return stats

        except Exception as e:
            logger.error(f"Error getting statistics for event {event_id}: {e}")
            raise

    def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get event statistics for a user"""
        try:
            with get_connection() as conn:
                stats = {}

                # Total RSVPs
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_rsvps WHERE user_id = ?
                """, (user_id,))
                stats['total_rsvps'] = cursor.fetchone()[0]

                # Total attended
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_attendance WHERE user_id = ?
                """, (user_id,))
                stats['total_attended'] = cursor.fetchone()[0]

                # Attendance by category
                cursor = conn.execute("""
                    SELECT e.event_category, COUNT(*) as count
                    FROM discovery_event_attendance a
                    JOIN unified_events e ON a.event_id = e.event_id
                    WHERE a.user_id = ? AND e.source_type = 'campus'
                    GROUP BY e.event_category
                    ORDER BY count DESC
                """, (user_id,))

                stats['attendance_by_category'] = {row[0]: row[1] for row in cursor.fetchall()}

                # Reviews written
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_ratings
                    WHERE user_id = ? AND review IS NOT NULL AND review != ''
                """, (user_id,))
                stats['reviews_written'] = cursor.fetchone()[0]

                # Photos uploaded
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM discovery_event_photos WHERE user_id = ?
                """, (user_id,))
                stats['photos_uploaded'] = cursor.fetchone()[0]

                return stats

        except Exception as e:
            logger.error(f"Error getting statistics for user {user_id}: {e}")
            raise

# Singleton instance
_events_service = None

def get_events_service() -> EventsService:
    """Get the singleton EventsService instance"""
    global _events_service
    if _events_service is None:
        _events_service = EventsService()
    return _events_service
