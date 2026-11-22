"""Small helpers shared by the Student Union screens that read real records.

* :func:`db` — a connection to the university database that is always
  closed (``with get_connection() as conn`` only ends the transaction).
* :func:`owner_id` — the id SU rows are owned by for the signed-in user
  (real student id, or ``user:<username>`` for staff/admin).
* :func:`open_target` — open a written file or a URL with the desktop's
  default handler, returning False rather than raising when it cannot.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from contextlib import contextmanager
from pathlib import Path

from education_system import paths
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domains.student_life.domain.student_life.student_union.identity import (
    current_student_id,
)

logger = logging.getLogger(__name__)

STAFF_ROLES = frozenset({"admin", "superadmin", "administrator", "staff"})


@contextmanager
def db():
    conn = get_connection(str(paths.UNIVERSITY_DEFAULT_DB_PATH))
    try:
        yield conn
    finally:
        conn.close()


def owner_id(conn, auth) -> str | None:
    return current_student_id(conn.cursor(), auth)


def username(auth) -> str | None:
    user = getattr(auth, "current_user", None) or {}
    return user.get("username") if isinstance(user, dict) else None


def is_staff(auth) -> bool:
    user = getattr(auth, "current_user", None) or {}
    try:
        return str(user.get("role") or "").lower() in STAFF_ROLES
    except AttributeError:
        return False


def open_target(target: str | Path) -> bool:
    """Open a local file or URL; True if a handler was launched."""
    text = str(target)
    try:
        if "://" in text and not text.startswith("file://"):
            return bool(webbrowser.open(text))
        path = Path(text)
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])  # noqa: S603,S607
        else:
            subprocess.Popen(["xdg-open", str(path)],  # noqa: S603,S607
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as exc:
        logger.debug("could not open %s: %s", text, exc)
        return False


__all__ = ["db", "owner_id", "username", "is_staff", "open_target", "STAFF_ROLES"]
