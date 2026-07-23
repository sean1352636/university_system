"""Template wizard dialog wrappers for the enhanced reporting GUI.

This module wraps the template wizard related methods of the GUI
class.  The wizard guides users through the creation of report
templates using a step-by-step interface.  Each function delegates
the corresponding call to the GUI instance.
"""

from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.shared.gui.enhanced_reporting.core import ReportingSystemGUI


def show_template_wizard(gui: ReportingSystemGUI) -> None:
    gui.show_template_wizard()


def show_wizard_step(gui: ReportingSystemGUI, *args: Any, **kwargs: Any) -> None:
    gui.show_wizard_step(*args, **kwargs)


def show_wizard_step_1(gui: ReportingSystemGUI) -> None:
    gui.show_wizard_step_1()


def wizard_next_step(gui: ReportingSystemGUI) -> None:
    gui.wizard_next_step()


def wizard_prev_step(gui: ReportingSystemGUI) -> None:
    gui.wizard_prev_step()


def wizard_finish(gui: ReportingSystemGUI) -> None:
    gui.wizard_finish()


__all__ = [
    "show_template_wizard",
    "show_wizard_step",
    "show_wizard_step_1",
    "wizard_next_step",
    "wizard_prev_step",
    "wizard_finish",
]