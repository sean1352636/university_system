"""
Peer Study Matching Service

Connects students for collaborative learning with intelligent matching algorithms.
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
import json
import hashlib

from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity
from education_system.systems.university.infrastructure.sql_safety import validate_identifier  # nosec B608

class StudyMatchingService:
    """Service for peer study matching and virtual study rooms."""

    def __init__(self):
        """Initialize the Study Matching Service."""
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Student Study Profiles table
            # Note: Removed FOREIGN KEY constraint on student_id to allow flexibility
            # with different authentication systems (users vs students tables)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL UNIQUE,
                    study_style TEXT DEFAULT 'Visual',
                    preferred_time TEXT DEFAULT 'Evening',
                    group_size_preference TEXT DEFAULT 'Small',
                    communication_style TEXT DEFAULT 'Collaborative',
                    noise_preference TEXT DEFAULT 'Quiet',
                    availability_json TEXT,
                    interests_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Study Groups table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_groups (
                    group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    creator_id TEXT NOT NULL,
                    max_members INTEGER DEFAULT 6,
                    current_members INTEGER DEFAULT 1,
                    meeting_schedule TEXT,
                    location TEXT,
                    is_virtual BOOLEAN DEFAULT 1,
                    status TEXT DEFAULT 'Active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Study Group Members table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_group_members (
                    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    role TEXT DEFAULT 'Member',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    contribution_score INTEGER DEFAULT 0,
                    attendance_count INTEGER DEFAULT 0,
                    FOREIGN KEY (group_id) REFERENCES study_groups(group_id) ON DELETE CASCADE,
                    UNIQUE(group_id, student_id)
                )
            """)

            # Virtual Study Rooms table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS virtual_study_rooms (
                    room_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER,
                    room_name TEXT NOT NULL,
                    room_code TEXT NOT NULL UNIQUE,
                    host_id TEXT NOT NULL,
                    course_id TEXT,
                    max_participants INTEGER DEFAULT 8,
                    current_participants INTEGER DEFAULT 0,
                    pomodoro_enabled BOOLEAN DEFAULT 1,
                    work_duration INTEGER DEFAULT 25,
                    break_duration INTEGER DEFAULT 5,
                    session_count INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    FOREIGN KEY (group_id) REFERENCES study_groups(group_id)
                )
            """)

            # Study Room Participants table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_room_participants (
                    participant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    left_at TEXT,
                    total_time_minutes INTEGER DEFAULT 0,
                    pomodoro_sessions_completed INTEGER DEFAULT 0,
                    is_currently_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (room_id) REFERENCES virtual_study_rooms(room_id) ON DELETE CASCADE
                )
            """)

            # Pomodoro Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    session_type TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_minutes INTEGER,
                    completed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (room_id) REFERENCES virtual_study_rooms(room_id) ON DELETE CASCADE
                )
            """)

            # Anonymous Q&A Board table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS qa_board (
                    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    student_id TEXT NOT NULL,
                    anonymous_id TEXT NOT NULL,
                    question_title TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    category TEXT DEFAULT 'General',
                    difficulty_level TEXT DEFAULT 'Medium',
                    upvotes INTEGER DEFAULT 0,
                    downvotes INTEGER DEFAULT 0,
                    view_count INTEGER DEFAULT 0,
                    is_answered BOOLEAN DEFAULT 0,
                    is_resolved BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Q&A Answers table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS qa_answers (
                    answer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    student_id TEXT NOT NULL,
                    anonymous_id TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    upvotes INTEGER DEFAULT 0,
                    downvotes INTEGER DEFAULT 0,
                    is_accepted BOOLEAN DEFAULT 0,
                    is_instructor_answer BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES qa_board(question_id) ON DELETE CASCADE
                )
            """)

            # Q&A Votes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS qa_votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id INTEGER NOT NULL,
                    vote_type TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(student_id, target_type, target_id)
                )
            """)

            # Study Match Suggestions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_match_suggestions (
                    suggestion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    suggested_student_id TEXT NOT NULL,
                    course_id TEXT,
                    compatibility_score REAL DEFAULT 0.0,
                    match_reason TEXT,
                    status TEXT DEFAULT 'Pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    responded_at TEXT
                )
            """)

            log_activity('create', 'study_matching_tables',
                        details={'status': 'Study Matching tables created'})

    # ========== Study Profile Management ==========

    def create_study_profile(self, student_id: str, study_style: str = "Visual",
                            preferred_time: str = "Evening",
                            group_size_preference: str = "Small",
                            communication_style: str = "Collaborative",
                            noise_preference: str = "Quiet",
                            availability: Optional[List[str]] = None,
                            interests: Optional[List[str]] = None) -> int:
        """
        Create or update a student's study profile for matching.

        Args:
            student_id: Student's ID
            study_style: Visual, Auditory, Kinesthetic, or Reading/Writing
            preferred_time: Morning, Afternoon, Evening, or Night
            group_size_preference: Solo, Small (2-4), Medium (5-8), or Large (9+)
            communication_style: Collaborative, Independent, or Mixed
            noise_preference: Quiet, Moderate, or Lively
            availability: List of available days/times
            interests: List of academic interests

        Returns:
            Profile ID
        """
        availability_json = json.dumps(availability or [])
        interests_json = json.dumps(interests or [])

        with transaction() as conn:
            # Check if profile exists
            existing = conn.execute("""
                SELECT profile_id FROM study_profiles WHERE student_id = ?
            """, (student_id,)).fetchone()

            if existing:
                # Update existing profile
                conn.execute("""
                    UPDATE study_profiles
                    SET study_style = ?, preferred_time = ?,
                        group_size_preference = ?, communication_style = ?,
                        noise_preference = ?, availability_json = ?,
                        interests_json = ?, updated_at = ?
                    WHERE student_id = ?
                """, (study_style, preferred_time, group_size_preference,
                      communication_style, noise_preference, availability_json,
                      interests_json, datetime.now().isoformat(), student_id))
                profile_id = existing['profile_id']
            else:
                # Create new profile
                cursor = conn.execute("""
                    INSERT INTO study_profiles
                    (student_id, study_style, preferred_time, group_size_preference,
                     communication_style, noise_preference, availability_json, interests_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (student_id, study_style, preferred_time, group_size_preference,
                      communication_style, noise_preference, availability_json, interests_json))
                profile_id = cursor.lastrowid

            log_activity('create', 'study_profile',
                        details={'student_id': student_id, 'profile_id': profile_id})

            return profile_id

    def get_study_profile(self, student_id: str) -> Optional[Dict]:
        """Get a student's study profile."""
        with get_connection() as conn:
            profile = conn.execute("""
                SELECT * FROM study_profiles WHERE student_id = ?
            """, (student_id,)).fetchone()

            if not profile:
                return None

            profile_dict = dict(profile)
            profile_dict['availability'] = json.loads(profile_dict['availability_json'])
            profile_dict['interests'] = json.loads(profile_dict['interests_json'])
            del profile_dict['availability_json']
            del profile_dict['interests_json']

            return profile_dict

    # ========== Study Matching Algorithm ==========

    def find_study_matches(self, student_id: str, course_id: Optional[str] = None,
                          limit: int = 10) -> List[Dict]:
        """
        Find compatible study partners using intelligent matching algorithm.

        Args:
            student_id: Student's ID
            course_id: Course to find matches for (optional)
            limit: Maximum number of matches to return

        Returns:
            List of matched students with compatibility scores
        """
        with get_connection() as conn:
            # Get student's profile
            student_profile = self.get_study_profile(student_id)
            if not student_profile:
                return []

            # Find potential matches
            query = """
                SELECT sp.student_id, sp.study_style, sp.preferred_time,
                       sp.group_size_preference, sp.communication_style,
                       sp.noise_preference, sp.availability_json, sp.interests_json,
                       s.first_name, s.last_name
                FROM study_profiles sp
                LEFT JOIN students s ON sp.student_id = s.student_id
                WHERE sp.student_id != ?
            """
            params = [student_id]

            if course_id:
                query += """
                    AND sp.student_id IN (
                        SELECT student_id FROM student_modules WHERE module_code = ?
                    )
                """
                params.append(course_id)

            candidates = conn.execute(query, params).fetchall()

            # Calculate compatibility scores
            matches = []
            for candidate in candidates:
                score = self._calculate_compatibility_score(
                    student_profile, dict(candidate)
                )

                if score > 0.3:  # Minimum compatibility threshold
                    matches.append({
                        'student_id': candidate['student_id'],
                        'name': f"{candidate['first_name']} {candidate['last_name']}",
                        'compatibility_score': round(score * 100, 1),
                        'study_style': candidate['study_style'],
                        'preferred_time': candidate['preferred_time'],
                        'match_reason': self._generate_match_reason(
                            student_profile, dict(candidate)
                        )
                    })

            # Sort by compatibility score
            matches.sort(key=lambda x: x['compatibility_score'], reverse=True)

            log_activity('view', 'study_matches', details={
                'student_id': student_id,
                'matches_found': len(matches[:limit])
            })

            return matches[:limit]

    def _calculate_compatibility_score(self, profile1: Dict, profile2: Dict) -> float:
        """Calculate compatibility score between two study profiles."""
        score = 0.0
        weights = {
            'study_style': 0.25,
            'preferred_time': 0.20,
            'group_size_preference': 0.15,
            'communication_style': 0.20,
            'noise_preference': 0.10,
            'interests': 0.10
        }

        # Exact matches
        if profile1['study_style'] == profile2['study_style']:
            score += weights['study_style']

        if profile1['preferred_time'] == profile2['preferred_time']:
            score += weights['preferred_time']

        if profile1['group_size_preference'] == profile2['group_size_preference']:
            score += weights['group_size_preference']

        if profile1['communication_style'] == profile2['communication_style']:
            score += weights['communication_style']

        if profile1['noise_preference'] == profile2['noise_preference']:
            score += weights['noise_preference']

        # Interest overlap
        interests1 = set(profile1.get('interests', []))
        interests2 = set(json.loads(profile2.get('interests_json', '[]')))
        if interests1 and interests2:
            overlap = len(interests1 & interests2) / max(len(interests1), len(interests2))
            score += overlap * weights['interests']

        return score

    def _generate_match_reason(self, profile1: Dict, profile2: Dict) -> str:
        """Generate a human-readable reason for the match."""
        reasons = []

        if profile1['study_style'] == profile2['study_style']:
            reasons.append(f"Both prefer {profile1['study_style']} learning")

        if profile1['preferred_time'] == profile2['preferred_time']:
            reasons.append(f"Both study in the {profile1['preferred_time']}")

        if profile1['communication_style'] == profile2['communication_style']:
            reasons.append(f"Similar {profile1['communication_style'].lower()} approach")

        interests1 = set(profile1.get('interests', []))
        interests2 = set(json.loads(profile2.get('interests_json', '[]')))
        common = interests1 & interests2
        if common:
            reasons.append(f"Shared interests: {', '.join(list(common)[:2])}")

        return " • ".join(reasons) if reasons else "Compatible study preferences"

    def create_match_suggestion(self, student_id: str, suggested_student_id: str,
                               course_id: Optional[str] = None) -> int:
        """Create a study match suggestion."""
        # Calculate compatibility
        profile1 = self.get_study_profile(student_id)
        profile2 = self.get_study_profile(suggested_student_id)

        if not profile1 or not profile2:
            raise ValueError("Both students must have study profiles")

        score = self._calculate_compatibility_score(profile1, profile2)
        reason = self._generate_match_reason(profile1, profile2)

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO study_match_suggestions
                (student_id, suggested_student_id, course_id, compatibility_score, match_reason)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, suggested_student_id, course_id, score, reason))

            suggestion_id = cursor.lastrowid

            log_activity('create', 'match_suggestion',
                        details={'from': student_id, 'to': suggested_student_id, 'suggestion_id': suggestion_id})

            return suggestion_id

    # ========== Study Group Management ==========

    def create_study_group(self, course_id: str, group_name: str, creator_id: str,
                          max_members: int = 6, meeting_schedule: Optional[str] = None,
                          location: Optional[str] = None, is_virtual: bool = True) -> int:
        """
        Create a new study group.

        Args:
            course_id: Course ID
            group_name: Name of the group
            creator_id: Student creating the group
            max_members: Maximum number of members
            meeting_schedule: Meeting schedule description
            location: Physical location or virtual platform
            is_virtual: Whether the group meets virtually

        Returns:
            Group ID
        """
        with transaction() as conn:
            # Create group
            cursor = conn.execute("""
                INSERT INTO study_groups
                (course_id, group_name, creator_id, max_members,
                 meeting_schedule, location, is_virtual)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (course_id, group_name, creator_id, max_members,
                  meeting_schedule, location, is_virtual))

            group_id = cursor.lastrowid

            # Add creator as first member with Admin role
            conn.execute("""
                INSERT INTO study_group_members
                (group_id, student_id, role)
                VALUES (?, ?, 'Admin')
            """, (group_id, creator_id))

            log_activity('create', 'study_group',
                        details={'name': group_name, 'creator': creator_id, 'group_id': group_id})

            return group_id

    def join_study_group(self, group_id: int, student_id: str) -> bool:
        """Join an existing study group."""
        with transaction() as conn:
            # Check if group is full
            group = conn.execute("""
                SELECT max_members, current_members
                FROM study_groups WHERE group_id = ?
            """, (group_id,)).fetchone()

            if not group:
                raise ValueError("Study group not found")

            if group['current_members'] >= group['max_members']:
                raise ValueError("Study group is full")

            # Check if already a member
            existing = conn.execute("""
                SELECT membership_id FROM study_group_members
                WHERE group_id = ? AND student_id = ?
            """, (group_id, student_id)).fetchone()

            if existing:
                return False

            # Add member
            conn.execute("""
                INSERT INTO study_group_members (group_id, student_id)
                VALUES (?, ?)
            """, (group_id, student_id))

            # Update member count
            conn.execute("""
                UPDATE study_groups
                SET current_members = current_members + 1
                WHERE group_id = ?
            """, (group_id,))

            log_activity('create', 'group_membership',
                        details={'student_id': student_id, 'group_id': group_id})

            return True

    def get_study_group(self, group_id: int) -> Optional[Dict]:
        """Get study group details with members."""
        with get_connection() as conn:
            group = conn.execute("""
                SELECT * FROM study_groups WHERE group_id = ?
            """, (group_id,)).fetchone()

            if not group:
                return None

            members = conn.execute("""
                SELECT sgm.*, s.first_name, s.last_name
                FROM study_group_members sgm
                LEFT JOIN students s ON sgm.student_id = s.student_id
                WHERE sgm.group_id = ?
                ORDER BY sgm.role DESC, sgm.joined_at
            """, (group_id,)).fetchall()

            return {
                'group': dict(group),
                'members': [dict(m) for m in members]
            }

    def get_student_study_groups(self, student_id: str) -> List[Dict]:
        """Get all study groups a student is a member of."""
        with get_connection() as conn:
            groups = conn.execute("""
                SELECT sg.*, sgm.role, sgm.joined_at
                FROM study_groups sg
                JOIN study_group_members sgm ON sg.group_id = sgm.group_id
                WHERE sgm.student_id = ?
                ORDER BY sgm.joined_at DESC
            """, (student_id,)).fetchall()

            return [dict(g) for g in groups]

    def get_available_study_groups(self, course_id: str) -> List[Dict]:
        """Get available study groups for a course."""
        with get_connection() as conn:
            groups = conn.execute("""
                SELECT * FROM study_groups
                WHERE course_id = ?
                AND current_members < max_members
                AND status = 'Active'
                ORDER BY created_at DESC
            """, (course_id,)).fetchall()

            return [dict(g) for g in groups]

    # ========== Virtual Study Rooms ==========

    def create_virtual_study_room(self, host_id: str, room_name: str,
                                  course_id: Optional[str] = None,
                                  group_id: Optional[int] = None,
                                  max_participants: int = 8,
                                  pomodoro_enabled: bool = True,
                                  work_duration: int = 25,
                                  break_duration: int = 5) -> Dict:
        """
        Create a virtual study room with Pomodoro timer.

        Args:
            host_id: Student hosting the room
            room_name: Name of the study room
            course_id: Course ID (optional)
            group_id: Study group ID (optional)
            max_participants: Maximum number of participants
            pomodoro_enabled: Enable Pomodoro timer
            work_duration: Work duration in minutes (default 25)
            break_duration: Break duration in minutes (default 5)

        Returns:
            Dictionary with room details and access code
        """
        # Generate unique room code
        room_code = self._generate_room_code(host_id, room_name)

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO virtual_study_rooms
                (group_id, room_name, room_code, host_id, course_id,
                 max_participants, pomodoro_enabled, work_duration, break_duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (group_id, room_name, room_code, host_id, course_id,
                  max_participants, pomodoro_enabled, work_duration, break_duration))

            room_id = cursor.lastrowid

            # Add host as first participant
            conn.execute("""
                INSERT INTO study_room_participants
                (room_id, student_id)
                VALUES (?, ?)
            """, (room_id, host_id))

            # Update participant count
            conn.execute("""
                UPDATE virtual_study_rooms
                SET current_participants = 1
                WHERE room_id = ?
            """, (room_id,))

            log_activity('create', 'virtual_study_room',
                        details={'name': room_name, 'host': host_id, 'room_id': room_id})

            return {
                'room_id': room_id,
                'room_code': room_code,
                'room_name': room_name,
                'pomodoro_enabled': pomodoro_enabled
            }

    def _generate_room_code(self, host_id: str, room_name: str) -> str:
        """Generate a unique 6-character room code."""
        unique_string = f"{host_id}{room_name}{datetime.now().isoformat()}"
        hash_object = hashlib.sha256(unique_string.encode())
        return hash_object.hexdigest()[:6].upper()

    def join_virtual_study_room(self, room_code: str, student_id: str) -> Dict:
        """Join a virtual study room using room code."""
        with transaction() as conn:
            # Find room
            room = conn.execute("""
                SELECT * FROM virtual_study_rooms
                WHERE room_code = ? AND is_active = 1
            """, (room_code,)).fetchone()

            if not room:
                raise ValueError("Invalid room code or room is closed")

            if room['current_participants'] >= room['max_participants']:
                raise ValueError("Room is full")

            # Check if already in room
            existing = conn.execute("""
                SELECT participant_id FROM study_room_participants
                WHERE room_id = ? AND student_id = ? AND is_currently_active = 1
            """, (room['room_id'], student_id)).fetchone()

            if not existing:
                # Add participant
                conn.execute("""
                    INSERT INTO study_room_participants
                    (room_id, student_id)
                    VALUES (?, ?)
                """, (room['room_id'], student_id))

                # Update participant count
                conn.execute("""
                    UPDATE virtual_study_rooms
                    SET current_participants = current_participants + 1
                    WHERE room_id = ?
                """, (room['room_id'],))

            log_activity('create', 'room_participant',
                        details={'room_id': room['room_id'], 'student_id': student_id})

            return dict(room)

    def leave_virtual_study_room(self, room_id: int, student_id: str) -> bool:
        """Leave a virtual study room."""
        with transaction() as conn:
            # Update participant status
            conn.execute("""
                UPDATE study_room_participants
                SET is_currently_active = 0, left_at = ?
                WHERE room_id = ? AND student_id = ? AND is_currently_active = 1
            """, (datetime.now().isoformat(), room_id, student_id))

            # Update participant count
            conn.execute("""
                UPDATE virtual_study_rooms
                SET current_participants = current_participants - 1
                WHERE room_id = ?
            """, (room_id,))

            log_activity('update', 'room_participant',
                        details={'student_id': student_id, 'action': 'left', 'room_id': room_id})

            return True

    def get_active_study_rooms(self, course_id: Optional[str] = None) -> List[Dict]:
        """Get all active virtual study rooms."""
        with get_connection() as conn:
            query = """
                SELECT vsr.*, s.first_name, s.last_name
                FROM virtual_study_rooms vsr
                LEFT JOIN students s ON vsr.host_id = s.student_id
                WHERE vsr.is_active = 1
            """
            params = []

            if course_id:
                query += " AND vsr.course_id = ?"
                params.append(course_id)

            query += " ORDER BY vsr.created_at DESC"

            rooms = conn.execute(query, params).fetchall()
            return [dict(r) for r in rooms]

    # ========== Pomodoro Timer ==========

    def start_pomodoro_session(self, room_id: int, student_id: str,
                               session_type: str = "work") -> int:
        """
        Start a Pomodoro session (work or break).

        Args:
            room_id: Virtual study room ID
            student_id: Student's ID
            session_type: 'work' or 'break'

        Returns:
            Session ID
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO pomodoro_sessions
                (room_id, student_id, session_type, start_time)
                VALUES (?, ?, ?, ?)
            """, (room_id, student_id, session_type, datetime.now().isoformat()))

            session_id = cursor.lastrowid

            log_activity('create', 'pomodoro_session',
                        details={'type': session_type, 'session_id': session_id})

            return session_id

    def complete_pomodoro_session(self, session_id: int) -> bool:
        """Mark a Pomodoro session as completed."""
        with transaction() as conn:
            # Get session start time
            session = conn.execute("""
                SELECT start_time, session_type, room_id, student_id
                FROM pomodoro_sessions WHERE session_id = ?
            """, (session_id,)).fetchone()

            if not session:
                return False

            start_time = datetime.fromisoformat(session['start_time'])
            duration = int((datetime.now() - start_time).total_seconds() / 60)

            # Update session
            conn.execute("""
                UPDATE pomodoro_sessions
                SET end_time = ?, duration_minutes = ?, completed = 1
                WHERE session_id = ?
            """, (datetime.now().isoformat(), duration, session_id))

            # Update participant stats
            if session['session_type'] == 'work':
                conn.execute("""
                    UPDATE study_room_participants
                    SET pomodoro_sessions_completed = pomodoro_sessions_completed + 1,
                        total_time_minutes = total_time_minutes + ?
                    WHERE room_id = ? AND student_id = ?
                """, (duration, session['room_id'], session['student_id']))

                # Update room session count
                conn.execute("""
                    UPDATE virtual_study_rooms
                    SET session_count = session_count + 1
                    WHERE room_id = ?
                """, (session['room_id'],))

            log_activity('update', 'pomodoro_session',
                        details={'completed': True, 'duration': duration, 'session_id': session_id})

            return True

    def get_student_pomodoro_stats(self, student_id: str) -> Dict:
        """Get Pomodoro statistics for a student."""
        with get_connection() as conn:
            stats = conn.execute("""
                SELECT
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_sessions,
                    SUM(duration_minutes) as total_minutes,
                    AVG(duration_minutes) as avg_session_duration
                FROM pomodoro_sessions
                WHERE student_id = ? AND session_type = 'work'
            """, (student_id,)).fetchone()

            return dict(stats) if stats else {}

    # ========== Anonymous Q&A Board ==========

    def post_question(self, course_id: str, student_id: str, question_title: str,
                     question_text: str, category: str = "General",
                     difficulty_level: str = "Medium") -> Dict:
        """
        Post an anonymous question to the course Q&A board.

        Args:
            course_id: Course ID
            student_id: Student's ID (kept private)
            question_title: Question title
            question_text: Full question text
            category: Question category
            difficulty_level: Easy, Medium, or Hard

        Returns:
            Dictionary with question details and anonymous ID
        """
        # Generate anonymous ID
        anonymous_id = self._generate_anonymous_id(student_id, course_id)

        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO qa_board
                (course_id, student_id, anonymous_id, question_title,
                 question_text, category, difficulty_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (course_id, student_id, anonymous_id, question_title,
                  question_text, category, difficulty_level))

            question_id = cursor.lastrowid

            log_activity('create', 'qa_question',
                        details={'course_id': course_id, 'category': category, 'question_id': question_id})

            return {
                'question_id': question_id,
                'anonymous_id': anonymous_id,
                'title': question_title
            }

    def _generate_anonymous_id(self, student_id: str, course_id: str) -> str:
        """Generate a consistent anonymous ID for a student in a course."""
        unique_string = f"{student_id}{course_id}"
        hash_object = hashlib.sha256(unique_string.encode())
        return f"User_{hash_object.hexdigest()[:8]}"

    def post_answer(self, question_id: int, student_id: str, answer_text: str,
                   is_instructor: bool = False) -> int:
        """
        Post an anonymous answer to a question.

        Args:
            question_id: Question ID
            student_id: Student's ID (kept private)
            answer_text: Answer text
            is_instructor: Whether the answer is from an instructor

        Returns:
            Answer ID
        """
        with transaction() as conn:
            # Get course_id for anonymous ID
            question = conn.execute("""
                SELECT course_id FROM qa_board WHERE question_id = ?
            """, (question_id,)).fetchone()

            if not question:
                raise ValueError("Question not found")

            anonymous_id = self._generate_anonymous_id(student_id, question['course_id'])

            cursor = conn.execute("""
                INSERT INTO qa_answers
                (question_id, student_id, anonymous_id, answer_text, is_instructor_answer)
                VALUES (?, ?, ?, ?, ?)
            """, (question_id, student_id, anonymous_id, answer_text, is_instructor))

            answer_id = cursor.lastrowid

            # Mark question as answered
            conn.execute("""
                UPDATE qa_board
                SET is_answered = 1, updated_at = ?
                WHERE question_id = ?
            """, (datetime.now().isoformat(), question_id))

            log_activity('create', 'qa_answer',
                        details={'question_id': question_id, 'answer_id': answer_id})

            return answer_id

    def vote_on_content(self, student_id: str, target_type: str, target_id: int,
                       vote_type: str) -> bool:
        """
        Vote on a question or answer.

        Args:
            student_id: Student's ID
            target_type: 'question' or 'answer'
            target_id: Question or answer ID
            vote_type: 'upvote' or 'downvote'

        Returns:
            Success status
        """
        with transaction() as conn:
            # Check if already voted
            existing = conn.execute("""
                SELECT vote_id, vote_type FROM qa_votes
                WHERE student_id = ? AND target_type = ? AND target_id = ?
            """, (student_id, target_type, target_id)).fetchone()

            if existing:
                # Remove old vote
                old_vote = existing['vote_type']
                conn.execute("""
                    DELETE FROM qa_votes
                    WHERE vote_id = ?
                """, (existing['vote_id'],))

                # Decrement old vote count
                if target_type == 'question':
                    field = 'upvotes' if old_vote == 'upvote' else 'downvotes'
                    safe_field = validate_identifier(field, "column")
                    conn.execute(
                        "UPDATE qa_board"
                        " SET " + safe_field + " = " + safe_field + " - 1"
                        " WHERE question_id = ?",
                        (target_id,))
                else:
                    field = 'upvotes' if old_vote == 'upvote' else 'downvotes'
                    safe_field = validate_identifier(field, "column")
                    conn.execute(
                        "UPDATE qa_answers"
                        " SET " + safe_field + " = " + safe_field + " - 1"
                        " WHERE answer_id = ?",
                        (target_id,))

                # If same vote type, just remove (toggle off)
                if old_vote == vote_type:
                    return True

            # Add new vote
            conn.execute("""
                INSERT INTO qa_votes
                (student_id, target_type, target_id, vote_type)
                VALUES (?, ?, ?, ?)
            """, (student_id, target_type, target_id, vote_type))

            # Increment vote count
            if target_type == 'question':
                field = 'upvotes' if vote_type == 'upvote' else 'downvotes'
                safe_field = validate_identifier(field, "column")
                conn.execute(
                    "UPDATE qa_board"
                    " SET " + safe_field + " = " + safe_field + " + 1"
                    " WHERE question_id = ?",
                    (target_id,))
            else:
                field = 'upvotes' if vote_type == 'upvote' else 'downvotes'
                safe_field = validate_identifier(field, "column")
                conn.execute(
                    "UPDATE qa_answers"
                    " SET " + safe_field + " = " + safe_field + " + 1"
                    " WHERE answer_id = ?",
                    (target_id,))

            log_activity('create', 'qa_vote', details={
                'target_type': target_type,
                'target_id': target_id,
                'vote_type': vote_type
            })

            return True

    def get_course_questions(self, course_id: str, category: Optional[str] = None,
                            sort_by: str = "recent") -> List[Dict]:
        """
        Get questions from the Q&A board.

        Args:
            course_id: Course ID
            category: Filter by category (optional)
            sort_by: 'recent', 'popular', or 'unanswered'

        Returns:
            List of questions with answer counts
        """
        with get_connection() as conn:
            query = """
                SELECT q.*,
                       COUNT(DISTINCT a.answer_id) as answer_count
                FROM qa_board q
                LEFT JOIN qa_answers a ON q.question_id = a.question_id
                WHERE q.course_id = ?
            """
            params = [course_id]

            if category:
                query += " AND q.category = ?"
                params.append(category)

            query += " GROUP BY q.question_id"

            # Add sorting
            if sort_by == "popular":
                query += " ORDER BY (q.upvotes - q.downvotes) DESC, q.view_count DESC"
            elif sort_by == "unanswered":
                query += " HAVING answer_count = 0 ORDER BY q.created_at DESC"
            else:  # recent
                query += " ORDER BY q.created_at DESC"

            questions = conn.execute(query, params).fetchall()
            return [dict(q) for q in questions]

    def get_question_with_answers(self, question_id: int) -> Optional[Dict]:
        """Get a question with all its answers."""
        with transaction() as conn:
            # Increment view count
            conn.execute("""
                UPDATE qa_board
                SET view_count = view_count + 1
                WHERE question_id = ?
            """, (question_id,))

            # Get question
            question = conn.execute("""
                SELECT * FROM qa_board WHERE question_id = ?
            """, (question_id,)).fetchone()

            if not question:
                return None

            # Get answers
            answers = conn.execute("""
                SELECT * FROM qa_answers
                WHERE question_id = ?
                ORDER BY is_accepted DESC, (upvotes - downvotes) DESC, created_at
            """, (question_id,)).fetchall()

            return {
                'question': dict(question),
                'answers': [dict(a) for a in answers]
            }

    def mark_answer_accepted(self, answer_id: int, question_id: int) -> bool:
        """Mark an answer as accepted (only question author can do this)."""
        with transaction() as conn:
            # Unmark any previously accepted answers
            conn.execute("""
                UPDATE qa_answers
                SET is_accepted = 0
                WHERE question_id = ?
            """, (question_id,))

            # Mark new answer as accepted
            conn.execute("""
                UPDATE qa_answers
                SET is_accepted = 1
                WHERE answer_id = ?
            """, (answer_id,))

            # Mark question as resolved
            conn.execute("""
                UPDATE qa_board
                SET is_resolved = 1
                WHERE question_id = ?
            """, (question_id,))

            log_activity('update', 'qa_answer',
                        details={'accepted': True, 'answer_id': answer_id})

            return True

    # ========== Analytics ==========

    def get_study_matching_analytics(self, student_id: str) -> Dict:
        """Get comprehensive study matching analytics for a student."""
        with get_connection() as conn:
            # Group membership stats
            group_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_groups,
                    SUM(CASE WHEN sg.status = 'Active' THEN 1 ELSE 0 END) as active_groups,
                    AVG(sgm.contribution_score) as avg_contribution,
                    SUM(sgm.attendance_count) as total_attendance
                FROM study_group_members sgm
                JOIN study_groups sg ON sgm.group_id = sg.group_id
                WHERE sgm.student_id = ?
            """, (student_id,)).fetchone()

            # Virtual room stats
            room_stats = conn.execute("""
                SELECT
                    COUNT(DISTINCT room_id) as rooms_joined,
                    SUM(total_time_minutes) as total_study_time,
                    SUM(pomodoro_sessions_completed) as total_pomodoros
                FROM study_room_participants
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            # Q&A participation
            qa_stats = conn.execute("""
                SELECT
                    (SELECT COUNT(*) FROM qa_board WHERE student_id = ?) as questions_asked,
                    (SELECT COUNT(*) FROM qa_answers WHERE student_id = ?) as answers_given,
                    (SELECT SUM(upvotes) FROM qa_board WHERE student_id = ?) as question_upvotes,
                    (SELECT SUM(upvotes) FROM qa_answers WHERE student_id = ?) as answer_upvotes
            """, (student_id, student_id, student_id, student_id)).fetchone()

            return {
                'groups': dict(group_stats) if group_stats else {},
                'virtual_rooms': dict(room_stats) if room_stats else {},
                'qa_participation': dict(qa_stats) if qa_stats else {}
            }
