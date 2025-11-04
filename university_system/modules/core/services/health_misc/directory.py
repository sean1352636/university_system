from __future__ import annotations

from university_system.infrastructure.database.db import get_connection

def specialist_directory(auth):
    """Specialist directory"""
    print("\n===== Specialist Directory =====")

    # Mock specialist directory
    specialists = [
        {"name": "Dr. Smith", "specialty": "Cardiology", "phone": "(555) 123-4567", "location": "Medical Center A"},
        {"name": "Dr. Johnson", "specialty": "Dermatology", "phone": "(555) 234-5678", "location": "Skin Care Clinic"},
        {"name": "Dr. Williams", "specialty": "Endocrinology", "phone": "(555) 345-6789", "location": "Diabetes Center"},
        {"name": "Dr. Brown", "specialty": "Psychiatry", "phone": "(555) 456-7890", "location": "Mental Health Center"}
    ]

    specialty_filter = input("Filter by specialty (leave blank for all): ").strip()

    print(f"\n{'Name':<15} {'Specialty':<15} {'Phone':<15} {'Location':<20}")
    print("-" * 70)

    for specialist in specialists:
        if not specialty_filter or specialty_filter.lower() in specialist['specialty'].lower():
            print(f"{specialist['name']:<15} {specialist['specialty']:<15} {specialist['phone']:<15} {specialist['location']:<20}")

def emergency_information(auth):
    """Emergency information for students"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Emergency Information =====")

    print("🚨 EMERGENCY CONTACTS:")
    print("   • Campus Emergency: 911")
    print("   • Campus Safety: (555) 123-SAFE")
    print("   • Health Center: (555) 123-4567")
    print("   • Crisis Hotline: 988")
    print("   • Poison Control: 1-800-222-1222")

    # Show student's emergency contacts
    cursor.execute('''
    SELECT contact_name, relationship, phone_primary, medical_decision_maker
    FROM emergency_contacts
    WHERE student_id = ?
    ORDER BY priority_order
    ''', (student_id,))

    personal_contacts = cursor.fetchall()

    if personal_contacts:
        print(f"\n👥 YOUR EMERGENCY CONTACTS:")
        for name, relationship, phone, medical_dm in personal_contacts:
            dm_indicator = " (Medical Decision Maker)" if medical_dm else ""
            print(f"   • {name} ({relationship}): {phone}{dm_indicator}")
    else:
        print(f"\n⚠️ No personal emergency contacts on file.")
        print("   Please add emergency contacts through the health portal.")

    # Show critical medical information
    cursor.execute('''
    SELECT allergen, severity FROM allergies
    WHERE student_id = ? AND severity IN ('Severe', 'Life-threatening') AND verified = 1
    ''', (student_id,))

    critical_allergies = cursor.fetchall()

    if critical_allergies:
        print(f"\n🚨 CRITICAL ALLERGIES:")
        for allergen, severity in critical_allergies:
            print(f"   • {allergen} ({severity})")

    # Show active medical conditions
    cursor.execute('''
    SELECT condition_name, severity FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))

    conditions = cursor.fetchall()

    if conditions:
        print(f"\n📋 ACTIVE MEDICAL CONDITIONS:")
        for condition, severity in conditions:
            print(f"   • {condition} ({severity})")

    conn.close()
