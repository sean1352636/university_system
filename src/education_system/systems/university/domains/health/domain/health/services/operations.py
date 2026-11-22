from __future__ import annotations

from datetime import datetime

from education_system.systems.university.domains.health.domain.health.services.audit import log_audit_event
from education_system.systems.university.infrastructure.database.data_backup import backup_before_operation
from education_system.systems.university.domains.health.infrastructure.health.storage import get_connection
from education_system.systems.university.infrastructure.i18n import get_text
from education_system.systems.university.domains.health.domain.health.prompting import ask as _ask

def block_time_slots(auth, values=None):
    """Block specific time slots for providers"""
    backup_before_operation('block_time_slots')

    conn = get_connection()
    cursor = conn.cursor()

    provider_name = _ask(values, "provider_name", "Provider name: ")

    while True:
        block_date = _ask(values, "block_date", "Date to block (YYYY-MM-DD): ")
        try:
            datetime.strptime(block_date, '%Y-%m-%d')
            break
        except ValueError:
            print(get_text("health.operations.invalid_date_format", default="Invalid date format. Please use YYYY-MM-DD."))

    while True:
        start_time = _ask(values, "start_time", "Start time (HH:MM): ")
        try:
            datetime.strptime(start_time, '%H:%M')
            break
        except ValueError:
            print(get_text("health.operations.invalid_time_format", default="Invalid time format. Please use HH:MM."))

    while True:
        end_time = _ask(values, "end_time", "End time (HH:MM): ")
        try:
            datetime.strptime(end_time, '%H:%M')
            break
        except ValueError:
            print(get_text("health.operations.invalid_time_format", default="Invalid time format. Please use HH:MM."))

    reason = _ask(values, "reason", "Reason for blocking: ")

    # A blocked slot is provider time off for those hours (provider_time_off),
    # which every booking screen refuses — not a fake 'BLOCKED' appointment
    # (which also failed the students foreign key).
    from education_system.systems.university.domains.health.application.health import diary
    block_id, affected = diary.add_time_off(
        conn, provider=provider_name, start_date=block_date, end_date=block_date,
        start_time=start_time, end_time=end_time, reason=f"Blocked: {reason}",
        by=auth.current_user.get('username'))
    log_audit_event(auth.current_user['id'], 'block_time_slots', 'provider_time_off', block_id,
                    conn=conn)
    conn.commit()
    for appt in affected:
        print(f"  Note: {appt['date']} {appt['time']} {appt['type']} (student {appt['student_id']}) "
              "is already booked in this period.")
    print(get_text("health.operations.time_slot_blocked", provider=provider_name, date=block_date, start=start_time, end=end_time, default="Time Slot Blocked: {date} {end} {provider} {start}"))
    conn.close()

def patient_queue(auth, values=None):
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

    print(get_text("health.operations.patient_queue_title", date=today, default="===== PATIENT QUEUE ===== {date}"))

    if not queue:
        print(get_text("health.operations.no_patients_in_queue"))
        conn.close()
        return

    for apt_id, apt_time, first_name, last_name, student_id, apt_type, reason, status in queue:
        status_icon = "🟡" if status == 'checked_in' else "⏳"
        print(get_text("health.operations.queue_patient_header", icon=status_icon, time=apt_time, first_name=first_name, last_name=last_name, default="Queue Patient: {first_name} {icon} {last_name} {time}"))
        print(get_text("health.operations.queue_patient_id", student_id=student_id, default="Queue Patient ID: {student_id}"))
        print(get_text("health.operations.queue_patient_type", apt_type=apt_type, default="Queue Patient Type: {apt_type}"))
        print(get_text("health.operations.queue_patient_reason", reason=reason, default="Queue Patient Reason: {reason}"))
        print(get_text("health.operations.queue_patient_status", status=status, default="Queue Patient Status: {status}"))

        if status == 'checked_in':
            print(get_text("health.operations.ready_for_provider", default="Ready For Provider"))

    # Quick actions
    print(get_text("health.operations.quick_actions_title", default="===== QUICK ACTIONS ====="))
    print(get_text("health.operations.quick_action_mark_seen", default="Quick Action Mark Seen"))
    print(get_text("health.operations.quick_action_add_walkin", default="Quick Action Add Walkin"))
    print(get_text("health.operations.quick_action_return", default="Quick Action Return"))

    action = _ask(values, "action", get_text("health.operations.select_action_1_3", default="Select Action 1 3"))

    if action == '1':
        apt_id = _ask(values, "appointment_id", get_text("health.operations.enter_appointment_id", default="Enter Appointment ID: "))
        cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?',
                      ('completed', apt_id))
        conn.commit()
        print(get_text("health.operations.patient_marked_seen", default="Patient Marked Seen"))

    elif action == '2':
        student_id = _ask(values, "student_id", "Student ID: ").strip()
        reason = _ask(values, "reason", "Reason for visit: ").strip()
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

    print(get_text("health.operations.pending_tasks_title", default="===== PENDING TASKS ====="))

    tasks = []

    # Unverified vaccinations
    cursor.execute('''
    SELECT COUNT(*) FROM vaccination_records
    WHERE verified = 0
    ''')
    unverified_vax = cursor.fetchone()[0]

    if unverified_vax > 0:
        tasks.append(get_text("health.operations.task_vaccination_verification", count=unverified_vax, default="Task Vaccination Verification: {count}"))

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
        tasks.append(get_text("health.operations.task_care_plans_review", count=stale_care_plans, default="Task Care Plans Review: {count}"))

    # Students without emergency contacts
    cursor.execute('''
    SELECT COUNT(DISTINCT s.student_id)
    FROM students s
    LEFT JOIN emergency_contacts ec ON s.student_id = ec.student_id
    WHERE ec.student_id IS NULL
    ''')
    no_emergency_contacts = cursor.fetchone()[0]

    if no_emergency_contacts > 0:
        tasks.append(get_text("health.operations.task_missing_emergency_contacts", count=no_emergency_contacts, default="Task Missing Emergency Contacts: {count}"))

    if tasks:
        for task in tasks:
            print(f"  {task}")
    else:
        print(get_text("health.operations.no_pending_tasks", default="No Pending Tasks."))

    conn.close()

