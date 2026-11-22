"""Predictive analytics and forecasting methods for AnalyticsManager."""

import logging

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import messagebox
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking._dialogs import make_toplevel

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.domains.assessment.interfaces.gui.grade_tracking.analytics_manager.constants import get_connection

logger = logging.getLogger(__name__)


class PredictionsMixin:
    """Mixin providing prediction and forecasting methods."""

    def predict_grades_dialog(self):
        """Predict future grades for a specific student based on current performance"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get list of students
            cursor.execute("""
                SELECT DISTINCT s.student_id, s.first_name || ' ' || s.last_name AS name
                FROM students s
                JOIN grades g ON s.student_id = g.student_id
                ORDER BY s.last_name, s.first_name
            """)
            students = cursor.fetchall()

            if not students:
                messagebox.showinfo(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.grade_prediction', default="Grade Prediction"), _t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.no_students_with_grades_found', default="No students with grades found."))
                return

            # Create dialog for student selection
            dialog = make_toplevel(self.content_frame)
            dialog.title(_t('gui.academics.grade_tracking.analytics_manager.predictions.windows.predict_student_grades', default="Predict Student Grades"))
            dialog.geometry("500x400")
            dialog.transient(self.content_frame)

            ttk.Label(dialog, text=_t('gui.academics.grade_tracking.analytics_manager.predictions.labels.select_student', default="Select Student:"), font=('Arial', 10, 'bold')).pack(pady=10)

            # Student selection
            student_var = tk.StringVar()
            student_combo = ttk.Combobox(dialog, textvariable=student_var, width=40, state='readonly')
            student_combo['values'] = [f"{sid} - {name}" for sid, name in students]
            student_combo.pack(pady=5)

            # Results display
            results_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.grade_tracking.analytics_manager.predictions.labels.prediction_results', default="Prediction Results"), padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            results_text = tk.Text(results_frame, height=15, width=55, wrap=tk.WORD)
            results_scrollbar = ttk.Scrollbar(results_frame, command=results_text.yview)
            results_text.configure(yscrollcommand=results_scrollbar.set)
            results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            def predict_for_student():
                selection = student_var.get()
                if not selection:
                    messagebox.showwarning(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.selection_required', default="Selection Required"), _t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.please_select_a_student', default="Please select a student."))
                    return

                student_id = selection.split(' - ')[0]

                # Get student's performance data
                cursor.execute("""
                    SELECT
                        a.module_code,
                        m.module_name,
                        AVG(g.score / a.max_points * 100) AS avg_score,
                        COUNT(g.grade_id) AS assessment_count
                    FROM grades g
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    JOIN modules m ON a.module_code = m.module_code
                    WHERE g.student_id = ? AND a.max_points > 0
                    GROUP BY a.module_code, m.module_name
                """, (student_id,))
                modules = cursor.fetchall()

                if not modules:
                    results_text.delete('1.0', tk.END)
                    results_text.insert('1.0', "No graded assessments found for this student.")
                    return

                # Build prediction report
                report_lines = [f"Grade Predictions for: {selection}", "=" * 50, ""]

                module_predictions = []
                for module_code, module_name, avg_score, count in modules:
                    # Predict final grade
                    predicted_final = avg_score  # Base prediction

                    # Adjust based on trend if enough data
                    if count >= 3:
                        cursor.execute("""
                            SELECT g.score / a.max_points * 100
                            FROM grades g
                            JOIN assessments a ON g.assessment_id = a.assessment_id
                            WHERE g.student_id = ? AND a.module_code = ? AND a.max_points > 0
                            ORDER BY g.grade_id DESC
                            LIMIT 3
                        """, (student_id, module_code))
                        recent = [row[0] for row in cursor.fetchall()]

                        if len(recent) >= 3:
                            recent_avg = sum(recent[:2]) / 2
                            if recent_avg > avg_score:
                                predicted_final += (recent_avg - avg_score) * 0.3  # Trending up
                            elif recent_avg < avg_score:
                                predicted_final += (recent_avg - avg_score) * 0.3  # Trending down

                    # Determine letter grade
                    if predicted_final >= 90:
                        letter = "A"
                    elif predicted_final >= 80:
                        letter = "B"
                    elif predicted_final >= 70:
                        letter = "C"
                    elif predicted_final >= 60:
                        letter = "D"
                    else:
                        letter = "F"

                    module_predictions.append((module_name, avg_score, predicted_final, letter, count))

                # Display predictions by module
                for module_name, current, predicted, letter, count in sorted(module_predictions, key=lambda x: x[2], reverse=True):
                    trend = "↑" if predicted > current else "↓" if predicted < current else "→"
                    report_lines.append(f"{module_name}:")
                    report_lines.append(f"  Current Average: {current:.1f}%")
                    report_lines.append(f"  Predicted Final: {predicted:.1f}% ({letter}) {trend}")
                    report_lines.append(f"  Based on {count} assessments")
                    report_lines.append("")

                # Overall prediction
                overall_avg = sum(p[2] for p in module_predictions) / len(module_predictions)
                if overall_avg >= 90:
                    overall_letter = "A"
                elif overall_avg >= 80:
                    overall_letter = "B"
                elif overall_avg >= 70:
                    overall_letter = "C"
                elif overall_avg >= 60:
                    overall_letter = "D"
                else:
                    overall_letter = "F"

                report_lines.extend([
                    "Overall Prediction:",
                    f"  Predicted GPA Equivalent: {overall_avg:.1f}% ({overall_letter})",
                    "",
                    "Note: Predictions are estimates based on current performance.",
                    "Actual results may vary based on future assessments."
                ])

                results_text.delete('1.0', tk.END)
                results_text.insert('1.0', '\n'.join(report_lines))

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.analytics_manager.predictions.buttons.predict_grades', default="Predict Grades"), command=predict_for_student).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_t('gui.academics.grade_tracking.analytics_manager.predictions.buttons.close', default="Close"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"), f"Failed to predict grades: {e}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.error', default="Error"), f"Failed to open prediction dialog: {e}")
        finally:
            if conn:
                conn.close()

    def predict_gpa_dialog(self):
        """Predict GPA based on current trajectory"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    AVG(CASE g.letter_grade
                        WHEN 'A+' THEN 4.3 WHEN 'A' THEN 4.0 WHEN 'A-' THEN 3.7
                        WHEN 'B+' THEN 3.3 WHEN 'B' THEN 3.0 WHEN 'B-' THEN 2.7
                        WHEN 'C+' THEN 2.3 WHEN 'C' THEN 2.0 WHEN 'C-' THEN 1.7
                        WHEN 'D+' THEN 1.3 WHEN 'D' THEN 1.0 WHEN 'D-' THEN 0.7
                        WHEN 'F' THEN 0.0 ELSE 0
                    END) AS current_gpa
                FROM students s
                JOIN grades g ON s.student_id = g.student_id
                GROUP BY s.student_id, s.first_name, s.last_name
                HAVING COUNT(g.grade_id) > 0
            """)

            predictions = cursor.fetchall()

            if not predictions:
                messagebox.showinfo(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.gpa_prediction', default="GPA Prediction"), _t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.no_data_available_for_prediction', default="No data available for prediction."))
                return

            prediction_lines = [
                f"{name} ({student_id}): Current GPA: {gpa:.2f} | Projected Final GPA: {gpa:.2f}"
                for student_id, name, gpa in predictions
            ]

            sections = [
                ("GPA Predictions", prediction_lines),
                ("Note", ["Predictions based on current performance trends.",
                         "Actual results may vary based on future performance."])
            ]

            self._display_report("GPA Predictions", sections)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"), f"Failed to predict GPA: {e}")
        finally:
            if conn:
                conn.close()

    def predict_module_success(self):
        """Pass rate per module, and how the current cohort is tracking.

        Was a placeholder describing what it would need. The inputs were
        already there: historical module_grades give the pass rate, and
        current assessment marks give each module's live average.
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Historical outcome per module
            cursor.execute("""
                SELECT mg.module_code,
                       COUNT(*) AS graded,
                       SUM(CASE WHEN mg.final_score >= 40 THEN 1 ELSE 0 END) AS passed,
                       AVG(mg.final_score) AS avg_score
                FROM module_grades mg
                WHERE mg.final_score IS NOT NULL
                GROUP BY mg.module_code
                ORDER BY mg.module_code
            """)
            history = {r[0]: r for r in cursor.fetchall()}

            # Live performance per module from assessment marks
            cursor.execute("""
                SELECT a.module_code,
                       COUNT(g.grade_id) AS marks,
                       AVG(g.score / NULLIF(a.max_points, 0) * 100) AS current_avg
                FROM assessments a
                JOIN grades g ON g.assessment_id = a.assessment_id
                WHERE a.module_code IS NOT NULL AND a.max_points > 0
                GROUP BY a.module_code
            """)
            current = {r[0]: r for r in cursor.fetchall()}

            rows = []
            for module_code in sorted(set(history) | set(current)):
                hist = history.get(module_code)
                live = current.get(module_code)
                if hist and hist[1]:
                    rate = hist[2] / hist[1] * 100.0
                    basis = f"{hist[1]} past result(s)"
                else:
                    rate = None
                    basis = "no history"
                live_avg = live[2] if live and live[2] is not None else None

                # Predicted rate leans on history, adjusted by how the
                # current cohort is performing against a 40% pass mark.
                if rate is not None and live_avg is not None:
                    predicted = max(0.0, min(100.0, (rate + min(100.0, live_avg * 1.25)) / 2))
                elif rate is not None:
                    predicted = rate
                elif live_avg is not None:
                    predicted = max(0.0, min(100.0, live_avg * 1.25))
                else:
                    continue

                rows.append(
                    f"{module_code}: Predicted pass rate: {predicted:.1f}% | "
                    f"Historical: {f'{rate:.1f}%' if rate is not None else 'n/a'} | "
                    f"Current average: {f'{live_avg:.1f}' if live_avg is not None else 'n/a'} | "
                    f"Basis: {basis}")

            sections = [
                ("Module Success Prediction",
                 rows or ["No module grades or assessment marks recorded yet."]),
                ("Method", [
                    "Pass mark taken as 40%.",
                    "Where a module has both, the prediction is the mean of its "
                    "historical pass rate and its current cohort average scaled to "
                    "the pass mark; otherwise whichever is available is used.",
                    "Modules with neither are omitted rather than shown as 0%.",
                ]),
            ]
            self._display_report("Module Success Prediction", sections)

        except sqlite3.Error as e:
            messagebox.showerror(
                _t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"),
                f"Failed to predict module success: {e}")
        finally:
            if conn:
                conn.close()

    def calculate_success_probability(self):
        """Calculate probability of passing based on current performance"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    AVG(g.score / a.max_points * 100) AS avg_percentage
                FROM students s
                JOIN grades g ON s.student_id = g.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                GROUP BY s.student_id, s.first_name, s.last_name
                HAVING COUNT(g.grade_id) >= 3
            """)

            students = cursor.fetchall()
            probability_lines = []

            for student_id, name, avg in students:
                # Simple probability model based on current average
                if avg >= 70:
                    probability = min(95, 50 + (avg - 70) * 1.5)
                    risk = "Low"
                elif avg >= 60:
                    probability = 50 + (avg - 60) * 2
                    risk = "Medium"
                else:
                    probability = max(10, avg * 0.8)
                    risk = "High"

                probability_lines.append(
                    f"{name} ({student_id}): {probability:.1f}% pass probability | Risk: {risk}"
                )

            sections = [
                ("Success Probability Analysis", probability_lines if probability_lines else
                 ["Insufficient data for probability calculation"])
            ]

            self._display_report("Success Probability Report", sections)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"), f"Failed to calculate probabilities: {e}")
        finally:
            if conn:
                conn.close()

    def build_at_risk_model(self):
        """Score every student against the risk factors already recorded.

        Was a placeholder saying this needed machine learning. It does
        not: the factors that matter are attendance, current average,
        failed assessments and unsubmitted work, all of which are in the
        database. A transparent weighted score is also easier to defend
        to a student than a model nobody can explain.
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT s.student_id,
                       s.first_name || ' ' || s.last_name AS name,
                       AVG(g.score / NULLIF(a.max_points, 0) * 100) AS avg_pct,
                       COUNT(g.grade_id) AS marks,
                       SUM(CASE WHEN g.score / NULLIF(a.max_points, 0) * 100 < 40
                                THEN 1 ELSE 0 END) AS fails
                FROM students s
                LEFT JOIN grades g ON g.student_id = s.student_id
                LEFT JOIN assessments a ON a.assessment_id = g.assessment_id
                WHERE COALESCE(s.is_active, 1) = 1
                GROUP BY s.student_id, name
            """)
            academic = cursor.fetchall()

            # Attendance, when the module keeps it
            attendance = {}
            try:
                cursor.execute("""
                    SELECT student_id,
                           SUM(CASE WHEN LOWER(status) IN ('present','late')
                                    THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS pct
                    FROM attendance_records GROUP BY student_id
                """)
                attendance = {r[0]: r[1] for r in cursor.fetchall()}
            except sqlite3.Error:
                logger.debug("attendance unavailable for risk model", exc_info=True)

            # Work set but never handed in
            missing = {}
            try:
                cursor.execute("""
                    SELECT student_id, COUNT(*) FROM assignment_submissions
                    WHERE grade IS NULL AND LOWER(COALESCE(status,'')) != 'graded'
                    GROUP BY student_id
                """)
                missing = {r[0]: r[1] for r in cursor.fetchall()}
            except sqlite3.Error:
                logger.debug("submissions unavailable for risk model", exc_info=True)

            scored = []
            for student_id, name, avg_pct, marks, fails in academic:
                factors, score = [], 0
                if not marks:
                    score += 30
                    factors.append("no marks recorded")
                else:
                    if avg_pct is not None and avg_pct < 40:
                        score += 40
                        factors.append(f"average {avg_pct:.0f}% below pass")
                    elif avg_pct is not None and avg_pct < 55:
                        score += 20
                        factors.append(f"average {avg_pct:.0f}% marginal")
                    if fails:
                        score += min(25, fails * 10)
                        factors.append(f"{fails} failed assessment(s)")

                present = attendance.get(student_id)
                if present is not None and present < 70:
                    score += 25 if present < 50 else 15
                    factors.append(f"attendance {present:.0f}%")

                unsubmitted = missing.get(student_id, 0)
                if unsubmitted:
                    score += min(20, unsubmitted * 5)
                    factors.append(f"{unsubmitted} unsubmitted")

                score = min(100, score)
                band = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
                scored.append((score, band, name, student_id, factors))

            scored.sort(reverse=True)
            at_risk = [s for s in scored if s[0] >= 30]

            rows = [
                f"{name} ({student_id}): Risk score: {score} | Band: {band} | "
                f"Factors: {'; '.join(factors) if factors else 'none'}"
                for score, band, name, student_id, factors in at_risk
            ]
            counts = {b: sum(1 for s in scored if s[1] == b)
                      for b in ("High", "Medium", "Low")}

            sections = [
                ("Summary", [
                    f"Students scored: {len(scored)}",
                    f"High risk: {counts['High']}",
                    f"Medium risk: {counts['Medium']}",
                    f"Low risk: {counts['Low']}",
                ]),
                ("Flagged Students (score 30+)",
                 rows or ["No students currently meet the risk threshold."]),
                ("Scoring", [
                    "Average below pass 40 · marginal average 20 · each failed "
                    "assessment 10 (max 25) · attendance under 50% 25, under 70% 15 · "
                    "each unsubmitted piece 5 (max 20) · no marks at all 30.",
                    "Capped at 100. High 60+, Medium 30-59, Low under 30.",
                ]),
            ]
            self._display_report("At-Risk Prediction Model", sections)

        except sqlite3.Error as e:
            messagebox.showerror(
                _t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"),
                f"Failed to build the at-risk model: {e}")
        finally:
            if conn:
                conn.close()

    def analyze_dropout_risk(self):
        """Analyze dropout risk using predictive analytics"""
        # Leverage existing dropout_risk_analysis
        self.dropout_risk_analysis()

    def generate_early_warnings(self):
        """Generate early warning predictions"""
        # Leverage existing early_warning_system
        self.early_warning_system()

    def forecast_performance_trends(self):
        """Project the next period from the trend in recorded results.

        Was a placeholder saying this needed time-series analysis. With
        a handful of periods, a least-squares line over the period
        averages is both sufficient and honest about its own confidence.
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT strftime('%Y-%m', COALESCE(completion_date, date_recorded)) AS period,
                       COUNT(*) AS results,
                       AVG(final_score) AS avg_score
                FROM module_grades
                WHERE final_score IS NOT NULL
                  AND COALESCE(completion_date, date_recorded) IS NOT NULL
                GROUP BY period ORDER BY period
            """)
            periods = [r for r in cursor.fetchall() if r[0]]

            history = [
                f"{p}: Results: {n} | Average: {avg:.1f}"
                for p, n, avg in periods
            ]

            if len(periods) < 2:
                sections = [
                    ("Recorded Periods", history or ["No dated results recorded yet."]),
                    ("Forecast", [
                        "At least two periods of results are needed before a trend "
                        "can be projected.",
                    ]),
                ]
                self._display_report("Performance Forecast", sections)
                return

            # Least-squares fit over period index -> average score
            xs = list(range(len(periods)))
            ys = [float(p[2]) for p in periods]
            n = len(xs)
            mean_x, mean_y = sum(xs) / n, sum(ys) / n
            denom = sum((x - mean_x) ** 2 for x in xs)
            slope = (sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
                     if denom else 0.0)
            intercept = mean_y - slope * mean_x

            # R^2, so the forecast can say how well the line fits
            ss_tot = sum((y - mean_y) ** 2 for y in ys)
            ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
            r_squared = (1 - ss_res / ss_tot) if ss_tot else 1.0

            forecasts = []
            for step in (1, 2, 3):
                projected = max(0.0, min(100.0, intercept + slope * (n - 1 + step)))
                forecasts.append(
                    f"Period +{step}: Projected average: {projected:.1f}")

            direction = ("improving" if slope > 0.5 else
                         "declining" if slope < -0.5 else "broadly flat")
            confidence = ("strong" if r_squared >= 0.7 else
                          "moderate" if r_squared >= 0.4 else "weak")

            sections = [
                ("Recorded Periods", history),
                ("Forecast", forecasts),
                ("Trend", [
                    f"Direction: {direction}",
                    f"Change per period: {slope:+.2f} marks",
                    f"Fit (R squared): {r_squared:.2f} — {confidence}",
                ]),
                ("Method", [
                    "Least-squares line through the average score of each period.",
                    "A weak fit means the periods vary too much for the projection "
                    "to be relied on; treat it as a direction, not a number.",
                ]),
            ]
            self._display_report("Performance Forecast", sections)

        except sqlite3.Error as e:
            messagebox.showerror(
                _t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"),
                f"Failed to forecast performance: {e}")
        finally:
            if conn:
                conn.close()

    def forecast_course_performance(self):
        """Forecast overall course performance"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    course,
                    AVG(g.score / a.max_points * 100) AS current_avg,
                    COUNT(DISTINCT s.student_id) AS student_count
                FROM students s
                JOIN grades g ON s.student_id = g.student_id
                JOIN assessments a ON g.assessment_id = a.assessment_id
                WHERE course IS NOT NULL
                GROUP BY course
            """)

            courses = cursor.fetchall()

            forecast_lines = [
                f"{course}: Current Avg: {avg:.1f}% | Forecast: {avg:.1f}% | Students: {count}"
                for course, avg, count in courses
            ]

            sections = [
                ("Course Performance Forecast", forecast_lines if forecast_lines else ["No data available"])
            ]

            self._display_report("Course Performance Forecast", sections)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"), f"Failed to forecast performance: {e}")
        finally:
            if conn:
                conn.close()

    def forecast_success_rates(self):
        """Forecast overall success rates"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    COUNT(DISTINCT student_id) AS total_students,
                    SUM(CASE WHEN avg_grade >= 60 THEN 1 ELSE 0 END) AS passing_students
                FROM (
                    SELECT s.student_id, AVG(g.score / a.max_points * 100) AS avg_grade
                    FROM students s
                    JOIN grades g ON s.student_id = g.student_id
                    JOIN assessments a ON g.assessment_id = a.assessment_id
                    GROUP BY s.student_id
                )
            """)

            total, passing = cursor.fetchone()
            success_rate = (passing / total * 100) if total > 0 else 0

            sections = [
                ("Success Rate Forecast", [
                    f"Total Students: {total}",
                    f"Projected Passing Students: {passing}",
                    f"Projected Success Rate: {success_rate:.1f}%"
                ])
            ]

            self._display_report("Success Rate Forecast", sections)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"), f"Failed to forecast success rates: {e}")
        finally:
            if conn:
                conn.close()

    def batch_predict_grades(self):
        """Batch predict grades for multiple students based on current performance"""
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get all students with their current performance
            cursor.execute("""
                SELECT
                    s.student_id,
                    s.first_name || ' ' || s.last_name AS name,
                    s.course,
                    COUNT(g.grade_id) AS assessment_count,
                    AVG(g.score / a.max_points * 100) AS current_avg,
                    MIN(g.score / a.max_points * 100) AS min_score,
                    MAX(g.score / a.max_points * 100) AS max_score
                FROM students s
                LEFT JOIN grades g ON s.student_id = g.student_id
                LEFT JOIN assessments a ON g.assessment_id = a.assessment_id
                WHERE a.max_points > 0
                GROUP BY s.student_id, s.first_name, s.last_name, s.course
                HAVING COUNT(g.grade_id) >= 2
                ORDER BY s.last_name, s.first_name
            """)

            students = cursor.fetchall()

            if not students:
                messagebox.showinfo(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.batch_prediction', default="Batch Prediction"),
                                  _t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.not_enough_data_for_predictions_students_need_at_least_2_graded', default="Not enough data for predictions.\n"
                                  "Students need at least 2 graded assessments."))
                return

            predictions = []
            for student_id, name, course, count, avg, min_score, max_score in students:
                # Simple prediction model based on current performance
                # Predict final grade based on weighted average with trend analysis
                trend = "stable"
                predicted_final = avg

                # Calculate trend if there are enough grades
                if count >= 3:
                    # Get recent grades trend
                    cursor.execute("""
                        SELECT g.score / a.max_points * 100
                        FROM grades g
                        JOIN assessments a ON g.assessment_id = a.assessment_id
                        WHERE g.student_id = ? AND a.max_points > 0
                        ORDER BY g.grade_id DESC
                        LIMIT 3
                    """, (student_id,))
                    recent = [row[0] for row in cursor.fetchall()]

                    if len(recent) >= 3:
                        # Simple trend: compare recent vs earlier
                        recent_avg = sum(recent[:2]) / 2
                        if recent_avg > avg + 5:
                            trend = "improving"
                            predicted_final = avg + (recent_avg - avg) * 0.5
                        elif recent_avg < avg - 5:
                            trend = "declining"
                            predicted_final = avg + (recent_avg - avg) * 0.5

                # Determine predicted letter grade
                if predicted_final >= 90:
                    predicted_grade = "A"
                elif predicted_final >= 80:
                    predicted_grade = "B"
                elif predicted_final >= 70:
                    predicted_grade = "C"
                elif predicted_final >= 60:
                    predicted_grade = "D"
                else:
                    predicted_grade = "F"

                predictions.append({
                    'name': name,
                    'course': course,
                    'current_avg': avg,
                    'predicted_final': predicted_final,
                    'predicted_grade': predicted_grade,
                    'trend': trend,
                    'assessment_count': count
                })

            # Format predictions for display
            prediction_lines = []
            for idx, pred in enumerate(predictions, 1):
                trend_symbol = "↑" if pred['trend'] == 'improving' else "↓" if pred['trend'] == 'declining' else "→"
                line = (f"{idx}. {pred['name']} ({pred['course']}) | "
                       f"Current: {pred['current_avg']:.1f}% | "
                       f"Predicted Final: {pred['predicted_final']:.1f}% ({pred['predicted_grade']}) {trend_symbol} | "
                       f"Assessments: {pred['assessment_count']}")
                prediction_lines.append(line)

            # Group by predicted grade
            grade_groups = {}
            for pred in predictions:
                grade = pred['predicted_grade']
                if grade not in grade_groups:
                    grade_groups[grade] = 0
                grade_groups[grade] += 1

            summary_lines = [
                f"Total Students Analyzed: {len(predictions)}",
                "",
                "Predicted Grade Distribution:",
            ]
            for grade in ['A', 'B', 'C', 'D', 'F']:
                count = grade_groups.get(grade, 0)
                summary_lines.append(f"  {grade}: {count} students ({count/len(predictions)*100:.1f}%)")

            improving = sum(1 for p in predictions if p['trend'] == 'improving')
            declining = sum(1 for p in predictions if p['trend'] == 'declining')
            summary_lines.extend([
                "",
                f"Trending Up (↑): {improving} students",
                f"Trending Down (↓): {declining} students",
                f"Stable (→): {len(predictions) - improving - declining} students"
            ])

            sections = [
                ("Prediction Summary", summary_lines),
                ("Individual Predictions", prediction_lines)
            ]

            footer = ("Note: Predictions are based on current performance trends and historical data. "
                     "Actual results may vary based on future performance and assessment difficulty.")

            self._display_report("Batch Grade Predictions", sections, footer)

        except sqlite3.Error as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.database_error', default="Database Error"), f"Failed to predict grades: {e}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.grade_tracking.analytics_manager.predictions.dialogs.error', default="Error"), f"Failed to generate predictions: {e}")
        finally:
            if conn:
                conn.close()

    def batch_risk_assessment(self):
        """Perform batch risk assessment"""
        # Leverage existing identify_at_risk_students
        self.identify_at_risk_students()

    def generate_interventions(self):
        """Generate intervention strategies"""
        # Leverage existing intervention_recommendations
        self.intervention_recommendations()
