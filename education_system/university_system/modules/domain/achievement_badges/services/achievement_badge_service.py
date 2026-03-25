"""Achievement badge system service."""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.university_system.infrastructure.database.db import get_connection, transaction


class AchievementBadgeService:
    """Service for visual badges for milestones and extracurricular participation."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS badge_definitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    category TEXT DEFAULT 'academic',
                    icon_name TEXT,
                    criteria TEXT,
                    points INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_badges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    badge_id INTEGER NOT NULL,
                    awarded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    awarded_by TEXT,
                    reason TEXT,
                    is_displayed INTEGER DEFAULT 1,
                    FOREIGN KEY (badge_id) REFERENCES badge_definitions(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS badge_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    badge_id INTEGER NOT NULL,
                    current_progress INTEGER DEFAULT 0,
                    target_progress INTEGER DEFAULT 100,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (badge_id) REFERENCES badge_definitions(id)
                )
            """)
            conn.commit()

    def create_badge(self, name: str, description: str = None, category: str = 'academic',
                     icon_name: str = None, criteria: str = None, points: int = 0) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO badge_definitions (name, description, category, icon_name, criteria, points) VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, category, icon_name, criteria, points)
            )
            conn.commit()
            return cursor.lastrowid

    def get_badge(self, badge_id: int) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM badge_definitions WHERE id = ?", (badge_id,)).fetchone()
            return dict(row) if row else None

    def list_badges(self, active_only: bool = True) -> List[Dict]:
        with get_connection() as conn:
            if active_only:
                rows = conn.execute("SELECT * FROM badge_definitions WHERE is_active = 1 ORDER BY category, name").fetchall()
            else:
                rows = conn.execute("SELECT * FROM badge_definitions ORDER BY category, name").fetchall()
            return [dict(r) for r in rows]

    def list_badges_by_category(self, category: str) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM badge_definitions WHERE category = ? AND is_active = 1", (category,)).fetchall()
            return [dict(r) for r in rows]

    def award_badge(self, student_id: str, badge_id: int, awarded_by: str = None, reason: str = None) -> int:
        with transaction() as conn:
            existing = conn.execute("SELECT id FROM student_badges WHERE student_id = ? AND badge_id = ?", (student_id, badge_id)).fetchone()
            if existing:
                raise ValueError("Student already has this badge.")
            cursor = conn.execute(
                "INSERT INTO student_badges (student_id, badge_id, awarded_by, reason) VALUES (?, ?, ?, ?)",
                (student_id, badge_id, awarded_by, reason)
            )
            conn.commit()
            return cursor.lastrowid

    def revoke_badge(self, student_id: str, badge_id: int) -> bool:
        with transaction() as conn:
            conn.execute("DELETE FROM student_badges WHERE student_id = ? AND badge_id = ?", (student_id, badge_id))
            conn.commit()
            return True

    def get_student_badges(self, student_id: str) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT sb.*, bd.name, bd.description, bd.category, bd.icon_name, bd.points
                FROM student_badges sb JOIN badge_definitions bd ON sb.badge_id = bd.id
                WHERE sb.student_id = ? ORDER BY sb.awarded_at DESC
            """, (student_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_student_badge_count(self, student_id: str) -> Dict:
        with get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM student_badges WHERE student_id = ?", (student_id,)).fetchone()[0]
            points = conn.execute("""
                SELECT COALESCE(SUM(bd.points), 0) FROM student_badges sb
                JOIN badge_definitions bd ON sb.badge_id = bd.id WHERE sb.student_id = ?
            """, (student_id,)).fetchone()[0]
            return {"count": count, "total_points": points}

    def update_progress(self, student_id: str, badge_id: int, progress: int) -> bool:
        with transaction() as conn:
            existing = conn.execute("SELECT id FROM badge_progress WHERE student_id = ? AND badge_id = ?", (student_id, badge_id)).fetchone()
            if existing:
                conn.execute("UPDATE badge_progress SET current_progress = ?, last_updated = ? WHERE student_id = ? AND badge_id = ?",
                             (progress, datetime.now().isoformat(), student_id, badge_id))
            else:
                conn.execute("INSERT INTO badge_progress (student_id, badge_id, current_progress) VALUES (?, ?, ?)",
                             (student_id, badge_id, progress))
            conn.commit()
            return True

    def get_progress(self, student_id: str, badge_id: int = None) -> List[Dict]:
        with get_connection() as conn:
            if badge_id:
                rows = conn.execute("SELECT * FROM badge_progress WHERE student_id = ? AND badge_id = ?", (student_id, badge_id)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT bp.*, bd.name, bd.criteria FROM badge_progress bp
                    JOIN badge_definitions bd ON bp.badge_id = bd.id WHERE bp.student_id = ?
                """, (student_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_leaderboard(self, limit: int = 20) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute("""
                SELECT sb.student_id, COUNT(*) as badge_count, COALESCE(SUM(bd.points), 0) as total_points
                FROM student_badges sb JOIN badge_definitions bd ON sb.badge_id = bd.id
                GROUP BY sb.student_id ORDER BY total_points DESC LIMIT ?
            """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    def toggle_badge_display(self, student_id: str, badge_id: int) -> bool:
        with transaction() as conn:
            row = conn.execute("SELECT is_displayed FROM student_badges WHERE student_id = ? AND badge_id = ?", (student_id, badge_id)).fetchone()
            if row:
                new_val = 0 if row[0] == 1 else 1
                conn.execute("UPDATE student_badges SET is_displayed = ? WHERE student_id = ? AND badge_id = ?", (new_val, student_id, badge_id))
                conn.commit()
                return True
            return False

    def get_badge_statistics(self) -> Dict:
        with get_connection() as conn:
            total_badges = conn.execute("SELECT COUNT(*) FROM badge_definitions WHERE is_active = 1").fetchone()[0]
            total_awarded = conn.execute("SELECT COUNT(*) FROM student_badges").fetchone()[0]
            unique_students = conn.execute("SELECT COUNT(DISTINCT student_id) FROM student_badges").fetchone()[0]
            by_category = {}
            for row in conn.execute("SELECT bd.category, COUNT(*) FROM student_badges sb JOIN badge_definitions bd ON sb.badge_id = bd.id GROUP BY bd.category").fetchall():
                by_category[row[0]] = row[1]
            return {"total_badges": total_badges, "total_awarded": total_awarded, "unique_students": unique_students, "by_category": by_category}
