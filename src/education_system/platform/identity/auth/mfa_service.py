"""Multi-Factor Authentication service using TOTP."""

import hashlib
import hmac
import secrets
import string
import logging

import bcrypt as _bcrypt
import pyotp

from education_system.platform.identity.auth.exceptions import MFAError
from education_system.platform.identity.auth.db import connect

logger = logging.getLogger(__name__)

# Rate limiting for recovery code verification — persisted to the auth DB
# so the counter survives across processes / restarts. Falls back to a
# safe no-op when the DB is unavailable.
_RECOVERY_MAX_ATTEMPTS = 5
_RECOVERY_LOCKOUT_SECONDS = 15 * 60  # 15 minutes


def _recovery_rate_key(user_id: int) -> str:
    return f"mfa_recovery:{user_id}"


class MFAService:
    """Service for TOTP-based multi-factor authentication."""

    RECOVERY_CODE_COUNT = 10

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        from education_system.platform.identity.auth.rate_limit_store import PersistentRateLimiter
        self._rate_limiter = PersistentRateLimiter(db_path)

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
            return hmac.compare_digest(
                hashlib.sha256(normalised.encode()).hexdigest(), code_hash
            )
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

    @staticmethod
    def _table_exists(conn, name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    def is_mfa_enabled(self, user_id: int) -> bool:
        """Is a second factor actually required for this user at login?

        This is the gate ``UserAuth.login`` consults, so it has to agree
        with what the MFA settings screen reports. It used to check
        ``mfa_secrets`` alone — the TOTP secret — while enrolment through
        the email/SMS flows writes ``mfa_methods`` and ``mfa_user_settings``
        and never touches ``mfa_secrets``. An email-only enrolment therefore
        showed "ENABLED" everywhere and was silently never challenged.

        True when the user has *any* enabled factor — a TOTP secret or an
        enabled row in ``mfa_methods`` — and verification has not been
        deliberately switched off for them.
        """
        conn = self._conn()
        try:
            # An explicit "don't challenge this account" wins over
            # everything else; that is how MFA is intentionally suspended.
            if self._table_exists(conn, "mfa_user_settings"):
                settings = conn.execute(
                    "SELECT COALESCE(verification_disabled, 0) AS off "
                    "FROM mfa_user_settings WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                if settings and settings["off"]:
                    return False

            row = conn.execute(
                "SELECT is_enabled FROM mfa_secrets WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row and row["is_enabled"]:
                return True

            if self._table_exists(conn, "mfa_methods"):
                method = conn.execute(
                    "SELECT 1 FROM mfa_methods "
                    "WHERE user_id = ? AND COALESCE(is_enabled, 0) = 1 LIMIT 1",
                    (user_id,),
                ).fetchone()
                if method:
                    return True

            return False
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
        rl_key = _recovery_rate_key(user_id)

        # Check persistent rate limit (survives across workers/restarts)
        prior_failures = self._rate_limiter.count(rl_key, _RECOVERY_LOCKOUT_SECONDS)
        if prior_failures >= _RECOVERY_MAX_ATTEMPTS:
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
                self._rate_limiter.record(rl_key)
                return False

            conn.execute(
                "UPDATE mfa_recovery_codes SET is_used = 1 WHERE id = ?",
                (matched_id,),
            )
            conn.commit()
            # Clear failed attempts on success
            self._rate_limiter.clear(rl_key)
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
