"""Trusted device management for "remember this device" functionality.

When a user completes MFA on a device they can choose to trust it for a
configurable number of days (default 30).  Subsequent logins from the same
device skip the MFA challenge.

Device identity is derived from a secure, opaque token stored in a cookie
or local storage on the client side.  The server stores only a SHA-256 hash
of the token.
"""

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta

from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)

TRUST_DURATION_DAYS = int(os.getenv("EDU_DEVICE_TRUST_DAYS", "30"))
MAX_DEVICES_PER_USER = 10


class DeviceManager:
    """Manages trusted devices for MFA bypass."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def trust_device(self, user_id: int, device_name: str | None = None) -> str:
        """Register a trusted device for the user.

        Returns a device token that the client should store (e.g. in a
        secure cookie) and send back on subsequent logins.
        """
        raw_token = secrets.token_urlsafe(48)
        device_hash = self._hash_token(raw_token)
        expires_at = (datetime.utcnow() + timedelta(days=TRUST_DURATION_DAYS)).isoformat()

        conn = self._conn()
        try:
            # Clean up expired devices
            conn.execute(
                "DELETE FROM trusted_devices WHERE user_id = ? AND expires_at < ?",
                (user_id, datetime.utcnow().isoformat()),
            )

            # Enforce max devices per user (remove oldest)
            devices = conn.execute(
                "SELECT id FROM trusted_devices WHERE user_id = ? ORDER BY created_at ASC",
                (user_id,),
            ).fetchall()
            excess = len(devices) - MAX_DEVICES_PER_USER + 1
            if excess > 0:
                ids_to_remove = [r["id"] for r in devices[:excess]]
                placeholders = ",".join("?" * len(ids_to_remove))
                conn.execute(
                    f"DELETE FROM trusted_devices WHERE id IN ({placeholders})",  # nosec B608
                    ids_to_remove,
                )

            conn.execute(
                "INSERT INTO trusted_devices (user_id, device_hash, device_name, expires_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, device_hash, device_name, expires_at),
            )
            conn.commit()
            logger.info("Device trusted for user_id=%d (name=%s)", user_id, device_name)
        finally:
            conn.close()

        return raw_token

    def is_trusted(self, user_id: int, device_token: str) -> bool:
        """Check if a device token is valid and trusted for the given user."""
        if not device_token:
            return False

        device_hash = self._hash_token(device_token)
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, expires_at FROM trusted_devices "
                "WHERE user_id = ? AND device_hash = ?",
                (user_id, device_hash),
            ).fetchone()

            if not row:
                return False

            if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
                conn.execute("DELETE FROM trusted_devices WHERE id = ?", (row["id"],))
                conn.commit()
                return False

            # Update last_used_at
            conn.execute(
                "UPDATE trusted_devices SET last_used_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def revoke_device(self, user_id: int, device_token: str) -> bool:
        """Revoke trust for a specific device."""
        device_hash = self._hash_token(device_token)
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM trusted_devices WHERE user_id = ? AND device_hash = ?",
                (user_id, device_hash),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def revoke_all_devices(self, user_id: int) -> int:
        """Revoke all trusted devices for a user."""
        conn = self._conn()
        try:
            cur = conn.execute(
                "DELETE FROM trusted_devices WHERE user_id = ?", (user_id,),
            )
            conn.commit()
            logger.info("Revoked all trusted devices for user_id=%d", user_id)
            return cur.rowcount
        finally:
            conn.close()

    def list_devices(self, user_id: int) -> list[dict]:
        """List all trusted devices for a user."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, device_name, last_used_at, created_at, expires_at "
                "FROM trusted_devices WHERE user_id = ? ORDER BY last_used_at DESC",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
