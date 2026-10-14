"""Mirror parent-portal accounts into the shared auth database.

The portal keeps its own ``parent_accounts`` table (PBKDF2, in
``sixthform.db``) because it predates the shared auth DB and the REST API
authenticates against it directly. That left portal accounts invisible to
the universal login screen: an account created in the Parent Portal could
not be used to sign in to the Sixth Form System at all.

This module keeps a shadow copy of each portal account in the shared auth
DB (``users`` + ``user_systems`` with role ``parent`` on ``sixth_form``),
so the same username/password works at the universal login.

Direction of travel
-------------------
The portal is the *writer*: create / reset / activate / delete in the
portal push through to shared auth. The reverse direction is handled by
:func:`verify_shared_password`, which lets
:func:`~...parent_portal.authenticate` accept a password that was changed
on the shared side (via the login screen's change-password flow) and
re-sync the portal hash — otherwise the two stores would drift apart the
first time a parent changed their own password.

Every mirror write is best-effort *except* at account creation, where the
username is reserved up front so the portal never hands out an account
that cannot log in.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SYSTEM_KEY = "sixth_form"
PARENT_ROLE = "parent"

#: Shared auth database to mirror into. ``None`` means the platform
#: default. Tests monkeypatch this at a temp file so a portal test never
#: writes to the real auth.db.
AUTH_DB_PATH: str | None = None


class MirrorError(RuntimeError):
    """Raised when a portal account cannot be mirrored into shared auth."""


def _auth_db(*, commit: bool = False):
    from education_system.platform.identity.auth.db import get_connection
    return get_connection(AUTH_DB_PATH, commit=commit)


def _hash(password: str) -> str:
    from education_system.platform.identity.auth.password_manager import hash_password
    return hash_password(password)


# ── Lookups ──────────────────────────────────────────────────────────

def _find_user(conn, username: str):
    return conn.execute(
        "SELECT id, is_active FROM users WHERE username = ?", (username,)
    ).fetchone()


def _is_mirrored_parent(conn, user_id: int) -> bool:
    """True when this shared-auth user is a sixth-form parent.

    Used to tell "our own shadow row" apart from an unrelated staff or
    student account that happens to share the username.
    """
    row = conn.execute(
        "SELECT 1 FROM user_systems WHERE user_id = ? AND system_key = ? AND role = ?",
        (user_id, SYSTEM_KEY, PARENT_ROLE),
    ).fetchone()
    return row is not None


def has_mirror(username: str) -> bool:
    """True when this portal account can sign in at the universal login."""
    try:
        with _auth_db() as conn:
            row = _find_user(conn, username)
            if row is None or not row["is_active"]:
                return False
            return _is_mirrored_parent(conn, row["id"])
    except Exception as exc:
        logger.debug("Could not read shared-auth mirror for '%s': %s", username, exc)
        return False


def username_available(username: str) -> tuple[bool, str]:
    """Check a portal username can be claimed in shared auth.

    Returns ``(ok, reason)``. A username already held by a non-parent
    account is refused rather than co-opted — mirroring must never
    overwrite somebody else's credentials.
    """
    try:
        with _auth_db() as conn:
            row = _find_user(conn, username)
            if row is None:
                return True, ""
            if _is_mirrored_parent(conn, row["id"]):
                return False, (
                    f"Username '{username}' already exists as a sixth-form "
                    "parent login."
                )
            return False, (
                f"Username '{username}' is already taken by another system "
                "account. Choose a different username."
            )
    except Exception as exc:
        raise MirrorError(
            f"Could not reach the shared auth database: {exc}"
        ) from exc


# ── Writes ───────────────────────────────────────────────────────────

def upsert(username: str, password: str, full_name: str,
           email: str | None = None, *, is_active: bool = True) -> int | None:
    """Create or refresh the shared-auth shadow of a portal account.

    Returns the shared ``users.id``. The portal enforces a shorter
    password minimum (8) than the shared password policy, so the strength
    check is deliberately skipped here — the portal has already accepted
    this password and refusing it now would create an account nobody can
    use.
    """
    pw_hash = _hash(password)
    with _auth_db(commit=True) as conn:
        row = _find_user(conn, username)
        if row is None:
            cur = conn.execute(
                "INSERT INTO users "
                "(username, password_hash, display_name, email, is_active, "
                " legacy_salt, password_changed_at, must_change_password) "
                "VALUES (?, ?, ?, ?, ?, NULL, datetime('now'), 0)",
                (username, pw_hash, full_name, email, 1 if is_active else 0),
            )
            user_id = cur.lastrowid
        else:
            user_id = row["id"]
            if not _is_mirrored_parent(conn, user_id):
                raise MirrorError(
                    f"Username '{username}' is already taken by another "
                    "system account."
                )
            conn.execute(
                "UPDATE users SET password_hash = ?, legacy_salt = NULL, "
                "display_name = ?, email = ?, is_active = ?, "
                "failed_login_attempts = 0, locked_until = NULL, "
                "password_changed_at = datetime('now'), "
                "must_change_password = 0, updated_at = datetime('now') "
                "WHERE id = ?",
                (pw_hash, full_name, email, 1 if is_active else 0, user_id),
            )

        conn.execute(
            "INSERT OR IGNORE INTO user_systems (user_id, system_key, role) "
            "VALUES (?, ?, ?)",
            (user_id, SYSTEM_KEY, PARENT_ROLE),
        )
        conn.execute(
            "UPDATE user_systems SET role = ? WHERE user_id = ? AND system_key = ?",
            (PARENT_ROLE, user_id, SYSTEM_KEY),
        )

    logger.info("Mirrored parent-portal account '%s' to shared auth (id=%s)",
                username, user_id)
    return user_id


def set_password(username: str, new_password: str) -> None:
    """Push a portal password reset through to shared auth.

    Silently does nothing when there is no shadow row *and* nothing to
    build one from; callers that can create one should use :func:`upsert`.
    """
    pw_hash = _hash(new_password)
    with _auth_db(commit=True) as conn:
        row = _find_user(conn, username)
        if row is None or not _is_mirrored_parent(conn, row["id"]):
            logger.debug("No shared-auth mirror for parent '%s' to update", username)
            return
        conn.execute(
            "UPDATE users SET password_hash = ?, legacy_salt = NULL, "
            "failed_login_attempts = 0, locked_until = NULL, "
            "password_changed_at = datetime('now'), must_change_password = 0, "
            "updated_at = datetime('now') WHERE id = ?",
            (pw_hash, row["id"]),
        )
    logger.info("Synced parent-portal password reset for '%s' to shared auth", username)


def set_details(username: str, full_name: str, email: str | None) -> None:
    """Mirror a name/email edit, leaving the password alone."""
    with _auth_db(commit=True) as conn:
        row = _find_user(conn, username)
        if row is None or not _is_mirrored_parent(conn, row["id"]):
            logger.debug("No shared-auth mirror for parent '%s' to update", username)
            return
        conn.execute(
            "UPDATE users SET display_name = ?, email = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (full_name, email, row["id"]),
        )
    logger.info("Synced parent-portal details for '%s' to shared auth", username)


def set_active(username: str, active: bool) -> None:
    """Mirror an enable/disable so a disabled parent cannot use the login screen."""
    with _auth_db(commit=True) as conn:
        row = _find_user(conn, username)
        if row is None or not _is_mirrored_parent(conn, row["id"]):
            return
        conn.execute(
            "UPDATE users SET is_active = ?, updated_at = datetime('now') WHERE id = ?",
            (1 if active else 0, row["id"]),
        )
    logger.info("Set shared-auth account '%s' active=%s (parent portal)", username, active)


def remove(username: str) -> None:
    """Retire the shadow of a deleted portal account.

    The shared row is deactivated and its sixth-form access revoked rather
    than deleted: ``password_history``, ``security_audit_log`` and session
    records all reference ``users.id``, and dropping the row would orphan
    that audit trail.
    """
    with _auth_db(commit=True) as conn:
        row = _find_user(conn, username)
        if row is None or not _is_mirrored_parent(conn, row["id"]):
            return
        user_id = row["id"]
        conn.execute(
            "DELETE FROM user_systems WHERE user_id = ? AND system_key = ?",
            (user_id, SYSTEM_KEY),
        )
        remaining = conn.execute(
            "SELECT COUNT(*) AS n FROM user_systems WHERE user_id = ?", (user_id,)
        ).fetchone()["n"]
        if not remaining:
            conn.execute(
                "UPDATE users SET is_active = 0, updated_at = datetime('now') "
                "WHERE id = ?",
                (user_id,),
            )
    logger.info("Retired shared-auth mirror for deleted parent account '%s'", username)


# ── Reverse sync ─────────────────────────────────────────────────────

def verify_shared_password(username: str, password: str) -> bool:
    """True when *password* is the account's current shared-auth password.

    Lets the portal accept a password the parent changed on the shared
    side. Only mirrored parent accounts are considered, and a locked or
    deactivated shared account is refused — so this can never grant more
    than a login-screen sign-in would.
    """
    from datetime import datetime

    from education_system.platform.identity.auth.password_manager import verify_password

    try:
        with _auth_db() as conn:
            row = conn.execute(
                "SELECT id, password_hash, legacy_salt, is_active, locked_until "
                "FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if row is None or not row["is_active"]:
                return False
            if not _is_mirrored_parent(conn, row["id"]):
                return False
            if row["locked_until"]:
                try:
                    if datetime.fromisoformat(row["locked_until"]) > datetime.utcnow():
                        return False
                except ValueError:
                    return False
            return verify_password(
                password, row["password_hash"], legacy_salt=row["legacy_salt"],
            )
    except Exception as exc:
        logger.debug("Shared-auth fallback check failed for '%s': %s", username, exc)
        return False
