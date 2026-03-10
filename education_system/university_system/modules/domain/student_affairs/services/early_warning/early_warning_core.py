"""
Student Success Early Warning System Core Service

This module provides at-risk student identification, automated interventions,
success coaching, progress monitoring, and tutoring recommendations.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher
from education_system.university_system.modules.shared.utils.i18n import (
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False
    def send_email(*args, **kwargs):
        print(_t("early_warning.messages.email_not_available", default="Email would be sent (email service not available)"))
    def render_template(template_name, vars):
        return f"Template: {template_name}", "Email body would be here"


class RiskAssessmentManager:
    """Manages risk assessment and student profiles"""

    @staticmethod
    def calculate_risk_score(student_id: str) -> Tuple[int, str]:
        """
        Calculate overall risk score for a student

        Returns:
            Tuple of (risk_score, risk_level)
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Calculate academic risk (40% weight)
            academic_risk = RiskAssessmentManager._calculate_academic_risk(student_id)

            # Calculate attendance risk (30% weight)
            attendance_risk = RiskAssessmentManager._calculate_attendance_risk(student_id)

            # Calculate engagement risk (20% weight)
            engagement_risk = RiskAssessmentManager._calculate_engagement_risk(student_id)

            # Calculate financial risk (10% weight)
            financial_risk = RiskAssessmentManager._calculate_financial_risk(student_id)

            # Calculate weighted overall risk
            overall_risk = (
                academic_risk * 0.4 +
                attendance_risk * 0.3 +
                engagement_risk * 0.2 +
                financial_risk * 0.1
            )

            # Determine risk level
            if overall_risk >= 70:
                risk_level = 'critical'
            elif overall_risk >= 50:
                risk_level = 'high'
            elif overall_risk >= 30:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            # Update or create risk profile
            cursor.execute('''
                INSERT OR REPLACE INTO early_warning_profiles (
                    student_id, overall_risk_score, risk_level,
                    academic_risk_score, attendance_risk_score,
                    engagement_risk_score, financial_risk_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, int(overall_risk), risk_level, int(academic_risk),
                  int(attendance_risk), int(engagement_risk), int(financial_risk)))

            conn.commit()

            return int(overall_risk), risk_level

        finally:
            conn.close()

    @staticmethod
    def _calculate_academic_risk(student_id: str) -> int:
        """Calculate academic risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get average grades
            cursor.execute('''
                SELECT AVG(CAST(score as REAL) / CAST(max_score as REAL) * 100) as avg_grade
                FROM lms_gradebook
                WHERE student_id = ?
                AND graded_at >= date('now', '-3 months')
            ''', (student_id,))

            result = cursor.fetchone()
            avg_grade = result['avg_grade'] if result and result['avg_grade'] else 70

            # Convert grade to risk (lower grade = higher risk)
            if avg_grade >= 70:
                return 0
            elif avg_grade >= 60:
                return 30
            elif avg_grade >= 50:
                return 60
            else:
                return 90

        finally:
            conn.close()

    @staticmethod
    def _calculate_attendance_risk(student_id: str) -> int:
        """Calculate attendance risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT AVG(attendance_percentage) as avg_attendance,
                       MAX(consecutive_absences) as max_consecutive
                FROM attendance_analytics
                WHERE student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()

            if not result or not result['avg_attendance']:
                return 0  # No data, assume no risk

            avg_attendance = result['avg_attendance']
            max_consecutive = result['max_consecutive'] or 0

            # Calculate risk based on attendance
            attendance_risk = 0

            if avg_attendance >= 90:
                attendance_risk = 0
            elif avg_attendance >= 75:
                attendance_risk = 20
            elif avg_attendance >= 60:
                attendance_risk = 50
            else:
                attendance_risk = 80

            # Add risk for consecutive absences
            if max_consecutive >= 5:
                attendance_risk += 20
            elif max_consecutive >= 3:
                attendance_risk += 10

            return min(attendance_risk, 100)

        finally:
            conn.close()

    @staticmethod
    def _calculate_engagement_risk(student_id: str) -> int:
        """Calculate engagement risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Check LMS engagement
            cursor.execute('''
                SELECT COUNT(*) as video_views
                FROM lms_video_lectures
                WHERE video_id IN (
                    SELECT DISTINCT content_id FROM lms_course_content
                    WHERE lms_course_id IN (
                        SELECT lms_course_id FROM lms_courses WHERE module_code IN (
                            SELECT module_code FROM student_modules WHERE student_id = ?
                        )
                    )
                )
            ''', (student_id,))

            # Simple heuristic: if student has viewed videos recently, lower risk
            # In real system, would track actual student views, discussion participation, etc.

            return 30  # Placeholder

        finally:
            conn.close()

    @staticmethod
    def _calculate_financial_risk(student_id: str) -> int:
        """Calculate financial risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Check for outstanding fees
            cursor.execute('''
                SELECT COUNT(*) as unpaid_count
                FROM student_fees
                WHERE student_id = ? AND status = 'unpaid'
            ''', (student_id,))

            result = cursor.fetchone()
            unpaid_count = result['unpaid_count'] if result else 0

            if unpaid_count == 0:
                return 0
            elif unpaid_count <= 2:
                return 30
            else:
                return 70

        finally:
            conn.close()

    @staticmethod
    def get_at_risk_students(risk_level: str = "high") -> List[Dict[str, Any]]:
        """Get list of at-risk students"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            if risk_level == "high":
                condition = "p.risk_level IN ('high', 'critical')"
            elif risk_level == "critical":
                condition = "p.risk_level = 'critical'"
            elif risk_level == "medium":
                condition = "p.risk_level IN ('medium', 'high', 'critical')"
            elif risk_level == "low":
                condition = "p.risk_level = 'low'"
            elif risk_level == "all":
                # Show ALL students with LEFT JOIN to include those without profiles
                cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name, s.email_address, s.course,
                           COALESCE(p.overall_risk_score, 0) as overall_risk_score,
                           COALESCE(p.risk_level, 'not assessed') as risk_level,
                           COALESCE(p.academic_risk_score, 0) as academic_risk_score,
                           COALESCE(p.attendance_risk_score, 0) as attendance_risk_score,
                           COALESCE(p.engagement_risk_score, 0) as engagement_risk_score,
                           COALESCE(p.financial_risk_score, 0) as financial_risk_score
                    FROM students s
                    LEFT JOIN early_warning_profiles p ON s.student_id = p.student_id
                    ORDER BY p.overall_risk_score DESC NULLS LAST, s.last_name, s.first_name
                ''')
                return [dict(row) for row in cursor.fetchall()]
            else:
                condition = "1=1"

            cursor.execute('''
                SELECT p.*, s.first_name, s.last_name, s.email_address, s.course
                FROM early_warning_profiles p
                JOIN students s ON p.student_id = s.student_id
                WHERE ''' + condition + '''
                ORDER BY p.overall_risk_score DESC
            ''')

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()


