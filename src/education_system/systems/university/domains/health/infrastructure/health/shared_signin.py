"""Read-only lookups in the shared sign-in database (``auth.db``) for the
health services — who holds a university role there.

Kept here, in infrastructure, so the health domain does not open SQLite
itself (the slice rules forbid a domain layer importing a SQL driver).
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def users_with_university_role(role: str) -> list[tuple[str, str | None]]:
    """``[(username, display_name), ...]`` for shared sign-in accounts that
    hold ``role`` in the university. Opened read-only; ``[]`` if the
    database can't be read."""
    from education_system import paths
    try:
        conn = sqlite3.connect(f"file:{paths.PLATFORM_AUTH_DB}?mode=ro", uri=True)
    except sqlite3.Error:
        logger.debug("shared sign-in database not readable", exc_info=True)
        return []
    try:
        return [(str(u), d) for u, d in conn.execute(
            "SELECT u.username, u.display_name FROM users u JOIN user_systems s ON "
            "s.user_id = u.id WHERE s.system_key = 'university' AND LOWER(s.role) = ?",
            (str(role).lower(),)).fetchall()]
    finally:
        conn.close()
