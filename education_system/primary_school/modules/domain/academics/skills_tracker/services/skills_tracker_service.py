"""Skills tracking service for primary school pupils.

Tracks development across key skill areas for EYFS and KS1/KS2
using the Emerging/Developing/Expected/Greater Depth framework.
"""

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

SKILL_AREAS = {
    "communication_language": "Communication and Language",
    "physical_development": "Physical Development",
    "personal_social_emotional": "Personal, Social and Emotional Development",
    "literacy": "Literacy",
    "mathematics": "Mathematics",
    "understanding_world": "Understanding the World",
    "expressive_arts": "Expressive Arts and Design",
    "computing": "Computing",
    "science": "Science",
}

ASSESSMENT_LEVELS = ["emerging", "developing", "expected", "greater_depth"]


class SkillsTrackerService:
    """Manage pupil skill assessments and progress tracking."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._ensure_table()

    def _conn(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_table(self):
        conn = self._conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS skill_assessments (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    pupil_id        TEXT    NOT NULL,
                    skill_area      TEXT    NOT NULL,
                    level           TEXT    NOT NULL CHECK (level IN ('emerging', 'developing', 'expected', 'greater_depth')),
                    term            TEXT,
                    academic_year   TEXT,
                    assessed_by     TEXT,
                    notes           TEXT,
                    assessed_at     TEXT    NOT NULL DEFAULT (datetime('now')),
                    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_pupil ON skill_assessments(pupil_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_skill_area ON skill_assessments(skill_area)")
            conn.commit()
        finally:
            conn.close()

    def record_assessment(self, pupil_id: str, skill_area: str, level: str,
                          term: str | None = None, academic_year: str | None = None,
                          assessed_by: str | None = None, notes: str | None = None) -> int:
        """Record a skill assessment for a pupil."""
        if skill_area not in SKILL_AREAS:
            raise ValueError(f"Unknown skill area: {skill_area}")
        if level not in ASSESSMENT_LEVELS:
            raise ValueError(f"Invalid level: {level}. Must be one of {ASSESSMENT_LEVELS}")

        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO skill_assessments
                   (pupil_id, skill_area, level, term, academic_year, assessed_by, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (pupil_id, skill_area, level, term, academic_year, assessed_by, notes),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_pupil_profile(self, pupil_id: str) -> dict:
        """Get the latest skill assessment for each area."""
        conn = self._conn()
        try:
            profile = {}
            for area in SKILL_AREAS:
                row = conn.execute(
                    """SELECT * FROM skill_assessments
                       WHERE pupil_id = ? AND skill_area = ?
                       ORDER BY assessed_at DESC LIMIT 1""",
                    (pupil_id, area),
                ).fetchone()
                profile[area] = {
                    "area_name": SKILL_AREAS[area],
                    "current_level": dict(row)["level"] if row else None,
                    "assessed_at": dict(row)["assessed_at"] if row else None,
                }
            return profile
        finally:
            conn.close()

    def get_pupil_progress(self, pupil_id: str, skill_area: str | None = None) -> list[dict]:
        """Get assessment history for a pupil, optionally filtered by skill area."""
        conn = self._conn()
        try:
            if skill_area:
                rows = conn.execute(
                    "SELECT * FROM skill_assessments WHERE pupil_id = ? AND skill_area = ? ORDER BY assessed_at",
                    (pupil_id, skill_area),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM skill_assessments WHERE pupil_id = ? ORDER BY assessed_at",
                    (pupil_id,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_class_summary(self, pupil_ids: list[str], skill_area: str) -> dict:
        """Get summary statistics for a class in a specific skill area."""
        level_counts = {level: 0 for level in ASSESSMENT_LEVELS}
        for pid in pupil_ids:
            profile = self.get_pupil_profile(pid)
            level = profile.get(skill_area, {}).get("current_level")
            if level and level in level_counts:
                level_counts[level] += 1

        total = sum(level_counts.values())
        return {
            "skill_area": skill_area,
            "area_name": SKILL_AREAS.get(skill_area, skill_area),
            "total_pupils": total,
            "level_counts": level_counts,
            "level_percentages": {
                k: round(v / total * 100, 1) if total > 0 else 0
                for k, v in level_counts.items()
            },
        }
