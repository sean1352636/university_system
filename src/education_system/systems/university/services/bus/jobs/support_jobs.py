"""The scheduled Student Support / Helpdesk jobs, started from the university
launch beside the trip and health jobs (one daemon thread per process; a
failing job is logged and the rest still run).

Every five minutes:

* the active escalation rules (``student_support.automation.escalations`` —
  each rule acts on a ticket once);
* the SLA warnings and breaches (``escalations._process_sla_breaches`` —
  each alert once per ticket; e-mails go through the outbox after commit),
  after bringing every SLA pause for waiting on the student into line;
* the support mailbox (``student_support.email_in.poll`` — only when e-mail
  into tickets is turned on);

every hour:

* the support metrics snapshot (active tickets, hours to first response,
  satisfaction) into ``system_metrics``;
* closing resolved tickets nobody replied to (``student_support.lifecycle``,
  after the ``auto_close_days`` setting);

every day:

* the retention purge (``student_support.gdpr.run_retention_job`` — closed
  tickets past their tier's retention period lose their personal data and
  attachment files; upload folders of erased tickets are removed), and
  discarding support e-mails left in quarantine past
  ``email_in.QUARANTINE_DAYS``.

The first pass in a process makes sure the support tables are in their
current shape (``student_support.schema.apply``), so the jobs never run
against a database the support screens have not opened yet.
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)

INTERVAL = 300
HOUR = 3600
DAY = 86400
_WORKER: threading.Thread | None = None
_LOCK = threading.Lock()


def _ss(name):
    import importlib
    return importlib.import_module(
        "education_system.systems.university.domains.student_support.domain."
        f"student_support.{name}")


_SCHEMA_READY = False


def _ensure_schema() -> bool:
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        store = _ss("store")
        with store.writing() as conn:
            _ss("schema").apply(conn.execute)
        _SCHEMA_READY = True
    return True


FREQUENT = (
    ("schema", _ensure_schema),
    ("escalations", lambda: _ss("automation.escalations")._process_escalations()),
    ("sla", lambda: _ss("automation.escalations")._process_sla_breaches()),
    ("email_in", lambda: _ss("email_in").poll()),
)
HOURLY = (
    ("metrics", lambda: _ss("utils.metrics")._update_metrics()),
    ("auto_close", lambda: _ss("lifecycle").close_stale_resolved()),
)
DAILY = (
    ("retention", lambda: _ss("gdpr").run_retention_job()),
    ("inbound_quarantine", lambda: _ss("email_in").purge_old()),
)


def _run(jobs) -> dict:
    out: dict = {}
    for name, job in jobs:
        try:
            out[name] = job()
        except Exception as exc:
            logger.exception("Support job %s failed", name)
            out[name] = f"failed: {exc}"
    return out


def run_frequent() -> dict:
    return _run(FREQUENT)


def run_hourly() -> dict:
    return _run(HOURLY)


def run_daily() -> dict:
    return _run(DAILY)


def run_once() -> dict:
    """Every support job now."""
    return {**run_frequent(), **run_hourly(), **run_daily()}


def _loop() -> None:
    last_hourly = last_daily = 0.0
    while True:
        try:
            logger.debug("Support jobs: %s", run_frequent())
            if time.time() - last_hourly >= HOUR:
                logger.debug("Hourly support jobs: %s", run_hourly())
                last_hourly = time.time()
            if time.time() - last_daily >= DAY:
                logger.debug("Daily support jobs: %s", run_daily())
                last_daily = time.time()
        except Exception:
            logger.exception("Support jobs failed")
        time.sleep(INTERVAL)


def start_worker() -> bool:
    """Start the support jobs once per process; False if already running."""
    global _WORKER
    with _LOCK:
        if _WORKER and _WORKER.is_alive():
            return False
        _WORKER = threading.Thread(target=_loop, daemon=True, name="support-jobs")
        _WORKER.start()
        return True
