"""Personalised study recommendations based on exams and weak areas."""
import logging

logger = logging.getLogger(__name__)

from datetime import datetime
from typing import Dict, List, Optional

from education_system.systems.university.infrastructure.database.db import get_connection, transaction


from education_system.systems.university.infrastructure.sql_safety import (
    validate_identifier,
)


class StudyRecommendationService:
    """Service for personalised study recommendations."""

    def __init__(self):
        self._ensure_tables_exist()
        from education_system.systems.university.domains.academics.domain.study_hub.services import ProfileService, SessionService
        self.profiles = ProfileService()
        self.sessions = SessionService()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            # study_profiles and study_sessions are owned by
            # study_hub.services.profiles / .sessions, which this service
            # now writes through — see ProfileService's docstring for what
            # the previous arrangement (two vocabularies, one table) cost.
            # Only the recommendations table is created here.
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
            conn.commit()

    def create_profile(self, student_id: str, learning_style: str = 'reading',
                       study_hours_per_week: float = 0, preferred_times: str = None,
                       strengths: str = None, weaknesses: str = None) -> int:
        """Save the recommendation half of the student's study profile.

        Writes through ProfileService so this no longer stamps its own
        vocabulary over the matching profile, nor packs hours/strengths
        into the interests column that matching scores on.
        """
        return self.profiles.save(
            student_id, study_style=learning_style,
            preferred_time=preferred_times,
            hours_per_week=study_hours_per_week,
            strengths=strengths, weaknesses=weaknesses)

    def get_profile(self, student_id: str) -> Optional[Dict]:
        """The student's single study profile."""
        return self.profiles.get(student_id)

    #: Columns a caller may set. ``update_profile`` interpolates its keys as
    #: SQL identifiers, so an unfiltered ``**kwargs`` would be an injection
    #: point the moment anyone wired it to request data. Mirrors the allow-list
    #: the HTTP route already applies in study_recommendation_routes.py.
    _UPDATABLE_COLUMNS = frozenset({
        "learning_style", "study_hours_per_week", "preferred_times",
        "strengths", "weaknesses", "updated_at",
    })

    def update_profile(self, student_id: str, **kwargs) -> bool:
        """Update named profile fields, leaving the others alone."""
        return self.profiles.save(student_id, **kwargs) is not None

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
                          duration_minutes: int = 0, effectiveness_rating: int = None,
                          notes: str = None) -> int:
        """Record a manually logged study session in the shared log."""
        return self.sessions.log(
            student_id, minutes=duration_minutes, module_code=module_code,
            topic=topic, effectiveness=effectiveness_rating, notes=notes,
            source="manual")

    def get_study_history(self, student_id: str, limit: int = 50) -> List[Dict]:
        """Every study session, whatever recorded it."""
        return self.sessions.history(student_id, limit=limit)

    def get_study_stats(self, student_id: str) -> Dict:
        """Totals across manual logs, plan tasks and Pomodoros alike.

        These used to count only manually logged sessions, so a student
        who worked through their plan or ran focus timers appeared to
        have done nothing.
        """
        stats = self.sessions.stats(student_id)
        # Keys the old callers expect, over the merged figures.
        stats.setdefault("total_minutes", 0)
        stats["total_sessions"] = stats.get("sessions", 0)
        stats["total_hours"] = round(stats.get("total_minutes", 0) / 60.0, 1)
        stats["avg_effectiveness"] = stats.get("average_effectiveness")
        return stats

    def get_weak_areas(self, student_id: str) -> List[Dict]:
        """Modules rated least effective by the student."""
        return self.sessions.weak_areas(student_id)

    def get_study_streak(self, student_id: str) -> int:
        """Consecutive study days, counting every source."""
        return self.sessions.streak(student_id)
