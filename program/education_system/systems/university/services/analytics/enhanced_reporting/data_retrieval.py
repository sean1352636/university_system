"""Enhanced data retrieval for all report sections."""

from education_system.systems.university.services.analytics.enhanced_reporting._compat import pd
from education_system.systems.university.services.analytics.enhanced_reporting.config import get_reporting_db_connection


def get_section_dataframe(section, start_date, end_date, filters=None):
    """Enhanced data retrieval for all sections including new analytics"""
    conn = get_reporting_db_connection()

    try:
        if section == "correlation_analysis":
            return get_correlation_data(conn, start_date, end_date, filters)
        elif section == "trend_analysis":
            return get_trend_data(conn, start_date, end_date, filters)
        elif section == "performance_benchmarks":
            return get_benchmark_data(conn, start_date, end_date, filters)
        else:
            # Use existing data retrieval logic
            return get_original_section_data_complete(conn, section, start_date, end_date, filters)

    finally:
        conn.close()


def get_correlation_data(conn, start_date, end_date, filters):
    """Get data for correlation analysis"""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_records'")

    if cursor.fetchone():
        attendance_table = 'attendance_records'
    else:
        return pd.DataFrame()

    # Fixed query with proper table aliases
    query = f"""
    SELECT s.student_id, s.age, s.course,
           COUNT(DISTINCT sm.module_code) as module_count,
           AVG(CASE WHEN sg.grade IS NOT NULL THEN CAST(sg.grade AS FLOAT) ELSE NULL END) as avg_grade,
           COUNT(ar.student_id) as attendance_records,
           SUM(CASE WHEN LOWER(ar.status) IN ('present', 'attended') THEN 1 ELSE 0 END) as present_count
    FROM students s
    LEFT JOIN student_modules sm ON s.student_id = sm.student_id
    LEFT JOIN student_grades sg ON s.student_id = sg.student_id
    LEFT JOIN {attendance_table} ar ON s.student_id = ar.student_id
    WHERE s.registration_datetime BETWEEN ? AND ?
    GROUP BY s.student_id, s.age, s.course
    """

    params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    df = pd.read_sql_query(query, conn, params=params)

    # Calculate derived metrics
    df['attendance_rate'] = df.apply(
        lambda row: row['present_count'] / row['attendance_records'] if row['attendance_records'] > 0 else 0,
        axis=1
    )

    return df


def get_trend_data(conn, start_date, end_date, filters):
    """Get data for trend analysis"""
    query = """
    SELECT
        date(registration_datetime) as date,
        course,
        COUNT(*) as daily_registrations,
        AVG(age) as avg_age
    FROM students
    WHERE registration_datetime BETWEEN ? AND ?
    GROUP BY date(registration_datetime), course
    ORDER BY date
    """

    params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    return pd.read_sql_query(query, conn, params=params)


def get_benchmark_data(conn, start_date, end_date, filters):
    """Get data for performance benchmarks"""
    query = """
    SELECT
        course,
        COUNT(*) as student_count,
        AVG(age) as avg_age,
        MIN(age) as min_age,
        MAX(age) as max_age
    FROM students
    WHERE registration_datetime BETWEEN ? AND ?
    GROUP BY course
    """

    params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
    return pd.read_sql_query(query, conn, params=params)


