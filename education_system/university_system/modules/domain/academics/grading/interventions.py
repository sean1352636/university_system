from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.infrastructure.database.db import get_connection

def intervention_recommendations():
    """Generate intervention recommendations for at-risk students"""
    print("\nIntervention Recommendations")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get students with risk assessments
        cursor.execute('''
        SELECT sra.student_id, s.first_name, s.last_name, s.course,
               sra.risk_score, sra.risk_level
        FROM student_risk_assessment sra
        JOIN students s ON sra.student_id = s.student_id
        WHERE sra.risk_level IN ('High', 'Medium', 'Low')
        ORDER BY sra.risk_score DESC
        ''')

        students = cursor.fetchall()

        if not students:
            print("No risk assessments found. Run Student Risk Assessment first.")
            conn.close()
            return

        print(f"Generating intervention recommendations for {len(students)} students...")

        recommendations = []

        for student_id, first_name, last_name, course, risk_score, risk_level in students:
            student_recommendations = generate_intervention_plan(cursor, student_id,
                                                               first_name, last_name,
                                                               course, risk_score, risk_level)
            recommendations.append(student_recommendations)

        # Display recommendations
        display_intervention_recommendations(recommendations)

        # Save to database
        save_intervention_recommendations(cursor, recommendations)
        conn.commit()

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_intervention_plan(cursor, student_id, first_name, last_name, course, risk_score, risk_level):
    """Generate intervention plan for a specific student"""
    from education_system.university_system.modules.domain.academics.grading.grade_calculation import calculate_student_gpa

    interventions = []

    # Get current GPA
    gpa, _, _ = calculate_student_gpa(cursor, student_id)

    # Intervention 1: Academic Advising
    if risk_level in ['High', 'Medium']:
        interventions.append({
            'type': 'Academic Advising',
            'priority': 1 if risk_level == 'High' else 2,
            'description': 'Schedule meeting with academic advisor to review progress and create action plan',
            'timeline': '1 week' if risk_level == 'High' else '2 weeks'
        })

    # Intervention 2: Tutoring
    if gpa is not None and gpa < 2.5:
        interventions.append({
            'type': 'Tutoring',
            'priority': 1,
            'description': 'Arrange tutoring sessions for struggling subjects',
            'timeline': 'Immediate'
        })

    # Intervention 3: Study Skills Workshop
    if risk_score >= 20:
        interventions.append({
            'type': 'Study Skills Workshop',
            'priority': 2,
            'description': 'Enroll in study skills and time management workshop',
            'timeline': '2 weeks'
        })

    # Intervention 4: Mentoring
    if risk_level == 'High':
        interventions.append({
            'type': 'Mentoring',
            'priority': 2,
            'description': 'Pair with peer mentor or faculty mentor for ongoing support',
            'timeline': '1 week'
        })

    # Intervention 5: Counseling
    if risk_score >= 40:
        interventions.append({
            'type': 'Counseling',
            'priority': 1,
            'description': 'Refer to academic or personal counseling services',
            'timeline': 'Immediate'
        })

    # Intervention 6: Course Load Adjustment
    if gpa is not None and gpa < 2.0:
        interventions.append({
            'type': 'Modified Schedule',
            'priority': 1,
            'description': 'Consider reducing course load or adjusting schedule',
            'timeline': 'Next enrollment period'
        })

    return {
        'student_id': student_id,
        'name': f"{first_name} {last_name}",
        'course': course,
        'risk_score': risk_score,
        'risk_level': risk_level,
        'gpa': gpa,
        'interventions': sorted(interventions, key=lambda x: x['priority'])
    }

def display_intervention_recommendations(recommendations):
    """Display intervention recommendations"""
    print("\n" + "="*100)
    print("INTERVENTION RECOMMENDATIONS")
    print("="*100)

    for rec in recommendations:
        print(f"\nStudent: {rec['name']} ({rec['course']})")
        print(f"Risk Level: {rec['risk_level']} (Score: {rec['risk_score']})")
        print(f"Current GPA: {rec['gpa']:.2f}" if rec['gpa'] else "Current GPA: N/A")
        print("\nRecommended Interventions:")

        for intervention in rec['interventions']:
            priority_symbol = "🔴" if intervention['priority'] == 1 else "🟡"
            print(f"  {priority_symbol} {intervention['type']} (Priority {intervention['priority']})")
            print(f"     {intervention['description']}")
            print(f"     Timeline: {intervention['timeline']}")
            print()

def generate_system_recommendations(risk_data):
    """Generate system-wide recommendations based on risk data"""
    recommendations = []

    if not risk_data['students']:
        return recommendations

    summary_stats = risk_data['summary_stats']
    risk_dist = summary_stats['risk_distribution']
    total_students = summary_stats['total_students']
    avg_risk = summary_stats['avg_risk_score']

    # High-level recommendations based on risk distribution
    high_risk_pct = (risk_dist['High'] / total_students) * 100
    medium_risk_pct = (risk_dist['Medium'] / total_students) * 100

    if high_risk_pct > 15:
        recommendations.append(
            "Implement emergency academic intervention program - high percentage of students at severe risk")
        recommendations.append(
            "Consider comprehensive curriculum review and instructor training")
    elif high_risk_pct > 5:
        recommendations.append(
            "Strengthen early warning systems and increase counseling resources")

    if medium_risk_pct > 25:
        recommendations.append(
            "Expand tutoring services and academic support programs")
        recommendations.append(
            "Implement peer mentoring initiatives")

    # Recommendations based on average risk score
    if avg_risk > 30:
        recommendations.append(
            "Review admission standards and prerequisite requirements")
        recommendations.append(
            "Develop comprehensive student success programming")
    elif avg_risk > 20:
        recommendations.append(
            "Enhance academic advising and progress monitoring")

    # Always include these general recommendations
    recommendations.extend([
        "Establish regular risk assessment monitoring (monthly)",
        "Create targeted intervention protocols for each risk level",
        "Develop predictive analytics dashboard for administrators",
        "Train faculty in early identification of at-risk students"
    ])

    return recommendations


def save_intervention_recommendations(cursor, recommendations):
    """Save intervention recommendations to the database."""
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS intervention_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            intervention_type TEXT NOT NULL,
            priority INTEGER,
            description TEXT,
            timeline TEXT,
            risk_score REAL,
            risk_level TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    for rec in recommendations:
        for intervention in rec.get('interventions', []):
            cursor.execute('''
                INSERT INTO intervention_recommendations
                (student_id, intervention_type, priority, description, timeline, risk_score, risk_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                rec['student_id'],
                intervention['type'],
                intervention['priority'],
                intervention['description'],
                intervention['timeline'],
                rec['risk_score'],
                rec['risk_level'],
            ))
