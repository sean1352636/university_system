"""Shared imports and module state for the split implementation."""

import tkinter as tk

from tkinter import ttk, messagebox, filedialog

import logging

import json

from pathlib import Path

from education_system.systems.university.interfaces.gui.shell.main._tk_callback_filter import install_clean_close as _install_clean_close

from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import _lazy_import

from education_system.systems.university.infrastructure.i18n import get_text as _t, get_current_language_name, init_i18n

from education_system.systems.university.interfaces.gui.shell.main.imports.gui_imports import (
    ADVANCED_SEARCH_GUI_AVAILABLE,
    VIRTUAL_CLASSROOM_AVAILABLE,
)

logger = logging.getLogger(__name__)

_PIN_FILE = Path.home() / ".config" / "edu_system" / "university_pinned.json"

__all__ = [name for name in globals() if not name.startswith("__") and name != "__all__"]
