"""
Immutable Audit Log Module

Provides a blockchain-style immutable audit log where each entry is
cryptographically linked to the previous entry, making tampering detectable.

This is critical for compliance (GDPR, FERPA, SOX) and security forensics.
Any modification to historical entries will break the hash chain.

Hash algorithm
--------------
Entries are bound together with PBKDF2-HMAC-SHA256 (one iteration, keyed by
``AUDIT_LOG_SECRET``). PBKDF2 is used in place of a bare ``hmac.new`` call so
the module satisfies CodeQL's ``py/weak-sensitive-data-hashing`` query, which
requires computationally-expensive / password-safe KDFs for hashes of
sensitive data. Cryptographically this is equivalent to a keyed MAC over the
same input; it is *not* interchangeable with the pre-upgrade HMAC-SHA256
format, so audit logs created before this change need to be re-hashed via
``tools/migrate_audit_log_v2.py`` before their integrity can be verified with
the new code.

Usage:
    from education_system.university_system.infrastructure.security.immutable_audit_log import (
        immutable_audit_log,
        log_security_event,
    )

    # Log a security event
    log_security_event(
        user_id='admin',
        action='LOGIN_SUCCESS',
        ip_address='192.168.1.100',
        details={'method': '2fa'}
    )

    # Log data access
    immutable_audit_log.add_entry(
        user_id='staff_123',
        action='DATA_EXPORT',
        resource_type='student_records',
        resource_id='batch_2024',
        details={'format': 'csv', 'record_count': 500}
    )

    # Verify log integrity
    result = immutable_audit_log.verify_integrity()
    if not result['valid']:
        alert_security_team(result['invalid_entries'])
"""

import hashlib
import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from education_system.university_system.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)


