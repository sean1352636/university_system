"""Scheduling wrappers for the enhanced reporting GUI.

This module contains wrapper functions around the scheduling methods of
the GUI class as well as re-exporting standalone scheduling helpers
from the core module.  Use these functions to manage scheduled
reports without directly coupling to the GUI implementation.
"""

from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import ReportingSystemGUI
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import (
    load_scheduled_reports as load_scheduled_reports_standalone,
    save_scheduled_reports,
    start_scheduler,
)

def load_scheduled_reports(gui: ReportingSystemGUI) -> None:
    gui.load_scheduled_reports()


def _update_schedule_tree(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._update_schedule_tree(*args, **kwargs)


def create_schedule(gui: ReportingSystemGUI) -> None:
    gui.create_schedule()


def toggle_schedule(gui: ReportingSystemGUI) -> None:
    gui.toggle_schedule()


def edit_schedule(gui: ReportingSystemGUI) -> None:
    gui.edit_schedule()


def run_schedule_now(gui: ReportingSystemGUI) -> None:
    gui.run_schedule_now()


def delete_schedule(gui: ReportingSystemGUI) -> None:
    gui.delete_schedule()


def schedule_report(gui: ReportingSystemGUI) -> None:
    gui.schedule_report()


def schedule_advanced_report_menu(gui: ReportingSystemGUI) -> None:
    gui.schedule_advanced_report_menu()


def view_scheduled_reports_menu(gui: ReportingSystemGUI) -> None:
    gui.view_scheduled_reports_menu()


def manage_schedule_menu(gui: ReportingSystemGUI) -> None:
    gui.manage_schedule_menu()


def run_scheduler(gui: ReportingSystemGUI) -> None:
    gui.run_scheduler()


def start_scheduler_method(gui: ReportingSystemGUI) -> None:
    gui.start_scheduler_method()


__all__ = [
    "load_scheduled_reports",
    "_update_schedule_tree",
    "create_schedule",
    "toggle_schedule",
    "edit_schedule",
    "run_schedule_now",
    "delete_schedule",
    "schedule_report",
    "schedule_advanced_report_menu",
    "view_scheduled_reports_menu",
    "manage_schedule_menu",
    "run_scheduler",
    "start_scheduler_method",
    "load_scheduled_reports_standalone",
    "save_scheduled_reports",
    "start_scheduler",
]