"""One record of time spent studying, for the whole Study Hub.

There were three, none of which could see the others:

* ``study_plan_tasks`` — ticked-off tasks from an AI study plan
* ``study_sessions``   — manually logged sessions from recommendations
* ``pomodoro_sessions``— focus timers run inside a virtual study room

So a student's streak ignored their Pomodoros, the AI analytics ignored
their logged sessions, and the two "how much have I studied" numbers
disagreed by construction. Everything now writes here, tagged with where
it came from, and the old tables keep their own detail.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["SOURCES", "SessionService"]

#: Where a session came from. Kept on the row so a screen can still show
#: just its own kind while the totals count everything.
SOURCES = ("manual", "plan_task", "pomodoro", "flashcards")


class SessionService:
    """Append-and-report over the single ``study_sessions`` table."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.ensure_schema()

    def _transaction(self):
        from education_system.systems.university.infrastructure.database.db import (
            transaction,
        )
        return transaction(self.db_path) if self.db_path else transaction()

    def _connect(self):
        from education_system.systems.university.infrastructure.database.db import (
            get_connection,
        )
        return get_connection(self.db_path) if self.db_path else get_connection()

    def ensure_schema(self) -> None:
        try:
            with self._transaction() as conn:
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
                existing = {r[1] for r in conn.execute("PRAGMA table_info(study_sessions)")}
                # `source` and `source_id` are additions: the table predates
                # the merge and already holds manually logged sessions.
                for column, ddl in (("source", "TEXT DEFAULT 'manual'"),
                                    ("source_id", "INTEGER")):
                    if column not in existing:
                        conn.execute(
                            f"ALTER TABLE study_sessions ADD COLUMN {column} {ddl}")
                conn.commit()
        except Exception:
            logger.exception("Could not ensure study_sessions schema")

    # -- writes ---------------------------------------------------------
    def log(self, student_id: str, *, minutes: int = 0, module_code: str = None,
            topic: str = None, effectiveness: int = None, notes: str = None,
            source: str = "manual", source_id: int = None,
            studied_at: str = None) -> Optional[int]:
        """Record one study session. Returns its id."""
        if not student_id:
            return None
        if source not in SOURCES:
            source = "manual"
        try:
            with self._transaction() as conn:
                cursor = conn.execute(
                    "INSERT INTO study_sessions "
                    "(student_id, module_code, topic, duration_minutes, "
                    " effectiveness_rating, notes, studied_at, source, source_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(student_id), module_code, topic, int(minutes or 0),
                     effectiveness, notes,
                     studied_at or datetime.now().isoformat(), source, source_id))
                conn.commit()
                return cursor.lastrowid
        except Exception:
            logger.exception("Could not log study session for %s", student_id)
            return None

    # -- reads ----------------------------------------------------------
    def history(self, student_id: str, limit: int = 50,
                source: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM study_sessions WHERE student_id = ?"
        params: list = [str(student_id)]
        if source:
            sql += " AND COALESCE(source, 'manual') = ?"
            params.append(source)
        sql += " ORDER BY studied_at DESC LIMIT ?"
        params.append(int(limit))
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except Exception:
            logger.exception("Could not read study history for %s", student_id)
            return []

    def stats(self, student_id: str) -> Dict[str, Any]:
        """Totals across every source, plus a per-source breakdown."""
        blank = {"sessions": 0, "total_minutes": 0, "average_minutes": 0.0,
                 "average_effectiveness": None, "by_source": {}, "modules": 0}
        if not student_id:
            return blank
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0), "
                    "       AVG(duration_minutes), AVG(effectiveness_rating), "
                    "       COUNT(DISTINCT module_code) "
                    "FROM study_sessions WHERE student_id = ?",
                    (str(student_id),)).fetchone()
                by_source = {
                    r[0] or "manual": {"sessions": r[1], "minutes": r[2] or 0}
                    for r in conn.execute(
                        "SELECT COALESCE(source,'manual'), COUNT(*), "
                        "       COALESCE(SUM(duration_minutes),0) "
                        "FROM study_sessions WHERE student_id = ? "
                        "GROUP BY COALESCE(source,'manual')",
                        (str(student_id),)).fetchall()}
        except Exception:
            logger.exception("Could not compute study stats for %s", student_id)
            return blank
        return {
            "sessions": row[0] or 0,
            "total_minutes": row[1] or 0,
            "average_minutes": round(row[2] or 0.0, 1),
            "average_effectiveness": round(row[3], 2) if row[3] is not None else None,
            "modules": row[4] or 0,
            "by_source": by_source,
        }

    def streak(self, student_id: str) -> int:
        """Consecutive days up to today with at least one session.

        Counts every source — a Pomodoro in a study room is studying just
        as much as a manually logged hour, which the old streak ignored.
        """
        if not student_id:
            return 0
        try:
            with self._connect() as conn:
                days = [r[0] for r in conn.execute(
                    "SELECT DISTINCT DATE(studied_at) FROM study_sessions "
                    "WHERE student_id = ? AND studied_at IS NOT NULL "
                    "ORDER BY DATE(studied_at) DESC",
                    (str(student_id),)).fetchall() if r[0]]
        except Exception:
            logger.exception("Could not compute streak for %s", student_id)
            return 0
        if not days:
            return 0

        today = datetime.now().date()
        try:
            latest = datetime.strptime(days[0], "%Y-%m-%d").date()
        except ValueError:
            return 0
        # A streak survives "nothing yet today"; it breaks after a full
        # missed day, so yesterday still counts.
        if (today - latest).days > 1:
            return 0

        streak, expected = 0, latest
        for day in days:
            try:
                current = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                continue
            if current == expected:
                streak += 1
                expected -= timedelta(days=1)
            elif current < expected:
                break
        return streak

    def weak_areas(self, student_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Modules with the lowest average effectiveness rating."""
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT module_code, COUNT(*), AVG(effectiveness_rating), "
                    "       COALESCE(SUM(duration_minutes), 0) "
                    "FROM study_sessions "
                    "WHERE student_id = ? AND module_code IS NOT NULL "
                    "  AND effectiveness_rating IS NOT NULL "
                    "GROUP BY module_code "
                    "ORDER BY AVG(effectiveness_rating) ASC LIMIT ?",
                    (str(student_id), int(limit))).fetchall()
        except Exception:
            logger.exception("Could not compute weak areas for %s", student_id)
            return []
        return [{"module_code": r[0], "sessions": r[1],
                 "average_effectiveness": round(r[2], 2) if r[2] is not None else None,
                 "total_minutes": r[3]} for r in rows]
