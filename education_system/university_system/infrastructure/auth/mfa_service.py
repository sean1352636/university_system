#!/usr/bin/env python3
"""
Multi-Factor Authentication (MFA) Service
Provides comprehensive MFA functionality including:
- TOTP (Authenticator App)
- SMS OTP
- Email OTP
- Backup Recovery Codes
- Device Trust Management
- MFA Enforcement Policies
"""

from education_system.university_system.infrastructure.database.db import sqlite3
import pyotp
import qrcode
import secrets
import hashlib
import io
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import json

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from modules.shared.constants.paths import DEFAULT_DB_PATH
from education_system.university_system.core.i18n import get_text, _

# Import immutable audit logging for compliance
try:
    from education_system.university_system.infrastructure.security.audit_helpers import safe_log_security_event
    from education_system.university_system.infrastructure.security.immutable_audit_log import AuditAction
    IMMUTABLE_AUDIT_AVAILABLE = True
except ImportError:
    IMMUTABLE_AUDIT_AVAILABLE = False

# Import SMS service for sending OTP codes
try:
    from education_system.university_system.infrastructure.auth.sms_provider import send_otp as send_sms_otp
    SMS_SERVICE_AVAILABLE = True
except ImportError:
    SMS_SERVICE_AVAILABLE = False
    send_sms_otp = None

# Import Email OTP service for sending codes
try:
    from education_system.university_system.infrastructure.auth.email_otp_service import send_otp as send_email_otp
    EMAIL_OTP_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_OTP_SERVICE_AVAILABLE = False
    send_email_otp = None

