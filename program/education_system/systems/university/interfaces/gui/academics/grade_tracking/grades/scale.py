"""Extracted GradeManager behaviour."""
from . import *

GRADE_SYSTEMS = {
    "letter": {
        "A+": 4.3, "A": 4.0, "A-": 3.7,
        "B+": 3.3, "B": 3.0, "B-": 2.7,
        "C+": 2.3, "C": 2.0, "C-": 1.7,
        "D+": 1.3, "D": 1.0, "D-": 0.7,
        "F": 0.0
    },
    "percentage": {
        "range": (0, 100),
        "conversion": {
        (90, 100): "A+", (85, 89.99): "A", (80, 84.99): "A-",
        (75, 79.99): "B+", (70, 74.99): "B", (65, 69.99): "B-",
        (60, 64.99): "C+", (55, 59.99): "C", (50, 54.99): "C-",
        (45, 49.99): "D+", (40, 44.99): "D", (35, 39.99): "D-",
        (0, 34.99): "F"
        }
    }
}

def percentage_to_letter(percentage):
    """Convert a percentage score to a letter grade"""
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        min_score, max_score = score_range
        if min_score <= percentage <= max_score:
            return letter
    return 'F'

def letter_to_percentage(letter_grade):
    """Convert a letter grade to a percentage score (midpoint of range)"""
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        if letter == letter_grade:
            min_score, max_score = score_range
        return (min_score + max_score) / 2
    return 0

def letter_to_gpa(letter_grade):
    """Convert a letter grade to a GPA value"""
    if letter_grade in GRADE_SYSTEMS["letter"]:
        return GRADE_SYSTEMS["letter"][letter_grade]
    return 0

class GradeScaleMixin:
    def percentage_to_letter(self, percentage):
        """Convert percentage to letter grade"""
        if percentage >= 93:
            return 'A+'
        elif percentage >= 90:
            return 'A'
        elif percentage >= 87:
            return 'A-'
        elif percentage >= 83:
            return 'B+'
        elif percentage >= 80:
            return 'B'
        elif percentage >= 77:
            return 'B-'
        elif percentage >= 73:
            return 'C+'
        elif percentage >= 70:
            return 'C'
        elif percentage >= 67:
            return 'C-'
        elif percentage >= 63:
            return 'D+'
        elif percentage >= 60:
            return 'D'
        elif percentage >= 57:
            return 'D-'
        else:
            return 'F'

    def letter_to_gpa(self, letter_grade):
        """Convert letter grade to GPA points"""
        grade_map = {
            'A+': 4.3, 'A': 4.0, 'A-': 3.7,
            'B+': 3.3, 'B': 3.0, 'B-': 2.7,
            'C+': 2.3, 'C': 2.0, 'C-': 1.7,
            'D+': 1.3, 'D': 1.0, 'D-': 0.7,
            'F': 0.0
        }
        return grade_map.get(letter_grade, 0.0)
