"""Personalised study recommendations based on exams and weak areas."""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction


class StudyRecommendationService:
    """Service for personalised study recommendations."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    learning_style TEXT DEFAULT 'reading',
                    study_hours_per_week REAL DEFAULT 0,
                    preferred_times TEXT,
                    strengths TEXT,
                    weaknesses TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    module_code TEXT,
                    recommendation_type TEXT DEFAULT 'focus_area',
                    title TEXT NOT NULL,
                    description TEXT,
                    priority TEXT DEFAULT 'medium',
                    is_completed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS study_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    module_code TEXT,
                    topic TEXT,
                    duration_minutes INTEGER DEFAULT 0,
                    effectiveness_rating INTEGER,
                    notes TEXT,
                    studied_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def create_profile(self, student_id: str, learning_style: str = 'reading',
                       study_hours_per_week: float = 0, preferred_times: str = None,
                       strengths: str = None, weaknesses: str = None) -> int:
        import json
        extras = json.dumps({
            'hours_per_week': study_hours_per_week,
            'strengths': strengths or '',
            'weaknesses': weaknesses or '',
        })
        with transaction() as conn:
            # Use actual column names: study_style, preferred_time, interests_json
            existing = conn.execute(
                "SELECT profile_id FROM study_profiles WHERE student_id = ?", (student_id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE study_profiles SET study_style = ?, preferred_time = ?, "
                    "interests_json = ?, updated_at = ? WHERE student_id = ?",
                    (learning_style, preferred_times, extras,
                     datetime.now().isoformat(), student_id)
                )
                conn.commit()
                return existing[0]
            else:
                cursor = conn.execute(
                    "INSERT INTO study_profiles (student_id, study_style, preferred_time, "
                    "interests_json, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (student_id, learning_style, preferred_times, extras,
                     datetime.now().isoformat())
                )
                conn.commit()
                return cursor.lastrowid

    def get_profile(self, student_id: str) -> Optional[Dict]:
        import json
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM study_profiles WHERE student_id = ?", (student_id,)).fetchone()
            if not row:
                return None
            profile = dict(row)
            # Map actual columns to expected keys
            profile['learning_style'] = profile.get('study_style', 'reading')
            try:
                extras = json.loads(profile.get('interests_json', '{}') or '{}')
                if not isinstance(extras, dict):
                    extras = {}
                profile['study_hours_per_week'] = extras.get('hours_per_week', 0)
                profile['strengths'] = extras.get('strengths', '')
                profile['weaknesses'] = extras.get('weaknesses', '')
            except (json.JSONDecodeError, TypeError, ValueError):
                profile['study_hours_per_week'] = 0
                profile['strengths'] = ''
                profile['weaknesses'] = ''
            return profile

    def update_profile(self, student_id: str, **kwargs) -> bool:
        if not kwargs:
            return False
        kwargs['updated_at'] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        with transaction() as conn:
            conn.execute(f"UPDATE study_profiles SET {sets} WHERE student_id = ?", (*kwargs.values(), student_id))
            conn.commit()
            return True

    def generate_recommendations(self, student_id: str) -> List[Dict]:
        """Generate study recommendations based on grades and weak areas."""
        recommendations = []
        weak_areas = self.get_weak_areas(student_id)

        for area in weak_areas:
            rec = {
                "student_id": student_id,
                "module_code": area.get('module_code', area.get('course', '')),
                "recommendation_type": "focus_area",
                "title": f"Review {area.get('module_code', area.get('course', 'this subject'))}",
                "description": f"Your grade ({area.get('grade', area.get('score', 'N/A'))}) suggests more study is needed. Focus on core concepts and practice problems.",
                "priority": "high" if float(area.get('score', area.get('grade', 50))) < 40 else "medium",
            }
            recommendations.append(rec)

        # Add general recommendations
        profile = self.get_profile(student_id)
        if profile and profile.get('learning_style'):
            style = profile['learning_style']
            tips = {
                'visual': "Try using mind maps, diagrams, and colour-coded notes.",
                'auditory': "Record lectures, use podcasts, and discuss topics with peers.",
                'reading': "Summarise textbook chapters and create revision notes.",
                'kinesthetic': "Use hands-on practice, labs, and real-world applications.",
            }
            recommendations.append({
                "student_id": student_id, "module_code": None,
                "recommendation_type": "technique", "title": f"Study technique for {style} learners",
                "description": tips.get(style, "Use varied study methods."), "priority": "low"
            })

        # Save recommendations
        with transaction() as conn:
            for rec in recommendations:
                conn.execute(
                    "INSERT INTO study_recommendations (student_id, module_code, recommendation_type, title, description, priority) VALUES (?, ?, ?, ?, ?, ?)",
                    (rec['student_id'], rec['module_code'], rec['recommendation_type'], rec['title'], rec['description'], rec['priority'])
                )
            conn.commit()

        return recommendations

    def get_recommendations(self, student_id: str, active_only: bool = True) -> List[Dict]:
        with get_connection() as conn:
            if active_only:
                rows = conn.execute("SELECT * FROM study_recommendations WHERE student_id = ? AND is_completed = 0 ORDER BY priority, created_at DESC", (student_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM study_recommendations WHERE student_id = ? ORDER BY created_at DESC", (student_id,)).fetchall()
            return [dict(r) for r in rows]

    def mark_recommendation_completed(self, rec_id: int) -> bool:
        with transaction() as conn:
            conn.execute("UPDATE study_recommendations SET is_completed = 1 WHERE id = ?", (rec_id,))
            conn.commit()
            return True

    def log_study_session(self, student_id: str, module_code: str = None, topic: str = None,
                          duration_minutes: int = 0, effectiveness_rating: int = None, notes: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO study_sessions (student_id, module_code, topic, duration_minutes, effectiveness_rating, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (student_id, module_code, topic, duration_minutes, effectiveness_rating, notes)
            )
            conn.commit()
            return cursor.lastrowid

    def get_study_history(self, student_id: str, limit: int = 50) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM study_sessions WHERE student_id = ? ORDER BY studied_at DESC LIMIT ?", (student_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def get_study_stats(self, student_id: str) -> Dict:
        with get_connection() as conn:
            total = conn.execute("SELECT COALESCE(SUM(duration_minutes), 0) FROM study_sessions WHERE student_id = ?", (student_id,)).fetchone()[0]
            sessions = conn.execute("SELECT COUNT(*) FROM study_sessions WHERE student_id = ?", (student_id,)).fetchone()[0]
            avg_eff = conn.execute("SELECT AVG(effectiveness_rating) FROM study_sessions WHERE student_id = ? AND effectiveness_rating IS NOT NULL", (student_id,)).fetchone()[0]
            return {"total_minutes": total, "total_hours": round(total / 60, 1), "total_sessions": sessions,
                    "avg_effectiveness": round(avg_eff, 1) if avg_eff else 0}

    def get_weak_areas(self, student_id: str) -> List[Dict]:
        """Analyze grades to find weak areas."""
        with get_connection() as conn:
            weak = []
            try:
                rows = conn.execute("""
                    SELECT module_code, course, grade, score FROM grades
                    WHERE student_id = ? AND (score < 50 OR grade IN ('F', 'D', 'D-'))
                    ORDER BY score ASC
                """, (student_id,)).fetchall()
                weak = [dict(r) for r in rows]
            except Exception:
                pass
            return weak

    def get_study_streak(self, student_id: str) -> int:
        """Calculate consecutive days studied."""
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT DATE(studied_at) as study_date FROM study_sessions WHERE student_id = ? ORDER BY study_date DESC",
                (student_id,)
            ).fetchall()
            if not rows:
                return 0
            streak = 1
            for i in range(1, len(rows)):
                # Simple streak counting
                streak += 1
            return min(streak, len(rows))
