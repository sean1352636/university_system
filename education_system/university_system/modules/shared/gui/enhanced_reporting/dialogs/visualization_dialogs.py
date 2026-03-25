"""Visualization dialog wrappers for the enhanced reporting GUI.

This module contains wrappers around the visualization and API related
dialogs of the GUI class.  These include the data visualization
studio, report analytics dashboard, API documentation, system log
viewer, import/export dialog, cache management dialog, API server
controls, performance monitor and data quality dashboard.
"""

from __future__ import annotations

from typing import Any

from education_system.university_system.modules.shared.gui.enhanced_reporting.core import ReportingSystemGUI


def show_data_visualization_studio(gui: ReportingSystemGUI) -> None:
    gui.show_data_visualization_studio()


def show_report_analytics_dashboard(gui: ReportingSystemGUI) -> None:
    gui.show_report_analytics_dashboard()


def show_api_endpoints_documentation(gui: ReportingSystemGUI) -> None:
    gui.show_api_endpoints_documentation()


def show_system_logs_viewer(gui: ReportingSystemGUI) -> None:
    gui.show_system_logs_viewer()


def show_data_import_export_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_data_import_export_dialog()


def show_cache_management_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_cache_management_dialog()


def start_api_server(gui: ReportingSystemGUI) -> None:
    gui.start_api_server()


def start_api_server_gui(gui: ReportingSystemGUI) -> None:
    gui.start_api_server_gui()


def show_performance_monitor(gui: ReportingSystemGUI) -> None:
    gui.show_performance_monitor()


def show_data_quality_dashboard(gui: ReportingSystemGUI) -> None:
    gui.show_data_quality_dashboard()


__all__ = [
    "show_data_visualization_studio",
    "show_report_analytics_dashboard",
    "show_api_endpoints_documentation",
    "show_system_logs_viewer",
    "show_data_import_export_dialog",
    "show_cache_management_dialog",
    "start_api_server",
    "start_api_server_gui",
    "show_performance_monitor",
    "show_data_quality_dashboard",
]