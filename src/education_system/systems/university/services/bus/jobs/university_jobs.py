"""The university's general scheduled jobs, started from the university
launch beside the support, trip and HR jobs (one daemon thread per process;
a failing job is logged and the rest still run).

Every fifteen minutes:

* safeguarding e-mails still "Queued" are sent again
  (``safeguarding.notifications.retry_queued_emails``);
* scheduled assignments open and deadline reminders go out
  (``assignments.assignment_rules.runner.run``);

every day:

* the degree-audit sweep for the current academic year's cohort
  (``degree_audit.run_degree_audit_sweep`` - the Graduation Forecast KPI);
* ungraded online exams (``ungraded_exams`` - the marker is reminded after
  7 days; after 14 the student's transcript is held until it is marked);
* unclaimed mailroom parcels past the free period (``overdue_mail``);
* cohort attendance risk per module (``attendance_risk``);
* record retention (``governance/infrastructure/data_lifecycle_store`` -
  each record type acts only once an administrator turns it on; until then
  it reports how many records are due);
* complaint deadline reminders to each handler (``application.complaints
  .procedure.run_reminders`` - stages due within two days or overdue);
* the safeguarding daily digest to the on-call DSL and the alerts for cases
  past their SLA.

A daily job runs once per calendar day however often the system is started
(``university_job_runs`` records the last run); the worker checks hourly.

The university event outbox has its own worker
(``application/outbox_dispatcher``).
"""

from __future__ import annotations

import importlib
import logging
import threading
import time
from datetime import date

logger = logging.getLogger(__name__)

INTERVAL = 900
_WORKER: threading.Thread | None = None
_LOCK = threading.Lock()
_UNI = "education_system.systems.university"


def _call(module: str, name: str, **kwargs):
    return getattr(importlib.import_module(f"{_UNI}.{module}"), name)(**kwargs)


def _cohort_year() -> int:
    """The start year of the current academic year (September to August)."""
    today = date.today()
    return today.year if today.month >= 9 else today.year - 1


FREQUENT = (
    ("assignment_schedule_and_reminders", lambda: _call(
        "domains.assessment.domain.assignments.assignment_rules.runner", "run")),
    ("safeguarding_email_retry", lambda: _call(
        "domains.safeguarding.application.services.notifications", "retry_queued_emails")),
)
DAILY = (
    ("degree_audit", lambda: _call("services.bus.jobs.degree_audit",
                                   "run_degree_audit_sweep", cohort_year=_cohort_year())),
    ("ungraded_exams", lambda: _call("services.bus.jobs.ungraded_exams",
                                     "sweep_ungraded_exams")),
    ("overdue_mail", lambda: _call("services.bus.jobs.overdue_mail", "sweep_overdue_mail")),
    ("attendance_risk", lambda: _call("services.bus.jobs.attendance_risk",
                                      "sweep_cohort_attendance_risk")),
    ("data_retention", lambda: _call(
        "domains.governance.infrastructure.data_lifecycle_store", "daily_job")),
    ("safeguarding_sla_alerts", lambda: _call(
        "domains.safeguarding.application.services.notifications", "stuck_case_alerts")),
    ("complaint_reminders", lambda: _call("application.complaints.procedure",
                                          "run_reminders")),
    ("safeguarding_digest", lambda: bool(_call(
        "domains.safeguarding.application.services.notifications", "daily_dsl_digest"))),
)


def _run(jobs) -> dict:
    out: dict = {}
    for name, job in jobs:
        try:
            out[name] = job()
        except Exception as exc:
            logger.exception("University job %s failed", name)
            out[name] = f"failed: {exc}"
    return out


def run_frequent() -> dict:
    return _run(FREQUENT)


def _ran_today(name: str) -> bool:
    """Claim today's run of a daily job; False when it already ran today
    (in this or an earlier launch), so a restart does not repeat it."""
    from education_system.systems.university.infrastructure.database.db import transaction

    today = date.today().isoformat()
    with transaction() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS university_job_runs ("
                     "job TEXT PRIMARY KEY, last_run_date TEXT NOT NULL)")
        row = conn.execute("SELECT last_run_date FROM university_job_runs WHERE job = ?",
                           (name,)).fetchone()
        if row and row[0] == today:
            return True
        conn.execute("INSERT INTO university_job_runs (job, last_run_date) VALUES (?, ?) "
                     "ON CONFLICT(job) DO UPDATE SET last_run_date = excluded.last_run_date",
                     (name, today))
    return False


def run_daily(*, force: bool = False) -> dict:
    """The daily jobs not yet run today (all of them with ``force``)."""
    return _run([(name, job) for name, job in DAILY if force or not _ran_today(name)])


def run_once() -> dict:
    """Every job now."""
    return {**run_frequent(), **run_daily(force=True)}


def _loop() -> None:
    last_daily = 0.0
    while True:
        try:
            logger.debug("University jobs: %s", run_frequent())
            if time.time() - last_daily >= 3600:
                ran = run_daily()
                if ran:
                    logger.info("Daily university jobs: %s", ran)
                last_daily = time.time()
        except Exception:
            logger.exception("University jobs failed")
        time.sleep(INTERVAL)


def start_worker() -> bool:
    """Start the jobs once per process; False if already running."""
    global _WORKER
    with _LOCK:
        if _WORKER and _WORKER.is_alive():
            return False
        _WORKER = threading.Thread(target=_loop, daemon=True, name="university-jobs")
        _WORKER.start()
        return True
