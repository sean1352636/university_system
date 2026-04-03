from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.services import (
    track_medication_adherence, manage_refill_reminders,
)


def manage_prescriptions(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to manage prescriptions.")
        return

    while True:
        print("\n===== Prescription Management =====")
        print("1. Add Prescription")
        print("2. View Prescriptions")
        print("3. Update Prescription Status")
        print("4. Medication Adherence Tracking")
        print("5. Prescription Refill Reminders")
        print("6. Return to Main Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            add_prescription(auth)
        elif choice == '2':
            view_prescriptions(auth)
        elif choice == '3':
            update_prescription_status(auth)
        elif choice == '4':
            track_medication_adherence(auth)
        elif choice == '5':
            manage_refill_reminders(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")



def add_prescription(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add prescriptions.")
        return

    backup_before_operation('add_prescription')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return

    # Check for allergies first
    cursor.execute('''
    SELECT allergen, severity FROM allergies
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    allergies = cursor.fetchall()

    if allergies:
        print("\n⚠️  ALLERGY ALERT - Patient has the following verified allergies:")
        for allergen, severity in allergies:
            print(f"- {allergen} ({severity})")

        proceed = input("\nHave you checked for drug interactions? (y/n): ").lower()
        if proceed != 'y':
            print("Please check for interactions before prescribing.")
            conn.close()
            return

    medication_name = input("Medication name: ")
    dosage = input("Dosage (e.g., 500mg): ")
    frequency = input("Frequency (e.g., twice daily): ")

    while True:
        prescribed_date = input("Prescribed date (YYYY-MM-DD) [today]: ").strip()
        if not prescribed_date:
            prescribed_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(prescribed_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        start_date = input("Start date (YYYY-MM-DD) [today]: ").strip()
        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        end_date = input("End date (YYYY-MM-DD) [leave blank for ongoing]: ").strip()
        if not end_date:
            end_date = None
            break
        try:
            datetime.strptime(end_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    prescriber = input(f"Prescriber [Dr. {auth.current_user['username']}]: ").strip()
    if not prescriber:
        prescriber = f"Dr. {auth.current_user['username']}"

    pharmacy = input("Pharmacy: ")
    notes = input("Additional notes: ")

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO prescriptions
    (student_id, medication_name, dosage, frequency, prescribed_date, start_date, end_date,
     prescriber, pharmacy, status, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, medication_name, dosage, frequency, prescribed_date, start_date,
          end_date, prescriber, pharmacy, 'active', notes, created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_prescription', 'prescription', cursor.lastrowid)
    print("\nPrescription added successfully!")
    conn.close()



def view_prescriptions(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view prescriptions.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID: ")

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print("Error: Student ID not found.")
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

    cursor.execute('''
    SELECT id, medication_name, dosage, frequency, prescribed_date, start_date, end_date,
           prescriber, pharmacy, status, notes
    FROM prescriptions
    WHERE student_id = ?
    ORDER BY prescribed_date DESC
    ''', (student_id,))

    prescriptions = cursor.fetchall()

    if not prescriptions:
        print("No prescription records found.")
        conn.close()
        return

    print("\n===== Prescription Records =====")
    for prescription in prescriptions:
        presc_id, medication, dosage, frequency, prescribed_date, start_date, end_date, prescriber, pharmacy, status, notes = prescription

        print(f"\nID: {presc_id}")
        print(f"Medication: {medication}")
        print(f"Dosage: {dosage}")
        print(f"Frequency: {frequency}")
        print(f"Prescribed: {prescribed_date}")
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date if end_date else 'Ongoing'}")
        print(f"Prescriber: {prescriber}")
        print(f"Pharmacy: {pharmacy}")
        print(f"Status: {status}")
        if notes:
            print(f"Notes: {notes}")

        # Check if prescription is expired
        if end_date and datetime.strptime(end_date, '%Y-%m-%d') < datetime.now():
            print("⚠️  EXPIRED")
        elif status == 'active':
            print("✅ ACTIVE")

        print("-" * 30)

    conn.close()



def update_prescription_status(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update prescriptions.")
        return

    backup_before_operation('update_prescription_status')

    conn = get_connection()
    cursor = conn.cursor()

    prescription_id = input("Enter prescription ID to update: ")

    cursor.execute('''
    SELECT p.id, s.student_id, s.first_name, s.last_name, p.medication_name,
           p.dosage, p.status
    FROM prescriptions p
    JOIN students s ON p.student_id = s.student_id
    WHERE p.id = ?
    ''', (prescription_id,))

    prescription = cursor.fetchone()

    if not prescription:
        print("Error: Prescription not found.")
        conn.close()
        return

    presc_id, student_id, first_name, last_name, medication, dosage, current_status = prescription

    print(f"\nPrescription Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Medication: {medication} ({dosage})")
    print(f"Current Status: {current_status}")

    status_options = ['active', 'completed', 'discontinued', 'on_hold']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")

    while True:
        choice = input("\nSelect new status (1-4): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    cursor.execute('''
    UPDATE prescriptions SET status = ? WHERE id = ?
    ''', (new_status, prescription_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_prescription_status', 'prescription', prescription_id, f"Status changed from {current_status} to {new_status}")
    print(f"\nPrescription status updated to '{new_status}' successfully!")
    conn.close()



