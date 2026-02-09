"""
Data Warehouse Service

Implements ETL (Extract, Transform, Load) pipelines and star schema
for analytics and business intelligence.

Star Schema Design:
- Fact Tables: enrollments, grades, payments
- Dimension Tables: students, courses, time, departments
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from university_system.infrastructure.database.db import get_connection, transaction

logger = logging.getLogger(__name__)

# Optional dependency
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not available - limited data warehouse features")


class DataWarehouse:
    """
    Data warehouse with ETL pipelines

    Features:
    - Extract from operational database
    - Transform for analytics
    - Load to star schema
    - Incremental updates
    - Data quality checks
    """

    def __init__(self):
        """Initialize data warehouse"""
        self._ensure_star_schema()

    def _ensure_star_schema(self):
        """Create data warehouse star schema tables"""
        try:
            with transaction() as conn:
                # Dimension: Time
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dim_time (
                        time_key INTEGER PRIMARY KEY,
                        date TEXT NOT NULL UNIQUE,
                        year INTEGER,
                        quarter INTEGER,
                        month INTEGER,
                        week INTEGER,
                        day INTEGER,
                        day_of_week INTEGER,
                        month_name TEXT,
                        quarter_name TEXT
                    )
                ''')

                # Dimension: Student
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dim_student (
                        student_key INTEGER PRIMARY KEY,
                        student_id TEXT NOT NULL UNIQUE,
                        student_name TEXT,
                        department TEXT,
                        enrollment_status TEXT,
                        cohort_year INTEGER,
                        current_gpa REAL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Dimension: Course
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dim_course (
                        course_key INTEGER PRIMARY KEY,
                        course_id TEXT NOT NULL UNIQUE,
                        course_code TEXT,
                        course_name TEXT,
                        department TEXT,
                        credits INTEGER,
                        level TEXT,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Dimension: Department
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS dim_department (
                        department_key INTEGER PRIMARY KEY,
                        department_name TEXT NOT NULL UNIQUE,
                        faculty_count INTEGER,
                        budget REAL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Fact: Enrollment
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS fact_enrollment (
                        enrollment_key INTEGER PRIMARY KEY AUTOINCREMENT,
                        time_key INTEGER,
                        student_key INTEGER,
                        course_key INTEGER,
                        department_key INTEGER,
                        enrollment_status TEXT,
                        grade TEXT,
                        credits INTEGER,
                        tuition_amount REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (time_key) REFERENCES dim_time(time_key),
                        FOREIGN KEY (student_key) REFERENCES dim_student(student_key),
                        FOREIGN KEY (course_key) REFERENCES dim_course(course_key),
                        FOREIGN KEY (department_key) REFERENCES dim_department(department_key)
                    )
                ''')

                # Fact: Grade
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS fact_grade (
                        grade_key INTEGER PRIMARY KEY AUTOINCREMENT,
                        time_key INTEGER,
                        student_key INTEGER,
                        course_key INTEGER,
                        grade TEXT,
                        grade_points REAL,
                        credits INTEGER,
                        instructor TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (time_key) REFERENCES dim_time(time_key),
                        FOREIGN KEY (student_key) REFERENCES dim_student(student_key),
                        FOREIGN KEY (course_key) REFERENCES dim_course(course_key)
                    )
                ''')

                # Fact: Analytics Snapshot (aggregated metrics)
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS fact_analytics_snapshot (
                        snapshot_key INTEGER PRIMARY KEY AUTOINCREMENT,
                        time_key INTEGER,
                        total_students INTEGER,
                        active_enrollments INTEGER,
                        average_gpa REAL,
                        retention_rate REAL,
                        graduation_rate REAL,
                        total_revenue REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (time_key) REFERENCES dim_time(time_key)
                    )
                ''')

                # Create indexes for performance
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_fact_enrollment_time
                    ON fact_enrollment(time_key)
                ''')

                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_fact_grade_time
                    ON fact_grade(time_key)
                ''')

                logger.info("Data warehouse star schema ensured")
        except Exception as e:
            logger.error(f"Error creating star schema: {e}")

    def sync_operational_data(
        self,
        full_sync: bool = False
    ) -> Dict[str, int]:
        """
        Sync data from operational database to data warehouse

        Args:
            full_sync: If True, rebuild all dimensions and facts

        Returns:
            Dictionary with counts of synced records
        """
        counts = {
            'time_dimension': 0,
            'student_dimension': 0,
            'course_dimension': 0,
            'department_dimension': 0,
            'enrollment_facts': 0,
            'grade_facts': 0
        }

        try:
            # 1. Sync Time Dimension
            counts['time_dimension'] = self._sync_time_dimension()

            # 2. Sync Student Dimension
            counts['student_dimension'] = self._sync_student_dimension(full_sync)

            # 3. Sync Course Dimension
            counts['course_dimension'] = self._sync_course_dimension(full_sync)

            # 4. Sync Department Dimension
            counts['department_dimension'] = self._sync_department_dimension(full_sync)

            # 5. Sync Enrollment Facts
            counts['enrollment_facts'] = self._sync_enrollment_facts(full_sync)

            # 6. Sync Grade Facts
            counts['grade_facts'] = self._sync_grade_facts(full_sync)

            logger.info(f"Data warehouse sync completed: {counts}")
            return counts

        except Exception as e:
            logger.error(f"Error syncing operational data: {e}")
            return counts

    def _sync_time_dimension(self) -> int:
        """Populate time dimension for the next 5 years"""
        try:
            # Check if already populated
            with get_connection() as conn:
                cursor = conn.execute('SELECT COUNT(*) FROM dim_time')
                if cursor.fetchone()[0] > 0:
                    return 0  # Already populated

            count = 0
            start_date = datetime(2020, 1, 1)
            end_date = datetime.now() + timedelta(days=365*5)

            with transaction() as conn:
                current_date = start_date
                while current_date <= end_date:
                    time_key = int(current_date.strftime('%Y%m%d'))
                    date_str = current_date.strftime('%Y-%m-%d')
                    year = current_date.year
                    quarter = (current_date.month - 1) // 3 + 1
                    month = current_date.month
                    week = current_date.isocalendar()[1]
                    day = current_date.day
                    day_of_week = current_date.weekday()
                    month_name = current_date.strftime('%B')
                    quarter_name = f'Q{quarter}'

                    conn.execute('''
                        INSERT OR IGNORE INTO dim_time
                        (time_key, date, year, quarter, month, week, day,
                         day_of_week, month_name, quarter_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (time_key, date_str, year, quarter, month, week, day,
                          day_of_week, month_name, quarter_name))

                    count += 1
                    current_date += timedelta(days=1)

            logger.info(f"Populated time dimension with {count} records")
            return count

        except Exception as e:
            logger.error(f"Error syncing time dimension: {e}")
            return 0

    def _sync_student_dimension(self, full_sync: bool) -> int:
        """Sync student dimension"""
        try:
            with get_connection() as conn:
                # Extract from operational DB
                cursor = conn.execute('''
                    SELECT
                        student_id,
                        first_name || ' ' || last_name as student_name,
                        department,
                        enrollment_status,
                        strftime('%Y', created_at) as cohort_year,
                        gpa
                    FROM students
                ''')

                count = 0
                with transaction() as trans_conn:
                    for row in cursor.fetchall():
                        trans_conn.execute('''
                            INSERT OR REPLACE INTO dim_student
                            (student_id, student_name, department, enrollment_status,
                             cohort_year, current_gpa)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', row)
                        count += 1

            logger.info(f"Synced {count} student dimension records")
            return count

        except Exception as e:
            logger.error(f"Error syncing student dimension: {e}")
            return 0

    def _sync_course_dimension(self, full_sync: bool) -> int:
        """Sync course dimension"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        course_id,
                        course_code,
                        course_name,
                        department,
                        credits,
                        level
                    FROM courses
                ''')

                count = 0
                with transaction() as trans_conn:
                    for row in cursor.fetchall():
                        trans_conn.execute('''
                            INSERT OR REPLACE INTO dim_course
                            (course_id, course_code, course_name, department,
                             credits, level)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', row)
                        count += 1

            logger.info(f"Synced {count} course dimension records")
            return count

        except Exception as e:
            logger.error(f"Error syncing course dimension: {e}")
            return 0

    def _sync_department_dimension(self, full_sync: bool) -> int:
        """Sync department dimension"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT DISTINCT
                        department,
                        COUNT(DISTINCT student_id) as student_count
                    FROM students
                    WHERE department IS NOT NULL
                    GROUP BY department
                ''')

                count = 0
                with transaction() as trans_conn:
                    for row in cursor.fetchall():
                        trans_conn.execute('''
                            INSERT OR REPLACE INTO dim_department
                            (department_name, faculty_count)
                            VALUES (?, ?)
                        ''', (row[0], 0))  # Would populate faculty_count from staff table
                        count += 1

            logger.info(f"Synced {count} department dimension records")
            return count

        except Exception as e:
            logger.error(f"Error syncing department dimension: {e}")
            return 0

    def _sync_enrollment_facts(self, full_sync: bool) -> int:
        """Sync enrollment facts"""
        try:
            with get_connection() as conn:
                # Only sync recent enrollments unless full_sync
                where_clause = "" if full_sync else "WHERE e.created_at >= date('now', '-30 days')"

                cursor = conn.execute(f'''
                    SELECT
                        e.enrollment_id,
                        CAST(strftime('%Y%m%d', e.created_at) AS INTEGER) as time_key,
                        s.student_key,
                        c.course_key,
                        d.department_key,
                        e.status,
                        g.final_grade,
                        co.credits,
                        0.0 as tuition_amount
                    FROM enrollments e
                    LEFT JOIN dim_student s ON e.student_id = s.student_id
                    LEFT JOIN dim_course c ON e.course_id = c.course_id
                    LEFT JOIN courses co ON e.course_id = co.course_id
                    LEFT JOIN dim_department d ON co.department = d.department_name
                    LEFT JOIN grades g ON e.student_id = g.student_id
                        AND e.course_id = g.course_id
                    {where_clause}
                ''')

                count = 0
                with transaction() as trans_conn:
                    for row in cursor.fetchall():
                        trans_conn.execute('''
                            INSERT OR IGNORE INTO fact_enrollment
                            (time_key, student_key, course_key, department_key,
                             enrollment_status, grade, credits, tuition_amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', row[1:])  # Skip enrollment_id
                        count += 1

            logger.info(f"Synced {count} enrollment fact records")
            return count

        except Exception as e:
            logger.error(f"Error syncing enrollment facts: {e}")
            return 0

    def _sync_grade_facts(self, full_sync: bool) -> int:
        """Sync grade facts"""
        try:
            with get_connection() as conn:
                where_clause = "" if full_sync else "WHERE g.created_at >= date('now', '-30 days')"

                cursor = conn.execute(f'''
                    SELECT
                        CAST(strftime('%Y%m%d', g.created_at) AS INTEGER) as time_key,
                        s.student_key,
                        c.course_key,
                        g.final_grade,
                        CASE g.final_grade
                            WHEN 'A' THEN 4.0
                            WHEN 'B' THEN 3.0
                            WHEN 'C' THEN 2.0
                            WHEN 'D' THEN 1.0
                            ELSE 0.0
                        END as grade_points,
                        co.credits,
                        g.instructor_name
                    FROM grades g
                    LEFT JOIN dim_student s ON g.student_id = s.student_id
                    LEFT JOIN dim_course c ON g.course_id = c.course_id
                    LEFT JOIN courses co ON g.course_id = co.course_id
                    {where_clause}
                ''')

                count = 0
                with transaction() as trans_conn:
                    for row in cursor.fetchall():
                        trans_conn.execute('''
                            INSERT OR IGNORE INTO fact_grade
                            (time_key, student_key, course_key, grade,
                             grade_points, credits, instructor)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', row)
                        count += 1

            logger.info(f"Synced {count} grade fact records")
            return count

        except Exception as e:
            logger.error(f"Error syncing grade facts: {e}")
            return 0

    def create_analytics_snapshot(self) -> bool:
        """Create daily analytics snapshot"""
        try:
            time_key = int(datetime.now().strftime('%Y%m%d'))

            with get_connection() as conn:
                # Calculate metrics
                cursor = conn.execute('''
                    SELECT
                        COUNT(DISTINCT student_id) as total_students,
                        COUNT(DISTINCT CASE WHEN enrollment_status = 'enrolled' THEN student_id END) as active_students,
                        AVG(gpa) as avg_gpa
                    FROM students
                ''')

                row = cursor.fetchone()
                total_students = row[0] if row else 0
                active_students = row[1] if row else 0
                avg_gpa = row[2] if row and row[2] else 0.0

                # Insert snapshot
                with transaction() as trans_conn:
                    trans_conn.execute('''
                        INSERT INTO fact_analytics_snapshot
                        (time_key, total_students, active_enrollments, average_gpa,
                         retention_rate, graduation_rate, total_revenue)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (time_key, total_students, active_students, avg_gpa, 0.0, 0.0, 0.0))

                logger.info(f"Created analytics snapshot for {time_key}")
                return True

        except Exception as e:
            logger.error(f"Error creating analytics snapshot: {e}")
            return False

    def get_bi_dataset(
        self,
        dataset_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get dataset for BI tool consumption

        Args:
            dataset_name: Name of dataset (enrollment_trends, grade_distribution, etc.)
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of records
        """
        try:
            if dataset_name == 'enrollment_trends':
                return self._get_enrollment_trends_dataset(start_date, end_date)
            elif dataset_name == 'grade_distribution':
                return self._get_grade_distribution_dataset(start_date, end_date)
            elif dataset_name == 'department_metrics':
                return self._get_department_metrics_dataset()
            else:
                return []

        except Exception as e:
            logger.error(f"Error getting BI dataset: {e}")
            return []

    def _get_enrollment_trends_dataset(
        self,
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get enrollment trends dataset"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        t.date,
                        t.year,
                        t.month,
                        t.quarter,
                        COUNT(*) as enrollment_count,
                        d.department_name,
                        AVG(s.current_gpa) as avg_gpa
                    FROM fact_enrollment f
                    JOIN dim_time t ON f.time_key = t.time_key
                    LEFT JOIN dim_student s ON f.student_key = s.student_key
                    LEFT JOIN dim_department d ON f.department_key = d.department_key
                    GROUP BY t.date, d.department_name
                    ORDER BY t.date DESC
                ''')

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'date': row[0],
                        'year': row[1],
                        'month': row[2],
                        'quarter': row[3],
                        'enrollment_count': row[4],
                        'department': row[5] or 'Unknown',
                        'avg_gpa': round(row[6], 2) if row[6] else 0.0
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting enrollment trends dataset: {e}")
            return []

    def _get_grade_distribution_dataset(
        self,
        start_date: Optional[str],
        end_date: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get grade distribution dataset"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        c.course_code,
                        c.course_name,
                        c.department,
                        f.grade,
                        COUNT(*) as count,
                        AVG(f.grade_points) as avg_grade_points
                    FROM fact_grade f
                    JOIN dim_course c ON f.course_key = c.course_key
                    WHERE f.grade IS NOT NULL
                    GROUP BY c.course_code, f.grade
                    ORDER BY c.course_code, f.grade
                ''')

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'course_code': row[0],
                        'course_name': row[1],
                        'department': row[2],
                        'grade': row[3],
                        'count': row[4],
                        'avg_grade_points': round(row[5], 2) if row[5] else 0.0
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting grade distribution dataset: {e}")
            return []

    def _get_department_metrics_dataset(self) -> List[Dict[str, Any]]:
        """Get department metrics dataset"""
        try:
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT
                        d.department_name,
                        COUNT(DISTINCT s.student_key) as student_count,
                        AVG(s.current_gpa) as avg_gpa,
                        COUNT(DISTINCT f.course_key) as courses_offered
                    FROM dim_department d
                    LEFT JOIN dim_student s ON d.department_name = s.department
                    LEFT JOIN fact_enrollment f ON d.department_key = f.department_key
                    GROUP BY d.department_name
                    ORDER BY student_count DESC
                ''')

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'department': row[0],
                        'student_count': row[1],
                        'avg_gpa': round(row[2], 2) if row[2] else 0.0,
                        'courses_offered': row[3]
                    })

                return results

        except Exception as e:
            logger.error(f"Error getting department metrics dataset: {e}")
            return []


# Singleton instance
_data_warehouse: Optional[DataWarehouse] = None


def get_data_warehouse() -> DataWarehouse:
    """Get or create data warehouse singleton"""
    global _data_warehouse
    if _data_warehouse is None:
        _data_warehouse = DataWarehouse()
    return _data_warehouse
