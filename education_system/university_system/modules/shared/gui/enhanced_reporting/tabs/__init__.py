"""Tab wrappers for the enhanced reporting GUI.

This subpackage exposes convenience functions that mirror the tab
creation methods defined on :class:`~modules.shared.gui.enhanced_reporting.core.ReportingSystemGUI`.
Each function accepts an instance of the main GUI class and delegates
the call to the corresponding method.  These wrappers simplify the
use of tab creators in a functional style without exposing the
internal implementation.
"""

from __future__ import annotations

from education_system.university_system.modules.shared.gui.enhanced_reporting.core import ReportingSystemGUI  # type: ignore

def create_templates_tab(gui: ReportingSystemGUI) -> None:
    """Create the templates tab for the given GUI instance.

    Parameters
    ----------
    gui: ReportingSystemGUI
        The GUI instance on which to create the templates tab.
    """
    gui.create_templates_tab()


def create_reports_tab(gui: ReportingSystemGUI) -> None:
    """Create the reports tab for the given GUI instance."""
    gui.create_reports_tab()


def create_analytics_tab(gui: ReportingSystemGUI) -> None:
    """Create the analytics tab for the given GUI instance."""
    gui.create_analytics_tab()


def create_schedule_tab(gui: ReportingSystemGUI) -> None:
    """Create the scheduling tab for the given GUI instance."""
    gui.create_schedule_tab()


def create_system_tab(gui: ReportingSystemGUI) -> None:
    """Create the system management tab for the given GUI instance."""
    gui.create_system_tab()


def complete_system_tab_config_display(gui: ReportingSystemGUI) -> None:
    """Complete the configuration display area in the system tab.

    This function delegates to
    :meth:`~modules.shared.gui.enhanced_reporting.core.ReportingSystemGUI.complete_system_tab_config_display`.
    """
    gui.complete_system_tab_config_display()


def check_system_requirements_gui(gui: ReportingSystemGUI) -> None:
    """Run the system requirements check GUI for the given instance."""
    gui.check_system_requirements_gui()


def check_system_status(gui: ReportingSystemGUI) -> None:
    """Check and update the system status for the given GUI instance."""
    gui.check_system_status()


__all__ = [
    "create_templates_tab",
    "create_reports_tab",
    "create_analytics_tab",
    "create_schedule_tab",
    "create_system_tab",
    "complete_system_tab_config_display",
    "check_system_requirements_gui",
    "check_system_status",
]