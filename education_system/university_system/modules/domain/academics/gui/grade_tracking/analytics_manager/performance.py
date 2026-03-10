"""Performance analysis methods for AnalyticsManager."""

import tkinter as tk
from tkinter import messagebox

from education_system.university_system.infrastructure.database.db import sqlite3
from .constants import get_connection


class PerformanceMixin:
    """Mixin providing performance analysis methods."""

    # ============================================================================
    # PERFORMANCE ANALYSIS METHODS (5 methods)
    # ============================================================================

    def show_grade_distribution(self):
        """Display grade distribution across all assessments"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Query both grades table and assignment_submissions table
            cursor.execute("""
                SELECT letter_grade, COUNT(*) AS count
                FROM (
                    -- Traditional assessments from grades table
                    SELECT letter_grade
                    FROM grades
                    WHERE letter_grade IS NOT NULL

                    UNION ALL

                    -- Assignment submissions from assignment_submissions table
                    SELECT
                        CASE
                            WHEN grade >= 93 THEN 'A+'
                            WHEN grade >= 90 THEN 'A'
                            WHEN grade >= 87 THEN 'A-'
                            WHEN grade >= 83 THEN 'B+'
                            WHEN grade >= 80 THEN 'B'
                            WHEN grade >= 77 THEN 'B-'
                            WHEN grade >= 73 THEN 'C+'
                            WHEN grade >= 70 THEN 'C'
                            WHEN grade >= 67 THEN 'C-'
                            WHEN grade >= 63 THEN 'D+'
                            WHEN grade >= 60 THEN 'D'
                            WHEN grade >= 57 THEN 'D-'
                            ELSE 'F'
                        END AS letter_grade
                    FROM assignment_submissions
                    WHERE grade IS NOT NULL
                ) AS combined_grades
                GROUP BY letter_grade
                ORDER BY
                    CASE letter_grade
                        WHEN 'A+' THEN 1 WHEN 'A' THEN 2 WHEN 'A-' THEN 3
                        WHEN 'B+' THEN 4 WHEN 'B' THEN 5 WHEN 'B-' THEN 6
                        WHEN 'C+' THEN 7 WHEN 'C' THEN 8 WHEN 'C-' THEN 9
                        WHEN 'D+' THEN 10 WHEN 'D' THEN 11 WHEN 'D-' THEN 12
                        WHEN 'F' THEN 13 ELSE 14
                    END
            """)

            distribution = cursor.fetchall()
            total_grades = sum(count for _, count in distribution)

            if total_grades == 0:
                messagebox.showinfo("Grade Distribution", "No grades recorded yet.")
                return

            dist_lines = [
                f"{grade}: {count} ({count/total_grades*100:.1f}%)"
                for grade, count in distribution
            ]

            sections = [
                ("Grade Distribution Summary", [
                    f"Total Grades: {total_grades}",
                    ""
                ]),
                ("Distribution by Letter Grade", dist_lines)
            ]

            self._display_report("Grade Distribution Analysis", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to show grade distribution: {e}")
        finally:
            if conn:
                conn.close()

    def analyze_module_performance(self):
        """Analyze performance across all modules"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Query both grades and assignment_submissions tables
            cursor.execute("""
                SELECT
                    module_code,
                    module_name,
                    COUNT(DISTINCT student_id) AS student_count,
                    COUNT(*) AS total_grades,
                    AVG(percentage) AS avg_percentage,
                    SUM(CASE WHEN letter_grade IN ('A+', 'A', 'A-') THEN 1 ELSE 0 END) AS excellent_count,
                    SUM(CASE WHEN letter_grade IN ('F', 'D', 'D-') THEN 1 ELSE 0 END) AS poor_count
                FROM (
                    -- Traditional assessments from grades table
                    SELECT
                        m.module_code,
                        m.module_name,
                        g.student_id,
                        (g.score / a.max_points * 100) AS percentage,
                        g.letter_grade
                    FROM modules m
                    JOIN assessments a ON m.module_code = a.module_code
                    JOIN grades g ON a.assessment_id = g.assessment_id

                    UNION ALL

                    -- Assignment submissions from assignment_submissions table
                    SELECT
                        m.module_code,
                        m.module_name,
                        sub.student_id,
                        sub.grade AS percentage,
                        CASE
                            WHEN sub.grade >= 93 THEN 'A+'
                            WHEN sub.grade >= 90 THEN 'A'
                            WHEN sub.grade >= 87 THEN 'A-'
                            WHEN sub.grade >= 83 THEN 'B+'
                            WHEN sub.grade >= 80 THEN 'B'
                            WHEN sub.grade >= 77 THEN 'B-'
                            WHEN sub.grade >= 73 THEN 'C+'
                            WHEN sub.grade >= 70 THEN 'C'
                            WHEN sub.grade >= 67 THEN 'C-'
                            WHEN sub.grade >= 63 THEN 'D+'
                            WHEN sub.grade >= 60 THEN 'D'
                            WHEN sub.grade >= 57 THEN 'D-'
                            ELSE 'F'
                        END AS letter_grade
                    FROM modules m
                    JOIN assignments asn ON m.module_code = asn.module_code
                    JOIN assignment_submissions sub ON asn.id = sub.assignment_id
                    WHERE sub.grade IS NOT NULL
                ) AS combined_data
                GROUP BY module_code, module_name
                HAVING COUNT(*) > 0
                ORDER BY avg_percentage DESC
            """)

            modules = cursor.fetchall()

            if not modules:
                messagebox.showinfo("Module Performance", "No module data available.")
                return

            module_lines = [
                f"{code} - {name}\n"
                f"  Students: {students} | Grades: {grades} | Avg: {avg:.1f}%\n"
                f"  Excellent (A): {excellent} | Poor (D/F): {poor}"
                for code, name, students, grades, avg, excellent, poor in modules
            ]

            sections = [
                ("Module Performance Overview", [
                    f"Total Modules Analyzed: {len(modules)}",
                    f"Average Module Performance: {sum(m[4] for m in modules)/len(modules):.1f}%"
                ]),
                ("Module Details", module_lines)
            ]

            self._display_report("Module Performance Analysis", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to analyze module performance: {e}")
        finally:
            if conn:
                conn.close()

    def compare_course_performance(self):
        """Compare performance across different courses"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Query both grades and assignment_submissions tables
            cursor.execute("""
                SELECT
                    s.course,
                    COUNT(DISTINCT cg.student_id) AS student_count,
                    AVG(cg.percentage) AS avg_percentage,
                    MIN(cg.percentage) AS min_percentage,
                    MAX(cg.percentage) AS max_percentage
                FROM students s
                JOIN (
                    -- Traditional assessments
                    SELECT g.student_id, (g.score / a.max_points * 100) AS percentage
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id

                    UNION ALL

                    -- Assignment submissions
                    SELECT sub.student_id, sub.grade AS percentage
                    FROM assignment_submissions sub
                    WHERE sub.grade IS NOT NULL
                ) AS cg ON s.student_id = cg.student_id
                WHERE s.course IS NOT NULL
                GROUP BY s.course
                ORDER BY avg_percentage DESC
            """)

            courses = cursor.fetchall()

            if not courses:
                messagebox.showinfo("Course Comparison", "No course data available.")
                return

            course_lines = [
                f"{course}: {students} students | Avg: {avg:.1f}% | Range: {min_val:.1f}% - {max_val:.1f}%"
                for course, students, avg, min_val, max_val in courses
            ]

            sections = [
                ("Course Performance Comparison", course_lines)
            ]

            self._display_report("Course Performance Comparison", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to compare course performance: {e}")
        finally:
            if conn:
                conn.close()

    def analyze_performance_trends(self):
        """Analyze performance trends over time"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Query both grades and assignment_submissions tables
            cursor.execute("""
                SELECT
                    date(submission_date) AS submission_month,
                    AVG(percentage) AS avg_percentage,
                    COUNT(*) AS grade_count
                FROM (
                    -- Traditional assessments
                    SELECT g.submission_date, (g.score / a.max_points * 100) AS percentage
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    WHERE g.submission_date IS NOT NULL

                    UNION ALL

                    -- Assignment submissions
                    SELECT sub.graded_date AS submission_date, sub.grade AS percentage
                    FROM assignment_submissions sub
                    WHERE sub.grade IS NOT NULL AND sub.graded_date IS NOT NULL
                ) AS combined_grades
                GROUP BY date(submission_date)
                ORDER BY submission_month
            """)

            trends = cursor.fetchall()

            if not trends:
                messagebox.showinfo("Performance Trends", "Insufficient data for trend analysis.")
                return

            trend_lines = [
                f"{month}: {avg:.1f}% average ({count} grades)"
                for month, avg, count in trends
            ]

            sections = [
                ("Performance Trends Over Time", trend_lines)
            ]

            self._display_report("Performance Trend Analysis", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to analyze trends: {e}")
        finally:
            if conn:
                conn.close()

    def generate_performance_dashboard(self):
        """Generate comprehensive performance dashboard"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Total students
            cursor.execute("SELECT COUNT(*) FROM students")
            total_students = cursor.fetchone()[0]

            # Total modules with grades
            cursor.execute("""
                SELECT COUNT(DISTINCT module_code)
                FROM (
                    SELECT m.module_code
                    FROM modules m
                    WHERE EXISTS (
                        SELECT 1 FROM grades g
                        JOIN assessments a ON g.assessment_id = a.assessment_id
                        WHERE a.module_code = m.module_code
                    ) OR EXISTS (
                        SELECT 1 FROM assignment_submissions sub
                        JOIN assignments asn ON sub.assignment_id = asn.id
                        WHERE asn.module_code = m.module_code AND sub.grade IS NOT NULL
                    )
                )
            """)
            total_modules = cursor.fetchone()[0]

            # Total assessments
            cursor.execute("""
                SELECT
                    (SELECT COUNT(*) FROM assessments) +
                    (SELECT COUNT(*) FROM assignments)
            """)
            total_assessments = cursor.fetchone()[0]

            # Total grades and average from both sources
            cursor.execute("""
                SELECT COUNT(*), AVG(percentage)
                FROM (
                    SELECT (g.score / a.max_points * 100) AS percentage
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id

                    UNION ALL

                    SELECT sub.grade AS percentage
                    FROM assignment_submissions sub
                    WHERE sub.grade IS NOT NULL
                ) AS combined_grades
            """)
            total_grades, overall_avg = cursor.fetchone()

            # Grade distribution from both sources
            cursor.execute("""
                SELECT letter_grade, COUNT(*) AS count
                FROM (
                    SELECT letter_grade FROM grades WHERE letter_grade IS NOT NULL
                    UNION ALL
                    SELECT
                        CASE
                            WHEN grade >= 93 THEN 'A+'
                            WHEN grade >= 90 THEN 'A'
                            WHEN grade >= 87 THEN 'A-'
                            WHEN grade >= 83 THEN 'B+'
                            WHEN grade >= 80 THEN 'B'
                            WHEN grade >= 77 THEN 'B-'
                            WHEN grade >= 73 THEN 'C+'
                            WHEN grade >= 70 THEN 'C'
                            WHEN grade >= 67 THEN 'C-'
                            WHEN grade >= 63 THEN 'D+'
                            WHEN grade >= 60 THEN 'D'
                            WHEN grade >= 57 THEN 'D-'
                            ELSE 'F'
                        END
                    FROM assignment_submissions WHERE grade IS NOT NULL
                ) AS combined_grades
                GROUP BY letter_grade
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """)
            top_grades = cursor.fetchall()

            sections = [
                ("System Overview", [
                    f"Total Students: {total_students or 0}",
                    f"Total Modules: {total_modules or 0}",
                    f"Total Assessments: {total_assessments or 0}",
                    f"Total Grades Recorded: {total_grades or 0}",
                    f"Overall Average: {overall_avg:.1f}%" if overall_avg else "Overall Average: N/A"
                ]),
                ("Top Grade Distribution", [
                    f"{grade}: {count} occurrences"
                    for grade, count in top_grades
                ] if top_grades else ["No data available."])
            ]

            self._display_report("Performance Dashboard", sections)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate dashboard: {e}")
        finally:
            if conn:
                conn.close()
