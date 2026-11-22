"""The results-day job: applies held UCAS confirmations once results are out.

Results day holds every confirmation, rejection and e-mail for an applicant
until each exam result its verdict relies on is published (see
``admissions.domain.ucas.results_day``). This applies them once the
embargo lifts — every fifteen minutes, so a place confirmed on the morning
of results day is not left waiting until somebody opens the board. Started
from the university launch beside the other jobs (one daemon thread per
process; a failing pass is logged and the next still runs).
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

INTERVAL = 900
_WORKER: threading.Thread | None = None


def run_once() -> dict:
    """Apply every held results-day action whose results are published."""
    from education_system.systems.university.domains.admissions.domain.ucas import (
        results_day,
    )
    if not results_day.list_holds(status="Held"):
        return {}
    return results_day.apply_released_holds(
        released_by="auto (results-day job)")


def _loop() -> None:
    while True:
        try:
            report = run_once()
            if report:
                logger.info("Results-day holds: %s", report)
        except Exception:
            logger.exception("Results-day hold job failed")
        time.sleep(INTERVAL)


def start_worker() -> bool:
    """Start the results-day job once per process."""
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return False
    _WORKER = threading.Thread(target=_loop, daemon=True,
                               name="ucas-results-day")
    _WORKER.start()
    return True
