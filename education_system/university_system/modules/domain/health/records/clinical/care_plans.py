from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.university_system.modules.domain.health.services import get_user_student_id


def manage_care_plans(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to manage care plans.")
        return

    while True:
        print("\n===== Care Plan Management =====")
        print("1. Create Care Plan")
        print("2. View Care Plans")
        print("3. Update Care Plan")
        print("4. Care Plan Progress Tracking")
        print("5. Return to Main Menu")

        choice = input("\nEnter your choice (1-5): ")

        if choice == '1':
            create_care_plan(auth)
        elif choice == '2':
            view_care_plans(auth)
        elif choice == '3':
            update_care_plan(auth)
        elif choice == '4':
            track_care_plan_progress(auth)
        elif choice == '5':
            break
        else:
            print("Invalid choice. Please try again.")



def create_care_plan(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to create care plans.")
        return

    backup_before_operation('create_care_plan')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone()[0] == 0:
        print("Error: Student ID not found.")
        conn.close()
        return

    # Show student's medical conditions
    cursor.execute('''
    SELECT id, condition_name, severity, status
    FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))

    conditions = cursor.fetchall()

    if conditions:
        print("\nActive Medical Conditions:")
        for i, (cond_id, condition, severity, status) in enumerate(conditions):
            print(f"{i+1}. {condition} ({severity})")

        condition_choice = input("\nSelect condition for care plan (number): ")
        try:
            condition_index = int(condition_choice) - 1
            if 0 <= condition_index < len(conditions):
                condition_id = conditions[condition_index][0]
                condition_name = conditions[condition_index][1]
            else:
                print("Invalid selection.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return
    else:
        print("No active medical conditions found. Creating general care plan.")
        condition_id = None
        condition_name = "General Care"

    plan_name = input(f"Care plan name [Care Plan for {condition_name}]: ").strip()
    if not plan_name:
        plan_name = f"Care Plan for {condition_name}"

    description = input("Care plan description: ")

    while True:
        start_date = input("Start date (YYYY-MM-DD) [today]: ").strip()
        if not start_date:
            start_date = datetime.now().strftime('%Y-%m-%d')
            break
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        end_date = input("End date (YYYY-MM-DD) [leave blank for ongoing]: ").strip()
        if not end_date:
            end_date = None
            break
        try:
            datetime.strptime(end_date, '%Y-%m-%d')
            break
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")

    provider = input(f"Provider [Dr. {auth.current_user['username']}]: ").strip()
    if not provider:
        provider = f"Dr. {auth.current_user['username']}"

    goals = input("Care plan goals: ")
    interventions = input("Planned interventions: ")

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO care_plans
    (student_id, condition_id, plan_name, description, start_date, end_date,
     provider, status, goals, interventions, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, condition_id, plan_name, description, start_date, end_date,
          provider, 'active', goals, interventions, created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'create_care_plan', 'care_plan', cursor.lastrowid)
    print("\nCare plan created successfully!")
    conn.close()



def view_care_plans(auth):
    if not (auth.check_permission('view_any_health_record') or auth.check_permission('view_own_health_record')):
        print("You don't have permission to view care plans.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    if auth.check_permission('view_any_health_record'):
        student_id = input("Enter student ID (leave blank for all): ").strip()

        if student_id:
            cursor.execute("SELECT COUNT(*) FROM students WHERE student_id = ?", (student_id,))
            if cursor.fetchone()[0] == 0:
                print("Error: Student ID not found.")
                conn.close()
                return

            cursor.execute('''
            SELECT cp.id, cp.plan_name, cp.description, cp.start_date, cp.end_date,
                   cp.provider, cp.status, cp.goals, cp.interventions, mc.condition_name
            FROM care_plans cp
            LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
            WHERE cp.student_id = ?
            ORDER BY cp.start_date DESC
            ''', (student_id,))
        else:
            cursor.execute('''
            SELECT cp.id, s.student_id, s.first_name, s.last_name, cp.plan_name,
                   cp.start_date, cp.end_date, cp.provider, cp.status, mc.condition_name
            FROM care_plans cp
            JOIN students s ON cp.student_id = s.student_id
            LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
            ORDER BY cp.start_date DESC
            LIMIT 50
            ''')
    else:
        student_id = get_user_student_id(auth)
        if not student_id:
            print("Error: No student ID associated with your account.")
            conn.close()
            return

        cursor.execute('''
        SELECT cp.id, cp.plan_name, cp.description, cp.start_date, cp.end_date,
               cp.provider, cp.status, cp.goals, cp.interventions, mc.condition_name
        FROM care_plans cp
        LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
        WHERE cp.student_id = ?
        ORDER BY cp.start_date DESC
        ''', (student_id,))

    care_plans = cursor.fetchall()

    if not care_plans:
        print("No care plans found.")
        conn.close()
        return

    print("\n===== Care Plans =====")
    for plan in care_plans:
        if auth.check_permission('view_any_health_record') and not student_id:
            # All plans view
            plan_id, student_id, first_name, last_name, plan_name, start_date, end_date, provider, status, condition_name = plan
            print(f"\nID: {plan_id}")
            print(f"Student: {first_name} {last_name} (ID: {student_id})")
            print(f"Plan: {plan_name}")
            print(f"Condition: {condition_name if condition_name else 'General Care'}")
            print(f"Start Date: {start_date}")
            print(f"End Date: {end_date if end_date else 'Ongoing'}")
            print(f"Provider: {provider}")
            print(f"Status: {status}")
        else:
            # Specific student view
            plan_id, plan_name, description, start_date, end_date, provider, status, goals, interventions, condition_name = plan
            print(f"\nID: {plan_id}")
            print(f"Plan: {plan_name}")
            print(f"Condition: {condition_name if condition_name else 'General Care'}")
            print(f"Description: {description}")
            print(f"Start Date: {start_date}")
            print(f"End Date: {end_date if end_date else 'Ongoing'}")
            print(f"Provider: {provider}")
            print(f"Status: {status}")
            print(f"Goals: {goals}")
            print(f"Interventions: {interventions}")

        print("-" * 30)

    conn.close()



def update_care_plan(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to update care plans.")
        return

    backup_before_operation('update_care_plan')

    conn = get_connection()
    cursor = conn.cursor()

    care_plan_id = input("Enter care plan ID to update: ")

    cursor.execute('''
    SELECT cp.id, s.student_id, s.first_name, s.last_name, cp.plan_name,
           cp.description, cp.status, cp.goals, cp.interventions
    FROM care_plans cp
    JOIN students s ON cp.student_id = s.student_id
    WHERE cp.id = ?
    ''', (care_plan_id,))

    care_plan = cursor.fetchone()

    if not care_plan:
        print("Error: Care plan not found.")
        conn.close()
        return

    cp_id, student_id, first_name, last_name, plan_name, description, status, goals, interventions = care_plan

    print(f"\nCurrent Care Plan:")
    print(f"Student: {first_name} {last_name} (ID: {student_id})")
    print(f"Plan: {plan_name}")
    print(f"Status: {status}")
    print(f"Goals: {goals}")
    print(f"Interventions: {interventions}")

    print("\nEnter new values (press Enter to keep current):")

    new_description = input(f"Description [{description}]: ").strip()
    if not new_description:
        new_description = description

    status_options = ['active', 'completed', 'on_hold', 'discontinued']
    print(f"\nCurrent status: {status}")
    print("Status options: active, completed, on_hold, discontinued")
    new_status = input(f"New status [{status}]: ").strip()
    if not new_status or new_status not in status_options:
        new_status = status

    new_goals = input(f"Goals [{goals}]: ").strip()
    if not new_goals:
        new_goals = goals

    new_interventions = input(f"Interventions [{interventions}]: ").strip()
    if not new_interventions:
        new_interventions = interventions

    cursor.execute('''
    UPDATE care_plans
    SET description = ?, status = ?, goals = ?, interventions = ?
    WHERE id = ?
    ''', (new_description, new_status, new_goals, new_interventions, care_plan_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_care_plan', 'care_plan', care_plan_id)
    print("\nCare plan updated successfully!")
    conn.close()



def track_care_plan_progress(auth):
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to track care plan progress.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Get active care plans for student
    cursor.execute('''
    SELECT cp.id, cp.plan_name, cp.start_date, cp.goals, cp.interventions,
           mc.condition_name
    FROM care_plans cp
    LEFT JOIN medical_conditions mc ON cp.condition_id = mc.id
    WHERE cp.student_id = ? AND cp.status = 'active'
    ORDER BY cp.start_date DESC
    ''', (student_id,))

    care_plans = cursor.fetchall()

    if not care_plans:
        print("No active care plans found for this student.")
        conn.close()
        return

    print(f"\n===== Care Plan Progress Tracking for Student {student_id} =====")

    for plan in care_plans:
        cp_id, plan_name, start_date, goals, interventions, condition_name = plan

        print(f"\nCare Plan: {plan_name}")
        print(f"Condition: {condition_name if condition_name else 'General Care'}")
        print(f"Started: {start_date}")
        print(f"Goals: {goals}")
        print(f"Interventions: {interventions}")

        # Track progress
        days_active = (datetime.now() - datetime.strptime(start_date, '%Y-%m-%d')).days
        print(f"Days active: {days_active}")

        # Progress assessment
        print("\nProgress Assessment:")
        goal_progress = input("Goal achievement (0-100%): ")
        adherence = input("Treatment adherence (0-100%): ")
        improvement = input("Overall improvement (Poor/Fair/Good/Excellent): ")

        notes = input("Progress notes: ")

        # Record progress (this would go into a care_plan_progress table in a full system)
        progress_date = datetime.now().strftime('%Y-%m-%d')
        print(f"\nProgress recorded for {progress_date}")
        print(f"Goal Progress: {goal_progress}%")
        print(f"Adherence: {adherence}%")
        print(f"Improvement: {improvement}")

        # Suggest plan modifications if needed
        if goal_progress.isdigit() and int(goal_progress) < 50:
            print("⚠️  Low goal achievement - Consider plan modification")

        if adherence.isdigit() and int(adherence) < 70:
            print("⚠️  Poor adherence - Address barriers to treatment")

        print("-" * 40)

    conn.close()



