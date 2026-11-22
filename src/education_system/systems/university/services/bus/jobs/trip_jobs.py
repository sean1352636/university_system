"""The scheduled trip jobs, started from the university launch beside the
daily health jobs (same pattern as ``pastoral/infrastructure/health/
retention_worker``: one daemon thread per process, each job on its own
connection, a failing job logged and the rest still run).

Every hour:

* waiting-list offers past their 48 hours lapse and go to the next person
  (``trip_management.waitlist.expire_offers``);
* the T-7 / T-1 reminders with the itinerary pack
  (``trip_management.comms.send_reminders`` — each sent once);

once a day:

* the retention purge of participants' personal details six months after
  a trip (``trip_management.retention.purge_due``);
* sealing any plain-text medical / dietary / accessibility value still in
  ``trip_participants`` (``trip_management.medical.seal_existing``);
* attendance for completed trips that count towards a module
  (``trip_management.rollcall.record_attendance`` — idempotent).
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

HOUR = 3600
DAY = 86400
_WORKER: threading.Thread | None = None


def _tm(name):
    import importlib
    return importlib.import_module(
        "education_system.systems.university.domains.operations.domain.campus.mobility."
        f"services.trip_management.{name}")


def _attendance_for_completed() -> int:
    database, rollcall = _tm("database"), _tm("rollcall")
    with database.read_connection() as c:
        trip_ids = [r[0] for r in c.execute(
            "SELECT id FROM trips WHERE status = 'completed' AND COALESCE(counts_as_attendance, 0) = 1 "
            "AND COALESCE(module_code, '') <> ''").fetchall()]
    return sum(rollcall.record_attendance(trip_id) for trip_id in trip_ids)


HOURLY = (
    ("expire_offers", lambda: _tm("waitlist").expire_offers()),
    ("reminders", lambda: _tm("comms").send_reminders()),
)
DAILY = (
    ("retention", lambda: _tm("retention").purge_due()),
    ("seal_existing", lambda: _tm("medical").seal_existing()),
    ("attendance", _attendance_for_completed),
)


def _run(jobs) -> dict:
    out: dict = {}
    for name, job in jobs:
        try:
            out[name] = job()
        except Exception as exc:
            logger.exception("Trip job %s failed", name)
            out[name] = f"failed: {exc}"
    return out


def run_hourly() -> dict:
    return _run(HOURLY)


def run_daily() -> dict:
    return _run(DAILY)


def run_once() -> dict:
    """Every trip job now (the hourly ones, then the daily ones)."""
    return {**run_hourly(), **run_daily()}


def _loop() -> None:
    last_daily = 0.0
    while True:
        try:
            logger.info("Hourly trip jobs: %s", run_hourly())
            if time.time() - last_daily >= DAY:
                logger.info("Daily trip jobs: %s", run_daily())
                last_daily = time.time()
        except Exception:
            logger.exception("Trip jobs failed")
        time.sleep(HOUR)


def start_worker() -> bool:
    """Start the trip jobs once per process."""
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return False
    _WORKER = threading.Thread(target=_loop, daemon=True, name="trip-jobs")
    _WORKER.start()
    return True
