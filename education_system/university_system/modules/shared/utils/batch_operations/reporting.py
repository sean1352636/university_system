import os
import json
import datetime
from typing import Dict, List

from education_system.university_system.utils.logging.log_config import configure_logging
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

logger = configure_logging(name=__name__)


class ReportingMixin:
    """Mixin providing reporting, history, and data quality dashboard methods."""

    def generate_import_reports(self):
        """Generate detailed reports on batch operations"""
        print("\n" + _t("shared.utils.batch_operations.title_generate_reports"))

        if not self.import_history:
            try:
                with open('import_history.json', 'r') as f:
                    self.import_history = json.load(f)
            except FileNotFoundError:
                print(_t("shared.utils.batch_operations.no_import_history"))
                return

        if not self.import_history:
            print(_t("shared.utils.batch_operations.no_history_available"))
            return

        print("\n" + _t("shared.utils.batch_operations.report_options"))
        print(_t("shared.utils.batch_operations.report_success_rates"))
        print(_t("shared.utils.batch_operations.report_error_analysis"))
        print(_t("shared.utils.batch_operations.report_performance"))
        print(_t("shared.utils.batch_operations.report_comprehensive"))

        choice = input(_t("shared.utils.batch_operations.prompt_choose_report"))

        if choice == '1':
            self.generate_success_rate_report()
        elif choice == '2':
            self.generate_error_analysis_report()
        elif choice == '3':
            self.generate_performance_report()
        elif choice == '4':
            self.generate_comprehensive_report()
        else:
            print(_t("shared.utils.batch_operations.invalid_choice"))

    def generate_success_rate_report(self):
        """Generate import success rate report"""
        print("\n" + _t("shared.utils.batch_operations.title_success_rate_report"))

        total_operations = len(self.import_history)
        total_records = sum(op['total_records'] for op in self.import_history)
        total_successful = sum(op['successful_imports'] for op in self.import_history)
        total_failed = sum(op['failed_imports'] for op in self.import_history)

        success_rate = (total_successful / total_records * 100) if total_records > 0 else 0

        report = {
            'summary': {
                'total_operations': total_operations,
                'total_records_processed': total_records,
                'total_successful_imports': total_successful,
                'total_failed_imports': total_failed,
                'overall_success_rate': round(success_rate, 2)
            },
            'by_operation_type': {},
            'recent_operations': self.import_history[-10:]
        }

        # Group by operation type
        by_type = {}
        for op in self.import_history:
            op_type = op['operation_type']
            if op_type not in by_type:
                by_type[op_type] = {'operations': 0, 'total': 0, 'successful': 0, 'failed': 0}

            by_type[op_type]['operations'] += 1
            by_type[op_type]['total'] += op['total_records']
            by_type[op_type]['successful'] += op['successful_imports']
            by_type[op_type]['failed'] += op['failed_imports']

        for op_type, stats in by_type.items():
            sr = (stats['successful'] / stats['total'] * 100) if stats['total'] > 0 else 0
            report['by_operation_type'][op_type] = {
                'operations': stats['operations'],
                'total_records': stats['total'],
                'success_rate': round(sr, 2)
            }

        # Export report
        filename = f"success_rate_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(_t("shared.utils.batch_operations.success_rate_exported", filename=filename))
        print(_t("shared.utils.batch_operations.overall_success_rate", rate=f"{success_rate:.1f}"))

    def generate_error_analysis_report(self):
        """Analyze common errors in import operations"""
        print("\n" + _t("shared.utils.batch_operations.title_error_analysis"))

        all_errors = []
        for op in self.import_history:
            all_errors.extend(op.get('errors', []))

        if not all_errors:
            print(_t("shared.utils.batch_operations.no_errors_in_history"))
            return

        # Analyze error patterns
        error_types = {}
        for error in all_errors:
            error_msg = error.get('error', 'Unknown error')
            error_types[error_msg] = error_types.get(error_msg, 0) + 1

        # Sort by frequency
        sorted_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)

        report = {
            'total_errors': len(all_errors),
            'unique_error_types': len(error_types),
            'most_common_errors': sorted_errors[:10],
            'error_frequency_analysis': {
                'validation_errors': len([e for e in all_errors if 'validation' in str(e).lower()]),
                'database_errors': len([e for e in all_errors if 'database' in str(e).lower()]),
                'format_errors': len([e for e in all_errors if 'format' in str(e).lower()])
            }
        }

        filename = f"error_analysis_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(_t("shared.utils.batch_operations.error_analysis_exported", filename=filename))
        print(_t("shared.utils.batch_operations.most_common_error", error=sorted_errors[0][0], count=sorted_errors[0][1]))

    def generate_performance_report(self):
        """Generate performance trends report"""
        print("\n" + _t("shared.utils.batch_operations.title_performance_report"))

        performance_data = []
        for op in self.import_history:
            if op['duration_seconds'] > 0:
                records_per_second = op['total_records'] / op['duration_seconds']
                performance_data.append({
                    'timestamp': op['timestamp'],
                    'operation_type': op['operation_type'],
                    'total_records': op['total_records'],
                    'duration_seconds': op['duration_seconds'],
                    'records_per_second': round(records_per_second, 2)
                })

        if not performance_data:
            print(_t("shared.utils.batch_operations.no_performance_data"))
            return

        avg_performance = sum(p['records_per_second'] for p in performance_data) / len(performance_data)

        report = {
            'summary': {
                'total_operations_analyzed': len(performance_data),
                'average_records_per_second': round(avg_performance, 2),
                'fastest_operation': max(performance_data, key=lambda x: x['records_per_second']),
                'slowest_operation': min(performance_data, key=lambda x: x['records_per_second'])
            },
            'performance_by_operation_type': {},
            'detailed_performance': performance_data
        }

        # Group by operation type
        by_type = {}
        for p in performance_data:
            op_type = p['operation_type']
            if op_type not in by_type:
                by_type[op_type] = []
            by_type[op_type].append(p['records_per_second'])

        for op_type, speeds in by_type.items():
            report['performance_by_operation_type'][op_type] = {
                'average_records_per_second': round(sum(speeds) / len(speeds), 2),
                'operations_count': len(speeds),
                'best_performance': round(max(speeds), 2),
                'worst_performance': round(min(speeds), 2)
            }

        filename = f"performance_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        print(_t("shared.utils.batch_operations.performance_exported", filename=filename))
        print(_t("shared.utils.batch_operations.average_performance", rate=f"{avg_performance:.1f}"))

    def generate_comprehensive_report(self):
        """Generate a comprehensive report with all metrics"""
        print("\n" + _t("shared.utils.batch_operations.generating_comprehensive"))

        # Combine all report types
        self.generate_success_rate_report()
        self.generate_error_analysis_report()
        self.generate_performance_report()

        print(_t("shared.utils.batch_operations.comprehensive_complete"))

    def data_quality_dashboard(self):
        """Display comprehensive data quality dashboard"""
        from education_system.university_system.infrastructure.database.db import sqlite3
        print("\n" + _t("shared.utils.batch_operations.title_quality_dashboard"))

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Basic statistics
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT email_address) FROM students")
            unique_emails = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM students WHERE email_address IS NULL OR email_address = ''")
            missing_emails = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM students WHERE first_name IS NULL OR first_name = '' OR last_name IS NULL OR last_name = ''")
            incomplete_names = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM students WHERE dob IS NULL OR dob = ''")
            missing_dob = cursor.fetchone()[0]

            # Module enrollment completeness
            cursor.execute('''
            SELECT COUNT(DISTINCT s.student_id)
            FROM students s
            LEFT JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.student_id IS NULL
            ''')
            students_no_modules = cursor.fetchone()[0]

            # Display dashboard
            print(_t("batch_ops.dashboard.overall_statistics"))
            print(_t("batch_ops.dashboard.total_students", count=f"{total_students:,}"))
            print(_t("batch_ops.dashboard.data_completeness", percentage=f"{((total_students - missing_emails - incomplete_names - missing_dob) / total_students * 100):.1f}"))

            print(_t("batch_ops.dashboard.email_quality"))
            print(_t("batch_ops.dashboard.unique_emails", count=f"{unique_emails:,}"))
            print(_t("batch_ops.dashboard.missing_emails", count=f"{missing_emails:,}"))
            print(_t("batch_ops.dashboard.email_uniqueness", percentage=f"{(unique_emails / total_students * 100):.1f}"))

            print(_t("batch_ops.dashboard.name_completeness"))
            print(_t("batch_ops.dashboard.complete_names", count=f"{total_students - incomplete_names:,}"))
            print(_t("batch_ops.dashboard.incomplete_names", count=f"{incomplete_names:,}"))

            print(_t("batch_ops.dashboard.date_of_birth"))
            print(_t("batch_ops.dashboard.missing_dob", count=f"{missing_dob:,}"))
            print(_t("batch_ops.dashboard.dob_completeness", percentage=f"{((total_students - missing_dob) / total_students * 100):.1f}"))

            print(_t("batch_ops.dashboard.module_enrollment"))
            print(_t("batch_ops.dashboard.students_no_modules", count=f"{students_no_modules:,}"))
            print(_t("batch_ops.dashboard.enrollment_rate", percentage=f"{((total_students - students_no_modules) / total_students * 100):.1f}"))

            # Course distribution
            cursor.execute("SELECT course, COUNT(*) FROM students GROUP BY course")
            course_dist = cursor.fetchall()
            print(_t("batch_ops.dashboard.course_distribution"))
            for course, count in course_dist:
                percentage = (count / total_students * 100)
                print(f"{course}: {count:,} ({percentage:.1f}%)")

            # Age distribution
            cursor.execute('''
            SELECT
                CASE
                    WHEN age < 20 THEN 'Under 20'
                    WHEN age BETWEEN 20 AND 24 THEN '20-24'
                    WHEN age BETWEEN 25 AND 29 THEN '25-29'
                    WHEN age >= 30 THEN '30+'
                END as age_group,
                COUNT(*)
            FROM students
            WHERE age IS NOT NULL
            GROUP BY age_group
            ''')
            age_dist = cursor.fetchall()
            print(_t("batch_ops.dashboard.age_distribution"))
            for age_group, count in age_dist:
                percentage = (count / total_students * 100)
                print(f"{age_group}: {count:,} ({percentage:.1f}%)")

            # Registration trends
            cursor.execute('''
            SELECT DATE(registration_datetime) as reg_date, COUNT(*)
            FROM students
            WHERE registration_datetime >= date('now', '-30 days')
            GROUP BY reg_date
            ORDER BY reg_date DESC
            LIMIT 10
            ''')
            recent_registrations = cursor.fetchall()
            print(_t("batch_ops.dashboard.recent_registrations"))
            for date, count in recent_registrations:
                print(f"{date}: {count:,} students")

        except sqlite3.Error as e:
            print(_t("batch_ops.dashboard.database_error", error=str(e)))
        finally:
            conn.close()

    def show_import_history(self):
        """Display import operation history"""
        print("\n" + _t("shared.utils.batch_operations.title_import_history"))

        if not self.import_history:
            try:
                with open('import_history.json', 'r') as f:
                    self.import_history = json.load(f)
            except FileNotFoundError:
                print(_t("shared.utils.batch_operations.no_import_history"))
                return

        if not self.import_history:
            print(_t("shared.utils.batch_operations.no_history_available"))
            return

        print("\n" + _t("shared.utils.batch_operations.showing_operations", count=min(20, len(self.import_history))))
        print("-" * 100)

        for i, op in enumerate(reversed(self.import_history[-20:]), 1):
            timestamp = datetime.datetime.fromisoformat(op['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            status = "UNDONE" if op.get('undone', False) else "ACTIVE"

            print(f"{i:2}. {timestamp} | {op['operation_type']:<25} | "
                  f"Records: {op['successful_imports']:4}/{op['total_records']:<4} | "
                  f"Errors: {op['failed_imports']:3} | {status}")

            if op['failed_imports'] > 0 and op.get('errors'):
                print(f"    \U0001f4c4 File: {os.path.basename(op['file_path'])}")
                print(f"    \u274c Sample errors: {'; '.join([e.get('error', 'Unknown')[:50] for e in op['errors'][:2]])}")

        # Show summary statistics
        total_ops = len(self.import_history)
        total_records = sum(op['total_records'] for op in self.import_history)
        total_successful = sum(op['successful_imports'] for op in self.import_history)
        total_failed = sum(op['failed_imports'] for op in self.import_history)

        print("\n" + _t("shared.utils.batch_operations.summary_statistics"))
        print(f"{_t('shared.utils.batch_operations.total_operations')}: {total_ops}")
        print(f"{_t('shared.utils.batch_operations.total_records_processed')}: {total_records:,}")
        success_rate = f"{(total_successful/total_records*100):.1f}%" if total_records > 0 else "N/A"
        print(f"{_t('shared.utils.batch_operations.success_rate')}: {success_rate}")
        print(f"{_t('shared.utils.batch_operations.total_errors')}: {total_failed:,}")
