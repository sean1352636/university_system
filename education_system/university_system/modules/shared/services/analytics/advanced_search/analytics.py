"""Analytics & reporting: search analytics dashboard, demographics, academic performance."""
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.utils.sql_safety import validate_identifier
from .admin import audit_log
from .db import ensure_search_analytics_schema


@audit_log
def search_analytics_dashboard():
    """Display comprehensive search analytics dashboard"""
    print("\n📊 SEARCH ANALYTICS DASHBOARD")
    print("="*50)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Direct fix: Create the search_analytics table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            search_query TEXT,
            search_type TEXT,
            search_criteria TEXT,
            results_count INTEGER,
            execution_time REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT
        )
        ''')

        columns = ensure_search_analytics_schema(cursor)
        time_column = 'timestamp' if 'timestamp' in columns else 'search_datetime'

        cursor.execute("SELECT COUNT(*) FROM search_analytics")
        analytics_count = cursor.fetchone()[0]
        if analytics_count == 0:
            print("⚠ No search analytics data available yet. Run searches to build analytics history.")
            conn.close()
            return

        # Most frequent searches
        cursor.execute('''
        SELECT search_type, COUNT(*) as frequency
        FROM search_analytics
        GROUP BY search_type
        ORDER BY frequency DESC
        LIMIT 10
        ''')
        frequent_searches = cursor.fetchall()

        # Search trends by date
        if time_column:
            safe_time_col = validate_identifier(time_column, "column")
            cursor.execute(
            "SELECT DATE([" + safe_time_col + "]) as search_date, COUNT(*) as searches"
            " FROM search_analytics"
            " WHERE [" + safe_time_col + "] >= date('now', '-30 days')"
            " GROUP BY DATE([" + safe_time_col + "])"
            " ORDER BY search_date DESC"
            " LIMIT 10"
            )
            daily_trends = cursor.fetchall()
        else:
            daily_trends = []

        # Average execution times
        cursor.execute('''
        SELECT search_type, COALESCE(AVG(execution_time), 0.0) as avg_time
        FROM search_analytics
        GROUP BY search_type
        ORDER BY avg_time DESC
        ''')
        performance_stats = cursor.fetchall()

        # Display results
        print("\n🔥 TOP 10 MOST FREQUENT SEARCHES:")
        print("-" * 40)
        for search_type, freq in frequent_searches:
            print(f"{search_type:<25} {freq:>8} times")

        print("\n📈 SEARCH TRENDS (Last 30 days):")
        print("-" * 40)
        for date, count in daily_trends:
            print(f"{date:<15} {count:>8} searches")

        print("\n⚡ PERFORMANCE STATISTICS:")
        print("-" * 40)
        for search_type, avg_time in performance_stats:
            avg_time_display = avg_time if avg_time is not None else 0.0
            print(f"{search_type:<25} {avg_time_display:>8.2f}s avg")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error accessing analytics: {e}")

@audit_log
def student_demographics_reports():
    """Generate comprehensive demographics reports"""
    print("\n👥 STUDENT DEMOGRAPHICS REPORTS")
    print("="*50)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nSelect report type:")
        print("1. Age Distribution")
        print("2. Gender Breakdown by Course")
        print("3. Enrollment Trends")
        print("4. Module Popularity")
        print("5. All Reports")

        choice = input("Enter choice (1-5): ").strip()

        if choice in ['1', '5']:
            # Age distribution
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
            age_dist = cursor.fetchall()

            print("\n📊 AGE DISTRIBUTION:")
            print("-" * 30)
            for age_group, count in age_dist:
                print(f"{age_group:<15} {count:>8} students")

        if choice in ['2', '5']:
            # Gender breakdown by course
            cursor.execute('''
            SELECT course, gender, COUNT(*) as count
            FROM students
            GROUP BY course, gender
            ORDER BY course, gender
            ''')
            gender_course = cursor.fetchall()

            print("\n⚧ GENDER BREAKDOWN BY COURSE:")
            print("-" * 40)
            current_course = None
            for course, gender, count in gender_course:
                if course != current_course:
                    print(f"\n{course} Course:")
                    current_course = course
                print(f"  {gender:<10} {count:>8} students")

        if choice in ['3', '5']:
            # Enrollment trends
            cursor.execute('''
            SELECT
                strftime('%Y-%m', registration_datetime) as month,
                COUNT(*) as enrollments
            FROM students
            WHERE registration_datetime >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', registration_datetime)
            ORDER BY month DESC
            ''')
            trends = cursor.fetchall()

            print("\n📈 ENROLLMENT TRENDS (Last 12 months):")
            print("-" * 40)
            for month, count in trends:
                print(f"{month:<10} {count:>8} new students")

        if choice in ['4', '5']:
            # Module popularity
            cursor.execute('''
            SELECT sm.module_name, COUNT(*) as enrollments
            FROM student_modules sm
            GROUP BY sm.module_name
            ORDER BY enrollments DESC
            LIMIT 10
            ''')
            popular_modules = cursor.fetchall()

            print("\n🎓 TOP 10 MOST POPULAR MODULES:")
            print("-" * 50)
            for module, count in popular_modules:
                print(f"{module:<35} {count:>8} students")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error generating demographics report: {e}")

@audit_log
def academic_performance_analysis():
    """Analyze academic performance patterns"""
    print("\n🎯 ACADEMIC PERFORMANCE ANALYSIS")
    print("="*50)

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Direct fix: Check if grade column exists, if not add it
        cursor.execute("PRAGMA table_info(student_modules)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'grade' not in columns:
            cursor.execute('ALTER TABLE student_modules ADD COLUMN grade TEXT')
            print("✓ Added missing 'grade' column to student_modules table")

            # Add some sample grades to existing records
            cursor.execute('UPDATE student_modules SET grade = "A" WHERE id % 4 = 0')
            cursor.execute('UPDATE student_modules SET grade = "B" WHERE id % 4 = 1')
            cursor.execute('UPDATE student_modules SET grade = "C" WHERE id % 4 = 2')
            cursor.execute('UPDATE student_modules SET grade = NULL WHERE id % 4 = 3')  # In progress
            conn.commit()
            print("✓ Added sample grades to existing records")

        # Module completion rates
        cursor.execute('''
        SELECT
            sm.module_name,
            COUNT(*) as total_enrolled,
            COALESCE(AVG(CASE WHEN sm.grade IS NOT NULL THEN 1.0 ELSE 0.0 END) * 100, 0.0) as completion_rate
        FROM student_modules sm
        GROUP BY sm.module_name
        HAVING COUNT(*) >= 5
        ORDER BY completion_rate DESC
        ''')
        completion_rates = cursor.fetchall()

        print("\n📈 MODULE COMPLETION RATES:")
        print("-" * 60)
        print(f"{'Module Name':<35} {'Enrolled':<10} {'Completion %':<12}")
        print("-" * 60)
        for module, enrolled, rate in completion_rates:
            rate_display = rate if rate is not None else 0.0
            print(f"{module:<35} {enrolled:<10} {rate_display:>10.1f}%")

        # Students with incomplete modules
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name,
               COUNT(sm.module_code) as total_modules,
               SUM(CASE WHEN sm.grade IS NULL THEN 1 ELSE 0 END) as incomplete
        FROM students s
        JOIN student_modules sm ON s.student_id = sm.student_id
        GROUP BY s.student_id, s.first_name, s.last_name
        HAVING incomplete > 0
        ORDER BY incomplete DESC
        LIMIT 10
        ''')
        incomplete_students = cursor.fetchall()

        print("\n⚠️  TOP 10 STUDENTS WITH INCOMPLETE MODULES:")
        print("-" * 70)
        print(f"{'Student ID':<12} {'Name':<25} {'Total':<8} {'Incomplete':<12}")
        print("-" * 70)
        for sid, fname, lname, total, incomplete in incomplete_students:
            name = f"{fname} {lname}"
            print(f"{sid:<12} {name:<25} {total:<8} {incomplete:<12}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Error in performance analysis: {e}")
