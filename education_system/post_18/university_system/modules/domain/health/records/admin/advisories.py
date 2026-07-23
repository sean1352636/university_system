from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.post_18.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.post_18.university_system.infrastructure.email import (
    send_appointment_confirmation,
    send_health_notification,
)


def add_health_advisory(auth):
    if not auth.check_permission('issue_health_advisories'):
        print("You don't have permission to issue health advisories.")
        return

    backup_before_operation('add_health_advisory')

    conn = get_connection()
    cursor = conn.cursor()

    title = input("Advisory title: ")

    # Advisory types
    advisory_types = [
        'Disease Outbreak',
        'Safety Alert',
        'Vaccination Reminder',
        'Wellness Tip',
        'Emergency Notice',
        'Policy Update',
        'Seasonal Health',
        'General Information'
    ]

    print("\nAdvisory Types:")
    for i, advisory_type in enumerate(advisory_types):
        print(f"{i+1}. {advisory_type}")

    while True:
        type_choice = input("\nSelect advisory type (1-8): ")
        if type_choice.isdigit() and 1 <= int(type_choice) <= len(advisory_types):
            advisory_type = advisory_types[int(type_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    content = input("Advisory content: ")

    # Priority levels
    priority_levels = ['Low', 'Medium', 'High', 'Critical']
    print("\nPriority Levels:")
    for i, priority in enumerate(priority_levels):
        print(f"{i+1}. {priority}")

    while True:
        priority_choice = input("\nSelect priority (1-4): ")
        if priority_choice.isdigit() and 1 <= int(priority_choice) <= len(priority_levels):
            priority = priority_levels[int(priority_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    # Target audience
    target_audiences = ['All Students', 'Specific Groups', 'Staff Only', 'High Risk Students']
    print("\nTarget Audience:")
    for i, audience in enumerate(target_audiences):
        print(f"{i+1}. {audience}")

    while True:
        audience_choice = input("\nSelect target audience (1-4): ")
        if audience_choice.isdigit() and 1 <= int(audience_choice) <= len(target_audiences):
            target_audience = target_audiences[int(audience_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    while True:
        effective_date = input("Effective date (YYYY-MM-DD) [today]: ").strip()
        if not effective_date:
            effective_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(effective_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        expiry_date = input("Expiry date (YYYY-MM-DD) [leave blank for no expiry]: ").strip()
        if not expiry_date:
            expiry_date = None
            break
        try:
            datetime.strptime(expiry_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO health_advisories
    (title, advisory_type, content, priority, target_audience, effective_date,
     expiry_date, issued_by, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, advisory_type, content, priority, target_audience, effective_date,
          expiry_date, auth.current_user['username'], 'active', created_at))

    conn.commit()
    advisory_id = cursor.lastrowid

    log_audit_event(auth.current_user['id'], 'issue_health_advisory', 'health_advisory', advisory_id)

    print("\nHealth advisory issued successfully!")
    print(f"Advisory ID: {advisory_id}")

    # Automatically send email notifications to target audience
    try:
        # Get students based on target audience
        if target_audience == 'All Students':
            cursor.execute('SELECT student_id FROM students WHERE status = "active"')
        elif target_audience == 'High Risk Students':
            # Send to students with chronic conditions or recent health issues
            cursor.execute('''
                SELECT DISTINCT mr.student_id
                FROM medical_records mr
                WHERE mr.record_type IN ('chronic_condition', 'prescription')
                AND mr.student_id IN (SELECT student_id FROM students WHERE status = "active")
            ''')
        elif target_audience == 'Staff Only':
            # Send to staff/faculty
            cursor.execute('''
                SELECT id as student_id FROM users
                WHERE role IN ('staff', 'admin', 'instructor') AND is_active = 1
            ''')
        else:  # Specific Groups - send to all active students as fallback
            cursor.execute('SELECT student_id FROM students WHERE status = "active"')

        students = cursor.fetchall()
        notification_count = 0

        for (student_id,) in students:
            try:
                send_health_notification(student_id, title, content, priority)
                notification_count += 1
            except Exception as e:
                print(f"Warning: Could not send notification to student {student_id}: {e}")

        print(f"✉️  Automatic email notifications sent to {notification_count} recipients")
        if priority == 'Critical':
            print("🚨 CRITICAL ADVISORY - Email notifications sent to all relevant parties")
    except Exception as e:
        print(f"Warning: Could not send email notifications: {e}")

    conn.close()



def view_health_advisories(auth):
    if not (auth.check_permission('view_health_advisories') or auth.check_permission('issue_health_advisories')):
        print("You don't have permission to view health advisories.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nFilter options:")
    print("1. All active advisories")
    print("2. By priority")
    print("3. By type")
    print("4. Recent advisories (last 30 days)")

    filter_choice = input("\nSelect filter (1-4): ")

    if filter_choice == '1':
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE status = 'active' AND (expiry_date IS NULL OR expiry_date >= ?)
        ORDER BY priority DESC, effective_date DESC
        ''', (datetime.now().strftime('%Y-%m-%d'),))

    elif filter_choice == '2':
        priority = input("Enter priority (Low/Medium/High/Critical): ")
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE priority = ? AND status = 'active'
        ORDER BY effective_date DESC
        ''', (priority,))

    elif filter_choice == '3':
        advisory_type = input("Enter advisory type: ")
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE advisory_type LIKE ? AND status = 'active'
        ORDER BY effective_date DESC
        ''', (f'%{advisory_type}%',))

    elif filter_choice == '4':
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
        SELECT id, title, advisory_type, priority, target_audience, effective_date,
               expiry_date, issued_by, status
        FROM health_advisories
        WHERE effective_date >= ?
        ORDER BY effective_date DESC
        ''', (thirty_days_ago,))

    else:
        print("Invalid choice.")
        conn.close()
        return

    advisories = cursor.fetchall()

    if not advisories:
        print("No health advisories found.")
        conn.close()
        return

    print("\n===== Health Advisories =====")
    for advisory in advisories:
        adv_id, title, adv_type, priority, target_audience, effective_date, expiry_date, issued_by, status = advisory

        print(f"\nID: {adv_id}")
        print(f"Title: {title}")
        print(f"Type: {adv_type}")
        print(f"Priority: {priority}")
        print(f"Target: {target_audience}")
        print(f"Effective: {effective_date}")
        print(f"Expires: {expiry_date if expiry_date else 'No expiry'}")
        print(f"Issued by: {issued_by}")

        # Priority indicators
        if priority == 'Critical':
            print("🚨 CRITICAL ADVISORY")
        elif priority == 'High':
            print("🔴 HIGH PRIORITY")
        elif priority == 'Medium':
            print("🟡 MEDIUM PRIORITY")

        # Show content if requested
        view_content = input("View full content? (y/n): ").lower()
        if view_content == 'y':
            cursor.execute('SELECT content FROM health_advisories WHERE id = ?', (adv_id,))
            content = cursor.fetchone()[0]
            print(f"Content: {content}")

        print("-" * 30)

    conn.close()



