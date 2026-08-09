import numpy as np
from datetime import datetime

from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.domain.assessment.grading.grade_calculation.utils import calculate_trend_slope
from education_system.systems.university.domain.assessment.grading.grade_calculation.gpa import calculate_student_gpa
from education_system.systems.university.domain.assessment.grading.grade_calculation.prediction import extract_student_features


def assess_student_risk(cursor, student_id, first_name, last_name, course):
    """Assess risk level for a specific student"""
    try:
        # Calculate current GPA
        gpa, credits, _ = calculate_student_gpa(cursor, student_id)

        # Initialize risk factors
        risk_factors = []
        risk_score = 0

        # Factor 1: Low GPA
        if gpa and gpa < 2.0:
            risk_factors.append("Low GPA")
            risk_score += 30
        elif gpa and gpa < 2.5:
            risk_factors.append("Below Average GPA")
            risk_score += 15

        # Factor 2: Failed assessments
        cursor.execute('''
        SELECT COUNT(*) FROM grades g
        WHERE g.student_id = ? AND g.letter_grade = 'F'
        ''', (student_id,))

        failed_count = cursor.fetchone()[0]
        if failed_count > 2:
            risk_factors.append("Multiple Failed Assessments")
            risk_score += 25
        elif failed_count > 0:
            risk_factors.append("Some Failed Assessments")
            risk_score += 10

        # Factor 3: Declining performance trend
        cursor.execute('''
        SELECT g.score / a.max_points * 100
        FROM grades g
        JOIN assessments a ON g.assessment_id = a.assessment_id
        WHERE g.student_id = ?
        ORDER BY g.submission_date DESC
        LIMIT 5
        ''', (student_id,))

        recent_scores = [row[0] for row in cursor.fetchall()]
        if len(recent_scores) >= 3:
            trend_slope = calculate_trend_slope(recent_scores[::-1])  # Reverse for chronological order
            if trend_slope < -5:  # Declining by more than 5% per assessment
                risk_factors.append("Declining Performance")
                risk_score += 20

        # Factor 4: Low submission rate
        features = extract_student_features(cursor, student_id)
        if features and features['submission_rate'] < 0.8:
            risk_factors.append("Low Submission Rate")
            risk_score += 15

        # Determine risk level
        if risk_score >= 50:
            risk_level = "High"
        elif risk_score >= 30:
            risk_level = "Medium"
        elif risk_score >= 15:
            risk_level = "Low"
        else:
            risk_level = "Minimal"

        return {
            'student_id': student_id,
            'name': f"{first_name} {last_name}",
            'course': course,
            'gpa': gpa,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors
        }

    except sqlite3.Error as e:
        print(f"Error assessing risk for student {student_id}: {e}")
        return None


def student_risk_assessment():
    """Assess risk levels for all students"""
    print("\nStudent Risk Assessment")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get all students with grades
        cursor.execute('''
        SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course
        FROM students s
        JOIN module_grades mg ON s.student_id = mg.student_id
        ORDER BY s.last_name, s.first_name
        ''')

        students = cursor.fetchall()

        if not students:
            print("No students with grades found.")
            conn.close()
            return

        print(f"Assessing risk for {len(students)} students...")

        risk_assessments = []

        for student_id, first_name, last_name, course in students:
            risk_data = assess_student_risk(cursor, student_id, first_name, last_name, course)
            if risk_data:
                risk_assessments.append(risk_data)

        # Sort by risk score (highest first)
        risk_assessments.sort(key=lambda x: x['risk_score'], reverse=True)

        # Display results
        display_risk_assessment_results(risk_assessments)

        # Save to database
        save_risk_assessments(cursor, risk_assessments)
        conn.commit()

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")


def display_risk_assessment_results(risk_assessments):
    """Display risk assessment results"""
    print("\n" + "="*100)
    print("STUDENT RISK ASSESSMENT RESULTS")
    print("="*100)

    # Summary by risk level
    risk_counts = {'High': 0, 'Medium': 0, 'Low': 0, 'Minimal': 0}
    for assessment in risk_assessments:
        risk_counts[assessment['risk_level']] += 1

    print("\nRisk Level Summary:")
    print(f"High Risk: {risk_counts['High']} students")
    print(f"Medium Risk: {risk_counts['Medium']} students")
    print(f"Low Risk: {risk_counts['Low']} students")
    print(f"Minimal Risk: {risk_counts['Minimal']} students")

    # Show high-risk students in detail
    high_risk = [a for a in risk_assessments if a['risk_level'] == 'High']
    if high_risk:
        print(f"\nHIGH RISK STUDENTS ({len(high_risk)}):")
        print("-" * 80)
        for student in high_risk:
            print(f"{student['name']} ({student['course']})")
            print(f"  Risk Score: {student['risk_score']}")
            print(f"  GPA: {student['gpa']:.2f}" if student['gpa'] else "  GPA: N/A")
            print(f"  Risk Factors: {', '.join(student['risk_factors'])}")
            print()


def save_risk_assessments(cursor, risk_assessments):
    """Save risk assessments to database"""
    assessment_date = datetime.now().strftime('%Y-%m-%d')

    for assessment in risk_assessments:
        # Clear existing assessment for this student
        cursor.execute('''
        DELETE FROM student_risk_assessment
        WHERE student_id = ?
        ''', (assessment['student_id'],))

        # Insert new assessment
        cursor.execute('''
        INSERT INTO student_risk_assessment
        (student_id, risk_score, risk_level, assessment_date, prediction_model, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (assessment['student_id'], assessment['risk_score'], assessment['risk_level'],
              assessment_date, 'Rule-based Model', 0.85))
