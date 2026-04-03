from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event


def screening_reminders(auth):
    """Send screening reminders"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get students with due screenings
    seven_days = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT ss.id, s.first_name, s.last_name, s.student_id, ss.screening_type, ss.due_date
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date <= ? AND ss.status = 'due'
    ORDER BY ss.due_date
    ''', (seven_days,))

    reminder_list = cursor.fetchall()

    if not reminder_list:
        print("No screening reminders to send.")
        conn.close()
        return

    print(f"\n===== Screening Reminders ({len(reminder_list)} students) =====")

    for screen_id, first_name, last_name, student_id, screening_type, due_date in reminder_list:
        print(f"• {first_name} {last_name} (ID: {student_id})")
        print(f"  {screening_type} due {due_date}")

    send_reminders = input(f"\nSend reminders to all {len(reminder_list)} students? (y/n): ").lower()

    if send_reminders == 'y':
        # In a real system, this would send email/SMS reminders
        print("Screening reminders sent successfully!")
        log_audit_event(auth.current_user['id'], 'send_screening_reminders', 'screening', len(reminder_list))
    else:
        print("Reminder sending cancelled.")

    conn.close()



def population_screening_reports(auth):
    """Generate population screening reports"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Population Screening Reports =====")

    # Screening compliance rates
    cursor.execute('''
    SELECT screening_type,
           COUNT(*) as total_due,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
           SUM(CASE WHEN due_date < date('now') AND status = 'due' THEN 1 ELSE 0 END) as overdue
    FROM screening_schedules
    WHERE due_date >= date('now', '-365 days')
    GROUP BY screening_type
    ORDER BY total_due DESC
    ''')

    compliance_data = cursor.fetchall()

    if compliance_data:
        print("Screening Compliance Rates (Last 12 Months):")
        print(f"{'Screening Type':<25} {'Total':<8} {'Completed':<10} {'Overdue':<8} {'Rate':<8}")
        print("-" * 65)

        for screening, total, completed, overdue in compliance_data:
            compliance_rate = (completed / total * 100) if total > 0 else 0
            print(f"{screening:<25} {total:<8} {completed:<10} {overdue:<8} {compliance_rate:.1f}%")

    # Age group analysis
    cursor.execute('''
    SELECT
        CASE
            WHEN s.age < 25 THEN '18-24'
            WHEN s.age < 35 THEN '25-34'
            WHEN s.age < 45 THEN '35-44'
            ELSE '45+'
        END as age_group,
        COUNT(DISTINCT ss.student_id) as students_with_screenings,
        AVG(CASE WHEN ss.status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as avg_compliance
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date >= date('now', '-365 days')
    GROUP BY age_group
    ORDER BY age_group
    ''')

    age_analysis = cursor.fetchall()

    if age_analysis:
        print(f"\nCompliance by Age Group:")
        print(f"{'Age Group':<12} {'Students':<10} {'Compliance':<12}")
        print("-" * 35)

        for age_group, students, compliance in age_analysis:
            print(f"{age_group:<12} {students:<10} {compliance:.1f}%")

    conn.close()



