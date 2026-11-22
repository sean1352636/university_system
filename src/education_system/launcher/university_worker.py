"""Headless university background worker, for server deployments.

The desktop launcher starts the university's background jobs when someone
opens the university (``systems._init_university``). On a server nobody
does, so this process runs them on their own:

    python -m education_system.launcher.university_worker

It bootstraps the university exactly as a launch does (database, migrations,
shared auth) - which starts every worker: the event outbox and lifecycle
actions, the e-mail outbox and timed e-mails, the batch scheduler, the
integrity, health, trip, support, HR and results-day jobs, the general
daily jobs and the cross-system drainer - then waits until it is stopped
(SIGTERM / SIGINT).
"""

from __future__ import annotations

import logging
import signal
import threading


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    from education_system.launcher.systems import _init_university

    _init_university()
    logging.getLogger(__name__).info("University worker running")
    stop.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
