"""Real-time notification service.

Persists notifications to SQLite so reconnecting clients can fetch missed
events, and pushes them instantly via Socket.IO when the user is online.
"""

import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS realtime_notifications (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    title             TEXT NOT NULL,
    body              TEXT,
    notification_type TEXT NOT NULL DEFAULT 'info',  -- 'info', 'warning', 'success', 'error'
    system_key        TEXT,
    is_read           INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rt_notif_user ON realtime_notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_rt_notif_system ON realtime_notifications(system_key, created_at);
"""


def _init_notification_db(db_path: str) -> None:
    """Create realtime_notifications table (idempotent)."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


class RealtimeNotificationService:
    """Push and persist notifications for education system users.

    Parameters
    ----------
    db_path:
        Path to an SQLite database (e.g. the shared auth.db or a dedicated
        notifications DB).
    """

    def __init__(self, db_path: str):
        self._db_path = str(db_path)
        _init_notification_db(self._db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat()

    # ------------------------------------------------------------------
    # Core push
    # ------------------------------------------------------------------
    def push_notification(
        self,
        user_id: int,
        title: str,
        body: str = "",
        notification_type: str = "info",
        system_key: str | None = None,
    ) -> dict:
        """Persist a notification and emit it via Socket.IO if user is connected.

        Returns the persisted notification record.
        """
        now = self._now()
        conn = self._conn()
        try:
            cur = conn.execute(
                "INSERT INTO realtime_notifications "
                "(user_id, title, body, notification_type, system_key, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, title, body, notification_type, system_key, now),
            )
            conn.commit()
            notif_id = cur.lastrowid
        finally:
            conn.close()

        record = {
            "id": notif_id,
            "user_id": user_id,
            "title": title,
            "body": body,
            "notification_type": notification_type,
            "system_key": system_key,
            "is_read": False,
            "created_at": now,
        }

        # Attempt real-time push (no-op if Socket.IO is unavailable or user offline)
        self._emit(user_id, record)
        return record

    def push_bulk(self, user_ids: list[int], title: str, body: str = "",
                  notification_type: str = "info", system_key: str | None = None) -> int:
        """Push the same notification to multiple users. Returns count sent."""
        count = 0
        for uid in user_ids:
            try:
                self.push_notification(uid, title, body, notification_type, system_key)
                count += 1
            except Exception as exc:
                logger.warning("push_bulk: failed for user_id=%s: %s", uid, exc)
        return count

    def _emit(self, user_id: int, data: dict) -> None:
        """Try to emit via Socket.IO; silently skip if not available."""
        try:
            from education_system.platform.delivery.api.websocket_server import emit_to_user
            emit_to_user(user_id, "notification", data)
        except Exception:
            pass  # Non-fatal – notification is already persisted

    # ------------------------------------------------------------------
    # Read pending / history
    # ------------------------------------------------------------------
    def get_pending_notifications(self, user_id: int, limit: int = 50) -> list[dict]:
        """Return unread notifications for a user (e.g. after reconnect)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM realtime_notifications "
                "WHERE user_id = ? AND is_read = 0 "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_notifications(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> list[dict]:
        """Return paginated notifications for a user."""
        conn = self._conn()
        try:
            where = "WHERE user_id = ?"
            params: list = [user_id]
            if unread_only:
                where += " AND is_read = 0"
            rows = conn.execute(
                f"SELECT * FROM realtime_notifications {where} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_unread_count(self, user_id: int) -> int:
        """Return the number of unread notifications for a user."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM realtime_notifications "
                "WHERE user_id = ? AND is_read = 0",
                (user_id,),
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Mark read
    # ------------------------------------------------------------------
    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark a single notification as read."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE realtime_notifications SET is_read = 1 WHERE id = ?",
                (notification_id,),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications for a user as read. Returns count updated."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "UPDATE realtime_notifications SET is_read = 1 "
                "WHERE user_id = ? AND is_read = 0",
                (user_id,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def delete_old_notifications(self, days: int = 90) -> int:
        """Delete read notifications older than *days*. Returns count deleted."""
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM realtime_notifications WHERE is_read = 1 AND created_at < ?",
                (cutoff,),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
