"""Core authentication class for the unified Education System auth."""

from datetime import datetime, timedelta
import logging
import os

from education_system.shared.auth.exceptions import AuthError
from education_system.shared.auth.defaults import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES
from education_system.shared.auth.db import connect
from education_system.shared.auth.password_manager import (
    hash_password,
    verify_password,
    validate_password_strength,
    constant_time_dummy_verify,
)
from education_system.shared.auth.session_manager import SessionManager
from education_system.shared.auth.role_manager import RoleManager

logger = logging.getLogger(__name__)


def _recovery_code_login_enabled() -> bool:
    """Whether an MFA recovery code may be entered *in the password field* as a
    single-use break-glass login (for a user who has lost both their password
    and their authenticator).

    This is enabled by default and is guarded by: a length pre-check, an
    MFA-enabled-only gate, the recovery-code rate limiter, single-use
    consumption, and a forced password change on success. Deployments that
    prefer strict separation — requiring the explicit ``/mfa/verify`` recovery
    flow instead of overloading the password field — can set
    ``EDU_DISABLE_RECOVERY_CODE_LOGIN=1``.
    """
    return os.environ.get("EDU_DISABLE_RECOVERY_CODE_LOGIN", "").strip().lower() not in (
        "1", "true", "yes", "on",
    )


def _must_change_password(user_row) -> bool:
    """Safely read the ``must_change_password`` flag from a users row.

    Guards against older DB rows / connections that predate the column so a
    missing column reads as False rather than raising.
    """
    try:
        return bool(user_row["must_change_password"])
    except (IndexError, KeyError, TypeError):
        return False


