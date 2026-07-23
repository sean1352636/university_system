"""Student app portal service - aggregates timetable, grades, messages."""

from datetime import datetime
from typing import Dict, List, Optional

from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction


class StudentAppService:
    """Service for student mobile-responsive portal."""

    def __init__(self):
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_app_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT UNIQUE NOT NULL,
                    theme TEXT DEFAULT 'light',
                    notifications_enabled INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'en',
                    dashboard_layout TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_app_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    notification_type TEXT DEFAULT 'announcement',
                    title TEXT NOT NULL,
                    message TEXT,
                    is_read INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_quick_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    link_title TEXT NOT NULL,
                    link_url TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.commit()

    def get_student_dashboard(self, student_id: str) -> Dict:
        """Aggregate dashboard data from various sources."""
        dashboard = {"student_id": student_id, "timetable": [], "grades": [], "notifications": [], "deadlines": []}
        with get_connection() as conn:
            try:
                rows = conn.execute("SELECT * FROM timetable_entries WHERE student_id = ? ORDER BY day, start_time LIMIT 10", (student_id,)).fetchall()
                dashboard['timetable'] = [dict(r) for r in rows]
            except Exception:
                pass
            try:
                rows = conn.execute("SELECT * FROM grades WHERE student_id = ? ORDER BY date_recorded DESC LIMIT 5", (student_id,)).fetchall()
                dashboard['grades'] = [dict(r) for r in rows]
            except Exception:
                pass
            unread = conn.execute("SELECT COUNT(*) FROM student_app_notifications WHERE student_id = ? AND is_read = 0", (student_id,)).fetchone()[0]
            dashboard['unread_notifications'] = unread
            notifs = conn.execute("SELECT * FROM student_app_notifications WHERE student_id = ? ORDER BY created_at DESC LIMIT 5", (student_id,)).fetchall()
            dashboard['notifications'] = [dict(r) for r in notifs]
        return dashboard

    def get_preferences(self, student_id: str) -> Optional[Dict]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM student_app_preferences WHERE student_id = ?", (student_id,)).fetchone()
            return dict(row) if row else None

    def update_preferences(self, student_id: str, theme: str = None, notifications_enabled: int = None, language: str = None) -> bool:
        with transaction() as conn:
            existing = conn.execute("SELECT id FROM student_app_preferences WHERE student_id = ?", (student_id,)).fetchone()
            if existing:
                updates = []
                values = []
                if theme is not None:
                    updates.append("theme = ?")
                    values.append(theme)
                if notifications_enabled is not None:
                    updates.append("notifications_enabled = ?")
                    values.append(notifications_enabled)
                if language is not None:
                    updates.append("language = ?")
                    values.append(language)
                updates.append("updated_at = ?")
                values.append(datetime.now().isoformat())
                values.append(student_id)
                conn.execute(f"UPDATE student_app_preferences SET {', '.join(updates)} WHERE student_id = ?", values)
            else:
                conn.execute(
                    "INSERT INTO student_app_preferences (student_id, theme, notifications_enabled, language) VALUES (?, ?, ?, ?)",
                    (student_id, theme or 'light', notifications_enabled if notifications_enabled is not None else 1, language or 'en')
                )
            conn.commit()
            return True

    def get_notifications(self, student_id: str, unread_only: bool = False) -> List[Dict]:
        with get_connection() as conn:
            if unread_only:
                rows = conn.execute("SELECT * FROM student_app_notifications WHERE student_id = ? AND is_read = 0 ORDER BY created_at DESC", (student_id,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM student_app_notifications WHERE student_id = ? ORDER BY created_at DESC", (student_id,)).fetchall()
            return [dict(r) for r in rows]

    def mark_notification_read(self, notification_id: int) -> bool:
        with transaction() as conn:
            conn.execute("UPDATE student_app_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
            conn.commit()
            return True

    def mark_all_notifications_read(self, student_id: str) -> int:
        with transaction() as conn:
            cursor = conn.execute("UPDATE student_app_notifications SET is_read = 1 WHERE student_id = ? AND is_read = 0", (student_id,))
            conn.commit()
            return cursor.rowcount

    def create_notification(self, student_id: str, title: str, message: str = None,
                            notification_type: str = 'announcement', expires_at: str = None) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO student_app_notifications (student_id, notification_type, title, message, expires_at) VALUES (?, ?, ?, ?, ?)",
                (student_id, notification_type, title, message, expires_at)
            )
            conn.commit()
            return cursor.lastrowid

    def get_unread_count(self, student_id: str) -> int:
        with get_connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM student_app_notifications WHERE student_id = ? AND is_read = 0", (student_id,)).fetchone()[0]

    def add_quick_link(self, student_id: str, link_title: str, link_url: str, display_order: int = 0) -> int:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO student_quick_links (student_id, link_title, link_url, display_order) VALUES (?, ?, ?, ?)",
                (student_id, link_title, link_url, display_order)
            )
            conn.commit()
            return cursor.lastrowid

    def get_quick_links(self, student_id: str) -> List[Dict]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM student_quick_links WHERE student_id = ? AND is_active = 1 ORDER BY display_order", (student_id,)).fetchall()
            return [dict(r) for r in rows]

    def remove_quick_link(self, link_id: int) -> bool:
        with transaction() as conn:
            conn.execute("DELETE FROM student_quick_links WHERE id = ?", (link_id,))
            conn.commit()
            return True
