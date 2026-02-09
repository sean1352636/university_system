"""Settings dialog wrappers for the enhanced reporting GUI.

This module provides a functional interface to the settings-related
dialogs defined on the GUI class.  It also re-exports standalone
functions from the core module for directory and theme settings as
well as email validation.
"""

from __future__ import annotations

from typing import Any

from ..core import ReportingSystemGUI
from ..core import show_directory_settings as standalone_show_directory_settings
from ..core import show_theme_settings as standalone_show_theme_settings
from ..core import validate_email_settings


def show_backup_restore_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_backup_restore_dialog()


def show_user_management_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_user_management_dialog()


def show_directory_settings(gui: ReportingSystemGUI) -> None:
    """Invoke the standalone directory settings dialog.

    For convenience, this wrapper will first try to call the method on
    the GUI instance if available; otherwise it will fall back to the
    standalone function defined in the core module.
    """
    if hasattr(gui, "show_directory_settings"):
        # type: ignore[attr-defined]
        gui.show_directory_settings()  # type: ignore[misc]
    else:
        standalone_show_directory_settings(gui)


def show_theme_settings(gui: ReportingSystemGUI) -> None:
    if hasattr(gui, "show_theme_settings"):
        gui.show_theme_settings()  # type: ignore[misc]
    else:
        standalone_show_theme_settings(gui)


def show_settings(gui: ReportingSystemGUI) -> None:
    gui.show_settings()


def show_advanced_settings(gui: ReportingSystemGUI) -> None:
    gui.show_advanced_settings()


def show_email_settings_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_email_settings_dialog()


def show_system_config_editor(gui: ReportingSystemGUI) -> None:
    gui.show_system_config_editor()


__all__ = [
    "show_backup_restore_dialog",
    "show_user_management_dialog",
    "show_directory_settings",
    "show_theme_settings",
    "show_settings",
    "show_advanced_settings",
    "show_email_settings_dialog",
    "show_system_config_editor",
    "validate_email_settings",
]