from __future__ import annotations

from datetime import datetime, timedelta

from education_system.university_system.modules.domain.health.services.health_context import get_user_student_id
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.utils.i18n import get_text

def manage_allergies(auth):
    if not auth or not auth.current_user:
        print(get_text("health.allergies.login_required"))
        return

    while True:
        print("\n" + get_text("health.allergies.menu_title"))
        print(get_text("health.allergies.menu_add"))
        print(get_text("health.allergies.menu_view"))
        print(get_text("health.allergies.menu_update"))
        print(get_text("health.allergies.menu_delete"))
        print(get_text("health.allergies.menu_check_interactions"))
        print(get_text("health.allergies.menu_return"))

        choice = input("\n" + get_text("health.allergies.enter_choice"))

        if choice == '1':
            # Import the function locally to avoid circular imports
            from education_system.university_system.modules.domain.health.records.clinical.allergies import add_allergy
            add_allergy(auth)
        elif choice == '2':
            view_allergies(auth)
        elif choice == '3':
            # Import the function locally to avoid circular imports
            from education_system.university_system.modules.domain.health.records.clinical.allergies import update_allergy
            update_allergy(auth)
        elif choice == '4':
            # Import the function locally to avoid circular imports
            from education_system.university_system.modules.domain.health.records.clinical.allergies import delete_allergy
            delete_allergy(auth)
        elif choice == '5':
            check_drug_interactions(auth)
        elif choice == '6':
            break
        else:
            print(get_text("health.allergies.invalid_choice"))

def critical_values_alert(auth):
    """Alert system for critical lab values"""
    if not auth.check_permission('manage_health_records'):
        print(get_text("health.allergies.critical_values_permission_denied"))
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
        print(get_text("health.allergies.no_critical_values"))
        conn.close()
        return

    print("\n" + get_text("health.allergies.critical_values_title"))

    for result in critical_results:
        result_id, student_id, first_name, last_name, test_name, result_value, reference_range, units, abnormal_flag, resulted_date, ordering_provider = result

        print("\n" + get_text("health.allergies.critical_value_alert_header"))
        print(get_text("health.allergies.student_info", first_name=first_name, last_name=last_name, student_id=student_id))
        print(get_text("health.allergies.test_label", test_name=test_name))
        print(get_text("health.allergies.result_label", result_value=result_value, units=units))
        print(get_text("health.allergies.reference_range_label", reference_range=reference_range))
        flag_text = get_text("health.allergies.flag_high") if abnormal_flag == 'H' else get_text("health.allergies.flag_low")
        print(get_text("health.allergies.flag_label", flag=flag_text))
        print(get_text("health.allergies.date_label", date=resulted_date))
        print(get_text("health.allergies.ordering_provider_label", provider=ordering_provider))

        # Check if provider has been notified
        provider_notified = input(get_text("health.allergies.provider_notified_prompt")).lower()
        if provider_notified != 'y':
            print(get_text("health.allergies.urgent_notify_provider"))

        print("-" * 50)

    conn.close()

def view_allergies(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print(get_text("health.allergies.view_permission_denied"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input(get_text("health.allergies.enter_student_id"))

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print(get_text("health.allergies.student_not_found"))
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print(get_text("health.allergies.no_student_id_associated"))
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
        print(get_text("health.allergies.no_records_found"))
        conn.close()
        return

    print("\n" + get_text("health.allergies.records_title"))
    for allergy in allergies:
        allergy_id, allergen, severity, reaction, diagnosed_date, provider, verified = allergy

        print("\n" + get_text("health.allergies.id_label", id=allergy_id))
        print(get_text("health.allergies.allergen_label", allergen=allergen))
        print(get_text("health.allergies.severity_label", severity=severity))
        print(get_text("health.allergies.reaction_label", reaction=reaction))
        print(get_text("health.allergies.diagnosed_label", date=diagnosed_date))
        print(get_text("health.allergies.provider_label", provider=provider))
        verified_text = get_text("health.allergies.yes") if verified else get_text("health.allergies.no")
        print(get_text("health.allergies.verified_label", verified=verified_text))

        if severity in ['Severe', 'Life-threatening']:
            print(get_text("health.allergies.critical_allergy_alert"))

        print("-" * 30)

    conn.close()

def check_drug_interactions(auth):
    """Check for potential drug interactions with allergies"""
    if not auth.check_permission('manage_health_records'):
        print(get_text("health.allergies.interactions_permission_denied"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input(get_text("health.allergies.enter_student_id"))

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
        print(get_text("health.allergies.no_allergies_or_medications"))
        conn.close()
        return

    print("\n" + get_text("health.allergies.drug_interaction_title", student_id=student_id))

    print("\n" + get_text("health.allergies.verified_allergies_header"))
    for allergen, severity in allergies:
        print(get_text("health.allergies.allergy_list_item", allergen=allergen, severity=severity))

    print("\n" + get_text("health.allergies.active_medications_header"))
    for medication, dosage in medications:
        print(get_text("health.allergies.medication_list_item", medication=medication, dosage=dosage))

    # Simple interaction checking (in a real system, this would use a drug database)
    potential_interactions = check_basic_interactions(allergies, medications)

    if potential_interactions:
        print("\n" + get_text("health.allergies.potential_interactions_header"))
        for interaction in potential_interactions:
            print(get_text("health.allergies.interaction_list_item", interaction=interaction))
    else:
        print("\n" + get_text("health.allergies.no_interactions_detected"))

    print("\n" + get_text("health.allergies.interaction_note"))
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
                            interactions.append(get_text("health.allergies.interaction_warning", medication=med, allergen=allergen, severity=severity))

    return interactions
