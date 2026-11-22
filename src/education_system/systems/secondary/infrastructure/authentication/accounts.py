"""The shared login database (``auth.db``), as the secondary system uses it.

Only two things: create a pupil's login, and remove the secondary role
from it. Tests and probes point it at a scratch file with
:func:`use_auth_db` so they never touch the real accounts.
"""

from __future__ import annotations

from education_system.systems.secondary import SYSTEM_KEY

PUPIL_ROLE = "student"

_override: str | None = None


def use_auth_db(path: str | None) -> None:
    """Point account operations at *path* (``None`` = the real auth.db)."""
    global _override
    _override = str(path) if path else None


def _guard() -> None:
    """Refuse to reach the real auth.db while the school database is redirected.

    A test or probe that points the school DB at a scratch file (with
    ``database.use_database``) but forgets :func:`use_auth_db` would
    otherwise create real logins for fake pupils.
    """
    from education_system import paths
    from education_system.systems.secondary.infrastructure.database import connection as database
    if _override is None and database.db_path() != paths.SECONDARY_PUPILS_DB:
        raise RuntimeError(
            "The secondary database is redirected (test mode) but auth.db is not - "
            "call accounts.use_auth_db(<scratch file>) too")


def _auth():
    from education_system.platform.identity.auth.core import UserAuth
    _guard()
    return UserAuth(db_path=_override)


def auth_setting(key: str, default=None):
    """One shared sign-in setting from auth.db (lockout, password age,
    session timeout...)."""
    return _auth().get_setting(key, default)


def set_auth_setting(key: str, value) -> None:
    """Save a shared sign-in setting (it applies to every system).
    Callers check permissions and log it (settings.set_auth_policy)."""
    _auth().set_setting(key, value)


def clear_auth_setting(key: str) -> None:
    """Remove a stored sign-in setting, so the platform default applies."""
    conn = _connect()
    try:
        conn.execute("DELETE FROM auth_settings WHERE key = ?", (key,))
        conn.commit()
    except Exception as e:  # noqa: BLE001 - nothing stored yet is fine
        if "no such table" not in str(e):
            raise
    finally:
        conn.close()


def password_reset_policy() -> bool:
    """Whether this school forces password resets by age (its own switch in
    auth.db, else the platform-wide one)."""
    from education_system.systems.secondary import SYSTEM_KEY
    return _auth().get_system_password_policy(SYSTEM_KEY)


def set_password_reset_policy(enabled: bool) -> None:
    from education_system.systems.secondary import SYSTEM_KEY
    _auth().set_system_password_policy(SYSTEM_KEY, bool(enabled))


def _connect():
    from education_system.platform.identity.auth.db import connect
    _guard()
    return connect(_override)


