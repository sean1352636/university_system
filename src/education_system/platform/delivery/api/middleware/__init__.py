"""Request middleware, and the order it must be applied in.

Order is behaviour here, not taste. Each entry below depends on the ones
above it having already run:

1. ``request_context``  assigns ``g.request_id`` and starts the timer.
   Everything downstream logs against that id, so it goes first.
2. ``tenant``           resolves the tenant and binds it to ``g``. Must
   precede anything that reads tenant-scoped data, and must follow (1)
   so a rejection is still traceable.
3. ``rate_limit``       needs the caller identified — per-username limits
   read the token — but must run before expensive work.
4. ``caching``          may short-circuit with a cached response, so it
   comes after the checks that decide whether the caller is allowed one.
5. ``csrf``             validates unsafe methods last, once the request
   is otherwise understood.

:func:`apply_all` is the single place that order is expressed. Registering
these individually in the app factory is how the ordering drifts.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: (module attribute, callable name) in apply order.
APPLY_ORDER: tuple[tuple[str, str], ...] = (
    ("request_context", "register_middleware"),
    ("tenant", "register_tenant_middleware"),
    ("rate_limit", "register_rate_limiting"),
    ("caching", "register_caching"),
    ("csrf", "register_csrf"),
)


def apply_all(app, **options) -> list[str]:
    """Apply every middleware to *app*, in order. Returns what was applied.

    A middleware whose registration function is absent is skipped rather
    than fatal — the modules were assembled from several codebases and
    not all expose the same entry point yet. The skip is logged, never
    silent, so a missing one shows up at startup instead of as absent
    behaviour in production.
    """
    import importlib

    applied: list[str] = []
    for module_name, func_name in APPLY_ORDER:
        try:
            module = importlib.import_module(
                f"education_system.platform.delivery.api.middleware.{module_name}")
        except Exception as exc:
            logger.error("Middleware %s failed to import: %s", module_name, exc)
            continue
        func = getattr(module, func_name, None)
        if func is None:
            logger.warning("Middleware %s has no %s(); skipped",
                           module_name, func_name)
            continue
        try:
            func(app, **options.get(module_name, {}))
            applied.append(module_name)
        except Exception as exc:
            logger.error("Middleware %s failed to apply: %s", module_name, exc)
    logger.info("Middleware applied: %s", ", ".join(applied) or "none")
    return applied


__all__ = ["APPLY_ORDER", "apply_all"]


# ── Backwards compatibility ──────────────────────────────────────────
# ``middleware.py`` became this package, and a package shadows a module
# of the same name — so a compat shim next to it could never be imported.
# Callers still do ``from ...api.middleware import register_middleware``,
# so the old module's names are re-exported here.

from education_system.platform.delivery.api.middleware.request_context import (  # noqa: E402,F401
    __dict__ as _request_context_ns,
)

globals().update({k: v for k, v in _request_context_ns.items()
                  if not k.startswith("__") and k not in globals()})
