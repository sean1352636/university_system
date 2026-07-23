from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from datetime import datetime, timedelta
from education_system.post_18.university_system.modules.domain.health.records.db.audit import log_audit_event
from education_system.post_18.university_system.modules.domain.health.services import get_user_student_id
from education_system.post_18.university_system.modules.domain.health.records.wellness.challenges import health_challenges
from education_system.post_18.university_system.modules.domain.health.records.wellness.resources import wellness_resources


def wellness_programs(auth):
    if not auth or not auth.current_user:
        print("You must be logged in to access wellness programs.")
        return

    while True:
        print("\n===== Wellness Programs =====")
        print("1. View Available Programs")
        print("2. Enroll in Program")
        print("3. Track Progress")
        print("4. Health Challenges")
        print("5. Wellness Resources")
        print("6. Program Analytics (Staff Only)")
        print("7. Return to Main Menu")

        choice = input("\nEnter your choice (1-7): ")

        if choice == '1':
            view_wellness_programs(auth)
        elif choice == '2':
            enroll_in_wellness_program(auth)
        elif choice == '3':
            track_wellness_progress(auth)
        elif choice == '4':
            health_challenges(auth)
        elif choice == '5':
            wellness_resources(auth)
        elif choice == '6':
            wellness_program_analytics(auth)
        elif choice == '7':
            break
        else:
            print("Invalid choice. Please try again.")