class IndicatorManager:
    """Manages risk indicators and flags"""

    @staticmethod
    def add_indicator(
        student_id: str,
        indicator_type: str,
        indicator_value: str,
        severity: str,
        notes: str = ""
    ) -> int:
        """Add a risk indicator for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_indicators (
                    student_id, indicator_type, indicator_value, severity, notes
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, indicator_type, indicator_value, severity, notes))

            indicator_id = cursor.lastrowid
            conn.commit()

            # Trigger intervention if high severity
            if severity in ['high', 'critical']:
                InterventionManager.create_intervention(
                    student_id,
                    indicator_type,
                    f"auto_{indicator_type}",
                    severity,
                    f"Automated intervention triggered by {indicator_type} indicator"
                )

            return indicator_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding indicator: {e}")
        finally:
            conn.close()

    @staticmethod
    def resolve_indicator(indicator_id: int, notes: str = "") -> bool:
        """Mark an indicator as resolved"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE early_warning_indicators
                SET is_resolved = 1, resolved_at = ?, notes = ?
                WHERE indicator_id = ?
            ''', (datetime.now().isoformat(), notes, indicator_id))

            conn.commit()
            return True

        finally:
            conn.close()

    @staticmethod
    def get_active_indicators(student_id: str) -> List[Dict[str, Any]]:
        """Get active indicators for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM early_warning_indicators
                WHERE student_id = ? AND is_resolved = 0
                ORDER BY detected_at DESC
            ''', (student_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()


class InterventionManager:
    """Manages interventions and actions"""

    @staticmethod
    def create_intervention(
        student_id: str,
        trigger_type: str,
        intervention_type: str,
        priority: str,
        description: str,
        assigned_to: str = "",
        scheduled_date: str = ""
    ) -> int:
        """Create a new intervention"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_interventions (
                    student_id, trigger_type, intervention_type, priority,
                    description, assigned_to, scheduled_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, trigger_type, intervention_type, priority,
                  description, assigned_to, scheduled_date))

            intervention_id = cursor.lastrowid
            conn.commit()

            # Send notification
            InterventionManager._notify_intervention(intervention_id)

            return intervention_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating intervention: {e}")
        finally:
            conn.close()

    @staticmethod
    def _notify_intervention(intervention_id: int) -> None:
        """Send notification about new intervention"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT i.*, s.first_name, s.last_name, s.email_address
                FROM early_warning_interventions i
                JOIN students s ON i.student_id = s.student_id
                WHERE i.intervention_id = ?
            ''', (intervention_id,))

            intervention = cursor.fetchone()
            if not intervention:
                return

            # Notify assigned staff
            if intervention['assigned_to']:
                subject, body = render_template('intervention_assigned', {
                    'first_name': intervention['first_name'],
                    'last_name': intervention['last_name'],
                    'priority': intervention['priority'],
                    'intervention_type': intervention['intervention_type'],
                    'description': intervention['description'],
                    'scheduled_date': intervention['scheduled_date'] if intervention['scheduled_date'] else 'Not scheduled'
                })

                # In real system, send to assigned staff email
                print(f"Intervention notification: {subject}")

        finally:
            conn.close()

    @staticmethod
    def complete_intervention(intervention_id: int, outcome: str, notes: str = "") -> bool:
        """Mark an intervention as completed"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE early_warning_interventions
                SET status = 'completed', completed_date = ?, outcome = ?, notes = ?, updated_at = ?
                WHERE intervention_id = ?
            ''', (date.today().isoformat(), outcome, notes, datetime.now().isoformat(), intervention_id))

            conn.commit()
            return True

        finally:
            conn.close()

    @staticmethod
    def get_pending_interventions(assigned_to: str = "") -> List[Dict[str, Any]]:
        """Get pending interventions"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            query = '''
                SELECT i.*, s.first_name, s.last_name
                FROM early_warning_interventions i
                JOIN students s ON i.student_id = s.student_id
                WHERE i.status = 'pending'
            '''
            params = []

            if assigned_to:
                query += ' AND i.assigned_to = ?'
                params.append(assigned_to)

            query += ' ORDER BY i.priority DESC, i.created_at'

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()


class CoachingManager:
    """Manages success coaches and student assignments"""

    @staticmethod
    def register_coach(
        user_id: str,
        name: str,
        specialization: str = "",
        max_students: int = 30
    ) -> int:
        """Register a success coach"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_coaches (
                    user_id, name, specialization, max_students
                )
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, specialization, max_students))

            coach_id = cursor.lastrowid
            conn.commit()

            return coach_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error registering coach: {e}")
        finally:
            conn.close()

    @staticmethod
    def assign_student_to_coach(
        student_id: str,
        coach_id: int,
        reason: str,
        meeting_frequency: str = "weekly"
    ) -> int:
        """Assign a student to a success coach"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Check coach capacity
            cursor.execute('''
                SELECT COUNT(*) as current_students, max_students
                FROM early_warning_coaching_assignments ca
                JOIN early_warning_coaches c ON ca.coach_id = c.coach_id
                WHERE ca.coach_id = ? AND ca.status = 'active'
                GROUP BY c.coach_id, c.max_students
            ''', (coach_id,))

            capacity = cursor.fetchone()
            if capacity and capacity['current_students'] >= capacity['max_students']:
                raise Exception("Coach has reached maximum student capacity")

            cursor.execute('''
                INSERT INTO early_warning_coaching_assignments (
                    student_id, coach_id, reason, meeting_frequency
                )
                VALUES (?, ?, ?, ?)
            ''', (student_id, coach_id, reason, meeting_frequency))

            assignment_id = cursor.lastrowid
            conn.commit()

            # Send notification
            CoachingManager._notify_assignment(assignment_id)

            return assignment_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error assigning student to coach: {e}")
        finally:
            conn.close()

    @staticmethod
    def _notify_assignment(assignment_id: int) -> None:
        """Notify student and coach of assignment"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT ca.*, s.first_name, s.last_name, s.email_address, c.name as coach_name
                FROM early_warning_coaching_assignments ca
                JOIN students s ON ca.student_id = s.student_id
                JOIN early_warning_coaches c ON ca.coach_id = c.coach_id
                WHERE ca.assignment_id = ?
            ''', (assignment_id,))

            assignment = cursor.fetchone()
            if not assignment:
                return

            # Notify student using template
            subject, body = render_template('success_coach_assigned', {
                'first_name': assignment['first_name'],
                'coach_name': assignment['coach_name'],
                'meeting_frequency': assignment['meeting_frequency']
            })

            send_email(assignment['email_address'], subject, body)

        finally:
            conn.close()

    @staticmethod
    def record_progress(
        student_id: str,
        coach_id: int,
        academic_progress: str,
        attendance_progress: str,
        engagement_progress: str,
        goals_achieved: str,
        concerns: str,
        next_steps: str
    ) -> int:
        """Record progress monitoring"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_progress_monitoring (
                    student_id, coach_id, academic_progress, attendance_progress,
                    engagement_progress, goals_achieved, concerns, next_steps
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, coach_id, academic_progress, attendance_progress,
                  engagement_progress, goals_achieved, concerns, next_steps))

            monitoring_id = cursor.lastrowid

            # Update assignment with last meeting date
            cursor.execute('''
                UPDATE early_warning_coaching_assignments
                SET last_meeting_date = ?
                WHERE student_id = ? AND coach_id = ? AND status = 'active'
            ''', (date.today().isoformat(), student_id, coach_id))

            conn.commit()

            return monitoring_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error recording progress: {e}")
        finally:
            conn.close()


class TutoringManager:
    """Manages tutoring recommendations"""

    @staticmethod
    def create_tutoring_recommendation(
        student_id: str,
        module_code: str,
        recommended_by: str,
        recommendation_type: str,
        priority: str = "medium"
    ) -> int:
        """Create a tutoring recommendation"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO early_warning_tutoring_recommendations (
                    student_id, module_code, recommended_by, recommendation_type, priority
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, module_code, recommended_by, recommendation_type, priority))

            recommendation_id = cursor.lastrowid
            conn.commit()

            # Notify student
            TutoringManager._notify_recommendation(recommendation_id)

            return recommendation_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating tutoring recommendation: {e}")
        finally:
            conn.close()

    @staticmethod
    def _notify_recommendation(recommendation_id: int) -> None:
        """Notify student of tutoring recommendation"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT tr.*, s.first_name, s.email_address
                FROM early_warning_tutoring_recommendations tr
                JOIN students s ON tr.student_id = s.student_id
                WHERE tr.recommendation_id = ?
            ''', (recommendation_id,))

            rec = cursor.fetchone()
            if not rec:
                return

            subject, body = render_template('tutoring_recommended', {
                'first_name': rec['first_name'],
                'module_code': rec['module_code'],
                'recommendation_type': rec['recommendation_type'],
                'priority': rec['priority']
            })

            send_email(rec['email_address'], subject, body)

        finally:
            conn.close()

    @staticmethod
    def assign_tutor(recommendation_id: int, tutor_assigned: str) -> bool:
        """Assign a tutor to a recommendation"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE early_warning_tutoring_recommendations
                SET tutor_assigned = ?, status = 'assigned'
                WHERE recommendation_id = ?
            ''', (tutor_assigned, recommendation_id))

            conn.commit()
            return True

        finally:
            conn.close()


def display_early_warning_menu(auth):
    """Display the Student Success Early Warning System CLI menu"""
    print("\n" + "="*50)
    print(f" {_t('early_warning.cli.title', default='STUDENT SUCCESS EARLY WARNING SYSTEM')}")
    print("="*50)
    print(f"1. {_t('early_warning.cli.menu.at_risk', default='View At-Risk Students')}")
    print(f"2. {_t('early_warning.cli.menu.dashboard', default='Risk Assessment Dashboard')}")
    print(f"3. {_t('early_warning.cli.menu.intervention', default='Create Intervention Plan')}")
    print(f"4. {_t('early_warning.cli.menu.coach', default='Assign Success Coach')}")
    print(f"5. {_t('early_warning.cli.menu.progress', default='Track Student Progress')}")
    print(f"6. {_t('early_warning.cli.menu.tutoring', default='Tutoring Recommendations')}")
    print(f"7. {_t('early_warning.cli.menu.alerts', default='Send Alert Notifications')}")
    print(f"8. {_t('early_warning.cli.menu.language', default='Language')}")
    print(f"9. {_t('early_warning.cli.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{_t('early_warning.cli.prompt.choice', default='Enter your choice (1-9)')}: ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n{_t('early_warning.cli.feature_available', default='Feature available via Early Warning managers')}")
                print("Use: from education_system.university_system.modules.domain.student_affairs.services.early_warning import RiskAssessmentManager")
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
                print(_t('early_warning.cli.returning', default='Returning to main menu...'))
                break
            else:
                print(_t('early_warning.cli.invalid_choice', default='Invalid choice.'))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(_t('early_warning.cli.error', default='Error: {error}').format(error=e))


def launch_early_warning_gui(root, auth):
    """Launch the Student Success Early Warning System GUI"""
    import tkinter as tk
    from tkinter import ttk, messagebox, simpledialog
    from education_system.university_system.infrastructure.database.schemas.attendance_warning_schemas import init_early_warning_system_db

    # Import internationalization (i18n) for multi-language support
    try:
        from education_system.university_system.modules.shared.utils.i18n import (
            get_text as _t,
            get_current_language,
        )
    except ImportError:
        _t = lambda key, **kwargs: kwargs.get("default", key)
        get_current_language = lambda: "en"

    # Check authentication
    if not auth or not hasattr(auth, 'current_user') or not auth.current_user:
        messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.login_required", default="You must be logged in to access the Early Warning System."))
        return

    # Initialize database tables
    try:
        init_early_warning_system_db()
    except Exception as e:
        messagebox.showerror(_t("common.database_error", default="Database Error"), _t("early_warning.errors.db_init_failed", default="Failed to initialize database: {error}").format(error=e))
        return

    class EarlyWarningGUI:
        def __init__(self, parent, auth_instance):
            self.root = tk.Toplevel(parent)
            self.root.title(_t("early_warning.window_title", default="Student Success Early Warning System"))
            self.root.geometry("1200x800")
            self.auth = auth_instance
            self.current_user = auth_instance.current_user

            self.create_widgets()
            self.load_at_risk_students()

        def create_widgets(self):
            """Create the main GUI layout"""
            # Initialize status_var FIRST - before any tabs are created
            self.status_var = tk.StringVar(value=_t("common.ready", default="Ready"))

            # Header
            header_frame = ttk.Frame(self.root)
            header_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Label(header_frame, text=_t("early_warning.title", default="Student Success Early Warning System"),
                     font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

            ttk.Button(header_frame, text=_t("common.return_to_main_menu", default="Return to Homescreen"),
                      command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)
            ttk.Button(header_frame, text=_t("common.refresh", default="Refresh"),
                      command=self.load_at_risk_students).pack(side=tk.RIGHT, padx=5)
            ttk.Button(header_frame, text=_t("early_warning.calculate_all_risk_scores", default="Calculate All Risk Scores"),
                      command=self.calculate_all_risks).pack(side=tk.RIGHT, padx=5)

            # Create notebook for tabs
            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            # Tab 1: At-Risk Students
            self.create_at_risk_tab()

            # Tab 2: Interventions
            self.create_interventions_tab()

            # Tab 3: Coaching
            self.create_coaching_tab()

            # Tab 4: Tutoring
            self.create_tutoring_tab()

            # Tab 5: Risk Indicators
            self.create_indicators_tab()

            # Status bar (status_var already initialized at the top of this method)
            status_bar = ttk.Label(self.root, textvariable=self.status_var,
                                  relief=tk.SUNKEN, anchor=tk.W)
            status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        def create_at_risk_tab(self):
            """Create the at-risk students tab"""
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=_t("early_warning.tabs.at_risk_students", default="At-Risk Students"))

            # Filter frame
            filter_frame = ttk.LabelFrame(tab, text=_t("common.filters", default="Filters"), padding=10)
            filter_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Label(filter_frame, text=_t("early_warning.risk_level", default="Risk Level:")).pack(side=tk.LEFT, padx=5)
            self.risk_filter = ttk.Combobox(filter_frame,
                                           values=["All", "Critical", "High", "Medium", "Low"],
                                           state="readonly", width=15)
            self.risk_filter.set("High")
            self.risk_filter.pack(side=tk.LEFT, padx=5)
            self.risk_filter.bind('<<ComboboxSelected>>', lambda e: self.load_at_risk_students())

            # Students list
            list_frame = ttk.Frame(tab)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            columns = ("student_id", "name", "risk_score", "risk_level",
                      "academic", "attendance", "engagement", "financial")
            self.students_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

            self.students_tree.heading("student_id", text="Student ID")
            self.students_tree.heading("name", text="Name")
            self.students_tree.heading("risk_score", text="Risk Score")
            self.students_tree.heading("risk_level", text="Risk Level")
            self.students_tree.heading("academic", text="Academic")
            self.students_tree.heading("attendance", text="Attendance")
            self.students_tree.heading("engagement", text="Engagement")
            self.students_tree.heading("financial", text="Financial")

            self.students_tree.column("student_id", width=100)
            self.students_tree.column("name", width=200)
            self.students_tree.column("risk_score", width=80)
            self.students_tree.column("risk_level", width=80)
            self.students_tree.column("academic", width=80)
            self.students_tree.column("attendance", width=80)
            self.students_tree.column("engagement", width=80)
            self.students_tree.column("financial", width=80)

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                     command=self.students_tree.yview)
            self.students_tree.configure(yscrollcommand=scrollbar.set)

            self.students_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Buttons
            btn_frame = ttk.Frame(tab)
            btn_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(btn_frame, text=_t("early_warning.calculate_risk_selected", default="Calculate Risk for Selected"),
                      command=self.calculate_selected_risk).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t("early_warning.create_intervention", default="Create Intervention"),
                      command=self.create_intervention).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t("early_warning.assign_coach", default="Assign Coach"),
                      command=self.assign_coach).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t("early_warning.send_alert", default="Send Alert"),
                      command=self.send_alert).pack(side=tk.LEFT, padx=5)

        def create_interventions_tab(self):
            """Create the interventions tab"""
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=_t("early_warning.tabs.interventions", default="Interventions"))

            # Interventions list
            list_frame = ttk.Frame(tab)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ("id", "student_id", "student_name", "type", "priority",
                      "status", "assigned_to", "created", "scheduled")
            self.interventions_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

            for col in columns:
                self.interventions_tree.heading(col, text=col.replace("_", " ").title())
                self.interventions_tree.column(col, width=100)

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                     command=self.interventions_tree.yview)
            self.interventions_tree.configure(yscrollcommand=scrollbar.set)

            self.interventions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Buttons
            btn_frame = ttk.Frame(tab)
            btn_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(btn_frame, text="Refresh",
                      command=self.load_interventions).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Complete Intervention",
                      command=self.complete_intervention).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="View Details",
                      command=self.view_intervention_details).pack(side=tk.LEFT, padx=5)

            self.load_interventions()

        def create_coaching_tab(self):
            """Create the coaching tab"""
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=_t("early_warning.tabs.success_coaching", default="Success Coaching"))

            # Split into two panes
            paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
            paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Left: Coaches list
            coaches_frame = ttk.LabelFrame(paned, text=_t("early_warning.coaches", default="Coaches"), padding=10)
            paned.add(coaches_frame, weight=1)

            columns = ("coach_id", "name", "specialization", "students", "max_students")
            self.coaches_tree = ttk.Treeview(coaches_frame, columns=columns, show="headings")

            self.coaches_tree.heading("coach_id", text="ID")
            self.coaches_tree.heading("name", text="Name")
            self.coaches_tree.heading("specialization", text="Specialization")
            self.coaches_tree.heading("students", text="Students")
            self.coaches_tree.heading("max_students", text="Max")

            for col in columns:
                self.coaches_tree.column(col, width=100)

            self.coaches_tree.pack(fill=tk.BOTH, expand=True)

            coach_btn_frame = ttk.Frame(coaches_frame)
            coach_btn_frame.pack(fill=tk.X, pady=5)
            ttk.Button(coach_btn_frame, text="Register Coach",
                      command=self.register_coach).pack(side=tk.LEFT, padx=5)
            ttk.Button(coach_btn_frame, text="Refresh",
                      command=self.load_coaches).pack(side=tk.LEFT, padx=5)

            # Right: Assignments
            assignments_frame = ttk.LabelFrame(paned, text=_t("early_warning.coach_assignments", default="Coach Assignments"), padding=10)
            paned.add(assignments_frame, weight=1)

            columns = ("student_id", "student_name", "coach_name", "frequency", "last_meeting", "status")
            self.assignments_tree = ttk.Treeview(assignments_frame, columns=columns, show="headings")

            for col in columns:
                self.assignments_tree.heading(col, text=col.replace("_", " ").title())
                self.assignments_tree.column(col, width=100)

            self.assignments_tree.pack(fill=tk.BOTH, expand=True)

            assign_btn_frame = ttk.Frame(assignments_frame)
            assign_btn_frame.pack(fill=tk.X, pady=5)
            ttk.Button(assign_btn_frame, text="Record Progress",
                      command=self.record_progress).pack(side=tk.LEFT, padx=5)
            ttk.Button(assign_btn_frame, text="Refresh",
                      command=self.load_coach_assignments).pack(side=tk.LEFT, padx=5)

            self.load_coaches()
            self.load_coach_assignments()

        def create_tutoring_tab(self):
            """Create the tutoring tab"""
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=_t("early_warning.tabs.tutoring_recommendations", default="Tutoring Recommendations"))

            # Tutoring recommendations list
            list_frame = ttk.Frame(tab)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ("id", "student_id", "student_name", "module", "type",
                      "priority", "status", "tutor", "created")
            self.tutoring_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

            for col in columns:
                self.tutoring_tree.heading(col, text=col.replace("_", " ").title())
                self.tutoring_tree.column(col, width=100)

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                     command=self.tutoring_tree.yview)
            self.tutoring_tree.configure(yscrollcommand=scrollbar.set)

            self.tutoring_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Buttons
            btn_frame = ttk.Frame(tab)
            btn_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(btn_frame, text="Create Recommendation",
                      command=self.create_tutoring_recommendation).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Assign Tutor",
                      command=self.assign_tutor).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text="Refresh",
                      command=self.load_tutoring_recommendations).pack(side=tk.LEFT, padx=5)

            self.load_tutoring_recommendations()

        def create_indicators_tab(self):
            """Create the risk indicators tab"""
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=_t("early_warning.tabs.risk_indicators", default="Risk Indicators"))

            # Indicators list
            list_frame = ttk.Frame(tab)
            list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            columns = ("id", "student_id", "student_name", "type", "value",
                      "severity", "detected", "resolved", "notes")
            self.indicators_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

            for col in columns:
                self.indicators_tree.heading(col, text=col.replace("_", " ").title())
                self.indicators_tree.column(col, width=100)

            scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                     command=self.indicators_tree.yview)
            self.indicators_tree.configure(yscrollcommand=scrollbar.set)

            self.indicators_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Buttons
            btn_frame = ttk.Frame(tab)
            btn_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Button(btn_frame, text=_t("early_warning.buttons.add_indicator", default="Add Indicator"),
                      command=self.add_indicator).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t("early_warning.buttons.resolve_indicator", default="Resolve Indicator"),
                      command=self.resolve_indicator).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text=_t("common.refresh", default="Refresh"),
                      command=self.load_indicators).pack(side=tk.LEFT, padx=5)

            self.load_indicators()

        def load_at_risk_students(self):
            """Load at-risk students based on filter"""
            try:
                for item in self.students_tree.get_children():
                    self.students_tree.delete(item)

                risk_level = self.risk_filter.get().lower()
                if risk_level == "all":
                    students = RiskAssessmentManager.get_at_risk_students("all")
                else:
                    students = RiskAssessmentManager.get_at_risk_students(risk_level)

                for student in students:
                    name = f"{student.get('first_name', '')} {student.get('last_name', '')}"
                    self.students_tree.insert("", tk.END, values=(
                        student['student_id'],
                        name,
                        student.get('overall_risk_score', 0),
                        student.get('risk_level', 'unknown'),
                        student.get('academic_risk_score', 0),
                        student.get('attendance_risk_score', 0),
                        student.get('engagement_risk_score', 0),
                        student.get('financial_risk_score', 0)
                    ))

                self.status_var.set(_t("early_warning.status.loaded_students", default="Loaded {count} at-risk students").format(count=len(students)))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_students_failed", default="Failed to load students: {error}").format(error=e))
                self.status_var.set(_t("common.error", default="Error") + f": {e}")

        def calculate_all_risks(self):
            """Calculate risk scores for all students"""
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT student_id FROM students")
                students = cursor.fetchall()
                conn.close()

                count = 0
                for row in students:
                    student_id = row['student_id'] if isinstance(row, dict) else row[0]
                    try:
                        RiskAssessmentManager.calculate_risk_score(student_id)
                        count += 1
                    except Exception as e:
                        print(f"Error calculating risk for {student_id}: {e}")

                messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.risk_calculated_all", default="Calculated risk scores for {count} students").format(count=count))
                # Set filter to All and show all students with their calculated data
                self.risk_filter.set("All")
                self.load_at_risk_students()
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.calculate_risks_failed", default="Failed to calculate risks: {error}").format(error=e))

        def calculate_selected_risk(self):
            """Calculate risk for selected student"""
            selection = self.students_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_student", default="Please select a student"))
                return

            try:
                student_id = self.students_tree.item(selection[0])['values'][0]
                score, level = RiskAssessmentManager.calculate_risk_score(student_id)
                messagebox.showinfo(_t("early_warning.dialogs.risk_calculated", default="Risk Calculated"),
                                   _t("early_warning.messages.risk_result", default="Student {student_id}\nRisk Score: {score}\nRisk Level: {level}").format(student_id=student_id, score=score, level=level))
                self.load_at_risk_students()
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.calculate_risk_failed", default="Failed to calculate risk: {error}").format(error=e))

        def create_intervention(self):
            """Create a new intervention for selected student"""
            selection = self.students_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_student", default="Please select a student"))
                return

            student_id = self.students_tree.item(selection[0])['values'][0]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("early_warning.dialogs.create_intervention", default="Create Intervention"))
            dialog.geometry("500x400")

            ttk.Label(dialog, text=_t("early_warning.labels.student", default="Student") + f": {student_id}", font=('Arial', 12, 'bold')).pack(pady=10)

            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=_t("early_warning.labels.trigger_type", default="Trigger Type:")).grid(row=0, column=0, sticky=tk.W, pady=5)
            trigger_type = ttk.Combobox(frame, values=["academic", "attendance", "engagement", "financial", "other"])
            trigger_type.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
            trigger_type.set("academic")

            ttk.Label(frame, text=_t("early_warning.labels.intervention_type", default="Intervention Type:")).grid(row=1, column=0, sticky=tk.W, pady=5)
            intervention_type = ttk.Combobox(frame, values=["auto_email", "manual_meeting", "coaching", "tutoring", "counseling"])
            intervention_type.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
            intervention_type.set("coaching")

            ttk.Label(frame, text=_t("early_warning.labels.priority", default="Priority:")).grid(row=2, column=0, sticky=tk.W, pady=5)
            priority = ttk.Combobox(frame, values=["low", "medium", "high", "critical"])
            priority.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
            priority.set("high")

            ttk.Label(frame, text=_t("early_warning.labels.assigned_to", default="Assigned To:")).grid(row=3, column=0, sticky=tk.W, pady=5)
            assigned_to = ttk.Entry(frame)
            assigned_to.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)

            ttk.Label(frame, text=_t("common.description", default="Description:")).grid(row=4, column=0, sticky=tk.W, pady=5)
            description = tk.Text(frame, height=5, width=30)
            description.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5)

            def save():
                try:
                    InterventionManager.create_intervention(
                        student_id=student_id,
                        trigger_type=trigger_type.get(),
                        intervention_type=intervention_type.get(),
                        priority=priority.get(),
                        description=description.get("1.0", tk.END).strip(),
                        assigned_to=assigned_to.get()
                    )
                    messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.intervention_created", default="Intervention created successfully"))
                    dialog.destroy()
                    self.load_interventions()
                except Exception as e:
                    messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.create_intervention_failed", default="Failed to create intervention: {error}").format(error=e))

            ttk.Button(dialog, text=_t("common.save", default="Save"), command=save).pack(side=tk.LEFT, padx=20, pady=10)
            ttk.Button(dialog, text=_t("common.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=20, pady=10)

        def assign_coach(self):
            """Assign a coach to selected student"""
            selection = self.students_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_student", default="Please select a student"))
                return

            student_id = self.students_tree.item(selection[0])['values'][0]

            # Get available coaches
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT coach_id, name FROM early_warning_coaches WHERE status = 'active'")
                coaches = cursor.fetchall()
                conn.close()

                if not coaches:
                    messagebox.showwarning(_t("early_warning.dialogs.no_coaches", default="No Coaches"), _t("early_warning.warnings.no_coaches_available", default="No active coaches available. Please register a coach first."))
                    return

                # Create dialog
                dialog = tk.Toplevel(self.root)
                dialog.title(_t("early_warning.dialogs.assign_coach", default="Assign Coach"))
                dialog.geometry("400x300")

                frame = ttk.Frame(dialog, padding=20)
                frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(frame, text=_t("early_warning.labels.student", default="Student") + f": {student_id}", font=('Arial', 12, 'bold')).pack(pady=10)

                ttk.Label(frame, text=_t("early_warning.labels.select_coach", default="Select Coach:")).pack(anchor=tk.W, pady=5)
                coach_var = tk.StringVar()
                coach_combo = ttk.Combobox(frame, textvariable=coach_var, state="readonly")
                coach_combo['values'] = [f"{c['coach_id']}: {c['name']}" for c in coaches]
                coach_combo.pack(fill=tk.X, pady=5)

                ttk.Label(frame, text=_t("early_warning.labels.meeting_frequency", default="Meeting Frequency:")).pack(anchor=tk.W, pady=5)
                frequency = ttk.Combobox(frame, values=["weekly", "bi-weekly", "monthly"])
                frequency.set("weekly")
                frequency.pack(fill=tk.X, pady=5)

                ttk.Label(frame, text=_t("early_warning.labels.reason", default="Reason:")).pack(anchor=tk.W, pady=5)
                reason = tk.Text(frame, height=4)
                reason.pack(fill=tk.X, pady=5)

                def save():
                    if not coach_var.get():
                        messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_coach", default="Please select a coach"))
                        return

                    coach_id = int(coach_var.get().split(":")[0])
                    try:
                        CoachingManager.assign_student_to_coach(
                            student_id=student_id,
                            coach_id=coach_id,
                            reason=reason.get("1.0", tk.END).strip(),
                            meeting_frequency=frequency.get()
                        )
                        messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.coach_assigned", default="Coach assigned successfully"))
                        dialog.destroy()
                        self.load_coach_assignments()
                    except Exception as e:
                        messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.assign_coach_failed", default="Failed to assign coach: {error}").format(error=e))

                ttk.Button(dialog, text=_t("early_warning.buttons.assign", default="Assign"), command=save).pack(side=tk.LEFT, padx=20, pady=10)
                ttk.Button(dialog, text=_t("common.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=20, pady=10)

            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_coaches_failed", default="Failed to load coaches: {error}").format(error=e))

        def send_alert(self):
            """Send alert notification to selected student"""
            selection = self.students_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_student", default="Please select a student"))
                return

            student_id = self.students_tree.item(selection[0])['values'][0]

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT email_address, first_name FROM students WHERE student_id = ?", (student_id,))
                student = cursor.fetchone()
                conn.close()

                if not student:
                    messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.student_not_found", default="Student not found"))
                    return

                email = student['email_address'] if isinstance(student, dict) else student[1]
                name = student['first_name'] if isinstance(student, dict) else student[0]

                if HAS_EMAIL:
                    subject, body = render_template('student_support_available', {
                        'name': name
                    })

                    send_email(email, subject, body)
                    messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.alert_sent", default="Alert sent to {email}").format(email=email))
                else:
                    messagebox.showinfo(_t("early_warning.dialogs.email_not_configured", default="Email Not Configured"),
                                       _t("early_warning.messages.email_would_be_sent", default="Email service not available. Alert would be sent to: {email}").format(email=email))

            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.send_alert_failed", default="Failed to send alert: {error}").format(error=e))

        def load_interventions(self):
            """Load all interventions"""
            try:
                for item in self.interventions_tree.get_children():
                    self.interventions_tree.delete(item)

                interventions = InterventionManager.get_pending_interventions()

                for intervention in interventions:
                    name = f"{intervention.get('first_name', '')} {intervention.get('last_name', '')}"
                    self.interventions_tree.insert("", tk.END, values=(
                        intervention['intervention_id'],
                        intervention['student_id'],
                        name,
                        intervention['intervention_type'],
                        intervention['priority'],
                        intervention['status'],
                        intervention.get('assigned_to', ''),
                        intervention.get('created_at', '')[:10] if intervention.get('created_at') else '',
                        intervention.get('scheduled_date', '')
                    ))

                self.status_var.set(_t("early_warning.status.loaded_interventions", default="Loaded {count} interventions").format(count=len(interventions)))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_interventions_failed", default="Failed to load interventions: {error}").format(error=e))

        def complete_intervention(self):
            """Mark intervention as completed"""
            selection = self.interventions_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_intervention", default="Please select an intervention"))
                return

            intervention_id = self.interventions_tree.item(selection[0])['values'][0]

            # Create dialog
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("early_warning.dialogs.complete_intervention", default="Complete Intervention"))
            dialog.geometry("400x250")

            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=_t("early_warning.labels.outcome", default="Outcome:")).pack(anchor=tk.W, pady=5)
            outcome = ttk.Combobox(frame, values=["successful", "partially_successful", "unsuccessful", "no_response"])
            outcome.set("successful")
            outcome.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("common.notes", default="Notes:")).pack(anchor=tk.W, pady=5)
            notes = tk.Text(frame, height=5)
            notes.pack(fill=tk.X, pady=5)

            def save():
                try:
                    InterventionManager.complete_intervention(
                        intervention_id=intervention_id,
                        outcome=outcome.get(),
                        notes=notes.get("1.0", tk.END).strip()
                    )
                    messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.intervention_completed", default="Intervention marked as completed"))
                    dialog.destroy()
                    self.load_interventions()
                except Exception as e:
                    messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.complete_intervention_failed", default="Failed to complete intervention: {error}").format(error=e))

            ttk.Button(dialog, text=_t("common.save", default="Save"), command=save).pack(side=tk.LEFT, padx=20, pady=10)
            ttk.Button(dialog, text=_t("common.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=20, pady=10)

        def view_intervention_details(self):
            """View detailed intervention information"""
            selection = self.interventions_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_intervention", default="Please select an intervention"))
                return

            values = self.interventions_tree.item(selection[0])['values']

            details = _t("early_warning.dialogs.intervention_details_content", default="""Intervention Details:

