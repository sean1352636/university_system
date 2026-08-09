import csv
import json
import datetime
from typing import Dict, List, Tuple

from education_system.systems.university.infrastructure.logging.log_config import configure_logging
from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = configure_logging(name=__name__)


class ExportOpsMixin:
    """Mixin providing export operations."""

    def export_students_to_file(self):
        """Export student data with filtering options"""
        from education_system.systems.university.infrastructure.database.db import sqlite3
        print("\n" + _t("shared.utils.batch_operations.title_export_students"))

        # Choose export format
        format_choice = input(_t("shared.utils.batch_operations.prompt_export_format"))
        if format_choice not in ['1', '2', '3']:
            print(_t("shared.utils.batch_operations.invalid_choice"))
            return

        formats = {'1': 'csv', '2': 'xlsx', '3': 'json'}
        export_format = formats[format_choice]

        # Choose filtering options
        print("\n" + _t("shared.utils.batch_operations.filtering_options"))
        print(_t("shared.utils.batch_operations.filter_all_students"))
        print(_t("shared.utils.batch_operations.filter_by_course"))
        print(_t("shared.utils.batch_operations.filter_by_date"))

        filter_choice = input(_t("shared.utils.batch_operations.prompt_choose_filter"))

        # Build query based on filter
        base_query = """
        SELECT s.student_id, s.email_address, s.title, s.first_name, s.middle_name,
               s.last_name, s.gender, s.dob, s.age, s.course, s.registration_datetime,
               GROUP_CONCAT(sm.module_code || ': ' || sm.module_name, '; ') as modules
        FROM students s
        LEFT JOIN student_modules sm ON s.student_id = sm.student_id
        """

        params = []

        if filter_choice == '2':
            course = input(_t("shared.utils.batch_operations.prompt_enter_course")).upper()
            if course in ['CS', 'DS']:
                base_query += " WHERE s.course = ?"
                params.append(course)
            else:
                print(_t("shared.utils.batch_operations.invalid_course"))
                return

        elif filter_choice == '3':
            start_date = input(_t("shared.utils.batch_operations.prompt_start_date"))
            end_date = input(_t("shared.utils.batch_operations.prompt_end_date"))
            base_query += " WHERE DATE(s.registration_datetime) BETWEEN ? AND ?"
            params.extend([start_date, end_date])

        base_query += " GROUP BY s.student_id ORDER BY s.last_name, s.first_name"

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(base_query, params)
            results = cursor.fetchall()

            if not results:
                print(_t("shared.utils.batch_operations.no_students_matching"))
                return

            print(_t("shared.utils.batch_operations.students_to_export", count=len(results)))

            # Get column names
            columns = [description[0] for description in cursor.description]

            # Choose output file
            default_filename = f"students_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_format}"
            output_path = input(_t("shared.utils.batch_operations.prompt_output_filename", default=default_filename)).strip()
            if not output_path:
                output_path = default_filename

            # Export data
            self.export_data_to_file(results, columns, output_path, export_format)

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()

    def export_data_to_file(self, data: List[Tuple], columns: List[str], filename: str, format_type: str):
        """Export data to specified format"""
        import pandas as pd
        try:
            if format_type == 'csv':
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(columns)
                    writer.writerows(data)

            elif format_type == 'xlsx':
                df = pd.DataFrame(data, columns=columns)
                df.to_excel(filename, index=False)

            elif format_type == 'json':
                # Convert to list of dictionaries
                json_data = [dict(zip(columns, row)) for row in data]
                with open(filename, 'w', encoding='utf-8') as jsonfile:
                    json.dump(json_data, jsonfile, indent=2, default=str)

            print(_t("shared.utils.batch_operations.export_success", filename=filename))

        except Exception as e:
            print(_t("shared.utils.batch_operations.error_exporting", error=str(e)))

    def export_enrollment_statistics(self):
        """Export course and module enrollment statistics"""
        from education_system.systems.university.infrastructure.database.db import sqlite3
        print("\n" + _t("shared.utils.batch_operations.title_export_stats"))

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stats = {}

            # Course enrollment stats
            cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
            stats['course_enrollment'] = dict(cursor.fetchall())

            # Module enrollment stats
            cursor.execute("""
            SELECT module_code, module_name, COUNT(*) as enrollment_count
            FROM student_modules
            GROUP BY module_code, module_name
            ORDER BY enrollment_count DESC
            """)
            stats['module_enrollment'] = [
                {'module_code': row[0], 'module_name': row[1], 'enrollment': row[2]}
                for row in cursor.fetchall()
            ]

            # Gender distribution
            cursor.execute("SELECT gender, COUNT(*) FROM students GROUP BY gender")
            stats['gender_distribution'] = dict(cursor.fetchall())

            # Age distribution
            cursor.execute("""
            SELECT
                CASE
                    WHEN age < 20 THEN 'Under 20'
                    WHEN age BETWEEN 20 AND 24 THEN '20-24'
                    WHEN age BETWEEN 25 AND 29 THEN '25-29'
                    WHEN age >= 30 THEN '30+'
                END as age_group,
                COUNT(*)
            FROM students
            GROUP BY age_group
            """)
            stats['age_distribution'] = dict(cursor.fetchall())

            # Registration trends (last 12 months)
            cursor.execute("""
            SELECT strftime('%Y-%m', registration_datetime) as month, COUNT(*)
            FROM students
            WHERE registration_datetime >= date('now', '-12 months')
            GROUP BY month
            ORDER BY month
            """)
            stats['registration_trends'] = dict(cursor.fetchall())

            # Export to JSON
            filename = f"enrollment_statistics_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, default=str)

            print(_t("shared.utils.batch_operations.stats_exported", filename=filename))

            # Display summary
            print("\n" + _t("shared.utils.batch_operations.summary"))
            print(f"{_t('shared.utils.batch_operations.course_enrollment')}: {stats['course_enrollment']}")
            print(f"{_t('shared.utils.batch_operations.total_students')}: {sum(stats['course_enrollment'].values())}")
            print(f"{_t('shared.utils.batch_operations.most_popular_module')}: {stats['module_enrollment'][0]['module_name']} ({stats['module_enrollment'][0]['enrollment']} {_t('shared.utils.batch_operations.students')})")

        except sqlite3.Error as e:
            print(_t("shared.utils.batch_operations.database_error", error=str(e)))
        finally:
            conn.close()
