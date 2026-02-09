from __future__ import annotations

from datetime import datetime, timedelta

from university_system.modules.domain.health.services.audit import log_audit_event
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.database.db import get_connection
from university_system.modules.shared.utils.i18n import get_text as _t

def generate_disease_surveillance_report(auth, start_date, end_date):
    """Generate disease surveillance report"""
    conn = get_connection()
    cursor = conn.cursor()

    report_content = []
    report_content.append(_t("health_misc.surveillance.report_title"))
    report_content.append("=" * 28)
    report_content.append(_t("health_misc.surveillance.period", start_date=start_date, end_date=end_date))
    report_content.append(_t("health_misc.surveillance.generated", timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    report_content.append("")

    # Disease cases by type
    cursor.execute('''
    SELECT disease_name, COUNT(*) as case_count,
           SUM(CASE WHEN severity IN ('Severe', 'Critical') THEN 1 ELSE 0 END) as severe_cases,
           SUM(CASE WHEN contact_tracing_needed = 1 THEN 1 ELSE 0 END) as requiring_tracing
    FROM disease_surveillance
    WHERE case_date BETWEEN ? AND ?
    GROUP BY disease_name
    ORDER BY case_count DESC
    ''', (start_date, end_date))

    disease_data = cursor.fetchall()

    if disease_data:
        total_cases = sum(count for _, count, _, _ in disease_data)
        report_content.append(_t("health_misc.surveillance.disease_cases_by_type"))
        report_content.append("-" * 20)
        report_content.append(_t("health_misc.surveillance.total_cases", count=total_cases))
        report_content.append("")

        for disease, count, severe, tracing in disease_data:
            report_content.append(_t("health_misc.surveillance.disease_case_count", disease=disease, count=count))
            report_content.append(_t("health_misc.surveillance.severe_critical", count=severe))
            report_content.append(_t("health_misc.surveillance.requiring_contact_tracing", count=tracing))

    # Status summary
    cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM disease_surveillance
    WHERE case_date BETWEEN ? AND ?
    GROUP BY status
    ''', (start_date, end_date))

    status_data = cursor.fetchall()

    if status_data:
        report_content.append("")
        report_content.append(_t("health_misc.surveillance.case_status_summary"))
        report_content.append("-" * 19)
        for status, count in status_data:
            report_content.append(_t("health_misc.surveillance.status_count", status=status, count=count))

    # Display report
    for line in report_content:
        print(line)

    conn.close()

def conduct_contact_tracing(auth):
    if not auth.check_permission('issue_health_advisories'):
        print(_t("health_misc.surveillance.no_permission_contact_tracing"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    case_id = input(_t("health_misc.surveillance.enter_case_id_for_tracing"))

    cursor.execute('''
    SELECT ds.id, s.student_id, s.first_name, s.last_name, ds.disease_name,
           ds.case_date, ds.symptoms, ds.severity
    FROM disease_surveillance ds
    JOIN students s ON ds.student_id = s.student_id
    WHERE ds.id = ?
    ''', (case_id,))

    case = cursor.fetchone()

    if not case:
        print(_t("health_misc.surveillance.error_case_not_found"))
        conn.close()
        return

    case_id, student_id, first_name, last_name, disease, case_date, symptoms, severity = case

    print(_t("health_misc.surveillance.contact_tracing_header", case_id=case_id))
    print(_t("health_misc.surveillance.patient_info", first_name=first_name, last_name=last_name, student_id=student_id))
    print(_t("health_misc.surveillance.disease_label", disease=disease))
    print(_t("health_misc.surveillance.case_date_label", case_date=case_date))
    print(_t("health_misc.surveillance.severity_label", severity=severity))

    # Contact tracing parameters
    print(_t("health_misc.surveillance.contact_tracing_parameters"))

    # Exposure period
    exposure_start = input(_t("health_misc.surveillance.exposure_start_date_prompt"))
    exposure_end = input(_t("health_misc.surveillance.exposure_end_date_prompt"))

    # Contact categories
    print(_t("health_misc.surveillance.contact_categories_header"))
    print(_t("health_misc.surveillance.contact_category_household"))
    print(_t("health_misc.surveillance.contact_category_close"))
    print(_t("health_misc.surveillance.contact_category_casual"))
    print(_t("health_misc.surveillance.contact_category_healthcare"))

    # Gather contact information
    contacts = []

    print(_t("health_misc.surveillance.enter_contact_info_prompt"))
    while True:
        contact_name = input(_t("health_misc.surveillance.contact_name_prompt")).strip()
        if contact_name.lower() == 'done':
            break

        contact_type = input(_t("health_misc.surveillance.contact_type_prompt"))
        contact_date = input(_t("health_misc.surveillance.last_contact_date_prompt"))
        contact_duration = input(_t("health_misc.surveillance.contact_duration_prompt"))

        contacts.append({
            'name': contact_name,
            'type': contact_type,
            'date': contact_date,
            'duration': contact_duration
        })

    print(_t("health_misc.surveillance.contact_tracing_summary_header"))
    print(_t("health_misc.surveillance.total_contacts_identified", count=len(contacts)))

    # Risk assessment for each contact
    high_risk_contacts = []
    moderate_risk_contacts = []
    low_risk_contacts = []

    for contact in contacts:
        try:
            from university_system.modules.domain.health.portal.data_privacy import assess_contact_risk
            risk_level = assess_contact_risk(contact, disease, severity)
        except ImportError:
            risk_level = "low"  # fallback if security module not available
        contact['risk'] = risk_level

        if risk_level == 'High':
            high_risk_contacts.append(contact)
        elif risk_level == 'Moderate':
            moderate_risk_contacts.append(contact)
        else:
            low_risk_contacts.append(contact)

    print(_t("health_misc.surveillance.risk_classification_header"))
    print(_t("health_misc.surveillance.high_risk_count", count=len(high_risk_contacts)))
    print(_t("health_misc.surveillance.moderate_risk_count", count=len(moderate_risk_contacts)))
    print(_t("health_misc.surveillance.low_risk_count", count=len(low_risk_contacts)))

    # Recommendations
    print(_t("health_misc.surveillance.recommendations_header"))

    if high_risk_contacts:
        print(_t("health_misc.surveillance.high_risk_immediate_actions"))
        for contact in high_risk_contacts:
            print(_t("health_misc.surveillance.high_risk_contact_action", name=contact['name']))

    if moderate_risk_contacts:
        print(_t("health_misc.surveillance.moderate_risk_monitor"))
        for contact in moderate_risk_contacts:
            print(_t("health_misc.surveillance.moderate_risk_contact_action", name=contact['name']))

    # Update case record
    cursor.execute('''
    UPDATE disease_surveillance 
    SET contact_tracing_completed = 1, contacts_identified = ?
    WHERE id = ?
    ''', (len(contacts), case_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'conduct_contact_tracing', 'disease_surveillance', case_id,
                   f"Identified {len(contacts)} contacts")

    print(_t("health_misc.surveillance.contact_tracing_completed", case_id=case_id))
    conn.close()

def investigate_outbreak(auth):
    if not auth.check_permission('issue_health_advisories'):
        print(_t("health_misc.surveillance.no_permission_outbreak_investigation"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    print(_t("health_misc.surveillance.outbreak_investigation_header"))

    # Identify potential outbreaks
    print(_t("health_misc.surveillance.scanning_outbreaks"))

    # Look for clusters of same disease in recent period
    fourteen_days_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT disease_name, COUNT(*) as case_count,
           MIN(case_date) as first_case, MAX(case_date) as last_case
    FROM disease_surveillance
    WHERE case_date >= ? AND status IN ('under_investigation', 'confirmed')
    GROUP BY disease_name
    HAVING COUNT(*) >= 3
    ORDER BY case_count DESC
    ''', (fourteen_days_ago,))

    potential_outbreaks = cursor.fetchall()

    if not potential_outbreaks:
        print(_t("health_misc.surveillance.no_outbreaks_detected"))
        conn.close()
        return

    print(_t("health_misc.surveillance.potential_outbreaks_detected"))
    for i, (disease, count, first_case, last_case) in enumerate(potential_outbreaks):
        print(_t("health_misc.surveillance.outbreak_item", index=i+1, disease=disease, count=count, first_case=first_case, last_case=last_case))

    while True:
        choice = input(_t("health_misc.surveillance.select_outbreak_prompt", max_choice=len(potential_outbreaks)))
        if choice.isdigit() and 1 <= int(choice) <= len(potential_outbreaks):
            selected_outbreak = potential_outbreaks[int(choice) - 1]
            break
        print(_t("health_misc.surveillance.invalid_choice_try_again"))

    disease_name, case_count, first_case, last_case = selected_outbreak

    print(_t("health_misc.surveillance.investigating_outbreak_header", disease_name=disease_name))
    print(_t("health_misc.surveillance.cases_count", count=case_count))
    print(_t("health_misc.surveillance.period", start_date=first_case, end_date=last_case))

    # Get detailed case information
    cursor.execute('''
    SELECT ds.id, s.student_id, s.first_name, s.last_name, ds.case_date,
           ds.symptoms, ds.severity, ds.contact_tracing_needed
    FROM disease_surveillance ds
    JOIN students s ON ds.student_id = s.student_id
    WHERE ds.disease_name = ? AND ds.case_date >= ?
    ORDER BY ds.case_date
    ''', (disease_name, fourteen_days_ago))

    cases = cursor.fetchall()

    print(_t("health_misc.surveillance.case_details_header"))
    for case in cases:
        case_id, student_id, first_name, last_name, case_date, symptoms, severity, contact_tracing = case
        print(_t("health_misc.surveillance.case_detail_line", case_id=case_id, first_name=first_name, last_name=last_name, case_date=case_date, severity=severity))

    # Outbreak investigation steps
    print(_t("health_misc.surveillance.outbreak_investigation_protocol_header"))

    # 1. Case definition
    case_definition = input(_t("health_misc.surveillance.define_case_criteria_prompt"))

    # 2. Case finding
    additional_cases = input(_t("health_misc.surveillance.additional_cases_prompt"))

    # 3. Hypothesis generation
    print(_t("health_misc.surveillance.possible_sources_header"))
    source_hypotheses = input(_t("health_misc.surveillance.suspected_sources_prompt"))

    # 4. Control measures
    print(_t("health_misc.surveillance.control_measures_implemented"))
    control_measures = []

    measures = [
        _t("health_misc.surveillance.measure_isolation"),
        _t("health_misc.surveillance.measure_quarantine"),
        _t("health_misc.surveillance.measure_enhanced_surveillance"),
        _t("health_misc.surveillance.measure_environmental_cleaning"),
        _t("health_misc.surveillance.measure_vaccination"),
        _t("health_misc.surveillance.measure_health_education"),
        _t("health_misc.surveillance.measure_facility_restrictions")
    ]

    print(_t("health_misc.surveillance.available_control_measures"))
    for i, measure in enumerate(measures):
        print(f"{i+1}. {measure}")

    while True:
        measure_choice = input(_t("health_misc.surveillance.select_control_measure_prompt")).strip()
        if measure_choice.lower() == 'done':
            break

        try:
            measure_idx = int(measure_choice) - 1
            if 0 <= measure_idx < len(measures):
                control_measures.append(measures[measure_idx])
                print(_t("health_misc.surveillance.added_measure", measure=measures[measure_idx]))
            else:
                print(_t("health_misc.surveillance.invalid_choice"))
        except ValueError:
            print(_t("health_misc.surveillance.invalid_input"))

    # Record outbreak investigation
    investigation_date = datetime.now().strftime('%Y-%m-%d')

    # Create outbreak record (this would be in an outbreaks table in a full system)
    outbreak_summary = {
        'disease': disease_name,
        'cases': case_count,
        'period': f"{first_case} to {last_case}",
        'case_definition': case_definition,
        'suspected_source': source_hypotheses,
        'control_measures': control_measures,
        'investigation_date': investigation_date,
        'investigator': auth.current_user['username']
    }

    print(_t("health_misc.surveillance.outbreak_investigation_summary_header"))
    for key, value in outbreak_summary.items():
        print(_t("health_misc.surveillance.summary_key_value", key=key.replace('_', ' ').title(), value=value))

    log_audit_event(auth.current_user['id'], 'investigate_outbreak', 'outbreak', 0,
                   f"{disease_name} outbreak - {case_count} cases")

    # Update case statuses
    update_cases = input(_t("health_misc.surveillance.update_cases_confirmed_prompt")).lower()
    if update_cases == 'y':
        cursor.execute('''
        UPDATE disease_surveillance
        SET status = 'confirmed'
        WHERE disease_name = ? AND case_date >= ?
        ''', (disease_name, fourteen_days_ago))

        conn.commit()
        print(_t("health_misc.surveillance.case_statuses_updated"))

    print(_t("health_misc.surveillance.outbreak_investigation_completed"))
    conn.close()

def analyze_disease_trends(auth):
    if not auth.check_permission('issue_health_advisories'):
        print(_t("health_misc.surveillance.no_permission_analyze_trends"))
        return

    conn = get_connection()
    cursor = conn.cursor()

    print(_t("health_misc.surveillance.disease_trends_header"))

    # Monthly disease trends (last 12 months)
    twelve_months_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT 
        strftime('%Y-%m', case_date) as month,
        disease_name,
        COUNT(*) as case_count
    FROM disease_surveillance
    WHERE case_date >= ?
    GROUP BY strftime('%Y-%m', case_date), disease_name
    ORDER BY month, case_count DESC
    ''', (twelve_months_ago,))

    monthly_trends = cursor.fetchall()

    if monthly_trends:
        print(_t("health_misc.surveillance.monthly_disease_trends"))
        current_month = ""
        for month, disease, count in monthly_trends:
            if month != current_month:
                print(_t("health_misc.surveillance.month_header", month=month))
                current_month = month
            print(_t("health_misc.surveillance.disease_cases_indent", disease=disease, count=count))

    # Seasonal patterns
    cursor.execute('''
    SELECT 
        CASE 
            WHEN strftime('%m', case_date) IN ('12', '01', '02') THEN 'Winter'
            WHEN strftime('%m', case_date) IN ('03', '04', '05') THEN 'Spring'
            WHEN strftime('%m', case_date) IN ('06', '07', '08') THEN 'Summer'
            WHEN strftime('%m', case_date) IN ('09', '10', '11') THEN 'Fall'
        END as season,
        disease_name,
        COUNT(*) as case_count
    FROM disease_surveillance
    WHERE case_date >= ?
    GROUP BY season, disease_name
    ORDER BY season, case_count DESC
    ''', (twelve_months_ago,))

    seasonal_trends = cursor.fetchall()

    if seasonal_trends:
        print(_t("health_misc.surveillance.seasonal_disease_patterns"))
        current_season = ""
        for season, disease, count in seasonal_trends:
            if season != current_season:
                print(_t("health_misc.surveillance.season_header", season=season))
                current_season = season
            print(_t("health_misc.surveillance.disease_cases_indent", disease=disease, count=count))

    # Disease severity trends
    cursor.execute('''
    SELECT 
        disease_name,
        severity,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY disease_name), 1) as percentage
    FROM disease_surveillance
    WHERE case_date >= ?
    GROUP BY disease_name, severity
    ORDER BY disease_name, 
        CASE severity 
            WHEN 'Critical' THEN 1 
            WHEN 'Severe' THEN 2 
            WHEN 'Moderate' THEN 3 
            WHEN 'Mild' THEN 4 
        END
    ''', (twelve_months_ago,))

    severity_trends = cursor.fetchall()

    if severity_trends:
        print(_t("health_misc.surveillance.disease_severity_distribution"))
        current_disease = ""
        for disease, severity, count, percentage in severity_trends:
            if disease != current_disease:
                print(_t("health_misc.surveillance.disease_header", disease=disease))
                current_disease = disease
            print(_t("health_misc.surveillance.severity_cases_indent", severity=severity, count=count, percentage=percentage))

    # Emerging threats analysis
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    sixty_days_ago = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT 
        disease_name,
        SUM(CASE WHEN case_date >= ? THEN 1 ELSE 0 END) as recent_cases,
        SUM(CASE WHEN case_date BETWEEN ? AND ? THEN 1 ELSE 0 END) as previous_cases
    FROM disease_surveillance
    WHERE case_date >= ?
    GROUP BY disease_name
    HAVING recent_cases > 0
    ORDER BY recent_cases DESC
    ''', (thirty_days_ago, sixty_days_ago, thirty_days_ago, sixty_days_ago))

    emerging_threats = cursor.fetchall()

    if emerging_threats:
        print(_t("health_misc.surveillance.emerging_threat_analysis"))
        for disease, recent, previous in emerging_threats:
            if previous > 0:
                change = ((recent - previous) / previous) * 100
                trend = "+" if change > 0 else "-" if change < 0 else "="
                print(_t("health_misc.surveillance.emerging_threat_change", disease=disease, recent=recent, trend=trend, change=f"{change:+.1f}"))
            else:
                print(_t("health_misc.surveillance.emerging_threat_new", disease=disease, recent=recent))

    conn.close()

