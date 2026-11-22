from __future__ import annotations

from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.domains.health.domain.health.services.contacts import get_user_student_id

def specialist_directory(auth):
    """Specialists the health centre works with: the providers on the
    clinic schedules (with their specialty and location) and the
    specialists students have been referred to."""
    print(f"\n{_t('health_misc.directory.specialist_directory_title', default='===== SPECIALIST DIRECTORY =====')}")
    conn = get_connection(row_factory=False)
    try:
        specialists = {}
        for name, specialty, location in conn.execute(
                "SELECT provider_name, COALESCE(specialty, ''), COALESCE(location, '') FROM "
                "provider_schedules WHERE COALESCE(active, 1) = 1 AND provider_name IS NOT NULL"):
            specialists.setdefault((name, specialty), {"location": location, "source": "clinic"})
        for name, specialty in conn.execute(
                "SELECT DISTINCT specialist_provider, COALESCE(specialty, '') FROM referrals "
                "WHERE COALESCE(specialist_provider, '') <> ''"):
            specialists.setdefault((name, specialty), {"location": "", "source": "referral"})
    finally:
        conn.close()
    if not specialists:
        print("No specialists are on file yet (add provider schedules or referrals).")
        return

    specialty_filter = input(_t("health_misc.directory.filter_by_specialty_prompt")).strip()

    print(f"\n{_t('health_misc.directory.column_name', default='Name'):<22} {_t('health_misc.directory.column_specialty', default='Specialty'):<18} {_t('health_misc.directory.column_location', default='Location'):<22} Source")
    print("-" * 75)
    for (name, specialty), info in sorted(specialists.items()):
        if not specialty_filter or specialty_filter.lower() in specialty.lower():
            print(f"{name:<22} {specialty or '-':<18} {info['location'] or '-':<22} {info['source']}")

def emergency_information(auth):
    """Emergency information for students"""
    student_id = get_user_student_id(auth)
    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n{_t('health_misc.directory.emergency_information_title', default='===== EMERGENCY INFORMATION =====')}")

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
        print(f"\n{_t('health_misc.directory.your_emergency_contacts_header', default='Your Emergency Contacts:')}")
        for name, relationship, phone, medical_dm in personal_contacts:
            dm_indicator = f" {_t('health_misc.directory.medical_decision_maker', default='Medical decision maker: {name}')}" if medical_dm else ""
            print(f"   • {name} ({relationship}): {phone}{dm_indicator}")
    else:
        print(f"\n{_t('health_misc.directory.no_emergency_contacts', default='No emergency contacts on record.')}")
        print(_t("health_misc.directory.add_contacts_prompt"))

    # Show critical medical information
    cursor.execute('''
    SELECT allergen, severity FROM allergies
    WHERE student_id = ? AND severity IN ('Severe', 'Life-threatening') AND verified = 1
    ''', (student_id,))

    critical_allergies = cursor.fetchall()

    if critical_allergies:
        print(f"\n{_t('health_misc.directory.critical_allergies_header', default='Critical Allergies:')}")
        for allergen, severity in critical_allergies:
            print(f"   • {allergen} ({severity})")

    # Show active medical conditions
    cursor.execute('''
    SELECT condition_name, severity FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))

    conditions = cursor.fetchall()

    if conditions:
        print(f"\n{_t('health_misc.directory.active_conditions_header', default='Active Conditions:')}")
        for condition, severity in conditions:
            print(f"   • {condition} ({severity})")

    conn.close()
