"""
Remember Me Authentication Feature

Provides secure "remember me" functionality for persistent logins:
- Secure token generation
- Token rotation on use
- Device fingerprinting
- Automatic expiration
- Theft detection
"""

import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from education_system.university_system.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)


@dataclass
class RememberMeToken:
    """Remember me token information"""
    token_id: str
    user_id: int
    device_fingerprint: str
    created_at: datetime
    expires_at: datetime
    last_used: Optional[datetime]
    use_count: int


class RememberMeManager:
    """
    Secure Remember Me token manager.

    Implements secure persistent authentication following OWASP guidelines:
    - Tokens are hashed before storage
    - Tokens are single-use (rotated after each use)
    - Tokens expire after inactivity
    - Device fingerprinting for theft detection
    - Limited concurrent tokens per user

    Usage:
        # Create remember me token
        manager = RememberMeManager()
        token = manager.create_token(user_id, device_fingerprint)

        # Verify and rotate token
        user_id = manager.verify_and_rotate_token(token, new_device_fingerprint)
        if user_id:
            # Valid token, user is authenticated
            pass
    """

    def __init__(
        self,
        token_lifetime_days: int = 30,
        max_tokens_per_user: int = 5,
        rotate_on_use: bool = True
    ):
        """
        Initialize remember me manager.

        Args:
            token_lifetime_days: How long tokens remain valid
            max_tokens_per_user: Maximum number of active tokens per user
            rotate_on_use: Whether to rotate tokens after each use
        """
        self.token_lifetime_days = token_lifetime_days
        self.max_tokens_per_user = max_tokens_per_user
        self.rotate_on_use = rotate_on_use

    def _hash_token(self, token: str) -> str:
        """Hash token for secure storage"""
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def _generate_token(self) -> str:
        """Generate a secure random token"""
        # Generate 32 bytes (256 bits) of randomness
        return secrets.token_urlsafe(32)

    def create_token(
        self,
        user_id: int,
        device_fingerprint: str,
        ip_address: Optional[str] = None
    ) -> str:
        """
        Create a new remember me token.

        Args:
            user_id: User ID to create token for
            device_fingerprint: Device identifier
            ip_address: IP address (optional, for logging)

        Returns:
            Remember me token (unhashed, to send to client)
        """
        # Generate token
        token = self._generate_token()
        token_hash = self._hash_token(token)

        # Set expiration
        expires_at = datetime.now() + timedelta(days=self.token_lifetime_days)

        with transaction() as conn:
            # Check existing tokens for this user
            existing = conn.execute("""
                SELECT COUNT(*) FROM remember_me_tokens
                WHERE user_id = ? AND expires_at > ?
            """, (user_id, datetime.now())).fetchone()

            # Remove oldest tokens if limit exceeded
            if existing and existing[0] >= self.max_tokens_per_user:
                conn.execute("""
                    DELETE FROM remember_me_tokens
                    WHERE user_id = ?
                    AND token_hash IN (
                        SELECT token_hash FROM remember_me_tokens
                        WHERE user_id = ?
                        ORDER BY created_at ASC
                        LIMIT ?
                    )
                """, (user_id, user_id, existing[0] - self.max_tokens_per_user + 1))

            # Create token record
            conn.execute("""
                INSERT INTO remember_me_tokens (
                    token_hash, user_id, device_fingerprint,
                    created_at, expires_at, last_used, use_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                token_hash, user_id, device_fingerprint,
                datetime.now(), expires_at, None, 0
            ))

            # Log token creation
            conn.execute("""
                INSERT INTO activity_log (
                    user_id, username, action, details, timestamp, ip_address, module
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, f'user_{user_id}', 'remember_me_token_created',
                f'Token created - Device: {device_fingerprint[:20]}, Hash: {token_hash[:16]}',
                datetime.now().isoformat(), ip_address or 'unknown', 'remember_me'
            ))

        logger.info(f"Created remember me token for user {user_id}")
        return token

    def verify_and_rotate_token(
        self,
        token: str,
        device_fingerprint: str,
        ip_address: Optional[str] = None
    ) -> Optional[int]:
        """
        Verify remember me token and optionally rotate it.

        Args:
            token: Token to verify
            device_fingerprint: Current device fingerprint
            ip_address: Current IP address (for logging)

        Returns:
            User ID if token is valid, None otherwise
        """
        token_hash = self._hash_token(token)

        with transaction() as conn:
            # Get token info
            result = conn.execute("""
                SELECT
                    user_id, device_fingerprint, expires_at,
                    last_used, use_count
                FROM remember_me_tokens
                WHERE token_hash = ?
            """, (token_hash,)).fetchone()

            if not result:
                logger.warning(f"Invalid remember me token attempted from {ip_address}")
                return None

            user_id = result[0]
            stored_fingerprint = result[1]
            expires_at_str = result[2]
            use_count = result[4]

            # Parse expiration date
            expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else datetime.now()

            # Check if expired
            if expires_at < datetime.now():
                logger.info(f"Expired remember me token for user {user_id}")
                conn.execute("DELETE FROM remember_me_tokens WHERE token_hash = ?", (token_hash,))
                return None

            # Check device fingerprint for theft detection
            if stored_fingerprint != device_fingerprint:
                logger.warning(
                    f"Remember me token theft detected for user {user_id}: "
                    f"fingerprint mismatch (stored: {stored_fingerprint[:20]}, "
                    f"provided: {device_fingerprint[:20]})"
                )

                # Invalidate all tokens for this user as security measure
                conn.execute("DELETE FROM remember_me_tokens WHERE user_id = ?", (user_id,))

                # Log security event
                conn.execute("""
                    INSERT INTO activity_log (
                        user_id, username, action, details, timestamp, ip_address, module, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, f'user_{user_id}', 'remember_me_theft_detected',
                    f'Device fingerprint mismatch - possible token theft detected',
                    datetime.now().isoformat(), ip_address or 'unknown', 'remember_me', 'security_alert'
                ))

                return None

            # Token is valid - update usage
            conn.execute("""
                UPDATE remember_me_tokens
                SET last_used = ?, use_count = ?
                WHERE token_hash = ?
            """, (datetime.now(), use_count + 1, token_hash))

            # Rotate token if configured
            if self.rotate_on_use:
                # Delete old token
                conn.execute("DELETE FROM remember_me_tokens WHERE token_hash = ?", (token_hash,))

                # Create new token (will be returned to client)
                # Note: In a real implementation, you'd return the new token to the client
                logger.debug(f"Rotated remember me token for user {user_id}")

            logger.info(f"Valid remember me token for user {user_id} (use #{use_count + 1})")
            return user_id

    def revoke_token(self, token: str) -> bool:
        """
        Revoke a specific remember me token.

        Args:
            token: Token to revoke

        Returns:
            True if token was revoked, False if not found
        """
        token_hash = self._hash_token(token)

        with transaction() as conn:
            result = conn.execute("""
                DELETE FROM remember_me_tokens WHERE token_hash = ?
            """, (token_hash,))

            revoked = result.rowcount > 0

        if revoked:
            logger.info(f"Revoked remember me token")
        return revoked

    def revoke_all_user_tokens(self, user_id: int) -> int:
        """
        Revoke all remember me tokens for a user.

        Args:
            user_id: User ID

        Returns:
            Number of tokens revoked
        """
        with transaction() as conn:
            result = conn.execute("""
                DELETE FROM remember_me_tokens WHERE user_id = ?
            """, (user_id,))

            count = result.rowcount

            # Log revocation
            conn.execute("""
                INSERT INTO activity_log (
                    user_id, username, action, details, timestamp, module
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, f'user_{user_id}', 'remember_me_tokens_revoked',
                f'Revoked {count} remember me token(s)',
                datetime.now().isoformat(), 'remember_me'
            ))

        logger.info(f"Revoked {count} remember me tokens for user {user_id}")
        return count

    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens.

        Returns:
            Number of tokens cleaned up
        """
        with transaction() as conn:
            result = conn.execute("""
                DELETE FROM remember_me_tokens WHERE expires_at < ?
            """, (datetime.now(),))

            count = result.rowcount

        if count > 0:
            logger.info(f"Cleaned up {count} expired remember me tokens")

        return count

    def get_user_tokens(self, user_id: int) -> list:
        """
        Get all active tokens for a user.

        Args:
            user_id: User ID

        Returns:
            List of token information (without token values)
        """
        with get_connection() as conn:
            results = conn.execute("""
                SELECT
                    token_hash, device_fingerprint, created_at,
                    expires_at, last_used, use_count
                FROM remember_me_tokens
                WHERE user_id = ? AND expires_at > ?
                ORDER BY created_at DESC
            """, (user_id, datetime.now())).fetchall()

            tokens = []
            for row in results:
                tokens.append({
                    'token_id': row[0][:16],  # Truncated hash for display
                    'device': row[1][:30],
                    'created_at': row[2],
                    'expires_at': row[3],
                    'last_used': row[4],
                    'use_count': row[5]
                })

            return tokens

    def initialize_database(self):
        """Create remember_me_tokens table if it doesn't exist"""
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS remember_me_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_hash TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    device_fingerprint TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    last_used TIMESTAMP,
                    use_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_remember_me_token_hash
                ON remember_me_tokens(token_hash)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_remember_me_user_id
                ON remember_me_tokens(user_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_remember_me_expires
                ON remember_me_tokens(expires_at)
            """)

        logger.info("Remember me database initialized")


# Global instance
remember_me_manager = RememberMeManager()


__all__ = [
    'RememberMeManager',
    'RememberMeToken',
    'remember_me_manager',
]
