from __future__ import annotations

from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.i18n import get_text as _t

def critical_alerts_dashboard(auth):
    """Show critical alerts for provider"""
    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n{_t('health_misc.dashboards.alerts_title')}")

    alerts = []

    # Critical lab values (last 7 days)
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT lr.test_name, lr.result_value, lr.resulted_date, s.first_name, s.last_name, s.student_id
    FROM lab_results lr
    JOIN students s ON lr.student_id = s.student_id
    WHERE lr.abnormal_flag IN ('H', 'L') AND lr.resulted_date >= ?
    ORDER BY lr.resulted_date DESC
    ''', (seven_days_ago,))

    critical_labs = cursor.fetchall()

    for test, value, date, first_name, last_name, student_id in critical_labs:
        alerts.append(_t('health_misc.dashboards.critical_lab', test=test, value=value, first_name=first_name, last_name=last_name, student_id=student_id, date=date))

    # Severe allergic reactions in vaccinations
    cursor.execute('''
    SELECT vr.vaccine_name, vr.administered_date, s.first_name, s.last_name, s.student_id
    FROM vaccination_records vr
    JOIN students s ON vr.student_id = s.student_id
    WHERE vr.adverse_reaction = 1 AND vr.administered_date >= ?
    ''', (seven_days_ago,))

    adverse_reactions = cursor.fetchall()

    for vaccine, date, first_name, last_name, student_id in adverse_reactions:
        alerts.append(_t('health_misc.dashboards.adverse_reaction', vaccine=vaccine, first_name=first_name, last_name=last_name, student_id=student_id, date=date))

    # Overdue follow-ups
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT ra.follow_up_date, s.first_name, s.last_name, s.student_id, ra.assessment_type
    FROM risk_assessments ra
    JOIN students s ON ra.student_id = s.student_id
    WHERE ra.follow_up_date < ? AND ra.follow_up_date IS NOT NULL
    ''', (today,))

    overdue_followups = cursor.fetchall()

    for follow_date, first_name, last_name, student_id, assessment in overdue_followups:
        alerts.append(_t('health_misc.dashboards.overdue_followup', assessment=assessment, first_name=first_name, last_name=last_name, student_id=student_id, follow_date=follow_date))

    if alerts:
        for alert in alerts:
            print(f"  {alert}")
    else:
        print(f"  {_t('health_misc.dashboards.no_alerts')}")

    conn.close()

def generate_custom_report(auth):
    """Generate custom reports based on user criteria"""
    print(f"\n{_t('health_misc.dashboards.report_generator_title')}")
    print(_t('health_misc.dashboards.available_reports'))
    print(f"1. {_t('health_misc.dashboards.student_health_summary')}")
    print(f"2. {_t('health_misc.dashboards.vaccination_status')}")
    print(f"3. {_t('health_misc.dashboards.appointment_schedule')}")
    print(f"4. {_t('health_misc.dashboards.health_condition_analysis')}")
    print(f"5. {_t('health_misc.dashboards.provider_performance')}")

    choice = input(f"\n{_t('health_misc.dashboards.select_report_type')}").strip()

    if choice == '1':
        from education_system.post_18.university_system.modules.domain.health.records.analytics.population import generate_student_health_summary
        return generate_student_health_summary(auth)
    elif choice == '2':
        from education_system.post_18.university_system.modules.domain.health.records.vaccinations.reports import generate_vaccination_status_report
        return generate_vaccination_status_report(auth)
    elif choice == '3':
        from education_system.post_18.university_system.modules.domain.health.appointments.appointment_booking import generate_appointment_schedule_report
        return generate_appointment_schedule_report(auth)
    elif choice == '4':
        from education_system.post_18.university_system.modules.domain.health.records.analytics.trends import generate_health_condition_analysis
        return generate_health_condition_analysis(auth)
    elif choice == '5':
        from education_system.post_18.university_system.modules.domain.health.appointments.appointment_booking import generate_provider_performance_report
        return generate_provider_performance_report(auth)
    else:
        print(_t('health_misc.dashboards.invalid_selection'))
