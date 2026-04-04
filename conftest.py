"""Root conftest.py — applies to ALL test paths across every subsystem.

Optimisations here run once per session before any test module is imported.
"""

import threading


def pytest_configure(config):
    """Global optimisations that must run before test collection."""
    _suppress_daemon_threads()


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
})

_real_thread_start = threading.Thread.start


def _guarded_thread_start(self):
    if getattr(self, 'name', '') in _SUPPRESSED_THREAD_NAMES:
        return  # silently skip
    return _real_thread_start(self)


def _suppress_daemon_threads():
    """Prevent known daemon threads from starting during tests."""
    threading.Thread.start = _guarded_thread_start