def disease_surveillance_system(auth):
    if not auth or not auth.current_user:
        print(_t("health_misc.surveillance.must_be_logged_in"))
        return

    if not auth.check_permission('issue_health_advisories'):
        print(_t("health_misc.surveillance.no_permission_access"))
        return

    while True:
        print(_t("health_misc.surveillance.system_header"))
        print(_t("health_misc.surveillance.menu_report_case"))
        print(_t("health_misc.surveillance.menu_view_cases"))
        print(_t("health_misc.surveillance.menu_contact_tracing"))
        print(_t("health_misc.surveillance.menu_outbreak_investigation"))
        print(_t("health_misc.surveillance.menu_disease_trends"))
        print(_t("health_misc.surveillance.menu_public_health_report"))
        print(_t("health_misc.surveillance.menu_return"))

        choice = input(_t("health_misc.surveillance.enter_choice_1_7"))

        if choice == '1':
            report_disease_case(auth)
        elif choice == '2':
            view_disease_cases(auth)
        elif choice == '3':
            conduct_contact_tracing(auth)
        elif choice == '4':
            investigate_outbreak(auth)
        elif choice == '5':
            analyze_disease_trends(auth)
        elif choice == '6':
            from university_system.modules.domain.health.records.medical_records import generate_public_health_report
            generate_public_health_report(auth)
        elif choice == '7':
            break
        else:
            print(_t("health_misc.surveillance.invalid_choice_try_again"))

