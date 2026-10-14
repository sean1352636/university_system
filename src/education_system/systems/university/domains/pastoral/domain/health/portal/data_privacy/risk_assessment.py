"""Health risk assessment workflows (database-backed, interactive)."""
import logging

logger = logging.getLogger(__name__)

import json
from datetime import datetime

from education_system.systems.university.domains.pastoral.domain.health.services import get_connection
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation

from .audit import log_audit_event
from .risk_scoring import (
    calculate_risk_score,
    generate_risk_recommendations,
    get_risk_factors,
)

def view_risk_assessments(auth):
    """List recent risk assessments and optionally show details for one."""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view risk assessments.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== View Risk Assessments =====")
    student_id = input("Filter by student ID (leave blank for latest 10): ").strip()

    if student_id:
        cursor.execute("""
            SELECT ra.id, ra.student_id, s.first_name, s.last_name,
                   ra.assessment_type, ra.risk_score, ra.assessed_date,
                   COALESCE(ra.follow_up_date, '')
            FROM risk_assessments ra
            LEFT JOIN students s ON s.student_id = ra.student_id
            WHERE ra.student_id = ?
            ORDER BY ra.assessed_date DESC, ra.id DESC
            LIMIT 50
        """, (student_id,))
    else:
        cursor.execute("""
            SELECT ra.id, ra.student_id, s.first_name, s.last_name,
                   ra.assessment_type, ra.risk_score, ra.assessed_date,
                   COALESCE(ra.follow_up_date, '')
            FROM risk_assessments ra
            LEFT JOIN students s ON s.student_id = ra.student_id
            ORDER BY ra.assessed_date DESC, ra.id DESC
            LIMIT 10
        """)

    rows = cursor.fetchall()
    if not rows:
        print("No risk assessments found.")
        conn.close()
        return

    print("\nID | Student | Type | Score | Assessed | Follow-up")
    print("-" * 78)
    for rid, sid, fn, ln, atype, score, assessed, follow in rows:
        name = f"{(fn or '').strip()} {(ln or '').strip()}".strip() or sid
        print(f"{rid} | {name} ({sid}) | {atype} | {score} | {assessed or '-'} | {follow or '-'}")

    sel = input("\nEnter an assessment ID to view details (or press Enter to return): ").strip()
    if sel.isdigit():
        cursor.execute("""
            SELECT ra.id, ra.student_id, s.first_name, s.last_name,
                   ra.assessment_type, ra.risk_score, ra.risk_factors,
                   ra.recommendations, ra.assessed_date, ra.assessed_by,
                   ra.follow_up_date, ra.created_at
            FROM risk_assessments ra
            LEFT JOIN students s ON s.student_id = ra.student_id
            WHERE ra.id = ?
        """, (int(sel),))
        rec = cursor.fetchone()
        if rec:
            (rid, sid, fn, ln, atype, score, rf_json, rec_json,
             assessed, by, follow, created) = rec

            print("\n--- Assessment Detail ---")
            print(f"ID: {rid}")
            print(f"Student: { (fn or '').strip()} { (ln or '').strip()} (ID: {sid})")
            print(f"Type: {atype}")
            print(f"Risk Score: {score}")
            print(f"Assessed: {assessed} by {by}")
            print(f"Follow-up: {follow or '-'}")

            try:
                risk_factors = json.loads(rf_json) if rf_json else []
            except Exception:
                risk_factors = rf_json

            try:
                recommendations = json.loads(rec_json) if rec_json else []
            except Exception:
                recommendations = rec_json

            print("\nRisk Factors:")
            if isinstance(risk_factors, list):
                for item in risk_factors:
                    print(f" - {item}")
            else:
                print(f" {risk_factors}")

            print("\nRecommendations:")
            if isinstance(recommendations, list):
                for item in recommendations:
                    print(f" - {item}")
            else:
                print(f" {recommendations}")

            log_audit_event(auth.current_user['id'],
                            'view_risk_assessment_detail', 'risk_assessment', rid)

    log_audit_event(auth.current_user['id'],
                    'view_risk_assessments', 'risk_assessment', 'list')
    conn.close()


