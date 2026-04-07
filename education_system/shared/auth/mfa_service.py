"""Multi-Factor Authentication service using TOTP."""

import hashlib
import secrets
import string
import logging
import time

import bcrypt as _bcrypt
import pyotp

from education_system.shared.auth.exceptions import MFAError
from education_system.shared.auth.db import connect

logger = logging.getLogger(__name__)

# Rate limiting for recovery code verification
_recovery_attempts: dict[int, list[float]] = {}
_RECOVERY_MAX_ATTEMPTS = 5
_RECOVERY_LOCKOUT_SECONDS = 15 * 60  # 15 minutes


class MFAService:
    """Service for TOTP-based multi-factor authentication."""

    RECOVERY_CODE_COUNT = 10

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path

    def _conn(self):
        return connect(self._db_path)

    @staticmethod
    def _hash_code(code: str) -> str:
        """Bcrypt hash a recovery code for offline attack resistance."""
        normalised = code.strip().upper().encode("utf-8")
        return _bcrypt.hashpw(normalised, _bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_code_hash(code: str, code_hash: str) -> bool:
        """Verify a recovery code against its hash.

        Supports both new bcrypt hashes and legacy SHA-256 hashes (64 hex
        chars, no ``$`` prefix) for codes created before the upgrade.
        """
        normalised = code.strip().upper()
        # Legacy SHA-256 detection
        if len(code_hash) == 64 and not code_hash.startswith("$"):
            return hashlib.sha256(normalised.encode()).hexdigest() == code_hash
        try:
            return _bcrypt.checkpw(normalised.encode("utf-8"), code_hash.encode("utf-8"))
        except (ValueError, AttributeError):
            return False

    @staticmethod
    def _generate_recovery_code() -> str:
        """Generate a single recovery code in XXXX-XXXX format."""
        chars = string.ascii_uppercase + string.digits
        part1 = "".join(secrets.choice(chars) for _ in range(4))
        part2 = "".join(secrets.choice(chars) for _ in range(4))
        return f"{part1}-{part2}"

    def setup_totp(self, user_id: int, username: str) -> dict:
        """Set up TOTP for a user. Returns secret, provisioning URI, and recovery codes."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,))

            secret = pyotp.random_base32()
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=username, issuer_name="Education System"
            )

            conn.execute(
                "INSERT INTO mfa_secrets (user_id, totp_secret, is_enabled) VALUES (?, ?, 1)",
                (user_id, secret),
            )

            codes = []
            for _ in range(self.RECOVERY_CODE_COUNT):
                code = self._generate_recovery_code()
                codes.append(code)
                conn.execute(
                    "INSERT INTO mfa_recovery_codes (user_id, code_hash) VALUES (?, ?)",
                    (user_id, self._hash_code(code)),
                )

            conn.commit()
            logger.info("MFA set up for user_id=%d", user_id)
            return {
                "secret": secret,
                "provisioning_uri": provisioning_uri,
                "recovery_codes": codes,
            }
        except Exception as e:
            conn.rollback()
            logger.error("Failed to setup MFA for user_id=%d", user_id)
            raise MFAError("Failed to set up MFA. Please try again.") from e
        finally:
            conn.close()

    def verify_totp(self, user_id: int, code: str) -> bool:
        """Verify a TOTP code with 1-step window tolerance."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT totp_secret, is_enabled FROM mfa_secrets WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if not row:
                raise MFAError("MFA is not set up for this user.")
            if not row["is_enabled"]:
                raise MFAError("MFA is disabled for this user.")

            totp = pyotp.TOTP(row["totp_secret"])
            return totp.verify(code, valid_window=1)
        finally:
            conn.close()

    def is_mfa_enabled(self, user_id: int) -> bool:
        """Check if MFA is enabled for a user."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT is_enabled FROM mfa_secrets WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return bool(row and row["is_enabled"])
        finally:
            conn.close()

    def disable_mfa(self, user_id: int) -> bool:
        """Disable MFA for a user."""
        conn = self._conn()
        try:
            result = conn.execute(
                "DELETE FROM mfa_secrets WHERE user_id = ?", (user_id,)
            )
            conn.execute(
                "DELETE FROM mfa_recovery_codes WHERE user_id = ?", (user_id,)
            )
            conn.commit()
            logger.info("MFA disabled for user_id=%d", user_id)
            if result.rowcount == 0:
                raise MFAError("MFA is not set up for this user.")
            return True
        except MFAError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def verify_recovery_code(self, user_id: int, code: str) -> bool:
        """Verify and consume a recovery code.

        Rate limited: after 5 failed attempts, locks out for 15 minutes.
        """
        now = time.time()

        # Check rate limit
        if user_id in _recovery_attempts:
            # Prune attempts outside the lockout window
            _recovery_attempts[user_id] = [
                t for t in _recovery_attempts[user_id]
                if now - t < _RECOVERY_LOCKOUT_SECONDS
            ]
            if len(_recovery_attempts[user_id]) >= _RECOVERY_MAX_ATTEMPTS:
                logger.warning(
                    "Recovery code verification locked out for user_id=%d", user_id
                )
                raise MFAError(
                    "Too many failed recovery code attempts. "
                    "Please try again in 15 minutes."
                )

        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT id, code_hash FROM mfa_recovery_codes WHERE user_id = ? AND is_used = 0",
                (user_id,),
            ).fetchall()

            matched_id = None
            for row in rows:
                if self._verify_code_hash(code, row["code_hash"]):
                    matched_id = row["id"]
                    break

            if matched_id is None:
                # Record failed attempt
                _recovery_attempts.setdefault(user_id, []).append(now)
                return False

            conn.execute(
                "UPDATE mfa_recovery_codes SET is_used = 1 WHERE id = ?",
                (matched_id,),
            )
            conn.commit()
            # Clear failed attempts on success
            _recovery_attempts.pop(user_id, None)
            logger.info("Recovery code used for user_id=%d", user_id)
            return True
        finally:
            conn.close()

    def get_remaining_recovery_codes(self, user_id: int) -> int:
        """Get the number of unused recovery codes."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM mfa_recovery_codes WHERE user_id = ? AND is_used = 0",
                (user_id,),
            ).fetchone()
            return row["cnt"]
        finally:
            conn.close()
