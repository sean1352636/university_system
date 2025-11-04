from __future__ import annotations

from datetime import datetime, timedelta

from university_system.modules.core.services.health_misc.audit import log_audit_event
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.database.db import get_connection

def generate_disease_surveillance_report(auth, start_date, end_date):
    """Generate disease surveillance report"""
    conn = get_connection()
    cursor = conn.cursor()

    report_content = []
    report_content.append("DISEASE SURVEILLANCE REPORT")
    report_content.append("=" * 28)
    report_content.append(f"Period: {start_date} to {end_date}")
    report_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
        report_content.append("DISEASE CASES BY TYPE")
        report_content.append("-" * 20)
        report_content.append(f"Total Cases: {total_cases}")
        report_content.append("")

        for disease, count, severe, tracing in disease_data:
            report_content.append(f"{disease}: {count} cases")
            report_content.append(f"  Severe/Critical: {severe}")
            report_content.append(f"  Requiring Contact Tracing: {tracing}")

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
        report_content.append("CASE STATUS SUMMARY")
        report_content.append("-" * 19)
        for status, count in status_data:
            report_content.append(f"{status}: {count}")

    # Display report
    for line in report_content:
        print(line)

    conn.close()

def conduct_contact_tracing(auth):
    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to conduct contact tracing.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    case_id = input("Enter disease case ID for contact tracing: ")

    cursor.execute('''
    SELECT ds.id, s.student_id, s.first_name, s.last_name, ds.disease_name,
           ds.case_date, ds.symptoms, ds.severity
    FROM disease_surveillance ds
    JOIN students s ON ds.student_id = s.student_id
    WHERE ds.id = ?
    ''', (case_id,))

    case = cursor.fetchone()

    if not case:
        print("Error: Disease case not found.")
        conn.close()
        return

    case_id, student_id, first_name, last_name, disease, case_date, symptoms, severity = case

    print(f"\n===== Contact Tracing for Case {case_id} =====")
    print(f"Patient: {first_name} {last_name} (ID: {student_id})")
    print(f"Disease: {disease}")
    print(f"Case Date: {case_date}")
    print(f"Severity: {severity}")

    # Contact tracing parameters
    print("\nContact Tracing Parameters:")

    # Exposure period
    exposure_start = input("Exposure period start date (YYYY-MM-DD): ")
    exposure_end = input("Exposure period end date (YYYY-MM-DD): ")

    # Contact categories
    print("\nContact Categories:")
    print("1. Household contacts")
    print("2. Close contacts (within 6 feet for 15+ minutes)")
    print("3. Casual contacts")
    print("4. Healthcare worker contacts")

    # Gather contact information
    contacts = []

    print("\nEnter contact information (type 'done' when finished):")
    while True:
        contact_name = input("Contact name (or 'done'): ").strip()
        if contact_name.lower() == 'done':
            break

        contact_type = input("Contact type (household/close/casual/healthcare): ")
        contact_date = input("Last contact date (YYYY-MM-DD): ")
        contact_duration = input("Contact duration (minutes): ")

        contacts.append({
            'name': contact_name,
            'type': contact_type,
            'date': contact_date,
            'duration': contact_duration
        })

    print(f"\n===== Contact Tracing Summary =====")
    print(f"Total contacts identified: {len(contacts)}")

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

    print(f"\nRisk Classification:")
    print(f"High Risk: {len(high_risk_contacts)}")
    print(f"Moderate Risk: {len(moderate_risk_contacts)}")
    print(f"Low Risk: {len(low_risk_contacts)}")

    # Recommendations
    print(f"\n===== Recommendations =====")

    if high_risk_contacts:
        print("High Risk Contacts - Immediate Actions:")
        for contact in high_risk_contacts:
            print(f"- {contact['name']}: Quarantine, testing, daily monitoring")

    if moderate_risk_contacts:
        print("Moderate Risk Contacts - Monitor closely:")
        for contact in moderate_risk_contacts:
            print(f"- {contact['name']}: Testing, symptom monitoring")

    # Update case record
    cursor.execute('''
    UPDATE disease_surveillance 
    SET contact_tracing_completed = 1, contacts_identified = ?
    WHERE id = ?
    ''', (len(contacts), case_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'conduct_contact_tracing', 'disease_surveillance', case_id,
                   f"Identified {len(contacts)} contacts")

    print(f"\nContact tracing completed for case {case_id}")
    conn.close()

def investigate_outbreak(auth):
    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to investigate outbreaks.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Outbreak Investigation =====")

    # Identify potential outbreaks
    print("Scanning for potential outbreaks...")

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
        print("No potential outbreaks detected in the last 14 days.")
        conn.close()
        return

    print("\nPotential Outbreaks Detected:")
    for i, (disease, count, first_case, last_case) in enumerate(potential_outbreaks):
        print(f"{i+1}. {disease}: {count} cases ({first_case} to {last_case})")

    while True:
        choice = input(f"\nSelect outbreak to investigate (1-{len(potential_outbreaks)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(potential_outbreaks):
            selected_outbreak = potential_outbreaks[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    disease_name, case_count, first_case, last_case = selected_outbreak

    print(f"\n===== Investigating {disease_name} Outbreak =====")
    print(f"Cases: {case_count}")
    print(f"Period: {first_case} to {last_case}")

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

    print(f"\nCase Details:")
    for case in cases:
        case_id, student_id, first_name, last_name, case_date, symptoms, severity, contact_tracing = case
        print(f"Case {case_id}: {first_name} {last_name} - {case_date} ({severity})")

    # Outbreak investigation steps
    print(f"\n===== Outbreak Investigation Protocol =====")

    # 1. Case definition
    case_definition = input("Define case criteria: ")

    # 2. Case finding
    additional_cases = input("Additional cases found during investigation: ")

    # 3. Hypothesis generation
    print("\nPossible sources/causes:")
    source_hypotheses = input("Enter suspected source(s): ")

    # 4. Control measures
    print("\nControl measures implemented:")
    control_measures = []

    measures = [
        "Isolation of cases",
        "Quarantine of contacts",
        "Enhanced surveillance",
        "Environmental cleaning",
        "Vaccination campaign",
        "Health education",
        "Facility restrictions"
    ]

    print("Available control measures:")
    for i, measure in enumerate(measures):
        print(f"{i+1}. {measure}")

    while True:
        measure_choice = input("Select control measure (number) or 'done': ").strip()
        if measure_choice.lower() == 'done':
            break

        try:
            measure_idx = int(measure_choice) - 1
            if 0 <= measure_idx < len(measures):
                control_measures.append(measures[measure_idx])
                print(f"Added: {measures[measure_idx]}")
            else:
                print("Invalid choice.")
        except ValueError:
            print("Invalid input.")

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

    print(f"\n===== Outbreak Investigation Summary =====")
    for key, value in outbreak_summary.items():
        print(f"{key.replace('_', ' ').title()}: {value}")

    log_audit_event(auth.current_user['id'], 'investigate_outbreak', 'outbreak', 0,
                   f"{disease_name} outbreak - {case_count} cases")

    # Update case statuses
    update_cases = input("\nUpdate all cases to 'confirmed'? (y/n): ").lower()
    if update_cases == 'y':
        cursor.execute('''
        UPDATE disease_surveillance 
        SET status = 'confirmed'
        WHERE disease_name = ? AND case_date >= ?
        ''', (disease_name, fourteen_days_ago))

        conn.commit()
        print("Case statuses updated to confirmed.")

    print("\nOutbreak investigation completed.")
    conn.close()

def analyze_disease_trends(auth):
    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to analyze disease trends.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Disease Trends Analysis =====")

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
        print("Monthly Disease Trends (Last 12 Months):")
        current_month = ""
        for month, disease, count in monthly_trends:
            if month != current_month:
                print(f"\n{month}:")
                current_month = month
            print(f"  {disease}: {count} cases")

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
        print("\nSeasonal Disease Patterns:")
        current_season = ""
        for season, disease, count in seasonal_trends:
            if season != current_season:
                print(f"\n{season}:")
                current_season = season
            print(f"  {disease}: {count} cases")

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
        print("\nDisease Severity Distribution:")
        current_disease = ""
        for disease, severity, count, percentage in severity_trends:
            if disease != current_disease:
                print(f"\n{disease}:")
                current_disease = disease
            print(f"  {severity}: {count} cases ({percentage}%)")

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
        print("\nEmerging Threat Analysis (Last 30 vs Previous 30 Days):")
        for disease, recent, previous in emerging_threats:
            if previous > 0:
                change = ((recent - previous) / previous) * 100
                trend = "↗️" if change > 0 else "↘️" if change < 0 else "→"
                print(f"{disease}: {recent} cases {trend} ({change:+.1f}% change)")
            else:
                print(f"{disease}: {recent} cases (NEW)")

    conn.close()

def disease_surveillance_system(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to access disease surveillance.")
        return

    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to access disease surveillance.")
        return

    while True:
        print("\n===== Disease Surveillance System =====")
        print("1. Report Disease Case")
        print("2. View Disease Cases")
        print("3. Contact Tracing")
        print("4. Outbreak Investigation")
        print("5. Disease Trends Analysis")
        print("6. Generate Public Health Report")
        print("7. Return to Main Menu")

        choice = input("\nEnter your choice (1-7): ")

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
            print("Invalid choice. Please try again.")

def report_disease_case(auth):
    backup_before_operation('report_disease_case')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
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
        'Other'
    ]

    print("\nCommon Reportable Diseases:")
    for i, disease in enumerate(common_diseases):
        print(f"{i+1}. {disease}")

    while True:
        disease_choice = input("\nSelect disease (1-12): ")
        if disease_choice.isdigit() and 1 <= int(disease_choice) <= len(common_diseases):
            disease_name = common_diseases[int(disease_choice) - 1]
            if disease_name == 'Other':
                disease_name = input("Enter disease name: ")
            break
        print("Invalid choice. Please try again.")

    while True:
        case_date = input("Case date (YYYY-MM-DD) [today]: ").strip()
        if not case_date:
            case_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(case_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    symptoms = input("Symptoms: ")

    severity_levels = ['Mild', 'Moderate', 'Severe', 'Critical']
    print("\nSeverity Levels:")
    for i, level in enumerate(severity_levels):
        print(f"{i+1}. {level}")

    while True:
        severity_choice = input("\nSelect severity (1-4): ")
        if severity_choice.isdigit() and 1 <= int(severity_choice) <= len(severity_levels):
            severity = severity_levels[int(severity_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    contact_tracing_needed = input("Contact tracing needed? (y/n): ").lower() == 'y'
    isolation_required = input("Isolation required? (y/n): ").lower() == 'y'

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
    print(f"\nDisease case reported successfully! Case ID: {case_id}")

    # Check for outbreak potential
    cursor.execute('''
    SELECT COUNT(*) FROM disease_surveillance 
    WHERE disease_name = ? AND case_date >= ?
    ''', (disease_name, (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')))

    recent_cases = cursor.fetchone()[0]

    if recent_cases >= 3:
        print(f"\n⚠️  OUTBREAK ALERT: {recent_cases} cases of {disease_name} in the last 14 days!")
        print("Consider initiating outbreak investigation procedures.")

    conn.close()

def view_disease_cases(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Disease Cases =====")
    print("1. View All Cases")
    print("2. View Cases by Disease")
    print("3. View Cases by Date Range")
    print("4. View Active Cases")

    choice = input("\nSelect view option (1-4): ")

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
        disease_name = input("Enter disease name: ")
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
        start_date = input("Start date (YYYY-MM-DD): ")
        end_date = input("End date (YYYY-MM-DD): ")

        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format.")
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
        print("Invalid choice.")
        conn.close()
        return

    cases = cursor.fetchall()

    if not cases:
        print("No disease cases found.")
        conn.close()
        return

    for case in cases:
        case_id, student_id, first_name, last_name, disease, case_date, severity, status, contact_tracing, isolation = case

        print(f"\nCase ID: {case_id}")
        print(f"Student: {first_name} {last_name} (ID: {student_id})")
        print(f"Disease: {disease}")
        print(f"Date: {case_date}")
        print(f"Severity: {severity}")
        print(f"Status: {status}")

        if contact_tracing:
            print("🔍 Contact tracing required")
        if isolation:
            print("🏠 Isolation required")

        print("-" * 30)

    conn.close()
