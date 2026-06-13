"""
Mental Health & Wellness Service

Provides comprehensive wellness tracking and mental health support.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity

class WellnessService:
    """Service for mental health and wellness tracking."""

    def __init__(self):
        """Initialize the Wellness Service."""
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Wellness check-ins table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wellness_checkins (
                    checkin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    checkin_date TEXT NOT NULL,
                    overall_mood INTEGER CHECK(overall_mood BETWEEN 1 AND 10),
                    stress_level INTEGER CHECK(stress_level BETWEEN 1 AND 10),
                    sleep_quality INTEGER CHECK(sleep_quality BETWEEN 1 AND 10),
                    energy_level INTEGER CHECK(energy_level BETWEEN 1 AND 10),
                    anxiety_level INTEGER CHECK(anxiety_level BETWEEN 1 AND 10),
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Mood tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mood_tracking (
                    mood_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    mood_date TEXT NOT NULL,
                    mood_type TEXT NOT NULL,
                    intensity INTEGER CHECK(intensity BETWEEN 1 AND 5),
                    triggers TEXT,
                    activities TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Sleep tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sleep_tracking (
                    sleep_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    sleep_date TEXT NOT NULL,
                    bedtime TEXT,
                    wake_time TEXT,
                    hours_slept REAL,
                    sleep_quality INTEGER CHECK(sleep_quality BETWEEN 1 AND 5),
                    interruptions INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Wellness goals table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wellness_goals (
                    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    goal_type TEXT NOT NULL,
                    goal_description TEXT NOT NULL,
                    target_value REAL,
                    current_value REAL DEFAULT 0,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT DEFAULT 'Active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Exercise tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exercise_tracking (
                    exercise_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    exercise_date TEXT NOT NULL,
                    exercise_type TEXT NOT NULL,
                    duration_minutes INTEGER,
                    intensity TEXT,
                    calories_burned INTEGER,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Hydration tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS hydration_tracking (
                    hydration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    tracking_date TEXT NOT NULL,
                    glasses_consumed INTEGER DEFAULT 0,
                    daily_goal INTEGER DEFAULT 8,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Crisis resources table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crisis_resources (
                    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_name TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    contact_info TEXT NOT NULL,
                    description TEXT,
                    availability TEXT DEFAULT '24/7',
                    is_active BOOLEAN DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Counseling appointments table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS counseling_appointments (
                    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    appointment_date TEXT NOT NULL,
                    appointment_time TEXT NOT NULL,
                    counselor_name TEXT,
                    appointment_type TEXT,
                    status TEXT DEFAULT 'Scheduled',
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Wellness gamification points
            conn.execute("""
                CREATE TABLE IF NOT EXISTS wellness_points (
                    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    points_earned INTEGER DEFAULT 0,
                    activity_type TEXT NOT NULL,
                    activity_description TEXT,
                    earned_date TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                )
            """)

            # Insert default crisis resources
            conn.execute("""
                INSERT OR IGNORE INTO crisis_resources (resource_id, resource_name, resource_type, contact_info, description)
                VALUES
                (1, 'National Suicide Prevention Lifeline', 'Crisis Hotline', '988', 'Free, confidential support 24/7'),
                (2, 'Crisis Text Line', 'Text Support', 'Text HOME to 741741', 'Free crisis counseling via text'),
                (3, 'Campus Counseling Center', 'On-Campus', '555-0100', 'Free counseling for students'),
                (4, 'Campus Security', 'Emergency', '555-0911', '24/7 campus emergency response')
            """)

            log_activity('create', 'wellness_tables', details={'status': 'Wellness tables created'})

    # ========== Wellness Check-ins ==========

    def create_checkin(self, student_id: str, overall_mood: int, stress_level: int,
                      sleep_quality: int, energy_level: int, anxiety_level: int,
                      notes: Optional[str] = None) -> int:
        """Create a wellness check-in."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO wellness_checkins
                (student_id, checkin_date, overall_mood, stress_level, sleep_quality,
                 energy_level, anxiety_level, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, datetime.now().strftime('%Y-%m-%d'), overall_mood,
                  stress_level, sleep_quality, energy_level, anxiety_level, notes))

            checkin_id = cursor.lastrowid

            # Award points for checking in
            self._award_points(student_id, 10, 'wellness_checkin', 'Completed wellness check-in', conn=conn)

            log_activity('create', 'wellness_checkin',
                        details={'checkin_id': checkin_id, 'student_id': student_id})

            return checkin_id

    def get_recent_checkins(self, student_id: str, days: int = 30) -> List[Dict]:
        """Get recent wellness check-ins."""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        with get_connection() as conn:
            checkins = conn.execute("""
                SELECT * FROM wellness_checkins
                WHERE student_id = ? AND checkin_date >= ?
                ORDER BY checkin_date DESC
            """, (student_id, cutoff_date)).fetchall()

            return [dict(row) for row in checkins]

    def analyze_wellness_patterns(self, student_id: str, days: int = 30) -> Dict:
        """Analyze wellness patterns and detect trends."""
        checkins = self.get_recent_checkins(student_id, days)

        if not checkins:
            return {'message': 'No check-in data available'}

        # Calculate averages
        avg_mood = sum(c['overall_mood'] for c in checkins) / len(checkins)
        avg_stress = sum(c['stress_level'] for c in checkins) / len(checkins)
        avg_sleep = sum(c['sleep_quality'] for c in checkins) / len(checkins)
        avg_energy = sum(c['energy_level'] for c in checkins) / len(checkins)
        avg_anxiety = sum(c['anxiety_level'] for c in checkins) / len(checkins)

        # Detect concerning patterns
        concerns = []
        if avg_stress >= 7:
            concerns.append("High stress levels detected")
        if avg_anxiety >= 7:
            concerns.append("Elevated anxiety levels")
        if avg_sleep <= 4:
            concerns.append("Poor sleep quality")
        if avg_energy <= 4:
            concerns.append("Low energy levels")

        return {
            'period_days': days,
            'total_checkins': len(checkins),
            'averages': {
                'mood': round(avg_mood, 1),
                'stress': round(avg_stress, 1),
                'sleep_quality': round(avg_sleep, 1),
                'energy': round(avg_energy, 1),
                'anxiety': round(avg_anxiety, 1)
            },
            'concerns': concerns,
            'recommendation': 'Consider scheduling a counseling appointment' if concerns else 'Keep up the great work!'
        }

    # ========== Mood Tracking ==========

    def log_mood(self, student_id: str, mood_type: str, intensity: int,
                 triggers: Optional[str] = None, activities: Optional[str] = None,
                 notes: Optional[str] = None) -> int:
        """Log a mood entry."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO mood_tracking
                (student_id, mood_date, mood_type, intensity, triggers, activities, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_id, datetime.now().strftime('%Y-%m-%d'), mood_type,
                  intensity, triggers, activities, notes))

            mood_id = cursor.lastrowid

            # Award points
            self._award_points(student_id, 5, 'mood_tracking', 'Logged mood', conn=conn)

            log_activity('create', 'mood_log',
                        details={'mood_id': mood_id, 'mood_type': mood_type})

            return mood_id

    def get_mood_history(self, student_id: str, days: int = 30) -> List[Dict]:
        """Get mood history."""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        with get_connection() as conn:
            moods = conn.execute("""
                SELECT * FROM mood_tracking
                WHERE student_id = ? AND mood_date >= ?
                ORDER BY mood_date DESC, created_at DESC
            """, (student_id, cutoff_date)).fetchall()

            return [dict(row) for row in moods]

    # ========== Sleep Tracking ==========

    def log_sleep(self, student_id: str, sleep_date: str, bedtime: str,
                  wake_time: str, hours_slept: float, sleep_quality: int,
                  interruptions: int = 0, notes: Optional[str] = None) -> int:
        """Log sleep data."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO sleep_tracking
                (student_id, sleep_date, bedtime, wake_time, hours_slept,
                 sleep_quality, interruptions, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, sleep_date, bedtime, wake_time, hours_slept,
                  sleep_quality, interruptions, notes))

            sleep_id = cursor.lastrowid

            # Award points for tracking sleep
            self._award_points(student_id, 5, 'sleep_tracking', 'Logged sleep', conn=conn)

            # Bonus points for good sleep
            if hours_slept >= 7 and sleep_quality >= 4:
                self._award_points(student_id, 10, 'quality_sleep', 'Quality sleep achieved', conn=conn)

            log_activity('create', 'sleep_log',
                        details={'sleep_id': sleep_id, 'hours': hours_slept})

            return sleep_id

    def get_sleep_analytics(self, student_id: str, days: int = 30) -> Dict:
        """Get sleep analytics."""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        with get_connection() as conn:
            sleep_data = conn.execute("""
                SELECT * FROM sleep_tracking
                WHERE student_id = ? AND sleep_date >= ?
                ORDER BY sleep_date
            """, (student_id, cutoff_date)).fetchall()

            if not sleep_data:
                return {'message': 'No sleep data available'}

            avg_hours = sum(s['hours_slept'] for s in sleep_data) / len(sleep_data)
            avg_quality = sum(s['sleep_quality'] for s in sleep_data) / len(sleep_data)
            total_interruptions = sum(s['interruptions'] for s in sleep_data)

            return {
                'period_days': days,
                'nights_tracked': len(sleep_data),
                'average_hours': round(avg_hours, 1),
                'average_quality': round(avg_quality, 1),
                'total_interruptions': total_interruptions,
                'recommendation': 'Aim for 7-9 hours per night' if avg_hours < 7 else 'Great sleep habits!'
            }

    # ========== Wellness Goals ==========

    def create_wellness_goal(self, student_id: str, goal_type: str,
                            goal_description: str, target_value: float,
                            end_date: Optional[str] = None) -> int:
        """Create a wellness goal."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO wellness_goals
                (student_id, goal_type, goal_description, target_value, start_date, end_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, goal_type, goal_description, target_value,
                  datetime.now().strftime('%Y-%m-%d'), end_date))

            goal_id = cursor.lastrowid

            log_activity('create', 'wellness_goal', goal_id=goal_id,
                        details={'type': goal_type})

            return goal_id

    def update_goal_progress(self, goal_id: int, new_value: float) -> bool:
        """Update progress on a wellness goal."""
        with transaction() as conn:
            # Get goal details
            goal = conn.execute("""
                SELECT target_value, student_id FROM wellness_goals WHERE goal_id = ?
            """, (goal_id,)).fetchone()

            if not goal:
                return False

            # Update current value
            conn.execute("""
                UPDATE wellness_goals
                SET current_value = ?
                WHERE goal_id = ?
            """, (new_value, goal_id))

            # Check if goal achieved
            if new_value >= goal['target_value']:
                conn.execute("""
                    UPDATE wellness_goals
                    SET status = 'Achieved'
                    WHERE goal_id = ?
                """, (goal_id,))

                # Award bonus points
                self._award_points(goal['student_id'], 50, 'goal_achieved',
                                 'Wellness goal achieved!', conn=conn)

            log_activity('update', 'wellness_goal',
                        details={'goal_id': goal_id, 'new_value': new_value})

            return True

    def get_active_goals(self, student_id: str) -> List[Dict]:
        """Get active wellness goals."""
        with get_connection() as conn:
            goals = conn.execute("""
                SELECT * FROM wellness_goals
                WHERE student_id = ? AND status = 'Active'
                ORDER BY created_at DESC
            """, (student_id,)).fetchall()

            return [dict(row) for row in goals]

    # ========== Exercise & Hydration ==========

    def log_exercise(self, student_id: str, exercise_type: str,
                    duration_minutes: int, intensity: str,
                    calories_burned: Optional[int] = None,
                    notes: Optional[str] = None) -> int:
        """Log an exercise session."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO exercise_tracking
                (student_id, exercise_date, exercise_type, duration_minutes,
                 intensity, calories_burned, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_id, datetime.now().strftime('%Y-%m-%d'), exercise_type,
                  duration_minutes, intensity, calories_burned, notes))

            exercise_id = cursor.lastrowid

            # Award points based on duration
            points = min(duration_minutes // 10, 30)  # Max 30 points
            self._award_points(student_id, points, 'exercise', f'{duration_minutes} min exercise', conn=conn)

            log_activity('create', 'exercise_log',
                        details={'exercise_id': exercise_id, 'type': exercise_type, 'duration': duration_minutes})

            return exercise_id

    def log_hydration(self, student_id: str, glasses: int) -> int:
        """Log hydration for today."""
        today = datetime.now().strftime('%Y-%m-%d')

        with transaction() as conn:
            # Check if entry exists for today
            existing = conn.execute("""
                SELECT hydration_id, glasses_consumed FROM hydration_tracking
                WHERE student_id = ? AND tracking_date = ?
            """, (student_id, today)).fetchone()

            if existing:
                # Update existing entry
                new_total = existing['glasses_consumed'] + glasses
                conn.execute("""
                    UPDATE hydration_tracking
                    SET glasses_consumed = ?
                    WHERE hydration_id = ?
                """, (new_total, existing['hydration_id']))

                hydration_id = existing['hydration_id']
            else:
                # Create new entry
                cursor = conn.execute("""
                    INSERT INTO hydration_tracking
                    (student_id, tracking_date, glasses_consumed)
                    VALUES (?, ?, ?)
                """, (student_id, today, glasses))

                hydration_id = cursor.lastrowid

            # Award points (1 point per glass, max 10/day)
            self._award_points(student_id, min(glasses, 10), 'hydration',
                             f'Logged {glasses} glasses of water', conn=conn)

            return hydration_id

    def get_hydration_status(self, student_id: str) -> Dict:
        """Get today's hydration status."""
        today = datetime.now().strftime('%Y-%m-%d')

        with get_connection() as conn:
            status = conn.execute("""
                SELECT glasses_consumed, daily_goal FROM hydration_tracking
                WHERE student_id = ? AND tracking_date = ?
            """, (student_id, today)).fetchone()

            if not status:
                return {'glasses_consumed': 0, 'daily_goal': 8, 'percentage': 0}

            percentage = (status['glasses_consumed'] / status['daily_goal']) * 100

            return {
                'glasses_consumed': status['glasses_consumed'],
                'daily_goal': status['daily_goal'],
                'percentage': round(percentage, 1),
                'goal_met': status['glasses_consumed'] >= status['daily_goal']
            }

    # ========== Crisis Resources ==========

    def get_crisis_resources(self) -> List[Dict]:
        """Get all active crisis resources."""
        with get_connection() as conn:
            resources = conn.execute("""
                SELECT * FROM crisis_resources
                WHERE is_active = 1
                ORDER BY resource_type, resource_name
            """, ()).fetchall()

            return [dict(row) for row in resources]

    def schedule_counseling(self, student_id: str, appointment_date: str,
                           appointment_time: str, appointment_type: str,
                           notes: Optional[str] = None) -> int:
        """Schedule a counseling appointment."""
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO counseling_appointments
                (student_id, appointment_date, appointment_time,
                 appointment_type, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, appointment_date, appointment_time,
                  appointment_type, notes))

            appointment_id = cursor.lastrowid

            log_activity('create', 'counseling_appointment',
                        appointment_id=appointment_id,
                        details={'student_id': student_id, 'date': appointment_date})

            return appointment_id

    def get_counseling_appointments(self, student_id: str) -> List[Dict]:
        """Get counseling appointments for a student."""
        with get_connection() as conn:
            appointments = conn.execute("""
                SELECT * FROM counseling_appointments
                WHERE student_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
                LIMIT 20
            """, (student_id,)).fetchall()

            return [dict(row) for row in appointments]

    def list_all_appointments(self, status: Optional[str] = None,
                              limit: int = 200) -> List[Dict]:
        """Staff view: list every counselling appointment, newest first."""
        with get_connection() as conn:
            if status:
                rows = conn.execute("""
                    SELECT * FROM counseling_appointments
                    WHERE status = ?
                    ORDER BY appointment_date DESC, appointment_time DESC
                    LIMIT ?
                """, (status, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM counseling_appointments
                    ORDER BY appointment_date DESC, appointment_time DESC
                    LIMIT ?
                """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def update_appointment(self, appointment_id: int,
                           status: Optional[str] = None,
                           counselor_name: Optional[str] = None,
                           notes: Optional[str] = None) -> bool:
        """Staff update of an appointment's status / counsellor / outcome notes."""
        fields, values = [], []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if counselor_name is not None:
            fields.append("counselor_name = ?")
            values.append(counselor_name)
        if notes is not None:
            fields.append("notes = ?")
            values.append(notes)
        if not fields:
            return False
        values.append(appointment_id)
        with transaction() as conn:
            conn.execute(
                f"UPDATE counseling_appointments SET {', '.join(fields)} "
                "WHERE appointment_id = ?",
                values,
            )
            log_activity('update', 'counseling_appointment',
                         appointment_id=appointment_id,
                         details={'fields': [f.split(' = ')[0] for f in fields]})
            return True

    # ========== Gamification ==========

    def _award_points(self, student_id: str, points: int, activity_type: str,
                     description: str, conn=None):
        """
        Award wellness points to a student.

        Args:
            student_id: Student ID
            points: Points to award
            activity_type: Type of activity
            description: Activity description
            conn: Optional database connection (if within existing transaction)
        """
        if conn:
            # Use existing connection (within transaction)
            conn.execute("""
                INSERT INTO wellness_points
                (student_id, points_earned, activity_type, activity_description, earned_date)
                VALUES (?, ?, ?, ?, ?)
            """, (student_id, points, activity_type, description,
                  datetime.now().strftime('%Y-%m-%d')))
        else:
            # Create new transaction (standalone call)
            with transaction() as trans_conn:
                trans_conn.execute("""
                    INSERT INTO wellness_points
                    (student_id, points_earned, activity_type, activity_description, earned_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (student_id, points, activity_type, description,
                      datetime.now().strftime('%Y-%m-%d')))

    def get_total_wellness_points(self, student_id: str) -> int:
        """Get total wellness points for a student."""
        with get_connection() as conn:
            result = conn.execute("""
                SELECT SUM(points_earned) as total FROM wellness_points
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            return result['total'] if result['total'] else 0

    def get_wellness_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top wellness point earners."""
        with get_connection() as conn:
            leaderboard = conn.execute("""
                SELECT student_id, SUM(points_earned) as total_points,
                       COUNT(*) as activities
                FROM wellness_points
                GROUP BY student_id
                ORDER BY total_points DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [dict(row) for row in leaderboard]

    # ========== Analytics ==========

    def get_comprehensive_wellness_report(self, student_id: str, days: int = 30) -> Dict:
        """Get comprehensive wellness report."""
        wellness_patterns = self.analyze_wellness_patterns(student_id, days)
        sleep_analytics = self.get_sleep_analytics(student_id, days)
        total_points = self.get_total_wellness_points(student_id)
        active_goals = self.get_active_goals(student_id)

        return {
            'wellness_patterns': wellness_patterns,
            'sleep_analytics': sleep_analytics,
            'total_wellness_points': total_points,
            'active_goals_count': len(active_goals),
            'active_goals': [dict(g) for g in active_goals]
        }
