"""The daily academic integrity worker, on its own connection: removes
submitted text past the retention period (``application/integrity/records
.purge``), sends reminders and closes cases whose appeal period has passed
(``application/integrity/jobs``), retries failed automatic checks
(``submission_hook.retry_failures``) and runs the AI detector's scheduled
batch jobs whose time has come (each as the person who scheduled it)."""

from __future__ import annotations

import logging
import threading
import time

from education_system.systems.university.application.integrity import (
    jobs as integrity_jobs,
    records as integrity_records,
)

logger = logging.getLogger(__name__)

DAY = 86400
_WORKER: threading.Thread | None = None


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def purge_now(db_path=None) -> int:
    conn = _connect(db_path)
    try:
        removed = integrity_records.purge(conn)
        conn.commit()
        return removed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def jobs_now(db_path=None) -> dict:
    """Reminders and automatic closing; e-mails go after the commit."""
    conn = _connect(db_path)
    try:
        done = integrity_jobs.run_daily(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    if done["emails"]:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(done.pop("emails"))
    return done


def batch_jobs_now(db_path=None) -> dict:
    from education_system.systems.university.shared.ai.ai_detector.detector.main import (
        AIDetector,
    )
    kwargs = {"db_path": str(db_path)} if db_path else {}
    return AIDetector(**kwargs).run_due_batch_jobs()


def run_once(db_path=None) -> dict:
    """Every daily job once; a failing job does not stop the others."""
    from education_system.systems.university.infrastructure.integrity import submission_hook
    report: dict = {}
    for name, job in (("purged", purge_now), ("jobs", jobs_now),
                      ("retries", submission_hook.retry_failures),
                      ("ai_batch_jobs", batch_jobs_now)):
        try:
            report[name] = job(db_path)
        except Exception:
            logger.exception("Integrity daily job %s failed", name)
            report[name] = None
    return report


def _loop(db_path) -> None:
    while True:
        report = run_once(db_path)
        if any(report.values()):
            logger.info("Integrity daily jobs: %s", report)
        time.sleep(DAY)


def start_worker(db_path=None) -> bool:
    """Start the daily jobs once per process."""
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return False
    _WORKER = threading.Thread(target=_loop, args=(db_path,), daemon=True,
                               name="integrity-daily")
    _WORKER.start()
    return True
