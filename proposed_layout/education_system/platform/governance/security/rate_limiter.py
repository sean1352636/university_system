"""Persistent rate limiter using SQLite storage."""

import sqlite3
import time
import threading
import os

_DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "db_files", "rate_limits.db")


class PersistentRateLimiter:
    """SQLite-backed rate limiter that persists across restarts."""

    def __init__(self, db_path=None):
        self._db_path = db_path or _DEFAULT_DB
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_key ON rate_limits(key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_ts ON rate_limits(timestamp)")
        conn.commit()
        conn.close()

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple:
        """Check if a request is allowed.

        Returns (allowed: bool, retry_after: int).
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            conn = sqlite3.connect(self._db_path)
            try:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM rate_limits WHERE key = ? AND timestamp > ?",
                    (key, window_start)
                )
                count = cursor.fetchone()[0]

                if count >= max_requests:
                    cursor = conn.execute(
                        "SELECT MIN(timestamp) FROM rate_limits WHERE key = ? AND timestamp > ?",
                        (key, window_start)
                    )
                    oldest = cursor.fetchone()[0]
                    retry_after = int((oldest + window_seconds) - now) + 1
                    return False, max(retry_after, 1)

                conn.execute(
                    "INSERT INTO rate_limits (key, timestamp) VALUES (?, ?)",
                    (key, now)
                )
                conn.commit()
                return True, 0
            finally:
                conn.close()

    def cleanup_expired(self, max_age_seconds=3600):
        """Remove expired rate limit entries."""
        cutoff = time.time() - max_age_seconds
        conn = sqlite3.connect(self._db_path)
        conn.execute("DELETE FROM rate_limits WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()

    def reset(self, key: str):
        """Reset rate limit for a specific key."""
        conn = sqlite3.connect(self._db_path)
        conn.execute("DELETE FROM rate_limits WHERE key = ?", (key,))
        conn.commit()
        conn.close()
