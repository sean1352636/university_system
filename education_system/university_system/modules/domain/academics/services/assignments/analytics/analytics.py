from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.sql_safety import validate_table_name
from datetime import datetime, timedelta
import csv
import os


class AnalyticsMixin:
    """Mixin providing analytics dashboard, reports, and calendar view."""

    def generate_analytics_dashboard(self):
        """Generate comprehensive analytics dashboard"""
        if not self._check_permission('view_all_submissions'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            print("\nAnalytics Dashboard")
            print("=" * 50)

            # Overall statistics
            cursor.execute('SELECT COUNT(*) FROM assignments WHERE is_active = 1')
            total_assignments = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM assignment_submissions')
            total_submissions = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE grade IS NOT NULL')
            graded_submissions = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE late_submission = 1')
            late_submissions = cursor.fetchone()[0]

            print(f"Total Active Assignments: {total_assignments}")
            print(f"Total Submissions: {total_submissions}")
            print(f"Graded Submissions: {graded_submissions}")
            print(f"Late Submissions: {late_submissions}")

            if total_submissions > 0:
                print(f"Grading Progress: {(graded_submissions/total_submissions)*100:.1f}%")
                print(f"Late Submission Rate: {(late_submissions/total_submissions)*100:.1f}%")

            # Module-wise statistics
            print("\nModule-wise Statistics:")
            cursor.execute('''
            SELECT a.module_code, COUNT(DISTINCT a.id) as assignments,
                   COUNT(s.id) as submissions, AVG(s.grade) as avg_grade
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE a.is_active = 1
            GROUP BY a.module_code
            ORDER BY a.module_code
            ''')

            module_stats = cursor.fetchall()
            for module, assignments, submissions, avg_grade in module_stats:
                grade_text = f"{avg_grade:.1f}%" if avg_grade else "N/A"
                print(f"- {module}: {assignments} assignments, {submissions} submissions, Avg: {grade_text}")

            # Grade distribution
            print("\nGrade Distribution:")
            cursor.execute('''
            SELECT
                CASE
                    WHEN grade >= 90 THEN 'A (90-100%)'
                    WHEN grade >= 80 THEN 'B (80-89%)'
                    WHEN grade >= 70 THEN 'C (70-79%)'
                    WHEN grade >= 60 THEN 'D (60-69%)'
                    ELSE 'F (Below 60%)'
                END as grade_band,
                COUNT(*) as count
            FROM assignment_submissions
            WHERE grade IS NOT NULL
            GROUP BY
                CASE
                    WHEN grade >= 90 THEN 'A (90-100%)'
                    WHEN grade >= 80 THEN 'B (80-89%)'
                    WHEN grade >= 70 THEN 'C (70-79%)'
                    WHEN grade >= 60 THEN 'D (60-69%)'
                    ELSE 'F (Below 60%)'
                END
            ORDER BY grade_band
            ''')

            grade_dist = cursor.fetchall()
            for grade_band, count in grade_dist:
                print(f"- {grade_band}: {count} students")

            # Recent activity
            print("\nRecent Activity (Last 7 days):")
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            SELECT COUNT(*) FROM assignment_submissions WHERE submission_date >= ?
            ''', (week_ago,))
            recent_submissions = cursor.fetchone()[0]

            cursor.execute('''
            SELECT COUNT(*) FROM assignment_submissions WHERE graded_date >= ?
            ''', (week_ago,))
            recent_gradings = cursor.fetchone()[0]

            print(f"- New submissions: {recent_submissions}")
            print(f"- Assignments graded: {recent_gradings}")

            # Export option
            export = input("\nExport detailed report? (y/n): ").lower()
            if export == 'y':
                self._export_analytics_report(cursor)

            conn.close()

        except Exception as e:
            print(f"Error generating analytics: {e}")

    def _export_analytics_report(self, cursor):
        """Export detailed analytics report"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"analytics_report_{timestamp}.csv"
            filepath = os.path.join(self.submission_dir, 'exports', filename)

            cursor.execute('''
            SELECT a.title, a.module_code, a.due_date,
                   COUNT(s.id) as submissions,
                   COUNT(CASE WHEN s.grade IS NOT NULL THEN 1 END) as graded,
                   COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) as late,
                   AVG(s.grade) as avg_grade,
                   MIN(s.grade) as min_grade,
                   MAX(s.grade) as max_grade
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE a.is_active = 1
            GROUP BY a.id, a.title, a.module_code, a.due_date
            ORDER BY a.due_date
            ''')

            data = cursor.fetchall()

            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['Assignment', 'Module', 'Due Date', 'Submissions',
                               'Graded', 'Late', 'Avg Grade', 'Min Grade', 'Max Grade'])

                for row in data:
                    writer.writerow(row)

            print(f"Report exported to: {filepath}")

        except Exception as e:
            print(f"Error exporting report: {e}")

    def view_assignment_calendar(self):
        """View assignments in calendar format"""
        if not self._check_permission('view_assignments'):
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now()
            start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                end_of_month = start_of_month.replace(year=now.year + 1, month=1) - timedelta(days=1)
            else:
                end_of_month = start_of_month.replace(month=now.month + 1) - timedelta(days=1)

            student_id = self._get_student_id()
            if student_id:
                cursor.execute('''
                SELECT a.title, a.due_date, a.module_code
                FROM assignments a
                JOIN student_modules sm ON a.module_code = sm.module_code
                WHERE sm.student_id = ? AND a.is_active = 1
                AND date(a.due_date) BETWEEN ? AND ?
                ORDER BY a.due_date
                ''', (student_id, start_of_month.strftime('%Y-%m-%d'),
                      end_of_month.strftime('%Y-%m-%d')))
            else:
                cursor.execute('''
                SELECT title, due_date, module_code
                FROM assignments
                WHERE is_active = 1
                AND date(due_date) BETWEEN ? AND ?
                ORDER BY due_date
                ''', (start_of_month.strftime('%Y-%m-%d'),
                      end_of_month.strftime('%Y-%m-%d')))

            assignments = cursor.fetchall()

            print(f"\nAssignment Calendar - {now.strftime('%B %Y')}")
            print("=" * 60)

            if not assignments:
                print("No assignments this month.")
            else:
                current_date = None
                for title, due_date, module in assignments:
                    due_dt = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                    date_str = due_dt.strftime('%Y-%m-%d')

                    if date_str != current_date:
                        current_date = date_str
                        print(f"\n{due_dt.strftime('%A, %B %d, %Y')}:")
                        print("-" * 30)

                    print(f"  {due_dt.strftime('%H:%M')} - {title} ({module})")

            conn.close()

        except Exception as e:
            print(f"Error viewing calendar: {e}")

    # API methods

    def get_grade_distribution(self, assignment_id):
        """Get grade distribution statistics for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT grade FROM assignment_submissions
                WHERE assignment_id = ? AND grade IS NOT NULL
            ''', (assignment_id,))

            grades = [row[0] for row in cursor.fetchall()]
            conn.close()

            if not grades:
                return {}

            import statistics
            return {
                'count': len(grades),
                'mean': statistics.mean(grades),
                'median': statistics.median(grades),
                'min': min(grades),
                'max': max(grades),
                'std_dev': statistics.stdev(grades) if len(grades) > 1 else 0
            }

        except Exception as e:
            print(f"Error calculating grade distribution: {e}")
            return {}

    def get_submission_trends(self, assignment_id):
        """Get submission trends over time"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT DATE(submission_date) as date, COUNT(*) as count
                FROM assignment_submissions
                WHERE assignment_id = ?
                GROUP BY DATE(submission_date)
                ORDER BY date
            ''', (assignment_id,))

            trends = cursor.fetchall()
            conn.close()

            return [{'date': row[0], 'count': row[1]} for row in trends]

        except Exception as e:
            print(f"Error getting submission trends: {e}")
            return []

    def get_performance_analytics(self, student_id=None):
        """Get performance analytics for a student"""
        try:
            if not student_id:
                student_id = self._get_student_id()

            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT
                        COUNT(*) as total_submissions,
                        COUNT(CASE WHEN grade IS NOT NULL THEN 1 END) as graded_count,
                        AVG(grade) as avg_grade,
                        COUNT(CASE WHEN late_submission = 1 THEN 1 END) as late_count
                    FROM assignment_submissions
                    WHERE student_id = ?
                ''', (student_id,))

                result = cursor.fetchone()
            finally:
                conn.close()

            return {
                'total_submissions': result[0],
                'graded_count': result[1],
                'average_grade': result[2],
                'late_submissions': result[3]
            }

        except Exception as e:
            print(f"Error getting performance analytics: {e}")
            return {}

    def get_engagement_metrics(self, assignment_id):
        """Get engagement metrics for an assignment"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(DISTINCT sm.student_id)
                FROM student_modules sm
                INNER JOIN assignments a ON sm.module_code = a.module_code
                WHERE a.id = ?
            ''', (assignment_id,))
            total_students = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))
            submission_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ? AND late_submission = 1', (assignment_id,))
            late_count = cursor.fetchone()[0]

            conn.close()

            return {
                'total_students': total_students,
                'submission_count': submission_count,
                'submission_rate': (submission_count / total_students * 100) if total_students > 0 else 0,
                'late_submissions': late_count,
                'on_time_submissions': submission_count - late_count
            }

        except Exception as e:
            print(f"Error getting engagement metrics: {e}")
            return {}

    def generate_custom_report(self, report_type, filters=None):
        """Generate a custom analytics report"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            if report_type == 'module_performance':
                query = '''
                    SELECT
                        a.module_code,
                        COUNT(DISTINCT a.id) as assignment_count,
                        COUNT(s.id) as submission_count,
                        AVG(s.grade) as avg_grade
                    FROM assignments a
                    LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
                    GROUP BY a.module_code
                '''
            elif report_type == 'student_summary':
                query = '''
                    SELECT
                        s.student_id,
                        COUNT(s.id) as submissions,
                        AVG(s.grade) as avg_grade,
                        COUNT(CASE WHEN s.late_submission = 1 THEN 1 END) as late_count
                    FROM assignment_submissions s
                    GROUP BY s.student_id
                '''
            else:
                print("Unknown report type")
                return []

            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()

            return results

        except Exception as e:
            print(f"Error generating custom report: {e}")
            return []
