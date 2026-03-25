"""Report operations for the enhanced reporting GUI.

This module wraps the report-related methods of the GUI class and
re-exports standalone helpers for sending reports via email.  These
wrappers make it easy to perform operations such as opening,
sharing or deleting reports from outside the GUI context.
"""

from __future__ import annotations

from typing import Any

from education_system.university_system.modules.shared.gui.enhanced_reporting.core import ReportingSystemGUI
from education_system.university_system.modules.shared.gui.enhanced_reporting.core import send_report_email  # standalone helper


def open_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.open_report(*args, **kwargs)


def share_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.share_report(*args, **kwargs)


def delete_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.delete_report(*args, **kwargs)


def send_report_email_method(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    """Delegate to the GUI method for sending a report via email."""
    gui.send_report_email(*args, **kwargs)


def send_scheduled_report_email(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.send_scheduled_report_email(*args, **kwargs)


def _send_report_to_admin(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._send_report_to_admin(*args, **kwargs)


def _save_analytics_report(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui._save_analytics_report(*args, **kwargs)


__all__ = [
    "open_report",
    "share_report",
    "delete_report",
    "send_report_email_method",
    "send_scheduled_report_email",
    "_send_report_to_admin",
    "_save_analytics_report",
    "send_report_email",
]