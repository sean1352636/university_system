"""The hourly health clinic job (``application/health/diary``), on its own
connection: 24-hour and 2-hour appointment reminders for every clinic
(health, dental, counselling, mental health), feedback requests after a
completed appointment, automatic screening reminders, and lapsed
waiting-list offers passed to the next person. Each e-mail goes once, to
the outbox, after the commit. Started from the university launch; the
manual reminder buttons in the portal stay as they were."""

from __future__ import annotations

import logging
import threading
import time

from education_system.systems.university.domains.health.application.health import diary

logger = logging.getLogger(__name__)

HOUR = 3600
_WORKER: threading.Thread | None = None


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def run_once(db_path=None, now=None) -> dict:
    conn = _connect(db_path)
    try:
        emails = diary.due_reminders(conn, now=now) + diary.expire_offers(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    sent, failed = diary.send_emails(emails)
    return {"queued": len(emails), "sent": sent, "failed": failed}


def _loop(db_path) -> None:
    while True:
        try:
            report = run_once(db_path)
            if report["queued"]:
                logger.info("Health reminders: %s", report)
        except Exception:
            logger.exception("Health reminder run failed")
        time.sleep(HOUR)


def start_worker(db_path=None) -> bool:
    """Start the hourly run once per process."""
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return False
    _WORKER = threading.Thread(target=_loop, args=(db_path,), daemon=True,
                               name="health-reminders-hourly")
    _WORKER.start()
    return True
