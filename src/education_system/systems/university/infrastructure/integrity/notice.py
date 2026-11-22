"""The academic integrity notice students see where they submit work,
read and acknowledged on short connections of their own."""

from __future__ import annotations

import logging

from education_system.systems.university.application.integrity import access as integrity_access

logger = logging.getLogger(__name__)


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def notice_text(db_path=None) -> str:
    try:
        conn = _connect(db_path)
        try:
            return integrity_access.notice(conn)["text"]
        finally:
            conn.close()
    except Exception:
        logger.debug("Integrity notice unavailable", exc_info=True)
        return integrity_access.SETTINGS["notice_text"]


def acknowledge(username, db_path=None) -> None:
    """Record that ``username`` has seen the current notice."""
    if not username:
        return
    conn = _connect(db_path)
    try:
        integrity_access.acknowledge(conn, integrity_access.person(conn, username))
        conn.commit()
    except Exception:
        conn.rollback()
        logger.debug("Integrity notice acknowledgement not recorded", exc_info=True)
    finally:
        conn.close()
