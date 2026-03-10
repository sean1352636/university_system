from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.records.analytics.population import show_population_health_metrics
from education_system.university_system.modules.domain.health.records.analytics.provider import analyze_provider_workload, show_appointment_utilization_stats
from education_system.university_system.modules.domain.health.records.analytics.quality import show_quality_metrics
from education_system.university_system.modules.domain.health.records.analytics.reports import generate_custom_report
from education_system.university_system.modules.domain.health.records.vaccinations.reports import generate_vaccination_coverage_report


def health_analytics_dashboard(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view health analytics.")
        return
    
    while True:
        print("\n===== Health Analytics Dashboard =====")
        print("1. Population Health Metrics")
        print("2. Vaccination Coverage Report")
        print("3. Appointment Utilization Statistics")
        print("4. Health Trends Analysis")
        print("5. Provider Workload Analysis")
        print("6. Quality Metrics")
        print("7. Generate Custom Report")
        print("8. Return to Main Menu")
        
        choice = input("\nEnter your choice (1-8): ")
        
        if choice == '1':
            show_population_health_metrics(auth)
        elif choice == '2':
            generate_vaccination_coverage_report(auth)
        elif choice == '3':
            show_appointment_utilization_stats(auth)
        elif choice == '4':
            analyze_health_trends(auth)
        elif choice == '5':
            analyze_provider_workload(auth)
        elif choice == '6':
            show_quality_metrics(auth)
        elif choice == '7':
            generate_custom_report(auth)
        elif choice == '8':
            break
        else:
            print("Invalid choice. Please try again.")



def analyze_health_trends(auth):
    """Analyze health trends over time"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Health Trends Analysis =====")
    
    # Monthly health records trend (last 12 months)
    twelve_months_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    cursor.execute('''
    SELECT 
        strftime('%Y-%m', record_date) as month,
        COUNT(*) as record_count
    FROM health_records
    WHERE record_date >= ?
    GROUP BY strftime('%Y-%m', record_date)
    ORDER BY month
    ''', (twelve_months_ago,))
    
    monthly_records = cursor.fetchall()
    
    if monthly_records:
        print("Monthly Health Records (Last 12 Months):")
        for month, count in monthly_records:
            print(f"  {month}: {count} records")
    
    # Seasonal illness patterns
    cursor.execute('''
    SELECT 
        strftime('%m', record_date) as month,
        record_type,
        COUNT(*) as count
    FROM health_records
    WHERE record_date >= ? AND record_type IN ('General Medical', 'Illness Treatment')
    GROUP BY strftime('%m', record_date), record_type
    ORDER BY month, count DESC
    ''', (twelve_months_ago,))
    
    seasonal_patterns = cursor.fetchall()
    
    if seasonal_patterns:
        print("\nSeasonal Illness Patterns:")
        current_month = ""
        for month, record_type, count in seasonal_patterns:
            month_name = datetime.strptime(month, '%m').strftime('%B')
            if month_name != current_month:
                print(f"  {month_name}:")
                current_month = month_name
            print(f"    {record_type}: {count}")
    
    # Emergency contact usage trends
    cursor.execute('''
    SELECT 
        strftime('%Y-%m', created_at) as month,
        COUNT(*) as emergency_contacts
    FROM emergency_contacts
    WHERE created_at >= ?
    GROUP BY strftime('%Y-%m', created_at)
    ORDER BY month
    ''', (twelve_months_ago,))
    
    emergency_trends = cursor.fetchall()
    
    if emergency_trends:
        print("\nEmergency Contact Updates (Last 12 Months):")
        for month, count in emergency_trends:
            print(f"  {month}: {count} updates")
    
    conn.close()



def generate_health_condition_analysis(auth):
    """Generate health condition analysis report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n===== Health Condition Analysis =====")
    
    # Top health conditions
    cursor.execute('''
    SELECT condition_name, severity, COUNT(*) as patient_count,
           AVG(CASE WHEN status = 'active' THEN 1.0 ELSE 0.0 END) * 100 as active_percentage
    FROM medical_conditions
    GROUP BY condition_name, severity
    ORDER BY patient_count DESC
    LIMIT 20
    ''')
    
    conditions = cursor.fetchall()
    
    if conditions:
        print("Top Health Conditions:")
        print("-" * 60)
        print(f"{'Condition':<25} {'Severity':<10} {'Count':<6} {'Active %':<8}")
        print("-" * 60)
        
        for condition, severity, count, active_pct in conditions:
            print(f"{condition:<25} {severity:<10} {count:<6} {active_pct:.1f}%")
    
    # Condition trends by age group
    cursor.execute('''
    SELECT 
        CASE 
            WHEN s.age < 20 THEN '18-19'
            WHEN s.age < 25 THEN '20-24'
            WHEN s.age < 30 THEN '25-29'
            ELSE '30+'
        END as age_group,
        mc.condition_name,
        COUNT(*) as count
    FROM medical_conditions mc
    JOIN students s ON mc.student_id = s.student_id
    WHERE mc.status = 'active'
    GROUP BY age_group, mc.condition_name
    HAVING count >= 2
    ORDER BY age_group, count DESC
    ''')
    
    age_trends = cursor.fetchall()
    
    if age_trends:
        print(f"\nCondition Distribution by Age Group:")
        print("-" * 50)
        
        current_age_group = ""
        for age_group, condition, count in age_trends:
            if age_group != current_age_group:
                print(f"\nAge {age_group}:")
                current_age_group = age_group
            print(f"  {condition}: {count} cases")
    
    # Severity analysis
    cursor.execute('''
    SELECT severity, COUNT(*) as count,
           COUNT(*) * 100.0 / (SELECT COUNT(*) FROM medical_conditions WHERE status = 'active') as percentage
    FROM medical_conditions
    WHERE status = 'active'
    GROUP BY severity
    ORDER BY count DESC
    ''')
    
    severity_data = cursor.fetchall()
    
    if severity_data:
        print(f"\nCondition Severity Distribution:")
        print("-" * 35)
        for severity, count, percentage in severity_data:
            print(f"{severity}: {count} ({percentage:.1f}%)")
    
    conn.close()



