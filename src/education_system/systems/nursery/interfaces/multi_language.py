"""Multi-Language — System (Nursery System).

The nursery uses the platform's shared translation service
(``platform.features.i18n``): one language list, one saved preference and one
selector dialog for every system. This module is the nursery's entry point to
it, used by the GUI and the CLI.
"""

from __future__ import annotations

from typing import Any

from education_system.platform.features.i18n import core as i18n

FEATURE_NAME = "Multi-Language"


def current_language() -> tuple[str, str]:
    """``(code, native name)`` of the language in use."""
    return i18n.get_current_language(), i18n.get_current_language_name()


def available_languages() -> list[tuple[str, str]]:
    """Every supported language as ``(code, name)``."""
    return i18n.get_available_language_list()


def set_language(code: str, *, save: bool = True) -> bool:
    """Switch language (and save it as the preference); False if unknown."""
    return i18n.set_language(code, save=save)


def open_selector(parent: Any = None) -> str:
    """Show the shared language selector dialog; returns the chosen code."""
    from education_system.platform.features.i18n.selector_gui import show_language_selector
    return show_language_selector(parent)


def open_selector_cli() -> str:
    """Show the shared terminal language selector; returns the chosen code."""
    from education_system.platform.features.i18n.selector_cli import (
        show_language_selector_cli,
    )
    return show_language_selector_cli()


__all__ = ["FEATURE_NAME", "available_languages", "current_language",
           "open_selector", "open_selector_cli", "set_language"]
