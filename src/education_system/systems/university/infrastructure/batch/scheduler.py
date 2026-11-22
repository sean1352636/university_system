"""Runs scheduled batch work in the background, every minute, on its own
connections: watched folders at their daily time and scheduled batch
reports (``application/batch/schedule``), and scheduled Document Manager
reports (``utils/document_manager/report_schedules``). Report e-mails go
through the outbox after the run commits."""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

INTERVAL = 60
_WORKER: threading.Thread | None = None


def run_once(db_path=None) -> dict:
    """Every due job once; one failing does not stop the other."""
    from education_system.systems.university.application.batch import schedule as batch_schedule
    report: dict = {}
    try:
        report["watches"] = batch_schedule.run_due_watches(db_path=db_path)
    except Exception:
        logger.exception("Scheduled watched-folder imports failed")
        report["watches"] = None
    try:
        emails = batch_schedule.run_due_reports(db_path=db_path)
        if emails:
            from education_system.systems.university.infrastructure.ui.record_screens import (
                send_emails,
            )
            send_emails(emails)
        report["reports"] = len(emails)
    except Exception:
        logger.exception("Scheduled batch reports failed")
        report["reports"] = None
    try:
        from education_system.systems.university.infrastructure.utils.document_manager import (
            report_schedules as document_reports,
        )
        emails = document_reports.run_due_reports(db_path=db_path)
        if emails:
            from education_system.systems.university.infrastructure.ui.record_screens import (
                send_emails,
            )
            send_emails(emails)
        report["document_reports"] = len(emails)
    except Exception:
        logger.exception("Scheduled document manager reports failed")
        report["document_reports"] = None
    return report


def _loop(db_path) -> None:
    while True:
        report = run_once(db_path)
        if report.get("watches") or report.get("reports") or report.get("document_reports"):
            logger.info("Scheduled batch work: %s", report)
        time.sleep(INTERVAL)


def start_worker(db_path=None) -> bool:
    """Start the scheduler once per process."""
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return False
    _WORKER = threading.Thread(target=_loop, args=(db_path,), daemon=True,
                               name="batch-scheduler")
    _WORKER.start()
    return True
