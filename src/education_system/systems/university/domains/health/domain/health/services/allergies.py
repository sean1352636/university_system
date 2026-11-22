from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.domains.health.domain.health.services.health_context import get_user_student_id
from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection
from education_system.systems.university.infrastructure.i18n import get_text

def manage_allergies(auth):
    if not auth or not auth.current_user:
        print(get_text("health.allergies.login_required", default="You must be logged in to manage allergies."))
        return

    while True:
        print("\n" + get_text("health.allergies.menu_title", default="===== ALLERGIES ====="))
        print(get_text("health.allergies.menu_add", default="1. Add Allergy"))
        print(get_text("health.allergies.menu_view", default="2. View Allergies"))
        print(get_text("health.allergies.menu_update", default="3. Update Allergy"))
        print(get_text("health.allergies.menu_delete", default="4. Delete Allergy"))
        print(get_text("health.allergies.menu_check_interactions", default="5. Check Drug Interactions"))
        print(get_text("health.allergies.menu_return", default="6. Return to Health Portal"))

        choice = input("\n" + get_text("health.allergies.enter_choice", default="Enter your choice: "))

        if choice == '1':
            # Import the function locally to avoid circular imports
            from education_system.systems.university.domains.health.domain.health.records.clinical.allergies import add_allergy
            add_allergy(auth)
        elif choice == '2':
            view_allergies(auth)
        elif choice == '3':
            # Import the function locally to avoid circular imports
            from education_system.systems.university.domains.health.domain.health.records.clinical.allergies import update_allergy
            update_allergy(auth)
        elif choice == '4':
            # Import the function locally to avoid circular imports
            from education_system.systems.university.domains.health.domain.health.records.clinical.allergies import delete_allergy
            delete_allergy(auth)
        elif choice == '5':
            check_drug_interactions(auth)
        elif choice == '6':
            break
        else:
            print(get_text("health.allergies.invalid_choice", default="Invalid choice. Please try again."))

def critical_values_alert(auth):
    """Alert system for critical lab values"""
    if not auth.check_permission('manage_health_records'):
        print(get_text("health.allergies.critical_values_permission_denied", default="You don't have permission to view critical values."))
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
        print(get_text("health.allergies.no_critical_values", default="No critical values are outstanding."))
        conn.close()
        return

    print("\n" + get_text("health.allergies.critical_values_title", default="===== CRITICAL LAB VALUES ====="))

    for result in critical_results:
        result_id, student_id, first_name, last_name, test_name, result_value, reference_range, units, abnormal_flag, resulted_date, ordering_provider = result

        print("\n" + get_text("health.allergies.critical_value_alert_header", default="--- CRITICAL VALUE ---"))
        print(get_text("health.allergies.student_info", first_name=first_name, last_name=last_name, student_id=student_id, default="Student: {first_name} {last_name} ({student_id})"))
        print(get_text("health.allergies.test_label", test_name=test_name, default="Test: {test_name}"))
        print(get_text("health.allergies.result_label", result_value=result_value, units=units, default="Result: {result_value} {units}"))
        print(get_text("health.allergies.reference_range_label", reference_range=reference_range, default="Reference Range: {reference_range}"))
        flag_text = get_text("health.allergies.flag_high", default="HIGH") if abnormal_flag == 'H' else get_text("health.allergies.flag_low", default="LOW")
        print(get_text("health.allergies.flag_label", flag=flag_text, default="Flag: {flag}"))
        print(get_text("health.allergies.date_label", date=resulted_date, default="Date: {date}"))
        print(get_text("health.allergies.ordering_provider_label", provider=ordering_provider, default="Ordering Provider: {provider}"))

        # Check if provider has been notified
        provider_notified = input(get_text("health.allergies.provider_notified_prompt", default="Has the ordering provider been notified? (y/n): ")).lower()
        if provider_notified != 'y':
            print(get_text("health.allergies.urgent_notify_provider", default="URGENT: notify the ordering provider now."))

        print("-" * 50)

    conn.close()

