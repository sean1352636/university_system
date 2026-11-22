"""The page and menu registries (modules/<module>/gui|cli/__init__.py) point at
real screens, and every key in them is a sidebar entry."""

from __future__ import annotations

import importlib
import inspect

import pytest

from education_system.systems.secondary.app import gui_main
from education_system.systems.secondary.app import routing as menu
from education_system.systems.secondary.ui.cli.menus import menus
from education_system.systems.secondary.ui.gui.navigation import pages

MENU_KEYS = {key for _label, key in menu.all_entries()}
PAGES = pages.registry()
MENUS = menus.registry()


@pytest.mark.parametrize("key", sorted(PAGES))
def test_page_draw_function_takes_what_the_window_passes(key: str) -> None:
    page = PAGES[key]
    assert key in MENU_KEYS, f"{key} is not a sidebar entry"
    params = inspect.signature(pages.load(page)).parameters
    wanted = {"principal", *page.links} | ({"state"} if page.state else set())
    missing = wanted - set(params)
    assert not missing, f"{page.module}.{page.draw} has no {sorted(missing)} parameter"


@pytest.mark.parametrize("key", sorted(MENUS))
def test_cli_menu_exists(key: str) -> None:
    assert key in MENU_KEYS, f"{key} is not a sidebar entry"
    area, module, func = MENUS[key]
    mod = importlib.import_module(f"{pages.MODULES_PKG}.{area}.cli.{module}")
    assert callable(getattr(mod, func, None)), f"{module}.{func} is missing"


def test_window_methods_and_pages_do_not_overlap() -> None:
    methods = {name[5:] for name in vars(gui_main.SecondaryMainGUI) if name.startswith("open_")}
    both = methods & set(PAGES)
    assert not both, f"keys with both an open_ method and a page: {sorted(both)}"


def test_every_built_menu_entry_has_a_gui_page() -> None:
    methods = {name[5:] for name in vars(gui_main.SecondaryMainGUI) if name.startswith("open_")}
    no_gui = set(MENUS) - set(PAGES) - methods
    assert not no_gui, f"CLI menus with no GUI page: {sorted(no_gui)}"


def test_page_states_are_not_shared() -> None:
    states = [p.state for p in PAGES.values() if p.state]
    assert len(states) == len(set(states))
