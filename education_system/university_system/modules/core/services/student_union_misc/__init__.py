"""Backwards-compatible shim package.

The student union services were migrated from
``modules.core.services.student_union_misc`` to
``modules.domain.student_affairs.student_union.services``.

This package re-exports every submodule from the new location so that
existing imports and ``unittest.mock.patch`` targets that reference the
old path continue to work.
"""

from __future__ import annotations

import importlib
import sys

_REAL_PKG = "education_system.university_system.modules.domain.student_affairs.student_union.services"
_THIS_PKG = __name__  # education_system.university_system.modules.core.services.student_union_misc

# Submodules that tests (and possibly production code) reference via the old path.
_SUBMODULES = [
    "analytics",
    "communications",
    "competitions",
    "context",
    "context_setup",
    "events",
    "facilities",
    "menu",
    "points",
    "support",
    "sustainability",
    "union_context",
    "union_db_schema",
    "volunteering",
    "voting",
]


def _ensure_submodule(name: str):
    """Import the real submodule and alias it under the old package path."""
    real_fqn = f"{_REAL_PKG}.{name}"
    shim_fqn = f"{_THIS_PKG}.{name}"

    # Import the real module if not yet loaded.
    mod = importlib.import_module(real_fqn)

    # Register it under the old fully-qualified name so that
    # ``from ... import`` and ``patch('...')`` both resolve.
    sys.modules[shim_fqn] = mod
    return mod


# Eagerly register every known submodule so that ``patch()`` can resolve
# dotted paths like ``student_union_misc.context.auth``.
for _name in _SUBMODULES:
    try:
        _mod = _ensure_submodule(_name)
        # Also expose as a package attribute for ``getattr`` access.
        globals()[_name] = _mod
    except ImportError:
        # If a submodule legitimately doesn't exist yet, skip silently.
        pass


def __getattr__(name: str):
    """Lazy fallback for any submodule not in the explicit list."""
    try:
        return _ensure_submodule(name)
    except ImportError:
        raise AttributeError(
            f"module {_THIS_PKG!r} has no attribute {name!r}"
        ) from None
