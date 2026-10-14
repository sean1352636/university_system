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
from education_system.platform.governance.security.fail_closed import (
    SecurityControlError,
    alert_security_failure,
)
from education_system.paths import PLATFORM_AUDIT_DB_FILE, PLATFORM_DB_FILES_DIR as _AUDIT_DB_DIR


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

    # Cross-system — data or identity crossing a system boundary. Kept
    # apart from data.* so a funding or data-protection audit can ask
    # "what left this system, and on whose authority?" in one filter.
    CROSS_SYSTEM_TRANSFER = "cross_system.transfer"
    CROSS_BOUNDARY_HANDOVER = "cross_system.handover"
    CROSS_SYSTEM_ACCESS = "cross_system.access"
    IDENTITY_MERGE = "cross_system.identity_merge"


# The audit_log table is owned by `audit_service`, which is the only
# module that may define its shape.
#
# This module used to carry a rival CREATE TABLE of its own, naming the
# columns target_type / target_id / user_agent where the canonical table
# names them resource_type / resource_id and adds severity + checksum.
# Both used CREATE TABLE IF NOT EXISTS against the same file, so whichever
# ran first won and the other silently wrote to a table it did not
# describe. In practice audit_service won — it holds the live rows — and
# every write from here failed at `CREATE INDEX ... (target_type, ...)`
# with "no such column: target_type", taking the calling operation down
# with it because an unrecorded audit entry raises.
#
# The public keyword arguments below stay `target_type` / `target_id`:
# they are this class's vocabulary, callers use them, and they map onto
# the canonical columns on the way in.
_TARGET_TO_RESOURCE = {"target_type": "resource_type",
                       "target_id": "resource_id"}


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
        self._db_path = db_path or str(PLATFORM_AUDIT_DB_FILE)
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_db(self) -> None:
        """Create the canonical table via its owner, never a local copy."""
        from education_system.platform.governance.audit import audit_service

        audit_service.init_audit_db(self._db_path)

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
        severity: str = "info",
    ) -> int:
        """Record an audit entry. Returns the entry ID.

        Writes through `AuditService` so the row carries the same columns
        and the same tamper-detection checksum as every other entry — a
        row this class wrote by hand would fail `verify_integrity`, which
        reads exactly like evidence of tampering.

        Raises:
            SecurityControlError: if the entry could not be written. Audit is a
                security control; a caller that cannot record what it did must
                not proceed as though it had.
        """
        from education_system.platform.governance.audit.audit_service import (
            AuditService,
        )

        if isinstance(action, AuditAction):
            action = action.value

        # The canonical table has no user_agent column. It travels inside
        # details rather than being dropped: for the auth events this
        # logger records, the client string is often the only thing that
        # distinguishes a normal login from a suspicious one.
        if user_agent:
            if isinstance(details, dict):
                details = {**details, "user_agent": user_agent}
            elif details is None:
                details = {"user_agent": user_agent}
            else:
                details = f"{details} [user_agent={user_agent}]"

        try:
            return AuditService(self._db_path).log(
                action, system_key=self.system_key, user_id=user_id,
                username=username, resource_type=target_type,
                resource_id=target_id, details=details,
                ip_address=ip_address, severity=severity,
            )
        except Exception as e:
            # An audit write that fails is a control failure, not a warning to
            # be dropped on the floor: the caller had every reason to believe
            # the action was recorded, and nothing else in the system will
            # notice the gap. Alert, then deny by raising — the caller decides
            # whether its operation can proceed unaudited, and for the security
            # actions this logger records the answer is no.
            #
            # The old `return -1` was worse than silent: it looked like a
            # successful call to any caller that did not compare against -1.
            alert_security_failure(
                "audit.write",
                f"Could not record audit entry {action!r}: {e}",
                user_id=user_id,
                exc=e,
            )
            raise SecurityControlError("audit.write", str(e), cause=e) from e

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
            conditions.append("resource_type = ?")
            params.append(target_type)
        if target_id:
            conditions.append("resource_id = ?")
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
                # Callers of this class speak target_*; the row speaks
                # resource_*. Both keys are present so a caller reading
                # either gets an answer instead of a KeyError.
                for target_key, resource_key in _TARGET_TO_RESOURCE.items():
                    d[target_key] = d.get(resource_key)
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