ID: {id}
Student ID: {student_id}
Student Name: {student_name}
Type: {type}
Priority: {priority}
Status: {status}
Assigned To: {assigned_to}
Created: {created}
Scheduled: {scheduled}""").format(
                id=values[0],
                student_id=values[1],
                student_name=values[2],
                type=values[3],
                priority=values[4],
                status=values[5],
                assigned_to=values[6],
                created=values[7],
                scheduled=values[8]
            )

            messagebox.showinfo(_t("early_warning.dialogs.intervention_details", default="Intervention Details"), details)

        def load_coaches(self):
            """Load all coaches"""
            try:
                for item in self.coaches_tree.get_children():
                    self.coaches_tree.delete(item)

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT c.coach_id, c.name, c.specialization, c.max_students,
                           COUNT(ca.assignment_id) as current_students
                    FROM early_warning_coaches c
                    LEFT JOIN early_warning_coaching_assignments ca
                        ON c.coach_id = ca.coach_id AND ca.status = 'active'
                    GROUP BY c.coach_id
                ''')
                coaches = cursor.fetchall()
                conn.close()

                for coach in coaches:
                    self.coaches_tree.insert("", tk.END, values=(
                        coach['coach_id'] if isinstance(coach, dict) else coach[0],
                        coach['name'] if isinstance(coach, dict) else coach[1],
                        coach['specialization'] if isinstance(coach, dict) else coach[2],
                        coach['current_students'] if isinstance(coach, dict) else coach[4],
                        coach['max_students'] if isinstance(coach, dict) else coach[3]
                    ))

                self.status_var.set(_t("early_warning.status.loaded_coaches", default="Loaded {count} coaches").format(count=len(coaches)))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_coaches_failed", default="Failed to load coaches: {error}").format(error=e))

        def register_coach(self):
            """Register a new success coach"""
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("early_warning.dialogs.register_coach", default="Register Coach"))
            dialog.geometry("400x300")

            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=_t("early_warning.labels.user_id", default="User ID:")).pack(anchor=tk.W, pady=5)
            user_id = ttk.Entry(frame)
            user_id.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("common.name", default="Name:")).pack(anchor=tk.W, pady=5)
            name = ttk.Entry(frame)
            name.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("early_warning.labels.specialization", default="Specialization:")).pack(anchor=tk.W, pady=5)
            specialization = ttk.Entry(frame)
            specialization.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("early_warning.labels.max_students", default="Max Students:")).pack(anchor=tk.W, pady=5)
            max_students = ttk.Spinbox(frame, from_=1, to=100, value=30)
            max_students.pack(fill=tk.X, pady=5)

            def save():
                try:
                    CoachingManager.register_coach(
                        user_id=user_id.get(),
                        name=name.get(),
                        specialization=specialization.get(),
                        max_students=int(max_students.get())
                    )
                    messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.coach_registered", default="Coach registered successfully"))
                    dialog.destroy()
                    self.load_coaches()
                except Exception as e:
                    messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.register_coach_failed", default="Failed to register coach: {error}").format(error=e))

            ttk.Button(dialog, text=_t("early_warning.buttons.register", default="Register"), command=save).pack(side=tk.LEFT, padx=20, pady=10)
            ttk.Button(dialog, text=_t("common.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=20, pady=10)

        def load_coach_assignments(self):
            """Load all coach assignments"""
            try:
                for item in self.assignments_tree.get_children():
                    self.assignments_tree.delete(item)

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT ca.*, s.first_name, s.last_name, c.name as coach_name
                    FROM early_warning_coaching_assignments ca
                    JOIN students s ON ca.student_id = s.student_id
                    JOIN early_warning_coaches c ON ca.coach_id = c.coach_id
                    WHERE ca.status = 'active'
                    ORDER BY ca.assigned_date DESC
                ''')
                assignments = cursor.fetchall()
                conn.close()

                for assignment in assignments:
                    student_name = f"{assignment['first_name']} {assignment['last_name']}" if isinstance(assignment, dict) else f"{assignment[1]} {assignment[2]}"
                    self.assignments_tree.insert("", tk.END, values=(
                        assignment['student_id'] if isinstance(assignment, dict) else assignment[0],
                        student_name,
                        assignment['coach_name'] if isinstance(assignment, dict) else assignment[3],
                        assignment['meeting_frequency'] if isinstance(assignment, dict) else assignment[4],
                        assignment.get('last_meeting_date', '') if isinstance(assignment, dict) else '',
                        assignment['status'] if isinstance(assignment, dict) else assignment[5]
                    ))

                self.status_var.set(_t("early_warning.status.loaded_assignments", default="Loaded {count} coach assignments").format(count=len(assignments)))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_assignments_failed", default="Failed to load assignments: {error}").format(error=e))

        def record_progress(self):
            """Record progress for a coaching assignment"""
            selection = self.assignments_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_assignment", default="Please select an assignment"))
                return

            values = self.assignments_tree.item(selection[0])['values']
            student_id = values[0]

            # Get coach_id
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT coach_id FROM early_warning_coaching_assignments
                    WHERE student_id = ? AND status = 'active'
                ''', (student_id,))
                result = cursor.fetchone()
                conn.close()

                if not result:
                    messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.assignment_not_found", default="Assignment not found"))
                    return

                coach_id = result['coach_id'] if isinstance(result, dict) else result[0]

                # Create dialog
                dialog = tk.Toplevel(self.root)
                dialog.title(_t("early_warning.dialogs.record_progress", default="Record Progress"))
                dialog.geometry("500x600")

                frame = ttk.Frame(dialog, padding=20)
                frame.pack(fill=tk.BOTH, expand=True)

                ttk.Label(frame, text=_t("early_warning.labels.student", default="Student") + f": {student_id}", font=('Arial', 12, 'bold')).pack(pady=10)

                ttk.Label(frame, text=_t("early_warning.labels.academic_progress", default="Academic Progress:")).pack(anchor=tk.W, pady=5)
                academic = tk.Text(frame, height=3)
                academic.pack(fill=tk.X, pady=5)

                ttk.Label(frame, text=_t("early_warning.labels.attendance_progress", default="Attendance Progress:")).pack(anchor=tk.W, pady=5)
                attendance = tk.Text(frame, height=3)
                attendance.pack(fill=tk.X, pady=5)

                ttk.Label(frame, text=_t("early_warning.labels.engagement_progress", default="Engagement Progress:")).pack(anchor=tk.W, pady=5)
                engagement = tk.Text(frame, height=3)
                engagement.pack(fill=tk.X, pady=5)

                ttk.Label(frame, text=_t("early_warning.labels.goals_achieved", default="Goals Achieved:")).pack(anchor=tk.W, pady=5)
                goals = tk.Text(frame, height=2)
                goals.pack(fill=tk.X, pady=5)

                ttk.Label(frame, text=_t("early_warning.labels.concerns", default="Concerns:")).pack(anchor=tk.W, pady=5)
                concerns = tk.Text(frame, height=2)
                concerns.pack(fill=tk.X, pady=5)

                ttk.Label(frame, text=_t("early_warning.labels.next_steps", default="Next Steps:")).pack(anchor=tk.W, pady=5)
                next_steps = tk.Text(frame, height=2)
                next_steps.pack(fill=tk.X, pady=5)

                def save():
                    try:
                        CoachingManager.record_progress(
                            student_id=student_id,
                            coach_id=coach_id,
                            academic_progress=academic.get("1.0", tk.END).strip(),
                            attendance_progress=attendance.get("1.0", tk.END).strip(),
                            engagement_progress=engagement.get("1.0", tk.END).strip(),
                            goals_achieved=goals.get("1.0", tk.END).strip(),
                            concerns=concerns.get("1.0", tk.END).strip(),
                            next_steps=next_steps.get("1.0", tk.END).strip()
                        )
                        messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.progress_recorded", default="Progress recorded successfully"))
                        dialog.destroy()
                        self.load_coach_assignments()
                    except Exception as e:
                        messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.record_progress_failed", default="Failed to record progress: {error}").format(error=e))

                ttk.Button(dialog, text=_t("common.save", default="Save"), command=save).pack(side=tk.LEFT, padx=20, pady=10)
                ttk.Button(dialog, text=_t("common.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=20, pady=10)

            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_assignment_failed", default="Failed to load assignment: {error}").format(error=e))

        def load_tutoring_recommendations(self):
            """Load all tutoring recommendations"""
            try:
                for item in self.tutoring_tree.get_children():
                    self.tutoring_tree.delete(item)

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT tr.*, s.first_name, s.last_name
                    FROM early_warning_tutoring_recommendations tr
                    JOIN students s ON tr.student_id = s.student_id
                    ORDER BY tr.created_at DESC
                ''')
                recommendations = cursor.fetchall()
                conn.close()

                for rec in recommendations:
                    student_name = f"{rec['first_name']} {rec['last_name']}" if isinstance(rec, dict) else f"{rec[1]} {rec[2]}"
                    self.tutoring_tree.insert("", tk.END, values=(
                        rec['recommendation_id'] if isinstance(rec, dict) else rec[0],
                        rec['student_id'] if isinstance(rec, dict) else rec[1],
                        student_name,
                        rec['module_code'] if isinstance(rec, dict) else rec[2],
                        rec['recommendation_type'] if isinstance(rec, dict) else rec[3],
                        rec['priority'] if isinstance(rec, dict) else rec[4],
                        rec['status'] if isinstance(rec, dict) else rec[5],
                        rec.get('tutor_assigned', '') if isinstance(rec, dict) else '',
                        rec.get('created_at', '')[:10] if isinstance(rec, dict) and rec.get('created_at') else ''
                    ))

                self.status_var.set(_t("early_warning.status.loaded_recommendations", default="Loaded {count} tutoring recommendations").format(count=len(recommendations)))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_recommendations_failed", default="Failed to load recommendations: {error}").format(error=e))

        def create_tutoring_recommendation(self):
            """Create a new tutoring recommendation"""
            dialog = tk.Toplevel(self.root)
            dialog.title(_t("early_warning.dialogs.create_tutoring_recommendation", default="Create Tutoring Recommendation"))
            dialog.geometry("400x350")

            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(frame, text=_t("early_warning.labels.student_id", default="Student ID:")).pack(anchor=tk.W, pady=5)
            student_id = ttk.Entry(frame)
            student_id.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("early_warning.labels.module_code", default="Module Code:")).pack(anchor=tk.W, pady=5)
            module_code = ttk.Entry(frame)
            module_code.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("early_warning.labels.recommendation_type", default="Recommendation Type:")).pack(anchor=tk.W, pady=5)
            rec_type = ttk.Combobox(frame, values=["one-on-one", "group_tutoring", "study_group", "online_resources"])
            rec_type.set("one-on-one")
            rec_type.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("early_warning.labels.priority", default="Priority:")).pack(anchor=tk.W, pady=5)
            priority = ttk.Combobox(frame, values=["low", "medium", "high"])
            priority.set("medium")
            priority.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text=_t("early_warning.labels.recommended_by", default="Recommended By:")).pack(anchor=tk.W, pady=5)
            recommended_by = ttk.Entry(frame)
            recommended_by.insert(0, self.current_user.get('username', 'system'))
            recommended_by.pack(fill=tk.X, pady=5)

            def save():
                try:
                    TutoringManager.create_tutoring_recommendation(
                        student_id=student_id.get(),
                        module_code=module_code.get(),
                        recommended_by=recommended_by.get(),
                        recommendation_type=rec_type.get(),
                        priority=priority.get()
                    )
                    messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.recommendation_created", default="Tutoring recommendation created successfully"))
                    dialog.destroy()
                    self.load_tutoring_recommendations()
                except Exception as e:
                    messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.create_recommendation_failed", default="Failed to create recommendation: {error}").format(error=e))

            ttk.Button(dialog, text=_t("common.create", default="Create"), command=save).pack(side=tk.LEFT, padx=20, pady=10)
            ttk.Button(dialog, text=_t("common.cancel", default="Cancel"), command=dialog.destroy).pack(side=tk.RIGHT, padx=20, pady=10)

        def assign_tutor(self):
            """Assign a tutor to a recommendation"""
            selection = self.tutoring_tree.selection()
            if not selection:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t("early_warning.warnings.select_recommendation", default="Please select a recommendation"))
                return

            recommendation_id = self.tutoring_tree.item(selection[0])['values'][0]

            tutor_name = simpledialog.askstring(_t("early_warning.dialogs.assign_tutor", default="Assign Tutor"), _t("early_warning.prompts.enter_tutor_name", default="Enter tutor name:"))
            if tutor_name:
                try:
                    TutoringManager.assign_tutor(recommendation_id, tutor_name)
                    messagebox.showinfo(_t("common.success", default="Success"), _t("early_warning.messages.tutor_assigned", default="Tutor assigned successfully"))
                    self.load_tutoring_recommendations()
                except Exception as e:
                    messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.assign_tutor_failed", default="Failed to assign tutor: {error}").format(error=e))

        def load_indicators(self):
            """Load all risk indicators"""
            try:
                for item in self.indicators_tree.get_children():
                    self.indicators_tree.delete(item)

                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT i.*, s.first_name, s.last_name
                    FROM early_warning_indicators i
                    JOIN students s ON i.student_id = s.student_id
                    ORDER BY i.detected_at DESC
                    LIMIT 500
                ''')
                indicators = cursor.fetchall()
                conn.close()

                for ind in indicators:
                    student_name = f"{ind['first_name']} {ind['last_name']}" if isinstance(ind, dict) else f"{ind[1]} {ind[2]}"
                    self.indicators_tree.insert("", tk.END, values=(
                        ind['indicator_id'] if isinstance(ind, dict) else ind[0],
                        ind['student_id'] if isinstance(ind, dict) else ind[1],
                        student_name,
                        ind['indicator_type'] if isinstance(ind, dict) else ind[2],
                        ind['indicator_value'] if isinstance(ind, dict) else ind[3],
                        ind['severity'] if isinstance(ind, dict) else ind[4],
                        ind.get('detected_at', '')[:10] if isinstance(ind, dict) and ind.get('detected_at') else '',
                        _t("common.yes", default="Yes") if (ind['is_resolved'] if isinstance(ind, dict) else ind[5]) else _t("common.no", default="No"),
                        ind.get('notes', '') if isinstance(ind, dict) else ''
                    ))

                self.status_var.set(_t("early_warning.status.loaded_indicators", default="Loaded {count} risk indicators").format(count=len(indicators)))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("early_warning.errors.load_indicators_failed", default="Failed to load indicators: {error}").format(error=e))

        def add_indicator(self):
            """Add a new risk indicator"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Add Risk Indicator")
            dialog.geometry("400x450")

            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill=tk.BOTH, expand=True)

            # Get list of valid students for dropdown
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT student_id, first_name, last_name FROM students ORDER BY last_name, first_name")
                students = cursor.fetchall()
                conn.close()
                student_list = [f"{s[0]} - {s[1]} {s[2]}" for s in students]
            except Exception:
                student_list = []

            ttk.Label(frame, text="Select Student:").pack(anchor=tk.W, pady=5)
            student_var = tk.StringVar()
            student_combo = ttk.Combobox(frame, textvariable=student_var, values=student_list, width=40)
            student_combo.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text="Indicator Type:").pack(anchor=tk.W, pady=5)
            ind_type = ttk.Combobox(frame, values=["academic", "attendance", "engagement", "financial", "behavioral", "health"])
            ind_type.set("academic")
            ind_type.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text="Indicator Value:").pack(anchor=tk.W, pady=5)
            ind_value = ttk.Entry(frame)
            ind_value.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text="Severity:").pack(anchor=tk.W, pady=5)
            severity = ttk.Combobox(frame, values=["low", "medium", "high", "critical"])
            severity.set("medium")
            severity.pack(fill=tk.X, pady=5)

            ttk.Label(frame, text="Notes:").pack(anchor=tk.W, pady=5)
            notes = tk.Text(frame, height=5)
            notes.pack(fill=tk.X, pady=5)

            def save():
                selected = student_var.get()
                if not selected:
                    messagebox.showwarning("Warning", "Please select a student")
                    return

                # Extract student_id from selection (format: "ID - Name")
                student_id = selected.split(" - ")[0].strip()

                if not ind_value.get().strip():
                    messagebox.showwarning("Warning", "Please enter an indicator value")
                    return

                try:
                    IndicatorManager.add_indicator(
                        student_id=student_id,
                        indicator_type=ind_type.get(),
                        indicator_value=ind_value.get(),
                        severity=severity.get(),
                        notes=notes.get("1.0", tk.END).strip()
                    )
                    messagebox.showinfo("Success", "Indicator added successfully")
                    dialog.destroy()
                    self.load_indicators()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to add indicator: {e}")

            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, pady=10)
            ttk.Button(btn_frame, text="Add", command=save).pack(side=tk.LEFT, padx=20)
            ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=20)

        def resolve_indicator(self):
            """Resolve a risk indicator"""
            selection = self.indicators_tree.selection()
            if not selection:
                messagebox.showwarning("Warning", "Please select an indicator")
                return

            indicator_id = self.indicators_tree.item(selection[0])['values'][0]

            notes = simpledialog.askstring("Resolve Indicator", "Enter resolution notes:")
            if notes:
                try:
                    IndicatorManager.resolve_indicator(indicator_id, notes)
                    messagebox.showinfo("Success", "Indicator resolved successfully")
                    self.load_indicators()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to resolve indicator: {e}")

        def return_to_homescreen(self):
            """Close this window and return to the main menu"""
            try:
                self.root.destroy()
            except Exception as e:
                print(f"Error returning to homescreen: {e}")

    # Create and launch the GUI
    try:
        app = EarlyWarningGUI(root, auth)
        print("✅ Student Success Early Warning System GUI opened successfully")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Early Warning System: {str(e)}")
        print(f"❌ Early Warning System error: {e}")



__all__ = [
    'RiskAssessmentManager',
    'IndicatorManager',
    'InterventionManager',
    'CoachingManager',
    'TutoringManager',
    'display_early_warning_menu',
    'launch_early_warning_gui',
]
