from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.post_18.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.post_18.university_system.modules.domain.health.services import specialist_directory


def manage_referrals(auth):
    """Referral management system"""
    if not auth.check_permission('manage_health_records'):
        print("You don't have permission to manage referrals.")
        return

    while True:
        print("\n===== Referral Management =====")
        print("1. Create New Referral")
        print("2. View Referrals")
        print("3. Update Referral Status")
        print("4. Specialist Directory")
        print("5. Referral Follow-up")
        print("6. Referral Reports")
        print("7. Return to Main Menu")

        choice = input("\nEnter your choice (1-7): ")

        if choice == '1':
            create_referral(auth)
        elif choice == '2':
            view_referrals(auth)
        elif choice == '3':
            update_referral_status(auth)
        elif choice == '4':
            specialist_directory(auth)
        elif choice == '5':
            referral_followup(auth)
        elif choice == '6':
            referral_reports(auth)
        elif choice == '7':
            break
        else:
            print("Invalid choice. Please try again.")



def create_referral(auth):
    """Create new referral"""
    backup_before_operation('create_referral')

    conn = get_connection()
    cursor = conn.cursor()

    student_id = input("Enter student ID: ")

    # Verify student exists
    cursor.execute("SELECT first_name, last_name FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    if not student:
        print("Error: Student ID not found.")
        conn.close()
        return

    print(f"Creating referral for: {student[0]} {student[1]}")

    referring_provider = input(f"Referring provider [Dr. {auth.current_user['username']}]: ").strip()
    if not referring_provider:
        referring_provider = f"Dr. {auth.current_user['username']}"

    specialist_provider = input("Specialist provider: ")

    specialties = [
        'Cardiology', 'Dermatology', 'Endocrinology', 'Gastroenterology',
        'Neurology', 'Orthopedics', 'Psychiatry', 'Pulmonology', 'Urology', 'Other'
    ]

    print("\nSpecialties:")
    for i, specialty in enumerate(specialties):
        print(f"{i+1}. {specialty}")

    while True:
        specialty_choice = input("\nSelect specialty (1-10): ")
        if specialty_choice.isdigit() and 1 <= int(specialty_choice) <= len(specialties):
            specialty = specialties[int(specialty_choice) - 1]
            if specialty == 'Other':
                specialty = input("Enter specialty: ")
            break
        print("Invalid choice. Please try again.")

    reason = input("Reason for referral: ")

    urgency_levels = ['Routine', 'Urgent', 'STAT']
    print("\nUrgency Levels:")
    for i, urgency in enumerate(urgency_levels):
        print(f"{i+1}. {urgency}")

    while True:
        urgency_choice = input("\nSelect urgency (1-3): ")
        if urgency_choice.isdigit() and 1 <= int(urgency_choice) <= len(urgency_levels):
            urgency = urgency_levels[int(urgency_choice) - 1]
            break
        print("Invalid choice. Please try again.")

    referral_date = datetime.now().strftime('%Y-%m-%d')
    notes = input("Additional notes: ")
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO referrals
    (student_id, referring_provider, specialist_provider, specialty, reason,
     urgency, referral_date, status, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (student_id, referring_provider, specialist_provider, specialty, reason,
          urgency, referral_date, 'pending', notes, created_at))

    conn.commit()
    referral_id = cursor.lastrowid

    log_audit_event(auth.current_user['id'], 'create_referral', 'referral', referral_id)
    print(f"\nReferral created successfully! Referral ID: {referral_id}")

    if urgency == 'STAT':
        print("🚨 STAT REFERRAL - Immediate action required!")

    conn.close()



def view_referrals(auth):
    """View referrals"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\nFilter options:")
    print("1. All referrals")
    print("2. By student ID")
    print("3. By status")
    print("4. By specialty")
    print("5. Pending referrals only")

    filter_choice = input("\nSelect filter (1-5): ")

    if filter_choice == '1':
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        ORDER BY r.referral_date DESC
        LIMIT 50
        ''')

    elif filter_choice == '2':
        student_id = input("Enter student ID: ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.student_id = ?
        ORDER BY r.referral_date DESC
        ''', (student_id,))

    elif filter_choice == '3':
        status = input("Enter status (pending/scheduled/completed/cancelled): ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.status = ?
        ORDER BY r.referral_date DESC
        ''', (status,))

    elif filter_choice == '4':
        specialty = input("Enter specialty: ")
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.specialty LIKE ?
        ORDER BY r.referral_date DESC
        ''', (f'%{specialty}%',))

    elif filter_choice == '5':
        cursor.execute('''
        SELECT r.id, s.student_id, s.first_name, s.last_name, r.referring_provider,
               r.specialist_provider, r.specialty, r.urgency, r.referral_date, r.status
        FROM referrals r
        JOIN students s ON r.student_id = s.student_id
        WHERE r.status = 'pending'
        ORDER BY r.urgency DESC, r.referral_date
        ''')

    else:
        print("Invalid choice.")
        conn.close()
        return

    referrals = cursor.fetchall()

    if not referrals:
        print("No referrals found.")
        conn.close()
        return

    print("\n===== Referrals =====")
    for referral in referrals:
        ref_id, student_id, first_name, last_name, referring, specialist, specialty, urgency, ref_date, status = referral

        print(f"\nReferral ID: {ref_id}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Referring: {referring}")
        print(f"Specialist: {specialist}")
        print(f"Specialty: {specialty}")
        print(f"Urgency: {urgency}")
        print(f"Date: {ref_date}")
        print(f"Status: {status}")

        if urgency == 'STAT':
            print("🚨 STAT REFERRAL")
        elif urgency == 'Urgent':
            print("⚠️ URGENT")

        print("-" * 30)

    conn.close()



def update_referral_status(auth):
    """Update referral status"""
    backup_before_operation('update_referral_status')

    conn = get_connection()
    cursor = conn.cursor()

    referral_id = input("Enter referral ID to update: ")

    cursor.execute('''
    SELECT r.id, s.first_name, s.last_name, r.specialist_provider,
           r.specialty, r.status
    FROM referrals r
    JOIN students s ON r.student_id = s.student_id
    WHERE r.id = ?
    ''', (referral_id,))

    referral = cursor.fetchone()

    if not referral:
        print("Error: Referral not found.")
        conn.close()
        return

    ref_id, first_name, last_name, specialist, specialty, current_status = referral

    print("\nReferral Details:")
    print(f"Patient: {first_name} {last_name}")
    print(f"Specialist: {specialist}")
    print(f"Specialty: {specialty}")
    print(f"Current Status: {current_status}")

    status_options = ['pending', 'scheduled', 'completed', 'cancelled', 'no_show']
    print("\nStatus Options:")
    for i, status in enumerate(status_options):
        print(f"{i+1}. {status}")

    while True:
        choice = input("\nSelect new status (1-5): ")
        if choice.isdigit() and 1 <= int(choice) <= len(status_options):
            new_status = status_options[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    appointment_date = None
    if new_status == 'scheduled':
        while True:
            appointment_date = input("Appointment date (YYYY-MM-DD): ")
            try:
                datetime.strptime(appointment_date, '%Y-%m-%d')
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")

    notes = input("Additional notes: ")

    cursor.execute('''
    UPDATE referrals
    SET status = ?, appointment_date = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
    WHERE id = ?
    ''', (new_status, appointment_date, notes, notes, referral_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'update_referral_status', 'referral', referral_id,
                   f"Status changed from {current_status} to {new_status}")

    print(f"\nReferral status updated to '{new_status}' successfully!")
    conn.close()



def referral_followup(auth):
    """Follow up on referrals"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get referrals needing follow-up
    cursor.execute('''
    SELECT r.id, s.first_name, s.last_name, r.specialist_provider,
           r.specialty, r.referral_date, r.status
    FROM referrals r
    JOIN students s ON r.student_id = s.student_id
    WHERE r.status IN ('scheduled', 'pending')
    AND r.referral_date < date('now', '-30 days')
    ORDER BY r.referral_date
    ''')

    followup_needed = cursor.fetchall()

    if not followup_needed:
        print("No referrals requiring follow-up.")
        conn.close()
        return

    print("\n===== Referrals Needing Follow-up =====")

    for ref_id, first_name, last_name, specialist, specialty, ref_date, status in followup_needed:
        days_since = (datetime.now() - datetime.strptime(ref_date, '%Y-%m-%d')).days

        print(f"\nReferral ID: {ref_id}")
        print(f"Patient: {first_name} {last_name}")
        print(f"Specialist: {specialist} ({specialty})")
        print(f"Referred: {ref_date} ({days_since} days ago)")
        print(f"Status: {status}")

        if days_since > 60:
            print("🔴 URGENT: Over 60 days old")
        elif days_since > 30:
            print("🟡 Follow-up needed")

    conn.close()



def referral_reports(auth):
    """Generate referral reports"""
    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Referral Reports =====")

    # Referral statistics
    cursor.execute('''
    SELECT specialty, COUNT(*) as referral_count,
           AVG(CASE WHEN status = 'completed' THEN 1.0 ELSE 0.0 END) * 100 as completion_rate
    FROM referrals
    WHERE referral_date >= date('now', '-30 days')
    GROUP BY specialty
    ORDER BY referral_count DESC
    ''')

    stats = cursor.fetchall()

    print("Referral Statistics (Last 30 Days):")
    print(f"{'Specialty':<20} {'Count':<8} {'Completion Rate':<15}")
    print("-" * 45)

    for specialty, count, completion_rate in stats:
        print(f"{specialty:<20} {count:<8} {completion_rate:.1f}%")

    # Monthly trend
    cursor.execute('''
    SELECT strftime('%Y-%m', referral_date) as month, COUNT(*) as count
    FROM referrals
    WHERE referral_date >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', referral_date)
    ORDER BY month
    ''')

    monthly_trends = cursor.fetchall()

    if monthly_trends:
        print("\nMonthly Referral Trends:")
        for month, count in monthly_trends:
            print(f"  {month}: {count} referrals")

    conn.close()



