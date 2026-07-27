"""Centralized, append-only audit logger for all education systems.

Improvement #7: Centralized Audit Logging

Provides a shared, tamper-evident audit trail for authentication events,
data changes, GDPR requests, and safeguarding actions across all 4 systems.
"""

import json
import logging
import sqlite3
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)

# Runtime state lives under var/, not inside the package (ADR 0018).
from education_system.platform.paths import AUDIT_DB_FILE, DB_FILES_DIR as _AUDIT_DB_DIR


class AuditAction(str, Enum):
    """Standard audit actions across all systems."""
    # Auth
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    PASSWORD_CHANGE = "auth.password_change"
    MFA_ENABLE = "auth.mfa_enable"
    MFA_DISABLE = "auth.mfa_disable"
    ACCOUNT_LOCKED = "auth.account_locked"

    # Data
    CREATE = "data.create"
    READ = "data.read"
    UPDATE = "data.update"
    DELETE = "data.delete"
    EXPORT = "data.export"
    IMPORT = "data.import"

    # Admin
    ROLE_CHANGE = "admin.role_change"
    PERMISSION_CHANGE = "admin.permission_change"
    CONFIG_CHANGE = "admin.config_change"
    USER_CREATE = "admin.user_create"
    USER_DEACTIVATE = "admin.user_deactivate"

    # GDPR
    DATA_ACCESS_REQUEST = "gdpr.data_access_request"
    DATA_DELETION_REQUEST = "gdpr.data_deletion_request"
    CONSENT_UPDATE = "gdpr.consent_update"

    # Safeguarding
    SAFEGUARDING_REPORT = "safeguarding.report"
    SAFEGUARDING_VIEW = "safeguarding.view"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    system_key TEXT NOT NULL,
    action TEXT NOT NULL,
    user_id INTEGER,
    username TEXT,
    target_type TEXT,
    target_id TEXT,
    details TEXT,
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_system ON audit_log(system_key);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_type, target_id);
"""


class AuditLogger:
    """Centralized audit logger writing to a shared SQLite database.

    Usage:
        audit = AuditLogger("sixth_form")
        audit.log(AuditAction.CREATE, user_id=1, username="admin",
                  target_type="student", target_id="SFC0001",
                  details={"first_name": "John", "last_name": "Doe"})
    """

    def __init__(self, system_key: str, db_path: str | None = None):
        self.system_key = system_key
        self._db_path = db_path or str(AUDIT_DB_FILE)
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def log(
        self,
        action: str | AuditAction,
        *,
        user_id: int | None = None,
        username: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict | str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> int:
        """Record an audit entry. Returns the entry ID."""
        if isinstance(action, AuditAction):
            action = action.value
        if isinstance(details, dict):
            details = json.dumps(details)

        conn = self._connect()
        try:
            cursor = conn.execute(
                """INSERT INTO audit_log
                   (system_key, action, user_id, username, target_type,
                    target_id, details, ip_address, user_agent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.system_key, action, user_id, username, target_type,
                 target_id, details, ip_address, user_agent),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)
            return -1
        finally:
            conn.close()

    def query(
        self,
        *,
        action: str | None = None,
        user_id: int | None = None,
        username: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        system_key: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Query audit log entries with optional filters."""
        conditions = []
        params = []

        if system_key:
            conditions.append("system_key = ?")
            params.append(system_key)
        else:
            conditions.append("system_key = ?")
            params.append(self.system_key)

        if action:
            conditions.append("action = ?")
            params.append(action if isinstance(action, str) else action.value)
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if username:
            conditions.append("username = ?")
            params.append(username)
        if target_type:
            conditions.append("target_type = ?")
            params.append(target_type)
        if target_id:
            conditions.append("target_id = ?")
            params.append(target_id)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        if until:
            conditions.append("timestamp <= ?")
            params.append(until)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT * FROM audit_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                if d.get("details"):
                    try:
                        d["details"] = json.loads(d["details"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                result.append(d)
            return result
        finally:
            conn.close()

    def count(self, *, action: str | None = None, since: str | None = None) -> int:
        """Count audit entries matching filters."""
        conditions = ["system_key = ?"]
        params: list = [self.system_key]
        if action:
            conditions.append("action = ?")
            params.append(action if isinstance(action, str) else action.value)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = f"WHERE {' AND '.join(conditions)}"
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT COUNT(*) as cnt FROM audit_log {where}", params
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()