def usernames_like(base: str) -> set[str]:
    """Existing usernames equal to *base* or *base* + digits (any case)."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT username FROM users WHERE lower(username) = lower(?) "
            "OR lower(username) GLOB lower(?) || '[0-9]*'", (base, base)).fetchall()
    finally:
        conn.close()
    return {r[0].lower() for r in rows}


def create_login(username: str, password: str, *, display_name: str, email: str) -> int:
    """Create a new pupil login and return its user id.

    The pupil password (surname + 5 digits) is deliberately simpler than the
    staff password policy, so this uses ``provision_user``, which does not
    apply that policy. It is an upsert, so refuse up front if the name is taken
    - an existing account must never be changed from here.
    """
    if username.lower() in usernames_like(username):
        raise ValueError(f"The username '{username}' is already in use")
    return _auth().provision_user(username, password, display_name=display_name,
                                  email=email, systems=[(SYSTEM_KEY, PUPIL_ROLE)])


def close_pupil_login(username: str, email: str, message: str) -> bool:
    """Take the pupil role off a login and leave *message* for the owner to see
    if they try to sign in. A login that still has another system (say they
    moved on to the sixth form) stays usable there and gets no message.
    False if the account no longer matches."""
    auth = _auth()
    if not auth.revoke_system_access(username, email, SYSTEM_KEY, PUPIL_ROLE):
        return False
    conn = _connect()
    try:
        row = conn.execute("SELECT is_active FROM users WHERE username = ? AND email = ?",
                           (username, email)).fetchone()
    finally:
        conn.close()
    if row is not None and not row[0]:
        auth.set_deactivation_message(username, email, message)
    return True


def reopen_pupil_login(username: str, email: str) -> bool:
    """Give a returning pupil their login back (same username and password)."""
    return _auth().restore_system_access(username, email, SYSTEM_KEY, PUPIL_ROLE)


def remove_pupil_access(username: str, email: str) -> bool:
    """Take the secondary pupil role off a login (deactivating it if that was
    its only system). False if the account no longer matches."""
    return _auth().revoke_system_access(username, email, SYSTEM_KEY, PUPIL_ROLE)


def staff_logins() -> list[dict]:
    """Active logins with a secondary staff role: [{username, display_name, email, role}],
    by name. Read-only - used to pick a teacher."""
    from education_system.systems.secondary.core.permissions.access import _LEGACY_KEYS, STAFF_ROLES
    keys = (SYSTEM_KEY, *_LEGACY_KEYS)
    roles = tuple(sorted(STAFF_ROLES))
    import sqlite3
    conn = _connect()
    try:
        try:
            rows = conn.execute(
            "SELECT u.username, u.display_name, u.email, s.role FROM users u "
            "JOIN user_systems s ON s.user_id = u.id WHERE u.is_active = 1 "
            f"AND s.system_key IN ({', '.join('?' * len(keys))}) "  # nosec B608 - placeholders only
            f"AND s.role IN ({', '.join('?' * len(roles))}) "
            "ORDER BY lower(coalesce(u.display_name, u.username))", (*keys, *roles)).fetchall()
        except sqlite3.OperationalError:  # an empty / not-yet-initialised auth.db
            rows = []
    finally:
        conn.close()
    seen, out = set(), []
    for r in rows:
        if r[0].lower() not in seen:
            seen.add(r[0].lower())
            out.append({"username": r[0], "display_name": r[1] or r[0], "email": r[2],
                        "role": r[3]})
    return out


# ── Portal logins (pupils linked by hand, parents) ───────────────────

PARENT_ROLE = "parent"


def _login_row(where: str, value: str) -> dict | None:
    from education_system.systems.secondary.core.permissions.access import _LEGACY_KEYS
    conn = _connect()
    try:
        r = conn.execute(f"SELECT id, username, email, display_name, is_active FROM users "  # nosec B608 - fixed column
                         f"WHERE lower({where}) = lower(?) ORDER BY id LIMIT 1",
                         (value.strip(),)).fetchone()
        if r is None:
            return None
        keys = (SYSTEM_KEY, *_LEGACY_KEYS)
        role = conn.execute(
            f"SELECT role FROM user_systems WHERE user_id = ? AND system_key IN "  # nosec B608 - placeholders only
            f"({', '.join('?' * len(keys))}) LIMIT 1", (r[0], *keys)).fetchone()
    finally:
        conn.close()
    return {"id": r[0], "username": r[1], "email": r[2], "display_name": r[3] or r[1],
            "is_active": bool(r[4]), "role": role[0] if role else None}


def find_login(username: str) -> dict | None:
    """{id, username, email, display_name, is_active, role} - role is the
    login's secondary role (None if it has none). Read-only."""
    return _login_row("username", username) if username and username.strip() else None


def find_login_by_email(email: str) -> dict | None:
    """The oldest login with this e-mail address (any system), or None."""
    return _login_row("email", email) if email and email.strip() else None


def create_parent_login(username: str, password: str, *, display_name: str,
                        email: str) -> int:
    """A new login with the secondary ``parent`` role. Refuses a taken name."""
    if username.lower() in usernames_like(username):
        raise ValueError(f"The username '{username}' is already in use")
    return _auth().provision_user(username, password, display_name=display_name,
                                  email=email, systems=[(SYSTEM_KEY, PARENT_ROLE)])


def grant_role(username: str, email: str | None, role: str) -> bool:
    """Give an existing login the secondary *role* (it must have none here).
    Matches username and e-mail together. False if the account doesn't match."""
    return _auth().restore_system_access(username, email or "", SYSTEM_KEY, role)


def revoke_role(username: str, email: str | None, role: str) -> bool:
    """Take the secondary *role* off a login (deactivated only if it was its
    only system). False if the account doesn't match."""
    return _auth().revoke_system_access(username, email or "", SYSTEM_KEY, role)
