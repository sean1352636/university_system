"""Shared authentication bootstrap and university MFA sync."""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def init_shared_auth():
    """Initialise the shared auth database on first run."""
    from education_system.shared.auth.schema import initialise_auth_db, seed_default_users
    initialise_auth_db()
    seed_default_users()


def sync_university_mfa_to_shared():
    """Copy any TOTP secrets from the university DB to the shared auth DB.

    This ensures that users who set up MFA through the university GUI
    before the shared-auth sync was added will still be prompted for
    TOTP when logging in via the universal login.
    """
    # Read TOTP secrets from university DB
    from education_system.post_18.university_system.core.paths import DEFAULT_DB_PATH
    uni_conn = sqlite3.connect(str(DEFAULT_DB_PATH))
    uni_conn.row_factory = sqlite3.Row
    try:
        rows = uni_conn.execute(
            "SELECT ua.user_id, ua.username, ua.two_fa_secret "
            "FROM user_accounts ua "
            "WHERE ua.two_fa_secret IS NOT NULL AND ua.two_fa_secret != ''"
        ).fetchall()
    except sqlite3.OperationalError:
        return  # table or column doesn't exist yet
    finally:
        uni_conn.close()

    if not rows:
        return

    # Write them to the shared auth mfa_secrets table
    from education_system.shared.auth.db import connect as shared_connect
    shared_conn = shared_connect()
    try:
        synced = 0
        for row in rows:
            username = row["username"]
            secret = row["two_fa_secret"]

            shared_row = shared_conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if not shared_row:
                continue

            shared_uid = shared_row["id"]
            existing = shared_conn.execute(
                "SELECT id FROM mfa_secrets WHERE user_id = ?", (shared_uid,)
            ).fetchone()
            if existing:
                continue

            shared_conn.execute(
                "INSERT INTO mfa_secrets (user_id, totp_secret, is_enabled) "
                "VALUES (?, ?, 1)",
                (shared_uid, secret),
            )
            synced += 1

        if synced:
            shared_conn.commit()
            logger.info("Synced %d university TOTP secret(s) to shared auth DB", synced)
    finally:
        shared_conn.close()


def gui_universal_login(target_system: str | None = None):
    """Show the universal login window.

    Returns (user_info, system_key, system_role, auth) or None if cancelled.
    """
    init_shared_auth()

    from education_system.shared.gui.login_gui import UniversalLoginWindow
    login = UniversalLoginWindow(target_system=target_system)
    login.mainloop()

    if login.user_info and login.system_key:
        return login.user_info, login.system_key, login.system_role, login.auth
    return None


def cli_universal_login(target_system: str | None = None):
    """Show the universal CLI login prompt.

    Returns (user_info, system_key, system_role, auth) or None if cancelled.
    """
    init_shared_auth()

    from education_system.shared.cli.login_cli import universal_cli_login
    return universal_cli_login(target_system=target_system)
