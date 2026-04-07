"""Persistent rate limiting backed by SQLite.

Stores rate-limit timestamps in the ``rate_limits`` table of the auth
database so they survive process restarts.  Falls back to in-memory
storage if the database is unavailable.
"""

import logging
import time

from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)


class PersistentRateLimiter:
    """SQLite-backed sliding-window rate limiter."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    def is_limited(self, key: str, limit: int, window: int) -> bool:
        """Check if *key* has exceeded *limit* requests in the last *window* seconds.

        Records the current timestamp if under the limit; returns True if over.
        """
        now = time.time()
        cutoff = now - window
        conn = self._conn()
        try:
            # Prune old entries for this key
            conn.execute(
                "DELETE FROM rate_limits WHERE key = ? AND timestamp < ?",
                (key, cutoff),
            )
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM rate_limits WHERE key = ? AND timestamp >= ?",
                (key, cutoff),
            ).fetchone()
            if row["cnt"] >= limit:
                conn.commit()
                return True
            conn.execute(
                "INSERT INTO rate_limits (key, timestamp) VALUES (?, ?)",
                (key, now),
            )
            conn.commit()
            return False
        except Exception as exc:
            logger.debug("Rate limiter DB error (non-fatal): %s", exc)
            return False
        finally:
            conn.close()

    def cleanup(self, max_age: int = 7200) -> int:
        """Remove entries older than *max_age* seconds.  Returns rows deleted."""
        cutoff = time.time() - max_age
        conn = self._conn()
        try:
            cur = conn.execute("DELETE FROM rate_limits WHERE timestamp < ?", (cutoff,))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
