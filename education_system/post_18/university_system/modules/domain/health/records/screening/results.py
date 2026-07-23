from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.data_backup import backup_before_operation
from education_system.post_18.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.post_18.university_system.modules.domain.health.records.screening.schedules import calculate_next_screening_date


def record_screening_results(auth):
    """Record screening results"""
    backup_before_operation('record_screening_results')

    conn = get_connection()
    cursor = conn.cursor()

    screening_id = input("Enter screening ID: ")

    cursor.execute('''
    SELECT ss.id, s.first_name, s.last_name, ss.screening_type, ss.due_date
    FROM screening_schedules ss
    JOIN students s ON ss.student_id = s.student_id
    WHERE ss.id = ?
    ''', (screening_id,))

    screening = cursor.fetchone()

    if not screening:
        print("Error: Screening not found.")
        conn.close()
        return

    screen_id, first_name, last_name, screening_type, due_date = screening

    print("\nRecording results for:")
    print(f"Patient: {first_name} {last_name}")
    print(f"Screening: {screening_type}")

    completed_date = input("Completed date (YYYY-MM-DD) [today]: ").strip()
    if not completed_date:
        completed_date = datetime.now().strftime('%Y-%m-%d')

    results = input("Screening results: ")

    # Calculate next due date
    next_due_date = calculate_next_screening_date(screening_type)

    cursor.execute('''
    UPDATE screening_schedules
    SET completed_date = ?, status = 'completed', results = ?, next_due_date = ?
    WHERE id = ?
    ''', (completed_date, results, next_due_date, screening_id))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'record_screening_results', 'screening', screening_id)

    print("\nScreening results recorded successfully!")
    print(f"Next screening due: {next_due_date}")

    conn.close()



