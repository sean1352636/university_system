"""GUI Language Selector - Thin shim delegating to shared i18n module.

This module re-exports the shared language selector so that existing
imports across 70+ files continue to work without modification.

Usage:
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector
    )

    selected_language = show_gui_language_selector()
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

# Delegate to the shared i18n selector
from education_system.shared.i18n.selector_gui import (
    LanguageSelectorDialog,
    show_language_selector,
)
from education_system.shared.i18n.core import (
    get_current_language,
    get_current_language_name,
    reload_translations,
)


def show_gui_language_selector(parent: Optional[tk.Tk] = None) -> str:
    """Show the GUI language selector dialog.

    Delegates to the shared i18n selector.

    Args:
        parent: Optional parent window.

    Returns:
        The selected language code.
    """
    return show_language_selector(parent)


def create_language_menu_button(parent: tk.Widget, auth=None) -> ttk.Button:
    """Create a language selection button for use in GUI menus.

    Opens the shared language selector dialog and reloads translations
    if the language was changed.

    Args:
        parent: Parent widget.
        auth: Unused, kept for backward compatibility.

    Returns:
        The created button widget.
    """
    def on_click():
        old_lang = get_current_language()
        show_language_selector(parent.winfo_toplevel())
        new_lang = get_current_language()
        if old_lang != new_lang:
            reload_translations()

    btn = ttk.Button(
        parent,
        text=f"Language [{get_current_language_name()}]",
        command=on_click,
    )
    return btn


__all__ = [
    "LanguageSelectorDialog",
    "show_gui_language_selector",
    "create_language_menu_button",
]
