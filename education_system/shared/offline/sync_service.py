"""Offline-first data synchronisation service.

Provides a local cache layer and mutation queue so the application
can operate offline and reconcile changes when connectivity returns.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key   TEXT    UNIQUE NOT NULL,
    data        TEXT    NOT NULL,
    system_key  TEXT    NOT NULL,
    entity_type TEXT    NOT NULL,
    cached_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    expires_at  TEXT,
    etag        TEXT
);
CREATE INDEX IF NOT EXISTS idx_cache_key ON sync_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_system ON sync_cache(system_key);

CREATE TABLE IF NOT EXISTS sync_mutation_queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    operation       TEXT    NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    entity_type     TEXT    NOT NULL,
    entity_id       TEXT,
    system_key      TEXT    NOT NULL,
    payload         TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'syncing', 'synced', 'conflict', 'failed')),
    retry_count     INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    synced_at       TEXT,
    user_id         INTEGER
);
CREATE INDEX IF NOT EXISTS idx_mutation_status ON sync_mutation_queue(status);

CREATE TABLE IF NOT EXISTS sync_state (
    system_key      TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    last_sync_at    TEXT,
    last_sync_token TEXT,
    PRIMARY KEY (system_key, entity_type)
);
"""


def _get_db_path():
    shared_root = Path(__file__).resolve().parent.parent
    db_dir = shared_root / "data" / "db_files"
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / "offline_sync.db")


class OfflineSyncService:
    """Offline-first data caching and sync queue manager."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or _get_db_path()
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._conn()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # ── Cache operations ──────────────────────────────────────────────

    def cache_get(self, cache_key: str) -> dict | None:
        """Get cached data by key. Returns None if expired or missing."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT data, expires_at FROM sync_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if not row:
                return None
            if row["expires_at"] and row["expires_at"] < datetime.utcnow().isoformat():
                conn.execute("DELETE FROM sync_cache WHERE cache_key = ?", (cache_key,))
                conn.commit()
                return None
            return json.loads(row["data"])
        finally:
            conn.close()

    def cache_set(self, cache_key: str, data: dict, system_key: str,
                  entity_type: str, ttl_seconds: int = 3600, etag: str | None = None):
        """Store data in the local cache."""
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.utcfromtimestamp(time.time() + ttl_seconds).isoformat()

        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO sync_cache
                   (cache_key, data, system_key, entity_type, expires_at, etag)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (cache_key, json.dumps(data, default=str), system_key,
                 entity_type, expires_at, etag),
            )
            conn.commit()
        finally:
            conn.close()

    def cache_invalidate(self, cache_key: str | None = None,
                         system_key: str | None = None,
                         entity_type: str | None = None):
        """Invalidate cache entries by key, system, or entity type."""
        conn = self._conn()
        try:
            if cache_key:
                conn.execute("DELETE FROM sync_cache WHERE cache_key = ?", (cache_key,))
            elif system_key and entity_type:
                conn.execute(
                    "DELETE FROM sync_cache WHERE system_key = ? AND entity_type = ?",
                    (system_key, entity_type),
                )
            elif system_key:
                conn.execute("DELETE FROM sync_cache WHERE system_key = ?", (system_key,))
            else:
                conn.execute("DELETE FROM sync_cache")
            conn.commit()
        finally:
            conn.close()

    # ── Mutation queue ────────────────────────────────────────────────

    def queue_mutation(self, operation: str, entity_type: str, system_key: str,
                       payload: dict, entity_id: str | None = None,
                       user_id: int | None = None) -> int:
        """Queue an offline mutation for later sync. Returns the queue entry ID."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                """INSERT INTO sync_mutation_queue
                   (operation, entity_type, entity_id, system_key, payload, user_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (operation, entity_type, entity_id, system_key,
                 json.dumps(payload, default=str), user_id),
            )
            conn.commit()
            logger.info("Queued offline %s for %s/%s", operation, system_key, entity_type)
            return cursor.lastrowid
        finally:
            conn.close()

    def get_pending_mutations(self, system_key: str | None = None,
                              limit: int = 100) -> list[dict]:
        """Get pending mutations to sync."""
        conn = self._conn()
        try:
            if system_key:
                rows = conn.execute(
                    "SELECT * FROM sync_mutation_queue WHERE status = 'pending' AND system_key = ? ORDER BY created_at LIMIT ?",
                    (system_key, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sync_mutation_queue WHERE status = 'pending' ORDER BY created_at LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def mark_synced(self, mutation_id: int):
        """Mark a mutation as successfully synced."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE sync_mutation_queue SET status = 'synced', synced_at = strftime('%Y-%m-%dT%H:%M:%S', 'now') WHERE id = ?",
                (mutation_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_failed(self, mutation_id: int, error: str):
        """Mark a mutation as failed."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE sync_mutation_queue SET status = 'failed', error_message = ?, retry_count = retry_count + 1 WHERE id = ?",
                (error[:500], mutation_id),
            )
            conn.commit()
        finally:
            conn.close()

    def mark_conflict(self, mutation_id: int, error: str):
        """Mark a mutation as having a conflict requiring manual resolution."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE sync_mutation_queue SET status = 'conflict', error_message = ? WHERE id = ?",
                (error[:500], mutation_id),
            )
            conn.commit()
        finally:
            conn.close()

    # ── Sync state ────────────────────────────────────────────────────

    def get_sync_state(self, system_key: str, entity_type: str) -> dict | None:
        """Get the last sync state for a system/entity combination."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM sync_state WHERE system_key = ? AND entity_type = ?",
                (system_key, entity_type),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_sync_state(self, system_key: str, entity_type: str,
                          sync_token: str | None = None):
        """Update the sync state after a successful sync."""
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO sync_state
                   (system_key, entity_type, last_sync_at, last_sync_token)
                   VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%S', 'now'), ?)""",
                (system_key, entity_type, sync_token),
            )
            conn.commit()
        finally:
            conn.close()

    def get_sync_status(self) -> dict:
        """Get overall sync status summary."""
        conn = self._conn()
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM sync_mutation_queue WHERE status = 'pending'"
            ).fetchone()[0]
            conflicts = conn.execute(
                "SELECT COUNT(*) FROM sync_mutation_queue WHERE status = 'conflict'"
            ).fetchone()[0]
            failed = conn.execute(
                "SELECT COUNT(*) FROM sync_mutation_queue WHERE status = 'failed'"
            ).fetchone()[0]
            cached = conn.execute("SELECT COUNT(*) FROM sync_cache").fetchone()[0]
            return {
                "pending_mutations": pending,
                "conflicts": conflicts,
                "failed": failed,
                "cached_items": cached,
                "is_online": True,  # Would check actual connectivity in production
            }
        finally:
            conn.close()

    def cleanup_expired_cache(self):
        """Remove expired cache entries."""
        conn = self._conn()
        try:
            cursor = conn.execute(
                "DELETE FROM sync_cache WHERE expires_at IS NOT NULL AND expires_at < strftime('%Y-%m-%dT%H:%M:%S', 'now')"
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
