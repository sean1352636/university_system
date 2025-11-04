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

import sqlite3
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

    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)

    def _hash_value(self, value: str) -> str:
        """Securely hash a value using SHA-256"""
        return hashlib.sha256(value.encode()).hexdigest()

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
                INSERT INTO mfa_methods (user_id, method_type, is_primary, setup_completed_at)
                VALUES (?, 'totp', 1, ?)
                ON CONFLICT(user_id, method_type) DO UPDATE SET
                    is_primary = 1,
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

            conn.commit()

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

            # In production, integrate with SMS provider here
            # For now, return code for testing
            return {
                'success': True,
                'code': code,  # Remove in production
                'expires_at': expires_at.isoformat(),
                'message': f'OTP sent to {phone_number}'
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

            # In production, send email here
            return {
                'success': True,
                'code': code,  # Remove in production
                'expires_at': expires_at.isoformat(),
                'message': f'OTP sent to {email}'
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
                INSERT INTO mfa_user_settings (user_id, mfa_enabled)
                VALUES (?, 1)
                ON CONFLICT(user_id) DO UPDATE SET mfa_enabled = 1
            """, (user_id,))

            conn.commit()
            return {'success': True, 'message': 'MFA enabled successfully'}

        except Exception as e:
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()

    def disable_mfa(self, user_id: int) -> Dict:
        """Disable MFA for a user (admin only)"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Disable all methods
            cursor.execute("UPDATE mfa_methods SET is_enabled = 0 WHERE user_id = ?", (user_id,))

            # Update settings
            cursor.execute("""
                UPDATE mfa_user_settings SET mfa_enabled = 0 WHERE user_id = ?
            """, (user_id,))

            conn.commit()
            return {'success': True, 'message': 'MFA disabled successfully'}

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
    """Quick setup TOTP"""
    service = MFAService()
    return service.setup_totp(user_id, username)


def verify_totp(user_id: int, code: str, device_id: str = None) -> Dict:
    """Quick verify TOTP"""
    service = MFAService()
    return service.verify_totp(user_id, code, device_id)


def generate_sms_otp(user_id: int, phone: str) -> Dict:
    """Quick generate SMS OTP"""
    service = MFAService()
    return service.generate_sms_otp(user_id, phone)


def verify_sms_otp(user_id: int, code: str, device_id: str = None) -> Dict:
    """Quick verify SMS OTP"""
    service = MFAService()
    return service.verify_sms_otp(user_id, code, device_id)


if __name__ == '__main__':
    # Test MFA service
    print("MFA Service initialized successfully")
    service = MFAService()
    print(f"Database: {service.db_path}")
    print("Ready for MFA operations")
