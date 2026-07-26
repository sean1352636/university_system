from tkinter import messagebox, simpledialog
import threading

from education_system.systems.university.infrastructure.i18n import get_text as _

from education_system.systems.university.interfaces.gui.academics.grade_tracking_management_gui._imports import (
    PREDICTIVE_ANALYTICS_AVAILABLE,
    identify_at_risk_students,
    calculate_risk_factors,
    early_warning_system,
    generate_early_warning_alert,
    export_at_risk_students,
    export_early_warning_alerts,
    export_dropout_risk_list,
    build_at_risk_prediction_model,
    analyze_dropout_risk_factors,
    build_dropout_prediction_model,
    generate_dropout_interventions,
    generate_dropout_intervention_plan,
    identify_high_dropout_risk,
    calculate_dropout_risk_score,
    generate_risk_report,
    collect_comprehensive_risk_data,
    generate_comprehensive_risk_report,
)


class PredictiveAnalyticsMixin:
    # Predictive Analytics Functions
    def identify_at_risk_students_gui(self):
        """Identify students at risk of academic failure"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.risk.login_required_identify"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror(_("common.error"), _("grades.risk.no_permission_identify"))
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=identify_at_risk_students, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.risk.identify_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.risk.failed_identify").format(error=str(e)))
            print(f"Identify at-risk students error: {e}")

    def calculate_risk_factors_gui(self, student_id=None):
        """Calculate risk factors for a student"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.risk.login_required_calculate"))
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        _("grades.dialogs.student_id_title"),
                        _("grades.dialogs.enter_student_id"),
                        parent=self.root
                    )

                    if not student_id:
                        return

                def calculate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        risk_score, risk_factors = calculate_risk_factors(cursor, student_id)
                        print(f"Risk Score: {risk_score}")
                        print(f"Risk Factors: {risk_factors}")
                        conn.close()
                    except Exception as e:
                        print(f"Error calculating risk factors: {e}")

                thread = threading.Thread(target=calculate, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.risk.calculate_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.risk.failed_calculate").format(error=str(e)))
            print(f"Calculate risk factors error: {e}")

    def early_warning_system_gui(self):
        """Implement early warning system for at-risk students"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.risk.login_required_warning"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror(_("common.error"), _("grades.risk.no_permission_warning"))
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=early_warning_system, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.risk.warning_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.risk.failed_warning").format(error=str(e)))
            print(f"Early warning system error: {e}")

    def generate_early_warning_alert_gui(self, student_id=None):
        """Generate early warning alert for a student"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.risk.login_required_alert"))
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('generate_alerts')):
            messagebox.showerror(_("common.error"), _("grades.risk.no_permission_alert"))
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        _("grades.dialogs.student_id_title"),
                        _("grades.dialogs.enter_student_id"),
                        parent=self.root
                    )

                    if not student_id:
                        return

                def generate_alert():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        # Fetch student details
                        cursor.execute(
                            "SELECT first_name, last_name, course, email_address FROM students WHERE student_id = ?",
                            (student_id,)
                        )
                        result = cursor.fetchone()

                        if not result:
                            print(f"Student {student_id} not found in database")
                            conn.close()
                            return

                        first_name, last_name, course, email = result

                        # Calculate risk
                        risk_score, _ = calculate_risk_factors(cursor, student_id)

                        # Determine risk level
                        if risk_score >= 70:
                            risk_level = "High"
                        elif risk_score >= 40:
                            risk_level = "Medium"
                        else:
                            risk_level = "Low"

                        generate_early_warning_alert(cursor, student_id, first_name, last_name, course, email, risk_score, risk_level)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating early warning alert: {e}")

                thread = threading.Thread(target=generate_alert, daemon=True)
                thread.start()
            else:
                messagebox.showerror(_("common.error"), _("grades.risk.alert_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.risk.failed_alert").format(error=str(e)))
            print(f"Generate early warning alert error: {e}")

    def export_at_risk_students_gui(self, at_risk_students=None, threshold=None):
        """Export at-risk students list to file"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.export.login_required_risk"))
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if at_risk_students and threshold is not None:
                    export_at_risk_students(at_risk_students, threshold)
                    messagebox.showinfo(_("common.success"), _("grades.export.risk_students_exported"))
                else:
                    messagebox.showinfo(_("common.info"), _("grades.export.identify_risk_first"))
            else:
                messagebox.showerror(_("common.error"), _("grades.export.risk_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.export.failed_risk").format(error=str(e)))
            print(f"Export at-risk students error: {e}")

    def export_early_warning_alerts_gui(self, alerts=None):
        """Export early warning alerts to file"""
        if not self.auth.current_user:
            messagebox.showerror(_("common.error"), _("grades.export.login_required_alerts"))
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if alerts:
                    export_early_warning_alerts(alerts)
                    messagebox.showinfo(_("common.success"), _("grades.export.alerts_exported"))
                else:
                    messagebox.showinfo(_("common.info"), _("grades.export.generate_alerts_first"))
            else:
                messagebox.showerror(_("common.error"), _("grades.export.alerts_not_available"))
        except Exception as e:
            messagebox.showerror(_("common.error"), _("grades.export.failed_alerts").format(error=str(e)))
            print(f"Export alerts error: {e}")

    def export_dropout_risk_list_gui(self, high_risk_students=None):
        """Export dropout risk list to file"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to export dropout risk list.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if high_risk_students:
                    export_dropout_risk_list(high_risk_students)
                    messagebox.showinfo("Success", "Dropout risk list exported successfully")
                else:
                    messagebox.showinfo("Info", "Please identify high dropout risk students first.")
            else:
                messagebox.showerror("Error", "Export dropout risk list not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export dropout risk list: {str(e)}")
            print(f"Export dropout risk list error: {e}")

    def build_at_risk_prediction_model_gui(self):
        """Build ML model to predict at-risk students"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to build prediction models.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to build ML models.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def build_model():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        build_at_risk_prediction_model(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error building at-risk prediction model: {e}")

                thread = threading.Thread(target=build_model, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Build at-risk prediction model not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build prediction model: {str(e)}")
            print(f"Build prediction model error: {e}")

    def analyze_dropout_risk_factors_gui(self):
        """Analyze common dropout risk factors"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to analyze dropout risk factors.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to analyze dropout risk factors.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def analyze():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        analyze_dropout_risk_factors(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error analyzing dropout risk factors: {e}")

                thread = threading.Thread(target=analyze, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Analyze dropout risk factors not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to analyze dropout risk factors: {str(e)}")
            print(f"Analyze dropout risk factors error: {e}")

    def build_dropout_prediction_model_gui(self):
        """Build predictive model for dropout risk"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to build dropout prediction model.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('use_ml_models')):
            messagebox.showerror("Error", "You don't have permission to build ML models.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def build_model():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        build_dropout_prediction_model(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error building dropout prediction model: {e}")

                thread = threading.Thread(target=build_model, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Build dropout prediction model not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to build dropout prediction model: {str(e)}")
            print(f"Build dropout prediction model error: {e}")

    def generate_dropout_interventions_gui(self):
        """Generate dropout prevention interventions"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate interventions.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('generate_interventions')):
            messagebox.showerror("Error", "You don't have permission to generate interventions.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def generate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        generate_dropout_interventions(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating dropout interventions: {e}")

                thread = threading.Thread(target=generate, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate dropout interventions not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate interventions: {str(e)}")
            print(f"Generate interventions error: {e}")

    def generate_dropout_intervention_plan_gui(self, student_id=None):
        """Generate individual dropout intervention plan"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate intervention plans.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('generate_interventions')):
            messagebox.showerror("Error", "You don't have permission to generate intervention plans.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
                        parent=self.root
                    )

                    if not student_id:
                        return

                def generate_plan():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()

                        # Fetch student details
                        cursor.execute(
                            "SELECT first_name, last_name, course, email_address FROM students WHERE student_id = ?",
                            (student_id,)
                        )
                        result = cursor.fetchone()

                        if not result:
                            print(f"Student {student_id} not found in database")
                            conn.close()
                            return

                        first_name, last_name, course, email = result
                        generate_dropout_intervention_plan(cursor, student_id, first_name, last_name, course, email)
                        conn.close()
                    except Exception as e:
                        print(f"Error generating intervention plan: {e}")

                thread = threading.Thread(target=generate_plan, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate dropout intervention plan not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate intervention plan: {str(e)}")
            print(f"Generate intervention plan error: {e}")

    def identify_high_dropout_risk_gui(self):
        """Identify students at high risk of dropping out"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to identify high dropout risk students.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_risk_analysis')):
            messagebox.showerror("Error", "You don't have permission to identify high dropout risk students.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                def identify():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        identify_high_dropout_risk(cursor)
                        conn.close()
                    except Exception as e:
                        print(f"Error identifying high dropout risk students: {e}")

                thread = threading.Thread(target=identify, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Identify high dropout risk not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to identify high dropout risk students: {str(e)}")
            print(f"Identify high dropout risk error: {e}")

    def calculate_dropout_risk_score_gui(self, student_id=None):
        """Calculate dropout risk score for a student"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to calculate dropout risk score.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                # If no student_id provided, prompt for one
                if not student_id:
                    student_id = simpledialog.askstring(
                        "Student ID",
                        "Enter Student ID:",
                        parent=self.root
                    )

                    if not student_id:
                        return

                def calculate():
                    try:
                        conn = get_connection()
                        cursor = conn.cursor()
                        risk_score = calculate_dropout_risk_score(cursor, student_id)
                        print(f"Dropout Risk Score for {student_id}: {risk_score}")
                        conn.close()
                    except Exception as e:
                        print(f"Error calculating dropout risk score: {e}")

                thread = threading.Thread(target=calculate, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Calculate dropout risk score not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate dropout risk score: {str(e)}")
            print(f"Calculate dropout risk score error: {e}")

    def generate_risk_report_gui(self):
        """Generate comprehensive risk assessment report"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate risk reports.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror("Error", "You don't have permission to generate risk reports.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                thread = threading.Thread(target=generate_risk_report, daemon=True)
                thread.start()
            else:
                messagebox.showerror("Error", "Generate risk report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate risk report: {str(e)}")
            print(f"Generate risk report error: {e}")

    def collect_comprehensive_risk_data_gui(self):
        """Collect comprehensive risk assessment data"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to collect risk data.")
            return None

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                from education_system.systems.university.infrastructure.database.db import get_connection

                conn = get_connection()
                cursor = conn.cursor()
                risk_data = collect_comprehensive_risk_data(cursor)
                conn.close()
                return risk_data
            else:
                messagebox.showerror("Error", "Collect risk data not available.")
                return None
        except Exception as e:
            messagebox.showerror("Error", f"Failed to collect risk data: {str(e)}")
            print(f"Collect risk data error: {e}")
            return None

    def generate_comprehensive_risk_report_gui(self, risk_data=None):
        """Generate comprehensive risk assessment report"""
        if not self.auth.current_user:
            messagebox.showerror("Error", "You must be logged in to generate comprehensive risk reports.")
            return

        if not (self.auth.check_permission('manage_grades') or
                self.auth.check_permission('view_reports')):
            messagebox.showerror("Error", "You don't have permission to generate comprehensive risk reports.")
            return

        try:
            if PREDICTIVE_ANALYTICS_AVAILABLE:
                if not risk_data:
                    risk_data = self.collect_comprehensive_risk_data_gui()

                if risk_data:
                    def generate():
                        generate_comprehensive_risk_report(risk_data)

                    thread = threading.Thread(target=generate, daemon=True)
                    thread.start()
            else:
                messagebox.showerror("Error", "Generate comprehensive risk report not available.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate comprehensive risk report: {str(e)}")
            print(f"Generate comprehensive risk report error: {e}")