def screening_recommendations(auth):
    """
    Simple wrapper: ask for an existing assessment ID, then print
    recommendations using generate_risk_recommendations().
    """
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view recommendations.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Risk-Based Screening Recommendations =====")
    sel = input("Enter an assessment ID (tip: use 'View Risk Assessments' to find one): ").strip()
    if not sel.isdigit():
        print("Invalid ID.")
        conn.close()
        return

    cursor.execute("""
        SELECT assessment_type, risk_score, risk_factors
        FROM risk_assessments
        WHERE id = ?
    """, (int(sel),))
    row = cursor.fetchone()
    if not row:
        print("Assessment not found.")
        conn.close()
        return

    assessment_type, risk_score, rf_json = row
    try:
        risk_factors = json.loads(rf_json) if rf_json else []
    except Exception:
        risk_factors = []

    recs = generate_risk_recommendations(assessment_type, risk_score, risk_factors)

    print("\nRecommendations:")
    for r in recs:
        print(f" - {r}")

    log_audit_event(auth.current_user['id'],
                    'screening_recommendations', 'risk_assessment', int(sel))
    conn.close()


def population_risk_analysis(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to perform population risk analysis.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Population Risk Analysis =====")

    # High-risk student identification
    print("HIGH-RISK STUDENT IDENTIFICATION")
    print("-" * 32)

    # Students with multiple chronic conditions
    cursor.execute('''
    SELECT mc.student_id, s.first_name, s.last_name, COUNT(*) as condition_count,
           GROUP_CONCAT(mc.condition_name, ', ') as conditions
    FROM medical_conditions mc
    JOIN students s ON mc.student_id = s.student_id
    WHERE mc.status = 'active'
    GROUP BY mc.student_id, s.first_name, s.last_name
    HAVING COUNT(*) >= 2
    ORDER BY condition_count DESC
    ''')

    multi_condition_students = cursor.fetchall()

    if multi_condition_students:
        print(f"Students with multiple chronic conditions: {len(multi_condition_students)}")
        print("Top cases requiring care coordination:")
        for student_id, first_name, last_name, count, conditions in multi_condition_students[:5]:
            print(f"  {first_name} {last_name} (ID: {student_id}): {count} conditions")
            print(f"    Conditions: {conditions}")

    # Students with severe allergies
    cursor.execute('''
    SELECT a.student_id, s.first_name, s.last_name,
           GROUP_CONCAT(a.allergen, ', ') as severe_allergies
    FROM allergies a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.severity IN ('Severe', 'Life-threatening') AND a.verified = 1
    GROUP BY a.student_id, s.first_name, s.last_name
    ''')

    severe_allergy_students = cursor.fetchall()

    if severe_allergy_students:
        print(f"\nStudents with severe allergies: {len(severe_allergy_students)}")
        print("Requiring emergency action plans:")
        for student_id, first_name, last_name, allergies in severe_allergy_students[:5]:
            print(f"  {first_name} {last_name} (ID: {student_id})")
            print(f"    Severe allergies: {allergies}")

    # Risk stratification by demographics
    print("\nRISK STRATIFICATION ANALYSIS")
    print("-" * 27)

    # Age-based risk analysis
    cursor.execute('''
    SELECT
        CASE
            WHEN age < 20 THEN '18-19'
            WHEN age < 25 THEN '20-24'
            WHEN age < 30 THEN '25-29'
            WHEN age >= 30 THEN '30+'
        END as age_group,
        COUNT(*) as total_students,
        SUM(CASE WHEN EXISTS (
            SELECT 1 FROM medical_conditions mc
            WHERE mc.student_id = s.student_id AND mc.status = 'active'
        ) THEN 1 ELSE 0 END) as with_conditions
    FROM students s
    GROUP BY age_group
    ORDER BY age_group
    ''')

    age_risk_data = cursor.fetchall()

    if age_risk_data:
        print("Chronic condition prevalence by age group:")
        for age_group, total, with_conditions in age_risk_data:
            prevalence = (with_conditions / total * 100) if total > 0 else 0
            print(f"  {age_group}: {with_conditions}/{total} ({prevalence:.1f}%)")

    # Mental health risk indicators
    cursor.execute('''
    SELECT COUNT(DISTINCT student_id) as mental_health_cases
    FROM medical_conditions
    WHERE condition_name IN ('Depression', 'Anxiety', 'PTSD', 'Bipolar Disorder')
    AND status = 'active'
    ''')

    mental_health_cases = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    mental_health_prevalence = (mental_health_cases / total_students * 100) if total_students > 0 else 0

    print(f"\nMental health conditions: {mental_health_cases} students ({mental_health_prevalence:.1f}%)")

    if mental_health_prevalence > 15:  # Above typical college rates
        print("  ⚠️  High prevalence - Consider expanded mental health services")
    elif mental_health_prevalence > 10:
        print("  🟡 Moderate prevalence - Monitor trends")
    else:
        print("  ✅ Within expected range")

    # Preventive care gaps
    print("\nPREVENTIVE CARE GAPS")
    print("-" * 19)

    # Vaccination gaps
    critical_vaccines = ['COVID-19', 'Influenza (Flu)', 'Hepatitis B', 'MMR']

    for vaccine in critical_vaccines:
        cursor.execute('''
        SELECT COUNT(DISTINCT student_id)
        FROM vaccination_records
        WHERE vaccine_name = ? AND verified = 1
        ''', (vaccine,))

        vaccinated = cursor.fetchone()[0]
        coverage = (vaccinated / total_students * 100) if total_students > 0 else 0

        print(f"{vaccine}: {coverage:.1f}% coverage")

        if coverage < 70:
            print("  🔴 Low coverage - Priority intervention needed")
        elif coverage < 85:
            print("  🟡 Suboptimal - Targeted outreach recommended")
        else:
            print("  ✅ Good coverage")

    # Emergency preparedness gaps
    cursor.execute('''
    SELECT COUNT(DISTINCT s.student_id)
    FROM students s
    LEFT JOIN emergency_contacts ec ON s.student_id = ec.student_id
    WHERE ec.student_id IS NULL
    ''')

    no_emergency_contacts = cursor.fetchone()[0]
    emergency_gap = (no_emergency_contacts / total_students * 100) if total_students > 0 else 0

    print(f"\nStudents without emergency contacts: {no_emergency_contacts} ({emergency_gap:.1f}%)")

    if emergency_gap > 10:
        print("  🔴 High gap - Emergency preparedness campaign needed")
    elif emergency_gap > 5:
        print("  🟡 Moderate gap - Targeted outreach")
    else:
        print("  ✅ Good emergency preparedness")

    # Generate population risk score
    risk_factors = 0

    if mental_health_prevalence > 15:
        risk_factors += 2
    elif mental_health_prevalence > 10:
        risk_factors += 1

    # Check vaccination coverage
    low_coverage_vaccines = 0
    for vaccine in critical_vaccines:
        cursor.execute('''
        SELECT COUNT(DISTINCT student_id)
        FROM vaccination_records
        WHERE vaccine_name = ? AND verified = 1
        ''', (vaccine,))

        vaccinated = cursor.fetchone()[0]
        coverage = (vaccinated / total_students * 100) if total_students > 0 else 0

        if coverage < 70:
            low_coverage_vaccines += 1

    risk_factors += low_coverage_vaccines

    if emergency_gap > 10:
        risk_factors += 1

    print("\n===== POPULATION RISK ASSESSMENT =====")
    print(f"Risk Score: {risk_factors}/7")

    if risk_factors >= 5:
        risk_level = "HIGH"
        print("🔴 HIGH RISK - Multiple intervention priorities")
    elif risk_factors >= 3:
        risk_level = "MODERATE"
        print("🟡 MODERATE RISK - Targeted interventions needed")
    else:
        risk_level = "LOW"
        print("✅ LOW RISK - Maintain current programs")

    # Recommendations
    print("\nRECOMMENDATIONS:")

    if mental_health_prevalence > 15:
        print("• Expand mental health services and counseling staff")
        print("• Implement mental health screening programs")

    if low_coverage_vaccines > 2:
        print("• Launch comprehensive vaccination campaign")
        print("• Implement vaccination requirements or incentives")

    if emergency_gap > 10:
        print("• Emergency contact collection campaign")
        print("• Integrate into enrollment/registration process")

    if len(multi_condition_students) > 10:
        print("• Develop care coordination programs")
        print("• Implement chronic disease management protocols")

    if not any([mental_health_prevalence > 10, low_coverage_vaccines > 1, emergency_gap > 5]):
        print("• Continue current preventive health programs")
        print("• Regular monitoring of population health metrics")

    conn.close()


def health_risk_assessment(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to access health risk assessment.")
        return

    while True:
        print("\n===== Health Risk Assessment =====")
        print("1. Conduct Risk Assessment")
        print("2. View Risk Assessments")
        print("3. Risk-Based Screening Recommendations")
        print("4. Population Risk Analysis")
        print("5. Return to Main Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            conduct_risk_assessment(auth)
        elif choice == '2':
            view_risk_assessments(auth)
        elif choice == '3':
            screening_recommendations(auth)
        elif choice == '4':
            population_risk_analysis(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")


def conduct_risk_assessment(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to conduct risk assessments.")
        return

    backup_before_operation('conduct_risk_assessment')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT first_name, last_name, age FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()

    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return

    first_name, last_name, age = student

    print(f"\n===== Risk Assessment for {first_name} {last_name} =====")

    # Assessment types
    assessment_types = [
        'General Health Risk',
        'Cardiovascular Risk',
        'Diabetes Risk',
        'Mental Health Risk',
        'Substance Use Risk',
        'Infectious Disease Risk'
    ]

    print("\nAssessment Types:")
    for i, assessment_type in enumerate(assessment_types):
        print(f"{i+1}. {assessment_type}")

    while True:
        type_choice = input("\nSelect assessment type (1-6): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(assessment_types):
            assessment_type = assessment_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    # Get existing health data for risk calculation
    cursor.execute('''
    SELECT condition_name, severity FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))
    conditions = cursor.fetchall()

    cursor.execute('''
    SELECT allergen, severity FROM allergies
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    allergies = cursor.fetchall()

    cursor.execute('''
    SELECT bmi FROM vital_signs
    WHERE student_id = ? AND bmi IS NOT NULL
    ORDER BY measurement_date DESC LIMIT 1
    ''', (student_id,))
    latest_bmi = cursor.fetchone()

    # Calculate risk score based on assessment type
    risk_score = calculate_risk_score(assessment_type, age, conditions, allergies, latest_bmi)

    # Get risk factors
    risk_factors = get_risk_factors(assessment_type, age, conditions, allergies, latest_bmi)

    # Generate recommendations
    recommendations = generate_risk_recommendations(assessment_type, risk_score, risk_factors)

    print("\nRisk Assessment Results:")
    print(f"Assessment Type: {assessment_type}")
    print(f"Risk Score: {risk_score}/100")

    if risk_score < 25:
        risk_level = "Low Risk"
    elif risk_score < 50:
        risk_level = "Moderate Risk"
    elif risk_score < 75:
        risk_level = "High Risk"
    else:
        risk_level = "Very High Risk"

    print(f"Risk Level: {risk_level}")

    if risk_factors:
        print("\nRisk Factors:")
        for factor in risk_factors:
            print(f"- {factor}")

    if recommendations:
        print("\nRecommendations:")
        for recommendation in recommendations:
            print(f"- {recommendation}")

    # Ask for follow-up date
    follow_up_needed = input("\nSchedule follow-up assessment? (y/n): ").lower() == 'y'
    follow_up_date = None

    if follow_up_needed:
        while True:
            follow_up_input = input("Follow-up date (YYYY-MM-DD): ")
            try:
                datetime.strptime(follow_up_input, '%Y-%m-%d')
                follow_up_date = follow_up_input
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

    # Save assessment
    assessed_date = datetime.now().strftime('%Y-%m-%d')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO risk_assessments
    (student_id, assessment_type, risk_score, risk_factors, recommendations,
     assessed_date, assessed_by, follow_up_date, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, assessment_type, risk_score, json.dumps(risk_factors),
          json.dumps(recommendations), assessed_date, auth.current_user['username'],
          follow_up_date, created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'conduct_risk_assessment', 'risk_assessment', cursor.lastrowid)

    print("\nRisk assessment completed and saved!")

    conn.close()

    try:
        from education_system.systems.university.services.bus.integration_bus import (
            publish_health_risk_assessment,
        )
        publish_health_risk_assessment(
            student_id=str(student_id),
            assessment_type=assessment_type,
            risk_score=int(risk_score),
            risk_factors=risk_factors,
            follow_up_date=follow_up_date,
            assessed_by=auth.current_user['username'],
        )
    except Exception:
        logger.debug("Suppressed exception", exc_info=True)
