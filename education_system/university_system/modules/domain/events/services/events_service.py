"""
Event Discovery Engine Service Layer

Provides comprehensive event management with personalized recommendations,
RSVP system, attendance tracking, calendar integration, and social features.

Features:
- Personalized event recommendations based on interests and attendance history
- Friends' event attendance tracking (opt-in social feature)
- Calendar integration with one-click RSVP
- Event reminders and location details
- Event check-in for attendance tracking
- Event photos and recaps
- Multi-category support (Academic, Social, Athletic, Cultural, Career, Community Service)
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import json
import logging

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

logger = logging.getLogger(__name__)

class EventsService:
    """Service for managing university events, RSVPs, and recommendations"""

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
        """Initialize the events service and create database tables"""
        self.initialize_database()

    def initialize_database(self):
        """Create all necessary database tables for event management"""
        try:
            with transaction() as conn:
                # Events table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS discovery_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        category TEXT NOT NULL,
                        start_datetime TEXT NOT NULL,
                        end_datetime TEXT NOT NULL,
                        location TEXT NOT NULL,
                        building TEXT,
                        room TEXT,
                        organizer_id TEXT,
                        organizer_name TEXT,
                        organizer_type TEXT,
                        max_capacity INTEGER,
                        registration_required INTEGER DEFAULT 0,
                        registration_deadline TEXT,
                        event_image_url TEXT,
                        tags TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        cancelled INTEGER DEFAULT 0
                    )
                """)

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
                        FOREIGN KEY (event_id) REFERENCES discovery_events(event_id),
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
                        FOREIGN KEY (event_id) REFERENCES discovery_events(event_id),
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
                        FOREIGN KEY (event_id) REFERENCES discovery_events(event_id)
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
                        FOREIGN KEY (event_id) REFERENCES discovery_events(event_id),
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
                    CREATE INDEX IF NOT EXISTS idx_events_datetime
                    ON discovery_events(start_datetime)
                """)

                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_events_category
                    ON discovery_events(category)
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

    # ==================== Event Management ====================

    def create_event(self, event_data: Dict[str, Any], user_id: str) -> int:
        """
        Create a new event

        Args:
            event_data: Dictionary containing event details
            user_id: ID of the user creating the event

        Returns:
            event_id of the created event
        """
        try:
            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO discovery_events (
                        title, description, category, start_datetime, end_datetime,
                        location, building, room, organizer_id, organizer_name,
                        organizer_type, max_capacity, registration_required,
                        registration_deadline, event_image_url, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_data['title'],
                    event_data.get('description', ''),
                    event_data['category'],
                    event_data['start_datetime'],
                    event_data['end_datetime'],
                    event_data['location'],
                    event_data.get('building', ''),
                    event_data.get('room', ''),
                    user_id,
                    event_data.get('organizer_name', ''),
                    event_data.get('organizer_type', 'Student'),
                    event_data.get('max_capacity', 0),
                    event_data.get('registration_required', 0),
                    event_data.get('registration_deadline', ''),
                    event_data.get('event_image_url', ''),
                    json.dumps(event_data.get('tags', []))
                ))

                event_id = cursor.lastrowid

                log_activity(
                    'create', 'event', event_id=event_id,
                    user_id=user_id,
                    details={'title': event_data['title']}
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
                    SELECT * FROM discovery_events WHERE event_id = ?
                """, (event_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                columns = [description[0] for description in cursor.description]
                event = dict(zip(columns, row))

                # Parse tags
                if event['tags']:
                    event['tags'] = json.loads(event['tags'])
                else:
                    event['tags'] = []

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
            with transaction() as conn:
                # Build update query dynamically
                update_fields = []
                values = []

                for field in ['title', 'description', 'category', 'start_datetime',
                             'end_datetime', 'location', 'building', 'room',
                             'max_capacity', 'registration_required',
                             'registration_deadline', 'event_image_url']:
                    if field in event_data:
                        update_fields.append(f"{field} = ?")
                        values.append(event_data[field])

                if 'tags' in event_data:
                    update_fields.append("tags = ?")
                    values.append(json.dumps(event_data['tags']))

                if not update_fields:
                    return False

                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(event_id)

                query = f"UPDATE discovery_events SET {', '.join(update_fields)} WHERE event_id = ?"
                conn.execute(query, values)

                log_activity(
                    'update', 'event', event_id=event_id,
                    user_id=user_id,
                    details={'updated_fields': list(event_data.keys())}
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
                    UPDATE discovery_events SET cancelled = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE event_id = ?
                """, (event_id,))

                log_activity(
                    'cancel', 'event', event_id=event_id,
                    user_id=user_id
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
                query = "SELECT * FROM discovery_events WHERE cancelled = 0"
                params = []

                if upcoming_only:
                    query += " AND start_datetime >= datetime('now')"

                if category:
                    query += " AND category = ?"
                    params.append(category)

                if start_date:
                    query += " AND start_datetime >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND start_datetime <= ?"
                    params.append(end_date)

                if keyword:
                    query += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)"
                    keyword_pattern = f"%{keyword}%"
                    params.extend([keyword_pattern, keyword_pattern, keyword_pattern])

                query += " ORDER BY start_datetime ASC"

                cursor = conn.execute(query, params)
                columns = [description[0] for description in cursor.description]
                events = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # Enrich with additional data
                for event in events:
                    if event['tags']:
                        event['tags'] = json.loads(event['tags'])
                    else:
                        event['tags'] = []

                    # Get RSVP count
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
                    SELECT * FROM discovery_events
                    WHERE cancelled = 0 AND start_datetime >= datetime('now')
                    ORDER BY start_datetime ASC
                    LIMIT ?
                """, (limit,))

                columns = [description[0] for description in cursor.description]
                events = [dict(zip(columns, row)) for row in cursor.fetchall()]

                # Enrich with additional data
                for event in events:
                    if event['tags']:
                        event['tags'] = json.loads(event['tags'])
                    else:
                        event['tags'] = []

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
                    SELECT max_capacity, registration_required FROM discovery_events
                    WHERE event_id = ?
                """, (event_id,))

                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Event {event_id} not found")

                max_capacity, registration_required = row

                if registration_required and max_capacity > 0:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM discovery_event_rsvps
                        WHERE event_id = ? AND rsvp_status = 'Going'
                    """, (event_id,))

                    current_count = cursor.fetchone()[0]
                    if current_count >= max_capacity and status == 'Going':
                        raise ValueError("Event is at full capacity")

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
                    'rsvp', 'event', event_id=event_id,
                    user_id=user_id,
                    details={'status': status, 'add_to_calendar': add_to_calendar}
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
                    FROM discovery_events e
                    JOIN discovery_event_rsvps r ON e.event_id = r.event_id
                    WHERE r.user_id = ? AND e.cancelled = 0
                """

                params = [user_id]

                if upcoming_only:
                    query += " AND e.start_datetime >= datetime('now')"

                query += " ORDER BY e.start_datetime ASC"

                cursor = conn.execute(query, params)
                columns = [description[0] for description in cursor.description]
                events = [dict(zip(columns, row)) for row in cursor.fetchall()]

                for event in events:
                    if event['tags']:
                        event['tags'] = json.loads(event['tags'])
                    else:
                        event['tags'] = []

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
                    'cancel_rsvp', 'event', event_id=event_id,
                    user_id=user_id
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
                # Verify event is happening now
                cursor = conn.execute("""
                    SELECT start_datetime, end_datetime FROM discovery_events
                    WHERE event_id = ?
                """, (event_id,))

                row = cursor.fetchone()
                if not row:
                    raise ValueError(f"Event {event_id} not found")

                start_time, end_time = row
                now = datetime.now().isoformat()

                # Allow check-in 30 minutes before and until event end
                start_check = (datetime.fromisoformat(start_time) - timedelta(minutes=30)).isoformat()

                if now < start_check or now > end_time:
                    raise ValueError("Event is not currently happening")

                # Record check-in
                conn.execute("""
                    INSERT INTO discovery_event_attendance (event_id, user_id, check_in_time)
                    VALUES (?, ?, ?)
                    ON CONFLICT(event_id, user_id) DO UPDATE SET
                        check_in_time = excluded.check_in_time
                """, (event_id, user_id, now))

                log_activity(
                    'check_in', 'event', event_id=event_id,
                    user_id=user_id
                )

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
                    'check_out', 'event', event_id=event_id,
                    user_id=user_id
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
                    FROM discovery_events e
                    JOIN discovery_event_attendance a ON e.event_id = a.event_id
                    WHERE a.user_id = ?
                    ORDER BY a.check_in_time DESC
                """, (user_id,))

                columns = [description[0] for description in cursor.description]
                events = [dict(zip(columns, row)) for row in cursor.fetchall()]

                for event in events:
                    if event['tags']:
                        event['tags'] = json.loads(event['tags'])
                    else:
                        event['tags'] = []

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
                    SELECT e.category, COUNT(*) as count
                    FROM discovery_event_attendance a
                    JOIN discovery_events e ON a.event_id = e.event_id
                    WHERE a.user_id = ?
                    GROUP BY e.category
                """, (user_id,))

                attendance_history = {row[0]: row[1] for row in cursor.fetchall()}

                # Get upcoming events not already RSVP'd to
                cursor = conn.execute("""
                    SELECT e.* FROM discovery_events e
                    WHERE e.cancelled = 0
                    AND e.start_datetime >= datetime('now')
                    AND e.event_id NOT IN (
                        SELECT event_id FROM discovery_event_rsvps WHERE user_id = ?
                    )
                    ORDER BY e.start_datetime ASC
                """, (user_id,))

                columns = [description[0] for description in cursor.description]
                events = [dict(zip(columns, row)) for row in cursor.fetchall()]

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

                    # Friends attending score (0-20 points)
                    # Note: Would need a friends table for full implementation
                    # For now, this is a placeholder

                    event['recommendation_score'] = score
                    event['rsvp_count'] = rsvp_count

                    if event['tags']:
                        event['tags'] = json.loads(event['tags'])
                    else:
                        event['tags'] = []

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
                    'rate', 'event', event_id=event_id,
                    user_id=user_id,
                    details={'rating': rating}
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
                    'upload_photo', 'event', event_id=event_id,
                    user_id=user_id,
                    details={'photo_id': photo_id}
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
        Get list of friends attending an event

        Note: This is a placeholder. Full implementation would require
        a friends/connections table to determine friendships.
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
                    SELECT e.category, COUNT(*) as count
                    FROM discovery_event_attendance a
                    JOIN discovery_events e ON a.event_id = e.event_id
                    WHERE a.user_id = ?
                    GROUP BY e.category
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
