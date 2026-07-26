"""Root conftest.py — applies to ALL test paths across every subsystem.

Optimisations here run once per session before any test module is imported.
"""

import logging
import os
import threading


def pytest_configure(config):
    """Global optimisations that must run before test collection."""
    # The auth test suite calls seed_default_users() directly and expects the
    # well-known demo accounts to exist. Seeding is now gated behind
    # EDU_DEV_SEED (a fresh production DB no longer auto-provisions weak
    # defaults), so opt the whole test run into dev seeding unless the
    # environment already sets it explicitly.
    os.environ.setdefault("EDU_DEV_SEED", "true")
    _suppress_daemon_threads()
    _quiet_noisy_loggers()


# ── Import-time log noise suppression ───────────────────────────────────────
#
# A few modules emit WARNING-level log records when optional dependencies are
# absent (e.g. the file-upload validator logs "pyclamd not installed" when
# ClamAV virus scanning isn't available). These are expected in the test/dev
# environment and only add noise, so we raise their level to ERROR.

_QUIET_LOGGERS = (
    "education_system.systems.university.infrastructure.security.file_upload_validator",
)


def _quiet_noisy_loggers():
    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(logging.ERROR)


# ── Background-thread suppression ───────────────────────────────────────────
#
# Several modules start long-running daemon threads at import time or on
# first instantiation (MaintenanceScheduler, DatabaseMaintenanceTimer,
# LogProcessor, email workers, backup schedulers).  These threads sleep
# for 60+ seconds and cause CI timeouts / slow teardown.
#
# We monkey-patch threading.Thread.start and threading.Timer.start so
# that threads whose names match a known set of daemon-thread names are
# silently skipped.  This runs before ANY module is imported, so it
# catches singletons created at import time.

_SUPPRESSED_THREAD_NAMES = frozenset({
    "MaintenanceScheduler",
    "DatabaseMaintenanceTimer",
    "LogProcessor",
    "BackupScheduler",
    "RetentionScheduler",
    "EmailScheduler",
    "EmailWorker",
    "CrossSystemBusDrainer",
})

_real_thread_start = threading.Thread.start


def _guarded_thread_start(self):
    if getattr(self, 'name', '') in _SUPPRESSED_THREAD_NAMES:
        return  # silently skip
    return _real_thread_start(self)


def _suppress_daemon_threads():
    """Prevent known daemon threads from starting during tests."""
    threading.Thread.start = _guarded_thread_start
