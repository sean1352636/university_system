"""Visualization: interactive charts and graphs (text-based)."""
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection


def interactive_charts():
    """Generate interactive charts and visualizations"""
    print("\n📊 INTERACTIVE CHARTS & GRAPHS")
    print("="*50)

    print("Available visualizations:")
    print("1. Age Distribution Histogram")
    print("2. Course Enrollment Pie Chart")
    print("3. Registration Timeline")
    print("4. Gender Distribution by Course")
    print("5. Module Popularity Chart")

    choice = input("Select visualization (1-5): ").strip()

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if choice == '1':
            generate_age_histogram(cursor)
        elif choice == '2':
            generate_course_pie_chart(cursor)
        elif choice == '3':
            generate_registration_timeline(cursor)
        elif choice == '4':
            generate_gender_course_chart(cursor)
        elif choice == '5':
            generate_module_popularity_chart(cursor)

        conn.close()

    except sqlite3.Error as e:
        print(f"Error generating visualization: {e}")

def generate_age_histogram(cursor):
    """Generate age distribution histogram (text-based)"""
    cursor.execute('''
    SELECT
        CASE
            WHEN age < 20 THEN 'Under 20'
            WHEN age BETWEEN 20 AND 25 THEN '20-25'
            WHEN age BETWEEN 26 AND 30 THEN '26-30'
            WHEN age BETWEEN 31 AND 35 THEN '31-35'
            ELSE 'Over 35'
        END as age_group,
        COUNT(*) as count
    FROM students
    GROUP BY age_group
    ORDER BY
        CASE age_group
            WHEN 'Under 20' THEN 1
            WHEN '20-25' THEN 2
            WHEN '26-30' THEN 3
            WHEN '31-35' THEN 4
            ELSE 5
        END
    ''')

    data = cursor.fetchall()

    print("\n📊 AGE DISTRIBUTION HISTOGRAM:")
    print("-" * 50)

    max_count = max(count for _, count in data) if data else 1

    for age_group, count in data:
        bar_length = int((count / max_count) * 40)
        bar = '█' * bar_length
        print(f"{age_group:<15} |{bar:<40} {count}")

def generate_course_pie_chart(cursor):
    """Generate course enrollment pie chart (text-based)"""
    cursor.execute('''
    SELECT course, COUNT(*) as count
    FROM students
    GROUP BY course
    ORDER BY count DESC
    ''')

    data = cursor.fetchall()
    if not data:
        print("No course data available.")
        return

    total = sum(count for _, count in data)

    print("\n🥧 COURSE ENROLLMENT PIE CHART:")
    print("-" * 50)

    for course, count in data:
        percentage = (count / total) * 100 if total > 0 else 0
        pie_chars = int(percentage / 2.5)  # Each char represents 2.5%
        pie_slice = '●' * pie_chars
        print(f"{course:<10} |{pie_slice:<40} {count:>6} ({percentage:>5.1f}%)")

def generate_registration_timeline(cursor):
    """Generate registration timeline"""
    cursor.execute('''
    SELECT
        strftime('%Y-%m', registration_datetime) as month,
        COUNT(*) as registrations
    FROM students
    WHERE registration_datetime >= date('now', '-12 months')
    GROUP BY strftime('%Y-%m', registration_datetime)
    ORDER BY month
    ''')

    data = cursor.fetchall()

    print("\n📈 REGISTRATION TIMELINE (Last 12 months):")
    print("-" * 50)

    if not data:
        print("No registration data available.")
        return

    max_registrations = max(count for _, count in data)

    for month, count in data:
        bar_length = int((count / max_registrations) * 30) if max_registrations > 0 else 0
        bar = '▓' * bar_length
        print(f"{month} |{bar:<30} {count}")

def generate_gender_course_chart(cursor):
    """Generate gender distribution by course chart"""
    cursor.execute('''
    SELECT course, gender, COUNT(*) as count
    FROM students
    GROUP BY course, gender
    ORDER BY course, gender
    ''')

    data = cursor.fetchall()

    print("\n⚧ GENDER DISTRIBUTION BY COURSE:")
    print("-" * 60)

    current_course = None
    for course, gender, count in data:
        if course != current_course:
            if current_course is not None:
                print()  # Add spacing between courses
            print(f"\n{course} Course:")
            current_course = course

        bar_length = min(count, 30)  # Cap at 30 chars
        bar = '█' * bar_length
        print(f"  {gender:<10} |{bar:<30} {count}")

def generate_module_popularity_chart(cursor):
    """Generate module popularity chart"""
    cursor.execute('''
    SELECT sm.module_name, COUNT(*) as enrollments
    FROM student_modules sm
    GROUP BY sm.module_name
    ORDER BY enrollments DESC
    LIMIT 15
    ''')

    data = cursor.fetchall()

    print("\n🎓 TOP 15 MOST POPULAR MODULES:")
    print("-" * 70)

    if not data:
        print("No module enrollment data available.")
        return

    max_enrollments = max(count for _, count in data)

    for i, (module_name, count) in enumerate(data, 1):
        bar_length = int((count / max_enrollments) * 40) if max_enrollments > 0 else 0
        bar = '▓' * bar_length

        # Truncate long module names
        display_name = module_name[:35] + "..." if len(module_name) > 38 else module_name

        print(f"{i:2d}. {display_name:<38} |{bar:<40} {count}")
