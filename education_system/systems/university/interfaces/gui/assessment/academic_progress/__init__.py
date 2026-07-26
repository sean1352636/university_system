"""Academic Progress GUI package."""

from education_system.systems.university.interfaces.gui.assessment.academic_progress.progress_gui import AcademicProgressGUI
from education_system.systems.university.interfaces.gui.assessment.academic_progress.gpa_calculator_gui import GPACalculatorGUI
from education_system.systems.university.interfaces.gui.assessment.academic_progress.degree_progress_gui import DegreeProgressGUI
from education_system.systems.university.interfaces.gui.assessment.academic_progress.grades_breakdown_gui import GradesBreakdownGUI

__all__ = ['AcademicProgressGUI', 'GPACalculatorGUI', 'DegreeProgressGUI', 'GradesBreakdownGUI']
