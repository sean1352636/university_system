"""Unified audit logging service for all education system subsystems.

Provides a single audit trail across university, college, secondary, and
primary systems with structured, immutable-style append-only logging.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_AUDIT_DB: Path | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    system_key      TEXT    NOT NULL,
    user_id         INTEGER,
    username        TEXT,
    action          TEXT    NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    details         TEXT,
    ip_address      TEXT,
    severity        TEXT    NOT NULL DEFAULT 'info'
                        CHECK (severity IN ('info', 'warning', 'critical', 'security')),
    checksum        TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_system ON audit_log(system_key);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_log(severity);
"""


def get_audit_db_path() -> Path:
    if _AUDIT_DB is not None:
        return _AUDIT_DB
    shared_root = Path(__file__).resolve().parent.parent
    db_dir = shared_root / "data" / "db_files"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "audit.db"


def _connect(db_path=None):
    path = str(db_path or get_audit_db_path())
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_audit_db(db_path=None):
    """Create audit tables (idempotent)."""
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        logger.info("Unified audit DB initialised at %s", db_path or get_audit_db_path())
    finally:
        conn.close()


class AuditService:
    """Unified audit logging across all education systems."""

    def __init__(self, db_path=None):
        self._db_path = db_path
        init_audit_db(db_path)

    def log(self, action: str, system_key: str = "shared", user_id: int | None = None,
            username: str | None = None, resource_type: str | None = None,
            resource_id: str | None = None, details: dict | str | None = None,
            ip_address: str | None = None, severity: str = "info") -> int:
        """Append an audit entry. Returns the entry ID."""
        import hashlib
        if isinstance(details, dict):
            details = json.dumps(details, default=str)

        # Compute checksum for tamper detection
        checksum_data = f"{system_key}|{user_id}|{action}|{resource_type}|{details}"
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()[:16]

        conn = _connect(self._db_path)
        try:
            cursor = conn.execute(
                """INSERT INTO audit_log
                   (system_key, user_id, username, action, resource_type, resource_id,
                    details, ip_address, severity, checksum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (system_key, user_id, username, action, resource_type,
                 str(resource_id) if resource_id is not None else None,
                 details, ip_address, severity, checksum),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def log_security(self, action: str, **kwargs) -> int:
        """Log a security-relevant event."""
        return self.log(action, severity="security", **kwargs)

    def query(self, system_key: str | None = None, user_id: int | None = None,
              action: str | None = None, severity: str | None = None,
              since: str | None = None, until: str | None = None,
              limit: int = 100, offset: int = 0) -> list[dict]:
        """Query audit entries with filters."""
        conditions = []
        params = []

        if system_key:
            conditions.append("system_key = ?")
            params.append(system_key)
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if action:
            conditions.append("action LIKE ?")
            params.append(f"%{action}%")
        if severity:
            conditions.append("severity = ?")
            params.append(severity)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = " AND ".join(conditions) if conditions else "1=1"
        conn = _connect(self._db_path)
        try:
            rows = conn.execute(
                f"SELECT * FROM audit_log WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def verify_integrity(self, entry_id: int) -> bool:
        """Verify the checksum of an audit entry (tamper detection)."""
        import hashlib
        conn = _connect(self._db_path)
        try:
            row = conn.execute("SELECT * FROM audit_log WHERE id = ?", (entry_id,)).fetchone()
            if not row:
                return False
            checksum_data = f"{row['system_key']}|{row['user_id']}|{row['action']}|{row['resource_type']}|{row['details']}"
            expected = hashlib.sha256(checksum_data.encode()).hexdigest()[:16]
            return expected == row["checksum"]
        finally:
            conn.close()

    def get_stats(self, system_key: str | None = None, days: int = 30) -> dict:
        """Get audit log statistics."""
        conn = _connect(self._db_path)
        try:
            since = datetime.utcnow().isoformat()[:10]
            base_where = "timestamp >= date('now', ?)"
            params = [f"-{days} days"]
            if system_key:
                base_where += " AND system_key = ?"
                params.append(system_key)

            total = conn.execute(f"SELECT COUNT(*) FROM audit_log WHERE {base_where}", params).fetchone()[0]
            by_severity = {}
            for row in conn.execute(
                f"SELECT severity, COUNT(*) as cnt FROM audit_log WHERE {base_where} GROUP BY severity", params
            ).fetchall():
                by_severity[row[0]] = row[1]
            by_action = {}
            for row in conn.execute(
                f"SELECT action, COUNT(*) as cnt FROM audit_log WHERE {base_where} GROUP BY action ORDER BY cnt DESC LIMIT 20", params
            ).fetchall():
                by_action[row[0]] = row[1]

            return {"total": total, "by_severity": by_severity, "top_actions": by_action, "days": days}
        finally:
            conn.close()
