from __future__ import annotations

from datetime import datetime, timedelta

from university_system.modules.core.services.health_misc.health_context import get_user_student_id
from university_system.infrastructure.database.db import get_connection

def manage_allergies(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to manage allergies.")
        return

    while True:
        print("\n===== Allergy Management =====")
        print("1. Add Allergy")
        print("2. View Allergies")
        print("3. Update Allergy")
        print("4. Delete Allergy")
        print("5. Check Drug Interactions")
        print("6. Return to Main Menu")

        choice = input("\nEnter your choice (1-6): ")

        if choice == '1':
            # Import the function locally to avoid circular imports
            from university_system.modules.domain.health.records.medical_records import add_allergy
            add_allergy(auth)
        elif choice == '2':
            view_allergies(auth)
        elif choice == '3':
            # Import the function locally to avoid circular imports
            from university_system.modules.domain.health.records.medical_records import update_allergy
            update_allergy(auth)
        elif choice == '4':
            # Import the function locally to avoid circular imports
            from university_system.modules.domain.health.records.medical_records import delete_allergy
            delete_allergy(auth)
        elif choice == '5':
            check_drug_interactions(auth)
        elif choice == '6':
            break
        else:
            print("Invalid choice. Please try again.")

def critical_values_alert(auth):
    """Alert system for critical lab values"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to view critical values.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get critical values from last 7 days
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT lr.id, s.student_id, s.first_name, s.last_name, lr.test_name,
           lr.result_value, lr.reference_range, lr.units, lr.abnormal_flag,
           lr.resulted_date, lr.ordering_provider
    FROM lab_results lr
    JOIN students s ON lr.student_id = s.student_id
    WHERE lr.abnormal_flag IN ('H', 'L') AND lr.resulted_date >= ?
    ORDER BY lr.resulted_date DESC
    ''', (seven_days_ago,))

    critical_results = cursor.fetchall()

    if not critical_results:
        print("No critical lab values in the last 7 days.")
        conn.close()
        return

    print("\n===== Critical Lab Values Alert (Last 7 Days) =====")

    for result in critical_results:
        result_id, student_id, first_name, last_name, test_name, result_value, reference_range, units, abnormal_flag, resulted_date, ordering_provider = result

        print(f"\n🚨 CRITICAL VALUE ALERT")
        print(f"Student: {first_name} {last_name} (ID: {student_id})")
        print(f"Test: {test_name}")
        print(f"Result: {result_value} {units}")
        print(f"Reference Range: {reference_range}")
        print(f"Flag: {'HIGH' if abnormal_flag == 'H' else 'LOW'}")
        print(f"Date: {resulted_date}")
        print(f"Ordering Provider: {ordering_provider}")

        # Check if provider has been notified
        provider_notified = input("Has ordering provider been notified? (y/n): ").lower()
        if provider_notified != 'y':
            print("⚠️  URGENT: Notify ordering provider immediately!")

        print("-" * 50)

    conn.close()

def view_allergies(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view allergies.")
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
    SELECT id, allergen, severity, reaction_description, diagnosed_date, provider, verified
    FROM allergies
    WHERE student_id = ?
    ORDER BY severity DESC, allergen
    ''', (student_id,))

    allergies = cursor.fetchall()

    if not allergies:
        print("No allergy records found.")
        conn.close()
        return

    print("\n===== Allergy Records =====")
    for allergy in allergies:
        allergy_id, allergen, severity, reaction, diagnosed_date, provider, verified = allergy

        print(f"\nID: {allergy_id}")
        print(f"Allergen: {allergen}")
        print(f"Severity: {severity}")
        print(f"Reaction: {reaction}")
        print(f"Diagnosed: {diagnosed_date}")
        print(f"Provider: {provider}")
        print(f"Verified: {'Yes' if verified else 'No'}")

        if severity in ['Severe', 'Life-threatening']:
            print("⚠️  CRITICAL ALLERGY - ALERT REQUIRED")

        print("-" * 30)

    conn.close()

def check_drug_interactions(auth):
    """Check for potential drug interactions with allergies"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to check drug interactions.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Get all allergies and active medications
    cursor.execute('''
    SELECT allergen, severity FROM allergies 
    WHERE student_id = ? AND verified = 1
    ''', (student_id,))
    allergies = cursor.fetchall()

    cursor.execute('''
    SELECT medication_name, dosage FROM prescriptions 
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))
    medications = cursor.fetchall()

    if not allergies and not medications:
        print("No allergies or active medications found.")
        conn.close()
        return

    print(f"\n===== Drug Interaction Check for Student {student_id} =====")

    print("\nVerified Allergies:")
    for allergen, severity in allergies:
        print(f"- {allergen} ({severity})")

    print("\nActive Medications:")
    for medication, dosage in medications:
        print(f"- {medication} ({dosage})")

    # Simple interaction checking (in a real system, this would use a drug database)
    potential_interactions = check_basic_interactions(allergies, medications)

    if potential_interactions:
        print("\n⚠️  POTENTIAL INTERACTIONS DETECTED:")
        for interaction in potential_interactions:
            print(f"- {interaction}")
    else:
        print("\n✅ No obvious interactions detected.")

    print("\nNote: This is a basic check. Always consult a pharmacist or physician for comprehensive interaction analysis.")
    conn.close()

def check_basic_interactions(allergies, medications):
    """Basic drug interaction checking"""
    interactions = []

    # Simple allergy-medication checking
    allergy_map = {
        'penicillin': ['amoxicillin', 'ampicillin', 'penicillin'],
        'sulfa': ['sulfamethoxazole', 'trimethoprim'],
        'aspirin': ['aspirin', 'ibuprofen', 'naproxen'],
        'latex': ['some injectable medications'],
    }

    for allergen, severity in allergies:
        allergen_lower = allergen.lower()
        for key, contraindicated_meds in allergy_map.items():
            if key in allergen_lower:
                for med, _ in medications:
                    for contraindicated in contraindicated_meds:
                        if contraindicated.lower() in med.lower():
                            interactions.append(f"{med} may interact with {allergen} allergy ({severity})")

    return interactions