def get_original_section_data_complete(conn, section, start_date, end_date, filters):
    """Complete implementation of original section data retrieval"""

    if section == "student_overview":
        query = """
        SELECT COUNT(*) as total_students,
               COUNT(DISTINCT course) as total_courses,
               AVG(age) as avg_age
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        """
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        return pd.read_sql_query(query, conn, params=params)

    elif section == "student_list":
        query = """
        SELECT student_id, first_name, last_name, email_address, course,
               age, gender, registration_datetime
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        ORDER BY registration_datetime DESC
        """
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        return pd.read_sql_query(query, conn, params=params)

    elif section == "course_distribution":
        query = """
        SELECT course, COUNT(*) as student_count
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        GROUP BY course
        ORDER BY student_count DESC
        """
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        return pd.read_sql_query(query, conn, params=params)

    elif section == "gender_distribution":
        query = """
        SELECT gender, COUNT(*) as student_count
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        AND gender IS NOT NULL
        GROUP BY gender
        ORDER BY student_count DESC
        """
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        return pd.read_sql_query(query, conn, params=params)

    elif section == "age_distribution":
        query = """
        SELECT
            CASE
                WHEN age < 20 THEN 'Under 20'
                WHEN age BETWEEN 20 AND 25 THEN '20-25'
                WHEN age BETWEEN 26 AND 30 THEN '26-30'
                WHEN age BETWEEN 31 AND 35 THEN '31-35'
                ELSE 'Over 35'
            END as age_group,
            COUNT(*) as student_count
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        AND age IS NOT NULL
        GROUP BY age_group
        ORDER BY student_count DESC
        """
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        return pd.read_sql_query(query, conn, params=params)

    elif section == "registration_trends":
        query = """
        SELECT
            DATE(registration_datetime) as registration_date,
            COUNT(*) as registration_count
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        GROUP BY DATE(registration_datetime)
        ORDER BY registration_date
        """
        params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
        return pd.read_sql_query(query, conn, params=params)

    elif section == "module_popularity":
        # Check if student_modules table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_modules'")
        if cursor.fetchone():
            query = """
            SELECT sm.module_code,
                   COALESCE(m.module_name, sm.module_code) as module_name,
                   COUNT(DISTINCT sm.student_id) as student_count
            FROM student_modules sm
            JOIN students s ON sm.student_id = s.student_id
            LEFT JOIN modules m ON sm.module_code = m.module_code
            WHERE s.registration_datetime BETWEEN ? AND ?
            GROUP BY sm.module_code, m.module_name
            ORDER BY student_count DESC
            """
            params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            return pd.read_sql_query(query, conn, params=params)
        else:
            # Return empty DataFrame if table doesn't exist
            return pd.DataFrame(columns=['module_code', 'module_name', 'student_count'])

    elif section == "grade_distribution":
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_grades'")
        if cursor.fetchone():
            query = """
            SELECT sg.grade, COUNT(*) as student_count
            FROM student_grades sg
            JOIN students s ON sg.student_id = s.student_id
            WHERE s.registration_datetime BETWEEN ? AND ?
            AND sg.grade IS NOT NULL AND sg.grade != ''
            GROUP BY sg.grade
            ORDER BY sg.grade
            """
            params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            return pd.read_sql_query(query, conn, params=params)
        else:
            return pd.DataFrame(columns=['grade', 'student_count'])

    elif section == "attendance_summary":
        # Check for attendance tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_records'")
        if cursor.fetchone():
            query = """
            SELECT
                CASE
                    WHEN LOWER(ar.status) IN ('present', 'attended') THEN 'Present'
                    WHEN LOWER(ar.status) IN ('absent', 'not attended') THEN 'Absent'
                    WHEN LOWER(ar.status) IN ('late', 'tardy') THEN 'Late'
                    WHEN LOWER(ar.status) IN ('excused', 'excused absence') THEN 'Excused'
                    ELSE ar.status
                END as status,
                COUNT(*) as count
            FROM attendance_records ar
            JOIN students s ON ar.student_id = s.student_id
            WHERE s.registration_datetime BETWEEN ? AND ?
            AND ar.status IS NOT NULL
            GROUP BY
                CASE
                    WHEN LOWER(ar.status) IN ('present', 'attended') THEN 'Present'
                    WHEN LOWER(ar.status) IN ('absent', 'not attended') THEN 'Absent'
                    WHEN LOWER(ar.status) IN ('late', 'tardy') THEN 'Late'
                    WHEN LOWER(ar.status) IN ('excused', 'excused absence') THEN 'Excused'
                    ELSE ar.status
                END
            ORDER BY count DESC
            """
            params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
            return pd.read_sql_query(query, conn, params=params)
        else:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_attendance'")
            if cursor.fetchone():
                query = """
                SELECT sa.status, COUNT(*) as count
                FROM student_attendance sa
                JOIN students s ON sa.student_id = s.student_id
                WHERE s.registration_datetime BETWEEN ? AND ?
                AND sa.status IS NOT NULL
                GROUP BY sa.status
                ORDER BY count DESC
                """
                params = [f"{start_date} 00:00:00", f"{end_date} 23:59:59"]
                return pd.read_sql_query(query, conn, params=params)
            else:
                return pd.DataFrame(columns=['status', 'count'])

    # For any unrecognized sections, return empty DataFrame
    return pd.DataFrame()
