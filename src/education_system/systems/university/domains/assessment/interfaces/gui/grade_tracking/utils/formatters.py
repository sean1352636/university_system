"""Formatting utilities for grade tracking"""


def format_percentage(value, decimals=2):
    """Format a number as a percentage"""
    try:
        return f"{float(value):.{decimals}f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_gpa(value, decimals=2):
    """Format GPA value"""
    try:
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def format_letter_grade(percentage):
    """Convert percentage to letter grade"""
    try:
        pct = float(percentage)
        if pct >= 90:
            return "A+"
        elif pct >= 85:
            return "A"
        elif pct >= 80:
            return "A-"
        elif pct >= 77:
            return "B+"
        elif pct >= 73:
            return "B"
        elif pct >= 70:
            return "B-"
        elif pct >= 67:
            return "C+"
        elif pct >= 63:
            return "C"
        elif pct >= 60:
            return "C-"
        elif pct >= 57:
            return "D+"
        elif pct >= 53:
            return "D"
        elif pct >= 50:
            return "D-"
        else:
            return "F"
    except (ValueError, TypeError):
        return "N/A"
