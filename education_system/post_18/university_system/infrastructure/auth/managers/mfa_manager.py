"""
Multi-Factor Authentication (MFA) Manager Module

This module handles MFA/2FA operations including TOTP setup, recovery codes,
and verification for enhanced account security.

Classes:
    MFAManager: Manages multi-factor authentication operations
"""

from typing import Dict, List, Optional
import hashlib
import secrets
import logging
from datetime import datetime
import pyotp
import io
import base64

from education_system.post_18.university_system.infrastructure.database.db import sqlite3

logger = logging.getLogger(__name__)

__all__ = ['MFAManager']


class MFAManager:
    """
    Manager for Multi-Factor Authentication operations.

    This class handles 2FA/MFA setup, verification, recovery codes, and
    TOTP secret management for enhanced account security.

    Attributes:
        db_manager: Database manager instance for data operations
        activity_logger: Activity logger for audit trails
    """

    def __init__(self, db_manager, activity_logger):
        """
        Initialize the MFAManager.

        Parameters:
            db_manager: Database manager instance
            activity_logger: Activity logger instance
        """
        self.db_manager = db_manager
        self.activity_logger = activity_logger

    def _generate_secret(self) -> str:
        """
        Generate a new TOTP secret.

        Returns:
            str: Base32 encoded secret for TOTP
        """
        return pyotp.random_base32()

    def _generate_recovery_codes(self, count: int = 10) -> List[str]:
        """
        Generate recovery codes for 2FA.

        Parameters:
            count: Number of recovery codes to generate (default 10)

        Returns:
            list: List of recovery codes in format XXXX-XXXX
        """
        codes = []
        for _ in range(count):
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(f"{code[:4]}-{code[4:]}")
        return codes

    def _hash_recovery_code(self, code: str, salt: str = None) -> str:
        """
        Hash a recovery code for secure storage using salted SHA256.

        Parameters:
            code: Recovery code to hash
            salt: Optional salt (generated if not provided)

        Returns:
            str: Salt and hash in format 'salt$hash'
        """
        if salt is None:
            salt = secrets.token_hex(16)
        code_hash = hashlib.sha256((salt + code).encode()).hexdigest()
        return f"{salt}${code_hash}"

    def _verify_recovery_code(self, code: str, stored_hash: str) -> bool:
        """
        Verify a recovery code against a stored salted hash.

        Parameters:
            code: Recovery code to verify
            stored_hash: Stored hash in format 'salt$hash'

        Returns:
            bool: True if code matches
        """
        if '$' in stored_hash:
            salt, _ = stored_hash.split('$', 1)
            return secrets.compare_digest(self._hash_recovery_code(code, salt), stored_hash)
        else:
            # Legacy unsalted hash fallback
            return secrets.compare_digest(hashlib.sha256(code.encode()).hexdigest(), stored_hash)

    def enable_two_fa(self, user_id: int) -> Dict[str, any]:
        """
        Enable 2FA for a user.

        Generates a new TOTP secret, recovery codes, and QR code for the user
        to set up 2FA in their authenticator app.

        Parameters:
            user_id: User ID to enable 2FA for

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - secret: str - TOTP secret (if successful)
                  - qr_code: str - Base64 encoded QR code image (if successful)
                  - recovery_codes: list - Recovery codes (if successful)
                  - message: str - Result message

        Notes:
            - Creates QR code for easy scanning
            - Stores hashed recovery codes
            - Returns recovery codes in clear text for user to save
            - Updates user_accounts table with 2FA enabled
        """
        import qrcode
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Generate new secret
                secret = self._generate_secret()

                # Update user account
                cursor.execute(
                    'UPDATE user_accounts SET two_fa_enabled = 1, two_fa_secret = ? WHERE user_id = ?',
                    (secret, user_id)
                )

                # Generate recovery codes
                recovery_codes = self._generate_recovery_codes()

                # Store hashed recovery codes
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for code in recovery_codes:
                    code_hash = self._hash_recovery_code(code)
                    cursor.execute(
                        'INSERT INTO two_fa_recovery_codes (user_id, code_hash, created_at) VALUES (?, ?, ?)',
                        (user_id, code_hash, timestamp)
                    )

                conn.commit()

                # Get user info for QR code
                cursor.execute('''
                    SELECT ua.username, u.email
                    FROM user_accounts ua
                    JOIN users u ON ua.user_id = u.id
                    WHERE u.id = ?
                ''', (user_id,))

                user_data = cursor.fetchone()
                username = user_data[0]
                email = user_data[1]

                # Generate TOTP URI for QR code
                totp = pyotp.TOTP(secret)
                provisioning_uri = totp.provisioning_uri(
                    name=email,
                    issuer_name='Student Records System'
                )

                # Generate QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(provisioning_uri)
                qr.make(fit=True)

                # Create QR code image
                img = qr.make_image(fill_color="black", back_color="white")

                # Convert to base64 for display
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                img_base64 = base64.b64encode(img_buffer.getvalue()).decode()

                return {
                    'success': True,
                    'secret': secret,
                    'qr_code': img_base64,
                    'recovery_codes': recovery_codes,
                    'message': '2FA has been enabled successfully.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return {'success': False, 'message': 'Failed to enable 2FA.'}

    def disable_two_fa(self, user_id: int) -> Dict[str, any]:
        """
        Disable 2FA for a user.

        Removes 2FA secret and recovery codes from the database.

        Parameters:
            user_id: User ID to disable 2FA for

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - message: str - Result message

        Notes:
            - Removes TOTP secret from user_accounts
            - Deletes all recovery codes
            - Cannot be undone without re-enabling
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Update user account
                cursor.execute(
                    'UPDATE user_accounts SET two_fa_enabled = 0, two_fa_secret = NULL WHERE user_id = ?',
                    (user_id,)
                )

                # Remove recovery codes
                cursor.execute('DELETE FROM two_fa_recovery_codes WHERE user_id = ?', (user_id,))

                conn.commit()

                return {'success': True, 'message': '2FA has been disabled successfully.'}

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return {'success': False, 'message': 'Failed to disable 2FA.'}

    def verify_two_fa_code(self, user_id: int, code: str) -> bool:
        """
        Verify a 2FA TOTP code.

        Validates a time-based one-time password (TOTP) code against the
        user's secret.

        Parameters:
            user_id: User ID to verify code for
            code: TOTP code to verify

        Returns:
            bool: True if code is valid, False otherwise

        Notes:
            - Allows 1 time step before/after current time (valid_window=1)
            - Typically gives ~90 second window for code validity
            - Returns False if user doesn't have 2FA enabled
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get user's 2FA secret
                cursor.execute(
                    'SELECT two_fa_secret FROM user_accounts WHERE user_id = ? AND two_fa_enabled = 1',
                    (user_id,)
                )

                result = cursor.fetchone()

                if not result or not result[0]:
                    return False

                secret = result[0]

                # Verify TOTP code
                totp = pyotp.TOTP(secret)
                is_valid = totp.verify(code, valid_window=1)  # Allow 1 step before/after

                return is_valid

        except sqlite3.Error as e:
            logger.error(f"Database error verifying 2FA code: {e}")
            return False
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid 2FA code format: {e}")
            return False

    def verify_recovery_code(self, user_id: int, code: str) -> bool:
        """
        Verify and use a recovery code.

        Validates a recovery code and marks it as used. Recovery codes are
        single-use backup codes for 2FA.

        Parameters:
            user_id: User ID to verify code for
            code: Recovery code to verify

        Returns:
            bool: True if code is valid and unused, False otherwise

        Side Effects:
            - Marks recovery code as used if valid
            - Records timestamp of code usage

        Notes:
            - Recovery codes are single-use only
            - Hashes code before database lookup
            - Returns False if code already used or doesn't exist
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Fetch all unused codes for user and verify against each (salted hashes)
                cursor.execute(
                    'SELECT id, code_hash FROM two_fa_recovery_codes WHERE user_id = ? AND is_used = 0',
                    (user_id,)
                )

                rows = cursor.fetchall()
                code_id = None
                for row in rows:
                    if self._verify_recovery_code(code, row[1]):
                        code_id = row[0]
                        break

                if code_id is None:
                    return False

                # Mark code as used
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    'UPDATE two_fa_recovery_codes SET is_used = 1, used_at = ? WHERE id = ?',
                    (timestamp, code_id)
                )

                conn.commit()

                return True

        except Exception as e:
            logger.error(f"Error verifying recovery code: {e}")
            return False

    def regenerate_recovery_codes(self, user_id: int) -> Dict[str, any]:
        """
        Regenerate recovery codes for a user.

        Deletes all existing recovery codes and generates new ones.

        Parameters:
            user_id: User ID to regenerate codes for

        Returns:
            dict: Result dictionary containing:
                  - success: bool - Whether operation succeeded
                  - recovery_codes: list - New recovery codes (if successful)
                  - message: str - Result message

        Notes:
            - Invalidates all previous recovery codes
            - Generates new set of 10 codes
            - User should save new codes immediately
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Delete old recovery codes
                cursor.execute('DELETE FROM two_fa_recovery_codes WHERE user_id = ?', (user_id,))

                # Generate new recovery codes
                recovery_codes = self._generate_recovery_codes()

                # Store hashed recovery codes
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                for code in recovery_codes:
                    code_hash = self._hash_recovery_code(code)
                    cursor.execute(
                        'INSERT INTO two_fa_recovery_codes (user_id, code_hash, created_at) VALUES (?, ?, ?)',
                        (user_id, code_hash, timestamp)
                    )

                conn.commit()

                return {
                    'success': True,
                    'recovery_codes': recovery_codes,
                    'message': 'Recovery codes regenerated successfully.'
                }

        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return {'success': False, 'message': 'Failed to regenerate recovery codes.'}
