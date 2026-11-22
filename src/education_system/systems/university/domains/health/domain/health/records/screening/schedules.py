from education_system.systems.university.domains.health.infrastructure.health.storage import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.systems.university.domains.health.domain.health.records.db.audit import log_audit_event
from education_system.systems.university.domains.health.domain.health.prompting import ask as _ask


def calculate_screening_due_date(screening_type, age):
    """Calculate recommended due date for screening based on type and age"""
    base_date = datetime.now()

    # Age-based recommendations
    if screening_type == 'Annual Physical Exam':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')
    elif screening_type == 'Blood Pressure Screening':
        if age >= 40:
            return (base_date + timedelta(days=180)).strftime('%Y-%m-%d')  # Every 6 months
        else:
            return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Annually
    elif screening_type == 'Cholesterol Screening':
        if age >= 35:
            return (base_date + timedelta(days=365*3)).strftime('%Y-%m-%d')  # Every 3 years
        else:
            return (base_date + timedelta(days=365*5)).strftime('%Y-%m-%d')  # Every 5 years
    elif screening_type == 'Diabetes Screening':
        if age >= 35:
            return (base_date + timedelta(days=365*3)).strftime('%Y-%m-%d')  # Every 3 years
        else:
            return (base_date + timedelta(days=365*5)).strftime('%Y-%m-%d')  # Every 5 years
    elif screening_type == 'Mental Health Screening':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Annually
    elif screening_type == 'STI Screening':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Annually if sexually active
    else:
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')  # Default annual



def calculate_next_screening_date(screening_type):
    """Calculate next screening due date"""
    base_date = datetime.now()

    if screening_type == 'Annual Physical Exam':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')
    elif screening_type == 'Blood Pressure Screening':
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')
    elif screening_type == 'Cholesterol Screening':
        return (base_date + timedelta(days=365*3)).strftime('%Y-%m-%d')
    else:
        return (base_date + timedelta(days=365)).strftime('%Y-%m-%d')



def view_due_screenings(auth):
    """View due screenings"""
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    thirty_days = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT ss.id, s.student_id, s.first_name, s.last_name, ss.screening_type,
           ss.due_date, ss.status, ss.provider
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date <= ? AND ss.status = 'due'
    ORDER BY ss.due_date
    ''', (thirty_days,))

    due_screenings = cursor.fetchall()

    if not due_screenings:
        print("No screenings due in the next 30 days.")
        conn.close()
        return

    print("\n===== Due Screenings (Next 30 Days) =====")

    for screen_id, student_id, first_name, last_name, screening_type, due_date, status, provider in due_screenings:
        due_datetime = datetime.strptime(due_date, '%Y-%m-%d')
        days_until_due = (due_datetime - datetime.now()).days

        if days_until_due < 0:
            urgency = "🔴 OVERDUE"
        elif days_until_due <= 7:
            urgency = "🟡 DUE SOON"
        else:
            urgency = "ℹ️ UPCOMING"

        print(f"\n{urgency} ID: {screen_id}")
        print(f"Patient: {first_name} {last_name} (ID: {student_id})")
        print(f"Screening: {screening_type}")
        print(f"Due Date: {due_date}")
        if days_until_due < 0:
            print(f"Overdue by: {abs(days_until_due)} days")
        else:
            print(f"Due in: {days_until_due} days")
        print(f"Provider: {provider}")

    conn.close()



def overdue_screenings(auth, values=None):
    """View overdue screenings"""
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')

    cursor.execute('''
    SELECT ss.id, s.student_id, s.first_name, s.last_name, ss.screening_type,
           ss.due_date, ss.provider, s.email_address
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.due_date < ? AND ss.status = 'due'
    ORDER BY ss.due_date
    ''', (today,))

    overdue = cursor.fetchall()

    if not overdue:
        print("No overdue screenings found.")
        conn.close()
        return

    print("\n===== Overdue Screenings =====")

    students = []
    without_email = 0
    for (screen_id, student_id, first_name, last_name, screening_type,
         due_date, provider, email) in overdue:
        due_datetime = datetime.strptime(due_date, '%Y-%m-%d')
        days_overdue = (datetime.now() - due_datetime).days
        name = f"{first_name or ''} {last_name or ''}".strip() or student_id

        print(f"\n🔴 OVERDUE - ID: {screen_id}")
        print(f"Patient: {name} (ID: {student_id})")
        print(f"Screening: {screening_type}")
        print(f"Due Date: {due_date}")
        print(f"Overdue by: {days_overdue} days")
        print(f"Provider: {provider}")

        if days_overdue > 90:
            print("⚠️ CRITICAL: Over 90 days overdue")
        if not email:
            without_email += 1
            print("(no email address on file — cannot be notified)")

        students.append({
            'screening_id': screen_id, 'student_id': student_id,
            'student_name': name, 'screening_type': screening_type,
            'due_date': due_date, 'days_overdue': days_overdue,
            'provider': provider, 'email': email,
        })

    print(f"\nTotal overdue screenings: {len(overdue)}")
    if without_email:
        print(f"{without_email} of them have no email address on file.")

    # This used to print "Reminder notifications sent to patients and
    # providers." without sending anything at all.
    send_reminders = _ask(values, "send_reminders", 
        f"\nEmail the {len(students) - without_email} student(s) who can be "
        "reached? (y/n): ").strip().lower()

    # Close before sending: the email service opens its own connection to the
    # same database, and one writer at a time avoids the lock.
    conn.close()

    if send_reminders != 'y':
        print("Notification cancelled. Nothing has been sent.")
        return

    from education_system.systems.university.domains.health.domain.health.records.screening.reminders import (
        notify_screening_overdue,
    )

    sent = failed = 0
    for student in students:
        if notify_screening_overdue(student):
            sent += 1
        else:
            failed += 1

    print(f"\nOverdue notices: {sent} sent, {failed} not sent.")
    log_audit_event(auth.current_user['id'], 'send_overdue_screening_notices',
                    'screening', sent, f"{sent} sent, {failed} failed")



