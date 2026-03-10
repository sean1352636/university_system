from education_system.university_system.modules.domain.academics.grading.grade_calculation.constants import GRADE_SYSTEMS


def percentage_to_letter(percentage):
    """Convert a percentage score to a letter grade"""
    if percentage >= 97:
        return "A+"
    elif percentage >= 93:
        return "A"
    elif percentage >= 90:
        return "A-"
    elif percentage >= 87:
        return "B+"
    elif percentage >= 83:
        return "B"
    elif percentage >= 80:
        return "B-"
    elif percentage >= 77:
        return "C+"
    elif percentage >= 73:
        return "C"
    elif percentage >= 70:
        return "C-"
    elif percentage >= 67:
        return "D+"
    elif percentage >= 63:
        return "D"
    elif percentage >= 60:
        return "D-"
    else:
        return "F"

def letter_to_percentage(letter_grade):
    """Convert a letter grade to a percentage (midpoint of range)"""
    grade_midpoints = {
        "A+": 98.5,
        "A": 95.0,
        "A-": 91.5,
        "B+": 85.0,
        "B": 81.5,
        "B-": 78.5,
        "C+": 75.0,
        "C": 71.5,
        "C-": 68.5,
        "D+": 65.0,
        "D": 61.5,
        "D-": 58.5,
        "F": 30.0  # Arbitrary low value for F
    }
    return grade_midpoints.get(letter_grade, 0)

def letter_to_gpa(letter_grade):
    """Convert a letter grade to a GPA value"""
    if letter_grade in GRADE_SYSTEMS["letter"]:
        return GRADE_SYSTEMS["letter"][letter_grade]

    return 0  # Default to 0 if no match or F
