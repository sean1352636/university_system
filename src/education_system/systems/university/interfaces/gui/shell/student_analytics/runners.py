"""Run/dispatch mixin for the Student Analytics GUI."""
from education_system.systems.university.interfaces.gui.shell.student_analytics._imports import tk, ttk, messagebox, _t


class RunnersMixin:
    """Mixin providing thread dispatch wrappers and status updates."""

    def run_analysis_thread(self, analysis_func, analysis_name):
        """Run analysis in main thread to avoid matplotlib threading issues"""
        try:
            self.update_status(f"Running {analysis_name}...")
            self.progress.start()
            self.root.update()  # Process pending events

            # Run analysis in main thread (not daemon thread)
            # This prevents matplotlib from crashing
            result = analysis_func()

            # If result is a dictionary with GUI data, display it in a GUI window
            if isinstance(result, dict) and 'figure' in result:
                self.display_results_window(
                    result.get('title', analysis_name),
                    result.get('summary', ''),
                    result.get('figure')
                )
            else:
                # Old-style analysis that doesn't return data
                self.update_status(_t("analytics.status.completed", name=analysis_name))
                messagebox.showinfo(_t("analytics.dialogs.analysis_complete"),
                                  _t("analytics.messages.analysis_completed", name=analysis_name))
        except Exception as e:
            import traceback
            error_msg = f"Error in {analysis_name}: {str(e)}\n\n{traceback.format_exc()}"
            self.update_status(_t("analytics.status.error", name=analysis_name))
            messagebox.showerror(_t("analytics.dialogs.analysis_error"), error_msg)
            print(error_msg)
        finally:
            self.progress.stop()

    def update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=message)
        self.root.update_idletasks()

    def refresh_stats(self):
        """Refresh the quick stats in header"""
        try:
            students_df = self.analytics.get_all_students()

            if not students_df.empty:
                total_students = len(students_df)
                avg_gpa = students_df['gpa'].mean()
                completion_rate = (students_df['completion_status'] == 'Completed').mean() * 100
                at_risk = (students_df['gpa'] < 2.0).sum()

                self.stats_labels['total_students'].config(text=f"{total_students}")
                self.stats_labels['avg_gpa'].config(text=f"{avg_gpa:.2f}")
                self.stats_labels['completion_rate'].config(text=f"{completion_rate:.1f}%")
                self.stats_labels['at_risk'].config(text=f"{at_risk}")
            else:
                for label in self.stats_labels.values():
                    label.config(text=_t("common.no_data"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("analytics.error.refresh_stats", error=str(e)))

    # Analysis method wrappers
    def run_demographics(self):
        self.run_analysis_thread(self.analytics.analyze_student_demographics, "Student Demographics")

    def run_module_popularity(self):
        self.run_analysis_thread(self.analytics.analyze_module_popularity, "Module Popularity")

    def run_course_enrollments(self):
        self.run_analysis_thread(self.analytics.analyze_course_enrollments, "Course Enrollments")

    def run_registration_timeline(self):
        self.run_analysis_thread(self.analytics.analyze_registration_timeline, "Registration Timeline")

    def run_grade_distribution(self):
        self.run_analysis_thread(self.analytics.analyze_grade_distribution, "Grade Distribution")

    def run_academic_risk(self):
        self.run_analysis_thread(self.analytics.analyze_academic_risk, "Academic Risk Assessment")

    def run_module_difficulty(self):
        self.run_analysis_thread(self.analytics.analyze_module_difficulty, "Module Difficulty")

    def run_performance_trends(self):
        self.run_analysis_thread(self.analytics.analyze_performance_trends, "Performance Trends")

    def run_correlations(self):
        self.run_analysis_thread(self.analytics.analyze_correlations, "Correlation Analysis")

    def run_cohorts(self):
        self.run_analysis_thread(self.analytics.analyze_cohorts, "Cohort Analysis")

    def run_engagement(self):
        self.run_analysis_thread(self.analytics.analyze_engagement, "Engagement Analysis")

    def run_predictive(self):
        self.run_analysis_thread(self.analytics.predictive_analytics, "Predictive Analytics")

    def run_complete_report(self):
        self.run_analysis_thread(self.analytics.generate_complete_report, "Complete Report")

    def run_custom_report(self):
        self.show_custom_report_dialog()

    def run_email_reports(self):
        self.run_analysis_thread(self.analytics.email_reports, "Email Reports")

    def run_export(self, export_type):
        if export_type == 'excel':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('1'), "Excel Export")
        elif export_type == 'csv':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('2'), "CSV Export")
        elif export_type == 'json':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('3'), "JSON Export")
        elif export_type == 'summary':
            self.run_analysis_thread(lambda: self.analytics.export_data_choice('4'), "Summary Export")

    def run_data_quality(self):
        self.run_analysis_thread(self.analytics.data_quality_check, "Data Quality Check")
