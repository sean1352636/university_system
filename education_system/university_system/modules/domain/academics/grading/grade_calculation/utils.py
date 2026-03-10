import os
import csv
import numpy as np
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3


def select_student(cursor):
    """Let user pick a student; returns student_id or None."""
    cursor.execute('''
        SELECT student_id, first_name, middle_name, last_name, course
        FROM students
        ORDER BY last_name, first_name
    ''')
    rows = cursor.fetchall()
    if not rows:
        print("No students found.")
        return None

    print("\nAvailable Students:")
    for i, (sid, fname, mname, lname, course) in enumerate(rows, start=1):
        middle_initial = mname[0] + ". " if mname else ""
        full_name = f"{fname} {middle_initial}{lname}"
        print(f"{i}. {full_name} (ID: {sid}) - {course}")

    choice = input("Enter student number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(rows):
            print("Invalid selection.")
            return None
        return rows[idx][0]  # Return student_id
    except ValueError:
        print("Please enter a valid number.")
        return None

def calculate_trend_slope(values):
    """Calculate the trend slope for a list of values"""
    if len(values) < 2:
        return 0

    x = np.arange(len(values))
    slope = np.polyfit(x, values, 1)[0]
    return slope

def select_assessment(cursor):
    """Let user pick an assessment; returns assessment_id or None."""
    cursor.execute('''
        SELECT assessment_id, assessment_name, module_code
        FROM assessments
        ORDER BY date_created DESC
    ''')
    rows = cursor.fetchall()
    if not rows:
        print("No assessments found.")
        return None

    print("\nAvailable Assessments:")
    for i, (aid, name, module) in enumerate(rows, start=1):
        print(f"{i}. [{module}] {name} (ID: {aid})")

    choice = input("Enter assessment number: ").strip()
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(rows):
            print("Invalid selection.")
            return None
        return rows[idx][0]
    except ValueError:
        print("Please enter a valid number.")
        return None

def export_batch_predictions(predictions, filename_prefix):
    """Export batch predictions to CSV"""
    try:
        # Create the exports directory if it doesn't exist
        exports_dir = 'grade_exports'
        if not os.path.exists(exports_dir):
            os.makedirs(exports_dir)

        # Generate a filename based on current timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{exports_dir}/{filename_prefix}_{timestamp}.csv"

        with open(filename, 'w', newline='') as csvfile:
            if predictions:
                fieldnames = predictions[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(predictions)

        print(f"Predictions exported to {filename}")

    except Exception as e:
        print(f"Error exporting predictions: {e}")