def quick_patient_lookup(auth, values=None):
    """Quick patient lookup"""
    conn = get_connection()
    cursor = conn.cursor()

    search_term = _ask(values, "search_term", get_text("health.operations.enter_search_term", default="Enter Search Term: ")).strip()

    if not search_term:
        print(get_text("health.operations.please_enter_search_term", default="Please enter a search term."))
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
        print(get_text("health.operations.no_students_found", default="No students found."))
        conn.close()
        return

    print(get_text("health.operations.search_results_header", search_term=search_term, default="Search Results: {search_term}"))

    for i, (student_id, first_name, last_name, age, gender) in enumerate(students):
        print(get_text("health.operations.search_result_item", num=i+1, last_name=last_name, first_name=first_name, student_id=student_id, age=age, gender=gender, default="Search Result Item: {age} {first_name} {gender} {last_name} {num} {student_id}"))

    if len(students) == 1:
        selected_student = students[0]
    else:
        while True:
            choice = _ask(values, "choice", get_text("health.operations.select_student_prompt", count=len(students), default="Select Student {count}: "))
            if choice.lower() == 'q':
                conn.close()
                return
            if choice.isdigit() and 1 <= int(choice) <= len(students):
                selected_student = students[int(choice) - 1]
                break
            print(get_text("health.operations.invalid_choice", default="Invalid choice. Please try again."))

    # Show quick summary
    student_id, first_name, last_name, age, gender = selected_student

    print(get_text("health.operations.quick_summary_header", first_name=first_name, last_name=last_name, default="Quick Summary: {first_name} {last_name}"))

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
        print(get_text("health.operations.recent_appointments", default="Recent Appointments"))
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
        print(get_text("health.operations.active_conditions", default="Active Conditions"))
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
        print(get_text("health.operations.critical_allergies", default="Critical Allergies"))
        for allergen, severity in critical_allergies:
            print(f"  🚨 {allergen} ({severity})")

    conn.close()

def external_system_connections(auth):
    """External health systems: what the portal really exchanges with them.

    There is no live connection to a laboratory, insurer, registry or
    hospital system. Lab results and insurer verifications are entered by
    hand or imported from files and recorded as integration events
    (``application/health/integrations``); this shows those, not made-up
    connection states."""
    from education_system.systems.university.domains.health.application.health import (
        integrations,
    )
    print(get_text("health.operations.external_systems_header"))
    print("No external system is connected live. Results and verifications are recorded")
    print("by manual entry or file import, and are listed here from those records.\n")
    conn = get_connection(row_factory=False)
    try:
        summary = integrations.health_summary(conn)
        recent = {name: integrations.recent_events(conn, table, limit=5) for name, table in (
            ("Laboratory results", "lab_integration_events"),
            ("Insurance verification", "insurance_integration_events"))}
    except Exception as exc:
        print(f"Integration records could not be read: {exc}")
        return
    finally:
        conn.close()
    print(get_text("health.operations.external_system_status", default="External System Status"))
    for i, item in enumerate(summary, 1):
        print(f"{i}. {item['system']}  ({item['mode']})")
        print(get_text("health.operations.last_sync_label", last_sync=item['last_activity'] or 'never',
                       default="Last Sync: {last_sync}"))
        print(f"   Events (30 days): {item['events_30d']}   failures: {item['failures_30d']}")
        for at, event_type, status, patient, _payload in recent.get(item['system'], []):
            print(f"     {at}  {event_type}  {status}  student {patient or '-'}")