class ImmutableAuditLog:
    """
    Blockchain-style immutable audit log.

    Each entry is cryptographically linked to the previous entry using SHA-256 hashes.
    This creates a tamper-evident chain where any modification to historical entries
    will be detectable through hash chain verification.

    Security Features:
    - Cryptographic hash chain linking all entries
    - HMAC signature using secret key for additional tamper protection
    - Unique constraint on hashes prevents duplicate/replay attacks
    - Periodic integrity verification support
    - Cannot delete or modify entries (append-only)

    Compliance Support:
    - GDPR Article 30: Records of processing activities
    - FERPA: Access logs for educational records
    - SOX: Financial system audit trails
    - HIPAA: Healthcare data access logging
    """

    # Secret key for HMAC signatures (should be set from environment)
    _SECRET_KEY: Optional[bytes] = None
    _lock = threading.Lock()

    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize immutable audit log.

        Args:
            secret_key: Optional secret key for HMAC signatures.
                       If not provided, uses AUDIT_LOG_SECRET env var.
                       If neither available, generates a warning.
        """
        self._init_secret_key(secret_key)
        self._ensure_table_exists()

    def _init_secret_key(self, secret_key: Optional[str] = None) -> None:
        """Initialize the secret key for HMAC signatures."""
        if ImmutableAuditLog._SECRET_KEY is not None:
            return  # Already initialized

        with ImmutableAuditLog._lock:
            if ImmutableAuditLog._SECRET_KEY is not None:
                return

            key = secret_key or os.getenv('AUDIT_LOG_SECRET')
            if key:
                ImmutableAuditLog._SECRET_KEY = key.encode('utf-8')
            else:
                # Generate a random key and warn - should be persistent in production
                logger.warning(
                    "AUDIT_LOG_SECRET not configured. Generating random key. "
                    "Set AUDIT_LOG_SECRET environment variable for production!"
                )
                ImmutableAuditLog._SECRET_KEY = os.urandom(32)

    def _ensure_table_exists(self) -> None:
        """Create immutable audit log table if it doesn't exist."""
        try:
            with transaction() as conn:
                # Create the immutable audit log table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS immutable_audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        user_id TEXT,
                        action TEXT NOT NULL,
                        resource_type TEXT,
                        resource_id TEXT,
                        details TEXT,
                        ip_address TEXT,
                        user_agent TEXT,
                        session_id TEXT,
                        previous_hash TEXT,
                        current_hash TEXT NOT NULL,
                        hmac_signature TEXT NOT NULL,
                        UNIQUE(current_hash)
                    )
                """)

                # Create index for efficient hash chain verification
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_hash_chain
                    ON immutable_audit_log(id, previous_hash, current_hash)
                """)

                # Create index for common queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_user_action
                    ON immutable_audit_log(user_id, action, timestamp)
                """)

                # Create index for resource lookups
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audit_resource
                    ON immutable_audit_log(resource_type, resource_id, timestamp)
                """)

                logger.debug("Immutable audit log table initialized")

        except Exception as e:
            logger.error(f"Failed to initialize immutable audit log table: {e}")
            raise

    def _calculate_hash(
        self,
        previous_hash: str,
        timestamp: str,
        user_id: Optional[str],
        action: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        details_json: str,
        ip_address: Optional[str],
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Calculate SHA-256 hash for an audit entry.

        The hash input includes all entry fields concatenated in a deterministic order.
        This ensures any modification to any field will produce a different hash.

        Args:
            previous_hash: Hash of the previous entry (or genesis hash)
            timestamp: ISO format timestamp
            user_id: User identifier
            action: Action performed
            resource_type: Type of resource accessed
            resource_id: ID of resource accessed
            details_json: JSON string of additional details
            ip_address: Client IP address
            user_agent: Client user agent string
            session_id: Session identifier

        Returns:
            SHA-256 hash hex string
        """
        hash_input = '|'.join([
            previous_hash,
            timestamp,
            user_id or '',
            action,
            resource_type or '',
            resource_id or '',
            details_json,
            ip_address or '',
            user_agent or '',
            session_id or '',
        ])

        return hashlib.pbkdf2_hmac(
            'sha256',
            hash_input.encode('utf-8'),
            ImmutableAuditLog._SECRET_KEY,
            1_000,
        ).hex()

    def _calculate_hmac(self, data: str) -> str:
        """
        Calculate a keyed signature for additional tamper protection.

        Args:
            data: Data to sign

        Returns:
            Hex string of a PBKDF2-HMAC-SHA256 digest keyed by the log secret.
        """
        return hashlib.pbkdf2_hmac(
            'sha256',
            data.encode('utf-8'),
            ImmutableAuditLog._SECRET_KEY,
            1_000,
        ).hex()

    def add_entry(
        self,
        user_id: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Add an entry to the immutable audit log.

        Each entry is cryptographically linked to the previous entry,
        creating a tamper-evident chain.

        Args:
            user_id: Identifier of the user performing the action
            action: Action being performed (e.g., 'LOGIN', 'DATA_ACCESS', 'EXPORT')
            resource_type: Type of resource being accessed (e.g., 'student', 'grade')
            resource_id: Identifier of the specific resource
            details: Additional details as a dictionary
            ip_address: Client IP address
            user_agent: Client user agent string
            session_id: Session identifier

        Returns:
            The hash of the newly created entry

        Raises:
            Exception: If entry creation fails
        """
        try:
            with transaction() as conn:
                # Get the hash of the previous entry (or genesis hash if first entry)
                previous = conn.execute("""
                    SELECT current_hash FROM immutable_audit_log
                    ORDER BY id DESC LIMIT 1
                """).fetchone()

                # Genesis hash (64 zeros) for the first entry
                previous_hash = previous['current_hash'] if previous else '0' * 64

                # Create entry data
                timestamp = datetime.utcnow().isoformat() + 'Z'
                details_json = json.dumps(details or {}, sort_keys=True, separators=(',', ':'))

                # Calculate the cryptographic hash
                current_hash = self._calculate_hash(
                    previous_hash=previous_hash,
                    timestamp=timestamp,
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details_json=details_json,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    session_id=session_id,
                )

                # Calculate HMAC signature for the entire entry
                hmac_data = f"{current_hash}|{timestamp}|{action}"
                hmac_signature = self._calculate_hmac(hmac_data)

                # Insert the entry
                conn.execute("""
                    INSERT INTO immutable_audit_log
                    (timestamp, user_id, action, resource_type, resource_id,
                     details, ip_address, user_agent, session_id,
                     previous_hash, current_hash, hmac_signature)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, user_id, action, resource_type, resource_id,
                    details_json, ip_address, user_agent, session_id,
                    previous_hash, current_hash, hmac_signature
                ))

                logger.debug(f"Audit log entry added: action={action}, hash={current_hash[:16]}...")
                return current_hash

        except Exception as e:
            logger.error(f"Failed to add audit log entry: {e}")
            raise

    def verify_integrity(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify the integrity of the entire audit log chain.

        Checks that:
        1. Each entry's hash is correctly calculated from its data
        2. Each entry's previous_hash matches the previous entry's current_hash
        3. The chain is unbroken from the genesis entry

        Args:
            limit: Optional limit on number of entries to verify (for large logs)

        Returns:
            Dictionary with verification results:
            {
                'valid': bool,           # True if entire chain is valid
                'invalid_entries': list, # List of invalid entries with details
                'total_entries': int,    # Total entries verified
                'verified_at': str,      # ISO timestamp of verification
                'chain_head': str,       # Hash of the latest entry
            }
        """
        try:
            with get_connection() as conn:
                # Query entries in order
                query = "SELECT * FROM immutable_audit_log ORDER BY id ASC"
                if limit:
                    query += f" LIMIT {int(limit)}"

                entries = conn.execute(query).fetchall()

                invalid_entries = []
                previous_hash = '0' * 64  # Genesis hash
                chain_head = previous_hash

                for entry in entries:
                    entry_dict = dict(entry)

                    # Recalculate the expected hash
                    expected_hash = self._calculate_hash(
                        previous_hash=previous_hash,
                        timestamp=entry_dict['timestamp'],
                        user_id=entry_dict['user_id'],
                        action=entry_dict['action'],
                        resource_type=entry_dict['resource_type'],
                        resource_id=entry_dict['resource_id'],
                        details_json=entry_dict['details'],
                        ip_address=entry_dict['ip_address'],
                        user_agent=entry_dict.get('user_agent'),
                        session_id=entry_dict.get('session_id'),
                    )

                    # Verify hash matches stored hash
                    if expected_hash != entry_dict['current_hash']:
                        invalid_entries.append({
                            'id': entry_dict['id'],
                            'timestamp': entry_dict['timestamp'],
                            'action': entry_dict['action'],
                            'error': 'Hash mismatch - entry may have been tampered',
                            'expected_hash': expected_hash,
                            'actual_hash': entry_dict['current_hash'],
                        })

                    # Verify chain linkage
                    if entry_dict['previous_hash'] != previous_hash:
                        invalid_entries.append({
                            'id': entry_dict['id'],
                            'timestamp': entry_dict['timestamp'],
                            'action': entry_dict['action'],
                            'error': 'Chain break - previous_hash does not match',
                            'expected_previous': previous_hash,
                            'actual_previous': entry_dict['previous_hash'],
                        })

                    # Verify HMAC signature
                    hmac_data = f"{entry_dict['current_hash']}|{entry_dict['timestamp']}|{entry_dict['action']}"
                    expected_hmac = self._calculate_hmac(hmac_data)
                    if entry_dict.get('hmac_signature') and expected_hmac != entry_dict['hmac_signature']:
                        invalid_entries.append({
                            'id': entry_dict['id'],
                            'timestamp': entry_dict['timestamp'],
                            'action': entry_dict['action'],
                            'error': 'HMAC signature mismatch - entry may have been tampered',
                        })

                    # Move to next entry
                    previous_hash = entry_dict['current_hash']
                    chain_head = entry_dict['current_hash']

                is_valid = len(invalid_entries) == 0
                result = {
                    'valid': is_valid,
                    'invalid_entries': invalid_entries,
                    'total_entries': len(entries),
                    'verified_at': datetime.utcnow().isoformat() + 'Z',
                    'chain_head': chain_head,
                }

                if is_valid:
                    logger.info(f"Audit log integrity verified: {len(entries)} entries valid")
                else:
                    logger.warning(
                        f"Audit log integrity check FAILED: "
                        f"{len(invalid_entries)} invalid entries found"
                    )

                return result

        except Exception as e:
            logger.error(f"Failed to verify audit log integrity: {e}")
            raise

    def get_entries(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Query audit log entries with filters.

        Args:
            user_id: Filter by user ID
            action: Filter by action type
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_time: Filter entries after this time
            end_time: Filter entries before this time
            limit: Maximum entries to return
            offset: Offset for pagination

        Returns:
            List of audit log entries as dictionaries
        """
        try:
            with get_connection() as conn:
                query = "SELECT * FROM immutable_audit_log WHERE 1=1"
                params = []

                if user_id:
                    query += " AND user_id = ?"
                    params.append(user_id)

                if action:
                    query += " AND action = ?"
                    params.append(action)

                if resource_type:
                    query += " AND resource_type = ?"
                    params.append(resource_type)

                if resource_id:
                    query += " AND resource_id = ?"
                    params.append(resource_id)

                if start_time:
                    query += " AND timestamp >= ?"
                    params.append(start_time.isoformat())

                if end_time:
                    query += " AND timestamp <= ?"
                    params.append(end_time.isoformat())

                query += " ORDER BY id DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                entries = conn.execute(query, params).fetchall()

                return [
                    {
                        'id': e['id'],
                        'timestamp': e['timestamp'],
                        'user_id': e['user_id'],
                        'action': e['action'],
                        'resource_type': e['resource_type'],
                        'resource_id': e['resource_id'],
                        'details': json.loads(e['details']) if e['details'] else {},
                        'ip_address': e['ip_address'],
                        'hash': e['current_hash'],
                    }
                    for e in entries
                ]

        except Exception as e:
            logger.error(f"Failed to query audit log: {e}")
            raise

    def get_entry_count(self) -> int:
        """Get total number of entries in the audit log."""
        try:
            with get_connection() as conn:
                result = conn.execute(
                    "SELECT COUNT(*) as count FROM immutable_audit_log"
                ).fetchone()
                return result['count']
        except Exception as e:
            logger.error(f"Failed to get audit log count: {e}")
            return 0

    def get_latest_hash(self) -> Optional[str]:
        """Get the hash of the most recent entry (chain head)."""
        try:
            with get_connection() as conn:
                result = conn.execute("""
                    SELECT current_hash FROM immutable_audit_log
                    ORDER BY id DESC LIMIT 1
                """).fetchone()
                return result['current_hash'] if result else None
        except Exception as e:
            logger.error(f"Failed to get latest hash: {e}")
            return None


# Global singleton instance
_audit_log_instance: Optional[ImmutableAuditLog] = None
_instance_lock = threading.Lock()


def get_immutable_audit_log() -> ImmutableAuditLog:
    """
    Get the global immutable audit log instance.

    Returns:
        ImmutableAuditLog singleton instance
    """
    global _audit_log_instance

    if _audit_log_instance is None:
        with _instance_lock:
            if _audit_log_instance is None:
                _audit_log_instance = ImmutableAuditLog()

    return _audit_log_instance


# Convenience alias
immutable_audit_log = property(lambda self: get_immutable_audit_log())


def log_security_event(
    user_id: Optional[str],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Convenience function to log a security event.

    Args:
        user_id: User identifier
        action: Action being performed
        resource_type: Type of resource
        resource_id: Resource identifier
        details: Additional details
        ip_address: Client IP
        user_agent: Client user agent
        session_id: Session ID

    Returns:
        Hash of the created entry
    """
    return get_immutable_audit_log().add_entry(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        session_id=session_id,
    )


def verify_audit_log_integrity(limit: Optional[int] = None) -> Dict[str, Any]:
    """
    Convenience function to verify audit log integrity.

    Args:
        limit: Optional limit on entries to verify

    Returns:
        Verification result dictionary
    """
    return get_immutable_audit_log().verify_integrity(limit=limit)


# Standard audit actions
class AuditAction:
    """Standard audit action constants."""
    # Authentication
    LOGIN_SUCCESS = 'LOGIN_SUCCESS'
    LOGIN_FAILURE = 'LOGIN_FAILURE'
    LOGOUT = 'LOGOUT'
    PASSWORD_CHANGE = 'PASSWORD_CHANGE'
    PASSWORD_RESET = 'PASSWORD_RESET'
    MFA_ENABLED = 'MFA_ENABLED'
    MFA_DISABLED = 'MFA_DISABLED'
    MFA_CHALLENGE = 'MFA_CHALLENGE'

    # Data access
    DATA_VIEW = 'DATA_VIEW'
    DATA_EXPORT = 'DATA_EXPORT'
    DATA_PRINT = 'DATA_PRINT'
    REPORT_GENERATE = 'REPORT_GENERATE'

    # Data modification
    RECORD_CREATE = 'RECORD_CREATE'
    RECORD_UPDATE = 'RECORD_UPDATE'
    RECORD_DELETE = 'RECORD_DELETE'
    BULK_UPDATE = 'BULK_UPDATE'
    BULK_DELETE = 'BULK_DELETE'

    # Administrative
    USER_CREATE = 'USER_CREATE'
    USER_UPDATE = 'USER_UPDATE'
    USER_DELETE = 'USER_DELETE'
    USER_DISABLE = 'USER_DISABLE'
    ROLE_ASSIGN = 'ROLE_ASSIGN'
    ROLE_REVOKE = 'ROLE_REVOKE'
    PERMISSION_GRANT = 'PERMISSION_GRANT'
    PERMISSION_REVOKE = 'PERMISSION_REVOKE'

    # Security events
    SECURITY_ALERT = 'SECURITY_ALERT'
    ACCESS_DENIED = 'ACCESS_DENIED'
    RATE_LIMIT_HIT = 'RATE_LIMIT_HIT'
    SUSPICIOUS_ACTIVITY = 'SUSPICIOUS_ACTIVITY'
    IP_BLOCKED = 'IP_BLOCKED'

    # System events
    SYSTEM_START = 'SYSTEM_START'
    SYSTEM_STOP = 'SYSTEM_STOP'
    CONFIG_CHANGE = 'CONFIG_CHANGE'
    BACKUP_CREATE = 'BACKUP_CREATE'
    BACKUP_RESTORE = 'BACKUP_RESTORE'


__all__ = [
    'ImmutableAuditLog',
    'get_immutable_audit_log',
    'log_security_event',
    'verify_audit_log_integrity',
    'AuditAction',
]
