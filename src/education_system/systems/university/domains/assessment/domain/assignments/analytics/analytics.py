from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import validate_table_name
from education_system.systems.university.domains.assessment.domain.assignments.core.constants import SUBDIR_EXPORTS
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
            filepath = os.path.join(self.submission_dir, SUBDIR_EXPORTS, filename)

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

    # UK classification bands, highest first.
    _BANDS = ((70, "First (70+)"), (60, "2:1 (60-69)"), (50, "2:2 (50-59)"),
              (40, "Third (40-49)"), (0, "Fail (<40)"))

    def generate_advanced_analytics(self):
        """Per-assignment depth: mark bands, spread, marker comparison, timeliness."""
        if not self._check_permission('view_all_submissions'):
            return
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            assignments = conn.execute(
                "SELECT id, module_code, title, due_date FROM assignments "
                "WHERE COALESCE(is_active, 1) = 1 ORDER BY due_date DESC").fetchall()
        finally:
            conn.close()
        if not assignments:
            print("No assignments.")
            return
        print(f"\n{'ID':<5} {'Module':<11} {'Title':<40} {'Due':<16}")
        for a in assignments:
            print(f"{a['id']:<5} {str(a['module_code'])[:10]:<11} {str(a['title'])[:39]:<40} {str(a['due_date'])[:16]}")
        choice = input("\nAssignment ID (Enter = every assignment in a module): ").strip()
        if choice.isdigit() and int(choice) in {a['id'] for a in assignments}:
            ids = [int(choice)]
        else:
            module = input("Module code: ").strip()
            ids = [a['id'] for a in assignments if str(a['module_code']).lower() == module.lower()]
            if not ids:
                print("No assignments for that module.")
                return
        for aid in ids:
            self._advanced_assignment_report(aid)

    def _advanced_assignment_report(self, assignment_id):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            a = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
            subs = [dict(r) for r in conn.execute(
                "SELECT s.grade, s.graded_by, s.late_submission, s.late_days, s.submission_date, "
                "       s.word_count, s.word_penalty_pct, u.username AS marker "
                "FROM assignment_submissions s LEFT JOIN users u ON u.id = s.graded_by "
                "WHERE s.assignment_id = ? AND COALESCE(s.is_final_submission, 1) = 1",
                (assignment_id,))]
            ns = conn.execute("SELECT COUNT(*) FROM assignment_non_submissions "
                              "WHERE assignment_id = ? AND voided = 0", (assignment_id,)).fetchone()[0]
        finally:
            conn.close()
        engagement = self.get_engagement_metrics(assignment_id)
        print(f"\n{'=' * 70}\n#{assignment_id} {a['title']} ({a['module_code']}) — due {str(a['due_date'])[:16]}")
        print(f"{'=' * 70}")
        cohort = engagement.get('total_students', 0)
        print(f"Cohort: {cohort}   Submitted: {len(subs)}"
              + (f" ({len(subs) / cohort * 100:.0f}%)" if cohort else "")
              + f"   Late: {sum(1 for s in subs if s['late_submission'])}   Non-submissions: {ns}")
        late_days = [s['late_days'] for s in subs if s['late_submission'] and s['late_days']]
        if late_days:
            print(f"Average lateness: {sum(late_days) / len(late_days):.1f} day(s)")

        marks = [float(s['grade']) for s in subs if s['grade'] is not None]
        if not marks:
            print("No marks recorded yet.")
            return
        import statistics
        print(f"\nMarked: {len(marks)}   Mean {statistics.mean(marks):.1f}   Median {statistics.median(marks):.1f}   "
              f"SD {statistics.stdev(marks) if len(marks) > 1 else 0:.1f}   Range {min(marks):.0f}-{max(marks):.0f}")
        print("\nMark bands:")
        for floor, label in self._BANDS:
            ceiling = next((f for f, _ in self._BANDS if f > floor), 101)
            count = sum(1 for m in marks if floor <= m < ceiling)
            bar = '#' * round(count / len(marks) * 40)
            print(f"  {label:<14} {count:>4}  {bar}")

        by_marker = {}
        for s in subs:
            if s['grade'] is not None:
                by_marker.setdefault(s['marker'] or str(s['graded_by'] or 'unknown'), []).append(float(s['grade']))
        if len(by_marker) > 1:
            print("\nBy marker (a large gap can signal a moderation need):")
            overall = statistics.mean(marks)
            for marker, ms in sorted(by_marker.items()):
                print(f"  {marker[:20]:<20} {len(ms):>4} scripts   mean {statistics.mean(ms):5.1f}   "
                      f"({statistics.mean(ms) - overall:+.1f} vs overall)")

        on_time = [float(s['grade']) for s in subs if s['grade'] is not None and not s['late_submission']]
        late = [float(s['grade']) for s in subs if s['grade'] is not None and s['late_submission']]
        if on_time and late:
            print(f"\nOn-time mean {statistics.mean(on_time):.1f} vs late mean {statistics.mean(late):.1f}")
        penalised = sum(1 for s in subs if s['word_penalty_pct'])
        if penalised:
            print(f"Word-limit penalties applied: {penalised}")

    _CUSTOM_REPORTS = (
        ("module_performance", "Module performance (assignments, submissions, average mark)"),
        ("student_summary", "Student summary (submissions, average mark, lateness)"),
        ("assignment_status", "Assignment status (marked / released / outstanding)"),
        ("late_submissions", "Late submissions"),
        ("at_risk", "Students at risk (average under 40%, or non-submissions)"),
    )

    def generate_custom_reports(self):
        """Pick a report, view it, and optionally save it as CSV."""
        if not self._check_permission('view_all_submissions'):
            return
        print("\nCustom Reports")
        for i, (_, label) in enumerate(self._CUSTOM_REPORTS, 1):
            print(f"{i}. {label}")
        choice = input("Report number: ").strip()
        if not choice.isdigit() or not 0 < int(choice) <= len(self._CUSTOM_REPORTS):
            print("Invalid choice.")
            return
        key, label = self._CUSTOM_REPORTS[int(choice) - 1]
        module = input("Limit to module code (Enter for all): ").strip() or None
        headers, rows = self._custom_report_rows(key, module)
        if not rows:
            print("The report is empty.")
            return
        widths = [max(len(str(h)), *(len(self._fmt_cell(r[i])) for r in rows)) for i, h in enumerate(headers)]
        widths = [min(w, 30) for w in widths]
        print("\n" + label)
        print("  ".join(str(h)[:w].ljust(w) for h, w in zip(headers, widths)))
        print("-" * (sum(widths) + 2 * len(widths)))
        for r in rows:
            print("  ".join(self._fmt_cell(v)[:w].ljust(w) for v, w in zip(r, widths)))
        print(f"\n{len(rows)} row(s).")
        if input("Save as CSV? (y/n): ").strip().lower() == 'y':
            folder = os.path.join(self.submission_dir, SUBDIR_EXPORTS)
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"{key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            with open(path, 'w', newline='') as fh:
                writer = csv.writer(fh)
                writer.writerow(headers)
                writer.writerows(rows)
            print(f"Saved to {path}")

    @staticmethod
    def _fmt_cell(value):
        if value is None:
            return '—'
        if isinstance(value, float):
            return f"{value:.1f}"
        return str(value)

    def _custom_report_rows(self, key, module=None):
        mod = " AND a.module_code = ?" if module else ""
        params = (module,) if module else ()
        final = "COALESCE(s.is_final_submission, 1) = 1"
        queries = {
            "module_performance": (
                ["Module", "Assignments", "Submissions", "Marked", "Average %"],
                f"SELECT a.module_code, COUNT(DISTINCT a.id), COUNT(s.id), COUNT(s.grade), AVG(s.grade) "
                f"FROM assignments a LEFT JOIN assignment_submissions s ON s.assignment_id = a.id AND {final} "
                f"WHERE COALESCE(a.is_active, 1) = 1{mod} GROUP BY a.module_code ORDER BY a.module_code"),
            "student_summary": (
                ["Student", "Name", "Submissions", "Average %", "Late"],
                f"SELECT s.student_id, TRIM(COALESCE(st.first_name, '') || ' ' || COALESCE(st.last_name, '')), "
                f"       COUNT(s.id), AVG(s.grade), SUM(CASE WHEN s.late_submission = 1 THEN 1 ELSE 0 END) "
                f"FROM assignment_submissions s JOIN assignments a ON a.id = s.assignment_id "
                f"LEFT JOIN students st ON st.student_id = s.student_id "
                f"WHERE {final}{mod} GROUP BY s.student_id ORDER BY s.student_id"),
            "assignment_status": (
                ["ID", "Module", "Assignment", "Due", "Submitted", "Marked", "Released"],
                f"SELECT a.id, a.module_code, a.title, SUBSTR(a.due_date, 1, 16), COUNT(s.id), COUNT(s.grade), "
                f"       CASE WHEN a.grades_released_at IS NOT NULL THEN 'yes' ELSE 'no' END "
                f"FROM assignments a LEFT JOIN assignment_submissions s ON s.assignment_id = a.id AND {final} "
                f"WHERE COALESCE(a.is_active, 1) = 1{mod} GROUP BY a.id ORDER BY a.due_date"),
            "late_submissions": (
                ["Student", "Module", "Assignment", "Submitted", "Days late"],
                f"SELECT s.student_id, a.module_code, a.title, SUBSTR(s.submission_date, 1, 16), s.late_days "
                f"FROM assignment_submissions s JOIN assignments a ON a.id = s.assignment_id "
                f"WHERE s.late_submission = 1 AND {final}{mod} ORDER BY s.late_days DESC"),
            "at_risk": (
                ["Student", "Name", "Marked", "Average %", "Non-submissions"],
                f"SELECT st.student_id, TRIM(COALESCE(st.first_name, '') || ' ' || COALESCE(st.last_name, '')), "
                f"       (SELECT COUNT(*) FROM assignment_submissions s JOIN assignments a ON a.id = s.assignment_id "
                f"         WHERE s.student_id = st.student_id AND s.grade IS NOT NULL AND {final}{mod}), "
                f"       (SELECT AVG(s.grade) FROM assignment_submissions s JOIN assignments a ON a.id = s.assignment_id "
                f"         WHERE s.student_id = st.student_id AND s.grade IS NOT NULL AND {final}{mod}) AS avg_mark, "
                f"       (SELECT COUNT(*) FROM assignment_non_submissions n JOIN assignments a ON a.id = n.assignment_id "
                f"         WHERE n.student_id = st.student_id AND n.voided = 0{mod}) AS ns "
                f"FROM students st WHERE avg_mark < 40 OR ns > 0 ORDER BY ns DESC, avg_mark"),
        }
        headers, sql = queries[key]
        if key == "at_risk":
            params = params * 3
        conn = sqlite3.connect(self.db_path)
        try:
            return headers, conn.execute(sql, params).fetchall()  # nosec B608 - fixed SQL fragments
        except sqlite3.Error as e:
            print(f"Error building report: {e}")
            return headers, []
        finally:
            conn.close()
