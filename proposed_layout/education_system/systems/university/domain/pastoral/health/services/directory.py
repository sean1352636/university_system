from __future__ import annotations

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domain.pastoral.health.services.contacts import get_user_student_id

def specialist_directory(auth):
    """Specialist directory"""
    print(f"\n{_t('health_misc.directory.specialist_directory_title')}")

    # Mock specialist directory
    specialists = [
        {"name": "Dr. Smith", "specialty": "Cardiology", "phone": "(555) 123-4567", "location": "Medical Center A"},
        {"name": "Dr. Johnson", "specialty": "Dermatology", "phone": "(555) 234-5678", "location": "Skin Care Clinic"},
        {"name": "Dr. Williams", "specialty": "Endocrinology", "phone": "(555) 345-6789", "location": "Diabetes Center"},
        {"name": "Dr. Brown", "specialty": "Psychiatry", "phone": "(555) 456-7890", "location": "Mental Health Center"}
    ]

    specialty_filter = input(_t("health_misc.directory.filter_by_specialty_prompt")).strip()

    print(f"\n{_t('health_misc.directory.column_name'):<15} {_t('health_misc.directory.column_specialty'):<15} {_t('health_misc.directory.column_phone'):<15} {_t('health_misc.directory.column_location'):<20}")
    print("-" * 70)

    for specialist in specialists:
        if not specialty_filter or specialty_filter.lower() in specialist['specialty'].lower():
            print(f"{specialist['name']:<15} {specialist['specialty']:<15} {specialist['phone']:<15} {specialist['location']:<20}")

def emergency_information(auth):
    """Emergency information for students"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n{_t('health_misc.directory.emergency_information_title')}")

    print(_t("health_misc.directory.emergency_contacts_header"))
    print(_t("health_misc.directory.campus_emergency"))
    print(_t("health_misc.directory.campus_safety"))
    print(_t("health_misc.directory.health_center"))
    print(_t("health_misc.directory.crisis_hotline"))
    print(_t("health_misc.directory.poison_control"))

    # Show student's emergency contacts
    cursor.execute('''
    SELECT contact_name, relationship, phone_primary, medical_decision_maker
    FROM emergency_contacts
    WHERE student_id = ?
    ORDER BY priority_order
    ''', (student_id,))

    personal_contacts = cursor.fetchall()

    if personal_contacts:
        print(f"\n{_t('health_misc.directory.your_emergency_contacts_header')}")
        for name, relationship, phone, medical_dm in personal_contacts:
            dm_indicator = f" {_t('health_misc.directory.medical_decision_maker')}" if medical_dm else ""
            print(f"   • {name} ({relationship}): {phone}{dm_indicator}")
    else:
        print(f"\n{_t('health_misc.directory.no_emergency_contacts')}")
        print(_t("health_misc.directory.add_contacts_prompt"))

    # Show critical medical information
    cursor.execute('''
    SELECT allergen, severity FROM allergies
    WHERE student_id = ? AND severity IN ('Severe', 'Life-threatening') AND verified = 1
    ''', (student_id,))

    critical_allergies = cursor.fetchall()

    if critical_allergies:
        print(f"\n{_t('health_misc.directory.critical_allergies_header')}")
        for allergen, severity in critical_allergies:
            print(f"   • {allergen} ({severity})")

    # Show active medical conditions
    cursor.execute('''
    SELECT condition_name, severity FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))

    conditions = cursor.fetchall()

    if conditions:
        print(f"\n{_t('health_misc.directory.active_conditions_header')}")
        for condition, severity in conditions:
            print(f"   • {condition} ({severity})")

    conn.close()
