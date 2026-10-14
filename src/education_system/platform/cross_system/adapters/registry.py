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

import importlib
import logging
import threading

from education_system.platform.cross_system.adapters.base import (
    AdapterError,
    PhaseAdapter,
)

logger = logging.getLogger(__name__)

_adapters: dict[str, PhaseAdapter] = {}
_lock = threading.RLock()

# system -> dotted module path exposing ``register()``. Declaring costs a
# dict entry; the module is imported only when an adapter is first needed.
_declared: dict[str, str] = {}
_bootstrapped = False

#: The module that owns the table of adapter paths. The registry imports it
#: by name, and only as a fallback: a process that never ran the launcher
#: (the API server, a script, a test) still has to reach a destination
#: system's adapter, and a sixth-form route that cannot find the FE
#: adapter because FE was not the system launched is a route that works
#: only on some machines.
_DECLARATIONS_MODULE = "education_system.launcher.systems"


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


def declare(system: str, module_path: str) -> None:
    """Record where ``system``'s adapter lives, without importing it.

    The module must expose ``register()`` (or an ``ADAPTER`` instance).
    Only the launched system's adapter is registered at start-up, but an
    orchestrator running in that process routinely needs the *other*
    end of a boundary — secondary's post-16 board needs the sixth form's
    adapter — so :func:`require` loads a declared one on first use.
    """
    with _lock:
        _declared[system] = module_path


def declared_systems() -> dict[str, str]:
    """Every declared ``system -> module path``, registered or not."""
    _bootstrap_declarations()
    with _lock:
        return dict(_declared)


def _bootstrap_declarations() -> None:
    """Pull in the launcher's declarations once, if nobody has yet."""
    global _bootstrapped
    with _lock:
        if _bootstrapped:
            return
        _bootstrapped = True
    try:
        module = importlib.import_module(_DECLARATIONS_MODULE)
        declare_all = getattr(module, "declare_phase_adapters", None)
        if callable(declare_all):
            declare_all()
    except Exception:
        logger.debug("Adapter declarations from %s unavailable",
                     _DECLARATIONS_MODULE, exc_info=True)


def load(system: str) -> PhaseAdapter | None:
    """The adapter for ``system``, importing its declared module if it
    has not registered yet. ``None`` when nothing is declared for it."""
    adapter = get(system)
    if adapter is not None:
        return adapter
    with _lock:
        module_path = _declared.get(system)
    if module_path is None:
        _bootstrap_declarations()
        with _lock:
            module_path = _declared.get(system)
    if module_path is None:
        return None
    try:
        module = importlib.import_module(module_path)
    except Exception as exc:
        raise AdapterError(
            f"The {system!r} adapter module {module_path} could not be "
            f"imported: {exc}") from exc
    hook = getattr(module, "register", None)
    if callable(hook):
        hook()
    else:
        instance = getattr(module, "ADAPTER", None)
        if isinstance(instance, PhaseAdapter):
            register(instance)
    return get(system)


def require(system: str) -> PhaseAdapter:
    """The adapter for ``system``, raising if absent.

    Use where the caller genuinely cannot proceed without one — creating
    a local learner record, for instance. A declared-but-unregistered
    adapter is loaded on demand.
    """
    adapter = load(system)
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
    "declare",
    "declared_systems",
    "get",
    "load",
    "require",
    "registered_systems",
    "capability_matrix",
    "unregister",
    "clear_for_test",
]
