"""Data utility functions for the enhanced reporting GUI."""

from education_system.systems.university.interfaces.gui.shell.enhanced_reporting.standalone.constants import (
    logging, os, json, pd, datetime, timedelta,
    paths, get_db_connection,
    ENHANCED_AVAILABLE, load_templates,
)


def serialize_dataframe(df):
    """Serialize dataframe for API responses"""
    try:
        return {
            'columns': df.columns.tolist(),
            'data': df.values.tolist(),
            'index': df.index.tolist() if hasattr(df.index, 'tolist') else list(df.index),
            'shape': df.shape,
            'dtypes': {col: str(df[col].dtype) for col in df.columns}
        }
    except Exception as e:
        return {'error': f'Serialization failed: {str(e)}'}

def get_template(name):
    """Get template by name"""
    try:
        templates = load_templates() if ENHANCED_AVAILABLE else []
        for template in templates:
            if template['name'] == name:
                return template
        return None
    except Exception as e:
        logging.error(f"Error getting template {name}: {str(e)}")
        return None

def get_section_dataframe(section, start_date, end_date, filters=None):
    """Get dataframe for specific section with filters"""
    try:
        conn = get_db_connection()
        if not conn:
            return pd.DataFrame()

        base_query = ""
        params = [start_date, end_date]

        if section == 'student_overview':
            base_query = """
            SELECT 'Total Students' as metric, COUNT(*) as value FROM students
            WHERE registration_datetime BETWEEN ? AND ?
            UNION ALL
            SELECT 'Unique Courses' as metric, COUNT(DISTINCT course) as value FROM students
            WHERE course IS NOT NULL AND registration_datetime BETWEEN ? AND ?
            """
            params = [start_date + ' 00:00:00', end_date + ' 23:59:59', start_date + ' 00:00:00', end_date + ' 23:59:59']

        elif section == 'student_list':
            base_query = """
            SELECT student_id, first_name, last_name, email_address, course,
                   age, gender, registration_datetime
            FROM students
            WHERE registration_datetime BETWEEN ? AND ?
            ORDER BY registration_datetime DESC
            """
            params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        elif section == 'course_distribution':
            base_query = "SELECT course, COUNT(*) as count FROM students WHERE registration_datetime BETWEEN ? AND ?"
            params = [start_date + ' 00:00:00', end_date + ' 23:59:59']
            if filters and filters.get('course'):
                base_query += " AND course = ?"
                params.append(filters['course'])
            base_query += " GROUP BY course ORDER BY count DESC"

        elif section == 'gender_distribution':
            base_query = "SELECT gender, COUNT(*) as count FROM students WHERE registration_datetime BETWEEN ? AND ? AND gender IS NOT NULL GROUP BY gender"
            params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        elif section == 'age_distribution':
            base_query = """
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
            WHERE age IS NOT NULL AND registration_datetime BETWEEN ? AND ?
            GROUP BY age_group
            """
            params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        elif section == 'registration_trends':
            base_query = """
            SELECT DATE(registration_datetime) as registration_date, COUNT(*) as count
            FROM students
            WHERE registration_datetime BETWEEN ? AND ?
            GROUP BY DATE(registration_datetime)
            ORDER BY registration_date
            """
            params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        else:
            # Generic query for unknown sections - get all students
            base_query = "SELECT * FROM students WHERE registration_datetime BETWEEN ? AND ?"
            params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        if filters and filters.get('course') and 'course' not in base_query.lower():
            if 'WHERE' in base_query.upper():
                base_query += " AND course = ?"
            else:
                base_query += " WHERE course = ?"
            params.append(filters['course'])

        df = pd.read_sql_query(base_query, conn, params=params)
        conn.close()
        return df

    except Exception as e:
        logging.error(f"Error getting section dataframe: {str(e)}")
        if 'conn' in locals() and conn:
            conn.close()
        return pd.DataFrame()

def get_correlation_data(conn, start_date, end_date, filters):
    """Get correlation data for analysis"""
    try:
        query = """
        SELECT age,
               LENGTH(first_name || ' ' || last_name) as name_length,
               CASE WHEN course = 'CS' THEN 1 ELSE 0 END as is_cs,
               CASE WHEN gender = 'Male' THEN 1 ELSE 0 END as is_male
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        AND age IS NOT NULL
        AND first_name IS NOT NULL
        AND course IS NOT NULL
        AND gender IS NOT NULL
        """
        params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        if filters and filters.get('course'):
            query += " AND course = ?"
            params.append(filters['course'])

        df = pd.read_sql_query(query, conn, params=params)
        return df

    except Exception as e:
        logging.error(f"Error getting correlation data: {str(e)}")
        return pd.DataFrame()

def get_trend_data(conn, start_date, end_date, filters):
    """Get trend data for analysis"""
    try:
        query = """
        SELECT DATE(registration_datetime) as date,
               COUNT(*) as registrations,
               COUNT(DISTINCT course) as unique_courses,
               AVG(age) as avg_age
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        GROUP BY DATE(registration_datetime)
        ORDER BY date
        """
        params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        df = pd.read_sql_query(query, conn, params=params)
        return df

    except Exception as e:
        logging.error(f"Error getting trend data: {str(e)}")
        return pd.DataFrame()

def get_benchmark_data(conn, start_date, end_date, filters):
    """Get benchmark data for comparisons"""
    try:
        # Get current period data
        current_query = """
        SELECT 'Current Period' as period,
               COUNT(*) as total_students,
               COUNT(DISTINCT course) as unique_courses,
               AVG(age) as avg_age
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        """
        params = [start_date + ' 00:00:00', end_date + ' 23:59:59']

        # Calculate previous period dates
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        period_length = (end_dt - start_dt).days

        prev_end_dt = start_dt - timedelta(days=1)
        prev_start_dt = prev_end_dt - timedelta(days=period_length)

        previous_query = """
        SELECT 'Previous Period' as period,
               COUNT(*) as total_students,
               COUNT(DISTINCT course) as unique_courses,
               AVG(age) as avg_age
        FROM students
        WHERE registration_datetime BETWEEN ? AND ?
        """

        # Combine queries
        combined_query = f"""
        {current_query}
        UNION ALL
        {previous_query}
        """

        all_params = params + [prev_start_dt.strftime('%Y-%m-%d') + ' 00:00:00', prev_end_dt.strftime('%Y-%m-%d') + ' 23:59:59']
        df = pd.read_sql_query(combined_query, conn, params=all_params)
        return df

    except Exception as e:
        logging.error(f"Error getting benchmark data: {str(e)}")
        return pd.DataFrame()

def get_original_section_data_complete(conn, section, start_date, end_date, filters):
    """Get complete original section data"""
    try:
        return get_section_dataframe(section, start_date, end_date, filters)
    except Exception as e:
        logging.error(f"Error getting original section data: {str(e)}")
        return pd.DataFrame()
