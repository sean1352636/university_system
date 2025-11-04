from __future__ import annotations

from datetime import datetime, timedelta

from university_system.infrastructure.database.db import get_connection

def critical_alerts_dashboard(auth):
    """Show critical alerts for provider"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Critical Alerts Dashboard =====")

    alerts = []

    # Critical lab values (last 7 days)
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT lr.test_name, lr.result_value, lr.resulted_date, s.first_name, s.last_name, s.student_id
    FROM lab_results lr
    JOIN students s ON lr.student_id = s.student_id
    WHERE lr.abnormal_flag IN ('H', 'L') AND lr.resulted_date >= ?
    ORDER BY lr.resulted_date DESC
    ''', (seven_days_ago,))

    critical_labs = cursor.fetchall()

    for test, value, date, first_name, last_name, student_id in critical_labs:
        alerts.append(f"🚨 CRITICAL LAB: {test} = {value} for {first_name} {last_name} ({student_id}) on {date}")

    # Severe allergic reactions in vaccinations
    cursor.execute('''
    SELECT vr.vaccine_name, vr.administered_date, s.first_name, s.last_name, s.student_id
    FROM vaccination_records vr
    JOIN students s ON vr.student_id = s.student_id
    WHERE vr.adverse_reaction = 1 AND vr.administered_date >= ?
    ''', (seven_days_ago,))

    adverse_reactions = cursor.fetchall()

    for vaccine, date, first_name, last_name, student_id in adverse_reactions:
        alerts.append(f"⚠️ ADVERSE REACTION: {vaccine} for {first_name} {last_name} ({student_id}) on {date}")

    # Overdue follow-ups
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT ra.follow_up_date, s.first_name, s.last_name, s.student_id, ra.assessment_type
    FROM risk_assessments ra
    JOIN students s ON ra.student_id = s.student_id
    WHERE ra.follow_up_date < ? AND ra.follow_up_date IS NOT NULL
    ''', (today,))

    overdue_followups = cursor.fetchall()

    for follow_date, first_name, last_name, student_id, assessment in overdue_followups:
        alerts.append(f"📋 OVERDUE FOLLOW-UP: {assessment} for {first_name} {last_name} ({student_id}) due {follow_date}")

    if alerts:
        for alert in alerts:
            print(f"  {alert}")
    else:
        print("  ✅ No critical alerts at this time.")

    conn.close()

def generate_custom_report(auth):
    """Generate custom reports based on user criteria"""
    print("\n===== Custom Report Generator =====")
    print("Available Report Types:")
    print("1. Student Health Summary")
    print("2. Vaccination Status Report")
    print("3. Appointment Schedule Report")
    print("4. Health Condition Analysis")
    print("5. Provider Performance Report")

    choice = input("\nSelect report type (1-5): ").strip()

    if choice == '1':
        from university_system.modules.domain.health.records.medical_records import generate_student_health_summary
        return generate_student_health_summary(auth)
    elif choice == '2':
        from university_system.modules.domain.health.records.medical_records import generate_vaccination_status_report
        return generate_vaccination_status_report(auth)
    elif choice == '3':
        from university_system.modules.domain.health.appointments.appointment_booking import generate_appointment_schedule_report
        return generate_appointment_schedule_report(auth)
    elif choice == '4':
        from university_system.modules.domain.health.records.medical_records import generate_health_condition_analysis
        return generate_health_condition_analysis(auth)
    elif choice == '5':
        from university_system.modules.domain.health.appointments.appointment_booking import generate_provider_performance_report
        return generate_provider_performance_report(auth)
    else:
        print("Invalid selection.")
