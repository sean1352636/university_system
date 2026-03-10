"""Custom reports and scheduled reports management."""
import csv
import json
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from . import _globals


def generate_custom_reports():
    """Generate custom reports with user-defined parameters"""
    print("\n📊 CUSTOM REPORT GENERATOR")
    print("="*50)

    print("Report types:")
    print("1. Student summary report")
    print("2. Module enrollment report")
    print("3. Demographics analysis")
    print("4. Performance report")
    print("5. Custom SQL report")

    choice = input("Select report type (1-5): ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if choice == '1':
            generate_student_summary_report(cursor)
        elif choice == '2':
            generate_module_enrollment_report(cursor)
        elif choice == '3':
            generate_demographics_analysis(cursor)
        elif choice == '4':
            generate_performance_report(cursor)
        elif choice == '5':
            generate_custom_sql_report(cursor)
        else:
            print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_student_summary_report(cursor):
    """Generate comprehensive student summary report"""
    print("\n📋 STUDENT SUMMARY REPORT")
    print("="*60)

    # Overall statistics
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT course) FROM students")
    total_courses = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(age) FROM students WHERE age IS NOT NULL")
    avg_age = cursor.fetchone()[0] or 0

    print(f"📊 OVERVIEW:")
    print(f"Total Students: {total_students}")
    print(f"Total Courses: {total_courses}")
    print(f"Average Age: {avg_age:.1f}")

    # Course breakdown
    cursor.execute('''
    SELECT course, COUNT(*) as count
    FROM students
    GROUP BY course
    ORDER BY count DESC
    ''')

    course_data = cursor.fetchall()

    print(f"\n📚 COURSE BREAKDOWN:")
    for course, count in course_data:
        percentage = (count / total_students) * 100 if total_students > 0 else 0
        print(f"  {course}: {count} students ({percentage:.1f}%)")

    # Gender distribution
    cursor.execute('''
    SELECT gender, COUNT(*) as count
    FROM students
    GROUP BY gender
    ORDER BY count DESC
    ''')

    gender_data = cursor.fetchall()

    print(f"\n👥 GENDER DISTRIBUTION:")
    for gender, count in gender_data:
        percentage = (count / total_students) * 100 if total_students > 0 else 0
        print(f"  {gender}: {count} students ({percentage:.1f}%)")

    # Recent registrations
    cursor.execute('''
    SELECT COUNT(*) FROM students
    WHERE registration_datetime >= date('now', '-30 days')
    ''')

    recent_registrations = cursor.fetchone()[0]

    print(f"\n📅 RECENT ACTIVITY:")
    print(f"New registrations (last 30 days): {recent_registrations}")

def generate_module_enrollment_report(cursor):
    """Generate module enrollment report"""
    print("\n🎓 MODULE ENROLLMENT REPORT")
    print("="*60)

    # Module statistics
    cursor.execute('''
    SELECT sm.module_code, sm.module_name, sm.module_type,
           COUNT(*) as total_enrolled,
           SUM(CASE WHEN sm.grade IS NOT NULL THEN 1 ELSE 0 END) as completed,
           AVG(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1.0 ELSE 0.0 END) * 100 as success_rate
    FROM student_modules sm
    GROUP BY sm.module_code, sm.module_name, sm.module_type
    ORDER BY total_enrolled DESC
    ''')

    module_data = cursor.fetchall()

    if not module_data:
        print("No module enrollment data found.")
        return

    print(f"📊 MODULE STATISTICS:")
    print("-" * 100)
    print(f"{'Code':<10} {'Name':<30} {'Type':<12} {'Enrolled':<10} {'Completed':<10} {'Success %':<10}")
    print("-" * 100)

    for code, name, mod_type, enrolled, completed, success_rate in module_data:
        success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"
        name_display = name[:27] + "..." if len(name) > 30 else name

        print(f"{code:<10} {name_display:<30} {mod_type:<12} {enrolled:<10} {completed:<10} {success_display:<10}")

    # Summary statistics
    total_enrollments = sum(row[3] for row in module_data)
    total_completions = sum(row[4] for row in module_data)
    overall_completion_rate = (total_completions / total_enrollments) * 100 if total_enrollments > 0 else 0

    print(f"\n📈 SUMMARY:")
    print(f"Total Enrollments: {total_enrollments}")
    print(f"Total Completions: {total_completions}")
    print(f"Overall Completion Rate: {overall_completion_rate:.1f}%")

