from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui._imports import (
    GRADE_CALCULATION_AVAILABLE,
    percentage_to_letter,
    letter_to_percentage,
    letter_to_gpa,
    calculate_trend_slope,
)


class GradeCalculationsMixin:
    # Grade Calculation Utility Functions
    def percentage_to_letter_gui(self, percentage):
        """Convert percentage to letter grade"""
        if GRADE_CALCULATION_AVAILABLE:
            return percentage_to_letter(percentage)
        else:
            return "N/A"

    def letter_to_percentage_gui(self, letter_grade):
        """Convert letter grade to percentage"""
        if GRADE_CALCULATION_AVAILABLE:
            return letter_to_percentage(letter_grade)
        else:
            return 0

    def letter_to_gpa_gui(self, letter_grade):
        """Convert letter grade to GPA points"""
        if GRADE_CALCULATION_AVAILABLE:
            return letter_to_gpa(letter_grade)
        else:
            return 0

    def calculate_trend_slope_gui(self, values):
        """Calculate trend slope for values"""
        if GRADE_CALCULATION_AVAILABLE:
            return calculate_trend_slope(values)
        else:
            return 0
