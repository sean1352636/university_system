"""The feature list every system's main menu presents, as data.

The GUI and CLI of each system render the same navigation structure, but each
system declares it in its own place and its own shape: a dict in
``nursery/menu.py``, a list of tuples in ``primary``/``secondary``/
``sixth_form``, a per-role mapping in ``fe_college`` and ``apprenticeships``.

This normalises all six onto ``{category: [feature, ...]}`` so tooling can ask
one question — "what can a user actually do in this system?" — without
knowing where each menu happens to live. Used to generate API routes for menu
features and to test that the API keeps pace with the menus.

University is deliberately absent: its surface is organised by domain rather
than by a single main menu, and it already has its own route tree.
"""

from __future__ import annotations

import importlib
import logging
import re
from typing import Callable

logger = logging.getLogger(__name__)

#: system key -> (module path, attribute, shape)
SOURCES: dict[str, tuple[str, str, str]] = {
    "nursery": ("education_system.systems.nursery.menu",
                "NAV_CATEGORIES", "sections"),
    "primary": ("education_system.systems.primary.gui_main",
                "NAV_CATEGORIES", "sections"),
    "secondary": ("education_system.systems.secondary.gui_main",
                  "NAV_CATEGORIES", "sections"),
    "sixth_form": ("education_system.systems.sixth_form.interfaces.gui.gui_main",
                   "NAV_CATEGORIES", "sections"),
    "fe_college": ("education_system.systems.fe_college.gui_main",
                   "NAVIGATION", "by_role"),
    "apprenticeships": ("education_system.systems.apprenticeships.interfaces.gui.gui_main",
                        "NAV_BY_ROLE", "by_role"),
}


def slugify(label: str) -> str:
    """'Daily Register' -> 'daily-register'. The URL segment for a feature."""
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def snake(label: str) -> str:
    """'Daily Register' -> 'daily_register'. The Python identifier."""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _label_of(item) -> str:
    """Menu items are either a bare label or (key, label) / (label, key)."""
    if isinstance(item, str):
        return item
    # Sections carry (key, label); by_role carries (key, label) too. The label
    # is the human-facing half, which is the longer, space-bearing one.
    parts = [p for p in item if isinstance(p, str)]
    if not parts:
        return str(item)
    return max(parts, key=lambda p: (" " in p, len(p)))


def _from_mapping(nav) -> dict[str, list[str]]:
    return {str(k): [_label_of(i) for i in v] for k, v in nav.items()}


def _from_sections(nav) -> dict[str, list[str]]:
    # Accept either a list of (category, items) or a mapping: two systems
    # spell the same structure differently and both are legitimate.
    pairs = nav.items() if hasattr(nav, "items") else nav
    return {str(cat): [_label_of(i) for i in items] for cat, items in pairs}


def _from_by_role(nav) -> dict[str, list[str]]:
    """Union every role's menu: the API serves all roles, not one."""
    merged: dict[str, set[str]] = {}
    for _role, sections in nav.items():
        for category, items in sections:
            merged.setdefault(str(category), set()).update(
                _label_of(i) for i in items)
    return {k: sorted(v) for k, v in merged.items()}


_SHAPES: dict[str, Callable] = {
    "mapping": _from_mapping,
    "sections": _from_sections,
    "by_role": _from_by_role,
}


def menu_for(system_key: str) -> dict[str, list[str]]:
    """``{category: [feature label, ...]}`` for one system."""
    module_path, attribute, shape = SOURCES[system_key]
    nav = getattr(importlib.import_module(module_path), attribute)
    return _SHAPES[shape](nav)


def all_menus() -> dict[str, dict[str, list[str]]]:
    """Every system's menu. A system that cannot be read is skipped, loudly."""
    out: dict[str, dict[str, list[str]]] = {}
    for key in SOURCES:
        try:
            out[key] = menu_for(key)
        except Exception:
            logger.error("Could not read the %s menu", key, exc_info=True)
    return out


def feature_count(menus: dict[str, dict[str, list[str]]] | None = None) -> int:
    menus = all_menus() if menus is None else menus
    return sum(len(items) for menu in menus.values() for items in menu.values())


__all__ = ["SOURCES", "all_menus", "feature_count", "menu_for", "slugify", "snake"]
