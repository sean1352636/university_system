"""Risk assessment and early warning methods for AnalyticsManager."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.constants import get_connection
from education_system.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.utils import safe_grab_set


def _open_connection():
    raw_conn = get_connection()
    enter = getattr(raw_conn, "__enter__", None)
    if callable(enter):
        try:
            conn = enter()
            if conn is not None:
                return raw_conn, conn
        except Exception:
            pass
    return raw_conn, raw_conn


class RiskMixin:
    """Mixin providing risk assessment methods."""

    @staticmethod
    def _pad_row(row, size, defaults=None):
        values = list(row)
        if defaults is None:
            defaults = [0] * size
        values.extend(defaults[len(values):size])
        return values[:size]

    @staticmethod
    def _num(value, default=0):
        return value if isinstance(value, (int, float)) else default

    def identify_at_risk_students(self):
        """Identify students at risk based on grades and performance.

        Delegates risk scoring to
        ``grading.predictive_analytics.calculate_dropout_risk_score``
        (which factors in GPA, failed modules, submission rate and
        declining-performance trend) so the canonical formula is used
        everywhere instead of this view's earlier ad-hoc thresholds.
        """
        from education_system.university_system.modules.domain.academics.grading.predictive_analytics import (
            calculate_dropout_risk_score,
            calculate_risk_factors,
        )
        from education_system.university_system.modules.domain.academics.gui.grade_tracking.integrations import (
            flag_at_risk_student,
            fetch_overall_attendance,
        )

        conn = None
        try:
            raw_conn, conn = _open_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT student_id, first_name || ' ' || last_name AS name FROM students"
            )
            students = cursor.fetchall()
            at_risk_students = []

            for student_id, name in students:
                try:
                    risk_score = calculate_dropout_risk_score(cursor, student_id)
                except Exception:
                    continue
                if risk_score < 30:
                    continue
                risk_level = "High" if risk_score >= 60 else "Medium"
                try:
                    factors = calculate_risk_factors(cursor, student_id) or {}
                except Exception:
                    factors = {}
                # Add an attendance column from services.attendance so the
                # view shows grades + absence patterns side-by-side.
                attendance = fetch_overall_attendance(student_id)
                if attendance:
                    factors["attendance_pct"] = attendance["percentage"]
                factors_summary = ", ".join(
                    f"{k}: {v}" for k, v in factors.items() if v not in (None, 0, "")
                )
                at_risk_students.append(
                    (student_id, name, risk_score, risk_level, factors_summary)
                )

                # Auto-flag the student in the early-warning subsystem so
                # student_affairs picks it up; idempotent on the open
                # 'grade_risk' indicator per student.
                try:
                    flag_at_risk_student(
                        student_id=student_id,
                        risk_score=int(risk_score),
                        risk_level=risk_level,
                        factors_summary=factors_summary,
                    )
                except Exception:
                    pass

            if not at_risk_students:
                messagebox.showinfo("At-Risk Students", "No students currently identified as at-risk.")
                return

            # Display results window
            results_window = tk.Toplevel(self.root)
            results_window.title("At-Risk Students")
            results_window.geometry("900x600")
            safe_grab_set(results_window)

            ttk.Label(results_window, text="At-Risk Student Identification",
                     font=('Arial', 16, 'bold')).pack(pady=10)

            # Summary
            high_risk = sum(1 for s in at_risk_students if s[3] == "High")
            medium_risk = sum(1 for s in at_risk_students if s[3] == "Medium")
            summary = f"Total At-Risk: {len(at_risk_students)} | High Risk: {high_risk} | Medium Risk: {medium_risk}"
            ttk.Label(results_window, text=summary, font=('Arial', 11)).pack(pady=5)

            # Results frame
            results_frame = ttk.Frame(results_window)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            # Treeview
            columns = ('Student ID', 'Name', 'Risk Score', 'Risk Level', 'Risk Factors')
            tree = ttk.Treeview(results_frame, columns=columns, show='headings')

            for col in columns:
                tree.heading(col, text=col)

            tree.column('Student ID', width=100)
            tree.column('Name', width=150)
            tree.column('Risk Score', width=100)
            tree.column('Risk Level', width=100)
            tree.column('Risk Factors', width=400)

            scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Sort by risk score (highest first)
            at_risk_students.sort(key=lambda x: x[2], reverse=True)

            for student_id, name, risk_score, risk_level, risk_factors in at_risk_students:
                tree.insert('', 'end', values=(student_id, name, risk_score, risk_level, risk_factors))

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to identify at-risk students: {e}")
        finally:
            if conn:
                if raw_conn is not conn and hasattr(raw_conn, "__exit__"):
                    raw_conn.__exit__(None, None, None)
                else:
                    conn.close()

    def student_risk_assessment(self):
        """Perform detailed risk assessment for a selected student"""
        # Get student selection dialog
        conn = None
        try:
            raw_conn, conn = _open_connection()
            cursor = conn.cursor()

            # Get all students
            cursor.execute("SELECT student_id, first_name || ' ' || last_name FROM students ORDER BY last_name")
            students = cursor.fetchall()

            if not students:
                messagebox.showinfo("No Students", "No students found in database.")
                return

            # Selection dialog
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Student for Risk Assessment")
            dialog.geometry("400x500")
            safe_grab_set(dialog)

            ttk.Label(dialog, text="Select a student:", font=('Arial', 12, 'bold')).pack(pady=10)

            # Listbox with scrollbar
            list_frame = ttk.Frame(dialog)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)

            for student_id, name in students:
                listbox.insert(tk.END, f"{student_id} - {name}")

            def assess_student():
                selection = listbox.curselection()
                if not selection:
                    messagebox.showwarning("No Selection", "Please select a student.")
                    return

                student_id = students[selection[0]][0]
                dialog.destroy()
                self._perform_detailed_risk_assessment(student_id)

            ttk.Button(dialog, text="Assess", command=assess_student).pack(pady=10)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load students: {e}")
        finally:
            if conn:
                if raw_conn is not conn and hasattr(raw_conn, "__exit__"):
                    raw_conn.__exit__(None, None, None)
                else:
                    conn.close()

    def _perform_detailed_risk_assessment(self, student_id):
        """Helper method to perform detailed risk assessment"""
        conn = None
        try:
            raw_conn, conn = _open_connection()
            cursor = conn.cursor()

            # Get student info
            cursor.execute("SELECT first_name || ' ' || last_name FROM students WHERE student_id = ?", (student_id,))
            student_name = cursor.fetchone()[0]

            # Get grade statistics from both sources
            cursor.execute("""
                SELECT
                    COUNT(*) AS total_grades,
                    AVG(percentage) AS avg_percentage,
                    MIN(percentage) AS min_percentage,
                    MAX(percentage) AS max_percentage,
                    SUM(CASE WHEN letter_grade IN ('F', 'D-', 'D') THEN 1 ELSE 0 END) AS poor_grades,
                    SUM(CASE WHEN letter_grade IN ('A+', 'A', 'A-') THEN 1 ELSE 0 END) AS excellent_grades
                FROM (
                    -- Traditional assessments from grades table
                    SELECT
                        (g.score / a.max_points * 100) AS percentage,
                        g.letter_grade
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    WHERE g.student_id = ?

                    UNION ALL

                    -- Assignment submissions from assignment_submissions table
                    SELECT
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
                    FROM assignment_submissions sub
                    WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                ) AS combined_grades
            """, (student_id, student_id))

            stats = cursor.fetchone()
            total_grades, avg_pct, min_pct, max_pct, poor_grades, excellent_grades = stats

            # Calculate risk factors
            risk_factors = []
            risk_score = 0

            if avg_pct:
                if avg_pct < 50:
                    risk_score += 50
                    risk_factors.append(("Academic Performance", f"Very low average: {avg_pct:.1f}%", "Critical"))
                elif avg_pct < 60:
                    risk_score += 35
                    risk_factors.append(("Academic Performance", f"Low average: {avg_pct:.1f}%", "High"))
                elif avg_pct < 70:
                    risk_score += 20
                    risk_factors.append(("Academic Performance", f"Below average: {avg_pct:.1f}%", "Medium"))

            if poor_grades and poor_grades >= 3:
                risk_score += 30
                risk_factors.append(("Failing Grades", f"{poor_grades} poor grades", "High"))
            elif poor_grades and poor_grades >= 1:
                risk_score += 15
                risk_factors.append(("Failing Grades", f"{poor_grades} poor grade(s)", "Medium"))

            if total_grades < 3:
                risk_score += 10
                risk_factors.append(("Engagement", "Very few submissions", "Low"))

            # Determine overall risk level
            if risk_score >= 60:
                overall_risk = "CRITICAL"
            elif risk_score >= 40:
                overall_risk = "HIGH"
            elif risk_score >= 20:
                overall_risk = "MEDIUM"
            else:
                overall_risk = "LOW"

            # Display report
            sections = [
                ("Student Information", [
                    f"Student ID: {student_id}",
                    f"Student Name: {student_name}",
                    f"Overall Risk Level: {overall_risk}",
                    f"Risk Score: {risk_score}/100"
                ]),
                ("Academic Statistics", [
                    f"Total Assessments Completed: {total_grades or 0}",
                    f"Average Score: {avg_pct:.1f}%" if avg_pct else "Average Score: N/A",
                    f"Lowest Score: {min_pct:.1f}%" if min_pct else "Lowest Score: N/A",
                    f"Highest Score: {max_pct:.1f}%" if max_pct else "Highest Score: N/A",
                    f"Excellent Grades (A): {excellent_grades or 0}",
                    f"Poor Grades (D/F): {poor_grades or 0}"
                ]),
                ("Risk Factors", [f"• {category}: {description} (Severity: {severity})"
                                  for category, description, severity in risk_factors]
                 if risk_factors else ["No significant risk factors identified"]),
                ("Recommendations", self._generate_recommendations(risk_score, risk_factors))
            ]

            self._display_report(f"Risk Assessment Report - {student_name}", sections,
                               "This assessment is based on current academic performance data.")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to perform risk assessment: {e}")
        finally:
            if conn:
                conn.close()

    def _generate_recommendations(self, risk_score, risk_factors):
        """Generate intervention recommendations based on risk factors"""
        recommendations = []

        if risk_score >= 60:
            recommendations.append("• URGENT: Schedule immediate intervention meeting")
            recommendations.append("• Assign academic mentor or tutor")
            recommendations.append("• Review learning support services availability")

        if any("Academic Performance" in str(factor) for factor in risk_factors):
            recommendations.append("• Provide additional tutoring in weak subject areas")
            recommendations.append("• Review study habits and time management skills")

        if any("Failing Grades" in str(factor) for factor in risk_factors):
            recommendations.append("• Arrange one-on-one sessions with instructors")
            recommendations.append("• Consider grade improvement opportunities")

        if any("Engagement" in str(factor) for factor in risk_factors):
            recommendations.append("• Investigate attendance and participation issues")
            recommendations.append("• Reach out to discuss personal challenges")

        if not recommendations:
            recommendations.append("• Continue monitoring academic progress")
            recommendations.append("• Encourage participation in enrichment activities")

        return recommendations

    def dropout_risk_analysis(self):
        """Analyze students at risk of dropping out"""
        conn = None
        try:
            raw_conn, conn = _open_connection()
            cursor = conn.cursor()

            # Query both grades and assignment_submissions tables
            cursor.execute("""
                SELECT
                    student_id,
                    name,
                    course,
                    COUNT(*) AS total_submissions,
                    AVG(percentage) AS avg_percentage,
                    SUM(CASE WHEN letter_grade = 'F' THEN 1 ELSE 0 END) AS failures,
                    MAX(submission_date) AS last_submission
                FROM (
                    SELECT
                        s.student_id,
                        s.first_name || ' ' || s.last_name AS name,
                        s.course,
                        (g.score / a.max_points * 100) AS percentage,
                        g.letter_grade,
                        g.submission_date
                    FROM students s
                    JOIN grades g ON s.student_id = g.student_id
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    WHERE s.status = 'Active'

                    UNION ALL

                    SELECT
                        s.student_id,
                        s.first_name || ' ' || s.last_name AS name,
                        s.course,
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
                        END AS letter_grade,
                        sub.graded_date AS submission_date
                    FROM students s
                    JOIN assignment_submissions sub ON s.student_id = sub.student_id
                    WHERE s.status = 'Active' AND sub.grade IS NOT NULL
                ) AS combined_data
                GROUP BY student_id, name, course
            """)

            students = cursor.fetchall()
            dropout_risks = []

            for student_id, name, course, submissions, avg_pct, failures, last_sub in (
                self._pad_row(row, 7, ["", "", "", 0, 0.0, 0, ""]) for row in students
            ):
                submissions = self._num(submissions, 0)
                avg_pct = self._num(avg_pct, 0.0)
                failures = self._num(failures, 0)
                dropout_score = 0
                reasons = []

                # Low submission count indicates disengagement
                if submissions == 0:
                    dropout_score += 50
                    reasons.append("No submissions recorded")
                elif submissions < 3:
                    dropout_score += 30
                    reasons.append("Very low engagement")

                # Poor academic performance
                if avg_pct and avg_pct < 40:
                    dropout_score += 40
                    reasons.append(f"Critically low average: {avg_pct:.1f}%")
                elif avg_pct and avg_pct < 50:
                    dropout_score += 25
                    reasons.append(f"Very low average: {avg_pct:.1f}%")

                # Multiple failures
                if failures and failures >= 3:
                    dropout_score += 30
                    reasons.append(f"{failures} failed assessments")

                # Lack of recent activity
                if last_sub:
                    try:
                        last_date = datetime.strptime(last_sub, '%Y-%m-%d')
                        days_inactive = (datetime.now() - last_date).days
                        if days_inactive > 30:
                            dropout_score += 20
                            reasons.append(f"{days_inactive} days since last submission")
                    except (ValueError, TypeError):
                        pass

                if dropout_score >= 40:  # Threshold for dropout risk
                    risk_level = "Critical" if dropout_score >= 70 else "High" if dropout_score >= 50 else "Moderate"
                    dropout_risks.append((student_id, name, course, dropout_score, risk_level, "; ".join(reasons)))

            # Display results
            if not dropout_risks:
                messagebox.showinfo("Dropout Risk Analysis", "No students identified at significant dropout risk.")
                return

            # Sort by dropout score
            dropout_risks.sort(key=lambda x: x[3], reverse=True)

            sections = [
                ("Summary", [
                    f"Total Students at Dropout Risk: {len(dropout_risks)}",
                    f"Critical Risk: {sum(1 for r in dropout_risks if r[4] == 'Critical')}",
                    f"High Risk: {sum(1 for r in dropout_risks if r[4] == 'High')}",
                    f"Moderate Risk: {sum(1 for r in dropout_risks if r[4] == 'Moderate')}"
                ]),
                ("At-Risk Students", [
                    f"{idx+1}. {name} ({student_id}) - {course}\n"
                    f"   Risk Level: {risk_level} (Score: {score})\n"
                    f"   Reasons: {reasons}"
                    for idx, (student_id, name, course, score, risk_level, reasons) in enumerate(dropout_risks)
                ])
            ]

            self._display_report("Dropout Risk Analysis", sections,
                               "Immediate intervention recommended for critical and high-risk students.")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to analyze dropout risk: {e}")
        finally:
            if conn:
                if raw_conn is not conn and hasattr(raw_conn, "__exit__"):
                    raw_conn.__exit__(None, None, None)
                else:
                    conn.close()

    def intervention_recommendations(self):
        """Generate intervention recommendations for at-risk students"""
        conn = None
        try:
            raw_conn, conn = _open_connection()
            cursor = conn.cursor()

            # Get at-risk students
            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    AVG(g.score / a.max_points * 100) AS avg_percentage,
                    SUM(CASE WHEN g.letter_grade IN ('F', 'D') THEN 1 ELSE 0 END) AS poor_grades,
                    COUNT(g.grade_id) AS total_grades
                FROM students s
                JOIN grades g ON s.student_id = g.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                GROUP BY s.student_id, s.first_name, s.last_name
                HAVING AVG(g.score / a.max_points * 100) < 70 OR
                       SUM(CASE WHEN g.letter_grade IN ('F', 'D') THEN 1 ELSE 0 END) >= 2
            """)

            at_risk = cursor.fetchall()

            if not at_risk:
                messagebox.showinfo("Interventions", "No students currently require intervention.")
                return

            interventions = []
            for student_id, name, avg_pct, poor_grades, total_grades in (
                self._pad_row(row, 5, ["", "", 0.0, 0, 0]) for row in at_risk
            ):
                avg_pct = self._num(avg_pct, 0.0)
                poor_grades = self._num(poor_grades, 0)
                total_grades = self._num(total_grades, 0)
                student_interventions = []

                # Academic interventions
                if avg_pct and avg_pct < 50:
                    student_interventions.append("URGENT: One-on-one tutoring (minimum 3 sessions/week)")
                    student_interventions.append("Academic probation review")
                elif avg_pct and avg_pct < 60:
                    student_interventions.append("Regular tutoring sessions (2x/week)")
                    student_interventions.append("Study skills workshop")
                elif avg_pct and avg_pct < 70:
                    student_interventions.append("Peer tutoring or study group")
                    student_interventions.append("Office hours attendance")

                # Based on failing grades
                if poor_grades >= 3:
                    student_interventions.append("Academic advisor meeting (urgent)")
                    student_interventions.append("Course load review and adjustment")
                elif poor_grades >= 2:
                    student_interventions.append("Instructor consultations for failing subjects")

                # Engagement interventions
                if total_grades < 5:
                    student_interventions.append("Attendance monitoring")
                    student_interventions.append("Wellness check-in")

                # General support
                student_interventions.append("Learning resource center orientation")
                student_interventions.append("Time management counseling")

                interventions.append((student_id, name, avg_pct or 0, poor_grades, student_interventions))

            # Display report
            sections = [
                ("Overview", [
                    f"Students Requiring Intervention: {len(interventions)}",
                    f"Critical Cases (avg < 50%): {sum(1 for i in interventions if i[2] < 50)}",
                    f"High Priority (avg < 60%): {sum(1 for i in interventions if 50 <= i[2] < 60)}"
                ]),
                ("Recommended Interventions", [
                    f"\n{name} ({student_id})\n"
                    f"Current Average: {avg:.1f}% | Failing Grades: {poor}\n"
                    f"Recommended Actions:\n" + "\n".join(f"  • {action}" for action in actions)
                    for student_id, name, avg, poor, actions in interventions
                ])
            ]

            self._display_report("Intervention Recommendations", sections,
                               "Follow up with students within 48 hours of critical interventions.")

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to generate interventions: {e}")
        finally:
            if conn:
                if raw_conn is not conn and hasattr(raw_conn, "__exit__"):
                    raw_conn.__exit__(None, None, None)
                else:
                    conn.close()

    def early_warning_system(self):
        """Generate early warning alerts for students showing concerning patterns"""
        conn = None
        try:
            raw_conn, conn = _open_connection()
            cursor = conn.cursor()

            warnings = []

            # Check for sudden grade drops
            cursor.execute("""
                SELECT DISTINCT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    g.score / a.max_points * 100 AS percentage,
                    g.submission_date,
                    a.assessment_name
                FROM students s
                JOIN grades g ON s.student_id = g.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                WHERE g.score / a.max_points * 100 < 60
                ORDER BY s.student_id, g.submission_date DESC
            """)

            for student_id, name, percentage, date, assessment in (
                self._pad_row(row, 5, ["", "", 0.0, "", ""]) for row in cursor.fetchall()
            ):
                percentage = self._num(percentage, 0.0)
                warnings.append((student_id, name, "Low Score Alert",
                               f"{assessment}: {percentage:.1f}%", "High"))

            # Check for missing submissions (students with very few grades)
            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    COUNT(g.grade_id) AS submission_count
                FROM students s
                LEFT JOIN grades g ON s.student_id = g.student_id
                WHERE s.status = 'Active'
                GROUP BY s.student_id, s.first_name, s.last_name
                HAVING COUNT(g.grade_id) < 3
            """)

            for student_id, name, count in (
                self._pad_row(row, 3, ["", "", 0]) for row in cursor.fetchall()
            ):
                count = self._num(count, 0)
                warnings.append((student_id, name, "Low Engagement",
                               f"Only {count} submission(s) recorded", "Medium"))

            if not warnings:
                messagebox.showinfo("Early Warning System", "No current warnings to display.")
                return

            # Display warnings window
            warning_window = tk.Toplevel(self.root)
            warning_window.title("Early Warning Alerts")
            warning_window.geometry("900x600")
            safe_grab_set(warning_window)

            ttk.Label(warning_window, text="Early Warning Alerts",
                     font=('Arial', 16, 'bold')).pack(pady=10)

            # Summary
            high_count = sum(1 for w in warnings if w[4] == "High")
            medium_count = sum(1 for w in warnings if w[4] == "Medium")

            summary_text = f"Total Warnings: {len(warnings)} | High Priority: {high_count} | Medium Priority: {medium_count}"
            ttk.Label(warning_window, text=summary_text, font=('Arial', 11)).pack(pady=5)

            # Results frame
            results_frame = ttk.Frame(warning_window)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            # Results treeview
            columns = ('Priority', 'Student ID', 'Name', 'Warning Type', 'Details')
            tree = ttk.Treeview(results_frame, columns=columns, show='headings')

            for col in columns:
                tree.heading(col, text=col)

            tree.column('Priority', width=80)
            tree.column('Student ID', width=100)
            tree.column('Name', width=150)
            tree.column('Warning Type', width=150)
            tree.column('Details', width=250)

            scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Sort by priority (High first)
            warnings.sort(key=lambda x: (0 if x[4] == "High" else 1, x[1]))

            for student_id, name, warning_type, details, priority in warnings:
                tree.insert('', 'end', values=(priority, student_id, name, warning_type, details))

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to generate early warnings: {e}")
        finally:
            if conn:
                if raw_conn is not conn and hasattr(raw_conn, "__exit__"):
                    raw_conn.__exit__(None, None, None)
                else:
                    conn.close()
