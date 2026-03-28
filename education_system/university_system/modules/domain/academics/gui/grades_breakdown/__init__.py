"""Grades Breakdown by Module package.

Re-exports GradesBreakdownGUI from its new location in academic_progress
for backward compatibility.
"""

from education_system.university_system.modules.domain.academic_progress.gui.grades_breakdown_gui import GradesBreakdownGUI

__all__ = ['GradesBreakdownGUI']
