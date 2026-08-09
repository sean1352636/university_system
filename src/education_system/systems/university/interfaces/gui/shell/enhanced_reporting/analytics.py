"""Analytics wrappers for the enhanced reporting GUI.

This module exposes a functional interface to the analytics-related
methods available on the :class:`~modules.shared.gui.enhanced_reporting.core.ReportingSystemGUI`.  For
each analytics capability there is a corresponding function which
takes a GUI instance and delegates to the underlying method.

Due to the large number of analytics operations available, the
wrappers provided here cover quality checks, predictions, anomaly
detection, correlation analysis and comprehensive reporting helpers.
"""

from __future__ import annotations

from typing import Any

from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.core import ReportingSystemGUI

def run_quality_check(gui: ReportingSystemGUI) -> None:
    gui.run_quality_check()


def _display_quality_results(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._display_quality_results(*args, **kwargs)


def export_quality_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.export_quality_report(*args, **kwargs)


def run_predictions(gui: ReportingSystemGUI) -> None:
    gui.run_predictions()


def _display_predictions_results(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._display_predictions_results(*args, **kwargs)


def run_anomaly_detection(gui: ReportingSystemGUI) -> None:
    gui.run_anomaly_detection()


def _display_anomaly_results(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._display_anomaly_results(*args, **kwargs)


def run_correlation_analysis(gui: ReportingSystemGUI) -> None:
    gui.run_correlation_analysis()


def _show_correlation_results(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._show_correlation_results(*args, **kwargs)


def run_quality_checks(gui: ReportingSystemGUI) -> None:
    gui.run_quality_checks()


def display_quality_checks_results(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.display_quality_checks_results(*args, **kwargs)


def check_missing_data(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.check_missing_data(*args, **kwargs)


def check_duplicates(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.check_duplicates(*args, **kwargs)


def check_invalid_data(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.check_invalid_data(*args, **kwargs)


def check_data_freshness(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.check_data_freshness(*args, **kwargs)


def create_correlation_matrix(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.create_correlation_matrix(*args, **kwargs)


def create_heatmap(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.create_heatmap(*args, **kwargs)


def create_interactive_dashboard(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.create_interactive_dashboard(*args, **kwargs)


def show_visualization_result(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.show_visualization_result(*args, **kwargs)


def detect_anomalies(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.detect_anomalies(*args, **kwargs)


def predict_dropout_risk(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.predict_dropout_risk(*args, **kwargs)


def run_comprehensive_quality_check(gui: ReportingSystemGUI) -> None:
    gui.run_comprehensive_quality_check()


def display_comprehensive_quality_results(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.display_comprehensive_quality_results(*args, **kwargs)


def run_comprehensive_predictions(gui: ReportingSystemGUI) -> None:
    gui.run_comprehensive_predictions()


def display_comprehensive_predictions(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.display_comprehensive_predictions(*args, **kwargs)


def run_comprehensive_anomaly_detection(gui: ReportingSystemGUI) -> None:
    gui.run_comprehensive_anomaly_detection()


def display_comprehensive_anomalies(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.display_comprehensive_anomalies(*args, **kwargs)


def run_comprehensive_correlation(gui: ReportingSystemGUI) -> None:
    gui.run_comprehensive_correlation()


def display_comprehensive_correlation(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.display_comprehensive_correlation(*args, **kwargs)


def generate_correlation_heatmap(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.generate_correlation_heatmap(*args, **kwargs)


def show_correlation_heatmap_result(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.show_correlation_heatmap_result(*args, **kwargs)


def export_predictions_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.export_predictions_report(*args, **kwargs)


def export_anomaly_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.export_anomaly_report(*args, **kwargs)


def export_correlation_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.export_correlation_report(*args, **kwargs)