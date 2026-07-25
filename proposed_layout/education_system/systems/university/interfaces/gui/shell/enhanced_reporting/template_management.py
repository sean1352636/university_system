"""Template management wrappers for the enhanced reporting GUI.

This module provides functional wrappers around the template-related
methods defined on :class:`~modules.shared.gui.enhanced_reporting.core.ReportingSystemGUI`.
Each function accepts an instance of the main GUI class and delegates
to the underlying method.  These functions simplify programmatic
access to the template management features without needing to subclass
the GUI.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import ReportingSystemGUI  # type: ignore

def load_templates(gui: ReportingSystemGUI) -> None:
    gui.load_templates()


def _update_template_listbox(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._update_template_listbox(*args, **kwargs)


def _update_template_combos(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._update_template_combos(*args, **kwargs)


def refresh_templates(gui: ReportingSystemGUI) -> None:
    gui.refresh_templates()


def import_template_dialog(gui: ReportingSystemGUI) -> None:
    gui.import_template_dialog()


def on_template_select(gui: ReportingSystemGUI, *args, **kwargs) -> None:
    gui.on_template_select(*args, **kwargs)


def display_template_details(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.display_template_details(*args, **kwargs)


def create_template_dialog(gui: ReportingSystemGUI) -> None:
    gui.create_template_dialog()


def edit_template_dialog(gui: ReportingSystemGUI) -> None:
    gui.edit_template_dialog()


def delete_template(gui: ReportingSystemGUI) -> None:
    gui.delete_template()


def export_template(gui: ReportingSystemGUI) -> None:
    gui.export_template()


def duplicate_template(gui: ReportingSystemGUI) -> None:
    gui.duplicate_template()


def preview_template(gui: ReportingSystemGUI) -> None:
    gui.preview_template()


def save_template_method(gui: ReportingSystemGUI, *args, **kwargs) -> None:
    gui.save_template_method(*args, **kwargs)


def save_template_dict_method(gui: ReportingSystemGUI, *args, **kwargs) -> None:
    gui.save_template_dict_method(*args, **kwargs)


def view_templates_menu(gui: ReportingSystemGUI) -> None:
    gui.view_templates_menu()


def to_dict_report_template(gui: ReportingSystemGUI, *args, **kwargs):
    return gui.to_dict_report_template(*args, **kwargs)


def create_advanced_template_menu(gui: ReportingSystemGUI) -> None:
    gui.create_advanced_template_menu()


def delete_template_from_db(gui: ReportingSystemGUI, *args, **kwargs) -> None:
    gui.delete_template_from_db(*args, **kwargs)


def delete_template_menu(gui: ReportingSystemGUI) -> None:
    gui.delete_template_menu()


__all__ = [
    "load_templates",
    "_update_template_listbox",
    "_update_template_combos",
    "refresh_templates",
    "import_template_dialog",
    "on_template_select",
    "display_template_details",
    "create_template_dialog",
    "edit_template_dialog",
    "delete_template",
    "export_template",
    "duplicate_template",
    "preview_template",
    "save_template_method",
    "save_template_dict_method",
    "view_templates_menu",
    "to_dict_report_template",
    "create_advanced_template_menu",
    "delete_template_from_db",
    "delete_template_menu",
]