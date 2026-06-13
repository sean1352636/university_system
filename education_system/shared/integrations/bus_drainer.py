"""Turn the durable bus into a real-time backbone.

The bus is durable but inert until something polls it. This module
provides three ways to poll:

* :func:`drain_once` — register a system's consumers and dispatch any
  pending events once (used by the launcher at startup, and by cron).
* :class:`BackgroundDrainer` — a daemon thread that calls
  :func:`drain_once` on an interval so events propagate continuously
  while a system is running. Its thread name is in the conftest
  daemon-thread suppression set, so it never runs during tests.
* ``python -m education_system.shared.integrations.bus_drainer`` — a CLI
  entrypoint for cron / systemd: ``--system college --interval 30`` to run
  forever, or ``--once`` for a single pass.

So events such as ``safeguarding.flag.raised``, ``gdpr.redaction.requested``
and ``parent.linkage.changed`` deliver between live systems instead of
waiting for the next launch.
"""

from __future__ import annotations

import argparse
import logging
import threading

from education_system.shared.integrations import cross_system_bus
from education_system.shared.integrations.bus_consumers import register_consumers

logger = logging.getLogger(__name__)

# Matched by the conftest daemon-thread suppression set so tests never spin it.
DRAINER_THREAD_NAME = "CrossSystemBusDrainer"

_DEFAULT_INTERVAL = 30.0


def drain_once(system: str, *, db_path: str | None = None) -> int:
    """Register ``system``'s consumers and dispatch any pending events once.

    Returns the number of (event, handler) dispatches. Safe to call
    repeatedly and concurrently with other systems' drainers.
    """
    register_consumers(system)
    return cross_system_bus.poll_and_dispatch(system, db_path=db_path)


class BackgroundDrainer(threading.Thread):
    """Daemon thread that drains a system's bus events on an interval."""

    def __init__(self, system: str, *, interval: float = _DEFAULT_INTERVAL,
                 db_path: str | None = None) -> None:
        super().__init__(name=DRAINER_THREAD_NAME, daemon=True)
        self.system = system
        self.interval = interval
        self._db_path = db_path
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # pragma: no cover - exercised only at runtime
        logger.info("Bus drainer started for %s (every %ss)",
                    self.system, self.interval)
        while not self._stop.is_set():
            try:
                n = drain_once(self.system, db_path=self._db_path)
                if n:
                    logger.info("Bus drainer dispatched %d event(s) for %s",
                                n, self.system)
            except Exception:
                logger.exception("Bus drainer pass failed for %s", self.system)
            self._stop.wait(self.interval)
        logger.info("Bus drainer stopped for %s", self.system)


# One drainer per system per process; start_background_drainer is idempotent.
_drainers: dict[str, BackgroundDrainer] = {}


def start_background_drainer(system: str, *, interval: float = _DEFAULT_INTERVAL,
                             db_path: str | None = None) -> BackgroundDrainer | None:
    """Start (once) a background drainer for ``system``. Returns the thread.

    During tests ``Thread.start`` is monkey-patched to skip threads named
    ``CrossSystemBusDrainer``, so this is a no-op there.
    """
    existing = _drainers.get(system)
    if existing is not None and existing.is_alive():
        return existing
    drainer = BackgroundDrainer(system, interval=interval, db_path=db_path)
    _drainers[system] = drainer
    try:
        drainer.start()
    except Exception:
        logger.exception("Could not start bus drainer for %s", system)
        return None
    return drainer


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Drain the cross-system event bus for a system.")
    parser.add_argument("--system", required=True,
                        help="System key (nursery/primary/school/college/university)")
    parser.add_argument("--interval", type=float, default=_DEFAULT_INTERVAL,
                        help="Seconds between passes when running continuously")
    parser.add_argument("--once", action="store_true",
                        help="Drain a single batch and exit (for cron)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    if args.once:
        n = drain_once(args.system)
        print(f"Dispatched {n} event(s) for {args.system}")
        return 0

    drainer = BackgroundDrainer(args.system, interval=args.interval)
    try:
        drainer.run()  # run in the foreground for cron/systemd
    except KeyboardInterrupt:
        drainer.stop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())


__all__ = [
    "drain_once",
    "BackgroundDrainer",
    "start_background_drainer",
    "DRAINER_THREAD_NAME",
]
