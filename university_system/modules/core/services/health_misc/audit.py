from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta

from university_system.modules.core.services.health_misc.health_context import audit_logger
from university_system.infrastructure.database.db import get_connection

def log_audit_event(user_id, action, resource_type, resource_id, details=None, conn=None, max_retries=5):
    """
    Write an audit row. If `conn` is provided, reuse it (recommended) so the
    audit write is in the same transaction. Falls back to its own connection.
    Retries on SQLITE_BUSY to be extra defensive.
    """
    try:
        reuse_conn = conn is not None
        if not reuse_conn:
            conn = get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        payload = (user_id, action, resource_type, str(resource_id), timestamp, '', details or '')

        # Table is created during init_enhanced_health_db(); don't do DDL here.

        for attempt in range(max_retries):
            try:
                cursor.execute("""
                    INSERT INTO audit_trail
                    (user_id, action, resource_type, resource_id, timestamp, old_values, new_values)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, payload)
                if not reuse_conn:
                    conn.commit()
                break
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if "database is locked" in msg and attempt < max_retries - 1:
                    time.sleep(0.15 * (2 ** attempt))  # 150ms, 300ms, 600ms, ...
                    continue
                raise

        # File logger (non-blocking)
        audit_logger.info(
            f"USER:{user_id} ACTION:{action} RESOURCE:{resource_type}:{resource_id} DETAILS:{details}"
        )
    except Exception as e:
        # Don't crash the business flow
        print(f"Warning: Audit logging failed: {e}")
    finally:
        if conn and not reuse_conn:
            try:
                conn.close()
            except Exception:
                pass

def analyze_data_access_patterns(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Data Access Pattern Analysis =====")

    # Access patterns for the last 30 days
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

    # Most active users
    cursor.execute('''
    SELECT user_id, COUNT(*) as access_count
    FROM audit_trail
    WHERE action LIKE '%view%' AND timestamp >= ?
    GROUP BY user_id
    ORDER BY access_count DESC
    LIMIT 10
    ''', (thirty_days_ago,))

    active_users = cursor.fetchall()

    if active_users:
        print("Most Active Users (Health Record Access):")
        for user, count in active_users:
            print(f"  {user}: {count} accesses")

            # Flag unusual activity
            if count > 1000:  # Threshold for investigation
                print(f"    ⚠️  HIGH ACTIVITY - Review access patterns")

    # Access by time of day
    cursor.execute('''
    SELECT strftime('%H', timestamp) as hour, COUNT(*) as access_count
    FROM audit_trail
    WHERE action LIKE '%view%' AND timestamp >= ?
    GROUP BY strftime('%H', timestamp)
    ORDER BY hour
    ''', (thirty_days_ago,))

    hourly_access = cursor.fetchall()

    if hourly_access:
        print("\nAccess by Hour of Day:")
        for hour, count in hourly_access:
            hour_int = int(hour)

            # Flag unusual hours (late night/early morning)
            if 0 <= hour_int <= 5 or hour_int >= 22:
                if count > 10:  # Threshold for after-hours activity
                    print(f"  {hour}:00 - {count} accesses ⚠️  After hours activity")
                else:
                    print(f"  {hour}:00 - {count} accesses")
            else:
                print(f"  {hour}:00 - {count} accesses")

    # Resource access patterns
    cursor.execute('''
    SELECT resource_type, COUNT(*) as access_count
    FROM audit_trail
    WHERE timestamp >= ?
    GROUP BY resource_type
    ORDER BY access_count DESC
    ''', (thirty_days_ago,))

    resource_access = cursor.fetchall()

    if resource_access:
        print("\nMost Accessed Resource Types:")
        for resource, count in resource_access:
            print(f"  {resource}: {count} accesses")

    # Suspicious patterns detection
    print("\n===== Suspicious Activity Detection =====")

    # Bulk data access (many records in short time)
    cursor.execute('''
    SELECT user_id, COUNT(*) as rapid_access,
           MIN(timestamp) as start_time, MAX(timestamp) as end_time
    FROM audit_trail
    WHERE action LIKE '%view%' AND timestamp >= datetime('now', '-1 hour')
    GROUP BY user_id
    HAVING COUNT(*) > 50
    ORDER BY rapid_access DESC
    ''', )

    rapid_access = cursor.fetchall()

    if rapid_access:
        print("Rapid Data Access (>50 records in 1 hour):")
        for user, count, start, end in rapid_access:
            print(f"  {user}: {count} accesses from {start} to {end}")
            print(f"    🔴 INVESTIGATE - Potential data extraction")
    else:
        print("No suspicious rapid access patterns detected.")

    # Access outside normal hours
    cursor.execute('''
    SELECT user_id, COUNT(*) as after_hours_count
    FROM audit_trail
    WHERE action LIKE '%view%' 
    AND (strftime('%H', timestamp) < '07' OR strftime('%H', timestamp) > '19')
    AND timestamp >= ?
    GROUP BY user_id
    HAVING COUNT(*) > 20
    ORDER BY after_hours_count DESC
    ''', (thirty_days_ago,))

    after_hours = cursor.fetchall()

    if after_hours:
        print("\nExtensive After-Hours Access:")
        for user, count in after_hours:
            print(f"  {user}: {count} after-hours accesses")
            print(f"    ⚠️  REVIEW - Unusual access times")

    conn.close()

def view_failed_logins(auth):
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Failed Login Attempts =====")

    # Get failed login attempts from last 7 days
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    SELECT user_id, ip_address, timestamp, resource_id
    FROM audit_trail
    WHERE action = 'failed_login' AND timestamp >= ?
    ORDER BY timestamp DESC
    ''', (seven_days_ago,))

    failed_logins = cursor.fetchall()

    if not failed_logins:
        print("No failed login attempts in the last 7 days.")
        conn.close()
        return

    print(f"Failed login attempts (last 7 days): {len(failed_logins)}")
    print("-" * 50)

    # Group by user for analysis
    user_attempts = {}
    ip_attempts = {}

    for user_id, ip_address, timestamp, resource_id in failed_logins:
        print(f"{timestamp} - User: {user_id} - IP: {ip_address}")

        # Count attempts per user
        if user_id in user_attempts:
            user_attempts[user_id] += 1
        else:
            user_attempts[user_id] = 1

        # Count attempts per IP
        if ip_address in ip_attempts:
            ip_attempts[ip_address] += 1
        else:
            ip_attempts[ip_address] = 1

    # Analysis
    print(f"\n===== Analysis =====")

    # Users with multiple failed attempts
    repeat_users = {user: count for user, count in user_attempts.items() if count >= 3}
    if repeat_users:
        print("Users with 3+ failed attempts:")
        for user, count in sorted(repeat_users.items(), key=lambda x: x[1], reverse=True):
            print(f"  {user}: {count} attempts")
            if count >= 5:
                print(f"    🔴 HIGH RISK - Consider account lockout")

    # IPs with multiple failed attempts
    repeat_ips = {ip: count for ip, count in ip_attempts.items() if count >= 5}
    if repeat_ips:
        print("\nIPs with 5+ failed attempts:")
        for ip, count in sorted(repeat_ips.items(), key=lambda x: x[1], reverse=True):
            print(f"  {ip}: {count} attempts")
            if count >= 10:
                print(f"    🔴 POTENTIAL ATTACK - Consider IP blocking")

    conn.close()

def performance_improvement(auth):
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to access performance improvement.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Performance Improvement Opportunities =====")

    # Identify improvement areas
    improvement_areas = []

    # Low vaccination coverage
    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute('''
    SELECT vaccine_name, COUNT(DISTINCT student_id) as coverage
    FROM vaccination_records
    WHERE verified = 1
    GROUP BY vaccine_name
    ''')

    vaccine_coverage = cursor.fetchall()

    for vaccine, coverage in vaccine_coverage:
        coverage_rate = (coverage / total_students * 100) if total_students > 0 else 0
        if coverage_rate < 80:
            improvement_areas.append({
                'area': 'Vaccination Coverage',
                'issue': f'{vaccine} coverage at {coverage_rate:.1f}%',
                'target': '≥80% coverage',
                'actions': [
                    'Targeted outreach campaign',
                    'Reminder system implementation',
                    'Educational materials distribution',
                    'Mobile vaccination clinics'
                ]
            })

    # High no-show rates
    cursor.execute('''
    SELECT 
        COUNT(*) as total_appointments,
        SUM(CASE WHEN status = 'no-show' THEN 1 ELSE 0 END) as no_shows
    FROM health_appointments
    WHERE appointment_date >= date('now', '-30 days')
    ''')

    appt_data = cursor.fetchone()
    if appt_data[0] > 0:
        no_show_rate = (appt_data[1] / appt_data[0] * 100)
        if no_show_rate > 15:
            improvement_areas.append({
                'area': 'Appointment Management',
                'issue': f'No-show rate at {no_show_rate:.1f}%',
                'target': '≤10% no-show rate',
                'actions': [
                    'Automated reminder system',
                    'Flexible scheduling options',
                    'Patient education on importance',
                    'Easy rescheduling process'
                ]
            })

    # Incomplete health records
    cursor.execute('''
    SELECT 
        COUNT(*) as total_students,
        COUNT(DISTINCT hr.student_id) as with_health_records
    FROM students s
    LEFT JOIN health_records hr ON s.student_id = hr.student_id
    ''')

    health_record_data = cursor.fetchone()
    if health_record_data[0] > 0:
        health_record_rate = (health_record_data[1] / health_record_data[0] * 100)
        if health_record_rate < 90:
            improvement_areas.append({
                'area': 'Health Record Completeness',
                'issue': f'Only {health_record_rate:.1f}% of students have health records',
                'target': '≥95% completeness',
                'actions': [
                    'Health screening campaigns',
                    'Mandatory health assessments',
                    'Improved data collection processes',
                    'Staff training on documentation'
                ]
            })

    # Low care plan utilization for chronic conditions
    cursor.execute('''
    SELECT 
        COUNT(DISTINCT mc.student_id) as chronic_patients,
        COUNT(DISTINCT cp.student_id) as with_care_plans
    FROM medical_conditions mc
    LEFT JOIN care_plans cp ON mc.student_id = cp.student_id AND cp.status = 'active'
    WHERE mc.status = 'active'
    ''')

    care_plan_data = cursor.fetchone()
    if care_plan_data[0] > 0:
        care_plan_rate = (care_plan_data[1] / care_plan_data[0] * 100)
        if care_plan_rate < 70:
            improvement_areas.append({
                'area': 'Chronic Care Management',
                'issue': f'Only {care_plan_rate:.1f}% of chronic patients have care plans',
                'target': '≥80% care plan utilization',
                'actions': [
                    'Provider training on care planning',
                    'Care plan templates development',
                    'Patient engagement programs',
                    'Regular care plan reviews'
                ]
            })

    # Display improvement opportunities
    if improvement_areas:
        for i, area in enumerate(improvement_areas, 1):
            print(f"\n{i}. {area['area']}")
            print(f"   Current Issue: {area['issue']}")
            print(f"   Target: {area['target']}")
            print("   Recommended Actions:")
            for action in area['actions']:
                print(f"   • {action}")
            print("-" * 50)
    else:
        print("No significant improvement opportunities identified.")
        print("All metrics are within acceptable ranges.")

    # Performance improvement plan
    if improvement_areas:
        create_plan = input("\nCreate performance improvement plan? (y/n): ").lower()
        if create_plan == 'y':
            print("\n===== Performance Improvement Plan =====")

            plan_name = input("Plan name: ")
            plan_start = input("Start date (YYYY-MM-DD): ")
            plan_end = input("End date (YYYY-MM-DD): ")
            responsible_party = input(f"Responsible party [{auth.current_user['username']}]: ").strip()
            if not responsible_party:
                responsible_party = auth.current_user['username']

            print(f"\nPerformance Improvement Plan: {plan_name}")
            print(f"Timeline: {plan_start} to {plan_end}")
            print(f"Responsible: {responsible_party}")
            print("\nPriority Areas:")

            for i, area in enumerate(improvement_areas[:3], 1):  # Top 3 priorities
                print(f"{i}. {area['area']} - {area['issue']}")

            log_audit_event(auth.current_user['id'], 'create_improvement_plan', 'quality_improvement', 0,
                           f"Plan: {plan_name}")
            print("\nPerformance improvement plan created!")

    conn.close()
