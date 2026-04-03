from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.services import generate_disease_surveillance_report
from education_system.university_system.modules.domain.health.records.analytics.population import generate_population_health_report, generate_student_health_summary_report
from education_system.university_system.modules.domain.health.records.vaccinations.reports import generate_vaccination_analysis_report


def generate_health_report(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to generate health reports.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Health Report Generator =====")

    # Report options
    report_types = [
        'Student Health Summary',
        'Population Health Statistics',
        'Disease Surveillance Report',
        'Vaccination Coverage Analysis',
        'Provider Utilization Report',
        'Quality Metrics Dashboard'
    ]

    print("Available Report Types:")
    for i, report_type in enumerate(report_types):
        print(f"{i+1}. {report_type}")

    while True:
        choice = input(f"\nSelect report type (1-{len(report_types)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(report_types):
            selected_report = report_types[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    # Date range for report
    while True:
        start_date = input("Start date (YYYY-MM-DD): ")
        end_date = input("End date (YYYY-MM-DD): ")
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    print(f"\nGenerating {selected_report} for period {start_date} to {end_date}...")

    # Generate report based on type
    if selected_report == 'Population Health Statistics':
        generate_population_health_report(auth, start_date, end_date)
    elif selected_report == 'Disease Surveillance Report':
        # already imported from health_misc at module level, fine to call
        generate_disease_surveillance_report(auth, start_date, end_date)
    elif selected_report == 'Vaccination Coverage Analysis':
        generate_vaccination_analysis_report(auth, start_date, end_date)
    elif selected_report == 'Provider Utilization Report':
        from education_system.university_system.modules.domain.health.appointments.appointment_booking import generate_provider_utilization_report
        generate_provider_utilization_report(auth, start_date, end_date)
    elif selected_report == 'Quality Metrics Dashboard':
        from education_system.university_system.modules.domain.health.records.quality_assurance import generate_quality_metrics_report
        generate_quality_metrics_report(auth, start_date, end_date)
    elif selected_report == 'Student Health Summary':
        generate_student_health_summary_report(auth, start_date, end_date)
    else:
        print("Report type not yet implemented.")

    conn.close()



