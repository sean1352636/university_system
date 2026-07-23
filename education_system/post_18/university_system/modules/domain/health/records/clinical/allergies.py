from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.post_18.university_system.modules.domain.health.records.db.audit import log_audit_event


def add_allergy(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to add allergies.")
        return

    backup_before_operation('add_allergy')

    conn = get_connection()
    cursor = conn.cursor()

    # Get student ID
    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return

    allergen = input("Allergen name: ")

    severity_levels = ['Mild', 'Moderate', 'Severe', 'Life-threatening']
    print("\nSeverity Levels:")
    for i, level in enumerate(severity_levels):
        print(f"{i+1}. {level}")

    while True:
        severity_choice = input("\nSelect severity (1-4): ")
        if severity_choice.isdigit() and 1 <= int(severity_choice) <= len(severity_levels):
            severity = severity_levels[int(severity_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    reaction_description = input("Describe typical reaction: ")

    while True:
        diagnosed_date = input("Date diagnosed (YYYY-MM-DD) [today]: ").strip()
        if not diagnosed_date:
            diagnosed_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(diagnosed_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    provider = input("Diagnosing provider: ")
    verified = 1 if auth.current_user['role'] == 'health_provider' else 0
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO allergies
    (student_id, allergen, severity, reaction_description, diagnosed_date, provider, verified, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, allergen, severity, reaction_description, diagnosed_date, provider, verified, created_at))

    conn.commit()

    # Get the ID of the newly inserted allergy record
    allergy_id = cursor.lastrowid

    # Log the correct audit event
    log_audit_event(auth.current_user['id'], 'add_allergy', 'allergy', allergy_id)

    print("\nAllergy record added successfully!")

    # Display severity warning for severe allergies
    if severity in ['Severe', 'Life-threatening']:
        print(f"\n⚠️  CRITICAL ALLERGY ALERT: {severity} {allergen} allergy")
        print("This allergy should be prominently displayed in the patient's medical record.")

    # Check for drug interactions with existing prescriptions
    cursor.execute('''
    SELECT medication_name FROM prescriptions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))

    active_medications = [row[0] for row in cursor.fetchall()]
    if active_medications:
        print(f"\n⚠️  WARNING: Student has active medications. Please review for potential interactions with {allergen}:")
        for med in active_medications:
            print(f"- {med}")
        print("Consider consulting a pharmacist or using a drug interaction checker.")

    conn.close()



def update_allergy(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update allergies.")
        return

    backup_before_operation('update_allergy')

    conn = get_connection()
    cursor = conn.cursor()

    allergy_id = input("Enter allergy ID to update: ")

    cursor.execute('''
    SELECT a.id, s.student_id, s.first_name, s.last_name, a.allergen,
           a.severity, a.reaction_description, a.provider, a.verified
    FROM allergies a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.id = ?
    ''', (allergy_id,))

    allergy = cursor.fetchone()

    if not allergy:
        print("Error: Allergy record not found.")
        conn.close()
        return

    allergy_id, student_id, first_name, last_name, allergen, severity, reaction, provider, verified = allergy

    print("\nCurrent Allergy Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Allergen: {allergen}")
    print(f"Severity: {severity}")
    print(f"Reaction: {reaction}")
    print(f"Provider: {provider}")
    print(f"Verified: {'Yes' if verified else 'No'}")

    print("\nEnter new values (press Enter to keep current):")

    severity_levels = ['Mild', 'Moderate', 'Severe', 'Life-threatening']
    print(f"\nCurrent severity: {severity}")
    print("Severity options: Mild, Moderate, Severe, Life-threatening")
    new_severity = input(f"New severity [{severity}]: ").strip()
    if not new_severity or new_severity not in severity_levels:
        new_severity = severity

    new_reaction = input(f"Reaction description [{reaction}]: ").strip()
    if not new_reaction:
        new_reaction = reaction

    new_provider = input(f"Provider [{provider}]: ").strip()
    if not new_provider:
        new_provider = provider

    verify_input = input(f"Verified ({'Yes' if verified else 'No'}) [y/n]: ").strip().lower()
    if verify_input == 'y':
        new_verified = 1
    elif verify_input == 'n':
        new_verified = 0
    else:
        new_verified = verified

    cursor.execute('''
    UPDATE allergies
    SET severity = ?, reaction_description = ?, provider = ?, verified = ?
    WHERE id = ?
    ''', (new_severity, new_reaction, new_provider, new_verified, allergy_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_allergy', 'allergy', allergy_id)
    print("\nAllergy record updated successfully!")

    # Show severity warning for severe allergies
    if new_severity in ['Severe', 'Life-threatening']:
        print(f"\n⚠️  CRITICAL ALLERGY ALERT: {new_severity} {allergen} allergy")

    conn.close()



def delete_allergy(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to delete allergies.")
        return

    backup_before_operation('delete_allergy')

    conn = get_connection()
    cursor = conn.cursor()

    allergy_id = input("Enter allergy ID to delete: ")

    cursor.execute('''
    SELECT a.id, s.student_id, s.first_name, s.last_name, a.allergen,
           a.severity, a.reaction_description
    FROM allergies a
    JOIN students s ON a.student_id = s.student_id
    WHERE a.id = ?
    ''', (allergy_id,))

    allergy = cursor.fetchone()

    if not allergy:
        print("Error: Allergy record not found.")
        conn.close()
        return

    allergy_id, student_id, first_name, last_name, allergen, severity, reaction = allergy

    print("\nAllergy to delete:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Allergen: {allergen}")
    print(f"Severity: {severity}")
    print(f"Reaction: {reaction}")

    if severity in ['Severe', 'Life-threatening']:
        print("\n⚠️  WARNING: This is a severe allergy record!")

    confirm = input("\nAre you sure you want to delete this allergy record? (yes/no): ").lower()
    if confirm != 'yes':
        print("Deletion cancelled.")
        conn.close()
        return

    cursor.execute('DELETE FROM allergies WHERE id = ?', (allergy_id,))
    conn.commit()

    log_audit_event(auth.current_user['id'], 'delete_allergy', 'allergy', allergy_id,
                   f"Deleted {allergen} allergy for student {student_id}")
    print("\nAllergy record deleted successfully!")
    conn.close()