def report_disease_case(auth):
    backup_before_operation('report_disease_case')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input(_t("health_misc.surveillance.enter_student_id"))

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print(_t("health_misc.surveillance.error_student_not_found"))
        conn.close()
        return

    # Common reportable diseases
    common_diseases = [
        'COVID-19',
        'Influenza',
        'Norovirus',
        'Strep Throat',
        'Meningitis',
        'Tuberculosis',
        'Measles',
        'Mumps',
        'Rubella',
        'Hepatitis A',
        'Hepatitis B',
        _t("health_misc.surveillance.disease_other")
    ]

    print(_t("health_misc.surveillance.common_reportable_diseases"))
    for i, disease in enumerate(common_diseases):
        print(f"{i+1}. {disease}")

    while True:
        disease_choice = input(_t("health_misc.surveillance.select_disease_prompt"))
        if disease_choice.isdigit() and 1 <= int(disease_choice) <= len(common_diseases):
            disease_name = common_diseases[int(disease_choice) - 1]
            if disease_name == _t("health_misc.surveillance.disease_other"):
                disease_name = input(_t("health_misc.surveillance.enter_disease_name"))
            break
        print(_t("health_misc.surveillance.invalid_choice_try_again"))

    while True:
        case_date = input(_t("health_misc.surveillance.case_date_prompt")).strip()
        if not case_date:
            case_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(case_date, '%Y-%m-%d')
            break
        except ValueError:
            print(_t("health_misc.surveillance.invalid_date_format"))

    symptoms = input(_t("health_misc.surveillance.symptoms_prompt"))

    severity_levels = [
        _t("health_misc.surveillance.severity_mild"),
        _t("health_misc.surveillance.severity_moderate"),
        _t("health_misc.surveillance.severity_severe"),
        _t("health_misc.surveillance.severity_critical")
    ]
    print(_t("health_misc.surveillance.severity_levels_header"))
    for i, level in enumerate(severity_levels):
        print(f"{i+1}. {level}")

    while True:
        severity_choice = input(_t("health_misc.surveillance.select_severity_prompt"))
        if severity_choice.isdigit() and 1 <= int(severity_choice) <= len(severity_levels):
            severity = severity_levels[int(severity_choice) - 1]
            break
        print(_t("health_misc.surveillance.invalid_choice_try_again"))

    contact_tracing_needed = input(_t("health_misc.surveillance.contact_tracing_needed_prompt")).lower() == 'y'
    isolation_required = input(_t("health_misc.surveillance.isolation_required_prompt")).lower() == 'y'

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO disease_surveillance 
    (disease_name, case_date, student_id, symptoms, severity, status, 
     contact_tracing_needed, isolation_required, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (disease_name, case_date, student_id, symptoms, severity, 'under_investigation',
          1 if contact_tracing_needed else 0, 1 if isolation_required else 0, created_at))

    conn.commit()
    case_id = cursor.lastrowid

    log_audit_event(auth.current_user['id'], 'report_disease_case', 'disease_surveillance', case_id)
    print(_t("health_misc.surveillance.disease_case_reported_success", case_id=case_id))

    # Check for outbreak potential
    cursor.execute('''
    SELECT COUNT(*) FROM disease_surveillance
    WHERE disease_name = ? AND case_date >= ?
    ''', (disease_name, (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')))

    recent_cases = cursor.fetchone()[0]

    if recent_cases >= 3:
        print(_t("health_misc.surveillance.outbreak_alert", count=recent_cases, disease_name=disease_name))
        print(_t("health_misc.surveillance.consider_outbreak_investigation"))

    conn.close()

def view_disease_cases(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print(_t("health_misc.surveillance.disease_cases_header"))
    print(_t("health_misc.surveillance.view_all_cases"))
    print(_t("health_misc.surveillance.view_cases_by_disease"))
    print(_t("health_misc.surveillance.view_cases_by_date_range"))
    print(_t("health_misc.surveillance.view_active_cases"))

    choice = input(_t("health_misc.surveillance.select_view_option"))

    if choice == '1':
        cursor.execute('''
        SELECT ds.id, s.student_id, s.first_name, s.last_name, ds.disease_name,
               ds.case_date, ds.severity, ds.status, ds.contact_tracing_needed,
               ds.isolation_required
        FROM disease_surveillance ds
        JOIN students s ON ds.student_id = s.student_id
        ORDER BY ds.case_date DESC
        LIMIT 50
        ''')

    elif choice == '2':
        disease_name = input(_t("health_misc.surveillance.enter_disease_name_filter"))
        cursor.execute('''
        SELECT ds.id, s.student_id, s.first_name, s.last_name, ds.disease_name,
               ds.case_date, ds.severity, ds.status, ds.contact_tracing_needed,
               ds.isolation_required
        FROM disease_surveillance ds
        JOIN students s ON ds.student_id = s.student_id
        WHERE ds.disease_name LIKE ?
        ORDER BY ds.case_date DESC
        ''', (f'%{disease_name}%',))

    elif choice == '3':
        start_date = input(_t("health_misc.surveillance.start_date_prompt"))
        end_date = input(_t("health_misc.surveillance.end_date_prompt"))

        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            print(_t("health_misc.surveillance.invalid_date_format"))
            conn.close()
            return

        cursor.execute('''
        SELECT ds.id, s.student_id, s.first_name, s.last_name, ds.disease_name,
               ds.case_date, ds.severity, ds.status, ds.contact_tracing_needed,
               ds.isolation_required
        FROM disease_surveillance ds
        JOIN students s ON ds.student_id = s.student_id
        WHERE ds.case_date BETWEEN ? AND ?
        ORDER BY ds.case_date DESC
        ''', (start_date, end_date))

    elif choice == '4':
        cursor.execute('''
        SELECT ds.id, s.student_id, s.first_name, s.last_name, ds.disease_name,
               ds.case_date, ds.severity, ds.status, ds.contact_tracing_needed,
               ds.isolation_required
        FROM disease_surveillance ds
        JOIN students s ON ds.student_id = s.student_id
        WHERE ds.status IN ('under_investigation', 'confirmed')
        ORDER BY ds.case_date DESC
        ''')

    else:
        print(_t("health_misc.surveillance.invalid_choice"))
        conn.close()
        return

    cases = cursor.fetchall()

    if not cases:
        print(_t("health_misc.surveillance.no_disease_cases_found"))
        conn.close()
        return

    for case in cases:
        case_id, student_id, first_name, last_name, disease, case_date, severity, status, contact_tracing, isolation = case

        print(_t("health_misc.surveillance.case_id_label", case_id=case_id))
        print(_t("health_misc.surveillance.student_label", first_name=first_name, last_name=last_name, student_id=student_id))
        print(_t("health_misc.surveillance.disease_display", disease=disease))
        print(_t("health_misc.surveillance.date_display", date=case_date))
        print(_t("health_misc.surveillance.severity_display", severity=severity))
        print(_t("health_misc.surveillance.status_display", status=status))

        if contact_tracing:
            print(_t("health_misc.surveillance.contact_tracing_required"))
        if isolation:
            print(_t("health_misc.surveillance.isolation_required"))

        print("-" * 30)

    conn.close()
