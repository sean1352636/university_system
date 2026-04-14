"""Degree Progress Tracker package.

Re-exports DegreeProgressGUI from its new location in academic_progress
for backward compatibility.
"""

from education_system.university_system.modules.domain.academics.academic_progress.gui.degree_progress_gui import DegreeProgressGUI

__all__ = ['DegreeProgressGUI']
