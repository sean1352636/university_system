"""Scheduled audit log and rate-limit cleanup.

Replaces the opportunistic cleanup in ``schema.py`` with a proper
background scheduler that runs at a configurable interval (default:
every 6 hours).

Usage:
    from education_system.shared.auth.audit_scheduler import start_cleanup_scheduler

    start_cleanup_scheduler()          # uses default auth DB path
    start_cleanup_scheduler(db_path)   # explicit path
"""

import logging
import os
import threading

from education_system.shared.auth.schema import cleanup_sq_tables

logger = logging.getLogger(__name__)

_CLEANUP_INTERVAL_HOURS = int(os.getenv("EDU_AUDIT_CLEANUP_HOURS", "6"))
_CLEANUP_INTERVAL_SECONDS = _CLEANUP_INTERVAL_HOURS * 3600

_scheduler_started = False
_lock = threading.Lock()


def _run_cleanup(db_path: str | None):
    """Execute one cleanup cycle and schedule the next."""
    try:
        cleanup_sq_tables(db_path)

        # Also clean up expired rate-limit entries
        try:
            from education_system.shared.auth.rate_limit_store import PersistentRateLimiter
            limiter = PersistentRateLimiter(db_path)
            deleted = limiter.cleanup(max_age=7200)
            if deleted:
                logger.debug("Rate-limit cleanup: removed %d stale entries", deleted)
        except Exception:
            pass

        # Clean up expired email verification tokens
        try:
            from education_system.shared.auth.db import connect
            conn = connect(db_path)
            try:
                from datetime import datetime
                now = datetime.utcnow().isoformat()
                conn.execute(
                    "DELETE FROM email_verification_tokens WHERE expires_at < ?",
                    (now,),
                )
                conn.execute(
                    "DELETE FROM password_reset_tokens WHERE expires_at < ?",
                    (now,),
                )
                conn.execute(
                    "DELETE FROM trusted_devices WHERE expires_at < ?",
                    (now,),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass

    except Exception as exc:
        logger.warning("Scheduled cleanup failed: %s", exc)

    # Re-schedule
    timer = threading.Timer(_CLEANUP_INTERVAL_SECONDS, _run_cleanup, args=(db_path,))
    timer.daemon = True
    timer.start()


def start_cleanup_scheduler(db_path: str | None = None):
    """Start the background cleanup scheduler (idempotent).

    Runs immediately on first call, then every ``EDU_AUDIT_CLEANUP_HOURS``
    hours (default 6).  The scheduler thread is daemonic and will not
    prevent the process from exiting.
    """
    global _scheduler_started
    with _lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    logger.info(
        "Audit cleanup scheduler started (interval=%dh)",
        _CLEANUP_INTERVAL_HOURS,
    )
    # Run first cleanup immediately in a separate thread
    thread = threading.Thread(target=_run_cleanup, args=(db_path,), daemon=True)
    thread.start()
