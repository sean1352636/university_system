"""
Roommate Finder Service

Helps students find compatible roommates through questionnaires, matching algorithms,
and anonymous messaging.
"""

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import hashlib

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
from education_system.post_18.university_system.core.activity_logger import log_activity
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608

class RoommateService:
    """Service for roommate matching and communication."""

    def __init__(self):
        """Initialize the Roommate Finder Service."""
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Roommate Profiles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS roommate_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL,
                    bio TEXT,
                    budget_min INTEGER,
                    budget_max INTEGER,
                    move_in_date TEXT,
                    preferred_gender TEXT,
                    age INTEGER,
                    major TEXT,
                    year_of_study TEXT,
                    smoking_preference TEXT DEFAULT 'No',
                    pet_preference TEXT DEFAULT 'No pets',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Compatibility Questionnaire Responses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compatibility_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    response_value TEXT NOT NULL,
                    importance_level TEXT DEFAULT 'Medium',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE
                )
            """)

            # Compatibility Questions table (predefined)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compatibility_questions (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    response_type TEXT DEFAULT 'scale',
                    options TEXT,
                    weight REAL DEFAULT 1.0,
                    is_active BOOLEAN DEFAULT 1
                )
            """)

            # Roommate Matches table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS roommate_matches (
                    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id_1 INTEGER NOT NULL,
                    profile_id_2 INTEGER NOT NULL,
                    compatibility_score REAL NOT NULL,
                    match_reasons TEXT,
                    status TEXT DEFAULT 'Suggested',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (profile_id_1) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE,
                    FOREIGN KEY (profile_id_2) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE
                )
            """)

            # Anonymous Messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS roommate_messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    sender_profile_id INTEGER NOT NULL,
                    receiver_profile_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT 0,
                    sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES roommate_matches(match_id) ON DELETE CASCADE,
                    FOREIGN KEY (sender_profile_id) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE,
                    FOREIGN KEY (receiver_profile_id) REFERENCES roommate_profiles(profile_id) ON DELETE CASCADE
                )
            """)

            # Initialize default compatibility questions
            self._initialize_default_questions(conn)

            log_activity('create', 'roommate_finder_tables',
                        details={'status': 'Roommate Finder tables created'})

    def _initialize_default_questions(self, conn):
        """Initialize default compatibility questions."""
        # Check if questions already exist
        existing = conn.execute(
            "SELECT COUNT(*) as count FROM compatibility_questions"
        ).fetchone()

        if existing['count'] > 0:
            return

        default_questions = [
            # Lifestyle
            ("Lifestyle", "What time do you typically go to bed?", "choice",
             "Before 10 PM|10 PM - Midnight|After Midnight|Varies", 1.5),
            ("Lifestyle", "How tidy are you? (1=Very messy, 5=Very clean)", "scale",
             "1-5", 2.0),
            ("Lifestyle", "How often do you have guests over?", "choice",
             "Rarely|Occasionally|Frequently|Very Often", 1.3),
            ("Lifestyle", "Do you prefer quiet study time or background music?", "choice",
             "Complete silence|Quiet background|Moderate music|Loud music", 1.2),

            # Social Preferences
            ("Social", "How social are you? (1=Introverted, 5=Extroverted)", "scale",
             "1-5", 1.0),
            ("Social", "Do you prefer alone time or hanging out with roommates?", "choice",
             "Mostly alone|Some alone time|Balanced|Mostly together", 1.4),
            ("Social", "How do you handle conflicts?", "choice",
             "Avoid|Discuss calmly|Assert directly|Need mediator", 1.8),

            # Habits
            ("Habits", "How important is cleanliness to you?", "choice",
             "Not important|Somewhat|Important|Very important", 2.0),
            ("Habits", "Are you a morning person or night owl?", "choice",
             "Morning person|Early riser|Night owl|No preference", 1.2),
            ("Habits", "How do you feel about sharing food/supplies?", "choice",
             "Share everything|Share some|Keep separate|Ask first", 1.1),

            # Study Habits
            ("Study", "When do you prefer to study?", "choice",
             "Morning|Afternoon|Evening|Late night", 0.8),
            ("Study", "Do you study in your room or elsewhere?", "choice",
             "Always in room|Mostly in room|Mostly elsewhere|Never in room", 1.0),

            # Preferences
            ("Preferences", "Temperature preference", "choice",
             "Very cool|Cool|Moderate|Warm|Very warm", 1.3),
            ("Preferences", "How important is having similar interests?", "choice",
             "Not important|Somewhat|Important|Very important", 0.9),
        ]

        for category, question, resp_type, options, weight in default_questions:
            conn.execute("""
                INSERT INTO compatibility_questions
                (category, question_text, response_type, options, weight)
                VALUES (?, ?, ?, ?, ?)
            """, (category, question, resp_type, options, weight))

    # ========== Profile Management ==========

    def create_profile(self, student_id: str, display_name: str, bio: str = "",
                      budget_min: int = 0, budget_max: int = 0,
                      move_in_date: Optional[str] = None,
                      preferred_gender: str = "No preference",
                      age: Optional[int] = None, major: str = "",
                      year_of_study: str = "", smoking_preference: str = "No",
                      pet_preference: str = "No pets") -> int:
        """
        Create a roommate profile for a student.

        Args:
            student_id: Student's ID
            display_name: Public display name (can be anonymous)
            bio: Short bio about themselves
            budget_min: Minimum monthly budget
            budget_max: Maximum monthly budget
            move_in_date: Preferred move-in date (YYYY-MM-DD)
            preferred_gender: Gender preference for roommate
            age: Student's age
            major: Student's major
            year_of_study: Year in school
            smoking_preference: Smoking preference
            pet_preference: Pet preference

        Returns:
            Profile ID
        """
        with transaction() as conn:
            # Check if student exists in students table
            student_exists = conn.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (student_id,)
            ).fetchone()

            # If student doesn't exist, create a basic student record
            if not student_exists:
                conn.execute("""
                    INSERT INTO students (student_id, status, registration_datetime)
                    VALUES (?, 'Active', ?)
                """, (student_id, datetime.now().isoformat()))

            cursor = conn.execute("""
                INSERT INTO roommate_profiles
                (student_id, display_name, bio, budget_min, budget_max,
                 move_in_date, preferred_gender, age, major, year_of_study,
                 smoking_preference, pet_preference)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, display_name, bio, budget_min, budget_max,
                  move_in_date, preferred_gender, age, major, year_of_study,
                  smoking_preference, pet_preference))

            profile_id = cursor.lastrowid

            log_activity('create', 'roommate_profile',
                        details={'student_id': student_id, 'profile_id': profile_id})

            return profile_id

    def update_profile(self, profile_id: int, **updates) -> bool:
        """Update roommate profile with given fields."""
        if not updates:
            return False

        allowed_fields = {
            'display_name', 'bio', 'budget_min', 'budget_max', 'move_in_date',
            'preferred_gender', 'age', 'major', 'year_of_study',
            'smoking_preference', 'pet_preference', 'is_active'
        }

        # Filter to only allowed fields
        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not valid_updates:
            return False

        # Build UPDATE query
        set_clause = ", ".join([validate_identifier(field, "column") + " = ?" for field in valid_updates.keys()])
        set_clause += ", updated_at = ?"

        values = list(valid_updates.values())
        values.append(datetime.now().isoformat())
        values.append(profile_id)

        with transaction() as conn:
            conn.execute(
                "UPDATE roommate_profiles"
                " SET " + set_clause +
                " WHERE profile_id = ?",
                values)

            log_activity('update', 'roommate_profile',
                        details={'profile_id': profile_id, 'updated_fields': list(valid_updates.keys())})

        return True

    def get_profile(self, profile_id: int) -> Optional[Dict]:
        """Get roommate profile by ID."""
        with get_connection() as conn:
            profile = conn.execute("""
                SELECT * FROM roommate_profiles WHERE profile_id = ?
            """, (profile_id,)).fetchone()

            return dict(profile) if profile else None

    def get_profile_by_student(self, student_id: str) -> Optional[Dict]:
        """Get roommate profile by student ID."""
        with get_connection() as conn:
            profile = conn.execute("""
                SELECT * FROM roommate_profiles WHERE student_id = ?
            """, (student_id,)).fetchone()

            return dict(profile) if profile else None

    # ========== Compatibility Questionnaire ==========

    def get_questions(self) -> List[Dict]:
        """Get all active compatibility questions."""
        with get_connection() as conn:
            questions = conn.execute("""
                SELECT * FROM compatibility_questions
                WHERE is_active = 1
                ORDER BY category, question_id
            """).fetchall()

            return [dict(q) for q in questions]

    def submit_questionnaire(self, profile_id: int,
                            responses: List[Dict[str, any]]) -> bool:
        """
        Submit compatibility questionnaire responses.

        Args:
            profile_id: Profile ID
            responses: List of dicts with 'question_id', 'response_value', 'importance_level'

        Returns:
            Success status
        """
        with transaction() as conn:
            # Delete existing responses
            conn.execute("""
                DELETE FROM compatibility_responses WHERE profile_id = ?
            """, (profile_id,))

            # Insert new responses
            for response in responses:
                conn.execute("""
                    INSERT INTO compatibility_responses
                    (profile_id, question_id, response_value, importance_level)
                    VALUES (?, ?, ?, ?)
                """, (profile_id, response['question_id'],
                      response['response_value'],
                      response.get('importance_level', 'Medium')))

            log_activity('update', 'compatibility_questionnaire',
                        details={'profile_id': profile_id, 'responses_submitted': len(responses)})

        return True

    def get_questionnaire_responses(self, profile_id: int) -> List[Dict]:
        """Get all questionnaire responses for a profile."""
        with get_connection() as conn:
            responses = conn.execute("""
                SELECT cr.*, cq.question_text, cq.category, cq.weight
                FROM compatibility_responses cr
                JOIN compatibility_questions cq ON cr.question_id = cq.question_id
                WHERE cr.profile_id = ?
                ORDER BY cq.category, cq.question_id
            """, (profile_id,)).fetchall()

            return [dict(r) for r in responses]

    # ========== Matching Algorithm ==========

    def calculate_compatibility(self, profile_id_1: int,
                               profile_id_2: int) -> Tuple[float, List[str]]:
        """
        Calculate compatibility score between two profiles.

        Args:
            profile_id_1: First profile ID
            profile_id_2: Second profile ID

        Returns:
            Tuple of (compatibility_score, match_reasons)
        """
        with get_connection() as conn:
            # Get both profiles
            profile1 = conn.execute(
                "SELECT * FROM roommate_profiles WHERE profile_id = ?",
                (profile_id_1,)
            ).fetchone()
            profile2 = conn.execute(
                "SELECT * FROM roommate_profiles WHERE profile_id = ?",
                (profile_id_2,)
            ).fetchone()

            if not profile1 or not profile2:
                return 0.0, ["Profile not found"]

            # Get questionnaire responses
            responses1 = conn.execute("""
                SELECT cr.*, cq.weight, cq.question_text
                FROM compatibility_responses cr
                JOIN compatibility_questions cq ON cr.question_id = cq.question_id
                WHERE cr.profile_id = ?
            """, (profile_id_1,)).fetchall()

            responses2 = conn.execute("""
                SELECT cr.*, cq.weight, cq.question_text
                FROM compatibility_responses cr
                JOIN compatibility_questions cq ON cr.question_id = cq.question_id
                WHERE cr.profile_id = ?
            """, (profile_id_2,)).fetchall()

            # Create response maps
            resp_map1 = {r['question_id']: r for r in responses1}
            resp_map2 = {r['question_id']: r for r in responses2}

            # Calculate compatibility
            total_score = 0.0
            max_score = 0.0
            match_reasons = []

            # Compare questionnaire responses
            for q_id in set(resp_map1.keys()) & set(resp_map2.keys()):
                r1 = resp_map1[q_id]
                r2 = resp_map2[q_id]
                weight = r1['weight']

                # Importance multiplier
                importance_mult = self._get_importance_multiplier(
                    r1['importance_level'], r2['importance_level']
                )

                max_score += weight * importance_mult

                if r1['response_value'] == r2['response_value']:
                    # Exact match
                    total_score += weight * importance_mult
                    match_reasons.append(f"Both: {r1['question_text'][:50]}...")
                elif self._is_similar_response(r1['response_value'], r2['response_value']):
                    # Similar response
                    total_score += (weight * importance_mult * 0.5)

            # Add profile compatibility factors
            profile_score, profile_reasons = self._calculate_profile_compatibility(
                dict(profile1), dict(profile2)
            )
            total_score += profile_score
            max_score += 30.0  # Max profile score
            match_reasons.extend(profile_reasons)

            # Normalize to 0-100
            compatibility_score = (total_score / max_score * 100) if max_score > 0 else 0

            return round(compatibility_score, 2), match_reasons

    def _get_importance_multiplier(self, imp1: str, imp2: str) -> float:
        """Get importance multiplier based on importance levels."""
        importance_values = {
            'Low': 0.5,
            'Medium': 1.0,
            'High': 1.5,
            'Critical': 2.0
        }
        return (importance_values.get(imp1, 1.0) + importance_values.get(imp2, 1.0)) / 2

    def _is_similar_response(self, resp1: str, resp2: str) -> bool:
        """Check if two responses are similar."""
        # For scale responses (numeric)
        try:
            val1 = int(resp1)
            val2 = int(resp2)
            return abs(val1 - val2) <= 1
        except ValueError:
            pass

        # For text responses, check if they share keywords
        keywords1 = set(resp1.lower().split())
        keywords2 = set(resp2.lower().split())
        return len(keywords1 & keywords2) > 0

    def _calculate_profile_compatibility(self, profile1: Dict,
                                        profile2: Dict) -> Tuple[float, List[str]]:
        """Calculate compatibility based on profile attributes."""
        score = 0.0
        reasons = []

        # Budget compatibility (10 points)
        if profile1['budget_min'] and profile2['budget_min']:
            budget_overlap = not (
                profile1['budget_max'] < profile2['budget_min'] or
                profile2['budget_max'] < profile1['budget_min']
            )
            if budget_overlap:
                score += 10
                reasons.append("Compatible budget ranges")

        # Major similarity (5 points)
        if profile1['major'] and profile2['major']:
            if profile1['major'].lower() == profile2['major'].lower():
                score += 5
                reasons.append(f"Same major: {profile1['major']}")

        # Year of study (5 points)
        if profile1['year_of_study'] and profile2['year_of_study']:
            if profile1['year_of_study'] == profile2['year_of_study']:
                score += 5
                reasons.append(f"Same year: {profile1['year_of_study']}")

        # Smoking preference (5 points - critical)
        if profile1['smoking_preference'] == profile2['smoking_preference']:
            score += 5
            reasons.append("Same smoking preference")

        # Pet preference (5 points)
        if profile1['pet_preference'] == profile2['pet_preference']:
            score += 5
            reasons.append("Same pet preference")

        return score, reasons

    def find_matches(self, profile_id: int, min_score: float = 50.0,
                    limit: int = 20) -> List[Dict]:
        """
        Find compatible roommate matches for a profile.

        Args:
            profile_id: Profile ID to find matches for
            min_score: Minimum compatibility score (0-100)
            limit: Maximum number of matches to return

        Returns:
            List of match dictionaries with scores and reasons
        """
        with get_connection() as conn:
            # Get the profile
            profile = conn.execute(
                "SELECT * FROM roommate_profiles WHERE profile_id = ?",
                (profile_id,)
            ).fetchone()

            if not profile:
                return []

            # Get all other active profiles
            candidates = conn.execute("""
                SELECT profile_id FROM roommate_profiles
                WHERE profile_id != ? AND is_active = 1
            """, (profile_id,)).fetchall()

            matches = []
            for candidate in candidates:
                candidate_id = candidate['profile_id']
                score, reasons = self.calculate_compatibility(profile_id, candidate_id)

                if score >= min_score:
                    # Get candidate profile
                    candidate_profile = conn.execute(
                        "SELECT * FROM roommate_profiles WHERE profile_id = ?",
                        (candidate_id,)
                    ).fetchone()

                    matches.append({
                        'profile_id': candidate_id,
                        'profile': dict(candidate_profile),
                        'compatibility_score': score,
                        'match_reasons': reasons
                    })

            # Sort by compatibility score
            matches.sort(key=lambda x: x['compatibility_score'], reverse=True)

            # Store top matches in database
            with transaction() as conn:
                for match in matches[:limit]:
                    # Check if match already exists
                    existing = conn.execute("""
                        SELECT match_id FROM roommate_matches
                        WHERE (profile_id_1 = ? AND profile_id_2 = ?)
                           OR (profile_id_1 = ? AND profile_id_2 = ?)
                    """, (profile_id, match['profile_id'],
                          match['profile_id'], profile_id)).fetchone()

                    if not existing:
                        conn.execute("""
                            INSERT INTO roommate_matches
                            (profile_id_1, profile_id_2, compatibility_score, match_reasons)
                            VALUES (?, ?, ?, ?)
                        """, (profile_id, match['profile_id'],
                              match['compatibility_score'],
                              json.dumps(match['match_reasons'])))

            log_activity('create', 'roommate_matches',
                        details={'profile_id': profile_id, 'matches_found': len(matches[:limit])})

            return matches[:limit]

    def get_matches(self, profile_id: int) -> List[Dict]:
        """Get all matches for a profile."""
        with get_connection() as conn:
            matches = conn.execute("""
                SELECT rm.*, rp.display_name, rp.bio, rp.major, rp.year_of_study
                FROM roommate_matches rm
                JOIN roommate_profiles rp ON
                    (CASE WHEN rm.profile_id_1 = ? THEN rm.profile_id_2
                          ELSE rm.profile_id_1 END) = rp.profile_id
                WHERE rm.profile_id_1 = ? OR rm.profile_id_2 = ?
                ORDER BY rm.compatibility_score DESC
            """, (profile_id, profile_id, profile_id)).fetchall()

            return [dict(m) for m in matches]

    def update_match_status(self, match_id: int, status: str) -> bool:
        """Update match status (Suggested, Interested, Connected, Declined)."""
        valid_statuses = ['Suggested', 'Interested', 'Connected', 'Declined']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of {valid_statuses}")

        with transaction() as conn:
            conn.execute("""
                UPDATE roommate_matches SET status = ? WHERE match_id = ?
            """, (status, match_id))

            log_activity('update', 'roommate_match_status',
                        details={'match_id': match_id, 'status': status})

        return True

    # ========== Anonymous Messaging ==========

    def send_message(self, match_id: int, sender_profile_id: int,
                    message_text: str) -> int:
        """
        Send an anonymous message to a matched roommate.

        Args:
            match_id: Match ID
            sender_profile_id: Sender's profile ID
            message_text: Message content

        Returns:
            Message ID
        """
        # Validate match and get receiver
        with get_connection() as conn:
            match = conn.execute("""
                SELECT profile_id_1, profile_id_2 FROM roommate_matches
                WHERE match_id = ?
            """, (match_id,)).fetchone()

            if not match:
                raise ValueError("Match not found")

            # Determine receiver
            if match['profile_id_1'] == sender_profile_id:
                receiver_profile_id = match['profile_id_2']
            elif match['profile_id_2'] == sender_profile_id:
                receiver_profile_id = match['profile_id_1']
            else:
                raise ValueError("Sender is not part of this match")

        # Send message
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO roommate_messages
                (match_id, sender_profile_id, receiver_profile_id, message_text)
                VALUES (?, ?, ?, ?)
            """, (match_id, sender_profile_id, receiver_profile_id, message_text))

            message_id = cursor.lastrowid

            log_activity('create', 'roommate_message',
                        details={'message_id': message_id, 'match_id': match_id})

            return message_id

    def get_messages(self, match_id: int, profile_id: int) -> List[Dict]:
        """Get all messages for a match (from perspective of profile_id)."""
        with get_connection() as conn:
            messages = conn.execute("""
                SELECT *,
                    CASE WHEN sender_profile_id = ? THEN 'sent' ELSE 'received' END as direction
                FROM roommate_messages
                WHERE match_id = ?
                ORDER BY sent_at ASC
            """, (profile_id, match_id)).fetchall()

            return [dict(m) for m in messages]

    def mark_messages_read(self, match_id: int, profile_id: int) -> int:
        """Mark all messages as read for a profile in a match."""
        with transaction() as conn:
            cursor = conn.execute("""
                UPDATE roommate_messages
                SET is_read = 1
                WHERE match_id = ? AND receiver_profile_id = ? AND is_read = 0
            """, (match_id, profile_id))

            return cursor.rowcount

    def get_unread_count(self, profile_id: int) -> int:
        """Get count of unread messages for a profile."""
        with get_connection() as conn:
            result = conn.execute("""
                SELECT COUNT(*) as count FROM roommate_messages
                WHERE receiver_profile_id = ? AND is_read = 0
            """, (profile_id,)).fetchone()

            return result['count'] if result else 0

    # ========== Analytics ==========

    def get_profile_stats(self, profile_id: int) -> Dict:
        """Get statistics for a roommate profile."""
        with get_connection() as conn:
            # Match stats
            match_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_matches,
                    AVG(compatibility_score) as avg_score,
                    MAX(compatibility_score) as max_score
                FROM roommate_matches
                WHERE profile_id_1 = ? OR profile_id_2 = ?
            """, (profile_id, profile_id)).fetchone()

            # Message stats
            message_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_messages,
                    SUM(CASE WHEN sender_profile_id = ? THEN 1 ELSE 0 END) as sent_count,
                    SUM(CASE WHEN receiver_profile_id = ? THEN 1 ELSE 0 END) as received_count
                FROM roommate_messages rm
                JOIN roommate_matches m ON rm.match_id = m.match_id
                WHERE m.profile_id_1 = ? OR m.profile_id_2 = ?
            """, (profile_id, profile_id, profile_id, profile_id)).fetchone()

            return {
                'matches': dict(match_stats) if match_stats else {},
                'messages': dict(message_stats) if message_stats else {}
            }
