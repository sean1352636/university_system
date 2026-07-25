"""Scheduled execution of GDPR data retention policies.

Uses the ``schedule`` library (pip install schedule) to run policies on a
configurable timetable.  The scheduler runs in a daemon thread so it does
not block the main application.

Usage (standalone)::

    from education_system.platform.services.data_retention.scheduler import RetentionScheduler
    scheduler = RetentionScheduler()
    scheduler.start()          # starts background thread
    scheduler.run_once()       # trigger an immediate run

Environment variables
---------------------
RETENTION_RUN_TIME   — 24-h "HH:MM" time for the daily run (default: "02:00")
RETENTION_INTERVAL_H — run every N hours instead of once-daily (optional)
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)


def _import_schedule():
    try:
        import schedule
        return schedule
    except ImportError as exc:
        raise ImportError(
            "The 'schedule' package is required for the retention scheduler. "
            "Install it with: pip install schedule"
        ) from exc


class RetentionScheduler:
    """Schedules and runs data retention policies in a background thread.

    Parameters
    ----------
    retention_db_path:
        Path to the shared retention database.  Passed through to
        ``RetentionPolicyEngine``.
    run_time:
        Daily run time in ``"HH:MM"`` 24-hour format (default ``"02:00"``).
    interval_hours:
        If set, run every N hours instead of once-daily.
    on_complete:
        Optional callback ``(results: list[dict]) -> None`` called after each
        successful run with the list of job records returned by the engine.
    """

    def __init__(
        self,
        retention_db_path: str | Path | None = None,
        run_time: str = "02:00",
        interval_hours: int | None = None,
        on_complete: Callable[[list[dict]], None] | None = None,
    ):
        import os
        self._db_path = retention_db_path
        self._run_time = os.getenv("RETENTION_RUN_TIME", run_time)
        raw_interval = os.getenv("RETENTION_INTERVAL_H")
        self._interval_hours = (
            int(raw_interval) if raw_interval else interval_hours
        )
        self._on_complete = on_complete
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler thread (idempotent)."""
        if self._running:
            logger.warning("RetentionScheduler already running.")
            return

        schedule = _import_schedule()
        schedule.clear("retention")

        if self._interval_hours:
            schedule.every(self._interval_hours).hours.do(
                self._run_policies_safe
            ).tag("retention")
            logger.info(
                "Retention scheduler: will run every %d hour(s).",
                self._interval_hours,
            )
        else:
            schedule.every().day.at(self._run_time).do(
                self._run_policies_safe
            ).tag("retention")
            logger.info(
                "Retention scheduler: will run daily at %s.", self._run_time
            )

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="RetentionSchedulerThread",
            daemon=True,
        )
        self._running = True
        self._thread.start()
        logger.info("RetentionScheduler started.")

    def stop(self) -> None:
        """Signal the background thread to stop."""
        self._stop_event.set()
        self._running = False
        logger.info("RetentionScheduler stop requested.")

    def run_once(self) -> list[dict]:
        """Trigger an immediate policy run (blocking, returns job records)."""
        return self._run_policies_safe()

    @property
    def is_running(self) -> bool:
        return self._running and (
            self._thread is not None and self._thread.is_alive()
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        schedule = _import_schedule()
        while not self._stop_event.is_set():
            schedule.run_pending()
            # Sleep in short increments so stop() is responsive
            self._stop_event.wait(timeout=30)
        logger.info("RetentionScheduler loop exited.")

    def _run_policies_safe(self) -> list[dict]:
        """Run all active policies and swallow exceptions to protect the loop."""
        from .policy_engine import RetentionPolicyEngine

        started = datetime.utcnow().isoformat()
        logger.info("Retention run started at %s", started)
        try:
            engine = RetentionPolicyEngine(self._db_path)
            results = engine.run_all_policies()
            logger.info(
                "Retention run completed: %d jobs processed.", len(results)
            )
            if self._on_complete:
                try:
                    self._on_complete(results)
                except Exception as cb_exc:
                    logger.error("on_complete callback raised: %s", cb_exc)
            return results
        except Exception as exc:
            logger.error("Retention run failed: %s", exc, exc_info=True)
            return []