def generate_demographics_analysis(cursor):
    """Generate detailed demographics analysis"""
    print("\n👥 DEMOGRAPHICS ANALYSIS REPORT")
    print("="*60)

    # Age distribution analysis
    cursor.execute('''
    SELECT
        CASE
            WHEN age < 20 THEN 'Under 20'
            WHEN age BETWEEN 20 AND 25 THEN '20-25'
            WHEN age BETWEEN 26 AND 30 THEN '26-30'
            WHEN age BETWEEN 31 AND 35 THEN '31-35'
            WHEN age BETWEEN 36 AND 40 THEN '36-40'
            ELSE 'Over 40'
        END as age_group,
        COUNT(*) as count
    FROM students
    WHERE age IS NOT NULL
    GROUP BY age_group
    ORDER BY
        CASE age_group
            WHEN 'Under 20' THEN 1
            WHEN '20-25' THEN 2
            WHEN '26-30' THEN 3
            WHEN '31-35' THEN 4
            WHEN '36-40' THEN 5
            ELSE 6
        END
    ''')

    age_data = cursor.fetchall()
    total_with_age = sum(count for _, count in age_data)

    print(f"📊 AGE DISTRIBUTION:")
    print("-" * 40)
    for age_group, count in age_data:
        percentage = (count / total_with_age) * 100 if total_with_age > 0 else 0
        bar = '█' * min(int(percentage / 2), 40)
        print(f"{age_group:<15} |{bar:<40} {count:>5} ({percentage:>5.1f}%)")

    # Cross-tabulation: Course by Gender
    cursor.execute('''
    SELECT course, gender, COUNT(*) as count
    FROM students
    GROUP BY course, gender
    ORDER BY course, gender
    ''')

    cross_tab = cursor.fetchall()

    print(f"\n📋 COURSE × GENDER CROSS-TABULATION:")
    print("-" * 50)

    # Organize data for display
    courses = {}
    for course, gender, count in cross_tab:
        if course not in courses:
            courses[course] = {}
        courses[course][gender] = count

    # Display cross-tabulation
    genders = ['male', 'female', 'other']
    header = f"{'Course':<10}" + "".join(f"{g.capitalize():<10}" for g in genders) + "Total"
    print(header)
    print("-" * len(header))

    for course, gender_counts in courses.items():
        row = f"{course:<10}"
        total = 0
        for gender in genders:
            count = gender_counts.get(gender, 0)
            row += f"{count:<10}"
            total += count
        row += f"{total}"
        print(row)

def generate_performance_report(cursor):
    """Generate academic performance report"""
    print("\n🎯 ACADEMIC PERFORMANCE REPORT")
    print("="*60)

    # Student performance metrics
    cursor.execute('''
    SELECT s.student_id, s.first_name, s.last_name, s.course,
           COUNT(sm.module_code) as total_modules,
           SUM(CASE WHEN sm.grade IS NOT NULL THEN 1 ELSE 0 END) as completed_modules,
           SUM(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1 ELSE 0 END) as passed_modules,
           AVG(CASE WHEN sm.grade IN ('A', 'B', 'C', 'D') THEN 1.0 ELSE 0.0 END) * 100 as success_rate
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
    GROUP BY s.student_id, s.first_name, s.last_name, s.course
    HAVING total_modules > 0
    ORDER BY success_rate DESC, completed_modules DESC
    ''')

    performance_data = cursor.fetchall()

    if not performance_data:
        print("No performance data available.")
        return

    print(f"🏆 TOP PERFORMING STUDENTS:")
    print("-" * 100)
    print(f"{'Rank':<5} {'Student ID':<12} {'Name':<25} {'Course':<8} {'Modules':<10} {'Success %':<10}")
    print("-" * 100)

    for rank, (student_id, first_name, last_name, course, total, completed, passed, success_rate) in enumerate(performance_data[:20], 1):
        name = f"{first_name} {last_name}"
        modules_text = f"{completed}/{total}"
        success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"

        print(f"{rank:<5} {student_id:<12} {name:<25} {course:<8} {modules_text:<10} {success_display:<10}")

    # Performance statistics by course
    cursor.execute('''
    SELECT s.course,
           AVG(CASE WHEN sm.grade IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100 as avg_completion_rate,
           AVG(CASE WHEN sm.grade IS NOT NULL AND sm.grade != 'F' THEN 1.0 ELSE 0.0 END) * 100 as avg_success_rate
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
    GROUP BY s.course
    ORDER BY avg_success_rate DESC
    ''')

    course_performance = cursor.fetchall()

    print(f"\n📊 PERFORMANCE BY COURSE:")
    print("-" * 60)
    print(f"{'Course':<10} {'Avg Completion %':<18} {'Avg Success %':<15}")
    print("-" * 60)

    for course, completion_rate, success_rate in course_performance:
        completion_display = f"{completion_rate:.1f}%" if completion_rate is not None else "N/A"
        success_display = f"{success_rate:.1f}%" if success_rate is not None else "N/A"

        print(f"{course:<10} {completion_display:<18} {success_display:<15}")

