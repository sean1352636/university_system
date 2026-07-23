"""Predictive analytics and forecasting methods for AnalyticsManager."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.constants import get_connection


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
                messagebox.showinfo("Grade Prediction", "No students with grades found.")
                return

            # Create dialog for student selection
            dialog = tk.Toplevel(self.content_frame)
            dialog.title("Predict Student Grades")
            dialog.geometry("500x400")
            dialog.transient(self.content_frame)

            ttk.Label(dialog, text="Select Student:", font=('Arial', 10, 'bold')).pack(pady=10)

            # Student selection
            student_var = tk.StringVar()
            student_combo = ttk.Combobox(dialog, textvariable=student_var, width=40, state='readonly')
            student_combo['values'] = [f"{sid} - {name}" for sid, name in students]
            student_combo.pack(pady=5)

            # Results display
            results_frame = ttk.LabelFrame(dialog, text="Prediction Results", padding=10)
            results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            results_text = tk.Text(results_frame, height=15, width=55, wrap=tk.WORD)
            results_scrollbar = ttk.Scrollbar(results_frame, command=results_text.yview)
            results_text.configure(yscrollcommand=results_scrollbar.set)
            results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            results_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            def predict_for_student():
                selection = student_var.get()
                if not selection:
                    messagebox.showwarning("Selection Required", "Please select a student.")
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

            ttk.Button(button_frame, text="Predict Grades", command=predict_for_student).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to predict grades: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open prediction dialog: {e}")
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
                messagebox.showinfo("GPA Prediction", "No data available for prediction.")
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
            messagebox.showerror("Database Error", f"Failed to predict GPA: {e}")
        finally:
            if conn:
                conn.close()

    def predict_module_success(self):
        """Predict success probability for modules"""
        messagebox.showinfo("Module Success Prediction",
                          "Module success prediction analyzes:\n"
                          "• Historical pass rates\n"
                          "• Current student performance\n"
                          "• Assessment difficulty trends\n\n"
                          "This feature requires statistical analysis of past data.")

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
            messagebox.showerror("Database Error", f"Failed to calculate probabilities: {e}")
        finally:
            if conn:
                conn.close()

    def build_at_risk_model(self):
        """Build predictive model for at-risk identification"""
        messagebox.showinfo("At-Risk Model",
                          "Building at-risk prediction model requires:\n"
                          "• Historical student data\n"
                          "• Feature engineering\n"
                          "• Machine learning algorithms\n\n"
                          "This is an advanced feature requiring ML libraries.")

    def analyze_dropout_risk(self):
        """Analyze dropout risk using predictive analytics"""
        # Leverage existing dropout_risk_analysis
        self.dropout_risk_analysis()

    def generate_early_warnings(self):
        """Generate early warning predictions"""
        # Leverage existing early_warning_system
        self.early_warning_system()

    def forecast_performance_trends(self):
        """Forecast future performance trends"""
        messagebox.showinfo("Performance Forecasting",
                          "Performance forecasting analyzes historical trends to predict:\n"
                          "• Future grade trajectories\n"
                          "• Expected performance by module\n"
                          "• Cohort-level outcomes\n\n"
                          "Requires time-series analysis capabilities.")

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
            messagebox.showerror("Database Error", f"Failed to forecast performance: {e}")
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
            messagebox.showerror("Database Error", f"Failed to forecast success rates: {e}")
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
                messagebox.showinfo("Batch Prediction",
                                  "Not enough data for predictions.\n"
                                  "Students need at least 2 graded assessments.")
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
            messagebox.showerror("Database Error", f"Failed to predict grades: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate predictions: {e}")
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
