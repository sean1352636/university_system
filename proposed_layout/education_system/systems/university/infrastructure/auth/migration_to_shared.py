"""Migrate existing university user_accounts into the shared auth database.

This script copies credentials from the university's ``user_accounts`` table
into the shared ``auth.db`` so that university users can log in via the
unified login flow.  PBKDF2 hashes are stored as-is with their salt in the
``legacy_salt`` column; they will be transparently re-hashed to bcrypt on
each user's first successful login.

Usage::

    python -m education_system.systems.university.infrastructure.auth.migration_to_shared
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def migrate(university_db_path: str | None = None):
    """Copy university credentials into the shared auth database."""
    from education_system.platform.identity.auth.db import connect as shared_connect
    from education_system.platform.identity.auth.schema import initialise_auth_db, seed_default_users

    if university_db_path is None:
        from education_system.systems.university.infrastructure import paths
        university_db_path = str(paths.DEFAULT_DB_PATH)

    # Ensure shared DB schema exists
    initialise_auth_db()
    seed_default_users()

    # Open university DB
    uni_conn = sqlite3.connect(university_db_path, timeout=30)
    uni_conn.row_factory = sqlite3.Row

    shared_conn = shared_connect()

    try:
        # Read all university accounts
        try:
            rows = uni_conn.execute(
                """SELECT ua.username, ua.password_hash, ua.salt, u.role,
                          u.email, u.first_name, u.last_name
                   FROM user_accounts ua
                   LEFT JOIN users u ON ua.user_id = u.id
                   WHERE ua.is_active = 1"""
            ).fetchall()
        except sqlite3.OperationalError:
            logger.warning("No user_accounts table found in university DB")
            return 0

        migrated = 0
        for row in rows:
            username = row["username"]

            # Skip if already in shared DB
            existing = shared_conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                logger.debug("User '%s' already exists in shared auth DB", username)
                continue

            display_name = ""
            if row["first_name"] and row["last_name"]:
                display_name = f"{row['first_name']} {row['last_name']}"
            elif row["first_name"]:
                display_name = row["first_name"]

            # Insert with legacy PBKDF2 hash and salt
            cursor = shared_conn.execute(
                """INSERT INTO users
                   (username, password_hash, display_name, email, legacy_salt)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    username,
                    row["password_hash"],
                    display_name or username,
                    row["email"] or f"{username}@university.local",
                    row["salt"],
                ),
            )
            user_id = cursor.lastrowid

            # Grant university system access
            role = row["role"] or "student"
            shared_conn.execute(
                """INSERT OR IGNORE INTO user_systems
                   (user_id, system_key, role) VALUES (?, ?, ?)""",
                (user_id, "university", role),
            )
            migrated += 1
            logger.info("Migrated user '%s' (role=%s)", username, role)

        shared_conn.commit()
        logger.info("Migration complete: %d accounts migrated", migrated)
        return migrated

    finally:
        uni_conn.close()
        shared_conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    count = migrate()
    print(f"Migrated {count} university accounts to shared auth database.")
