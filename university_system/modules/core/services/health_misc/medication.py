from __future__ import annotations

from datetime import datetime, timedelta

from university_system.infrastructure.database.db import get_connection

def track_medication_adherence(auth):
    """Track medication adherence for students"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to track medication adherence.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    cursor.execute('''
    SELECT p.id, p.medication_name, p.dosage, p.frequency, p.start_date
    FROM prescriptions p
    WHERE p.student_id = ? AND p.status = 'active'
    ORDER BY p.start_date DESC
    ''', (student_id,))

    active_prescriptions = cursor.fetchall()

    if not active_prescriptions:
        print("No active prescriptions found for this student.")
        conn.close()
        return

    print(f"\n===== Medication Adherence Tracking for Student {student_id} =====")

    for prescription in active_prescriptions:
        presc_id, medication, dosage, frequency, start_date = prescription

        print(f"\nMedication: {medication} ({dosage})")
        print(f"Frequency: {frequency}")
        print(f"Started: {start_date}")

        # Simple adherence tracking (in real system, this would be more sophisticated)
        adherence = input(f"Patient adherence level (0-100%): ")
        try:
            adherence_pct = int(adherence)
            if 0 <= adherence_pct <= 100:
                if adherence_pct < 80:
                    print("⚠️  Poor adherence - Consider intervention")
                elif adherence_pct < 95:
                    print("⚠️  Moderate adherence - Monitor closely")
                else:
                    print("✅ Good adherence")
            else:
                print("Invalid percentage")
        except ValueError:
            print("Invalid input")

    conn.close()

def manage_refill_reminders(auth):
    """Manage prescription refill reminders"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage refill reminders.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Prescription Refill Reminders =====")

    # Find prescriptions that might need refills soon
    thirty_days_from_now = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT p.id, s.student_id, s.first_name, s.last_name, p.medication_name, 
           p.dosage, p.end_date, p.pharmacy
    FROM prescriptions p
    JOIN students s ON p.student_id = s.student_id
    WHERE p.status = 'active' AND p.end_date IS NOT NULL AND p.end_date <= ?
    ORDER BY p.end_date
    ''', (thirty_days_from_now,))

    upcoming_refills = cursor.fetchall()

    if not upcoming_refills:
        print("No prescriptions requiring refills in the next 30 days.")
        conn.close()
        return

    print("Prescriptions requiring refills in the next 30 days:")

    for prescription in upcoming_refills:
        presc_id, student_id, first_name, last_name, medication, dosage, end_date, pharmacy = prescription

        print(f"\nStudent: {first_name} {last_name} (ID: {student_id})")
        print(f"Medication: {medication} ({dosage})")
        print(f"Expires: {end_date}")
        print(f"Pharmacy: {pharmacy}")

        days_until_expiry = (datetime.strptime(end_date, '%Y-%m-%d') - datetime.now()).days

        if days_until_expiry <= 7:
            print("🔴 URGENT - Expires within 7 days")
        elif days_until_expiry <= 14:
            print("🟡 WARNING - Expires within 14 days")
        else:
            print("🟢 INFO - Expires within 30 days")

        # Option to send reminder
        send_reminder = input("Send refill reminder? (y/n): ").lower()
        if send_reminder == 'y':
            # In a real system, this would send an email or SMS
            print(f"Reminder sent to {first_name} {last_name}")

        print("-" * 30)

    conn.close()