class UserAuth:
    """Unified authentication facade for all Education System subsystems."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path
        self.session_manager = SessionManager(db_path)
        self.role_manager = RoleManager(db_path)
        self._current_user: dict | None = None
        self._current_token: str | None = None

    def _conn(self):
        return connect(self._db_path)

    @property
    def current_user(self) -> dict | None:
        return self._current_user

    @property
    def is_logged_in(self) -> bool:
        return self._current_user is not None

    def _record_login_attempt(self, username: str, success: bool) -> None:
        """Mirror every login attempt into the university DB's
        ``login_attempts`` table so the login-analytics dashboard can
        count it.

        Best-effort: any failure (table missing, DB locked, university
        package unavailable) is logged at debug-level and swallowed —
        the auth flow itself must never break because of analytics.
        """
        try:
            from education_system.post_18.university_system.infrastructure.database.db import (
                get_connection as get_uni_connection,
            )
        except ImportError:
            return
        try:
            with get_uni_connection() as conn:
                if hasattr(conn, "row_factory"):
                    pass  # context manager already gives us a connection
                cur = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='login_attempts'"
                )
                if not cur.fetchone():
                    return
                conn.execute(
                    "INSERT INTO login_attempts "
                    "(username, attempt_time, ip_address, success) "
                    "VALUES (?, datetime('now'), ?, ?)",
                    (username, "unknown", 1 if success else 0),
                )
                conn.commit()
        except Exception as exc:
            logger.debug("login_attempts insert failed: %s", exc)

    def login(self, username: str, password: str) -> dict:
        """Authenticate a user against the shared auth database.

        Returns a user info dict on success. Raises AuthError on failure.
        The returned dict includes the list of systems the user can access.
        """
        try:
            result = self._login_impl(username, password)
        except AuthError:
            self._record_login_attempt(username, success=False)
            raise
        # Only record success when auth has actually completed. A
        # password match that still requires MFA is *not* a successful
        # login — recording it as success=1 would mask password brute-
        # forcing in dashboards/alerts that watch success ratios. The
        # final success entry is written by ``verify_mfa`` once MFA
        # passes.
        if not (isinstance(result, dict) and result.get("mfa_required")):
            self._record_login_attempt(username, success=True)
        else:
            logger.info(
                "Login for '%s' awaiting MFA verification (not counted as success)",
                username,
            )
        return result

    def _login_impl(self, username: str, password: str) -> dict:
        """Original login body — see ``login`` for the public wrapper."""
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

            if not user:
                # Run a dummy bcrypt check so unknown-user response time
                # matches a real failed login (~400ms).  Without this an
                # attacker can enumerate valid usernames by timing.
                constant_time_dummy_verify(password)
                logger.warning("Login failed: unknown user '%s'", username)
                raise AuthError("Invalid username or password.")

            if not user["is_active"]:
                # Same reasoning — don't leak account existence via timing.
                constant_time_dummy_verify(password)
                logger.warning("Login attempt on deactivated account: '%s'", username)
                raise AuthError("Invalid username or password.")

            # Check lockout
            if user["locked_until"]:
                locked_until = datetime.fromisoformat(user["locked_until"])
                if locked_until > datetime.utcnow():
                    logger.warning("Login attempt on locked account: '%s'", username)
                    raise AuthError("Account locked due to too many failed attempts.")
                else:
                    conn.execute(
                        "UPDATE users SET locked_until = NULL, failed_login_attempts = 0 WHERE id = ?",
                        (user["id"],),
                    )
                    conn.commit()

            legacy_salt = user["legacy_salt"] if "legacy_salt" in user.keys() else None
            password_ok = verify_password(password, user["password_hash"], legacy_salt=legacy_salt)

            # Recovery-code login: if the password didn't match, accept an
            # unused MFA recovery code as a single-use bypass. The code is
            # consumed and the account is flagged for forced password reset
            # so the user must set a new password on first login.
            recovery_used = False
            if not password_ok and _recovery_code_login_enabled():
                if self._try_recovery_code_login(conn, user["id"], password):
                    recovery_used = True
                    password_ok = True
                    # Flag for forced password change
                    conn.execute(
                        "UPDATE users SET password_changed_at = NULL WHERE id = ?",
                        (user["id"],),
                    )
                    conn.commit()
                    logger.info(
                        "User '%s' logged in via MFA recovery code", username,
                    )

            if not password_ok:
                attempts = user["failed_login_attempts"] + 1
                updates = {"failed_login_attempts": attempts}
                if attempts >= MAX_LOGIN_ATTEMPTS:
                    lockout = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
                    updates["locked_until"] = lockout.isoformat()
                    logger.critical(
                        "SECURITY ALERT: Account '%s' locked after %d failed login attempts. "
                        "Lockout expires at %s.",
                        username, attempts, updates["locked_until"],
                    )
                    self._notify_lockout(username, attempts)

                # Keys are from a fixed whitelist (failed_login_attempts, locked_until)
                _valid_keys = {"failed_login_attempts", "locked_until"}
                for k in updates:
                    if k not in _valid_keys:
                        raise ValueError(f"Unexpected update key: {k!r}")
                set_parts = ", ".join(f"{k} = ?" for k in updates)
                conn.execute(
                    f"UPDATE users SET {set_parts} WHERE id = ?",  # nosec B608  # keys validated against allowlist
                    (*updates.values(), user["id"]),
                )
                conn.commit()
                logger.warning("Login failed: bad auth for '%s' (attempt %d)", username, attempts)  # nosemgrep: python-logger-credential-disclosure
                raise AuthError("Invalid username or password.")

            # If verified via legacy PBKDF2, re-hash with bcrypt transparently
            if legacy_salt:
                new_hash = hash_password(password)
                conn.execute(
                    "UPDATE users SET password_hash = ?, legacy_salt = NULL WHERE id = ?",
                    (new_hash, user["id"]),
                )
                logger.info("Re-hashed legacy PBKDF2 to bcrypt for user '%s'", username)  # nosemgrep: python-logger-credential-disclosure

            # Reset failed attempts and update last_login
            conn.execute(
                "UPDATE users SET failed_login_attempts = 0, locked_until = NULL, "
                "last_login = datetime('now') WHERE id = ?",
                (user["id"],),
            )
            conn.commit()

            # Check password expiry. Recovery-code logins always force a
            # password change because the user no longer knows the real
            # password — without this flag they'd be locked out on the
            # next login.
            password_expired = recovery_used or self.check_password_expiry(user["id"])

            # Fetch systems the user has access to
            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user["id"],),
            ).fetchall()

        finally:
            conn.close()

        # Check MFA — but skip the MFA challenge when the user logged in
        # with a recovery code, since the code is itself a one-time second
        # factor and they no longer have access to the authenticator.
        if not recovery_used:
            mfa_required = False
            try:
                from education_system.shared.auth.mfa_service import MFAService
                mfa_svc = MFAService(self._db_path)
                if mfa_svc.is_mfa_enabled(user["id"]):
                    mfa_required = True
            except ImportError:
                pass

            # Also honour MFA enabled via the university subsystem
            # (mfa_user_settings / mfa_methods in student_records.db).
            # The university setup wizard writes there but not into the
            # shared mfa_secrets table, so without this fall-through the
            # login screen would silently bypass MFA.
            if not mfa_required:
                try:
                    from education_system.post_18.university_system.infrastructure.database.db import (
                        get_connection,
                    )
                    uconn = get_connection()
                    try:
                        # The MFA wizard saves mfa_methods / mfa_user_settings
                        # keyed by the SHARED users.id (passed through as
                        # `current_user["id"]`). The previous code re-mapped
                        # to ``user_accounts.id`` — an unrelated PK — so
                        # admin/staff who had MFA enabled were silently
                        # bypassed at login because the IDs didn't match.
                        # Also accept the legacy mapping (via
                        # ``user_accounts.user_id`` FK) so older setups
                        # written under that scheme still challenge.
                        candidate_ids = {user["id"]}
                        try:
                            urow = uconn.execute(
                                "SELECT id, user_id FROM user_accounts WHERE username = ?",
                                (user["username"],),
                            ).fetchone()
                            if urow:
                                # Some schemas key MFA tables off user_accounts.user_id (FK),
                                # others off user_accounts.id (PK) — try both as a fallback
                                # before declaring "no MFA configured".
                                try:
                                    candidate_ids.add(urow["user_id"])
                                except (IndexError, KeyError, TypeError):
                                    pass
                                try:
                                    candidate_ids.add(urow["id"])
                                except (IndexError, KeyError, TypeError):
                                    pass
                        except Exception as exc:
                            logger.debug(
                                "MFA candidate lookup for '%s' failed: %s",
                                user["username"], exc,
                            )

                        candidate_ids = {cid for cid in candidate_ids if cid is not None}
                        for cid in candidate_ids:
                            srow = uconn.execute(
                                "SELECT mfa_enabled, COALESCE(verification_disabled, 0) AS off "
                                "FROM mfa_user_settings WHERE user_id = ?",
                                (cid,),
                            ).fetchone()
                            if srow and srow["mfa_enabled"] and not srow["off"]:
                                mrow = uconn.execute(
                                    "SELECT 1 FROM mfa_methods "
                                    "WHERE user_id = ? AND is_enabled = 1 LIMIT 1",
                                    (cid,),
                                ).fetchone()
                                if mrow:
                                    mfa_required = True
                                    break
                    finally:
                        uconn.close()
                except ImportError:
                    pass
                except Exception as exc:
                    logger.warning(
                        "University MFA lookup failed for %s: %s",
                        user["username"], exc, exc_info=True,
                    )

            if mfa_required:
                return {
                    "mfa_required": True,
                    "user_id": user["id"],
                    "username": user["username"],
                    "password_expired": password_expired,
                    "must_change_password": _must_change_password(user),
                }

        # Enforce MFA for privileged roles
        user_roles = {s["role"] for s in systems}
        mfa_setup_required = self._check_mfa_required(user["id"], user_roles)

        # Create session
        token = self.session_manager.create_session(user["id"])

        self._current_user = {
            "id": user["id"],
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"] or user["username"],
            "email": user["email"],
            "systems": [
                {"system_key": s["system_key"], "role": s["role"]}
                for s in systems
            ],
            "password_expired": password_expired,
            "must_change_password": _must_change_password(user),
            "mfa_setup_required": mfa_setup_required,
        }
        self._current_token = token
        logger.info("User '%s' logged in", user["username"])

        return self._current_user

    def verify_mfa(self, user_id: int, code: str) -> dict:
        """Complete login after MFA verification."""
        from education_system.shared.auth.mfa_service import MFAService
        from education_system.shared.auth.exceptions import MFAError
        mfa_svc = MFAService(self._db_path)

        # ``verify_totp`` / ``verify_recovery_code`` raise MFAError when
        # no TOTP secret / no recovery codes are configured for the user
        # (common when the only enrolled second factor is email OTP,
        # which is verified out-of-band by the GUI before this method
        # is reached). Treat "not set up" the same as "code didn't
        # match" — a missing factor isn't a verification, but it's also
        # not a crash. Surface every failure to callers as the same
        # friendly AuthError they already know how to render.
        def _try_totp() -> bool:
            try:
                return bool(mfa_svc.verify_totp(user_id, code))
            except MFAError:
                return False

        def _try_recovery() -> bool:
            try:
                return bool(mfa_svc.verify_recovery_code(user_id, code))
            except MFAError:
                return False

        if not _try_totp() and not _try_recovery():
            logger.warning("MFA verification failed for user_id=%d", user_id)  # lgtm[py/clear-text-logging-sensitive-data]
            raise AuthError("Invalid MFA code.")

        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not user:
                raise AuthError("User not found.")

            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

        password_expired = self.check_password_expiry(user["id"])
        user_roles = {s["role"] for s in systems}
        mfa_setup_required = self._check_mfa_required(user["id"], user_roles)
        token = self.session_manager.create_session(user["id"])

        self._current_user = {
            "id": user["id"],
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"] or user["username"],
            "email": user["email"],
            "systems": [
                {"system_key": s["system_key"], "role": s["role"]}
                for s in systems
            ],
            "password_expired": password_expired,
            "must_change_password": _must_change_password(user),
            "mfa_setup_required": mfa_setup_required,
        }
        self._current_token = token
        logger.info("MFA verified for user '%s'", user["username"])
        # MFA passed → full auth complete. Record the success now so
        # brute-force watchers see one success per fully-authenticated
        # login (and only one).
        self._record_login_attempt(user["username"], success=True)

        return self._current_user

    def complete_mfa_login(self, user_id: int) -> dict:
        """Complete login after MFA was already verified externally (e.g. email OTP).

        Same as verify_mfa but without re-checking the code.
        """
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not user:
                raise AuthError("User not found.")

            systems = conn.execute(
                "SELECT system_key, role FROM user_systems WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()

        password_expired = self.check_password_expiry(user["id"])
        user_roles = {s["role"] for s in systems}
        mfa_setup_required = self._check_mfa_required(user["id"], user_roles)
        token = self.session_manager.create_session(user["id"])

        self._current_user = {
            "id": user["id"],
            "user_id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"] or user["username"],
            "email": user["email"],
            "systems": [
                {"system_key": s["system_key"], "role": s["role"]}
                for s in systems
            ],
            "password_expired": password_expired,
            "must_change_password": _must_change_password(user),
            "mfa_setup_required": mfa_setup_required,
        }
        self._current_token = token
        logger.info("MFA login completed for user '%s' (external verification)", user["username"])
        # External MFA verified → record the final success entry. Mirrors
        # ``verify_mfa`` so brute-force analytics see one success per
        # completed login regardless of which MFA flow was used.
        self._record_login_attempt(user["username"], success=True)

        return self._current_user

    def _try_recovery_code_login(self, conn, user_id: int, candidate: str) -> bool:
        """If *candidate* matches an unused MFA recovery code for the user,
        consume it and return True. Returns False if MFA isn't set up for
        the user, the rate-limit is exceeded, or the code doesn't match.

        The provided *conn* is intentionally not used for the recovery-code
        verification itself — MFAService opens its own connection so the
        consume-on-match write commits independently.
        """
        # Cheap rejection for inputs that can't possibly be a recovery code
        # (codes are short alphanumerics like "ABCD-1234"). This avoids
        # paying bcrypt cost for every wrong-password attempt.
        cleaned = candidate.strip().upper()
        if not (4 <= len(cleaned) <= 20):
            return False

        try:
            from education_system.shared.auth.mfa_service import MFAService, MFAError
        except ImportError:
            return False

        mfa_svc = MFAService(self._db_path)
        if not mfa_svc.is_mfa_enabled(user_id):
            return False

        try:
            return mfa_svc.verify_recovery_code(user_id, candidate)
        except MFAError as exc:
            # Rate-limit lockout — surface as a normal AuthError so the user
            # gets feedback instead of a silent fall-through to "invalid".
            raise AuthError(str(exc)) from exc
        except Exception as exc:
            logger.debug("Recovery code login check failed: %s", exc)
            return False

    def _check_mfa_required(self, user_id: int, roles: set[str]) -> bool:
        """Check if MFA is required but not set up for privileged roles."""
        _MFA_REQUIRED_ROLES = {"admin", "staff"}
        if not roles & _MFA_REQUIRED_ROLES:
            return False
        try:
            from education_system.shared.auth.mfa_service import MFAService
            mfa_svc = MFAService(self._db_path)
            return not mfa_svc.is_mfa_enabled(user_id)
        except ImportError:
            return False

    def get_role_for_system(self, system_key: str) -> str | None:
        """Get the current user's role for a specific system."""
        if not self._current_user:
            return None
        for s in self._current_user.get("systems", []):
            if s["system_key"] == system_key:
                return s["role"]
        return None

    def logout(self):
        """Logout the current user."""
        logger.info(  # lgtm[py/clear-text-logging-sensitive-data]
            "User logged out: %s",
            self._current_user.get("username", "?") if self._current_user else "unknown",
        )
        if self._current_token:
            self.session_manager.invalidate_session(self._current_token)
        self._current_user = None
        self._current_token = None

    def create_user(
        self, username: str, password: str, display_name: str | None = None,
        email: str | None = None, systems: list[tuple[str, str]] | None = None,
    ) -> int:
        """Create a new user account. Returns the user ID.

        *systems* is a list of (system_key, role) tuples.
        """
        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            raise AuthError(msg)

        pw_hash = hash_password(password)
        conn = self._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, display_name, email) VALUES (?, ?, ?, ?)",
                (username, pw_hash, display_name, email),
            )
            user_id = cursor.lastrowid
            if systems:
                for system_key, role in systems:
                    conn.execute(
                        "INSERT INTO user_systems (user_id, system_key, role) VALUES (?, ?, ?)",
                        (user_id, system_key, role),
                    )
            conn.commit()
            logger.info("User created: '%s' (id=%d)", username, user_id)
            return user_id
        except Exception as e:
            conn.rollback()
            if "UNIQUE" in str(e):
                raise AuthError(f"Username '{username}' already exists.") from e
            logger.error("Failed to create user '%s'", username)
            raise AuthError("Failed to create user.") from e
        finally:
            conn.close()

    def provision_user(
        self, username: str, plaintext_password: str, *,
        display_name: str | None = None, email: str | None = None,
        systems: list[tuple[str, str]] | None = None,
    ) -> int:
        """Idempotently upsert a shared-auth account from a known-good plaintext
        password and return the shared ``users.id``.

        Unlike :meth:`create_user`, this is meant for *migrating* an account that
        has already authenticated against a legacy auth backend, so it:

        - stores a bcrypt hash (``legacy_salt`` cleared, ``password_changed_at``
          set so the next shared login isn't immediately forced to reset), and
        - does **not** run :func:`validate_password_strength` — legacy passwords
          (e.g. ``student123``) would fail the current policy and bricking the
          migration would lock the user out of the fast path forever.

        *systems* is a list of ``(system_key, role)`` tuples; roles are kept
        current on repeat calls.
        """
        pw_hash = hash_password(plaintext_password)
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, legacy_salt FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                cursor = conn.execute(
                    "INSERT INTO users "
                    "(username, password_hash, display_name, email, "
                    " legacy_salt, password_changed_at) "
                    "VALUES (?, ?, ?, ?, NULL, datetime('now'))",
                    (username, pw_hash, display_name, email),
                )
                user_id = cursor.lastrowid
            else:
                user_id = row["id"]
                # Only rewrite the hash on the first real migration (legacy_salt
                # still set). Once on bcrypt, leave repeat calls as cheap no-ops.
                if row["legacy_salt"] is not None:
                    conn.execute(
                        "UPDATE users SET password_hash = ?, legacy_salt = NULL, "
                        "updated_at = datetime('now') WHERE id = ?",
                        (pw_hash, user_id),
                    )

            for system_key, role in (systems or []):
                conn.execute(
                    "INSERT OR IGNORE INTO user_systems (user_id, system_key, role) "
                    "VALUES (?, ?, ?)",
                    (user_id, system_key, role),
                )
                conn.execute(
                    "UPDATE user_systems SET role = ? "
                    "WHERE user_id = ? AND system_key = ?",
                    (role, user_id, system_key),
                )

            conn.commit()
            logger.info("Provisioned shared-auth account for '%s' (id=%d)", username, user_id)
            return user_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def change_password(self, user_id: int, old_password: str, new_password: str):
        """Change a user's password."""
        conn = self._conn()
        try:
            user = conn.execute(
                "SELECT password_hash, legacy_salt FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if not user:
                raise AuthError("User not found.")

            legacy_salt = user["legacy_salt"] if "legacy_salt" in user.keys() else None
            if not verify_password(old_password, user["password_hash"], legacy_salt=legacy_salt):
                raise AuthError("Current password is incorrect.")

            is_valid, msg = validate_password_strength(new_password)
            if not is_valid:
                raise AuthError(msg)

            # Check password history (last 5)
            history = conn.execute(
                "SELECT password_hash FROM password_history WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
                (user_id,),
            ).fetchall()
            for h in history:
                if verify_password(new_password, h["password_hash"]):
                    raise AuthError("Cannot reuse any of your last 5 passwords.")

            # Also check the current password hash against reuse
            if verify_password(new_password, user["password_hash"]):
                raise AuthError("Cannot reuse any of your last 5 passwords.")

            # Save old hash to password history
            conn.execute(
                "INSERT INTO password_history (user_id, password_hash) VALUES (?, ?)",
                (user_id, user["password_hash"]),
            )

            new_hash = hash_password(new_password)
            conn.execute(
                "UPDATE users SET password_hash = ?, password_changed_at = datetime('now'), "
                "must_change_password = 0, updated_at = datetime('now') WHERE id = ?",
                (new_hash, user_id),
            )
            conn.commit()
            logger.info("Password changed for user_id=%d", user_id)

            self.session_manager.invalidate_user_sessions(user_id)
        finally:
            conn.close()

    def check_password_expiry(self, user_id: int, max_age_days: int = 90) -> bool:
        """Check if a user's password must be reset. Returns True if it must.

        The policy is evaluated **per system**: each education system
        (university, college, …) has its own ``force_password_reset:<system>``
        toggle (falling back to the global ``force_password_reset`` default) and
        its own admin-triggered ``force_password_reset_pending:<system>`` epoch.
        Because a user shares one password across every system they belong to,
        the reset is forced if *any* of their systems mandates it.
        """
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT password_changed_at FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            system_keys = [
                r["system_key"] for r in conn.execute(
                    "SELECT system_key FROM user_systems WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            ]
        except Exception as exc:
            # Fail closed: if the check can't be evaluated (DB error) treat
            # the password as expired rather than silently letting the user
            # skip the forced reset. A DB outage must not disable forced
            # password rotation cluster-wide.
            logger.warning(
                "check_password_expiry failed for user_id=%d: %s — treating as expired",
                user_id, exc,
            )
            return True
        finally:
            conn.close()

        changed_raw = row["password_changed_at"] if row else None
        changed = None
        if changed_raw:
            try:
                changed = datetime.fromisoformat(changed_raw)
            except Exception as exc:
                logger.warning(
                    "check_password_expiry: bad password_changed_at for user_id=%d: %s"
                    " — treating as expired", user_id, exc,
                )
                return True  # malformed timestamp → fail closed

        # Users with no system rows fall back to the plain global policy.
        scope = system_keys or [None]
        for system_key in scope:
            if system_key is None:
                policy_on = self.get_setting("force_password_reset", True)
                pending = None
            else:
                policy_on = self.get_system_password_policy(system_key)
                pending = self.get_setting(
                    f"force_password_reset_pending:{system_key}", None
                )

            # Admin-triggered force reset: anyone whose password predates the
            # epoch (or who never set one) must reset. Users who have already
            # changed their password since then clear themselves automatically.
            if pending:
                try:
                    epoch = datetime.fromisoformat(pending)
                    if changed is None or changed < epoch:
                        return True
                except Exception:
                    pass  # ignore an unparseable epoch rather than lock everyone out

            # Age-based expiry, honouring the per-system policy toggle.
            if policy_on:
                if changed is None:
                    return True  # never set = expired
                if (datetime.now() - changed).days > max_age_days:
                    return True

        return False

    # ── Per-system password reset policy ────────────────────────────────

    @staticmethod
    def _known_systems() -> dict:
        """Return the canonical {system_key: label} map (lazy import)."""
        from education_system.shared.auth.defaults import SYSTEMS
        return SYSTEMS

    def get_system_password_policy(self, system_key: str) -> bool:
        """Effective age-expiry policy for *system_key*.

        Uses the per-system ``force_password_reset:<system>`` override when set,
        otherwise the global ``force_password_reset`` default (True).
        """
        override = self.get_setting(f"force_password_reset:{system_key}", None)
        if override is None:
            return bool(self.get_setting("force_password_reset", True))
        return bool(override)

    def set_system_password_policy(self, system_key: str, enabled: bool) -> None:
        """Enable/disable the age-based forced-reset policy for one system."""
        self.set_setting(f"force_password_reset:{system_key}", bool(enabled))

    def force_system_password_reset(self, system_key=None) -> tuple:
        """Force every user in *system_key* to reset on next login.

        Pass ``None`` (or ``"all"``) to apply to every known system. Records a
        reset epoch; any user in the system whose password is older than it must
        change it at next login. Returns ``(epoch_iso, [system_keys])``.
        """
        epoch = datetime.now().isoformat()
        targets = (
            list(self._known_systems())
            if system_key in (None, "all")
            else [system_key]
        )
        for sk in targets:
            self.set_setting(f"force_password_reset_pending:{sk}", epoch)
        logger.info("Forced password reset for systems: %s", ", ".join(targets))
        return epoch, targets

    def clear_system_password_reset(self, system_key=None) -> list:
        """Cancel a pending forced reset for *system_key* (or all systems)."""
        targets = (
            list(self._known_systems())
            if system_key in (None, "all")
            else [system_key]
        )
        for sk in targets:
            self.delete_setting(f"force_password_reset_pending:{sk}")
        return targets

    def get_password_policy_overview(self) -> list:
        """Per-system snapshot for the superadmin UI.

        Returns a list of dicts: ``system``, ``label``, ``policy_enabled``,
        ``pending_since`` (ISO string or None).
        """
        overview = []
        for sk, label in self._known_systems().items():
            overview.append({
                "system": sk,
                "label": label,
                "policy_enabled": self.get_system_password_policy(sk),
                "pending_since": self.get_setting(
                    f"force_password_reset_pending:{sk}", None
                ),
            })
        return overview

    # ── Admin settings helpers ──────────────────────────────────────────

    def _ensure_settings_table(self, conn):
        """Create the auth_settings table if it doesn't exist."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

    def get_setting(self, key: str, default=None):
        """Read an admin setting from auth_settings. Returns *default* if unset."""
        conn = self._conn()
        try:
            self._ensure_settings_table(conn)
            row = conn.execute(
                "SELECT value FROM auth_settings WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return default
            raw = row["value"]
            # Coerce booleans stored as "true"/"false"
            if raw.lower() in ("true", "1"):
                return True
            if raw.lower() in ("false", "0"):
                return False
            return raw
        except Exception:
            return default
        finally:
            conn.close()

    def set_setting(self, key: str, value) -> None:
        """Write an admin setting to auth_settings."""
        conn = self._conn()
        try:
            self._ensure_settings_table(conn)
            str_val = str(value).lower() if isinstance(value, bool) else str(value)
            conn.execute(
                "INSERT OR REPLACE INTO auth_settings (key, value) VALUES (?, ?)",
                (key, str_val),
            )
            conn.commit()
        finally:
            conn.close()

    def delete_setting(self, key: str) -> None:
        """Remove an admin setting, reverting it to its coded default."""
        conn = self._conn()
        try:
            self._ensure_settings_table(conn)
            conn.execute("DELETE FROM auth_settings WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()

    def _notify_lockout(self, username: str, attempts: int):
        """Send an alert when an account is locked out."""
        try:
            from education_system.shared.email.otp_sender import send_otp
            from education_system.shared.email.config import load_email_config

            cfg = load_email_config()
            admin_email = cfg.get("sender_email", "")
            if admin_email:
                from email.mime.text import MIMEText
                import smtplib

                smtp_server = cfg.get("smtp_server", "")
                smtp_port = cfg.get("smtp_port", 587)
                smtp_user = cfg.get("smtp_username", "")
                smtp_pass = cfg.get("smtp_password", "")
                use_tls = cfg.get("use_tls", True)

                if all([smtp_server, smtp_user, smtp_pass]):
                    msg = MIMEText(
                        f"Account '{username}' has been locked after {attempts} "
                        f"failed login attempts at {datetime.utcnow().isoformat()}.\n\n"
                        f"The account will be unlocked automatically after "
                        f"{LOCKOUT_DURATION_MINUTES} minutes.",
                    )
                    msg["Subject"] = f"Security Alert: Account '{username}' locked"
                    msg["From"] = smtp_user
                    msg["To"] = admin_email

                    server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                    if use_tls:
                        server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(smtp_user, [admin_email], msg.as_string())
                    server.quit()
                    logger.info("Lockout alert email sent for '%s'", username)
        except Exception as exc:
            logger.debug("Could not send lockout alert email: %s", exc)

    # Confirmation phrase callers must supply to actually run the
    # legacy-reset bulk-deactivation. Prevents accidental invocation
    # (and forces any attacker with an admin token to type a specific
    # string rather than just hit the endpoint).
    LEGACY_RESET_CONFIRMATION = "I_UNDERSTAND_DEACTIVATE_LEGACY_ACCOUNTS"

    def force_legacy_password_reset(
        self,
        confirmation: str,
        actor_user_id: int | None = None,
        actor_username: str | None = None,
    ) -> int:
        """Deactivate all accounts still using legacy PBKDF2 hashes.

        Requires an explicit *confirmation* phrase matching
        ``LEGACY_RESET_CONFIRMATION`` — otherwise raises ``AuthError``.
        Every successful run is audited (logger + best-effort
        ``audit_log`` table row) so the operation is traceable.

        These accounts have a non-NULL ``legacy_salt``, meaning they have
        never logged in since the bcrypt migration.  Returns the number
        of accounts affected.
        """
        if confirmation != self.LEGACY_RESET_CONFIRMATION:
            raise AuthError(
                "force_legacy_password_reset requires the confirmation "
                "phrase to proceed (this is a destructive bulk operation)."
            )

        conn = self._conn()
        try:
            # Capture the user IDs being deactivated so we can audit each
            # one rather than only logging a row-count summary.
            affected_rows = conn.execute(
                "SELECT id, username FROM users "
                "WHERE legacy_salt IS NOT NULL AND is_active = 1",
            ).fetchall()
            affected_ids = [r["id"] for r in affected_rows]

            cursor = conn.execute(
                "UPDATE users SET is_active = 0 WHERE legacy_salt IS NOT NULL AND is_active = 1",
            )
            affected = cursor.rowcount

            # Write audit rows (best effort — audit_log may not exist on
            # older deployments).
            try:
                for row in affected_rows:
                    conn.execute(
                        "INSERT INTO audit_log "
                        "(user_id, action, target, actor_user_id, created_at) "
                        "VALUES (?, ?, ?, ?, datetime('now'))",
                        (
                            row["id"],
                            "force_legacy_password_reset",
                            row["username"],
                            actor_user_id,
                        ),
                    )
            except Exception as exc:
                logger.debug("audit_log insert skipped (table missing?): %s", exc)

            conn.commit()
            if affected:
                logger.warning(
                    "force_legacy_password_reset: deactivated %d accounts "
                    "(actor_user_id=%s actor_username=%s ids=%s)",
                    affected, actor_user_id, actor_username, affected_ids,
                )
            return affected
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> dict | None:
        """Get user info by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT id, username, display_name, email, is_active, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
