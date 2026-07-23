"""Monitor and report on data quality issues."""

from datetime import datetime

from education_system.post_18.university_system.modules.shared.services.analytics.enhanced_reporting.config import get_reporting_db_connection


class DataQualityMonitor:
    """Monitor and report on data quality issues"""

    @staticmethod
    def run_quality_checks():
        conn = get_reporting_db_connection()
        quality_report = {
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }

        try:
            # Check for missing data
            missing_data = DataQualityMonitor.check_missing_data(conn)
            quality_report['checks']['missing_data'] = missing_data

            # Check for duplicates
            duplicates = DataQualityMonitor.check_duplicates(conn)
            quality_report['checks']['duplicates'] = duplicates

            # Check for invalid data
            invalid_data = DataQualityMonitor.check_invalid_data(conn)
            quality_report['checks']['invalid_data'] = invalid_data

            # Check data freshness
            freshness = DataQualityMonitor.check_data_freshness(conn)
            quality_report['checks']['data_freshness'] = freshness

        finally:
            conn.close()

        return quality_report

    @staticmethod
    def check_missing_data(conn):
        results = {}

        # Check students table
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM students WHERE email_address IS NULL OR email_address = ''")
        missing_emails = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM students WHERE first_name IS NULL OR first_name = ''")
        missing_names = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM students WHERE course IS NULL OR course = ''")
        missing_courses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM students")
        total_students = cursor.fetchone()[0]

        results['students'] = {
            'missing_emails': missing_emails,
            'missing_names': missing_names,
            'missing_courses': missing_courses,
            'total_records': total_students
        }

        return results

    @staticmethod
    def check_duplicates(conn):
        results = {}

        cursor = conn.cursor()

        # Check for duplicate emails
        cursor.execute("""
            SELECT email_address, COUNT(*) as count
            FROM students
            WHERE email_address IS NOT NULL AND email_address != ''
            GROUP BY email_address
            HAVING COUNT(*) > 1
        """)
        duplicate_emails = cursor.fetchall()

        results['duplicate_emails'] = len(duplicate_emails)
        results['duplicate_email_details'] = [{'email': row[0], 'count': row[1]} for row in duplicate_emails]

        return results

    @staticmethod
    def check_invalid_data(conn):
        results = {}

        cursor = conn.cursor()

        # Check for invalid ages
        cursor.execute("SELECT COUNT(*) FROM students WHERE age < 0 OR age > 100")
        invalid_ages = cursor.fetchone()[0]

        # Check for invalid email formats
        cursor.execute("""
            SELECT COUNT(*) FROM students
            WHERE email_address IS NOT NULL
            AND email_address != ''
            AND email_address NOT LIKE '%@%.%'
        """)
        invalid_emails = cursor.fetchone()[0]

        results['invalid_ages'] = invalid_ages
        results['invalid_emails'] = invalid_emails

        return results

    @staticmethod
    def check_data_freshness(conn):
        results = {}

        cursor = conn.cursor()

        # Check when data was last updated
        cursor.execute("SELECT MAX(registration_datetime) FROM students")
        last_registration = cursor.fetchone()[0]

        if last_registration:
            last_reg_date = datetime.strptime(last_registration, '%Y-%m-%d %H:%M:%S')
            days_since_last = (datetime.now() - last_reg_date).days
            results['days_since_last_registration'] = days_since_last
            results['last_registration_date'] = last_registration
        else:
            results['days_since_last_registration'] = None
            results['last_registration_date'] = None

        return results
