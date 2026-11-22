"""The scheduled Staff HR jobs, started from the university launch beside the
support jobs (one daemon thread per process; a failing job is logged and the
rest still run).

Every day:

* the HR reminders (``staff_hr.reminders.run`` — contracts ending in 90 / 30
  days, probation reviews, overdue onboarding tasks, right-to-work
  follow-ups, DBS re-checks, expiring staff documents; each reminder once,
  by e-mail and in-app, to the person, their line manager and HR);
* the certification expiry sweep (``certification_expiry`` — the existing
  job, not duplicated);
* the jobs in :data:`JOBS`, named by dotted path so a module that is not
  there yet is logged rather than stopping the others.
"""

from __future__ import annotations

import importlib
import logging
import threading
import time

logger = logging.getLogger(__name__)

INTERVAL = 3600
DAY = 86400
_WORKER: threading.Thread | None = None
_LOCK = threading.Lock()

_STAFF_HR = "education_system.systems.university.domains.staff.domain.staff_hr"

#: Daily jobs by dotted name: ``(name, "package.module.function")`` — the leave
#: year jobs (entitlement allocation, carry-over expiry), sickness triggers,
#: family-leave and flexible-working deadlines, the annual pay
#: increment (acts once per increment date) and the HR retention policies.
JOBS = (
    ("leave_absence", f"{_STAFF_HR}.entitlement.run_daily"),
    ("sickness_absence", f"{_STAFF_HR}.absence.run_daily"),
    ("family_leave", f"{_STAFF_HR}.family_leave.run_daily"),
    ("flexible_working", f"{_STAFF_HR}.flexible_working.run_daily"),
    ("pay_increments", f"{_STAFF_HR}.pay_structure.increment_job"),
    ("retention", f"{_STAFF_HR}.retention.daily_job"),
)


def _dotted(path: str):
    module, _, attr = path.partition(":") if ":" in path else path.rpartition(".")
    try:
        fn = getattr(importlib.import_module(module), attr)
    except (ImportError, AttributeError) as exc:
        logger.info("Staff HR job %s not available yet (%s)", path, exc)
        return "not available"
    return fn()


def _reminders():
    from education_system.systems.university.domains.staff.domain.staff_hr import reminders
    return reminders.run()


def _certifications():
    from education_system.systems.university.services.bus.jobs.certification_expiry import (
        sweep_expiring_certifications,
    )
    return sweep_expiring_certifications()


DAILY = (
    ("reminders", _reminders),
    ("certifications", _certifications),
) + tuple((name, (lambda p=path: _dotted(p))) for name, path in JOBS)


def _run(jobs) -> dict:
    out: dict = {}
    for name, job in jobs:
        try:
            out[name] = job()
        except Exception as exc:
            logger.exception("Staff HR job %s failed", name)
            out[name] = f"failed: {exc}"
    return out


def run_daily() -> dict:
    return _run(DAILY)


def run_once() -> dict:
    """Every Staff HR job now."""
    return run_daily()


def _loop() -> None:
    last_daily = 0.0
    while True:
        try:
            if time.time() - last_daily >= DAY:
                logger.debug("Daily Staff HR jobs: %s", run_daily())
                last_daily = time.time()
        except Exception:
            logger.exception("Staff HR jobs failed")
        time.sleep(INTERVAL)


def start_worker() -> bool:
    """Start the Staff HR jobs once per process; False if already running."""
    global _WORKER
    with _LOCK:
        if _WORKER and _WORKER.is_alive():
            return False
        _WORKER = threading.Thread(target=_loop, daemon=True, name="staff-hr-jobs")
        _WORKER.start()
        return True
