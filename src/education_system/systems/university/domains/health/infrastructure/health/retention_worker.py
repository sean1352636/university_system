"""The daily health jobs, on their own connection, started from the
university launch:

* the retention purge (``application/health/retention``) — only when a
  health policy has ``auto_delete = 1``;
* first aid reminders (``application/health/first_aid.run_daily``) —
  certificate expiries, RIDDOR deadlines, kit/AED checks;
* medical accommodations (``services/bus/accommodation_bus.reconcile``) —
  expiries, and carrying approvals to exams/assessments/module staff.

E-mails go through the outbox after the commit."""

from __future__ import annotations

import logging
import threading
import time

from education_system.systems.university.domains.health.application.health import retention

logger = logging.getLogger(__name__)

DAY = 86400
_WORKER: threading.Thread | None = None


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    # Row factory: the immutable audit log reads its chain by column name.
    return get_connection(db_path, row_factory=True)


def run_once(db_path=None) -> dict:
    conn = _connect(db_path)
    try:
        if not retention.any_auto_delete(conn):
            return {"skipped": "no auto_delete health policy"}
        report = retention.purge(conn, by="system:health-retention", dry_run=False)
        conn.commit()
        return report["removed"]
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_daily_jobs(db_path=None) -> dict:
    """First aid reminders and accommodation reconciliation (see the module
    docstring). Each job runs on its own; one failing does not stop the
    other."""
    out: dict = {}
    from education_system.systems.university.domains.health.application.health import (
        first_aid,
    )
    from education_system.systems.university.domains.health.infrastructure.health import (
        first_aid_schema,
    )
    conn = _connect(db_path)
    try:
        first_aid_schema.apply_to_connection(conn)
        emails = first_aid.run_daily(conn)
        conn.commit()
        out["first_aid_reminders"] = len(emails)
    except Exception:
        conn.rollback()
        logger.exception("First aid reminders failed")
        emails = []
    finally:
        conn.close()
    _send(emails)
    try:
        from education_system.systems.university.services.bus import accommodation_bus
        conn = _connect(db_path)
        try:
            result = accommodation_bus.reconcile(conn, send=True)
        finally:
            conn.close()
        out["accommodations"] = {k: v for k, v in result.items() if k != "emails"}
    except Exception:
        logger.exception("Medical accommodation reconciliation failed")
    return out


def _send(emails) -> None:
    if not emails:
        return
    try:
        from education_system.systems.university.infrastructure.email.email_service.core import (
            send_email,
        )
    except Exception:
        logger.debug("E-mail unavailable; %d health reminders not sent", len(emails))
        return
    for address, subject, body in emails:
        try:
            send_email(address, subject, body)
        except Exception:
            logger.debug("Health reminder to %s failed", address, exc_info=True)


def _loop(db_path) -> None:
    while True:
        try:
            removed = run_once(db_path)
            if removed and "skipped" not in removed:
                logger.info("Health retention purge: %s", removed)
        except Exception:
            logger.exception("Health retention purge failed")
        try:
            logger.info("Daily health jobs: %s", run_daily_jobs(db_path))
        except Exception:
            logger.exception("Daily health jobs failed")
        time.sleep(DAY)


def start_worker(db_path=None) -> bool:
    """Start the daily health jobs once per process. The purge inside still
    runs only when a health policy asks for automatic deletion (checked
    each day); reminders and accommodation reconciliation always run."""
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return False
    _WORKER = threading.Thread(target=_loop, args=(db_path,), daemon=True,
                               name="health-retention-daily")
    _WORKER.start()
    return True
