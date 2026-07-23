from __future__ import annotations

import numpy as np
from education_system.post_18.university_system.modules.domain.academics.grading.grade_web_context import GRADE_SYSTEMS

def _get_calculate_course_statistics():
    try:
        from education_system.post_18.university_system.modules.domain.academics.grading.performance_analytics import calculate_course_statistics
        return calculate_course_statistics
    except Exception:
        return None

def select_student(cursor):
    """Let user pick a student; returns student_id or None."""
    cursor.execute('''
        SELECT student_id, first_name, last_name
        FROM students
        ORDER BY last_name, first_name
    ''')
    rows = cursor.fetchall()
    if not rows:
        print("No students found.")
        return None

    print("\nAvailable Students:")
    for i, (sid, first, last) in enumerate(rows, start=1):
        print(f"{i}. {first} {last} (ID: {sid})")

    choice = input("Enter student number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(rows):
            print("Invalid selection.")
            return None
        return rows[idx][0]
    except ValueError:
        print("Please enter a valid number.")
        return None

def percentage_to_letter(percentage):
    """Convert a percentage score to a letter grade"""
    if percentage is None:
        return 'F'
    # Cap at 100+ → A+
    if percentage > 100:
        percentage = 100
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        min_score, max_score = score_range
        if min_score <= percentage <= max_score:
            return letter

    return 'F'

def letter_to_percentage(letter_grade):
    """Convert a letter grade to a percentage score (midpoint of range)"""
    if not letter_grade:
        return 0
    for score_range, letter in GRADE_SYSTEMS["percentage"]["conversion"].items():
        if letter == letter_grade:
            min_score, max_score = score_range
            return (min_score + max_score) / 2

    return 0

def calculate_trend_slope(values):
    """Calculate the slope of a trend line"""
    if len(values) < 2:
        return 0

    x = np.arange(len(values))
    slope = np.polyfit(x, values, 1)[0]
    return slope
