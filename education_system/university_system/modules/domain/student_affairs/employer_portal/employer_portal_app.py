"""Standalone Tk launcher for the Employer Portal.

Auth: piggybacks on the main university auth — when launched as a
subprocess from the unified main GUI, EDU_AUTH_* env vars carry the
logged-in user's identity. The portal reads them via
`EmployerPortalFrame(auth=...)`; there is no in-app login.

Persistence: data lives in the central `student_records.db` (tables
`employer_accounts`, `placement_reviews`, `placement_review_signoffs`
managed by the underlying service). Any stray *.db files alongside this
module are removed on startup.

Logging: routed through the shared rotating `app.log` via
`infrastructure.logging.log_config.configure_logging`.
"""
from __future__ import annotations

import logging
import os
import pathlib
import sys

_p = pathlib.Path(__file__).resolve()
while _p.parent != _p and not (_p / "education_system").is_dir():
    _p = _p.parent
if str(_p) not in sys.path:
    sys.path.insert(0, str(_p))

import tkinter as tk  # noqa: E402

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    configure_logging(name=__name__)
except Exception:
    logger.debug("Central log config unavailable; falling back to default handlers", exc_info=True)


def _get_current_user():
    """Resolve the logged-in user dict from EDU_AUTH_* env vars, with a
    fallback to the in-process global auth singleton."""
    user_id = os.environ.get('EDU_AUTH_USER_ID') or ''
    username = os.environ.get('EDU_AUTH_USERNAME') or ''
    role = os.environ.get('EDU_AUTH_ROLE') or ''
    email = os.environ.get('EDU_AUTH_EMAIL') or ''
    perms_raw = os.environ.get('EDU_AUTH_PERMISSIONS') or ''
    if user_id or username:
        return {
            'id': user_id or None,
            'user_id': user_id or None,
            'username': username,
            'role': role,
            'email': email,
            'permissions': [p for p in perms_raw.split(',') if p],
        }
    try:
        from education_system.university_system.infrastructure.auth import get_global_auth
        ga = get_global_auth()
        if ga and getattr(ga, 'current_user', None):
            return ga.current_user
    except Exception:
        logger.debug("get_global_auth fallback failed", exc_info=True)
    return None


def _remove_legacy_db():
    """Sweep any stray local SQLite files left alongside this module by
    earlier iterations. Data lives in the central student_records.db."""
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(here):
        return
    for fname in os.listdir(here):
        if fname.endswith(('.db', '.db-wal', '.db-shm', '.db-journal')):
            path = os.path.join(here, fname)
            try:
                os.remove(path)
                logger.info("Removed legacy employer-portal DB file: %s", path)
            except OSError:
                logger.warning("Could not remove legacy DB file %s", path,
                               exc_info=True)


from education_system.university_system.modules.domain.student_affairs.employer_portal.gui.employer_portal_gui import (  # noqa: E402
    EmployerPortalFrame,
)


def main() -> None:
    _remove_legacy_db()
    user = _get_current_user()
    logger.info("Employer Portal starting user=%s role=%s",
                (user or {}).get('username') or 'guest',
                (user or {}).get('role') or 'none')

    root = tk.Tk()
    root.title("Employer Portal")
    root.geometry("980x640")
    EmployerPortalFrame(root, auth=user).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
