"""System maintenance wrappers for the enhanced reporting GUI.

This module provides functions to perform various maintenance tasks
exposed by the enhanced reporting GUI.  Functions are provided to
delegate calls to a :class:`~modules.shared.gui.enhanced_reporting.core.ReportingSystemGUI` instance as
well as re-export standalone maintenance helpers from the core module.
"""

from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import ReportingSystemGUI
from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import (
    run_system_maintenance,
    cleanup_old_reports,
    get_log_file as get_log_file_standalone,
)

def clean_old_reports(gui: ReportingSystemGUI) -> None:
    gui.clean_old_reports()


def clear_cache(gui: ReportingSystemGUI) -> None:
    gui.clear_cache()


def run_maintenance_quality_check(gui: ReportingSystemGUI) -> None:
    gui.run_maintenance_quality_check()


def optimize_database(gui: ReportingSystemGUI) -> None:
    gui.optimize_database()


def run_all_maintenance(gui: ReportingSystemGUI) -> None:
    gui.run_all_maintenance()


def export_system_logs(gui: ReportingSystemGUI) -> None:
    gui.export_system_logs()


def reload_config(gui: ReportingSystemGUI) -> None:
    gui.reload_config()


def save_config(gui: ReportingSystemGUI) -> None:
    gui.save_config()


def save_scheduled_reports_method(gui: ReportingSystemGUI) -> None:
    gui.save_scheduled_reports()


def run_maintenance_menu(gui: ReportingSystemGUI) -> None:
    gui.run_maintenance_menu()


def configure_logging(gui: ReportingSystemGUI) -> None:
    gui.configure_logging()


def load_config(gui: ReportingSystemGUI) -> None:
    gui.load_config()


def get_log_file(gui: ReportingSystemGUI, *args: Any, **kwargs: Any):
    return gui.get_log_file(*args, **kwargs)


def get_reporting_db_connection(gui: ReportingSystemGUI):
    return gui.get_reporting_db_connection()


def export_logs_menu(gui: ReportingSystemGUI) -> None:
    gui.export_logs_menu()


def display_enhanced_reporting_menu(gui: ReportingSystemGUI) -> None:
    gui.display_enhanced_reporting_menu()


__all__ = [
    "clean_old_reports",
    "clear_cache",
    "run_maintenance_quality_check",
    "optimize_database",
    "run_all_maintenance",
    "export_system_logs",
    "reload_config",
    "save_config",
    "save_scheduled_reports_method",
    "run_maintenance_menu",
    "configure_logging",
    "load_config",
    "get_log_file",
    "get_reporting_db_connection",
    "export_logs_menu",
    "display_enhanced_reporting_menu",
    "run_system_maintenance",
    "cleanup_old_reports",
    "get_log_file_standalone",
]