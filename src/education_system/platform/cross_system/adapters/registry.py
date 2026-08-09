"""Where the platform looks up "who handles the ``primary`` side?".

Each system registers its adapter once, at import of its own package.
The platform never imports a system module directly, so the dependency
only ever points inwards: systems know about the platform, the platform
knows about the abstract contract.

Lookups are forgiving by design. :func:`get` returns ``None`` for an
unregistered system, because plenty of legitimate destinations have no
adapter at all — an apprenticeship provider, an employer, home
education, or a school outside the platform. The workflow in
``transitions`` still records those moves; there is simply nobody to call
to create a local record.
"""

from __future__ import annotations

import logging
import threading

from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    PhaseAdapter,
)

logger = logging.getLogger(__name__)

_adapters: dict[str, PhaseAdapter] = {}
_lock = threading.RLock()


def register(adapter: PhaseAdapter, *, replace: bool = False) -> PhaseAdapter:
    """Register one system's adapter. Returns it, so a module can do
    ``ADAPTER = registry.register(PrimaryAdapter())``.

    Re-registering the same system raises unless ``replace=True``, which
    keeps a stray second import from silently swapping the live adapter
    for a half-configured one.
    """
    if not isinstance(adapter, PhaseAdapter):
        raise AdapterError(
            f"{adapter!r} is not a PhaseAdapter")
    key = adapter.system
    if not key:
        raise AdapterError(f"{type(adapter).__name__} has no system key")
    with _lock:
        existing = _adapters.get(key)
        if existing is not None and not replace:
            if type(existing) is type(adapter):
                # Same class re-registering (module reimported under a
                # different name) is a no-op, not a conflict.
                return existing
            raise AdapterError(
                f"System {key!r} already has adapter "
                f"{type(existing).__name__}; pass replace=True to override")
        _adapters[key] = adapter
    logger.info("Registered %s adapter for %r (%s)", type(adapter).__name__,
                key, ", ".join(sorted(k for k, v in
                                      adapter.capabilities().items() if v))
                or "no capabilities yet")
    return adapter


def get(system: str) -> PhaseAdapter | None:
    """The adapter for ``system``, or ``None`` if nothing is registered.

    ``None`` is an expected answer, not an error — see the module
    docstring.
    """
    with _lock:
        return _adapters.get(system)


def require(system: str) -> PhaseAdapter:
    """The adapter for ``system``, raising if absent.

    Use where the caller genuinely cannot proceed without one — creating
    a local learner record, for instance.
    """
    adapter = get(system)
    if adapter is None:
        raise AdapterError(
            f"No adapter registered for system {system!r}; registered: "
            f"{', '.join(sorted(_adapters)) or '(none)'}")
    return adapter


def registered_systems() -> list[str]:
    with _lock:
        return sorted(_adapters)


def capability_matrix() -> dict[str, dict[str, bool]]:
    """Every registered adapter's capabilities, for the transition
    dashboard and for diagnosing a boundary that will not work yet."""
    with _lock:
        return {k: a.capabilities() for k, a in sorted(_adapters.items())}


def unregister(system: str) -> None:
    """Drop one adapter. Mainly for tests."""
    with _lock:
        _adapters.pop(system, None)


def clear_for_test() -> None:
    """Test-only: empty the registry between cases."""
    with _lock:
        _adapters.clear()


__all__ = [
    "register",
    "get",
    "require",
    "registered_systems",
    "capability_matrix",
    "unregister",
    "clear_for_test",
]
