"""What-If GPA Calculator package.

Re-exports GPACalculatorGUI from its new location in academic_progress
for backward compatibility.
"""

from education_system.university_system.modules.domain.academic_progress.gui.gpa_calculator_gui import GPACalculatorGUI

__all__ = ['GPACalculatorGUI']
