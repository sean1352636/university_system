"""Background runner for the sixth form scheduler.

A daemon thread wakes every ``tick_seconds``, runs whatever is due
(:func:`core.run_due_jobs`) and goes back to sleep. Jobs run on this
thread, never on the GUI thread, and never touch Tk; the GUI only reads
the run history the jobs write.

Two app instances may both run a background scheduler — the per-job
database lock means each job still runs once. Set the environment
variable ``EDU_SIXTHFORM_SCHEDULER=off`` to stop the GUI starting one
(for example when cron runs ``run_due_jobs`` instead).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Callable

from education_system.systems.sixth_form.infrastructure.scheduler import core

logger = logging.getLogger(__name__)

DEFAULT_TICK_SECONDS = 60
#: Give the app time to finish opening before the first run.
DEFAULT_FIRST_DELAY_SECONDS = 20
ENV_SWITCH = "EDU_SIXTHFORM_SCHEDULER"


def disabled_by_env() -> bool:
    return (os.environ.get(ENV_SWITCH) or "").strip().lower() in (
        "0", "off", "false", "no", "disabled")


class BackgroundScheduler:
    def __init__(self, *, tick_seconds: int = DEFAULT_TICK_SECONDS,
                 first_delay_seconds: int = DEFAULT_FIRST_DELAY_SECONDS) -> None:
        self.tick_seconds = max(5, int(tick_seconds))
        self.first_delay_seconds = max(0, int(first_delay_seconds))
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.last_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if self.running:
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop,
                                        name="sixth-form-scheduler", daemon=True)
        self._thread.start()
        logger.info("Sixth form background scheduler started (tick %ds)",
                    self.tick_seconds)
        return True

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)
        logger.info("Sixth form background scheduler stopped")

    def poke(self) -> None:
        """Check for due jobs now rather than at the next tick."""
        self._wake.set()

    def _sleep(self, seconds: float) -> None:
        self._wake.wait(timeout=seconds)
        self._wake.clear()

    def _loop(self) -> None:
        self._sleep(self.first_delay_seconds)
        while not self._stop.is_set():
            try:
                core.run_due_jobs(should_stop=self._stop.is_set)
                self.last_error = None
            except Exception as e:  # noqa: BLE001 - the loop must survive
                self.last_error = str(e)
                logger.exception("Scheduler tick failed")
            if self._stop.is_set():
                break
            self._sleep(self.tick_seconds)


_INSTANCE: BackgroundScheduler | None = None
_INSTANCE_LOCK = threading.Lock()


def instance() -> BackgroundScheduler | None:
    return _INSTANCE


def start(**kwargs) -> BackgroundScheduler | None:
    """Start the process-wide background scheduler (idempotent).
    Returns ``None`` when switched off by :data:`ENV_SWITCH`."""
    global _INSTANCE
    if disabled_by_env():
        logger.info("Sixth form background scheduler is switched off (%s)",
                    ENV_SWITCH)
        return None
    with _INSTANCE_LOCK:
        if _INSTANCE is None:
            _INSTANCE = BackgroundScheduler(**kwargs)
        _INSTANCE.start()
        return _INSTANCE


def stop() -> None:
    with _INSTANCE_LOCK:
        if _INSTANCE is not None:
            _INSTANCE.stop()


def run_in_background(name: str, *, triggered_by: str | None = None,
                      on_done: Callable[[core.Run | None, Exception | None], None]
                      | None = None) -> threading.Thread:
    """Run one job now on a worker thread ("Run now" in the GUI).

    ``on_done(run, error)`` is called on the worker thread — a GUI must
    hand it back to its own thread (e.g. via a queue polled with
    ``after``) before touching widgets.
    """
    def work() -> None:
        run: core.Run | None = None
        err: Exception | None = None
        try:
            run = core.run_job(name, trigger=core.TRIGGER_MANUAL,
                               triggered_by=triggered_by)
        except Exception as e:  # noqa: BLE001 - reported to the caller
            err = e
            logger.exception("Manual run of %s failed to start", name)
        if on_done is not None:
            try:
                on_done(run, err)
            except Exception:  # noqa: BLE001
                logger.exception("on_done callback failed")

    t = threading.Thread(target=work, name=f"sixth-form-job-{name}", daemon=True)
    t.start()
    return t