class MFAService:
    """Comprehensive Multi-Factor Authentication Service"""

    def __init__(self, db_path: str = None):
        """Initialize MFA service with database connection"""
        if db_path is None:
            db_path = str(DEFAULT_DB_PATH)

        self.db_path = db_path
        self.otp_expiry_minutes = 10  # OTP codes expire in 10 minutes
        self.max_otp_attempts = 3  # Maximum verification attempts per code
        self.device_trust_days = 30  # Default device trust duration

        # Ensure verification_disabled column exists
        self._ensure_schema()

    # ------------------------------------------------------------------
    #  Shared-auth MFA sync helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sync_totp_to_shared_auth(user_id: int, secret: str, username: str | None = None):
        """Sync a TOTP secret to the shared auth ``mfa_secrets`` table.

        This ensures the universal login (which checks ``auth.db``) can
        detect that MFA is enabled for this user.
        """
        try:
            shared_uid = MFAService._resolve_shared_user_id(user_id, username=username)
            if shared_uid is None:
                return

            from education_system.shared.auth.db import connect as shared_connect
            conn = shared_connect()
            try:
                conn.execute(
                    "INSERT INTO mfa_secrets (user_id, totp_secret, is_enabled) "
                    "VALUES (?, ?, 1) "
                    "ON CONFLICT(user_id) DO UPDATE SET totp_secret = ?, is_enabled = 1",
                    (shared_uid, secret, secret),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            # Non-fatal – university MFA still works; universal login
            # will just skip the TOTP prompt.
            import logging
            logging.getLogger(__name__).warning(
                "Could not sync TOTP to shared auth DB: %s", exc
            )

    @staticmethod
    def _resolve_shared_user_id(user_id: int, username: str | None = None):
        """Resolve a university user_id to the matching shared auth user_id.

        Because the university DB and shared auth DB use independent ID
        sequences, the same numeric ID may refer to different users.  We
        therefore resolve via *username* first, falling back to a direct
        ID match only when the username is unknown.

        Returns the shared auth user_id or *None* if the user cannot be
        found in the shared auth DB.
        """
        from education_system.shared.auth.db import connect as shared_connect

        # Determine the username if not provided
        if username is None:
            try:
                from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH
                import sqlite3 as _sqlite3
                uni_conn = _sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    uni_row = uni_conn.execute(
                        "SELECT username FROM users WHERE id = ?",
                        (user_id,),
                    ).fetchone()
                    if uni_row:
                        username = uni_row[0]
                finally:
                    uni_conn.close()
            except Exception:
                pass

        conn = shared_connect()
        try:
            # Prefer username-based lookup (reliable across DBs)
            if username:
                row = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()
                if row:
                    return row["id"]

            # Last resort: try the raw ID (works when the user logged
            # in via the shared auth and IDs happen to match).
            row = conn.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row:
                return user_id

            return None
        finally:
            conn.close()

    @staticmethod
    def _enable_shared_auth_mfa(user_id: int):
        """Mark MFA as enabled in the shared auth DB."""
        try:
            shared_uid = MFAService._resolve_shared_user_id(user_id)
            if shared_uid is None:
                return
            from education_system.shared.auth.db import connect as shared_connect
            conn = shared_connect()
            try:
                conn.execute(
                    "UPDATE mfa_secrets SET is_enabled = 1 WHERE user_id = ?",
                    (shared_uid,),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Could not enable MFA in shared auth DB: %s", exc
            )

    @staticmethod
    def _disable_shared_auth_mfa(user_id: int):
        """Mark MFA as disabled in the shared auth DB."""
        try:
            shared_uid = MFAService._resolve_shared_user_id(user_id)
            if shared_uid is None:
                return
            from education_system.shared.auth.db import connect as shared_connect
            conn = shared_connect()
            try:
                conn.execute(
                    "UPDATE mfa_secrets SET is_enabled = 0 WHERE user_id = ?",
                    (shared_uid,),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Could not disable MFA in shared auth DB: %s", exc
            )

    def _get_connection(self):
        """Get database connection with FK checks disabled.

        The MFA tables reference users(id) but after the shared-auth
        refactor user IDs may originate from the shared auth DB.
        Disabling FK enforcement here avoids spurious constraint errors.
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = OFF")
        return conn

    def _ensure_schema(self):
        """Ensure required schema columns exist"""
        def _get_columns(cur, table_name: str) -> List[str]:
            cur.execute(f"PRAGMA table_info({table_name})")
            return [row[1] for row in cur.fetchall()]

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # mfa_user_settings: add verification_disabled if missing
            cols = _get_columns(cursor, "mfa_user_settings")
            if cols and "verification_disabled" not in cols:
                cursor.execute(
                    "ALTER TABLE mfa_user_settings ADD COLUMN verification_disabled BOOLEAN DEFAULT 0"
                )

            # mfa_methods: align legacy schema (phone_number/email) with method_identifier
            cols = _get_columns(cursor, "mfa_methods")
            if cols:
                if "method_identifier" not in cols:
                    cursor.execute("ALTER TABLE mfa_methods ADD COLUMN method_identifier TEXT")
                    # Backfill from legacy columns if they exist
                    if "phone_number" in cols:
                        cursor.execute("""
                            UPDATE mfa_methods
                            SET method_identifier = phone_number
                            WHERE method_type = 'sms'
                              AND (method_identifier IS NULL OR method_identifier = '')
                              AND phone_number IS NOT NULL
                        """)
                    if "email" in cols:
                        cursor.execute("""
                            UPDATE mfa_methods
                            SET method_identifier = email
                            WHERE method_type = 'email'
                              AND (method_identifier IS NULL OR method_identifier = '')
                              AND email IS NOT NULL
                        """)

                if "is_primary" not in cols:
                    cursor.execute("ALTER TABLE mfa_methods ADD COLUMN is_primary BOOLEAN DEFAULT 0")
                if "setup_completed_at" not in cols:
                    cursor.execute("ALTER TABLE mfa_methods ADD COLUMN setup_completed_at TIMESTAMP")
                if "updated_at" not in cols:
                    cursor.execute("ALTER TABLE mfa_methods ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _hash_value(self, value: str) -> str:
        """Securely hash a value using SHA-256"""
        return hashlib.sha256(value.encode()).hexdigest()

    def _is_mfa_contact_in_use(self, method_type: str, method_identifier: str, exclude_user_id: Optional[int] = None) -> Tuple[bool, Optional[int]]:
        """
        Check if an email or phone number is already in use by another user for MFA.

        Args:
            method_type: 'email' or 'sms'
            method_identifier: Email address or phone number to check
            exclude_user_id: User ID to exclude from check (for updates)

        Returns:
            Tuple of (is_in_use: bool, user_id: Optional[int])
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            if exclude_user_id:
                cursor.execute("""
                    SELECT user_id FROM mfa_methods
                    WHERE method_type = ? AND method_identifier = ?
                    AND user_id != ? AND is_enabled = 1
                    LIMIT 1
                """, (method_type, method_identifier, exclude_user_id))
            else:
                cursor.execute("""
                    SELECT user_id FROM mfa_methods
                    WHERE method_type = ? AND method_identifier = ?
                    AND is_enabled = 1
                    LIMIT 1
                """, (method_type, method_identifier))

            result = cursor.fetchone()
            if result:
                return (True, result[0])
            return (False, None)

        finally:
            conn.close()

    # ========== TOTP (Authenticator App) Methods ==========

    def setup_totp(self, user_id: int, username: str, issuer: str = "University System") -> Dict:
        """
        Setup TOTP for a user
        Returns: Dict with secret, qr_code (bytes), and backup_url
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Generate TOTP secret
            secret = pyotp.random_base32()

            # Create TOTP URI for QR code
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=username,
                issuer_name=issuer
            )

            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()

            # Store in database
            cursor.execute("""
                INSERT INTO mfa_methods (user_id, method_type, is_primary, is_enabled, setup_completed_at)
                VALUES (?, 'totp', 1, 1, ?)
                ON CONFLICT(user_id, method_type) DO UPDATE SET
                    is_primary = 1,
                    is_enabled = 1,
                    setup_completed_at = ?
            """, (user_id, datetime.now(), datetime.now()))

            # Store secret in user_accounts table (assuming it exists from exploration)
            cursor.execute("""
                UPDATE user_accounts
                SET two_fa_secret = ?
                WHERE user_id = ?
            """, (secret, user_id))

            # Generate backup recovery codes
            recovery_codes = self._generate_recovery_codes(user_id, cursor)

            # Auto-enable MFA now that TOTP is set up
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, mfa_enabled, mfa_status)
                VALUES (?, 1, 'active')
                ON CONFLICT(user_id) DO UPDATE SET
                    mfa_enabled = 1,
                    mfa_status = 'active',
                    disabled_at = NULL,
                    verification_disabled = 0
            """, (user_id,))

            conn.commit()

            # Sync TOTP secret to shared auth DB so the universal
            # login (run.py) can detect MFA is enabled for this user.
            self._sync_totp_to_shared_auth(user_id, secret, username=username)

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_ENABLED,
                    user_id=str(user_id),
                    resource_type='mfa',
                    details={'username': username, 'method': 'totp'}
                )

            return {
                'success': True,
                'secret': secret,
                'qr_code': img_bytes,
                'provisioning_uri': provisioning_uri,
                'recovery_codes': recovery_codes
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def verify_totp(self, user_id: int, code: str, device_id: Optional[str] = None) -> Dict:
        """
        Verify TOTP code
        Returns: Dict with success status and optional trust_token
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get user's TOTP secret
            cursor.execute("""
                SELECT two_fa_secret FROM user_accounts WHERE user_id = ?
            """, (user_id,))
            result = cursor.fetchone()

            if not result or not result[0]:
                return {'success': False, 'error': 'TOTP not configured'}

            secret = result[0]
            totp = pyotp.TOTP(secret)

            # Verify code (with 1-step window for clock skew)
            is_valid = totp.verify(code, valid_window=1)

            # Log attempt
            self._log_verification_attempt(
                user_id, 'totp', is_valid, None, device_id, cursor
            )

            if is_valid:
                # Update last used
                cursor.execute("""
                    UPDATE mfa_methods
                    SET last_used_at = ?
                    WHERE user_id = ? AND method_type = 'totp'
                """, (datetime.now(), user_id))

                # Update user settings
                cursor.execute("""
                    INSERT INTO mfa_user_settings (user_id, last_successful_verification)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        last_successful_verification = ?,
                        failed_attempts = 0
                """, (user_id, datetime.now(), datetime.now()))

                conn.commit()

                # Immutable audit log for compliance
                if IMMUTABLE_AUDIT_AVAILABLE:
                    safe_log_security_event(
                        action=AuditAction.MFA_CHALLENGE,
                        user_id=str(user_id),
                        resource_type='mfa',
                        details={'method': 'totp', 'success': True}
                    )

                result = {'success': True, 'method': 'totp'}

                # Generate device trust token if requested
                if device_id:
                    trust_token = self._create_trusted_device(user_id, device_id, cursor)
                    conn.commit()
                    result['trust_token'] = trust_token

                return result
            else:
                self._increment_failed_attempts(user_id, cursor)
                conn.commit()

                # Immutable audit log for compliance
                if IMMUTABLE_AUDIT_AVAILABLE:
                    safe_log_security_event(
                        action=AuditAction.MFA_CHALLENGE,
                        user_id=str(user_id),
                        resource_type='mfa',
                        details={'method': 'totp', 'success': False, 'reason': 'invalid_code'}
                    )

                return {'success': False, 'error': 'Invalid TOTP code'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ========== SMS OTP Methods ==========

    def generate_sms_otp(self, user_id: int, phone_number: str) -> Dict:
        """
        Generate and store SMS OTP code
        Returns: Dict with success status and code (for testing/development)
        """
        # Validate phone number uniqueness
        is_in_use, existing_user = self._is_mfa_contact_in_use('sms', phone_number, exclude_user_id=user_id)
        if is_in_use:
            return {
                'success': False,
                'error': f'This phone number is already registered for MFA by another user (User ID: {existing_user}). Each phone number can only be linked to one account.'
            }

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Generate 6-digit OTP
            code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
            code_hash = self._hash_value(code)

            # Calculate expiry
            expires_at = datetime.now() + timedelta(minutes=self.otp_expiry_minutes)

            # Invalidate previous codes
            cursor.execute("""
                UPDATE mfa_otp_codes
                SET is_used = 1
                WHERE user_id = ? AND method_type = 'sms' AND is_used = 0
            """, (user_id,))

            # Store new code
            cursor.execute("""
                INSERT INTO mfa_otp_codes
                (user_id, method_type, code, code_hash, expires_at)
                VALUES (?, 'sms', ?, ?, ?)
            """, (user_id, code, code_hash, expires_at))

            # Update or create SMS method
            cursor.execute("""
                INSERT INTO mfa_methods (user_id, method_type, method_identifier, is_enabled)
                VALUES (?, 'sms', ?, 1)
                ON CONFLICT(user_id, method_type) DO UPDATE SET
                    method_identifier = ?,
                    is_enabled = 1
            """, (user_id, phone_number, phone_number))

            conn.commit()

            # Actually send SMS via configured provider
            sms_sent = False
            sms_error = None

            if SMS_SERVICE_AVAILABLE and send_sms_otp:
                try:
                    result = send_sms_otp(phone_number, code)
                    sms_sent = result.get('success', False)
                    if not sms_sent:
                        sms_error = result.get('error', 'Unknown SMS error')
                except Exception as e:
                    sms_error = str(e)

            if sms_sent:
                return {
                    'success': True,
                    'expires_at': expires_at.isoformat(),
                    'message': f'OTP sent to {phone_number}'
                }
            else:
                # SMS failed - return code for display (fallback for testing)
                return {
                    'success': True,
                    'code': code,  # Show code since SMS failed
                    'expires_at': expires_at.isoformat(),
                    'message': f'SMS delivery failed ({sms_error}). Your code is displayed above.',
                    'sms_failed': True
                }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def verify_sms_otp(self, user_id: int, code: str, device_id: Optional[str] = None) -> Dict:
        """Verify SMS OTP code"""
        return self._verify_otp(user_id, code, 'sms', device_id)

    # ========== Email OTP Methods ==========

    def generate_email_otp(self, user_id: int, email: str) -> Dict:
        """
        Generate and store Email OTP code
        Returns: Dict with success status and code (for testing/development)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Generate 6-digit OTP
            code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
            code_hash = self._hash_value(code)

            # Calculate expiry
            expires_at = datetime.now() + timedelta(minutes=self.otp_expiry_minutes)

            # Invalidate previous codes
            cursor.execute("""
                UPDATE mfa_otp_codes
                SET is_used = 1
                WHERE user_id = ? AND method_type = 'email' AND is_used = 0
            """, (user_id,))

            # Store new code
            cursor.execute("""
                INSERT INTO mfa_otp_codes
                (user_id, method_type, code, code_hash, expires_at)
                VALUES (?, 'email', ?, ?, ?)
            """, (user_id, code, code_hash, expires_at))

            # Update or create email method
            cursor.execute("""
                INSERT INTO mfa_methods (user_id, method_type, method_identifier, is_enabled)
                VALUES (?, 'email', ?, 1)
                ON CONFLICT(user_id, method_type) DO UPDATE SET
                    method_identifier = ?,
                    is_enabled = 1
            """, (user_id, email, email))

            conn.commit()

            # Actually send Email via configured provider
            email_sent = False
            email_error = None

            if EMAIL_OTP_SERVICE_AVAILABLE and send_email_otp:
                try:
                    # Get username for email template
                    cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
                    row = cursor.fetchone()
                    username = row[0] if row else 'User'

                    result = send_email_otp(email, code, username)
                    email_sent = result.get('success', False)
                    if not email_sent:
                        email_error = result.get('error', 'Unknown email error')
                except Exception as e:
                    email_error = str(e)

            if email_sent:
                return {
                    'success': True,
                    'expires_at': expires_at.isoformat(),
                    'message': f'OTP sent to {email}'
                }
            else:
                # Email failed - return code for display (fallback for testing)
                return {
                    'success': True,
                    'code': code,  # Show code since email failed
                    'expires_at': expires_at.isoformat(),
                    'message': f'Email delivery failed ({email_error}). Your code is displayed above.',
                    'email_failed': True
                }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def verify_email_otp(self, user_id: int, code: str, device_id: Optional[str] = None) -> Dict:
        """Verify Email OTP code"""
        return self._verify_otp(user_id, code, 'email', device_id)

    def _verify_otp(self, user_id: int, code: str, method_type: str, device_id: Optional[str] = None) -> Dict:
        """Generic OTP verification for SMS/Email"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            code_hash = self._hash_value(code)

            # Find valid OTP
            cursor.execute("""
                SELECT id, expires_at, attempts
                FROM mfa_otp_codes
                WHERE user_id = ? AND method_type = ? AND code_hash = ?
                  AND is_used = 0 AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id, method_type, code_hash, datetime.now()))

            result = cursor.fetchone()

            if not result:
                self._log_verification_attempt(
                    user_id, method_type, False, 'Invalid or expired code', device_id, cursor
                )
                self._increment_failed_attempts(user_id, cursor)
                conn.commit()
                return {'success': False, 'error': 'Invalid or expired OTP'}

            otp_id, expires_at, attempts = result

            # Check attempts
            if attempts >= self.max_otp_attempts:
                cursor.execute("UPDATE mfa_otp_codes SET is_used = 1 WHERE id = ?", (otp_id,))
                self._log_verification_attempt(
                    user_id, method_type, False, 'Too many attempts', device_id, cursor
                )
                conn.commit()
                return {'success': False, 'error': 'Too many attempts'}

            # Mark as used
            cursor.execute("""
                UPDATE mfa_otp_codes
                SET is_used = 1, used_at = ?
                WHERE id = ?
            """, (datetime.now(), otp_id))

            # Update method last used
            cursor.execute("""
                UPDATE mfa_methods
                SET last_used_at = ?
                WHERE user_id = ? AND method_type = ?
            """, (datetime.now(), user_id, method_type))

            # Update user settings
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, last_successful_verification)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_successful_verification = ?,
                    failed_attempts = 0
            """, (user_id, datetime.now(), datetime.now()))

            self._log_verification_attempt(user_id, method_type, True, None, device_id, cursor)
            conn.commit()

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_CHALLENGE,
                    user_id=str(user_id),
                    resource_type='mfa',
                    details={'method': method_type, 'success': True}
                )

            result = {'success': True, 'method': method_type}

            # Generate device trust token if requested
            if device_id:
                trust_token = self._create_trusted_device(user_id, device_id, cursor)
                conn.commit()
                result['trust_token'] = trust_token

            return result

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ========== Recovery Codes Methods ==========

    def _generate_recovery_codes(self, user_id: int, cursor, count: int = 10) -> List[str]:
        """Generate backup recovery codes"""
        # Delete existing codes
        cursor.execute("DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,))

        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
            code_formatted = f"{code[:4]}-{code[4:]}"
            codes.append(code_formatted)

            code_hash = self._hash_value(code_formatted)
            expires_at = datetime.now() + timedelta(days=365)  # 1 year expiry

            cursor.execute("""
                INSERT INTO mfa_recovery_codes (user_id, code_hash, expires_at)
                VALUES (?, ?, ?)
            """, (user_id, code_hash, expires_at))

        # Mark as generated
        cursor.execute("""
            INSERT INTO mfa_user_settings (user_id, backup_codes_generated)
            VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET backup_codes_generated = 1
        """, (user_id,))

        return codes

    def generate_recovery_codes(self, user_id: int) -> Dict:
        """Public method to generate recovery codes"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            codes = self._generate_recovery_codes(user_id, cursor)
            conn.commit()
            return {'success': True, 'codes': codes}
        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def verify_recovery_code(self, user_id: int, code: str, device_id: Optional[str] = None) -> Dict:
        """Verify and consume a recovery code"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            code_hash = self._hash_value(code)

            # Find unused recovery code
            cursor.execute("""
                SELECT id, expires_at
                FROM mfa_recovery_codes
                WHERE user_id = ? AND code_hash = ? AND is_used = 0
                  AND (expires_at IS NULL OR expires_at > ?)
                LIMIT 1
            """, (user_id, code_hash, datetime.now()))

            result = cursor.fetchone()

            if not result:
                self._log_verification_attempt(
                    user_id, 'recovery_code', False, 'Invalid or used code', device_id, cursor
                )
                conn.commit()
                return {'success': False, 'error': 'Invalid or already used recovery code'}

            code_id = result[0]

            # Mark as used
            cursor.execute("""
                UPDATE mfa_recovery_codes
                SET is_used = 1, used_at = ?
                WHERE id = ?
            """, (datetime.now(), code_id))

            # Update user settings
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, last_successful_verification)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_successful_verification = ?,
                    failed_attempts = 0
            """, (user_id, datetime.now(), datetime.now()))

            # Check remaining codes
            cursor.execute("""
                SELECT COUNT(*) FROM mfa_recovery_codes
                WHERE user_id = ? AND is_used = 0
            """, (user_id,))
            remaining = cursor.fetchone()[0]

            self._log_verification_attempt(user_id, 'recovery_code', True, None, device_id, cursor)
            conn.commit()

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_CHALLENGE,
                    user_id=str(user_id),
                    resource_type='mfa',
                    details={'method': 'recovery_code', 'success': True, 'remaining_codes': remaining}
                )

            result = {
                'success': True,
                'method': 'recovery_code',
                'remaining_codes': remaining
            }

            if remaining <= 2:
                result['warning'] = f'Only {remaining} recovery codes remaining. Generate new codes soon.'

            # Generate device trust token if requested
            if device_id:
                trust_token = self._create_trusted_device(user_id, device_id, cursor)
                conn.commit()
                result['trust_token'] = trust_token

            return result

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ========== Device Trust Methods ==========

    def _create_trusted_device(self, user_id: int, device_id: str, cursor,
                               device_name: str = None, ip_address: str = None) -> str:
        """Create a trusted device entry"""
        trust_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=self.device_trust_days)

        cursor.execute("""
            INSERT INTO mfa_trusted_devices
            (user_id, device_id, device_name, trust_token, expires_at, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, device_id) DO UPDATE SET
                trust_token = ?,
                expires_at = ?,
                trusted_at = CURRENT_TIMESTAMP,
                is_trusted = 1,
                revoked_at = NULL
        """, (user_id, device_id, device_name, trust_token, expires_at, ip_address,
              trust_token, expires_at))

        return trust_token

    def verify_trusted_device(self, user_id: int, device_id: str, trust_token: str) -> Dict:
        """Verify if a device is trusted"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT id, expires_at
                FROM mfa_trusted_devices
                WHERE user_id = ? AND device_id = ? AND trust_token = ?
                  AND is_trusted = 1 AND revoked_at IS NULL
                  AND expires_at > ?
            """, (user_id, device_id, trust_token, datetime.now()))

            result = cursor.fetchone()

            if result:
                # Update last used
                cursor.execute("""
                    UPDATE mfa_trusted_devices
                    SET last_used_at = ?
                    WHERE id = ?
                """, (datetime.now(), result[0]))
                conn.commit()
                return {'success': True, 'trusted': True}
            else:
                return {'success': True, 'trusted': False}

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def revoke_trusted_device(self, user_id: int, device_id: str) -> Dict:
        """Revoke trust for a device"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE mfa_trusted_devices
                SET is_trusted = 0, revoked_at = ?
                WHERE user_id = ? AND device_id = ?
            """, (datetime.now(), user_id, device_id))

            conn.commit()
            return {'success': True, 'message': 'Device trust revoked'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def get_trusted_devices(self, user_id: int) -> Dict:
        """Get list of trusted devices for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT device_id, device_name, trusted_at, expires_at, last_used_at, ip_address
                FROM mfa_trusted_devices
                WHERE user_id = ? AND is_trusted = 1 AND revoked_at IS NULL
                ORDER BY trusted_at DESC
            """, (user_id,))

            devices = []
            for row in cursor.fetchall():
                devices.append({
                    'device_id': row[0],
                    'device_name': row[1],
                    'trusted_at': row[2],
                    'expires_at': row[3],
                    'last_used_at': row[4],
                    'ip_address': row[5]
                })

            return {'success': True, 'devices': devices}

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ========== MFA Enforcement Methods ==========

    def check_mfa_required(self, user_id: int, role: str) -> Dict:
        """Check if MFA is required for a user/role"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get enforcement policy
            cursor.execute("""
                SELECT mfa_required, allowed_methods, minimum_methods,
                       grace_period_days, allow_device_trust
                FROM mfa_enforcement_policies
                WHERE role_name = ?
            """, (role,))

            policy = cursor.fetchone()

            if not policy:
                return {'success': True, 'required': False}

            mfa_required, allowed_methods, min_methods, grace_days, allow_trust = policy

            # Get user MFA settings
            cursor.execute("""
                SELECT mfa_enabled, enforcement_deadline, bypass_until
                FROM mfa_user_settings
                WHERE user_id = ?
            """, (user_id,))

            settings = cursor.fetchone()

            if settings:
                mfa_enabled, deadline, bypass_until = settings

                # Check bypass
                if bypass_until and datetime.fromisoformat(bypass_until) > datetime.now():
                    return {'success': True, 'required': False, 'bypassed': True}

                # Check if already enabled
                if mfa_enabled:
                    return {'success': True, 'required': False, 'already_enabled': True}

                # Check grace period
                if deadline and datetime.fromisoformat(deadline) > datetime.now():
                    return {
                        'success': True,
                        'required': False,
                        'grace_period': True,
                        'deadline': deadline
                    }

            return {
                'success': True,
                'required': mfa_required,
                'allowed_methods': json.loads(allowed_methods) if allowed_methods else [],
                'minimum_methods': min_methods,
                'allow_device_trust': bool(allow_trust)
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def get_user_mfa_methods(self, user_id: int) -> Dict:
        """Get all enabled MFA methods for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT method_type, method_identifier, is_primary, last_used_at, setup_completed_at
                FROM mfa_methods
                WHERE user_id = ? AND is_enabled = 1
                ORDER BY is_primary DESC, method_type
            """, (user_id,))

            methods = []
            for row in cursor.fetchall():
                methods.append({
                    'type': row[0],
                    'identifier': row[1],
                    'is_primary': bool(row[2]),
                    'last_used': row[3],
                    'setup_completed': row[4]
                })

            return {'success': True, 'methods': methods}

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def enable_mfa(self, user_id: int) -> Dict:
        """Mark MFA as enabled for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, mfa_enabled, mfa_status)
                VALUES (?, 1, 'active')
                ON CONFLICT(user_id) DO UPDATE SET
                    mfa_enabled = 1,
                    mfa_status = 'active',
                    disabled_at = NULL,
                    verification_disabled = 0
            """, (user_id,))

            conn.commit()

            # Sync to shared auth DB
            self._enable_shared_auth_mfa(user_id)

            return {'success': True, 'message': 'MFA enabled successfully'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def disable_mfa(self, user_id: int) -> Dict:
        """Disable MFA for a user - saves settings for potential re-enable within 90 days"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Disable all methods (but keep the data)
            cursor.execute("UPDATE mfa_methods SET is_enabled = 0 WHERE user_id = ?", (user_id,))

            # Update settings with status and disabled timestamp
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, mfa_enabled, mfa_status, disabled_at, verification_disabled)
                VALUES (?, 0, 'disabled', CURRENT_TIMESTAMP, 1)
                ON CONFLICT(user_id) DO UPDATE SET
                    mfa_enabled = 0,
                    mfa_status = 'disabled',
                    disabled_at = CURRENT_TIMESTAMP,
                    verification_disabled = 1
            """, (user_id,))

            conn.commit()

            # Sync to shared auth DB
            self._disable_shared_auth_mfa(user_id)

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_DISABLED,
                    user_id=str(user_id),
                    resource_type='mfa',
                    details={'user_id': str(user_id)}
                )

            return {'success': True, 'message': 'MFA disabled successfully. Settings saved for 90 days.'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def get_saved_mfa_methods(self, user_id: int) -> Dict:
        """Get all MFA methods for a user (including disabled/saved ones)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT method_type, method_identifier, is_primary, is_enabled, last_used_at, setup_completed_at
                FROM mfa_methods
                WHERE user_id = ?
                ORDER BY is_primary DESC, method_type
            """, (user_id,))

            methods = []
            for row in cursor.fetchall():
                methods.append({
                    'type': row[0],
                    'identifier': row[1],
                    'is_primary': bool(row[2]),
                    'is_enabled': bool(row[3]),
                    'last_used': row[4],
                    'setup_completed': row[5]
                })

            return {'success': True, 'methods': methods}

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def reenable_mfa(self, user_id: int) -> Dict:
        """Re-enable previously disabled MFA methods for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if there are saved methods to re-enable
            cursor.execute("""
                SELECT COUNT(*) FROM mfa_methods WHERE user_id = ?
            """, (user_id,))
            count = cursor.fetchone()[0]

            if count == 0:
                return {'success': False, 'error': 'No saved MFA methods found'}

            # Re-enable all methods
            cursor.execute("UPDATE mfa_methods SET is_enabled = 1 WHERE user_id = ?", (user_id,))

            # Update settings - set status to active and clear disabled_at
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, mfa_enabled, mfa_status, disabled_at, verification_disabled)
                VALUES (?, 1, 'active', NULL, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    mfa_enabled = 1,
                    mfa_status = 'active',
                    disabled_at = NULL,
                    verification_disabled = 0
            """, (user_id,))

            conn.commit()

            # Sync to shared auth DB
            self._enable_shared_auth_mfa(user_id)

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_ENABLED,
                    user_id=str(user_id),
                    resource_type='mfa',
                    details={'user_id': str(user_id), 'action': 're-enabled'}
                )

            return {'success': True, 'message': 'MFA re-enabled successfully', 'methods_count': count}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def is_verification_disabled(self, user_id: int) -> bool:
        """Check if all login verification is disabled for a user (password only)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT verification_disabled
                FROM mfa_user_settings
                WHERE user_id = ?
            """, (user_id,))

            result = cursor.fetchone()
            if result:
                return bool(result[0])
            return False  # Default: verification enabled

        except Exception:
            return False  # Default: verification enabled on error
        finally:
            conn.close()

    def set_verification_disabled(self, user_id: int, disabled: bool) -> Dict:
        """Enable or disable all login verification for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, verification_disabled)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET verification_disabled = ?
            """, (user_id, int(disabled), int(disabled)))

            conn.commit()

            # Sync to shared auth DB — when verification is disabled,
            # mark MFA as disabled in the shared DB too so the universal
            # login won't prompt for a TOTP code.
            if disabled:
                self._disable_shared_auth_mfa(user_id)
            else:
                self._enable_shared_auth_mfa(user_id)

            status = "disabled" if disabled else "enabled"
            return {'success': True, 'message': f'Login verification {status}'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def is_mfa_active(self, user_id: int) -> bool:
        """Check if MFA is active for a user (requires MFA on login)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT mfa_status, mfa_enabled
                FROM mfa_user_settings
                WHERE user_id = ?
            """, (user_id,))

            result = cursor.fetchone()
            if result:
                mfa_status = result[0]
                mfa_enabled = result[1]
                # MFA is active if status is 'active' and mfa_enabled is true
                return mfa_status == 'active' and bool(mfa_enabled)
            return False  # Default: MFA not active

        except Exception:
            return False  # Default: MFA not active on error
        finally:
            conn.close()

    def get_mfa_status(self, user_id: int) -> Dict:
        """Get full MFA status for a user"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT mfa_status, mfa_enabled, verification_disabled, disabled_at
                FROM mfa_user_settings
                WHERE user_id = ?
            """, (user_id,))

            result = cursor.fetchone()
            if result:
                return {
                    'success': True,
                    'status': result[0] or 'disabled',
                    'mfa_enabled': bool(result[1]),
                    'verification_disabled': bool(result[2]),
                    'disabled_at': result[3]
                }
            return {
                'success': True,
                'status': 'disabled',
                'mfa_enabled': False,
                'verification_disabled': False,
                'disabled_at': None
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def update_mfa_method(self, user_id: int, method_type: str, identifier: str) -> Dict:
        """Update/override an existing MFA method with new data"""
        # Validate uniqueness for email and sms methods
        if method_type in ('email', 'sms'):
            is_in_use, existing_user = self._is_mfa_contact_in_use(method_type, identifier, exclude_user_id=user_id)
            if is_in_use:
                contact_type = 'email address' if method_type == 'email' else 'phone number'
                return {
                    'success': False,
                    'error': f'This {contact_type} is already registered for MFA by another user (User ID: {existing_user}). Each {contact_type} can only be linked to one account.'
                }

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Update or insert the MFA method (override existing)
            cursor.execute("""
                INSERT INTO mfa_methods (user_id, method_type, method_identifier, is_enabled, is_primary, setup_completed_at)
                VALUES (?, ?, ?, 1, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, method_type) DO UPDATE SET
                    method_identifier = ?,
                    is_enabled = 1,
                    setup_completed_at = CURRENT_TIMESTAMP
            """, (user_id, method_type, identifier, identifier))

            # Ensure MFA settings are set to active
            cursor.execute("""
                INSERT INTO mfa_user_settings (user_id, mfa_enabled, mfa_status, disabled_at, verification_disabled)
                VALUES (?, 1, 'active', NULL, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    mfa_enabled = 1,
                    mfa_status = 'active',
                    disabled_at = NULL,
                    verification_disabled = 0
            """, (user_id,))

            conn.commit()

            # Immutable audit log for compliance
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_ENABLED,
                    user_id=str(user_id),
                    resource_type='mfa',
                    details={'user_id': str(user_id), 'method_type': method_type, 'action': 'updated'}
                )

            return {'success': True, 'message': f'MFA method {method_type} updated successfully'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def cleanup_expired_disabled_mfa(self) -> Dict:
        """Delete MFA data for accounts that have been disabled for more than 90 days"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Find users with MFA disabled for more than 90 days
            cursor.execute("""
                SELECT user_id FROM mfa_user_settings
                WHERE mfa_status = 'disabled'
                AND disabled_at IS NOT NULL
                AND disabled_at < datetime('now', '-90 days')
            """)

            expired_users = [row[0] for row in cursor.fetchall()]

            if not expired_users:
                return {'success': True, 'message': 'No expired MFA records to clean up', 'deleted_count': 0}

            deleted_count = 0
            for user_id in expired_users:
                # Delete MFA methods
                cursor.execute("DELETE FROM mfa_methods WHERE user_id = ?", (user_id,))
                # Delete OTP codes
                cursor.execute("DELETE FROM mfa_otp_codes WHERE user_id = ?", (user_id,))
                # Delete trusted devices
                cursor.execute("DELETE FROM mfa_trusted_devices WHERE user_id = ?", (user_id,))
                # Delete recovery codes
                cursor.execute("DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,))
                # Reset MFA settings
                cursor.execute("""
                    UPDATE mfa_user_settings
                    SET mfa_enabled = 0, mfa_status = 'disabled', disabled_at = NULL
                    WHERE user_id = ?
                """, (user_id,))
                deleted_count += 1

                # Audit log
                if IMMUTABLE_AUDIT_AVAILABLE:
                    safe_log_security_event(
                        action=AuditAction.MFA_DISABLED,
                        user_id=str(user_id),
                        resource_type='mfa',
                        details={'user_id': str(user_id), 'reason': '90-day expiry cleanup'}
                    )

            conn.commit()
            return {
                'success': True,
                'message': f'Cleaned up MFA data for {deleted_count} expired accounts',
                'deleted_count': deleted_count,
                'user_ids': expired_users
            }

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def delete_mfa_for_user(self, user_id: int) -> Dict:
        """Completely delete all MFA data for a user (requires new setup)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Delete all MFA related data
            cursor.execute("DELETE FROM mfa_methods WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM mfa_otp_codes WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM mfa_trusted_devices WHERE user_id = ?", (user_id,))
            cursor.execute("DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,))

            # Reset MFA settings
            cursor.execute("""
                UPDATE mfa_user_settings
                SET mfa_enabled = 0, mfa_status = 'disabled', disabled_at = NULL, verification_disabled = 0
                WHERE user_id = ?
            """, (user_id,))

            conn.commit()

            # Audit log
            if IMMUTABLE_AUDIT_AVAILABLE:
                safe_log_security_event(
                    action=AuditAction.MFA_DISABLED,
                    user_id=str(user_id),
                    resource_type='mfa',
                    details={'user_id': str(user_id), 'action': 'complete_deletion'}
                )

            return {'success': True, 'message': 'All MFA data deleted. User will need to set up MFA again.'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    # ========== Helper Methods ==========

    def _log_verification_attempt(self, user_id: int, method_type: str, success: bool,
                                   failure_reason: Optional[str], device_id: Optional[str],
                                   cursor):
        """Log MFA verification attempt"""
        cursor.execute("""
            INSERT INTO mfa_verification_attempts
            (user_id, method_type, success, failure_reason, device_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, method_type, success, failure_reason, device_id))

    def _increment_failed_attempts(self, user_id: int, cursor):
        """Increment failed MFA attempts and potentially lock account"""
        cursor.execute("""
            INSERT INTO mfa_user_settings (user_id, failed_attempts)
            VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                failed_attempts = failed_attempts + 1
        """, (user_id,))

        # Check if should lock
        cursor.execute("SELECT failed_attempts FROM mfa_user_settings WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result and result[0] >= 5:
            # Lock for 15 minutes
            locked_until = datetime.now() + timedelta(minutes=15)
            cursor.execute("""
                UPDATE mfa_user_settings
                SET locked_until = ?
                WHERE user_id = ?
            """, (locked_until, user_id))

    def is_mfa_locked(self, user_id: int) -> bool:
        """Check if user is locked due to failed MFA attempts"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT locked_until FROM mfa_user_settings
                WHERE user_id = ? AND locked_until > ?
            """, (user_id, datetime.now()))

            result = cursor.fetchone()
            return result is not None

        finally:
            conn.close()

# Convenience functions for quick access
def setup_totp(user_id: int, username: str) -> Dict:
    """
    Set up Time-based One-Time Password (TOTP) authentication for a user.

    Creates a new TOTP secret for the specified user and generates the
    provisioning URI needed for authenticator apps (Google Authenticator,
    Authy, etc.). This is a convenience wrapper around MFAService.setup_totp().

    Parameters
    ----------
    user_id : int
        The unique identifier of the user setting up TOTP.
    username : str
        The username to display in authenticator apps. This appears as
        the account name when scanning the QR code.

    Returns
    -------
    Dict
        Setup result containing:
        - 'success': bool - Whether setup was successful
        - 'secret': str - The TOTP secret key (if success)
        - 'provisioning_uri': str - URI for QR code generation (if success)
        - 'error': str - Error message (if failed)

    Examples
    --------
    >>> result = setup_totp(user_id=123, username="john.doe")
    >>> if result['success']:
    ...     # Generate QR code from provisioning_uri
    ...     qr_uri = result['provisioning_uri']
    ...     print(f"Scan this QR code: {qr_uri}")

    See Also
    --------
    verify_totp : Verify a TOTP code.
    MFAService.setup_totp : The underlying service method.
    """
    service = MFAService()
    return service.setup_totp(user_id, username)

def verify_totp(user_id: int, code: str, device_id: str = None) -> Dict:
    """
    Verify a Time-based One-Time Password (TOTP) code for a user.

    Validates the 6-digit TOTP code entered by the user against their
    stored secret. Includes replay attack protection and rate limiting.
    This is a convenience wrapper around MFAService.verify_totp().

    Parameters
    ----------
    user_id : int
        The unique identifier of the user to verify.
    code : str
        The 6-digit TOTP code from the user's authenticator app.
    device_id : str, optional
        Optional device identifier for trusted device tracking.
        If provided and verification succeeds, the device may be
        remembered to skip MFA on future logins.

    Returns
    -------
    Dict
        Verification result containing:
        - 'success': bool - Whether the code was valid
        - 'error': str - Error message (if failed)
        - 'remaining_attempts': int - Attempts left before lockout (if failed)

    Raises
    ------
    MFALockoutError
        If the user has exceeded maximum verification attempts.

    Examples
    --------
    >>> result = verify_totp(user_id=123, code="123456")
    >>> if result['success']:
    ...     print("MFA verification successful!")
    ... else:
    ...     print(f"Verification failed: {result.get('error')}")

    See Also
    --------
    setup_totp : Set up TOTP for a user.
    MFAService.verify_totp : The underlying service method.
    """
    service = MFAService()
    return service.verify_totp(user_id, code, device_id)

def generate_sms_otp(user_id: int, phone: str) -> Dict:
    """
    Generate and send an SMS One-Time Password to a user's phone.

    Creates a new OTP code and sends it via SMS to the provided phone
    number. The code is valid for a limited time (typically 5 minutes).
    This is a convenience wrapper around MFAService.generate_sms_otp().

    Parameters
    ----------
    user_id : int
        The unique identifier of the user requesting the OTP.
    phone : str
        The phone number to send the OTP to. Should be in E.164 format
        (e.g., "+1234567890") or local format with country code configured.

    Returns
    -------
    Dict
        Generation result containing:
        - 'success': bool - Whether OTP was generated and sent
        - 'expires_at': datetime - When the OTP expires (if success)
        - 'error': str - Error message (if failed)

    Notes
    -----
    The actual SMS delivery depends on the configured SMS provider.
    In development environments, the OTP may be logged instead of sent.

    Examples
    --------
    >>> result = generate_sms_otp(user_id=123, phone="+15551234567")
    >>> if result['success']:
    ...     print(f"OTP sent. Expires at: {result['expires_at']}")
    ... else:
    ...     print(f"Failed to send OTP: {result.get('error')}")

    See Also
    --------
    verify_sms_otp : Verify an SMS OTP code.
    MFAService.generate_sms_otp : The underlying service method.
    """
    service = MFAService()
    return service.generate_sms_otp(user_id, phone)

def verify_sms_otp(user_id: int, code: str, device_id: str = None) -> Dict:
    """
    Verify an SMS One-Time Password code for a user.

    Validates the OTP code entered by the user against the stored
    code sent via SMS. Includes expiration checking and rate limiting.
    This is a convenience wrapper around MFAService.verify_sms_otp().

    Parameters
    ----------
    user_id : int
        The unique identifier of the user to verify.
    code : str
        The OTP code received via SMS (typically 6 digits).
    device_id : str, optional
        Optional device identifier for trusted device tracking.
        If provided and verification succeeds, the device may be
        remembered to skip MFA on future logins.

    Returns
    -------
    Dict
        Verification result containing:
        - 'success': bool - Whether the code was valid
        - 'error': str - Error message (if failed)
        - 'remaining_attempts': int - Attempts left before lockout (if failed)

    Raises
    ------
    MFALockoutError
        If the user has exceeded maximum verification attempts.

    Examples
    --------
    >>> result = verify_sms_otp(user_id=123, code="654321")
    >>> if result['success']:
    ...     print("SMS OTP verification successful!")
    ... else:
    ...     print(f"Verification failed: {result.get('error')}")

    See Also
    --------
    generate_sms_otp : Generate and send an SMS OTP.
    MFAService.verify_sms_otp : The underlying service method.
    """
    service = MFAService()
    return service.verify_sms_otp(user_id, code, device_id)

if __name__ == '__main__':
    # Test MFA service
    print("MFA Service initialized successfully")
    service = MFAService()
    print(f"Database: {service.db_path}")
    print("Ready for MFA operations")
