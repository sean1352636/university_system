"""Extracted demographic-reporting behaviour."""
from . import *

class AdvancedControllerMixin:
    def _refresh_data(self):
        """Refresh data from database"""
        self._generate_full_report()

    def _generate_full_report(self):
        """Generate comprehensive demographic report"""
        try:
            conn = get_connection()
            if conn is None:
                messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.demographics.database_connection_failed"))
                return

            cursor = conn.cursor()

            # Fetch all student data with demographics
            query = """
                SELECT
                    s.student_id,
                    COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '') as full_name,
                    COALESCE(d.gender, s.gender, 'Unknown') as gender,
                    COALESCE(s.age, 0) as age,
                    COALESCE(s.course, 'Unknown') as course,
                    COALESCE(s.status, 'Unknown') as status,
                    COALESCE(d.ethnicity, 'Unknown') as ethnicity,
                    COALESCE(d.academic_level, 'Unknown') as academic_level,
                    COALESCE(d.age_group, 'Unknown') as age_group,
                    s.enrollment_date
                FROM students s
                LEFT JOIN student_demographics d ON s.student_id = d.student_id
            """
            cursor.execute(query)
            self.raw_data = cursor.fetchall()
            conn.close()

            if not self.raw_data:
                messagebox.showinfo(_t("advanced_search.demographics.no_data_title"), _t("advanced_search.demographics.no_data_msg"))
                return

            # Process data for reports
            self._process_demographics()

            # Update all tabs
            self._update_overview()
            self._update_gender_analysis()
            self._update_age_analysis()
            self._update_course_analysis()
            self._update_full_report()

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('generate', 'advanced_demographic_report', details={
                    'total_students': len(self.raw_data)
                })
            except ImportError:
                pass

        except Exception as e:
            messagebox.showerror(_t("advanced_search.error_title"), _t("advanced_search.demographics.failed_to_generate_report", error=str(e)))
