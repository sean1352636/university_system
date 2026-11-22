"""The CLI menu registry: which terminal menu a menu key runs.

Each area lists its menus in ``modules/<module>/cli/__init__.py``::

    MENUS = {
        "behaviour": "behaviour_cli",             # runs behaviour_cli.menu(principal)
        "staff_portal": "my_day_cli:show",        # runs my_day_cli.show(principal)
    }

Entries are plain strings, so nothing is imported until a menu is chosen.
"""

from __future__ import annotations

import importlib
from functools import lru_cache
from typing import Any, Callable

from education_system.systems.secondary.ui.gui.navigation.pages import MODULES_PKG, module_names


@lru_cache(maxsize=1)
def registry() -> dict[str, tuple[str, str, str]]:
    """``{key: (area, module, function)}`` for every module. A key claimed twice
    is an error."""
    out: dict[str, tuple[str, str, str]] = {}
    for area in module_names():
        pkg = importlib.import_module(f"{MODULES_PKG}.{area}.cli")
        for key, target in getattr(pkg, "MENUS", {}).items():
            if key in out:
                raise ValueError(f"menu key {key!r} is in both {out[key][0]} and {area}")
            module, _sep, func = target.partition(":")
            out[key] = (area, module, func or "menu")
    return out


def find(key: str) -> Callable[[Any], Any] | None:
    """The function to run for *key* - called with the principal - or None
    when no area has that menu. Its module is imported now."""
    entry = registry().get(key)
    if entry is None:
        return None
    area, module, func = entry
    return getattr(importlib.import_module(f"{MODULES_PKG}.{area}.cli.{module}"), func)
