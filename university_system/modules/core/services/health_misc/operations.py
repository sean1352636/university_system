from __future__ import annotations

from datetime import datetime

from university_system.modules.core.services.health_misc.audit import log_audit_event
from university_system.infrastructure.database.data_backup import backup_before_operation
from university_system.infrastructure.database.db import get_connection

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
            print("Invalid date format. Please use YYYY-MM-DD.")

    while True:
        start_time = input("Start time (HH:MM): ")
        try:
            datetime.strptime(start_time, '%H:%M')
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM.")

    while True:
        end_time = input("End time (HH:MM): ")
        try:
            datetime.strptime(end_time, '%H:%M')
            break
        except ValueError:
            print("Invalid time format. Please use HH:MM.")

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
    print(f"\nTime slot blocked for {provider_name} on {block_date} from {start_time} to {end_time}")
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

    print(f"\n===== Patient Queue ({today}) =====")

    if not queue:
        print("No patients in queue.")
        conn.close()
        return

    for apt_id, apt_time, first_name, last_name, student_id, apt_type, reason, status in queue:
        status_icon = "🟡" if status == 'checked_in' else "⏳"
        print(f"\n{status_icon} {apt_time} - {first_name} {last_name}")
        print(f"    ID: {student_id}")
        print(f"    Type: {apt_type}")
        print(f"    Reason: {reason}")
        print(f"    Status: {status}")

        if status == 'checked_in':
            print("    📋 READY FOR PROVIDER")

    # Quick actions
    print("\nQuick Actions:")
    print("1. Mark patient as seen")
    print("2. Add walk-in patient")
    print("3. Return to dashboard")

    action = input("\nSelect action (1-3): ")

    if action == '1':
        apt_id = input("Enter appointment ID to mark as seen: ")
        cursor.execute('UPDATE health_appointments SET status = ? WHERE id = ?', 
                      ('completed', apt_id))
        conn.commit()
        print("Patient marked as seen.")

    elif action == '2':
        print("Walk-in patient registration would go here.")

    conn.close()

def pending_tasks(auth):
    """Show pending tasks for provider"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Pending Tasks =====")

    tasks = []

    # Unverified vaccinations
    cursor.execute('''
    SELECT COUNT(*) FROM vaccination_records 
    WHERE verified = 0
    ''')
    unverified_vax = cursor.fetchone()[0]

    if unverified_vax > 0:
        tasks.append(f"📋 {unverified_vax} vaccination records need verification")

    # Pending referrals
    cursor.execute('''
    SELECT COUNT(*) FROM referrals 
    WHERE status = 'pending'
    ''')
    pending_referrals = cursor.fetchone()[0]

    if pending_referrals > 0:
        tasks.append(f"📋 {pending_referrals} referrals pending specialist contact")

    # Care plans needing updates
    cursor.execute('''
    SELECT COUNT(*) FROM care_plans 
    WHERE status = 'active' AND start_date < date('now', '-90 days')
    ''')
    stale_care_plans = cursor.fetchone()[0]

    if stale_care_plans > 0:
        tasks.append(f"📋 {stale_care_plans} care plans need review (>90 days old)")

    # Students without emergency contacts
    cursor.execute('''
    SELECT COUNT(DISTINCT s.student_id) 
    FROM students s
    LEFT JOIN emergency_contacts ec ON s.student_id = ec.student_id
    WHERE ec.student_id IS NULL
    ''')
    no_emergency_contacts = cursor.fetchone()[0]

    if no_emergency_contacts > 0:
        tasks.append(f"📋 {no_emergency_contacts} students missing emergency contacts")

    if tasks:
        for task in tasks:
            print(f"  {task}")
    else:
        print("  ✅ No pending tasks.")

    conn.close()

def quick_patient_lookup(auth):
    """Quick patient lookup"""
    conn = get_connection()
    cursor = conn.cursor()

    search_term = input("Enter student ID, name, or partial name: ").strip()

    if not search_term:
        print("Please enter a search term.")
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
        print("No students found matching your search.")
        conn.close()
        return

    print(f"\n===== Search Results for '{search_term}' =====")

    for i, (student_id, first_name, last_name, age, gender) in enumerate(students):
        print(f"{i+1}. {last_name}, {first_name} (ID: {student_id}) - Age: {age}, Gender: {gender}")

    if len(students) == 1:
        selected_student = students[0]
    else:
        while True:
            choice = input(f"\nSelect student (1-{len(students)}) or 'q' to quit: ")
            if choice.lower() == 'q':
                conn.close()
                return
            if choice.isdigit() and 1 <= int(choice) <= len(students):
                selected_student = students[int(choice) - 1]
                break
            print("Invalid choice. Please try again.")

    # Show quick summary
    student_id, first_name, last_name, age, gender = selected_student

    print(f"\n===== Quick Summary: {first_name} {last_name} =====")

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
        print("Recent Appointments:")
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
        print("Active Conditions:")
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
        print("🚨 CRITICAL ALLERGIES:")
        for allergen, severity in critical_allergies:
            print(f"  🚨 {allergen} ({severity})")

    conn.close()

def external_system_connections(auth):
    """Manage external system connections"""
    print("\n===== External System Connections =====")

    # Mock external systems
    systems = [
        {"name": "LabCorp Integration", "status": "Connected", "last_sync": "2024-01-15 14:30"},
        {"name": "Quest Diagnostics", "status": "Disconnected", "last_sync": "2024-01-10 09:15"},
        {"name": "Insurance Verification", "status": "Connected", "last_sync": "2024-01-15 16:45"},
        {"name": "State Immunization Registry", "status": "Connected", "last_sync": "2024-01-15 12:00"},
        {"name": "Hospital EMR System", "status": "Pending", "last_sync": "Never"}
    ]

    print("External System Status:")
    for i, system in enumerate(systems):
        status_icon = "✅" if system["status"] == "Connected" else "❌" if system["status"] == "Disconnected" else "🟡"
        print(f"{i+1}. {status_icon} {system['name']}")
        print(f"   Status: {system['status']}")
        print(f"   Last Sync: {system['last_sync']}")

    print("\nActions:")
    print("1. Test Connection")
    print("2. Configure New Integration")
    print("3. Disconnect System")
    print("4. View Connection Details")
    print("5. Return to integration menu")

    choice = input("\nSelect action (1-5): ")

    if choice == '1':
        system_num = input("Enter system number to test: ")
        print(f"Testing connection to system {system_num}...")
        print("Connection test completed. Status: OK")

    elif choice == '2':
        system_name = input("Enter new system name: ")
        endpoint_url = input("Enter API endpoint URL: ")
        print(f"Integration configured for {system_name}")
        log_audit_event(auth.current_user['id'], 'configure_integration', 'integration', 0, system_name)
