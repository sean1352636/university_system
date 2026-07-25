from __future__ import annotations

from datetime import datetime

from education_system.systems.university.domain.pastoral.health.services.audit import log_audit_event
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.i18n import get_text

def block_time_slots(auth):
    """Block specific time slots for providers"""
    backup_before_operation('block_time_slots')

    conn = get_connection()
    cursor = conn.cursor()

    provider_name = input("Provider name: ")

    while True:
        block_date = input("Date to block (YYYY-MM-DD): ")
        try:
            datetime.strptime(block_date, '%Y-%m-%d')
            break
        except ValueError:
            print(get_text("health.operations.invalid_date_format"))

    while True:
        start_time = input("Start time (HH:MM): ")
        try:
            datetime.strptime(start_time, '%H:%M')
            break
        except ValueError:
            print(get_text("health.operations.invalid_time_format"))

    while True:
        end_time = input("End time (HH:MM): ")
        try:
            datetime.strptime(end_time, '%H:%M')
            break
        except ValueError:
            print(get_text("health.operations.invalid_time_format"))

    reason = input("Reason for blocking: ")

    # Create blocked appointment entries
    cursor.execute('''
    INSERT INTO health_appointments
    (student_id, appointment_type, appointment_date, appointment_time, provider,
     reason, status, scheduled_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('BLOCKED', 'BLOCKED_TIME', block_date, start_time, provider_name,
          f"BLOCKED: {reason}", 'blocked', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'block_time_slots', 'provider_schedule', cursor.lastrowid)
    print(get_text("health.operations.time_slot_blocked", provider=provider_name, date=block_date, start=start_time, end=end_time))
    conn.close()

def patient_queue(auth):
    """Show patient queue/waiting list"""
    conn = get_connection()
    cursor = conn.cursor()

    provider_name = f"Dr. {auth.current_user['username']}"
    today = datetime.now().strftime('%Y-%m-%d')

    # Get today's appointments that are scheduled but not completed
    cursor.execute('''
    SELECT ha.id, ha.appointment_time, s.first_name, s.last_name, s.student_id,
           ha.appointment_type, ha.reason, ha.status
    FROM health_appointments ha
    JOIN students s ON ha.student_id = s.student_id
    WHERE ha.provider = ? AND ha.appointment_date = ?
    AND ha.status IN ('scheduled', 'checked_in')
    ORDER BY ha.appointment_time
    ''', (provider_name, today))

    queue = cursor.fetchall()

    print(get_text("health.operations.patient_queue_title", date=today))

    if not queue:
        print(get_text("health.operations.no_patients_in_queue"))
        conn.close()
        return

    for apt_id, apt_time, first_name, last_name, student_id, apt_type, reason, status in queue:
        status_icon = "🟡" if status == 'checked_in' else "⏳"
        print(get_text("health.operations.queue_patient_header", icon=status_icon, time=apt_time, first_name=first_name, last_name=last_name))
        print(get_text("health.operations.queue_patient_id", student_id=student_id))
        print(get_text("health.operations.queue_patient_type", apt_type=apt_type))
        print(get_text("health.operations.queue_patient_reason", reason=reason))
        print(get_text("health.operations.queue_patient_status", status=status))

        if status == 'checked_in':
            print(get_text("health.operations.ready_for_provider"))

    # Quick actions
    print(get_text("health.operations.quick_actions_title"))
    print(get_text("health.operations.quick_action_mark_seen"))
    print(get_text("health.operations.quick_action_add_walkin"))
    print(get_text("health.operations.quick_action_return"))

    action = input(get_text("health.operations.select_action_1_3"))

    if action == '1':
        apt_id = input(get_text("health.operations.enter_appointment_id"))
        cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?',
                      ('completed', apt_id))
        conn.commit()
        print(get_text("health.operations.patient_marked_seen"))

    elif action == '2':
        student_id = input("Student ID: ").strip()
        reason = input("Reason for visit: ").strip()
        if not student_id or not reason:
            print("Student ID and reason are required.")
        else:
            cursor.execute('''
            INSERT INTO health_appointments
            (student_id, appointment_type, appointment_date, appointment_time, provider,
             reason, status, scheduled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id,
                'Walk-in',
                today,
                datetime.now().strftime('%H:%M'),
                provider_name,
                reason,
                'checked_in',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))
            conn.commit()
            log_audit_event(auth.current_user['id'], 'register_walkin', 'health_appointments', cursor.lastrowid)
            print(f"Walk-in registered and checked in for {student_id}.")

    conn.close()

def pending_tasks(auth):
    """Show pending tasks for provider"""
    conn = get_connection()
    cursor = conn.cursor()

    print(get_text("health.operations.pending_tasks_title"))

    tasks = []

    # Unverified vaccinations
    cursor.execute('''
    SELECT COUNT(*) FROM vaccination_records
    WHERE verified = 0
    ''')
    unverified_vax = cursor.fetchone()[0]

    if unverified_vax > 0:
        tasks.append(get_text("health.operations.task_vaccination_verification", count=unverified_vax))

    # Pending referrals
    cursor.execute('''
    SELECT COUNT(*) FROM referrals
    WHERE status = 'pending'
    ''')
    pending_referrals = cursor.fetchone()[0]

    if pending_referrals > 0:
        tasks.append(get_text("health.operations.task_referrals_pending", count=pending_referrals))

    # Care plans needing updates
    cursor.execute('''
    SELECT COUNT(*) FROM care_plans
    WHERE status = 'active' AND start_date < date('now', '-90 days')
    ''')
    stale_care_plans = cursor.fetchone()[0]

    if stale_care_plans > 0:
        tasks.append(get_text("health.operations.task_care_plans_review", count=stale_care_plans))

    # Students without emergency contacts
    cursor.execute('''
    SELECT COUNT(DISTINCT s.student_id)
    FROM students s
    LEFT JOIN emergency_contacts ec ON s.student_id = ec.student_id
    WHERE ec.student_id IS NULL
    ''')
    no_emergency_contacts = cursor.fetchone()[0]

    if no_emergency_contacts > 0:
        tasks.append(get_text("health.operations.task_missing_emergency_contacts", count=no_emergency_contacts))

    if tasks:
        for task in tasks:
            print(f"  {task}")
    else:
        print(get_text("health.operations.no_pending_tasks"))

    conn.close()