def view_wellness_programs(auth):
    conn = get_connection()
    cursor = conn.cursor()

    # Get current wellness campaigns
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT id, campaign_name, campaign_type, description, start_date, end_date, status
    FROM health_campaigns
    WHERE campaign_type = 'wellness' AND (end_date IS NULL OR end_date >= ?)
    ORDER BY start_date DESC
    ''', (today,))

    programs = cursor.fetchall()

    if not programs:
        print("No active wellness programs found.")
        conn.close()
        return

    print("\n===== Available Wellness Programs =====")
    for program in programs:
        program_id, name, program_type, description, start_date, end_date, status = program

        print(f"\nProgram ID: {program_id}")
        print(f"Name: {name}")
        print(f"Type: {program_type}")
        print(f"Description: {description}")
        print(f"Start Date: {start_date}")
        print(f"End Date: {end_date if end_date else 'Ongoing'}")
        print(f"Status: {status}")

        # Check if user is enrolled
        if auth.current_user['role'] == 'student':
            student_id = get_user_student_id(auth)
            if student_id:
                cursor.execute('''
                SELECT status FROM wellness_participation
                WHERE student_id = ? AND program_name = ?
                ''', (student_id, name))

                enrollment = cursor.fetchone()
                if enrollment:
                    print(f"Your Status: {enrollment[0]}")
                else:
                    print("Your Status: Not enrolled")

        print("-" * 30)

    conn.close()



def enroll_in_wellness_program(auth):
    if auth.current_user['role'] != 'student':
        print("Only students can enroll in wellness programs.")
        return

    student_id = get_user_student_id(auth)
    if not student_id:
        print("Error: No student ID associated with your account.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Show available programs
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
    SELECT id, campaign_name, description
    FROM health_campaigns
    WHERE campaign_type = 'wellness' AND (end_date IS NULL OR end_date >= ?) AND status = 'active'
    ORDER BY start_date DESC
    ''', (today,))

    programs = cursor.fetchall()

    if not programs:
        print("No programs available for enrollment.")
        conn.close()
        return

    print("\nAvailable Programs:")
    for i, (program_id, name, description) in enumerate(programs):
        print(f"{i+1}. {name} - {description}")

    while True:
        choice = input("\nSelect program to enroll in (number): ")
        if choice.isdigit() and 1 <= int(choice) <= len(programs):
            selected_program = programs[int(choice) - 1]
            break
        print("Invalid choice. Please try again.")

    program_id, program_name, description = selected_program

    # Check if already enrolled
    cursor.execute('''
    SELECT status FROM wellness_participation
    WHERE student_id = ? AND program_name = ?
    ''', (student_id, program_name))

    existing_enrollment = cursor.fetchone()
    if existing_enrollment:
        print(f"You are already enrolled in this program with status: {existing_enrollment[0]}")
        conn.close()
        return

    # Enroll student
    enrollment_date = datetime.now().strftime('%Y-%m-%d')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
    INSERT INTO wellness_participation
    (student_id, program_name, enrollment_date, status, created_at)
    VALUES (?, ?, ?, ?, ?)
    ''', (student_id, program_name, enrollment_date, 'enrolled', created_at))

    conn.commit()
    log_audit_event(auth.current_user['id'], 'enroll_wellness_program', 'wellness_participation', cursor.lastrowid)

    print(f"\nSuccessfully enrolled in {program_name}!")
    print("You can now track your progress and participate in program activities.")

    conn.close()



def track_wellness_progress(auth):
    if auth.current_user['role'] != 'student':
        print("Only students can track wellness progress.")
        return

    student_id = get_user_student_id(auth)
    if not student_id:
        print("Error: No student ID associated with your account.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get enrolled programs
    cursor.execute('''
    SELECT program_name, enrollment_date, status, progress_score, goals_met
    FROM wellness_participation
    WHERE student_id = ?
    ORDER BY enrollment_date DESC
    ''', (student_id,))

    enrollments = cursor.fetchall()

    if not enrollments:
        print("You are not enrolled in any wellness programs.")
        conn.close()
        return

    print("\n===== Your Wellness Progress =====")

    for enrollment in enrollments:
        program_name, enrollment_date, status, progress_score, goals_met = enrollment

        print(f"\nProgram: {program_name}")
        print(f"Enrolled: {enrollment_date}")
        print(f"Status: {status}")
        print(f"Progress Score: {progress_score}%")
        print(f"Goals Met: {goals_met}")

        # Simple progress tracking
        if status == 'enrolled':
            new_progress = input(f"Update progress for {program_name} (0-100%): ").strip()
            if new_progress.isdigit() and 0 <= int(new_progress) <= 100:
                cursor.execute('''
                UPDATE wellness_participation
                SET progress_score = ?
                WHERE student_id = ? AND program_name = ?
                ''', (int(new_progress), student_id, program_name))

                conn.commit()
                print(f"Progress updated to {new_progress}%")

                # Check for milestones
                if int(new_progress) >= 100:
                    cursor.execute('''
                    UPDATE wellness_participation
                    SET status = 'completed', completion_date = ?
                    WHERE student_id = ? AND program_name = ?
                    ''', (datetime.now().strftime('%Y-%m-%d'), student_id, program_name))

                    conn.commit()
                    print("🎉 Congratulations! You have completed this program!")

        print("-" * 30)

    conn.close()



def wellness_program_analytics(auth):
    """Analytics for wellness programs (staff only)"""
    if not auth.check_permission('view_any_health_record'):
        print("You don't have permission to view program analytics.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\n===== Wellness Program Analytics =====")

    # Program enrollment statistics
    cursor.execute('''
    SELECT program_name, COUNT(*) as enrollment_count,
           AVG(progress_score) as avg_progress,
           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completion_count
    FROM wellness_participation
    GROUP BY program_name
    ORDER BY enrollment_count DESC
    ''')

    program_stats = cursor.fetchall()

    if program_stats:
        print("Program Enrollment Statistics:")
        for program, enrollment, avg_progress, completions in program_stats:
            completion_rate = (completions / enrollment * 100) if enrollment > 0 else 0
            print(f"\n{program}:")
            print(f"  Enrollment: {enrollment}")
            print(f"  Average Progress: {avg_progress:.1f}%")
            print(f"  Completions: {completions} ({completion_rate:.1f}%)")

    # Monthly enrollment trends
    cursor.execute('''
    SELECT strftime('%Y-%m', enrollment_date) as month,
           COUNT(*) as enrollments
    FROM wellness_participation
    WHERE enrollment_date >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', enrollment_date)
    ORDER BY month
    ''')

    monthly_trends = cursor.fetchall()

    if monthly_trends:
        print("\nMonthly Enrollment Trends (Last 12 Months):")
        for month, enrollments in monthly_trends:
            print(f"  {month}: {enrollments} enrollments")

    conn.close()