def view_allergies(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print(get_text("health.allergies.view_permission_denied", default="You don't have permission to view allergy records."))
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input(get_text("health.allergies.enter_student_id", default="Enter student ID: "))

        cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
        if cursor.fetchone()[0] == 0:
            print(get_text("health.allergies.student_not_found", default="Error: Student ID not found."))
            conn.close()
            return
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print(get_text("health.allergies.no_student_id_associated", default="Error: No student ID associated with your account."))
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
        print(get_text("health.allergies.no_records_found", default="No allergy records found."))
        conn.close()
        return

    print("\n" + get_text("health.allergies.records_title", default="===== ALLERGY RECORDS ====="))
    for allergy in allergies:
        allergy_id, allergen, severity, reaction, diagnosed_date, provider, verified = allergy

        print("\n" + get_text("health.allergies.id_label", id=allergy_id, default="ID: {id}"))
        print(get_text("health.allergies.allergen_label", allergen=allergen, default="Allergen: {allergen}"))
        print(get_text("health.allergies.severity_label", severity=severity, default="Severity: {severity}"))
        print(get_text("health.allergies.reaction_label", reaction=reaction, default="Reaction: {reaction}"))
        print(get_text("health.allergies.diagnosed_label", date=diagnosed_date, default="Diagnosed: {date}"))
        print(get_text("health.allergies.provider_label", provider=provider, default="Provider: {provider}"))
        verified_text = get_text("health.allergies.yes", default="Yes") if verified else get_text("health.allergies.no", default="No")
        print(get_text("health.allergies.verified_label", verified=verified_text, default="Verified: {verified}"))

        if severity in ['Severe', 'Life-threatening']:
            print(get_text("health.allergies.critical_allergy_alert", default="  *** CRITICAL ALLERGY - see emergency plan ***"))

        print("-" * 30)

    conn.close()

def check_drug_interactions(auth):
    """Check for potential drug interactions with allergies"""
    if not auth.check_permission('manage_health_records'):
        print(get_text("health.allergies.interactions_permission_denied", default="You don't have permission to check drug interactions."))
        return

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input(get_text("health.allergies.enter_student_id", default="Enter student ID: "))

    # Every allergy on record, verified or not.
    #
    # This used to filter on ``verified = 1``. Only a health_provider's own
    # entry is auto-verified (see add_allergy), so an allergy added by an
    # admin was stored unverified and then silently ignored here — the screen
    # reported "no verified allergies" for a student who demonstrably had one.
    # Dropping a known allergy from a safety check is the wrong failure
    # direction, so unverified ones are screened too and flagged as such.
    cursor.execute('''
    SELECT allergen, severity, COALESCE(verified, 0) FROM allergies
    WHERE student_id = ?
    ORDER BY COALESCE(verified, 0) DESC, allergen
    ''', (student_id,))
    all_allergies = cursor.fetchall()

    verified_allergies = [(a, s) for a, s, v in all_allergies if v]
    unverified_allergies = [(a, s) for a, s, v in all_allergies if not v]
    allergies = [(a, s) for a, s, _v in all_allergies]

    cursor.execute('''
    SELECT medication_name, dosage FROM prescriptions
    WHERE student_id = ? AND LOWER(COALESCE(status, '')) = 'active'
    ''', (student_id,))
    medications = cursor.fetchall()

    if not allergies and not medications:
        print(get_text("health.allergies.no_allergies_or_medications", default="No allergies or active medications on record."))
        conn.close()
        return

    print("\n" + get_text("health.allergies.drug_interaction_title", student_id=student_id, default="===== DRUG INTERACTION CHECK: {student_id} ====="))

    if verified_allergies:
        print("\n" + get_text("health.allergies.verified_allergies_header", default="Verified allergies:"))
        for allergen, severity in verified_allergies:
            print(get_text("health.allergies.allergy_list_item", allergen=allergen, severity=severity, default="  - {allergen} ({severity})"))

    if unverified_allergies:
        print("\n" + get_text("health.allergies.unverified_allergies_header",
                              default="Unverified allergies (screened, but not yet confirmed by a provider):"))
        for allergen, severity in unverified_allergies:
            print(get_text("health.allergies.allergy_list_item", allergen=allergen, severity=severity, default="  - {allergen} ({severity})"))
        print(get_text("health.allergies.verify_hint",
                       default="  Confirm these via Allergy Management -> Update Allergy."))

    if not allergies:
        print("\n" + get_text("health.allergies.no_allergies_on_record",
                              default="No allergies on record for this student."))

    if medications:
        print("\n" + get_text("health.allergies.active_medications_header", default="Active medications:"))
        for medication, dosage in medications:
            print(get_text("health.allergies.medication_list_item", medication=medication, dosage=dosage, default="  - {medication} {dosage}"))
    else:
        print("\n" + get_text("health.allergies.no_active_medications",
                              default="No active medications on record for this student."))

    # Allergy/interaction screen over the maintained drug tables.
    potential_interactions = check_basic_interactions(allergies, medications, conn=conn,
                                                      student_id=student_id)

    if potential_interactions:
        print("\n" + get_text("health.allergies.potential_interactions_header", default="Potential interactions:"))
        for interaction in potential_interactions:
            print(get_text("health.allergies.interaction_list_item", interaction=interaction, default="  ! {interaction}"))
    else:
        print("\n" + get_text("health.allergies.no_interactions_detected", default="No interactions detected."))

    print("\n" + get_text("health.allergies.interaction_note", default="Note: this is a basic screen and does not replace pharmacist review."))
    conn.close()

def check_basic_interactions(allergies, medications, conn=None, student_id=None):
    """Allergy and drug-interaction screen over the maintained tables
    (``drug_classes`` / ``drug_class_cross_reactivity`` / ``drug_interactions``,
    via application/health/prescribing). With ``student_id`` the dental
    clinic's allergy record is screened too."""
    from education_system.systems.university.domains.health.application.health import (
        prescribing,
    )
    own = conn is None
    if own:
        conn = get_connection()
    try:
        prescribing.ensure_schema(conn)
        all_allergies = list(allergies)
        if student_id:
            all_allergies += [(a["allergen"], a["severity"]) for a in
                              prescribing.allergies_for(conn, student_id)
                              if a["source"] == "dental record"]
        cross = {(a.lower(), b.lower()) for a, b in conn.execute(
            "SELECT class_a, class_b FROM drug_class_cross_reactivity").fetchall()}
        interactions = []
        meds = [m for m, _ in medications if m]
        for med in meds:
            drugs, classes = prescribing.classify(conn, med)
            for allergen, severity in all_allergies:
                a_drugs, a_classes = prescribing.classify(conn, allergen)
                if (a_drugs & drugs) or (a_classes & classes):
                    interactions.append(get_text("health.allergies.interaction_warning", medication=med, allergen=allergen, severity=severity, default="{medication} may interact with the {allergen} allergy ({severity})"))
                elif any((ac, mc) in cross for ac in a_classes for mc in classes):
                    interactions.append(f"{med}: possible cross-reactivity with the {allergen} "
                                        f"allergy ({severity})")
        for i, med in enumerate(meds):
            for other, severity, text in prescribing.interactions_between(conn, med, meds[i + 1:]):
                interactions.append(f"{med} + {other} ({severity}): {text}")
        return interactions
    finally:
        if own:
            conn.close()
