"""CLI Language Selector — university-flavoured adapter over ``shared.i18n``.

This is NOT a deprecated re-export shim. It exposes a small, stable
university-CLI interface (``display_language_selector``,
``display_language_menu_option``, ``get_startup_language_choice``) that
wraps the cross-system ``education_system.shared.i18n`` selector and adds
behaviour the university CLI expects: the legacy ``force_show`` parameter,
a "language can be changed at startup" hint, and a startup-default helper.

40+ university CLI menus depend on this surface — keep the imports stable.
"""

from __future__ import annotations

from typing import Optional

from education_system.shared.i18n.selector_cli import show_language_selector_cli
from education_system.shared.i18n.core import get_current_language


def display_language_selector(force_show: bool = False) -> str:
    """Display the language selection menu.

    Delegates to the shared CLI language selector.

    Args:
        force_show: Kept for backward compatibility (ignored).

    Returns:
        The selected language code.
    """
    return show_language_selector_cli()


def display_language_menu_option() -> None:
    """Display a note that language can be changed at startup.

    Language selection is now handled at application startup via the
    shared i18n module, so this just prints an informational message.
    """
    print("\nLanguage can be changed at application startup.")
    print(f"Current language: {get_current_language()}\n")


def get_startup_language_choice() -> Optional[str]:
    """Return the current language from the shared i18n module.

    Language selection now happens at startup via the shared module,
    so this simply returns the currently active language code without
    prompting.

    Returns:
        The current language code.
    """
    return get_current_language()


__all__ = [
    "display_language_selector",
    "display_language_menu_option",
    "get_startup_language_choice",
]
