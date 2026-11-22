"""The GUI page registry: which screen a menu key opens.

Each feature module lists its pages in ``modules/<module>/gui/__init__.py``::

    PAGES = {
        "behaviour": Page("Behaviour & Rewards", "behaviour_views", "draw_behaviour",
                          state="_behaviour_state", links=("open_pupil",)),
    }

The main window looks a menu key up here and calls the draw function as
``draw(parent, principal=..., state=..., <link>=...)``:

* *state* names a dict the main window keeps, so a page's tab and filters
  survive a redraw (leave it out for a page that keeps none);
* *links* are the main-window callbacks the page needs, by keyword - see
  ``LINKS`` for the ones on offer (``open_pupil`` opens a pupil's profile).

Entries are plain strings, so reading the registry imports no screen: a
page's module is imported only when it is opened (startup stays fast).
This module must not import tkinter for the same reason.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Any, Callable

MODULES_PKG = "education_system.systems.secondary.modules"

#: The callbacks a page may ask the main window for (keyword -> what it does).
LINKS = {
    "open_pupil": "open a pupil's profile (pupil_id)",
    "on_status": "set the status bar text (str)",
    "open_application": "open one admissions application (application_id)",
    "open_year": "open one year group (year)",
    "open_form": "open one form group (form_id)",
    "open_group": "open one teaching group (group_id)",
    "open_message": "open one e-mail (message_id)",
}


@dataclass(frozen=True)
class Page:
    title: str                  # the heading the page is shown (and popped out) under
    module: str                 # the view module inside the module's gui/ package
    draw: str                   # its draw function: draw(parent, principal=..., ...)
    state: str | None = None    # main-window dict that keeps tabs/filters across redraws
    links: tuple[str, ...] = ()  # callbacks the page needs, from LINKS
    area: str = ""              # its feature module (modules/<area>/); filled in by the registry

    @property
    def module_path(self) -> str:
        return f"{MODULES_PKG}.{self.area}.gui.{self.module}"


def module_names() -> list[str]:
    modules = importlib.import_module(MODULES_PKG)
    return sorted(m.name for m in pkgutil.iter_modules(modules.__path__) if m.ispkg)


@lru_cache(maxsize=1)
def registry() -> dict[str, Page]:
    """Every area's pages by menu key. A key claimed twice is an error."""
    out: dict[str, Page] = {}
    for area in module_names():
        pkg = importlib.import_module(f"{MODULES_PKG}.{area}.gui")
        for key, page in getattr(pkg, "PAGES", {}).items():
            if key in out:
                raise ValueError(f"page key {key!r} is in both {out[key].area} and {area}")
            unknown = set(page.links) - set(LINKS)
            if unknown:
                raise ValueError(f"page {key!r} asks for unknown links {sorted(unknown)}")
            out[key] = replace(page, area=area)
    return out


def find(key: str) -> Page | None:
    return registry().get(key)


def load(page: Page) -> Callable[..., Any]:
    """The page's draw function (imports its module now)."""
    return getattr(importlib.import_module(page.module_path), page.draw)
