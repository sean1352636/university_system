"""Validation utilities for grade tracking"""


def validate_grade(grade_value, max_grade=100):
    """Validate grade value is within acceptable range"""
    try:
        grade = float(grade_value)
        return 0 <= grade <= max_grade
    except (ValueError, TypeError):
        return False


def validate_gpa(gpa_value, max_gpa=4.0):
    """Validate GPA value"""
    try:
        gpa = float(gpa_value)
        return 0 <= gpa <= max_gpa
    except (ValueError, TypeError):
        return False


def validate_percentage(percentage):
    """Validate percentage value"""
    try:
        pct = float(percentage)
        return 0 <= pct <= 100
    except (ValueError, TypeError):
        return False
