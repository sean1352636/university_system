"""Report generation wrappers and utilities for the enhanced reporting GUI.

This module provides functional wrappers around the report-generation
methods defined on :class:`~modules.shared.gui.enhanced_reporting.core.ReportingSystemGUI`.  It also
re-exports standalone report generation helpers from the core module so
they can be used independently of a GUI instance.
"""

from __future__ import annotations

from typing import Any

from .core import ReportingSystemGUI
from .core import (
    generate_enhanced_pdf_report,
    generate_enhanced_section,
    generate_enhanced_excel_report as generate_enhanced_excel_report_standalone,
    generate_interactive_report as generate_interactive_report_standalone,
    generate_statistical_summary,
    generate_quality_section,
    generate_predictions_section,
)

def generate_from_template(gui: ReportingSystemGUI) -> None:
    gui.generate_from_template()


def generate_report(gui: ReportingSystemGUI) -> None:
    gui.generate_report()


def show_report_success(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.show_report_success(*args, **kwargs)


def load_recent_reports(gui: ReportingSystemGUI) -> None:
    gui.load_recent_reports()


def _update_reports_tree(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._update_reports_tree(*args, **kwargs)


def refresh_reports(gui: ReportingSystemGUI) -> None:
    gui.refresh_reports()


def generate_report_method(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.generate_report_method(*args, **kwargs)


def generate_enhanced_excel_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.generate_enhanced_excel_report(*args, **kwargs)


def generate_interactive_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.generate_interactive_report(*args, **kwargs)


def generate_advanced_report_menu(gui: ReportingSystemGUI) -> None:
    gui.generate_advanced_report_menu()


def generate_interactive_report_menu(gui: ReportingSystemGUI) -> None:
    gui.generate_interactive_report_menu()


# Re-export standalone helpers for convenience
__all__ = [
    "generate_from_template",
    "generate_report",
    "show_report_success",
    "load_recent_reports",
    "_update_reports_tree",
    "refresh_reports",
    "generate_report_method",
    "generate_enhanced_excel_report",
    "generate_interactive_report",
    "generate_advanced_report_menu",
    "generate_interactive_report_menu",
    "generate_enhanced_pdf_report",
    "generate_enhanced_section",
    "generate_enhanced_excel_report_standalone",
    "generate_interactive_report_standalone",
    "generate_statistical_summary",
    "generate_quality_section",
    "generate_predictions_section",
]