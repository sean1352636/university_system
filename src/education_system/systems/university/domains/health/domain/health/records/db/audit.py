"""The health portal's audit of changes to health data.

Each entry goes to ``audit_trail`` (with ``data_hash`` chained to the
previous health entry, so a changed or removed row shows) **and** to the
hash-chained immutable audit log. A failure to record raises
:class:`AuditWriteError`: a change to health data that cannot be audited
must not pass silently. Pass the caller's ``conn`` to write the entry in the
same transaction as the change, so the change is rolled back with it.
"""

import hashlib
import json
import logging
import time
from datetime import datetime

from education_system.systems.university.domains.health.infrastructure.health.storage import (
    get_connection,
    sqlite3,
)
from education_system.systems.university.infrastructure.logging.log_config import configure_logging

logger = logging.getLogger(__name__)
audit_logger = configure_logging(name=__name__)


class AuditWriteError(RuntimeError):
    """The audit entry for a change to health data could not be written."""


def _chain_hash(cursor, payload: dict) -> str:
    row = cursor.execute("SELECT data_hash FROM audit_trail WHERE resource_type LIKE 'health%' "
                         "OR module_name = 'health' ORDER BY id DESC LIMIT 1").fetchone()
    previous = (row[0] if row and row[0] else "") if row else ""
    body = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256((previous + body).encode("utf-8")).hexdigest()


def _columns(cursor) -> set:
    return {r[1] for r in cursor.execute("PRAGMA table_info(audit_trail)").fetchall()}


def log_audit_event(user_id, action, resource_type, resource_id, details=None, conn=None,
                    max_retries=5, reason=None):
    """Record a change to health data (see the module docstring). ``reason``
    is the why, asked for by sensitive CLI actions."""
    reuse_conn = conn is not None
    if not reuse_conn:
        conn = get_connection()
    try:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        detail_text = details if isinstance(details, str) else (
            json.dumps(details, default=str) if details else "")
        if reason:
            detail_text = f"{detail_text} | reason: {reason}" if detail_text else f"reason: {reason}"
        cols = _columns(cursor)
        payload = {"user_id": str(user_id), "action": action, "resource_type": resource_type,
                   "resource_id": str(resource_id), "details": detail_text,
                   "timestamp": timestamp}
        values = {"user_id": str(user_id), "action": action, "resource_type": resource_type,
                  "resource_id": str(resource_id), "timestamp": timestamp,
                  "old_values": "", "new_values": detail_text}
        if "data_hash" in cols:
            values["data_hash"] = _chain_hash(cursor, payload)
        if "module_name" in cols:
            values["module_name"] = "health"
        if "details" in cols:
            values["details"] = detail_text
        values = {k: v for k, v in values.items() if k in cols}
        names = ", ".join(values)
        marks = ", ".join("?" * len(values))
        for attempt in range(max_retries):
            try:
                cursor.execute(f"INSERT INTO audit_trail ({names}) VALUES ({marks})",  # nosec B608
                               tuple(values.values()))
                break
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    time.sleep(0.15 * (2 ** attempt))
                    continue
                raise
        from education_system.systems.university.infrastructure.security.immutable_audit_log import (
            log_security_event,
        )
        log_security_event(user_id=str(user_id), action=str(action).upper(),
                           resource_type=f"health_{resource_type}",
                           resource_id=str(resource_id),
                           details={"details": detail_text}, conn=conn)
        if not reuse_conn:
            conn.commit()
        audit_logger.info("USER:%s ACTION:%s RESOURCE:%s:%s", user_id, action, resource_type,
                          resource_id)
    except Exception as exc:
        if not reuse_conn:
            try:
                conn.rollback()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        raise AuditWriteError(f"The change could not be audited: {exc}") from exc
    finally:
        if not reuse_conn:
            try:
                conn.close()
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
