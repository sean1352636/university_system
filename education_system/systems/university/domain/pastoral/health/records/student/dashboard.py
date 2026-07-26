from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domain.pastoral.health.records.db.audit import log_audit_event
from education_system.systems.university.domain.pastoral.health.services import get_user_student_id
from education_system.systems.university.domain.pastoral.health.services import emergency_information
from education_system.systems.university.domain.pastoral.health.records.student.wellness import manage_wellness_goals, track_personal_metrics
from education_system.systems.university.domain.pastoral.health.records.vaccinations.tracking import immunization_status
from education_system.systems.university.domain.pastoral.health.records.student.resources import student_health_resources
from education_system.systems.university.domain.pastoral.health.appointments.appointment_booking import show_upcoming_appointments


def student_health_dashboard(auth):
    """Personal health dashboard for students"""
    if auth.current_user['role'] != 'student':
        print("This dashboard is only available to students.")
        return

    student_id = get_user_student_id(auth)
    if not student_id:
        print("Error: No student ID associated with your account.")
        return

    while True:
        print("\n===== Your Health Dashboard =====")
        print("1. Health Summary")
        print("2. Upcoming Appointments")
        print("3. Health Reminders")
        print("4. Wellness Goals")
        print("5. Immunization Status")
        print("6. Health Metrics Tracking")
        print("7. Emergency Information")
        print("8. Health Resources")
        print("9. Return to Main Menu")

        choice = input("\nEnter your choice (1-9): ")

        if choice == '1':
            show_personal_health_summary(auth)
        elif choice == '2':
            show_upcoming_appointments(auth)
        elif choice == '3':
            show_health_reminders(auth)
        elif choice == '4':
            manage_wellness_goals(auth)
        elif choice == '5':
            immunization_status(auth)
        elif choice == '6':
            track_personal_metrics(auth)
        elif choice == '7':
            emergency_information(auth)
        elif choice == '8':
            student_health_resources(auth)
        elif choice == '9':
            break
        else:
            print("Invalid choice. Please try again.")



def show_personal_health_summary(auth):
    """Show personal health summary"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()

    # Get student info
    cursor.execute("SELECT first_name, last_name, age FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()

    print(f"\n===== Health Summary for {student[0]} {student[1]} =====")
    print(f"Age: {student[2]}")

    # Recent health records
    cursor.execute('''
    SELECT record_type, record_date, description, provider
    FROM health_records
    WHERE student_id = ?
    ORDER BY record_date DESC
    LIMIT 5
    ''', (student_id,))

    recent_records = cursor.fetchall()

    if recent_records:
        print("\nRecent Health Records:")
        for record_type, record_date, description, provider in recent_records:
            print(f"  {record_date}: {record_type} - {description[:50]}...")

    # Active medical conditions
    cursor.execute('''
    SELECT condition_name, severity FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))

    conditions = cursor.fetchall()

    if conditions:
        print("\nActive Medical Conditions:")
        for condition, severity in conditions:
            print(f"  • {condition} ({severity})")

    # Allergies
    cursor.execute('''
    SELECT allergen, severity FROM allergies
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))

    allergies = cursor.fetchall()

    if allergies:
        print("\nVerified Allergies:")
        for allergen, severity in allergies:
            alert = "🚨" if severity in ['Severe', 'Life-threatening'] else "⚠️"
            print(f"  {alert} {allergen} ({severity})")

    # Latest vital signs
    cursor.execute('''
    SELECT measurement_date, blood_pressure_systolic, blood_pressure_diastolic,
           heart_rate, temperature, weight, bmi
    FROM vital_signs
    WHERE student_id = ?
    ORDER BY measurement_date DESC
    LIMIT 1
    ''', (student_id,))

    vitals = cursor.fetchone()

    if vitals:
        date, bp_sys, bp_dia, hr, temp, weight, bmi = vitals
        print(f"\nLatest Vital Signs ({date}):")
        if bp_sys and bp_dia:
            print(f"  Blood Pressure: {bp_sys}/{bp_dia} mmHg")
        if hr:
            print(f"  Heart Rate: {hr} bpm")
        if temp:
            print(f"  Temperature: {temp}°F")
        if weight:
            print(f"  Weight: {weight} lbs")
        if bmi:
            print(f"  BMI: {bmi}")

    conn.close()



def show_health_reminders(auth):
    """Show health reminders"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()

    reminders = []

    # Check for expiring vaccinations
    ninety_days = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT vaccine_name, expiry_date FROM vaccination_records
    WHERE student_id = ? AND expiry_date <= ? AND verified = 1
    ORDER BY expiry_date
    ''', (student_id, ninety_days))

    expiring_vaccines = cursor.fetchall()

    for vaccine, expiry in expiring_vaccines:
        days_until_expiry = (datetime.strptime(expiry, '%Y-%m-%d') - datetime.now()).days
        if days_until_expiry <= 0:
            reminders.append(f"🔴 EXPIRED: {vaccine} vaccination (expired {expiry})")
        elif days_until_expiry <= 30:
            reminders.append(f"🟡 EXPIRING SOON: {vaccine} vaccination expires {expiry}")
        else:
            reminders.append(f"ℹ️ {vaccine} vaccination expires {expiry}")

    # Check for overdue appointments
    cursor.execute('''
    SELECT COUNT(*) FROM health_appointments
    WHERE student_id = ? AND appointment_date < ? AND status = 'scheduled'
    ''', (student_id, datetime.now().strftime('%Y-%m-%d')))

    overdue_appointments = cursor.fetchone()[0]
    if overdue_appointments > 0:
        reminders.append(f"⚠️ You have {overdue_appointments} overdue appointment(s)")

    # Check for missing emergency contacts
    cursor.execute('''
    SELECT COUNT(*) FROM emergency_contacts WHERE student_id = ?
    ''', (student_id,))

    emergency_contacts = cursor.fetchone()[0]
    if emergency_contacts == 0:
        reminders.append("ℹ️ Please add emergency contact information")

    # Check for missing insurance info
    cursor.execute('''
    SELECT COUNT(*) FROM insurance_information WHERE student_id = ?
    ''', (student_id,))

    insurance_info = cursor.fetchone()[0]
    if insurance_info == 0:
        reminders.append("ℹ️ Please add insurance information")

    print("\n===== Health Reminders =====")

    if reminders:
        for reminder in reminders:
            print(f"  {reminder}")
    else:
        print("  ✅ No health reminders at this time.")

    conn.close()