def generate_custom_sql_report(cursor):
    """Generate report from custom SQL query"""
    print("\n💻 CUSTOM SQL REPORT")
    print("="*50)

    print("⚠️  Warning: Only use trusted SQL queries.")
    print("Available tables: students, student_modules, search_analytics")

    query = input("\nEnter SQL query: ").strip()

    if not query:
        print("No query provided.")
        return

    # Basic validation
    forbidden_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE']
    query_upper = query.upper()

    for keyword in forbidden_keywords:
        if keyword in query_upper:
            print(f"❌ Forbidden keyword '{keyword}' detected. Query rejected.")
            return

    try:
        cursor.execute(query)
        results = cursor.fetchall()

        if not results:
            print("Query executed successfully but returned no results.")
            return

        # Get column names
        column_names = [description[0] for description in cursor.description]

        print(f"\n📊 QUERY RESULTS ({len(results)} rows):")
        print("-" * 100)

        # Display header
        header = " | ".join(f"{name:<15}" for name in column_names)
        print(header)
        print("-" * len(header))

        # Display results (limit to first 50 rows for readability)
        for row in results[:50]:
            row_str = " | ".join(f"{str(value):<15}" for value in row)
            print(row_str)

        if len(results) > 50:
            print(f"\n... and {len(results) - 50} more rows")

        # Export option
        export_choice = input(f"\nExport results to CSV? (y/n): ").strip().lower()
        if export_choice == 'y':
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"custom_report_{timestamp}.csv"

            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(column_names)
                writer.writerows(results)

            print(f"✅ Results exported to {filename}")

    except sqlite3.Error as e:
        print(f"SQL Error: {e}")

def manage_scheduled_reports():
    """Manage scheduled reports"""
    print("\n📅 SCHEDULED REPORTS MANAGEMENT")
    print("="*50)

    print("1. View scheduled reports")
    print("2. Create new scheduled report")
    print("3. Modify scheduled report")
    print("4. Delete scheduled report")
    print("5. Run scheduled report now")

    choice = input("Select option (1-5): ").strip()

    if choice == '1':
        view_scheduled_reports()
    elif choice == '2':
        create_scheduled_report()
    elif choice == '3':
        modify_scheduled_report()
    elif choice == '4':
        delete_scheduled_report()
    elif choice == '5':
        run_scheduled_report()

