"""GDPR consent tracking service.

Manages consent records for data processing across all education systems.
Supports granting, withdrawing, and querying consent by type and user.
"""

import logging
from datetime import datetime

from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)

# Standard consent types for education systems
CONSENT_TYPES = {
    "data_processing": "General data processing for educational purposes",
    "photo_internal": "Use of photographs for internal school purposes",
    "photo_external": "Use of photographs on website/social media",
    "medical_treatment": "Emergency medical treatment consent",
    "data_sharing_authorities": "Sharing data with educational authorities (DfE, Ofsted)",
    "data_sharing_third_party": "Sharing data with third-party services",
    "email_communications": "Receiving email communications",
    "sms_communications": "Receiving SMS communications",
    "marketing": "Marketing communications",
    "biometric_data": "Use of biometric data (fingerprint, facial recognition)",
    "online_platforms": "Use of online learning platforms",
    "trip_activities": "Blanket consent for school trips and activities",
    "research": "Use of anonymised data for research purposes",
    "cookies_analytics": "Website analytics cookies",
    "cookies_functional": "Functional website cookies",
}


class ConsentService:
    """Manages GDPR consent records."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self._ensure_table()

    def _conn(self):
        return connect(self._db_path)

    def _ensure_table(self):
        """Ensure the consent_records table exists (migration-safe)."""
        conn = self._conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS consent_records (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id         INTEGER NOT NULL,
                    consent_type    TEXT    NOT NULL,
                    granted         INTEGER NOT NULL DEFAULT 0,
                    granted_at      TEXT,
                    withdrawn_at    TEXT,
                    ip_address      TEXT,
                    source          TEXT    DEFAULT 'manual',
                    version         TEXT    DEFAULT '1.0',
                    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_consent_user ON consent_records(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_consent_type ON consent_records(consent_type)")
            conn.commit()
        finally:
            conn.close()

    def grant_consent(self, user_id: int, consent_type: str,
                      ip_address: str | None = None, source: str = "manual",
                      version: str = "1.0") -> int:
        """Grant consent for a specific type. Returns the record ID."""
        conn = self._conn()
        try:
            now = datetime.utcnow().isoformat()
            # Check for existing record
            existing = conn.execute(
                "SELECT id FROM consent_records WHERE user_id = ? AND consent_type = ?",
                (user_id, consent_type),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE consent_records SET granted = 1, granted_at = ?,
                       withdrawn_at = NULL, ip_address = ?, source = ?,
                       version = ?, updated_at = ? WHERE id = ?""",
                    (now, ip_address, source, version, now, existing["id"]),
                )
                conn.commit()
                logger.info("Consent re-granted: user_id=%d type=%s", user_id, consent_type)
                return existing["id"]

            cursor = conn.execute(
                """INSERT INTO consent_records
                   (user_id, consent_type, granted, granted_at, ip_address, source, version)
                   VALUES (?, ?, 1, ?, ?, ?, ?)""",
                (user_id, consent_type, now, ip_address, source, version),
            )
            conn.commit()
            logger.info("Consent granted: user_id=%d type=%s", user_id, consent_type)
            return cursor.lastrowid
        finally:
            conn.close()

    def withdraw_consent(self, user_id: int, consent_type: str,
                         ip_address: str | None = None) -> bool:
        """Withdraw consent for a specific type."""
        conn = self._conn()
        try:
            now = datetime.utcnow().isoformat()
            cursor = conn.execute(
                """UPDATE consent_records SET granted = 0, withdrawn_at = ?,
                   ip_address = ?, updated_at = ?
                   WHERE user_id = ? AND consent_type = ? AND granted = 1""",
                (now, ip_address, now, user_id, consent_type),
            )
            conn.commit()
            if cursor.rowcount > 0:
                logger.info("Consent withdrawn: user_id=%d type=%s", user_id, consent_type)
                return True
            return False
        finally:
            conn.close()

    def get_user_consents(self, user_id: int) -> list[dict]:
        """Get all consent records for a user."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM consent_records WHERE user_id = ? ORDER BY consent_type",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def has_consent(self, user_id: int, consent_type: str) -> bool:
        """Check if a user has active consent for a specific type."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT granted FROM consent_records WHERE user_id = ? AND consent_type = ? AND granted = 1",
                (user_id, consent_type),
            ).fetchone()
            return bool(row)
        finally:
            conn.close()

    def get_consent_summary(self, user_id: int) -> dict:
        """Get a summary of all consent types with their status."""
        consents = self.get_user_consents(user_id)
        granted = {c["consent_type"] for c in consents if c["granted"]}
        return {
            ctype: {
                "description": desc,
                "granted": ctype in granted,
            }
            for ctype, desc in CONSENT_TYPES.items()
        }

    def bulk_grant(self, user_id: int, consent_types: list[str],
                   ip_address: str | None = None, source: str = "registration") -> int:
        """Grant multiple consents at once (e.g., during registration)."""
        count = 0
        for ct in consent_types:
            self.grant_consent(user_id, ct, ip_address=ip_address, source=source)
            count += 1
        return count

    def export_consent_history(self, user_id: int) -> list[dict]:
        """Export full consent history for DSAR compliance."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """SELECT consent_type, granted, granted_at, withdrawn_at,
                   source, version, created_at, updated_at
                   FROM consent_records WHERE user_id = ?
                   ORDER BY created_at""",
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
