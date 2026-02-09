"""Advanced dialog wrappers for the enhanced reporting GUI.

This module provides wrapper functions for advanced dialog operations
defined on the GUI class.  These dialogs include advanced template
creation, scheduling, comparison, versioning and bulk operations, as
well as data quality, predictive analytics, anomaly detection and
correlation analysis dialogs.
"""

from __future__ import annotations

from typing import Any

from ..core import ReportingSystemGUI


def show_advanced_template_creation_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_advanced_template_creation_dialog()


def show_enhanced_scheduling_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_enhanced_scheduling_dialog()


def show_template_comparison_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_template_comparison_dialog()


def show_template_versioning_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_template_versioning_dialog()


def show_bulk_operations_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_bulk_operations_dialog()


def show_data_quality_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_data_quality_dialog()


def show_predictive_analytics_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_predictive_analytics_dialog()


def show_anomaly_detection_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_anomaly_detection_dialog()


def show_correlation_analysis_dialog(gui: ReportingSystemGUI) -> None:
    gui.show_correlation_analysis_dialog()


__all__ = [
    "show_advanced_template_creation_dialog",
    "show_enhanced_scheduling_dialog",
    "show_template_comparison_dialog",
    "show_template_versioning_dialog",
    "show_bulk_operations_dialog",
    "show_data_quality_dialog",
    "show_predictive_analytics_dialog",
    "show_anomaly_detection_dialog",
    "show_correlation_analysis_dialog",
]