def view_scheduled_reports():
    """View all scheduled reports"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT id, report_name, schedule_pattern, email_recipients,
               last_run, is_active
        FROM scheduled_reports
        WHERE user_id = ?
        ORDER BY report_name
        ''', (_globals.current_user,))

        reports = cursor.fetchall()

        if not reports:
            print("No scheduled reports found.")
            return

        print(f"\n📋 YOUR SCHEDULED REPORTS:")
        print("-" * 100)
        print(f"{'ID':<5} {'Name':<25} {'Schedule':<15} {'Recipients':<25} {'Last Run':<15} {'Active':<8}")
        print("-" * 100)

        for report_id, name, schedule, recipients, last_run, active in reports:
            active_text = "Yes" if active else "No"
            last_run_text = last_run[:10] if last_run else "Never"
            recipients_text = recipients[:22] + "..." if len(recipients) > 25 else recipients

            print(f"{report_id:<5} {name:<25} {schedule:<15} {recipients_text:<25} {last_run_text:<15} {active_text:<8}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error viewing scheduled reports: {e}")

def create_scheduled_report():
    """Create a new scheduled report"""
    print("\n📝 CREATE SCHEDULED REPORT")
    print("-" * 40)

    report_name = input("Report name: ").strip()
    if not report_name:
        print("Report name is required.")
        return

    print("\nSchedule patterns:")
    print("1. Daily")
    print("2. Weekly")
    print("3. Monthly")
    print("4. Custom")

    schedule_choice = input("Select schedule (1-4): ").strip()

    schedule_patterns = {
        '1': 'daily',
        '2': 'weekly',
        '3': 'monthly',
        '4': input("Enter custom schedule pattern: ").strip()
    }

    schedule_pattern = schedule_patterns.get(schedule_choice, 'weekly')

    email_recipients = input("Email recipients (comma-separated): ").strip()

    # For simplicity, use the last search criteria
    if _globals.last_search_results:
        search_criteria = {"type": "last_search", "count": len(_globals.last_search_results)}
    else:
        search_criteria = {"type": "all_students"}

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        INSERT INTO scheduled_reports
        (user_id, report_name, search_criteria, schedule_pattern, email_recipients)
        VALUES (?, ?, ?, ?, ?)
        ''', (_globals.current_user, report_name, json.dumps(search_criteria), schedule_pattern, email_recipients))

        conn.commit()
        conn.close()

        print(f"✅ Scheduled report '{report_name}' created successfully!")
        print(f"Schedule: {schedule_pattern}")
        print(f"Recipients: {email_recipients}")

    except sqlite3.Error as e:
        print(f"Error creating scheduled report: {e}")

def modify_scheduled_report():
    """Modify an existing scheduled report"""
    view_scheduled_reports()

    try:
        report_id = int(input("\nEnter report ID to modify: "))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT report_name, schedule_pattern, email_recipients, is_active
        FROM scheduled_reports
        WHERE id = ? AND user_id = ?
        ''', (report_id, _globals.current_user))

        result = cursor.fetchone()
        if not result:
            print("Report not found or access denied.")
            return

        name, schedule, recipients, active = result

        print(f"\nCurrent settings:")
        print(f"Name: {name}")
        print(f"Schedule: {schedule}")
        print(f"Recipients: {recipients}")
        print(f"Active: {'Yes' if active else 'No'}")

        # Get new values
        new_name = input(f"New name (current: {name}): ").strip()
        new_schedule = input(f"New schedule (current: {schedule}): ").strip()
        new_recipients = input(f"New recipients (current: {recipients}): ").strip()
        new_active = input(f"Active? y/n (current: {'y' if active else 'n'}): ").strip().lower()

        # Update only changed fields
        updates = []
        params = []

        if new_name:
            updates.append("report_name = ?")
            params.append(new_name)

        if new_schedule:
            updates.append("schedule_pattern = ?")
            params.append(new_schedule)

        if new_recipients:
            updates.append("email_recipients = ?")
            params.append(new_recipients)

        if new_active in ['y', 'n']:
            updates.append("is_active = ?")
            params.append(1 if new_active == 'y' else 0)

        if updates:
            query = f"UPDATE scheduled_reports SET {', '.join(updates)} WHERE id = ?"
            params.append(report_id)

            cursor.execute(query, params)
            conn.commit()
            print("✅ Report updated successfully.")
        else:
            print("No changes made.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error modifying report: {e}")

def delete_scheduled_report():
    """Delete a scheduled report"""
    view_scheduled_reports()

    try:
        report_id = int(input("\nEnter report ID to delete: "))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT report_name FROM scheduled_reports
        WHERE id = ? AND user_id = ?
        ''', (report_id, _globals.current_user))

        result = cursor.fetchone()
        if not result:
            print("Report not found or access denied.")
            return

        report_name = result[0]
        confirm = input(f"Delete report '{report_name}'? (y/n): ").strip().lower()

        if confirm == 'y':
            cursor.execute('DELETE FROM scheduled_reports WHERE id = ?', (report_id,))
            conn.commit()
            print(f"✅ Report '{report_name}' deleted successfully.")
        else:
            print("Deletion cancelled.")

        conn.close()

    except (ValueError, sqlite3.Error) as e:
        print(f"Error deleting report: {e}")

def run_scheduled_report():
    """Run a scheduled report immediately"""
    view_scheduled_reports()

    try:
        report_id = int(input("\nEnter report ID to run: "))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT report_name, search_criteria, email_recipients
        FROM scheduled_reports
        WHERE id = ? AND user_id = ?
        ''', (report_id, _globals.current_user))

        result = cursor.fetchone()
        if not result:
            print("Report not found or access denied.")
            return

        report_name, criteria_json, recipients = result

        print(f"\n🏃 Running report '{report_name}'...")

        # Simulate report execution
        criteria = json.loads(criteria_json)

        # For simplicity, just show current student count
        cursor.execute("SELECT COUNT(*) FROM students")
        student_count = cursor.fetchone()[0]

        print(f"✅ Report executed successfully!")
        print(f"Report: {report_name}")
        print(f"Data: {student_count} students")
        print(f"Recipients: {recipients}")
        print(f"Execution time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Update last run time
        cursor.execute('''
        UPDATE scheduled_reports
        SET last_run = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (report_id,))

        conn.commit()
        conn.close()

        print("📧 Report would be emailed to recipients in production.")

    except (ValueError, sqlite3.Error) as e:
        print(f"Error running report: {e}")
