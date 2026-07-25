from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domain.pastoral.health.records.db.audit import log_audit_event


def screening_guidelines(auth):
    """Display screening guidelines"""
    print("\n===== Preventive Screening Guidelines =====")

    guidelines = {
        "18-21 Years": [
            "Annual physical examination",
            "Blood pressure screening annually",
            "Mental health screening annually",
            "STI screening if sexually active",
            "Cervical cancer screening (ages 21+)"
        ],
        "22-29 Years": [
            "Annual physical examination",
            "Blood pressure screening annually",
            "Cholesterol screening every 5 years",
            "Mental health screening annually",
            "STI screening if sexually active",
            "Cervical cancer screening every 3 years"
        ],
        "30-39 Years": [
            "Annual physical examination",
            "Blood pressure screening annually",
            "Cholesterol screening every 5 years",
            "Diabetes screening every 3 years",
            "Mental health screening annually",
            "Cervical cancer screening every 3 years"
        ],
        "40+ Years": [
            "Annual physical examination",
            "Blood pressure screening every 6 months",
            "Cholesterol screening every 3 years",
            "Diabetes screening every 3 years",
            "Mental health screening annually",
            "Mammography annually (women 40+)",
            "Cervical cancer screening every 3 years",
            "Colonoscopy every 10 years (50+)"
        ]
    }

    for age_group, screenings in guidelines.items():
        print(f"\n{age_group}:")
        for screening in screenings:
            print(f"  • {screening}")

    print("\n" + "="*50)
    print("Note: Guidelines may vary based on individual risk factors")
    print("and family history. Consult with healthcare provider for")
    print("personalized screening recommendations.")



def screening_recommendations(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to generate screening recommendations.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Health Screening Recommendations =====")

    # Age-based screening recommendations
    print("AGE-BASED SCREENING RECOMMENDATIONS")
    print("-" * 35)

    # Get students by age groups
    age_groups = [
        ('18-21', 18, 21, ['Mental health screening', 'STI testing', 'Immunization review']),
        ('22-25', 22, 25, ['Blood pressure check', 'Cholesterol screening', 'Mental health screening']),
        ('26-30', 26, 30, ['Diabetes screening', 'Blood pressure check', 'Cholesterol screening']),
        ('30+', 30, 100, ['Comprehensive metabolic panel', 'Cardiovascular risk assessment'])
    ]

    for age_range, min_age, max_age, recommended_screenings in age_groups:
        cursor.execute('''
        SELECT COUNT(*) FROM students
        WHERE age BETWEEN ? AND ?
        ''', (min_age, max_age))

        student_count = cursor.fetchone()[0]

        if student_count > 0:
            print(f"\nAge Group {age_range}: {student_count} students")
            print("Recommended screenings:")
            for screening in recommended_screenings:
                print(f"  • {screening}")

    # Risk-based screening recommendations
    print("\nRISK-BASED SCREENING RECOMMENDATIONS")
    print("-" * 34)

    # Students with family history indicators
    cursor.execute('''
    SELECT student_id, first_name, last_name
    FROM students s
    WHERE EXISTS (
        SELECT 1 FROM medical_conditions mc
        WHERE mc.student_id = s.student_id
        AND mc.condition_name IN ('Family History of Heart Disease', 'Family History of Diabetes', 'Family History of Cancer')
        AND mc.status = 'active'
    )
    ''')

    family_history_students = cursor.fetchall()

    if family_history_students:
        print(f"Students with significant family history: {len(family_history_students)}")
        print("Enhanced screening recommendations:")
        print("  • Earlier cardiovascular screening")
        print("  • Diabetes screening (if family history of diabetes)")
        print("  • Cancer screening discussion")
        print("  • Genetic counseling referral consideration")

    # Students with chronic conditions needing monitoring
    cursor.execute('''
    SELECT mc.condition_name, COUNT(*) as patient_count
    FROM medical_conditions mc
    WHERE mc.status = 'active'
    AND mc.condition_name IN ('Diabetes', 'Hypertension', 'Asthma', 'Depression')
    GROUP BY mc.condition_name
    ORDER BY patient_count DESC
    ''')

    chronic_conditions = cursor.fetchall()

    if chronic_conditions:
        print("\nChronic condition monitoring:")

        condition_monitoring = {
            'Diabetes': ['HbA1c every 3-6 months', 'Annual eye exam', 'Foot exam', 'Kidney function tests'],
            'Hypertension': ['Blood pressure checks every 3 months', 'Annual cardiovascular risk assessment'],
            'Asthma': ['Peak flow monitoring', 'Annual spirometry', 'Allergy testing if indicated'],
            'Depression': ['PHQ-9 screening every 3 months', 'Annual comprehensive mental health assessment']
        }

        for condition, count in chronic_conditions:
            print(f"\n{condition} ({count} students):")
            if condition in condition_monitoring:
                for monitoring in condition_monitoring[condition]:
                    print(f"  • {monitoring}")

    # Population-specific recommendations
    print("\nPOPULATION-SPECIFIC RECOMMENDATIONS")
    print("-" * 33)

    # High-risk behaviors screening
    cursor.execute('''
    SELECT COUNT(*) FROM students
    WHERE age BETWEEN 18 AND 25
    ''')

    young_adults = cursor.fetchone()[0]

    if young_adults > 0:
        print(f"Young adults (18-25): {young_adults} students")
        print("Universal screening recommendations:")
        print("  • Alcohol and substance use screening (AUDIT, DAST)")
        print("  • Mental health screening (PHQ-9, GAD-7)")
        print("  • Sexual health screening")
        print("  • Nutrition and exercise assessment")

    # Create screening schedule
    create_schedule = input("\nCreate individualized screening schedules? (y/n): ").lower()

    if create_schedule == 'y':
        print("\n===== Screening Schedule Generation =====")

        # This would create personalized screening schedules based on age, risk factors, etc.
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.age,
               GROUP_CONCAT(mc.condition_name) as conditions
        FROM students s
        LEFT JOIN medical_conditions mc ON s.student_id = mc.student_id AND mc.status = 'active'
        GROUP BY s.student_id, s.first_name, s.last_name, s.age
        LIMIT 10
        ''')

        sample_students = cursor.fetchall()

        print("Sample screening schedules generated:")

        for student_id, first_name, last_name, age, conditions in sample_students:
            print(f"\n{first_name} {last_name} (Age: {age}):")

            # Age-based recommendations
            if 18 <= age <= 21:
                print("  • Annual: Mental health screening, immunization review")
                print("  • Every 2 years: STI testing (if sexually active)")
            elif 22 <= age <= 25:
                print("  • Annual: Blood pressure, mental health screening")
                print("  • Every 5 years: Cholesterol screening")
            elif 26 <= age <= 30:
                print("  • Annual: Blood pressure, diabetes screening")
                print("  • Every 3 years: Cholesterol screening")
            else:
                print("  • Annual: Comprehensive metabolic panel")
                print("  • Every 2 years: Cardiovascular risk assessment")

            # Condition-based additions
            if conditions:
                print(f"  • Additional monitoring for: {conditions}")

        # Save schedules (in a real system)
        print(f"\nScreening schedules generated for all {len(sample_students)} students.")
        log_audit_event(auth.current_user['id'], 'generate_screening_schedules', 'screening', 0,
                       f"Schedules for {len(sample_students)} students")

    conn.close()



