from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domain.pastoral.health.records.db.audit import log_audit_event
from education_system.systems.university.domain.pastoral.health.services import get_user_student_id


def manage_medical_conditions(auth):
    """Manage chronic medical conditions"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage medical conditions.")
        return

    while True:
        print("\n===== Medical Conditions Management =====")
        print("1. Add Medical Condition")
        print("2. View Medical Conditions")
        print("3. Update Condition Status")
        print("4. Condition Management Plans")
        print("5. Return to Previous Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            add_medical_condition(auth)
        elif choice == '2':
            view_medical_conditions(auth)
        elif choice == '3':
            update_condition_status(auth)
        elif choice == '4':
            condition_management_plans(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")



def add_medical_condition(auth):
    backup_before_operation('add_medical_condition')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return

    condition_name = input("Condition name: ")
    icd_code = input("ICD-10 code (optional): ")

    severity_levels = ['Mild', 'Moderate', 'Severe']
    print("\nSeverity Levels:")
    for i, level in enumerate(severity_levels):
        print(f"{i+1}. {level}")

    while True:
        severity_choice = input("\nSelect severity (1-3): ")
        if severity_choice.isdigit() and 1 <= int(severity_choice) <= len(severity_levels):
            severity = severity_levels[int(severity_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    while True:
        diagnosed_date = input("Diagnosed date (YYYY-MM-DD): ")
        try:
            datetime.strptime(diagnosed_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    provider = input(f"Diagnosing provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"

    notes = input("Additional notes: ")

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO medical_conditions
    (student_id, condition_name, icd_code, severity, diagnosed_date, status, provider, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, condition_name, icd_code, severity, diagnosed_date, 'active', provider, notes, created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'add_medical_condition', 'medical_condition', cursor.lastrowid)
    print("\nMedical condition added successfully!")
    conn.close()



def view_medical_conditions(auth):
    """View medical conditions - either for a specific student or summary view"""
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view medical conditions.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if auth.check_permission('view_any_health_record'):
            student_id = input("Enter student ID (leave blank for summary): ").strip()

            if student_id:
                # Check if student exists
                cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
                if cursor.fetchone()[0] == 0:
                    print("Error: Student ID not found.")
                    return

                # Get specific student's medical conditions
                cursor.execute('''
                SELECT id, condition_name, icd_code, severity, diagnosed_date, status,
                       provider, notes
                FROM medical_conditions
                WHERE student_id = ?
                ORDER BY diagnosed_date DESC
                ''', (student_id,))

                conditions = cursor.fetchall()

                if not conditions:
                    print(f"No medical conditions found for student ID: {student_id}")
                    return

                print(f"\n===== Medical Conditions for Student {student_id} =====")
                for condition in conditions:
                    condition_id, name, icd_code, severity, diagnosed_date, status, provider, notes = condition
                    print(f"\nCondition ID: {condition_id}")
                    print(f"Condition: {name}")
                    print(f"ICD Code: {icd_code}")
                    print(f"Severity: {severity}")
                    print(f"Diagnosed: {diagnosed_date}")
                    print(f"Status: {status}")
                    print(f"Provider: {provider}")
                    if notes:
                        print(f"Notes: {notes}")
                    print("-" * 40)
            else:
                # Summary view - all active conditions
                cursor.execute('''
                SELECT mc.condition_name, mc.severity, COUNT(*) as count,
                       GROUP_CONCAT(s.first_name || ' ' || s.last_name) as students,
                       GROUP_CONCAT(mc.student_id) as student_ids
                FROM medical_conditions mc
                JOIN students s ON mc.student_id = s.student_id
                WHERE mc.status = 'active'
                GROUP BY mc.condition_name, mc.severity
                ORDER BY count DESC
                ''')

                summary = cursor.fetchall()

                if not summary:
                    print("No active medical conditions found.")
                    return

                print("\n===== Medical Conditions Summary =====")
                print(f"{'Condition':<25} {'Severity':<10} {'Count':<6} {'Students'}")
                print("-" * 70)

                for row in summary:
                    condition, severity, count, students, student_ids = row
                    # Truncate student list if too long
                    student_list = students if len(students) <= 50 else students[:47] + "..."
                    print(f"{condition:<25} {severity:<10} {count:<6} {student_list}")
        else:
            # User can only view their own conditions
            student_id = get_user_student_id(auth)
            if not student_id:
                print("Error: No student ID associated with your account.")
                return

            cursor.execute('''
            SELECT id, condition_name, icd_code, severity, diagnosed_date, status,
                   provider, notes
            FROM medical_conditions
            WHERE student_id = ?
            ORDER BY diagnosed_date DESC
            ''', (student_id,))

            conditions = cursor.fetchall()

            if not conditions:
                print("No medical conditions found for your account.")
                return

            print("\n===== Your Medical Conditions =====")
            for condition in conditions:
                condition_id, name, icd_code, severity, diagnosed_date, status, provider, notes = condition
                print(f"\nCondition ID: {condition_id}")
                print(f"Condition: {name}")
                print(f"ICD Code: {icd_code}")
                print(f"Severity: {severity}")
                print(f"Diagnosed: {diagnosed_date}")
                print(f"Status: {status}")
                print(f"Provider: {provider}")
                if notes:
                    print(f"Notes: {notes}")
                print("-" * 40)

    finally:
        conn.close()



def update_condition_status(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update condition status.")
        return

    backup_before_operation('update_condition_status')

    conn = get_connection()
    cursor = conn.cursor()

    condition_id = input("Enter condition ID to update: ")

    cursor.execute('''
    SELECT mc.id, s.student_id, s.first_name, s.last_name, mc.condition_name,
           mc.severity, mc.status, mc.provider
    FROM medical_conditions mc
    JOIN students s ON mc.student_id = s.student_id
    WHERE mc.id = ?
    ''', (condition_id,))

    condition = cursor.fetchone()

    if not condition:
        print("Error: Medical condition not found.")
        conn.close()
        return

    cond_id, student_id, first_name, last_name, condition_name, severity, current_status, provider = condition

    print("\nCondition Details:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Condition: {condition_name}")
    print(f"Severity: {severity}")
    print(f"Current Status: {current_status}")
    print(f"Provider: {provider}")

    status_options = ['active', 'resolved', 'managed', 'inactive']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")

    while True:
        choice = input("\nSelect new status (1-4): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    notes = input("Update notes (optional): ")

    cursor.execute('''
    UPDATE medical_conditions
    SET status = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
    WHERE id = ?
    ''', (new_status, notes, notes, condition_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_condition_status', 'medical_condition', condition_id,
                   f"Status changed from {current_status} to {new_status}")

    print(f"\nCondition status updated to '{new_status}' successfully!")

    # If condition is resolved, suggest care plan completion
    if new_status == 'resolved':
        cursor.execute('''
        SELECT id, plan_name FROM care_plans
        WHERE condition_id = ? AND status = 'active'
        ''', (condition_id,))

        active_plans = cursor.fetchall()
        if active_plans:
            print("\n📋 Active care plans found for this condition:")
            for plan_id, plan_name in active_plans:
                print(f"  - {plan_name} (ID: {plan_id})")

            complete_plans = input("Mark associated care plans as completed? (y/n): ").lower()
            if complete_plans == 'y':
                cursor.execute('''
                UPDATE care_plans
                SET status = 'completed', end_date = ?
                WHERE condition_id = ? AND status = 'active'
                ''', (datetime.now().strftime('%Y-%m-%d'), condition_id))
                conn.commit()
                print("Associated care plans marked as completed.")

    conn.close()



def condition_management_plans(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage condition plans.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Condition Management Plans =====")

    # Show common chronic conditions needing management
    cursor.execute('''
    SELECT condition_name, COUNT(*) as patient_count
    FROM medical_conditions
    WHERE status = 'active'
    GROUP BY condition_name
    ORDER BY patient_count DESC
    LIMIT 10
    ''')

    conditions = cursor.fetchall()

    if conditions:
        print("Conditions requiring active management:")
        for condition, count in conditions:
            print(f"- {condition}: {count} patients")

        # Show care plan coverage
        cursor.execute('''
        SELECT
            mc.condition_name,
            COUNT(DISTINCT mc.student_id) as total_patients,
            COUNT(DISTINCT cp.student_id) as with_care_plans
        FROM medical_conditions mc
        LEFT JOIN care_plans cp ON mc.id = cp.condition_id AND cp.status = 'active'
        WHERE mc.status = 'active'
        GROUP BY mc.condition_name
        ORDER BY total_patients DESC
        ''')

        coverage = cursor.fetchall()

        print("\nCare Plan Coverage:")
        for condition, total, with_plans in coverage:
            coverage_pct = (with_plans / total * 100) if total > 0 else 0
            print(f"{condition}: {with_plans}/{total} ({coverage_pct:.1f}%)")

            if coverage_pct < 50:
                print("  ⚠️  Low coverage - Consider developing care plans")

    # Template care plans for common conditions
    condition_templates = {
        'Diabetes': {
            'goals': 'Maintain HbA1c <7%, prevent complications, lifestyle management',
            'interventions': 'Blood glucose monitoring, medication adherence, diet counseling, exercise program'
        },
        'Hypertension': {
            'goals': 'Blood pressure <130/80, lifestyle modifications, medication adherence',
            'interventions': 'Regular BP monitoring, sodium reduction, weight management, stress reduction'
        },
        'Asthma': {
            'goals': 'Symptom control, prevent exacerbations, maintain normal activity',
            'interventions': 'Inhaler technique education, trigger avoidance, action plan, peak flow monitoring'
        }
    }

    print("\nAvailable care plan templates:")
    for condition, template in condition_templates.items():
        print(f"\n{condition}:")
        print(f"  Goals: {template['goals']}")
        print(f"  Interventions: {template['interventions']}")

    conn.close()