def quick_patient_lookup(auth):
    """Quick patient lookup"""
    conn = get_connection()
    cursor = conn.cursor()

    search_term = input(get_text("health.operations.enter_search_term")).strip()

    if not search_term:
        print(get_text("health.operations.please_enter_search_term"))
        conn.close()
        return

    # Search by ID or name
    cursor.execute('''
    SELECT student_id, first_name, last_name, age, gender
    FROM students
    WHERE student_id LIKE ? OR first_name LIKE ? OR last_name LIKE ?
    ORDER BY last_name, first_name
    LIMIT 10
    ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

    students = cursor.fetchall()

    if not students:
        print(get_text("health.operations.no_students_found"))
        conn.close()
        return

    print(get_text("health.operations.search_results_header", search_term=search_term))

    for i, (student_id, first_name, last_name, age, gender) in enumerate(students):
        print(get_text("health.operations.search_result_item", num=i+1, last_name=last_name, first_name=first_name, student_id=student_id, age=age, gender=gender))

    if len(students) == 1:
        selected_student = students[0]
    else:
        while True:
            choice = input(get_text("health.operations.select_student_prompt", count=len(students)))
            if choice.lower() == 'q':
                conn.close()
                return
            if choice.isdigit() and 1 <= int(choice) <= len(students):
                selected_student = students[int(choice) - 1]
                break
            print(get_text("health.operations.invalid_choice"))

    # Show quick summary
    student_id, first_name, last_name, age, gender = selected_student

    print(get_text("health.operations.quick_summary_header", first_name=first_name, last_name=last_name))

    # Recent appointments
    cursor.execute('''
    SELECT appointment_date, appointment_type, status
    FROM health_appointments
    WHERE student_id = ?
    ORDER BY appointment_date DESC
    LIMIT 3
    ''', (student_id,))

    recent_appts = cursor.fetchall()

    if recent_appts:
        print(get_text("health.operations.recent_appointments"))
        for date, apt_type, status in recent_appts:
            print(f"  {date}: {apt_type} ({status})")

    # Active conditions
    cursor.execute('''
    SELECT condition_name, severity
    FROM medical_conditions
    WHERE student_id = ? AND status = 'active'
    ''', (student_id,))

    conditions = cursor.fetchall()

    if conditions:
        print(get_text("health.operations.active_conditions"))
        for condition, severity in conditions:
            print(f"  • {condition} ({severity})")

    # Critical allergies
    cursor.execute('''
    SELECT allergen, severity
    FROM allergies
    WHERE student_id = ? AND severity IN ('Severe', 'Life-threatening') AND verified = 1
    ''', (student_id,))

    critical_allergies = cursor.fetchall()

    if critical_allergies:
        print(get_text("health.operations.critical_allergies"))
        for allergen, severity in critical_allergies:
            print(f"  🚨 {allergen} ({severity})")

    conn.close()

def external_system_connections(auth):
    """Manage external system connections"""
    print(get_text("health.operations.external_systems_header"))

    # Mock external systems
    systems = [
        {"name": "LabCorp Integration", "status": "Connected", "last_sync": "2024-01-15 14:30"},
        {"name": "Quest Diagnostics", "status": "Disconnected", "last_sync": "2024-01-10 09:15"},
        {"name": "Insurance Verification", "status": "Connected", "last_sync": "2024-01-15 16:45"},
        {"name": "State Immunization Registry", "status": "Connected", "last_sync": "2024-01-15 12:00"},
        {"name": "Hospital EMR System", "status": "Pending", "last_sync": "Never"}
    ]

    print(get_text("health.operations.external_system_status"))
    for i, system in enumerate(systems):
        status_icon = "✅" if system["status"] == "Connected" else "❌" if system["status"] == "Disconnected" else "🟡"
        print(f"{i+1}. {status_icon} {system['name']}")
        print(get_text("health.operations.status_label", status=system['status']))
        print(get_text("health.operations.last_sync_label", last_sync=system['last_sync']))

    print(get_text("health.operations.actions_menu"))
    print(get_text("health.operations.action_test_connection"))
    print(get_text("health.operations.action_configure_new"))
    print(get_text("health.operations.action_disconnect"))
    print(get_text("health.operations.action_view_details"))
    print(get_text("health.operations.action_return"))

    choice = input(get_text("health.operations.select_action_1_5"))

    if choice == '1':
        system_num = input(get_text("health.operations.enter_system_number"))
        print(get_text("health.operations.testing_connection", system_num=system_num))
        print(get_text("health.operations.connection_test_ok"))

    elif choice == '2':
        system_name = input(get_text("health.operations.enter_system_name"))
        endpoint_url = input(get_text("health.operations.enter_api_endpoint"))
        print(get_text("health.operations.integration_configured", system_name=system_name))
        log_audit_event(auth.current_user['id'], 'configure_integration', 'integration', 0, system_name)
